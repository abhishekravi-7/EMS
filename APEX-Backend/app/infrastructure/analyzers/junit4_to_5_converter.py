"""Automated JUnit 4 to JUnit 5 AST and regex modernizer."""

from __future__ import annotations

import re
from pathlib import Path


class JUnit4To5Modernizer:
    """Modernizes pre-existing JUnit 4 test files to modern JUnit 5 syntax."""

    def is_junit4_file(self, code: str) -> bool:
        return any(
            pattern in code
            for pattern in (
                "import org.junit.Test;",
                "import org.junit.Assert;",
                "import static org.junit.Assert",
                "import org.junit.Before;",
                "import org.junit.After;",
                "import org.junit.BeforeClass;",
                "import org.junit.AfterClass;",
                "import org.junit.Ignore;",
                "import org.junit.runner.RunWith;",
            )
        )

    def convert_to_junit5(self, code: str) -> str:
        if not self.is_junit4_file(code):
            return code

        converted = code

        # 1. Imports
        converted = converted.replace("import org.junit.Test;", "import org.junit.jupiter.api.Test;")
        converted = converted.replace("import org.junit.Before;", "import org.junit.jupiter.api.BeforeEach;")
        converted = converted.replace("import org.junit.After;", "import org.junit.jupiter.api.AfterEach;")
        converted = converted.replace("import org.junit.BeforeClass;", "import org.junit.jupiter.api.BeforeAll;")
        converted = converted.replace("import org.junit.AfterClass;", "import org.junit.jupiter.api.AfterAll;")
        converted = converted.replace("import org.junit.Ignore;", "import org.junit.jupiter.api.Disabled;")
        converted = converted.replace("import static org.junit.Assert.*;", "import static org.junit.jupiter.api.Assertions.*;")
        converted = re.sub(r"import\s+static\s+org\.junit\.Assert\.(\w+);", r"import static org.junit.jupiter.api.Assertions.\1;", converted)
        converted = converted.replace("import org.junit.Assert;", "import org.junit.jupiter.api.Assertions;")

        # 2. Annotations
        converted = re.sub(r"@Before\b(?!\w)", "@BeforeEach", converted)
        converted = re.sub(r"@After\b(?!\w)", "@AfterEach", converted)
        converted = re.sub(r"@BeforeClass\b(?!\w)", "@BeforeAll", converted)
        converted = re.sub(r"@AfterClass\b(?!\w)", "@AfterAll", converted)
        converted = re.sub(r"@Ignore\b(?!\w)", "@Disabled", converted)

        # 3. Mockito & Spring RunWith replacements
        if "@RunWith(MockitoJUnitRunner.class)" in converted:
            converted = converted.replace("@RunWith(MockitoJUnitRunner.class)", "@ExtendWith(MockitoExtension.class)")
            if "import org.junit.jupiter.api.extension.ExtendWith;" not in converted:
                converted = "import org.junit.jupiter.api.extension.ExtendWith;\nimport org.mockito.junit.jupiter.MockitoExtension;\n" + converted

        if "@RunWith(SpringRunner.class)" in converted or "@RunWith(SpringJUnit4ClassRunner.class)" in converted:
            converted = re.sub(r"@RunWith\((?:SpringRunner|SpringJUnit4ClassRunner)\.class\)", "@ExtendWith(SpringExtension.class)", converted)
            if "import org.junit.jupiter.api.extension.ExtendWith;" not in converted:
                converted = "import org.junit.jupiter.api.extension.ExtendWith;\nimport org.springframework.test.context.junit.jupiter.SpringExtension;\n" + converted

        # 4. Handle @Test(expected = Exception.class)
        expected_pattern = re.compile(r"@Test\s*\(\s*expected\s*=\s*([\w\.]+)\.class\s*\)")
        if expected_pattern.search(converted):
            if "import static org.junit.jupiter.api.Assertions.assertThrows;" not in converted and "import static org.junit.jupiter.api.Assertions.*;" not in converted:
                converted = "import static org.junit.jupiter.api.Assertions.assertThrows;\n" + converted
            converted = expected_pattern.sub(r"@Test", converted)

        # 5. Clean up old imports
        converted = converted.replace("import org.junit.runner.RunWith;", "")

        return converted

    def convert_project_tests(self, project_dir: Path) -> list[dict[str, str]]:
        test_dir = project_dir / "src" / "test" / "java"
        if not test_dir.exists():
            return []

        converted_files: list[dict[str, str]] = []
        for test_file in test_dir.rglob("*.java"):
            try:
                code = test_file.read_text(encoding="utf-8", errors="ignore")
                if self.is_junit4_file(code):
                    junit5_code = self.convert_to_junit5(code)
                    test_file.write_text(junit5_code, encoding="utf-8")
                    rel_path = str(test_file.relative_to(project_dir)).replace("\\", "/")
                    converted_files.append({
                        "file_name": test_file.name,
                        "relative_path": rel_path,
                        "original_code": code,
                        "converted_code": junit5_code,
                    })
            except Exception:  # noqa: BLE001, S112
                continue  # nosec B112

        return converted_files
