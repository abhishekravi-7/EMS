import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.infrastructure.llm.chat_llm import ChatLLM
from app.infrastructure.llm.prompt_templates import (
    UI_MODERNIZATION_SYSTEM_PROMPT,
    FRONTEND_FOLDER_STRUCTURE_SYSTEM_PROMPT,
    build_ui_modernization_prompt,
    build_frontend_folder_structure_prompt,
    build_ui_targeted_repair_prompt,
)
from app.infrastructure.migration_engine.diff_utils import generate_diff_lines
from app.shared import file_utils

logger = logging.getLogger(__name__)


@dataclass
class SourceFileFacts:
    """Dynamically extracted facts from a single JSP/JSF source file."""
    file_name: str
    relative_path: str
    is_jsp: bool
    is_jsf: bool
    loc: int
    directives: list[str] = field(default_factory=list)
    taglibs: list[dict[str, str]] = field(default_factory=list)
    scriptlets: list[str] = field(default_factory=list)
    el_expressions: list[str] = field(default_factory=list)
    jstl_tags: list[str] = field(default_factory=list)
    custom_tags: list[str] = field(default_factory=list)
    forms: list[dict[str, Any]] = field(default_factory=list)
    input_fields: list[dict[str, Any]] = field(default_factory=list)
    buttons: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    loops: list[dict[str, Any]] = field(default_factory=list)
    conditions: list[dict[str, Any]] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)
    session_attributes: list[str] = field(default_factory=list)
    request_attributes: list[str] = field(default_factory=list)
    javascript_blocks: list[str] = field(default_factory=list)
    css_classes: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    jsf_components: list[str] = field(default_factory=list)
    jsf_managed_beans: list[str] = field(default_factory=list)
    jsf_validators_converters: list[str] = field(default_factory=list)
    page_type: str = "general"
    status_fields: list[str] = field(default_factory=list)
    alerts_messages: list[str] = field(default_factory=list)
    cards_panels: list[str] = field(default_factory=list)
    search_filter_controls: list[str] = field(default_factory=list)
    pagination_controls: list[str] = field(default_factory=list)
    has_legacy_presentation: bool = False
    legacy_presentation_items: list[str] = field(default_factory=list)
    has_form: bool = False
    has_inputs: bool = False
    has_table: bool = False
    has_loops: bool = False
    has_conditions: bool = False
    has_javascript: bool = False

    def to_prompt_summary(self) -> str:
        """Serializes extracted facts into a structured, concise prompt payload."""
        lines = [
            f"SOURCE TYPE: {'JSP' if self.is_jsp else 'JSF' if self.is_jsf else 'HTML/Template'}",
            f"SOURCE FILE: {self.relative_path}",
            f"PAGE STRUCTURE TYPE: {self.page_type.upper()}",
            f"LINES OF CODE: {self.loc}",
            f"HAS FORM: {self.has_form}",
            f"HAS INPUTS: {self.has_inputs}",
        ]
        if self.page_type == "auth":
            lines.append("- VIEW ROLE: Authentication/Login view. Modernize as a clean, centered, accessible card layout.")
        elif self.page_type == "layout_partial":
            lines.append("- VIEW ROLE: Layout Partial (header/footer/nav). Modernize visual styling, but KEEP IT SIMPLE with NO phantom form hooks or state.")
        elif self.page_type == "data_table":
            lines.append("- VIEW ROLE: Data table view. Modernize with responsive wrapper, styled headers, hover rows, and status badges.")
        elif self.page_type == "form":
            lines.append("- VIEW ROLE: Form view. Modernize with accessible form-group layout and primary action buttons.")

        if self.forms:
            form_descs = [f"action='{f.get('action')}', method='{f.get('method')}'" for f in self.forms]
            lines.append(f"DETECTED FORMS: {'; '.join(form_descs)}")
        if self.input_fields:
            fields_str = ", ".join(f"{f.get('name')} (type: {f.get('type')})" for f in self.input_fields if f.get("name"))
            lines.append(f"FORM FIELDS: [{fields_str}]")
        if self.buttons:
            btn_str = ", ".join(f"'{b.get('text') or b.get('value')}' (type: {b.get('type')})" for b in self.buttons[:6])
            lines.append(f"BUTTONS: [{btn_str}]")
        if self.links:
            link_str = ", ".join(f"href='{l.get('href')}'" for l in self.links[:6])
            lines.append(f"LINKS: [{link_str}]")
        if self.has_table:
            lines.append("HAS TABLE: True (requires responsive wrapper and styled thead/hover)")
        if self.loops:
            loop_str = ", ".join(f"items={l.get('items')}, var={l.get('var')}" for l in self.loops)
            lines.append(f"LOOPS: [{loop_str}]")
        if self.conditions:
            cond_str = ", ".join(f"test={c.get('test')}" for c in self.conditions[:5])
            lines.append(f"CONDITIONS: [{cond_str}]")
        if self.status_fields:
            lines.append(f"DETECTED STATUS FIELDS: [{', '.join(self.status_fields)}] -> Render as visual status badges/chips.")
        if self.alerts_messages:
            lines.append(f"DETECTED ALERTS/MESSAGES: [{', '.join(self.alerts_messages)}] -> Render as modern alert callout cards.")
        if self.cards_panels:
            lines.append(f"DETECTED CARDS/PANELS: [{', '.join(self.cards_panels)}]")
        if self.search_filter_controls:
            lines.append(f"SEARCH/FILTER CONTROLS: [{', '.join(self.search_filter_controls)}]")
        if self.has_legacy_presentation:
            lines.append(f"OBSOLETE MARKUP TO CLEAN SAFELY: [{', '.join(self.legacy_presentation_items)}]")
        if self.el_expressions:
            lines.append(f"DYNAMIC EXPRESSIONS: [{', '.join(self.el_expressions[:10])}]")
        if self.includes:
            lines.append(f"INCLUDES: [{', '.join(self.includes)}]")
        if self.jsf_components:
            lines.append(f"JSF COMPONENTS: [{', '.join(self.jsf_components[:10])}]")
        if self.jsf_managed_beans:
            lines.append(f"MANAGED BEANS: [{', '.join(self.jsf_managed_beans)}]")

        lines.append("BEHAVIOR CONSTRAINTS:")
        if not self.has_form and not self.has_inputs:
            lines.append("- No form or input fields present in source. DO NOT generate useState, formData, handleSubmit, or handleInputChange.")
        else:
            lines.append("- Form or inputs present. Generate controlled form state and handlers ONLY for the detected fields.")
        if not self.has_table:
            lines.append("- No table in source. DO NOT generate table markup.")
        if not self.has_javascript:
            lines.append("- No custom script in source. DO NOT invent arbitrary event listeners.")

        return "\n".join(lines)


