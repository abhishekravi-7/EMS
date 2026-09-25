"""Dynamic framework and target version compatibility analyzer.

Inspects the repository files (package.json, lockfiles, .nvmrc, tsconfig.json,
angular.json, build tools, and runtime environment) to build a compact
repository-context payload, and delegates the recommendation reasoning and
target-version evaluation to the LLM.

Deterministic tasks:
- JSP/JSPF file detection & counts
- JSF/XHTML file detection & counts
- package.json detection & dependency parsing
- Lockfile / package manager detection
- tsconfig.json & angular.json detection
- Host runtime Node.js detection

Dynamic LLM tasks:
- Migration target evaluation & recommendation
- Environment-specific compatibility reasoning
- Dynamic target version selection
- Repository-specific migration reasons & constraints
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.llm.huggingface_client import HuggingFaceClient
from app.shared import file_utils

logger = logging.getLogger(__name__)

# Directories commonly hosting frontend assets or configurations
_CANDIDATE_DIRS = ("", "frontend", "client", "web", "ui", "webapp", "src/main/webapp")

# In-memory recommendation cache: { cache_key: (FrameworkRecommendations, timestamp) }
_RECOMMENDATION_CACHE: dict[str, tuple[FrameworkRecommendations, float]] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour cache TTL

FRONTEND_RECOMMENDATION_SYSTEM_PROMPT = """You are the frontend modernization recommendation engine for JavaAPEX.

Analyze only the supplied repository metadata.
The source application is a Java web application containing JSP and/or JSF files.

Recommend an appropriate frontend migration target among the targets that are explicitly marked as available.
Your recommendation must be based only on supplied evidence.

Evaluate:
- JSP/JSF presence and file counts
- existing React/Angular environment
- Node.js version
- TypeScript version
- RxJS version
- package manager
- build tooling
- existing frontend dependencies
- repository configuration

Crucial instruction for target versions:
- You must dynamically determine and recommend specific, compatible target framework versions for BOTH React and Angular (e.g. React 19.3, React 18.3.1; Angular 22.x, Angular 20.x, Angular 19.x, Angular 18.x, Angular 16.x) compatible with the detected Node.js runtime and environment.
- target_version must NEVER be "unknown". Always recommend a specific modern target version for migration.
- Provide candidate available_versions (e.g. ["19.3", "18.3.1"] or ["22.x", "20.x"]) for each framework so the user has compatible version options in the UI dropdown.
- If the project already has an existing framework version, prefer compatibility with that existing version unless modernization is needed.
- If no existing framework is installed, dynamically recommend the optimal compatible modern version based on the Node.js runtime and ecosystem support.
- Do not recommend a target that is unavailable in available_targets.
- Do not use fixed version tiers.
- Do not return generic boilerplate.
- Every recommendation reason must be specific to the supplied repository metadata.

Return ONLY a valid JSON object matching the requested schema. No surrounding markdown, no explanations outside JSON."""


def _run_async(coro: Any) -> Any:
    """Helper to run an async coroutine synchronously from sync callers, avoiding event-loop conflicts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


@dataclass(frozen=True)
class FrameworkRecommendationItem:
    framework: str
    target_version: str
    compatibility: str
    is_recommended: bool
    reasons: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    available_versions: list[str] = field(default_factory=list)
    current_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework,
            "targetVersion": self.target_version,
            "compatibility": self.compatibility,
            "isRecommended": self.is_recommended,
            "reasons": list(self.reasons),
            "constraints": list(self.constraints),
            "availableVersions": list(self.available_versions),
            "currentVersion": self.current_version,
        }


# Alias for backward compatibility with existing imports
FrameworkRecommendation = FrameworkRecommendationItem


