"""Dynamic framework and target version compatibility analyzer.

Inspects the repository files (package.json, lockfiles, .nvmrc, tsconfig.json,
angular.json, build tools, and runtime environment) to determine the highest
compatible stable target versions for React and Angular migrations.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.shared import file_utils

logger = logging.getLogger(__name__)

# Directories commonly hosting frontend assets or configurations
_CANDIDATE_DIRS = ("", "frontend", "client", "web", "ui", "webapp", "src/main/webapp")


@dataclass(frozen=True)
class FrameworkRecommendation:
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


@dataclass(frozen=True)
class FrameworkRecommendations:
    react: FrameworkRecommendation
    angular: FrameworkRecommendation

    def to_dict(self) -> dict[str, Any]:
        return {
            "react": self.react.to_dict(),
            "angular": self.angular.to_dict(),
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
    package_json_path: Path | None = None
    tsconfig_path: Path | None = None
    angular_json_path: Path | None = None
    lockfile_path: Path | None = None
    has_jsp: bool = False
    has_jsf: bool = False


class FrontendCompatibilityAnalyzer:
    """Analyzes the repository environment and calculates compatible React & Angular target versions."""

    def analyze(self, root: Path, project_analysis: Any = None) -> FrameworkRecommendations:
        env = self._inspect_environment(root, project_analysis)
        react_rec = self._evaluate_react(env)
        angular_rec = self._evaluate_angular(env)

        # React is typically the recommended default for legacy JSP/Servlet apps unless
        # the repository already has Angular dependencies or configurations configured.
        if env.existing_angular_version and not env.existing_react_version:
            angular_rec = FrameworkRecommendation(
                framework=angular_rec.framework,
                target_version=angular_rec.target_version,
                compatibility=angular_rec.compatibility,
                is_recommended=True,
                reasons=angular_rec.reasons,
                constraints=angular_rec.constraints,
                available_versions=angular_rec.available_versions,
                current_version=angular_rec.current_version,
            )
            react_rec = FrameworkRecommendation(
                framework=react_rec.framework,
                target_version=react_rec.target_version,
                compatibility=react_rec.compatibility,
                is_recommended=False,
                reasons=react_rec.reasons,
                constraints=react_rec.constraints,
                available_versions=react_rec.available_versions,
                current_version=react_rec.current_version,
            )

        return FrameworkRecommendations(react=react_rec, angular=angular_rec)

    # -- Environment inspection --------------------------------------------- #

    def _inspect_environment(self, root: Path, project_analysis: Any = None) -> DetectedEnvironment:
        env = DetectedEnvironment()

        # Check JSP / JSF presence
        if project_analysis is not None:
            jsp_cnt = getattr(project_analysis, "jsp_file_count", None)
            jsf_cnt = getattr(project_analysis, "jsf_file_count", None)
            env.has_jsp = bool(jsp_cnt and jsp_cnt > 0)
            env.has_jsf = bool(jsf_cnt and jsf_cnt > 0)
        else:
            env.has_jsp = file_utils.count_files(root, ".jsp", limit=1) > 0 or file_utils.count_files(root, ".jspf", limit=1) > 0
            env.has_jsf = file_utils.count_files(root, ".jsf", limit=1) > 0 or file_utils.count_files(root, ".xhtml", limit=1) > 0

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

        # Existing React
        if "react" in deps:
            env.existing_react_version = deps["react"]
        elif "react-dom" in deps:
            env.existing_react_version = deps["react-dom"]

        # Existing Angular
        if "@angular/core" in deps:
            env.existing_angular_version = deps["@angular/core"]
        elif "@angular/cli" in deps:
            env.existing_angular_version = deps["@angular/cli"]

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
    def _extract_major_version(version_str: str) -> int | None:
        """Extracts the leading integer major version from a version specification string."""
        cleaned = re.sub(r"[^\d.]", "", version_str)
        parts = cleaned.split(".")
        if parts and parts[0].isdigit():
            return int(parts[0])
        return None

    # -- React evaluation ---------------------------------------------------- #

    def _evaluate_react(self, env: DetectedEnvironment) -> FrameworkRecommendation:
        current = env.existing_react_version
        cleaned_current = re.sub(r"[^\d.]", "", current) if current else None

        node_major = env.node_major if env.node_major is not None else 20
        ts_major = env.typescript_major

        # React compatibility tier selection:
        # Tier 1: React 19.3 (requires Node >= 18, TS >= 5.0 if TS present)
        # Tier 2: React 18.3.1 (requires Node >= 14, TS >= 4.5)
        # Tier 3: React 17.0.2 (older Node < 14)
        if node_major < 14:
            target_version = "17.0.2"
            available_versions = ["17.0.2"]
            compatibility = "Compatible with legacy Node.js environment"
            reasons = [
                f"Node.js {node_major} detected; React 18+ requires Node.js 14+.",
                "React 17.0.2 is the highest compatible version for this runtime.",
            ]
            constraints = ["Runtime does not satisfy Node.js 18+ requirement for React 19."]
        elif node_major < 18 or (ts_major is not None and ts_major < 5):
            target_version = "18.3.1"
            available_versions = ["18.3.1", "17.0.2"]
            compatibility = "Compatible with detected environment"
            reasons = [
                f"Node.js {node_major} and TypeScript {env.typescript_version or '4.x'} detected in repository.",
                "React 19 requires Node.js >= 18.0.0 and TypeScript >= 5.0.",
                "React 18.3.1 is the highest fully compatible stable release for this environment.",
            ]
            constraints = ["Upgrade Node.js to 18+ and TypeScript to 5.0+ to unlock React 19."]
        else:
            target_version = "19.3"
            available_versions = ["19.3", "18.3.1", "17.0.2"]
            compatibility = "Compatible with detected project environment"
            reasons = [
                "Compatible with detected project environment and modern ESM runtime.",
                "Supports TypeScript 5+ JSX transform and modern React 19 component architecture.",
            ]
            constraints = []

        if current:
            reasons.insert(0, f"Detected existing React dependency: {current}.")

        return FrameworkRecommendation(
            framework="React",
            target_version=target_version,
            compatibility=compatibility,
            is_recommended=True,
            reasons=reasons,
            constraints=constraints,
            available_versions=available_versions,
            current_version=cleaned_current or current,
        )

    # -- Angular evaluation -------------------------------------------------- #

    def _evaluate_angular(self, env: DetectedEnvironment) -> FrameworkRecommendation:
        current = env.existing_angular_version
        cleaned_current = re.sub(r"[^\d.]", "", current) if current else None

        node_major = env.node_major if env.node_major is not None else 20
        ts_major = env.typescript_major

        # Angular version compatibility tiers:
        # Tier 1: Angular 22.x (Modern greenfield target / next major; requires Node >= 20, TS >= 5.6, RxJS >= 7.8)
        # Tier 2: Angular 18.x / 19.x (Node 18.19+, TS 5.4 - 5.6)
        # Tier 3: Angular 16.x (Node 16.x, TS 4.9 - 5.1)
        # Tier 4: Angular 14.x (Node 14.x)
        if node_major < 16:
            target_version = "14.3.0"
            available_versions = ["14.3.0"]
            compatibility = "Compatible with legacy Node.js runtime"
            reasons = [
                f"Node.js {node_major} detected; modern Angular requires Node.js >= 18.",
                "Angular 14.3.0 is the highest compatible release for this runtime.",
            ]
            constraints = ["Node.js runtime constraint prevents using Angular 15+."]
        elif node_major < 18 or (ts_major is not None and ts_major < 5):
            target_version = "16.2.12"
            available_versions = ["16.2.12", "15.2.10", "14.3.0"]
            compatibility = "Compatible with detected environment"
            reasons = [
                f"Node.js {node_major} and TypeScript {env.typescript_version or '4.x'} detected in repository.",
                "Angular 17+ dropped support for Node.js 16 and TypeScript 4.x.",
                "Angular 16.2.12 is the highest compatible version.",
            ]
            constraints = ["Angular 17+ requires Node.js >= 18.13.0 and TypeScript >= 5.2."]
        else:
            # Modern environment: Angular 22.x
            target_version = "22.x"
            available_versions = ["22.x", "21.x", "20.x", "19.x", "18.x"]
            if env.angular_json_path or env.existing_angular_version:
                compatibility = "Compatible with detected project environment"
                reasons = [
                    "Compatible with detected modern Node.js runtime and Angular toolchain.",
                    "Aligns core Angular packages with Angular CLI 22.x.",
                ]
                constraints = []
            else:
                compatibility = "Compatibility requires Node.js / TypeScript alignment."
                reasons = [
                    "Compatibility requires Node.js / TypeScript alignment.",
                    "Requires configuring Angular CLI toolchain, TypeScript 5.6+, and RxJS 7.8+ in project.",
                ]
                constraints = [
                    "Requires alignment between Angular CLI and backend build artifacts.",
                ]

        if current:
            reasons.insert(0, f"Detected existing Angular dependency: {current}.")

        return FrameworkRecommendation(
            framework="Angular",
            target_version=target_version,
            compatibility=compatibility,
            is_recommended=False,
            reasons=reasons,
            constraints=constraints,
            available_versions=available_versions,
            current_version=cleaned_current or current,
        )
