from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from coverage_agent.agent import JaCoCoCoverageAgent
from coverage_agent.build import BuildRunner
from coverage_agent.jacoco import JaCoCoParser
from coverage_agent.models import CoverageAgentRequest
from coverage_agent.project_inspector import ProjectInspector

mcp = FastMCP("javaapex-coverage")

inspector = ProjectInspector()
parser = JaCoCoParser()


class EnvLLM:
    """
    LLM adapter with provider switch.

    Selection via LLM_PROVIDER (default "auto": Gemini primary with
    Ollama as ultimate fallback):
        LLM_PROVIDER=auto    -> GeminiWithOllamaFallback (default).
                                Tries Gemini first; uses Ollama for a call
                                ONLY when the Gemini request fails and the
                                required wait is >= LLM_FALLBACK_DELAY_THRESHOLD
                                (default 180s, i.e. 3 mins).
        LLM_PROVIDER=gemini  -> GeminiCoverageLLM (free tier, 1M context)
        LLM_PROVIDER=ollama  -> OllamaCoverageLLM (local, private)

    Overrides:
        GEMINI_API_KEY / GEMINI_MODEL / GEMINI_TEMP
        OLLAMA_MODEL / OLLAMA_HOST
        LLM_FALLBACK_DELAY_THRESHOLD (seconds, default "180")
        LLM_GEMINI_BUDGET (seconds, default "300")
    """

    def __init__(self, model: str | None = None, provider: str | None = None):
        self._llm = None
        self._model = model
        self._provider = (provider or os.getenv("LLM_PROVIDER") or "auto").lower()

    def _build(self):
        provider = self._provider
        if provider == "auto":
            if os.getenv("GEMINI_API_KEY"):
                from coverage_agent.fallback_llm import GeminiWithOllamaFallback

                return GeminiWithOllamaFallback(gemini_model=self._model)
            from coverage_agent.ollama_llm import OllamaCoverageLLM

            return OllamaCoverageLLM(model=self._model)
        if provider == "gemini":
            from coverage_agent.gemini_llm import GeminiCoverageLLM

            return GeminiCoverageLLM(model=self._model)
        if provider == "ollama":
            from coverage_agent.ollama_llm import OllamaCoverageLLM

            return OllamaCoverageLLM(model=self._model)
        if provider == "gemini-fallback":
            from coverage_agent.fallback_llm import GeminiWithOllamaFallback

            return GeminiWithOllamaFallback(gemini_model=self._model)
        raise RuntimeError(
            f'Unknown LLM_PROVIDER="{provider}". Use "auto", "gemini", "ollama", or "gemini-fallback".'
        )

    async def generate(self, prompt: str) -> str:
        if self._llm is None:
            self._llm = self._build()
        return await self._llm.generate(prompt)


@mcp.tool()
def inspect_project(project_dir: str) -> dict:
    p = inspector.inspect(project_dir)
    return {
        "root": p.root,
        "build_tool": p.build_tool,
        "java_version": p.java_version,
        "test_framework": p.test_framework,
        "jacoco_report": p.jacoco_report,
        "source_roots": p.source_roots,
        "test_roots": p.test_roots,
    }


@mcp.tool()
def run_jacoco(project_dir: str, build_tool: str | None = None) -> dict:
    p = inspector.inspect(project_dir, build_tool)
    result = BuildRunner(p.root).run_coverage(p.build_tool)
    report = Path(p.root) / (
        "target/site/jacoco/jacoco.xml"
        if p.build_tool == "maven"
        else "build/reports/jacoco/test/jacocoTestReport.xml"
    )
    parsed = parser.parse(str(report)) if report.exists() else {}
    return {
        "success": result.ok,
        "output": result.output[-15000:],
        "report": str(report),
        "coverage": parsed,
    }


@mcp.tool()
def get_coverage_gaps(project_dir: str, build_tool: str | None = None) -> dict:
    p = inspector.inspect(project_dir, build_tool)
    report = Path(p.root) / (
        "target/site/jacoco/jacoco.xml"
        if p.build_tool == "maven"
        else "build/reports/jacoco/test/jacocoTestReport.xml"
    )
    if not report.exists():
        return {"error": "JaCoCo report does not exist. Run run_jacoco first."}
    gaps = parser.gaps(
        str(report), p.source_roots[0] if p.source_roots else None
    )
    return {"gaps": [g.model_dump() for g in gaps]}


@mcp.tool()
async def ensure_coverage(
    project_dir: str,
    target_coverage: float = 80.0,
    max_iterations: int = 30,
    max_parallel_shards: int = 4,
    build_tool: str | None = None,
    java_version: str | None = None,
    ignore_test_failures: bool = False,
) -> dict:
    """Drive coverage to target (up to 30 iterations by default). Test execution always tolerates failures so
    a JaCoCo report is produced from whatever ran; set
    ignore_test_failures=True to count coverage-only success."""
    # Drive the shared agent with the environment-selected LLM
    # (default: Gemini primary, Ollama ultimate fallback).
    # Test files only; failed iterations are rolled back.
    # Coverage is always measured from a real JaCoCo report.
    # Returns the full CoverageAgentResult as a dict.
    agent = JaCoCoCoverageAgent(EnvLLM())
    result = await agent.ensure_coverage(
        CoverageAgentRequest(
            project_dir=project_dir,
            target_coverage=target_coverage,
            max_iterations=max_iterations,
            max_parallel_shards=max_parallel_shards,
            build_tool=build_tool,
            java_version=java_version,
            ignore_test_failures=ignore_test_failures,
        )
    )
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
