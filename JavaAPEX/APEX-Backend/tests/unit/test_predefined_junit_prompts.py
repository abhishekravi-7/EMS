"""Unit tests for predefined JUnit coverage prompts and combination logic."""

import pytest
from app.core.junit_prompts import PREDEFINED_JUNIT_PROMPTS, combine_junit_prompts
from app.schemas.unit_test import TestingPromptAnalysis, TestingPromptAnalysisRequest


def test_predefined_prompts_count_and_structure():
    assert len(PREDEFINED_JUNIT_PROMPTS) == 5
    prompt_ids = [p["id"] for p in PREDEFINED_JUNIT_PROMPTS]
    assert "comprehensive_junit_coverage" in prompt_ids
    assert "business_logic_functional_paths" in prompt_ids
    assert "branch_condition_edge_case" in prompt_ids
    assert "exception_negative_scenario" in prompt_ids
    assert "jacoco_dynamic_coverage_gap" in prompt_ids

    for p in PREDEFINED_JUNIT_PROMPTS:
        assert "id" in p
        assert "title" in p
        assert "prompt" in p
        assert "description" in p


def test_combine_junit_prompts_combinations():
    # Scenario 1: No checkbox + No manual prompt
    combined_empty = combine_junit_prompts([], "")
    assert combined_empty == ""

    # Scenario 2: Only Prompt 1
    combined_p1 = combine_junit_prompts(["comprehensive_junit_coverage"], None)
    assert "Analyze the entire application and create comprehensive JUnit test coverage" in combined_p1

    # Scenario 3: Prompt 1 + Prompt 5
    combined_p1_p5 = combine_junit_prompts(["comprehensive_junit_coverage", "jacoco_dynamic_coverage_gap"], None)
    assert "Analyze the entire application" in combined_p1_p5
    assert "Analyze the existing JUnit tests and JaCoCo coverage report" in combined_p1_p5

    # Scenario 4: Manual prompt only
    combined_manual = combine_junit_prompts([], "Focus on payment calculation")
    assert "Additional User Guidance: Focus on payment calculation" in combined_manual

    # Scenario 5: Prompt 1 + Manual prompt
    combined_p1_manual = combine_junit_prompts(["comprehensive_junit_coverage"], "Focus on login")
    assert "Analyze the entire application" in combined_p1_manual
    assert "Additional User Guidance: Focus on login" in combined_p1_manual

    # Scenario 6: Multiple predefined + Manual prompt
    combined_multi = combine_junit_prompts(
        ["comprehensive_junit_coverage", "branch_condition_edge_case", "jacoco_dynamic_coverage_gap"],
        "Focus on payment gateway"
    )
    assert "Analyze the entire application" in combined_multi
    assert "maximize meaningful coverage of conditional logic" in combined_multi
    assert "JaCoCo coverage report" in combined_multi
    assert "Additional User Guidance: Focus on payment gateway" in combined_multi


def test_schema_supports_predefined_prompts():
    req = TestingPromptAnalysisRequest(
        selected_predefined_prompts=["comprehensive_junit_coverage", "jacoco_dynamic_coverage_gap"],
        manual_prompt="Special focus on connection pools",
    )
    assert req.selected_predefined_prompts == ["comprehensive_junit_coverage", "jacoco_dynamic_coverage_gap"]
    assert req.manual_prompt == "Special focus on connection pools"

    analysis = TestingPromptAnalysis(
        testing_focus="Comprehensive & Coverage Gap Analysis",
        testing_objective="Achieve 80-90% coverage",
        coverage_target="80-90%",
    )
    assert analysis.coverage_target == "80-90%"


def test_extract_prompt_target_classes_distinct_per_prompt():
    from app.infrastructure.llm.junit_generator import extract_prompt_target_classes

    sample_repo_classes = [
        "AccountService", "UserService", "CustomerProcessor",
        "AccountValidator", "UserRuleChecker", "SecurityController",
        "AuthException", "ValidationHandler",
        "CacheUtil", "StringHelperImpl"
    ]

    # Prompt 1: Business Logic
    p1_classes, _ = extract_prompt_target_classes("", sample_repo_classes, selected_prompt_ids=["business_logic_functional_paths"])
    assert "AccountService" in p1_classes or "UserService" in p1_classes or "CustomerProcessor" in p1_classes
    assert "UserRuleChecker" not in p1_classes

    # Prompt 2: Branch & Edge Cases
    p2_classes, _ = extract_prompt_target_classes("", sample_repo_classes, selected_prompt_ids=["branch_condition_edge_case"])
    assert "AccountValidator" in p2_classes or "UserRuleChecker" in p2_classes or "SecurityController" in p2_classes
    assert "AccountService" not in p2_classes

    # Prompt 3: Exceptions & Negative Scenarios
    p3_classes, _ = extract_prompt_target_classes("", sample_repo_classes, selected_prompt_ids=["exception_negative_scenario"])
    assert "AuthException" in p3_classes or "ValidationHandler" in p3_classes
    assert "AccountService" not in p3_classes


def test_html_report_generator_white_theme():
    from app.application.services.unit_test_report_generator import UnitTestReportGenerator

    gen = UnitTestReportGenerator()
    html_output = gen.generate_html_report("job_test_12345")
    assert "<!DOCTYPE html>" in html_output
    assert "--bg-main: #f8fafc;" in html_output
    assert "--bg-card: #ffffff;" in html_output
    assert "--text-primary: #0f172a;" in html_output


