from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class RepositoryComposition(BaseModel):
    total_files: int = Field(..., alias="totalFiles")
    java_files: int = Field(..., alias="javaFiles")
    xml_config_files: int = Field(..., alias="xmlConfigFiles")
    other_files: int = Field(..., alias="otherFiles")

    model_config = {"populate_by_name": True}

class ModernizationAnalysis(BaseModel):
    source_java_version: str = Field(..., alias="sourceJavaVersion")
    java_version_feature_count: int = Field(..., alias="javaVersionFeatureCount")
    deprecated_api_count: Optional[int] = Field(None, alias="deprecatedApiCount")
    javax_migration_count: Optional[int] = Field(None, alias="javaxMigrationCount")
    old_spring_usage_count: Optional[int] = Field(None, alias="oldSpringUsageCount")
    security_vulnerability_count: Optional[int] = Field(None, alias="securityVulnerabilityCount")
    code_smell_count: Optional[int] = Field(None, alias="codeSmellCount")
    legacy_api_count: Optional[int] = Field(None, alias="legacyApiCount")
    migration_blocker_count: Optional[int] = Field(None, alias="migrationBlockerCount")

    model_config = {"populate_by_name": True}

class MigrationSummary(BaseModel):
    status: str
    total_items: int = Field(..., alias="totalItems")
    auto_migratable: int = Field(..., alias="autoMigratable")
    manual_changes: int = Field(..., alias="manualChanges")
    needs_review: int = Field(..., alias="needsReview")
    compilation_errors: int = Field(..., alias="compilationErrors")
    completed: int = Field(..., alias="completed")

    model_config = {"populate_by_name": True}

class DashboardStatsResponse(BaseModel):
    repository_id: str = Field(..., alias="repositoryId")
    job_id: str = Field(..., alias="jobId")
    repository_name: str = Field(..., alias="repositoryName")
    repository_composition: RepositoryComposition = Field(..., alias="repositoryComposition")
    modernization_analysis: ModernizationAnalysis = Field(..., alias="modernizationAnalysis")
    migration_summary: MigrationSummary = Field(..., alias="migrationSummary")
    generated_at: datetime = Field(..., alias="generatedAt")

    model_config = {"populate_by_name": True}
