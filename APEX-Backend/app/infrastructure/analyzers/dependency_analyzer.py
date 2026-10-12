"""Extracts declared dependencies from Maven or Gradle build files and frontend package manifests."""

from __future__ import annotations

import json
import logging
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
    "testImplementation",
    "testCompileOnly",
    "testRuntimeOnly",
    "annotationProcessor",
    "developmentOnly",
    "compile",  # legacy
    "testCompile",  # legacy
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
            "declaredVersion": self.declared_version,
            "resolvedVersion": self.resolved_version,
            "versionSource": self.version_source,
        }


class DependencyAnalyzer:
    def analyze(
        self,
        pom_root: Element | None,
        build_gradle_text: str,
        project_root: Path | None = None,
    ) -> list[Dependency]:
        """Extract declared Java dependencies from Maven or Gradle."""
        if pom_root is not None:
            deps = self._from_maven_comprehensive(project_root)
            if not deps:
                deps = self._from_maven_basic(pom_root)
            return deps
        if build_gradle_text:
            return self._from_gradle(build_gradle_text)
        return []

    def analyze_frontend(self, repo_root: Path | None) -> list[Dependency]:
        """Find and parse all package.json files across the repository."""
        if not repo_root or not repo_root.is_dir():
            return []
        return self._from_frontend_packages(repo_root)

    def _from_maven_basic(self, pom_root: Element | None) -> list[Dependency]:
        """Fallback lightweight Maven dependency extraction without CLI."""
        if pom_root is None:
            return []
        deps: list[Dependency] = []
        seen = set()
        for dep in pom_root.iter():
            tag = dep.tag.split("}", 1)[1] if "}" in dep.tag else dep.tag
            if tag == "dependency":
                gid, aid, ver, scope = "", "", None, "compile"
                for child in dep:
                    ctag = child.tag.split("}", 1)[1] if "}" in child.tag else child.tag
                    text = child.text.strip() if child.text else ""
                    if ctag == "groupId":
                        gid = text
                    elif ctag == "artifactId":
                        aid = text
                    elif ctag == "version":
                        ver = text
                    elif ctag == "scope":
                        scope = text
                if gid and aid:
                    key = (gid, aid, scope)
                    if key not in seen:
                        seen.add(key)
                        deps.append(
                            Dependency(
                                group_id=gid,
                                artifact_id=aid,
                                version=ver,
                                scope=scope,
                                type="jar",
                                direct=True,
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

    def _from_maven_comprehensive(self, project_root: Path | None) -> list[Dependency]:
        if not project_root or not (project_root / "pom.xml").exists():
            return []

        mvn = resolve_executable("mvn")
        if not mvn:
            logger.debug("Maven executable not found; falling back to basic parsing.")
            return []

        tree_file = project_root / f"dep-tree-{uuid.uuid4().hex[:8]}.txt"
        pom_file = project_root / f"eff-pom-{uuid.uuid4().hex[:8]}.xml"

        cmd_tree = [mvn, "dependency:tree", f"-DoutputFile={tree_file.name}", "-B"]
        cmd_pom = [mvn, "help:effective-pom", f"-Doutput={pom_file.name}", "-B"]

        try:
            run_command(cmd_tree, cwd=project_root, timeout=120)
            run_command(cmd_pom, cwd=project_root, timeout=120)

            tree_content = tree_file.read_text(encoding="utf-8") if tree_file.exists() else ""
            pom_content = pom_file.read_text(encoding="utf-8") if pom_file.exists() else ""

            tree_file.unlink(missing_ok=True)
            pom_file.unlink(missing_ok=True)

            return self._parse_maven_outputs(tree_content, pom_content)
        except Exception as exc:
            logger.error("Error during comprehensive Maven analysis: %s", exc)
            return []

    def _parse_maven_outputs(self, tree_content: str, pom_content: str) -> list[Dependency]:
        """Parse dependency:tree and help:effective-pom to extract every dependency."""
        resolved_deps: dict[tuple[str, str, str, str, str], Dependency] = {}

        current_module = "root"
        lines = tree_content.splitlines()

        # 0. Identify internal modules
        internal_modules = set()
        for line in lines:
            clean_line = line.replace("[INFO]", "").strip()
            m = re.match(r"^([\w.\-]+):([\w.\-]+):pom:([\w.\-]+)$", clean_line)
            if m: internal_modules.add((m.group(1), m.group(2)))

        dep_re = re.compile(r"([\w.\-]+):([\w.\-]+):([\w.\-]+):(?:([\w.\-]+):)?([\w.\-]+):([\w.\-]+)$")

        for line in lines:
            info_content = line.split("[INFO]", 1)[1] if "[INFO]" in line else line
            clean_line = info_content.strip()
            if not clean_line: continue

            if not any(m in info_content[:10] for m in ["+-", "\\-", "|"]):
                module_match = re.match(r"^([\w.\-]+):([\w.\-]+):pom:([\w.\-]+)$", clean_line)
                if module_match:
                    current_module = module_match.group(2)
                    continue

            dep_match = dep_re.search(clean_line)
            if dep_match:
                gid, aid, dtype, classifier, version, scope = dep_match.groups()

                marker_idx = info_content.find("+-")
                if marker_idx == -1: marker_idx = info_content.find("\\-")

                # Heuristic for direct vs transitive
                prefix = info_content[:marker_idx] if marker_idx != -1 else info_content
                is_direct = "|" not in prefix and marker_idx != -1

                key = (current_module, gid, aid, scope, classifier or "")

                if key not in resolved_deps:
                    v_source = "TRANSITIVE" if not is_direct else "UNKNOWN"
                    if (gid, aid) in internal_modules:
                         v_source = "INTERNAL_MODULE"

                    resolved_deps[key] = Dependency(
                        group_id=gid,
                        artifact_id=aid,
                        version=version,
                        module=current_module,
                        type=dtype,
                        classifier=classifier,
                        scope=scope,
                        direct=is_direct,
                        transitive=not is_direct,
                        resolved_version=version,
                        version_source=v_source
                    )

        if pom_content:
            try:
                root = fromstring(pom_content)
                for el in root.iter():
                    if isinstance(el.tag, str) and "}" in el.tag:
                        el.tag = el.tag.split("}", 1)[1]

                for dep in resolved_deps.values():
                    if dep.version_source == "UNKNOWN":
                         source = "DIRECT"
                         if dep.group_id.startswith("org.springframework.boot"):
                              source = "SPRING_BOOT_PARENT"

                         object.__setattr__(dep, 'version_source', source)
            except:
                pass

        return list(resolved_deps.values())

    # -- Gradle -------------------------------------------------------------- #

    def _from_gradle(self, build_text: str) -> list[Dependency]:
        result: list[Dependency] = []
        seen: set[tuple[str, str]] = set()
        configs = "|".join(_GRADLE_CONFIGS)

        pattern = re.compile(
            rf"\b(?:{configs})\s*[(\s]\s*['\"]([^'\"]+:[^'\"]+)['\"]",
        )
        for match in pattern.finditer(build_text):
            coordinate = match.group(1)
            parts = coordinate.split(":")
            if len(parts) < 2:
                continue
            group, artifact = parts[0], parts[1]
            version = parts[2] if len(parts) >= 3 else None
            key = (group, artifact)
            if key in seen:
                continue
            seen.add(key)
            result.append(Dependency(group, artifact, version))
        return result
