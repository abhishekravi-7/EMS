"""Unit tests for BRD document upload, parsing, workflow extraction, and combined proposed test generation."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi import UploadFile

from app.api.v1.endpoints.discovery_controller import (
    delete_brd_document,
    get_brd_document_metadata,
    upload_brd_document,
    view_brd_document,
)
from app.application.use_cases.proposed_tests.brd_analyzer import BrdAnalyzer
from app.application.use_cases.proposed_tests.proposed_test_generator import ProposedTestGenerator
from app.application.use_cases.proposed_tests.proposed_test_service import ProposedTestService
from app.domain.models.proposed_test_models import ProposedTestCase
from app.infrastructure.persistence.models import User

SAMPLE_BRD_TEXT = """# Business Requirements Document (BRD) - E-Commerce Migration

## 1. Executive Summary
This document specifies the business requirements and core workflows for the Java APEX Retail System.

## 2. Functional Requirements

FR-101: Customer Authentication & Single Sign-On
- Users must be able to log in using valid email credentials.
- Acceptance Criteria: System verifies JWT token and redirects to Dashboard.

FR-102: Product Catalog Search & Filtering
- Customers can search products by category, price, and keyword.
- Acceptance Criteria: Results return within 500ms with pagination.

FR-103: Order Checkout & Payment Processing
- Customers can add items to cart, select delivery address, and pay.
- Acceptance Criteria: On payment success, order status becomes CONFIRMED.

## 3. Business Workflows

Workflow 1: Customer Login Journey
1. User navigates to login page
2. User enters registered email and password
3. System validates credentials against authentication service
4. System issues access token and loads user profile

Workflow 2: Checkout and Payment Flow
Customer Login -> Search Product -> Add Product to Cart -> Checkout -> Payment -> Order Confirmation

Workflow 3: Invalid Payment Rejection
1. Customer initiates payment with expired credit card
2. Payment gateway rejects transaction
3. System displays validation error code 400
"""


def test_brd_analyzer_markdown_extraction():
    with TemporaryDirectory() as tmpdir:
        brd_path = Path(tmpdir) / "sample_brd.md"
        brd_path.write_text(SAMPLE_BRD_TEXT, encoding="utf-8")

        analyzer = BrdAnalyzer(brd_path, job_id="job_test_001")
        result = analyzer.extract()

        assert result.error is None
        assert len(result.requirements) >= 3
        assert any(r.id == "FR-101" for r in result.requirements)
        assert any(r.id == "FR-102" for r in result.requirements)

        assert len(result.workflows) == 3
        login_wf = next((w for w in result.workflows if "Login" in w.name), None)
        assert login_wf is not None
        assert len(login_wf.steps) >= 3
        assert login_wf.priority == "HIGH"


def test_brd_analyzer_docx_extraction():
    with TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "test_spec.docx"

        # Create a synthetic docx archive
        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body>
            <w:p><w:t>FR-201: User Profile Management</w:t></w:p>
            <w:p><w:t>Requirement to update user address and email settings.</w:t></w:p>
            <w:p><w:t>Workflow: Profile Edit Journey</w:t></w:p>
            <w:p><w:t>1. Open Profile Page</w:t></w:p>
            <w:p><w:t>2. Modify user address field</w:t></w:p>
            <w:p><w:t>3. Submit update form</w:t></w:p>
          </w:body>
        </w:document>"""

        with zipfile.ZipFile(docx_path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)

        analyzer = BrdAnalyzer(docx_path, job_id="job_test_docx")
        result = analyzer.extract()

        assert result.error is None
        assert len(result.requirements) >= 1
        assert any(r.id == "FR-201" for r in result.requirements)


