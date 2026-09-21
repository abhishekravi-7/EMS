from __future__ import annotations

import pytest
from app.application.services import report_service


def test_build_result_derives_actual_migration_findings():
    mock_report = {
        "jobId": "test-job-report-1",
        "status": "COMPLETED",
        "sourceRepoUrl": "https://github.com/example/sample-repo",
        "sourceJavaVersion": "8",
        "targetJavaVersion": "17",
        "effectiveTargetJavaVersion": "17",
        "destination": {
            "mode": "CREATE_NEW_REPO",
            "targetRepoName": "sample-repo-Migrated",
            "targetOwner": "JavaAPEX",
            "targetHost": "github.com",
        },
        "startedAt": "2026-09-08T10:00:00Z",
        "completedAt": "2026-09-08T10:02:30Z",
        "progressPercent": 100,
        "filesModified": 3,
        "modifiedFiles": ["pom.xml", "src/main/java/App.java", "src/test/java/AppTest.java"],
        "importChanges": [
            {
                "file": "src/main/java/App.java",
                "added": ["jakarta.persistence.Entity"],
                "removed": ["javax.persistence.Entity"],
            }
        ],
        "ruleExecutions": [
            {
                "ruleId": "JUNIT4_TO_JUNIT5",
                "category": "Test Modernization",
                "message": "Updated JUnit 4 assertions to JUnit 5 Jupiter",
                "filePath": "src/test/java/AppTest.java",
                "lineNumber": 15,
            }
        ],
        "dependencyUpgrades": [
            {
                "groupId": "org.springframework.boot",
                "artifactId": "spring-boot-starter-web",
                "sourceVersion": "2.7.0",
                "resolvedTargetVersion": "3.2.0",
                "status": "UPGRADED",
            }
        ],
        "buildModernization": ["Updated Java source/target release version in pom.xml"],
    }

    result = report_service.build_result(mock_report)
    summary = report_service.build_summary(mock_report)

    # 1. Target Repo Resolution
    assert result["target_repo"] == "https://github.com/JavaAPEX/sample-repo-Migrated"
    assert summary["target_repo"] == "https://github.com/JavaAPEX/sample-repo-Migrated"

    # 2. Files Modified
    assert result["files_modified"] == 3
    assert summary["files_modified"] == 3

    # 3. Dynamic Issues Derivation & Count
    assert result["issues_fixed"] == 4
    assert summary["issues_fixed"] == 4
    assert len(result["issues"]) == 4

    categories = [i["category"] for i in result["issues"]]
    assert "Test Modernization" in categories
    assert "Namespace Migration" in categories
    assert "Dependency Modernization" in categories
    assert "Build Modernization" in categories

    # 4. Dependency Upgrades
    assert len(result["dependency_upgrades"]) == 1
    assert result["dependency_upgrades"][0]["artifactId"] == "spring-boot-starter-web"
    assert len(result["dependencies"]) == 1


def test_clean_repo_name():
    from app.infrastructure.github.repo_creator import RepoCreator

    assert RepoCreator.clean_repo_name("test-repository") == "test-repository"
    assert RepoCreator.clean_repo_name("test-repository.git") == "test-repository"
    assert RepoCreator.clean_repo_name("https://github.com/test-owner/test-repository") == "test-repository"
    assert RepoCreator.clean_repo_name("https://github.com/test-owner/test-repository.git") == "test-repository"
    assert RepoCreator.clean_repo_name("https://github.com/test-owner/test-repository-Migrated2026") == "test-repository-Migrated2026"
    assert RepoCreator.clean_repo_name("git@github.com:test-owner/test-repository.git") == "test-repository"
    assert RepoCreator.clean_repo_name("/path/to/my-custom-repo") == "my-custom-repo"
    assert RepoCreator.clean_repo_name("C:\\Projects\\my-custom-repo") == "my-custom-repo"
    assert RepoCreator.clean_repo_name("") == "repo"
    assert RepoCreator.clean_repo_name(None) == "repo"


