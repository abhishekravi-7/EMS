"""Collect non-Spring web, documentation, test, and Gradle evidence for BRDs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from app.shared import file_utils


@dataclass(frozen=True)
class StructuredEvidence:
    claim_type: str
    repository_path: str
    line_range: tuple[int, int]
    operation: str
    subject: str
    related_findings: list[str] = field(default_factory=list)
    confidence: str = "Observed in code — needs business confirmation"
    uncertainty: str = ""


@dataclass(frozen=True)
class RepositoryBrdEvidence:
    repository_kind: str = "APPLICATION_REPOSITORY"
    documentation: list[dict[str, Any]] = field(default_factory=list)
    web_routes: list[dict[str, Any]] = field(default_factory=list)
    gradle_builds: list[dict[str, Any]] = field(default_factory=list)
    test_evidence: list[dict[str, Any]] = field(default_factory=list)
    workflow_edges: list[dict[str, Any]] = field(default_factory=list)
    structured_evidence: list[StructuredEvidence] = field(default_factory=list)


class _WebMarkupParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[dict[str, Any]] = []
        self.fields: list[str] = []
        self._form: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        line = self.getpos()[0]
        if tag.lower() == "form":
            self._form = {
                "action": values.get("action", ""),
                "method": values.get("method", "").upper() or None,
                "line_start": line,
                "fields": [],
            }
            self.forms.append(self._form)
        elif tag.lower() in {"input", "select", "textarea"} and values.get("name"):
            name = values["name"]
            self.fields.append(name)
            if self._form is not None:
                self._form["fields"].append(name)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "form":
            self._form = None


class BrdRepositoryEvidenceScanner:
    """Extract evidence records without conflating docs, UI routes, APIs, or tests."""

    _DOC_SUFFIXES = (".md", ".adoc", ".asciidoc", ".txt")
    _DOC_TERMS = re.compile(
        r"\b(learn|guide|tutorial|application|build|enter|input|convert|conversion|return|result|display|deploy|module|start|finish|test|user|height|centimeter|feet|inches|workflow|form|archive|liberty)\b",
        re.I,
    )

    def scan(self, root: Path, files: list[str], application_type: str) -> RepositoryBrdEvidence:
        documentation = self._documentation(root, files)
        gradle_builds = self._gradle_builds(root, files)
        web_routes, workflow_edges = self._web_evidence(root, files, gradle_builds)
        test_evidence = self._tests(root, files)
        doc_text = " ".join(str(item["text"]) for item in documentation)
        test_text = " ".join(str(item["text"]) for item in test_evidence)

        is_test_automation = any(
            re.search(r"\b(playwright|selenium|cypress|webdriver|pagefactory|testbase)\b", f"{file_path} {test_text}", re.I)
            for file_path in files
        ) and not any(f.endswith(".java") and "controller" in f.lower() for f in files)

        is_library = not any(f.endswith(".java") and ("controller" in f.lower() or "rest" in f.lower()) for f in files) and not is_test_automation
        tutorial_signals = len(gradle_builds) > 1 and bool(
            re.search(r"\b(guide|tutorial|learn how|getting started)\b", doc_text, re.I)
        )

        if is_test_automation:
            repository_kind = "TEST_AUTOMATION_FRAMEWORK"
        elif is_library:
            repository_kind = "LIBRARY_REPOSITORY"
        elif tutorial_signals:
            repository_kind = "BUILD_TUTORIAL"
        else:
            repository_kind = "APPLICATION_REPOSITORY"

        structured_evidence = []
        for doc in documentation:
            structured_evidence.append(StructuredEvidence(
                claim_type="DOCUMENTATION_CLAIM",
                repository_path=doc["file"],
                line_range=(doc["line_start"], doc["line_end"]),
                operation="Document statement",
                subject="Documentation",
                confidence="Documentation claim; needs business confirmation",
            ))
        for test in test_evidence:
            structured_evidence.append(StructuredEvidence(
                claim_type="TEST_ASSERTION",
                repository_path=test["file"],
                line_range=(test["line_start"], test["line_end"]),
                operation="Test assertion",
                subject="Test suite",
                confidence="Test assertion exists; execution not inferred",
            ))

        return RepositoryBrdEvidence(
            repository_kind=repository_kind,
            documentation=documentation,
            web_routes=web_routes,
            gradle_builds=gradle_builds,
            test_evidence=test_evidence,
            workflow_edges=workflow_edges,
            structured_evidence=structured_evidence,
        )

    @classmethod
    def _documentation(cls, root: Path, files: list[str]) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for relative_path in files:
            path = Path(relative_path)
            if path.suffix.lower() not in cls._DOC_SUFFIXES and path.name.lower() not in {"readme", "readme.md", "readme.adoc"}:
                continue
            source = file_utils.read_text(root / relative_path)
            for line_number, raw_line in enumerate(source.splitlines(), start=1):
                text = raw_line.strip()
                if not text or text.startswith(("//", "#include::", "image::", "video::", "[source")):
                    continue
                if text.startswith(("----", "```", "....")):
                    continue
                if not cls._DOC_TERMS.search(text) and not re.match(r"^(?:#{1,6}|={1,4})\s+", text):
                    continue
                evidence.append({
                    "claim_type": "DOCUMENTATION_CLAIM",
                    "text": text[:600],
                    "file": relative_path,
                    "line_start": line_number,
                    "line_end": line_number,
                    "status": "Documentation claim — not stakeholder approval or proof of runtime behavior",
                })
                if len(evidence) >= 100:
                    return evidence
        return evidence

    @staticmethod
    def _gradle_builds(root: Path, files: list[str]) -> list[dict[str, Any]]:
        settings_files = [path for path in files if Path(path).name.lower() in {"settings.gradle", "settings.gradle.kts"}]
        builds: list[dict[str, Any]] = []
        for settings_path in settings_files:
            settings_text = file_utils.read_text(root / settings_path)
            root_dir = Path(settings_path).parent
            included = []
            for match in re.finditer(r"\binclude\s*(?:\(([^)]*)\)|([^\r\n]+))", settings_text):
                fragment = match.group(1) or match.group(2) or ""
                for project_path in re.findall(r"['\"](:[\w.\-:]+)['\"]", fragment):
                    name = project_path.lstrip(":").split(":")[-1]
                    if name and name not in included:
                        included.append(name)

            if not included:
                root_build = (root_dir / "build.gradle").as_posix()
                if root_build in files or (root_dir / "build.gradle.kts").as_posix() in files:
                    included = sorted({
                        Path(candidate).parent.name
                        for candidate in files
                        if Path(candidate).parent.parent == root_dir
                        and Path(candidate).name in {"build.gradle", "build.gradle.kts"}
                    })
            project_dirs = {name: name for name in included}
            for line in settings_text.splitlines():
                match = re.search(r"project\(['\"](:[^'\"]+)['\"]\)\.projectDir\s*=\s*['\"]([^'\"]+)", line)
                if match:
                    project_dirs[match.group(1).lstrip(":").split(":")[-1]] = match.group(2).replace("$rootDir/", "")
            modules = []
            edges = []
            for name in included:
                module_rel = (root_dir / project_dirs.get(name, name)).as_posix()
                module_build_path = next((
                    candidate for candidate in (f"{module_rel}/build.gradle", f"{module_rel}/build.gradle.kts")
                    if candidate in files
                ), None)
                module_text = file_utils.read_text(root / module_build_path) if module_build_path else ""
                plugins = sorted(set(re.findall(r"(?:apply\s+plugin\s*:\s*|id\s*\(?\s*)['\"]([\w.-]+)['\"]", module_text)))
                module_info = {
                    "name": name,
                    "path": module_rel,
                    "build_file": module_build_path,
                    "plugins": plugins,
                    "archive_configured": bool(re.search(r"archive(?:FileName|BaseName|Extension)", module_text)),
                    "source": module_build_path or settings_path,
                    "line_start": 1,
                    "line_end": max(1, len(module_text.splitlines())) if module_text else 1,
                }
                modules.append(module_info)
                if module_build_path:
                    for line_number, line in enumerate(module_text.splitlines(), start=1):
                        match = re.search(r"\b(implementation|api|deploy|compileOnly|runtimeOnly)\s+project\s*(?:\(\s*(?:path\s*:\s*)?['\"](:[^'\"]+)['\"][^)]*\)|\s*['\"](:[^'\"]+)['\"]\s*\))", line)
                        if match:
                            target_path = (match.group(2) or match.group(3) or "").lstrip(":").split(":")[-1]
                            edges.append({
                                "from": name,
                                "to": target_path,
                                "configuration": match.group(1),
                                "file": module_build_path,
                                "line_start": line_number,
                                "line_end": line_number,
                            })
            deployment_configs = []
            ear_prefix = (root_dir / "ear").as_posix().rstrip("/") + "/"
            for candidate in files:
                if not candidate.startswith(ear_prefix) or Path(candidate).name.lower() not in {"server.xml", "server.env", "containerfile"}:
                    continue
                config_text = file_utils.read_text(root / candidate)
                deployment_configs.append({
                    "file": candidate,
                    "line_start": 1,
                    "line_end": max(1, len(config_text.splitlines())),
                    "application_configured": "enterpriseApplication" in config_text,
                    "features": re.findall(r"<feature>\s*([^<]+)\s*</feature>", config_text),
                })
            builds.append({
                "variant": root_dir.as_posix() or ".",
                "settings_file": settings_path,
                "projects_declared_in_settings": bool(re.search(r"\binclude\b", settings_text)),
                "modules": modules,
                "edges": edges,
                "deployment_configs": deployment_configs,
                "line_start": 1,
                "line_end": max(1, len(settings_text.splitlines())),
            })
        return builds

    @staticmethod
    def _web_evidence(
        root: Path,
        files: list[str],
        gradle_builds: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        context_root_by_variant: dict[str, str] = {}
        for build in gradle_builds:
            for module in build["modules"]:
                if module["name"] != "ear" or not module["build_file"]:
                    continue
                text = file_utils.read_text(root / module["build_file"])
                match = re.search(r"webModule\s*\([^,]+,\s*['\"]([^'\"]+)['\"]", text)
                if match:
                    context_root_by_variant[build["variant"]] = "/" + match.group(1).strip("/")

        routes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        java_by_class: dict[str, dict[str, str]] = {}
        for relative_path in files:
            if relative_path.lower().endswith(".java"):
                variant = Path(relative_path).parts[0] if len(Path(relative_path).parts) > 1 else "."
                java_by_class.setdefault(variant, {})[Path(relative_path).stem] = relative_path

        # Android Manifest and Layout Evidence Extraction
        for relative_path in files:
            file_name = Path(relative_path).name.lower()
            lowered_path = relative_path.lower()
            if file_name in ("androidmanifest.xml", "manifest.xml"):
                try:
                    m_text = file_utils.read_text(root / relative_path)
                    for act_m in re.finditer(r"<activity\b([^>]*?)android:name=['\"]([^'\"]+)['\"]", m_text, re.I):
                        act_name = act_m.group(2).split(".")[-1]
                        line_no = m_text[:act_m.start()].count("\n") + 1
                        routes.append({
                            "route_type": "ANDROID_ACTIVITY",
                            "variant": "",
                            "path": f"activity://{act_name}",
                            "method": "UI",
                            "file": relative_path,
                            "line_start": line_no,
                            "line_end": line_no,
                            "inputs": [],
                        })
                    for perm_m in re.finditer(r"<uses-permission\b([^>]*?)android:name=['\"]([^'\"]+)['\"]", m_text, re.I):
                        perm_name = perm_m.group(2)
                        line_no = m_text[:perm_m.start()].count("\n") + 1
                        edges.append({
                            "edge_type": "ANDROID_PERMISSION",
                            "from": "App",
                            "to": perm_name,
                            "file": relative_path,
                            "line_start": line_no,
                            "line_end": line_no,
                        })
                except Exception:
                    pass

            if "res/layout" in lowered_path and lowered_path.endswith(".xml"):
                try:
                    l_text = file_utils.read_text(root / relative_path)
                    views = re.findall(r"<(Button|TextView|EditText|ImageView|CheckBox|Spinner|Switch|RecyclerView|ProgressBar)\b", l_text, re.I)
                    routes.append({
                        "route_type": "ANDROID_LAYOUT",
                        "variant": "",
                        "path": f"layout://{Path(relative_path).stem}",
                        "method": "UI",
                        "file": relative_path,
                        "line_start": 1,
                        "line_end": max(1, len(l_text.splitlines())),
                        "inputs": sorted(set(views)),
                    })
                except Exception:
                    pass

        for relative_path in files:
            lowered = relative_path.lower()
            if not (lowered.endswith(".jsp") or lowered.endswith(".html")):
                continue
            if "/webapp/" not in f"/{lowered}/":
                continue
            marker = "/webapp/"
            web_path = relative_path[relative_path.lower().index(marker) + len(marker):]
            parent = Path(relative_path).parent.as_posix()
            variant = parent.split("/", 1)[0] if parent not in {".", ""} else ""
            context_root = context_root_by_variant.get(variant, "")
            page_path = (context_root + "/" + web_path).replace("//", "/")
            if Path(web_path).name.lower() == "index.jsp":
                page_path = context_root + "/"
            parser = _WebMarkupParser()
            source = file_utils.read_text(root / relative_path)
            try:
                parser.feed(source)
            except Exception:
                pass
            routes.append({
                "route_type": "WEB_PAGE",
                "variant": variant,
                "path": page_path,
                "method": None,
                "file": relative_path,
                "line_start": 1,
                "line_end": max(1, len(source.splitlines())),
                "inputs": parser.fields,
            })
            for form in parser.forms:
                action = form["action"]
                resolved_action = (context_root + "/" + action.lstrip("/")) if action else page_path
                routes.append({
                    "route_type": "WEB_FORM",
                    "variant": variant,
                    "path": resolved_action,
                    "method": form["method"],
                    "file": relative_path,
                    "line_start": form["line_start"],
                    "line_end": form["line_start"],
                    "inputs": form["fields"],
                })
                edges.append({
                    "edge_type": "FORM_SUBMITS_TO",
                    "variant": variant,
                    "from": page_path,
                    "to": resolved_action,
                    "method": form["method"],
                    "file": relative_path,
                    "line_start": form["line_start"],
                    "line_end": form["line_start"],
                })

        return routes, edges

    @staticmethod
    def _tests(root: Path, files: list[str]) -> list[dict[str, Any]]:
        evidence = []
        for relative_path in files:
            path = Path(relative_path)
            if not any(part.lower() in {"test", "tests", "it", "integration-test", "integration-tests"} for part in path.parts):
                continue
            source = file_utils.read_text(root / relative_path)
            for line_number, line in enumerate(source.splitlines(), start=1):
                if re.search(r"@Test\b|\bassert(?:Equals|True|False|Throws|Null|NotNull|That)\s*\(", line):
                    evidence.append({
                        "file": relative_path,
                        "line_start": line_number,
                        "line_end": line_number,
                        "text": line.strip()[:300],
                        "status": "Test assertion exists; test execution not inferred",
                    })
                    if len(evidence) >= 100:
                        return evidence
        return evidence
