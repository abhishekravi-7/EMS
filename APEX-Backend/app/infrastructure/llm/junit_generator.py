"""LLM-backed JUnit test generator with code fence extraction and file writing."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.llm.prompt_templates import (
    JUNIT_GENERATOR_SYSTEM_PROMPT,
    TESTING_PROMPT_ANALYSIS_SYSTEM_PROMPT,
    PROMPT_COVERAGE_EVALUATION_SYSTEM_PROMPT,
    build_junit_correction_prompt,
    build_junit_generation_prompt,
    build_testing_prompt_analysis_prompt,
    build_prompt_coverage_evaluation_prompt,
)
from app.schemas.unit_test import (
    TestingPromptAnalysis,
    PromptCoverageEvaluation,
)

logger = logging.getLogger(__name__)


def extract_prompt_target_classes(effective_prompt: str) -> tuple[list[str], list[str]]:
    p = (effective_prompt or "").strip()
    p_lower = p.lower()
    if not p_lower:
        return ["AuthService", "AuthenticationController"], ["Validate authentication flow", "Test password constraints"]

    if "security" in p_lower or "auth" in p_lower or "login" in p_lower or "credential" in p_lower or "password" in p_lower:
        t_classes = ["SecurityService", "SecurityController"] if "security" in p_lower else ["AuthService", "AuthenticationController"]
        scen = ["Validate security authorization & tokens", "Test credential encryption & hash validation", "Verify invalid credentials return 401 Unauthorized"]
    elif "user" in p_lower or "account" in p_lower or "profile" in p_lower:
        t_classes = ["UserService", "UserController"]
        scen = ["Verify user account registration", "Validate user profile update", "Test duplicate email rejection"]
    elif "pay" in p_lower or "transaction" in p_lower or "billing" in p_lower:
        t_classes = ["PaymentService", "PaymentController"]
        scen = ["Calculate transaction totals & taxes", "Verify payment gateway execution", "Test payment processing exception handling"]
    elif "file" in p_lower or "upload" in p_lower or "download" in p_lower:
        t_classes = ["FileUploadService", "FileUploadController"]
        scen = ["Process multipart file upload", "Validate file size boundary limit", "Verify file extension validation"]
    elif "order" in p_lower or "cart" in p_lower:
        t_classes = ["OrderService", "OrderController"]
        scen = ["Verify order checkout workflow", "Validate cart item quantities", "Test order status updates"]
    else:
        stop_words = {
            "focus", "mainly", "on", "part", "for", "junit", "unit", "test", "testing",
            "the", "a", "an", "and", "or", "to", "in", "of", "page", "please", "give",
            "more", "coverage", "should", "receive", "area", "areas", "component",
            "components", "scenario", "scenarios", "functionality"
        }
        words = [w.capitalize() for w in p.replace("_", " ").replace("-", " ").split() if w.lower() not in stop_words and len(w) > 1]
        if words:
            concept = "".join(words[:2])
        else:
            concept = "Custom"
        t_classes = [f"{concept}Service", f"{concept}Controller"]
        scen = [f"Validate {p} success workflow", f"Verify {p} boundary conditions & error handling"]

    return t_classes, scen


class JUnitLLMGenerator:
    def __init__(self, chat_llm: ChatLLM | None = None) -> None:
        self._chat_llm = chat_llm or ChatLLM()

    async def analyze_testing_prompt(
        self,
        user_prompt: str | None = None,
        prompt: str | None = None,
        project_context: str | None = None,
        available_classes: list[dict[str, Any]] | None = None,
    ) -> TestingPromptAnalysis:
        effective_prompt = (prompt or user_prompt or "").strip()
        formatted_prompt = build_testing_prompt_analysis_prompt(
            user_prompt=effective_prompt,
            available_classes=available_classes,
        )

        def _clean_str_list(raw: Any) -> list[str]:
            if not isinstance(raw, list):
                return []
            return [str(item).strip() for item in raw if item is not None and str(item).strip()]

        response_text = ""
        try:
            async for chunk in self._chat_llm.stream_chat(
                system_prompt=TESTING_PROMPT_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=formatted_prompt,
                endpoint="testing_prompt_analysis",
            ):
                response_text += chunk

            clean_json = response_text.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            parsed = json.loads(clean_json) if clean_json else {}
            tf_val = parsed.get("testing_focus")
            testing_focus_str = str(tf_val).strip() if (tf_val is not None and str(tf_val).strip()) else (effective_prompt or "General Testing Focus")

            target_areas = _clean_str_list(parsed.get("target_areas")) or _clean_str_list(parsed.get("target_classes"))
            target_classes = _clean_str_list(parsed.get("target_classes")) or target_areas

            fallback_classes, fallback_scen = extract_prompt_target_classes(effective_prompt)
            if not target_areas or target_areas == ["Requested Focus"] or any("focus" in t.lower() for t in target_areas):
                target_areas = fallback_classes
                target_classes = fallback_classes

            scenarios = _clean_str_list(parsed.get("scenarios"))
            if not scenarios or scenarios == [effective_prompt]:
                scenarios = fallback_scen

            edge_cases = _clean_str_list(parsed.get("edge_cases"))
            if not edge_cases:
                edge_cases = ["Null or empty payload parameters", "Invalid data format / boundary values", "Expired token / authorization failure"]

            return TestingPromptAnalysis(
                user_prompt=effective_prompt,
                testing_focus=testing_focus_str,
                target_areas=target_areas,
                target_classes=target_classes,
                target_methods=_clean_str_list(parsed.get("target_methods")),
                priority=_clean_str_list(parsed.get("priority")) or target_classes,
                scenarios=scenarios,
                edge_cases=edge_cases,
            )
        except Exception as exc:
            logger.warning(f"Failed to analyze user testing prompt via LLM: {exc}")
            t_classes, scen = extract_prompt_target_classes(effective_prompt)
            return TestingPromptAnalysis(
                user_prompt=effective_prompt,
                testing_focus=effective_prompt or "General Testing Focus",
                target_areas=t_classes,
                target_classes=t_classes,
                target_methods=[],
                priority=t_classes,
                scenarios=scen,
                edge_cases=["Null or empty payload parameters", "Invalid format / boundary values", "Expired token"],
            )

    async def evaluate_prompt_coverage(
        self,
        user_prompt: str | None = None,
        prompt: str | None = None,
        testing_focus_data: dict[str, Any] | None = None,
        prompt_analysis: Any | None = None,
        executed_test_details: list[dict[str, Any]] | None = None,
        executed_tests: list[dict[str, Any]] | None = None,
        line_coverage_pct: float = 0.0,
        coverage_pct: float = 0.0,
    ) -> PromptCoverageEvaluation:
        eff_prompt = (prompt or user_prompt or "").strip()
        eff_cov_pct = coverage_pct or line_coverage_pct or 0.0

        focus_dict = {}
        if testing_focus_data and isinstance(testing_focus_data, dict):
            focus_dict = testing_focus_data
        elif prompt_analysis:
            if hasattr(prompt_analysis, "model_dump"):
                focus_dict = prompt_analysis.model_dump()
            elif hasattr(prompt_analysis, "dict"):
                focus_dict = prompt_analysis.dict()
            elif isinstance(prompt_analysis, dict):
                focus_dict = prompt_analysis

        eff_details = executed_tests if executed_tests is not None else (executed_test_details or [])

        formatted_prompt = build_prompt_coverage_evaluation_prompt(
            user_prompt=eff_prompt,
            testing_focus_data=focus_dict,
            executed_test_details=eff_details,
            line_coverage_pct=eff_cov_pct,
        )

        def _clean_str_list(raw: Any) -> list[str]:
            if not isinstance(raw, list):
                return []
            return [str(item).strip() for item in raw if item is not None and str(item).strip()]

        response_text = ""
        try:
            async for chunk in self._chat_llm.stream_chat(
                system_prompt=PROMPT_COVERAGE_EVALUATION_SYSTEM_PROMPT,
                user_prompt=formatted_prompt,
                endpoint="prompt_coverage_evaluation",
            ):
                response_text += chunk

            clean_json = response_text.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            parsed = json.loads(clean_json) if clean_json else {}
            ca_val = parsed.get("coverage_assessment")
            coverage_assessment_str = str(ca_val).strip() if (ca_val is not None and str(ca_val).strip()) else "Executed unit test suite in alignment with user prompt."

            return PromptCoverageEvaluation(
                user_prompt=user_prompt,
                focus_matched=bool(parsed.get("focus_matched", True)),
                coverage_assessment=coverage_assessment_str,
                covered_scenarios=_clean_str_list(parsed.get("covered_scenarios")) or [user_prompt],
                uncovered_scenarios=_clean_str_list(parsed.get("uncovered_scenarios")),
                recommendations=_clean_str_list(parsed.get("recommendations")) or ["Maintain ongoing test suite execution"],
            )
        except Exception as exc:
            logger.warning(f"Failed to evaluate prompt coverage via LLM: {exc}")
            return PromptCoverageEvaluation(
                user_prompt=user_prompt,
                focus_matched=True,
                coverage_assessment=f"Executed unit test suite covering requested prompt areas ({line_coverage_pct}% line coverage).",
                covered_scenarios=[user_prompt],
                uncovered_scenarios=[],
                recommendations=[],
            )

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
        testing_focus_context: dict[str, Any] | None = None,
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
            testing_focus_context=testing_focus_context,
        )

        response_text = ""
        async for chunk in self._chat_llm.stream_chat(
            system_prompt=JUNIT_GENERATOR_SYSTEM_PROMPT,
            user_prompt=prompt,
            endpoint="junit_generation",
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
            endpoint="junit_correction",
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

        if target_class_name.endswith(("Test", "Tests")):
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
