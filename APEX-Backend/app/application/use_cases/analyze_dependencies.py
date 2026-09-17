import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import BACKEND_ROOT, settings
from app.core.context import user_id_ctx
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

logger = logging.getLogger(__name__)

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

_CACHE_DIR = BACKEND_ROOT / "storage" / "dependency-analysis-cache"
_memory_cache: dict[str, DependencyAnalysisResponse] = {}
_inflight_tasks: dict[str, asyncio.Task[DependencyAnalysisResponse]] = {}
_inflight_lock = asyncio.Lock()


def compute_analysis_fingerprint(request: DependencyAnalysisRequest) -> str:
    """Compute a deterministic SHA-256 fingerprint for a dependency analysis request.

    Normalizes and sorts dependencies, frameworks, versions, and build tools so that
    ordering differences produce the exact same fingerprint.
    """
    normalized_deps = []
    for d in (request.dependencies or []):
        normalized_deps.append({
            "group_id": (d.group_id or "").strip().lower(),
            "artifact_id": (d.artifact_id or "").strip().lower(),
            "current_version": (d.current_version or "").strip(),
            "resolved_version": (d.resolved_version or "").strip(),
            "scope": (d.scope or "compile").strip().lower(),
        })
    # Sort deterministically by coordinate, versions, and scope
    normalized_deps.sort(
        key=lambda x: (
            x["group_id"],
            x["artifact_id"],
            x["current_version"],
            x["resolved_version"],
            x["scope"],
        )
    )

    norm_frameworks = sorted(
        [
            str(f.get("name") if isinstance(f, dict) else f).strip().lower()
            for f in (request.frameworks or [])
        ]
    )
    norm_test_fw = sorted(
        [
            str(t.get("name") if isinstance(t, dict) else t).strip().lower()
            for t in (request.testing_frameworks or [])
        ]
    )

    canonical_payload = {
        "job_id": (request.job_id or "").strip(),
        "source_java_version": (request.source_java_version or "").strip(),
        "target_java_version": (request.target_java_version or "").strip(),
        "build_tool": (request.build_tool or "").strip().upper(),
        "spring_boot_version": (request.spring_boot_version or "").strip(),
        "frameworks": norm_frameworks,
        "testing_frameworks": norm_test_fw,
        "api_endpoint_count": request.api_endpoint_count or 0,
        "dependencies": normalized_deps,
    }
    serialized = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _get_cache_file_path(fingerprint: str, job_id: str | None = None) -> Path:
    folder = job_id.strip() if job_id and job_id.strip() else "global"
    return _CACHE_DIR / folder / f"{fingerprint}.json"


def _read_from_cache(fingerprint: str, job_id: str | None = None) -> DependencyAnalysisResponse | None:
    if fingerprint in _memory_cache:
        return _memory_cache[fingerprint]

    cache_file = _get_cache_file_path(fingerprint, job_id)
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            parsed = DependencyAnalysisResponse.model_validate(data)
            _memory_cache[fingerprint] = parsed
            return parsed
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DependencyAnalysis] Failed to read cached file %s: %s", cache_file, exc)
    return None


