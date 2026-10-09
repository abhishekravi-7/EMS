"""Detect build plugins, imported BOMs, and framework signals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from xml.etree.ElementTree import Element  # nosec B405 - type annotation only; callers parse via defusedxml

from app.infrastructure.analyzers.dependency_analyzer import Dependency


@dataclass(frozen=True)
class BuildPlugin:
    group_id: str
    artifact_id: str
    version: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "groupId": self.group_id,
            "artifactId": self.artifact_id,
            "version": self.version
        }


@dataclass(frozen=True)
class BomVersion:
    group_id: str
    artifact_id: str
    version: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "groupId": self.group_id,
            "artifactId": self.artifact_id,
            "version": self.version,
        }


class BuildMetadataAnalyzer:
    def detect_plugins(self, pom_root: Element | None, build_gradle_text: str) -> list[BuildPlugin]:
        if pom_root is not None:
            return self._maven_plugins(pom_root)
        return self._gradle_plugins(build_gradle_text)

    def detect_boms(self, pom_root: Element | None, build_gradle_text: str) -> list[BomVersion]:
        if pom_root is not None:
            return self._maven_boms(pom_root)
        return self._gradle_boms(build_gradle_text)

    def detect_frameworks(
        self,
        *,
        spring_boot_version: str | None,
        dependencies: list[Dependency],
        build_gradle_text: str,
        spring_boot_signal: bool = False,
        frontend_dependencies: list[Dependency] | None = None,
    ) -> list[str]:
        frameworks: set[str] = set()
        coordinates = {
            f"{dependency.group_id}:{dependency.artifact_id}".lower()
            for dependency in dependencies
        }
        groups = {dependency.group_id.lower() for dependency in dependencies}

        # Java Backend Frameworks & Libraries
        if (
            spring_boot_version
            or spring_boot_signal
            or any(item.startswith("org.springframework.boot:") for item in coordinates)
        ):
            frameworks.add("spring-boot")
        if "org.springframework" in groups:
            frameworks.add("spring-framework")
        if any("spring-security" in item for item in coordinates):
            frameworks.add("spring-security")
        if any(item.startswith("org.springframework.cloud:") for item in coordinates):
            frameworks.add("spring-cloud")
        if any("spring-data" in item or "starter-data-" in item for item in coordinates):
            frameworks.add("spring-data")
        if any(item.startswith("org.hibernate") for item in groups) or any("hibernate" in item for item in coordinates):
            frameworks.add("hibernate")
        if any(item.startswith("jakarta.") for item in groups):
            frameworks.add("jakarta-ee")
        if any(item.startswith("javax.") for item in groups):
            frameworks.add("javax-ee")
        if any("junit" in item for item in coordinates):
            frameworks.add("junit")
        if any("mockito" in item for item in coordinates):
            frameworks.add("mockito")
        if any("lombok" in item for item in coordinates):
            frameworks.add("lombok")
        if any("liquibase" in item for item in coordinates):
            frameworks.add("liquibase")
        if any("flyway" in item for item in coordinates):
            frameworks.add("flyway")
        if any("springdoc" in item or "swagger" in item for item in coordinates):
            frameworks.add("springdoc-openapi")
        if any(item.startswith("org.apache.struts") for item in groups):
            frameworks.add("struts")
        if any("mybatis" in item for item in coordinates):
            frameworks.add("mybatis")
        if "org.springframework.boot" in build_gradle_text:
            frameworks.add("spring-boot")

        # Frontend Frameworks & Libraries
        all_frontend_deps = list(frontend_dependencies or [])
        # Also check if any npm dependencies were passed in dependencies directly
        for d in dependencies:
            if d.type and d.type.startswith("npm"):
                all_frontend_deps.append(d)

        if all_frontend_deps:
            fe_names = {(d.name or d.artifact_id or "").lower() for d in all_frontend_deps}
            fe_coords = {f"{d.group_id}:{d.artifact_id}".lower() for d in all_frontend_deps}

            # Angular: @angular/core as primary evidence
            if (
                "@angular/core" in fe_names
                or any(d.group_id == "@angular" and d.artifact_id in ("core", "@angular/core") for d in all_frontend_deps)
                or any(c in ("@angular:core", "@angular:@angular/core") for c in fe_coords)
            ):
                frameworks.add("angular")

            # Angular Router
            if (
                "@angular/router" in fe_names
                or any(d.group_id == "@angular" and d.artifact_id in ("router", "@angular/router") for d in all_frontend_deps)
            ):
                frameworks.add("angular-router")

            # React: react or react-dom as primary evidence
            if (
                "react" in fe_names
                or "react-dom" in fe_names
                or any(d.artifact_id in ("react", "react-dom") for d in all_frontend_deps)
            ):
                frameworks.add("react")

            # React Router: react-router or react-router-dom
            if (
                "react-router" in fe_names
                or "react-router-dom" in fe_names
                or any(d.artifact_id in ("react-router", "react-router-dom") for d in all_frontend_deps)
            ):
                frameworks.add("react-router")

            # Vue
            if "vue" in fe_names or any(d.artifact_id == "vue" for d in all_frontend_deps):
                frameworks.add("vue")

            # Svelte
            if "svelte" in fe_names or any(d.artifact_id == "svelte" for d in all_frontend_deps):
                frameworks.add("svelte")

            # TypeScript
            if "typescript" in fe_names or any(d.artifact_id == "typescript" for d in all_frontend_deps):
                frameworks.add("typescript")

            # Vite
            if "vite" in fe_names or any(d.artifact_id == "vite" for d in all_frontend_deps):
                frameworks.add("vite")

            # Webpack
            if "webpack" in fe_names or any(d.artifact_id == "webpack" for d in all_frontend_deps):
                frameworks.add("webpack")

            # Tailwind CSS
            if "tailwindcss" in fe_names or any(d.artifact_id == "tailwindcss" for d in all_frontend_deps):
                frameworks.add("tailwindcss")

            # Axios
            if "axios" in fe_names or any(d.artifact_id == "axios" for d in all_frontend_deps):
                frameworks.add("axios")

            # Next.js
            if "next" in fe_names or any(d.artifact_id == "next" for d in all_frontend_deps):
                frameworks.add("next")

            # Redux
            if (
                "redux" in fe_names
                or "@reduxjs/toolkit" in fe_names
                or any("redux" in d.artifact_id.lower() for d in all_frontend_deps)
            ):
                frameworks.add("redux")

            # Testing Tools
            if "jest" in fe_names or any(d.artifact_id == "jest" for d in all_frontend_deps):
                frameworks.add("jest")
            if "vitest" in fe_names or any(d.artifact_id == "vitest" for d in all_frontend_deps):
                frameworks.add("vitest")
            if "cypress" in fe_names or any(d.artifact_id == "cypress" for d in all_frontend_deps):
                frameworks.add("cypress")
            if (
                "@playwright/test" in fe_names
                or "playwright" in fe_names
                or any(d.artifact_id in ("playwright", "@playwright/test") for d in all_frontend_deps)
            ):
                frameworks.add("playwright")

        return sorted(frameworks)

    # -- Maven --------------------------------------------------------------- #

    @staticmethod
    def _maven_plugins(pom_root: Element) -> list[BuildPlugin]:
        plugins: list[BuildPlugin] = []
        seen: set[str] = set()
        for plugin in pom_root.iter("plugin"):
            group = _text(plugin.find("groupId")) or "org.apache.maven.plugins"
            artifact = _text(plugin.find("artifactId"))
            version = _text(plugin.find("version"))
            if not artifact:
                continue
            plugin_id = f"{group}:{artifact}"
            if plugin_id in seen:
                continue
            seen.add(plugin_id)
            plugins.append(BuildPlugin(group, artifact, version))
        return plugins

    @staticmethod
    def _maven_boms(pom_root: Element) -> list[BomVersion]:
        boms: list[BomVersion] = []
        dependency_management = pom_root.find("dependencyManagement")
        if dependency_management is None:
            return boms
        dependencies = dependency_management.find("dependencies")
        if dependencies is None:
            return boms
        for dependency in dependencies.findall("dependency"):
            dep_type = _text(dependency.find("type"))
            scope = _text(dependency.find("scope"))
            if dep_type != "pom" or scope != "import":
                continue
            group = _text(dependency.find("groupId"))
            artifact = _text(dependency.find("artifactId"))
            if group and artifact:
                boms.append(BomVersion(group, artifact, _text(dependency.find("version"))))
        return boms

    # -- Gradle -------------------------------------------------------------- #

    @staticmethod
    def _gradle_plugins(build_text: str) -> list[BuildPlugin]:
        plugins: list[BuildPlugin] = []
        seen: set[str] = set()
        patterns = [
            r"id\s*[( ]\s*['\"]([^'\"]+)['\"]\)?\s*(?:version\s*['\"]([^'\"]+)['\"])?",
            r"classpath\s*[( ]\s*['\"]([^:'\"]+):([^:'\"]+):([^'\"]+)['\"]",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, build_text):
                if match.lastindex and match.lastindex >= 2 and ":" in match.group(1):
                    # classpath case or complex id
                    parts = match.group(1).split(":")
                    group = parts[0]
                    artifact = parts[1]
                    version = parts[2] if len(parts) >= 3 else match.group(2)
                else:
                    # simple id case
                    group = ""
                    artifact = match.group(1)
                    version = match.group(2) if match.lastindex and match.lastindex >= 2 else None

                plugin_id = f"{group}:{artifact}"
                if plugin_id in seen:
                    continue
                seen.add(plugin_id)
                plugins.append(BuildPlugin(group, artifact, version))
        return plugins

    @staticmethod
    def _gradle_boms(build_text: str) -> list[BomVersion]:
        boms: list[BomVersion] = []
        patterns = [
            r"platform\s*[( ]\s*['\"]([^:'\"]+):([^:'\"]+):([^'\"]+)['\"]",
            r"mavenBom\s*[( ]\s*['\"]([^:'\"]+):([^:'\"]+):([^'\"]+)['\"]",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, build_text):
                boms.append(BomVersion(match.group(1), match.group(2), match.group(3)))
        return boms


def _text(node: Element | None) -> str | None:
    return node.text.strip() if node is not None and node.text else None
