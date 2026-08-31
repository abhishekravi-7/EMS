"""Codebase and feature discovery analyzer for Proposed Functional Test Cases."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


class ProposedTestAnalyzer:
    """Performs static & semantic analysis of the codebase to discover testable features and gaps."""

    def __init__(self, repo_dir: Path, existing_tests: list[dict[str, Any]] | None = None) -> None:
        self.repo_dir = Path(repo_dir)
        self.existing_tests = existing_tests or []

    def analyze(self) -> dict[str, Any]:
        """Discovers application features and existing coverage gaps."""
        if not self.repo_dir.exists():
            return {
                "controllers": [],
                "endpoints": [],
                "services": [],
                "repositories": [],
                "entities": [],
                "ui_workflows": [],
                "existing_coverage": {},
                "gaps": [],
            }

        endpoints, controllers = self._scan_controllers_and_endpoints()
        services = self._scan_services()
        repositories = self._scan_repositories()
        entities = self._scan_entities()
        ui_workflows = self._scan_ui_workflows()
        existing_coverage = self._map_existing_coverage()

        return {
            "controllers": controllers,
            "endpoints": endpoints,
            "services": services,
            "repositories": repositories,
            "entities": entities,
            "ui_workflows": ui_workflows,
            "existing_coverage": existing_coverage,
        }

    def _scan_controllers_and_endpoints(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        endpoints: list[dict[str, Any]] = []
        controllers: list[dict[str, Any]] = []

        mapping_pattern = re.compile(
            r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\s*(?:\(\s*(?:value\s*=\s*|path\s*=\s*)?["\']([^"\']*)["\']|\(\s*\{([^}]+)\}|\s*)',
            re.IGNORECASE,
        )
        class_request_mapping_pattern = re.compile(
            r'@RequestMapping\s*(?:\(\s*(?:value\s*=\s*|path\s*=\s*)?["\']([^"\']*)["\']|\s*)',
            re.IGNORECASE,
        )

        for root, dirs, files in os.walk(self.repo_dir):
            for skip in [".git", "node_modules", "target", "build", "venv", "__pycache__", "dist", ".gradle"]:
                if skip in dirs:
                    dirs.remove(skip)

            for file in files:
                if not file.endswith((".java", ".kt", ".py", ".ts", ".js")):
                    continue

                filepath = Path(root) / file
                rel_path = filepath.relative_to(self.repo_dir).as_posix()
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except Exception:  # noqa: BLE001, S112
                    continue  # nosec B112

                # Java / Spring Boot Controllers
                if "@RestController" in content or "@Controller" in content or "Controller" in file:
                    base_path = ""
                    base_match = class_request_mapping_pattern.search(content)
                    if base_match and base_match.group(1):
                        base_path = "/" + base_match.group(1).strip("/").strip()

                    methods_found: list[dict[str, Any]] = []
                    lines = content.splitlines()
                    for idx, line in enumerate(lines):
                        match = mapping_pattern.search(line)
                        if match:
                            ann_type = match.group(1).upper()
                            sub_path = (match.group(2) or "").strip().strip("/")
                            if not sub_path and match.group(3):
                                # Multiple paths or params
                                raw_paths = match.group(3).split(",")
                                if raw_paths:
                                    sub_path = raw_paths[0].replace('"', '').replace("'", '').strip().strip("/")

                            method_http = "GET"
                            if "POST" in ann_type:
                                method_http = "POST"
                            elif "PUT" in ann_type:
                                method_http = "PUT"
                            elif "DELETE" in ann_type:
                                method_http = "DELETE"
                            elif "PATCH" in ann_type:
                                method_http = "PATCH"

                            full_path = f"{base_path}/{sub_path}".replace("//", "/")
                            if not full_path.startswith("/"):
                                full_path = "/" + full_path

                            # Infer method name from next few lines
                            handler_name = f"handle{ann_type.replace('MAPPING', '')}"
                            for next_line in lines[idx : min(idx + 5, len(lines))]:
                                fn_match = re.search(r'(?:public|protected|private)?\s+[\w\<\>\[\]]+\s+(\w+)\s*\(', next_line)
                                if fn_match:
                                    handler_name = fn_match.group(1)
                                    break

                            ep_info = {
                                "method": method_http,
                                "endpoint": full_path,
                                "handler": handler_name,
                                "file": rel_path,
                                "class_name": filepath.stem,
                                "source": filepath.stem,
                            }
                            methods_found.append(ep_info)
                            endpoints.append(ep_info)

                    controllers.append({
                        "name": filepath.stem,
                        "file": rel_path,
                        "base_path": base_path,
                        "endpoints": methods_found,
                    })

                # Python FastAPI / Flask routes
                elif "@app." in content or "@router." in content:
                    py_route_pattern = re.compile(
                        r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                        re.IGNORECASE,
                    )
                    for match in py_route_pattern.finditer(content):
                        method_http = match.group(1).upper()
                        path = match.group(2)
                        endpoints.append({
                            "method": method_http,
                            "endpoint": path,
                            "handler": "route_handler",
                            "file": rel_path,
                            "class_name": filepath.stem,
                            "source": filepath.stem,
                        })

                # Express.js routes
                elif "router." in content or "app." in content:
                    js_route_pattern = re.compile(
                        r'(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                        re.IGNORECASE,
                    )
                    for match in js_route_pattern.finditer(content):
                        method_http = match.group(1).upper()
                        path = match.group(2)
                        endpoints.append({
                            "method": method_http,
                            "endpoint": path,
                            "handler": "express_handler",
                            "file": rel_path,
                            "class_name": filepath.stem,
                            "source": filepath.stem,
                        })

        return endpoints, controllers

    def _scan_services(self) -> list[dict[str, Any]]:
        services: list[dict[str, Any]] = []
        method_sig_pattern = re.compile(
            r'public\s+([\w\<\>\[\]]+)\s+(\w+)\s*\(([^)]*)\)',
            re.IGNORECASE,
        )

        for root, dirs, files in os.walk(self.repo_dir):
            for skip in [".git", "node_modules", "target", "build", "venv", "__pycache__", "dist"]:
                if skip in dirs:
                    dirs.remove(skip)

            for file in files:
                if not file.endswith((".java", ".kt")):
                    continue

                filepath = Path(root) / file
                rel_path = filepath.relative_to(self.repo_dir).as_posix()
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except Exception:  # noqa: BLE001, S112
                    continue  # nosec B112

                if "@Service" in content or "Service" in file or "Manager" in file or "Processor" in file:
                    methods = []
                    for match in method_sig_pattern.finditer(content):
                        ret_type, method_name, params = match.groups()
                        if method_name not in ["equals", "hashCode", "toString", "getClass"]:
                            methods.append({
                                "name": method_name,
                                "return_type": ret_type,
                                "params": params.strip(),
                            })

                    services.append({
                        "name": filepath.stem,
                        "file": rel_path,
                        "methods": methods[:15],
                    })

        return services

    def _scan_repositories(self) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        for root, dirs, files in os.walk(self.repo_dir):
            for skip in [".git", "node_modules", "target", "build", "venv", "__pycache__"]:
                if skip in dirs:
                    dirs.remove(skip)

            for file in files:
                if file.endswith((".java", ".kt")) and ("Repository" in file or "Dao" in file or "@Repository" in file):
                    filepath = Path(root) / file
                    repos.append({
                        "name": filepath.stem,
                        "file": filepath.relative_to(self.repo_dir).as_posix(),
                    })
        return repos

    def _scan_entities(self) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        for root, dirs, files in os.walk(self.repo_dir):
            for skip in [".git", "node_modules", "target", "build", "venv", "__pycache__"]:
                if skip in dirs:
                    dirs.remove(skip)

            for file in files:
                if file.endswith((".java", ".kt")):
                    filepath = Path(root) / file
                    try:
                        c = filepath.read_text(encoding="utf-8", errors="ignore")
                        if "@Entity" in c or "@Table" in c or "model" in str(filepath).lower():
                            entities.append({
                                "name": filepath.stem,
                                "file": filepath.relative_to(self.repo_dir).as_posix(),
                            })
                    except Exception:  # noqa: BLE001, S110
                        pass  # nosec B110
        return entities

    def _scan_ui_workflows(self) -> list[dict[str, Any]]:
        ui_items: list[dict[str, Any]] = []
        extensions = [".html", ".jsp", ".jsx", ".tsx", ".vue", ".js", ".ts"]

        for root, dirs, files in os.walk(self.repo_dir):
            for skip in [".git", "node_modules", "target", "build", "venv", "__pycache__", "dist"]:
                if skip in dirs:
                    dirs.remove(skip)

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    filepath = Path(root) / file
                    rel_path = filepath.relative_to(self.repo_dir).as_posix()
                    try:
                        content = filepath.read_text(encoding="utf-8", errors="ignore")
                        c_low = content.lower()

                        is_ui_page = (
                            ext in [".html", ".jsp", ".vue"]
                            or "page" in file.lower()
                            or "view" in file.lower()
                            or "modal" in file.lower()
                            or "<form" in c_low
                            or "onsubmit" in c_low
                            or "<button" in c_low
                            or "input" in c_low
                        )

                        if is_ui_page:
                            has_login = "login" in file.lower() or "signin" in file.lower() or "auth" in file.lower() or "password" in c_low
                            has_form = "<form" in c_low or "onsubmit" in c_low or "formik" in c_low or "useform" in c_low
                            has_table = "<table" in c_low or "datatable" in c_low or "grid" in c_low

                            workflow_type = "AUTH" if has_login else "FORM" if has_form else "DASHBOARD" if has_table else "NAVIGATION"

                            ui_items.append({
                                "name": filepath.stem,
                                "file": rel_path,
                                "type": workflow_type,
                                "has_login": has_login,
                                "has_form": has_form,
                                "has_table": has_table,
                            })
                    except Exception:  # noqa: BLE001, S110
                        pass  # nosec B110

        return ui_items

    def _map_existing_coverage(self) -> dict[str, set[str]]:
        """Extracts existing test names, classes, methods, and endpoints to prevent duplicate proposals."""
        coverage: dict[str, set[str]] = {
            "methods": set(),
            "classes": set(),
            "endpoints": set(),
            "routes": set(),
            "scenarios": set(),
        }

        for t in self.existing_tests:
            name = (t.get("name") or t.get("test_name") or "").lower()
            cls = (t.get("classname") or t.get("suite") or t.get("module") or "").lower()
            file = (t.get("file") or "").lower()

            if name:
                coverage["methods"].add(name)
                # Normalize test names e.g. testGetUserById -> getuserbyid
                clean_name = re.sub(r'^(test_|test|should_?)', '', name).lower()
                coverage["scenarios"].add(clean_name)

            if cls:
                coverage["classes"].add(cls)
            if file:
                coverage["classes"].add(Path(file).stem.lower())

            # Detect endpoints in test names or files
            for verb in ["get", "post", "put", "delete", "patch"]:
                if verb in name:
                    coverage["endpoints"].add(f"{verb}_{name}")

        return {k: list(v) for k, v in coverage.items()}
