"""Use case for validating JUnit test cases via Multi-Agent pipeline (AST Smell Detector + LLM Critic Agent)."""

from __future__ import annotations

from sqlalchemy.orm import Session
from app.infrastructure.analyzers.test_smell_detector import TestSmellDetector
from app.infrastructure.llm.agents.critic_agent import TestCriticAgent
from app.application.services.llm_token_tracing_service import LLMTokenTracingService
from app.schemas.unit_test import UnitTestValidationReport, TestSmellDetail


class ValidateUnitTestSuiteUseCase:
    """Orchestrates static AST smell analysis and LLM Critic review for JUnit test suites."""

    def __init__(
        self,
        smell_detector: TestSmellDetector | None = None,
        critic_agent: TestCriticAgent | None = None,
    ) -> None:
        self._smell_detector = smell_detector or TestSmellDetector()
        self._critic_agent = critic_agent or TestCriticAgent()

    async def validate(
        self,
        source_code: str,
        test_code: str,
        target_class_name: str | None = None,
        db: Session | None = None,
        job_id: str | None = None,
    ) -> UnitTestValidationReport:
        # Wrap critic agent's ChatLLM with tracing if DB is available
        original_chat = self._critic_agent._chat_llm
        if db:
            tracing_chat = LLMTokenTracingService(
                chat_llm=original_chat,
                db=db,
                job_id=job_id,
                endpoint="junit_critic"
            )
            self._critic_agent._chat_llm = tracing_chat

        try:
            # Step 1: AST Static Smell Detection (<10ms)
            static_smells = self._smell_detector.detect_smells(
                test_code=test_code,
                target_class_name=target_class_name,
            )

            has_critical_smells = any(s.severity in ("CRITICAL", "HIGH") for s in static_smells)

            # Step 2: LLM Critic Agent Evaluation
            critic_report = await self._critic_agent.evaluate_test_code(
                source_code=source_code,
                test_code=test_code,
                target_class_name=target_class_name,
            )

            # Merge static smells + critic smells
            all_smells: list[TestSmellDetail] = []
            all_smells.extend(static_smells)
            all_smells.extend(critic_report.smells_detected)

            # Compute overall validity
            overall_valid = (
                not has_critical_smells
                and critic_report.is_valid
                and critic_report.critic_score >= 70.0
            )

            feedback_summary = critic_report.critique_feedback
            if static_smells:
                static_msg = "; ".join([f"{s.smell_type}: {s.message}" for s in static_smells])
                feedback_summary = f"[Static AST Smells]: {static_msg}. [LLM Critic Review]: {critic_report.critique_feedback}"

            return UnitTestValidationReport(
                is_valid=overall_valid,
                critic_score=critic_report.critic_score if not has_critical_smells else min(critic_report.critic_score, 40.0),
                smells_detected=all_smells,
                critique_feedback=feedback_summary,
                compiler_passed=critic_report.compiler_passed,
            )
        finally:
            if db:
                self._critic_agent._chat_llm = original_chat
