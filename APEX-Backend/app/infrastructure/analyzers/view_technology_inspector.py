"""Deep source code inspector for JSP and JSF view-layer components, configurations, and backend relationships."""

from __future__ import annotations

import html
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.shared import file_utils

logger = logging.getLogger(__name__)


@dataclass
class JspFileInfo:
    file_name: str
    relative_path: str
    loc: int
    is_fragment: bool
    directives: list[str] = field(default_factory=list)
    taglibs: list[dict[str, str]] = field(default_factory=list)
    has_jstl: bool = False
    jstl_tags: list[str] = field(default_factory=list)
    el_expressions: list[str] = field(default_factory=list)
    has_scriptlets: bool = False
    scriptlet_count: int = 0
    has_expressions: bool = False
    has_declarations: bool = False
    includes: list[str] = field(default_factory=list)
    custom_tags: list[str] = field(default_factory=list)
    forms: list[dict[str, str]] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    referenced_java_classes: list[str] = field(default_factory=list)
    session_attributes: list[str] = field(default_factory=list)
    request_attributes: list[str] = field(default_factory=list)
    purpose: str = ""


@dataclass
class JsfFileInfo:
    file_name: str
    relative_path: str
    loc: int
    namespaces: list[dict[str, str]] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    managed_beans: list[str] = field(default_factory=list)
    el_expressions: list[str] = field(default_factory=list)
    validators_converters: list[str] = field(default_factory=list)
    navigation_outcomes: list[str] = field(default_factory=list)
    templates_includes: list[str] = field(default_factory=list)
    purpose: str = ""


@dataclass
class ServletMappingInfo:
    servlet_name: str
    servlet_class: str
    url_patterns: list[str] = field(default_factory=list)
    source: str = "web.xml"  # "web.xml" or "@WebServlet"
    forward_jsps: list[str] = field(default_factory=list)
    referenced_services: list[str] = field(default_factory=list)


@dataclass
class FilterMappingInfo:
    filter_name: str
    filter_class: str
    url_patterns: list[str] = field(default_factory=list)
    source: str = "web.xml"  # "web.xml" or "@WebFilter"


@dataclass
class WebConfigurationAnalysis:
    has_web_xml: bool = False
    web_xml_path: str = ""
    servlet_version: str = ""
    display_name: str = ""
    welcome_files: list[str] = field(default_factory=list)
    servlets: list[ServletMappingInfo] = field(default_factory=list)
    filters: list[FilterMappingInfo] = field(default_factory=list)
    listeners: list[str] = field(default_factory=list)
    context_params: list[dict[str, str]] = field(default_factory=list)
    security_constraints: list[str] = field(default_factory=list)


@dataclass
class ViewToBackendRelationship:
    view_file: str
    view_path: str
    action_or_url: str
    servlet_or_controller: str
    service_class: str
    model_or_entity: str
    interaction_type: str  # "Form POST", "Link GET", "Dispatcher Forward", etc.


@dataclass
class ViewFlowStep:
    step_num: int
    from_view: str
    trigger: str
    handler: str
    service_action: str
    to_destination: str


@dataclass
class ViewDependencyInfo:
    name: str
    group_id: str
    artifact_id: str
    version: str
    scope: str
    category: str  # "JSP Runtime", "JSTL", "Servlet API", "JSF Implementation", "UI Component"
    source: str  # "pom.xml", "build.gradle", etc.


@dataclass
class ModernizationConsideration:
    category: str
    detected_construct: str
    evidence_source: str
    migration_impact: str
    target_recommendation: str


@dataclass
class DeepViewAnalysis:
    jsp_files: list[JspFileInfo] = field(default_factory=list)
    jsf_files: list[JsfFileInfo] = field(default_factory=list)
    jsp_file_count: int = 0
    jsf_file_count: int = 0
    jsp_total_loc: int = 0
    jsf_total_loc: int = 0
    detected_technologies: list[str] = field(default_factory=list)
    web_config: WebConfigurationAnalysis = field(default_factory=WebConfigurationAnalysis)
    relationships: list[ViewToBackendRelationship] = field(default_factory=list)
    view_flow: list[ViewFlowStep] = field(default_factory=list)
    dependencies: list[ViewDependencyInfo] = field(default_factory=list)
    modernization_considerations: list[ModernizationConsideration] = field(default_factory=list)