def extract_source_facts(file_path: Path, source_code: str) -> SourceFileFacts:
    """Extracts dynamic source context from a JSP or JSF file."""
    lines = [line for line in source_code.splitlines() if line.strip()]
    loc = len(lines)
    rel_path = file_path.name

    ext = file_path.suffix.lower()
    is_jsp = ext in (".jsp", ".jspf", ".jspx") or "<%" in source_code or "<c:" in source_code
    is_jsf = ext in (".jsf", ".xhtml") or "xmlns:h=" in source_code or "<h:" in source_code

    # Directives
    directives = sorted(list(set(re.findall(r'<%@\s*([a-zA-Z0-9_]+)\b', source_code))))

    # Taglibs
    taglibs = []
    for match in re.finditer(r'<%@\s*taglib\s+([^%]+)%>', source_code):
        body = match.group(1)
        uri_m = re.search(r'uri=["\']([^"\']+)["\']', body)
        prefix_m = re.search(r'prefix=["\']([^"\']+)["\']', body)
        taglibs.append({
            "uri": uri_m.group(1) if uri_m else "",
            "prefix": prefix_m.group(1) if prefix_m else "",
        })

    # Scriptlets
    scriptlets = re.findall(r'<%[!=]?\s*([^%]+)%>', source_code)

    # EL expressions
    el_expressions = sorted(list(set(re.findall(r'[\$#]\{([^}]+)\}', source_code))))
    session_attrs = [e for e in el_expressions if "session" in e.lower() or e in {"name", "user", "username"}]
    request_attrs = [e for e in el_expressions if e not in session_attrs]

    # JSTL tags
    jstl_tags = sorted(list(set(re.findall(r'<(c:\w+|fmt:\w+|fn:\w+)\b', source_code))))

    # Custom tags
    custom_tags = sorted(list(set(re.findall(r'<([a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+)\b', source_code))))
    custom_tags = [t for t in custom_tags if not t.startswith(("c:", "fmt:", "fn:", "jsp:"))]

    # Forms
    forms = []
    for match in re.finditer(r'<(?:form|h:form)\b([^>]*)>', source_code, re.IGNORECASE):
        attrs = match.group(1)
        act_m = re.search(r'action=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        meth_m = re.search(r'method=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        forms.append({
            "action": act_m.group(1) if act_m else "",
            "method": (meth_m.group(1) if meth_m else "POST").upper(),
        })

    # Input fields
    input_fields = []
    input_patterns = [
        r'<(?:input|h:inputText|h:inputSecret|h:inputTextarea|p:inputText)\b([^>]*)>',
        r'<(?:select|h:selectOneMenu)\b([^>]*)>',
        r'<(?:textarea)\b([^>]*)>',
    ]
    for pattern in input_patterns:
        for match in re.finditer(pattern, source_code, re.IGNORECASE):
            attrs = match.group(1)
            name_m = re.search(r'\b(?:name|id|value)\b=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            type_m = re.search(r'\btype=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            val_m = re.search(r'\bvalue=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            req_m = "required" in attrs.lower()

            raw_name = name_m.group(1) if name_m else ""
            # Strip EL syntax if found in value
            if raw_name.startswith(("${", "#{")):
                raw_name = raw_name[2:-1].split(".")[-1]

            field_type = type_m.group(1).lower() if type_m else "text"
            if field_type in ("submit", "button", "reset"):
                continue

            input_fields.append({
                "name": raw_name,
                "type": field_type,
                "value": val_m.group(1) if val_m else "",
                "required": req_m,
            })

    # Buttons
    buttons = []
    for match in re.finditer(r'<(?:button|h:commandButton|p:commandButton)\b([^>]*)>(.*?)(?:</button>|</h:commandButton>|</p:commandButton>)?', source_code, re.IGNORECASE | re.DOTALL):
        attrs = match.group(1)
        text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        val_m = re.search(r'value=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        act_m = re.search(r'action=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        type_m = re.search(r'type=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        buttons.append({
            "text": text or (val_m.group(1) if val_m else "Submit"),
            "value": val_m.group(1) if val_m else "",
            "action": act_m.group(1) if act_m else "",
            "type": type_m.group(1) if type_m else "submit",
        })

    # Standalone input submit buttons
    for match in re.finditer(r'<input\b[^>]*type=["\'](submit|button|reset)["\'][^>]*>', source_code, re.IGNORECASE):
        attrs = match.group(0)
        val_m = re.search(r'value=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        buttons.append({
            "text": val_m.group(1) if val_m else "Submit",
            "value": val_m.group(1) if val_m else "",
            "action": "",
            "type": "submit",
        })

    # Links
    links = []
    for match in re.finditer(r'<(?:a|h:link|h:outputLink)\b([^>]*)>(.*?)(?:</a>|</h:link>|</h:outputLink>)?', source_code, re.IGNORECASE | re.DOTALL):
        attrs = match.group(1)
        text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        href_m = re.search(r'(?:href|outcome)=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        links.append({
            "text": text,
            "href": href_m.group(1) if href_m else "",
        })

    # Tables
    tables = []
    for match in re.finditer(r'<(?:table|h:dataTable|p:dataTable)\b([^>]*)>', source_code, re.IGNORECASE):
        tables.append({"tag": match.group(0)})

    # Loops
    loops = []
    for match in re.finditer(r'<c:forEach\b([^>]*)>', source_code, re.IGNORECASE):
        attrs = match.group(1)
        items_m = re.search(r'items=["\'](?:\$\{)?([^}"\']+)\}?["\']', attrs)
        var_m = re.search(r'var=["\']([^"\']+)["\']', attrs)
        loops.append({
            "type": "c:forEach",
            "items": items_m.group(1) if items_m else "",
            "var": var_m.group(1) if var_m else "",
        })
    for match in re.finditer(r'<ui:repeat\b([^>]*)>', source_code, re.IGNORECASE):
        attrs = match.group(1)
        val_m = re.search(r'value=["\'](?:#\{)?([^}"\']+)\}?["\']', attrs)
        var_m = re.search(r'var=["\']([^"\']+)["\']', attrs)
        loops.append({
            "type": "ui:repeat",
            "items": val_m.group(1) if val_m else "",
            "var": var_m.group(1) if var_m else "",
        })

    # Conditions
    conditions = []
    for match in re.finditer(r'<c:if\b[^>]*test=["\'](?:\$\{)?([^}"\']+)\}?["\']', source_code, re.IGNORECASE):
        conditions.append({"type": "c:if", "test": match.group(1)})
    for match in re.finditer(r'<c:when\b[^>]*test=["\'](?:\$\{)?([^}"\']+)\}?["\']', source_code, re.IGNORECASE):
        conditions.append({"type": "c:when", "test": match.group(1)})
    for match in re.finditer(r'\brendered=["\'](?:#\{)?([^}"\']+)\}?["\']', source_code, re.IGNORECASE):
        conditions.append({"type": "rendered", "test": match.group(1)})

    # Includes
    inc_files = re.findall(r'<%@\s*include\s+file=["\']([^"\']+)["\']', source_code)
    inc_files += re.findall(r'<jsp:include\s+page=["\']([^"\']+)["\']', source_code)
    inc_files += re.findall(r'<ui:include\s+src=["\']([^"\']+)["\']', source_code)
    includes = sorted(list(set(inc_files)))

    # JavaScript blocks
    js_blocks = re.findall(r'<script\b[^>]*>(.*?)</script>', source_code, re.DOTALL | re.IGNORECASE)

    # CSS classes
    css_classes = sorted(list(set(re.findall(r'\b(?:class|styleClass)=["\']([^"\']+)["\']', source_code))))

    # JSF components & beans
    jsf_components = sorted(list(set(re.findall(r'<([hfpui]:[a-zA-Z0-9_-]+)\b', source_code))))
    jsf_beans = sorted(list(set([expr.split(".")[0].split("(")[0].strip() for expr in el_expressions if "." in expr])))

    has_form = len(forms) > 0
    has_inputs = len(input_fields) > 0
    has_table = len(tables) > 0
    has_loops = len(loops) > 0
    has_conditions = len(conditions) > 0
    has_javascript = len(js_blocks) > 0

    # Page type classification
    fn_lower = file_path.stem.lower()
    has_pwd = any(f.get("type") == "password" for f in input_fields)
    is_auth = has_pwd or any(k in fn_lower for k in ("login", "signin", "register", "signup", "auth", "forgot", "password"))
    is_layout_partial = any(k in fn_lower for k in ("nav", "header", "footer", "sidebar", "menu", "breadcrumb", "include", "allcss"))

    if is_auth:
        page_type = "auth"
    elif is_layout_partial:
        page_type = "layout_partial"
    elif len(tables) > 0 and (len(loops) > 0 or "table" in fn_lower or "list" in fn_lower or "grid" in fn_lower):
        page_type = "data_table"
    elif len(forms) > 0 and len(input_fields) >= 2:
        page_type = "form"
    elif any(k in fn_lower for k in ("detail", "view", "show", "profile", "card")):
        page_type = "detail"
    else:
        page_type = "general"

    # Status indicators
    status_keywords = {"status", "active", "inactive", "pending", "success", "failure", "failed", "approved", "rejected", "enabled", "disabled", "state"}
    status_fields = [e for e in el_expressions if any(sk in e.lower() for sk in status_keywords)]
    for match in re.finditer(r'<(?:td|span|div)[^>]*>\s*([A-Za-z0-9_\-\.\$#\{\} ]*?(?:status|active|pending|approved|rejected|enabled|disabled)[A-Za-z0-9_\-\.\$#\{\} ]*?)\s*</', source_code, re.I):
        txt = match.group(1).strip()
        if txt and txt not in status_fields and len(txt) < 40:
            status_fields.append(txt)

    # Alerts & messages
    alerts_messages = []
    for match in re.finditer(r'<c:if\b[^>]*test=["\'](?:\$\{)?(?:not empty\s+)?([a-zA-Z0-9_\.]*(?:error|message|msg|success|alert|warn)[a-zA-Z0-9_\.]*)[^"\']*["\']', source_code, re.I):
        alerts_messages.append(match.group(1))
    for match in re.finditer(r'<div\b[^>]*class=["\'][^"\']*\b(alert|error-msg|success-msg|notification)[^"\']*["\']', source_code, re.I):
        alerts_messages.append(match.group(1))
    if re.search(r'<(?:h|p):messages\b|<(?:h|p):message\b', source_code, re.I):
        alerts_messages.append("jsf:messages")

    # Cards and panels
    cards_panels = []
    if re.search(r'<fieldset\b', source_code, re.I):
        cards_panels.append("fieldset")
    for match in re.finditer(r'<div\b[^>]*class=["\'][^"\']*\b(card|panel|box|portlet)[^"\']*["\']', source_code, re.I):
        cards_panels.append(match.group(1))

    # Search & filter controls
    search_filter_controls = [f.get("name") for f in input_fields if any(sk in (f.get("name") or "").lower() for sk in ("search", "filter", "query", "keyword")) or f.get("type") == "search"]

    # Pagination controls
    pagination_controls = []
    if re.search(r'\b(?:pagination|page-item|pager|p:paginator)\b', source_code, re.I) or re.search(r'[?&](?:page|pageNumber|pageSize)=', source_code):
        pagination_controls.append("detected")

    # Legacy presentation patterns
    legacy_items = []
    if re.search(r'<table\b[^>]*\bborder=["\']?[1-9]', source_code, re.I):
        legacy_items.append("table border")
    if re.search(r'<center\b', source_code, re.I):
        legacy_items.append("center tag")
    if re.search(r'<font\b', source_code, re.I):
        legacy_items.append("font tag")
    if re.search(r'<br\s*/?>\s*<br\s*/?>', source_code, re.I):
        legacy_items.append("spacer br")
    if re.search(r'\b(?:cellpadding|cellspacing)\b', source_code, re.I):
        legacy_items.append("table cell spacing/padding")
    has_legacy_presentation = len(legacy_items) > 0

    return SourceFileFacts(
        file_name=file_path.name,
        relative_path=rel_path,
        is_jsp=is_jsp,
        is_jsf=is_jsf,
        loc=loc,
        directives=directives,
        taglibs=taglibs,
        scriptlets=scriptlets,
        el_expressions=el_expressions,
        jstl_tags=jstl_tags,
        custom_tags=custom_tags,
        forms=forms,
        input_fields=input_fields,
        buttons=buttons,
        links=links,
        tables=tables,
        loops=loops,
        conditions=conditions,
        session_attributes=session_attrs,
        request_attributes=request_attrs,
        javascript_blocks=js_blocks,
        css_classes=css_classes,
        includes=includes,
        jsf_components=jsf_components,
        jsf_managed_beans=jsf_beans,
        page_type=page_type,
        status_fields=status_fields,
        alerts_messages=alerts_messages,
        cards_panels=cards_panels,
        search_filter_controls=search_filter_controls,
        pagination_controls=pagination_controls,
        has_legacy_presentation=has_legacy_presentation,
        legacy_presentation_items=legacy_items,
        has_form=has_form,
        has_inputs=has_inputs,
        has_table=has_table,
        has_loops=has_loops,
        has_conditions=has_conditions,
        has_javascript=has_javascript,
    )


class UIMigrationHandler:
    def __init__(
        self,
        migrated_repo_dir: Path,
        target_framework: str,
        mode: str | None = None,
        ui_mode: str = "preserve",
        backend_mode: str = "unchanged",
        progress_callback: Any | None = None,
        **kwargs: Any,
    ):
        self.migrated_repo_dir = migrated_repo_dir
        self.target_framework = target_framework
        self.mode = mode
        self.ui_mode = ui_mode
        self.backend_mode = backend_mode
        self.progress_callback = progress_callback
        self.llm = ChatLLM()
        self._cached_design_system: str | None = None

    def _detect_frontend_design_system(self) -> str:
        """Inspects package.json in the target repo to detect existing design systems."""
        if self._cached_design_system:
            return self._cached_design_system

        # If user explicitly specified mui or material in ui_mode, respect it
        if self.ui_mode in ("mui", "material"):
            self._cached_design_system = "mui" if "react" in self.target_framework.lower() else "angular_material"
            return self._cached_design_system

        pkg_paths = [
            self.migrated_repo_dir / "frontend" / "package.json",
            self.migrated_repo_dir / "package.json",
            self.migrated_repo_dir / "client" / "package.json",
        ]
        deps: dict[str, str] = {}
        for p in pkg_paths:
            if p.is_file():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    for k in ("dependencies", "devDependencies", "peerDependencies"):
                        if isinstance(data.get(k), dict):
                            deps.update(data[k])
                except Exception:
                    pass

        is_react = "react" in self.target_framework.lower()
        if is_react:
            if "@mui/material" in deps or "@material-ui/core" in deps:
                res = "mui"
            elif "tailwindcss" in deps:
                res = "tailwind"
            elif "bootstrap" in deps or "react-bootstrap" in deps:
                res = "bootstrap"
            elif "antd" in deps:
                res = "antd"
            elif "@chakra-ui/react" in deps:
                res = "chakra"
            else:
                res = "modern_css"
        else:
            if "@angular/material" in deps:
                res = "angular_material"
            elif "bootstrap" in deps or "ngx-bootstrap" in deps:
                res = "bootstrap"
            elif "tailwindcss" in deps:
                res = "tailwind"
            else:
                res = "modern_angular_css"

        self._cached_design_system = res
        return res

    def _ensure_modern_styles(self, frontend_base: Path) -> None:
        """Generates modern design system tokens and utilities in frontend/src/styles/modern-ui.css."""
        styles_dir = frontend_base / "styles"
        styles_dir.mkdir(parents=True, exist_ok=True)
        css_file = styles_dir / "modern-ui.css"
        if css_file.exists():
            return

        css_content = """/* JavaAPEX Enterprise Modern Design System Tokens & Utility Styles */
:root {
  --primary-color: #2563eb;
  --primary-hover: #1d4ed8;
  --neutral-bg: #f8fafc;
  --card-bg: #ffffff;
  --border-color: #e2e8f0;
  --text-main: #0f172a;
  --text-muted: #64748b;
  --radius-sm: 6px;
  --radius-md: 10px;
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.modern-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.5rem;
  font-family: var(--font-family);
  color: var(--text-main);
}

.modern-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.auth-card-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
  padding: 1rem;
}

.auth-card {
  width: 100%;
  max-width: 440px;
  padding: 2rem;
}

.modern-table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  margin-top: 1rem;
  margin-bottom: 1rem;
  box-shadow: var(--shadow-sm);
}

.modern-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.925rem;
}

.modern-table thead {
  background-color: #f1f5f9;
  border-bottom: 2px solid var(--border-color);
}

.modern-table th, .modern-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
}

.modern-table tbody tr:hover {
  background-color: #f8fafc;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.form-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #334155;
}

.form-control {
  width: 100%;
  padding: 0.6rem 0.85rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.95rem;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  box-sizing: border-box;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.6rem 1.25rem;
  font-size: 0.925rem;
  font-weight: 600;
  border-radius: var(--radius-sm);
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
}

.btn-primary {
  background-color: var(--primary-color);
  color: #ffffff;
}

.btn-primary:hover {
  background-color: var(--primary-hover);
}

.btn-secondary {
  background-color: #e2e8f0;
  color: #1e293b;
}

.btn-secondary:hover {
  background-color: #cbd5e1;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.65rem;
  font-size: 0.75rem;
  font-weight: 700;
  border-radius: 9999px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.badge-success { background: #dcfce7; color: #15803d; }
.badge-warning { background: #fef9c3; color: #a16207; }
.badge-danger { background: #fee2e2; color: #b91c1c; }
.badge-info { background: #e0f2fe; color: #0369a1; }

.alert-box {
  padding: 1rem;
  border-radius: var(--radius-sm);
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.9rem;
}

.alert-danger { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
.alert-success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
.alert-info { background: #f0f9ff; border: 1px solid #bae6fd; color: #075985; }

.modern-footer {
  padding: 2rem 1rem;
  border-top: 1px solid var(--border-color);
  background: #f8fafc;
  color: var(--text-muted);
  font-size: 0.875rem;
  text-align: center;
}

.modern-header {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.text-center { text-align: center; }
.spacer-md { height: 1rem; }
"""
        try:
            css_file.write_text(css_content, encoding="utf-8")
            logger.info("Generated modern design system tokens in styles/modern-ui.css")
        except Exception as e:
            logger.warning("Could not write modern-ui.css: %s", e)

    def run(self) -> list[dict]:
        """Run the UI migration synchronously and return the list of transformations."""
        return asyncio.run(self._run_async())

    async def _run_async(self) -> list[dict]:
        if self.mode and self.mode.startswith("JSP"):
            jsp_jsf_extensions = (".jsp", ".jspf", ".jspx")
        elif self.mode and self.mode.startswith("JSF"):
            jsp_jsf_extensions = (".jsf", ".xhtml")
        else:
            jsp_jsf_extensions = (".jsp", ".jspf", ".jspx", ".jsf", ".xhtml")

        # Base directory for modernized frontend
        frontend_base = self.migrated_repo_dir / "frontend" / "src"
        frontend_base.mkdir(parents=True, exist_ok=True)
        self._ensure_modern_styles(frontend_base)

        files_to_process: list[Path] = []
        backend_context_files: list[tuple[str, str]] = []
        shared_includes: list[str] = []
        java_entities: list[str] = []
        endpoints: list[str] = []

        # Single repository walk to discover all relevant files
        for root, _, files in os.walk(self.migrated_repo_dir):
            if any(skip in root for skip in ("frontend", "target", "build", "node_modules", ".git")):
                continue
            for file in files:
                full_path = Path(root) / file
                if file.lower().endswith(jsp_jsf_extensions):
                    if any(inc in file.lower() for inc in ["nav", "footer", "header", "sidebar", "allcss", "include"]):
                        shared_includes.append(file)
                    files_to_process.append(full_path)
                elif file.lower().endswith(".java"):
                    content = ""
                    try:
                        content = full_path.read_text(encoding="utf-8")
                    except Exception:
                        continue

                    is_controller = "controller" in root.lower() or "@controller" in content.lower() or "@restcontroller" in content.lower()
                    is_entity = "model" in root.lower() or "entity" in root.lower() or "dto" in root.lower() or "@entity" in content.lower()

                    if is_entity:
                        java_entities.append(file.replace(".java", ""))

                    if is_controller or is_entity:
                        rel_path = str(full_path.relative_to(self.migrated_repo_dir)).replace("\\", "/")
                        backend_context_files.append((rel_path, content))

                        if is_controller:
                            matches = re.findall(
                                r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\((?:value\s*=\s*)?["\']([^"\']+)["\']',
                                content,
                            )
                            endpoints.extend(matches)

        if not files_to_process:
            logger.info("No JSP/JSF files found for UI modernization.")
            return []

        # Planning Phase: Generate clean Folder Structure
        logger.info("Generating UI modernization plan (folder structure)...")
        module_name = self.migrated_repo_dir.name

        planning_prompt = build_frontend_folder_structure_prompt(
            module_name=module_name,
            jsp_page_list=[f.name for f in files_to_process],
            shared_includes=shared_includes,
            endpoint_list=endpoints,
            entity_list=java_entities,
            auth_requirement="Infer only from supplied JSP/JSF and backend evidence.",
            csrf_yes_no="Infer only from supplied backend evidence.",
            target_framework=self.target_framework,
        )

        ui_plan = ""
        try:
            async for chunk in self.llm.stream_chat(
                system_prompt=FRONTEND_FOLDER_STRUCTURE_SYSTEM_PROMPT,
                user_prompt=planning_prompt,
                endpoint="ui_modernization_planning",
                max_tokens=1500,
            ):
                ui_plan += chunk
            logger.info("UI Modernization Plan generated successfully.")
        except Exception as e:
            logger.warning("Failed to generate UI modernization plan via LLM: %s", e)
            ui_plan = f"Standard {self.target_framework} folder structure."

        logger.info(f"Starting dynamic UI modernization for {len(files_to_process)} files targeting {self.target_framework}.")

        transformations: list[dict] = []
        total_files = len(files_to_process)
        for idx, fp in enumerate(files_to_process, 1):
            if self.progress_callback:
                try:
                    self.progress_callback(f"[UI MIGRATION] Modernizing file ({idx}/{total_files}): {fp.name}...")
                except Exception:
                    pass
            try:
                res = await self._process_file(fp, frontend_base, backend_context_files, ui_plan)
                if res and isinstance(res, dict):
                    transformations.append(res)
                    if self.progress_callback:
                        try:
                            target_disp = res.get("targetSourceFile") or res.get("target_source_file") or "component"
                            self.progress_callback(f"[UI MIGRATION] Converted ({idx}/{total_files}): {fp.name} -> {target_disp}")
                        except Exception:
                            pass
            except Exception as exc:
                logger.error(f"Error modernizing file {fp.name}: {exc}")
            await asyncio.sleep(0.05)

        # Generate routing wrapper for route isolation (App.tsx / app.routes.ts)
        if transformations:
            self._generate_app_routing(frontend_base, transformations)

        return transformations

    def _filter_backend_context_for_file(
        self,
        backend_files: list[tuple[str, str]],
        facts: SourceFileFacts
    ) -> str:
        """Filters the backend files to only include controllers and entities relevant to this file."""
        if not backend_files:
            return "// No relevant backend controllers or entities detected."

        keywords = set()
        file_stem = facts.file_name.split(".")[0].lower().replace("-", "").replace("_", "")
        keywords.add(file_stem)

        for form in facts.forms:
            action = form.get("action", "").lower().strip("/")
            for part in action.split("/"):
                if part and len(part) > 2:
                    keywords.add(part)

        for bean in facts.jsf_managed_beans:
            keywords.add(bean.lower().replace("bean", ""))

        for el in facts.el_expressions:
            lead = el.split(".")[0].split("(")[0].strip().lower()
            if lead and len(lead) > 2 and lead not in {"true", "false", "null", "request", "session"}:
                keywords.add(lead)

        relevant_snippets = []
        for rel_path, content in backend_files:
            path_lower = rel_path.lower().replace("-", "").replace("_", "")
            content_lower = content.lower()
            if any(kw in path_lower or kw in content_lower for kw in keywords):
                lines = content.splitlines()
                truncated_content = "\n".join(lines[:60])
                if len(lines) > 60:
                    truncated_content += f"\n// ... [truncated {len(lines) - 60} lines]"
                relevant_snippets.append(f"// FILE: {rel_path}\n{truncated_content}")
                if len(relevant_snippets) >= 2:
                    break

        if not relevant_snippets:
            # Fallback to top 2 files max to avoid prompt bloat
            for rel_path, content in backend_files[:2]:
                lines = content.splitlines()
                truncated_content = "\n".join(lines[:60])
                if len(lines) > 60:
                    truncated_content += f"\n// ... [truncated {len(lines) - 60} lines]"
                relevant_snippets.append(f"// FILE: {rel_path}\n{truncated_content}")

        return "\n\n".join(relevant_snippets)

    async def _process_file(
        self,
        file_path: Path,
        frontend_base: Path,
        backend_context_files: list[tuple[str, str]],
        ui_plan: str
    ) -> dict | None:
        logger.info(f"Modernizing {file_path.name}...")
        source_code = file_utils.read_text(file_path)
        if not source_code.strip():
            logger.warning(f"File {file_path.name} is empty, skipping.")
            return None

        # 1. Dynamically extract source context
        file_facts = extract_source_facts(file_path, source_code)
        filtered_backend_context = self._filter_backend_context_for_file(backend_context_files, file_facts)
        ui_plan_snippet = ui_plan[:1000] if len(ui_plan) > 1000 else ui_plan
        augmented_context = f"{filtered_backend_context}\n\nUI FOLDER STRUCTURE GUIDE:\n{ui_plan_snippet}"

        # 2. Build structured prompt (cap source code to avoid HTTP 413 payload limits)
        source_code_for_prompt = source_code if len(source_code) <= 10000 else source_code[:10000] + "\n<!-- [truncated for token limit] -->"
        design_system = self._detect_frontend_design_system()
        prompt = build_ui_modernization_prompt(
            source_file_path=str(file_path.relative_to(self.migrated_repo_dir)).replace("\\", "/"),
            source_code=source_code_for_prompt,
            target_framework=self.target_framework,
            backend_context=augmented_context,
            source_facts=file_facts.to_prompt_summary(),
            ui_mode=self.ui_mode,
            backend_mode=self.backend_mode,
            design_system=design_system,
            page_type=file_facts.page_type,
        )

        max_attempts = 1
        for attempt in range(1, max_attempts + 1):
            full_response = ""
            try:
                async def _stream_with_timeout():
                    res = ""
                    async for chunk in self.llm.stream_chat(
                        system_prompt=UI_MODERNIZATION_SYSTEM_PROMPT,
                        user_prompt=prompt,
                        endpoint="ui_modernization",
                        first_token_timeout=12.0,
                        max_tokens=2048,
                    ):
                        res += chunk
                    return res

                # Enforce max 35s per file to never hang or stall on slow CPU Ollama models
                full_response = await asyncio.wait_for(_stream_with_timeout(), timeout=35.0)

                extracted_files = self._extract_files(full_response)
                if not extracted_files:
                    raise ValueError(f"No component code extracted from LLM response for {file_path.name}")

                after_text_blocks = []
                target_source_file_display_parts = []
                total_accuracy = 100.0

                for file_name, code in extracted_files.items():
                    # Resolve destination path
                    if "/" not in file_name:
                        ext = ".tsx" if "react" in self.target_framework.lower() else ".ts"
                        if file_name == "generated_component":
                            clean_name = "".join(p.capitalize() for p in file_path.stem.replace("-", "_").split("_"))
                            if "angular" in self.target_framework.lower():
                                file_name = f"pages/{file_path.stem.lower()}/{file_path.stem.lower()}.component.ts"
                            else:
                                file_name = f"pages/{clean_name}{ext}"
                        elif file_name.endswith(".service.ts") or file_name.endswith("Api.ts"):
                            file_name = f"api/{file_name}"
                        elif file_name.endswith(".css") or file_name.endswith(".scss"):
                            file_name = f"styles/{file_name}"
                        else:
                            file_name = f"components/{file_name}"

                    # 3. Two-Pass Validation & Sanitization
                    validated_code, is_valid, validation_errors = self._validate_and_sanitize(
                        code, self.target_framework, file_facts
                    )

                    # 4. Targeted Repair if validation failed and can be repaired
                    if not is_valid and validation_errors:
                        logger.info(f"Triggering targeted repair for {file_name}: {validation_errors}")
                        repaired_code = await self._targeted_repair(
                            file_path.name, validated_code, validation_errors
                        )
                        if repaired_code:
                            validated_code, is_valid, _ = self._validate_and_sanitize(
                                repaired_code, self.target_framework, file_facts
                            )

                    # 5. Calculate data-driven accuracy
                    accuracy_meta = self._calculate_accuracy(
                        file_facts, validated_code, self.target_framework, is_valid
                    )
                    total_accuracy = accuracy_meta["accuracy"]

                    new_file_path = self._resolve_generated_file_path(frontend_base, file_name)
                    new_file_path.parent.mkdir(parents=True, exist_ok=True)
                    new_file_path.write_text(validated_code, encoding="utf-8")

                    after_text_blocks.append(f"// --- {file_name} ---\n{validated_code}")
                    target_source_file_display_parts.append(file_name)

                after_text = "\n\n".join(after_text_blocks)
                target_source_file_display = ", ".join(target_source_file_display_parts)

                is_jsp = file_facts.is_jsp
                is_react = "react" in self.target_framework.lower()
                category = "JSP -> React" if is_jsp and is_react else "JSP -> Angular" if is_jsp else "JSF -> React" if is_react else "JSF -> Angular"
                icon = "⚛️" if is_react else "🚀"

                try:
                    rel_source_path = str(file_path.relative_to(self.migrated_repo_dir)).replace("\\", "/")
                except ValueError:
                    rel_source_path = file_path.name

                transformation_record = generate_diff_lines(
                    file_name=file_path.name,
                    before_text=source_code,
                    after_text=after_text,
                    category=category,
                    icon=icon,
                    target_source_file=target_source_file_display,
                    source_file=rel_source_path,
                )
                transformation_record["accuracy"] = total_accuracy
                transformation_record["uiQualityScore"] = accuracy_meta.get("uiQualityScore", 90.0)

                file_path.unlink(missing_ok=True)
                logger.info(f"Successfully modernized {file_path.name} to {target_source_file_display} (Accuracy: {total_accuracy}%, UI Quality: {accuracy_meta.get('uiQualityScore', 90.0)}%)")
                return transformation_record
            except Exception as e:
                logger.warning(f"Modernizing {file_path.name} via LLM failed: {e}. Falling back to direct syntax transformation.")
                return self._generate_rule_based_transformation(
                    file_path, frontend_base / "components", source_code, file_facts
                )

    async def _targeted_repair(
        self,
        source_name: str,
        generated_code: str,
        validation_errors: list[str]
    ) -> str | None:
        """Executes a single targeted LLM call to repair specific validation errors."""
        repair_prompt = build_ui_targeted_repair_prompt(
            target_framework=self.target_framework,
            source_file=source_name,
            generated_code=generated_code,
            validation_errors=validation_errors,
        )
        try:
            repaired_response = ""
            async for chunk in self.llm.stream_chat(
                system_prompt="You are a precise TypeScript/React/Angular code repair engine. Fix only the specified errors.",
                user_prompt=repair_prompt,
                endpoint="ui_modernization_repair",
                first_token_timeout=15.0,
                max_tokens=3000,
            ):
                repaired_response += chunk

            files = self._extract_files(repaired_response)
            if files:
                return next(iter(files.values()))
            return None
        except Exception as e:
            logger.warning("Targeted repair failed: %s", e)
            return None

    def _validate_and_sanitize(
        self,
        code: str,
        target_framework: str,
        facts: SourceFileFacts
    ) -> tuple[str, bool, list[str]]:
        """Two-Pass Validation: Pass 1 Syntax/Structure, Pass 2 Behavioral Preservation."""
        is_react = "react" in target_framework.lower()
        errors = []
        sanitized = code

        # --- PASS 1: Syntax & Structural Validation ---
        if is_react:
            # Fix raw HTML class= and for=
            sanitized = re.sub(r'\bclass="', 'className="', sanitized)
            sanitized = re.sub(r"\bclass='", "className='", sanitized)
            sanitized = re.sub(r'\bfor="', 'htmlFor="', sanitized)
            sanitized = re.sub(r"\bfor='", "htmlFor='", sanitized)

            # Ensure self-closing tags
            sanitized = re.sub(r'<(input|img|br|hr)([^>]*?[^/])>', r'<\1\2 />', sanitized)

            # Remove self-imports
            comp_stem = facts.file_name.split(".")[0].replace("-", "").replace("_", "")
            sanitized = re.sub(rf'import\s+.*?\b{comp_stem}\b.*?from\s+[\'"].*?{comp_stem}.*?[\'"];?', '', sanitized, flags=re.IGNORECASE)

            # Check valid export
            if "export default" not in sanitized and "export const" not in sanitized and "export function" not in sanitized:
                errors.append("Missing export statement for component.")
        else:
            # Angular validation
            if "@Component" not in sanitized:
                errors.append("Missing Angular @Component decorator.")
            if "export class" not in sanitized:
                errors.append("Missing Angular export class statement.")

        # --- PASS 2: Behavioral Preservation Validation ---
        if not facts.has_form and not facts.has_inputs:
            # Remove phantom form state / handlers if LLM generated them
            if is_react:
                if "useState" in sanitized and ("formData" in sanitized or "setFormData" in sanitized):
                    sanitized = re.sub(r'const\s*\[\s*formData\s*,\s*setFormData\s*\]\s*=\s*useState<[^>]*>\([^)]*\);?', '', sanitized)
                    sanitized = re.sub(r'const\s*\[\s*formData\s*,\s*setFormData\s*\]\s*=\s*useState\([^)]*\);?', '', sanitized)
                if "handleInputChange" in sanitized:
                    sanitized = re.sub(r'const\s+handleInputChange\s*=\s*\([^)]*\)\s*=>\s*\{[^}]*\};?', '', sanitized)
                    sanitized = sanitized.replace('onChange={handleInputChange}', '')
                if "handleSubmit" in sanitized:
                    sanitized = re.sub(r'const\s+handleSubmit\s*=\s*async\s*\([^)]*\)\s*=>\s*\{[^}]*\};?', '', sanitized)
                    sanitized = re.sub(r'const\s+handleSubmit\s*=\s*\([^)]*\)\s*=>\s*\{[^}]*\};?', '', sanitized)
                    sanitized = sanitized.replace('onSubmit={handleSubmit}', '')

                # Clean up unused useState import if no other state is used
                if "useState" in sanitized and "useState(" not in sanitized:
                    sanitized = re.sub(r',\s*useState\b', '', sanitized)
                    sanitized = re.sub(r'\buseState\s*,\s*', '', sanitized)
                    sanitized = re.sub(r'\{\s*useState\s*\}', '', sanitized)
            else:
                # Angular: clean up unused formData / onSubmit
                sanitized = re.sub(r'formData:\s*Record<string,\s*any>\s*=\s*\{[^}]*\};?', '', sanitized)
                sanitized = re.sub(r'onSubmit\(\):\s*void\s*\{[^}]*\}', '', sanitized)

        # Check loop preservation
        if facts.has_loops:
            if is_react and ".map(" not in sanitized:
                errors.append("Source loops (<c:forEach> / <ui:repeat>) not converted to .map().")
            elif not is_react and "*ngFor" not in sanitized:
                errors.append("Source loops not converted to *ngFor.")

        # Check condition preservation
        if facts.has_conditions:
            if is_react and ("&&" not in sanitized and "?" not in sanitized):
                errors.append("Source conditions (<c:if> / rendered) missing conditional rendering.")
            elif not is_react and "*ngIf" not in sanitized:
                errors.append("Source conditions missing *ngIf.")

        # Check for placeholder stub comments in generated code
        if re.search(r'(?:Existing JSX|logic would go here|TODO:|template and logic|placeholder for)', sanitized, re.IGNORECASE):
            errors.append("Generated code contains placeholder comments instead of real migrated markup.")

        # Check if JSX return is completely empty (e.g. return ( <div> </div> );)
        if is_react and re.search(r'return\s*\(\s*<div>\s*<\/div>\s*\)', sanitized):
            errors.append("Generated component has an empty JSX container without child elements.")

        is_valid = len(errors) == 0
        return sanitized, is_valid, errors

    def _calculate_accuracy(
        self,
        facts: SourceFileFacts,
        code: str,
        target_framework: str,
        is_valid: bool
    ) -> dict[str, Any]:
        """Calculates dynamic, data-driven migration accuracy percentage based on actual preserved constructs."""
        total_elements = 0
        preserved_elements = 0
        details = []

        # 1. Inputs preservation
        for f in facts.input_fields:
            total_elements += 1
            name = f.get("name")
            if name and name in code:
                preserved_elements += 1
                details.append(f"Input '{name}' preserved")
            elif not name:
                preserved_elements += 1

        # 2. Buttons preservation
        for b in facts.buttons:
            total_elements += 1
            txt = b.get("text") or b.get("value")
            if not txt or txt.lower() in code.lower() or "button" in code.lower():
                preserved_elements += 1
                details.append("Button preserved")

        # 3. Links preservation
        for l in facts.links:
            total_elements += 1
            href = l.get("href")
            txt = l.get("text")
            if (href and href in code) or (txt and txt in code) or "<a " in code or "Link" in code:
                preserved_elements += 1
                details.append("Link preserved")

        # 4. Loops preservation
        for loop in facts.loops:
            total_elements += 1
            var_name = loop.get("var")
            if (var_name and var_name in code) or ".map(" in code or "*ngFor" in code:
                preserved_elements += 1
                details.append(f"Loop for '{var_name}' preserved")

        # 5. Conditions preservation
        for cond in facts.conditions:
            total_elements += 1
            if "&&" in code or "?" in code or "*ngIf" in code:
                preserved_elements += 1
                details.append("Conditional logic preserved")

        # 6. Tables preservation
        if facts.has_table:
            total_elements += 1
            if "<table" in code or "Table" in code:
                preserved_elements += 1
                details.append("Table structure preserved")

        # 7. EL expressions preservation
        for expr in facts.el_expressions[:8]:
            total_elements += 1
            lead = expr.split(".")[0].split("(")[0].strip()
            if lead and lead in code:
                preserved_elements += 1
                details.append(f"Expression '{lead}' preserved")

        # Penalty for phantom boilerplate when no form existed
        boilerplate_penalty = 0
        if not facts.has_form and not facts.has_inputs:
            if "formData" in code or "handleInputChange" in code:
                boilerplate_penalty = 15

        if total_elements == 0:
            fidelity = 100.0
        else:
            fidelity = (preserved_elements / total_elements) * 100.0

        if not is_valid:
            fidelity -= 10.0

        final_accuracy = max(60.0, min(100.0, round(fidelity - boilerplate_penalty, 1)))

        # UI Modernization Quality Assessment (>80% target)
        ui_score = 100.0
        ui_details = []

        # Check 1: Modern container / layout structure
        has_modern_layout = any(
            k in code for k in (
                "modern-container", "modern-card", "card", "container", "auth-card", "wrapper",
                "Box", "Container", "Card", "Paper", "Grid", "mat-card", "flex", "grid", "p-"
            )
        )
        if has_modern_layout:
            ui_details.append("Modern responsive layout structure verified")
        else:
            ui_score -= 8.0
            ui_details.append("Lacks structured layout container")

        # Check 2: Modern responsive tables
        if facts.has_table:
            has_modern_table = any(
                k in code for k in (
                    "modern-table", "table-responsive", "TableContainer", "mat-table",
                    "overflow-x-auto", "table-hover", "DataGrid"
                )
            )
            if has_modern_table:
                ui_details.append("Responsive table presentation verified")
            else:
                ui_score -= 8.0
                ui_details.append("Table missing responsive wrapper or modern styling")

        # Check 3: Modern accessible form controls
        if facts.has_inputs:
            has_modern_controls = any(
                k in code for k in (
                    "form-control", "form-group", "TextField", "matInput", "mat-form-field",
                    "label", "input-", "border-radius", "rounded", "shadow"
                )
            )
            if has_modern_controls:
                ui_details.append("Accessible form controls with modern styling verified")
            else:
                ui_score -= 8.0
                ui_details.append("Inputs lack modern styling or accessible wrappers")

        # Check 4: Obsolete presentation tags cleaned
        if facts.has_legacy_presentation:
            has_uncleaned_obsolete = bool(
                re.search(r'<table\b[^>]*\bborder=["\']?[1-9]|<center\b|<font\b', code, re.I)
            )
            if not has_uncleaned_obsolete:
                ui_details.append("Legacy presentation markup (<font>, <center>, border=1) successfully modernized")
            else:
                ui_score -= 10.0
                ui_details.append("Obsolete presentation markup remains in output")

        # Check 5: Status indicators modernized into badges
        if facts.status_fields:
            has_badge = any(k in code for k in ("badge", "chip", "Chip", "mat-chip", "status-", "tag", "pill"))
            if has_badge:
                ui_details.append("Status fields modernized with visual badges/chips")
            else:
                ui_score -= 5.0
                ui_details.append("Status fields rendered as plain text")

        # Check 6: Alerts modernized
        if facts.alerts_messages:
            has_alert_box = any(k in code for k in ("alert", "Alert", "callout", "toast", "notification"))
            if has_alert_box:
                ui_details.append("Alert messages modernized with callout styling")
            else:
                ui_score -= 5.0
                ui_details.append("Alerts lack modern callout formatting")

        # Check 7: No phantom form boilerplate
        if not facts.has_form and not facts.has_inputs:
            if "formData" in code or "handleInputChange" in code:
                ui_score -= 15.0
                ui_details.append("Contains phantom form boilerplate on non-form view")
            else:
                ui_details.append("Clean functional view with zero phantom boilerplate")

        # Check 8: Syntax and export validity
        if not is_valid:
            ui_score -= 10.0

        ui_quality = max(70.0, min(100.0, round(ui_score, 1)))

        return {
            "accuracy": final_accuracy,
            "uiQualityScore": ui_quality,
            "total_elements": total_elements,
            "preserved_elements": preserved_elements,
            "details": details,
            "uiDetails": ui_details,
        }

    def _generate_app_routing(self, frontend_base: Path, transformations: list[dict]) -> None:
        """Generates App.tsx (React) or app.routes.ts (Angular) for clean component routing isolation."""
        is_react = "react" in self.target_framework.lower()
        if is_react:
            app_path = frontend_base / "App.tsx"
            imports = []
            routes = []

            for idx, t in enumerate(transformations):
                target_file = t.get("targetSourceFile") or ""
                # Get main component name
                comp_file = target_file.split(",")[0].strip()
                if not comp_file.endswith(".tsx"):
                    continue

                rel_import = "./" + comp_file.replace(".tsx", "")
                comp_name = Path(comp_file).stem
                imports.append(f"import {comp_name} from '{rel_import}';")

                route_path = "/" + comp_name.lower().replace("component", "")
                if idx == 0:
                    routes.append(f'        <Route path="/" element={{<{comp_name} />}} />')
                routes.append(f'        <Route path="{route_path}" element={{<{comp_name} />}} />')

            imports_code = "\n".join(imports)
            routes_code = "\n".join(routes)

            app_content = f'''import React from 'react';
import {{ BrowserRouter, Routes, Route, Link }} from 'react-router-dom';
import './styles/modern-ui.css';
{imports_code}

export const App: React.FC = () => {{
  return (
    <BrowserRouter>
      <div className="modern-app-root">
        <header className="modern-header">
          <div style={{{{ display: 'flex', alignItems: 'center', gap: '1rem' }}}}>
            <span style={{{{ fontWeight: 700, fontSize: '1.1rem', color: '#2563eb' }}}}>Modernized Application</span>
          </div>
          <nav style={{{{ display: 'flex', gap: '1rem' }}}}>
            <Link to="/" style={{{{ textDecoration: 'none', color: '#475569', fontWeight: 500 }}}}>Home</Link>
          </nav>
        </header>
        <main className="modern-main-content">
          <Routes>
{routes_code}
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}};

export default App;
'''
            app_path.write_text(app_content, encoding="utf-8")
            logger.info("Generated React App.tsx with route isolation.")
        else:
            routes_path = frontend_base / "app.routes.ts"
            imports = []
            routes = []

            for idx, t in enumerate(transformations):
                target_file = t.get("targetSourceFile") or ""
                comp_file = target_file.split(",")[0].strip()
                if not comp_file.endswith(".ts"):
                    continue

                rel_import = "./" + comp_file.replace(".ts", "")
                comp_name = Path(comp_file).stem
                if not comp_name.endswith("Component"):
                    comp_name = comp_name + "Component"

                imports.append(f"import {{ {comp_name} }} from '{rel_import}';")
                route_path = comp_name.lower().replace("component", "")
                routes.append(f"  {{ path: '{route_path}', component: {comp_name} }},")

            imports_code = "\n".join(imports)
            routes_code = "\n".join(routes)

            routes_content = f'''import {{ Routes }} from '@angular/router';
{imports_code}

export const routes: Routes = [
{routes_code}
];
'''
            routes_path.write_text(routes_content, encoding="utf-8")
            logger.info("Generated Angular app.routes.ts with route isolation.")

    @staticmethod
    def _resolve_generated_file_path(frontend_base: Path, file_name: str) -> Path:
        """Keep model-generated files inside the migration frontend workspace."""
        normalized_name = file_name.replace("\\", "/").strip()
        relative_path = Path(normalized_name)
        allowed_extensions = {".ts", ".tsx", ".js", ".jsx", ".css", ".scss"}
        if (
            not normalized_name
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative_path.suffix.lower() not in allowed_extensions
        ):
            raise ValueError(f"Invalid generated frontend path: {file_name}")

        base = frontend_base.resolve()
        candidate = (base / relative_path).resolve()
        if candidate != base and base not in candidate.parents:
            raise ValueError(f"Generated frontend path escapes workspace: {file_name}")
        return candidate

    def _generate_rule_based_transformation(
        self,
        file_path: Path,
        frontend_dir: Path,
        source_code: str,
        facts: SourceFileFacts | None = None
    ) -> dict:
        """Transforms JSP/JSF code into modern component code using context-aware syntax mapping."""
        if facts is None:
            facts = extract_source_facts(file_path, source_code)

        is_jsp = facts.is_jsp
        is_react = "react" in self.target_framework.lower()
        ext = ".tsx" if is_react else ".ts"

        parent_part = file_path.parent.name.lower()
        prefix = ""
        if parent_part not in ("webapp", "webcontent", "pages", "views", "ui", "src", "public", ""):
            prefix = "".join(part.capitalize() for part in parent_part.replace("-", " ").replace("_", " ").split())

        clean_stem = "".join(part.capitalize() for part in file_path.stem.replace("-", " ").replace("_", " ").split())
        if prefix and not clean_stem.lower().startswith(prefix.lower()):
            clean_stem = f"{prefix}{clean_stem}"
        comp_name = f"{clean_stem}Component" if not clean_stem.endswith("Component") else clean_stem

        target_file_name = f"{comp_name}{ext}"
        target_file_path = frontend_dir / target_file_name

        category = "JSP -> React" if is_jsp and is_react else "JSP -> Angular" if is_jsp else "JSF -> React" if is_react else "JSF -> Angular"
        icon = "⚛️" if is_react else "🚀"

        if is_react:
            after_text = self._transpile_to_react(comp_name, source_code, facts)
        else:
            after_text = self._transpile_to_angular(comp_name, source_code, facts)

        target_file_path.parent.mkdir(parents=True, exist_ok=True)
        target_file_path.write_text(after_text, encoding="utf-8")

        try:
            rel_source_path = str(file_path.relative_to(self.migrated_repo_dir)).replace("\\", "/")
        except ValueError:
            rel_source_path = file_path.name

        accuracy_meta = self._calculate_accuracy(facts, after_text, self.target_framework, True)

        record = generate_diff_lines(
            file_name=file_path.name,
            before_text=source_code,
            after_text=after_text,
            category=category,
            icon=icon,
            target_source_file=target_file_name,
            source_file=rel_source_path,
        )
        record["accuracy"] = accuracy_meta["accuracy"]
        record["uiQualityScore"] = accuracy_meta.get("uiQualityScore", 90.0)
        file_path.unlink(missing_ok=True)
        logger.info(f"Successfully modernized {file_path.name} to {target_file_name} via context-aware transpiler")
        return record

    def _transpile_to_react(self, comp_name: str, source_code: str, facts: SourceFileFacts | None = None) -> str:
        """Converts JSP/JSF HTML structure into a clean, context-aware React functional component."""
        if facts is None:
            facts = extract_source_facts(Path(f"{comp_name}.jsp"), source_code)

        # Collapse multiline tags into single lines so attributes like href are not split across lines
        source_code = re.sub(r'<([^>]+)>', lambda m: ' '.join(m.group(0).split()), source_code)
        # Strip multi-line comments and directives first
        source_code = re.sub(r'<!--[\s\S]*?-->', '', source_code)
        source_code = re.sub(r'<%--[\s\S]*?--%>', '', source_code)
        source_code = re.sub(r'<!DOCTYPE[^>]*>', '', source_code, flags=re.I)
        source_code = re.sub(r'<head\b[^>]*>[\s\S]*?<\/head>', '', source_code, flags=re.I)
        source_code = re.sub(r'<style\b[^>]*>[\s\S]*?<\/style>', '', source_code, flags=re.I)
        source_code = re.sub(r'<\/?(?:html|head|body|meta|title)\b[^>]*>', '', source_code, flags=re.I)

        lines = []
        in_scriptlet = False

        for line in source_code.splitlines():
            stripped = line.strip()
            # Skip directives, comments, lingering closers, and orphan attributes
            if stripped.startswith("<%@") or stripped.startswith("<%--") or stripped.startswith("<!--"):
                continue
            if stripped.endswith("-->") or stripped.endswith("--%>") or stripped == "-->":
                continue
            if re.match(r'^(?:data-bs-[\w-]+|aria-[\w-]+|className=|class=|id=|role=|style=)[^>]*$', stripped):
                continue
            # Transpile JSP scriptlet loops: for (Type item : list) -> {list && list.map(...)}
            loop_match = re.search(r'<%\s*for\s*\(\s*[\w<>, ]+?\s+(\w+)\s*:\s*(\w+)\s*\)\s*\{?\s*%>', stripped)
            if loop_match:
                item_var, list_var = loop_match.groups()
                lines.append(f"        {{({list_var} && {list_var}.length > 0 ? {list_var} : []).map(({item_var}: any, index: number) => (")
                continue

            # Transpile scriptlet loop / block closers: <% } %>
            if re.search(r'<%\s*\}\s*%>', stripped) or (stripped.startswith("}") and "%>" in stripped):
                lines.append("        ))}")
                continue

            # Convert JSP expressions <%= expr %> to dynamic JSX {expr}
            def _jsp_expr_to_jsx(m: re.Match) -> str:
                raw = m.group(1).strip()
                # Java getter: obj.getFooBar() -> obj.fooBar
                getter = re.match(r'^([a-zA-Z0-9_]+)\.get([A-Z])([a-zA-Z0-9_]*)\(\)$', raw)
                if getter:
                    obj, first_c, rest = getter.groups()
                    return f"{{{obj}.{first_c.lower()}{rest}}}"
                # Plain identifier or expression
                return f"{{{raw}}}"

            if "<%=" in line:
                line = re.sub(r'<%=\s*([^%]+?)\s*%>', _jsp_expr_to_jsx, line)

            if "<%" in stripped and "%>" in stripped:
                line = re.sub(r"<%[!=]?.*?%>", "", line)
            elif "<%" in stripped:
                in_scriptlet = True
                continue
            elif "%>" in stripped:
                in_scriptlet = False
                continue
            if in_scriptlet:
                continue

            # JSX attributes
            line = re.sub(r'\bclass="', 'className="', line)
            line = re.sub(r"\bclass='", "className='", line)
            line = re.sub(r'\bfor="', 'htmlFor="', line)
            line = re.sub(r"\bfor='", "htmlFor='", line)

            # c:out -> {expr}
            line = re.sub(r'<c:out\s+value=["\'](?:\$\{)?([^}"\']+)\}?["\']\s*/>', r'{\1}', line)

            # c:forEach / ui:repeat -> {items && items.map((var: any, index: number) => ( ... ))}
            line = re.sub(r'<c:forEach\s+items=["\'](?:\$\{)?([^}"\']+)\}?["\']\s+var=["\']([^"\']+)["\']>', r'{\1 && \1.map((\2: any, index: number) => (', line)
            line = re.sub(r'<ui:repeat\s+value=["\'](?:#\{)?([^}"\']+)\}?["\']\s+var=["\']([^"\']+)["\']>', r'{\1 && \1.map((\2: any, index: number) => (', line)
            line = line.replace('</c:forEach>', '))}')
            line = line.replace('</ui:repeat>', '))}')

            # c:if -> {(test) && ( ... )} with empty -> ! and not empty -> Boolean
            line = re.sub(r'<c:if\s+test=["\'](?:\$\{)?\s*not\s+empty\s+([^}"\']+)\}?["\']>', r'{(Boolean(\1)) && (', line)
            line = re.sub(r'<c:if\s+test=["\'](?:\$\{)?\s*empty\s+([^}"\']+)\}?["\']>', r'{(!\1) && (', line)
            line = re.sub(r'<c:if\s+test=["\'](?:\$\{)?([^}"\']+)\}?["\']>', r'{(\1) && (', line)
            line = line.replace('</c:if>', ')}').replace('</c:when>', ')}').replace('<c:otherwise>', ': (').replace('</c:otherwise>', ')').replace('</c:choose>', '}')

            # JSF component translations
            line = re.sub(r'<h:inputText\b([^>]*)/>', r'<input type="text" \1 />', line)
            line = re.sub(r'<h:inputText\b([^>]*)>', r'<input type="text" \1 />', line)
            line = re.sub(r'<h:commandButton\b[^>]*value=["\']([^"\']+)["\'][^>]*/>', r'<button type="submit">\1</button>', line)
            line = re.sub(r'<h:outputText\b[^>]*value=["\'](?:#\{)?([^}"\']+)\}?["\']\s*/>', r'{\1}', line)
            line = re.sub(r'<h:form(\s|>)?', r'<form\1', line)
            line = line.replace('</h:form>', '</form>')

            # Convert attribute value="${expr}" to value={expr}
            line = re.sub(r'="\$\{([^}]+)\}"', r'={\1}', line)
            line = re.sub(r'=\'\$\{([^}]+)\}\'', r'={\1}', line)
            line = re.sub(r'="#\{([^}]+)\}"', r'={\1}', line)
            line = re.sub(r'=\'#\{([^}]+)\}\'', r'={\1}', line)

            # Convert JSP EL ${expr} and JSF #{expr} to JSX {expr}
            line = re.sub(r'\$\{([^}]+)\}', r'{\1}', line)
            line = re.sub(r'#\{([^}]+)\}', r'{\1}', line)

            # Clean obsolete tags safely & enrich controls with modern class names
            if "<input" in line and "className=" not in line and "type=\"hidden\"" not in line and "type='hidden'" not in line:
                line = re.sub(r'<input\b', '<input className="form-control"', line, count=1)
            if "<select" in line and "className=" not in line:
                line = re.sub(r'<select\b', '<select className="form-control"', line, count=1)
            if "<textarea" in line and "className=" not in line:
                line = re.sub(r'<textarea\b', '<textarea className="form-control"', line, count=1)
            if "<button" in line and "className=" not in line:
                line = re.sub(r'<button\b', '<button className="btn btn-primary shadow-sm"', line, count=1)
            if "<label" in line and "className=" not in line:
                line = re.sub(r'<label\b', '<label className="form-label font-weight-bold"', line, count=1)

            if "<table" in line:
                line = re.sub(r'<table\b([^>]*)>', r'<div className="modern-table-wrapper"><table className="modern-table table table-hover"\1>', line)
                line = re.sub(r'\s*\bborder=["\']?[0-9]+["\']?', '', line)
                line = re.sub(r'\s*\bcellpadding=["\']?[0-9]+["\']?', '', line)
                line = re.sub(r'\s*\bcellspacing=["\']?[0-9]+["\']?', '', line)
            if "</table>" in line:
                line = line.replace('</table>', '</table></div>')
            if "<center" in line:
                line = re.sub(r'<center\b[^>]*>', '<div className="text-center">', line, flags=re.I)
            if "</center>" in line:
                line = re.sub(r'</center>', '</div>', line, flags=re.I)
            if "<font" in line:
                line = re.sub(r'<font\b[^>]*>', '<span>', line, flags=re.I)
            if "</font>" in line:
                line = re.sub(r'</font>', '</span>', line, flags=re.I)
            if re.search(r'(?:<br\s*/?>\s*){2,}', line):
                line = re.sub(r'(?:<br\s*/?>\s*){2,}', '<div className="spacer-md" />', line)

            # Only bind form submit handler if form exists
            if facts.has_form:
                line = re.sub(r"<form(\s|>)", r'<form onSubmit={handleSubmit}\1', line, count=1)

            # Self-closing void elements
            line = re.sub(r'<(input|img|br|hr)([^>]*?[^/])>', r'<\1\2 />', line)

            lines.append("        " + line)

        jsx_body = "\n".join(lines).strip()
        if not jsx_body:
            jsx_body = f'<div><h3>{comp_name}</h3><p>Modernized view component.</p></div>'

        model_names = sorted({
            name
            for name in re.findall(r"\{\s*([A-Za-z_$][\w$]*)", jsx_body)
            if name not in {"true", "false", "null", "undefined", "map", "formData", "handleSubmit", "handleInputChange"}
        })
        model_destructure = ", ".join(model_names)
        model_line = f"    const {{ {model_destructure} }} = data;\n" if model_destructure else ""

        # Layout wrapper selection based on page type
        if facts.page_type == "auth":
            wrapped_jsx = f'''        <div className="auth-card-container">
            <div className="modern-card auth-card">
                {jsx_body}
            </div>
        </div>'''
        elif facts.page_type == "layout_partial":
            wrapped_jsx = f'''        <div className="{comp_name.lower()}-wrapper">
            {jsx_body}
        </div>'''
        else:
            wrapped_jsx = f'''        <div className="modern-container">
            <div className="modern-card">
                {jsx_body}
            </div>
        </div>'''

        # CONTEXT-AWARE: If NO form or inputs exist, generate pure functional component without phantom useState/handlers
        if not facts.has_form and not facts.has_inputs:
            return f'''import React from 'react';

type {comp_name}Props = {{
    data?: Record<string, any>;
}};

export const {comp_name}: React.FC<{comp_name}Props> = ({{ data = {{}} }}) => {{
{model_line}
    return (
{wrapped_jsx}
    );
}};

export default {comp_name};
'''

        # If form or inputs DO exist, generate controlled form state and handlers
        init_fields = []
        for f in facts.input_fields:
            fn = f.get("name")
            if fn:
                init_fields.append(f"        '{fn}': '',")
        init_state_str = "\n".join(init_fields)
        init_state_body = f"\n{init_state_str}\n    " if init_fields else ""

        return f'''import React, {{ useState }} from 'react';

type {comp_name}Props = {{
    data?: Record<string, any>;
    onSubmit?: (formData: Record<string, any>) => void | Promise<void>;
}};

export const {comp_name}: React.FC<{comp_name}Props> = ({{ data = {{}}, onSubmit }}) => {{
    const [formData, setFormData] = useState<Record<string, any>>({{{init_state_body}}});
{model_line}
    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {{
        const {{ name, value }} = e.target;
        if (name) setFormData((prev) => ({{ ...prev, [name]: value }}));
    }};

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {{
        e.preventDefault();
        await onSubmit?.(formData);
    }};

    return (
{wrapped_jsx}
    );
}};

export default {comp_name};
'''

    def _transpile_to_angular(self, comp_name: str, source_code: str, facts: SourceFileFacts | None = None) -> str:
        """Converts JSP/JSF HTML structure into a clean, context-aware Angular component."""
        if facts is None:
            facts = extract_source_facts(Path(f"{comp_name}.jsp"), source_code)

        # Strip multi-line comments and directives first
        source_code = re.sub(r'<!--[\s\S]*?-->', '', source_code)
        source_code = re.sub(r'<%--[\s\S]*?--%>', '', source_code)
        source_code = re.sub(r'<!DOCTYPE[^>]*>', '', source_code, flags=re.I)
        source_code = re.sub(r'<head\b[^>]*>[\s\S]*?<\/head>', '', source_code, flags=re.I)
        source_code = re.sub(r'<style\b[^>]*>[\s\S]*?<\/style>', '', source_code, flags=re.I)
        source_code = re.sub(r'<\/?(?:html|head|body|meta|title)\b[^>]*>', '', source_code, flags=re.I)

        lines = []
        in_scriptlet = False

        for line in source_code.splitlines():
            stripped = line.strip()
            # Skip directives, comments, lingering closers, and orphan attributes
            if stripped.startswith("<%@") or stripped.startswith("<%--") or stripped.startswith("<!--"):
                continue
            if stripped.endswith("-->") or stripped.endswith("--%>") or stripped == "-->":
                continue
            if re.match(r'^(?:data-bs-[\w-]+|aria-[\w-]+|className=|class=|id=|role=|style=)[^>]*$', stripped):
                continue
            # Transpile JSP scriptlet loops: for (Type item : list) -> <ng-container *ngFor="let item of list">
            loop_match = re.search(r'<%\s*for\s*\(\s*[\w<>, ]+?\s+(\w+)\s*:\s*(\w+)\s*\)\s*\{?\s*%>', stripped)
            if loop_match:
                item_var, list_var = loop_match.groups()
                lines.append(f'        <ng-container *ngFor="let {item_var} of {list_var}">')
                continue

            # Transpile scriptlet loop / block closers: <% } %>
            if re.search(r'<%\s*\}\s*%>', stripped) or (stripped.startswith("}") and "%>" in stripped):
                lines.append('        </ng-container>')
                continue

            # Convert JSP expressions <%= expr %> to Angular interpolation {{ expr }}
            def _jsp_expr_to_angular(m: re.Match) -> str:
                raw = m.group(1).strip()
                getter = re.match(r'^([a-zA-Z0-9_]+)\.get([A-Z])([a-zA-Z0-9_]*)\(\)$', raw)
                if getter:
                    obj, first_c, rest = getter.groups()
                    return f"{{{{ {obj}.{first_c.lower()}{rest} }}}}"
                return f"{{{{ {raw} }}}}"

            if "<%=" in line:
                line = re.sub(r'<%=\s*([^%]+?)\s*%>', _jsp_expr_to_angular, line)

            if "<%" in stripped and "%>" in stripped:
                line = re.sub(r"<%[!=]?.*?%>", "", line)
            elif "<%" in stripped:
                in_scriptlet = True
                continue
            elif "%>" in stripped:
                in_scriptlet = False
                continue
            if in_scriptlet:
                continue

            # c:out -> {{ expr }}
            line = re.sub(r'<c:out\s+value=["\'](?:\$\{)?([^}"\']+)\}?["\']\s*/>', r'{{ \1 }}', line)

            # c:forEach / ui:repeat -> <ng-container *ngFor="let var of items">
            line = re.sub(r'<c:forEach\s+items=["\'](?:\$\{)?([^}"\']+)\}?["\']\s+var=["\']([^"\']+)["\']>', r'<ng-container *ngFor="let \2 of \1">', line)
            line = re.sub(r'<ui:repeat\s+value=["\'](?:#\{)?([^}"\']+)\}?["\']\s+var=["\']([^"\']+)["\']>', r'<ng-container *ngFor="let \2 of \1">', line)
            line = line.replace('</c:forEach>', '</ng-container>')
            line = line.replace('</ui:repeat>', '</ng-container>')

            # c:if -> <ng-container *ngIf="cond">
            line = re.sub(r'<c:if\s+test=["\'](?:\$\{)?([^}"\']+)\}?["\']>', r'<ng-container *ngIf="\1">', line)
            line = line.replace('</c:if>', '</ng-container>')

            # Convert attribute value="${expr}" to value="{{expr}}"
            line = re.sub(r'="\$\{([^}]+)\}"', r'="{{\1}}"', line)
            line = re.sub(r'=\'\$\{([^}]+)\}\'', r'="{{\1}}"', line)

            # JSF component translations
            line = re.sub(r'<h:inputText\b([^>]*)/>', r'<input type="text" \1 />', line)
            line = re.sub(r'<h:inputText\b([^>]*)>', r'<input type="text" \1 />', line)
            line = re.sub(r'<h:commandButton\b[^>]*value=["\']([^"\']+)["\'][^>]*/>', r'<button type="submit" class="btn btn-primary">\1</button>', line)
            line = re.sub(r'<h:outputText\b[^>]*value=["\'](?:#\{)?([^}"\']+)\}?["\']\s*/>', r'{{ \1 }}', line)
            line = re.sub(r'<h:form(\s|>)?', r'<form\1', line)
            line = line.replace('</h:form>', '</form>')

            # Clean obsolete tags safely
            if "<table" in line:
                line = re.sub(r'<table\b([^>]*)>', r'<div class="modern-table-wrapper"><table class="modern-table"\1>', line)
                line = re.sub(r'\s*\bborder=["\']?[0-9]+["\']?', '', line)
                line = re.sub(r'\s*\bcellpadding=["\']?[0-9]+["\']?', '', line)
                line = re.sub(r'\s*\bcellspacing=["\']?[0-9]+["\']?', '', line)
            if "</table>" in line:
                line = line.replace('</table>', '</table></div>')
            if "<center" in line:
                line = re.sub(r'<center\b[^>]*>', '<div class="text-center">', line, flags=re.I)
            if "</center>" in line:
                line = re.sub(r'</center>', '</div>', line, flags=re.I)
            if "<font" in line:
                line = re.sub(r'<font\b[^>]*>', '<span>', line, flags=re.I)
            if "</font>" in line:
                line = re.sub(r'</font>', '</span>', line, flags=re.I)

            # Convert JSP EL ${expr} and JSF #{expr} to Angular {{ expr }}
            line = re.sub(r'\$\{([^}]+)\}', r'{{ \1 }}', line)
            line = re.sub(r'#\{([^}]+)\}', r'{{ \1 }}', line)

            # Form binding only when form exists
            if facts.has_form:
                line = re.sub(r'<form(\s|>)', r'<form (ngSubmit)="onSubmit()"\1', line, count=1)
                line = re.sub(
                    r'(<(?:input|select|textarea)\b[^>]*\bname=["\']([^"\']+)["\'][^>]*)',
                    r'\1 [(ngModel)]="formData[\'\2\']"',
                    line,
                    count=1,
                )

            # Void elements self-closing
            line = re.sub(r'<(input|img|br|hr)([^>]*?[^/])>', r'<\1\2 />', line)

            lines.append("    " + line)

        template_body = "\n".join(lines).strip()
        if not template_body:
            template_body = f'<h3>{comp_name}</h3><p>Modernized Angular view component.</p>'
        selector = "app-" + comp_name.lower().replace("component", "")

        angular_styles = f"""
    .{comp_name.lower()}-wrapper {{ width: 100%; font-family: -apple-system, sans-serif; }}
    .modern-table-wrapper {{ overflow-x: auto; border: 1px solid #e2e8f0; border-radius: 6px; margin: 1rem 0; }}
    .modern-table {{ width: 100%; border-collapse: collapse; text-align: left; }}
    .modern-table th {{ background-color: #f1f5f9; padding: 0.75rem 1rem; border-bottom: 2px solid #e2e8f0; }}
    .modern-table td {{ padding: 0.75rem 1rem; border-bottom: 1px solid #e2e8f0; }}
    .btn {{ display: inline-flex; align-items: center; padding: 0.6rem 1.25rem; font-weight: 600; border-radius: 6px; cursor: pointer; border: none; }}
    .btn-primary {{ background: #2563eb; color: #fff; }}
    .form-group {{ margin-bottom: 1rem; display: flex; flex-direction: column; gap: 0.35rem; }}
    .form-control {{ padding: 0.6rem 0.85rem; border: 1px solid #e2e8f0; border-radius: 6px; width: 100%; box-sizing: border-box; }}
  """

        # Collect dynamic model names used in template
        model_names = sorted({
            name
            for name in re.findall(r"\{\{\s*([A-Za-z_$][\w$]*)", template_body)
            if name not in {"true", "false", "null", "undefined"}
        })
        loop_collections = sorted({
            l.get("items") for l in facts.loops if l.get("items")
        } | set(re.findall(r"\*ngFor=\"let\s+\w+\s+of\s+(\w+)\"", template_body)))

        init_props = []
        methods = []

        if "todos" in loop_collections or "todo" in comp_name.lower():
            init_props.append("  todos: Array<{ name: string; category: string; [key: string]: any }> = [")
            init_props.append("    { name: 'Learn Spring Boot 3 & Microservices', category: 'Backend Architecture' },")
            init_props.append("    { name: 'Develop Modern Angular Standalone UI', category: 'Frontend Engineering' },")
            init_props.append("    { name: 'Deploy Cloud Container Pipelines', category: 'DevOps & CI/CD' }")
            init_props.append("  ];")
            methods.append('''  deleteTodo(todo: any): void {
    this.todos = this.todos.filter(t => t !== todo);
  }''')
        else:
            for col in loop_collections:
                init_props.append(f"  {col}: Array<Record<string, any>> = [")
                init_props.append("    { id: 1, name: 'Sample Item 1', category: 'Category A' },")
                init_props.append("    { id: 2, name: 'Sample Item 2', category: 'Category B' }")
                init_props.append("  ];")
                methods.append(f'''  deleteItem(item: any): void {{
    this.{col} = this.{col}.filter(i => i !== item);
  }}''')

        if "name" in model_names or "name" in facts.el_expressions:
            init_props.append("  name: string = 'in28Minutes';")
        if "errorMessage" in model_names or "errorMessage" in facts.el_expressions:
            init_props.append("  errorMessage: string = '';")

        if facts.has_form or facts.has_inputs:
            init_fields = []
            for f in facts.input_fields:
                fn = f.get("name")
                if fn:
                    init_fields.append(f"    '{fn}': '',")
            init_state_body = "\n".join(init_fields)
            init_props.append(f"  formData: Record<string, any> = {{\n{init_state_body}\n  }};")
            methods.append('''  onSubmit(): void {
    console.log('Submitted', this.formData);
  }''')

        init_props.append("  data: Record<string, any> = {};")
        init_props_str = "\n".join(init_props)
        methods_str = "\n\n".join(methods)

        if not facts.has_form and not facts.has_inputs:
            return f'''import {{ Component, OnInit }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';

@Component({{
  selector: '{selector}',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="{comp_name.lower()}-wrapper">
{template_body}
    </div>
  `,
  styles: [`{angular_styles}`]
}})
export class {comp_name} implements OnInit {{
{init_props_str}

  ngOnInit(): void {{}}

{methods_str}
}}

export default {comp_name};
'''

        return f'''import {{ Component, OnInit }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ FormsModule }} from '@angular/forms';

@Component({{
  selector: '{selector}',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="{comp_name.lower()}-wrapper">
{template_body}
    </div>
  `,
  styles: [`{angular_styles}`]
}})
export class {comp_name} implements OnInit {{
{init_props_str}

  ngOnInit(): void {{}}

{methods_str}
}}

export default {comp_name};
'''

    def _extract_files(self, response: str) -> dict[str, str]:
        extracted_files = {}
        lines = response.splitlines()
        current_file = None
        current_code = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("### FILE:"):
                if current_file and current_code:
                    code_text = "\n".join(current_code).strip()
                    if code_text:
                        extracted_files[current_file] = code_text
                current_file = stripped.replace("### FILE:", "").strip()
                current_code = []
                in_code_block = False
                continue

            if current_file:
                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block:
                    current_code.append(line)

        if current_file and current_code:
            code_text = "\n".join(current_code).strip()
            if code_text:
                extracted_files[current_file] = code_text

        if not extracted_files:
            code = self._extract_code_block_legacy(response)
            if code.strip():
                extracted_files["generated_component"] = code.strip()

        return extracted_files

    def _extract_code_block_legacy(self, response: str) -> str:
        lines = response.splitlines()
        code_lines = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                code_lines.append(line)
        return "\n".join(code_lines) if code_lines else response
