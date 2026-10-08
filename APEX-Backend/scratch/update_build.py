new_content = r'''from __future__ import annotations

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

    @property
    def output(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()


class BuildRunner:
    def __init__(self, project_dir: str):
        self.root = Path(project_dir).resolve()

    def _command(self, tool: str, clean: bool = False) -> list[str]:
        if tool == "maven":
            mvn = "mvnw.cmd" if os.name == "nt" and (self.root / "mvnw.cmd").exists() else \
                  "mvnw" if (self.root / "mvnw").exists() else "mvn"
            return [mvn] + (["clean"] if clean else []) + ["org.jacoco:jacoco-maven-plugin:prepare-agent", "test", "org.jacoco:jacoco-maven-plugin:report"]

        gradle = "gradlew.bat" if os.name == "nt" and (self.root / "gradlew.bat").exists() else \
                 "gradlew" if (self.root / "gradlew").exists() else "gradle"
                 
        init_script_path = self.root / "jacoco-init.gradle"
        if not init_script_path.exists():
            init_script_path.write_text("allprojects { apply plugin: 'jacoco' }\n", encoding="utf-8")
            
        return [gradle, "--init-script", "jacoco-init.gradle"] + (["clean"] if clean else []) + ["test", "jacocoTestReport"]

    def run_coverage(self, tool: str, clean: bool = False) -> CommandResult:
        return self._run(self._command(tool, clean))

    def compile_tests(self, tool: str) -> CommandResult:
        if tool == "maven":
            mvn = "mvnw.cmd" if os.name == "nt" and (self.root / "mvnw.cmd").exists() else \
                  "mvnw" if (self.root / "mvnw").exists() else "mvn"
            return self._run([mvn, "-DskipTests", "test-compile"])

        gradle = "gradlew.bat" if os.name == "nt" and (self.root / "gradlew.bat").exists() else \
                 "gradlew" if (self.root / "gradlew").exists() else "gradle"
        return self._run([gradle, "testClasses"])

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
            return CommandResult(False, -1, "", str(exc))
'''
with open(r"C:\Users\Afzal\Documents\javaapex_coverage_mcp_agent\coverage_agent\build.py", "w", encoding="utf-8") as f:
    f.write(new_content)