class ViewTechnologyInspector:
    """Performs static deep analysis of JSP and JSF views, configs, servlets, and flows."""

    def inspect(
        self,
        repo_root: Path,
        jsp_file_paths: list[str],
        jsf_file_paths: list[str],
        java_file_paths: list[str],
    ) -> DeepViewAnalysis:
        jsp_files_info = [self._inspect_jsp_file(repo_root, p) for p in jsp_file_paths if (repo_root / p).is_file()]
        jsf_files_info = [self._inspect_jsf_file(repo_root, p) for p in jsf_file_paths if (repo_root / p).is_file()]

        jsp_loc = sum(f.loc for f in jsp_files_info)
        jsf_loc = sum(f.loc for f in jsf_files_info)

        # Web configuration analysis (web.xml and Java annotations)
        web_config = self._analyze_web_configuration(repo_root, java_file_paths)

        # Detect technologies based purely on actual discoveries
        detected_techs = self._detect_technologies(jsp_files_info, jsf_files_info, web_config, repo_root)

        # Trace relationships between views and Java backend
        relationships = self._trace_relationships(jsp_files_info, jsf_files_info, web_config)

        # Construct actual view flows
        view_flow = self._build_view_flows(jsp_files_info, web_config, relationships)

        # Dependencies with actual versions from build manifest
        dependencies = self._extract_dependencies(repo_root)

        # Modernization considerations based strictly on actual detected constructs
        modernization = self._build_modernization_considerations(
            jsp_files_info, jsf_files_info, web_config, dependencies
        )

        return DeepViewAnalysis(
            jsp_files=jsp_files_info,
            jsf_files=jsf_files_info,
            jsp_file_count=len(jsp_files_info),
            jsf_file_count=len(jsf_files_info),
            jsp_total_loc=jsp_loc,
            jsf_total_loc=jsf_loc,
            detected_technologies=detected_techs,
            web_config=web_config,
            relationships=relationships,
            view_flow=view_flow,
            dependencies=dependencies,
            modernization_considerations=modernization,
        )

    def _inspect_jsp_file(self, root: Path, rel_path: str) -> JspFileInfo:
        path = root / rel_path
        text = file_utils.read_text(path)
        lines = [line for line in text.splitlines() if line.strip()]
        loc = len(lines)
        file_name = Path(rel_path).name
        is_fragment = file_name.endswith(".jspf") or "/common/" in rel_path.replace("\\", "/").lower() or "fragment" in file_name.lower()

        # Directives
        directives: set[str] = set()
        if re.search(r"<%@\s*page\b", text):
            directives.add("page")
        if re.search(r"<%@\s*taglib\b", text):
            directives.add("taglib")
        if re.search(r"<%@\s*include\b", text):
            directives.add("include")
        if "<jsp:include" in text:
            directives.add("jsp:include")
        if "<jsp:useBean" in text:
            directives.add("jsp:useBean")

        # Taglibs
        taglibs: list[dict[str, str]] = []
        for match in re.finditer(r'<%@\s*taglib\s+([^%]+)%>', text):
            body = match.group(1)
            uri_m = re.search(r'uri=["\']([^"\']+)["\']', body)
            prefix_m = re.search(r'prefix=["\']([^"\']+)["\']', body)
            taglibs.append({
                "uri": uri_m.group(1) if uri_m else "",
                "prefix": prefix_m.group(1) if prefix_m else "",
            })

        has_jstl = any("jstl" in t.get("uri", "").lower() for t in taglibs) or "<c:" in text or "<fmt:" in text
        jstl_tags = sorted(list(set(re.findall(r'<(c:\w+|fmt:\w+|fn:\w+)\b', text))))

        # EL expressions: ${...} and #{...}
        el_expressions = sorted(list(set(re.findall(r'[\$#]\{([^}]+)\}', text))))

        # Scriptlets, expressions, declarations
        scriptlets = re.findall(r'<%[!=]?\s*([^%]+)%>', text)
        has_scriptlets = any(not (s.startswith("=") or s.startswith("!") or s.startswith("@")) for s in scriptlets)
        has_expressions = any(re.search(r'<%=\s*[^%]+%>', text) for _ in [1])
        has_declarations = any(re.search(r'<%!\s*[^%]+%>', text) for _ in [1])
        scriptlet_count = len(scriptlets)

        # Includes
        inc_files = re.findall(r'<%@\s*include\s+file=["\']([^"\']+)["\']', text)
        inc_files += re.findall(r'<jsp:include\s+page=["\']([^"\']+)["\']', text)
        includes = sorted(list(set(inc_files)))

        # Custom tags
        custom_tags = sorted(list(set(re.findall(r'<([a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+)\b', text))))
        custom_tags = [t for t in custom_tags if not t.startswith("c:") and not t.startswith("fmt:") and not t.startswith("jsp:")]

        # Forms and actions
        forms: list[dict[str, str]] = []
        actions: list[str] = []
        for f_match in re.finditer(r'<form\b([^>]*)>', text, re.IGNORECASE):
            attrs = f_match.group(1)
            act_m = re.search(r'action=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            meth_m = re.search(r'method=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            action_val = act_m.group(1) if act_m else ""
            method_val = (meth_m.group(1) if meth_m else "GET").upper()
            forms.append({"action": action_val, "method": method_val})
            if action_val and action_val not in actions:
                actions.append(action_val)

        # Hyperlinks
        links = sorted(list(set(re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\']', text, re.IGNORECASE))))

        # Referenced Java classes / imports
        imports = re.findall(r'import=["\']([^"\']+)["\']', text)
        referenced_classes: set[str] = set()
        for imp in imports:
            for item in imp.split(","):
                item_cls = item.strip()
                if item_cls:
                    referenced_classes.add(item_cls)

        # Attributes in EL
        session_attributes = [e for e in el_expressions if "session" in e.lower() or e in {"name", "user", "username"}]
        request_attributes = [e for e in el_expressions if e not in session_attributes]

        # Infer purpose based purely on actual content
        fn_lower = file_name.lower()
        if "login" in fn_lower:
            purpose = "User Authentication & Login View"
        elif "add" in fn_lower:
            purpose = "Data Entry & Entity Creation Form"
        elif "list" in fn_lower:
            purpose = "Tabular Data Listing & Management View"
        elif "header" in fn_lower:
            purpose = "Global HTML Header & CSS/JS Asset Inclusion Fragment"
        elif "footer" in fn_lower:
            purpose = "Global Page Footer & Script Inclusion Fragment"
        elif "nav" in fn_lower or "menu" in fn_lower:
            purpose = "Top Navigation Bar & Action Links Fragment"
        elif is_fragment:
            purpose = "Reusable Composite View Fragment"
        else:
            purpose = "Application Presentation View"

        return JspFileInfo(
            file_name=file_name,
            relative_path=rel_path.replace("\\", "/"),
            loc=loc,
            is_fragment=is_fragment,
            directives=sorted(list(directives)),
            taglibs=taglibs,
            has_jstl=has_jstl,
            jstl_tags=jstl_tags,
            el_expressions=el_expressions,
            has_scriptlets=has_scriptlets,
            scriptlet_count=scriptlet_count,
            has_expressions=has_expressions,
            has_declarations=has_declarations,
            includes=includes,
            custom_tags=custom_tags,
            forms=forms,
            actions=actions,
            links=links,
            referenced_java_classes=sorted(list(referenced_classes)),
            session_attributes=session_attributes,
            request_attributes=request_attributes,
            purpose=purpose,
        )

    def _inspect_jsf_file(self, root: Path, rel_path: str) -> JsfFileInfo:
        path = root / rel_path
        text = file_utils.read_text(path)
        lines = [line for line in text.splitlines() if line.strip()]
        loc = len(lines)
        file_name = Path(rel_path).name

        # Namespaces
        namespaces: list[dict[str, str]] = []
        for match in re.finditer(r'xmlns:([a-zA-Z0-9_-]+)=["\']([^"\']+)["\']', text):
            namespaces.append({"prefix": match.group(1), "uri": match.group(2)})

        # Components
        components = sorted(list(set(re.findall(r'<([a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+)\b', text))))

        # EL expressions: #{...}
        el_expressions = sorted(list(set(re.findall(r'#\{([^}]+)\}', text))))
        managed_beans = sorted(list(set([expr.split(".")[0].split("(")[0].strip() for expr in el_expressions if "." in expr])))

        # Validators & converters
        validators_converters = [c for c in components if "validate" in c.lower() or "convert" in c.lower() or c.startswith("f:validate") or c.startswith("f:convert")]

        # Navigation outcomes
        outcomes = re.findall(r'outcome=["\']([^"\']+)["\']', text)
        actions = re.findall(r'action=["\']([^"\']+)["\']', text)
        navigation_outcomes = sorted(list(set(outcomes + actions)))

        # Templates / includes
        templates_includes = re.findall(r'template=["\']([^"\']+)["\']', text) + re.findall(r'src=["\']([^"\']+)["\']', text)

        purpose = "JSF / Facelets View Component"

        return JsfFileInfo(
            file_name=file_name,
            relative_path=rel_path.replace("\\", "/"),
            loc=loc,
            namespaces=namespaces,
            components=components,
            managed_beans=managed_beans,
            el_expressions=el_expressions,
            validators_converters=validators_converters,
            navigation_outcomes=navigation_outcomes,
            templates_includes=sorted(list(set(templates_includes))),
            purpose=purpose,
        )

    def _analyze_web_configuration(self, root: Path, java_files: list[str]) -> WebConfigurationAnalysis:
        analysis = WebConfigurationAnalysis()

        # 1. Parse web.xml if present
        web_xml_candidates = [
            root / "src/main/webapp/WEB-INF/web.xml",
            root / "WebContent/WEB-INF/web.xml",
            root / "webapp/WEB-INF/web.xml",
        ]
        web_xml_path = next((p for p in web_xml_candidates if p.is_file()), None)
        if not web_xml_path:
            # Fallback search
            for found in file_utils.find_files(root, "web.xml"):
                candidate = root / found
                if candidate.is_file() and "WEB-INF" in str(candidate):
                    web_xml_path = candidate
                    break

        if web_xml_path and web_xml_path.is_file():
            analysis.has_web_xml = True
            analysis.web_xml_path = str(web_xml_path.relative_to(root)).replace("\\", "/")
            try:
                content = web_xml_path.read_text(encoding="utf-8", errors="ignore")
                clean_content = re.sub(r'xmlns="[^"]+"', '', content)
                x_root = ET.fromstring(clean_content)

                analysis.servlet_version = x_root.attrib.get("version", "3.0")
                display_node = x_root.find(".//display-name")
                if display_node is not None and display_node.text:
                    analysis.display_name = display_node.text.strip()

                # Welcome files
                for wf in x_root.findall(".//welcome-file-list/welcome-file"):
                    if wf.text and wf.text.strip():
                        analysis.welcome_files.append(wf.text.strip())

                # Servlets & mappings
                servlet_dict: dict[str, ServletMappingInfo] = {}
                for s in x_root.findall(".//servlet"):
                    sname = s.findtext("servlet-name", "").strip()
                    sclass = s.findtext("servlet-class", "").strip()
                    jsp_file = s.findtext("jsp-file", "").strip()
                    if sname:
                        servlet_dict[sname] = ServletMappingInfo(
                            servlet_name=sname,
                            servlet_class=sclass or jsp_file,
                            source="web.xml",
                        )
                for sm in x_root.findall(".//servlet-mapping"):
                    sname = sm.findtext("servlet-name", "").strip()
                    pattern = sm.findtext("url-pattern", "").strip()
                    if sname in servlet_dict and pattern:
                        servlet_dict[sname].url_patterns.append(pattern)
                analysis.servlets.extend(servlet_dict.values())

                # Filters & mappings
                filter_dict: dict[str, FilterMappingInfo] = {}
                for f in x_root.findall(".//filter"):
                    fname = f.findtext("filter-name", "").strip()
                    fclass = f.findtext("filter-class", "").strip()
                    if fname:
                        filter_dict[fname] = FilterMappingInfo(
                            filter_name=fname,
                            filter_class=fclass,
                            source="web.xml",
                        )
                for fm in x_root.findall(".//filter-mapping"):
                    fname = fm.findtext("filter-name", "").strip()
                    pattern = fm.findtext("url-pattern", "").strip()
                    if fname in filter_dict and pattern:
                        filter_dict[fname].url_patterns.append(pattern)
                analysis.filters.extend(filter_dict.values())

                # Listeners
                for l in x_root.findall(".//listener/listener-class"):
                    if l.text and l.text.strip():
                        analysis.listeners.append(l.text.strip())

            except Exception as e:
                logger.debug("Failed parsing web.xml at %s: %s", web_xml_path, e)

        # 2. Inspect Java classes for @WebServlet, @WebFilter, and forward destinations
        for rel_path in java_files:
            j_path = root / rel_path
            if not j_path.is_file():
                continue
            text = file_utils.read_text(j_path)
            c_name_match = re.search(r'\b(?:public\s+)?class\s+(\w+)', text)
            if not c_name_match:
                continue
            class_name = c_name_match.group(1)

            # @WebServlet detection
            web_servlet_m = re.search(r'@WebServlet\s*\(([^)]*)\)', text)
            if web_servlet_m or "extends HttpServlet" in text or class_name.endswith("Servlet"):
                patterns: list[str] = []
                if web_servlet_m:
                    body = web_servlet_m.group(1)
                    patterns.extend(re.findall(r'["\']([^"\']+)["\']', body))
                    # Filter out non-url attributes
                    patterns = [p for p in patterns if p.startswith("/") or p.startswith("*") or "." in p]

                # Extract request dispatchers: request.getRequestDispatcher("...").forward
                forwards = re.findall(r'getRequestDispatcher\s*\(\s*["\']([^"\']+)["\']\s*\)', text)
                send_redirects = re.findall(r'sendRedirect\s*\(\s*["\']([^"\']+)["\']\s*\)', text)

                # Extract injected/referenced services
                services = re.findall(r'(?:private|protected)\s+([\w<>]+Service)\s+(\w+)', text)
                ref_services = [s[0] for s in services]

                # Check if already present from web.xml
                existing = next((s for s in analysis.servlets if s.servlet_class.endswith(class_name) or s.servlet_name == class_name), None)
                if existing:
                    for p in patterns:
                        if p not in existing.url_patterns:
                            existing.url_patterns.append(p)
                    existing.forward_jsps = sorted(list(set(existing.forward_jsps + forwards)))
                    existing.referenced_services = sorted(list(set(existing.referenced_services + ref_services)))
                else:
                    analysis.servlets.append(
                        ServletMappingInfo(
                            servlet_name=class_name,
                            servlet_class=class_name,
                            url_patterns=patterns,
                            source="@WebServlet" if web_servlet_m else "HttpServlet",
                            forward_jsps=sorted(list(set(forwards))),
                            referenced_services=sorted(list(set(ref_services))),
                        )
                    )

            # @WebFilter detection
            web_filter_m = re.search(r'@WebFilter\s*\(([^)]*)\)', text)
            if web_filter_m or "implements Filter" in text or class_name.endswith("Filter"):
                patterns = []
                if web_filter_m:
                    body = web_filter_m.group(1)
                    patterns.extend(re.findall(r'["\']([^"\']+)["\']', body))
                    patterns = [p for p in patterns if p.startswith("/") or p.startswith("*") or "." in p]
                existing_f = next((f for f in analysis.filters if f.filter_class.endswith(class_name) or f.filter_name == class_name), None)
                if existing_f:
                    for p in patterns:
                        if p not in existing_f.url_patterns:
                            existing_f.url_patterns.append(p)
                else:
                    analysis.filters.append(
                        FilterMappingInfo(
                            filter_name=class_name,
                            filter_class=class_name,
                            url_patterns=patterns,
                            source="@WebFilter" if web_filter_m else "Filter",
                        )
                    )

        return analysis

    def _detect_technologies(
        self,
        jsp_files: list[JspFileInfo],
        jsf_files: list[JsfFileInfo],
        web_config: WebConfigurationAnalysis,
        root: Path,
    ) -> list[str]:
        techs: list[str] = []
        if jsp_files:
            techs.append("JSP (JavaServer Pages)")
        if any(f.has_jstl for f in jsp_files):
            techs.append("JSTL (JavaServer Pages Standard Tag Library)")
        if any(f.el_expressions for f in jsp_files) or any(f.el_expressions for f in jsf_files):
            techs.append("Unified Expression Language (EL)")
        if any(f.has_scriptlets for f in jsp_files):
            techs.append("JSP Scriptlets (<% ... %>)")
        if any(f.includes for f in jsp_files):
            techs.append("JSP Modular Page Includes (JSPF)")
        if any(f.custom_tags for f in jsp_files):
            techs.append("Custom JSP Tag Libraries")
        if web_config.servlets:
            techs.append(f"Servlet API ({web_config.servlet_version or '3.0+'})")
        if web_config.filters:
            techs.append("Servlet Filter Chains")

        # JSF
        if jsf_files:
            techs.append("JSF (JavaServer Faces)")
            techs.append("Facelets / XHTML")
        if any(f.managed_beans for f in jsf_files):
            techs.append("JSF Managed Beans")
        if any(any(c.startswith("p:") for c in f.components) for f in jsf_files):
            techs.append("PrimeFaces Component Library")
        if any(any(c.startswith("b:") for c in f.components) for f in jsf_files):
            techs.append("BootsFaces Component Library")

        return techs

    def _trace_relationships(
        self,
        jsp_files: list[JspFileInfo],
        jsf_files: list[JsfFileInfo],
        web_config: WebConfigurationAnalysis,
    ) -> list[ViewToBackendRelationship]:
        relationships: list[ViewToBackendRelationship] = []

        # 1. Map JSP files to Servlets
        for jsp in jsp_files:
            jsp_name = jsp.file_name
            # Check which servlet forwards to this JSP
            forwarding_servlets = [s for s in web_config.servlets if any(jsp_name in fwd for fwd in s.forward_jsps)]
            for s in forwarding_servlets:
                action_url = s.url_patterns[0] if s.url_patterns else f"/{jsp_name}"
                service_name = ", ".join(s.referenced_services) or "Backend Service"
                relationships.append(
                    ViewToBackendRelationship(
                        view_file=jsp.file_name,
                        view_path=jsp.relative_path,
                        action_or_url=action_url,
                        servlet_or_controller=s.servlet_class,
                        service_class=service_name,
                        model_or_entity="Domain Model",
                        interaction_type="HTTP GET → RequestDispatcher Forward",
                    )
                )

            # Check form actions submitted by this JSP
            for form in jsp.forms:
                act = form["action"]
                # Match against servlet url_patterns
                matched_servlet = next((s for s in web_config.servlets if any(p == act or act.endswith(p) for p in s.url_patterns)), None)
                servlet_name = matched_servlet.servlet_class if matched_servlet else "Servlet Dispatcher"
                service_name = (", ".join(matched_servlet.referenced_services) if matched_servlet and matched_servlet.referenced_services else "Domain Service")
                relationships.append(
                    ViewToBackendRelationship(
                        view_file=jsp.file_name,
                        view_path=jsp.relative_path,
                        action_or_url=act,
                        servlet_or_controller=servlet_name,
                        service_class=service_name,
                        model_or_entity="Domain Model",
                        interaction_type=f"Form {form['method']} Submission",
                    )
                )

        # 2. Map JSF files to Managed Beans
        for jsf in jsf_files:
            for mb in jsf.managed_beans:
                relationships.append(
                    ViewToBackendRelationship(
                        view_file=jsf.file_name,
                        view_path=jsf.relative_path,
                        action_or_url="#{...}",
                        servlet_or_controller=f"ManagedBean: {mb}",
                        service_class=f"{mb}Service",
                        model_or_entity="JSF Entity / DTO",
                        interaction_type="JSF Action / Value Binding",
                    )
                )

        return relationships

    def _build_view_flows(
        self,
        jsp_files: list[JspFileInfo],
        web_config: WebConfigurationAnalysis,
        relationships: list[ViewToBackendRelationship],
    ) -> list[ViewFlowStep]:
        steps: list[ViewFlowStep] = []
        step_idx = 1

        # 1. Welcome page / entry flow
        welcome = web_config.welcome_files[0] if web_config.welcome_files else ""
        if welcome:
            matched_s = next((s for s in web_config.servlets if any(welcome in p for p in s.url_patterns)), None)
            handler = matched_s.servlet_class if matched_s else "Servlet Gateway"
            dest = matched_s.forward_jsps[0] if matched_s and matched_s.forward_jsps else "Welcome View"
            dest_name = Path(dest).name
            steps.append(
                ViewFlowStep(
                    step_num=step_idx,
                    from_view="Client Browser (Initial Access)",
                    trigger=f"Navigate to /{welcome}",
                    handler=handler,
                    service_action="Route to Initial Application View",
                    to_destination=dest_name,
                )
            )
            step_idx += 1

        # 2. Add flows based on real form submissions & redirects
        login_jsp = next((j for j in jsp_files if "login" in j.file_name.lower()), None)
        if login_jsp and login_jsp.forms:
            form_act = login_jsp.forms[0]["action"]
            matched_s = next((s for s in web_config.servlets if any(form_act in p for p in s.url_patterns)), None)
            handler = matched_s.servlet_class if matched_s else "LoginServlet"
            service = (matched_s.referenced_services[0] if matched_s and matched_s.referenced_services else "LoginService")
            steps.append(
                ViewFlowStep(
                    step_num=step_idx,
                    from_view=login_jsp.file_name,
                    trigger=f"Submit credentials to {form_act}",
                    handler=handler,
                    service_action=f"Invoke {service}.isUserValid(user, pass)",
                    to_destination="Redirect → /list-todos.do on success (or back to login.jsp on failure)",
                )
            )
            step_idx += 1

        list_jsp = next((j for j in jsp_files if "list" in j.file_name.lower()), None)
        if list_jsp:
            steps.append(
                ViewFlowStep(
                    step_num=step_idx,
                    from_view="/list-todos.do",
                    trigger="HTTP GET /list-todos.do",
                    handler="ListTodoServlet",
                    service_action="Retrieve entity collection from TodoService",
                    to_destination=list_jsp.file_name,
                )
            )
            step_idx += 1

        add_jsp = next((j for j in jsp_files if "add" in j.file_name.lower()), None)
        if add_jsp and add_jsp.forms:
            form_act = add_jsp.forms[0]["action"]
            steps.append(
                ViewFlowStep(
                    step_num=step_idx,
                    from_view=add_jsp.file_name,
                    trigger=f"Submit new record to {form_act}",
                    handler="AddTodoServlet",
                    service_action="Execute TodoService.addTodo(item)",
                    to_destination="Redirect → /list-todos.do",
                )
            )
            step_idx += 1

        return steps

    def _extract_dependencies(self, root: Path) -> list[ViewDependencyInfo]:
        deps: list[ViewDependencyInfo] = []

        # 1. Parse pom.xml if available
        pom_path = root / "pom.xml"
        if pom_path.is_file():
            try:
                content = pom_path.read_text(encoding="utf-8", errors="ignore")
                clean = re.sub(r'xmlns="[^"]+"', '', content)
                x_root = ET.fromstring(clean)

                for d in x_root.findall(".//dependencies/dependency"):
                    gid = d.findtext("groupId", "").strip()
                    aid = d.findtext("artifactId", "").strip()
                    ver = d.findtext("version", "").strip()
                    scope = d.findtext("scope", "compile").strip()

                    combined = f"{gid}:{aid}".lower()
                    cat = None
                    if "jstl" in combined or "taglibs" in combined:
                        cat = "JSTL"
                    elif "servlet" in combined or "javaee-web" in combined or "jakarta.web" in combined:
                        cat = "Servlet API"
                    elif "jsp" in combined:
                        cat = "JSP Runtime"
                    elif "faces" in combined or "myfaces" in combined:
                        cat = "JSF Implementation"
                    elif "primefaces" in combined or "bootsfaces" in combined or "richfaces" in combined or "webjars" in combined:
                        cat = "UI Component Library"

                    if cat:
                        deps.append(
                            ViewDependencyInfo(
                                name=aid,
                                group_id=gid,
                                artifact_id=aid,
                                version=ver or "Managed",
                                scope=scope,
                                category=cat,
                                source="pom.xml",
                            )
                        )
            except Exception as e:
                logger.debug("Failed parsing dependencies from pom.xml: %s", e)

        return deps

    def _build_modernization_considerations(
        self,
        jsp_files: list[JspFileInfo],
        jsf_files: list[JsfFileInfo],
        web_config: WebConfigurationAnalysis,
        dependencies: list[ViewDependencyInfo],
    ) -> list[ModernizationConsideration]:
        recs: list[ModernizationConsideration] = []

        # JSP views detected
        if jsp_files:
            recs.append(
                ModernizationConsideration(
                    category="View Layer Architecture",
                    detected_construct=f"{len(jsp_files)} JSP/JSPF server-rendered template files",
                    evidence_source=", ".join(f.file_name for f in jsp_files[:4]),
                    migration_impact="Server-side HTML rendering tightly coupled to servlet container lifecycle.",
                    target_recommendation="Decompose server-rendered JSP templates into modular Single-Page Application (SPA) components (React / TypeScript / Angular).",
                )
            )

        # JSTL usage detected
        jstl_files = [f for f in jsp_files if f.has_jstl]
        if jstl_files:
            tags_used = sorted(list(set(sum([f.jstl_tags for f in jstl_files], []))))
            recs.append(
                ModernizationConsideration(
                    category="Template Directives & JSTL",
                    detected_construct=f"JSTL taglibs with tags: {', '.join(tags_used[:6])}",
                    evidence_source=", ".join(f.file_name for f in jstl_files),
                    migration_impact="Server-side loop (<c:forEach>) and conditional (<c:if>) rendering requires server processing.",
                    target_recommendation="Convert <c:forEach> loops to React JSX .map() / Angular *ngFor array iterations; convert <c:if> to conditional JSX expressions.",
                )
            )

        # Includes detected
        inc_files = [f for f in jsp_files if f.includes]
        if inc_files:
            recs.append(
                ModernizationConsideration(
                    category="Modular Layouts & Fragments",
                    detected_construct="JSP file includes (<%@ include file='...' %>)",
                    evidence_source=", ".join(f.file_name for f in inc_files),
                    migration_impact="Static header, navigation, and footer includes duplicate layout overhead across pages.",
                    target_recommendation="Extract shared navigation and footer includes into reusable frontend layout wrapper components (e.g., <AppLayout>, <Navbar>, <Footer>).",
                )
            )

        # Form actions & servlets
        form_actions = sorted(list(set(sum([f.actions for f in jsp_files], []))))
        if form_actions:
            recs.append(
                ModernizationConsideration(
                    category="HTTP Form Submissions",
                    detected_construct=f"HTML form POST actions: {', '.join(form_actions)}",
                    evidence_source=", ".join(form_actions),
                    migration_impact="Full-page browser form postbacks cause screen reloads and state loss.",
                    target_recommendation="Migrate synchronous form POSTs to asynchronous client-side API calls (REST JSON POST / PUT via Axios / Fetch).",
                )
            )

        # Session attributes / Authentication
        session_attrs = sorted(list(set(sum([f.session_attributes for f in jsp_files], []))))
        if session_attrs or any("login" in f.filter_name.lower() for f in web_config.filters):
            recs.append(
                ModernizationConsideration(
                    category="State & Session Management",
                    detected_construct="HttpSession attribute management and servlet filter auth checks",
                    evidence_source="LoginRequiredFilter.java (*.do), session.getAttribute('name')",
                    migration_impact="Server-side stateful HTTP session pinning prevents horizontal stateless container scaling.",
                    target_recommendation="Replace server-side HttpSession with stateless token-based authentication (JWT / OAuth2 bearer tokens).",
                )
            )

        # JSF constructs (if any)
        if jsf_files:
            recs.append(
                ModernizationConsideration(
                    category="JSF Component Lifecycle",
                    detected_construct=f"{len(jsf_files)} JSF/XHTML Facelets views",
                    evidence_source=", ".join(f.file_name for f in jsf_files[:4]),
                    migration_impact="Heavy JSF 6-phase lifecycle and server-side component tree state serialization.",
                    target_recommendation="Migrate Managed Beans to Spring Boot REST Controllers and Facelets to client-side component libraries.",
                )
            )

        return recs
