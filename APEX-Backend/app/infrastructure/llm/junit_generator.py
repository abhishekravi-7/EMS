"""LLM-backed JUnit test generator with code fence extraction and file writing."""

from __future__ import annotations

import re
from pathlib import Path
from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.llm.prompt_templates import (
    JUNIT_GENERATOR_SYSTEM_PROMPT,
    build_junit_correction_prompt,
    build_junit_generation_prompt,
)


class JUnitLLMGenerator:
    def __init__(self, chat_llm: ChatLLM | None = None) -> None:
        self._chat_llm = chat_llm or ChatLLM()

    async def generate_test_class(
        self,
        source_code: str,
        package_name: str,
        target_class_name: str,
        existing_test_code: str | None = None,
        java_version: str = "17",
        junit_version: str = "JUnit 5",
        spring_boot_version: str | None = None,
        uncovered_methods: list[str] | None = None,
    ) -> str:
        prompt = build_junit_generation_prompt(
            source_code=source_code,
            existing_test_code=existing_test_code,
            package_name=package_name,
            target_class_name=target_class_name,
            java_version=java_version,
            junit_version=junit_version,
            spring_boot_version=spring_boot_version,
            uncovered_methods=uncovered_methods,
        )

        response_text = ""
        async for chunk in self._chat_llm.stream_chat(
            system_prompt=JUNIT_GENERATOR_SYSTEM_PROMPT,
            user_prompt=prompt,
        ):
            response_text += chunk

        return self.extract_java_code(response_text)

    async def correct_failed_test_class(
        self,
        source_code: str,
        failed_test_code: str,
        error_log: str,
        target_class_name: str,
    ) -> str:
        prompt = build_junit_correction_prompt(
            source_code=source_code,
            failed_test_code=failed_test_code,
            error_log=error_log,
            target_class_name=target_class_name,
        )

        response_text = ""
        async for chunk in self._chat_llm.stream_chat(
            system_prompt=JUNIT_GENERATOR_SYSTEM_PROMPT,
            user_prompt=prompt,
        ):
            response_text += chunk

        return self.extract_java_code(response_text)

    def write_generated_test_file(
        self,
        project_dir: Path,
        package_name: str,
        target_class_name: str,
        generated_code: str,
    ) -> Path:
        """Writes generated test class to src/test/java/<package_path>/<target_class_name>Test.java."""
        package_path = package_name.replace(".", "/")
        test_dir = project_dir / "src" / "test" / "java" / package_path
        test_dir.mkdir(parents=True, exist_ok=True)

        if target_class_name.endswith("Test") or target_class_name.endswith("Tests"):
            test_class_stem = target_class_name
        else:
            test_class_stem = f"{target_class_name}Test"

        file_name = f"{test_class_stem}.java"
        test_file = test_dir / file_name

        # Ensure public class name in code matches filename stem
        code_to_write = re.sub(
            rf"public\s+class\s+{re.escape(target_class_name)}LLMTest\b",
            f"public class {test_class_stem}",
            generated_code,
        )

        test_file.write_text(code_to_write, encoding="utf-8")
        return test_file

    def extract_java_code(self, raw_llm_response: str) -> str:
        """Extracts Java code from markdown code fences or returns raw response."""
        match = re.search(r"```java\s*(.*?)\s*```", raw_llm_response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fallback to plain code fence if specified without language tag
        match_generic = re.search(r"```\s*(.*?)\s*```", raw_llm_response, re.DOTALL)
        if match_generic:
            return match_generic.group(1).strip()

        return raw_llm_response.strip()