def test_brd_analyzer_xlsx_extraction():
    with TemporaryDirectory() as tmpdir:
        xlsx_path = Path(tmpdir) / "business_spec.xlsx"

        # Create a multi-sheet synthetic xlsx archive with sharedStrings, workbook, and multiple worksheets
        with zipfile.ZipFile(xlsx_path, "w") as zf:
            # Shared strings
            shared_strings_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="7" uniqueCount="7">
                <si><t>Requirement ID</t></si>
                <si><t>FR-301: Payment Gateway Integration</t></si>
                <si><t>Payment processing workflow with tokenized cards</t></si>
                <si><t>Workflow 1: Checkout Payment Flow</t></si>
                <si><t>1. User selects payment method</t></si>
                <si><t>2. Card is authorized</t></si>
                <si><t>3. Order confirmed</t></si>
            </sst>"""
            zf.writestr("xl/sharedStrings.xml", shared_strings_xml)

            # Workbook
            wb_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                <sheets>
                    <sheet name="Requirements" sheetId="1" r:id="rId1"/>
                    <sheet name="Workflows" sheetId="2" r:id="rId2"/>
                </sheets>
            </workbook>"""
            zf.writestr("xl/workbook.xml", wb_xml)

            # Worksheet 1: Requirements
            sheet1_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                <sheetData>
                    <row r="1">
                        <c r="A1" t="s"><v>0</v></c>
                        <c r="B1" t="s"><v>1</v></c>
                    </row>
                    <row r="2">
                        <c r="A2" t="s"><v>2</v></c>
                    </row>
                </sheetData>
            </worksheet>"""
            zf.writestr("xl/worksheets/sheet1.xml", sheet1_xml)

            # Worksheet 2: Workflows
            sheet2_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                <sheetData>
                    <row r="1">
                        <c r="A1" t="s"><v>3</v></c>
                    </row>
                    <row r="2">
                        <c r="A2" t="s"><v>4</v></c>
                    </row>
                    <row r="3">
                        <c r="A3" t="s"><v>5</v></c>
                    </row>
                    <row r="4">
                        <c r="A4" t="s"><v>6</v></c>
                    </row>
                </sheetData>
            </worksheet>"""
            zf.writestr("xl/worksheets/sheet2.xml", sheet2_xml)

        analyzer = BrdAnalyzer(xlsx_path, job_id="job_test_xlsx")
        result = analyzer.extract()

        assert result.error is None
        assert len(result.requirements) >= 1
        assert any("FR-301" in r.id or "301" in r.title for r in result.requirements)
        assert len(result.workflows) >= 1
        assert any("Checkout" in w.name or "Payment" in w.name for w in result.workflows)


def test_brd_analyzer_xls_xml_extraction():
    with TemporaryDirectory() as tmpdir:
        xls_path = Path(tmpdir) / "business_spec.xls"

        # Create XML Spreadsheet 2003 format
        xml_spreadsheet = """<?xml version="1.0"?>
        <Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
                  xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
            <Worksheet ss:Name="Requirements">
                <Table>
                    <Row>
                        <Cell><Data ss:Type="String">FR-401: Order Fulfillment</Data></Cell>
                        <Cell><Data ss:Type="String">Warehouse dispatch and tracking notification</Data></Cell>
                    </Row>
                    <Row>
                        <Cell><Data ss:Type="String">Workflow 1: Order Dispatch Journey</Data></Cell>
                        <Cell><Data ss:Type="String">1. Pick items -> 2. Pack box -> 3. Ship order</Data></Cell>
                    </Row>
                </Table>
            </Worksheet>
        </Workbook>"""
        xls_path.write_text(xml_spreadsheet, encoding="utf-8")

        analyzer = BrdAnalyzer(xls_path, job_id="job_test_xls")
        result = analyzer.extract()

        assert result.error is None
        assert len(result.requirements) >= 1
        assert any("FR-401" in r.id or "401" in r.title for r in result.requirements)
        assert len(result.workflows) >= 1


def test_brd_analyzer_empty_file():
    with TemporaryDirectory() as tmpdir:
        empty_path = Path(tmpdir) / "empty.txt"
        empty_path.write_text("", encoding="utf-8")

        analyzer = BrdAnalyzer(empty_path, job_id="job_test_empty")
        result = analyzer.extract()

        assert result.error is not None
        assert "empty" in result.error.lower()


