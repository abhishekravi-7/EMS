"""Scanner for discovering existing Java test cases (JUnit/TestNG) in a repository."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, TypedDict


class TestCaseMethod(TypedDict):
    name: str
    line_number: int

class TestClassInfo(TypedDict):
    id: str
    className: str
    filePath: str
    framework: str
    methods: List[str]

class TestDiscoveryResult(TypedDict):
    framework: str
    buildTool: str
    tests: List[TestClassInfo]
    error: str | None

class ExistingTestDetector:
    """Detects and parses existing Java test classes and methods."""

    # Patterns to match common test locations
    TEST_SOURCE_DIRS = ["src/test/java", "src/test", "test", "tests"]

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def discover(self) -> TestDiscoveryResult:
        """Scan the project directory and return discovered test cases."""
        if not self.project_dir.exists():
            return {
                "framework": "Unknown",
                "buildTool": "Unknown",
                "tests": [],
                "error": f"Project directory does not exist: {self.project_dir}"
            }

        build_tool = self._detect_build_tool()
        tests = []
        frameworks_found = set()
        seen_keys = set()

        # Search in common test directories
        for test_dir_rel in self.TEST_SOURCE_DIRS:
            test_dir = self.project_dir / test_dir_rel
            if test_dir.exists() and test_dir.is_dir():
                discovered = self._scan_directory(test_dir)
                for t in discovered:
                    # Uniquely identify test class by className and filePath (Deduplication Rule)
                    key = (t["className"], t["filePath"])
                    if key not in seen_keys:
                        seen_keys.add(key)
                        frameworks_found.add(t["framework"])
                        tests.append(t)

        return {
            "framework": ", ".join(frameworks_found) if frameworks_found else "Unknown",
            "buildTool": build_tool,
            "tests": tests,
            "error": None if tests else "No test cases found in standard locations."
        }

    def _detect_build_tool(self) -> str:
        if (self.project_dir / "pom.xml").exists():
            return "Maven"
        if (self.project_dir / "build.gradle").exists() or (self.project_dir / "build.gradle.kts").exists():
            return "Gradle"
        return "Unknown"

    def _scan_directory(self, directory: Path) -> List[TestClassInfo]:
        discovered_tests = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".java"):
                    file_path = Path(root) / file
                    test_info = self._parse_test_file(file_path)
                    if test_info:
                        discovered_tests.append(test_info)
        return discovered_tests

    def _parse_test_file(self, file_path: Path) -> TestClassInfo | None:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return None

        # Basic check if it's likely a test file
        if not ("org.junit" in content or "org.testng" in content or "@Test" in content):
            return None

        framework = "JUnit 5" if "org.junit.jupiter" in content else "JUnit 4" if "org.junit" in content else "TestNG" if "org.testng" in content else "JUnit"

        # Extract package name to build full class name
        package_match = re.search(r"package\s+([\w\.]+)\s*;", content)
        package_name = package_match.group(1) if package_match else ""
        class_name = file_path.stem
        full_class_name = f"{package_name}.{class_name}" if package_name else class_name

        # Extract test methods using regex
        # Matches @Test followed by method signature
        methods = []

        # Pattern for JUnit 4/5 (@Test, @ParameterizedTest, @RepeatedTest, @TestFactory, @TestTemplate) and TestNG, allowing intermediate annotations
        test_method_pattern = re.compile(
            r'@(?:Test|ParameterizedTest|RepeatedTest|TestFactory|TestTemplate)\b(?:\([^)]*\))?'
            r'(?:\s*@[\w.]+(?:\([^)]*\))?)*'
            r'\s*(?:public\s+|protected\s+|private\s+)?(?:static\s+)?(?:final\s+)?(?:<[\w\s,.<>?]+>\s+)?(?:void|boolean|int|long|String|var|[\w<>[\],.]+)\s+'
            r'([a-zA-Z0-9_$]+)\s*\(',
            re.MULTILINE
        )

        for match in test_method_pattern.finditer(content):
            method_name = match.group(1)
            if method_name not in methods and method_name not in ("if", "for", "while", "switch", "catch", "new", "return", "class", "interface", "enum"):
                methods.append(method_name)


        if not methods:
            # Fallback for methods without explicit @Test if the class name suggests it's a test
            if "Test" in class_name:
                # Just identify the class if no methods are explicitly marked but it's clearly a test class
                pass
            else:
                return None

        try:
            rel_path = str(file_path.relative_to(self.project_dir)).replace("\\", "/")
        except ValueError:
            rel_path = str(file_path)

        return {
            "id": full_class_name,
            "className": full_class_name,
            "filePath": rel_path,
            "framework": framework,
            "methods": methods
        }
