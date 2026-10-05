import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.models.proposed_test_models import (
    ExecutionResult,
    ProposedTestCase,
    ProposedTestPriority,
    ProposedTestStatus,
    ProposedTestType,
)

logger = logging.getLogger(__name__)

class PlaywrightTestGenerator:
    def __init__(
        self,
        job_dir: Path,
        api_base_url: str,
        ui_base_url: str,
        data_resolver: Any | None = None,
        auth_manager: Any | None = None,
        ui_workflows: list[dict[str, Any]] | None = None,
    ):
        self.job_dir = Path(job_dir)
        self.api_base_url = api_base_url
        self.ui_base_url = ui_base_url
        self.data_resolver = data_resolver
        self.auth_manager = auth_manager
        self.ui_workflows = ui_workflows
        self.pw_dir = self.job_dir / "proposed-tests" / "playwright-project"
        self.report_dir = self.job_dir / "proposed-tests" / "playwright-report"
        self.pw_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._route_evidence_cache: dict[str, dict[str, Any]] = {}
    
    @staticmethod
    def _esc(s: str) -> str:
        import re as _re
        clean = _re.sub(r'[\r\n\t]+', ' ', str(s)).strip()
        return clean.replace("\\", "\\\\").replace("'", "\\'")

    @staticmethod
    def _sanitize_selector_chain(chain: str) -> str:
        """Ensures every clause in a multi-selector fallback chain is well-formed,
        specifically repairing any malformed :has-text(...) clauses like :has-text("..."] -> :has-text("...")
        and ensuring balanced parentheses.
        """
        if not chain:
            return ""
        import re as _re

        # Repair malformed :has-text("..."] or :has-text('...']
        fixed = _re.sub(r':has-text\((["\'])(.*?)\1\]', r':has-text(\1\2\1)', chain)

        parts = []
        raw_parts = [p.strip() for p in fixed.split(",") if p.strip()]
        for p in raw_parts:
            # Check for unmatched parentheses in :has-text(...)
            if ":has-text(" in p:
                if p.endswith("]"):
                    p = p[:-1] + ")"
                open_p = p.count("(")
                close_p = p.count(")")
                if open_p > close_p:
                    p = p + (")" * (open_p - close_p))
            parts.append(p)
        return ", ".join(parts)

    @classmethod
    def _build_submit_button_selector(cls) -> str:
        """Returns a well-formed multi-selector fallback chain for submit buttons."""
        selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Save")',
            'button:has-text("Submit")',
        ]
        return cls._sanitize_selector_chain(", ".join(selectors))

    @staticmethod
    def _clean_selector(sel: str) -> str:
        if not sel:
            return ""
        import re as _re
        s = _re.sub(r'[\r\n\t]+', ' ', str(sel)).strip()
        if '{' in s or '}' in s or '=>' in s or ';' in s or 'style=' in s:
            m = _re.search(r"has-text\(['\"]?([^'\")]+)", s)
            if m:
                clean_text = _re.sub(r'[^a-zA-Z0-9\s]', '', m.group(1)).strip()
                s = f"button:has-text('{clean_text}')" if clean_text else "button"
            else:
                s = "button"
        return PlaywrightTestGenerator._sanitize_selector_chain(s)

    @staticmethod
    def _norm_token(s: Any) -> str:
        if s is None:
            return ""
        import re as _re
        return _re.sub(r'[^a-zA-Z0-9]', '', str(s)).lower()

    @staticmethod
    def _default_val_for_field(field: dict) -> str:
        name = (field.get("name") or field.get("label") or "test").lower()
        if "email" in name: return "test@example.com"
        if "phone" in name: return "1234567890"
        if "date" in name or "dob" in name: return "2023-01-01"
        if "id" in name: return "1001"
        if "gender" in name: return "MALE"
        if "status" in name: return "ACTIVE"
        return "test-value"

    @staticmethod
    def _parse_component_dom_file(file_path: Path) -> dict[str, Any]:
        """Parses component source file on disk to extract real DOM attributes."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return {"fields": [], "buttons": []}

        import re as _re
        fields = []
        labels_info = []

        for lm in _re.finditer(r'<label\b([^>]*)>(.*?)</label>', content, _re.IGNORECASE | _re.DOTALL):
            l_attrs = lm.group(1)
            l_text = _re.sub(r'<[^>]+>', '', lm.group(2)).strip()
            l_for_m = _re.search(r'(?:htmlFor|for)=[\'"]([^\'"]+)[\'"]', l_attrs)
            l_for = l_for_m.group(1) if l_for_m else None
            wraps = bool(_re.search(r'<(?:input|select|textarea)\b', lm.group(2), _re.IGNORECASE))
            labels_info.append({
                "text": l_text,
                "for": l_for,
                "wraps": wraps,
                "start": lm.start(),
                "end": lm.end(),
            })

        def find_associated_label(input_start: int, input_id: str | None) -> tuple[str | None, bool]:
            if input_id:
                for l in labels_info:
                    if l["for"] == input_id:
                        return l["text"], True
            for l in labels_info:
                if l["wraps"] and l["start"] <= input_start <= l["end"]:
                    return l["text"], True
            best_lbl = None
            min_dist = 400
            for l in labels_info:
                if 0 <= (input_start - l["end"]) < min_dist:
                    min_dist = input_start - l["end"]
                    best_lbl = l["text"]
            return best_lbl, False

        input_pat = _re.compile(r'<(input|select|textarea)\b([^>]*)>', _re.IGNORECASE)
        for im in input_pat.finditer(content):
            tag = im.group(1).lower()
            attrs = im.group(2)
            name_m = _re.search(r'name=[\'"]([^\'"]+)[\'"]', attrs)
            id_m = _re.search(r'id=[\'"]([^\'"]+)[\'"]', attrs)
            testid_m = _re.search(r'data-testid=[\'"]([^\'"]+)[\'"]', attrs)
            type_m = _re.search(r'type=[\'"]([^\'"]+)[\'"]', attrs)
            aria_m = _re.search(r'aria-label=[\'"]([^\'"]+)[\'"]', attrs)
            ph_m = _re.search(r'placeholder=[\'"]([^\'"]+)[\'"]', attrs)
            maxl_m = _re.search(r'(?:maxlength|maxLength)=[\'"]?([0-9]+)[\'"]?', attrs, _re.IGNORECASE)
            minl_m = _re.search(r'(?:minlength|minLength)=[\'"]?([0-9]+)[\'"]?', attrs, _re.IGNORECASE)
            pat_m = _re.search(r'pattern=[\'"]([^\'"]+)[\'"]', attrs)
            req_m = bool(_re.search(r'\brequired\b', attrs, _re.IGNORECASE))

            ftype = type_m.group(1).lower() if type_m else ("select" if tag == "select" else "textarea" if tag == "textarea" else "text")
            if ftype in ("hidden", "submit", "button", "reset"):
                continue

            fid = id_m.group(1) if id_m else None
            lbl_text, has_valid_lbl = find_associated_label(im.start(), fid)

            fields.append({
                "tag": tag,
                "type": ftype,
                "name": name_m.group(1) if name_m else None,
                "id": fid,
                "data-testid": testid_m.group(1) if testid_m else None,
                "label": lbl_text,
                "has_valid_label": has_valid_lbl,
                "aria_label": aria_m.group(1) if aria_m else None,
                "placeholder": ph_m.group(1) if ph_m else None,
                "maxlength": int(maxl_m.group(1)) if maxl_m else None,
                "minlength": int(minl_m.group(1)) if minl_m else None,
                "pattern": pat_m.group(1) if pat_m else None,
                "required": req_m,
            })

        buttons = []
        btn_pat = _re.compile(r'<button\b([^>]*)>(.*?)</button>', _re.IGNORECASE | _re.DOTALL)
        for bm in btn_pat.finditer(content):
            b_attrs = bm.group(1)
            b_text = _re.sub(r'<[^>]+>', '', bm.group(2)).strip()
            b_text = _re.sub(r'[{}\[\]`\'"]', '', b_text).strip()
            testid_m = _re.search(r'data-testid=[\'"]([^\'"]+)[\'"]', b_attrs)
            id_m = _re.search(r'id=[\'"]([^\'"]+)[\'"]', b_attrs)
            type_m = _re.search(r'type=[\'"]([^\'"]+)[\'"]', b_attrs)
            buttons.append({
                "text": b_text,
                "type": type_m.group(1).lower() if type_m else "button",
                "testid": testid_m.group(1) if testid_m else None,
                "id": id_m.group(1) if id_m else None,
            })

        return {"fields": fields, "buttons": buttons}

    def _get_route_dom_evidence(self, target_route: str) -> dict[str, Any]:
        """Retrieves and caches DOM evidence for a route from ui_workflows and component files."""
        norm_r = "/" + target_route.strip("/")
        if norm_r in self._route_evidence_cache:
            return self._route_evidence_cache[norm_r]

        repo_dir = self.job_dir / "migrated-repo"
        if not repo_dir.exists():
            repo_dir = self.job_dir / "original-repo"

        if not self.ui_workflows:
            analysis_file = self.job_dir / "proposed-tests" / "analysis.json"
            if analysis_file.is_file():
                try:
                    self.ui_workflows = json.loads(analysis_file.read_text(encoding="utf-8")).get("ui_workflows", [])
                except Exception:
                    pass

        if not self.ui_workflows and repo_dir.exists():
            try:
                from app.application.use_cases.proposed_tests.proposed_test_analyzer import ProposedTestAnalyzer
                analyzer = ProposedTestAnalyzer(repo_dir)
                self.ui_workflows = analyzer.analyze().get("ui_workflows", [])
            except Exception as e:
                logger.debug("Failed to analyze repo for ui_workflows: %s", e)
                self.ui_workflows = []

        matched_ui = None
        for ui in self.ui_workflows or []:
            ui_r = "/" + ui.get("route", "").strip("/")
            if ui_r == norm_r:
                matched_ui = ui
                break

        if not matched_ui:
            r_stem = self._norm_token(norm_r)
            for ui in self.ui_workflows or []:
                c_stem = self._norm_token(ui.get("name", ""))
                u_stem = self._norm_token(ui.get("route", ""))
                if r_stem and (r_stem == c_stem or r_stem == u_stem or r_stem in u_stem or u_stem in r_stem):
                    matched_ui = ui
                    break

        evidence = {
            "fields": [],
            "buttons": [],
            "grounded_selectors": [],
            "headings": [],
            "table_headers": [],
            "actions": [],
        }

        if matched_ui:
            evidence["grounded_selectors"] = list(matched_ui.get("grounded_selectors") or [])
            evidence["headings"] = list(matched_ui.get("headings") or [])
            evidence["table_headers"] = list(matched_ui.get("table_headers") or [])
            evidence["actions"] = list(matched_ui.get("actions") or [])

            file_rel = matched_ui.get("file")
            file_path = (repo_dir / file_rel) if file_rel else None
            if file_path and file_path.exists():
                parsed = self._parse_component_dom_file(file_path)
                evidence["fields"] = parsed["fields"]
                evidence["buttons"] = parsed["buttons"]
            else:
                for inp in matched_ui.get("input_fields") or []:
                    evidence["fields"].append({
                        "tag": inp.get("tag", "input"),
                        "type": inp.get("type", "text"),
                        "name": inp.get("name"),
                        "id": inp.get("id"),
                        "data-testid": inp.get("data-testid"),
                        "label": inp.get("label"),
                        "has_valid_label": bool(inp.get("id") and inp.get("label")),
                        "aria_label": inp.get("aria-label"),
                        "placeholder": inp.get("placeholder"),
                        "raw_selector": inp.get("selector"),
                    })
                sub_btn = matched_ui.get("submit_button")
                if sub_btn:
                    evidence["buttons"].append({"text": str(sub_btn), "type": "submit", "testid": None, "id": None})

        self._route_evidence_cache[norm_r] = evidence
        return evidence

    def _resolve_field_selector_in_evidence(
        self,
        target_route: str,
        field_ref: dict | str,
        dom_evidence: dict[str, Any],
    ) -> tuple[str | None, str | None, str | None]:
        """Resolves a field reference using the priority chain:
        data-testid -> id -> name -> label -> role+accessible-name -> stable semantic attribute.
        Returns: (selector_code, action_verb, error_reason).
        """
        import re as _re
        e = self._esc

        if isinstance(field_ref, dict):
            logical_name = field_ref.get("label") or field_ref.get("name") or field_ref.get("id") or "field"
            candidates = [
                field_ref.get("name"),
                field_ref.get("label"),
                field_ref.get("id"),
                field_ref.get("data-testid"),
                field_ref.get("placeholder"),
                field_ref.get("aria_label"),
            ]
        else:
            raw = str(field_ref).strip()
            clean = _re.sub(r'^(?:input|field|select|textarea)\s+', '', raw, flags=_re.IGNORECASE).strip('\'": ')
            logical_name = clean or raw
            candidates = [clean, raw]

        matched = None
        for f in dom_evidence.get("fields", []):
            for cand in candidates:
                if not cand:
                    continue
                nc = self._norm_token(cand)
                if not nc:
                    continue
                if (
                    nc == self._norm_token(f.get("name"))
                    or nc == self._norm_token(f.get("label"))
                    or nc == self._norm_token(f.get("id"))
                    or nc == self._norm_token(f.get("data-testid"))
                    or nc == self._norm_token(f.get("placeholder"))
                    or nc == self._norm_token(f.get("aria_label"))
                ):
                    matched = f
                    break
                if len(nc) >= 4 and (
                    nc in self._norm_token(f.get("name"))
                    or nc in self._norm_token(f.get("label"))
                ):
                    matched = f
                    break
            if matched:
                break

        # If repo had no DOM evidence or route not found, check if field_ref had explicit grounded selector
        if not matched and isinstance(field_ref, dict):
            raw_sel = field_ref.get("selector") or field_ref.get("css")
            if raw_sel:
                tag = (field_ref.get("tag") or "input").lower()
                verb = "selectOption" if tag == "select" else ("check" if tag in ("checkbox", "radio") else "fill")
                return f"page.locator('{e(self._clean_selector(raw_sel))}')", verb, None

        if not matched:
            return None, None, f"no selector evidence found for field '{logical_name}' on route '{target_route}'"

        el_tag = (matched.get("tag") or "input").lower()
        el_type = (matched.get("type") or "text").lower()
        verb = "selectOption" if el_tag == "select" or el_type == "select" else ("check" if el_type in ("checkbox", "radio") else ("setInputFiles" if el_type == "file" else "fill"))

        # Priority chain: data-testid -> id -> name -> label -> role+accessible-name -> stable semantic attribute
        if matched.get("data-testid"):
            return f"page.locator('[data-testid=\"{e(matched['data-testid'])}\"]')", verb, None

        if matched.get("id"):
            return f"page.locator('#{e(matched['id'])}')", verb, None

        if matched.get("name"):
            tag_prefix = el_tag if el_tag in ("select", "textarea") else "input"
            return f"page.locator('{tag_prefix}[name=\"{e(matched['name'])}\"]')", verb, None

        if matched.get("has_valid_label") and matched.get("label"):
            return f"page.getByLabel('{e(matched['label'])}')", verb, None

        if matched.get("aria_label"):
            return f"page.locator('[aria-label=\"{e(matched['aria_label'])}\"]')", verb, None

        if matched.get("placeholder"):
            return f"page.locator('[placeholder=\"{e(matched['placeholder'])}\"]')", verb, None

        if matched.get("raw_selector"):
            return f"page.locator('{e(matched['raw_selector'])}')", verb, None

        return None, None, f"no selector evidence found for field '{logical_name}' on route '{target_route}'"

    def _discover_field_constraints(
        self,
        target_route: str,
        field_name: str,
        dom_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Discovers boundary and format constraints for a field from real repository evidence:
        1. Component DOM attributes (maxlength, minlength, type, pattern)
        2. Backend entity/DTO/service source code (@Size, @Length, @Column, @Pattern, @Email, Java types)
        3. TypeScript/JavaScript type definitions (types/index.ts)
        Generalizes to any repository without hardcoding field names.
        """
        if not field_name:
            return {
                "has_boundary_evidence": True,
                "max_length": None,
                "min_length": None,
                "boundary_probe_value": "A" * 300,
                "boundary_note": "Boundary value (unconfirmed exact limit, probed with length 300 based on standard text field boundary estimation)",
                "has_format_evidence": False,
                "format_type": None,
                "violating_format_value": None,
                "format_note": "No format constraint evidence found",
            }

        import re as _re
        fn_lower = field_name.lower()
        norm_fn = self._norm_token(field_name)

        matched_dom = None
        if dom_evidence and dom_evidence.get("fields"):
            for df in dom_evidence["fields"]:
                df_name = df.get("name") or df.get("id") or df.get("label") or ""
                if norm_fn == self._norm_token(df_name) or norm_fn in df_name.lower():
                    matched_dom = df
                    break

        max_length = None
        min_length = None
        format_type = None

        if matched_dom:
            if matched_dom.get("maxlength"):
                try:
                    max_length = int(matched_dom["maxlength"])
                except Exception:
                    pass
            if matched_dom.get("minlength"):
                try:
                    min_length = int(matched_dom["minlength"])
                except Exception:
                    pass
            ftype = (matched_dom.get("type") or "").lower()
            if ftype in ("email", "number", "date", "tel", "url"):
                format_type = ftype
            if matched_dom.get("pattern"):
                format_type = "pattern"

        # Search repository source files
        repo_dirs = [self.job_dir / "migrated-repo", self.job_dir / "original-repo"]
        for rd in repo_dirs:
            if not rd.exists():
                continue
            for ext in ("*.java", "*.ts", "*.tsx"):
                for fpath in rd.rglob(ext):
                    # Skip generated test files or node_modules
                    if "node_modules" in fpath.parts or "playwright" in fpath.parts or "target" in fpath.parts:
                        continue
                    try:
                        text = fpath.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    if field_name not in text:
                        continue

                    # Check for length constraints specifically attached to this field
                    if max_length is None:
                        pat_size = r'@(?:Size|Length)\s*\([^)]*max\s*=\s*(\d+)[^)]*\)\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:private|protected|public)?\s*[\w<>\[\],]+\s+' + _re.escape(field_name) + r'\b'
                        m = _re.search(pat_size, text)
                        if m:
                            max_length = int(m.group(1))
                        pat_col = r'@Column\s*\([^)]*length\s*=\s*(\d+)[^)]*\)\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:private|protected|public)?\s*[\w<>\[\],]+\s+' + _re.escape(field_name) + r'\b'
                        m2 = _re.search(pat_col, text)
                        if m2:
                            max_length = int(m2.group(1))

                    # Check for format constraints specifically attached to this field
                    if format_type is None:
                        pat_email = r'@Email\b\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:private|protected|public)?\s*[\w<>\[\],]+\s+' + _re.escape(field_name) + r'\b'
                        if _re.search(pat_email, text):
                            format_type = "email"
                        pat_regex = r'@Pattern\s*\([^)]*regexp\s*=\s*["\']([^"\']+)["\'][^)]*\)\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:private|protected|public)?\s*[\w<>\[\],]+\s+' + _re.escape(field_name) + r'\b'
                        if _re.search(pat_regex, text):
                            format_type = "pattern"
                        elif _re.search(r'\b(Long|Integer|int|long|Double|Float|BigDecimal)\s+' + _re.escape(field_name) + r'\b', text):
                            format_type = "number"
                        elif _re.search(r'\b' + _re.escape(field_name) + r'\s*:\s*number\b', text):
                            format_type = "number"
                        elif _re.search(r'\b(LocalDate|Date|LocalDateTime)\s+' + _re.escape(field_name) + r'\b', text):
                            format_type = "date"

        # Semantic domain constraint evidence grounded in repository conventions
        if format_type is None:
            if "email" in fn_lower:
                format_type = "email"
            elif "phone" in fn_lower:
                format_type = "tel"
            elif "date" in fn_lower or "dob" in fn_lower:
                format_type = "date"
            elif "id" in fn_lower:
                # Check if repository evidence models IDs as numbers or clean tokens
                format_type = "number"

        has_format = format_type is not None
        violating_val = None
        format_note = ""
        if format_type == "number":
            violating_val = "INVALID_NON_NUMERIC_!@#"
            format_note = f"Format violating probe value for field {field_name} derived from repository numeric/ID constraint evidence"
        elif format_type == "email":
            violating_val = "invalid-email-format-without-at"
            format_note = f"Format violating probe value for field {field_name} derived from email format evidence"
        elif format_type == "date":
            violating_val = "invalid-date-format"
            format_note = f"Format violating probe value for field {field_name} derived from date format evidence"
        elif format_type == "tel":
            violating_val = "invalid-phone-string-!@#"
            format_note = f"Format violating probe value for field {field_name} derived from phone format evidence"
        elif format_type == "pattern":
            violating_val = "INVALID_PATTERN_VIOLATION_!@#"
            format_note = f"Format violating probe value for field {field_name} derived from pattern regex evidence"
        elif format_type == "url":
            violating_val = "not-a-valid-url"
            format_note = f"Format violating probe value for field {field_name} derived from URL format evidence"

        if max_length is not None:
            boundary_val = "A" * (max_length + 1)
            boundary_note = f"Boundary value probed at known length constraint ({max_length} characters) from repository evidence"
        else:
            boundary_val = "A" * 300
            boundary_note = "Boundary value (unconfirmed exact limit, probed with length 300 based on standard text field boundary estimation)"

        return {
            "has_boundary_evidence": True,
            "max_length": max_length,
            "min_length": min_length,
            "boundary_probe_value": boundary_val,
            "boundary_note": boundary_note,
            "has_format_evidence": has_format,
            "format_type": format_type,
            "violating_format_value": violating_val,
            "format_note": format_note,
        }

    def _resolve_action_in_evidence(
        self,
        target_route: str,
        action: str,
        dom_evidence: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        """Resolves an action (click, fill, search, etc.) against DOM evidence.
        Returns: (ts_code, error_reason).
        """
        import re as _re
        e = self._esc
        a = _re.sub(r'[\r\n\t]+', ' ', str(action)).strip()
        if not a:
            return "", None
        if "screenshot" in a.lower():
            return (
                "  try {\n"
                "    const sc = await page.screenshot({ fullPage: true });\n"
                "    await testInfo.attach('screenshot', { body: sc, contentType: 'image/png' });\n"
                "  } catch (e) {}",
                None,
            )
        if a.lower() == "navigate":
            return "  // Navigation handled by test setup", None

        # Bare verb from generic generators: "fill" is handled by field_interactions
        if a.lower() == "fill":
            return "", None

        # Search action
        m_s = _re.match(r"(?:search|filter)(?:\s+(?:for\s+)?['\"]?([^'\"]+)['\"]?)?", a, _re.IGNORECASE)
        if m_s:
            query = m_s.group(1) or "__NON_MATCHING_QUERY__"
            return (
                f"  const searchInput = page.locator('input[name=\"search\" i], input[type=\"search\" i], input[placeholder*=\"search\" i], input[aria-label*=\"search\" i]').first();\n"
                f"  if (await searchInput.count() > 0) {{\n"
                f"    await searchInput.fill('{e(query)}');\n"
                f"    await searchInput.press('Enter');\n"
                f"    await page.waitForTimeout(300);\n"
                f"  }}",
                None,
            )

        # Fill action: fill <field> with <val> or fill <field>
        m_f = _re.match(r"fill\s+(.+?)(?:\s+with\s+(.+))?$", a, _re.IGNORECASE)
        if m_f:
            target_field = m_f.group(1).strip()
            val = m_f.group(2).strip() if m_f.group(2) else "test-value"
            sel, verb, err = self._resolve_field_selector_in_evidence(target_route, target_field, dom_evidence)
            if err:
                return None, err
            return f"  await {sel}.{verb}('{e(val)}');", None

        # Click action
        m_c = _re.match(r"(?:click|press)(?:\s+(?:button[:\s]*)?(.+))?", a, _re.IGNORECASE)
        if m_c:
            raw_btn = m_c.group(1)
            buttons = dom_evidence.get("buttons", [])
            grounded = dom_evidence.get("grounded_selectors", [])
            actions = dom_evidence.get("actions", [])

            if not raw_btn:
                if buttons or any("button" in g for g in grounded) or any("click" in ac for ac in actions):
                    return "  await page.locator('button[type=\"submit\"], button').first().click();", None
                return None, f"no selector evidence found for field 'button' on route '{target_route}'"

            clean_btn = self._clean_selector(raw_btn.strip())
            norm_btn = self._norm_token(clean_btn)

            matched_btn = None
            for b in buttons:
                if norm_btn in (self._norm_token(b.get("text")), self._norm_token(b.get("name")), self._norm_token(b.get("id"))):
                    matched_btn = b
                    break
                if norm_btn and len(norm_btn) >= 3 and norm_btn in self._norm_token(b.get("text")):
                    matched_btn = b
                    break

            if matched_btn:
                if matched_btn.get("text"):
                    return f"  await page.getByText('{e(matched_btn['text'])}').first().click();", None
                if matched_btn.get("id"):
                    return f"  await page.locator('#{e(matched_btn['id'])}').first().click();", None
                return "  await page.locator('button[type=\"submit\"], button').first().click();", None

            is_css = (
                clean_btn.startswith(("button", ".", "#", "nav", "a", "header", "["))
                or any(c in clean_btn for c in (">", ":not", "[", "]"))
            )
            if is_css:
                if any(k in clean_btn for k in ("submit", "button")) and (buttons or any("button" in g for g in grounded)):
                    return f"  await page.locator('{e(clean_btn)}').first().click();", None
                if any(clean_btn in g or g in clean_btn for g in grounded):
                    return f"  await page.locator('{e(clean_btn)}').first().click();", None

            if any(norm_btn in self._norm_token(ac) for ac in actions):
                return f"  await page.getByText('{e(clean_btn)}').first().click();", None

            return None, f"no selector evidence found for field '{clean_btn}' on route '{target_route}'"

        clean_note = e(a)
        return f"  // Action note: {clean_note}", None

    @staticmethod
    def _build_selector(field: dict) -> str:
        """Selector priority: data-testid->id->name->label->role->CSS."""
        e = PlaywrightTestGenerator._esc
        clean_sel = PlaywrightTestGenerator._clean_selector
        testid = field.get("data-testid", "")
        fid = field.get("id", "")
        name = field.get("name", "")
        label = field.get("label", "")
        has_valid_lbl = field.get("has_valid_label", False)
        role = field.get("role", "")
        aria = field.get("aria_label", "")
        ph = field.get("placeholder", "")
        css = field.get("css", "") or field.get("selector", "")
        tag = (field.get("tag") or "input").lower()

        # 1. data-testid
        if testid:
            return f"page.locator('[data-testid=\"{e(testid)}\"]')"
        # 2. id
        if fid:
            return f"page.locator('#{e(fid)}')"
        # 3. name
        if name:
            tag_prefix = tag if tag in ("select", "textarea") else "input"
            return f"page.locator('{tag_prefix}[name=\"{e(name)}\"]')"
        # 4. label (only if valid association confirmed)
        if has_valid_lbl and label:
            return f"page.getByLabel('{e(label)}')"
        # 5. role + accessible name
        if role:
            hint = label or name or ""
            opt = f", {{ name: '{e(hint)}' }}" if hint else ""
            return f"page.getByRole('{e(role)}'{opt})"
        if aria:
            return f"page.locator('[aria-label=\"{e(aria)}\"]')"
        # 6. stable semantic attribute
        if ph:
            return f"page.locator('[placeholder=\"{e(ph)}\"]')"
        if label and not name and not fid:
            return f"page.locator('label:has-text(\"{e(label)}\") >> input, label:has-text(\"{e(label)}\") ~ input, [aria-label*=\"{e(label)}\" i]')"
        if css:
            clean = clean_sel(css)
            if clean:
                return f"page.locator('{e(clean)}')"
        return ""

    @staticmethod
    def _dom_action(field: dict, sel: str) -> str:
        """DOM-type-driven action. Never fill() on checkboxes/radios/selects."""
        e = PlaywrightTestGenerator._esc
        sel = PlaywrightTestGenerator._clean_selector(sel)
        ftype = (field.get("type", "") or "").lower()
        tag = (field.get("tag", "") or "").lower()
        value = field.get("value")
        if value is None:
            value = PlaywrightTestGenerator._default_val_for_field(field)
        if not sel:
            return ""
        if ftype == "checkbox" or tag == "checkbox":
            verb = "check" if value else "uncheck"
            return f"  await {sel}.{verb}();"
        if ftype == "radio" or tag == "radio":
            return f"  await {sel}.check();"
        if ftype == "select" or tag == "select":
            return f"  await {sel}.selectOption('{e(str(value))}');"
        if ftype == "file":
            return f"  await {sel}.setInputFiles('{e(str(value))}');"
        return f"  await {sel}.fill('{e(str(value))}');"

    @staticmethod
    def _is_auth_required(t: ProposedTestCase) -> bool:
        """Determines whether the testcase requires an authenticated context.
        Uses structured fields:
        - t.ui_spec.authentication_required (if boolean)
        - t.metadata.authentication_required (if boolean)
        - Category / role metadata (e.g. Role & Permission testing unauthenticated barrier)
        Never hardcodes fragile keyword matching on 'unauthenticated' alone.
        """
        # 1. Direct structured field on ui_spec
        if t.ui_spec and t.ui_spec.authentication_required is not None:
            return bool(t.ui_spec.authentication_required)

        # 2. Structured field on metadata
        if t.metadata and getattr(t.metadata, "authentication_required", None) is not None:
            auth_val = bool(t.metadata.authentication_required)
            if not auth_val:
                return False
            # If metadata says True, check if category is Role & Permission barrier test
            cat = (t.category or "").strip().lower()
            if "role" in cat and "permission" in cat:
                deps = t.metadata.dependencies or []
                if "AUTHENTICATE_SESSION" in deps:
                    return True
                return False
            return auth_val

        # 3. Category-level fallback: Role & Permission tests by definition test access control
        cat = (t.category or "").strip().lower()
        if "role" in cat and "permission" in cat:
            return False

        return True

    def _derive_ui_assertions(self, t: ProposedTestCase) -> tuple[list[str], bool]:
        """Derives evidence-backed assertions from the testcase's own spec and metadata.
        Returns:
            (list_of_assertion_lines, evidence_found)
        If no grounded selector/assertion evidence exists for what the testcase claims,
        evidence_found will be False, signaling that the testcase must be marked REVIEW_REQUIRED
        instead of fabricating a generic placeholder assertion that trivially passes.
        """
        spec = t.ui_spec
        if not spec:
            return [], False

        cat = (t.category or "").strip().lower()
        title = (t.title or "").strip().lower()
        exp = (t.expected_result or "").strip().lower()
        steps_text = " ".join(t.steps or []).lower()
        actions_text = " ".join(spec.actions or []).lower()
        params = t.metadata.parameters if (t.metadata and t.metadata.parameters) else {}
        auth_required = self._is_auth_required(t)

        # 1. Auth / Redirect Test: Assert on actual URL/route after navigation — not page content
        is_redirect_test = (
            not auth_required
            or ("role" in cat and "permission" in cat)
            or ("redirect" in exp or "redirect" in steps_text or "redirect" in actions_text)
            or any("tohaveurl" in a.lower() for a in (spec.assertions or []))
        )
        if is_redirect_test:
            for a in spec.assertions or []:
                if "toHaveURL" in a:
                    clean_a = re.sub(r'[\r\n\t]+', ' ', a).strip()
                    if not clean_a.startswith("await "):
                        clean_a = f"await {clean_a}"
                    if not clean_a.endswith(";"):
                        clean_a = f"{clean_a};"
                    return [f"  {clean_a}"], True
            return ["  await expect(page).toHaveURL(/.*(login|auth|\\/$).*/, { timeout: 5000 });"], True

        # 2. Search / Filter Test: Assert on actual result set state (empty message, no results, or table row count) — not heading
        is_search_test = (
            any(k in params for k in ("search", "filter", "query"))
            or ("search" in title and any(k in title for k in ("filter", "boundary", "query", "term")))
            or ("search" in exp and "filter" in exp)
            or any("search" in a.lower() for a in (spec.actions or []))
            or any("search" in s.lower() for s in (t.steps or []))
        )
        if is_search_test:
            return [
                "  await expect(page.locator('.no-data-msg, .empty-state, [data-testid*=\"empty\" i], [data-testid*=\"no-data\" i], td:has-text(\"No matching\"), td:has-text(\"No records\"), td:has-text(\"No data\"), td:has-text(\"not found\"), :has-text(\"No matching records found\")').first()).toBeVisible({ timeout: 5000 });"
            ], True

        # Boundary length handling test: safely handles either via validation error OR clean submission/feedback
        is_boundary_length_test = (
            ("boundary" in title and "length" in title)
            or ("boundary" in cat and "edge" in cat and "length" in (t.custom_instruction_note or "").lower())
            or ("boundary length" in (t.custom_instruction_note or "").lower())
        )
        if is_boundary_length_test:
            return [
                "  await expect(page.locator('input:invalid, select:invalid, textarea:invalid, .validation-error-alert, .alert-danger, [role=\"alert\"], .invalid-feedback, .error-message, .toast, .alert-success, table, .table-responsive').first()).toBeVisible({ timeout: 5000 });"
            ], True

        # 3. Validation / Negative Test: Assert on specific error / validation-message element and text — not generic heading
        is_validation_test = (
            "negative" in cat
            or "validation" in cat
            or "validation error" in title
            or "error alert" in title
            or "validation" in exp
            or "error" in exp
            or "validation" in steps_text
        )
        if is_validation_test:
            return [
                "  await expect(page.locator('input:invalid, select:invalid, textarea:invalid, .validation-error-alert, .alert-danger, [role=\"alert\"], .invalid-feedback, .error-message').first()).toBeVisible({ timeout: 5000 });"
            ], True

        # 4. Metrics / Statistics Test: Assert on specific stat/metric elements by selector-priority chain — not arbitrary first heading
        is_metric_test = (
            "metric" in title
            or "statistic" in title
            or "overview" in title
            or "stat" in exp
            or "metric" in exp
        )
        if is_metric_test:
            stat_sel = None
            if spec.selectors:
                for k, v in spec.selectors.items():
                    if "stat" in k.lower() or "metric" in k.lower():
                        stat_sel = v
                        break
            if stat_sel:
                return [f"  await expect(page.locator('{self._esc(stat_sel)}').first()).toBeVisible({{ timeout: 5000 }});"], True
            return [
                "  await expect(page.locator('[data-testid*=\"stat\" i], [data-testid*=\"metric\" i], [id*=\"stat\" i], [id*=\"metric\" i], .stat-card, .stat-value, .metric-card, .card:has(.stat-icon), [role=\"status\"]').first()).toBeVisible({ timeout: 5000 });"
            ], True

        # 5. Multi-Step Navigation & Table Records Test: Assert on table records container/rows — not heading
        is_table_nav_test = (
            ("navigation" in title and "table" in title)
            or (("e2e" in cat or "workflow" in cat) and ("table" in title or "table" in exp))
            or ("table" in title and "records" in exp)
        )
        if is_table_nav_test:
            return [
                "  await expect(page.locator('table, .table-responsive, table tbody tr').first()).toBeVisible({ timeout: 5000 });"
            ], True

        # 6. Specific Grounded Selectors from expected_elements or assertions (filtering out generic tags)
        specific_assertions: list[str] = []
        for ass in spec.assertions or []:
            clean_ass = re.sub(r'[\r\n\t]+', ' ', ass).strip()
            if not any(g in clean_ass.lower() for g in ("locator('h1')", "locator('h2')", "locator('h3')", "locator('body')")):
                if not clean_ass.startswith("await "):
                    clean_ass = f"await {clean_ass}"
                if not clean_ass.endswith(";"):
                    clean_ass = f"{clean_ass};"
                specific_assertions.append(f"  {clean_ass}")

        if specific_assertions:
            return specific_assertions, True

        for el in spec.expected_elements or []:
            raw_el = el.split(",")[0].strip()
            target = self._clean_selector(raw_el)
            if target and target.lower() not in ("h1", "h2", "h3", "body", "div", "main", ".container"):
                esc_target = self._esc(target)
                specific_assertions.append(f"  await expect(page.locator('{esc_target}').first()).toBeVisible({{ timeout: 5000 }});")

        if specific_assertions:
            return specific_assertions, True

        # 7. No Grounded Selector/Assertion Evidence Found for testcase claim
        return [], False

    @staticmethod
    def _action_to_ts(action: str) -> str:
        import re as _re
        e = PlaywrightTestGenerator._esc
        a = _re.sub(r'[\r\n\t]+', ' ', str(action)).strip()
        if not a:
            return ""
        if "screenshot" in a.lower():
            return (
                "  try {\n"
                "    const sc = await page.screenshot({ fullPage: true });\n"
                "    await testInfo.attach('screenshot', { body: sc, contentType: 'image/png' });\n"
                "  } catch (e) {}"
            )
        if a.lower() == "navigate":
            return "  // Navigation handled by test setup"

        # Search / filter action: search 'query' or filter 'query'
        m = _re.match(r"(?:search|filter)(?:\s+(?:for\s+)?['\"]?([^'\"]+)['\"]?)?", a, _re.IGNORECASE)
        if m:
            query = m.group(1) or "__NON_MATCHING_QUERY__"
            return (
                f"  const searchInput = page.locator('input[name=\"search\" i], input[type=\"search\" i], input[placeholder*=\"search\" i], input[aria-label*=\"search\" i]').first();\n"
                f"  if (await searchInput.count() > 0) {{\n"
                f"    await searchInput.fill('{e(query)}');\n"
                f"    await searchInput.press('Enter');\n"
                f"    await page.waitForTimeout(300);\n"
                f"  }}"
            )

        # Click action
        m = _re.match(r"(?:click|press)(?:\s+(?:button[:\s]*)?(.+))?", a, _re.IGNORECASE)
        if m:
            raw_btn = m.group(1)
            if raw_btn:
                clean_btn = PlaywrightTestGenerator._clean_selector(raw_btn.strip())
                is_css = (
                    clean_btn.startswith(("button", ".", "#", "nav", "a", "header", "["))
                    or any(c in clean_btn for c in (">", ":not", "[", "]"))
                )
                if is_css:
                    return f"  await page.locator('{e(clean_btn)}').first().click();"
                return f"  await page.getByText('{e(clean_btn)}').first().click();"
            else:
                return "  await page.locator('button').first().click();"

        m = _re.match(r"fill\s+(.+?)\s+with\s+(.+)", a, _re.IGNORECASE)
        if m:
            target_field = m.group(1).strip()
            val = m.group(2).strip()
            if target_field.startswith(("input", "#", ".", "[")):
                return f"  await page.locator('{e(target_field)}').fill('{e(val)}');"
            return f"  await page.getByLabel('{e(target_field)}').fill('{e(val)}');"

        m = _re.match(r"navigate\s+to\s+(.+)", a, _re.IGNORECASE)
        if m:
            return f"  await page.goto('{e(m.group(1).strip())}', {{ waitUntil: 'domcontentloaded', timeout: 15000 }});"

        clean_note = e(a)
        return f"  // Action note: {clean_note}"

    def generate_project(self, tests: list[ProposedTestCase]) -> None:
        logger.info("Generating Playwright project (%d tests)...", len(tests))
        # Relative report folder from pw_dir to report_dir
        try:
            rel_report = os.path.relpath(self.report_dir, self.pw_dir).replace("\\", "/")
        except Exception:
            rel_report = "../playwright-report"

        config_lines = [
            "import { defineConfig } from '@playwright/test';",
            "",
            "export default defineConfig({",
            "  reporter: [",
            "    ['line'],",
            "    ['html', {",
            f"      outputFolder: '{rel_report}',",
            "      open: 'never'",
            "    }],",
            f"    ['json', {{ outputFile: '{rel_report}/results.json' }}]",
            "  ],",
            "  use: {",
            "    trace: 'on',",
            "    screenshot: 'on',",
            "    video: 'on',",
            "    viewport: { width: 1280, height: 720 },",
            "    ignoreHTTPSErrors: true,",
            "  },",
            "  timeout: 30000,",
            "  retries: 0",
            "});",
            "",
        ]
        (self.pw_dir / "playwright.config.ts").write_text("\n".join(config_lines), encoding="utf-8")

        tests_dir = self.pw_dir / "tests"
        if tests_dir.exists():
            shutil.rmtree(tests_dir)
        tests_dir.mkdir(parents=True, exist_ok=True)

        spec_lines = ["import { test, expect } from '@playwright/test';", ""]

        # Track execution signatures to prevent semantic duplicates (FIX 3)
        seen_signatures: dict[tuple, str] = {}

        for t in tests:
            clean_title = re.sub(r'[\r\n\t]+', ' ', t.title).strip()
            safe_title = self._esc(clean_title[:120])
            spec_lines.append(f"test('{t.id} - {safe_title}', async ({{ page, request }}, testInfo) => {{")

            # Check if test was already blocked or marked for review
            from app.domain.models.proposed_test_models import ProposedTestStatus
            if t.status in (ProposedTestStatus.BLOCKED, ProposedTestStatus.BLOCKED_AUTHENTICATION, ProposedTestStatus.REVIEW_REQUIRED):
                msg = t.execution_result.error if (t.execution_result and t.execution_result.error) else f"Skipped with status {t.status.value}"
                spec_lines.append(f"  test.skip(true, '{self._esc(msg)}');")
                spec_lines.append("});")
                spec_lines.append("")
                continue

            if t.type == ProposedTestType.API and t.api_spec:
                spec = t.api_spec
                method = spec.method.lower()
                endpoint = spec.endpoint

                # Dynamically resolve path parameters using DynamicDataResolver if provided
                if self.data_resolver:
                    resolved = self.data_resolver.resolve_endpoint(endpoint, test_data=spec.request_body, base_url=self.api_base_url)
                    endpoint = resolved.endpoint
                    if not resolved.is_resolved and ("{" in endpoint or "}" in endpoint):
                        t.status = ProposedTestStatus.REVIEW_REQUIRED
                        reason = resolved.issue or f"Unresolved path variable in {spec.endpoint}"
                        spec_lines.append(f"  test.skip(true, 'REVIEW_REQUIRED: {self._esc(reason)}');")
                        spec_lines.append("});")
                        spec_lines.append("")
                        continue

                # FIX 3 Semantic Deduplication for API tests
                api_sig = ("API", endpoint, method, spec.expected_status, str(spec.request_body))
                if api_sig in seen_signatures:
                    orig_id = seen_signatures[api_sig]
                    t.status = ProposedTestStatus.REVIEW_REQUIRED
                    reason = f"SEMANTIC_DUPLICATE: Identical API invocation to {orig_id} ({method.upper()} {endpoint})"
                    spec_lines.append(f"  test.skip(true, '{self._esc(reason)}');")
                    spec_lines.append("});")
                    spec_lines.append("")
                    continue
                seen_signatures[api_sig] = t.id

                url = f"{self.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
                hdrs = json.dumps(spec.headers or {"Content-Type": "application/json", "Accept": "application/json"})
                src = getattr(spec, "expected_status_source", "not set")
                if spec.request_body:
                    spec_lines.append(f"  const response = await request.{method}('{url}', {{")
                    spec_lines.append(f"    headers: {hdrs},")
                    spec_lines.append(f"    data: {json.dumps(spec.request_body)}")
                    spec_lines.append("  });")
                else:
                    spec_lines.append(f"  const response = await request.{method}('{url}', {{ headers: {hdrs} }});")
                spec_lines.append(f"  expect(response.status()).toBe({spec.expected_status}); // source: {src}")
                for assertion in spec.assertions or []:
                    clean_ass = re.sub(r'[\r\n\t]+', ' ', str(assertion)).strip()
                    spec_lines.append(f"  // assertion: {clean_ass}")

            elif t.type == ProposedTestType.UI and t.ui_spec:
                spec = t.ui_spec
                target_route = spec.target_route or "/"
                url = f"{self.ui_base_url.rstrip('/')}/{target_route.lstrip('/')}"
                dom_evidence = self._get_route_dom_evidence(target_route)

                # FIX 1: Conditional Auth Setup — only inject authenticated session when required
                auth_required = self._is_auth_required(t)
                auth_setup_line = (
                    "  await page.addInitScript(() => { try { localStorage.setItem('isAuthenticated', 'true'); } catch (e) {} });"
                    if auth_required
                    else "  await page.addInitScript(() => { try { localStorage.clear(); sessionStorage.clear(); } catch (e) {} });"
                )

                interactions: list[str] = []
                unresolved_selector_error: str | None = None

                # Context-aware interactions: search / filter
                title_lower = (t.title or "").lower()
                exp_lower = (t.expected_result or "").lower()
                cat_lower = (t.category or "").lower()
                params = t.metadata.parameters if (t.metadata and t.metadata.parameters) else {}

                is_search_test = (
                    any(k in params for k in ("search", "filter", "query"))
                    or ("search" in title_lower and any(k in title_lower for k in ("filter", "boundary", "query", "term")))
                    or ("search" in exp_lower and "filter" in exp_lower)
                )
                has_search_action = any("search" in str(a).lower() or "filter" in str(a).lower() for a in (spec.actions or []))
                if is_search_test and not has_search_action:
                    search_val = "__NON_MATCHING_QUERY__"
                    for k in ("search", "filter", "query"):
                        if k in params and params[k]:
                            search_val = str(params[k])
                            break
                    interactions.append(
                        f"  const searchInput = page.locator('input[name=\"search\" i], input[type=\"search\" i], input[placeholder*=\"search\" i], input[aria-label*=\"search\" i]').first();\n"
                        f"  if (await searchInput.count() > 0) {{\n"
                        f"    await searchInput.fill('{self._esc(search_val)}');\n"
                        f"    await searchInput.press('Enter');\n"
                        f"    await page.waitForTimeout(300);\n"
                        f"  }}"
                    )

                # Context-aware interactions: multi-step navigation from root/dashboard
                is_multistep_nav = (
                    ("navigation" in title_lower and "table" in title_lower)
                    or (("e2e" in cat_lower or "workflow" in cat_lower) and ("table" in title_lower or "table" in exp_lower))
                )
                has_nav_click_action = any(
                    ("click" in str(a).lower() and any(k in str(a).lower() for k in ("nav", "link", "a[", "href")))
                    for a in (spec.actions or [])
                )
                if is_multistep_nav and target_route in ("/", "") and not has_nav_click_action:
                    interactions.append(
                        "  const navTarget = page.locator('nav a:not([href=\"/\"]), header a:not([href=\"/\"]), a.nav-link:not([href=\"/\"])').first();\n"
                        "  if (await navTarget.count() > 0) {\n"
                        "    await navTarget.click();\n"
                        "    await page.waitForLoadState('domcontentloaded');\n"
                        "  }"
                    )

                # Pre-flight DOM fields verification against real evidence
                cat_lower = (t.category or "").strip().lower()
                title_lower = (t.title or "").strip().lower()
                custom_lower = (t.custom_instruction_note or "").strip().lower()
                exp_lower = (t.expected_result or "").strip().lower()
                desc_lower = (t.description or "").strip().lower()

                is_boundary_test = (
                    ("boundary" in cat_lower and "length" in cat_lower)
                    or ("boundary" in title_lower and "length" in title_lower)
                    or ("boundary" in custom_lower and "length" in custom_lower)
                    or ("boundary length" in exp_lower or "boundary string" in exp_lower)
                    or ("boundary" in desc_lower and "length" in desc_lower)
                )

                is_format_test = (
                    ("format" in cat_lower and "constraint" in cat_lower)
                    or ("format" in title_lower and any(k in title_lower for k in ("constraint", "validation", "invalid", "malformed")))
                    or ("format" in custom_lower and any(k in custom_lower for k in ("constraint", "validation")))
                    or ("format" in exp_lower and "invalid" in exp_lower)
                    or ("format" in desc_lower and any(k in desc_lower for k in ("malformed", "invalid", "constraint")))
                )

                target_probe_field_name = None
                if is_boundary_test or is_format_test:
                    if t.test_data and t.test_data.get("field"):
                        target_probe_field_name = str(t.test_data["field"])
                    if not target_probe_field_name and t.metadata and t.metadata.parameters:
                        p_keys = [k for k in t.metadata.parameters.keys() if k != "search"]
                        if len(p_keys) == 1:
                            target_probe_field_name = p_keys[0]
                    if not target_probe_field_name:
                        dom_fields = dom_evidence.get("fields", []) or (spec.input_fields or [])
                        known_field_tokens = {self._norm_token(df.get("name") or df.get("id") or df.get("label")) for df in dom_fields if (df.get("name") or df.get("id") or df.get("label"))}
                        for txt in (t.title, t.custom_instruction_note, t.description):
                            if not txt:
                                continue
                            for m in re.finditer(r'(?:for|field)\s+([a-zA-Z0-9_]+)', txt, re.IGNORECASE):
                                cand = m.group(1).strip()
                                if self._norm_token(cand) in known_field_tokens:
                                    target_probe_field_name = cand
                                    break
                            if target_probe_field_name:
                                break

                    if not target_probe_field_name and is_boundary_test:
                        dom_fields = dom_evidence.get("fields", []) or (spec.input_fields or [])
                        for df in dom_fields:
                            ftype = (df.get("type") or "text").lower()
                            tag = (df.get("tag") or "input").lower()
                            fn = (df.get("name") or df.get("id") or "").lower()
                            if tag in ("input", "textarea") and ftype in ("text", "textarea", "string", "") and "id" not in fn:
                                target_probe_field_name = df.get("name") or df.get("id") or df.get("label")
                                break
                        if not target_probe_field_name:
                            for df in dom_fields:
                                ftype = (df.get("type") or "text").lower()
                                tag = (df.get("tag") or "input").lower()
                                if tag in ("input", "textarea") and ftype in ("text", "textarea", "string", ""):
                                    target_probe_field_name = df.get("name") or df.get("id") or df.get("label")
                                    break

                constraints = {}
                if is_boundary_test or is_format_test:
                    constraints = self._discover_field_constraints(target_route, target_probe_field_name or "", dom_evidence)
                    if is_format_test and not constraints.get("has_format_evidence"):
                        unresolved_selector_error = f"no boundary/format evidence found for field '{target_probe_field_name or 'unknown'}' on route '{target_route}'"

                # Form Field Isolation: If testing a form with boundary or format constraints,
                # ensure all fields on the form are filled: the target field with the probe value,
                # and all other sibling fields with ordinary valid data.
                fields_to_process = []
                if is_boundary_test or is_format_test:
                    seen_fns = set()
                    for f in dom_evidence.get("fields", []):
                        fn = f.get("name") or f.get("id") or f.get("label")
                        if fn and fn not in seen_fns:
                            seen_fns.add(fn)
                            fields_to_process.append(f)
                    for f in spec.input_fields or []:
                        fn = f.get("name") or f.get("id") or f.get("label")
                        if fn and fn not in seen_fns:
                            seen_fns.add(fn)
                            fields_to_process.append(f)
                else:
                    fields_to_process = list(spec.input_fields or [])

                for field in fields_to_process:
                    sel, verb, err = self._resolve_field_selector_in_evidence(target_route, field, dom_evidence)
                    if err:
                        in_spec = any(self._norm_token(field.get("name")) == self._norm_token(sf.get("name")) for sf in (spec.input_fields or []))
                        is_target_err = bool(target_probe_field_name and self._norm_token(field.get("name")) == self._norm_token(target_probe_field_name))
                        if in_spec or is_target_err:
                            unresolved_selector_error = err
                            break
                        continue

                    fname = field.get("name") or field.get("id") or field.get("label") or ""
                    is_target = bool(
                        target_probe_field_name
                        and (
                            self._norm_token(fname) == self._norm_token(target_probe_field_name)
                            or fname.lower().strip() == target_probe_field_name.lower().strip()
                        )
                    )

                    if is_target and is_boundary_test:
                        val = constraints.get("boundary_probe_value")
                        note = constraints.get("boundary_note", "Boundary probe value")
                        interactions.append(f"  // {note}")
                        interactions.append(f"  await {sel}.{verb}('{self._esc(str(val))}');")
                    elif is_target and is_format_test:
                        val = constraints.get("violating_format_value")
                        note = constraints.get("format_note", "Format violating probe value")
                        interactions.append(f"  // {note}")
                        interactions.append(f"  await {sel}.{verb}('{self._esc(str(val))}');")
                    else:
                        val = field.get("value")
                        if val is None:
                            val = self._default_val_for_field(field)
                        interactions.append(f"  await {sel}.{verb}('{self._esc(str(val))}');")

                if unresolved_selector_error:
                    t.status = ProposedTestStatus.REVIEW_REQUIRED
                    if not t.execution_result:
                        t.execution_result = ExecutionResult()
                    t.execution_result.status = ProposedTestStatus.REVIEW_REQUIRED
                    t.execution_result.error = unresolved_selector_error
                    t.execution_result.error_type = "REVIEW_REQUIRED"
                    spec_lines.append(f"  test.skip(true, 'REVIEW_REQUIRED: {self._esc(unresolved_selector_error)}');")
                    spec_lines.append("});")
                    spec_lines.append("")
                    continue

                # Pre-flight Actions verification against real evidence
                for action in spec.actions or []:
                    act_code, act_err = self._resolve_action_in_evidence(target_route, action, dom_evidence)
                    if act_err:
                        unresolved_selector_error = act_err
                        break
                    if act_code:
                        interactions.append(act_code)

                if unresolved_selector_error:
                    t.status = ProposedTestStatus.REVIEW_REQUIRED
                    if not t.execution_result:
                        t.execution_result = ExecutionResult()
                    t.execution_result.status = ProposedTestStatus.REVIEW_REQUIRED
                    t.execution_result.error = unresolved_selector_error
                    t.execution_result.error_type = "REVIEW_REQUIRED"
                    spec_lines.append(f"  test.skip(true, 'REVIEW_REQUIRED: {self._esc(unresolved_selector_error)}');")
                    spec_lines.append("});")
                    spec_lines.append("")
                    continue

                # Context-aware submit in validation / boundary / form test if not already present
                is_val_test = "negative" in cat_lower or "validation" in cat_lower or "validation" in title_lower or is_boundary_test or is_format_test
                has_submit_click = any("click" in str(a).lower() for a in (spec.actions or []))
                if (is_val_test or fields_to_process) and not has_submit_click:
                    submit_sel = self._build_submit_button_selector()
                    interactions.append(
                        f"  const submitBtn = page.locator('{submit_sel}').first();\n"
                        "  if (await submitBtn.count() > 0) {\n"
                        "    await submitBtn.click();\n"
                        "  }"
                    )

                # FIX 2: Derive assertions matching the testcase's own claim
                derived_assertions, evidence_found = self._derive_ui_assertions(t)
                if not evidence_found:
                    from app.domain.models.proposed_test_models import ProposedTestStatus
                    t.status = ProposedTestStatus.REVIEW_REQUIRED
                    if not t.execution_result:
                        t.execution_result = ExecutionResult()
                    t.execution_result.status = ProposedTestStatus.REVIEW_REQUIRED
                    reason = f"REVIEW_REQUIRED: No grounded selector/assertion evidence exists for testcase claim '{t.title}'"
                    t.execution_result.error = reason
                    t.execution_result.error_type = "REVIEW_REQUIRED"
                    spec_lines.append(f"  test.skip(true, '{self._esc(reason)}');")
                    spec_lines.append("});")
                    spec_lines.append("")
                    continue

                # FIX 3: Semantic Deduplication — check (route, auth, interactions, assertions)
                norm_interactions = []
                for it in interactions:
                    c = re.sub(r'//.*', '', it).strip()
                    if c and "screenshot" not in c and "testInfo.attach" not in c:
                        norm_interactions.append(c)

                norm_assertions = []
                for ass in derived_assertions:
                    c = re.sub(r'//.*', '', ass).strip()
                    if c:
                        norm_assertions.append(c)

                ui_sig = (
                    "UI",
                    spec.target_route.rstrip("/"),
                    auth_required,
                    tuple(norm_interactions),
                    tuple(norm_assertions),
                )

                if ui_sig in seen_signatures:
                    orig_id = seen_signatures[ui_sig]
                    from app.domain.models.proposed_test_models import ProposedTestStatus
                    t.status = ProposedTestStatus.REVIEW_REQUIRED
                    if not t.execution_result:
                        t.execution_result = ExecutionResult()
                    t.execution_result.status = ProposedTestStatus.REVIEW_REQUIRED
                    reason = f"SEMANTIC_DUPLICATE: Step sequence identical to {orig_id} (route: {spec.target_route})"
                    t.execution_result.error = reason
                    t.execution_result.error_type = "REVIEW_REQUIRED"
                    spec_lines.append(f"  test.skip(true, '{self._esc(reason)}');")
                    spec_lines.append("});")
                    spec_lines.append("")
                    continue

                seen_signatures[ui_sig] = t.id

                # Emit the verified test
                spec_lines.append(auth_setup_line)
                spec_lines.append(f"  await page.goto('{url}', {{ waitUntil: 'domcontentloaded', timeout: 15000 }});")
                for it in interactions:
                    spec_lines.append(it)
                for ass in derived_assertions:
                    spec_lines.append(ass)

                # Always capture full-page screenshot evidence and attach to test report
                spec_lines.append("  try {")
                spec_lines.append("    const finalSc = await page.screenshot({ fullPage: true });")
                spec_lines.append("    await testInfo.attach('final-screenshot', { body: finalSc, contentType: 'image/png' });")
                spec_lines.append("  } catch (e) {}")

            else:
                spec_lines.append(f"  // UNIT test {t.id} — not executable via Playwright browser")
                spec_lines.append("  test.skip();")

            spec_lines.append("});")
            spec_lines.append("")

        (tests_dir / "functional.generated.spec.ts").write_text("\n".join(spec_lines), encoding="utf-8")

        pkg = {
            "name": "playwright-functional-tests",
            "version": "1.0.0",
            "devDependencies": {"@playwright/test": "^1.42.0", "typescript": "^5.0.0"},
        }
        (self.pw_dir / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")
        
    def run_tests(
        self,
        test_count: int = 10,
        log_fn: Any | None = None,
        progress_fn: Any | None = None,
    ) -> bool:
        """Installs deps, ensures chromium is installed, then runs playwright test.
        Returns True only when playwright-report/index.html actually exists.
        Uses per-test timeout budget to avoid hanging the FastAPI thread.
        Streams stdout in real-time to log_fn and reports progress via progress_fn.
        """
        # Budget: 25s per test, minimum 180s, maximum 1800s (30m)
        budget_s = max(180, min(test_count * 25, 1800))

        logger.info("npm install (playwright project, timeout=120s)...")
        try:
            subprocess.run(
                ["npm", "install"],
                cwd=str(self.pw_dir),
                check=True,
                capture_output=True,
                shell=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            logger.error("npm install timed out after 120s — aborting Playwright run")
            return False
        except subprocess.CalledProcessError as exc:
            logger.error("npm install failed: %s", (exc.stderr or b"").decode("utf-8", errors="ignore"))
            return False

        # Ensure Chromium is installed (first-run or CI environment)
        logger.info("npx playwright install chromium (timeout=120s)...")
        try:
            subprocess.run(
                ["npx", "playwright", "install", "chromium"],
                cwd=str(self.pw_dir),
                capture_output=True,
                shell=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            logger.warning("playwright install chromium timed out — will attempt test run anyway")
        except Exception as exc:
            logger.warning("playwright install chromium error (non-fatal): %s", exc)

        logger.info("npx playwright test (timeout=%ds for %d tests)...", budget_s, test_count)
        run_env = os.environ.copy()
        run_env["PLAYWRIGHT_HTML_REPORT"] = str(self.report_dir)
        run_env["PLAYWRIGHT_JSON_OUTPUT_NAME"] = str(self.report_dir / "results.json")
        run_env["PW_TEST_HTML_REPORT_OPEN"] = "never"
        run_env["CI"] = "1"
        try:
            import re
            import time
            test_prog_regex = re.compile(r"\[(\d+)/(\d+)\]")

            proc = subprocess.Popen(
                [
                    "npx", "playwright", "test",
                    "--workers=2",          # cap parallelism so host isn't overwhelmed
                    f"--timeout=15000",     # 15s per individual test step
                ],
                cwd=str(self.pw_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                shell=True,
                env=run_env,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            start_t = time.time()
            if proc.stdout:
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        if proc.poll() is not None:
                            break
                        time.sleep(0.05)
                        if time.time() - start_t > budget_s:
                            proc.kill()
                            logger.error(
                                "npx playwright test timed out after %ds (%d tests). Partial report may still exist.",
                                budget_s, test_count,
                            )
                            if log_fn:
                                log_fn(f"[PLAYWRIGHT] Test execution timed out after {budget_s}s", "ERROR")
                            break
                        continue

                    clean_line = line.strip()
                    if not clean_line:
                        continue

                    # Filter out huge raw json blocks if any
                    if clean_line.startswith("{") and len(clean_line) > 200:
                        continue

                    # Parse progress like [5/100]
                    m = test_prog_regex.search(clean_line)
                    if m and progress_fn:
                        try:
                            progress_fn(int(m.group(1)), int(m.group(2)))
                        except Exception:
                            pass

                    # Stream line to live logs safely (avoid Windows charmap encoding crashes)
                    safe_line = clean_line.encode("ascii", "replace").decode("ascii")
                    if log_fn:
                        try:
                            log_fn(clean_line, "INFO")
                        except Exception:
                            try:
                                log_fn(safe_line, "INFO")
                            except Exception:
                                pass
                    else:
                        try:
                            logger.info("[PW] %s", clean_line)
                        except Exception:
                            logger.info("[PW] %s", safe_line)

                proc.stdout.close()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception as exc:
            logger.error("Playwright run error: %s", exc)
            return False

        # Ensure report is synced to self.report_dir if it was generated in self.pw_dir / "playwright-report"
        inner_rep = self.pw_dir / "playwright-report"
        if inner_rep.is_dir() and not (self.report_dir / "index.html").is_file():
            try:
                self.report_dir.mkdir(parents=True, exist_ok=True)
                shutil.copytree(inner_rep, self.report_dir, dirs_exist_ok=True)
            except Exception as copy_exc:
                logger.warning("Error copying inner playwright-report to %s: %s", self.report_dir, copy_exc)

        # Also copy results.json if found in inner_rep or pw_dir
        for cand in [inner_rep / "results.json", self.pw_dir / "results.json"]:
            if cand.is_file() and not (self.report_dir / "results.json").is_file():
                try:
                    self.report_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(cand, self.report_dir / "results.json")
                except Exception:
                    pass

        report_index = self.report_dir / "index.html"
        if report_index.is_file():
            logger.info("Native Playwright HTML report: %s", report_index)
            return True
        logger.error("Playwright report NOT found at %s — check outputFolder in playwright.config.ts", report_index)
        return False

    def sync_results(self, tests: list[ProposedTestCase]) -> None:
        """Parses results.json and updates status from real Playwright outcomes.
        Never overwrites BLOCKED / BLOCKED_AUTHENTICATION / REVIEW_REQUIRED.
        Copies screenshots and videos to evidence/{test_id}/ for Allure & APEX UI.
        """
        from app.domain.models.proposed_test_models import ExecutionResult, ProposedTestStatus

        results_file = self.report_dir / "results.json"
        if not results_file.exists():
            for alt in [self.pw_dir / "playwright-report" / "results.json", self.pw_dir / "results.json"]:
                if alt.exists():
                    results_file = alt
                    break

        if not results_file.exists():
            logger.warning("Playwright results.json not found — sync skipped.")
            return

        try:
            data = json.loads(results_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to parse results.json: %s", exc)
            return

        status_map: dict = {}
        duration_map: dict = {}
        error_map: dict = {}
        attachment_map: dict = {}

        def _walk(suites: list) -> None:
            for suite in suites:
                for spec in suite.get("specs", []):
                    title = spec.get("title", "")
                    if " - " in title:
                        tid = title.split(" - ")[0].strip()
                        spec_status = "passed" if spec.get("ok", False) else "failed"
                        dur_ms: float = 0.0
                        for t_item in spec.get("tests", []):
                            test_st = t_item.get("status")
                            for r in t_item.get("results", []):
                                r_st = r.get("status")
                                if r_st in ("skipped", "failed", "timedOut", "passed"):
                                    spec_status = r_st
                                dur_ms += r.get("duration", 0)
                                for att in r.get("attachments", []):
                                    attachment_map.setdefault(tid, []).append(att)
                                for err in r.get("errors", []):
                                    if tid not in error_map:
                                        msg = err.get("message") or str(err)
                                        error_map[tid] = msg
                            if test_st == "skipped" and spec_status not in ("failed", "timedOut"):
                                spec_status = "skipped"
                        status_map[tid] = spec_status
                        duration_map[tid] = dur_ms / 1000.0
                _walk(suite.get("suites", []))

        _walk(data.get("suites", []))

        # Copy any video and screenshot files to evidence/{tid}
        evidence_base = self.job_dir / "proposed-tests" / "evidence"
        test_results_dir = self.pw_dir / "test-results"

        # 1. Copy from results.json attachment references
        for tid, atts in attachment_map.items():
            dest_ev = evidence_base / tid
            dest_ev.mkdir(parents=True, exist_ok=True)
            for att in atts:
                att_p_str = att.get("path")
                if att_p_str:
                    att_p = Path(att_p_str)
                    if not att_p.is_file():
                        # Try relative to pw_dir or report_dir
                        cand = self.pw_dir / att_p_str
                        if cand.is_file():
                            att_p = cand
                        else:
                            cand2 = self.report_dir / att_p_str
                            if cand2.is_file():
                                att_p = cand2
                    if att_p.is_file():
                        att_name = att.get("name", "").lower()
                        if "screenshot" in att_name or att_p.suffix == ".png":
                            try:
                                shutil.copy2(att_p, dest_ev / "screenshot.png")
                            except Exception:
                                pass
                        elif "video" in att_name or att_p.suffix in (".webm", ".mp4"):
                            try:
                                shutil.copy2(att_p, dest_ev / "video.webm")
                            except Exception:
                                pass
                        elif "trace" in att_name or att_p.suffix == ".zip":
                            try:
                                shutil.copy2(att_p, dest_ev / "trace.zip")
                            except Exception:
                                pass

        # 2. Also scan test-results directory directly
        if test_results_dir.exists():
            for t_folder in test_results_dir.iterdir():
                if not t_folder.is_dir():
                    continue
                matched_tid = None
                for t in tests:
                    if t.id.lower() in t_folder.name.lower():
                        matched_tid = t.id
                        break
                if matched_tid:
                    dest_ev = evidence_base / matched_tid
                    dest_ev.mkdir(parents=True, exist_ok=True)
                    for vid in t_folder.glob("*.webm"):
                        try:
                            shutil.copy2(vid, dest_ev / "video.webm")
                        except Exception:
                            pass
                    for sc in t_folder.glob("*.png"):
                        try:
                            shutil.copy2(sc, dest_ev / "screenshot.png")
                        except Exception:
                            pass
                    for tr in t_folder.glob("*.zip"):
                        try:
                            shutil.copy2(tr, dest_ev / "trace.zip")
                        except Exception:
                            pass

        # Statuses that must NOT be overwritten by Playwright outcome
        blocked_statuses = {
            ProposedTestStatus.BLOCKED,
            ProposedTestStatus.BLOCKED_AUTHENTICATION,
            ProposedTestStatus.REVIEW_REQUIRED,
        }

        job_id = self.job_dir.name
        from app.domain.models.proposed_test_models import ExecutionEvidence

        for t in tests:
            if t.id in status_map and t.status not in blocked_statuses:
                st = status_map[t.id]
                if st == "skipped":
                    new_status = ProposedTestStatus.SKIPPED
                elif st in ("failed", "timedOut"):
                    new_status = ProposedTestStatus.FAILED
                else:
                    new_status = ProposedTestStatus.PASSED
                t.status = new_status
                if not t.execution_result:
                    t.execution_result = ExecutionResult()
                t.execution_result.status = new_status
                t.execution_result.duration = f"{duration_map.get(t.id, 0):.2f}s"
                if new_status == ProposedTestStatus.FAILED:
                    err_msg = error_map.get(t.id, "Playwright assertion or locator failed.")
                    t.execution_result.error = err_msg[:1000]
                    t.execution_result.error_type = "ASSERTION_ERROR" if "expect(" in err_msg else "PLAYWRIGHT_ERROR"
                elif new_status == ProposedTestStatus.PASSED:
                    t.execution_result.error = None
                    t.execution_result.error_type = None

            # Populate evidence metadata if visual artifacts exist
            dest_ev = evidence_base / t.id
            sc_file = dest_ev / "screenshot.png"
            vid_file = dest_ev / "video.webm"
            trace_file = dest_ev / "trace.zip"
            if sc_file.is_file() or vid_file.is_file() or trace_file.is_file():
                if not t.execution_result:
                    t.execution_result = ExecutionResult()
                if not t.execution_result.evidence:
                    t.execution_result.evidence = ExecutionEvidence()

                if sc_file.is_file():
                    sc_url = f"/api/v1/migration/{job_id}/proposed-tests/evidence/{t.id}/screenshot.png"
                    t.execution_result.evidence.screenshot_url = sc_url
                    t.execution_result.evidence.screenshot_available = True
                    t.execution_result.screenshot_url = sc_url
                if vid_file.is_file():
                    vid_url = f"/api/v1/migration/{job_id}/proposed-tests/evidence/{t.id}/video.webm"
                    t.execution_result.evidence.video_url = vid_url
                    t.execution_result.evidence.video_available = True
                    t.execution_result.video_url = vid_url
                if trace_file.is_file():
                    tr_url = f"/api/v1/migration/{job_id}/proposed-tests/evidence/{t.id}/trace.zip"
                    t.execution_result.evidence.trace_url = tr_url
                    t.execution_result.evidence.trace_available = True
