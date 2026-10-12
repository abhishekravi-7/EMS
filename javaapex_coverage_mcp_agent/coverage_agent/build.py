from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    tests_ok: bool = True

    @property
    def output(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()


_SUREFIRE_SUMMARY_RE = re.compile(
    r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)",
    re.IGNORECASE,
)


class BuildRunner:
    def __init__(self, project_dir: str):
        self.root = Path(project_dir).resolve()

    def _resolve_maven(self) -> str:
        """Resolve the Maven executable with full path for Windows compatibility."""
        if os.name == "nt" and (self.root / "mvnw.cmd").exists():
            return str((self.root / "mvnw.cmd").resolve())
        if (self.root / "mvnw").exists():
            return str((self.root / "mvnw").resolve())
        return "mvn"

    def _resolve_gradle(self) -> str:
        """Resolve the Gradle executable with full path for Windows compatibility."""
        if os.name == "nt" and (self.root / "gradlew.bat").exists():
            return str((self.root / "gradlew.bat").resolve())
        if (self.root / "gradlew").exists():
            return str((self.root / "gradlew").resolve())
        return "gradle"

    def _test_command(self, tool: str, clean: bool = False) -> list[str]:
        """Run tests but never let failing tests block JaCoCo data collection.

        Maven: surefire ``testFailureIgnore`` keeps the build going so the
        JaCoCo exec data is still written.
        Gradle: ``--continue`` lets ``jacocoTestReport`` run even when the
        ``test`` task fails.
        """
        if tool == "maven":
            mvn = self._resolve_maven()
            return [mvn] + (["clean"] if clean else []) + ["org.jacoco:jacoco-maven-plugin:prepare-agent", "test", "-DfailIfNoTests=false", "-DtestFailureIgnore=true"]

        gradle = self._resolve_gradle()
        self._ensure_gradle_jacoco_init()
        init = ["--init-script", "jacoco-init.gradle"]
        return [gradle] + init + (["clean"] if clean else []) + ["test", "--continue"]

    def _report_command(self, tool: str) -> list[str]:
        """Generate the JaCoCo XML report as a separate step.

        Running this independently of the test task is what allows a
        report to be produced even when tests fail — the exec data from
        whatever tests did run is still on disk.
        """
        if tool == "maven":
            return [self._resolve_maven(), "org.jacoco:jacoco-maven-plugin:report"]
        self._ensure_gradle_jacoco_init()
        return [self._resolve_gradle(), "--init-script", "jacoco-init.gradle", "jacocoTestReport"]

    def _report_path(self, tool: str) -> Path:
        if tool == "maven":
            return self.root / "target/site/jacoco/jacoco.xml"
        return self.root / "build/reports/jacoco/test/jacocoTestReport.xml"

    def _ensure_gradle_jacoco_init(self) -> None:
        init_script_path = self.root / "jacoco-init.gradle"
        if not init_script_path.exists():
            init_script_path.write_text("allprojects { apply plugin: 'jacoco' }\n", encoding="utf-8")

    def _command(self, tool: str, clean: bool = False) -> list[str]:
        # Kept for backwards compatibility; prefer run_coverage().
        return self._test_command(tool, clean) + self._report_command(tool)[1:]

    def run_coverage(self, tool: str, clean: bool = False) -> CommandResult:
        """Run tests (tolerating failures), then always attempt the report.

        ``ok`` is True when a JaCoCo XML report exists afterwards.
        ``tests_ok`` reflects the actual test outcome, scanned from
        surefire / Gradle test-result reports.
        """
        test_result = self._run(self._test_command(tool, clean))
        report_result = self._run(self._report_command(tool))

        stdout = "\n".join(s for s in (test_result.stdout, report_result.stdout) if s)
        stderr = "\n".join(s for s in (test_result.stderr, report_result.stderr) if s)
        report_exists = self._report_path(tool).exists()
        ok = report_result.returncode == 0 and report_exists

        failed = self.tests_failed(tool)
        if failed is None:
            tests_ok = test_result.ok
        else:
            tests_ok = not failed

        return CommandResult(
            ok=ok,
            returncode=report_result.returncode if report_exists else test_result.returncode,
            stdout=stdout,
            stderr=stderr,
            tests_ok=tests_ok,
        )

    def tests_failed(self, tool: str) -> bool | None:
        """Scan test reports for failures.

        Returns True (failures found), False (reports exist, all green),
        or None (no test reports — e.g. nothing compiled or no tests ran).
        """
        if tool == "maven":
            return self._scan_surefire()
        return self._scan_gradle_results()

    def _scan_surefire(self) -> bool | None:
        report_dir = self.root / "target" / "surefire-reports"
        files = sorted(report_dir.glob("*.txt"))
        if not files:
            return None
        for path in files:
            match = _SUREFIRE_SUMMARY_RE.search(path.read_text(errors="ignore"))
            if match and (int(match.group(2)) > 0 or int(match.group(3)) > 0):
                return True
        return False

    def _scan_gradle_results(self) -> bool | None:
        files = sorted((self.root / "build" / "test-results").rglob("TEST-*.xml"))
        if not files:
            return None
        import xml.etree.ElementTree as ET

        for path in files:
            try:
                root = ET.parse(str(path)).getroot()
            except ET.ParseError:
                continue
            if int(root.attrib.get("failures", 0) or 0) > 0:
                return True
            if int(root.attrib.get("errors", 0) or 0) > 0:
                return True
        return False

    def compile_tests(self, tool: str) -> CommandResult:
        if tool == "maven":
            mvn = self._resolve_maven()
            return self._run([mvn, "-DskipTests", "test-compile"])

        gradle = self._resolve_gradle()
        return self._run([gradle, "testClasses"])

    @staticmethod
    def blamed_test_files(output: str, project_root) -> list[Path]:
        """Extract test source files blamed by a failed compilation.

        Parses ``*.java`` paths (e.g. ``.../src/test/java/.../FooTest.java:[8,18]``)
        from compiler output. Only files that exist under the project are
        returned, so callers can safely intersect with their backup map for
        partial rollback. Never raises.
        """
        root = Path(project_root).resolve()
        found: list[Path] = []
        try:
            tokens = re.finditer(r"(\S+?\.java)", output or "")
        except Exception:
            return found
        for match in tokens:
            token = match.group(1).strip().strip(",;\"'[]()")
            if not token:
                continue
            # Collapse slash runs so single, double (double-encoded
            # logs), and mixed separators all match "src/test".
            norm = re.sub(r"[\\/]+", "/", token)
            if "src/test" not in norm:
                continue
            try:
                candidate = Path(token)
                if not candidate.is_absolute():
                    # Anchor relative paths (e.g. src/test/...) at the root;
                    # if the token starts mid-tree, anchor at the src/ segment.
                    if "src/" in norm:
                        candidate = root / norm[norm.index("src/"):]
                    else:
                        candidate = root / token
                candidate = candidate.resolve()
            except Exception:
                continue
            try:
                candidate.relative_to(root)
            except Exception:
                continue
            # No existence gate: the caller intersects with its own backup map,
            # so only files this run touched are ever reverted (including
            # newly created ones the compiler blames).
            if candidate not in found:
                found.append(candidate)
        return found

    def _run(self, command: list[str]) -> CommandResult:
        try:
            p = subprocess.run(
                command,
                cwd=self.root,
                text=True,
                capture_output=True,
                timeout=1800,
                shell=False,
            )
            return CommandResult(p.returncode == 0, p.returncode, p.stdout, p.stderr)
        except Exception as exc:
            return CommandResult(False, -1, "", str(exc), tests_ok=False)
