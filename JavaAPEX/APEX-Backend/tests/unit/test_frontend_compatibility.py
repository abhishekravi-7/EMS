"""Tests for dynamic frontend framework compatibility and target version recommendations."""

import json
import tempfile
from pathlib import Path
import pytest

from app.infrastructure.analyzers.frontend_compatibility_analyzer import (
    FrontendCompatibilityAnalyzer,
)


def test_pure_jsp_repository_recommendations():
    """When a pure Java/JSP project has no Node.js configuration, modern LTS targets are evaluated."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src" / "main" / "webapp" / "WEB-INF").mkdir(parents=True)
        (root / "src" / "main" / "webapp" / "WEB-INF" / "index.jsp").write_text("<%@ page %>")

        analyzer = FrontendCompatibilityAnalyzer()
        recs = analyzer.analyze(root)

        # React recommendation
        assert recs.react.framework == "React"
        assert recs.react.target_version == "19.3"
        assert recs.react.is_recommended is True
        assert "Compatible" in recs.react.compatibility
        assert len(recs.react.reasons) > 0
        assert recs.react.current_version is None

        # Angular recommendation
        assert recs.angular.framework == "Angular"
        assert recs.angular.target_version == "22.x"
        assert recs.angular.is_recommended is False
        assert "alignment" in recs.angular.compatibility.lower()
        assert len(recs.angular.reasons) > 0


def test_node_16_constrained_repository():
    """When Node 16 is specified in engines, both frameworks down-tier to compatible versions."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pkg = {
            "engines": {"node": "16.14.0"},
            "devDependencies": {"typescript": "4.8.4"},
        }
        (root / "package.json").write_text(json.dumps(pkg))

        analyzer = FrontendCompatibilityAnalyzer()
        recs = analyzer.analyze(root)

        assert recs.react.target_version == "18.3.1"
        assert "16" in " ".join(recs.react.reasons)

        assert recs.angular.target_version == "16.2.12"
        assert "16" in " ".join(recs.angular.reasons)


def test_existing_react_dependency_detected():
    """When React is already installed, the current version is detected and upgrade path calculated."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pkg = {
            "dependencies": {"react": "^17.0.2", "react-dom": "^17.0.2"},
        }
        (root / "package.json").write_text(json.dumps(pkg))

        analyzer = FrontendCompatibilityAnalyzer()
        recs = analyzer.analyze(root)

        assert recs.react.current_version == "17.0.2"
        assert recs.react.target_version == "19.3"
        assert recs.react.is_recommended is True
        assert any("17.0.2" in r for r in recs.react.reasons)


def test_existing_angular_dependency_detected():
    """When Angular is already installed, Angular is recommended over React."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pkg = {
            "dependencies": {"@angular/core": "^15.2.0"},
        }
        (root / "package.json").write_text(json.dumps(pkg))

        analyzer = FrontendCompatibilityAnalyzer()
        recs = analyzer.analyze(root)

        assert recs.angular.current_version == "15.2.0"
        assert recs.angular.is_recommended is True
        assert recs.react.is_recommended is False
