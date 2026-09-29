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


def test_summary_and_result_stages_for_completed_and_running_states():
    # 1. COMPLETED job
    completed_rep = {
        "jobId": "job-completed-test",
        "status": "COMPLETED",
        "progressPercent": 100,
        "currentStep": "Migration completed",
    }
    summary = report_service.build_summary(completed_rep)
    assert summary["status"] == "COMPLETED"
    assert summary["progress_percent"] == 100
    assert summary["current_stage"] == "migration-report"
    assert len(summary["stages"]) == 6
    assert all(st["status"] == "completed" for st in summary["stages"])

    # 2. RUNNING job at 25%
    running_rep = {
        "jobId": "job-running-test",
        "status": "RUNNING",
        "progressPercent": 25,
        "currentStage": "dependency-updates",
        "currentStep": "2. Dependencies updates",
    }
    running_summary = report_service.build_summary(running_rep)
    assert running_summary["status"] == "RUNNING"
    assert running_summary["progress_percent"] == 25
    assert running_summary["current_stage"] == "dependency-updates"
    assert running_summary["stages"][0]["status"] == "completed"
    assert running_summary["stages"][1]["status"] == "in_progress"
    assert running_summary["stages"][2]["status"] == "pending"



def test_build_report_details_categories():
    """Test build_report_details retrieves exact underlying records for all 5 summary cards."""
    mock_report = {
        "jobId": "job-detail-test-123",
        "status": "completed",
        "buildTool": "MAVEN",
        "filesModified": 2,
        "modifiedFiles": ["pom.xml", "src/main/webapp/login.jsp"],
        "fileDiffs": [
            {
                "relativePath": "pom.xml",
                "fileName": "pom.xml",
                "changeType": "MODIFIED",
                "addedLineCount": 1,
                "removedLineCount": 1,
            },
            {
                "relativePath": "src/main/webapp/login.jsp",
                "fileName": "login.jsp",
                "changeType": "MODIFIED",
                "addedLineCount": 50,
                "removedLineCount": 50,
            },
        ],
        "uiTransformations": [
            {
                "file": "LoginComponent.tsx",
                "sourceFile": "src/main/webapp/login.jsp",
                "targetFramework": "React",
                "sourceFramework": "JSP",
                "status": "Added",
                "additions": 50,
                "deletions": 50,
            }
        ],
        "importChanges": [
            {
                "file": "src/main/java/App.java",
                "added": ["jakarta.servlet.http.HttpServlet"],
                "removed": ["javax.servlet.http.HttpServlet"],
            }
        ],
        "dependencyUpgrades": [
            {
                "groupId": "org.springframework.boot",
                "artifactId": "spring-boot-starter",
                "sourceVersion": "2.7.0",
                "resolvedTargetVersion": "3.2.0",
                "status": "UPGRADED",
            }
        ],
        "fossa_report": {
            "vulnerabilities": [],
        },
    }

    # 1. Files
    files_detail = report_service.build_report_details(mock_report, "files")
    assert files_detail["type"] == "files"
    assert files_detail["total"] == 2
    assert len(files_detail["items"]) == 2
    assert files_detail["items"][0]["file_name"] == "pom.xml"
    assert files_detail["items"][1]["path"] == "src/main/webapp/login.jsp"
    assert files_detail["items"][1]["file_name"] == "LoginComponent.tsx"

    # 2. Issues
    issues_detail = report_service.build_report_details(mock_report, "issues")
    assert issues_detail["type"] == "issues"
    # 1 import change + 1 dependency upgrade + 1 UI transformation = 3 issues
    assert issues_detail["total"] == 3
    assert len(issues_detail["items"]) == 3

    # 3. Dependencies
    dep_detail = report_service.build_report_details(mock_report, "dependencies")
    assert dep_detail["type"] == "dependencies"
    assert dep_detail["total"] == 1
    assert dep_detail["items"][0]["name"] == "org.springframework.boot:spring-boot-starter"
    assert dep_detail["items"][0]["old_version"] == "2.7.0"
    assert dep_detail["items"][0]["new_version"] == "3.2.0"

    # 4. Vulnerabilities (empty)
    vuln_detail = report_service.build_report_details(mock_report, "vulnerabilities")
    assert vuln_detail["type"] == "vulnerabilities"
    assert vuln_detail["total"] == 0
    assert vuln_detail["items"] == []

    # 5. Transformations (Code Transmission)
    trans_detail = report_service.build_report_details(mock_report, "transformations")
    assert trans_detail["type"] == "transformations"
    # 1 UI transform + 1 Java import refactoring = 2 transformations
    assert trans_detail["total"] == 2
    assert trans_detail["items"][0]["source_file"] == "src/main/webapp/login.jsp"
    assert trans_detail["items"][0]["target_file"] == "LoginComponent.tsx"
    assert trans_detail["items"][0]["transformation_type"] == "JSP -> React"