def test_target_repo_resolution_cases():
    # 1. Authoritative targetRepo directly in report
    rep1 = {
        "jobId": "test-job-1",
        "targetRepo": "https://github.com/test-owner/test-app-Migrated2026",
    }
    assert report_service.build_result(rep1)["target_repo"] == "https://github.com/test-owner/test-app-Migrated2026"

    # 2. Authoritative target_repo (snake_case) with .git
    rep2 = {
        "jobId": "test-job-2",
        "target_repo": "https://github.com/test-owner/test-app-Migrated2026.git",
    }
    assert report_service.build_result(rep2)["target_repo"] == "https://github.com/test-owner/test-app-Migrated2026.git"

    # 3. Destination with full URL accidentally in targetRepoName (normalized cleanly)
    rep3 = {
        "jobId": "test-job-3",
        "sourceRepoUrl": "https://github.com/source-owner/source-app",
        "destination": {
            "mode": "CREATE_NEW_REPO",
            "targetOwner": "target-owner",
            "targetHost": "github.com",
            "targetRepoName": "https://github.com/target-owner/target-app-Migrated2026",
        },
    }
    assert report_service.build_result(rep3)["target_repo"] == "https://github.com/target-owner/target-app-Migrated2026"

    # 4. Destination with .git in targetRepoName
    rep4 = {
        "jobId": "test-job-4",
        "destination": {
            "mode": "CREATE_NEW_REPO",
            "targetOwner": "custom-owner-123",
            "targetHost": "github.com",
            "targetRepoName": "my-app-Migrated2026.git",
        },
    }
    assert report_service.build_result(rep4)["target_repo"] == "https://github.com/custom-owner-123/my-app-Migrated2026"

    # 5. Local folder destination
    rep5 = {
        "jobId": "test-job-5",
        "destination": {
            "mode": "LOCAL_FOLDER",
            "targetLocalDir": "C:/Projects/my-app-Migrated",
        },
    }
    assert report_service.build_result(rep5)["target_repo"] == "C:/Projects/my-app-Migrated"

    # 6. Existing repo branch destination
    rep6 = {
        "jobId": "test-job-6",
        "sourceRepoUrl": "https://github.com/source-owner/source-app.git",
        "destination": {
            "mode": "EXISTING_REPO_BRANCH",
            "targetBranch": "migration-v2",
        },
    }
    assert report_service.build_result(rep6)["target_repo"] == "https://github.com/source-owner/source-app/tree/migration-v2"

    # 7. Missing target URL / None destination
    rep7 = {
        "jobId": "test-job-7",
    }
    assert report_service.build_result(rep7)["target_repo"] is None


def test_github_create_repo_response_mapping():
    """Verify that authoritative GitHub API create response is used directly."""
    from app.infrastructure.github.profile_resolver import TargetProfile
    from app.infrastructure.github.repo_creator import RepoCreator

    profile = TargetProfile(owner="target-owner", is_org=False, host="github.com")
    gh_data = {
        "name": "target-app-Migrated2026",
        "full_name": "target-owner/target-app-Migrated2026",
        "html_url": "https://github.com/target-owner/target-app-Migrated2026",
        "clone_url": "https://github.com/target-owner/target-app-Migrated2026.git",
    }
    created = RepoCreator._created_repo_from_response(profile, "target-app-Migrated2026", gh_data)
    assert created.html_url == "https://github.com/target-owner/target-app-Migrated2026"
    assert created.clone_url == "https://github.com/target-owner/target-app-Migrated2026.git"
    assert created.name == "target-app-Migrated2026"
    assert created.owner == "target-owner"


def test_target_repo_does_not_contain_source_repo_url():
    """Regression test ensuring source repo URL/owner is never concatenated into target repository URL."""
    rep = {
        "jobId": "test-job-regression",
        "sourceRepoUrl": "https://github.com/source-owner/source-app",
        "destination": {
            "mode": "CREATE_NEW_REPO",
            "targetOwner": "target-owner",
            "targetHost": "github.com",
            "targetRepoName": "target-app-Migrated2026",
        },
    }
    res = report_service.build_result(rep)
    assert res["target_repo"] == "https://github.com/target-owner/target-app-Migrated2026"
    assert "source-owner" not in res["target_repo"]
    assert "source-app" not in res["target_repo"]
    assert "https-github" not in res["target_repo"]


def test_build_result_scan_execution_flags():
    """Verify that runSonar, runFossa, runTests flags are propagated to result and summary."""
    rep_off = {
        "jobId": "test-job-scans-off",
        "runSonar": False,
        "runFossa": False,
        "runTests": True,
    }
    res_off = report_service.build_result(rep_off)
    sum_off = report_service.build_summary(rep_off)
    assert res_off["run_sonar"] is False
    assert res_off["run_fossa"] is False
    assert res_off["run_tests"] is True
    assert sum_off["run_sonar"] is False
    assert sum_off["run_fossa"] is False
    assert sum_off["run_tests"] is True

    rep_on = {
        "jobId": "test-job-scans-on",
        "runSonar": True,
        "runFossa": True,
        "runTests": False,
    }
    res_on = report_service.build_result(rep_on)
    sum_on = report_service.build_summary(rep_on)
    assert res_on["run_sonar"] is True
    assert res_on["run_fossa"] is True
    assert res_on["run_tests"] is False
    assert sum_on["run_sonar"] is True
    assert sum_on["run_fossa"] is True
    assert sum_on["run_tests"] is False



