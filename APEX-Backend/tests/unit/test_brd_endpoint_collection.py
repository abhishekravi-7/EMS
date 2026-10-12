import tempfile
from pathlib import Path
from app.application.use_cases.generate_technical_document import GenerateTechnicalDocumentUseCase
from app.infrastructure.analyzers.microservice.java_class_scanner import JavaClassInfo, JavaEndpoint
from app.schemas.document_schema import TechnicalDocumentRequest
from unittest.mock import MagicMock


def test_document_instructions_are_selected_by_document_type():
    technical_request = TechnicalDocumentRequest(
        document_type="TECHNICAL_SPECIFICATION",
        brd_instructions="BRD instructions",
        technical_specification_instructions="Technical specification instructions",
    )
    brd_request = TechnicalDocumentRequest(
        document_type="BRD",
        brd_instructions="BRD instructions",
        technical_specification_instructions="Technical specification instructions",
    )

    assert GenerateTechnicalDocumentUseCase._get_effective_brd_instructions(
        technical_request
    ) == "Technical specification instructions"
    assert GenerateTechnicalDocumentUseCase._get_effective_brd_instructions(brd_request) == "BRD instructions"


def test_collect_endpoints_with_java_endpoints():
    uc = GenerateTechnicalDocumentUseCase()
    classes = [
        JavaClassInfo(
            relative_path="com/example/UserController.java",
            package="com.example",
            class_name="UserController",
            annotations={"RestController", "RequestMapping"},
            endpoints=[
                JavaEndpoint(method="GET", path="/api/users"),
                JavaEndpoint(method="POST", path="/api/users"),
            ],
        )
    ]
    analysis = MagicMock()
    eps = uc._collect_endpoints(analysis, classes)
    assert len(eps) == 2
    assert eps[0]["method"] == "GET"
    assert eps[0]["path"] == "/api/users"
    assert eps[0]["controller"] == "UserController"
    assert eps[0]["line_start"] is None
    assert eps[0]["line_end"] is None
    assert eps[1]["method"] == "POST"
    assert eps[1]["path"] == "/api/users"


def test_full_technical_document_generation_with_endpoints():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = Path(tmp_dir)
        src_dir = repo_path / "src" / "main" / "java" / "com" / "example"
        src_dir.mkdir(parents=True)

        pom = repo_path / "pom.xml"
        pom.write_text(
            """<project>
    <groupId>com.example</groupId>
    <artifactId>demo-app</artifactId>
    <version>1.0.0</version>
</project>""",
            encoding="utf-8",
        )

        controller = src_dir / "DemoController.java"
        controller.write_text(
            """package com.example;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class DemoController {
    @GetMapping("/api/items")
    public String getItems() {
        return "items";
    }
}
""",
            encoding="utf-8",
        )

        uc = GenerateTechnicalDocumentUseCase()
        req = TechnicalDocumentRequest(repository_url=str(repo_path))
        res = uc.execute(req)

        assert res.get("filename") is not None
        assert res.get("document_type") == "TECHNICAL_SPECIFICATION"
        assert len(res.get("html", "")) > 0
        assert "DemoController" in res.get("html", "")


def test_full_brd_document_generation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = Path(tmp_dir)
        src_dir = repo_path / "src" / "main" / "java" / "com" / "example"
        src_dir.mkdir(parents=True)

        pom = repo_path / "pom.xml"
        pom.write_text(
            """<project>
    <groupId>com.example</groupId>
    <artifactId>demo-app</artifactId>
    <version>1.0.0</version>
</project>""",
            encoding="utf-8",
        )

        readme = repo_path / "README.md"
        readme.write_text("# Demo Application\nSample business workflow and API routes documentation.")

        controller = src_dir / "DemoController.java"
        controller.write_text(
            """package com.example;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class DemoController {
    @GetMapping("/api/items")
    public String getItems() {
        return "items";
    }
}
""",
            encoding="utf-8",
        )

        uc = GenerateTechnicalDocumentUseCase()
        req = TechnicalDocumentRequest(repository_url=str(repo_path), document_type="BRD")
        res = uc.execute(req)

        assert res.get("filename") is not None
        assert len(res.get("html", "")) > 0
        assert "DemoController" in res.get("html", "") or "demo-app" in res.get("html", "")
