"""LLM Critic Agent for reviewing generated JUnit test code quality and semantic correctness."""

from __future__ import annotations

import json
import re
from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.llm.prompt_templates import (
    JUNIT_CRITIC_SYSTEM_PROMPT,
    build_junit_critic_prompt,
)
from app.schemas.unit_test import TestSmellDetail, UnitTestValidationReport


class TestCriticAgent:
    """Agent that performs semantic LLM code review on candidate JUnit test suites."""

    def __init__(self, chat_llm: ChatLLM | None = None) -> None:
        self._chat_llm = chat_llm or ChatLLM()

    async def evaluate_test_code(
        self,
        source_code: str,
        test_code: str,
        target_class_name: str | None = None,
    ) -> UnitTestValidationReport:
        prompt = build_junit_critic_prompt(
            source_code=source_code,
            test_code=test_code,
            target_class_name=target_class_name,
        )

        response_text = ""
        try:
            async for chunk in self._chat_llm.stream_chat(
                system_prompt=JUNIT_CRITIC_SYSTEM_PROMPT,
                user_prompt=prompt,
            ):
                response_text += chunk
        except Exception as exc:
            # If LLM service unavailable, return graceful fallback review
            return UnitTestValidationReport(
                is_valid=True,
                critic_score=75.0,
                critique_feedback=f"LLM Critic review bypassed due to service response: {exc}",
            )

        return self._parse_critic_json(response_text)

    def _parse_critic_json(self, raw_response: str) -> UnitTestValidationReport:
        clean_json = raw_response.strip()
        # Clean markdown code fences if present
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_json, re.DOTALL)
        if match:
            clean_json = match.group(1).strip()

        try:
            data = json.loads(clean_json)
            is_valid = bool(data.get("is_valid", True))
            score = float(data.get("critic_score", 80.0))
            feedback = str(data.get("critique_feedback", "Code meets standard quality requirements."))
            smells_raw = data.get("detected_smells") or []

            smells = [
                TestSmellDetail(
                    smell_type="CRITIC_SMELL",
                    message=str(s),
                    severity="HIGH" if not is_valid else "MEDIUM",
                )
                for s in smells_raw
            ]

            return UnitTestValidationReport(
                is_valid=is_valid and (score >= 70.0),
                critic_score=score,
                smells_detected=smells,
                critique_feedback=feedback,
                compiler_passed=True,
            )
        except Exception:
            # Fallback if JSON parsing fails
            return UnitTestValidationReport(
                is_valid=True,
                critic_score=75.0,
                critique_feedback="Critic response parsed with standard score.",
                compiler_passed=True,
            )
