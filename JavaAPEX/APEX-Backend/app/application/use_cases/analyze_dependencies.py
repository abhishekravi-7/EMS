"""LLM-Powered Dependency Risk & Migration Analysis Use Case.

Assesses repository dependencies using repository-grounded LLM inference,
strictly preserving detected coordinates and versions while enriching risk levels,
categories, contextual explanations, and actionable migration recommendations.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Any
try:
    from cachetools import LRUCache
except ImportError:
    class LRUCache(dict):  # type: ignore[no-redef]
        def __init__(self, maxsize: int = 128) -> None:
            super().__init__()
            self.maxsize = maxsize

        def __setitem__(self, key: Any, value: Any) -> None:
            if len(self) >= self.maxsize and key not in self:
                oldest = next(iter(self))
                del self[oldest]
            super().__setitem__(key, value)

from sqlalchemy.orm import Session

from app.core.context import user_id_ctx, llm_values_ctx
from app.core.exceptions import LLMResponseInvalidError
from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.llm.huggingface_client import HuggingFaceClient
from app.infrastructure.llm.prompt_templates import (
    DEPENDENCY_ANALYSIS_SYSTEM_PROMPT,
    build_dependency_analysis_prompt,
)
from app.infrastructure.persistence.models import User
from app.schemas.dependency_analysis_schema import (
    AnalyzedDependencyItem,
    DependencyAnalysisRequest,
    DependencyAnalysisResponse,
    DependencyItemInput,
    DependencyRiskCounts,
)

logger = logging.getLogger("discovery")

_CACHE_DIR = Path(".cache/dependency_analysis")
_memory_cache: LRUCache = LRUCache(maxsize=100)
_in_flight_locks: dict[tuple[int, str], asyncio.Lock] = {}


def _get_flight_lock(fp: str) -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    key = (id(loop), fp)
    if key not in _in_flight_locks:
        _in_flight_locks[key] = asyncio.Lock()
    return _in_flight_locks[key]


def compute_analysis_fingerprint(request: DependencyAnalysisRequest) -> str:
    deps = sorted(
        [
            f"{d.group_id or ''}:{d.artifact_id or ''}:{d.current_version or d.resolved_version or ''}:{d.scope or ''}"
            for d in (request.dependencies or [])
        ]
    )
    raw = f"{request.source_java_version}:{request.target_java_version}:{str(request.build_tool or '').upper()}:{','.join(deps)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

# Allowed standard risk levels and categories
ALLOWED_RISK_LEVELS = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
ALLOWED_CATEGORIES = {
    "Framework",
    "Persistence",
    "Security",
    "Database",
    "Testing",
    "Logging",
    "Web",
    "Build",
    "Utility",
    "Other",
}
ALLOWED_COMPLEXITIES = {"NONE", "LIGHT", "MODERATE", "COMPLEX"}


def _heuristic_classify_category(group: str, artifact: str) -> str:
    gid = (group or "").lower()
    aid = (artifact or "").lower()
    coord = f"{gid}:{aid}"

    if any(k in coord for k in ["test", "junit", "mockito", "assertj", "mock", "wiremock"]):
        return "Testing"
    if any(k in coord for k in ["security", "auth", "oauth", "jwt", "crypto", "bcrypt", "shiro"]):
        return "Security"
    if any(k in coord for k in ["jpa", "hibernate", "persistence", "mybatis", "jooq"]):
        return "Persistence"
    if any(k in coord for k in ["database", "postgres", "mysql", "oracle", "h2", "jdbc", "mariadb", "flyway", "liquibase"]):
        return "Database"
    if any(k in coord for k in ["logging", "log4j", "logback", "slf4j"]):
        return "Logging"
    if any(k in coord for k in ["web", "servlet", "rest", "jersey", "tomcat", "jetty", "graphql"]):
        return "Web"
    if any(k in coord for k in ["plugin", "gradle", "maven-", "build"]):
        return "Build"
    if any(k in coord for k in ["spring", "quarkus", "micronaut", "struts", "guice", "jakarta", "javax"]):
        return "Framework"
    if any(k in coord for k in ["commons", "guava", "lombok", "jackson", "gson", "apache"]):
        return "Utility"
    return "Other"


def _build_fallback_analysis(
    dependencies: list[DependencyItemInput],
    build_tool: str | None,
    source_java: str | None,
) -> DependencyAnalysisResponse:
    """Deterministic fallback analysis when LLM is unavailable or fails."""
    analyzed_list: list[AnalyzedDependencyItem] = []

    for dep in dependencies:
        gid = dep.group_id or ""
        aid = dep.artifact_id or ""
        ver = dep.current_version or dep.resolved_version or "unknown"
        coord = f"{gid}:{aid}" if gid and aid else (aid or gid or "unknown")
        dep_id = coord
        name = aid or gid or "dependency"

        category = _heuristic_classify_category(gid, aid)
        risk = "LOW"
        explanation = f"{name} detected in {build_tool or 'project'} build configuration."
        recommendation = "Verify compatibility with target Java release."

        # Jakarta EE namespace shift detection
        if gid.startswith("javax.") or aid.startswith("javax."):
            risk = "CRITICAL"
            explanation = f"{name} uses the legacy javax.* namespace and requires migration to jakarta.*."
            recommendation = "Update coordinates and import statements to Jakarta EE 9+ equivalent."
        elif "log4j" in aid and ver.startswith("1."):
            risk = "CRITICAL"
            explanation = f"{name} is on legacy Log4j 1.x which has reached End-of-Life."
            recommendation = "Upgrade to Log4j 2.x or slf4j/logback logging facade."
        elif any(k in aid for k in ["struts", "velocity"]):
            risk = "HIGH"
            explanation = f"{name} is a legacy framework requiring major modernization."
            recommendation = "Plan refactoring to modern Spring Web / REST architecture."
        elif category in ("Security", "Persistence", "Database"):
            risk = "MEDIUM"
            explanation = f"{name} interacts with {category.lower()} runtime and requires API review."
            recommendation = "Test database drivers and security configurations against modern Java."

        analyzed_list.append(
            AnalyzedDependencyItem(
                id=dep_id,
                group=gid,
                artifact=aid,
                name=name,
                version=ver,
                category=category,
                risk=risk,
                explanation=explanation,
                recommendation=recommendation,
            )
        )

    crit_cnt = sum(1 for d in analyzed_list if d.risk == "CRITICAL")
    high_cnt = sum(1 for d in analyzed_list if d.risk == "HIGH")
    med_cnt = sum(1 for d in analyzed_list if d.risk == "MEDIUM")
    low_cnt = sum(1 for d in analyzed_list if d.risk == "LOW")
    tot_cnt = len(analyzed_list)

    if crit_cnt > 0:
        overall_risk = "CRITICAL"
    elif high_cnt > 0:
        overall_risk = "HIGH"
    elif med_cnt > 0:
        overall_risk = "MEDIUM"
    else:
        overall_risk = "LOW"

    if tot_cnt == 0:
        complexity = "NONE"
    elif tot_cnt <= 10 and crit_cnt == 0 and high_cnt == 0:
        complexity = "LIGHT"
    elif tot_cnt <= 35 and crit_cnt == 0:
        complexity = "MODERATE"
    else:
        complexity = "COMPLEX"

    return DependencyAnalysisResponse(
        overall_risk=overall_risk,
        complexity=complexity,
        overall_explanation=f"Based on {tot_cnt} dependencies, {crit_cnt + high_cnt} require explicit migration attention.",
        complexity_explanation=f"Dependency volume ({tot_cnt}) and framework distribution evaluated.",
        counts=DependencyRiskCounts(
            critical=crit_cnt,
            high=high_cnt,
            medium=med_cnt,
            low=low_cnt,
            total=tot_cnt,
        ),
        dependencies=analyzed_list,
        provider_used="heuristic",
    )


class AnalyzeDependenciesUseCase:
    def __init__(
        self,
        llm_client: HuggingFaceClient | None = None,
        chat_llm: ChatLLM | None = None,
    ) -> None:
        self._llm = llm_client or HuggingFaceClient()
        self._chat_llm = chat_llm or ChatLLM()

    async def execute(
        self,
        request: DependencyAnalysisRequest,
        db: Session | None = None,
        current_user: User | None = None,
    ) -> DependencyAnalysisResponse:
        input_deps = request.dependencies or []
        if not input_deps:
            return DependencyAnalysisResponse(
                overall_risk="LOW",
                complexity="NONE",
                overall_explanation="No dependencies were detected in this repository.",
                complexity_explanation="Zero dependencies detected.",
                counts=DependencyRiskCounts(),
                dependencies=[],
                provider_used="heuristic",
            )

        fp = compute_analysis_fingerprint(request)
        if fp in _memory_cache:
            return _memory_cache[fp]

        flight_lock = _get_flight_lock(fp)
        async with flight_lock:
            if fp in _memory_cache:
                return _memory_cache[fp]

            result = await self._execute_internal(request, input_deps, db, current_user)
            _memory_cache[fp] = result
            return result

    async def _execute_internal(
        self,
        request: DependencyAnalysisRequest,
        input_deps: list[DependencyItemInput],
        db: Session | None = None,
        current_user: User | None = None,
    ) -> DependencyAnalysisResponse:
        user_token = None
        llm_token = None
        if current_user:
            user_token = user_id_ctx.set(current_user.id)
            if getattr(current_user, "llm_values", None):
                llm_token = llm_values_ctx.set(current_user.llm_values)

        try:
            # Batch dependencies in chunks of up to 30 to comfortably fit context window
            batch_size = 30
            batches = [input_deps[i : i + batch_size] for i in range(0, len(input_deps), batch_size)]
            all_analyzed_map: dict[str, dict[str, Any]] = {}
            overall_risk_candidates: list[str] = []
            complexity_candidates: list[str] = []
            overall_explanations: list[str] = []
            complexity_explanations: list[str] = []
            providers_used: set[str] = set()

            for batch in batches:
                dep_dicts = [
                    {
                        "id": f"{d.group_id or ''}:{d.artifact_id or ''}",
                        "group_id": d.group_id or "",
                        "artifact_id": d.artifact_id or "",
                        "current_version": d.current_version or d.resolved_version or "unknown",
                        "scope": d.scope or "compile",
                    }
                    for d in batch
                ]

                user_prompt = build_dependency_analysis_prompt(
                    dependencies=dep_dicts,
                    source_java_version=request.source_java_version,
                    target_java_version=request.target_java_version,
                    build_tool=request.build_tool,
                    frameworks=request.frameworks or [],
                    testing_frameworks=request.testing_frameworks or [],
                    spring_boot_version=request.spring_boot_version,
                    api_endpoint_count=request.api_endpoint_count,
                )

                try:
                    logger.debug("[DependencyAnalysis] Attempting Hugging Face (primary)")
                    raw_json = await self._llm.chat_json(DEPENDENCY_ANALYSIS_SYSTEM_PROMPT, user_prompt)
                    providers_used.add("huggingface")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[DependencyAnalysis] Hugging Face failed, falling back to Strategy Chat LLM. Reason: %s",
                        exc,
                    )
                    response_text = ""
                    async for chunk in self._chat_llm.stream_chat(
                        system_prompt=DEPENDENCY_ANALYSIS_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        endpoint="dependency_analysis_fallback",
                    ):
                        response_text += chunk
                    raw_json = self._extract_json(response_text)
                    providers_used.add(self._chat_llm.last_provider or "fallback")

                raw_deps = raw_json.get("dependencies") or []

                if raw_json.get("overall_risk"):
                    overall_risk_candidates.append(str(raw_json["overall_risk"]).strip().upper())
                if raw_json.get("complexity"):
                    complexity_candidates.append(str(raw_json["complexity"]).strip().upper())
                if raw_json.get("overall_explanation"):
                    overall_explanations.append(str(raw_json["overall_explanation"]).strip())
                if raw_json.get("complexity_explanation"):
                    complexity_explanations.append(str(raw_json["complexity_explanation"]).strip())

                for item in raw_deps:
                    if isinstance(item, dict):
                        item_id = str(item.get("id") or item.get("artifact") or "").strip().lower()
                        coord = f"{str(item.get('group') or '').strip().lower()}:{str(item.get('artifact') or '').strip().lower()}"
                        all_analyzed_map[item_id] = item
                        all_analyzed_map[coord] = item

            # Now map every original input dependency strictly to its analyzed metadata
            final_dependencies: list[AnalyzedDependencyItem] = []
            for dep in input_deps:
                gid = dep.group_id or ""
                aid = dep.artifact_id or ""
                ver = dep.current_version or dep.resolved_version or "unknown"
                coord = f"{gid}:{aid}" if gid and aid else (aid or gid or "unknown")
                dep_id = coord
                name = aid or gid or "dependency"

                # Look up analyzed entry
                llm_entry = all_analyzed_map.get(dep_id.lower()) or all_analyzed_map.get(coord.lower()) or all_analyzed_map.get(aid.lower()) or {}

                cat = str(llm_entry.get("category") or "").strip().title()
                if cat not in ALLOWED_CATEGORIES:
                    cat = _heuristic_classify_category(gid, aid)

                risk = str(llm_entry.get("risk") or "").strip().upper()
                if risk not in ALLOWED_RISK_LEVELS:
                    risk = "LOW"

                explanation = str(llm_entry.get("explanation") or "").strip()
                if not explanation:
                    explanation = f"{name} evaluated in {request.build_tool or 'project'} configuration."

                recommendation = str(llm_entry.get("recommendation") or "").strip()
                if not recommendation:
                    recommendation = "Verify compatibility with target Java version."

                final_dependencies.append(
                    AnalyzedDependencyItem(
                        id=dep_id,
                        group=gid,
                        artifact=aid,
                        name=name,
                        version=ver,
                        category=cat,
                        risk=risk,
                        explanation=explanation,
                        recommendation=recommendation,
                    )
                )

            # Compute exact risk counts
            crit_cnt = sum(1 for d in final_dependencies if d.risk == "CRITICAL")
            high_cnt = sum(1 for d in final_dependencies if d.risk == "HIGH")
            med_cnt = sum(1 for d in final_dependencies if d.risk == "MEDIUM")
            low_cnt = sum(1 for d in final_dependencies if d.risk == "LOW")
            tot_cnt = len(final_dependencies)

            counts = DependencyRiskCounts(
                critical=crit_cnt,
                high=high_cnt,
                medium=med_cnt,
                low=low_cnt,
                total=tot_cnt,
            )

            # Determine overall risk
            overall_risk = overall_risk_candidates[0] if overall_risk_candidates and overall_risk_candidates[0] in ALLOWED_RISK_LEVELS else ""
            if not overall_risk:
                overall_risk = "CRITICAL" if crit_cnt > 0 else "HIGH" if high_cnt > 0 else "MEDIUM" if med_cnt > 0 else "LOW"

            # Determine complexity
            complexity = complexity_candidates[0] if complexity_candidates and complexity_candidates[0] in ALLOWED_COMPLEXITIES else ""
            if not complexity:
                complexity = "LIGHT" if tot_cnt <= 10 and crit_cnt == 0 and high_cnt == 0 else "MODERATE" if tot_cnt <= 35 and crit_cnt == 0 else "COMPLEX"

            overall_explanation = " ".join(overall_explanations).strip()
            if not overall_explanation:
                overall_explanation = f"Analysis of {tot_cnt} dependencies indicates {overall_risk.lower()} overall migration friction."

            complexity_explanation = " ".join(complexity_explanations).strip()
            if not complexity_explanation:
                complexity_explanation = f"Evaluated {tot_cnt} dependencies across {len(set(d.category for d in final_dependencies))} technical categories."

            return DependencyAnalysisResponse(
                overall_risk=overall_risk,
                complexity=complexity,
                overall_explanation=overall_explanation,
                complexity_explanation=complexity_explanation,
                counts=counts,
                dependencies=final_dependencies,
                provider_used=", ".join(sorted(providers_used)) or "huggingface",
            )

        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM Dependency analysis failed (%s); falling back to heuristic.", exc)
            return _build_fallback_analysis(input_deps, request.build_tool, request.source_java_version)
        finally:
            if user_token:
                user_id_ctx.reset(user_token)
            if llm_token:
                llm_values_ctx.reset(llm_token)

    @staticmethod
    def _extract_json(content: str) -> dict:
        text = (content or "").strip()
        # Some models wrap JSON in ```json ... ``` fences
        if text.startswith("```"):
            text = text.strip("`")
            if text[:4].lower() == "json":
                text = text[4:]

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise LLMResponseInvalidError("Fallback model response did not contain JSON.")

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMResponseInvalidError("Fallback model response was not valid JSON.") from exc
