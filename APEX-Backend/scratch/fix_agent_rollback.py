import re

agent_path = r"C:\Users\Afzal\Documents\javaapex_coverage_mcp_agent\coverage_agent\agent.py"
with open(agent_path, "r", encoding="utf-8") as f:
    agent_code = f.read()

# Replace the file-writing + compile block with backup/rollback logic
old_block = """            changed_paths = []
            for change in changes:
                rel = Path(change.path)
                if rel.is_absolute():
                    target = rel.resolve()
                else:
                    target = (Path(project.root) / rel).resolve()

                if not self._is_test_file(target, project):
                    raise RuntimeError(
                        f"Coverage agent refused non-test modification: {target}"
                    )

                existed = target.exists()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(change.content, encoding="utf-8")
                changed_paths.append(str(target.relative_to(project.root)))

                if existed:
                    modified += 1
                else:
                    created += 1

            compile_result = runner.compile_tests(project.build_tool)

            if not compile_result.ok:
                repairs += 1
                previous_failure = compile_result.output[-12000:]
                history.append(CoverageIteration(
                    iteration=iteration,
                    coverage_before=current_coverage,
                    coverage_after=current_coverage,
                    tests_changed=changed_paths,
                    compilation_ok=False,
                    tests_ok=False,
                    build_output=compile_result.output[-12000:],
                    failure="test compilation failed",
                ))
                continue"""

new_block = """            changed_paths = []
            backups = {}  # path -> (original_content or None if new file)
            for change in changes:
                rel = Path(change.path)
                if rel.is_absolute():
                    target = rel.resolve()
                else:
                    target = (Path(project.root) / rel).resolve()

                if not self._is_test_file(target, project):
                    raise RuntimeError(
                        f"Coverage agent refused non-test modification: {target}"
                    )

                # Backup original content before overwriting
                if target.exists():
                    backups[target] = target.read_text(encoding="utf-8", errors="replace")
                else:
                    backups[target] = None  # Mark as newly created

                existed = target.exists()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(change.content, encoding="utf-8")
                changed_paths.append(str(target.relative_to(project.root)))

                if existed:
                    modified += 1
                else:
                    created += 1

            compile_result = runner.compile_tests(project.build_tool)

            if not compile_result.ok:
                repairs += 1
                # ROLLBACK: Restore original files so next iteration starts clean
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
                ))
                continue"""

if old_block in agent_code:
    agent_code = agent_code.replace(old_block, new_block)
    with open(agent_path, "w", encoding="utf-8") as f:
        f.write(agent_code)
    print("SUCCESS: agent.py updated with rollback mechanism")
else:
    print("ERROR: Could not find exact block to replace")
    # Debug: show what we're looking for vs what's there
    for i, line in enumerate(agent_code.splitlines(), 1):
        if "changed_paths" in line or "compile_result" in line or "backups" in line:
            print(f"  Line {i}: {line.rstrip()}")
