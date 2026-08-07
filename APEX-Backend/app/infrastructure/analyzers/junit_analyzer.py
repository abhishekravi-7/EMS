"""AST and static analyzer for Java source files and JUnit test classes."""

from __future__ import annotations

import re
from pathlib import Path
from app.schemas.unit_test import TestScenario, UnitTestAnalysisResponse


class JavaASTAnalyzer:
    """Parses Java source files and existing JUnit test classes using regex and token parsing."""

    def analyze_source_and_tests(
        self,
        source_code: str,
        test_code: str | None = None,
        source_filename: str = "TargetClass.java",
    ) -> UnitTestAnalysisResponse:
        package_name = self._extract_package_name(source_code)
        class_name = self._extract_class_name(source_code, source_filename)
        public_methods = self._extract_public_methods(source_code)
        existing_test_methods = self._extract_test_methods(test_code) if test_code else []

        # Determine which methods are already covered by matching test method names
        covered_methods: list[str] = []
        uncovered_methods: list[str] = []

        test_code_lower = (test_code or "").lower()
        for method in public_methods:
            method_name = method["name"]
            # A method is considered covered if its name appears inside test_code or a test method matches test<MethodName>
            if method_name.lower() in test_code_lower or f"test{method_name.lower()}" in test_code_lower:
                covered_methods.append(method_name)
            else:
                uncovered_methods.append(method_name)

        suggested_scenarios = self._generate_suggested_scenarios(
            class_name=class_name,
            public_methods=public_methods,
            uncovered_methods=uncovered_methods,
        )

        return UnitTestAnalysisResponse(
            target_class=class_name,
            package_name=package_name,
            existing_tests_count=len(existing_test_methods),
            covered_methods=covered_methods,
            uncovered_methods=uncovered_methods,
            suggested_scenarios=suggested_scenarios,
        )

    def analyze_files(
        self,
        source_path: Path,
        test_path: Path | None = None,
    ) -> UnitTestAnalysisResponse:
        source_code = source_path.read_text(encoding="utf-8", errors="replace")
        test_code = test_path.read_text(encoding="utf-8", errors="replace") if test_path and test_path.exists() else None

        return self.analyze_source_and_tests(
            source_code=source_code,
            test_code=test_code,
            source_filename=source_path.name,
        )

    def analyze_source_file(self, code: str, filename: str = "TargetClass.java") -> dict[str, str | list]:
        package_name = self._extract_package_name(code)
        class_name = self._extract_class_name(code, filename)
        public_methods = self._extract_public_methods(code)
        method_names = [m["name"] for m in public_methods]
        return {
            "package_name": package_name,
            "class_name": class_name,
            "public_methods": public_methods,
            "method_signatures": method_names,
        }

    def analyze_test_file(self, code: str, filename: str = "TargetTest.java") -> dict[str, str | list[str]]:
        package_name = self._extract_package_name(code)
        class_name = self._extract_class_name(code, filename)
        test_methods = self._extract_test_methods(code)
        return {
            "package_name": package_name,
            "class_name": class_name,
            "test_methods": test_methods,
        }


    def _extract_package_name(self, code: str) -> str:
        match = re.search(r"package\s+([\w\.]+)\s*;", code)
        return match.group(1) if match else "com.example"

    def _extract_class_name(self, code: str, fallback_filename: str) -> str:
        match = re.search(r"(?:public\s+|protected\s+)?(?:abstract\s+)?(?:final\s+)?class\s+(\w+)", code)
        if match:
            return match.group(1)
        stem = Path(fallback_filename).stem
        return stem if stem and stem != "TargetTest" else "TestClass"

    def _extract_public_methods(self, code: str) -> list[dict[str, str]]:
        """Extracts public and protected methods, their return types, and parameter strings."""
        methods: list[dict[str, str]] = []
        # Matches: public/protected [modifiers] ReturnType methodName(ParamType param1, ...) [throws Exception]
        pattern = re.compile(
            r"(?:public|protected)\s+(?:static\s+)?(?:final\s+)?([\w<>\[\]]+)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w\s,]+)?\s*\{"
        )
        for match in pattern.finditer(code):
            return_type = match.group(1).strip()
            method_name = match.group(2).strip()
            params_str = match.group(3).strip()

            # Exclude constructor
            if return_type and method_name and method_name[0].isupper():
                continue

            methods.append({
                "name": method_name,
                "return_type": return_type,
                "params": params_str,
            })

        return methods

    def _extract_test_methods(self, test_code: str) -> list[str]:
        if not test_code:
            return []
        # Matches @Test annotated methods
        pattern = re.compile(r"@Test\s+(?:public\s+)?void\s+(\w+)\s*\(\s*\)")
        return [match.group(1) for match in pattern.finditer(test_code)]

    def _generate_suggested_scenarios(
        self,
        class_name: str,
        public_methods: list[dict[str, str]],
        uncovered_methods: list[str],
    ) -> list[TestScenario]:
        scenarios: list[TestScenario] = []

        for m in public_methods:
            name = m["name"]
            params = m["params"]
            ret = m["return_type"]

            # Happy Path Scenario
            scenarios.append(
                TestScenario(
                    name=f"test{name.capitalize()}_Success",
                    scenario_type="happy_path",
                    description=f"Verifies successful execution of {name}() with valid parameters ({params}).",
                    target_method=name,
                )
            )

            # Null / Invalid Check Scenario
            if params and ("String" in params or "Object" in params or "List" in params or "Map" in params):
                scenarios.append(
                    TestScenario(
                        name=f"test{name.capitalize()}_NullOrEmptyInput",
                        scenario_type="null_check",
                        description=f"Verifies handling when null or empty arguments are passed to {name}().",
                        target_method=name,
                    )
                )

            # Boundary / Edge Case Scenario
            if params and ("int" in params or "long" in params or "double" in params or "float" in params):
                scenarios.append(
                    TestScenario(
                        name=f"test{name.capitalize()}_BoundaryValues",
                        scenario_type="boundary",
                        description=f"Verifies behavior of {name}() with boundary inputs (0, negative, MAX_VALUE).",
                        target_method=name,
                    )
                )

            # Exception Scenario
            scenarios.append(
                TestScenario(
                    name=f"test{name.capitalize()}_ThrowsException_OnInvalidState",
                    scenario_type="exception",
                    description=f"Verifies expected exception handling when {name}() encounters an invalid internal state.",
                    target_method=name,
                )
            )

        return scenarios
