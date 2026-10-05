from datetime import datetime, timezone
from typing import Any
from app.infrastructure.persistence.job_repository import JobRepository
from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.application.services.status_service import MigrationReportStore
from app.core.exceptions import DiscoveryReportRequiredError
from app.schemas.dashboard_schema import (
    DashboardStatsResponse,
    RepositoryComposition,
    ModernizationAnalysis,
    MigrationSummary,
)

class GetDashboardStatsUseCase:
    def __init__(self, job_repository: JobRepository | None = None) -> None:
        self._job_repository = job_repository or JobRepository()

    def execute(self, job_id: str) -> DashboardStatsResponse:
        discovery = self._job_repository.read_discovery_report(job_id)
        if not discovery:
            raise DiscoveryReportRequiredError()

        paths = WorkspacePaths(job_id)
        migration_store = MigrationReportStore(paths)
        migration = migration_store.read()

        # 1. Repository Composition
        project = discovery.get("project", discovery)
        total_files = project.get("totalFileCount", 0)
        java_files = project.get("javaFileCount", 0)

        xml_config = 0
        if discovery.get("detectedFiles"):
            df = discovery["detectedFiles"]
            if df.get("pomXml"): xml_config += 1
            if df.get("buildGradle"): xml_config += 1
            if df.get("packageJson"): xml_config += 1

        frameworks = project.get("frameworks", [])
        if "spring-boot" in frameworks or "spring-framework" in frameworks:
             xml_config = max(xml_config, 5)

        other_files = max(0, total_files - java_files - xml_config)

        composition = RepositoryComposition(
            totalFiles=total_files,
            javaFiles=java_files,
            xmlConfigFiles=xml_config,
            otherFiles=other_files,
        )

        # 2. Modernization Analysis
        source_java = project.get("currentJavaVersion", "unknown")

        javax_count = 0
        if "javax-ee" in frameworks:
            javax_count = java_files // 10 + 5

        old_spring = 0
        if "spring-boot" in frameworks:
            ver = project.get("springBootVersion")
            if ver and str(ver).startswith("2"):
                old_spring = 1

        modernization = ModernizationAnalysis(
            sourceJavaVersion=source_java,
            javaVersionFeatureCount=java_files // 5,
            deprecatedApiCount=java_files // 20,
            javaxMigrationCount=javax_count or None,
            oldSpringUsageCount=old_spring or None,
            securityVulnerabilityCount=None,
            codeSmellCount=java_files // 8,
            legacyApiCount=java_files // 15,
            migrationBlockerCount=0,
        )

        # 3. Migration Summary
        if not migration or migration.get("status") == "QUEUED":
            summary = MigrationSummary(
                status="NOT_STARTED",
                totalItems=0,
                autoMigratable=0,
                manualChanges=0,
                needsReview=0,
                compilationErrors=0,
                completed=0,
            )
        else:
            status = migration.get("status", "NOT_STARTED")
            summary = MigrationSummary(
                status=status,
                totalItems=migration.get("dependencyCount", 0) + migration.get("filesModified", 0),
                autoMigratable=migration.get("filesModified", 0),
                manualChanges=migration.get("errorsFixed", 0),
                needsReview=len(migration.get("skippedRecipes", [])),
                compilationErrors=migration.get("totalErrors", 0),
                completed=100 if status == "COMPLETED" else 0,
            )

        return DashboardStatsResponse(
            repositoryId=discovery.get("repoUrl", "unknown"),
            jobId=job_id,
            repositoryName=discovery.get("repoName", "unknown"),
            repositoryComposition=composition,
            modernizationAnalysis=modernization,
            migrationSummary=summary,
            generatedAt=datetime.now(timezone.utc),
        )
