"""Repository file categorizer module for Java APEX.

Performs a single-pass, mutually exclusive repository-wide file classification into
17 primary categories. Guarantees: sum(category_counts) == total_files.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.shared import file_utils

CAT_JAVA = "java"
CAT_JAVA_TEST = "java_test"
CAT_JSP = "jsp"
CAT_JSF = "jsf"
CAT_REACT = "react"
CAT_ANGULAR = "angular"
CAT_JAVASCRIPT = "javascript"
CAT_TYPESCRIPT = "typescript"
CAT_CSS = "css"
CAT_HTML = "html"
CAT_XML = "xml"
CAT_CONFIGURATION = "configuration"
CAT_RESOURCES = "resources"
CAT_DOCUMENTATION = "documentation"
CAT_SCRIPTS = "scripts"
CAT_SQL = "sql"
CAT_OTHER = "other"

ALL_CATEGORIES = [
    CAT_JAVA,
    CAT_JAVA_TEST,
    CAT_JSP,
    CAT_JSF,
    CAT_REACT,
    CAT_ANGULAR,
    CAT_JAVASCRIPT,
    CAT_TYPESCRIPT,
    CAT_CSS,
    CAT_HTML,
    CAT_XML,
    CAT_CONFIGURATION,
    CAT_RESOURCES,
    CAT_DOCUMENTATION,
    CAT_SCRIPTS,
    CAT_SQL,
    CAT_OTHER,
]

_EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "target",
    "build",
    "dist",
    "out",
    ".gradle",
    ".idea",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".vscode",
    ".settings",
    ".next",
    ".nuxt",
}


@dataclass
class FileClassification:
    rel_path: str
    extension: str
    category: str
    is_test: bool
    reason: str


@dataclass
class RepositoryFileMetrics:
    total: int
    categories: dict[str, int]
    category_files: dict[str, list[str]] = field(default_factory=dict)
    classifications: list[FileClassification] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "categories": dict(self.categories),
            "category_files": {k: list(v) for k, v in self.category_files.items()},
        }


class RepositoryFileCategorizer:
    """Classifies repository files in a single pass into 17 mutually exclusive categories."""

    def categorize_repository(self, root: Path) -> RepositoryFileMetrics:
        all_files: list[tuple[str, Path]] = []
        normalized_root = file_utils._long_path(root)
        root_str = str(normalized_root)

        for dirpath, dirnames, filenames in os.walk(root_str):
            # Prune excluded noise directories in-place
            dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS]
            for name in filenames:
                abs_path = Path(dirpath) / name
                try:
                    rel_path = abs_path.relative_to(normalized_root).as_posix()
                except ValueError:
                    rel_path = abs_path.as_posix()
                all_files.append((rel_path, abs_path))

        # Check project-level indicators for React & Angular
        package_json_deps: set[str] = set()
        has_angular_json = False

        for rel_path, abs_path in all_files:
            lower_rel = rel_path.lower()
            if lower_rel.endswith("package.json"):
                deps = self._read_package_deps(abs_path)
                package_json_deps.update(deps)
            elif lower_rel.endswith("angular.json"):
                has_angular_json = True

        has_react_dep = any("react" in d for d in package_json_deps)
        has_angular_dep = has_angular_json or any(d.startswith("@angular/") for d in package_json_deps)

        category_files: dict[str, list[str]] = {cat: [] for cat in ALL_CATEGORIES}
        categories_count: dict[str, int] = {cat: 0 for cat in ALL_CATEGORIES}
        classifications: list[FileClassification] = []

        for rel_path, abs_path in all_files:
            classification = self._classify_file(
                rel_path,
                abs_path,
                has_react_dep=has_react_dep,
                has_angular_dep=has_angular_dep,
            )
            cat = classification.category
            categories_count[cat] += 1
            category_files[cat].append(rel_path)
            classifications.append(classification)

            # Record Java Test files as a subset of Java
            if cat == CAT_JAVA and classification.is_test:
                categories_count[CAT_JAVA_TEST] += 1
                category_files[CAT_JAVA_TEST].append(rel_path)

        total = len(all_files)

        return RepositoryFileMetrics(
            total=total,
            categories=categories_count,
            category_files=category_files,
            classifications=classifications,
        )

    def _classify_file(
        self,
        rel_path: str,
        abs_path: Path,
        has_react_dep: bool,
        has_angular_dep: bool,
    ) -> FileClassification:
        lower_path = rel_path.lower()
        filename = Path(rel_path).name
        lower_filename = filename.lower()
        ext = Path(rel_path).suffix.lower()

        is_test = self._is_test_file(lower_path, lower_filename)

        # 1. Java & Java Test (All .java files belong to CAT_JAVA; test files marked is_test=True)
        if ext == ".java":
            return FileClassification(
                rel_path,
                ext,
                CAT_JAVA,
                is_test,
                "Java test source file" if is_test else "Java source file",
            )

        # 2. JSP
        if ext in (".jsp", ".jspf", ".jspx"):
            return FileClassification(rel_path, ext, CAT_JSP, is_test, "JSP view template")

        # 3. JSF
        if ext == ".jsf" or (ext == ".xhtml" and self._is_jsf_xhtml(lower_path, abs_path)):
            return FileClassification(rel_path, ext, CAT_JSF, is_test, "JSF view file")

        # 4. React (.jsx, .tsx)
        if ext in (".jsx", ".tsx"):
            return FileClassification(rel_path, ext, CAT_REACT, is_test, "React JSX/TSX source file")

        # 5. Framework-aware code/view files (.js, .mjs, .cjs, .ts, .html, .htm, .scss, .css, .sass, .less)
        if ext in (".ts", ".js", ".mjs", ".cjs", ".html", ".htm", ".scss", ".css", ".sass", ".less"):
            # Check React for .js/.ts
            if ext in (".js", ".ts", ".mjs", ".cjs"):
                is_react, react_reason = self._check_react_file(lower_path, lower_filename, abs_path, has_react_dep)
                if is_react:
                    return FileClassification(rel_path, ext, CAT_REACT, is_test, react_reason)

            # Check Angular
            is_angular, angular_reason = self._check_angular_file(
                lower_path, lower_filename, ext, abs_path, has_angular_dep
            )
            if is_angular:
                return FileClassification(rel_path, ext, CAT_ANGULAR, is_test, angular_reason)

            # Generic fallbacks
            if ext in (".js", ".mjs", ".cjs"):
                return FileClassification(rel_path, ext, CAT_JAVASCRIPT, is_test, "JavaScript source file")
            if ext == ".ts":
                return FileClassification(rel_path, ext, CAT_TYPESCRIPT, is_test, "TypeScript source file")
            if ext in (".css", ".scss", ".sass", ".less"):
                return FileClassification(rel_path, ext, CAT_CSS, is_test, "CSS / Style file")
            if ext in (".html", ".htm"):
                return FileClassification(rel_path, ext, CAT_HTML, is_test, "HTML document")

        # 6. XML
        if ext == ".xml":
            return FileClassification(rel_path, ext, CAT_XML, is_test, "XML document")

        # 7. Configuration
        if (
            ext
            in (
                ".properties",
                ".yml",
                ".yaml",
                ".json",
                ".toml",
                ".ini",
                ".conf",
                ".config",
                ".cfg",
                ".env",
                ".inf",
                ".policy",
            )
            or lower_filename
            in (
                "build.gradle",
                "build.gradle.kts",
                "settings.gradle",
                "settings.gradle.kts",
                "gradle.properties",
                "dockerfile",
                ".gitignore",
                ".dockerignore",
                ".editorconfig",
                ".gitattributes",
                ".eslintrc",
                ".prettierrc",
                "makefile",
            )
            or lower_filename.startswith(".env")
        ):
            return FileClassification(rel_path, ext, CAT_CONFIGURATION, is_test, "Configuration file")

        # 8. Resources / Assets
        if ext in (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".webp",
            ".ico",
            ".bmp",
            ".tiff",
            ".ttf",
            ".otf",
            ".woff",
            ".woff2",
            ".eot",
            ".mp3",
            ".wav",
            ".mp4",
            ".avi",
            ".mkv",
            ".flv",
            ".ogg",
            ".webm",
            ".jar",
            ".zip",
            ".tar",
            ".gz",
            ".pdf",
            ".xlsx",
            ".xls",
            ".doc",
            ".docx",
        ):
            return FileClassification(rel_path, ext, CAT_RESOURCES, is_test, "Resource asset file")

        # 9. Documentation
        is_doc_txt = ext == ".txt" and (
            lower_filename in ("readme.txt", "license.txt", "changelog.txt", "notice.txt", "contributing.txt")
            or "doc" in lower_path.split("/")
            or "docs" in lower_path.split("/")
        )
        if ext in (".md", ".markdown", ".rst", ".adoc") or is_doc_txt or lower_filename in (
            "readme",
            "readme.md",
            "readme.txt",
            "license",
            "notice",
            "changelog",
            "contributing",
        ):
            return FileClassification(rel_path, ext, CAT_DOCUMENTATION, is_test, "Documentation file")

        # 10. Shell / Scripts
        if ext in (".sh", ".bat", ".cmd", ".ps1", ".bash", ".zsh", ".fish") or lower_filename in (
            "mvnw",
            "gradlew",
            "jenkinsfile",
        ):
            return FileClassification(rel_path, ext, CAT_SCRIPTS, is_test, "Script / automation file")

        # 11. SQL
        if ext == ".sql":
            return FileClassification(rel_path, ext, CAT_SQL, is_test, "SQL script file")

        # 12. Other (Fallback)
        return FileClassification(rel_path, ext or "none", CAT_OTHER, is_test, "Other file")

    @staticmethod
    def _read_package_deps(path: Path) -> set[str]:
        deps: set[str] = set()
        text = file_utils.read_text(path)
        if not text:
            return deps
        try:
            data = json.loads(text)
            for block in ("dependencies", "devDependencies", "peerDependencies"):
                sec = data.get(block)
                if isinstance(sec, dict):
                    deps.update(sec.keys())
        except Exception:
            pass
        return deps

    @staticmethod
    def _is_test_file(lower_path: str, lower_filename: str) -> bool:
        # Check path locations
        for part in ("/src/test/", "src/test/", "/test/", "/tests/", "/__tests__/", "/spec/"):
            if part in lower_path:
                return True

        # Check naming patterns
        test_patterns = (
            "test.java",
            "tests.java",
            "testcase.java",
            "it.java",
            "testbase.java",
            ".test.js",
            ".spec.js",
            ".test.ts",
            ".spec.ts",
            ".test.jsx",
            ".spec.jsx",
            ".test.tsx",
            ".spec.tsx",
        )
        return any(lower_filename.endswith(pat) for pat in test_patterns)

    @staticmethod
    def _is_jsf_xhtml(lower_path: str, abs_path: Path) -> bool:
        if "src/main/webapp" in lower_path or "web-inf" in lower_path or "webcontent" in lower_path:
            return True
        text = file_utils.read_text(abs_path)
        if not text:
            return True
        text_lower = text[:4096].lower()
        jsf_markers = (
            "xmlns:h=",
            "xmlns:f=",
            "xmlns:ui=",
            "http://java.sun.com/jsf",
            "http://xmlns.jcp.org/jsf",
            "<h:form",
            "<ui:composition",
        )
        if any(m in text_lower for m in jsf_markers):
            return True
        return True  # .xhtml default for Java web applications

    @staticmethod
    def _check_react_file(
        lower_path: str, lower_filename: str, abs_path: Path, has_react_dep: bool
    ) -> tuple[bool, str]:
        # File extension or location indicators
        if lower_filename.endswith((".jsx", ".tsx")):
            return True, "React extension (.jsx/.tsx)"

        text = file_utils.read_text(abs_path)
        snippet = text[:4096] if text else ""

        # Content indicators
        react_import_regex = re.compile(
            r"""import\s+.*?\s+from\s+['"]react(-dom)?['"]|require\(['"]react(-dom)?['"]\)""",
            re.IGNORECASE,
        )
        if react_import_regex.search(snippet):
            return True, "React import statement detected"

        react_hooks = ("useState(", "useEffect(", "useContext(", "useReducer(", "useCallback(", "useMemo(", "useRef(")
        if any(hook in snippet for hook in react_hooks):
            return True, "React hook usage detected"

        if "React.Component" in snippet or "ReactDOM." in snippet:
            return True, "React class or DOM method detected"

        # Component naming/folder convention when project has react dependency
        if has_react_dep:
            for react_dir in ("/src/components/", "/src/pages/", "/src/views/", "/src/hooks/", "/src/context/"):
                if react_dir in lower_path:
                    return True, "File inside React component directory"

        return False, ""

    @staticmethod
    def _check_angular_file(
        lower_path: str,
        lower_filename: str,
        ext: str,
        abs_path: Path,
        has_angular_dep: bool,
    ) -> tuple[bool, str]:
        text = file_utils.read_text(abs_path)
        snippet = text[:4096] if text else ""

        if ext == ".ts":
            angular_decorators = ("@Component", "@Injectable", "@Directive", "@Pipe", "@NgModule")
            if any(dec in snippet for dec in angular_decorators):
                return True, "Angular decorator detected"

            if "from '@angular/" in snippet or 'from "@angular/' in snippet:
                return True, "Angular import detected"

            angular_suffixes = (
                ".component.ts",
                ".service.ts",
                ".directive.ts",
                ".pipe.ts",
                ".module.ts",
                ".guard.ts",
            )
            if any(lower_filename.endswith(s) for s in angular_suffixes):
                return True, "Angular file naming convention"

        elif ext in (".html", ".htm"):
            angular_html_patterns = ("*ngif=", "*ngfor=", "[(ngmodel)]=", "(click)=", "[ngclass]=", "[ngstyle]=")
            snippet_lower = snippet.lower()
            if any(pat in snippet_lower for pat in angular_html_patterns) or ("{{" in snippet and "}}" in snippet):
                return True, "Angular template syntax detected"

            if has_angular_dep and lower_filename.endswith(".component.html"):
                return True, "Angular component template file"

        elif ext in (".scss", ".css"):
            if has_angular_dep and lower_filename.endswith((".component.scss", ".component.css")):
                return True, "Angular component stylesheet"

        return False, ""
