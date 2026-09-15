import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.application.use_cases.run_discovery import RunDiscoveryUseCase
from app.infrastructure.persistence.job_repository import JobRepository
from app.infrastructure.git.repository_cloner import RepositoryCloner
from app.infrastructure.analyzers.project_analyzer import ProjectAnalyzer

@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=JobRepository)
    repo.read_connect_report.return_value = {
        "repoUrl": "https://github.com/test/repo",
        "owner": "test",
        "repoName": "repo",
        "repoVisibility": "PUBLIC"
    }
    repo.read_discovery_report.return_value = None
    return repo

@pytest.fixture
def mock_cloner():
    return MagicMock(spec=RepositoryCloner)

@patch("app.infrastructure.analyzers.api_endpoint_detector.ApiEndpointDetector.detect")
def test_discovery_includes_endpoints(mock_detect, mock_repo, mock_cloner, tmp_path):
    # Mock detected endpoints
    mock_detect.return_value = [
        {"id": "1", "httpMethod": "GET", "path": "/api/users", "controller": "UserController"}
    ]
    
    # Mock analyzer to return a valid ProjectAnalysis
    analyzer = ProjectAnalyzer()
    
    use_case = RunDiscoveryUseCase(job_repository=mock_repo, cloner=mock_cloner, analyzer=analyzer)
    
    # We need to mock the filesystem for the analyzer
    with patch.object(Path, "is_dir", return_value=True), \
         patch.object(Path, "iterdir", return_value=[Path("pom.xml")]), \
         patch("app.infrastructure.workspace.workspace_manager.WorkspaceManager.prepare_original_repo_target"), \
         patch("app.shared.file_utils.find_files", return_value=["pom.xml", "src/main/java/Controller.java"]), \
         patch("app.shared.file_utils.read_text", return_value="<project></project>"), \
         patch("app.infrastructure.analyzers.build_tool_detector.BuildToolDetector.detect") as mock_bt:
        
        mock_bt.return_value = MagicMock(build_tool="MAVEN", is_supported=True, has_pom_xml=True)
        
        outcome = use_case.execute(job_id="test-job")
        
        assert "apiEndpoints" in outcome.response["project"]
        assert len(outcome.response["project"]["apiEndpoints"]) == 1
        assert outcome.response["project"]["apiEndpoints"][0]["path"] == "/api/users"
        
        # Verify it was saved to the report
        assert "apiEndpoints" in outcome.report
        assert len(outcome.report["apiEndpoints"]) == 1
