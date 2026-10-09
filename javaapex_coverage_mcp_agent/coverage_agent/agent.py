from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Optional

from .build import BuildRunner
from .jacoco import JaCoCoParser
from .llm import CoverageLLM, FileChange, parse_changes, build_generation_prompt
from .models import (
    CoverageAgentRequest,
    CoverageAgentResult,
    CoverageIteration, CoverageGap,
)
from .project_inspector import ProjectInspector


class JaCoCoCoverageAgent:
    """
    Autonomous JaCoCo coverage engineer for JavaAPEX.

    The agent:
      1. Inspects Maven/Gradle + Java configuration.
      2. Runs baseline JaCoCo.
      3. Parses per-class gaps.
      4. Asks the LLM for targeted test changes.
      5. Writes tests only.
      6. Compiles tests.
      7. Reruns JaCoCo.
      8. Repeats until target or iteration budget is exhausted.
    """

    def __init__(self, llm: CoverageLLM, inspector=None, parser=None):
        self.llm = llm
        self.inspector = inspector or ProjectInspector()
        self.parser = parser or JaCoCoParser()

    async def ensure_coverage(self, request: CoverageAgentRequest) -> CoverageAgentResult:
        project = self.inspector.inspect(
            request.project_dir,
            request.build_tool,
            request.java_version,
        )
        runner = BuildRunner(project.root)

        baseline_cmd = runner.run_coverage(project.build_tool, clean=not request.skip_clean)
        report_path = self._report_path(project.root, project.build_tool)

        initial_coverage = 0.0
        previous_failure = ""
        if not Path(report_path).exists():
            if self._main_compile_broken(baseline_cmd.output):
                return CoverageAgentResult(
                    success=False,
                    target_coverage=request.target_coverage,
                    initial_coverage=0,
                    final_coverage=0,
                    coverage_metric=request.coverage_metric,
                    build_tool=project.build_tool,
                    java_version=project.java_version,
                    failure_reason=(
                        "Production sources under src/main do not compile, so no "
                        "bytecode exists for JaCoCo to measure. The coverage agent "
                        "may only modify test files — fix the main-source "
                        "compilation errors first.\n" + baseline_cmd.output[-10000:]
                    ),
                )
            if not baseline_cmd.ok:
                previous_failure = baseline_cmd.output[-12000:]
            else:
                return CoverageAgentResult(
                    success=False,
                    target_coverage=request.target_coverage,
                    initial_coverage=0,
                    final_coverage=0,
                    coverage_metric=request.coverage_metric,
                    build_tool=project.build_tool,
                    java_version=project.java_version,
                    failure_reason="JaCoCo report was not generated.\n" + baseline_cmd.output[-10000:],
                )
        else:
            initial = self.parser.parse(report_path)
            initial_coverage = self._metric(initial, request.coverage_metric)
            if not baseline_cmd.tests_ok and not request.ignore_test_failures:
                # Report exists (from tolerant execution) but tests are red:
                # enter the loop so the LLM attempts repairs.
                previous_failure = baseline_cmd.output[-12000:]

        if initial_coverage >= request.target_coverage and (
            baseline_cmd.tests_ok or request.ignore_test_failures
        ):
            return CoverageAgentResult(
                success=True,
                target_coverage=request.target_coverage,
                initial_coverage=initial_coverage,
                final_coverage=initial_coverage,
                coverage_metric=request.coverage_metric,
                build_tool=project.build_tool,
                java_version=project.java_version,
                jacoco_report=report_path,
            )

        history = []
        created = 0
        modified = 0
        repairs = 0
        current_coverage = initial_coverage
        best_coverage = initial_coverage

        for iteration in range(1, request.max_iterations + 1):
            if Path(report_path).exists():
                all_gaps = self.parser.gaps(
                    report_path,
                    source_root=(project.source_roots[0] if project.source_roots else None),
                )[:12]
            else:
                all_gaps = [CoverageGap(class_name="CompilationRepair", priority=1.0)]

            if not all_gaps and not previous_failure:
                break

            # Fan-out: one shard per module so every module is improved
            # concurrently with small, focused prompts instead of one blob.
            shards = self._shard_gaps(
                all_gaps,
                depth=request.shard_package_depth,
                max_per_shard=request.max_gaps_per_shard,
                max_shards=request.max_parallel_shards,
            )
            shard_label = "+".join(name for name, _ in shards)

            test_text = self._collect_tests(project)
            # Shard-scoped test context: each shard sees only tests from its
            # own module plus a small shared head. The legacy single-shard
            # path keeps the full global context (behavior unchanged).
            legacy = len(shards) == 1 and shards[0][0] == "all"
            contexts: dict[str, str] = {}
            for name, gap_subset in shards:
                if legacy:
                    contexts[name] = test_text
                else:
                    contexts[name] = self._collect_tests_for_shard(
                        project, name, gap_subset
                    )
            sema = asyncio.Semaphore(max(1, request.max_parallel_shards))

            async def _bounded(name, gaps):
                async with sema:
                    return await self._generate_shard(
                        name, gaps, project, contexts[name], previous_failure
                    )

            shard_results = await asyncio.gather(
                *[_bounded(name, gaps) for name, gaps in shards]
            )

            # Merge with a claim map: the first shard to claim a test file
            # wins; later shards drop that file with a warning.
            claimed: dict[str, str] = {}
            merged: list[tuple[str, FileChange]] = []
            shard_errors: list[str] = []
            for name, changes, raw, error in shard_results:
                if error:
                    shard_errors.append(f"[{name}] {error}")
                for change in changes:
                    key = self._change_key(change, project)
                    if key in claimed:
                        import logging as _log
                        _log.getLogger(__name__).warning(
                            "[CoverageAgent] Shard %s dropped %s (claimed by %s)",
                            name, change.path, claimed[key],
                        )
                        continue
                    claimed[key] = name
                    merged.append((name, change))

            if not merged:
                previous_failure = (
                    "; ".join(shard_errors)[:12000]
                    or "All shards returned no changes"
                )
                history.append(CoverageIteration(
                    iteration=iteration,
                    coverage_before=current_coverage,
                    coverage_after=current_coverage,
                    tests_changed=[],
                    compilation_ok=False,
                    tests_ok=False,
                    build_output=previous_failure,
                    failure="All shards returned no parseable changes",
                    shard=shard_label,
                ))
                continue

            changed_paths = []
            backups = {}  # path -> (original_content or None if new file)
            shard_of: dict = {}  # applied file path -> shard name
            for shard_name, change in merged:
                rel = Path(change.path)
                if rel.is_absolute():
                    target = rel.resolve()
                else:
                    target = (Path(project.root) / rel).resolve()

                if not self._is_test_file(target, project):
                    import logging as _log
                    _log.getLogger(__name__).warning(
                        "[CoverageAgent] Skipping non-test path: %s", target
                    )
                    continue

                # Backup original content before overwriting
                if target.exists():
                    backups[target] = target.read_text(encoding="utf-8", errors="replace")
                else:
                    backups[target] = None  # Mark as newly created

                existed = target.exists()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(change.content, encoding="utf-8")
                changed_paths.append(str(target.relative_to(project.root)))
                shard_of[target] = shard_name

                if existed:
                    modified += 1
                else:
                    created += 1

            compile_result = runner.compile_tests(project.build_tool)

            if not compile_result.ok:
                repairs += 1
                # PARTIAL ROLLBACK: revert only the files javac blames so the
                # good shards' work survives. Full revert only as fallback.
                blamed = [
                    b for b in BuildRunner.blamed_test_files(
                        compile_result.output, project.root
                    ) if b in backups
                ]
                if blamed:
                    for fpath in blamed:
                        original = backups.pop(fpath)
                        shard_of.pop(fpath, None)
                        if original is None:
                            # File was newly created — delete it
                            try:
                                fpath.unlink(missing_ok=True)
                            except Exception:
                                pass
                        else:
                            # Restore original content
                            fpath.write_text(original, encoding="utf-8")
                    changed_paths = [
                        str(f.relative_to(project.root)) for f in backups
                    ]
                    compile_result = runner.compile_tests(project.build_tool)

            if not compile_result.ok:
                # FULL ROLLBACK: Restore original files so next iteration starts clean
                for fpath, original in backups.items():
                    if original is None:
                        # File was newly created — delete it
                        try:
                            fpath.unlink(missing_ok=True)
                        except Exception:
                            pass
                    else:
                        # Restore original content
                        fpath.write_text(original, encoding="utf-8")

                previous_failure = compile_result.output[-12000:]
                history.append(CoverageIteration(
                    iteration=iteration,
                    coverage_before=current_coverage,
                    coverage_after=current_coverage,
                    tests_changed=changed_paths,
                    compilation_ok=False,
                    tests_ok=False,
                    build_output=compile_result.output[-12000:],
                    failure="test compilation failed (changes rolled back)",
                    shard=shard_label,
                ))
                if self._main_compile_broken(compile_result.output):
                    return CoverageAgentResult(
                        success=False,
                        target_coverage=request.target_coverage,
                        initial_coverage=initial_coverage,
                        final_coverage=current_coverage,
                        coverage_metric=request.coverage_metric,
                        build_tool=project.build_tool,
                        java_version=project.java_version,
                        iterations=iteration,
                        tests_created=created,
                        tests_modified=modified,
                        compilation_repairs=repairs,
                        iteration_history=history,
                        jacoco_report=report_path,
                        failure_reason=(
                            "Production sources under src/main do not compile, so "
                            "no bytecode exists for JaCoCo to measure. The coverage "
                            "agent may only modify test files — fix the main-source "
                            "compilation errors first.\n" + compile_result.output[-10000:]
                        ),
                    )
                continue

            verify_result = runner.run_coverage(project.build_tool, clean=False)

            if not Path(report_path).exists():
                previous_failure = verify_result.output[-12000:]
                history.append(CoverageIteration(
                    iteration=iteration,
                    coverage_before=current_coverage,
                    coverage_after=current_coverage,
                    tests_changed=changed_paths,
                    compilation_ok=True,
                    tests_ok=False,
                    build_output=verify_result.output[-12000:],
                    failure="JaCoCo report missing after verification",
                ))
                continue

            parsed = self.parser.parse(report_path)
            new_coverage = self._metric(parsed, request.coverage_metric)
            current_coverage = new_coverage
            best_coverage = max(best_coverage, new_coverage)
            surviving = sorted({shard_of[f] for f in backups if f in shard_of})

            history.append(CoverageIteration(
                iteration=iteration,
                coverage_before=history[-1].coverage_after if history else initial_coverage,
                coverage_after=new_coverage,
                tests_changed=changed_paths,
                compilation_ok=True,
                tests_ok=verify_result.tests_ok,
                build_output=verify_result.output[-12000:],
                shard="+".join(surviving) if surviving else shard_label,
            ))

            coverage_ok = new_coverage >= request.target_coverage
            tests_ok_for_success = verify_result.tests_ok or request.ignore_test_failures
            if coverage_ok and tests_ok_for_success:
                return CoverageAgentResult(
                    success=True,
                    target_coverage=request.target_coverage,
                    initial_coverage=initial_coverage,
                    final_coverage=new_coverage,
                    coverage_metric=request.coverage_metric,
                    build_tool=project.build_tool,
                    java_version=project.java_version,
                    iterations=iteration,
                    tests_created=created,
                    tests_modified=modified,
                    compilation_repairs=repairs,
                    iteration_history=history,
                    remaining_gaps=[],
                    jacoco_report=report_path,
                )

            if not verify_result.tests_ok:
                previous_failure = verify_result.output[-12000:]

        if Path(report_path).exists():
            final_parsed = self.parser.parse(report_path)
            final_coverage = self._metric(final_parsed, request.coverage_metric)
            remaining = self.parser.gaps(
                report_path,
                source_root=(project.source_roots[0] if project.source_roots else None),
            )[:20]
            scan = runner.tests_failed(project.build_tool)
            tests_failing = bool(scan)  # True only with concrete failure evidence
        else:
            final_coverage = best_coverage
            remaining = []
            tests_failing = True

        coverage_ok = final_coverage >= request.target_coverage
        if request.ignore_test_failures:
            success = coverage_ok
        else:
            success = coverage_ok and not tests_failing

        if success:
            failure_reason = None
        elif coverage_ok and tests_failing:
            failure_reason = (
                f"Coverage target reached ({final_coverage:.1f}%) but tests are "
                "failing. Fix the failing tests, or re-run with "
                "ignore_test_failures=True to accept coverage-only success."
            )
        else:
            failure_reason = "Iteration budget exhausted before target coverage was reached."

        return CoverageAgentResult(
            success=success,
            target_coverage=request.target_coverage,
            initial_coverage=initial_coverage,
            final_coverage=final_coverage,
            coverage_metric=request.coverage_metric,
            build_tool=project.build_tool,
            java_version=project.java_version,
            iterations=request.max_iterations,
            tests_created=created,
            tests_modified=modified,
            compilation_repairs=repairs,
            iteration_history=history,
            remaining_gaps=remaining,
            jacoco_report=report_path,
            failure_reason=failure_reason,
        )

    @staticmethod
    def _main_compile_broken(output: str) -> bool:
        """Heuristic: compilation errors pointing at src/main (not tests).

        The agent may only write test files, so broken production sources
        can never be repaired by iterating — fail fast instead.

        Requires an actual ``.java`` file under ``src/main`` on an error
        line; a mere resource-copy mention (e.g. ``src\\main\\resources``)
        alongside a *test* compilation error must not count.
        """
        import re
        lowered = (output or "").lower()
        return bool(re.search(
            r"src[\\/]main[\\/][^\n]*?\.java[^\n]*?error"
            r"|error[^\n]*?src[\\/]main[\\/][^\n]*?\.java",
            lowered,
        ))

    @staticmethod
    def _metric(parsed, metric):
        return parsed.get(f"{metric.upper().lower()}_coverage",
                          parsed.get("line_coverage", 0.0))

    @staticmethod
    def _report_path(root, tool):
        if tool == "maven":
            return str(Path(root) / "target/site/jacoco/jacoco.xml")
        return str(Path(root) / "build/reports/jacoco/test/jacocoTestReport.xml")

    @staticmethod
    def _is_test_file(target: Path, project) -> bool:
        if target.suffix != ".java":
            return False
        roots = [Path(x).resolve() for x in project.test_roots]
        try:
            return any(target.is_relative_to(r) for r in roots)
        except AttributeError:
            return any(str(target).startswith(str(r)) for r in roots)

    @staticmethod
    def _collect_sources(project, gaps):
        chunks = []
        for gap in gaps[:5]:
            p = Path(gap.source_file) if gap.source_file else None
            if p and p.exists():
                text = p.read_text(errors="ignore")
                chunks.append(f"\n===== {p} =====\n{text[:30000]}")
                continue
            # JaCoCo XML only carries the bare filename (e.g.
            # "AttendanceRepository.java"); resolve it by filename search
            # under the known source roots so the LLM gets real context.
            fname = (p.name if p else None) or (
                gap.class_name.split(".")[-1].split("$")[0] + ".java"
            )
            for root in (project.source_roots or []):
                try:
                    hits = sorted(Path(root).rglob(fname))
                except Exception:
                    continue
                if hits:
                    text = hits[0].read_text(errors="ignore")
                    chunks.append(f"\n===== {hits[0]} =====\n{text[:30000]}")
                    break
        return "\n".join(chunks)

    @staticmethod
    def _collect_tests(project):
        chunks = []
        for root in project.test_roots:
            for p in Path(root).rglob("*.java"):
                try:
                    chunks.append(f"\n===== {p} =====\n{p.read_text(errors='ignore')[:20000]}")
                except Exception:
                    pass
                if len(chunks) >= 12:
                    return "\n".join(chunks)
        return "\n".join(chunks)

    @staticmethod
    def _shard_gaps(gaps, depth=4, max_per_shard=3, max_shards=4):
        """Split gaps into per-module shards for concurrent fixing.

        Groups by the first ``depth`` package segments (e.g. depth=4 ->
        ``com.employee.system.controller``). Oversized groups are chunked so
        no shard exceeds ``max_per_shard`` gaps; shards are ranked by summed
        priority and capped at ``max_shards``. ``max_shards <= 1`` preserves
        the legacy single-blob behavior.
        """
        if max_shards <= 1:
            return [("all", list(gaps))]
        groups: dict[str, list] = {}
        for gap in gaps:
            package = (gap.package or "").strip()
            key = ".".join(package.split(".")[:depth]) if package else "(default)"
            groups.setdefault(key, []).append(gap)
        chunks: list[tuple[str, list]] = []
        for key, items in groups.items():
            if len(items) <= max_per_shard:
                chunks.append((key, items))
            else:
                for i in range(0, len(items), max_per_shard):
                    chunks.append((f"{key}#{i // max_per_shard + 1}", items[i:i + max_per_shard]))
        chunks.sort(key=lambda kv: sum(g.priority for g in kv[1]), reverse=True)
        return chunks[:max_shards]

    async def _generate_shard(self, shard_name, shard_gaps, project, test_text, previous_failure):
        """Build a shard-scoped prompt and collect one shard's file changes.

        Returns ``(shard_name, changes, raw, error)``; ``error`` is "" on
        success. A shard that fails never blocks the other shards.
        """
        source_text = self._collect_sources(project, shard_gaps)
        prompt = build_generation_prompt(
            project, shard_gaps, source_text, test_text, previous_failure
        )
        try:
            raw = await self.llm.generate(prompt)
        except Exception as exc:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "[CoverageAgent] Shard %s LLM generate failed: %s", shard_name, exc
            )
            return (shard_name, [], "", f"LLM generate failed: {exc}")
        try:
            changes = parse_changes(raw)
        except Exception as parse_exc:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "[CoverageAgent] Shard %s returned unparseable JSON: %s", shard_name, parse_exc
            )
            return (shard_name, [], raw, f"LLM output was not valid JSON: {parse_exc}")
        if not changes:
            return (shard_name, [], raw, f"no parseable changes ({len(raw or '')} chars)")
        return (shard_name, changes, raw, "")

    @staticmethod
    def _change_key(change, project) -> str:
        """Normalize a proposed change path for claim-map deduplication."""
        try:
            rel = Path(change.path)
            if rel.is_absolute():
                key = str(rel.resolve().relative_to(Path(project.root).resolve()))
            else:
                key = str(rel)
        except Exception:
            key = str(change.path)
        return key.replace("\\", "/").lower()

    @staticmethod
    def _collect_tests_for_shard(project, shard_name, shard_gaps, char_budget=30000):
        """Collect only tests relevant to one shard's module.

        Includes test files under the shard's package directory plus any test
        whose name references a gap class. Falls back to a small head of the
        global context when nothing matches (e.g. repair shards).
        """
        base = shard_name.split("#")[0]
        segs = [s for s in base.split(".") if s] or [base]
        focus = set(segs[-2:])
        gap_names = {
            (g.class_name or "").split(".")[-1].split("$")[0].lower()
            for g in (shard_gaps or [])
        }
        chunks = []
        total = 0
        for root in project.test_roots:
            try:
                files = sorted(Path(root).rglob("*.java"))
            except Exception:
                continue
            for p in files:
                try:
                    rel_parts = [part.lower() for part in p.relative_to(root).parts]
                except Exception:
                    rel_parts = [p.name.lower()]
                stem = p.stem.lower()
                hit = (
                    bool(focus & set(rel_parts))
                    or any(name and (name in stem or stem in name) for name in gap_names)
                )
                if not hit:
                    continue
                try:
                    text = p.read_text(errors="ignore")[:6000]
                except Exception:
                    continue
                chunk = f"\n===== {p} =====\n{text}"
                chunks.append(chunk)
                total += len(chunk)
                if total >= char_budget:
                    return "\n".join(chunks)
        if chunks:
            return "\n".join(chunks)
        return JaCoCoCoverageAgent._collect_tests(project)[:10000]
