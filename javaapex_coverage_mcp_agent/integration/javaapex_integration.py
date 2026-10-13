"""
JavaAPEX integration adapter.

Replace the import/path for your existing ChatLLM implementation.

The key integration point is after the existing JUnit generation loop and
before execute_project_suite() returns its final result.
"""

from coverage_agent.agent import JaCoCoCoverageAgent
from coverage_agent.llm import JsonLLMAdapter
from coverage_agent.models import CoverageAgentRequest


async def run_coverage_stage(
    project_dir: str,
    generator,
    build_tool: str | None = None,
    java_version: str | None = None,
):
    # `generator` should expose the existing JavaAPEX ChatLLM.
    # Adjust `generator.chat_llm` to your actual field.
    chat_llm = generator.chat_llm
    llm = JsonLLMAdapter(chat_llm)

    agent = JaCoCoCoverageAgent(llm=llm)

    return await agent.ensure_coverage(
        CoverageAgentRequest(
            project_dir=project_dir,
            build_tool=build_tool,
            java_version=java_version,
            target_coverage=80.0,
            max_iterations=30,
            coverage_metric="LINE",
        )
    )


# In run_unit_tests.py:
#
# agent_result = await run_coverage_stage(
#     project_dir=project_dir,
#     generator=self._generator,
#     build_tool=req.build_tool,
#     java_version=req.java_version,
# )
#
# Then expose agent_result in the existing API response.
