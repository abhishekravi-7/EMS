"""Unit tests for Functional Document Grounding Engine and its 5 DoD criteria."""

from __future__ import annotations

from typing import Any
import pytest

from app.application.use_cases.proposed_tests.functional_document_grounding_engine import (
    FunctionalDocumentGroundingEngine,
)
from app.domain.models.proposed_test_models import (
    ApiTestSpec,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    TestCaseMetadata,
    UiTestSpec,
    ValidationStatus,
)


def _build_sample_evidence() -> dict[str, Any]:
    return {
        "endpoints": [
            {
                "method": "GET",
                "endpoint": "/api/employees",
                "class_name": "EmployeeController",
                "parameters": [],
                "request_body_sample": None,
            },
            {
                "method": "POST",
                "endpoint": "/api/employees",
                "class_name": "EmployeeController",
                "parameters": [],
                "request_body_sample": {
                    "firstName": "John",
                    "lastName": "Doe",
                    "email": "john@example.com",
                    "department": "Engineering",
                },
            },
            {
                "method": "GET",
                "endpoint": "/api/employees/{id}",
                "class_name": "EmployeeController",
                "parameters": [{"name": "id", "type": "Long"}],
                "request_body_sample": None,
            },
            {
                "method": "DELETE",
                "endpoint": "/api/employees/{id}",
                "class_name": "EmployeeController",
                "parameters": [{"name": "id", "type": "Long"}],
                "request_body_sample": None,
            },
        ],
        "ui_workflows": [
            {
                "name": "EmployeeList",
                "route": "/employees",
                "file": "EmployeeList.tsx",
                "grounded_selectors": ["table.employee-table", "button.add-btn", "input[name='search']"],
                "input_fields": [{"name": "search", "type": "text"}],
                "actions": ["navigate", "search", "click"],
            },
            {
                "name": "EmployeeForm",
                "route": "/employees/new",
                "file": "EmployeeForm.tsx",
                "grounded_selectors": ["form.employee-form", "button[type='submit']", "input[name='firstName']"],
                "input_fields": [
                    {"name": "firstName", "type": "text"},
                    {"name": "lastName", "type": "text"},
                    {"name": "email", "type": "email"},
                    {"name": "department", "type": "text"},
                ],
                "actions": ["navigate", "fill", "submit"],
            },
        ],
        "entities": [
            {
                "name": "Employee",
                "fields": [
                    {"name": "id", "type": "Long"},
                    {"name": "firstName", "type": "String"},
                    {"name": "lastName", "type": "String"},
                    {"name": "email", "type": "String"},
                    {"name": "department", "type": "String"},
                ],
            }
        ],
        "controllers": [{"name": "EmployeeController"}],
        "services": [{"name": "EmployeeService"}],
    }


def test_dod_1_grounded_scenarios_produce_real_executable_testcases():
    """DoD 1: Document whose scenarios genuinely describe real routes/endpoints/fields

    produces real, evidence-cited, executable testcases for those scenarios — and only those.
    """
    engine = FunctionalDocumentGroundingEngine()
    evidence = _build_sample_evidence()

    doc_text = """
FUNCTIONAL TESTING DOCUMENT
Version 1.0

1. Document Overview
This document outlines functional test scenarios for employee operations.

2. Scope
Testing CRUD operations on employees.

| TC ID | Module | Scenario | Steps / Data | Expected Result | Priority |
|---|---|---|---|---|---|
| TC-001 | Employee | Create valid employee | POST /api/employees with firstName, lastName, email, department | 201 Created; employee persisted | High |
| TC-002 | Employee UI | Fill and submit employee form | Navigate to /employees/new, enter firstName, lastName, click submit | Form submits successfully and redirects | High |
"""
    result = engine.process(doc_text, evidence)

    assert result["scenarios_extracted"] == 2
    assert len(result["matched"]) == 2
    assert len(result["unmatched"]) == 0
    assert len(result["partially_matched"]) == 0
    assert len(result["non_scenario_content_excluded"]) >= 2

    # Verify generated testcases are real, evidence-cited, executable
    api_tc = result["matched"][0]["generated_testcase"]
    assert api_tc["source"] == "functional_testing_document"
    assert api_tc["generation_source"] == "FUNCTIONAL_DOC"
    assert api_tc["status"] == "PROPOSED"
    assert api_tc["type"] == "API"
    assert api_tc["api_spec"]["endpoint"] == "/api/employees"
    assert api_tc["api_spec"]["method"] == "POST"
    assert "EmployeeController" in api_tc["metadata"]["expected_status_source"]
    assert api_tc["metadata"]["validation_status"] == "VALID"

    ui_tc = result["matched"][1]["generated_testcase"]
    assert ui_tc["source"] == "functional_testing_document"
    assert ui_tc["type"] == "UI"
    assert ui_tc["ui_spec"]["target_route"] == "/employees/new"
    assert "EmployeeForm" in ui_tc["metadata"]["evidence"][0]


