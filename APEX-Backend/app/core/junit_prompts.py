"""Predefined JUnit coverage prompts registry and prompt combination helper functions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

PREDEFINED_JUNIT_PROMPTS: List[Dict[str, str]] = [
    {
        "id": "comprehensive_junit_coverage",
        "title": "Comprehensive JUnit Coverage",
        "prompt": (
            "Analyze the entire application and create comprehensive JUnit test coverage across the repository. "
            "Dynamically identify the important classes, methods, business logic, execution paths, validations, "
            "conditions, dependencies, and application behavior that require unit testing. Cover positive, negative, "
            "boundary, edge, and exception scenarios wherever applicable. Use the existing JUnit testing infrastructure "
            "and JaCoCo coverage results to identify meaningful uncovered areas and generate additional tests. "
            "The goal is to achieve approximately 80–90% meaningful JUnit code coverage without creating redundant or artificial tests. "
            "Do not rely on predefined class names, methods, modules, or application-specific assumptions; "
            "determine the relevant test scope dynamically from the actual repository."
        ),
        "description": (
            "Provides broad repository-level JUnit coverage by dynamically analyzing application code, "
            "identifying important testable areas, and using JaCoCo results to improve meaningful coverage toward the 80–90% target."
        ),
    },
    {
        "id": "business_logic_functional_paths",
        "title": "Business Logic & Functional Paths",
        "prompt": (
            "Analyze the repository and generate JUnit tests that provide broad coverage of the application's core business logic "
            "and functional execution paths. Dynamically identify the important methods, services, components, validations, calculations, "
            "workflows, and interactions that contain meaningful application behavior. Cover normal execution, alternate execution paths, "
            "input variations, boundary conditions, and relevant dependencies. Use JaCoCo to identify uncovered business logic "
            "and generate additional tests where required. Do not assume specific business modules or functionality; "
            "determine the relevant areas dynamically from the source code."
        ),
        "description": (
            "Focuses JUnit testing on meaningful application behavior and core execution paths while dynamically identifying "
            "business logic from the repository."
        ),
    },
    {
        "id": "branch_condition_edge_case",
        "title": "Branch, Condition & Edge-Case Coverage",
        "prompt": (
            "Analyze the entire repository and generate JUnit tests that maximize meaningful coverage of conditional logic, "
            "branches, decision paths, loops, boundary conditions, and edge cases. Dynamically identify areas where different "
            "inputs or execution conditions can produce different outcomes and create tests for those scenarios. Include valid, "
            "invalid, null, empty, boundary, unexpected, and alternate inputs wherever applicable. Use JaCoCo line and branch coverage "
            "to identify remaining gaps and generate additional tests for important uncovered paths. Avoid redundant tests and "
            "do not modify production code solely to increase coverage."
        ),
        "description": (
            "Strengthens JUnit coverage by dynamically identifying conditional branches, decision paths, boundaries, and edge cases "
            "that may otherwise remain untested."
        ),
    },
    {
        "id": "exception_negative_scenario",
        "title": "Exception & Negative Scenario Coverage",
        "prompt": (
            "Analyze the repository and create comprehensive JUnit tests for error handling, exception paths, validation failures, "
            "invalid inputs, dependency failures, and other negative execution scenarios. Dynamically identify where exceptions or failure "
            "conditions can occur and verify that the application responds correctly. Also maintain coverage of successful execution paths "
            "so that negative testing complements rather than replaces normal testing. Use JaCoCo to identify uncovered exception and failure "
            "paths and generate additional tests where meaningful. Do not assume predefined exception types or scenarios; "
            "determine them from the actual application code."
        ),
        "description": (
            "Improves JUnit coverage of error handling and failure paths while maintaining coverage of normal application behavior."
        ),
    },
    {
        "id": "jacoco_dynamic_coverage_gap",
        "title": "JaCoCo Dynamic Coverage Gap Analysis",
        "prompt": (
            "Analyze the existing JUnit tests and JaCoCo coverage report for the entire repository. Dynamically identify meaningful "
            "uncovered classes, methods, lines, branches, conditions, execution paths, and important application logic. Based on the "
            "actual source code and current coverage results, determine which additional JUnit tests are required to improve meaningful coverage "
            "toward approximately 80–90%. Generate only the tests necessary to address the identified gaps, execute the tests, regenerate the "
            "JaCoCo report, and continue analyzing remaining meaningful gaps until the target is reasonably approached. Do not use hardcoded mappings, "
            "predefined test scenarios, or artificial tests created only to increase the coverage percentage."
        ),
        "description": (
            "Uses the actual JaCoCo report together with source-code analysis to dynamically identify and close meaningful JUnit coverage gaps."
        ),
    },
]

PROMPT_MAP: Dict[str, Dict[str, str]] = {item["id"]: item for item in PREDEFINED_JUNIT_PROMPTS}


def combine_junit_prompts(
    selected_prompt_ids: Optional[List[str]] = None,
    manual_prompt: Optional[str] = None,
) -> str:
    """Combines selected predefined prompt texts and/or manual prompt into a single cohesive testing prompt."""
    parts: List[str] = []

    if selected_prompt_ids:
        for pid in selected_prompt_ids:
            if pid in PROMPT_MAP:
                prompt_text = PROMPT_MAP[pid]["prompt"].strip()
                if prompt_text and prompt_text not in parts:
                    parts.append(prompt_text)

    if manual_prompt and manual_prompt.strip():
        m_prompt = manual_prompt.strip()
        if m_prompt not in parts:
            parts.append(f"Additional User Guidance: {m_prompt}")

    return "\n\n".join(parts).strip()
