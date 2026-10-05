"""
token_tracing.dashboard — a dependency-free web dashboard for JSONL trace logs.

Reads the JSONL file written by :class:`token_tracing.JsonlTraceSink` and
serves it two ways over plain HTTP (stdlib only — no framework, no build step):

* a small JSON API with CORS enabled, so any application (React, Angular,
  Vite, plain JS, ...) can consume the data and build its own UI on top:

  - ``GET /api/records`` — recent calls, newest first, filterable
  - ``GET /api/summary`` — totals plus per-model / per-endpoint / per-provider
    breakdowns

* a single self-contained HTML page at ``/`` (``dashboard.html``, shipped as
  package data) that renders that same API: summary cards, per-model and
  per-endpoint breakdowns, and a recent-calls table. Inline CSS + vanilla JS,
  no external assets, no build step.

Run it from the command line::

    python -m token_tracing.dashboard --jsonl logs/llm_usage.jsonl --port 8765

Or programmatically::

    from token_tracing.dashboard import run
    run("logs/llm_usage.jsonl", host="127.0.0.1", port=8765)

Embed the page anywhere — ``<iframe src="http://localhost:8765/">``, or drop
``token_tracing/dashboard.html`` into any app's static folder (Vite ``public/``,
Angular ``assets/``, ...) and point it at the API via ``window.TOKEN_TRACING_API``.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import importlib.resources
import json
import logging
import math
import urllib.parse
from pathlib import Path
from typing import Any

logger = logging.getLogger("token_tracing.dashboard")

DEFAULT_PORT = 8765
MAX_LIMIT = 1000

__all__ = [
    "DEFAULT_PORT",
    "DashboardHTTPServer",
    "create_server",
    "filter_records",
    "load_records",
    "run",
    "summarize",
]


# ── Data layer ─────────────────────────────────────────────────────────────────

def load_records(path: str | Path) -> list[dict[str, Any]]:
    """Parse ``path`` (JSONL from :class:`JsonlTraceSink`) newest-first.

    Tolerates a missing file (returns ``[]``) and malformed or half-written
    lines (skipped with a warning), so a concurrent append never breaks the
    page.
    """
    records: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("skipping malformed line %d in %s", lineno, path)
    except FileNotFoundError:
        return []
    records.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    return records


def filter_records(
    records: list[dict[str, Any]],
    *,
    model: str | None = None,
    endpoint: str | None = None,
    provider: str | None = None,
    error_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Newest-first records matching the filters, capped at ``limit``.

    ``model`` / ``endpoint`` / ``provider`` are exact matches; ``error_only``
    keeps only records carrying an ``error`` field.
    """
    limit = MAX_LIMIT if limit is None else max(0, min(int(limit), MAX_LIMIT))
    out: list[dict[str, Any]] = []
    for rec in records:
        if model and rec.get("model") != model:
            continue
        if endpoint and rec.get("endpoint") != endpoint:
            continue
        if provider and rec.get("provider") != provider:
            continue
        if error_only and not rec.get("error"):
            continue
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate records into the ``/api/summary`` payload."""
    total_input = total_output = total_cached = 0
    total_cost = 0.0
    error_calls = 0
    cached_calls = 0
    durations: list[float] = []
    last_ts: str | None = None
    buckets: dict[str, dict[str, dict[str, Any]]] = {
        "model": {}, "endpoint": {}, "provider": {},
    }

    for rec in records:
        total_input += rec.get("input_tokens") or 0
        total_output += rec.get("output_tokens") or 0
        total_cached += rec.get("cached_tokens") or 0
        total_cost += rec.get("estimated_cost_usd") or 0.0
        if rec.get("error"):
            error_calls += 1
        if rec.get("prompt_cache_hit") or (rec.get("cached_tokens") or 0) > 0:
            cached_calls += 1
        duration = rec.get("duration_ms")
        if duration is not None:
            durations.append(float(duration))
        ts = rec.get("timestamp")
        if ts:
            last_ts = max(last_ts or "", ts)
        for key, bucket in buckets.items():
            row = bucket.setdefault(
                rec.get(key) or "(unknown)",
                {"calls": 0, "total_tokens": 0, "cost_usd": 0.0, "errors": 0},
            )
            row["calls"] += 1
            row["total_tokens"] += rec.get("total_tokens") or 0
            row["cost_usd"] += rec.get("estimated_cost_usd") or 0.0
            if rec.get("error"):
                row["errors"] += 1

    def _sorted(bucket: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            ({"name": name, **row} for name, row in bucket.items()),
            key=lambda r: (r["cost_usd"], r["calls"]),
            reverse=True,
        )

    durations.sort()
    p95 = None
    if durations:
        p95 = durations[math.ceil(len(durations) * 0.95) - 1]
    n = len(records)

    return {
        "total_calls": n,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "total_cached_tokens": total_cached,
        "total_cost_usd": round(total_cost, 6),
        "error_calls": error_calls,
        "error_rate": round(error_calls / n, 4) if n else 0.0,
        "cache_hit_rate": round(cached_calls / n, 4) if n else 0.0,
        "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else None,
        "p95_duration_ms": round(p95, 1) if p95 is not None else None,
        "last_record_at": last_ts,
        "per_model": _sorted(buckets["model"]),
        "per_endpoint": _sorted(buckets["endpoint"]),
        "per_provider": _sorted(buckets["provider"]),
    }


# ── HTTP layer ─────────────────────────────────────────────────────────────────

class DashboardHTTPServer(http.server.ThreadingHTTPServer):
    """Threaded HTTP server serving the token-tracing dashboard."""


def create_server(
    jsonl_path: str | Path, host: str = "127.0.0.1", port: int = 0
) -> DashboardHTTPServer:
    """Create a dashboard server for ``jsonl_path`` (``port=0`` → ephemeral)."""
    handler = functools.partial(_DashboardHandler, jsonl_path=Path(jsonl_path))
    return DashboardHTTPServer((host, port), handler)


class _DashboardHandler(http.server.BaseHTTPRequestHandler):
    server_version = "token-tracing-dashboard/1.0"

    def __init__(self, *args: Any, jsonl_path: Path, **kwargs: Any) -> None:
        self._jsonl_path = jsonl_path
        super().__init__(*args, **kwargs)

    # ── plumbing ───────────────────────────────────────────────────────────────

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(data)

    def _send_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _query(self) -> dict[str, str]:
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        return {key: values[-1] for key, values in parsed.items()}

    def _filters(self) -> dict[str, Any]:
        q = self._query()
        try:
            limit = int(q.get("limit", "100"))
        except ValueError:
            limit = 100
        return {
            "model": q.get("model") or None,
            "endpoint": q.get("endpoint") or None,
            "provider": q.get("provider") or None,
            "error_only": q.get("error", "").lower() in {"1", "true", "yes"},
            "limit": limit,
        }

    # ── routes ─────────────────────────────────────────────────────────────────

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path in {"/api/records", "/api/records/"}:
            records = filter_records(load_records(self._jsonl_path), **self._filters())
            self._send_json({"count": len(records), "records": records})
        elif path in {"/api/summary", "/api/summary/"}:
            records = filter_records(load_records(self._jsonl_path), **self._filters())
            self._send_json(summarize(records))
        elif path in {"/", "/index.html"}:
            self._send_html(_load_html())
        else:
            self._send_json({"error": f"not found: {path}"}, status=404)

    def log_message(self, msg: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), msg % args)


def _load_html() -> str:
    """Return the bundled ``dashboard.html`` (shipped as package data)."""
    try:
        return (
            importlib.resources.files("token_tracing")
            .joinpath("dashboard.html")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        return (
            "<!doctype html><html><body><h1>dashboard.html not found</h1>"
            "<p>The dashboard page ships as package data; reinstall the "
            "package if it is missing.</p></body></html>"
        )


# ── Entry points ───────────────────────────────────────────────────────────────

def run(jsonl_path: str | Path, host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
    """Serve the dashboard until interrupted (Ctrl+C)."""
    server = create_server(jsonl_path, host=host, port=port)
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"token-tracing dashboard: {url}  (jsonl: {jsonl_path})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m token_tracing.dashboard",
        description="Serve a web dashboard for a token-tracing JSONL log.",
    )
    parser.add_argument(
        "--jsonl",
        default="llm_usage.jsonl",
        help="path to the JSONL trace log (default: llm_usage.jsonl)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"bind port (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.jsonl, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
