# Quick diagnostic: Run one iteration and capture the compilation error
import asyncio
import sys
import logging
import json
import re

sys.path.insert(0, r"C:\Users\Afzal\Documents\Apex\JavaAPEX\APEX-Backend")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("diag")

PROJECT_DIR = r"C:\Users\Afzal\Documents\Jacoco\EMS-Migrated20261008131222"

async def main():
    from coverage_agent.agent import JaCoCoCoverageAgent
    from coverage_agent.llm import JsonLLMAdapter
    from coverage_agent.models import CoverageAgentRequest
    from app.infrastructure.llm.chat_llm import ChatLLM

    mcp_chat_llm = ChatLLM()
    class DisabledGroq:
        is_configured = False
        provider = "groq"
    mcp_chat_llm._groq = DisabledGroq()

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
                    return '{"changes": [], "reasoning": "Failed to parse LLM JSON"}'

    agent_llm = RobustJsonLLMAdapter(mcp_chat_llm)
    coverage_agent = JaCoCoCoverageAgent(llm=agent_llm)

    agent_req = CoverageAgentRequest(
        project_dir=PROJECT_DIR,
        build_tool="maven",
        java_version="17",
        target_coverage=80.0,
        max_iterations=2,
        coverage_metric="LINE",
    )

    result = await coverage_agent.ensure_coverage(agent_req)

    logger.info("Initial: %.2f%%, Final: %.2f%%", result.initial_coverage or 0, result.final_coverage or 0)

    if hasattr(result, 'iteration_history') and result.iteration_history:
        for it in result.iteration_history:
            logger.info("=== ITERATION %d ===", it.iteration)
            logger.info("Compile OK: %s, Tests OK: %s", it.compilation_ok, it.tests_ok)
            logger.info("Files changed: %s", it.tests_changed)
            if it.build_output:
                # Extract just the compilation errors
                lines = it.build_output.splitlines()
                error_lines = [l for l in lines if "ERROR" in l or "error:" in l or "cannot find symbol" in l or "package" in l.lower() and "does not exist" in l.lower()]
                if error_lines:
                    logger.info("--- COMPILATION ERRORS (first 20) ---")
                    for el in error_lines[:20]:
                        logger.info("  %s", el.strip())
                else:
                    # Show last 30 lines of build output
                    logger.info("--- BUILD OUTPUT (last 30 lines) ---")
                    for bl in lines[-30:]:
                        logger.info("  %s", bl.strip())

if __name__ == "__main__":
    asyncio.run(main())