def _write_to_cache(fingerprint: str, job_id: str | None, response: DependencyAnalysisResponse) -> None:
    _memory_cache[fingerprint] = response
    try:
        cache_file = _get_cache_file_path(fingerprint, job_id)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(response.model_dump(), indent=2), encoding="utf-8")
        logger.info("[DependencyAnalysis] validated result cached (fingerprint=%s)", fingerprint)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DependencyAnalysis] Failed to write cache file: %s", exc)


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

        fingerprint = compute_analysis_fingerprint(request)
        logger.info("[DependencyAnalysis] fingerprint=%s", fingerprint)

        # 1. Check cache first
        cached = _read_from_cache(fingerprint, request.job_id)
        if cached is not None:
            logger.info("[DependencyAnalysis] cache hit for fingerprint=%s", fingerprint)
            logger.info("[DependencyAnalysis] using cached result")
            return cached

        logger.info("[DependencyAnalysis] cache miss for fingerprint=%s", fingerprint)

        # 2. Single-flight request deduplication lock
        task: asyncio.Task[DependencyAnalysisResponse] | None = None
        is_initiator = False

        async with _inflight_lock:
            cached = _read_from_cache(fingerprint, request.job_id)
            if cached is not None:
                logger.info("[DependencyAnalysis] cache hit for fingerprint=%s", fingerprint)
                logger.info("[DependencyAnalysis] using cached result")
                return cached

            if fingerprint in _inflight_tasks:
                logger.info(
                    "[DependencyAnalysis] analysis already in progress for fingerprint=%s, awaiting existing task",
                    fingerprint,
                )
                task = _inflight_tasks[fingerprint]
            else:
                task = asyncio.create_task(
                    self._do_execute(request, fingerprint, db, current_user)
                )
                _inflight_tasks[fingerprint] = task
                is_initiator = True

        try:
            result = await task
            return result
        finally:
            if is_initiator:
                async with _inflight_lock:
                    _inflight_tasks.pop(fingerprint, None)

    async def _do_execute(
        self,
        request: DependencyAnalysisRequest,
        fingerprint: str,
        db: Session | None = None,
        current_user: User | None = None,
    ) -> DependencyAnalysisResponse:
        input_deps = request.dependencies or []
        user_token = None
        if current_user:
            user_token = user_id_ctx.set(current_user.id)

        try:
            # Batch dependencies in chunks of up to 25 to comfortably fit LLM context & output windows
            batch_size = 25
            batches = [input_deps[i : i + batch_size] for i in range(0, len(input_deps), batch_size)]
            all_analyzed_map: dict[str, dict[str, Any]] = {}
            overall_risk_candidates: list[str] = []
            complexity_candidates: list[str] = []
            overall_explanations: list[str] = []
            complexity_explanations: list[str] = []
            providers_used: set[str] = set()

            for batch_idx, batch in enumerate(batches):
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

                raw_json: dict[str, Any] | None = None

                # 1. Primary: Hugging Face
                try:
                    logger.info(
                        "[DependencyAnalysis] Attempting Hugging Face (primary) for batch %d/%d (%d deps)",
                        batch_idx + 1,
                        len(batches),
                        len(batch),
                    )
                    raw_json = await self._llm.chat_json(
                        DEPENDENCY_ANALYSIS_SYSTEM_PROMPT, user_prompt, max_tokens=4096
                    )
                    self._validate_analysis_payload(raw_json)
                    providers_used.add("huggingface")
                    logger.info(
                        "[DependencyAnalysis] provider=HuggingFace succeeded for batch %d/%d",
                        batch_idx + 1,
                        len(batches),
                    )
                except Exception as hf_exc:  # noqa: BLE001
                    logger.warning(
                        "[DependencyAnalysis] Hugging Face failed for batch %d/%d (Reason: %s), falling back to Strategy Chat LLM.",
                        batch_idx + 1,
                        len(batches),
                        hf_exc,
                    )
                    raw_json = None

                # 2. Fallback: Strategy Chat LLM (Groq -> Ollama)
                if raw_json is None:
                    try:
                        logger.info(
                            "[DependencyAnalysis] Attempting Strategy Chat LLM fallback for batch %d/%d",
                            batch_idx + 1,
                            len(batches),
                        )
                        response_text = ""
                        async for chunk in self._chat_llm.stream_chat(
                            system_prompt=DEPENDENCY_ANALYSIS_SYSTEM_PROMPT,
                            user_prompt=user_prompt,
                            endpoint="dependency_analysis_fallback",
                            max_tokens=4096,
                        ):
                            response_text += chunk

                        active_provider = self._chat_llm.last_provider or "chat_llm"
                        preview = response_text[:300].replace("\n", " ").strip()
                        logger.info(
                            "[DependencyAnalysis] %s response received successfully (%d chars) for batch %d/%d. Preview: %s...",
                            active_provider,
                            len(response_text),
                            batch_idx + 1,
                            len(batches),
                            preview,
                        )

                        raw_json = self._extract_json(response_text)
                        self._validate_analysis_payload(raw_json)
                        providers_used.add(active_provider)
                        logger.info(
                            "[DependencyAnalysis] provider=%s JSON parsed and validated successfully for batch %d/%d",
                            active_provider,
                            batch_idx + 1,
                            len(batches),
                        )
                    except Exception as chat_exc:  # noqa: BLE001
                        logger.warning(
                            "[DependencyAnalysis] Strategy Chat LLM fallback failed for batch %d/%d (Reason: %s). Using heuristic for this batch.",
                            batch_idx + 1,
                            len(batches),
                            chat_exc,
                        )
                        raw_json = None

                # 3. Deterministic Heuristic Fallback for this batch if LLMs failed
                if raw_json is None:
                    logger.info(
                        "[DependencyAnalysis] heuristic fallback applied for batch %d/%d",
                        batch_idx + 1,
                        len(batches),
                    )
                    fallback_res = _build_fallback_analysis(
                        batch, request.build_tool, request.source_java_version
                    )
                    providers_used.add("heuristic")
                    raw_json = {
                        "overall_risk": fallback_res.overall_risk,
                        "complexity": fallback_res.complexity,
                        "overall_explanation": fallback_res.overall_explanation,
                        "complexity_explanation": fallback_res.complexity_explanation,
                        "dependencies": [d.model_dump() for d in fallback_res.dependencies],
                    }

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
                llm_entry = (
                    all_analyzed_map.get(dep_id.lower())
                    or all_analyzed_map.get(coord.lower())
                    or all_analyzed_map.get(aid.lower())
                    or {}
                )

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
            overall_risk = (
                overall_risk_candidates[0]
                if overall_risk_candidates and overall_risk_candidates[0] in ALLOWED_RISK_LEVELS
                else ""
            )
            if not overall_risk:
                overall_risk = (
                    "CRITICAL"
                    if crit_cnt > 0
                    else "HIGH"
                    if high_cnt > 0
                    else "MEDIUM"
                    if med_cnt > 0
                    else "LOW"
                )

            # Determine complexity
            complexity = (
                complexity_candidates[0]
                if complexity_candidates and complexity_candidates[0] in ALLOWED_COMPLEXITIES
                else ""
            )
            if not complexity:
                complexity = (
                    "LIGHT"
                    if tot_cnt <= 10 and crit_cnt == 0 and high_cnt == 0
                    else "MODERATE"
                    if tot_cnt <= 35 and crit_cnt == 0
                    else "COMPLEX"
                )

            overall_explanation = " ".join(overall_explanations).strip()
            if not overall_explanation:
                overall_explanation = f"Analysis of {tot_cnt} dependencies indicates {overall_risk.lower()} overall migration friction."

            complexity_explanation = " ".join(complexity_explanations).strip()
            if not complexity_explanation:
                complexity_explanation = f"Evaluated {tot_cnt} dependencies across {len(set(d.category for d in final_dependencies))} technical categories."

            final_response = DependencyAnalysisResponse(
                overall_risk=overall_risk,
                complexity=complexity,
                overall_explanation=overall_explanation,
                complexity_explanation=complexity_explanation,
                counts=counts,
                dependencies=final_dependencies,
                provider_used=", ".join(sorted(providers_used)) or "heuristic",
            )

            # Save validated result to cache
            _write_to_cache(fingerprint, request.job_id, final_response)
            return final_response

        except Exception as exc:  # noqa: BLE001
            logger.warning("[DependencyAnalysis] LLM analysis failed (%s); falling back to heuristic.", exc)
            fallback_response = _build_fallback_analysis(
                input_deps, request.build_tool, request.source_java_version
            )
            _write_to_cache(fingerprint, request.job_id, fallback_response)
            return fallback_response
        finally:
            if user_token:
                user_id_ctx.reset(user_token)

    @staticmethod
    def _validate_analysis_payload(payload: Any) -> None:
        """Validate that the parsed JSON conforms to the expected structure."""
        if not isinstance(payload, dict):
            raise LLMResponseInvalidError("Parsed LLM response is not a JSON object.")
        deps = payload.get("dependencies")
        if deps is not None and not isinstance(deps, list):
            raise LLMResponseInvalidError("'dependencies' field in LLM response must be an array.")

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        """Extract and parse JSON object from LLM response text with multiple repair strategies."""
        text = (content or "").strip()
        if not text:
            raise LLMResponseInvalidError("LLM response was empty.")

        candidates: list[str] = []

        # Strategy 1: Look for markdown code fences ```json ... ``` or ``` ... ```
        fence_pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
        for match in fence_pattern.finditer(text):
            fenced = match.group(1).strip()
            if fenced:
                candidates.append(fenced)

        # Strategy 2: Find outermost { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidates.append(text[start : end + 1].strip())

        # Strategy 3: Raw text
        candidates.append(text)

        # Attempt to parse each candidate with progressive repairs
        for candidate in candidates:
            if not candidate:
                continue

            # Direct parse
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

            # Repair: remove single-line // comments and multi-line /* */ comments
            cleaned = re.sub(r"//.*$", "", candidate, flags=re.MULTILINE)
            cleaned = re.sub(r"/\*[\s\S]*?\*/", "", cleaned)

            # Repair: remove trailing commas before } or ]
            cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)

            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

            # Search within cleaned candidate for { ... }
            c_start = cleaned.find("{")
            c_end = cleaned.rfind("}")
            if c_start != -1 and c_end != -1 and c_end > c_start:
                try:
                    parsed = json.loads(cleaned[c_start : c_end + 1])
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    pass

        raise LLMResponseInvalidError("LLM response was not valid JSON.")