@dataclass(frozen=True)
class FrameworkRecommendations:
    react: FrameworkRecommendationItem | None
    angular: FrameworkRecommendationItem | None
    recommended_target: str | None = None
    recommended_target_label: str | None = None
    confidence: str | None = None
    recommendation_summary: str | None = None
    recommendation_status: str = "available"

    def to_dict(self) -> dict[str, Any]:
        return {
            "react": self.react.to_dict() if self.react else None,
            "angular": self.angular.to_dict() if self.angular else None,
            "recommendedTarget": self.recommended_target,
            "recommendedTargetLabel": self.recommended_target_label,
            "confidence": self.confidence,
            "recommendationSummary": self.recommendation_summary,
            "recommendationStatus": self.recommendation_status,
        }


@dataclass
class DetectedEnvironment:
    node_version: str | None = None
    node_major: int | None = None
    node_source: str | None = None
    typescript_version: str | None = None
    typescript_major: int | None = None
    rxjs_version: str | None = None
    rxjs_major: int | None = None
    existing_react_version: str | None = None
    existing_angular_version: str | None = None
    build_tool: str | None = None
    package_manager: str | None = None
    package_json_path: Path | None = None
    tsconfig_path: Path | None = None
    angular_json_path: Path | None = None
    lockfile_path: Path | None = None
    has_jsp: bool = False
    has_jsf: bool = False
    jsp_count: int = 0
    jsf_count: int = 0
    detected_dependencies: list[str] = field(default_factory=list)


