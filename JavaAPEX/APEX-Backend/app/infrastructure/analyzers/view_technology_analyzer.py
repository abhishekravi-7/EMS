"""Analyzer for JSP and JSF view-layer technologies, tags, libraries, and migration indicators."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.shared import file_utils

logger = logging.getLogger(__name__)


@dataclass
class ViewTechnologyAnalysis:
    jsp_detected: bool
    jsp_file_count: int
    jsf_detected: bool
    jsf_file_count: int
    has_jsp_views: bool
    has_jsp_tags: bool
    has_jstl: bool
    has_jsf_xhtml: bool
    has_managed_beans: bool
    has_expression_language: bool
    indicators: list[dict[str, Any]] = field(default_factory=list)
    summary_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "jspDetected": self.jsp_detected,
            "jspFileCount": self.jsp_file_count,
            "jsfDetected": self.jsf_detected,
            "jsfFileCount": self.jsf_file_count,
            "hasJspViews": self.has_jsp_views,
            "hasJspTags": self.has_jsp_tags,
            "hasJstl": self.has_jstl,
            "hasJsfXhtml": self.has_jsf_xhtml,
            "hasManagedBeans": self.has_managed_beans,
            "hasExpressionLanguage": self.has_expression_language,
            "indicators": self.indicators,
            "summaryMessage": self.summary_message,
        }


class ViewTechnologyAnalyzer:
    """Analyzes repository view layer technologies, custom tags, JSTL, and JSF components."""

    def analyze(
        self,
        root: Path,
        jsp_files: list[str],
        jsf_files: list[str],
        java_files: list[str],
        dependencies: list[Any],
    ) -> ViewTechnologyAnalysis:
        jsp_count = len(jsp_files)
        jsf_count = len(jsf_files)
        jsp_detected = jsp_count > 0
        jsf_detected = jsf_count > 0

        has_jsp_views = jsp_detected

        # Check dependencies for JSTL, JSF, EL
        dep_names: list[str] = []
        for dep in dependencies:
            if hasattr(dep, "artifact_id") and dep.artifact_id:
                dep_names.append(str(dep.artifact_id).lower())
            if hasattr(dep, "group_id") and dep.group_id:
                dep_names.append(str(dep.group_id).lower())
            if isinstance(dep, dict):
                art = dep.get("artifactId") or dep.get("artifact_id") or ""
                grp = dep.get("groupId") or dep.get("group_id") or ""
                dep_names.append(str(art).lower())
                dep_names.append(str(grp).lower())

        dep_text = " ".join(dep_names)

        # Inspect JSP / JSPF files for taglib and JSTL
        has_jsp_tags = False
        has_jstl = any(term in dep_text for term in ("jstl", "taglibs", "standard.jar"))
        has_el_dep = any(term in dep_text for term in ("el-api", "javax.el", "jakarta.el"))

        # Scan JSP files for directives
        for rel_path in jsp_files[:30]:
            file_path = root / rel_path
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if "<%@ taglib" in content or "<%@taglib" in content:
                    has_jsp_tags = True
                if "http://java.sun.com/jsp/jstl" in content or "http://xmlns.jcp.org/jsp/jstl" in content or "jakarta.tags.core" in content:
                    has_jstl = True
                    has_jsp_tags = True
            except Exception as e:
                logger.debug("Failed reading JSP file %s: %s", file_path, e)

        # Check for custom .tag / .tld files
        if not has_jsp_tags:
            tag_files = file_utils.count_files(root, ".tag", limit=1) + file_utils.count_files(root, ".tagf", limit=1) + file_utils.count_files(root, ".tld", limit=1)
            if tag_files > 0:
                has_jsp_tags = True

        # JSF / XHTML detection
        has_faces_config = (root / "faces-config.xml").is_file() or file_utils.find_files(root, "faces-config.xml", limit=1)
        has_jsf_dep = any(term in dep_text for term in ("faces", "myfaces", "primefaces", "bootsfaces", "richfaces"))
        has_jsf_xhtml = jsf_detected or bool(has_faces_config) or has_jsf_dep

        # Managed Beans detection
        has_managed_beans = False
        if has_jsf_xhtml:
            managed_bean_pattern = re.compile(r"@(ManagedBean|Named|ViewScoped|FacesComponent)\b")
            for rel_path in java_files[:100]:
                file_path = root / rel_path
                if not file_path.is_file():
                    continue
                try:
                    j_content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if managed_bean_pattern.search(j_content):
                        has_managed_beans = True
                        break
                except Exception as e:
                    logger.debug("Failed reading Java file %s: %s", file_path, e)

        has_expression_language = has_el_dep

        # Build dynamic indicators
        indicators = [
            {
                "id": "jsp_views",
                "label": "JSP Views",
                "detected": has_jsp_views,
                "variant": "green" if has_jsp_views else "gray",
            },
            {
                "id": "jsp_tags",
                "label": "JSP Tags",
                "detected": has_jsp_tags,
                "variant": "blue" if has_jsp_tags else "gray",
            },
            {
                "id": "jstl",
                "label": "JSTL",
                "detected": has_jstl,
                "variant": "blue" if has_jstl else "gray",
            },
            {
                "id": "jsf_xhtml",
                "label": "JSF / XHTML",
                "detected": has_jsf_xhtml,
                "variant": "blue" if has_jsf_xhtml else "gray",
            },
            {
                "id": "managed_beans",
                "label": "Managed Beans",
                "detected": has_managed_beans,
                "variant": "blue" if has_managed_beans else "gray",
            },
            {
                "id": "expression_language",
                "label": "Expression Language",
                "detected": has_expression_language,
                "variant": "blue" if has_expression_language else "gray",
            },
        ]

        if jsp_detected and not jsf_detected:
            summary_message = "JSP files detected. The application uses JSP for its view layer. No JSF files were found in this repository."
        elif jsf_detected and not jsp_detected:
            summary_message = f"JSF (XHTML) files detected ({jsf_count} files). The application uses JSF for its view layer. No JSP files were found in this repository."
        elif jsp_detected and jsf_detected:
            summary_message = f"JSP ({jsp_count} files) and JSF ({jsf_count} files) detected. Both view technologies are present in this repository."
        else:
            summary_message = "No JSP or JSF view layer technology files were detected in this repository."

        return ViewTechnologyAnalysis(
            jsp_detected=jsp_detected,
            jsp_file_count=jsp_count,
            jsf_detected=jsf_detected,
            jsf_file_count=jsf_count,
            has_jsp_views=has_jsp_views,
            has_jsp_tags=has_jsp_tags,
            has_jstl=has_jstl,
            has_jsf_xhtml=has_jsf_xhtml,
            has_managed_beans=has_managed_beans,
            has_expression_language=has_expression_language,
            indicators=indicators,
            summary_message=summary_message,
        )
