"""Tests for dynamic frontend framework compatibility and LLM recommendation flow."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.infrastructure.analyzers.frontend_compatibility_analyzer import (
    FrontendCompatibilityAnalyzer,
    _RECOMMENDATION_CACHE,
)


@pytest.fixture(autouse=True)
def clear_rec_cache():
    """Clear in-memory recommendation cache between tests."""
    _RECOMMENDATION_CACHE.clear()
    yield
    _RECOMMENDATION_CACHE.clear()


def test_pure_jsp_repository_dynamic_recommendation():
    """Pure Java/JSP project generates dynamic LLM recommendation based on metadata."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src" / "main" / "webapp" / "WEB-INF").mkdir(parents=True)
        (root / "src" / "main" / "webapp" / "WEB-INF" / "index.jsp").write_text("<%@ page %>")

        mock_llm_response = {
            "recommended_target": "react",
            "recommended_target_label": "JSP -> React",
            "recommended_version": "19.0.0",
            "confidence": "high",
            "compatibility": {
                "node": {"detected": None, "required": "18.x+", "status": "compatible"},
                "typescript": {"detected": None, "required": "5.x+", "status": "compatible"},
            },
            "recommendation": "Pure JSP repository with 1 JSP file. React recommended for component migration.",
            "reasons": ["1 JSP file detected, clean migration path to React components."],
            "requirements": ["Configure Node.js and React toolchain."],
            "risks": [],
        }

        with patch.object(
            FrontendCompatibilityAnalyzer,
            "_query_llm_recommendation",
            return_value=mock_llm_response,
        ) as mock_query:
            analyzer = FrontendCompatibilityAnalyzer()
            recs = analyzer.analyze(root)

            # LLM was invoked with compact metadata
            mock_query.assert_called_once()
            called_context = mock_query.call_args[0][0]
            assert called_context["ui_framework_sources"]["jsp_files"] == 1
            assert called_context["ui_framework_sources"]["jsf_files"] == 0
            assert "JSP -> React" in called_context["available_targets"]
            assert "JSP -> Angular" in called_context["available_targets"]
            assert "JSF -> React" not in called_context["available_targets"]

            # Output mapped to existing schema
            assert recs.recommendation_status == "available"
            assert recs.recommended_target == "react"
            assert recs.recommended_target_label == "JSP -> React"
            assert recs.react.target_version == "19.0.0"
            assert recs.react.is_recommended is True
            assert recs.angular.is_recommended is False
            assert len(recs.react.reasons) > 0


def test_constrained_repository_passes_compact_payload_to_llm():
    """Repository with Node 16 / TypeScript 4.8 extracts environment and passes to LLM."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "index.jsp").write_text("<%@ page %>")
        pkg = {
            "engines": {"node": "16.14.0"},
            "devDependencies": {"typescript": "4.8.4"},
        }
        (root / "package.json").write_text(json.dumps(pkg))

        mock_llm_response = {
            "recommended_target": "react",
            "recommended_target_label": "JSP -> React",
            "recommended_version": "18.3.1",
            "confidence": "high",
            "compatibility": {
                "node": {"detected": "16.14.0", "required": "16.x+", "status": "compatible"},
                "typescript": {"detected": "4.8.4", "required": "4.8+", "status": "compatible"},
            },
            "recommendation": "Node 16 and TypeScript 4.8 detected; aligned to compatible React 18.",
            "reasons": ["Detected Node 16.14.0 is compatible with React 18."],
            "requirements": [],
            "risks": ["Node 16 is end-of-life."],
        }

        with patch.object(
            FrontendCompatibilityAnalyzer,
            "_query_llm_recommendation",
            return_value=mock_llm_response,
        ) as mock_query:
            analyzer = FrontendCompatibilityAnalyzer()
            recs = analyzer.analyze(root)

            called_context = mock_query.call_args[0][0]
            assert called_context["project_environment"]["node_version"] == "16.14.0"
            assert called_context["project_environment"]["typescript_version"] == "4.8.4"

            assert recs.react.target_version == "18.3.1"
            assert "Node 16.14.0" in " ".join(recs.react.reasons)


def test_existing_angular_dependency_detected_and_sent():
    """When Angular is already installed, detected version is sent to LLM in context payload."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "index.jsp").write_text("<%@ page %>")
        pkg = {
            "dependencies": {"@angular/core": "^15.2.0"},
        }
        (root / "package.json").write_text(json.dumps(pkg))

        mock_llm_response = {
            "recommended_target": "angular",
            "recommended_target_label": "JSP -> Angular",
            "recommended_version": "15.2.0",
            "confidence": "high",
            "compatibility": {
                "node": {"detected": None, "required": "16.x-18.x", "status": "compatible"},
                "typescript": {"detected": None, "required": "4.8-4.9", "status": "compatible"},
            },
            "recommendation": "Existing Angular 15.2.0 project detected.",
            "reasons": ["Maintains consistency with existing Angular 15.2.0 installation."],
            "requirements": [],
            "risks": [],
        }

        with patch.object(
            FrontendCompatibilityAnalyzer,
            "_query_llm_recommendation",
            return_value=mock_llm_response,
        ) as mock_query:
            analyzer = FrontendCompatibilityAnalyzer()
            recs = analyzer.analyze(root)

            called_context = mock_query.call_args[0][0]
            assert "15.2.0" in called_context["project_environment"]["angular_version"]
            assert recs.angular.current_version == "15.2.0"
            assert recs.angular.target_version == "15.2.0"
            assert recs.angular.is_recommended is True
            assert recs.react.is_recommended is False


