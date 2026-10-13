"""Extracts declared dependencies from Maven or Gradle build files and frontend package manifests."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element  # nosec B405 - type annotation only; callers parse via defusedxml
from defusedxml.ElementTree import fromstring

from app.shared.command_runner import resolve_executable, run_command

logger = logging.getLogger(__name__)

_GRADLE_CONFIGS = (
    "implementation",
    "api",
    "compileOnly",
    "compileOnlyApi",
    "runtimeOnly",
    "developmentOnly",
    "annotationProcessor",
    "compile",
    "runtime",
    "testImplementation",
    "testCompileOnly",
    "testRuntimeOnly",
    "testCompile",
    "testRuntime",
    "testAnnotationProcessor",
    "compileClasspath",
    "runtimeClasspath",
    "kapt",
    "ksp",
)

_IGNORED_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "target",
    ".gradle",
    ".mvn",
    ".idea",
    ".vscode",
    "coverage",
    ".next",
    ".nuxt",
    "bin",
    "obj",
}


def _clean_npm_version(raw_version: str | None) -> str | None:
    """Clean semver version range specifiers without inventing versions."""
    if not raw_version or not isinstance(raw_version, str):
        return None
    val = raw_version.strip()
    if not val or val in ("*", "latest"):
        return val

    # Match leading semver ranges like ^18.2.0, ~1.0.4, >=16.0.0, v2.3.1
    m = re.match(r"^[~^><=v\s]*(\d+(?:\.\d+)*(?:-[a-zA-Z0-9.\-_]+)?(?:\+[a-zA-Z0-9.\-_]+)?)", val)
    if m:
        return m.group(1)
    return val


def _parse_package_lock_json(lock_path: Path) -> dict[str, str]:
    """Extract resolved versions from package-lock.json (supports v1, v2, v3 formats)."""
    resolved: dict[str, str] = {}
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return resolved

    # npm v2 / v3 packages dictionary
    packages = data.get("packages")
    if isinstance(packages, dict):
        for pkg_key, pkg_info in packages.items():
            if not isinstance(pkg_info, dict):
                continue
            ver = pkg_info.get("version")
            if not ver or not isinstance(ver, str):
                continue
            if "node_modules/" in pkg_key:
                clean_name = pkg_key.split("node_modules/")[-1]
                if clean_name and clean_name not in resolved:
                    resolved[clean_name] = ver

    # npm v1 dependencies dictionary
    deps = data.get("dependencies")
    if isinstance(deps, dict):
        for pkg_name, dep_info in deps.items():
            if isinstance(dep_info, dict):
                ver = dep_info.get("version")
                if ver and isinstance(ver, str) and pkg_name not in resolved:
                    resolved[pkg_name] = ver

    return resolved


def _parse_yarn_lock(lock_path: Path) -> dict[str, str]:
    """Extract resolved versions from yarn.lock (classic & berry)."""
    resolved: dict[str, str] = {}
    try:
        content = lock_path.read_text(encoding="utf-8")
    except Exception:
        return resolved

    version_pattern = re.compile(r'^\s+version(?::|\s+)["\']?([^"\'\s]+)["\']?', re.MULTILINE)

    lines = content.splitlines()
    current_pkgs: list[str] = []
    for line in lines:
        if not line.startswith(" ") and ":" in line:
            current_pkgs = []
            for part in line.split(","):
                part_clean = part.strip().strip('"').strip("'")
                if "@" in part_clean:
                    at_idx = part_clean.rfind("@")
                    if at_idx > 0:
                        pkg = part_clean[:at_idx]
                        current_pkgs.append(pkg)
        elif line.startswith(" ") and current_pkgs:
            ver_match = version_pattern.match(line)
            if ver_match:
                ver = ver_match.group(1)
                for p in current_pkgs:
                    if p not in resolved:
                        resolved[p] = ver
                current_pkgs = []
    return resolved


def _parse_pnpm_lock(lock_path: Path) -> dict[str, str]:
    """Extract resolved versions from pnpm-lock.yaml."""
    resolved: dict[str, str] = {}
    try:
        content = lock_path.read_text(encoding="utf-8")
    except Exception:
        return resolved

    entry_pattern = re.compile(r"['\"]?/?((?:@[a-zA-Z0-9._\-]+\/)?[a-zA-Z0-9._\-]+)@([0-9a-zA-Z.\-_+]+)['\"]?:")
    for match in entry_pattern.finditer(content):
        pkg, ver = match.group(1), match.group(2)
        clean_ver = ver.split("(")[0].split("_")[0]
        if pkg not in resolved:
            resolved[pkg] = clean_ver
    return resolved


@dataclass(frozen=True)
class Dependency:
    group_id: str
    artifact_id: str
    version: str | None
    module: str = "root"
    name: str | None = None
    type: str = "jar"
    classifier: str | None = None
    scope: str = "compile"
    optional: bool = False
    direct: bool = True
    transitive: bool = False
    parent: str | None = None
    introduced_by: str | None = None
    declared_version: str | None = None
    resolved_version: str | None = None
    version_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "name": self.name or f"{self.group_id}:{self.artifact_id}",
            "groupId": self.group_id,
            "artifactId": self.artifact_id,
            "version": self.version,
            "type": self.type,
            "classifier": self.classifier,
            "scope": self.scope,
            "optional": self.optional,
            "direct": self.direct,
            "transitive": self.transitive,
            "parent": self.parent,
            "introducedBy": self.introduced_by,
            "declaredVersion": self.declared_version,
            "resolvedVersion": self.resolved_version,
            "versionSource": self.version_source,
        }


def _extract_declared_dependencies(pom_root: Element | None) -> list[dict[str, Any]]:
    """Extract direct <dependency> declarations under <project><dependencies>, ignoring <dependencyManagement>."""
    if pom_root is None:
        return []
    declared: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _strip_ns(tag: str) -> str:
        return tag.split("}", 1)[1] if "}" in tag else tag

    for child in pom_root:
        if _strip_ns(child.tag) == "dependencies":
            for dep in child:
                if _strip_ns(dep.tag) == "dependency":
                    gid, aid, ver, scope, opt = "", "", None, "compile", False
                    dtype, classifier = "jar", None
                    for prop in dep:
                        ptag = _strip_ns(prop.tag)
                        text = prop.text.strip() if prop.text else ""
                        if ptag == "groupId":
                            gid = text
                        elif ptag == "artifactId":
                            aid = text
                        elif ptag == "version":
                            ver = text
                        elif ptag == "scope":
                            scope = text
                        elif ptag == "optional":
                            opt = text.lower() == "true"
                        elif ptag == "type":
                            dtype = text
                        elif ptag == "classifier":
                            classifier = text
                    if gid and aid:
                        key = (gid, aid)
                        if key not in seen:
                            seen.add(key)
                            declared.append({
                                "group_id": gid,
                                "artifact_id": aid,
                                "version": ver,
                                "scope": scope,
                                "optional": opt,
                                "type": dtype,
                                "classifier": classifier,
                            })
    return declared


def _find_maven_executable(project_root: Path | None) -> str | None:
    """Find Maven executable, prioritizing project-level mvnw/mvnw.cmd before PATH."""
    if project_root:
        from app.shared.file_utils import to_plain_path_str

        clean_root = Path(to_plain_path_str(project_root))
        curr: Path | None = clean_root
        while curr and curr != curr.parent:
            mvnw_candidate = curr / ("mvnw.cmd" if os.name == "nt" else "mvnw")
            if mvnw_candidate.is_file():
                if os.name != "nt":
                    try:
                        if not os.access(mvnw_candidate, os.X_OK):
                            mvnw_candidate.chmod(mvnw_candidate.stat().st_mode | 0o111)
                    except Exception:
                        pass
                return str(mvnw_candidate)
            if (curr / ".git").exists() or curr.name == "original-repo":
                break
            curr = curr.parent
    return resolve_executable("mvn")


def _parse_maven_coordinate(text: str) -> tuple[str, str, str, str | None, str, str] | None:
    """Extract (groupId, artifactId, type, classifier, version, scope) from a dependency:tree coordinate."""
    clean = text.strip()
    if clean.startswith("("):
        clean = clean[1:]
    m6 = re.match(
        r"^([\w.\-]+):([\w.\-]+):([\w.\-]+):([\w.\-]+):([\w.\-]+):([\w.\-]+)(?:[\s;()\-].*)?$",
        clean,
    )
    if m6:
        g, a, t, c, v, s = m6.groups()
        return g, a, t, c, v, s
    m5 = re.match(
        r"^([\w.\-]+):([\w.\-]+):([\w.\-]+):([\w.\-]+):([\w.\-]+)(?:[\s;()\-].*)?$",
        clean,
    )
    if m5:
        g, a, t, v, s = m5.groups()
        return g, a, t, None, v, s
def _map_gradle_config_to_scope(config_name: str) -> str:
    """Map Gradle configuration to standard scope."""
    cfg = config_name.lower()
    if "test" in cfg:
        return "test"
    if "compileonly" in cfg:
        return "provided"
    if "runtime" in cfg:
        return "runtime"
    return "compile"


def _parse_version_catalog(catalog_path: Path) -> dict[str, tuple[str, str, str | None]]:
    """Extract libraries from gradle/libs.versions.toml into a normalized alias map."""
    resolved: dict[str, tuple[str, str, str | None]] = {}
    if not catalog_path.is_file():
        return resolved

    try:
        import tomllib

        data = tomllib.loads(catalog_path.read_text(encoding="utf-8"))
        versions_table = data.get("versions", {})
        libraries_table = data.get("libraries", {})

        for alias, lib_def in libraries_table.items():
            gid, aid, ver = "", "", None
            if isinstance(lib_def, str):
                parts = lib_def.split(":")
                if len(parts) >= 2:
                    gid, aid = parts[0], parts[1]
                    ver = parts[2] if len(parts) >= 3 else None
            elif isinstance(lib_def, dict):
                if "module" in lib_def:
                    parts = str(lib_def["module"]).split(":")
                    if len(parts) >= 2:
                        gid, aid = parts[0], parts[1]
                else:
                    gid = str(lib_def.get("group", ""))
                    aid = str(lib_def.get("name", ""))

                version_val = lib_def.get("version")
                if isinstance(version_val, dict):
                    v_ref = version_val.get("ref")
                    if v_ref and v_ref in versions_table:
                        ver = str(versions_table[v_ref])
                elif isinstance(version_val, str):
                    ver = version_val

            if gid and aid:
                resolved[alias] = (gid, aid, ver)
                resolved[alias.replace("-", ".")] = (gid, aid, ver)
                resolved[alias.replace("_", ".")] = (gid, aid, ver)
                resolved[alias.replace(".", "-")] = (gid, aid, ver)
                resolved[alias.replace(".", "_")] = (gid, aid, ver)
    except Exception as exc:
        logger.debug("Failed to parse version catalog %s: %s", catalog_path, exc)

    return resolved


_POM_CACHE: dict[tuple[str, str, str], list[dict[str, str]]] = {}


def _resolve_transitive_from_pom(group_id: str, artifact_id: str, version: str) -> list[dict[str, str]]:
    """Lightweight POM resolver to identify compile/runtime transitive dependencies of a direct dependency."""
    if not version or "${" in version or not group_id or not artifact_id:
        return []

    cache_key = (group_id, artifact_id, version)
    if cache_key in _POM_CACHE:
        return _POM_CACHE[cache_key]

    group_slash = group_id.replace(".", "/")
    user_home = Path.home()
    local_candidates = [
        user_home / f".m2/repository/{group_slash}/{artifact_id}/{version}/{artifact_id}-{version}.pom",
    ]
    gradle_cache_dir = user_home / f".gradle/caches/modules-2/files-2.1/{group_id}/{artifact_id}/{version}"
    if gradle_cache_dir.is_dir():
        for p in gradle_cache_dir.rglob("*.pom"):
            local_candidates.append(p)
            break

    pom_text = None
    for cand in local_candidates:
        if cand.is_file():
            try:
                pom_text = cand.read_text(encoding="utf-8")
                break
            except Exception:
                pass

    if not pom_text:
        url = f"https://repo1.maven.org/maven2/{group_slash}/{artifact_id}/{version}/{artifact_id}-{version}.pom"
        try:
            import urllib.request

            req = urllib.request.Request(url, headers={"User-Agent": "JavaAPEX/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                pom_text = resp.read().decode("utf-8")
        except Exception:
            _POM_CACHE[cache_key] = []
            return []

    try:
        root = fromstring(pom_text)
        for el in root.iter():
            if isinstance(el.tag, str) and "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]

        props: dict[str, str] = {}
        props_el = root.find("properties")
        if props_el is not None:
            for p in props_el:
                if isinstance(p.tag, str):
                    props[p.tag] = (p.text or "").strip()

        parent_el = root.find("parent")
        managed: dict[tuple[str, str], str] = {}
        if parent_el is not None:
            p_gid_el = parent_el.find("groupId")
            p_aid_el = parent_el.find("artifactId")
            p_ver_el = parent_el.find("version")
            if p_gid_el is not None and p_aid_el is not None and p_ver_el is not None:
                p_gid = (p_gid_el.text or "").strip()
                p_aid = (p_aid_el.text or "").strip()
                p_ver = (p_ver_el.text or "").strip()
                if p_gid and p_aid and p_ver:
                    parent_url = f"https://repo1.maven.org/maven2/{p_gid.replace('.', '/')}/{p_aid}/{p_ver}/{p_aid}-{p_ver}.pom"
                    try:
                        import urllib.request

                        req = urllib.request.Request(parent_url, headers={"User-Agent": "JavaAPEX/1.0"})
                        with urllib.request.urlopen(req, timeout=4) as resp:
                            p_text = resp.read().decode("utf-8")
                        p_root = fromstring(p_text)
                        for el in p_root.iter():
                            if isinstance(el.tag, str) and "}" in el.tag:
                                el.tag = el.tag.split("}", 1)[1]
                        p_props_el = p_root.find("properties")
                        if p_props_el is not None:
                            for p in p_props_el:
                                if isinstance(p.tag, str) and p.tag not in props:
                                    props[p.tag] = (p.text or "").strip()
                        for d in p_root.findall(".//dependencyManagement/dependencies/dependency"):
                            g = (d.find("groupId").text or "").strip() if d.find("groupId") is not None else ""
                            a = (d.find("artifactId").text or "").strip() if d.find("artifactId") is not None else ""
                            v = (d.find("version").text or "").strip() if d.find("version") is not None else ""
                            if g and a and v:
                                managed[(g, a)] = v
                    except Exception:
                        pass

        for d in root.findall(".//dependencyManagement/dependencies/dependency"):
            g = (d.find("groupId").text or "").strip() if d.find("groupId") is not None else ""
            a = (d.find("artifactId").text or "").strip() if d.find("artifactId") is not None else ""
            v = (d.find("version").text or "").strip() if d.find("version") is not None else ""
            if g and a and v:
                managed[(g, a)] = v

        trans_deps: list[dict[str, str]] = []
        for d in root.findall(".//dependencies/dependency"):
            g = (d.find("groupId").text or "").strip() if d.find("groupId") is not None else ""
            a = (d.find("artifactId").text or "").strip() if d.find("artifactId") is not None else ""
            v = (d.find("version").text or "").strip() if d.find("version") is not None else ""
            s = (d.find("scope").text or "").strip() if d.find("scope") is not None else "compile"
            opt = (d.find("optional").text or "").strip().lower() if d.find("optional") is not None else "false"

            if opt == "true" or s in ("test", "provided", "system"):
                continue

            if not v and (g, a) in managed:
                v = managed[(g, a)]

            if v.startswith("${") and v.endswith("}"):
                prop_key = v[2:-1]
                v = props.get(prop_key, v)

            if g and a:
                trans_deps.append({"group_id": g, "artifact_id": a, "version": v, "scope": s})

        _POM_CACHE[cache_key] = trans_deps
        return trans_deps
    except Exception as exc:
        logger.debug("Failed parsing POM for %s:%s:%s: %s", group_id, artifact_id, version, exc)
        _POM_CACHE[cache_key] = []
        return []


class DependencyAnalyzer:
    def __init__(self) -> None:
        self.last_resolution_status: str = "RESOLVED"
        self.last_resolution_method: str = "UNKNOWN"
        self.last_resolution_reason: str = ""

    def analyze(
        self,
        pom_root: Element | None,
        build_gradle_text: str,
        project_root: Path | None = None,
    ) -> list[Dependency]:
        """Extract declared Java dependencies from Maven or Gradle."""
        if pom_root is not None:
            deps = self._from_maven_comprehensive(project_root, pom_root)
            if not deps:
                deps = self._from_maven_basic(pom_root, project_root)
                if deps:
                    self.last_resolution_status = "FALLBACK_DIRECT_ONLY"
                    self.last_resolution_method = "POM_BASIC"
            return deps
        if build_gradle_text:
            return self._from_gradle(build_gradle_text, project_root)
        self.last_resolution_status = "NO_BUILD_FILE"
        self.last_resolution_method = "NONE"
        self.last_resolution_reason = "No Maven pom.xml or Gradle build manifest detected."
        return []

    def analyze_frontend(self, repo_root: Path | None) -> list[Dependency]:
        """Find and parse all package.json files across the repository."""
        if not repo_root or not repo_root.is_dir():
            return []
        return self._from_frontend_packages(repo_root)

    def _from_maven_basic(
        self, pom_root: Element | None, project_root: Path | None = None
    ) -> list[Dependency]:
        """Fallback lightweight Maven dependency extraction without CLI."""
        if pom_root is None and not project_root:
            return []
        declared = _extract_declared_dependencies(pom_root) if pom_root is not None else []
        if project_root and project_root.is_dir():
            for child_pom in project_root.rglob("pom.xml"):
                if pom_root is not None and child_pom.resolve() == (project_root / "pom.xml").resolve():
                    continue
                if any(ignored in child_pom.parts for ignored in _IGNORED_DIRS):
                    continue
                try:
                    from defusedxml.ElementTree import parse as xml_parse
                    child_tree = xml_parse(str(child_pom)).getroot()
                    declared.extend(_extract_declared_dependencies(child_tree))
                except Exception:
                    pass
        deps: list[Dependency] = []
        seen = set()
        for d in declared:
            key = (d.get("module") or "root", d["group_id"], d["artifact_id"])
            if key in seen:
                continue
            seen.add(key)
            ver = d["version"]
            deps.append(
                Dependency(
                    group_id=d["group_id"],
                    artifact_id=d["artifact_id"],
                    version=ver,
                    scope=d["scope"],
                    type=d["type"],
                    classifier=d["classifier"],
                    optional=d["optional"],
                    direct=True,
                    transitive=False,
                    declared_version=ver,
                    resolved_version=ver,
                    version_source="DIRECT" if ver else "MANAGED",
                )
            )
        return deps

    def _from_frontend_packages(self, root: Path) -> list[Dependency]:
        """Find and parse all package.json files across the repository."""
        package_files = self._find_package_json_files(root)
        all_deps: list[Dependency] = []
        seen_keys: set[tuple[str, str, str]] = set()

        for pkg_file in package_files:
            folder = pkg_file.parent
            try:
                rel_module = folder.relative_to(root).as_posix()
            except Exception:
                rel_module = "frontend"
            if rel_module == ".":
                rel_module = "root"

            deps = self._parse_package_json_file(pkg_file, module_name=rel_module, repo_root=root)
            for d in deps:
                key = (d.module, d.group_id, d.artifact_id)
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_deps.append(d)

        return all_deps

    def _find_package_json_files(self, root: Path) -> list[Path]:
        """Recursively scan for package.json while skipping ignored build/cache directories."""
        package_files: list[Path] = []
        try:
            for item in root.rglob("package.json"):
                parts = set(item.parts)
                if not parts.intersection(_IGNORED_DIRS) and item.is_file():
                    package_files.append(item)
        except Exception as exc:
            logger.debug("Error scanning for package.json files: %s", exc)
        return package_files

    def _parse_package_json_file(
        self, pkg_path: Path, module_name: str, repo_root: Path
    ) -> list[Dependency]:
        """Extract dependencies and devDependencies from a single package.json with lockfile resolution."""
        if not pkg_path.is_file():
            return []

        try:
            content = pkg_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception as exc:
            logger.debug("Failed to read or parse %s: %s", pkg_path, exc)
            return []

        if not isinstance(data, dict):
            return []

        resolved_versions: dict[str, str] = {}
        for search_dir in (pkg_path.parent, repo_root):
            if not resolved_versions and (search_dir / "package-lock.json").is_file():
                resolved_versions = _parse_package_lock_json(search_dir / "package-lock.json")
            if not resolved_versions and (search_dir / "yarn.lock").is_file():
                resolved_versions = _parse_yarn_lock(search_dir / "yarn.lock")
            if not resolved_versions and (search_dir / "pnpm-lock.yaml").is_file():
                resolved_versions = _parse_pnpm_lock(search_dir / "pnpm-lock.yaml")
            if resolved_versions:
                break

        results: list[Dependency] = []

        prod_deps = data.get("dependencies")
        if isinstance(prod_deps, dict):
            for name, declared_ver in prod_deps.items():
                dep = self._create_npm_dependency(
                    name=str(name),
                    raw_declared=str(declared_ver) if declared_ver is not None else None,
                    resolved_versions=resolved_versions,
                    module_name=module_name,
                    is_dev=False,
                )
                if dep:
                    results.append(dep)

        dev_deps = data.get("devDependencies")
        if isinstance(dev_deps, dict):
            for name, declared_ver in dev_deps.items():
                dep = self._create_npm_dependency(
                    name=str(name),
                    raw_declared=str(declared_ver) if declared_ver is not None else None,
                    resolved_versions=resolved_versions,
                    module_name=module_name,
                    is_dev=True,
                )
                if dep:
                    results.append(dep)

        return results

    def _create_npm_dependency(
        self,
        name: str,
        raw_declared: str | None,
        resolved_versions: dict[str, str],
        module_name: str,
        is_dev: bool,
    ) -> Dependency | None:
        clean_name = name.strip()
        if not clean_name:
            return None

        if clean_name.startswith("@") and "/" in clean_name:
            group_id, artifact_id = clean_name.split("/", 1)
        else:
            group_id = "npm"
            artifact_id = clean_name

        resolved_ver = resolved_versions.get(clean_name)
        if resolved_ver:
            final_version = resolved_ver
            ver_source = "LOCKFILE"
        elif raw_declared:
            final_version = _clean_npm_version(raw_declared)
            ver_source = "DECLARED"
        else:
            final_version = None
            ver_source = None

        return Dependency(
            group_id=group_id,
            artifact_id=artifact_id,
            version=final_version,
            module=module_name,
            name=clean_name,
            type="npm-dev" if is_dev else "npm",
            scope="devDependencies" if is_dev else "dependencies",
            direct=True,
            declared_version=raw_declared,
            resolved_version=resolved_ver,
            version_source=ver_source,
        )

    # -- Maven Comprehensive -------------------------------------------------- #

    def _from_maven_comprehensive(
        self,
        project_root: Path | None,
        pom_root: Element | None = None,
    ) -> list[Dependency]:
        if not project_root:
            self.last_resolution_status = "NO_PROJECT_ROOT"
            self.last_resolution_reason = "No project root directory provided."
            return []
        from app.shared.file_utils import to_plain_path_str

        clean_root = Path(to_plain_path_str(project_root))
        if not (clean_root / "pom.xml").exists():
            self.last_resolution_status = "NO_POM_XML"
            self.last_resolution_reason = f"No pom.xml found in {clean_root}."
            return []

        mvn = _find_maven_executable(clean_root)
        if not mvn:
            self.last_resolution_status = "FALLBACK_DIRECT_ONLY"
            self.last_resolution_reason = "Maven executable (mvn or mvnw) not found on PATH or in project."
            logger.debug("Maven executable not found; falling back to basic parsing.")
            return []

        declared_deps = _extract_declared_dependencies(pom_root) if pom_root is not None else []
        if clean_root.is_dir():
            for child_pom in clean_root.rglob("pom.xml"):
                if child_pom.resolve() == (clean_root / "pom.xml").resolve():
                    continue
                if any(ignored in child_pom.parts for ignored in _IGNORED_DIRS):
                    continue
                try:
                    from defusedxml.ElementTree import parse as xml_parse
                    child_tree = xml_parse(str(child_pom)).getroot()
                    declared_deps.extend(_extract_declared_dependencies(child_tree))
                except Exception:
                    pass

        cmd_tree = [mvn, "dependency:tree", "-B"]

        try:
            res_tree = run_command(cmd_tree, cwd=clean_root, timeout=120)
            tree_content = res_tree.stdout or ""

            if not res_tree.succeeded and not tree_content:
                self.last_resolution_status = "FALLBACK_DIRECT_ONLY"
                self.last_resolution_reason = (
                    f"Maven dependency:tree failed with exit code {res_tree.exit_code}: "
                    f"{(res_tree.stderr or res_tree.stdout or '').strip()[:200]}"
                )
                logger.warning("Comprehensive Maven analysis failed: %s", self.last_resolution_reason)
                return []

            deps = self._parse_maven_outputs(tree_content, "", declared_deps)
            if deps:
                self.last_resolution_status = "RESOLVED"
                self.last_resolution_method = "MAVEN_CLI"
                self.last_resolution_reason = f"Successfully resolved {len(deps)} dependencies via Maven CLI."
            else:
                self.last_resolution_status = "FALLBACK_DIRECT_ONLY"
                self.last_resolution_reason = "Maven dependency:tree returned no dependencies."
            return deps
        except Exception as exc:
            self.last_resolution_status = "FALLBACK_DIRECT_ONLY"
            self.last_resolution_reason = f"Exception during Maven dependency resolution: {exc}"
            logger.error("Error during comprehensive Maven analysis: %s", exc)
            return []

    def _parse_maven_outputs(
        self,
        tree_content: str,
        pom_content: str = "",
        declared_deps: list[dict[str, Any]] | None = None,
    ) -> list[Dependency]:
        """Parse dependency:tree and help:effective-pom to extract every dependency."""
        resolved_deps: dict[tuple[str, str, str], Dependency] = {}
        declared_map: dict[tuple[str, str], dict[str, Any]] = {
            (d["group_id"], d["artifact_id"]): d for d in (declared_deps or [])
        }

        current_module = "root"
        lines = tree_content.splitlines()

        # 0. Identify internal modules
        internal_modules = set()
        for line in lines:
            clean_line = line.replace("[INFO]", "").strip()
            m = re.match(r"^([\w.\-]+):([\w.\-]+):(?:pom|jar|war):([\w.\-]+)$", clean_line)
            if m:
                internal_modules.add((m.group(1), m.group(2)))

        ancestors: dict[int, str] = {}

        for line in lines:
            info_content = line.split("[INFO]", 1)[1] if "[INFO]" in line else line
            clean_line = info_content.strip()
            if not clean_line:
                continue

            marker_idx = -1
            for m in ["+-", "\\-"]:
                idx = info_content.find(m)
                if idx != -1 and (marker_idx == -1 or idx < marker_idx):
                    marker_idx = idx

            if marker_idx == -1:
                module_match = re.search(r"@\s+([\w.\-]+)\s+---", clean_line)
                if module_match:
                    current_module = module_match.group(1)
                    ancestors.clear()
                else:
                    coord_match = re.match(r"^([\w.\-]+):([\w.\-]+):(?:pom|jar|war):([\w.\-]+)$", clean_line)
                    if coord_match:
                        current_module = coord_match.group(2)
                        ancestors.clear()
                ancestors[0] = clean_line
                continue

            # depth calculation:
            depth = max(1, (marker_idx // 3) + 1)

            # Skip Maven omitted dependencies (conflicts, duplicates, cycles from verbose trees)
            if "omitted for " in clean_line.lower():
                continue

            content_after_marker = info_content[marker_idx + 2:].strip()
            parsed_coord = _parse_maven_coordinate(content_after_marker)
            if not parsed_coord:
                continue

            gid, aid, dtype, classifier, version, scope = parsed_coord
            coord = f"{gid}:{aid}"
            ancestors[depth] = coord

            is_declared = (gid, aid) in declared_map
            is_direct = (depth == 1) or is_declared

            dec_info = declared_map.get((gid, aid))
            is_optional = "(optional)" in clean_line.lower() or bool(dec_info and dec_info.get("optional"))

            parent = ancestors.get(depth - 1) if (depth > 1 and not is_direct) else None
            root_parent = ancestors.get(1) if (depth > 1 and not is_direct) else None

            key = (current_module, gid, aid)

            if key not in resolved_deps:
                v_source = "TRANSITIVE" if not is_direct else ("DIRECT" if (dec_info and dec_info.get("version")) else "MANAGED")
                if (gid, aid) in internal_modules:
                    v_source = "INTERNAL_MODULE"

                resolved_deps[key] = Dependency(
                    group_id=gid,
                    artifact_id=aid,
                    version=version,
                    module=current_module,
                    type=dtype,
                    classifier=classifier,
                    scope=dec_info.get("scope") if (dec_info and is_direct) else scope,
                    optional=is_optional,
                    direct=is_direct,
                    transitive=not is_direct,
                    parent=parent,
                    introduced_by=root_parent,
                    declared_version=dec_info.get("version") if dec_info else None,
                    resolved_version=version,
                    version_source=v_source,
                )
            else:
                existing = resolved_deps[key]
                if is_direct and not existing.direct:
                    resolved_deps[key] = Dependency(
                        group_id=gid,
                        artifact_id=aid,
                        version=version or existing.version,
                        module=current_module,
                        type=dtype or existing.type,
                        classifier=classifier or existing.classifier,
                        scope=dec_info.get("scope") if (dec_info and dec_info.get("scope")) else (existing.scope or scope),
                        optional=is_optional or existing.optional,
                        direct=True,
                        transitive=False,
                        parent=None,
                        introduced_by=None,
                        declared_version=dec_info.get("version") if dec_info else existing.declared_version,
                        resolved_version=version or existing.resolved_version,
                        version_source="DIRECT" if (dec_info and dec_info.get("version")) else "MANAGED",
                    )

        # Ensure all declared dependencies from the POM are included in the results
        for (d_gid, d_aid), dec_info in declared_map.items():
            if any(k[1] == d_gid and k[2] == d_aid for k in resolved_deps):
                continue
            key = (current_module, d_gid, d_aid)
            if key not in resolved_deps:
                resolved_deps[key] = Dependency(
                    group_id=d_gid,
                    artifact_id=d_aid,
                    version=dec_info.get("version"),
                    module=current_module,
                    type=dec_info.get("type") or "jar",
                    classifier=dec_info.get("classifier"),
                    scope=dec_info.get("scope") or "compile",
                    optional=bool(dec_info.get("optional")),
                    direct=True,
                    transitive=False,
                    parent=None,
                    introduced_by=None,
                    declared_version=dec_info.get("version"),
                    resolved_version=dec_info.get("version"),
                    version_source="DIRECT" if dec_info.get("version") else "MANAGED",
                )

        if pom_content:
            try:
                root = fromstring(pom_content)
                for el in root.iter():
                    if isinstance(el.tag, str) and "}" in el.tag:
                        el.tag = el.tag.split("}", 1)[1]

                for dep in resolved_deps.values():
                    if dep.version_source in ("UNKNOWN", "MANAGED"):
                        source = dep.version_source
                        if dep.group_id.startswith("org.springframework.boot"):
                            source = "SPRING_BOOT_PARENT"
                        object.__setattr__(dep, "version_source", source)
            except Exception:
                pass

        return list(resolved_deps.values())

    # -- Gradle -------------------------------------------------------------- #

    def _from_gradle(self, build_text: str, project_root: Path | None = None) -> list[Dependency]:
        if project_root:
            cli_deps = self._from_gradle_cli(project_root)
            if cli_deps:
                self.last_resolution_status = "RESOLVED"
                self.last_resolution_method = "GRADLE_CLI"
                self.last_resolution_reason = f"Successfully resolved {len(cli_deps)} dependencies via Gradle CLI."
                return cli_deps

        cli_err = getattr(self, "_gradle_cli_error", None) or "Gradle CLI execution unavailable"

        # Direct dependency extraction from build manifests (Groovy & Kotlin DSL, catalogs, submodules)
        direct_deps = self._extract_gradle_direct_dependencies(build_text, project_root)

        if not direct_deps:
            self.last_resolution_status = "RESOLUTION_FAILED"
            self.last_resolution_method = "GRADLE_FILE"
            self.last_resolution_reason = f"Gradle dependency resolution failed: {cli_err}; 0 dependencies parsed from build files."
            return []

        # Resolve transitive dependencies for direct production dependencies when project_root is provided
        transitive_deps = (
            self._resolve_gradle_transitive_dependencies(direct_deps) if project_root else []
        )
        all_deps = direct_deps + transitive_deps

        if transitive_deps:
            self.last_resolution_status = "RESOLVED"
            self.last_resolution_method = "GRADLE_BUILD_AND_POM"
            self.last_resolution_reason = (
                f"Gradle CLI execution failed ({cli_err}). "
                f"Resolved {len(direct_deps)} direct and {len(transitive_deps)} transitive dependencies via build manifests and dependency models."
            )
        else:
            self.last_resolution_status = "FALLBACK_DIRECT_ONLY"
            self.last_resolution_method = "GRADLE_FILE"
            self.last_resolution_reason = (
                f"Gradle CLI execution failed ({cli_err}). "
                f"Extracted {len(direct_deps)} direct dependencies from build manifests."
            )

        return all_deps

    def _extract_gradle_direct_dependencies(
        self, build_text: str, project_root: Path | None = None
    ) -> list[Dependency]:
        """Extract direct dependency declarations supporting Groovy, Kotlin DSL, version catalogs, and submodules."""
        catalog: dict[str, tuple[str, str, str | None]] = {}
        if project_root:
            from app.shared.file_utils import to_plain_path_str

            clean_root = Path(to_plain_path_str(project_root))
            for cat_path in (clean_root / "gradle/libs.versions.toml", clean_root / "libs.versions.toml"):
                if cat_path.is_file():
                    catalog = _parse_version_catalog(cat_path)
                    break

        configs = "|".join(_GRADLE_CONFIGS)
        result: list[Dependency] = []
        seen: set[tuple[str, str, str]] = set()

        module_texts: list[tuple[str, str]] = []
        if project_root and project_root.is_dir():
            from app.shared.file_utils import to_plain_path_str

            clean_root = Path(to_plain_path_str(project_root))
            build_files: list[tuple[str, Path]] = []
            for name in ("build.gradle", "build.gradle.kts"):
                f = clean_root / name
                if f.is_file():
                    build_files.append(("root", f))
            for ext in ("build.gradle", "build.gradle.kts"):
                for cand in clean_root.rglob(ext):
                    if cand.is_file() and not any(part in _IGNORED_DIRS for part in cand.parts):
                        if not any(cand == bf[1] for bf in build_files):
                            mod_name = cand.parent.name if cand.parent != clean_root else "root"
                            build_files.append((mod_name, cand))
            for mod_name, bf in build_files:
                try:
                    module_texts.append((mod_name, bf.read_text(encoding="utf-8")))
                except Exception:
                    pass

        if not module_texts:
            module_texts.append(("root", build_text or ""))

        # 1. Quoted and unquoted string coordinates: "implementation"("group:artifact:version") or implementation 'group:artifact:version'
        pattern_string = re.compile(
            rf"""(?i)(?:['"]?({configs})['"]?)\s*(?:\(\s*|\s+)\s*['"]([a-zA-Z0-9.\-_]+):([a-zA-Z0-9.\-_]+)(?::([a-zA-Z0-9.\-_]+))?['"]"""
        )
        # 2. Map / named-argument notation: group = "...", name = "...", version = "..."
        pattern_map = re.compile(
            rf"""(?i)(?:['"]?({configs})['"]?)\s*(?:\(\s*|\s+)[^)\n]*?group\s*(?:=|:)\s*['"]([^'"]+)['"][^)\n]*?name\s*(?:=|:)\s*['"]([^'"]+)['"](?:[^)\n]*?version\s*(?:=|:)\s*['"]([^'"]+)['"])?"""
        )
        # 3. Version catalog accessor (libs.xxx)
        pattern_catalog = re.compile(
            rf"""(?i)(?:['"]?({configs})['"]?)\s*(?:\(\s*|\s+)\s*libs(?:\.bundles)?\.([a-zA-Z0-9_.]+)"""
        )

        for mod_name, text in module_texts:
            # 1. String coordinates
            for m in pattern_string.finditer(text):
                cfg, gid, aid, ver = m.group(1), m.group(2), m.group(3), m.group(4)
                key = (mod_name, gid, aid)
                if key in seen:
                    continue
                seen.add(key)
                scope = _map_gradle_config_to_scope(cfg)
                result.append(
                    Dependency(
                        group_id=gid,
                        artifact_id=aid,
                        version=ver,
                        module=mod_name,
                        scope=scope,
                        direct=True,
                        transitive=False,
                        declared_version=ver,
                        resolved_version=ver,
                        version_source="DIRECT" if ver else "MANAGED",
                    )
                )

            # 2. Map coordinates
            for m in pattern_map.finditer(text):
                cfg, gid, aid, ver = m.group(1), m.group(2), m.group(3), m.group(4)
                key = (mod_name, gid, aid)
                if key in seen:
                    continue
                seen.add(key)
                scope = _map_gradle_config_to_scope(cfg)
                result.append(
                    Dependency(
                        group_id=gid,
                        artifact_id=aid,
                        version=ver,
                        module=mod_name,
                        scope=scope,
                        direct=True,
                        transitive=False,
                        declared_version=ver,
                        resolved_version=ver,
                        version_source="DIRECT" if ver else "MANAGED",
                    )
                )

            # 3. Version catalog coordinates
            if catalog:
                for m in pattern_catalog.finditer(text):
                    cfg, alias = m.group(1), m.group(2)
                    norm_aliases = [
                        alias,
                        alias.replace(".", "-"),
                        alias.replace(".", "_"),
                        alias.replace("_", "-"),
                    ]
                    cat_entry = None
                    for na in norm_aliases:
                        if na in catalog:
                            cat_entry = catalog[na]
                            break
                    if cat_entry:
                        gid, aid, ver = cat_entry
                        key = (mod_name, gid, aid)
                        if key in seen:
                            continue
                        seen.add(key)
                        scope = _map_gradle_config_to_scope(cfg)
                        result.append(
                            Dependency(
                                group_id=gid,
                                artifact_id=aid,
                                version=ver,
                                module=mod_name,
                                scope=scope,
                                direct=True,
                                transitive=False,
                                declared_version=ver,
                                resolved_version=ver,
                                version_source="DIRECT" if ver else "MANAGED",
                            )
                        )

        return result

    def _resolve_gradle_transitive_dependencies(self, direct_deps: list[Dependency]) -> list[Dependency]:
        """Discover transitive dependencies for direct production dependencies via POM models."""
        transitive_deps: list[Dependency] = []
        seen = {(d.group_id, d.artifact_id) for d in direct_deps}

        for dep in direct_deps:
            if dep.scope == "test":
                continue
            if not dep.version:
                continue

            trans_list = _resolve_transitive_from_pom(dep.group_id, dep.artifact_id, dep.version)
            for t in trans_list:
                key = (t["group_id"], t["artifact_id"])
                if key not in seen:
                    seen.add(key)
                    transitive_deps.append(
                        Dependency(
                            group_id=t["group_id"],
                            artifact_id=t["artifact_id"],
                            version=t.get("version"),
                            module=dep.module,
                            scope=t.get("scope", "compile"),
                            direct=False,
                            transitive=True,
                            parent=f"{dep.group_id}:{dep.artifact_id}",
                            introduced_by=f"{dep.group_id}:{dep.artifact_id}",
                            resolved_version=t.get("version"),
                            version_source="TRANSITIVE",
                        )
                    )

        return transitive_deps

    def _from_gradle_cli(self, project_root: Path) -> list[Dependency]:
        from app.shared.file_utils import to_plain_path_str

        clean_root = Path(to_plain_path_str(project_root))
        gradlew = clean_root / ("gradlew.bat" if os.name == "nt" else "gradlew")

        candidates: list[str] = []
        if gradlew.exists():
            candidates.append(str(gradlew))
        system_gradle = resolve_executable("gradle")
        if system_gradle and system_gradle not in candidates:
            candidates.append(system_gradle)

        if not candidates:
            self._gradle_cli_error = "No Gradle executable (gradlew or gradle on PATH) found."
            return []

        last_error = ""
        for cmd in candidates:
            try:
                res = run_command([cmd, "dependencies", "--console=plain"], cwd=clean_root, timeout=90)
                if res.succeeded and res.stdout:
                    deps = self._parse_gradle_dependencies_output(res.stdout)
                    if deps:
                        return deps
                err_text = (res.stderr or res.stdout or "").strip()
                last_error = f"{Path(cmd).name} exited with code {res.exit_code}: {err_text[:200]}"
            except Exception as exc:
                last_error = f"{Path(cmd).name} error: {exc}"

        self._gradle_cli_error = last_error
        return []

    def _parse_gradle_dependencies_output(self, output: str) -> list[Dependency]:
        resolved_deps: dict[tuple[str, str], Dependency] = {}
        dep_pattern = re.compile(r"([\w.\-]+):([\w.\-]+):([\w.\-]+)(?: -> ([\w.\-]+))?")
        ancestors: dict[int, str] = {}

        for line in output.splitlines():
            clean_line = line.strip()
            if not clean_line:
                continue

            marker_idx = -1
            for m in ["+---", "\\---"]:
                idx = line.find(m)
                if idx != -1 and (marker_idx == -1 or idx < marker_idx):
                    marker_idx = idx

            if marker_idx == -1:
                continue

            depth = max(1, (marker_idx // 5) + 1)
            is_direct = (depth == 1)

            m = dep_pattern.search(clean_line)
            if m:
                gid, aid, req_ver, selected_ver = m.groups()
                ver = selected_ver or req_ver
                coord = f"{gid}:{aid}"
                ancestors[depth] = coord

                parent = ancestors.get(depth - 1) if depth > 1 else None
                root_parent = ancestors.get(1) if depth > 1 else None
                key = (gid, aid)

                if key not in resolved_deps:
                    resolved_deps[key] = Dependency(
                        group_id=gid,
                        artifact_id=aid,
                        version=ver,
                        scope="compile",
                        direct=is_direct,
                        transitive=not is_direct,
                        parent=parent,
                        introduced_by=root_parent,
                        resolved_version=ver,
                        version_source="DIRECT" if is_direct else "TRANSITIVE",
                    )
                elif is_direct and not resolved_deps[key].direct:
                    resolved_deps[key] = Dependency(
                        group_id=gid,
                        artifact_id=aid,
                        version=ver or resolved_deps[key].version,
                        scope="compile",
                        direct=True,
                        transitive=False,
                        parent=None,
                        introduced_by=None,
                        resolved_version=ver or resolved_deps[key].resolved_version,
                        version_source="DIRECT",
                    )

        return list(resolved_deps.values())
