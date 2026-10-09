# End-to-end test: Run the MCP JaCoCo Coverage Agent loop
# against the EMS-Migrated project.
#
# This script:
# 1. Runs a baseline JaCoCo coverage measurement
# 2. Launches the MCP Coverage Agent loop (Ollama-only, target=80%)
# 3. Reports initial coverage, final coverage, iterations used

import asyncio
import sys
import time
import logging

# Ensure the explicitly requested MCP directory is prioritized
sys.path.insert(0, r"C:\Users\Afzal\Documents\javaapex_coverage_mcp_agent")

# Ensure project modules are importable
sys.path.insert(0, r"C:\Users\Afzal\Documents\Apex\JavaAPEX\APEX-Backend")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_pipeline")


PROJECT_DIR = r"C:\Users\Afzal\Documents\Jacoco\EMS-Migrated20261008131222"
TARGET_COVERAGE = 80.0
MAX_ITERATIONS = 10


async def main():
    logger.info("=" * 70)
    logger.info("PIPELINE TEST: MCP JaCoCo Coverage Agent Loop")
    logger.info("Project: %s", PROJECT_DIR)
    logger.info("Target: %.0f%% LINE coverage, Max iterations: %d", TARGET_COVERAGE, MAX_ITERATIONS)
    logger.info("=" * 70)

    # --- Step 1: Import the coverage agent ---
    try:
        from coverage_agent.agent import JaCoCoCoverageAgent
        from coverage_agent.llm import JsonLLMAdapter
        from coverage_agent.models import CoverageAgentRequest
        logger.info("[OK] coverage_agent package imported successfully")
    except ImportError as e:
        logger.error("[FAIL] Cannot import coverage_agent: %s", e)
        sys.exit(1)

    # --- Step 2: Create Ollama-only ChatLLM ---
    from app.infrastructure.llm.chat_llm import ChatLLM
    import json
    import re

    mcp_chat_llm = ChatLLM()

    class DisabledGroq:
        is_configured = False
        provider = "groq"

    mcp_chat_llm._groq = DisabledGroq()
    logger.info("[OK] ChatLLM created with Groq DISABLED (Ollama-only mode)")

    # --- Step 3: Wrap with RobustJsonLLMAdapter ---
    class RobustJsonLLMAdapter(JsonLLMAdapter):
        async def generate(self, prompt: str) -> str:
            raw = await super().generate(prompt)
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
            try:
                parsed = json.loads(text, strict=False)
                return json.dumps(parsed)
            except json.JSONDecodeError:
                fixed = re.sub(r'}\s*{', '}, {', text)
                fixed = re.sub(r',\s*}', '}', fixed)
                fixed = re.sub(r',\s*]', ']', fixed)
                try:
                    parsed = json.loads(fixed, strict=False)
                    return json.dumps(parsed)
                except json.JSONDecodeError:
                    logger.error("[JSON] Failed to parse LLM output, returning empty changes")
                    return '{"changes": [], "reasoning": "Failed to parse LLM JSON"}'

    agent_llm = RobustJsonLLMAdapter(mcp_chat_llm)
    logger.info("[OK] RobustJsonLLMAdapter created")

    # --- Step 4: Create agent and request ---
    coverage_agent = JaCoCoCoverageAgent(llm=agent_llm)

    agent_req = CoverageAgentRequest(
        project_dir=PROJECT_DIR,
        build_tool="maven",
        java_version="17",
        target_coverage=TARGET_COVERAGE,
        max_iterations=MAX_ITERATIONS,
        coverage_metric="LINE",
    )

    logger.info("[OK] CoverageAgentRequest created")
    logger.info("  build_tool=%s, java_version=%s", agent_req.build_tool, agent_req.java_version)
    logger.info("  target_coverage=%.0f%%, max_iterations=%d", agent_req.target_coverage, agent_req.max_iterations)

    # --- Step 5: Run the coverage loop ---
    logger.info("")
    logger.info("=" * 70)
    logger.info("STARTING MCP COVERAGE AGENT LOOP...")
    logger.info("=" * 70)

    start_time = time.time()
    try:
        result = await coverage_agent.ensure_coverage(agent_req)
    except Exception as e:
        logger.error("[FAIL] Coverage agent crashed: %s", e, exc_info=True)
        sys.exit(1)
    elapsed = time.time() - start_time

    # --- Step 6: Report results ---
    logger.info("")
    logger.info("=" * 70)
    logger.info("RESULTS")
    logger.info("=" * 70)
    logger.info("Success:            %s", result.success)
    logger.info("Initial Coverage:   %.2f%%", result.initial_coverage or 0)
    logger.info("Final Coverage:     %.2f%%", result.final_coverage or 0)
    logger.info("Target Coverage:    %.2f%%", result.target_coverage or 0)
    logger.info("Coverage Metric:    %s", result.coverage_metric)
    logger.info("Iterations Used:    %s", result.iterations or 0)
    logger.info("Tests Created:      %s", result.tests_created or 0)
    logger.info("Tests Modified:     %s", result.tests_modified or 0)
    logger.info("Compile Repairs:    %s", result.compilation_repairs or 0)
    logger.info("Time Elapsed:       %.1f seconds (%.1f minutes)", elapsed, elapsed / 60)
    logger.info("Build Tool:         %s", result.build_tool)
    logger.info("Java Version:       %s", result.java_version)

    if hasattr(result, 'iteration_history') and result.iteration_history:
        logger.info("")
        logger.info("--- Iteration History ---")
        for it in result.iteration_history:
            logger.info(
                "  Iter %d: %.2f%% -> %.2f%% | compile=%s tests=%s | files=%s",
                it.iteration,
                it.coverage_before or 0,
                it.coverage_after or 0,
                it.compilation_ok,
                it.tests_ok,
                it.tests_changed,
            )

    if hasattr(result, 'remaining_gaps') and result.remaining_gaps:
        logger.info("")
        logger.info("--- Remaining Coverage Gaps (top 5) ---")
        for gap in result.remaining_gaps[:5]:
            logger.info("  %s (priority=%.2f)", gap.class_name, gap.priority)

    if hasattr(result, 'failure_reason') and result.failure_reason:
        logger.info("")
        logger.info("Failure Reason: %s", result.failure_reason)

    logger.info("")
    if result.success:
        logger.info("✅ PIPELINE TEST PASSED — Reached %.2f%% coverage (target was %.0f%%)", result.final_coverage, TARGET_COVERAGE)
    else:
        improvement = (result.final_coverage or 0) - (result.initial_coverage or 0)
        logger.info("⚠️  PIPELINE TEST PARTIAL — Reached %.2f%% (improved by +%.2f%%, target was %.0f%%)", result.final_coverage or 0, improvement, TARGET_COVERAGE)

    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
