import asyncio
from coverage_agent.agent import JaCoCoCoverageAgent
from coverage_agent.models import CoverageAgentRequest
from app.infrastructure.llm.chat_llm import ChatLLM
from coverage_agent.llm import JsonLLMAdapter

async def main():
    llm = ChatLLM()
    agent_llm = JsonLLMAdapter(llm)
    agent = JaCoCoCoverageAgent(llm=agent_llm)
    req = CoverageAgentRequest(
        project_dir=r"C:\Users\Afzal\Documents\Apex\JavaAPEX\APEX-Backend\storage\migration-jobs\job_a34fb67de3f3\migrated-repo",
        target_coverage=80.0,
        max_iterations=1,
        build_tool="maven",
        coverage_metric="LINE"
    )
    print("Agent starting...")
    res = await agent.ensure_coverage(req)
    print("Result:", res)

asyncio.run(main())
