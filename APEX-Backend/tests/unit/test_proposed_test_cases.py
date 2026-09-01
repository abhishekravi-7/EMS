"""Unit tests for Proposed Functional Test Cases."""

from pathlib import Path
from tempfile import TemporaryDirectory

from app.application.use_cases.proposed_tests.proposed_test_analyzer import ProposedTestAnalyzer
from app.application.use_cases.proposed_tests.proposed_test_generator import ProposedTestGenerator
from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService
from app.domain.models.proposed_test_models import (
    ProposedTestStatus,
)


def test_proposed_test_analyzer_and_generator():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Create mock Spring Boot controller
        src_dir = root / "src" / "main" / "java" / "com" / "example"
        src_dir.mkdir(parents=True)
        controller_code = """
        package com.example;
        import org.springframework.web.bind.annotation.*;

        @RestController
        @RequestMapping("/api/v1/users")
        public class UserController {
            @GetMapping("/{id}")
            public User getUser(@PathVariable String id) { return null; }

            @PostMapping
            public User createUser(@RequestBody User u) { return null; }
        }
        """
        (src_dir / "UserController.java").write_text(controller_code)

        # Mock existing test that only covers GET /api/v1/users/{id}
        existing_tests = [
            {"name": "test_getUser", "classname": "UserControllerTest", "file": "UserControllerTest.java"}
        ]

        analyzer = ProposedTestAnalyzer(root, existing_tests=existing_tests)
        analysis_data = analyzer.analyze()

        assert len(analysis_data["endpoints"]) >= 2
        endpoints = [ep["endpoint"] for ep in analysis_data["endpoints"]]
        assert any("/api/v1/users" in ep for ep in endpoints)

        generator = ProposedTestGenerator(analysis_data)
        proposals = generator.generate()

        assert len(proposals) >= 1
        # Propose tests with explicit reason
        for p in proposals:
            assert p.reason != ""
            assert p.source != ""
            assert p.id.startswith("PTC-")
            assert p.status == ProposedTestStatus.PROPOSED


def test_proposed_test_service_lifecycle():
    with TemporaryDirectory() as tmpdir:
        service = ProposedTestService()
        job_id = "test_lifecycle_job"

        # Override storage dir to temp
        service._get_job_dir = lambda j: Path(tmpdir) / j
        (Path(tmpdir) / job_id).mkdir(parents=True)

        # 1. Before generation, proposals list is empty and status is IDLE
        initial_proposals = service.get_proposed_tests(job_id)
        assert len(initial_proposals) == 0
        initial_status = service.get_status(job_id)
        assert initial_status["status"] == "IDLE"

        # 2. Generate proposals
        proposals = service.generate_proposed_tests(job_id)
        assert len(proposals) > 0
        first_id = proposals[0].id

        # 3. Approve test
        approved = service.set_status(job_id, first_id, ProposedTestStatus.APPROVED)
        assert approved.status == ProposedTestStatus.APPROVED

        # 4. Update test
        updated = service.update_proposed_test(job_id, first_id, {"title": "Updated Title"})
        assert updated.title == "Updated Title"

        # 5. Check status and metrics
        status = service.get_status(job_id)
        assert status["metrics"]["approved"] == 1
        assert status["metrics"]["total"] == len(proposals)
