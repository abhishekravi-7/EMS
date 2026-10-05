"""Static AST and regex analyzer for detecting JUnit test smells before compilation or execution."""

from __future__ import annotations

import re

from app.schemas.unit_test import TestSmellDetail


class TestSmellDetector:
    """Performs fast rule-based static analysis (<10ms) on Java JUnit test code."""
    __test__ = False

    def detect_smells(self, test_code: str, target_class_name: str | None = None) -> list[TestSmellDetail]:
        smells: list[TestSmellDetail] = []

        if not test_code or not test_code.strip():
            smells.append(
                TestSmellDetail(
                    smell_type="EMPTY_TEST_CODE",
                    message="Generated test code is empty or whitespace.",
                    severity="CRITICAL",
                )
            )
            return smells

        # Rule 1: Package Statement Check
        if not re.search(r"package\s+[\w\.]+;", test_code):
            smells.append(
                TestSmellDetail(
                    smell_type="MISSING_PACKAGE",
                    message="Test class lacks an explicit package declaration.",
                    severity="HIGH",
                )
            )

        # Rule 2: Thread.sleep Flaky Smell
        for i, line in enumerate(test_code.splitlines(), start=1):
            if "Thread.sleep(" in line:
                smells.append(
                    TestSmellDetail(
                        smell_type="THREAD_SLEEP",
                        message="Use of Thread.sleep() introduces non-deterministic test flakiness.",
                        line_number=i,
                        severity="MEDIUM",
                    )
                )

        # Rule 3: Over-mocking target class under test
        if target_class_name:
            mock_target_pattern = re.compile(rf"@Mock\s+(?:private\s+)?{target_class_name}\b")
            if mock_target_pattern.search(test_code):
                smells.append(
                    TestSmellDetail(
                        smell_type="OVERMOCKING",
                        message=f"The target class under test ({target_class_name}) is annotated with @Mock instead of @InjectMocks or real instantiation.",
                        severity="CRITICAL",
                    )
                )

        # Rule 4: Method-level AST checks (@Test methods)
        test_method_blocks = self._extract_test_methods(test_code)
        for method_name, method_body, line_num in test_method_blocks:
            # Check 4a: Non-BDD naming convention check
            if not (method_name.startswith("given") and "_when" in method_name and "_then" in method_name):
                smells.append(
                    TestSmellDetail(
                        smell_type="NON_BDD_METHOD_NAME",
                        message=f"Test method '{method_name}' does not follow the given<Condition>_when<Action>_then<ExpectedResult>() BDD naming convention.",
                        line_number=line_num,
                        severity="LOW",
                    )
                )

            # Check 4b: Shallow Placeholder Test (only assertNotNull(service) / assertDoesNotThrow without service call)
            if self._is_shallow_placeholder_test(method_body, target_class_name):
                smells.append(
                    TestSmellDetail(
                        smell_type="SHALLOW_PLACEHOLDER_TEST",
                        message=f"Test method '{method_name}' is a shallow placeholder that only checks instantiation without invoking real business methods.",
                        line_number=line_num,
                        severity="CRITICAL",
                    )
                )

            # Check 4c: Tautological NPE Test (dereferencing null variable inside assertThrows)
            if self._is_tautological_npe_test(method_body):
                smells.append(
                    TestSmellDetail(
                        smell_type="TAUTOLOGICAL_NPE_TEST",
                        message=f"Test method '{method_name}' dereferences a local null variable to force a NullPointerException rather than testing class logic.",
                        line_number=line_num,
                        severity="HIGH",
                    )
                )

            # Check 4d: Physical File Creation without @TempDir
            if ("Files.createFile" in method_body or "new File(" in method_body) and "@TempDir" not in test_code:
                smells.append(
                    TestSmellDetail(
                        smell_type="HARDCODED_FILE_SYSTEM",
                        message=f"Test method '{method_name}' physically interacts with the filesystem without using @TempDir or Mockito mocks.",
                        line_number=line_num,
                        severity="MEDIUM",
                    )
                )

            # Check 4e: Missing Assertions
            if not self._has_assertion_or_verification(method_body):
                smells.append(
                    TestSmellDetail(
                        smell_type="NO_ASSERTIONS",
                        message=f"Test method '{method_name}' contains no assertions (assert*, verify(), assertThrows).",
                        line_number=line_num,
                        severity="HIGH",
                    )
                )

            # Check 4f: Tautological Assertions
            tautology = self._find_tautological_assertion(method_body)
            if tautology:
                smells.append(
                    TestSmellDetail(
                        smell_type="TAUTOLOGICAL_ASSERTION",
                        message=f"Test method '{method_name}' contains a tautological assertion: {tautology}.",
                        line_number=line_num,
                        severity="CRITICAL",
                    )
                )

        return smells

    def calculate_quality_score(self, smells: list[TestSmellDetail], test_code: str) -> float:
        """Calculates a dynamic, non-static quality score (0.0 to 100.0) based on detected test smells and coverage."""
        score = 100.0

        for smell in smells:
            if smell.severity == "CRITICAL":
                score -= 25.0
            elif smell.severity == "HIGH":
                score -= 15.0
            elif smell.severity == "MEDIUM":
                score -= 8.0
            elif smell.severity == "LOW":
                score -= 3.0

        # Reward proper BDD given_when_then method count
        bdd_matches = len(re.findall(r"void\s+given\w+_when\w+_then\w+\s*\(", test_code))
        if bdd_matches > 0:
            score += min(5.0, bdd_matches * 1.5)

        # Reward Mockito verification and AAA comments
        if "// Arrange" in test_code and "// Act" in test_code and "// Assert" in test_code:
            score += 4.0
        if "verify(" in test_code or "when(" in test_code:
            score += 3.0

        return max(45.0, min(99.0, round(score, 1)))

    def _is_shallow_placeholder_test(self, method_body: str, target_class_name: str | None) -> bool:
        """Detects if a test method only checks assertNotNull(instance) without calling target methods."""
        has_assert_not_null_only = "assertNotNull" in method_body and not any(
            kw in method_body for kw in ["assertEquals", "assertThrows", "assertTrue", "assertFalse", "verify("]
        )
        has_no_method_call = True
        if target_class_name:
            var_name = target_class_name[0].lower() + target_class_name[1:]
            if re.search(rf"\b{var_name}\.\w+\s*\(", method_body):
                has_no_method_call = False

        return has_assert_not_null_only and has_no_method_call

    def _is_tautological_npe_test(self, method_body: str) -> bool:
        """Detects assertThrows(NullPointerException.class, () -> nullObj.method())."""
        return bool(
            re.search(r"=\s*null\s*;", method_body)
            and re.search(r"assertThrows\s*\(\s*NullPointerException\.class", method_body)
        )

    def _extract_test_methods(self, code: str) -> list[tuple[str, str, int]]:
        """Extracts (method_name, method_body, line_number) for all @Test methods."""
        results: list[tuple[str, str, int]] = []
        lines = code.splitlines()

        for i, line in enumerate(lines, start=1):
            if "@Test" in line:
                method_name = "unknownMethod"
                body_lines: list[str] = []
                brace_count = 0
                started = False

                for j in range(i - 1, len(lines)):
                    cur_line = lines[j]
                    if not started:
                        match = re.search(r"void\s+(\w+)\s*\(", cur_line)
                        if match:
                            method_name = match.group(1)
                        if "{" in cur_line:
                            started = True
                            brace_count += cur_line.count("{") - cur_line.count("}")
                            body_lines.append(cur_line)
                    else:
                        brace_count += cur_line.count("{") - cur_line.count("}")
                        body_lines.append(cur_line)
                        if brace_count <= 0:
                            break

                results.append((method_name, "\n".join(body_lines), i))

        return results

    def _has_assertion_or_verification(self, method_body: str) -> bool:
        assertion_keywords = [
            "assert",
            "assertEquals",
            "assertTrue",
            "assertFalse",
            "assertNull",
            "assertNotNull",
            "assertThat",
            "assertThrows",
            "verify(",
            "verifyNoInteractions",
        ]
        return any(kw in method_body for kw in assertion_keywords)

    def _find_tautological_assertion(self, method_body: str) -> str | None:
        patterns = [
            (r"assertTrue\s*\(\s*true\s*\)", "assertTrue(true)"),
            (r"assertFalse\s*\(\s*false\s*\)", "assertFalse(false)"),
            (r"assertEquals\s*\(\s*(\w+)\s*,\s*\1\s*\)", "assertEquals(x, x)"),
            (r"assertThat\s*\(\s*true\s*\)\s*\.\s*isTrue\s*\(\s*\)", "assertThat(true).isTrue()"),
        ]
        for pattern, label in patterns:
            if re.search(pattern, method_body):
                return label
        return None
