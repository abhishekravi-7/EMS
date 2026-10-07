"""Dynamic repository analysis for modernized and source applications.

Inspects repository filesystem to detect:
- Build tools (Maven, Gradle, npm/yarn/pnpm)
- Project structure (single-module vs multi-module, submodules)
- Frameworks (Spring Boot, Spring MVC, Quarkus, Micronaut, React, Angular, Vue, Vite, Next.js, static)
- Application archetype (BACKEND_ONLY, FRONTEND_ONLY, FULL_STACK, MONOLITHIC_JAVA, STATIC_UI)
- Configured ports from properties/yml/yaml/env/package.json
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ApplicationType(str, Enum):
    BACKEND_ONLY = "BACKEND_ONLY"
    FRONTEND_ONLY = "FRONTEND_ONLY"
    FULL_STACK = "FULL_STACK"
    MONOLITHIC_JAVA = "MONOLITHIC_JAVA"
    STATIC_UI = "STATIC_UI"


class BuildToolType(str, Enum):
    MAVEN = "MAVEN"
    GRADLE = "GRADLE"
    NPM = "NPM"
    NONE = "NONE"


@dataclass
class JavaModuleInfo:
    name: str
    path: Path
    is_root: bool = False
    has_pom: bool = False
    has_gradle: bool = False
    is_spring_boot: bool = False
    is_quarkus: bool = False
    is_micronaut: bool = False
    packaging: str = "jar"  # jar, war, pom
    main_class: str | None = None
    configured_port: int | None = None
    jar_artifacts: list[Path] = field(default_factory=list)


@dataclass
class FrontendModuleInfo:
    name: str
    path: Path
    framework: str  # react, angular, vue, vite, nextjs, static
    has_package_json: bool = True
    dev_command: str = "npm run dev"
    configured_port: int | None = None
    build_dir: Path | None = None


@dataclass
class RepositoryAnalysisResult:
    repo_dir: Path
    app_type: ApplicationType
    build_tool: BuildToolType
    build_wrapper_cmd: str | None
    is_multi_module: bool
    backend_modules: list[JavaModuleInfo] = field(default_factory=list)
    frontend_modules: list[FrontendModuleInfo] = field(default_factory=list)
    primary_backend_module: JavaModuleInfo | None = None
    primary_frontend_module: FrontendModuleInfo | None = None
    configured_backend_port: int = 8080
    configured_frontend_port: int | None = None
    has_embedded_ui: bool = False  # Thymeleaf, JSP, static resources inside Spring Boot

    @property
    def archetype(self) -> ApplicationType:
        return self.app_type

    @property
    def configured_port(self) -> int:
        return self.configured_backend_port

    @property
    def wrapper_script(self) -> str | None:
        return self.build_wrapper_cmd


class RepositoryAnalyzer:
    """Inspects a repository to determine its build tool, architecture, and runtime requirements."""

    def __init__(self, repo_dir: Path | str) -> None:
        self.repo_dir = Path(repo_dir).resolve()

    def analyze(self) -> RepositoryAnalysisResult:
        """Performs full inspection of the repository."""
        is_windows = os.name == "nt"

        # 1. Inspect Java Modules first to catch subfolder pom.xml / build.gradle
        backend_modules: list[JavaModuleInfo] = []
        is_multi_module = False

        maven_modules, mvn_multi = self._inspect_maven_modules()
        gradle_modules, gradle_multi = self._inspect_gradle_modules()

        if maven_modules:
            backend_modules = maven_modules
            is_multi_module = mvn_multi
        elif gradle_modules:
            backend_modules = gradle_modules
            is_multi_module = gradle_multi

        # 2. Inspect Frontend Modules
        frontend_modules = self._inspect_frontend_modules()

        # 3. Determine Build Tool & Wrappers
        has_pom = any(m.has_pom for m in backend_modules) or (self.repo_dir / "pom.xml").exists()
        has_gradle = any(m.has_gradle for m in backend_modules) or (self.repo_dir / "build.gradle").exists() or (self.repo_dir / "build.gradle.kts").exists()
        has_pkg_json = any(f.has_package_json for f in frontend_modules) or (self.repo_dir / "package.json").exists()

        primary_backend: JavaModuleInfo | None = None
        if backend_modules:
            executable_candidates = [
                m for m in backend_modules
                if m.packaging != "pom" and (m.is_spring_boot or m.main_class or any(k in m.name.lower() for k in ["app", "server", "service", "portal", "backend"]))
            ]
            if executable_candidates:
                primary_backend = executable_candidates[0]
            else:
                non_pom = [m for m in backend_modules if m.packaging != "pom"]
                primary_backend = non_pom[0] if non_pom else backend_modules[0]

        mvnw_name = "mvnw.cmd" if is_windows else "mvnw"
        gradlew_name = "gradlew.bat" if is_windows else "gradlew"

        build_tool = BuildToolType.NONE
        build_wrapper_cmd = None

        if has_pom:
            build_tool = BuildToolType.MAVEN
            if (self.repo_dir / mvnw_name).exists():
                build_wrapper_cmd = str(self.repo_dir / mvnw_name)
            elif primary_backend and (primary_backend.path / mvnw_name).exists():
                build_wrapper_cmd = str(primary_backend.path / mvnw_name)
            else:
                build_wrapper_cmd = "mvn"
        elif has_gradle:
            build_tool = BuildToolType.GRADLE
            if (self.repo_dir / gradlew_name).exists():
                build_wrapper_cmd = str(self.repo_dir / gradlew_name)
            elif primary_backend and (primary_backend.path / gradlew_name).exists():
                build_wrapper_cmd = str(primary_backend.path / gradlew_name)
            else:
                build_wrapper_cmd = "gradle"
        elif has_pkg_json:
            build_tool = BuildToolType.NPM
            build_wrapper_cmd = "npm.cmd" if is_windows else "npm"

        # 5. Determine Primary Frontend Module
        primary_frontend: FrontendModuleInfo | None = frontend_modules[0] if frontend_modules else None

        # 6. Check for Embedded UI (Thymeleaf, JSP, static resources inside Spring Boot)
        has_embedded_ui = self._detect_embedded_ui(backend_modules)

        # 7. Classify Application Type
        if primary_backend and primary_frontend:
            app_type = ApplicationType.FULL_STACK
        elif primary_backend and has_embedded_ui:
            app_type = ApplicationType.MONOLITHIC_JAVA
        elif primary_backend:
            app_type = ApplicationType.BACKEND_ONLY
        elif primary_frontend:
            app_type = ApplicationType.FRONTEND_ONLY
        elif (self.repo_dir / "index.html").exists():
            app_type = ApplicationType.STATIC_UI
        else:
            app_type = ApplicationType.BACKEND_ONLY

        # 8. Resolve Configured Ports
        backend_port = self._resolve_configured_backend_port(backend_modules)
        frontend_port = primary_frontend.configured_port if primary_frontend else None

        return RepositoryAnalysisResult(
            repo_dir=self.repo_dir,
            app_type=app_type,
            build_tool=build_tool,
            build_wrapper_cmd=build_wrapper_cmd,
            is_multi_module=is_multi_module,
            backend_modules=backend_modules,
            frontend_modules=frontend_modules,
            primary_backend_module=primary_backend,
            primary_frontend_module=primary_frontend,
            configured_backend_port=backend_port,
            configured_frontend_port=frontend_port,
            has_embedded_ui=has_embedded_ui,
        )

    def _inspect_maven_modules(self) -> tuple[list[JavaModuleInfo], bool]:
        """Scans root pom.xml and child modules, including subfolder Maven projects."""
        modules: list[JavaModuleInfo] = []
        root_pom = self.repo_dir / "pom.xml"
        root_is_sb = False

        if root_pom.exists():
            content = root_pom.read_text(encoding="utf-8", errors="ignore")
            submodule_names = re.findall(r"<module>([^<]+)</module>", content)

            root_pkg = "jar"
            pkg_m = re.search(r"<packaging>([^<]+)</packaging>", content)
            if pkg_m:
                root_pkg = pkg_m.group(1).strip().lower()

            root_is_sb = "spring-boot" in content or "org.springframework.boot" in content
            root_mod = JavaModuleInfo(
                name=self.repo_dir.name,
                path=self.repo_dir,
                is_root=True,
                has_pom=True,
                is_spring_boot=root_is_sb,
                packaging=root_pkg,
                configured_port=self._extract_port_from_dir(self.repo_dir),
            )
            modules.append(root_mod)

            # Inspect declared submodules
            for s_name in submodule_names:
                s_path = self.repo_dir / s_name.strip()
                s_pom = s_path / "pom.xml"
                if s_pom.exists():
                    s_content = s_pom.read_text(encoding="utf-8", errors="ignore")
                    s_pkg = "jar"
                    s_pkg_m = re.search(r"<packaging>([^<]+)</packaging>", s_content)
                    if s_pkg_m:
                        s_pkg = s_pkg_m.group(1).strip().lower()
                    s_is_sb = "spring-boot" in s_content or "org.springframework.boot" in s_content or root_is_sb
                    s_mod = JavaModuleInfo(
                        name=s_path.name,
                        path=s_path,
                        is_root=False,
                        has_pom=True,
                        is_spring_boot=s_is_sb,
                        packaging=s_pkg,
                        configured_port=self._extract_port_from_dir(s_path),
                    )
                    modules.append(s_mod)

        # Also search immediate subdirectories for pom.xml
        if self.repo_dir.is_dir():
            for child in self.repo_dir.iterdir():
                if child.is_dir() and (child / "pom.xml").exists() and not any(m.path == child for m in modules):
                    child_content = (child / "pom.xml").read_text(encoding="utf-8", errors="ignore")
                    c_is_sb = "spring-boot" in child_content or "org.springframework.boot" in child_content or root_is_sb
                    c_pkg = "jar"
                    c_pkg_m = re.search(r"<packaging>([^<]+)</packaging>", child_content)
                    if c_pkg_m:
                        c_pkg = c_pkg_m.group(1).strip().lower()
                    c_mod = JavaModuleInfo(
                        name=child.name,
                        path=child,
                        is_root=False,
                        has_pom=True,
                        is_spring_boot=c_is_sb,
                        packaging=c_pkg,
                        configured_port=self._extract_port_from_dir(child),
                    )
                    modules.append(c_mod)

        is_multi_module = len(modules) > 1
        return modules, is_multi_module

    def _inspect_gradle_modules(self) -> tuple[list[JavaModuleInfo], bool]:
        """Scans Gradle settings.gradle and child projects, including subfolder Gradle projects."""
        modules: list[JavaModuleInfo] = []

        settings_file = self.repo_dir / "settings.gradle"
        if not settings_file.exists():
            settings_file = self.repo_dir / "settings.gradle.kts"

        root_gradle = self.repo_dir / "build.gradle"
        if not root_gradle.exists():
            root_gradle = self.repo_dir / "build.gradle.kts"

        subproject_names: list[str] = []
        if settings_file.exists():
            s_content = settings_file.read_text(encoding="utf-8", errors="ignore")
            for line in s_content.splitlines():
                if line.strip().startswith("include"):
                    clean = re.sub(r"include\s*|['\":()]", "", line)
                    for item in clean.split(","):
                        it = item.strip()
                        if it:
                            subproject_names.append(it)

        if root_gradle.exists() or settings_file.exists():
            root_mod = JavaModuleInfo(
                name=self.repo_dir.name,
                path=self.repo_dir,
                is_root=True,
                has_gradle=True,
                is_spring_boot=True,
                packaging="jar",
                configured_port=self._extract_port_from_dir(self.repo_dir),
            )
            modules.append(root_mod)

            for s_name in subproject_names:
                s_path = self.repo_dir / s_name
                if s_path.exists():
                    s_mod = JavaModuleInfo(
                        name=s_name,
                        path=s_path,
                        is_root=False,
                        has_gradle=True,
                        is_spring_boot=True,
                        packaging="jar",
                        configured_port=self._extract_port_from_dir(s_path),
                    )
                    modules.append(s_mod)

        # Search immediate subdirectories for build.gradle
        if self.repo_dir.is_dir():
            for child in self.repo_dir.iterdir():
                if child.is_dir() and ((child / "build.gradle").exists() or (child / "build.gradle.kts").exists()) and not any(m.path == child for m in modules):
                    c_mod = JavaModuleInfo(
                        name=child.name,
                        path=child,
                        is_root=False,
                        has_gradle=True,
                        is_spring_boot=True,
                        packaging="jar",
                        configured_port=self._extract_port_from_dir(child),
                    )
                    modules.append(c_mod)

        is_multi_module = len(modules) > 1
        return modules, is_multi_module

    def _inspect_frontend_modules(self) -> list[FrontendModuleInfo]:
        """Finds frontend applications in repo root or subdirectories like frontend/, client/, ui/."""
        frontends: list[FrontendModuleInfo] = []

        dirs_to_check = [self.repo_dir]
        for sub in ["frontend", "client", "ui", "web", "app-frontend", "portal"]:
            sub_p = self.repo_dir / sub
            if sub_p.is_dir():
                dirs_to_check.append(sub_p)

        if self.repo_dir.is_dir():
            for child in self.repo_dir.iterdir():
                if child.is_dir() and (child / "package.json").exists() and child not in dirs_to_check:
                    dirs_to_check.append(child)

        for d in dirs_to_check:
            pkg_json = d / "package.json"
            if not pkg_json.exists():
                continue

            content = pkg_json.read_text(encoding="utf-8", errors="ignore")
            # Determine framework
            if "next" in content:
                fw = "nextjs"
                dev_cmd = "npm run dev"
                port = 3000
            elif "@angular/core" in content or (d / "angular.json").exists():
                fw = "angular"
                dev_cmd = "npm start"
                port = 4200
            elif "vue" in content:
                fw = "vue"
                dev_cmd = "npm run dev"
                port = 5173
            elif "vite" in content or (d / "vite.config.ts").exists() or (d / "vite.config.js").exists():
                fw = "vite"
                dev_cmd = "npm run dev"
                port = 5173
            elif "react" in content:
                fw = "react"
                dev_cmd = "npm start"
                port = 3000
            else:
                fw = "node"
                dev_cmd = "npm start"
                port = 3000

            frontends.append(
                FrontendModuleInfo(
                    name=d.name,
                    path=d,
                    framework=fw,
                    has_package_json=True,
                    dev_command=dev_cmd,
                    configured_port=port,
                    build_dir=d / "dist" if (d / "dist").exists() else (d / "build" if (d / "build").exists() else None),
                )
            )

        return frontends

    def _detect_embedded_ui(self, backend_modules: list[JavaModuleInfo]) -> bool:
        """Detects whether backend contains embedded templates (Thymeleaf, FreeMarker, JSP) or static web resources."""
        paths_to_check = [self.repo_dir] + [m.path for m in backend_modules]
        for p in paths_to_check:
            for pattern in [
                "src/main/resources/templates",
                "src/main/resources/static",
                "src/main/webapp",
                "src/main/resources/public",
            ]:
                check_dir = p / pattern
                if check_dir.is_dir() and any(check_dir.iterdir()):
                    return True
        return False

    def _extract_port_from_dir(self, directory: Path) -> int | None:
        """Extracts configured server.port from properties or yaml files."""
        # 1. application.properties
        for prop_path in [
            directory / "src" / "main" / "resources" / "application.properties",
            directory / "application.properties",
        ]:
            if prop_path.exists():
                for line in prop_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    clean = line.strip()
                    if clean.startswith("server.port") and "=" in clean:
                        try:
                            val = clean.split("=", 1)[1].strip()
                            # Strip comments or trailing tokens
                            val = re.sub(r"[#;].*$", "", val).strip()
                            if val.isdigit():
                                return int(val)
                        except Exception:
                            pass

        # 2. application.yml / application.yaml
        for yml_path in [
            directory / "src" / "main" / "resources" / "application.yml",
            directory / "src" / "main" / "resources" / "application.yaml",
            directory / "application.yml",
            directory / "application.yaml",
        ]:
            if yml_path.exists():
                content = yml_path.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"server:\s*\n(?:\s+.*\n)*?\s+port:\s*(\d+)", content)
                if m:
                    return int(m.group(1))
                m_single = re.search(r"server\.port:\s*(\d+)", content)
                if m_single:
                    return int(m_single.group(1))

        return None

    def _resolve_configured_backend_port(self, modules: list[JavaModuleInfo]) -> int:
        """Finds configured backend port, checking modules in priority order."""
        for m in modules:
            if m.configured_port:
                return m.configured_port
        return 8080
