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

        security_rules = self._scan_security_rules()
        endpoints, controllers = self._scan_controllers_and_endpoints(security_rules=security_rules)
        services = self._scan_services()
        repositories = self._scan_repositories()
        entities = self._scan_entities()
        ui_workflows = self._scan_ui_workflows(security_rules=security_rules)
        existing_coverage = self._map_existing_coverage()

        from app.application.use_cases.proposed_tests.authentication_manager import AuthenticationManager
        credentials = [
            {"username": c.username, "password": c.password, "source": c.source, "role": c.role}
            for c in AuthenticationManager(self.repo_dir).discover_credentials()
        ]

        return {
            "controllers": controllers,
            "endpoints": endpoints,
            "services": services,
            "repositories": repositories,
            "entities": entities,
            "ui_workflows": ui_workflows,
            "existing_coverage": existing_coverage,
            "existing_tests": self.existing_tests,
            "security_rules": security_rules,
            "credentials": credentials,
        }

    # ── private helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_path_params(endpoint_path: str) -> list[str]:
        """Returns a list of path variable names from a URL template, e.g. /items/{id} → ['id']."""
        return re.findall(r'\{([^}]+)\}', endpoint_path)

    @staticmethod
    def _parse_handler_params(param_string: str) -> dict[str, Any]:
        """Parses a Java/Kotlin method parameter list and returns discovered request body type and path vars.

        Returns:
            {
              "request_body_type": str | None,   # e.g. "Employee", "TodoItem"
              "path_vars": list[str],            # e.g. ["id", "userId"]
              "has_request_body": bool,
            }
        """
        request_body_type: str | None = None
        path_vars: list[str] = []
        has_request_body = False

        if not param_string or not param_string.strip():
            return {"request_body_type": None, "path_vars": [], "has_request_body": False}

        # Split on commas that are NOT inside angle brackets
        parts: list[str] = []
        depth = 0
        current = ""
        for ch in param_string:
            if ch in "<([":
                depth += 1
                current += ch
            elif ch in ">)]":
                depth -= 1
                current += ch
            elif ch == "," and depth == 0:
                parts.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            parts.append(current.strip())

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # @RequestBody SomeType varName  →  request_body_type = SomeType
            rb_match = re.search(
                r'@RequestBody\s+(?:[\w<>\[\],?\s]+\s+)?(\w+)\s+\w+',
                part,
                re.IGNORECASE,
            )
            if rb_match:
                has_request_body = True
                request_body_type = rb_match.group(1)
                continue

            # Simpler: @RequestBody and just grab the Java type token before the param name
            if "@RequestBody" in part:
                has_request_body = True
                tokens = re.findall(r'\b([A-Z][a-zA-Z0-9]+)\b', part)
                if tokens:
                    request_body_type = tokens[0]
                continue

            # @PathVariable ... Long id  or  @PathVariable("id") Long id
            if "@PathVariable" in part:
                # try  @PathVariable("name") Type varName
                pv_explicit = re.search(r'@PathVariable\(["\']?(\w+)["\']?\)', part)
                if pv_explicit:
                    path_vars.append(pv_explicit.group(1))
                else:
                    # grab last token (the variable name)
                    last_tok = re.findall(r'\b(\w+)\b', part)
                    if last_tok:
                        path_vars.append(last_tok[-1])

        return {
            "request_body_type": request_body_type,
            "path_vars": path_vars,
            "has_request_body": has_request_body,
        }

    def _build_entity_field_map(self) -> dict[str, dict[str, str]]:
        """Scans entity/model/DTO classes and returns a map of class name → {field: type}.

        Only considers Java/Kotlin fields annotated with @Column, declared as private, or
        detected as Lombok/JPA fields.  Returns realistic field types so the generator
        can construct plausible (non-hallucinated) request bodies.
        """
        field_map: dict[str, dict[str, str]] = {}
        type_aliases: dict[str, str] = {
            "String": "string", "Integer": "integer", "int": "integer",
            "Long": "integer", "long": "integer", "Double": "number",
            "double": "number", "Float": "number", "float": "number",
            "Boolean": "boolean", "bool": "boolean", "boolean": "boolean",
            "LocalDate": "date", "LocalDateTime": "datetime",
            "Date": "date", "BigDecimal": "number",
        }
        # Primitive/wrapper sample values
        sample_values: dict[str, Any] = {
            "string": "sample", "integer": 1, "number": 1.0,
            "boolean": True, "date": "2024-01-01", "datetime": "2024-01-01T00:00:00Z",
        }

        for root, dirs, files in os.walk(self.repo_dir):
            for skip in [".git", "node_modules", "target", "build", "venv", "__pycache__", "dist"]:
                if skip in dirs:
                    dirs.remove(skip)

            for file in files:
                if not file.endswith((".java", ".kt")):
                    continue
                # Only scan model / entity / DTO / request files
                name_lower = file.lower()
                if not any(
                    k in name_lower
                    for k in ["entity", "model", "dto", "request", "response", "record"]
                ):
                    # Still include files in model / entity dirs
                    rel = str(Path(root).relative_to(self.repo_dir)).lower().replace("\\", "/")
                    if not any(
                        k in rel
                        for k in ["model", "entity", "dto", "domain", "payload"]
                    ):
                        continue

                filepath = Path(root) / file
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except Exception:  # noqa: BLE001
                    continue

                class_name = filepath.stem
                fields: dict[str, Any] = {}

                # Match: private/protected TypeName fieldName; (Java)
                field_pattern = re.compile(
                    r'(?:@[\w(]+\s*)*(?:private|protected)\s+([\w<>\[\],?\s]+?)\s+(\w+)\s*;',
                    re.MULTILINE,
                )
                for fm in field_pattern.finditer(content):
                    raw_type = fm.group(1).strip().split()[-1]  # last word is base type
                    field_name = fm.group(2)
                    # Skip static / id / version fields
                    if field_name.lower() in {"id", "version", "serialversionuid", "log", "logger"}:
                        continue
                    # Strip generics wrapper
                    base = re.sub(r'<.*>', '', raw_type).strip()
                    java_kind = type_aliases.get(base, "string")
                    sample = sample_values.get(java_kind, "value")
                    fields[field_name] = sample

                if fields:
                    field_map[class_name] = fields

        return field_map

    def _scan_security_rules(self) -> dict[str, Any]:
        """Scans WebFilter, Spring Security configs, and route guards to discover authentication rules."""
        rules: dict[str, Any] = {
            "has_auth": False,
            "public_patterns": [],
            "protected_patterns": [],
            "rule_sources": {},
        }
        for root, dirs, files in os.walk(self.repo_dir):
            for skip in [".git", "node_modules", "target", "build", "venv", "__pycache__", "dist"]:
                if skip in dirs:
                    dirs.remove(skip)
            for file in files:
                if not file.endswith((".java", ".kt", ".xml", ".ts", ".js", ".py")):
                    continue
                filepath = Path(root) / file
                rel_path = filepath.relative_to(self.repo_dir).as_posix()
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                # 1. Java Servlet WebFilter e.g. @WebFilter(urlPatterns = "*.do")
                if "@WebFilter" in content:
                    rules["has_auth"] = True
                    wf_match = re.search(r'@WebFilter\s*\([^)]*urlPatterns\s*=\s*(?:["\']([^"\']+)["\']|{\s*([^}]+)\s*})', content)
                    if wf_match:
                        raw_pts = [wf_match.group(1)] if wf_match.group(1) else [p.strip().strip('"').strip("'") for p in wf_match.group(2).split(",")]
                        for p in raw_pts:
                            rules["protected_patterns"].append(p)
                            rules["rule_sources"][p] = f"{rel_path}: @WebFilter(urlPatterns = '{p}')"
                    else:
                        wf_direct = re.search(r'@WebFilter\s*\(\s*["\']([^"\']+)["\']\s*\)', content)
                        if wf_direct:
                            p = wf_direct.group(1)
                            rules["protected_patterns"].append(p)
                            rules["rule_sources"][p] = f"{rel_path}: @WebFilter('{p}')"

                # 2. Spring Security configs
                if "SecurityFilterChain" in content or "WebSecurityConfigurerAdapter" in content or "@EnableWebSecurity" in content:
                    rules["has_auth"] = True
                    for m in re.finditer(r'antMatchers\s*\(\s*([^)]+)\)\s*\.permitAll\(\)', content):
                        for rp in m.group(1).split(","):
                            clean_p = rp.strip().strip('"').strip("'")
                            rules["public_patterns"].append(clean_p)
                            rules["rule_sources"][clean_p] = f"{rel_path}: antMatchers('{clean_p}').permitAll()"
                    for m in re.finditer(r'antMatchers\s*\(\s*([^)]+)\)\s*\.authenticated\(\)', content):
                        for rp in m.group(1).split(","):
                            clean_p = rp.strip().strip('"').strip("'")
                            rules["protected_patterns"].append(clean_p)
                            rules["rule_sources"][clean_p] = f"{rel_path}: antMatchers('{clean_p}').authenticated()"
                    if ".anyRequest().authenticated()" in content:
                        rules["protected_patterns"].append("/**")
                        rules["rule_sources"]["/**"] = f"{rel_path}: .anyRequest().authenticated()"
                    elif ".anyRequest().permitAll()" in content:
                        rules["public_patterns"].append("/**")
                        rules["rule_sources"]["/**"] = f"{rel_path}: .anyRequest().permitAll()"

        return rules

    @staticmethod
    def _evaluate_endpoint_security(endpoint: str, security_rules: dict[str, Any]) -> tuple[bool, str]:
        """Evaluates whether an endpoint path requires authentication, citing source evidence."""
        ep_norm = "/" + endpoint.lstrip("/").lower()
        # Explicit public auth/register endpoints
        if any(k in ep_norm for k in ["login", "signin", "register", "signup", "auth/token", "oauth"]):
            return False, "Public authentication/registration endpoint"
        for pub in security_rules.get("public_patterns", []):
            pub_norm = pub.lower()
            if pub_norm == "/**" or pub_norm == "*" or ep_norm == pub_norm or (pub_norm.endswith("/**") and ep_norm.startswith(pub_norm[:-3])):
                return False, security_rules.get("rule_sources", {}).get(pub, f"Public rule {pub}")
        for prot in security_rules.get("protected_patterns", []):
            prot_norm = prot.lower()
            if prot_norm == "/**" or prot_norm == "*" or ep_norm == prot_norm:
                return True, security_rules.get("rule_sources", {}).get(prot, f"Protected rule {prot}")
            if prot_norm.startswith("*.") and ep_norm.endswith(prot_norm[1:]):
                return True, security_rules.get("rule_sources", {}).get(prot, f"Protected rule {prot}")
            if prot_norm.endswith("/**") and ep_norm.startswith(prot_norm[:-3]):
                return True, security_rules.get("rule_sources", {}).get(prot, f"Protected rule {prot}")
        if security_rules.get("has_auth", False):
            return True, "Security configured in repository; endpoint requires authentication by default"
        return False, "No security constraints or filters active on endpoint"

    def _scan_controllers_and_endpoints(
        self,
        security_rules: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        endpoints: list[dict[str, Any]] = []
        controllers: list[dict[str, Any]] = []
        sec_rules = security_rules or self._scan_security_rules()

        # Pre-scan entity fields so we can attach them to endpoints
        entity_field_map = self._build_entity_field_map()

        mapping_pattern = re.compile(
            r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\s*(?:\(\s*(?:value\s*=\s*|path\s*=\s*)?["\']([^"\']*)["\']|\(\s*\{([^}]+)\}|\s*)',
            re.IGNORECASE,
        )
        class_request_mapping_pattern = re.compile(
            r'@RequestMapping\s*(?:\(\s*(?:value\s*=\s*|path\s*=\s*)?["\']([^"\']*)["\']|\s*)',
            re.IGNORECASE,
        )
        method_sig_pattern = re.compile(
            r'(?:public|protected|private)?\s+[\w\<\>\[\]?,\s]+\s+(\w+)\s*\(([^)]*)\)',
            re.DOTALL,
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
                except Exception:
                    continue

                # ── 1. Java / Spring Boot Controllers ─────────────────────────────
                if "@RestController" in content or "@Controller" in content or ("Controller" in file and not "Servlet" in file):
                    is_rest_class = "@RestController" in content or "@ResponseBody" in content
                    base_path = ""
                    base_match = class_request_mapping_pattern.search(content)
                    if base_match and base_match.group(1):
                        base_path = "/" + base_match.group(1).strip("/").strip()

                    lines = content.splitlines()
                    class_decl_idx = -1
                    for l_i, l_text in enumerate(lines):
                        if re.search(r'\b(?:public|protected|private)?\s*(?:abstract\s+)?class\b', l_text):
                            class_decl_idx = l_i
                            break

                    methods_found: list[dict[str, Any]] = []
                    for idx, line in enumerate(lines):
                        if class_decl_idx >= 0 and idx <= class_decl_idx and "RequestMapping" in line:
                            continue

                        match = mapping_pattern.search(line)
                        if match:
                            ann_type = match.group(1).upper()
                            sub_path = (match.group(2) or "").strip().strip("/")
                            if not sub_path and match.group(3):
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

                            handler_name = f"handle{ann_type.replace('MAPPING', '')}"
                            handler_params_info: dict[str, Any] = {}
                            snippet = "\n".join(lines[idx: min(idx + 12, len(lines))])
                            sig_match = method_sig_pattern.search(snippet)
                            if sig_match:
                                handler_name = sig_match.group(1)
                                handler_params_info = self._parse_handler_params(sig_match.group(2))
                            else:
                                for next_line in lines[idx: min(idx + 5, len(lines))]:
                                    fn_match = re.search(r'(?:public|protected|private)?\s+[\w\<\>\[\]]+\s+(\w+)\s*\(', next_line)
                                    if fn_match:
                                        handler_name = fn_match.group(1)
                                        break

                            request_body_sample: dict[str, Any] | None = None
                            request_body_type = handler_params_info.get("request_body_type")
                            if handler_params_info.get("has_request_body") and method_http in ("POST", "PUT", "PATCH"):
                                if request_body_type and request_body_type in entity_field_map:
                                    request_body_sample = dict(entity_field_map[request_body_type])
                                else:
                                    for ent_name, ent_fields in entity_field_map.items():
                                        if (
                                            ent_name.lower().rstrip("dto") == (request_body_type or "").lower().rstrip("dto")
                                            or (request_body_type and request_body_type.lower() in ent_name.lower())
                                        ):
                                            request_body_sample = dict(ent_fields)
                                            break

                            path_params = self._extract_path_params(full_path)
                            pv_from_handler = handler_params_info.get("path_vars", [])
                            all_path_params = list(dict.fromkeys(path_params + pv_from_handler))
                            param_sources = {p: f"{rel_path}: @PathVariable('{p}') in {handler_name}" for p in all_path_params}

                            # Derive classification from source evidence (Fix 7)
                            is_rest_ep = is_rest_class or full_path.startswith("/api/") or full_path.startswith("/rest/") or "ResponseBody" in snippet or "ResponseEntity" in snippet
                            if "redirect:" in snippet:
                                classification = "REDIRECT"
                                classification_source = f"{rel_path}: returns 'redirect:' view in {handler_name}()"
                                expected_status = 302
                                expected_status_source = f"{rel_path}: Spring redirect view returns HTTP 302"
                            elif is_rest_ep:
                                classification = "REST_API"
                                classification_source = f"{rel_path}: @RestController or ResponseEntity in {handler_name}()"
                                expected_status = 200
                                expected_status_source = f"{rel_path}: Method {handler_name}() return"
                            else:
                                classification = "HTML_MVC"
                                classification_source = f"{rel_path}: @Controller view template in {handler_name}()"
                                expected_status = 200
                                expected_status_source = f"{rel_path}: Controller view render returns HTTP 200"

                            # Derive expected status from source evidence (Fix 6)
                            rs_match = re.search(r'@ResponseStatus\s*\(\s*(?:value\s*=\s*|code\s*=\s*)?(?:HttpStatus\.)?([A-Z_0-9]+)', snippet)
                            if rs_match:
                                code_name = rs_match.group(1).upper()
                                status_map = {"CREATED": 201, "NO_CONTENT": 204, "OK": 200, "ACCEPTED": 202, "BAD_REQUEST": 400, "NOT_FOUND": 404}
                                if code_name in status_map:
                                    expected_status = status_map[code_name]
                                    expected_status_source = f"{rel_path}: @ResponseStatus({code_name})"
                            elif "ResponseEntity.created" in snippet or "HttpStatus.CREATED" in snippet:
                                expected_status = 201
                                expected_status_source = f"{rel_path}: ResponseEntity.created() in {handler_name}()"
                            elif "ResponseEntity.noContent" in snippet or "HttpStatus.NO_CONTENT" in snippet:
                                expected_status = 204
                                expected_status_source = f"{rel_path}: ResponseEntity.noContent() in {handler_name}()"

                            auth_req, auth_src = self._evaluate_endpoint_security(full_path, sec_rules)

                            ep_info: dict[str, Any] = {
                                "method": method_http,
                                "endpoint": full_path,
                                "handler": handler_name,
                                "file": rel_path,
                                "class_name": filepath.stem,
                                "source": filepath.stem,
                                "is_rest": is_rest_ep,
                                "classification": classification,
                                "classification_source": classification_source,
                                "expected_status": expected_status,
                                "expected_status_source": expected_status_source,
                                "authentication_required": auth_req,
                                "authentication_source": auth_src,
                                "path_params": all_path_params,
                                "parameter_sources": param_sources,
                                "request_body_type": request_body_type,
                                "request_body_sample": request_body_sample,
                                "has_request_body": handler_params_info.get("has_request_body", method_http in ("POST", "PUT", "PATCH")),
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

                # ── 2. Java EE Servlets (@WebServlet or extends HttpServlet) ───────
                elif "@WebServlet" in content or "extends HttpServlet" in content:
                    servlet_patterns: list[str] = []
                    ws_match = re.search(r'@WebServlet\s*\([^)]*(?:urlPatterns|value)\s*=\s*(?:["\']([^"\']+)["\']|{\s*([^}]+)\s*})', content)
                    if ws_match:
                        if ws_match.group(1):
                            servlet_patterns.append(ws_match.group(1))
                        elif ws_match.group(2):
                            servlet_patterns.extend([p.strip().strip('"').strip("'") for p in ws_match.group(2).split(",")])
                    else:
                        ws_direct = re.search(r'@WebServlet\s*\(\s*["\']([^"\']+)["\']\s*\)', content)
                        if ws_direct:
                            servlet_patterns.append(ws_direct.group(1))

                    if not servlet_patterns:
                        s_name = filepath.stem.lower().replace("servlet", "")
                        servlet_patterns.append(f"/{s_name}.do")

                    servlet_eps: list[dict[str, Any]] = []
                    for s_pat in servlet_patterns:
                        norm_pat = "/" + s_pat.lstrip("/")
                        for method_name, method_http in [("doGet", "GET"), ("doPost", "POST"), ("doPut", "PUT"), ("doDelete", "DELETE")]:
                            m_idx = content.find(f"void {method_name}")
                            if m_idx == -1:
                                m_idx = content.find(f"{method_name}(")
                            if m_idx == -1:
                                continue

                            method_body = content[m_idx: m_idx + 1500]
                            param_matches = re.findall(r'request\.getParameter\s*\(\s*["\']([^"\']+)["\']\s*\)', method_body)
                            param_sources = {p: f"{rel_path}: request.getParameter('{p}') in {method_name}()" for p in param_matches}

                            classification = "HTML_MVC"
                            classification_source = f"{rel_path}: Servlet {method_name}()"
                            expected_status = 200
                            expected_status_source = f"{rel_path}: {method_name}() renders view"

                            sr_m = re.search(r'response\.sendRedirect\s*\(\s*["\']([^"\']+)["\']\s*\)', method_body)
                            rd_m = re.search(r'request\.getRequestDispatcher\s*\(\s*["\']([^"\']+)["\']\s*\)\.forward', method_body)

                            if sr_m:
                                classification = "REDIRECT"
                                classification_source = f"{rel_path}: response.sendRedirect('{sr_m.group(1)}')"
                                expected_status = 302
                                expected_status_source = f"{rel_path}: sendRedirect returns HTTP 302"
                            elif rd_m:
                                classification = "HTML_MVC"
                                classification_source = f"{rel_path}: forward to {rd_m.group(1)}"
                                expected_status = 200
                                expected_status_source = f"{rel_path}: forward renders JSP view HTTP 200"

                            auth_req, auth_src = self._evaluate_endpoint_security(norm_pat, sec_rules)

                            ep_entry = {
                                "method": method_http,
                                "endpoint": norm_pat,
                                "handler": method_name,
                                "file": rel_path,
                                "class_name": filepath.stem,
                                "source": filepath.stem,
                                "is_rest": classification == "REST_API",
                                "classification": classification,
                                "classification_source": classification_source,
                                "expected_status": expected_status,
                                "expected_status_source": expected_status_source,
                                "authentication_required": auth_req,
                                "authentication_source": auth_src,
                                "path_params": self._extract_path_params(norm_pat),
                                "query_params": param_matches,
                                "parameter_sources": param_sources,
                                "request_body_sample": None,
                                "has_request_body": method_http in ("POST", "PUT", "PATCH") and not param_matches,
                            }
                            servlet_eps.append(ep_entry)
                            endpoints.append(ep_entry)

                    controllers.append({
                        "name": filepath.stem,
                        "file": rel_path,
                        "base_path": "",
                        "endpoints": servlet_eps,
                        "is_rest": False,
                    })

                # ── 3. Python FastAPI / Flask routes ──────────────────────────────
                elif "@app." in content or "@router." in content:
                    py_route_pattern = re.compile(
                        r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                        re.IGNORECASE,
                    )
                    for match in py_route_pattern.finditer(content):
                        method_http = match.group(1).upper()
                        path = match.group(2)
                        path_params = self._extract_path_params(path)
                        auth_req, auth_src = self._evaluate_endpoint_security(path, sec_rules)
                        endpoints.append({
                            "method": method_http,
                            "endpoint": path,
                            "handler": "route_handler",
                            "file": rel_path,
                            "class_name": filepath.stem,
                            "source": filepath.stem,
                            "is_rest": True,
                            "classification": "REST_API",
                            "classification_source": f"{rel_path}: FastAPI/Flask route",
                            "expected_status": 200 if method_http != "POST" else 201,
                            "expected_status_source": f"{rel_path}: FastAPI route handler",
                            "authentication_required": auth_req,
                            "authentication_source": auth_src,
                            "path_params": path_params,
                            "parameter_sources": {p: f"{rel_path}: path parameter '{p}'" for p in path_params},
                            "request_body_sample": None,
                            "has_request_body": method_http in ("POST", "PUT", "PATCH"),
                        })

                # ── 4. Express.js routes ──────────────────────────────────────────
                elif "router." in content or "app." in content:
                    js_route_pattern = re.compile(
                        r'(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                        re.IGNORECASE,
                    )
                    for match in js_route_pattern.finditer(content):
                        method_http = match.group(1).upper()
                        path = match.group(2)
                        path_params = self._extract_path_params(path)
                        auth_req, auth_src = self._evaluate_endpoint_security(path, sec_rules)
                        endpoints.append({
                            "method": method_http,
                            "endpoint": path,
                            "handler": "express_handler",
                            "file": rel_path,
                            "class_name": filepath.stem,
                            "source": filepath.stem,
                            "is_rest": True,
                            "classification": "REST_API",
                            "classification_source": f"{rel_path}: Express.js route",
                            "expected_status": 200,
                            "expected_status_source": f"{rel_path}: Express.js handler",
                            "authentication_required": auth_req,
                            "authentication_source": auth_src,
                            "path_params": path_params,
                            "parameter_sources": {p: f"{rel_path}: route parameter '{p}'" for p in path_params},
                            "request_body_sample": None,
                            "has_request_body": method_http in ("POST", "PUT", "PATCH"),
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

        # 5. Extract Inputs, Selects, Textareas, and Table Headers
        table_headers: list[str] = []
        submit_btn_text: str | None = None

        # Extract table column headers (HTML <th> or React Table columns: header: 'Name')
        th_pattern = re.compile(r'<th\b[^>]*>(.*?)</th>', re.IGNORECASE | re.DOTALL)
        for th in th_pattern.finditer(content):
            th_txt = re.sub(r'<[^>]+>', '', th.group(1)).strip()
            if th_txt and th_txt not in table_headers:
                table_headers.append(th_txt)
        react_col_pattern = re.compile(r'header:\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
        for rc in react_col_pattern.finditer(content):
            col_txt = rc.group(1).strip()
            if col_txt and col_txt not in table_headers:
                table_headers.append(col_txt)

        # Scan label elements for association with inputs
        label_map: dict[int, str] = {}
        for lm in re.finditer(r'<label\b[^>]*>(.*?)</label>', content, re.IGNORECASE | re.DOTALL):
            lbl_txt = re.sub(r'<[^>]+>', '', lm.group(1)).strip()
            if lbl_txt:
                label_map[lm.end()] = lbl_txt

        def _find_nearest_label(pos: int) -> str | None:
            best_lbl = None
            min_dist = 400
            for lbl_pos, lbl_txt in label_map.items():
                if 0 <= (pos - lbl_pos) < min_dist:
                    min_dist = pos - lbl_pos
                    best_lbl = lbl_txt
            return best_lbl

        input_pattern = re.compile(r'<(input|select|textarea)\b([^>]*)>(?:(.*?)</\1>)?', re.IGNORECASE | re.DOTALL)
        for im in input_pattern.finditer(content):
            el_tag = im.group(1).lower()
            attrs = im.group(2)
            testid_m = re.search(r'data-testid=["\']([^"\']+)["\']', attrs)
            id_m = re.search(r'id=["\']([^"\']+)["\']', attrs)
            name_m = re.search(r'name=["\']([^"\']+)["\']', attrs)
            th_field_m = re.search(r'th:field=["\'][*${]([^}]+)}["\']', attrs)
            val_m = re.search(r'value=\{?(?:formData\.)?([a-zA-Z0-9_]+)\}?', attrs)
            type_m = re.search(r'type=["\']([^"\']+)["\']', attrs)
            aria_label_m = re.search(r'aria-label=["\']([^"\']+)["\']', attrs)
            placeholder_m = re.search(r'placeholder=["\']([^"\']+)["\']', attrs)
            req_m = "required" in attrs.lower()

            field_type = type_m.group(1).lower() if type_m else ("select" if el_tag == "select" else "textarea" if el_tag == "textarea" else "text")
            if field_type in ["hidden", "submit", "button", "reset"]:
                continue

            nearest_lbl = _find_nearest_label(im.start())
            field_name = name_m.group(1) if name_m else (th_field_m.group(1) if th_field_m else (id_m.group(1) if id_m else (val_m.group(1) if val_m and val_m.group(1) not in ["e", "true", "false"] else None)))
            if not field_name and nearest_lbl:
                field_name = re.sub(r'[^a-zA-Z0-9]', '', nearest_lbl.lower())

            if field_name:
                field_name = field_name.replace("*", "").replace("{", "").replace("}", "").strip()

            # Selector Resolution Priority (Fix 4):
            # data-testid → id → name → label → role+accessible-name / placeholder → tag
            if testid_m:
                selector = f"[data-testid='{testid_m.group(1)}']"
                selector_source = f"data-testid='{testid_m.group(1)}'"
            elif id_m:
                selector = f"#{id_m.group(1)}"
                selector_source = f"id='{id_m.group(1)}'"
            elif name_m:
                selector = f"{el_tag}[name='{name_m.group(1)}']"
                selector_source = f"name='{name_m.group(1)}'"
            elif nearest_lbl:
                selector = f"label:has-text('{nearest_lbl}') >> {el_tag}"
                selector_source = f"label='{nearest_lbl}'"
            elif aria_label_m:
                selector = f"{el_tag}[aria-label='{aria_label_m.group(1)}']"
                selector_source = f"aria-label='{aria_label_m.group(1)}'"
            elif placeholder_m:
                selector = f"{el_tag}[placeholder='{placeholder_m.group(1)}']"
                selector_source = f"placeholder='{placeholder_m.group(1)}'"
            else:
                selector = el_tag
                selector_source = f"HTML <{el_tag}>"

            # Interaction-Type Mapping from real DOM type (Fix 5):
            if el_tag == "select":
                playwright_action = "selectOption"
            elif field_type == "checkbox":
                playwright_action = "check"
            elif field_type == "radio":
                playwright_action = "check"
            elif field_type == "file":
                playwright_action = "setInputFiles"
            else:
                playwright_action = "fill"

            selectors.append(selector)
            input_fields.append({
                "name": field_name or selector,
                "label": nearest_lbl or (aria_label_m.group(1) if aria_label_m else (placeholder_m.group(1) if placeholder_m else field_name or selector)),
                "type": field_type,
                "tag": el_tag,
                "selector": selector,
                "selector_source": selector_source,
                "playwright_action": playwright_action,
                "required": req_m,
            })

        # 6. Extract Action Buttons with Priority Selectors
        button_pattern = re.compile(r'<button\b([^>]*)>(.*?)</button>', re.IGNORECASE | re.DOTALL)
        for bm in button_pattern.finditer(content):
            attrs = bm.group(1)
            btn_text = re.sub(r'<[^>]+>', '', bm.group(2)).strip()
            testid_m = re.search(r'data-testid=["\']([^"\']+)["\']', attrs)
            id_m = re.search(r'id=["\']([^"\']+)["\']', attrs)
            name_m = re.search(r'name=["\']([^"\']+)["\']', attrs)
            is_submit = 'type="submit"' in attrs or "type='submit'" in attrs
            b_low = btn_text.lower()
            is_cancel = any(k in b_low for k in ["cancel", "reset", "back", "close"])
            is_logout = any(k in b_low for k in ["logout", "sign out", "log out"])

            if testid_m:
                btn_sel = f"[data-testid='{testid_m.group(1)}']"
                btn_sel_source = f"data-testid='{testid_m.group(1)}'"
            elif id_m:
                btn_sel = f"#{id_m.group(1)}"
                btn_sel_source = f"id='{id_m.group(1)}'"
            elif is_submit:
                btn_sel = "button[type='submit']"
                btn_sel_source = "button[type='submit']"
            elif btn_text:
                btn_sel = f"button:has-text('{btn_text}')"
                btn_sel_source = f"button text '{btn_text}'"
            elif name_m:
                btn_sel = f"button[name='{name_m.group(1)}']"
                btn_sel_source = f"name='{name_m.group(1)}'"
            else:
                btn_sel = "button"
                btn_sel_source = "HTML <button>"

            if is_submit or any(k in b_low for k in ["save", "submit", "create", "add", "record", "apply", "confirm"]):
                if not is_cancel and not is_logout:
                    if not submit_btn_text:
                        submit_btn_text = btn_text or "Submit"
                    selectors.append(btn_sel)
                    actions.append(f"click {btn_sel}")
            elif 'class=' in attrs and 'btn' in attrs:
                cls_m = re.search(r'class=["\']([^"\']+)["\']', attrs)
                if cls_m:
                    first_cls = cls_m.group(1).split()[0]
                    selectors.append(f"button.{first_cls}")
                    actions.append(f"click button.{first_cls}")
            elif not is_logout:
                selectors.append(btn_sel)
                actions.append(f"click {btn_sel}")

        # 7. Extract primary layout containers if present (e.g. .container-fluid, .container, .navbar, nav)
        if re.search(r'class=["\'][^"\']*\bcontainer-fluid\b', content):
            selectors.append(".container-fluid")
        elif re.search(r'class=["\'][^"\']*\bcontainer\b', content):
            selectors.append(".container")
        if re.search(r'<nav\b|class=["\'][^"\']*\bnavbar\b', content):
            selectors.append("nav")
        if re.search(r'class=["\'][^"\']*\bstat-card\b', content):
            selectors.append(".stat-card")
        if re.search(r'class=["\'][^"\']*\bdashboard-grid\b', content):
            selectors.append(".dashboard-grid")

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
            "table_headers": table_headers,
            "submit_button": submit_btn_text,
            "has_form": bool(input_fields) or "<form" in content.lower(),
            "has_table": bool(table_headers) or "<table" in content.lower(),
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

    def _scan_ui_workflows(self, security_rules: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ui_items: list[dict[str, Any]] = []
        extensions = [".html", ".jsp", ".jsx", ".tsx", ".vue", ".js", ".ts"]

        # Track template files mapped to controller routes
        discovered_templates: dict[str, dict[str, Any]] = {}
        spa_routes: list[dict[str, Any]] = []
        components_by_stem: dict[str, dict[str, Any]] = {}

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

                file_stem = Path(file).stem.lower()
                components_by_stem[file_stem] = {
                    "name": Path(file).stem,
                    "file": rel_path,
                    "ext": ext,
                    "content": content,
                }
                c_low = content.lower()

                # Check SPA React/Vue route declarations
                if ext in [".jsx", ".tsx", ".js", ".ts"]:
                    # Check for index route: <Route index element={<Dashboard />} />
                    index_matches = re.finditer(r'<Route\s+index(?:\s+element=\{<(\w+)|component=\{(\w+))?', content)
                    for im in index_matches:
                        comp_name = im.group(1) or im.group(2) or "Dashboard"
                        spa_routes.append({
                            "name": comp_name,
                            "route": "/",
                            "file": rel_path,
                        })

                    # Check for path routes: <Route path="..." element={<Comp ...
                    route_matches = re.finditer(r'<Route\s+(?:[^>]*\s+)?path=["\']([^"\']+)["\'](?:\s+element=\{<(\w+)|component=\{(\w+))?', content)
                    for rm in route_matches:
                        r_path = rm.group(1)
                        comp_name = rm.group(2) or rm.group(3) or "RouteView"
                        if r_path and "*" not in r_path:
                            # Skip layout shells like Layout, AppLayout, RootLayout
                            if comp_name.lower() in ["layout", "applayout", "rootlayout"] or "layout" in r_path.lower():
                                continue
                    # Check for Angular router routes: { path: 'login', component: LoginComponent }
                    ang_matches = re.finditer(r"\{\s*path:\s*['\"]([^'\"]*)['\"]\s*,\s*component:\s*(\w+)", content)
                    for am in ang_matches:
                        r_path = am.group(1).rstrip(".")
                        comp_name = am.group(2)
                        if not r_path or "*" in r_path:
                            continue
                        c_low = comp_name.lower()
                        if any(k in c_low for k in ["footer", "header", "nav", "layout"]):
                            continue
                        norm_r = "/" + r_path.strip("/")
                        spa_routes.append({
                            "name": comp_name,
                            "route": norm_r,
                            "file": rel_path,
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
                        "table_headers": dom_meta.get("table_headers", []),
                        "submit_button": dom_meta.get("submit_button"),
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
                        "table_headers": matched_template.get("table_headers", []),
                        "submit_button": matched_template.get("submit_button"),
                    })

        # Add SPA router routes with component-grounded DOM metadata
        for sr in spa_routes:
            if sr["route"] not in mapped_routes:
                mapped_routes.add(sr["route"])
                comp_key = sr["name"].lower()
                comp_data = components_by_stem.get(comp_key)
                if not comp_data:
                    comp_data = components_by_stem.get(comp_key.rstrip("s"))

                tmpl_content = comp_data["content"] if comp_data else None
                if tmpl_content:
                    tmpl_m = re.search(r'template:\s*`([^`]*)`', tmpl_content, re.DOTALL)
                    if tmpl_m:
                        tmpl_content = tmpl_m.group(1)
                comp_meta = self._extract_grounded_selectors(tmpl_content) if tmpl_content else None

                if comp_meta:
                    has_login = "login" in comp_key or "login" in sr["route"].lower() or "auth" in comp_key or comp_meta.get("has_login", False)
                    has_table = comp_meta.get("has_table", False) or "list" in comp_key
                    has_form = comp_meta.get("has_form", False) and not has_table
                    workflow_type = "AUTH" if has_login else "FORM" if has_form else "TABLE" if has_table else "DASHBOARD" if "dashboard" in comp_key else "NAVIGATION"

                    ui_items.append({
                        "name": sr["name"],
                        "route": sr["route"],
                        "file": comp_data["file"] if comp_data else sr["file"],
                        "type": workflow_type,
                        "has_login": has_login,
                        "has_form": has_form,
                        "has_table": has_table,
                        "is_fragment": False,
                        "grounded_selectors": comp_meta["grounded_selectors"] or ["form", "button", "h2"],
                        "input_fields": comp_meta["input_fields"],
                        "actions": comp_meta["actions"] or ["click button"],
                        "headings": comp_meta["headings"],
                        "table_headers": comp_meta.get("table_headers", []),
                        "submit_button": comp_meta.get("submit_button"),
                    })
                else:
                    has_login = "login" in sr["route"] or "auth" in sr["route"]
                    has_list = "list" in sr["name"].lower()
                    ui_items.append({
                        "name": sr["name"],
                        "route": sr["route"],
                        "file": sr["file"],
                        "type": "AUTH" if has_login else "TABLE" if has_list else "PAGE",
                        "has_login": has_login,
                        "has_form": not has_list and not has_login,
                        "has_table": has_list,
                        "is_fragment": False,
                        "grounded_selectors": ["table", "th"] if has_list else ["form", "button", "h2"],
                        "input_fields": [{"name": "username", "label": "Username", "type": "text"}, {"name": "password", "label": "Password", "type": "password"}] if has_login else [],
                        "actions": ["verify table"] if has_list else ["click button"],
                        "headings": [],
                        "table_headers": [],
                        "submit_button": "Submit",
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