class FrontendCompatibilityAnalyzer:
    """Analyzes repository metadata and calls the LLM to generate dynamic modernization recommendations."""

    def __init__(
        self,
        llm_client: HuggingFaceClient | None = None,
        chat_llm: ChatLLM | None = None,
    ) -> None:
        self._llm = llm_client or HuggingFaceClient()
        self._chat_llm = chat_llm or ChatLLM()

    def analyze(self, root: Path, project_analysis: Any = None) -> FrameworkRecommendations:
        """Synchronous entry point for analyzing repository and returning recommendations."""
        return _run_async(self.analyze_async(root, project_analysis))

    async def analyze_async(self, root: Path, project_analysis: Any = None) -> FrameworkRecommendations:
        """Asynchronous entry point for analyzing repository and returning recommendations."""
        env = self._inspect_environment(root, project_analysis)

        available_targets: list[str] = []
        if env.has_jsp:
            available_targets.extend(["JSP -> React", "JSP -> Angular"])
        if env.has_jsf:
            available_targets.extend(["JSF -> React", "JSF -> Angular"])

        if not available_targets:
            return FrameworkRecommendations(
                react=None,
                angular=None,
                recommendation_status="not_applicable",
            )

        context_payload: dict[str, Any] = {
            "ui_framework_sources": {
                "jsp_files": env.jsp_count,
                "jsf_files": env.jsf_count,
                "jsp_extensions": [".jsp", ".jspf"],
                "jsf_extensions": [".xhtml", ".jsf"],
            },
            "project_environment": {
                "node_version": env.node_version,
                "typescript_version": env.typescript_version,
                "angular_version": env.existing_angular_version,
                "react_version": env.existing_react_version,
                "rxjs_version": env.rxjs_version,
                "package_manager": env.package_manager,
                "build_tool": env.build_tool,
            },
            "configuration_files": {
                "package_json": env.package_json_path is not None,
                "tsconfig": env.tsconfig_path is not None,
                "angular_json": env.angular_json_path is not None,
                "vite": env.build_tool == "vite",
                "webpack": env.build_tool == "webpack",
            },
            "existing_dependencies": env.detected_dependencies[:20],
            "available_targets": available_targets,
        }

        cache_key = self._compute_cache_key(root, context_payload)
        now = time.time()
        if cache_key in _RECOMMENDATION_CACHE:
            cached_rec, timestamp = _RECOMMENDATION_CACHE[cache_key]
            if now - timestamp < CACHE_TTL_SECONDS:
                logger.info("[FrontendRecommendation] Cache hit for %s", cache_key)
                return cached_rec

        raw = await self._query_llm_recommendation(context_payload)
        if not raw or not isinstance(raw, dict):
            logger.warning(
                "[FrontendRecommendation] LLM recommendation failed or returned invalid response; returning unavailable status."
            )
            return FrameworkRecommendations(
                react=None,
                angular=None,
                recommendation_status="unavailable",
            )

        rec_target = str(raw.get("recommended_target") or "").lower().strip()
        rec_target_label = raw.get("recommended_target_label")
        rec_summary = raw.get("recommendation_summary")
        confidence = raw.get("confidence")

        react_data = raw.get("react")
        is_react_rec = rec_target == "react" or (
            isinstance(react_data, dict) and bool(react_data.get("is_recommended"))
        )

        angular_data = raw.get("angular")
        is_angular_rec = rec_target == "angular" or (
            isinstance(angular_data, dict) and bool(angular_data.get("is_recommended"))
        )

        if is_react_rec and is_angular_rec:
            if rec_target == "angular":
                is_react_rec = False
            else:
                is_angular_rec = False
        elif not is_react_rec and not is_angular_rec:
            if rec_target_label and "Angular" in str(rec_target_label):
                is_angular_rec = True
            else:
                is_react_rec = True

        react_item = self._build_recommendation_item(
            framework="React",
            raw_data=react_data,
            is_recommended=is_react_rec,
            current_version=env.existing_react_version,
            fallback_root_data=raw,
        )

        angular_item = self._build_recommendation_item(
            framework="Angular",
            raw_data=angular_data,
            is_recommended=is_angular_rec,
            current_version=env.existing_angular_version,
            fallback_root_data=raw,
        )

        react_item = FrameworkRecommendationItem(
            framework=react_item.framework,
            target_version=react_item.target_version,
            compatibility=react_item.compatibility,
            is_recommended=is_react_rec,
            reasons=react_item.reasons,
            constraints=react_item.constraints,
            available_versions=react_item.available_versions,
            current_version=react_item.current_version,
        )

        angular_item = FrameworkRecommendationItem(
            framework=angular_item.framework,
            target_version=angular_item.target_version,
            compatibility=angular_item.compatibility,
            is_recommended=is_angular_rec,
            reasons=angular_item.reasons,
            constraints=angular_item.constraints,
            available_versions=angular_item.available_versions,
            current_version=angular_item.current_version,
        )

        recommendations = FrameworkRecommendations(
            react=react_item,
            angular=angular_item,
            recommended_target="react" if is_react_rec else "angular",
            recommended_target_label=rec_target_label or ("JSP -> React" if is_react_rec else "JSP -> Angular"),
            confidence=confidence or "medium",
            recommendation_summary=rec_summary,
            recommendation_status="available",
        )

        _RECOMMENDATION_CACHE[cache_key] = (recommendations, now)
        return recommendations

    # -- LLM Query & Response parsing --------------------------------------- #

    async def _query_llm_recommendation(self, context_payload: dict[str, Any]) -> dict[str, Any] | None:
        system_prompt = FRONTEND_RECOMMENDATION_SYSTEM_PROMPT
        user_prompt = f"""Repository Frontend Context:
{json.dumps(context_payload, indent=2)}

Generate the frontend modernization recommendation JSON for this repository.
Required JSON schema:
{{
  "recommended_target": "react" or "angular",
  "recommended_target_label": "JSP -> React" or "JSP -> Angular" or "JSF -> React" or "JSF -> Angular",
  "confidence": "high" or "medium" or "low",
  "recommendation_summary": "Concise summary",
  "react": {{
    "target_version": "specific recommended version string (e.g. 19.3 or 18.3.1, must NOT be unknown)",
    "available_versions": ["version1", "version2"],
    "compatibility": "description",
    "is_recommended": boolean,
    "reasons": ["reason1", "reason2"],
    "constraints": ["constraint1"]
  }},
  "angular": {{
    "target_version": "specific recommended version string (e.g. 22.x or 20.x or 19.x, must NOT be unknown)",
    "available_versions": ["version1", "version2"],
    "compatibility": "description",
    "is_recommended": boolean,
    "reasons": ["reason1", "reason2"],
    "constraints": ["constraint1"]
  }}
}}"""

        # 1. Try Hugging Face if configured
        try:
            if self._llm and hasattr(self._llm, "chat_json"):
                raw = await self._llm.chat_json(system_prompt, user_prompt)
                if isinstance(raw, dict) and ("react" in raw or "angular" in raw or "recommended_target" in raw):
                    return raw
        except Exception as exc:
            logger.info(
                "[FrontendRecommendation] HuggingFace unavailable or failed: %s; trying ChatLLM...", exc
            )

        # 2. Try ChatLLM (Groq -> Ollama)
        try:
            if self._chat_llm and hasattr(self._chat_llm, "stream_chat"):
                chunks: list[str] = []
                async for chunk in self._chat_llm.stream_chat(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    endpoint="frontend_framework_recommendation",
                ):
                    chunks.append(chunk)
                response_text = "".join(chunks)
                parsed = self._extract_json(response_text)
                if isinstance(parsed, dict) and ("react" in parsed or "angular" in parsed or "recommended_target" in parsed):
                    return parsed
        except Exception as exc:
            logger.error("[FrontendRecommendation] ChatLLM failed: %s", exc)

        return None

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any] | None:
        text = (content or "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        json_str = text[start : end + 1]
        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError:
            cleaned = re.sub(r",\s*([\}\]])", r"\1", json_str)
            try:
                return json.loads(cleaned, strict=False)
            except Exception:
                return None

    @staticmethod
    def _build_recommendation_item(
        framework: str,
        raw_data: Any,
        is_recommended: bool,
        current_version: str | None = None,
        fallback_root_data: dict[str, Any] | None = None,
    ) -> FrameworkRecommendationItem:
        if not isinstance(raw_data, dict):
            if fallback_root_data and isinstance(fallback_root_data, dict):
                if is_recommended:
                    target_ver = str(
                        fallback_root_data.get("recommended_version")
                        or fallback_root_data.get("target_version")
                        or "unknown"
                    ).strip()
                    avail_vers = [target_ver] if target_ver != "unknown" else []

                    raw_comp = fallback_root_data.get("compatibility")
                    if isinstance(raw_comp, str) and raw_comp.strip():
                        compatibility = raw_comp.strip()
                    elif fallback_root_data.get("recommendation"):
                        compatibility = str(fallback_root_data.get("recommendation")).strip()
                    else:
                        compatibility = "Compatible with detected project environment."

                    reasons = fallback_root_data.get("reasons") or []
                    if isinstance(reasons, str):
                        reasons = [reasons]
                    elif not isinstance(reasons, list):
                        reasons = []

                    risks = fallback_root_data.get("risks") or fallback_root_data.get("requirements") or []
                    if isinstance(risks, str):
                        risks = [risks]
                    elif not isinstance(risks, list):
                        risks = []

                    return FrameworkRecommendationItem(
                        framework=framework,
                        target_version=target_ver,
                        compatibility=compatibility,
                        is_recommended=True,
                        reasons=[str(r) for r in reasons if str(r).strip()],
                        constraints=[str(c) for c in risks if str(c).strip()],
                        available_versions=avail_vers,
                        current_version=current_version,
                    )
                else:
                    alt_ver = str(
                        fallback_root_data.get(f"{framework.lower()}_version")
                        or fallback_root_data.get("alternative_version")
                        or ("22.x" if framework == "Angular" else "19.3")
                    ).strip()
                    return FrameworkRecommendationItem(
                        framework=framework,
                        target_version=alt_ver,
                        compatibility=f"Alternative {framework} migration target.",
                        is_recommended=False,
                        reasons=[f"Evaluated as alternative modern frontend target."],
                        constraints=[],
                        available_versions=[alt_ver] if alt_ver != "unknown" else [],
                        current_version=current_version,
                    )

            return FrameworkRecommendationItem(
                framework=framework,
                target_version="unknown",
                compatibility=f"Compatibility information for {framework} unavailable.",
                is_recommended=is_recommended,
                reasons=[],
                constraints=[],
                available_versions=[],
                current_version=current_version,
            )

        target_ver = str(raw_data.get("target_version") or raw_data.get("targetVersion") or "unknown").strip()
        avail_vers = raw_data.get("available_versions") or raw_data.get("availableVersions") or []
        if isinstance(avail_vers, str):
            avail_vers = [avail_vers]
        elif not isinstance(avail_vers, list):
            avail_vers = []
        avail_vers = [str(v).strip() for v in avail_vers if str(v).strip()]
        if target_ver != "unknown" and target_ver not in avail_vers:
            avail_vers.insert(0, target_ver)

        compatibility = str(raw_data.get("compatibility") or "").strip()
        if not compatibility:
            compatibility = f"Evaluated for {framework} migration."

        reasons = raw_data.get("reasons") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        elif not isinstance(reasons, list):
            reasons = []
        reasons = [str(r).strip() for r in reasons if str(r).strip()]

        constraints = raw_data.get("constraints") or []
        if isinstance(constraints, str):
            constraints = [constraints]
        elif not isinstance(constraints, list):
            constraints = []
        constraints = [str(c).strip() for c in constraints if str(c).strip()]

        return FrameworkRecommendationItem(
            framework=framework,
            target_version=target_ver,
            compatibility=compatibility,
            is_recommended=is_recommended,
            reasons=reasons,
            constraints=constraints,
            available_versions=avail_vers,
            current_version=current_version,
        )

    @staticmethod
    def _compute_cache_key(root: Path, context_payload: dict[str, Any]) -> str:
        payload_str = json.dumps(context_payload, sort_keys=True)
        h = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()[:16]
        return f"{root.resolve()}:{h}"

    # -- Environment inspection (Pure Static Detection) ---------------------- #

    def _inspect_environment(self, root: Path, project_analysis: Any = None) -> DetectedEnvironment:
        env = DetectedEnvironment()

        # Check JSP / JSF presence
        if project_analysis is not None:
            jsp_cnt = getattr(project_analysis, "jsp_file_count", None)
            if jsp_cnt is None and hasattr(project_analysis, "jsp_files"):
                jsp_cnt = len(project_analysis.jsp_files)
            jsf_cnt = getattr(project_analysis, "jsf_file_count", None)
            if jsf_cnt is None and hasattr(project_analysis, "jsf_files"):
                jsf_cnt = len(project_analysis.jsf_files)

            env.jsp_count = int(jsp_cnt or 0)
            env.jsf_count = int(jsf_cnt or 0)
            env.has_jsp = env.jsp_count > 0
            env.has_jsf = env.jsf_count > 0
        else:
            env.jsp_count = file_utils.count_files(root, ".jsp", limit=100) + file_utils.count_files(
                root, ".jspf", limit=100
            )
            env.jsf_count = file_utils.count_files(root, ".jsf", limit=100) + file_utils.count_files(
                root, ".xhtml", limit=100
            )
            env.has_jsp = env.jsp_count > 0
            env.has_jsf = env.jsf_count > 0

        # Search candidate directories for package.json, lockfiles, etc.
        for relative in _CANDIDATE_DIRS:
            base = root if relative == "" else root / relative
            if not base.is_dir():
                continue

            # package.json
            pkg_path = base / "package.json"
            if pkg_path.is_file() and env.package_json_path is None:
                env.package_json_path = pkg_path
                self._parse_package_json(pkg_path, env)

            # lockfiles
            for lock_name in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json"):
                lp = base / lock_name
                if lp.is_file() and env.lockfile_path is None:
                    env.lockfile_path = lp
                    if "yarn" in lock_name:
                        env.package_manager = "yarn"
                    elif "pnpm" in lock_name:
                        env.package_manager = "pnpm"
                    else:
                        env.package_manager = "npm"

            # tsconfig.json
            ts_path = base / "tsconfig.json"
            if ts_path.is_file() and env.tsconfig_path is None:
                env.tsconfig_path = ts_path

            # angular.json
            ang_path = base / "angular.json"
            if not ang_path.is_file():
                ang_path = base / ".angular-cli.json"
            if ang_path.is_file() and env.angular_json_path is None:
                env.angular_json_path = ang_path

            # .nvmrc / .node-version
            for node_cfg in (".nvmrc", ".node-version"):
                np = base / node_cfg
                if np.is_file() and env.node_version is None:
                    txt = file_utils.read_text(np).strip()
                    if txt:
                        env.node_version = txt
                        env.node_major = self._extract_major_version(txt)
                        env.node_source = node_cfg

            # bundler detection
            if (base / "vite.config.js").is_file() or (base / "vite.config.ts").is_file():
                env.build_tool = "vite"
            elif (base / "webpack.config.js").is_file() or (base / "webpack.config.ts").is_file():
                env.build_tool = "webpack"

        # If Node version was not explicitly constrained inside the repository,
        # inspect the active host Node.js runtime environment.
        if env.node_version is None:
            host_node = self._detect_host_node_version()
            if host_node:
                env.node_version = host_node
                env.node_major = self._extract_major_version(host_node)
                env.node_source = "system runtime"

        return env

    def _parse_package_json(self, path: Path, env: DetectedEnvironment) -> None:
        try:
            content = file_utils.read_text(path)
            data = json.loads(content or "{}")
        except Exception as exc:
            logger.warning("Could not parse package.json at %s: %s", path, exc)
            return

        # Engines
        engines = data.get("engines") or {}
        if isinstance(engines, dict) and "node" in engines and not env.node_version:
            node_engine = str(engines["node"])
            env.node_version = node_engine
            env.node_major = self._extract_major_version(node_engine)
            env.node_source = "package.json engines"

        # Dependencies & devDependencies
        deps: dict[str, str] = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            block = data.get(key)
            if isinstance(block, dict):
                deps.update({str(k): str(v) for k, v in block.items()})

        env.detected_dependencies = [f"{k}@{v}" for k, v in deps.items()]

        # Existing React
        if "react" in deps:
            env.existing_react_version = self._clean_version_spec(deps["react"])
        elif "react-dom" in deps:
            env.existing_react_version = self._clean_version_spec(deps["react-dom"])

        # Existing Angular
        if "@angular/core" in deps:
            env.existing_angular_version = self._clean_version_spec(deps["@angular/core"])
        elif "@angular/cli" in deps:
            env.existing_angular_version = self._clean_version_spec(deps["@angular/cli"])

        # TypeScript
        if "typescript" in deps:
            env.typescript_version = deps["typescript"]
            env.typescript_major = self._extract_major_version(deps["typescript"])

        # RxJS
        if "rxjs" in deps:
            env.rxjs_version = deps["rxjs"]
            env.rxjs_major = self._extract_major_version(deps["rxjs"])

        # Build tools
        if "vite" in deps:
            env.build_tool = "vite"
        elif "webpack" in deps and not env.build_tool:
            env.build_tool = "webpack"

    @staticmethod
    def _detect_host_node_version() -> str | None:
        """Inspects the local system Node runtime version if available."""
        node_bin = shutil.which("node")
        if not node_bin:
            return None
        try:
            res = subprocess.run(
                [node_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                out = res.stdout.strip()
                if out.startswith("v"):
                    out = out[1:]
                return out
        except Exception:
            pass
        return None

    @staticmethod
    def _clean_version_spec(version_str: str) -> str:
        """Strips leading semver range prefixes like ^, ~, >=, etc."""
        return re.sub(r"^[^\d]*", "", str(version_str).strip())

    @staticmethod
    def _extract_major_version(version_str: str) -> int | None:
        """Extracts the leading integer major version from a version specification string."""
        cleaned = re.sub(r"[^\d.]", "", version_str)
        parts = cleaned.split(".")
        if parts and parts[0].isdigit():
            return int(parts[0])
        return None
