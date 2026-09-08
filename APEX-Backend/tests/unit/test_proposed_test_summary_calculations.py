import pytest
from app.domain.models.proposed_test_models import (
    ProposedTestCase,
    ProposedTestType,
    ProposedTestPriority,
    ProposedTestStatus,
)
from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService


@pytest.fixture
def sample_25_test_cases():
    """
    Exact dataset representation corresponding to:
    Total: 25
    UI: 2, API: 23
    Must Have (P0): 12, Good To Have (P1: 11, P2: 2, P3: 0): 13
    Sources: 15 AI_GENERATED, 9 BRD_DOCUMENT, 1 BRD_AND_AI (or EXISTING)
    """
    tests = []
    
    # 1. 14 Pure AI Generated API Tests (P0: 6, P1: 6, P2: 2)
    for i in range(1, 15):
        priority = ProposedTestPriority.HIGH if i <= 6 else (ProposedTestPriority.MEDIUM if i <= 12 else ProposedTestPriority.LOW)
        tests.append(
            ProposedTestCase(
                id=f"PTC-{i:03d}",
                title=f"API Endpoint Test {i}",
                description=f"Generated API test case {i}",
                type=ProposedTestType.API,
                priority=priority,
                source=f"Controller{i % 4}.java",
                reason="Endpoint contract verification",
                expected_result="200 OK",
                status=ProposedTestStatus.PROPOSED,
                generation_source="AI_GENERATED",
            )
        )
    
    # 2. 1 Pure AI Generated UI Test (P0: 1)
    tests.append(
        ProposedTestCase(
            id="PTC-015",
            title="UI Workflow Login Test",
            description="Generated UI navigation test",
            type=ProposedTestType.UI,
            priority=ProposedTestPriority.HIGH,
            source="UI Router (/login)",
            reason="UI navigation check",
            expected_result="Login page visible",
            status=ProposedTestStatus.PROPOSED,
            generation_source="AI_GENERATED",
        )
    )

    # 3. 8 Pure BRD Document API Tests (P0: 4, P1: 4)
    for i in range(16, 24):
        priority = ProposedTestPriority.HIGH if i <= 19 else ProposedTestPriority.MEDIUM
        tests.append(
            ProposedTestCase(
                id=f"PTC-BRD-{i:03d}",
                title=f"BRD Requirement Flow {i}",
                description=f"Functional requirement {i}",
                type=ProposedTestType.API,
                priority=priority,
                source="BRD Document",
                reason="Business requirement verification",
                expected_result="Requirement passed",
                status=ProposedTestStatus.PROPOSED,
                generation_source="BRD_DOCUMENT",
            )
        )

    # 4. 1 Pure BRD Document UI Test (P0: 1)
    tests.append(
        ProposedTestCase(
            id="PTC-BRD-024",
            title="BRD Checkout UI Flow",
            description="Functional document checkout workflow",
            type=ProposedTestType.UI,
            priority=ProposedTestPriority.HIGH,
            source="UI Router (/checkout)",
            reason="Checkout screen verification",
            expected_result="Checkout elements visible",
            status=ProposedTestStatus.PROPOSED,
            generation_source="BRD_DOCUMENT",
        )
    )

    # 5. 1 Combined Cross-verified Test Case (BRD_AND_AI) (P1: 1) -> Total 25
    tests.append(
        ProposedTestCase(
            id="PTC-025",
            title="Cross-verified Pricing Calculation Flow",
            description="Aligned AI and BRD pricing logic test",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.MEDIUM,
            source="PricingService.java",
            reason="Pricing calculation cross-verified with BRD",
            expected_result="Calculation valid",
            status=ProposedTestStatus.PROPOSED,
            generation_source="BRD_AND_AI",
        )
    )

    return tests


def test_proposed_test_summary_dataset_consistency(sample_25_test_cases):
    service = ProposedTestService()
    metrics = service._compute_metrics(sample_25_test_cases)

    # 1. Total Count Verification
    assert len(sample_25_test_cases) == 25
    assert metrics.total == 25

    # 2. API + UI Breakdown
    ui_tests = [p for p in sample_25_test_cases if p.type == ProposedTestType.UI]
    api_tests = [p for p in sample_25_test_cases if p.type in [ProposedTestType.API, ProposedTestType.UNIT]]
    assert len(ui_tests) == 2
    assert len(api_tests) == 23
    assert len(ui_tests) + len(api_tests) == 25

    # 3. Priority Breakdown (P0, P1, P2, P3)
    p0_count = len([p for p in sample_25_test_cases if p.priority == ProposedTestPriority.HIGH])
    p1_count = len([p for p in sample_25_test_cases if p.priority == ProposedTestPriority.MEDIUM])
    p2_count = len([p for p in sample_25_test_cases if p.priority == ProposedTestPriority.LOW])
    p3_count = 0
    assert p0_count == 12  # Must Have
    assert p1_count == 11
    assert p2_count == 2
    assert p3_count == 0
    assert p0_count + p1_count + p2_count + p3_count == 25

    # 4. Must Have vs Good To Have
    must_have = p0_count
    good_to_have = p1_count + p2_count + p3_count
    assert must_have == 12
    assert good_to_have == 13
    assert must_have + good_to_have == 25

    # 5. Source Classification Consistency
    # Pure BRD is counted under BRD; AI and BRD_AND_AI are counted under AI
    brd_count = metrics.brd_generated_count
    ai_count = metrics.ai_generated_count
    existing_count = metrics.existing_count
    assert brd_count == 9   # 9 pure BRD (8 API + 1 UI)
    assert ai_count == 16   # 15 pure AI + 1 BRD_AND_AI
    assert existing_count == 0
    assert ai_count + brd_count + existing_count == 25

    # 6. Suite Composition Consistency
    suites = {}
    for t in sample_25_test_cases:
        suite = t.source
        suites[suite] = suites.get(suite, 0) + 1
    assert sum(suites.values()) == 25
