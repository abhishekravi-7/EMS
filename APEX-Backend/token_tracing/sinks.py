"""
Trace sinks — pluggable destinations for completed :class:`LLMCallRecord`
records.

Applications choose their storage: VOXA appends JSON lines to
``logs/llm_usage.jsonl`` (and separately persists per-query traces to Mongo via
its own orchestrator layer); other apps can implement the :class:`TraceSink`
protocol for their own store (database, queue, log aggregator, ...) and pass
it to ``init_token_tracing``.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Protocol

from .core import LLMCallRecord

logger = logging.getLogger("token_tracing")


class TraceSink(Protocol):
    """Anything that can persist a finished LLM call record."""

    def write(self, record: LLMCallRecord) -> None: ...


class NullTraceSink:
    """Discards records — the default when no sink is configured."""

    def write(self, record: LLMCallRecord) -> None:  # noqa: ARG002
        return None


class JsonlTraceSink:
    """
    Appends one JSON line per record to ``path`` (thread-safe).

    Mirrors the append behaviour VOXA used for ``logs/llm_usage.jsonl``:
    the parent directory is created on demand and a malformed record never
    raises — it is logged as a warning so one bad line can't take down a
    request that already succeeded.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def write(self, record: LLMCallRecord) -> None:
        try:
            line = json.dumps(record.to_dict(), default=str)
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except Exception as exc:  # pragma: no cover - defensive, must never raise  # noqa: BLE001
            logger.warning("[USAGE] could not write trace log: %s", exc)

    def append_raw(self, entry: dict) -> None:
        """Append one raw JSON line (a plain dict) to the same file.

        Exposed for legacy appenders that serialise dicts directly instead of
        going through :class:`LLMCallRecord` — never raises on failure.
        """
        try:
            line = json.dumps(entry, default=str)
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except Exception as exc:  # pragma: no cover - defensive, must never raise  # noqa: BLE001
            logger.warning("[USAGE] could not write trace log: %s", exc)


class ListTraceSink:
    """In-memory sink that appends record dicts to a list — useful for tests."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def write(self, record: LLMCallRecord) -> None:
        self.records.append(record.to_dict())
