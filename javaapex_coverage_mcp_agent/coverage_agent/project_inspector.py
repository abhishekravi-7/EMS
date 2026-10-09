from __future__ import annotations

import re
from pathlib import Path
from .models import ProjectInfo


class ProjectInspector:
    def inspect(self, project_dir: str, build_tool: str | None = None,
                java_version: str | None = None) -> ProjectInfo:
        root = Path(project_dir).resolve()

        if build_tool:
            tool = build_tool.lower()
        elif (root / "pom.xml").exists():
            tool = "maven"
        elif (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
            tool = "gradle"
        else:
            raise RuntimeError("Could not detect Maven or Gradle project.")

        if java_version is None:
            java_version = self._detect_java(root, tool)

        test_framework = self._detect_test_framework(root)
        report = self._find_report(root)

        return ProjectInfo(
            root=str(root),
            build_tool=tool,
            java_version=java_version,
            test_framework=test_framework,
            jacoco_report=report,
            source_roots=self._source_roots(root),
            test_roots=self._test_roots(root),
        )

    def _detect_java(self, root: Path, tool: str) -> str | None:
        files = [root / "pom.xml"] if tool == "maven" else [
            root / "build.gradle", root / "build.gradle.kts"
        ]
        text = "\n".join(p.read_text(errors="ignore") for p in files if p.exists())

        patterns = [
            r'<maven\.compiler\.release>\s*([^<]+)',
            r'<maven\.compiler\.source>\s*([^<]+)',
            r'<java\.version>\s*([^<]+)',
            r'JavaLanguageVersion\.of\(\s*(\d+)\s*\)',
            r'languageVersion\s*=\s*JavaLanguageVersion\.of\(\s*(\d+)',
            r'sourceCompatibility\s*=\s*[\'"]?(\d+(?:\.\d+)?)',
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()

        return None

    def _detect_test_framework(self, root: Path) -> str:
        for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            p = root / name
            if p.exists():
                text = p.read_text(errors="ignore")
                if "junit-jupiter" in text or "org.junit.jupiter" in text:
                    return "JUnit 5"
                if "junit:junit" in text:
                    return "JUnit 4"
        return "JUnit"

    def _find_report(self, root: Path) -> str | None:
        candidates = [
            root / "target/site/jacoco/jacoco.xml",
            root / "build/reports/jacoco/test/jacocoTestReport.xml",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    def _source_roots(self, root: Path) -> list[str]:
        return [str(p) for p in [
            root / "src/main/java",
            root / "src/main",
        ] if p.exists()]

    def _test_roots(self, root: Path) -> list[str]:
        return [str(p) for p in [
            root / "src/test/java",
            root / "src/test",
        ] if p.exists()]
