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
            "existing_tests": self.existing_tests,
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
                    is_rest_class = "@RestController" in content or "@ResponseBody" in content
                    base_path = ""
                    base_match = class_request_mapping_pattern.search(content)
                    if base_match and base_match.group(1):
                        base_path = "/" + base_match.group(1).strip("/").strip()

                    lines = content.splitlines()
                    # Find class declaration line index to avoid matching class-level annotations
                    class_decl_idx = -1
                    for l_i, l_text in enumerate(lines):
                        if re.search(r'\b(?:public|protected|private)?\s*(?:abstract\s+)?class\b', l_text):
                            class_decl_idx = l_i
                            break

                    methods_found: list[dict[str, Any]] = []
                    for idx, line in enumerate(lines):
                        if class_decl_idx >= 0 and idx <= class_decl_idx and "RequestMapping" in line:
                            # Skip class-level @RequestMapping
                            continue

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
                            if full_path.endswith("/") and len(full_path) > 1:
                                full_path = full_path.rstrip("/")
                            if not full_path.startswith("/"):
                                full_path = "/" + full_path

                            # Infer method name from next few lines
                            handler_name = f"handle{ann_type.replace('MAPPING', '')}"
                            for next_line in lines[idx : min(idx + 5, len(lines))]:
                                fn_match = re.search(r'(?:public|protected|private)?\s+[\w\<\>\[\]]+\s+(\w+)\s*\(', next_line)
                                if fn_match:
                                    handler_name = fn_match.group(1)
                                    break

                            is_rest_ep = is_rest_class or full_path.startswith("/api/") or full_path.startswith("/rest/") or "ResponseBody" in content
                            ep_info = {
                                "method": method_http,
                                "endpoint": full_path,
                                "handler": handler_name,
                                "file": rel_path,
                                "class_name": filepath.stem,
                                "source": filepath.stem,
                                "is_rest": is_rest_ep,
                            }
                            methods_found.append(ep_info)
                            endpoints.append(ep_info)

                    controllers.append({
                        "name": filepath.stem,
                        "file": rel_path,
                        "base_path": base_path,
                        "endpoints": methods_found,
                        "is_rest": is_rest_class,
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

    def _extract_grounded_selectors(self, content: str) -> dict[str, Any]:
        """Extracts grounded DOM selectors, input fields, action buttons, and headings from template/JSX content."""
        selectors: list[str] = []
        input_fields: list[dict[str, str]] = []
        actions: list[str] = []
        headings: list[str] = []

        # 1. Extract explicit DOM IDs (e.g. id="search-owner-form", id="vets", id="main-navbar")
        id_pattern = re.compile(r'\bid=["\']([a-zA-Z0-9_\-]+)["\']')
        for m in id_pattern.finditer(content):
            val = m.group(1).strip()
            if val and val.lower() not in ["null", "undefined", "true", "false"]:
                selectors.append(f"#{val}")

        # 2. Extract Forms (e.g. form#search-owner-form or form)
        form_pattern = re.compile(r'<form\b([^>]*)>', re.IGNORECASE)
        for fm in form_pattern.finditer(content):
            attrs = fm.group(1)
            id_m = re.search(r'id=["\']([^"\']+)["\']', attrs)
            if id_m:
                selectors.append(f"form#{id_m.group(1)}")
            else:
                selectors.append("form")

        # 3. Extract Tables (e.g. table#vets or table)
        table_pattern = re.compile(r'<table\b([^>]*)>', re.IGNORECASE)
        for tm in table_pattern.finditer(content):
            attrs = tm.group(1)
            id_m = re.search(r'id=["\']([^"\']+)["\']', attrs)
            if id_m:
                selectors.append(f"table#{id_m.group(1)}")
            else:
                selectors.append("table")

        # 4. Extract Headings (h1, h2, h3) and heading text
        heading_pattern = re.compile(r'<(h1|h2|h3)\b[^>]*>(.*?)</\1>', re.IGNORECASE | re.DOTALL)
        for hm in heading_pattern.finditer(content):
            tag = hm.group(1).lower()
            raw_text = re.sub(r'<[^>]+>', '', hm.group(2)).strip()
            if raw_text:
                headings.append(raw_text)
            selectors.append(tag)

        # Fallback heading tags if self-closing or template tags
        if not headings:
            if re.search(r'<h1\b', content, re.IGNORECASE):
                selectors.append("h1")
            if re.search(r'<h2\b', content, re.IGNORECASE):
                selectors.append("h2")
            if re.search(r'<h3\b', content, re.IGNORECASE):
                selectors.append("h3")

        # 5. Extract Inputs
        input_pattern = re.compile(r'<input\b([^>]*)>', re.IGNORECASE)
        for im in input_pattern.finditer(content):
            attrs = im.group(1)
            name_m = re.search(r'name=["\']([^"\']+)["\']', attrs)
            th_field_m = re.search(r'th:field=["\'][*${]([^}]+)}["\']', attrs)
            type_m = re.search(r'type=["\']([^"\']+)["\']', attrs)

            field_name = name_m.group(1) if name_m else (th_field_m.group(1) if th_field_m else None)
            field_type = type_m.group(1) if type_m else "text"

            if field_name:
                field_name = field_name.replace("*", "").replace("{", "").replace("}", "").strip()
                selectors.append(f"input[name='{field_name}']")
                input_fields.append({"name": field_name, "type": field_type})

        # 6. Extract Action Buttons
        button_pattern = re.compile(r'<button\b([^>]*)>(.*?)</button>', re.IGNORECASE | re.DOTALL)
        for bm in button_pattern.finditer(content):
            attrs = bm.group(1)
            btn_text = re.sub(r'<[^>]+>', '', bm.group(2)).strip()
            if 'type="submit"' in attrs or "type='submit'" in attrs:
                selectors.append("button[type='submit']")
                actions.append("click button[type='submit']")
            elif 'class=' in attrs and 'btn' in attrs:
                cls_m = re.search(r'class=["\']([^"\']+)["\']', attrs)
                if cls_m:
                    first_cls = cls_m.group(1).split()[0]
                    selectors.append(f"button.{first_cls}")
                    actions.append(f"click button.{first_cls}")
            else:
                selectors.append("button")
                actions.append(f"click button: {btn_text}" if btn_text else "click button")

        # 7. Extract primary layout containers if present (e.g. .container-fluid, .container, .navbar, nav)
        if re.search(r'class=["\'][^"\']*\bcontainer-fluid\b', content):
            selectors.append(".container-fluid")
        elif re.search(r'class=["\'][^"\']*\bcontainer\b', content):
            selectors.append(".container")
        if re.search(r'<nav\b|class=["\'][^"\']*\bnavbar\b', content):
            selectors.append("nav")

        # Deduplicate selectors while preserving discovery priority
        dedup_selectors: list[str] = []
        seen = set()
        for s in selectors:
            if s not in seen:
                seen.add(s)
                dedup_selectors.append(s)

        return {
            "grounded_selectors": dedup_selectors,
            "input_fields": input_fields,
            "actions": actions,
            "headings": headings,
        }

    def _is_fragment_or_component(self, rel_path: str, filename: str, content: str) -> bool:
        """Determines if a file is an internal UI fragment, partial, or layout component rather than a standalone page."""
        path_lower = rel_path.lower().replace("\\", "/")
        name_lower = Path(filename).stem.lower()

        # 1. Directory heuristics for fragments and components
        fragment_dir_keywords = [
            "/fragments/",
            "/partials/",
            "/components/",
            "/includes/",
            "/common/",
            "/shared/",
            "/layouts/",
            "/widgets/",
            "/tags/",
        ]
        if any(kw in path_lower for kw in fragment_dir_keywords):
            return True

        # 2. Filename heuristics for fragments/components
        fragment_name_keywords = [
            "header",
            "footer",
            "head",
            "preheader",
            "nav",
            "navbar",
            "sidebar",
            "menu",
            "layout",
            "inputfield",
            "selectfield",
            "datepicker",
            "modal",
            "button",
            "card",
            "item",
            "banner",
        ]
        if name_lower in fragment_name_keywords:
            return True

        # 3. Thymeleaf th:fragment attribute without full HTML document
        if "th:fragment=" in content and not ("<!doctype html" in content.lower() or "<html" in content.lower()):
            return True

        return False

    def _scan_ui_workflows(self) -> list[dict[str, Any]]:
        ui_items: list[dict[str, Any]] = []
        extensions = [".html", ".jsp", ".jsx", ".tsx", ".vue", ".js", ".ts"]

        # Track template files mapped to controller routes
        discovered_templates: dict[str, dict[str, Any]] = {}
        spa_routes: list[dict[str, Any]] = []

        for root, dirs, files in os.walk(self.repo_dir):
            for skip in [".git", "node_modules", "target", "build", "venv", "__pycache__", "dist"]:
                if skip in dirs:
                    dirs.remove(skip)

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in extensions:
                    continue

                filepath = Path(root) / file
                rel_path = filepath.relative_to(self.repo_dir).as_posix()
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except Exception:  # noqa: BLE001, S110
                    continue  # nosec B110

                c_low = content.lower()

                # Check SPA React/Vue route declarations
                if ext in [".jsx", ".tsx", ".js", ".ts"]:
                    route_matches = re.finditer(r'<Route\s+(?:[^>]*\s+)?path=["\']([^"\']+)["\'](?:\s+element=\{<(\w+)|component=\{(\w+))?', content)
                    for rm in route_matches:
                        r_path = rm.group(1)
                        comp_name = rm.group(2) or rm.group(3) or "RouteView"
                        if r_path and "*" not in r_path:
                            spa_routes.append({
                                "name": comp_name,
                                "route": "/" + r_path.strip("/"),
                                "file": rel_path,
                                "type": "AUTH" if "login" in r_path.lower() or "auth" in r_path.lower() else "PAGE",
                            })

                # Check HTML/JSP/Vue templates
                is_template_file = ext in [".html", ".jsp", ".vue"] or "page" in file.lower() or "view" in file.lower()
                if is_template_file:
                    is_frag = self._is_fragment_or_component(rel_path, file, content)
                    dom_meta = self._extract_grounded_selectors(content)

                    has_login = "login" in file.lower() or "signin" in file.lower() or "auth" in file.lower() or "password" in c_low
                    has_form = len(dom_meta["input_fields"]) > 0 or "<form" in c_low
                    has_table = "<table" in c_low or "table#" in "".join(dom_meta["grounded_selectors"])

                    workflow_type = "AUTH" if has_login else "FORM" if has_form else "DASHBOARD" if has_table else "NAVIGATION"

                    template_key = Path(file).stem.lower()
                    discovered_templates[template_key] = {
                        "name": Path(file).stem,
                        "file": rel_path,
                        "type": workflow_type,
                        "has_login": has_login,
                        "has_form": has_form,
                        "has_table": has_table,
                        "is_fragment": is_frag,
                        "grounded_selectors": dom_meta["grounded_selectors"],
                        "input_fields": dom_meta["input_fields"],
                        "actions": dom_meta["actions"],
                        "headings": dom_meta["headings"],
                    }

        # Match Spring MVC Controller endpoints that return view templates
        endpoints, controllers = self._scan_controllers_and_endpoints()
        mapped_routes: set[str] = set()

        for ep in endpoints:
            ep_path = ep.get("endpoint", "/")
            method = ep.get("method", "GET").upper()
            if method != "GET":
                continue

            # NEVER treat REST API endpoints as UI pages
            if ep.get("is_rest") or ep_path.startswith("/api/") or ep_path.startswith("/rest/"):
                continue

            # Infer view template from endpoint path (e.g. /owners/find -> findOwners or find, /vets.html -> vetList)
            path_parts = [p for p in ep_path.strip("/").split("/") if p and not p.startswith("{")]
            candidate_names = [p.lower().replace(".html", "").replace(".jsp", "") for p in path_parts]

            matched_template = None
            for cn in reversed(candidate_names):
                cn_stem = cn.rstrip("s")
                if cn in discovered_templates and not discovered_templates[cn]["is_fragment"]:
                    matched_template = discovered_templates[cn]
                    break
                # Check for substring / stem match (e.g. "vet" in "vetlist", "find" in "findowners")
                for tk, tv in discovered_templates.items():
                    tk_stem = tk.rstrip("s")
                    if not tv["is_fragment"] and (cn in tk or tk in cn or cn_stem in tk or tk_stem in cn or (len(cn_stem) >= 3 and cn_stem in tk_stem)):
                        matched_template = tv
                        break
                if matched_template:
                    break

            norm_ep = "/" + ep_path.strip("/")
            if norm_ep not in mapped_routes:
                if matched_template:
                    mapped_routes.add(norm_ep)
                    ui_items.append({
                        "name": matched_template["name"],
                        "route": norm_ep,
                        "file": matched_template["file"],
                        "type": matched_template["type"],
                        "has_login": matched_template["has_login"],
                        "has_form": matched_template["has_form"],
                        "has_table": matched_template["has_table"],
                        "is_fragment": False,
                        "grounded_selectors": matched_template["grounded_selectors"],
                        "input_fields": matched_template["input_fields"],
                        "actions": matched_template["actions"],
                        "headings": matched_template["headings"],
                    })

        # Add SPA router routes
        for sr in spa_routes:
            if sr["route"] not in mapped_routes:
                mapped_routes.add(sr["route"])
                ui_items.append({
                    "name": sr["name"],
                    "route": sr["route"],
                    "file": sr["file"],
                    "type": sr["type"],
                    "has_login": "login" in sr["route"],
                    "has_form": True,
                    "has_table": False,
                    "is_fragment": False,
                    "grounded_selectors": ["form", "button", "input", "h1", "h2"],
                    "input_fields": [{"name": "username", "type": "text"}, {"name": "password", "type": "password"}] if "login" in sr["route"] else [],
                    "actions": ["click button"],
                    "headings": [],
                })

        # Add top-level non-fragment templates (e.g. welcome.html -> /, login.html -> /login)
        for t_key, t_val in discovered_templates.items():
            if t_val["is_fragment"]:
                continue
            default_route = "/" if t_key in ["welcome", "index", "home"] else f"/{t_key}"
            if default_route not in mapped_routes:
                mapped_routes.add(default_route)
                ui_items.append({
                    "name": t_val["name"],
                    "route": default_route,
                    "file": t_val["file"],
                    "type": t_val["type"],
                    "has_login": t_val["has_login"],
                    "has_form": t_val["has_form"],
                    "has_table": t_val["has_table"],
                    "is_fragment": False,
                    "grounded_selectors": t_val["grounded_selectors"],
                    "input_fields": t_val["input_fields"],
                    "actions": t_val["actions"],
                    "headings": t_val["headings"],
                })

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
                clean_name = re.sub(r'^(test_|test|should_?)', '', name).lower()
                coverage["scenarios"].add(clean_name)

            if cls:
                coverage["classes"].add(cls)
            if file:
                coverage["classes"].add(Path(file).stem.lower())

            for verb in ["get", "post", "put", "delete", "patch"]:
                if verb in name:
                    coverage["endpoints"].add(f"{verb}_{name}")

        return {k: list(v) for k, v in coverage.items()}

