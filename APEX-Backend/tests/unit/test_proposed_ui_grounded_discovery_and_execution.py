"""Unit tests for Grounded UI Route Discovery, DOM Selectors Extraction, and Fragment Rejection."""

import http.server
import json
import shutil
import socketserver
import tempfile
import threading
from pathlib import Path
import pytest

from app.application.use_cases.proposed_tests.proposed_test_analyzer import ProposedTestAnalyzer
from app.application.use_cases.proposed_tests.proposed_test_generator import ProposedTestGenerator
from app.application.use_cases.proposed_tests.proposed_test_validator import ProposedTestValidator
from app.application.use_cases.proposed_tests.proposed_test_executor import (
    ProposedTestExecutor,
    resolve_migrated_app_url,
)
from app.domain.models.proposed_test_models import (
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
    UiTestSpec,
    ValidationStatus,
)


class MockPetClinicHandler(http.server.SimpleHTTPRequestHandler):
    """Simulates a running migrated Spring Boot MVC application (e.g. PetClinic)."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        if "/owners/find" in self.path:
            html = """
            <!DOCTYPE html>
            <html>
            <head><title>PetClinic :: Find Owners</title></head>
            <body>
                <nav class="navbar navbar-expand-lg" id="main-navbar">
                    <div class="container-fluid"><a class="navbar-brand" href="/"><span>PetClinic</span></a></div>
                </nav>
                <div class="container-fluid">
                    <h2>Find Owners</h2>
                    <form id="search-owner-form" action="/owners" method="get">
                        <div id="lastNameGroup">
                            <label>Last name: <input type="text" name="lastName" id="lastName" value="Franklin" /></label>
                        </div>
                        <button type="submit" class="btn-primary" id="find-owner-btn">Find Owner</button>
                    </form>
                </div>
            </body>
            </html>
            """
        elif "/vets.html" in self.path or "/vets" in self.path:
            html = """
            <!DOCTYPE html>
            <html>
            <head><title>PetClinic :: Veterinarians</title></head>
            <body>
                <nav id="main-navbar"><div class="container-fluid"><span>PetClinic</span></div></nav>
                <div class="container-fluid">
                    <h2>Veterinarians</h2>
                    <table id="vets" class="table table-striped">
                        <thead><tr><th>Name</th><th>Specialties</th></tr></thead>
                        <tbody><tr><td>James Carter</td><td>none</td></tr></tbody>
                    </table>
                </div>
            </body>
            </html>
            """
        else:
            # Home / Welcome route (/)
            html = """
            <!DOCTYPE html>
            <html>
            <head><title>PetClinic :: Welcome</title></head>
            <body>
                <nav id="main-navbar"><div class="container-fluid"><a class="navbar-brand" href="/">PetClinic</a></div></nav>
                <div class="container-fluid">
                    <h2>Welcome to PetClinic</h2>
                    <div class="row"><p>Application is up and running.</p></div>
                </div>
            </body>
            </html>
            """
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def running_petclinic_server():
    """Starts a live HTTP server in a background thread simulating the migrated PetClinic app."""
    server = socketserver.TCPServer(("127.0.0.1", 0), MockPetClinicHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def mock_petclinic_workspace(tmp_path):
    """Creates a realistic Spring Boot repository with controllers, views, and fragments."""
    repo = tmp_path / "petclinic_repo"
    repo.mkdir(parents=True, exist_ok=True)

    # application.properties
    (repo / "application.properties").write_text("server.port=8080\n", encoding="utf-8")

    # Controller Java source
    src_dir = repo / "src" / "main" / "java" / "org" / "springframework" / "samples" / "petclinic"
    src_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "WelcomeController.java").write_text(
        """
        package org.springframework.samples.petclinic;
        import org.springframework.stereotype.Controller;
        import org.springframework.web.bind.annotation.GetMapping;

        @Controller
        class WelcomeController {
            @GetMapping("/")
            public String welcome() { return "welcome"; }
        }
        """,
        encoding="utf-8",
    )

    (src_dir / "OwnerController.java").write_text(
        """
        package org.springframework.samples.petclinic;
        import org.springframework.stereotype.Controller;
        import org.springframework.web.bind.annotation.GetMapping;

        @Controller
        class OwnerController {
            @GetMapping("/owners/find")
            public String initFindForm() { return "owners/findOwners"; }

            @GetMapping("/owners/new")
            public String initCreationForm() { return "owners/createOrUpdateOwnerForm"; }
        }
        """,
        encoding="utf-8",
    )

    (src_dir / "VetController.java").write_text(
        """
        package org.springframework.samples.petclinic;
        import org.springframework.stereotype.Controller;
        import org.springframework.web.bind.annotation.GetMapping;

        @Controller
        class VetController {
            @GetMapping("/vets.html")
            public String showVetList() { return "vets/vetList"; }
        }
        """,
        encoding="utf-8",
    )

    # Templates directory
    tmpl_dir = repo / "src" / "main" / "resources" / "templates"
    (tmpl_dir / "fragments").mkdir(parents=True, exist_ok=True)
    (tmpl_dir / "owners").mkdir(parents=True, exist_ok=True)
    (tmpl_dir / "vets").mkdir(parents=True, exist_ok=True)

    # 1. Top-level template: welcome.html
    (tmpl_dir / "welcome.html").write_text(
        """
        <!DOCTYPE html>
        <html>
        <body>
            <h2>Welcome to PetClinic</h2>
            <div class="row">Welcome body</div>
        </body>
        </html>
        """,
        encoding="utf-8",
    )

    # 2. View template: findOwners.html
    (tmpl_dir / "owners" / "findOwners.html").write_text(
        """
        <!DOCTYPE html>
        <html>
        <body>
            <h2>Find Owners</h2>
            <form id="search-owner-form" action="/owners" method="get">
                <input class="form-control" name="lastName" size="30" />
                <button type="submit" class="btn btn-primary">Find Owner</button>
            </form>
        </body>
        </html>
        """,
        encoding="utf-8",
    )

    # 3. View template: vetList.html
    (tmpl_dir / "vets" / "vetList.html").write_text(
        """
        <!DOCTYPE html>
        <html>
        <body>
            <h2>Veterinarians</h2>
            <table id="vets" class="table table-striped">
                <thead><tr><th>Name</th></tr></thead>
            </table>
        </body>
        </html>
        """,
        encoding="utf-8",
    )

    # 4. Internal fragments (SHOULD NOT become standalone test routes like /footer, /head, /header, /preheader)
    (tmpl_dir / "fragments" / "layout.html").write_text(
        '<html th:fragment="layout"><head></head><body><div th:insert="${template}"></div></body></html>',
        encoding="utf-8",
    )
    (tmpl_dir / "fragments" / "header.html").write_text(
        '<div th:fragment="header"><header id="main-header">App Header</header></div>',
        encoding="utf-8",
    )
    (tmpl_dir / "fragments" / "footer.html").write_text(
        '<div th:fragment="footer"><footer>App Footer</footer></div>',
        encoding="utf-8",
    )
    (tmpl_dir / "fragments" / "head.html").write_text(
        '<head th:fragment="head"><meta charset="utf-8"></head>',
        encoding="utf-8",
    )
    (tmpl_dir / "fragments" / "preheader.html").write_text(
        '<div th:fragment="preheader"><p>Banner</p></div>',
        encoding="utf-8",
    )
    (tmpl_dir / "fragments" / "inputField.html").write_text(
        '<div th:fragment="input (label, name, type)"><input th:name="${name}"/></div>',
        encoding="utf-8",
    )

    return repo


def test_ui_route_discovery_excludes_fragments_and_includes_navigable_pages(mock_petclinic_workspace):
    """Verify analyzer discovers actual routes (/, /owners/find, /vets.html) and ignores fragments (/footer, /head, etc)."""
    analyzer = ProposedTestAnalyzer(mock_petclinic_workspace)
    analysis = analyzer.analyze()

    ui_workflows = analysis["ui_workflows"]
    routes = [u["route"] for u in ui_workflows]

    # Verify navigable routes are found
    assert "/" in routes or "/welcome" in routes
    assert "/owners/find" in routes
    assert "/vets.html" in routes or "/vets" in routes

    # Verify unrouted fragments (/footer, /head, /header, /preheader, /inputfield, /layout) are NOT present
    for bad_route in ["/footer", "/head", "/header", "/preheader", "/inputfield", "/layout", "/selectfield"]:
        assert bad_route not in routes, f"Fragment route {bad_route} should not be treated as a standalone UI workflow!"


def test_ui_proposals_grounded_in_real_dom_selectors(mock_petclinic_workspace):
    """Verify generated UI proposals use real template DOM selectors and NO data-testid='main-container'."""
    analyzer = ProposedTestAnalyzer(mock_petclinic_workspace)
    analysis = analyzer.analyze()

    generator = ProposedTestGenerator(analysis)
    proposals = generator.generate()

    ui_tests = [p for p in proposals if p.type == ProposedTestType.UI]
    assert len(ui_tests) >= 2

    for ui_test in ui_tests:
        spec = ui_test.ui_spec
        assert spec is not None
        assert spec.target_route not in ["/footer", "/head", "/header", "/preheader", "/layout", "/inputfield"]

        # Assert no blind fake selector [data-testid="main-container"]
        for sel in spec.expected_elements:
            assert "[data-testid='main-container']" not in sel
            assert "[data-testid=\"main-container\"]" not in sel

    # Specifically check findOwners UI test
    find_owner_tests = [t for t in ui_tests if "/owners/find" in t.ui_spec.target_route]
    if find_owner_tests:
        fot = find_owner_tests[0]
        # Must have grounded form or h2 or input selector
        assert any(s in ["form#search-owner-form", "form", "h2", "input[name='lastName']"] for s in fot.ui_spec.expected_elements)


def test_validator_rejects_unrouted_fragments_and_ungrounded_selectors(mock_petclinic_workspace):
    """Verify validator flags fragment routes as INVALID and ungrounded selectors as PARTIALLY_VALID."""
    analyzer = ProposedTestAnalyzer(mock_petclinic_workspace)
    analysis = analyzer.analyze()
    validator = ProposedTestValidator(mock_petclinic_workspace, analysis_data=analysis)

    # 1. Unrouted fragment /footer test -> INVALID
    fragment_test = ProposedTestCase(
        id="PTC-FRAG-01",
        title="Playwright UI: Test Footer Fragment",
        description="Check footer",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.LOW,
        source="FooterComponent",
        reason="Fragment test",
        expected_result="Rendered",
        ui_spec=UiTestSpec(target_route="/footer", expected_elements=["footer"]),
    )
    val_frag = validator.validate_test_case(fragment_test)
    assert val_frag.status == ValidationStatus.INVALID
    assert val_frag.playwright_executable is False
    assert "internal UI fragment" in val_frag.issue

    # 2. Test with hallucinated selector [data-testid="main-container"] -> PARTIALLY_VALID (not executable)
    fake_selector_test = ProposedTestCase(
        id="PTC-FAKE-SEL-01",
        title="Playwright UI: Test Find Owners with fake selector",
        description="Check find owners",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="OwnerController",
        reason="Find owners test",
        expected_result="Rendered",
        ui_spec=UiTestSpec(target_route="/owners/find", expected_elements=["[data-testid='main-container']"]),
    )
    val_fake = validator.validate_test_case(fake_selector_test)
    assert val_fake.status == ValidationStatus.PARTIALLY_VALID
    assert val_fake.playwright_executable is False
    assert "main-container" in val_fake.issue

    # 3. Grounded UI test with real route and real selector -> VALID (executable)
    grounded_test = ProposedTestCase(
        id="PTC-GROUNDED-01",
        title="Playwright UI: Test Find Owners Page",
        description="Check find owners with real selectors",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="OwnerController",
        reason="Find owners test",
        expected_result="Rendered",
        ui_spec=UiTestSpec(
            target_route="/owners/find",
            expected_elements=["form#search-owner-form", "h2"],
        ),
    )
    val_grounded = validator.validate_test_case(grounded_test)
    assert val_grounded.status == ValidationStatus.VALID
    assert val_grounded.playwright_executable is True
    assert val_grounded.issue is None


def test_real_playwright_execution_against_migrated_petclinic_app(running_petclinic_server, tmp_path):
    """End-to-end execution of grounded UI test with real Playwright against live PetClinic server."""
    evidence_dir = tmp_path / "evidence"
    executor = ProposedTestExecutor(
        job_id="mig-petclinic-job",
        evidence_dir=evidence_dir,
        base_url=running_petclinic_server,
    )

    ui_test = ProposedTestCase(
        id="PTC-PETCLINIC-FIND-OWNERS",
        title="Playwright UI: Verify Find Owners Workflow",
        description="Navigate to /owners/find, fill lastName, submit form, verify DOM elements",
        type=ProposedTestType.UI,
        priority=ProposedTestPriority.HIGH,
        source="OwnerController",
        reason="Verify owners search page",
        expected_result="Search form and headings visible",
        ui_spec=UiTestSpec(
            target_route="/owners/find",
            input_fields=[{"name": "lastName", "type": "text"}],
            actions=["click button[type='submit']"],
            expected_elements=["form#search-owner-form", "h2"],
        ),
    )

    res = executor.execute_test(ui_test)
    if res.status != ProposedTestStatus.PASSED:
        print(f"FAILED ERROR: {res.error}")
        print(f"STACK TRACE: {res.stack_trace}")
        print(f"STDOUT: {res.stdout}")
    assert res.status == ProposedTestStatus.PASSED
    assert res.error is None
    assert res.evidence.screenshot_available is True

    # Verify PNG screenshot on disk
    screenshot_file = evidence_dir / "PTC-PETCLINIC-FIND-OWNERS" / "screenshot.png"
    assert screenshot_file.exists()
    raw_bytes = screenshot_file.read_bytes()
    assert raw_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(raw_bytes) > 1000

    # Verify step log
    log_file = evidence_dir / "PTC-PETCLINIC-FIND-OWNERS" / "browser_steps.log"
    assert log_file.exists()
    log_text = log_file.read_text(encoding="utf-8")
    assert "form#search-owner-form" in log_text
    assert "Captured real full-page PNG screenshot" in log_text