def test_proposed_test_generator_with_brd_and_deduplication():
    with TemporaryDirectory() as tmpdir:
        brd_path = Path(tmpdir) / "spec.md"
        brd_path.write_text(SAMPLE_BRD_TEXT, encoding="utf-8")

        analyzer = BrdAnalyzer(brd_path, job_id="job_test_gen")
        brd_res = analyzer.extract()

        # Simulated codebase AST analysis with an overlapping auth endpoint and distinct product endpoint
        code_analysis = {
            "endpoints": [
                {
                    "method": "POST",
                    "endpoint": "/api/v1/auth/login",
                    "class_name": "AuthController",
                    "source": "AuthController",
                },
                {
                    "method": "GET",
                    "endpoint": "/api/v1/inventory/items",
                    "class_name": "InventoryController",
                    "source": "InventoryController",
                },
            ],
            "services": [
                {
                    "name": "PaymentService",
                    "methods": [{"name": "processPayment", "return_type": "PaymentResult", "params": "PaymentRequest req"}],
                }
            ],
            "ui_workflows": [],
            "existing_coverage": {"methods": [], "classes": [], "scenarios": []},
        }

        generator = ProposedTestGenerator(code_analysis, brd_analysis=brd_res)
        proposals = generator.generate()

        assert len(proposals) > 0

        # Check source attribution
        sources = {p.generation_source for p in proposals}
        assert "BRD_AND_AI" in sources or "BRD_DOCUMENT" in sources

        # Verify requirement traceability in reasons
        brd_proposals = [p for p in proposals if "BRD" in p.generation_source]
        assert len(brd_proposals) > 0
        for bp in brd_proposals:
            assert bp.reason != ""
            assert bp.id.startswith("PTC-")

        # Verify sequential unique IDs
        ids = [p.id for p in proposals]
        assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_brd_upload_and_service_lifecycle():
    with TemporaryDirectory() as tmpdir:
        job_id = "test_brd_job_123"
        job_dir = Path(tmpdir) / job_id
        job_dir.mkdir(parents=True)

        from app.application.services.status_service import _REPORT_CACHE
        _REPORT_CACHE[job_id] = {"status": "DISCOVERY_COMPLETED"}

        mock_user = User(id=1, email="test@example.com")

        # 1. Upload valid BRD file
        file_content = SAMPLE_BRD_TEXT.encode("utf-8")
        upload_file = UploadFile(
            file=io.BytesIO(file_content),
            filename="retail_spec.md",
            headers={"content-type": "text/markdown"},
        )

        # Mock WorkspacePaths storage_dir to tmpdir
        import app.api.v1.endpoints.discovery_controller as dc
        original_wp = dc.WorkspacePaths

        class TempWorkspacePaths(original_wp):
            def __init__(self, j_id: str, storage_dir: Path | None = None) -> None:
                super().__init__(j_id, storage_dir=Path(tmpdir))

        dc.WorkspacePaths = TempWorkspacePaths

        try:
            res = await upload_brd_document(job_id=job_id, file=upload_file, current_user=mock_user, db=None)
            assert res.status_code == 200
            data = json.loads(res.body.decode("utf-8"))
            assert data["filename"] == "retail_spec.md"
            assert data["status"] == "UPLOADED"

            # 2. Get BRD metadata
            meta_res = await get_brd_document_metadata(job_id=job_id, current_user=mock_user, db=None)
            assert meta_res.status_code == 200
            meta_data = json.loads(meta_res.body.decode("utf-8"))
            assert meta_data["filename"] == "retail_spec.md"

            # 3. View BRD file content
            view_res = await view_brd_document(job_id=job_id, current_user=mock_user, db=None)
            assert view_res.status_code == 200
            assert view_res.body == file_content
            assert 'inline; filename="retail_spec.md"' in view_res.headers["content-disposition"]

            # 4. Generate proposed tests through service with uploaded BRD
            service = ProposedTestService()
            service._get_job_dir = lambda j: Path(tmpdir) / j

            import app.application.use_cases.proposed_tests.proposed_test_service as pts
            pts.WorkspacePaths = TempWorkspacePaths

            proposals = service.generate_proposed_tests(job_id)
            assert len(proposals) > 0
            assert any("BRD" in p.generation_source for p in proposals)

            # Check metrics
            status = service.get_status(job_id)
            metrics = status["metrics"]
            assert metrics["total"] == len(proposals)
            assert metrics["ai_generated_count"] + metrics["brd_generated_count"] == metrics["total"]
            assert metrics["brd_generated_count"] > 0

            # 4. Delete BRD
            del_res = await delete_brd_document(job_id=job_id, current_user=mock_user, db=None)
            assert del_res.status_code == 200
            del_data = json.loads(del_res.body.decode("utf-8"))
            assert del_data["status"] == "DELETED"

        finally:
            dc.WorkspacePaths = original_wp


def test_proposed_test_source_counting_scenarios():
    service = ProposedTestService()

    # 1. AI-only test cases
    ai_only = [
        ProposedTestCase(
            id="PTC-001",
            title="Test 1",
            description="",
            type="API",
            priority="HIGH",
            source="Controller",
            reason="AI Gap",
            expected_result="OK",
            generation_source="AI_GENERATED",
        ),
        ProposedTestCase(
            id="PTC-002",
            title="Test 2",
            description="",
            type="API",
            priority="MEDIUM",
            source="Controller",
            reason="AI Gap",
            expected_result="OK",
            generation_source="AI_GENERATED",
        ),
    ]
    m1 = service._compute_metrics(ai_only)
    assert m1.total == 2
    assert m1.ai_generated_count == 2
    assert m1.brd_generated_count == 0

    # 2. BRD-only test cases
    brd_only = [
        ProposedTestCase(
            id="PTC-001",
            title="BRD Test 1",
            description="",
            type="UI",
            priority="HIGH",
            source="BRD Document",
            reason="BRD Spec",
            expected_result="OK",
            generation_source="BRD_DOCUMENT",
        ),
    ]
    m2 = service._compute_metrics(brd_only)
    assert m2.total == 1
    assert m2.ai_generated_count == 0
    assert m2.brd_generated_count == 1

    # 3. Deduplicated / Combined test cases (BRD_AND_AI)
    combined = [
        ProposedTestCase(
            id="PTC-001",
            title="Merged Login",
            description="",
            type="API",
            priority="HIGH",
            source="AuthController",
            reason="Both AI and BRD",
            expected_result="OK",
            generation_source="BRD_AND_AI",
        ),
        ProposedTestCase(
            id="PTC-002",
            title="Pure AI Test",
            description="",
            type="API",
            priority="MEDIUM",
            source="ProductController",
            reason="AI Gap",
            expected_result="OK",
            generation_source="AI_GENERATED",
        ),
        ProposedTestCase(
            id="PTC-003",
            title="Pure BRD Test",
            description="",
            type="UI",
            priority="HIGH",
            source="BRD Document",
            reason="BRD Spec",
            expected_result="OK",
            generation_source="BRD_DOCUMENT",
        ),
    ]
    m3 = service._compute_metrics(combined)
    assert m3.total == 3
    assert m3.ai_generated_count == 2  # 1 AI + 1 Merged BRD_AND_AI
    assert m3.brd_generated_count == 1  # 1 Pure BRD
    assert m3.ai_generated_count + m3.brd_generated_count == m3.total

    # 4. Empty test cases list
    m4 = service._compute_metrics([])
    assert m4.total == 0
    assert m4.ai_generated_count == 0
    assert m4.brd_generated_count == 0


