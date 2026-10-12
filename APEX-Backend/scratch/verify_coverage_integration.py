import asyncio
import os
import sys
import logging

sys.path.insert(0, r"C:\Users\Afzal\Documents\Apex\JavaAPEX\APEX-Backend")
sys.path.insert(0, r"C:\Users\Afzal\Documents\Apex\JavaAPEX\javaapex_coverage_mcp_agent")

from app.application.use_cases.run_unit_tests import RunUnitTestSuiteUseCase
from app.schemas.unit_test import UnitTestGenerateAndRunRequest
from app.infrastructure.llm.chat_llm import ChatLLM

class DisabledGroq:
    is_configured = False
    provider = "groq"
    
import app.infrastructure.llm.junit_generator as jgen
jgen.ChatLLM._groq = DisabledGroq()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger(__name__)

class MockRunUnitTestSuiteUseCase(RunUnitTestSuiteUseCase):
    pass

async def verify():
    project_dir = r"C:\Users\Afzal\Documents\Jacoco\EMS-Migrated20261008131222"
    
    use_case = MockRunUnitTestSuiteUseCase()
    # Patch generator to bypass slow LLM generation entirely
    async def dummy_generate(*args, **kwargs):
        raise Exception("Force AST fallback")
    use_case._generator.generate_test_class = dummy_generate
    
    req = UnitTestGenerateAndRunRequest(
        project_dir=project_dir,
        build_tool="maven",
        java_version="17",
        enable_validation_agent=False
    )
    
    # 1. Test without flag (Regression check)
    logger.info("=== 1. Testing without JAVAAPEX_COVERAGE_ENFORCE ===")
    os.environ["JAVAAPEX_COVERAGE_ENFORCE"] = "false"
    res1 = await use_case.execute_project_suite(req)
    if res1.coverage is None:
        logger.info("✅ SUCCESS: Coverage block is None when flag is OFF.")
    # 2. Test with flag ON
    logger.info("\n=== 2. Testing with JAVAAPEX_COVERAGE_ENFORCE=true ===")
    os.environ["JAVAAPEX_COVERAGE_ENFORCE"] = "true"
    # Ensure GEMINI_API_KEY is available in the environment; it should be picked up automatically.
    res2 = await use_case.execute_project_suite(req)
    if res2.coverage is not None:
        logger.info("✅ SUCCESS: Coverage block is present when flag is ON.")
        logger.info(f"Coverage block: {res2.coverage}")
        if res2.coverage.get("final", 0) >= res2.coverage.get("initial", 0):
            logger.info("✅ SUCCESS: Final coverage >= initial coverage.")
        else:
            logger.error("❌ FAIL: Final coverage is less than initial coverage.")
    else:
        logger.error("❌ FAIL: Coverage block is None when flag is ON.")

if __name__ == "__main__":
    asyncio.run(verify())
