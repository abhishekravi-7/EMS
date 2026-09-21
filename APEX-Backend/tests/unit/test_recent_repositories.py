import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.infrastructure.persistence.models import User

@pytest.fixture
def mock_user():
    user = User()
    user.id = "user_123"
    user.full_name = "Test User"
    user.email = "test@example.com"
    user.role = "USER"
    user.is_active = True
    return user

@pytest.fixture
def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_recent_repositories_unauthenticated():
    unauth_client = TestClient(app)
    response = unauth_client.get("/api/v1/connect/recent-repositories")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_recent_repositories_owner_and_components_all_states(client, mock_user):
    docs = [
        {
            "job_id": "job_completed_zero",
            "user_id": "user_123",
            "owner_name": "Sarah Connor",
            "repository_name": "org/repo-zero",
            "last_updated": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        },
        {
            "job_id": "job_completed_single",
            "user_id": "user_123",
            "owner_name": "   ",  # blank whitespace -> "Owner unavailable"
            "repository_name": "org/repo-single",
            "last_updated": datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        },
        {
            "job_id": "job_completed_multi",
            "user_id": "user_123",
            "owner_name": "John Doe",
            "repository_name": "org/repo-multi",
            "last_updated": datetime(2026, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
        },
        {
            "job_id": "job_not_started",
            "user_id": "user_123",
            "owner_name": "Alice Smith",
            "repository_name": "org/repo-not-started",
            "last_updated": datetime(2026, 1, 4, 12, 0, 0, tzinfo=timezone.utc),
        },
        {
            "job_id": "job_running",
            "user_id": "user_123",
            "owner_name": "Bob Builder",
            "repository_name": "org/repo-running",
            "last_updated": datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
        },
        {
            "job_id": "job_failed",
            "user_id": "user_123",
            "owner_name": "Charlie Chaplin",
            "repository_name": "org/repo-failed",
            "last_updated": datetime(2026, 1, 6, 12, 0, 0, tzinfo=timezone.utc),
        },
        {
            "job_id": "job_unsupported",
            "user_id": "user_123",
            "owner_name": None,  # None -> "Owner unavailable"
            "repository_name": "org/repo-unsupported",
            "last_updated": datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc),
        },
    ]

    reports = {
        "job_completed_zero": {
            "status": "DISCOVERY_COMPLETED",
            "apiEndpoints": [],
        },
        "job_completed_single": {
            "status": "DISCOVERY_COMPLETED",
            "apiEndpoints": [{"path": "/api/item", "method": "GET"}],
        },
        "job_completed_multi": {
            "status": "DISCOVERY_COMPLETED",
            "apiEndpoints": [{"path": f"/api/{i}", "method": "GET"} for i in range(15)],
        },
        "job_not_started": None,
        "job_running": {
            "status": "RUNNING",
        },
        "job_failed": {
            "status": "FAILED",
        },
        "job_unsupported": {
            "status": "UNKNOWN_STATE",
        },
    }

    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=list(reversed(docs)))
    mock_cursor.sort.return_value.limit.return_value = mock_cursor
    mock_db.migration_job_owners.find.return_value = mock_cursor
    mock_db.discovery_reports.find_one = AsyncMock(return_value=None)

    def mock_read_discovery(job_id):
        return reports.get(job_id)

    with patch("app.infrastructure.persistence.mongodb.get_mongodb", AsyncMock(return_value=mock_db)), \
         patch("app.infrastructure.persistence.job_repository.JobRepository.read_discovery_report", side_effect=mock_read_discovery), \
         patch("app.infrastructure.persistence.job_repository.JobRepository.read_connect_report", return_value={"repoVisibility": "PUBLIC"}):
        
        response = client.get("/api/v1/connect/recent-repositories")
        assert response.status_code == 200
        repos = response.json()["repositories"]
        assert len(repos) == 7

        by_id = {r["jobId"]: r for r in repos}

        # 1. Completed with 0 -> "0 APIs", "Sarah Connor"
        assert by_id["job_completed_zero"]["owner"] == "Sarah Connor"
        assert by_id["job_completed_zero"]["componentsCount"] == "0 APIs"
        assert by_id["job_completed_zero"]["status"] == "Analyzed"

        # 2. Completed with 1 -> "1 API", "Owner unavailable" (was whitespace)
        assert by_id["job_completed_single"]["owner"] == "Owner unavailable"
        assert by_id["job_completed_single"]["componentsCount"] == "1 API"
        assert by_id["job_completed_single"]["status"] == "Analyzed"

        # 3. Completed with 15 -> "15 APIs", "John Doe"
        assert by_id["job_completed_multi"]["owner"] == "John Doe"
        assert by_id["job_completed_multi"]["componentsCount"] == "15 APIs"
        assert by_id["job_completed_multi"]["status"] == "Analyzed"

        # 4. Not started -> "Not analyzed", "Alice Smith"
        assert by_id["job_not_started"]["owner"] == "Alice Smith"
        assert by_id["job_not_started"]["componentsCount"] == "Not analyzed"
        assert by_id["job_not_started"]["status"] == "Connected"

        # 5. Running -> "Analyzing…", "Bob Builder"
        assert by_id["job_running"]["owner"] == "Bob Builder"
        assert by_id["job_running"]["componentsCount"] == "Analyzing…"
        assert by_id["job_running"]["status"] == "Analyzing"

        # 6. Failed -> "Analysis failed", "Charlie Chaplin"
        assert by_id["job_failed"]["owner"] == "Charlie Chaplin"
        assert by_id["job_failed"]["componentsCount"] == "Analysis failed"
        assert by_id["job_failed"]["status"] == "Failed"

        # 7. Unsupported/missing metrics -> "Unavailable", "Owner unavailable" (was None)
        assert by_id["job_unsupported"]["owner"] == "Owner unavailable"
        assert by_id["job_unsupported"]["componentsCount"] == "Unavailable"
