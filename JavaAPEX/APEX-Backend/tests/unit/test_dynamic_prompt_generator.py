"""Unit tests verifying the dynamic LLM prompt generator and category/volume constraint enforcement."""

from pathlib import Path
import pytest

from app.application.use_cases.proposed_tests.proposed_test_generator import ProposedTestGenerator, PLATFORM_CATEGORIES
from app.application.use_cases.proposed_tests.proposed_test_validator import ProposedTestValidator
from app.domain.models.proposed_test_models import ProposedTestType, ValidationStatus


def test_directive_parsing_volumes_and_exclusions():
    analysis = {
        "functional_testing_suggestions": ["negative-testing", "edge-case", "role-permission", "e2e-workflow"],
        "functional_custom_prompt": "DONT GENERATE DUPLICATE TESTCASE, GENERATE 50 API TESTCASES AND 50 UI TESTCASES",
    }
    generator = ProposedTestGenerator(analysis)
    directives = generator._parse_directives()

    assert directives["api_target"] == 50
    assert directives["ui_target"] == 50
    assert directives["no_duplicates"] is True
    assert "happy-path" not in directives["enabled_cat_ids"]
    assert "negative-testing" in directives["enabled_cat_ids"]
    assert "edge-case" in directives["enabled_cat_ids"]
    assert "role-permission" in directives["enabled_cat_ids"]
    assert "e2e-workflow" in directives["enabled_cat_ids"]


def test_dynamic_prompt_construction():
    analysis = {
        "functional_testing_suggestions": ["negative-testing", "edge-case"],
        "functional_custom_prompt": "GENERATE 20 API TESTCASES",
        "endpoints": [
            {"method": "GET", "endpoint": "/api/users", "class_name": "UserController"},
            {"method": "POST", "endpoint": "/api/users", "class_name": "UserController"},
        ],
        "ui_workflows": [
            {"name": "UserForm", "route": "/users/new", "has_form": True},
        ],
    }
    generator = ProposedTestGenerator(analysis)
    directives = generator._parse_directives()
    prompt = generator.build_prompt(directives)

    assert "ROLE" in prompt
    assert "Negative & Validation Testing" in prompt
    assert "Edge Case Testing" in prompt
    # Happy Path must NOT be in enabled categories
    assert "- Happy Path Testing" not in prompt
    assert "GENERATE 20 API TESTCASES" in prompt
    assert "/api/users" in prompt
    assert "/users/new" in prompt


def test_generation_with_disabled_happy_path_produces_zero_happy_path():
    repo_path = Path("storage/migration-jobs/job_3fcd803b0285/migrated-repo")
    if not repo_path.exists():
        pytest.skip(f"Test repo {repo_path} not found")

    from app.application.use_cases.proposed_tests.proposed_test_analyzer import ProposedTestAnalyzer
    analyzer = ProposedTestAnalyzer(repo_path)
    analysis = analyzer.analyze()
    analysis["functional_testing_suggestions"] = ["negative-testing", "edge-case", "role-permission", "e2e-workflow"]
    analysis["functional_custom_prompt"] = "DONT GENERATE DUPLICATE TESTCASE, GENERATE 50 API TESTCASES AND 50 UI TESTCASES"

    generator = ProposedTestGenerator(analysis, repo_dir=repo_path)
    proposals = generator.generate()

    assert len(proposals) == 100
    api_tests = [p for p in proposals if p.type == ProposedTestType.API]
    ui_tests = [p for p in proposals if p.type == ProposedTestType.UI]

    assert len(api_tests) == 50
    assert len(ui_tests) == 50

    # Rule 2: ZERO happy path test cases must be generated
    happy_path_tests = [p for p in proposals if p.category == "Happy Path Testing" or "happy path" in p.title.lower()]
    assert len(happy_path_tests) == 0

    # Validate against actual repository evidence
    validator = ProposedTestValidator(repo_path, analysis_data=analysis)
    validated_proposals, summary = validator.validate_all(proposals)

    assert summary.total_llm_generated == 100
    assert summary.valid == 100
    assert summary.duplicate == 0
    assert summary.invalid == 0
    assert summary.hallucinated == 0
    assert summary.review_required == 0


def test_generation_with_ui_only_prompt_produces_exact_count():
    repo_path = Path("storage/migration-jobs/job_3fcd803b0285/migrated-repo")
    if not repo_path.exists():
        pytest.skip(f"Test repo {repo_path} not found")

    from app.application.use_cases.proposed_tests.proposed_test_analyzer import ProposedTestAnalyzer
    analyzer = ProposedTestAnalyzer(repo_path)
    analysis = analyzer.analyze()
    analysis["functional_custom_prompt"] = "50 ui testcase"

    generator = ProposedTestGenerator(analysis, repo_dir=repo_path)
    proposals = generator.generate()

    assert len(proposals) == 50
    api_tests = [p for p in proposals if p.type == ProposedTestType.API]
    ui_tests = [p for p in proposals if p.type == ProposedTestType.UI]

    assert len(ui_tests) == 50
    assert len(api_tests) == 0


def test_playwright_test_generator_sanitizes_multiline_jsx():
    from app.application.use_cases.proposed_tests.playwright_test_generator import PlaywrightTestGenerator
    from app.domain.models.proposed_test_models import ProposedTestCase, ProposedTestType, ProposedTestPriority, UiTestSpec

    test_case = ProposedTestCase(
        id="PTC-001",
        title="Test UI with JSX button",
        description="Verify UI render",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.MEDIUM,
        source="LLM Generated",
        reason="Test JSX button sanitization",
        expected_result="Button renders without syntax error",
        ui_spec=UiTestSpec(
            target_route="/salary",
            actions=["navigate", "screenshot"],
            expected_elements=["button:has-text('handleProcessPayment(row.id)}\n style={{ display: 'flex'"],
        ),
    )

    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        job_dir = Path(tmp_dir)
        pw_gen = PlaywrightTestGenerator(job_dir, "http://localhost:8080", "http://localhost:3000")
        pw_gen.generate_project([test_case])
        spec_path = pw_gen.pw_dir / "tests" / "functional.generated.spec.ts"
        assert spec_path.exists()
        content = spec_path.read_text(encoding="utf-8")
        # Check there are no unterminated strings or multiline locator issues
        assert "\n style={{ display:" not in content
        assert "button:has-text('handleProcessPayment" not in content
        assert "screenshot" in content

