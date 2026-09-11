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
