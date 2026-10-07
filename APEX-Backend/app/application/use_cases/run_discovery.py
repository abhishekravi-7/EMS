"""Run Discovery use case.

Responsibilities:
  * Validate that the connect report exists (Connect step completed).
  * Prepare the job workspace and clone the repo into ``original-repo``.
  * Analyze the cloned project (read-only) via the ProjectAnalyzer.
  * Save ``discovery-report.json``.
  * Return a clean discovery summary.

Explicitly NOT done here: migration-engine execution, Maven/Gradle builds, pushing
to GitHub, or any modification of the cloned repository.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.exceptions import ConnectReportNotFoundError, UnsupportedProjectError
from app.infrastructure.analyzers.project_analyzer import ProjectAnalysis, ProjectAnalyzer
from app.infrastructure.analyzers.microservice.java_class_scanner import JavaClassScanner
from app.infrastructure.analyzers.view_technology_inspector import ViewTechnologyInspector
from app.infrastructure.analyzers.spring_boot_eligibility import (
    SpringBootEligibility,
    compute_eligibility,
)
from app.infrastructure.git.repository_cloner import RepositoryCloner
from app.infrastructure.persistence.job_repository import JobRepository
from app.infrastructure.workspace.workspace_manager import WorkspaceManager
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.shared import file_utils

logger = logging.getLogger("discovery")

STATUS_COMPLETED = "DISCOVERY_COMPLETED"
NEXT_STEP = "STRATEGY"


@dataclass(frozen=True)
class DiscoveryOutcome:
    """What the use case returns: the ready-to-send response plus the report."""

    response: dict[str, Any]
    report: dict[str, Any]


class RunDiscoveryUseCase:
    def __init__(
        self,
        job_repository: JobRepository | None = None,
        cloner: RepositoryCloner | None = None,
        analyzer: ProjectAnalyzer | None = None,
        scanner: JavaClassScanner | None = None,
        view_inspector: ViewTechnologyInspector | None = None,
    ) -> None:
        self._job_repository = job_repository or JobRepository()
        self._cloner = cloner or RepositoryCloner()
        self._analyzer = analyzer or ProjectAnalyzer()
        self._scanner = scanner or JavaClassScanner()
        self._view_inspector = view_inspector or ViewTechnologyInspector()

    def execute(self, job_id: str, request_token: str | None = None, force_refresh: bool = False) -> DiscoveryOutcome:
        # 1. Connect report must exist.
        connect = self._job_repository.read_connect_report(job_id)
        if not connect:
            logger.error("[DISCOVERY FAILED] - JobID: %s - Connect report missing or Connect step not completed", job_id)
            raise ConnectReportNotFoundError()

        repo_url = connect.get("repoUrl", "")
        owner = connect.get("owner", "")
        repo_name = connect.get("repoName", "")
        visibility = connect.get("repoVisibility", "PUBLIC")
        storage_dir = getattr(self._job_repository, "_storage_dir", None)
        paths = WorkspacePaths(job_id, storage_dir=storage_dir)

        logger.info("[CONNECT -> DISCOVERY] - JobID: %s - Initiating transition to discovery for repo: %s", job_id, repo_url)
        logger.debug("[CONNECT -> DISCOVERY] - JobID: %s - Connect Metadata: owner=%s, repo=%s, visibility=%s", job_id, owner, repo_name, visibility)

        # Check if discovery was already completed and the cloned workspace is intact
        if not force_refresh:
            existing_report = self._job_repository.read_discovery_report(job_id)
            if (
                existing_report
                and existing_report.get("status") == STATUS_COMPLETED
                and paths.original_repo_dir.is_dir()
            ):
                logger.warning("[DISCOVERY REUSE] - JobID: %s - Reusing existing discovery report from cache", job_id)
                response = self._reconstruct_response_from_report(
                    job_id, repo_url, owner, repo_name, visibility, existing_report
                )
                return DiscoveryOutcome(response=response, report=existing_report)

        # The PAT is never persisted with the connect report (secret at rest);
        # it comes from the client on this request, falling back to the env token.
        token = (
            (request_token or "").strip()
            or (settings.github_token or "").strip()
            or None
        )

        logger.info("[DISCOVERY START] - JobID: %s - Repo: %s", job_id, repo_url)

        # 2. Prepare workspace + clone into original-repo (or verify local project).
        workspace = WorkspaceManager(paths)
        workspace.ensure_job_dirs()

        is_local_project = bool(connect.get("isLocalProject")) or repo_url.startswith("local://")

        if is_local_project:
            logger.info("[DISCOVERY LOCAL] - JobID: %s - Using local workspace files", job_id)
            if not paths.original_repo_dir.is_dir() or not any(paths.original_repo_dir.iterdir()):
                logger.error("[DISCOVERY ERROR] - JobID: %s - Local workspace empty or missing", job_id)
                raise UnsupportedProjectError()
        else:
            workspace.prepare_original_repo_target()
            logger.info("[DISCOVERY CLONE] - JobID: %s - Cloning repository into workspace...", job_id)
            self._cloner.clone(
                repo_url,
                paths.original_repo_dir,
                token=token,
                log_path=paths.discovery_log_path,
            )
            logger.info("[DISCOVERY ANALYSIS] - JobID: %s - Analyzing project files...", job_id)

        # 3. Analyze the cloned project (read-only).
        analysis = self._analyzer.analyze(paths.original_repo_dir)
        if not analysis.is_supported:
            logger.error("[DISCOVERY FAILED] - JobID: %s - Unsupported project (no Maven/Gradle build file found)", job_id)
            raise UnsupportedProjectError()

        # Run deeper AST and view analysis for the technical document generation
        logger.info("[DISCOVERY AST SCAN] - JobID: %s - Scanning Java classes and views...", job_id)
        classes = self._scanner.scan(paths.original_repo_dir)
        deep_view = self._view_inspector.inspect(
            repo_root=paths.original_repo_dir,
            jsp_file_paths=analysis.jsp_files,
            jsf_file_paths=analysis.jsf_files,
            java_file_paths=analysis.java_files,
        )
        self._job_repository.save_ast_cache(job_id, analysis, classes, deep_view)

        eligibility = compute_eligibility(
            build_tool_supported=analysis.is_supported,
            build_tool=analysis.build_tool,
            project_type=analysis.project_type,
            spring_framework_version=analysis.spring_framework_version,
            spring_boot_version=analysis.spring_boot_version,
            spring_boot_signal=analysis.spring_boot_signal,
            entrypoint_found=analysis.spring_entry_class is not None,
        )

        logger.info(
            "[DISCOVERY SCAN] - JobID: %s - TotalFiles: %d - JavaFiles: %d - ConfigFiles: %d - TestFiles: %d",
            job_id,
            analysis.total_file_count,
            len(analysis.java_files),
            len(analysis.config_files),
            len(analysis.test_files),
        )

        logger.debug(
            "[DISCOVERY METRICS] - JobID: %s - JavaLOC: %d - ConfigLOC: %d - TestLOC: %d - Modules: %d - Endpoints: %d",
            job_id,
            analysis.java_loc,
            analysis.config_loc,
            analysis.test_loc,
            len(analysis.modules),
            len(analysis.api_endpoints),
        )

        logger.info(
            "[DISCOVERY SUCCESS] - JobID: %s - BuildTool: %s - Java: %s - SpringBoot: %s - TotalFiles: %d - Dependencies: %d",
            job_id,
            analysis.build_tool,
            analysis.current_java_version,
            analysis.spring_boot_version or "N/A",
            analysis.total_file_count,
            analysis.dependency_count,
        )

        from app.infrastructure.analyzers.frontend_compatibility_analyzer import (
            FrontendCompatibilityAnalyzer,
        )
        framework_recommendations = FrontendCompatibilityAnalyzer().analyze(
            paths.original_repo_dir, analysis
        ).to_dict()

        created_at = datetime.now(timezone.utc).isoformat()

        # 4. Save discovery-report.json.
        report = self._build_report(
            job_id,
            repo_url,
            owner,
            repo_name,
            analysis,
            eligibility,
            created_at,
            framework_recommendations=framework_recommendations,
        )
        self._job_repository.save_discovery_report(job_id, report)

        # 4b. Index the report into the Strategy chatbot's vector store so the
        # first chat question is fast. Best-effort: an indexing failure (e.g.
        # embedding model not yet downloaded) must never break Discovery.
        self._index_for_chatbot(job_id, report)

        # 5. Build the clean summary response.
        response = self._build_response(
            job_id,
            repo_url,
            owner,
            repo_name,
            visibility,
            analysis,
            eligibility,
            framework_recommendations=framework_recommendations,
        )
        return DiscoveryOutcome(response=response, report=report)

    # -- chatbot indexing (best-effort) -------------------------------------- #

    @staticmethod
    def _index_for_chatbot(job_id: str, report: dict[str, Any]) -> None:
        """Index the discovery report for the Strategy chatbot; never raises."""
        if not settings.rag_enabled:
            return
        try:
            logger.debug("[DISCOVERY RAG] - JobID: %s - Indexing report into vector store...", job_id)
            from app.application.use_cases.index_repository import IndexRepositoryUseCase

            IndexRepositoryUseCase().index_report(report)
        except Exception:  # noqa: BLE001 - indexing is best-effort
            logger.warning(
                "[DISCOVERY RAG SKIPPED] - JobID: %s - Vector indexing skipped (non-fatal).", job_id, exc_info=True
            )

    # -- builders ------------------------------------------------------------ #

    @staticmethod
    def _build_stages(analysis: ProjectAnalysis, eligibility: SpringBootEligibility) -> dict[str, Any]:
        module_text = (
            f" across {len(analysis.modules)} modules."
            if analysis.multi_module
            else " in single-module layout."
        )
        fw_text = f", {', '.join(analysis.frameworks[:3])}" if analysis.frameworks else ""
        test_text = "automated tests present" if analysis.has_tests else "no automated tests"
        api_text = f", {len(analysis.api_endpoints)} endpoints" if analysis.api_endpoints else ""

        arch_type = (
            "Microservices"
            if (analysis.multi_module and len(analysis.modules) > 1)
            else "Modular Monolith"
        )
        if eligibility.spring_boot_conversion_eligible:
            fit_text = "Eligible for automated Spring Boot conversion & modern Java baseline."
        elif eligibility.spring_boot_upgrade_eligible:
            fit_text = f"Spring Boot {analysis.spring_boot_version or ''} eligible for Spring Boot 3 & Java 17+ upgrade."
        else:
            fit_text = "Ready for direct Java platform and dependency modernization."

        return {
            "repositoryMap": {
                "status": "COMPLETE",
                "totalFileCount": analysis.total_file_count,
                "javaFileCount": len(analysis.java_files),
                "configFileCount": len(analysis.config_files),
                "otherFileCount": len(analysis.other_files),
                "multiModule": analysis.multi_module,
                "modules": analysis.modules,
                "hasSrcMain": analysis.has_src_main,
                "hasSrcTest": analysis.has_src_test,
                "hasPomXml": analysis.has_pom_xml,
                "hasBuildGradle": analysis.has_build_gradle or analysis.has_build_gradle_kts,
                "summary": f"Mapped {analysis.total_file_count} files ({len(analysis.java_files)} Java, {len(analysis.config_files)} Config, {len(analysis.other_files)} Other){module_text}",
            },
            "dependencyGraph": {
                "status": "COMPLETE",
                "buildTool": analysis.build_tool,
                "dependencyCount": analysis.dependency_count,
                "buildPluginsCount": len(analysis.build_plugins),
                "bomsCount": len(analysis.bom_versions),
                "summary": f"Extracted {analysis.dependency_count} dependencies and {len(analysis.build_plugins)} build plugins from {analysis.build_tool.lower()} configuration.",
            },
            "previewSignals": {
                "status": "COMPLETE",
                "currentJavaVersion": analysis.current_java_version,
                "buildTool": analysis.build_tool,
                "frameworks": analysis.frameworks,
                "springBootVersion": analysis.spring_boot_version,
                "springFrameworkVersion": analysis.spring_framework_version,
                "hasTests": analysis.has_tests,
                "apiEndpointCount": len(analysis.api_endpoints),
                "frontendDetected": analysis.frontend.detected,
                "summary": f"Identified Java {analysis.current_java_version}, {analysis.build_tool}{fw_text}, {test_text}{api_text}.",
            },
            "serviceFit": {
                "status": "COMPLETE",
                "recommendedArchitecture": arch_type,
                "springBootConversionEligible": eligibility.spring_boot_conversion_eligible,
                "springBootUpgradeEligible": eligibility.spring_boot_upgrade_eligible,
                "summary": f"{arch_type} architecture. {fit_text}",
            },
        }

    @staticmethod
    def _build_report(
        job_id: str,
        repo_url: str,
        owner: str,
        repo_name: str,
        analysis: ProjectAnalysis,
        eligibility: SpringBootEligibility,
        created_at: str,
        framework_recommendations: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "jobId": job_id,
            "status": STATUS_COMPLETED,
            "repoUrl": repo_url,
            "owner": owner,
            "repoName": repo_name,
            "discoveryStages": RunDiscoveryUseCase._build_stages(analysis, eligibility),
            "buildTool": analysis.build_tool,
            "currentJavaVersion": analysis.current_java_version,
            "springBootVersion": analysis.spring_boot_version,
            "projectType": analysis.project_type,
            "multiModule": analysis.multi_module,
            "modules": analysis.modules,
            "dependencies": [dep.to_dict() for dep in analysis.dependencies],
            "buildPlugins": [plugin.to_dict() for plugin in analysis.build_plugins],
            "bomVersions": [bom.to_dict() for bom in analysis.bom_versions],
            "frameworks": analysis.frameworks,
            "dependencyCount": analysis.dependency_count,
            "hasTests": analysis.has_tests,
            "javaFileCount": len(analysis.java_files),
            "javaFiles": list(analysis.java_files)[:200],
            "apiEndpoints": analysis.api_endpoints,
            "configFileCount": len(analysis.config_files),
            "configFiles": list(analysis.config_files)[:100],
            "otherFileCount": len(analysis.other_files),
            "otherFiles": list(analysis.other_files)[:100],
            "jspFileCount": analysis.jsp_file_count,
            "jsfFileCount": analysis.jsf_file_count,
            "jspFiles": list(analysis.jsp_files),
            "jsfFiles": list(analysis.jsf_files),
            "viewTechnologies": analysis.view_technologies,
            "totalFileCount": analysis.total_file_count,
            "fileMetrics": analysis.file_metrics,
            "defaultBranch": "main",
            "buildWarning": analysis.build_warning,
            "sourceLayout": {
                "hasSrcMain": analysis.has_src_main,
                "hasSrcTest": analysis.has_src_test,
            },
            "springFrameworkVersion": analysis.spring_framework_version,
            "springEntryClass": analysis.spring_entry_class,
            "javaMigrationEligible": eligibility.java_migration_eligible,
            "javaMigrationReason": eligibility.java_migration_reason,
            "springDetected": eligibility.spring_detected,
            "springBootDetected": eligibility.spring_boot_detected,
            "springBootConversionEligible": eligibility.spring_boot_conversion_eligible,
            "springBootUpgradeEligible": eligibility.spring_boot_upgrade_eligible,
            "eligibilityReason": eligibility.eligibility_reason,
            "frontend": analysis.frontend.to_dict(),
            "detectedFiles": {
                "pomXml": analysis.has_pom_xml,
                "buildGradle": analysis.has_build_gradle or analysis.has_build_gradle_kts,
                "buildGradleKts": analysis.has_build_gradle_kts,
                "packageJson": analysis.has_package_json,
            },
            "springBootConversion": eligibility.to_dict(),
            "frameworkRecommendations": framework_recommendations,
            "createdAt": created_at,
        }

    @classmethod
    def _reconstruct_response_from_report(
        cls,
        job_id: str,
        repo_url: str,
        owner: str,
        repo_name: str,
        visibility: str,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        frontend_info = report.get("frontend") or {}
        frontend_detected = bool(frontend_info.get("detected", False))
        frontend_type = frontend_info.get("type") if frontend_detected else None

        detected_files = report.get("detectedFiles") or {}
        source_layout = report.get("sourceLayout") or {
            "hasSrcMain": bool(detected_files.get("pomXml") or detected_files.get("buildGradle")),
            "hasSrcTest": bool(report.get("hasTests", False)),
        }

        paths = WorkspacePaths(job_id)
        java_files = report.get("javaFiles")
        if java_files is None:
            java_files = report.get("java_files")
        config_files = report.get("configFiles")
        if config_files is None:
            config_files = report.get("config_files")
        other_files = report.get("otherFiles")
        if other_files is None:
            other_files = report.get("other_files")
        jsp_files = report.get("jspFiles")
        if jsp_files is None:
            jsp_files = report.get("jsp_files")
        jsf_files = report.get("jsfFiles")
        if jsf_files is None:
            jsf_files = report.get("jsf_files")

        if (
            java_files is None
            or jsp_files is None
            or jsf_files is None
            or config_files is None
            or other_files is None
        ) and paths.original_repo_dir.is_dir():
            all_files = file_utils.find_files(paths.original_repo_dir, "", limit=None)
            if java_files is None:
                java_files = [f for f in all_files if f.lower().endswith(".java")][:200]
            if jsp_files is None:
                jsp_files = [f for f in all_files if f.lower().endswith((".jsp", ".jspf", ".jspx"))]
            if jsf_files is None:
                jsf_files = [f for f in all_files if f.lower().endswith((".xhtml", ".jsf"))]
            if config_files is None:
                config_exts = (".xml", ".yml", ".yaml", ".properties", ".gradle", ".gradle.kts", ".json", ".conf", ".config", ".toml")
                config_files = [f for f in all_files if f not in (java_files or []) and f not in (jsp_files or []) and f not in (jsf_files or []) and any(f.lower().endswith(ext) for ext in config_exts)][:100]
            if other_files is None:
                other_files = [f for f in all_files if f not in (java_files or []) and f not in (config_files or []) and f not in (jsp_files or []) and f not in (jsf_files or [])][:100]

        java_files = java_files or []
        jsp_files = jsp_files or []
        jsf_files = jsf_files or []
        config_files = config_files or []
        other_files = other_files or []

        if other_files:
            jsp_jsf_exts = (".jsp", ".jspf", ".jspx", ".xhtml", ".jsf")
            other_files = [f for f in other_files if not f.lower().endswith(jsp_jsf_exts)]

        framework_recommendations = report.get("frameworkRecommendations")
        if not framework_recommendations and paths.original_repo_dir.is_dir():
            try:
                from app.infrastructure.analyzers.frontend_compatibility_analyzer import (
                    FrontendCompatibilityAnalyzer,
                )
                framework_recommendations = FrontendCompatibilityAnalyzer().analyze(
                    paths.original_repo_dir
                ).to_dict()
            except Exception:
                pass

        view_technologies = report.get("viewTechnologies")
        if not view_technologies and paths.original_repo_dir.is_dir():
            try:
                from app.infrastructure.analyzers.view_technology_analyzer import ViewTechnologyAnalyzer
                view_technologies = ViewTechnologyAnalyzer().analyze(
                    root=paths.original_repo_dir,
                    jsp_files=jsp_files,
                    jsf_files=jsf_files,
                    java_files=java_files,
                    dependencies=report.get("dependencies", []),
                ).to_dict()
            except Exception:
                pass

        return {
            "jobId": job_id,
            "status": STATUS_COMPLETED,
            "message": "Repository discovery completed successfully.",
            "repository": {
                "repoUrl": repo_url,
                "owner": owner,
                "repoName": repo_name,
                "visibility": visibility,
            },
            "project": {
                "buildTool": report.get("buildTool"),
                "currentJavaVersion": report.get("currentJavaVersion"),
                "springBootVersion": report.get("springBootVersion"),
                "projectType": report.get("projectType", "STANDARD_JAVA"),
                "multiModule": bool(report.get("multiModule", False)),
                "modules": report.get("modules", []),
                "dependenciesCount": report.get("dependencyCount", len(report.get("dependencies", []))),
                "frontendDetected": frontend_detected,
                "frontendType": frontend_type,
                "dependencies": report.get("dependencies", []),
                "buildPlugins": report.get("buildPlugins", []),
                "bomVersions": report.get("bomVersions", []),
                "frameworks": report.get("frameworks", []),
                "apiEndpoints": report.get("apiEndpoints", []),
                "hasTests": bool(report.get("hasTests", False)),
                "javaFileCount": report.get("javaFileCount") if report.get("javaFileCount") is not None else len(java_files),
                "javaFiles": java_files,
                "configFileCount": report.get("configFileCount") if report.get("configFileCount") is not None else len(config_files),
                "configFiles": config_files,
                "otherFileCount": len(other_files) if other_files is not None else report.get("otherFileCount"),
                "otherFiles": other_files,
                "jspFileCount": report.get("jspFileCount") if report.get("jspFileCount") is not None else len(jsp_files),
                "jsfFileCount": report.get("jsfFileCount") if report.get("jsfFileCount") is not None else len(jsf_files),
                "jspFiles": jsp_files,
                "jsfFiles": jsf_files,
                "totalFileCount": report.get("totalFileCount") or (len(java_files) + len(config_files) + len(jsp_files) + len(jsf_files) + len(other_files or [])),
                "fileMetrics": report.get("fileMetrics"),
                "defaultBranch": report.get("defaultBranch", "main"),
                "buildWarning": report.get("buildWarning"),
                "frontend": frontend_info,
                "frameworkRecommendations": framework_recommendations,
                "viewTechnologies": view_technologies or {},
                "detectedFiles": {
                    "pomXml": bool(detected_files.get("pomXml", False)),
                    "buildGradle": bool(detected_files.get("buildGradle", False)),
                    "buildGradleKts": bool(detected_files.get("buildGradleKts", False)),
                    "packageJson": bool(detected_files.get("packageJson", False)),
                },
                "sourceLayout": source_layout,
                "springFrameworkVersion": report.get("springFrameworkVersion"),
                "springEntryClass": report.get("springEntryClass"),
                "javaMigrationEligible": report.get("javaMigrationEligible", True),
                "javaMigrationReason": report.get("javaMigrationReason", ""),
                "springDetected": bool(report.get("springDetected", False)),
                "springBootDetected": bool(report.get("springBootDetected", False)),
                "springBootConversionEligible": bool(report.get("springBootConversionEligible", False)),
                "springBootUpgradeEligible": bool(report.get("springBootUpgradeEligible", False)),
                "eligibilityReason": report.get("eligibilityReason", ""),
                "springBootConversion": report.get("springBootConversion") or {
                    "repositoryAnalyzed": True,
                    "javaMigrationEligible": bool(report.get("javaMigrationEligible", True)),
                    "javaMigrationReason": report.get("javaMigrationReason", ""),
                    "springDetected": bool(report.get("springDetected", False)),
                    "springBootDetected": bool(report.get("springBootDetected", False)),
                    "springVersion": report.get("springFrameworkVersion"),
                    "springBootVersion": report.get("springBootVersion"),
                    "buildTool": report.get("buildTool"),
                    "springBootConversionEligible": bool(report.get("springBootConversionEligible", False)),
                    "springBootUpgradeEligible": bool(report.get("springBootUpgradeEligible", False)),
                    "eligibilityReason": report.get("eligibilityReason", ""),
                },
            },
            "nextStep": NEXT_STEP,
        }

    @staticmethod
    def _build_response(
        job_id: str,
        repo_url: str,
        owner: str,
        repo_name: str,
        visibility: str,
        analysis: ProjectAnalysis,
        eligibility: SpringBootEligibility,
        framework_recommendations: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "jobId": job_id,
            "status": STATUS_COMPLETED,
            "message": "Repository discovery completed successfully.",
            "repository": {
                "repoUrl": repo_url,
                "owner": owner,
                "repoName": repo_name,
                "visibility": visibility,
            },
            "project": {
                "buildTool": analysis.build_tool,
                "currentJavaVersion": analysis.current_java_version,
                "springBootVersion": analysis.spring_boot_version,
                "projectType": analysis.project_type,
                "multiModule": analysis.multi_module,
                "modules": analysis.modules,
                "dependenciesCount": analysis.dependency_count,
                "frontendDetected": analysis.frontend.detected,
                "frontendType": analysis.frontend.type if analysis.frontend.detected else None,
                # --- extra fields consumed by the existing frontend UI ---
                "dependencies": [dep.to_dict() for dep in analysis.dependencies],
                "buildPlugins": [plugin.to_dict() for plugin in analysis.build_plugins],
                "bomVersions": [bom.to_dict() for bom in analysis.bom_versions],
                "frameworks": analysis.frameworks,
                "apiEndpoints": analysis.api_endpoints,
                "hasTests": analysis.has_tests,
                "javaFileCount": len(analysis.java_files),
                "javaFiles": list(analysis.java_files)[:200],
                "configFileCount": len(analysis.config_files),
                "configFiles": list(analysis.config_files)[:100],
                "otherFileCount": len(analysis.other_files),
                "otherFiles": list(analysis.other_files)[:100],
                "jspFileCount": analysis.jsp_file_count,
                "jsfFileCount": analysis.jsf_file_count,
                "jspFiles": list(analysis.jsp_files),
                "jsfFiles": list(analysis.jsf_files),
                "totalFileCount": analysis.total_file_count,
                "fileMetrics": analysis.file_metrics,
                "defaultBranch": "main",
                "buildWarning": analysis.build_warning,
                "frontend": analysis.frontend.to_dict(),
                "frameworkRecommendations": framework_recommendations,
                "viewTechnologies": analysis.view_technologies,
                "detectedFiles": {
                    "pomXml": analysis.has_pom_xml,
                    "buildGradle": analysis.has_build_gradle,
                    "buildGradleKts": analysis.has_build_gradle_kts,
                    "packageJson": analysis.has_package_json,
                },
                "sourceLayout": {
                    "hasSrcMain": analysis.has_src_main,
                    "hasSrcTest": analysis.has_src_test,
                },
                "springFrameworkVersion": analysis.spring_framework_version,
                "springEntryClass": analysis.spring_entry_class,
                "javaMigrationEligible": eligibility.java_migration_eligible,
                "javaMigrationReason": eligibility.java_migration_reason,
                "springDetected": eligibility.spring_detected,
                "springBootDetected": eligibility.spring_boot_detected,
                "springBootConversionEligible": eligibility.spring_boot_conversion_eligible,
                "springBootUpgradeEligible": eligibility.spring_boot_upgrade_eligible,
                "eligibilityReason": eligibility.eligibility_reason,
                "springBootConversion": eligibility.to_dict(),
            },
            "nextStep": NEXT_STEP,
        }
