"""Dynamic Data Resolver for resolving runtime path parameters, entity IDs, and preconditions."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


@dataclass
class RuntimeContext:
    """Live runtime context storing real entity instances, credentials, and session state."""

    entities: dict[str, list[str]] = field(default_factory=dict)
    captured_ids: dict[str, str] = field(default_factory=dict)
    creation_endpoints: dict[str, dict[str, Any]] = field(default_factory=dict)
    auth_state: str = "UNAUTHENTICATED"
    cookies: list[dict[str, Any]] = field(default_factory=list)
    tokens: dict[str, str] = field(default_factory=dict)

    def store_entity_id(self, entity_type: str, entity_id: str) -> None:
        clean_type = entity_type.lower().rstrip("s")
        if clean_type not in self.entities:
            self.entities[clean_type] = []
        if entity_id not in self.entities[clean_type]:
            self.entities[clean_type].append(entity_id)

    def get_entity_id(self, entity_type: str) -> str | None:
        clean_type = entity_type.lower().rstrip("s")
        ids = self.entities.get(clean_type)
        return ids[0] if ids else None

    def store_id(self, param_name: str, entity_id: str) -> None:
        self.captured_ids[param_name] = entity_id

    def get_id(self, param_name: str) -> str | None:
        return self.captured_ids.get(param_name)


@dataclass
class EndpointResolution:
    """Represents the outcome of dynamic endpoint parameter resolution."""

    endpoint: str
    is_resolved: bool
    issue: str | None = None
    param_sources: dict[str, str] = field(default_factory=dict)
    param_values: dict[str, Any] = field(default_factory=dict)

    def __iter__(self):
        return iter((self.endpoint, self.is_resolved, self.issue, self.param_sources, self.param_values))

    def __getitem__(self, idx: int) -> Any:
        return (self.endpoint, self.is_resolved, self.issue, self.param_sources, self.param_values)[idx]


class DynamicDataResolver:
    """Discovers and resolves dynamic entity IDs and path variables from live application state, seed data, and creation endpoints."""

    def __init__(
        self,
        repo_dir: Path | None = None,
        log_fn: Any | None = None,
        runtime_context: RuntimeContext | None = None,
    ) -> None:
        self.repo_dir = repo_dir
        self.log_fn = log_fn or (lambda m, lvl="INFO": logger.info(f"[RESOLVER] {m}"))
        self.runtime_context = runtime_context or RuntimeContext()
        self._seeded_id_cache: dict[str, list[str]] = {}
        self._live_entity_cache: dict[str, list[str]] = {}
        self._scan_seed_sql_ids()

    def register_creation_endpoints(self, endpoints: list[dict[str, Any]]) -> None:
        """Indexes entity creation endpoints discovered from repository analysis."""
        for ep in endpoints:
            method = (ep.get("method") or "GET").upper()
            raw_path = ep.get("endpoint") or "/"
            if method == "POST" and not any(k in raw_path.lower() for k in ["login", "auth", "search", "filter", "token"]):
                # Extract probable entity name from collection path
                segments = [s for s in raw_path.strip("/").split("/") if s and not s.startswith("{") and not s.startswith(":")]
                if segments:
                    ent_name = segments[-1].lower().rstrip("s")
                    self.runtime_context.creation_endpoints[ent_name] = {
                        "endpoint": raw_path,
                        "method": "POST",
                        "request_body_sample": ep.get("request_body_sample") or ep.get("body_schema") or {},
                        "file": ep.get("file"),
                    }

    def _scan_seed_sql_ids(self) -> None:
        """Extracts concrete entity IDs declared in repository seed SQL files (e.g. data.sql, seed.sql)."""
        if not self.repo_dir or not self.repo_dir.exists():
            return

        for sql_file in self.repo_dir.rglob("*.sql"):
            try:
                content = sql_file.read_text(encoding="utf-8", errors="ignore")
                # Look for INSERT INTO table_name (ID, ...) VALUES (10001, ...)
                matches = re.finditer(
                    r"insert\s+into\s+([a-zA-Z0-9_]+)\s*\([^)]*\bid\b[^)]*\)\s*values\s*\(\s*([0-9]+|['\"][^'\"]+['\"])",
                    content,
                    re.IGNORECASE,
                )
                for m in matches:
                    tbl = m.group(1).lower().rstrip("s")
                    raw_id = m.group(2).strip().strip("'\"")
                    if raw_id:
                        if tbl not in self._seeded_id_cache:
                            self._seeded_id_cache[tbl] = []
                        if raw_id not in self._seeded_id_cache[tbl]:
                            self._seeded_id_cache[tbl].append(raw_id)
                            self.runtime_context.store_entity_id(tbl, raw_id)
            except Exception as e:
                logger.debug("Failed scanning SQL IDs in %s: %s", sql_file, e)

        if self._seeded_id_cache:
            self.log_fn(f"Discovered seeded entity IDs from SQL: {list(self._seeded_id_cache.keys())}")

    def get_parent_collection_endpoint(self, endpoint: str) -> str | None:
        """Derives the parent collection endpoint from a parametric route.
        e.g. /todos/{id}/assign -> /todos
             /api/notifications/{id}/read -> /api/notifications
             /todos/{id} -> /todos
        """
        segments = [s for s in endpoint.strip("/").split("/") if s]
        parent_segments: list[str] = []
        for s in segments:
            if s.startswith("{") or s.startswith(":") or s.isdigit():
                break
            parent_segments.append(s)

        if parent_segments:
            return "/" + "/".join(parent_segments)
        return None

    def probe_live_ids(self, parent_endpoint: str, base_url: str, headers: dict[str, str] | None = None) -> list[str]:
        """Queries the live parent endpoint to discover existing IDs."""
        cache_key = f"{base_url}{parent_endpoint}"
        if cache_key in self._live_entity_cache:
            return self._live_entity_cache[cache_key]

        target_url = f"{base_url.rstrip('/')}/{parent_endpoint.lstrip('/')}"
        req_headers = {"Accept": "application/json", **(headers or {})}

        try:
            req = urllib.request.Request(target_url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    raw_data = resp.read().decode("utf-8", errors="ignore")
                    parsed = json.loads(raw_data)
                    found_ids: list[str] = []

                    items = parsed if isinstance(parsed, list) else (
                        parsed.get("items") or parsed.get("content") or parsed.get("data") or []
                        if isinstance(parsed, dict) else []
                    )

                    for it in items:
                        if isinstance(it, dict):
                            val = it.get("id") or it.get("ID") or it.get("uuid")
                            if val is not None:
                                found_ids.append(str(val))

                    if found_ids:
                        self.log_fn(f"Discovered {len(found_ids)} live entity ID(s) from {parent_endpoint}: {found_ids[:3]}")
                        self._live_entity_cache[cache_key] = found_ids
                        # Record in runtime context
                        ent = parent_endpoint.strip("/").split("/")[-1].lower().rstrip("s")
                        for fid in found_ids:
                            self.runtime_context.store_entity_id(ent, fid)
                        return found_ids
        except Exception as e:
            logger.debug("Live probe for %s failed: %s", target_url, e)

        return []

    def create_entity_instance(
        self,
        entity_type: str,
        base_url: str,
        api_context: Any = None,
        headers: dict[str, str] | None = None,
    ) -> str | None:
        """Creates a real instance of an entity via its creation endpoint and captures its generated ID."""
        clean_type = entity_type.lower().rstrip("s")
        creator = self.runtime_context.creation_endpoints.get(clean_type)
        if not creator:
            return None

        creation_ep = creator["endpoint"]
        payload = creator.get("request_body_sample") or {}
        target_url = f"{base_url.rstrip('/')}/{creation_ep.lstrip('/')}"

        self.log_fn(f"Creating runtime entity instance for '{clean_type}' via POST {creation_ep}...")

        # 1. Try Playwright APIRequestContext if available
        if api_context:
            try:
                resp = api_context.post(
                    target_url,
                    data=payload,
                    headers={"Content-Type": "application/json", **(headers or {})},
                    timeout=5000,
                )
                if resp.status in (200, 201):
                    # Check Location header
                    loc = resp.headers.get("location")
                    if loc:
                        loc_id = loc.rstrip("/").split("/")[-1]
                        if loc_id and loc_id != clean_type:
                            self.runtime_context.store_entity_id(clean_type, loc_id)
                            return loc_id

                    try:
                        body_json = resp.json()
                        if isinstance(body_json, dict):
                            val = body_json.get("id") or body_json.get("ID") or body_json.get("uuid") or body_json.get(f"{clean_type}Id")
                            if val is not None:
                                sval = str(val)
                                self.runtime_context.store_entity_id(clean_type, sval)
                                return sval
                    except Exception:
                        pass
            except Exception as e:
                self.log_fn(f"Entity creation via Playwright API context failed: {e}", "WARN")

        # 2. Try standard urllib request
        try:
            req_data = json.dumps(payload).encode("utf-8") if payload else b"{}"
            req_headers = {"Content-Type": "application/json", "Accept": "application/json", **(headers or {})}
            req = urllib.request.Request(target_url, data=req_data, headers=req_headers, method="POST")
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status in (200, 201):
                    raw_data = resp.read().decode("utf-8", errors="ignore")
                    if raw_data:
                        body_json = json.loads(raw_data)
                        if isinstance(body_json, dict):
                            val = body_json.get("id") or body_json.get("ID") or body_json.get("uuid")
                            if val is not None:
                                sval = str(val)
                                self.runtime_context.store_entity_id(clean_type, sval)
                                return sval
        except Exception as e:
            logger.debug("Runtime entity creation for %s failed: %s", target_url, e)

        return None

    def resolve_endpoint(
        self,
        endpoint: str,
        test_data: dict[str, Any] | None = None,
        base_url: str | None = None,
        headers: dict[str, str] | None = None,
        api_context: Any | None = None,
    ) -> EndpointResolution:
        """
        Resolves path variables in an endpoint strictly from evidence:
        1. Explicit test_data / path_params with concrete evidence
        2. RuntimeContext captured IDs
        3. Live collection GET query
        4. Seeded SQL cache from repository data.sql
        5. Live entity creation via application endpoint

        Returns EndpointResolution with resolved endpoint, is_resolved, issue, param_sources, and param_values.
        """
        data = test_data or {}
        explicit_params = data.get("path_params", {}) if isinstance(data.get("path_params"), dict) else {}

        # Find all parameters like {id}, {todoId}, :id
        tokens = re.findall(r"\{([a-zA-Z0-9_]+)(?::[^\}]+)?\}", endpoint)
        if not tokens:
            tokens = re.findall(r":([a-zA-Z0-9_]+)", endpoint)

        if not tokens:
            return EndpointResolution(endpoint=endpoint, is_resolved=True, issue=None, param_sources={}, param_values={})

        resolved = endpoint
        parent_ep = self.get_parent_collection_endpoint(endpoint)
        live_ids: list[str] = []
        if parent_ep and base_url:
            live_ids = self.probe_live_ids(parent_ep, base_url, headers)

        param_sources: dict[str, str] = {}
        param_values: dict[str, Any] = {}

        for param in tokens:
            val: str | None = None
            source_desc: str | None = None
            param_lower = param.lower()

            # 1. Check RuntimeContext captured IDs
            ctx_id = self.runtime_context.get_id(param) or self.runtime_context.get_id(param_lower)
            if ctx_id:
                val = ctx_id
                source_desc = f"RuntimeContext captured ID ({param}={val})"

            # 2. Check explicit test_data
            if not val and param in explicit_params:
                val = str(explicit_params[param])
                source_desc = f"Explicit test_data.path_params ({param}={val})"
            elif not val and param in data and not isinstance(data[param], (dict, list)):
                val = str(data[param])
                source_desc = f"Explicit test_data field ({param}={val})"

            # 3. Check live discovered IDs from GET parent collection
            if not val and live_ids:
                val = live_ids[0]
                source_desc = f"Live GET query on parent endpoint '{parent_ep}'"

            # 4. Check RuntimeContext / seeded SQL IDs by matching resource name
            if not val:
                resource_candidates = [
                    param_lower.replace("id", "").rstrip("s"),
                    (parent_ep.strip("/").split("/")[-1].lower().rstrip("s")) if parent_ep else "",
                ]
                for rc in resource_candidates:
                    if rc:
                        ent_val = self.runtime_context.get_entity_id(rc)
                        if ent_val:
                            val = ent_val
                            source_desc = f"Seeded repository SQL data for table '{rc}'"
                            break
                        if rc in self._seeded_id_cache and self._seeded_id_cache[rc]:
                            val = self._seeded_id_cache[rc][0]
                            source_desc = f"Seeded repository SQL data for table '{rc}'"
                            break

            # 5. Attempt live runtime entity creation via application
            if not val and base_url:
                target_ent = param_lower.replace("id", "").rstrip("s") or (
                    parent_ep.strip("/").split("/")[-1].lower().rstrip("s") if parent_ep else ""
                )
                if target_ent:
                    created_id = self.create_entity_instance(target_ent, base_url, api_context, headers)
                    if created_id:
                        val = created_id
                        source_desc = f"Dynamically created entity instance via POST endpoint for '{target_ent}'"

            # If still not found: DO NOT ASSUME OR INVENT LITERAL IDS (1, 10001, etc.)!
            if not val:
                return EndpointResolution(
                    endpoint=endpoint,
                    is_resolved=False,
                    issue=f"Parameter '{param}' cannot be resolved: no seed data, live instance, or creation path found in repository.",
                    param_sources=param_sources,
                    param_values=param_values,
                )

            # Store resolved parameter and source
            param_sources[param] = source_desc or "Repository evidence"
            param_values[param] = val
            self.runtime_context.store_id(param, val)

            # Replace token in endpoint
            resolved = re.sub(rf"\{{{param}(?::[^\}}]+)?\}}", val, resolved)
            resolved = re.sub(rf":{param}\b", val, resolved)

        return EndpointResolution(
            endpoint=resolved,
            is_resolved=True,
            issue=None,
            param_sources=param_sources,
            param_values=param_values,
        )
