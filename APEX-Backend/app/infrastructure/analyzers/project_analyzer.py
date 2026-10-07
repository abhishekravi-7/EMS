"""Coordinates all Discovery detectors over a cloned project.

Reads the root build files once (parsing ``pom.xml`` a single time), then
delegates each concern to its dedicated detector and assembles a
:class:`ProjectAnalysis`. Strictly read-only — nothing here modifies the repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, ParseError  # nosec B405

from defusedxml.ElementTree import fromstring  # nosec B405

from app.infrastructure.analyzers.api_endpoint_detector import ApiEndpointDetector
from app.infrastructure.analyzers.build_metadata_analyzer import (
    BomVersion,
    BuildMetadataAnalyzer,
    BuildPlugin,
)
from app.infrastructure.analyzers.build_tool_detector import BuildToolDetector
from app.infrastructure.analyzers.dependency_analyzer import Dependency, DependencyAnalyzer
from app.infrastructure.analyzers.frontend_detector import FrontendDetector, FrontendResult
from app.infrastructure.analyzers.java_version_detector import JavaVersionDetector
from app.infrastructure.analyzers.module_detector import ModuleDetector
from app.infrastructure.analyzers.project_type_detector import ProjectTypeDetector
from app.infrastructure.analyzers.spring_boot_detector import SpringBootDetector
from app.infrastructure.analyzers.spring_entrypoint_scanner import SpringEntrypointScanner
from app.infrastructure.analyzers.spring_framework_detector import SpringFrameworkDetector
from app.infrastructure.analyzers.view_technology_analyzer import ViewTechnologyAnalyzer
from app.brd.analyzers.brd_repository_evidence import BrdRepositoryEvidenceScanner
from app.infrastructure.analyzers.repository_file_categorizer import (
    CAT_ANGULAR,
    CAT_CONFIGURATION,
    CAT_CSS,
    CAT_DOCUMENTATION,
    CAT_HTML,
    CAT_JAVA,
    CAT_JAVA_TEST,
    CAT_JAVASCRIPT,
    CAT_JSF,
    CAT_JSP,
    CAT_OTHER,
    CAT_REACT,
    CAT_RESOURCES,
    CAT_SCRIPTS,
    CAT_SQL,
    CAT_TYPESCRIPT,
    CAT_XML,
    RepositoryFileCategorizer,
)
from app.shared import file_utils


@dataclass(frozen=True)
class ProjectAnalysis:
    build_tool: str
    primary_build_tool: str | None
    build_warning: str | None
    current_java_version: str
    spring_boot_version: str | None
    spring_framework_version: str | None
    spring_boot_signal: bool
    spring_entry_class: str | None
    project_type: str
    multi_module: bool
    modules: list[str]
    dependencies: list[Dependency]
    build_plugins: list[BuildPlugin]
    bom_versions: list[BomVersion]
    frameworks: list[str]
    frontend: FrontendResult
    has_pom_xml: bool
    has_build_gradle: bool
    has_build_gradle_kts: bool
    has_package_json: bool
    has_src_main: bool
    has_src_test: bool
    has_tests: bool
    project_root: Path
    api_endpoints: list[dict[str, Any]] = field(default_factory=list)
    java_files: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    other_files: list[str] = field(default_factory=list)
    jsp_files: list[str] = field(default_factory=list)
    jsf_files: list[str] = field(default_factory=list)
    total_file_count: int = 0
    jsp_file_count: int = 0
    jsf_file_count: int = 0
    file_metrics: dict[str, Any] = field(default_factory=dict)
    view_technologies: dict[str, Any] = field(default_factory=dict)
    test_files: list[str] = field(default_factory=list)
    frontend_files: list[str] = field(default_factory=list)
    documentation_evidence: list[dict[str, Any]] = field(default_factory=list)
    web_routes: list[dict[str, Any]] = field(default_factory=list)
    gradle_builds: list[dict[str, Any]] = field(default_factory=list)
    workflow_edges: list[dict[str, Any]] = field(default_factory=list)
    test_evidence: list[dict[str, Any]] = field(default_factory=list)
    repository_kind: str = "APPLICATION_REPOSITORY"
    scheduled_jobs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def java_loc(self) -> int:
        return len(self.java_files) * 185

    @property
    def config_loc(self) -> int:
        return len(self.config_files) * 50

    @property
    def frontend_loc(self) -> int:
        return len(self.frontend_files or (self.jsp_files + self.jsf_files)) * 120

    @property
    def test_loc(self) -> int:
        return len(self.test_files) * 100

    @property
    def other_loc(self) -> int:
        return len(self.other_files) * 40

    @property
    def total_loc(self) -> int:
        return self.java_loc + self.config_loc + self.frontend_loc + self.test_loc + self.other_loc

    @property
    def dependency_count(self) -> int:
        return len(self.dependencies)

    @property
    def is_supported(self) -> bool:
        return self.build_tool in ("MAVEN", "GRADLE")


class ProjectAnalyzer:
    """Runs every detector over the cloned repository root."""

    def __init__(self) -> None:
        self._build_tool = BuildToolDetector()
        self._java_version = JavaVersionDetector()
        self._spring_boot = SpringBootDetector()
        self._spring_framework = SpringFrameworkDetector()
        self._spring_entrypoint = SpringEntrypointScanner()
        self._dependencies = DependencyAnalyzer()
        self._metadata = BuildMetadataAnalyzer()
        self._modules = ModuleDetector()
        self._project_type = ProjectTypeDetector()
        self._frontend = FrontendDetector()
        self._api_endpoints = ApiEndpointDetector()
        self._view_technology = ViewTechnologyAnalyzer()
        self._brd_evidence = BrdRepositoryEvidenceScanner()
        self._file_categorizer = RepositoryFileCategorizer()

    def analyze(self, root: Path) -> ProjectAnalysis:
        # The Java project may live in a subfolder (e.g. backend/pom.xml) rather
        # than the repo root. Resolve the actual project directory and analyze
        # from there; the frontend is still detected across the whole repo.
        project_root = self._resolve_project_root(root)

        build_tool = self._build_tool.detect(project_root)

        pom_root = (
            self._parse_pom(project_root / "pom.xml") if build_tool.has_pom_xml else None
        )
        build_gradle_text = self._read_gradle_build(project_root)
        settings_gradle_text = self._read_first(
            project_root, "settings.gradle", "settings.gradle.kts"
        )
        gradle_properties_text = self._read_first(project_root, "gradle.properties")

        java_version = self._java_version.detect(
            build_tool.build_tool, pom_root, build_gradle_text, gradle_properties_text
        )
        spring_boot_version = self._spring_boot.detect(pom_root, build_gradle_text)
        spring_boot_signal = self._spring_boot.has_signal(pom_root, build_gradle_text)
        spring_framework_version = self._spring_framework.detect(pom_root, build_gradle_text)

        # Single source of truth file categorization pass
        repo_metrics = self._file_categorizer.categorize_repository(root)
        file_metrics = repo_metrics.to_dict()
        total_file_count = repo_metrics.total

        # Populate backward-compatible lists from category_files
        cat_files = repo_metrics.category_files
        java_files = cat_files.get(CAT_JAVA, [])
        jsp_files = cat_files.get(CAT_JSP, [])
        jsf_files = cat_files.get(CAT_JSF, [])
        config_files = cat_files.get(CAT_XML, []) + cat_files.get(CAT_CONFIGURATION, [])
        other_files = (
            cat_files.get(CAT_REACT, [])
            + cat_files.get(CAT_ANGULAR, [])
            + cat_files.get(CAT_JAVASCRIPT, [])
            + cat_files.get(CAT_TYPESCRIPT, [])
            + cat_files.get(CAT_CSS, [])
            + cat_files.get(CAT_HTML, [])
            + cat_files.get(CAT_RESOURCES, [])
            + cat_files.get(CAT_DOCUMENTATION, [])
            + cat_files.get(CAT_SCRIPTS, [])
            + cat_files.get(CAT_SQL, [])
            + cat_files.get(CAT_OTHER, [])
        )
        test_files = [fc.rel_path for fc in repo_metrics.classifications if fc.is_test]
        frontend_files = (
            cat_files.get(CAT_JSP, [])
            + cat_files.get(CAT_JSF, [])
            + cat_files.get(CAT_REACT, [])
            + cat_files.get(CAT_ANGULAR, [])
            + cat_files.get(CAT_JAVASCRIPT, [])
            + cat_files.get(CAT_TYPESCRIPT, [])
            + cat_files.get(CAT_CSS, [])
            + cat_files.get(CAT_HTML, [])
        )

        spring_entry_class: str | None = None
        if not spring_boot_version and not spring_boot_signal:
            # Build-file signals were inconclusive (e.g. a custom parent that
            # manages the Spring Boot version elsewhere) -- fall back to a
            # real code-level scan for the entry-point markers.
            entrypoint = self._spring_entrypoint.scan(project_root, java_files)
            if entrypoint.found:
                spring_boot_signal = True
                spring_entry_class = entrypoint.entry_class

        dependencies = self._dependencies.analyze(pom_root, build_gradle_text, project_root)
        build_plugins = self._metadata.detect_plugins(pom_root, build_gradle_text)
        bom_versions = self._metadata.detect_boms(pom_root, build_gradle_text)
        frameworks = self._metadata.detect_frameworks(
            spring_boot_version=spring_boot_version,
            dependencies=dependencies,
            build_gradle_text=build_gradle_text,
            spring_boot_signal=spring_boot_signal,
        )
        modules = self._modules.detect(pom_root, settings_gradle_text)
        project_type = self._project_type.detect(
            project_root,
            build_tool.is_supported,
            spring_boot_version,
            dependencies,
            spring_boot_signal=spring_boot_signal,
        )
        # Scan the whole repo for a frontend (it commonly sits beside the backend,
        # e.g. repo/frontend + repo/backend).
        frontend = self._frontend.detect(root)

        api_endpoints = self._api_endpoints.detect(project_root)

        has_src_main = file_utils.exists(project_root, "src", "main")
        has_src_test = file_utils.exists(project_root, "src", "test")

        view_technologies = self._view_technology.analyze(
            root=root,
            jsp_files=jsp_files,
            jsf_files=jsf_files,
            java_files=java_files,
            dependencies=dependencies,
        ).to_dict()

        all_files_plain = [fc.rel_path for fc in repo_metrics.classifications]
        brd_evidence = self._brd_evidence.scan(root, all_files_plain, project_type)

        return ProjectAnalysis(
            build_tool=build_tool.build_tool,
            primary_build_tool=build_tool.primary_build_tool,
            build_warning=build_tool.warning,
            current_java_version=java_version,
            spring_boot_version=spring_boot_version,
            spring_framework_version=spring_framework_version,
            spring_boot_signal=spring_boot_signal,
            spring_entry_class=spring_entry_class,
            project_type=project_type,
            multi_module=modules.multi_module,
            modules=modules.modules,
            dependencies=dependencies,
            build_plugins=build_plugins,
            bom_versions=bom_versions,
            frameworks=frameworks,
            frontend=frontend,
            has_pom_xml=build_tool.has_pom_xml,
            has_build_gradle=build_tool.has_build_gradle,
            has_build_gradle_kts=build_tool.has_build_gradle_kts,
            has_package_json=(root / "package.json").is_file() or frontend.detected,
            has_src_main=has_src_main,
            has_src_test=has_src_test,
            has_tests=has_src_test or len(test_files) > 0,
            project_root=project_root,
            api_endpoints=api_endpoints,
            java_files=java_files,
            config_files=config_files,
            other_files=other_files,
            jsp_files=jsp_files,
            jsf_files=jsf_files,
            total_file_count=total_file_count,
            jsp_file_count=len(jsp_files),
            jsf_file_count=len(jsf_files),
            file_metrics=file_metrics,
            view_technologies=view_technologies,
            test_files=test_files,
            frontend_files=frontend_files,
            documentation_evidence=brd_evidence.documentation,
            web_routes=brd_evidence.web_routes,
            gradle_builds=brd_evidence.gradle_builds,
            workflow_edges=brd_evidence.workflow_edges,
            test_evidence=brd_evidence.test_evidence,
            repository_kind=brd_evidence.repository_kind,
        )

    @staticmethod
    def _resolve_project_root(root: Path) -> Path:
        """Return the directory that holds the build file.

        Prefers the repo root when it already has a build file; otherwise finds
        the shallowest subfolder containing a ``pom.xml`` / ``build.gradle`` /
        ``build.gradle.kts``. Falls back to the repo root when none is found.
        """
        build_files = ("pom.xml", "build.gradle", "build.gradle.kts")
        if any((root / name).is_file() for name in build_files):
            return root
        found = file_utils.find_shallowest_dir_with(root, build_files)
        return found or root

    # -- file reading -------------------------------------------------------- #

    @staticmethod
    def _parse_pom(pom_path: Path) -> Element | None:
        text = file_utils.read_text(pom_path)
        if not text.strip():
            return None
        try:
            root = fromstring(text)
        except ParseError:
            return None
        # Strip XML namespaces so downstream detectors can query bare tag names.
        for element in root.iter():
            if isinstance(element.tag, str) and "}" in element.tag:
                element.tag = element.tag.split("}", 1)[1]
        return root

    @staticmethod
    def _read_gradle_build(root: Path) -> str:
        parts = [
            file_utils.read_text(root / name)
            for name in ("build.gradle", "build.gradle.kts")
            if (root / name).is_file()
        ]
        return "\n".join(parts)

    @staticmethod
    def _read_first(root: Path, *names: str) -> str:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return file_utils.read_text(candidate)
        return ""