def test_dod_2_different_application_document_produces_zero_executed_all_unmatched():
    """DoD 2: Document describing a different application produces zero executed testcases,

    with every scenario reported as UNMATCHED and a stated reason.
    """
    engine = FunctionalDocumentGroundingEngine()
    evidence = _build_sample_evidence()

    # Document describing an Airline / Flight Booking application
    flight_doc = """
FUNCTIONAL TESTING DOCUMENT - Airline Booking System

1. Scope
Flight reservation and passenger booking workflows.

| TC ID | Module | Scenario | Steps / Data | Expected Result | Priority |
|---|---|---|---|---|---|
| FL-001 | Booking | Search available flights | GET /api/flights?origin=JFK&destination=LHR | 200 OK with flight schedule list | High |
| FL-002 | Reservation | Confirm passenger seat | POST /api/bookings with flightNumber and passengerName | 201 Created with booking PNR | High |
| FL-003 | Flight UI | View seat selection map | Navigate to /flights/seat-map in browser | Seat selection grid renders | Medium |
"""
    result = engine.process(flight_doc, evidence)

    assert result["scenarios_extracted"] == 3
    # Exactly ZERO executed testcases from the document
    assert len(result["matched"]) == 0
    # Every scenario reported as UNMATCHED
    assert len(result["unmatched"]) == 3
    for un in result["unmatched"]:
        assert "No endpoint, controller, or entity matching" in un["reason"] or "No UI route" in un["reason"]


def test_dod_3_partially_matched_scenario_references_missing_detail_review_required():
    """DoD 3: A scenario that's almost right but references a detail not found in evidence

    is REVIEW_REQUIRED / PARTIALLY_MATCHED, not silently passed or silently dropped.
    """
    engine = FunctionalDocumentGroundingEngine()
    evidence = _build_sample_evidence()

    partial_doc = """
| TC ID | Module | Scenario | Steps / Data | Expected Result | Priority |
|---|---|---|---|---|---|
| TC-PART-1 | Employee | Update employee status via PATCH | PATCH /api/employees/123/status | 200 OK | High |
| TC-PART-2 | Employee | Create employee with passport | POST /api/employees with field 'passportNumber' | 201 Created | High |
| TC-PART-3 | Employee UI | Export employees to PDF | Navigate to /employees, click 'Export PDF' button | PDF downloads | Medium |
"""
    result = engine.process(partial_doc, evidence)

    assert result["scenarios_extracted"] == 3
    assert len(result["matched"]) == 0
    assert len(result["partially_matched"]) == 3

    # TC-PART-1: Endpoint /api/employees exists, but PATCH or status is missing
    p1 = result["partially_matched"][0]
    assert "PATCH" in p1["missing_detail"] or "status" in p1["missing_detail"]

    # TC-PART-2: Endpoint exists, but passportNumber is not in schema
    p2 = result["partially_matched"][1]
    assert "passportNumber" in p2["missing_detail"]

    # TC-PART-3: UI route /employees exists, but 'Export PDF' button is missing
    p3 = result["partially_matched"][2]
    assert "Export PDF" in p3["missing_detail"]


def test_dod_4_deduplication_against_existing_inventory():
    """DoD 4: No document-sourced testcase duplicates an existing LLM-generated one in inventory."""
    engine = FunctionalDocumentGroundingEngine()
    evidence = _build_sample_evidence()

    # Pre-existing LLM-generated testcase in inventory covering GET /api/employees
    existing_inventory = [
        ProposedTestCase(
            id="PTC-001",
            title="Verify GET /api/employees returns list",
            description="LLM test for employees",
            type=ProposedTestType.API,
            priority=ProposedTestPriority.HIGH,
            source="LLM Generated",
            reason="Code analysis",
            expected_result="200 OK",
            status=ProposedTestStatus.PROPOSED,
            metadata=TestCaseMetadata(
                test_id="PTC-001",
                endpoint="/api/employees",
                method="GET",
                parameters={},
                expected_status=200,
                expected_status_source="EmployeeController",
                authentication_required=False,
                authentication_source="Public",
                selector=None,
                selector_source=None,
                evidence=["EmployeeController"],
                dependencies=[],
                confidence=1.0,
                validation_status=ValidationStatus.VALID,
            ),
            api_spec=ApiTestSpec(
                method="GET",
                endpoint="/api/employees",
                expected_status=200,
            ),
        )
    ]

    doc_text = """
| TC ID | Module | Scenario | Steps / Data | Expected Result | Priority |
|---|---|---|---|---|---|
| TC-DUP | Employee | List all employees | GET /api/employees | 200 OK | High |
| TC-NEW | Employee | Delete employee by ID | DELETE /api/employees/101 | 200 OK | High |
"""
    result = engine.process(doc_text, evidence, existing_inventory=existing_inventory)

    assert result["scenarios_extracted"] == 2
    # TC-DUP is recognized as a duplicate and skipped
    assert len(result["skipped_as_duplicate_of_existing"]) == 1
    assert result["skipped_as_duplicate_of_existing"][0]["duplicate_of_id"] == "PTC-001"

    # Only TC-NEW is added as an executable testcase
    assert len(result["matched"]) == 1
    assert result["matched"][0]["generated_testcase"]["api_spec"]["method"] == "DELETE"


