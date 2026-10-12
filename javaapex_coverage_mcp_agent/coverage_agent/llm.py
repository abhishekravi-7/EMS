from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class CoverageLLM(Protocol):
    async def generate(self, prompt: str) -> str:
        ...


@dataclass
class FileChange:
    path: str
    content: str
    action: str  # create | replace


class JsonLLMAdapter:
    """
    Adapter around JavaAPEX's existing ChatLLM.

    Pass an object implementing:
        async generate(prompt: str) -> str

    The model must return JSON:
    {
      "changes": [
        {"path": "src/test/java/...", "action": "create|replace", "content": "..."}
      ],
      "reasoning": "..."
    }
    """

    def __init__(self, chat_llm):
        self.chat_llm = chat_llm

    async def generate(self, prompt: str) -> str:
        chunks = []
        async for chunk in self.chat_llm.stream_chat(system_prompt="You are a JSON-generating bot.", user_prompt=prompt):
            chunks.append(chunk)
        return "".join(chunks)


def _sanitize_json(text: str) -> str:
    """Best-effort cleanup of malformed JSON from local LLMs."""
    # Strip markdown code fences
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Fix trailing commas
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    # Fix missing commas between objects
    text = re.sub(r'}\s*{', '}, {', text)
    return text


def parse_changes(raw: str) -> list[FileChange]:
    """Parse file changes from LLM JSON output, with robust error handling."""
    text = _sanitize_json(raw)

    try:
        data = json.loads(text, strict=False)
    except json.JSONDecodeError:
        # Try to extract JSON object with regex as fallback
        match = re.search(r'\{.*"changes"\s*:\s*\[.*?\]\s*.*?\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0), strict=False)
            except json.JSONDecodeError:
                logger.warning("[parse_changes] Could not parse LLM JSON even after regex extraction")
                return []
        else:
            logger.warning("[parse_changes] No valid JSON found in LLM output (%d chars)", len(text))
            return []

    if not isinstance(data, dict):
        logger.warning("[parse_changes] Parsed JSON is not a dict")
        return []

    changes = data.get("changes", [])
    if not isinstance(changes, list):
        return []

    result = []
    for item in changes:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        content = item.get("content")
        if not path or not content:
            continue
        result.append(FileChange(
            path=path,
            content=content,
            action=item.get("action", "replace"),
        ))
    return result


def build_generation_prompt(project, gaps, source_text, test_text, build_failure=""):
    gap_text = json.dumps([g.model_dump() for g in gaps], indent=2)
    return f"""
You are the autonomous JavaAPEX Coverage Engineer.

Your job is to improve genuine JaCoCo test coverage to at least the
configured target. Modify/create TEST FILES ONLY. Never modify production
code.

PROJECT
-------
Build tool: {project.build_tool}
Java: {project.java_version or "unknown"}
Test framework: {project.test_framework}

COVERAGE GAPS
-------------
{gap_text}

PRODUCTION SOURCE
-----------------
{source_text}

EXISTING TESTS
--------------
{test_text}

PREVIOUS BUILD/TEST FAILURE
---------------------------
{build_failure or "none"}

Rules:
1. Reuse existing test conventions and dependencies.
2. Target uncovered lines, methods, and branches.
3. Generate meaningful behavioral tests, not coverage padding.
4. Do not change src/main or production configuration.
5. Prefer modifying an existing relevant test file when practical.
6. Ensure imports, constructors, signatures, mocks, and assertions match
   the actual source.
7. Return ONLY valid JSON in this exact shape:

{{
  "changes": [
    {{
      "path": "src/test/java/...",
      "action": "create",
      "content": "complete Java source"
    }}
  ],
  "reasoning": "brief explanation"
}}
""".strip()
