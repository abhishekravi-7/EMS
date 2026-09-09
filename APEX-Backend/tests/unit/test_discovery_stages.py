"""Unit tests for Discovery 4-stage pipeline and data grounding."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from app.application.use_cases.run_discovery import RunDiscoveryUseCase, STATUS_COMPLETED
from app.infrastructure.analyzers.project_analyzer import ProjectAnalysis
from app.infrastructure.analyzers.dependency_analyzer import Dependency
from app.infrastructure.analyzers.frontend_detector import FrontendResult
from app.infrastructure.analyzers.spring_boot_eligibility import SpringBootEligibility


def test_build_stages_grounds_in_real_project_data():
    deps = [
        Dependency(group_id="org.springframework.boot", artifact_id="spring-boot-starter-web", version="2.7.0"),
        Dependency(group_id="org.junit.jupiter", artifact_id="junit-jupiter", version="5.8.2"),
    ]
    analysis = ProjectAnalysis(
        build_tool="MAVEN",
        primary_build_tool="MAVEN",
        build_warning=None,
        current_java_version="11",
        spring_boot_version="2.7.0",
        spring_framework_version="5.3.20",
        spring_boot_signal=True,
        spring_entry_class="com.example.DemoApplication",
        project_type="SPRING_BOOT",
        multi_module=False,
        modules=[],
        dependencies=deps,
        build_plugins=[],
        bom_versions=[],
        frameworks=["Spring Boot", "JUnit 5"],
        frontend=FrontendResult(detected=False, type="none", path=None, package_manager=None),
        has_pom_xml=True,
        has_build_gradle=False,
        has_build_gradle_kts=False,
        has_package_json=False,
        has_src_main=True,
        has_src_test=True,
        has_tests=True, project_root=Path("."), api_endpoints=[],
        java_files=["src/main/java/com/example/DemoApplication.java"],
        config_files=["pom.xml", "src/main/resources/application.properties"],
        other_files=["README.md"],
        total_file_count=4,
    )

    eligibility = SpringBootEligibility(
        repository_analyzed=True,
        java_migration_eligible=True,
        java_migration_reason="Valid Java project",
        spring_detected=True,
        spring_boot_detected=True,
        spring_version="5.3.20",
        spring_boot_version="2.7.0",
        build_tool="MAVEN",
        spring_boot_conversion_eligible=False,
        spring_boot_upgrade_eligible=True,
        eligibility_reason="Spring Boot 2.7.0 detected - eligible for upgrade to Spring Boot 3.",
    )

    stages = RunDiscoveryUseCase._build_stages(analysis, eligibility)

    # 1. Repository Map
    assert stages["repositoryMap"]["status"] == "COMPLETE"
    assert stages["repositoryMap"]["totalFileCount"] == 4
    assert stages["repositoryMap"]["javaFileCount"] == 1
    assert stages["repositoryMap"]["configFileCount"] == 2
    assert stages["repositoryMap"]["otherFileCount"] == 1
    assert "Mapped 4 files" in stages["repositoryMap"]["summary"]

    # 2. Dependency Graph
    assert stages["dependencyGraph"]["status"] == "COMPLETE"
    assert stages["dependencyGraph"]["dependencyCount"] == 2
    assert stages["dependencyGraph"]["buildTool"] == "MAVEN"
    assert "Extracted 2 dependencies" in stages["dependencyGraph"]["summary"]

    # 3. Preview Signals
    assert stages["previewSignals"]["status"] == "COMPLETE"
    assert stages["previewSignals"]["currentJavaVersion"] == "11"
    assert stages["previewSignals"]["hasTests"] is True
    assert "Java 11" in stages["previewSignals"]["summary"]

    # 4. Service Fit
    assert stages["serviceFit"]["status"] == "COMPLETE"
    assert stages["serviceFit"]["springBootUpgradeEligible"] is True
    assert "Modular Monolith" in stages["serviceFit"]["recommendedArchitecture"]
    assert "eligible for Spring Boot 3" in stages["serviceFit"]["summary"]


def test_force_refresh_reruns_fresh_analysis(tmp_path):
    job_repo = MagicMock()
    job_repo.read_connect_report.return_value = {
        "repoUrl": "https://github.com/example/demo-repo",
        "owner": "example",
        "repoName": "demo-repo",
        "repoVisibility": "PUBLIC",
    }
    # Existing cached report from previous run
    job_repo.read_discovery_report.return_value = {
        "status": STATUS_COMPLETED,
        "createdAt": "2026-01-01T00:00:00Z",
        "project": {
            "buildTool": "MAVEN",
            "currentJavaVersion": "8",
            "dependenciesCount": 5,
        },
    }

    cloner = MagicMock()
    analyzer = MagicMock()
    analyzer.analyze.return_value = ProjectAnalysis(
        build_tool="MAVEN",
        primary_build_tool="MAVEN",
        build_warning=None,
        current_java_version="17",
        spring_boot_version="3.1.0",
        spring_framework_version="6.0.0",
        spring_boot_signal=True,
        spring_entry_class="com.example.App",
        project_type="SPRING_BOOT",
        multi_module=False,
        modules=[],
        dependencies=[Dependency(group_id="org.springframework.boot", artifact_id="spring-boot-starter", version="3.1.0")],
        build_plugins=[],
        bom_versions=[],
        frameworks=["Spring Boot"],
        frontend=FrontendResult(detected=False, type="none", path=None, package_manager=None),
        has_pom_xml=True,
        has_build_gradle=False,
        has_build_gradle_kts=False,
        has_package_json=False,
        has_src_main=True,
        has_src_test=True,
        has_tests=True, project_root=Path("."), api_endpoints=[],
        java_files=["src/main/java/com/example/App.java"],
        config_files=["pom.xml"],
        other_files=[],
        total_file_count=2,
    )

    use_case = RunDiscoveryUseCase(job_repository=job_repo, cloner=cloner, analyzer=analyzer)

    # When force_refresh is True, it must NOT return the stale cached report (Java 8), but fresh analysis (Java 17)
    outcome = use_case.execute(job_id="test-job-123", force_refresh=True)

    assert outcome.response["status"] == STATUS_COMPLETED
    assert outcome.response["project"]["currentJavaVersion"] == "17"
    assert outcome.response["project"]["discoveryStages"]["repositoryMap"]["status"] == "COMPLETE"
    assert outcome.response["project"]["discoveryStages"]["serviceFit"]["status"] == "COMPLETE"
    assert job_repo.save_discovery_report.called
