"""Integration tests for FastAPI unit test endpoints using TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_JAVA_SOURCE = """
package com.example.service;

public class OrderService {
    public double calculateTotal(double price, int quantity) {
        if (price < 0 || quantity < 0) {
            throw new IllegalArgumentException("Price and quantity must be non-negative");
        }
        return price * quantity;
    }
}
"""

TAUTOLOGICAL_JUNIT_TEST = """
package com.example.service;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class OrderServiceLLMTest {
    @Test
    public void testCalculateTotal() {
        assertTrue(true);
    }
}
"""


def test_api_analyze_endpoint(tmp_path):
    # Setup dummy project dir
    src_dir = tmp_path / "src" / "main" / "java" / "com" / "example" / "service"
    src_dir.mkdir(parents=True)
    source_file = src_dir / "OrderService.java"
    source_file.write_text(SAMPLE_JAVA_SOURCE, encoding="utf-8")

    payload = {
        "project_dir": str(tmp_path),
        "relative_source_path": "src/main/java/com/example/service/OrderService.java",
    }

    response = client.post("/api/v1/unit-tests/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["target_class"] == "OrderService"
    assert data["package_name"] == "com.example.service"
    assert "calculateTotal" in data["uncovered_methods"]
    assert len(data["suggested_scenarios"]) > 0


def test_api_validate_endpoint():
    payload = {
        "source_code": SAMPLE_JAVA_SOURCE,
        "test_code": TAUTOLOGICAL_JUNIT_TEST,
        "target_class_name": "OrderService",
    }

    response = client.post("/api/v1/unit-tests/validate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["is_valid"] is False
    assert len(data["smells_detected"]) > 0
    assert any(s["smell_type"] == "TAUTOLOGICAL_ASSERTION" for s in data["smells_detected"])
