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
from app.infrastructure.analyzers.spring_boot_eligibility import (
    SpringBootEligibility,
    compute_eligibility,
)
from app.infrastructure.git.repository_cloner import RepositoryCloner
from app.infrastructure.persistence.job_repository import JobRepository
from app.infrastructure.workspace.workspace_manager import WorkspaceManager
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.shared import file_utils

logger = logging.getLogger(__name__)

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
    ) -> None:
        self._job_repository = job_repository or JobRepository()
        self._cloner = cloner or RepositoryCloner()
        self._analyzer = analyzer or ProjectAnalyzer()

    def execute(self, job_id: str, request_token: str | None = None) -> DiscoveryOutcome:
        # 1. Connect report must exist.
        connect = self._job_repository.read_connect_report(job_id)
        if not connect:
            raise ConnectReportNotFoundError()

        repo_url = connect.get("repoUrl", "")
        owner = connect.get("owner", "")
        repo_name = connect.get("repoName", "")
        visibility = connect.get("repoVisibility", "PUBLIC")

        paths = WorkspacePaths(job_id)

        # Check if discovery was already completed and the cloned workspace is intact
        existing_report = self._job_repository.read_discovery_report(job_id)
        if (
            existing_report
            and existing_report.get("status") == STATUS_COMPLETED
            and paths.original_repo_dir.is_dir()
        ):
            logger.info("Reusing existing discovery report for job %s (%s)", job_id, repo_url)
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

        logger.info("Discovery started for job %s (%s)", job_id, repo_url)

        # 2. Prepare workspace + clone into original-repo.
        workspace = WorkspaceManager(paths)
        workspace.ensure_job_dirs()
        workspace.prepare_original_repo_target()

        logger.info("Cloning repository into workspace for job %s ...", job_id)
        self._cloner.clone(
            repo_url,
            paths.original_repo_dir,
            token=token,
            log_path=paths.discovery_log_path,
        )
        logger.info("Clone finished for job %s. Analyzing project ...", job_id)

        # 3. Analyze the cloned project (read-only).
        analysis = self._analyzer.analyze(paths.original_repo_dir)
        if not analysis.is_supported:
            logger.info("Discovery for job %s: unsupported project (no Maven/Gradle).", job_id)
            raise UnsupportedProjectError()

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
            "Discovery completed for job %s: buildTool=%s javaVersion=%s springBoot=%s "
            "type=%s multiModule=%s dependencies=%d frontend=%s "
            "springDetected=%s springBootDetected=%s conversionEligible=%s upgradeEligible=%s",
            job_id,
            analysis.build_tool,
            analysis.current_java_version,
            analysis.spring_boot_version,
            analysis.project_type,
            analysis.multi_module,
            analysis.dependency_count,
            analysis.frontend.type if analysis.frontend.detected else "none",
            eligibility.spring_detected,
            eligibility.spring_boot_detected,
            eligibility.spring_boot_conversion_eligible,
            eligibility.spring_boot_upgrade_eligible,
        )

        created_at = datetime.now(timezone.utc).isoformat()

        # 4. Save discovery-report.json.
        report = self._build_report(
            job_id, repo_url, owner, repo_name, analysis, eligibility, created_at
        )
        self._job_repository.save_discovery_report(job_id, report)

        # 4b. Index the report into the Strategy chatbot's vector store so the
        # first chat question is fast. Best-effort: an indexing failure (e.g.
        # embedding model not yet downloaded) must never break Discovery.
        self._index_for_chatbot(job_id, report)

        # 5. Build the clean summary response.
        response = self._build_response(
            job_id, repo_url, owner, repo_name, visibility, analysis, eligibility
        )
        return DiscoveryOutcome(response=response, report=report)

    # -- chatbot indexing (best-effort) -------------------------------------- #

    @staticmethod
    def _index_for_chatbot(job_id: str, report: dict[str, Any]) -> None:
        """Index the discovery report for the Strategy chatbot; never raises."""
        if not settings.rag_enabled:
            return
        try:
            # Imported lazily so Discovery has no hard dependency on the RAG
            # stack (embeddings/vector store) being installed or importable.
            from app.application.use_cases.index_repository import IndexRepositoryUseCase

            IndexRepositoryUseCase().index_report(report)
        except Exception:  # noqa: BLE001 - indexing is best-effort
            logger.warning(
                "Chatbot indexing skipped for job %s (non-fatal).", job_id, exc_info=True
            )

    # -- builders ------------------------------------------------------------ #

    @staticmethod
    def _build_report(
        job_id: str,
        repo_url: str,
        owner: str,
        repo_name: str,
        analysis: ProjectAnalysis,
        eligibility: SpringBootEligibility,
        created_at: str,
    ) -> dict[str, Any]:
        return {
            "jobId": job_id,
            "status": STATUS_COMPLETED,
            "repoUrl": repo_url,
            "owner": owner,
            "repoName": repo_name,
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
            "configFileCount": len(analysis.config_files),
            "configFiles": list(analysis.config_files)[:100],
            "otherFileCount": len(analysis.other_files),
            "otherFiles": list(analysis.other_files)[:100],
            "totalFileCount": analysis.total_file_count,
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
        java_files = report.get("javaFiles") or []
        config_files = report.get("configFiles")
        other_files = report.get("otherFiles")

        if (not java_files or config_files is None or other_files is None) and paths.original_repo_dir.is_dir():
            all_files = file_utils.find_files(paths.original_repo_dir, "")
            if not java_files:
                java_files = [f for f in all_files if f.lower().endswith(".java")][:200]
            if config_files is None:
                config_exts = (".xml", ".yml", ".yaml", ".properties", ".gradle", ".gradle.kts", ".json", ".conf", ".config", ".toml")
                config_files = [f for f in all_files if any(f.lower().endswith(ext) for ext in config_exts)][:100]
            if other_files is None:
                other_files = [f for f in all_files if f not in (java_files or []) and f not in (config_files or [])][:100]

        config_files = config_files or []
        other_files = other_files or []

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
                "hasTests": bool(report.get("hasTests", False)),
                "javaFileCount": report.get("javaFileCount") or len(java_files),
                "javaFiles": java_files,
                "configFileCount": report.get("configFileCount") or len(config_files),
                "configFiles": config_files,
                "otherFileCount": report.get("otherFileCount") or len(other_files),
                "otherFiles": other_files,
                "totalFileCount": report.get("totalFileCount") or (len(java_files) + len(config_files) + len(other_files)),
                "defaultBranch": report.get("defaultBranch", "main"),
                "buildWarning": report.get("buildWarning"),
                "frontend": frontend_info,
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
                "springBootConversion": spring_boot_conv,
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
                "hasTests": analysis.has_tests,
                "javaFileCount": len(analysis.java_files),
                "javaFiles": list(analysis.java_files)[:200],
                "configFileCount": len(analysis.config_files),
                "configFiles": list(analysis.config_files)[:100],
                "otherFileCount": len(analysis.other_files),
                "otherFiles": list(analysis.other_files)[:100],
                "totalFileCount": analysis.total_file_count,
                "defaultBranch": "main",
                "buildWarning": analysis.build_warning,
                "frontend": analysis.frontend.to_dict(),
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