def test_llm_failure_returns_unavailable_without_fabrication():
    """When LLM call fails, return unavailable status without fabricating recommendations."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "index.jsp").write_text("<%@ page %>")

        with patch.object(
            FrontendCompatibilityAnalyzer,
            "_query_llm_recommendation",
            return_value=None,
        ):
            analyzer = FrontendCompatibilityAnalyzer()
            recs = analyzer.analyze(root)

            assert recs.recommendation_status == "unavailable"
            assert recs.react is None
            assert recs.angular is None
            assert recs.recommended_target is None


def test_recommendation_caching_avoids_duplicate_llm_calls():
    """Subsequent calls with identical metadata reuse cache and do not invoke LLM again."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "index.jsp").write_text("<%@ page %>")

        mock_llm_response = {
            "recommended_target": "react",
            "recommended_target_label": "JSP -> React",
            "recommended_version": "19.3",
            "confidence": "high",
            "compatibility": {},
            "recommendation": "Cached test rec.",
            "reasons": ["Test reason"],
            "requirements": [],
            "risks": [],
        }

        with patch.object(
            FrontendCompatibilityAnalyzer,
            "_query_llm_recommendation",
            return_value=mock_llm_response,
        ) as mock_query:
            analyzer = FrontendCompatibilityAnalyzer()
            recs1 = analyzer.analyze(root)
            recs2 = analyzer.analyze(root)

            assert mock_query.call_count == 1
            assert recs1 == recs2


def test_candidates_list_exposes_more_than_two_compatible_versions():
    """Verify that multiple candidates (>2) are populated in available_versions and incompatible ones are filtered."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "index.jsp").write_text("<%@ page %>")

        mock_llm_response = {
            "recommended_target": "angular",
            "recommended_target_label": "JSP -> Angular",
            "confidence": "high",
            "recommendation_summary": "Angular recommended for enterprise JSP modernization.",
            "angular": {
                "recommended": "22.x",
                "compatibility": "Compatible with Node.js runtime.",
                "reasons": ["Modern signals architecture."],
                "constraints": [],
                "candidates": [
                    {"version": "22.x", "compatible": True, "reason": "Latest stable."},
                    {"version": "21.x", "compatible": True, "reason": "Supported."},
                    {"version": "20.x", "compatible": True, "reason": "LTS supported."},
                    {"version": "19.x", "compatible": True, "reason": "Supported."},
                    {"version": "18.x", "compatible": True, "reason": "Supported."},
                    {"version": "15.x", "compatible": False, "reason": "Incompatible with Node runtime."},
                ],
            },
            "react": {
                "recommended": "19.x",
                "compatibility": "Compatible with Node.js runtime.",
                "reasons": ["Component-based architecture."],
                "constraints": [],
                "candidates": [
                    {"version": "19.x", "compatible": True, "reason": "Latest stable."},
                    {"version": "18.x", "compatible": True, "reason": "Widely adopted."},
                    {"version": "17.x", "compatible": True, "reason": "Supported."},
                    {"version": "16.x", "compatible": True, "reason": "Legacy compatible."},
                ],
            },
        }

        with patch.object(
            FrontendCompatibilityAnalyzer,
            "_query_llm_recommendation",
            return_value=mock_llm_response,
        ):
            analyzer = FrontendCompatibilityAnalyzer()
            recs = analyzer.analyze(root)

            # Angular should have exactly 5 compatible versions (15.x was compatible=False)
            assert recs.angular.target_version == "22.x"
            assert len(recs.angular.available_versions) == 5
            assert recs.angular.available_versions == ["22.x", "21.x", "20.x", "19.x", "18.x"]
            assert "15.x" not in recs.angular.available_versions

            # React should have 4 compatible versions
            assert recs.react.target_version == "19.x"
            assert len(recs.react.available_versions) == 4
            assert recs.react.available_versions == ["19.x", "18.x", "17.x", "16.x"]


def test_discovery_failure_returns_unavailable_without_static_fallbacks():
    """When discovery returns no versions and no repo dependencies exist, return unavailable without fallbacks."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "index.jsp").write_text("<%@ page %>")

        with patch.object(
            FrontendCompatibilityAnalyzer,
            "_discover_framework_versions",
            return_value={"react": [], "angular": []},
        ):
            analyzer = FrontendCompatibilityAnalyzer()
            recs = analyzer.analyze(root)

            assert recs.recommendation_status == "unavailable"
            assert recs.react is None
            assert recs.angular is None