def test_dod_5_generic_matching_different_domain_no_hardcoding():
    """DoD 5: None of the extraction or matching logic is hardcoded.

    Testing on a completely different domain (Veterinary Clinic) produces correct classifications.
    """
    engine = FunctionalDocumentGroundingEngine()

    vet_evidence = {
        "endpoints": [
            {
                "method": "POST",
                "endpoint": "/api/v1/patients",
                "class_name": "PatientController",
                "request_body_sample": {"animalName": "Milo", "species": "Cat", "ownerPhone": "555-1234"},
            },
            {
                "method": "GET",
                "endpoint": "/api/v1/patients/{id}",
                "class_name": "PatientController",
                "parameters": [{"name": "id", "type": "UUID"}],
                "request_body_sample": None,
            },
        ],
        "ui_workflows": [
            {
                "name": "PatientRoster",
                "route": "/patients",
                "file": "PatientRoster.tsx",
                "grounded_selectors": ["table.patient-list", "button#checkin-btn"],
                "input_fields": [],
                "actions": ["navigate"],
            }
        ],
        "entities": [
            {
                "name": "Patient",
                "fields": [{"name": "animalName"}, {"name": "species"}, {"name": "ownerPhone"}],
            }
        ],
        "controllers": [{"name": "PatientController"}],
        "services": [{"name": "PatientService"}],
    }

    doc_text = """
1. Document Overview
Vet Clinic System Specification.

| TC ID | Module | Scenario | Steps / Data | Expected Result | Priority |
|---|---|---|---|---|---|
| VT-001 | Patient | Register new patient animal | POST /api/v1/patients with animalName and species | 201 Created | High |
| VT-002 | Unknown | Order auto parts inventory | POST /api/parts/order with partSku | 200 OK | Low |
| VT-003 | Patient | Register patient with microchip frequency | POST /api/v1/patients with field 'microchipFrequency' | 201 Created | Medium |
"""
    result = engine.process(doc_text, vet_evidence)

    assert result["scenarios_extracted"] == 3
    # VT-001: Genuine match for Vet Clinic evidence
    assert len(result["matched"]) == 1
    assert result["matched"][0]["generated_testcase"]["api_spec"]["endpoint"] == "/api/v1/patients"

    # VT-002: Auto parts scenario completely absent from Vet Clinic evidence
    assert len(result["unmatched"]) == 1
    assert "No endpoint, controller, or entity matching" in result["unmatched"][0]["reason"]

    # VT-003: Patient endpoint exists, but 'microchipFrequency' is not in evidence
    assert len(result["partially_matched"]) == 1
    assert "microchipFrequency" in result["partially_matched"][0]["missing_detail"]


def test_stage_1_multiple_document_formats():
    """Verify Stage 1 parses Gherkin, numbered lists, and prose while excluding non-scenario headers."""
    engine = FunctionalDocumentGroundingEngine()

    gherkin_and_prose = """
# Functional Testing Specification
Confidential document. Author: QA Team.

## Preconditions
1. Database is seeded.
2. Server is listening on 8080.

Scenario: Verify user logout clears session
  Given a user is logged into /dashboard
  When user clicks the 'Logout' button
  Then user is redirected to /login

1. Verify that sending GET /api/health returns HTTP status 200 OK.
2. Validate that POST /api/feedback without message body displays validation error.

The application shall provide high availability and 99.9% uptime across all cloud regions.
"""
    scenarios, excluded = engine.extract_scenarios(gherkin_and_prose)

    assert len(scenarios) >= 3
    assert any(s.implied_type == "UI" for s in scenarios)
    assert any(s.implied_type == "API" for s in scenarios)
    assert any("Preconditions" in ex or "Confidential" in ex or "uptime" in ex for ex in excluded)