@pytest.mark.asyncio
async def test_brd_upload_validation_rejects_spoofed_or_exe_content():
    from fastapi import HTTPException
    from app.application.services.status_service import _REPORT_CACHE
    mock_user = User(id=1, email="test@example.com")
    job_id = "job_test_security"
    _REPORT_CACHE[job_id] = {"status": "DISCOVERY_COMPLETED"}

    with TemporaryDirectory() as tmpdir:
        import app.api.v1.endpoints.discovery_controller as dc
        original_wp = dc.WorkspacePaths

        class TempWorkspacePaths(original_wp):
            def __init__(self, j_id: str, storage_dir: Path | None = None) -> None:
                super().__init__(j_id, storage_dir=Path(tmpdir))

        dc.WorkspacePaths = TempWorkspacePaths

        try:
            # 1. Executable with MZ header rejected
            exe_file = UploadFile(
                file=io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"),
                size=8,
                filename="payload.exe",
                headers={"content-type": "application/x-msdownload"},
            )
            with pytest.raises(HTTPException) as exc_info:
                await upload_brd_document(job_id=job_id, file=exe_file, current_user=mock_user, db=None)
            assert exc_info.value.status_code == 400

            # 2. Spoofed PDF with text content rejected
            spoofed_pdf = UploadFile(
                file=io.BytesIO(b"This is just plain text, not a PDF!"),
                size=35,
                filename="fake.pdf",
                headers={"content-type": "application/pdf"},
            )
            with pytest.raises(HTTPException) as exc_info:
                await upload_brd_document(job_id=job_id, file=spoofed_pdf, current_user=mock_user, db=None)
            assert exc_info.value.status_code == 400
            assert "Invalid PDF" in str(exc_info.value.detail)

            # 3. Spoofed DOCX with non-ZIP content rejected
            spoofed_docx = UploadFile(
                file=io.BytesIO(b"Not a zip archive"),
                size=17,
                filename="fake.docx",
                headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
            )
            with pytest.raises(HTTPException) as exc_info:
                await upload_brd_document(job_id=job_id, file=spoofed_docx, current_user=mock_user, db=None)
            assert exc_info.value.status_code == 400
            assert "Invalid .docx" in str(exc_info.value.detail)

            # 4. Spoofed XLSX with non-ZIP content rejected
            spoofed_xlsx = UploadFile(
                file=io.BytesIO(b"Not a zip spreadsheet"),
                size=22,
                filename="fake.xlsx",
                headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            )
            with pytest.raises(HTTPException) as exc_info:
                await upload_brd_document(job_id=job_id, file=spoofed_xlsx, current_user=mock_user, db=None)
            assert exc_info.value.status_code == 400
            assert "Invalid .xlsx" in str(exc_info.value.detail)

            # 5. Unsupported file type rejected
            unsupported = UploadFile(
                file=io.BytesIO(b"col1,col2\n1,2"),
                size=13,
                filename="data.csv",
                headers={"content-type": "text/csv"},
            )
            with pytest.raises(HTTPException) as exc_info:
                await upload_brd_document(job_id=job_id, file=unsupported, current_user=mock_user, db=None)
            assert exc_info.value.status_code == 400
            assert "Unsupported file format" in str(exc_info.value.detail)

            # 6. Valid PDF accepted
            valid_pdf = UploadFile(
                file=io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"),
                size=45,
                filename="valid.pdf",
                headers={"content-type": "application/pdf"},
            )
            res = await upload_brd_document(job_id=job_id, file=valid_pdf, current_user=mock_user, db=None)
            assert res.status_code == 200

        finally:
            dc.WorkspacePaths = original_wp

