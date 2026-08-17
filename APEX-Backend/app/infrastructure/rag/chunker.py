"""Semantic chunking of a repository's discovery report.

The discovery report (``discovery-report.json``) is split into a handful of
human-readable knowledge sections — one chunk per ``chunk_type`` — instead of
being embedded as raw JSON. Natural-language sentences embed far better than
JSON braces/keys, so retrieval quality is much higher and each retrieved chunk
is directly usable as grounded LLM context.

Kept pure: input is the report ``dict``, output is a list of
:class:`KnowledgeChunk` objects. No embedding, storage, or IO here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class KnowledgeChunk:
    """A single semantic section of repository knowledge, ready to embed."""

    chunk_type: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _clean(value: Any, fallback: str = "unknown") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def build_chunks(report: dict[str, Any]) -> list[KnowledgeChunk]:
    """Split a discovery report into semantic knowledge chunks.

    Empty/irrelevant sections are skipped so we never embed noise. The order
    roughly follows how a reader would explore the project.
    """
    repo_name = _clean(report.get("repoName"), "the repository")
    build_tool = _clean(report.get("buildTool"))
    java_version = _clean(report.get("currentJavaVersion"))
    spring_boot = report.get("springBootVersion")
    project_type = _clean(report.get("projectType"))
    frameworks = [str(f).strip() for f in (report.get("frameworks") or []) if str(f).strip()]
    dependencies = [d for d in (report.get("dependencies") or []) if isinstance(d, dict)]
    build_plugins = [p for p in (report.get("buildPlugins") or []) if isinstance(p, dict)]
    modules = [str(m).strip() for m in (report.get("modules") or []) if str(m).strip()]
    multi_module = bool(report.get("multiModule"))
    frontend = report.get("frontend") or {}
    detected_files = report.get("detectedFiles") or {}

    chunks: list[KnowledgeChunk] = []

    # --- Project information ------------------------------------------------ #
    project_lines = [
        f"Repository: {repo_name}.",
        f"Owner: {_clean(report.get('owner'))}.",
        f"Repository URL: {_clean(report.get('repoUrl'))}.",
        f"Project type: {project_type}.",
        f"Multi-module project: {_yes_no(multi_module)}.",
    ]
    if modules:
        project_lines.append(f"Modules ({len(modules)}): {', '.join(modules)}.")
    chunks.append(KnowledgeChunk("project_info", " ".join(project_lines)))

    # --- Java information --------------------------------------------------- #
    java_text = (
        f"The project's current/detected Java version is Java {java_version}. "
        f"This is the source Java version considered for migration and modernization."
    )
    chunks.append(KnowledgeChunk("java_info", java_text))

    # --- Build tool --------------------------------------------------------- #
    build_lines = [f"The project is built with {build_tool}."]
    if build_plugins:
        plugin_parts = []
        for plugin in build_plugins:
            name = _clean(plugin.get("id"))
            version = plugin.get("version")
            plugin_parts.append(f"{name} (version {version})" if version else name)
        build_lines.append(f"Build plugins configured: {', '.join(plugin_parts)}.")
    chunks.append(KnowledgeChunk("build_tool", " ".join(build_lines)))

    # --- Framework information ---------------------------------------------- #
    framework_lines = []
    if spring_boot:
        framework_lines.append(f"Spring Boot version {spring_boot} is used.")
    if frameworks:
        framework_lines.append(f"Detected frameworks and libraries: {', '.join(frameworks)}.")
    if not framework_lines:
        framework_lines.append("No specific application framework was detected.")
    chunks.append(KnowledgeChunk("framework_info", " ".join(framework_lines)))

    # --- Dependencies ------------------------------------------------------- #
    dep_count = report.get("dependencyCount", len(dependencies))
    if dependencies:
        dep_lines = [f"The project declares {dep_count} dependencies:"]
        for dep in dependencies:
            group = _clean(dep.get("groupId"), "")
            artifact = _clean(dep.get("artifactId"), "unknown")
            version = dep.get("version")
            coord = f"{group}:{artifact}" if group else artifact
            dep_lines.append(f"- {coord}{f' version {version}' if version else ' (version managed)'}")
        chunks.append(KnowledgeChunk("dependencies", "\n".join(dep_lines)))
    else:
        chunks.append(
            KnowledgeChunk("dependencies", "No third-party dependencies were detected.")
        )

    # --- Frontend ----------------------------------------------------------- #
    if frontend.get("detected"):
        frontend_text = (
            f"A frontend was detected: type {_clean(frontend.get('type'))}, "
            f"located at {_clean(frontend.get('path'))}, "
            f"package manager {_clean(frontend.get('packageManager'))}."
        )
    else:
        frontend_text = "No frontend was detected; this is a backend/Java-only project."
    chunks.append(KnowledgeChunk("frontend", frontend_text))

    # --- Detected build files ---------------------------------------------- #
    present = [name for name, ok in detected_files.items() if ok]
    files_text = (
        f"Detected build/config files: {', '.join(present)}."
        if present
        else "No standard build/config files were detected."
    )
    chunks.append(KnowledgeChunk("detected_files", files_text))

    return chunks


# Keep long change lists bounded so a single chunk stays well under the
# retriever's 6000-char context budget (see retriever.py) and never crowds out
# other chunks. The file-list cap bounds the number of bullet lines; the
# per-chunk char cap is a final safety net for very long paths.
_MAX_LISTED_FILES = 20
_MAX_CHUNK_CHARS = 1800


def _truncate(text: str, limit: int = _MAX_CHUNK_CHARS) -> str:
    """Cap a chunk's text so no single chunk dominates the retrieval budget."""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n- ...(truncated)"


def build_migration_chunks(report: dict[str, Any]) -> list[KnowledgeChunk]:
    """Split a migration (execution) report into semantic knowledge chunks.

    Complements :func:`build_chunks`: the discovery report describes the project
    *before* migration, while this renders the *outcome* — how many files were
    modified, which files changed, import/source-code changes, and dependency
    upgrades — so the chatbot can answer questions about the migration result.
    Empty sections are skipped so we never embed noise.
    """
    chunks: list[KnowledgeChunk] = []

    # --- Migration summary -------------------------------------------------- #
    summary_lines: list[str] = []
    migration_summary = _clean(report.get("migrationSummary"), "")
    if migration_summary:
        summary_lines.append(f"Migration summary: {migration_summary}")

    sb_before = report.get("springBootVersionBefore")
    sb_after = report.get("springBootVersionAfter")
    if sb_before or sb_after:
        summary_lines.append(
            f"Spring Boot version changed from {_clean(sb_before, 'unknown')} "
            f"to {_clean(sb_after, 'unknown')}."
        )

    src_fw = _clean(report.get("springSourceFramework"), "")
    tgt_fw = _clean(report.get("springTargetFramework"), "")
    if src_fw or tgt_fw:
        summary_lines.append(
            f"Framework migration: from {src_fw or 'unknown'} to {tgt_fw or 'unknown'}."
        )

    build_status = _clean(report.get("buildStatus"), "")
    if build_status:
        summary_lines.append(
            f"Post-migration build status: {build_status} "
            f"(build success: {_yes_no(report.get('buildSuccess'))})."
        )
    if report.get("alreadyCompatible"):
        summary_lines.append(
            "The project was already compatible; little or no change was required."
        )
    if summary_lines:
        chunks.append(KnowledgeChunk("migration_summary", " ".join(summary_lines)))

    # --- Modified files ----------------------------------------------------- #
    files_modified = int(report.get("filesModified") or 0)
    modified_files = [str(f).strip() for f in (report.get("modifiedFiles") or []) if str(f).strip()]
    if files_modified or modified_files:
        count = files_modified or len(modified_files)
        modified_lines = [f"The migration modified {count} file(s)."]
        if modified_files:
            shown = modified_files[:_MAX_LISTED_FILES]
            modified_lines.append("Modified files:")
            modified_lines.extend(f"- {path}" for path in shown)
            remaining = len(modified_files) - len(shown)
            if remaining > 0:
                modified_lines.append(f"- ...and {remaining} more file(s).")
        chunks.append(KnowledgeChunk("modified_files", _truncate("\n".join(modified_lines))))
    else:
        chunks.append(
            KnowledgeChunk(
                "modified_files",
                "No files were reported as modified by this migration.",
            )
        )

    # --- Code changes (imports + source) ------------------------------------ #
    import_changes = [c for c in (report.get("importChanges") or []) if isinstance(c, dict)]
    source_changes = [c for c in (report.get("sourceChanges") or []) if isinstance(c, dict)]
    if import_changes or source_changes:
        change_lines: list[str] = []
        if import_changes:
            change_lines.append(
                f"Java import statements changed in {len(import_changes)} file(s)."
            )
            for change in import_changes[:_MAX_LISTED_FILES]:
                file = _clean(change.get("file"), "unknown file")
                added = [str(i).strip() for i in (change.get("added") or []) if str(i).strip()]
                removed = [str(i).strip() for i in (change.get("removed") or []) if str(i).strip()]
                parts = []
                if added:
                    parts.append(f"added {', '.join(added)}")
                if removed:
                    parts.append(f"removed {', '.join(removed)}")
                if parts:
                    change_lines.append(f"- {file}: {'; '.join(parts)}.")
        if source_changes:
            total_lines = sum(int(c.get("linesChanged") or 0) for c in source_changes)
            change_lines.append(
                f"Source code changed in {len(source_changes)} file(s), "
                f"about {total_lines} line(s) in total."
            )
            for change in source_changes[:_MAX_LISTED_FILES]:
                file = _clean(change.get("file"), "unknown file")
                change_lines.append(f"- {file}: {int(change.get('linesChanged') or 0)} line(s) changed.")
        chunks.append(KnowledgeChunk("code_changes", _truncate("\n".join(change_lines))))

    # --- Dependency upgrades ------------------------------------------------ #
    dependency_upgrades = [
        d for d in (report.get("dependencyUpgrades") or []) if isinstance(d, dict)
    ]
    if dependency_upgrades:
        upgrade_lines = [
            f"The migration upgraded {len(dependency_upgrades)} dependency/dependencies:"
        ]
        for upgrade in dependency_upgrades:
            coord = _clean(upgrade.get("coordinate"), "unknown")
            old_version = _clean(upgrade.get("oldVersion"), "unknown")
            new_version = _clean(upgrade.get("newVersion"), "unknown")
            upgrade_lines.append(f"- {coord}: {old_version} -> {new_version}")
        chunks.append(KnowledgeChunk("dependency_upgrades", "\n".join(upgrade_lines)))

    return chunks


import re

def chunk_java_file(content: str, file_path: str, version: str) -> list[KnowledgeChunk]:
    """Perform logical class-and-method code-aware chunking for Java files."""
    lines = content.splitlines()
    if not lines:
        return []
    chunks = []
    
    # 1. Extract package and imports
    package_imports_lines = []
    first_class_line_idx = -1
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Check for class, interface, enum, or annotation declaration
        if ("class " in stripped or "interface " in stripped or "enum " in stripped or stripped.startswith("@")):
            # Make sure it's not an import, package, or comment line
            if not (stripped.startswith("import ") or stripped.startswith("package ") or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")):
                first_class_line_idx = idx
                break
        if stripped.startswith("package ") or stripped.startswith("import "):
            package_imports_lines.append(line)
            
    header = "\n".join(package_imports_lines) if package_imports_lines else ""
    
    # If no class declaration was found, index the whole file
    if first_class_line_idx == -1:
        chunks.append(KnowledgeChunk(
            chunk_type="code_file",
            text=content,
            metadata={
                "file_path": file_path,
                "version": version,
                "start_line": 1,
                "end_line": len(lines)
            }
        ))
        return chunks

    # 2. Heuristically parse class and methods via bracket-matching
    bracket_count = 0
    in_class = False
    class_name = "UnknownClass"
    current_block_lines = []
    block_start_line = 1
    
    for idx in range(first_class_line_idx, len(lines)):
        line = lines[idx]
        current_block_lines.append(line)
        
        # Simple clean line ignoring brackets inside strings or comments
        clean_line = line
        if "//" in clean_line:
            clean_line = clean_line.split("//")[0]
        clean_line = re.sub(r'".*?"', '""', clean_line)
        clean_line = re.sub(r"'.*?'", "''", clean_line)
        
        open_brackets = clean_line.count("{")
        close_brackets = clean_line.count("}")
        
        if not in_class:
            class_match = re.search(r'(?:class|interface|enum)\s+([A-Za-z0-9_]+)', line)
            if class_match:
                class_name = class_match.group(1)
                in_class = True
                
        bracket_count += open_brackets - close_brackets
        
        if bracket_count <= 0 and in_class:
            text = (header + "\n" + "\n".join(current_block_lines)).strip()
            chunks.append(KnowledgeChunk(
                chunk_type="java_class",
                text=text,
                metadata={
                    "file_path": file_path,
                    "version": version,
                    "class_name": class_name,
                    "start_line": block_start_line,
                    "end_line": idx + 1
                }
            ))
            current_block_lines = []
            block_start_line = idx + 2
            in_class = False
            bracket_count = 0
        elif in_class and bracket_count == 1 and close_brackets > 0:
            text = (header + "\n" + "\n".join(current_block_lines)).strip()
            method_name = "unknown"
            for bline in current_block_lines:
                m = re.search(r'([A-Za-z0-9_]+)\s*\([^)]*\)\s*(?:throws\s+[A-Za-z0-9_,\s]+)?\s*\{', bline)
                if m:
                    method_name = m.group(1)
                    break
            chunks.append(KnowledgeChunk(
                chunk_type="java_method",
                text=text,
                metadata={
                    "file_path": file_path,
                    "version": version,
                    "class_name": class_name,
                    "method_name": method_name,
                    "start_line": block_start_line,
                    "end_line": idx + 1
                }
            ))
            current_block_lines = []
            block_start_line = idx + 2
            
    if current_block_lines:
        text = (header + "\n" + "\n".join(current_block_lines)).strip()
        chunks.append(KnowledgeChunk(
            chunk_type="java_class" if in_class else "code_file",
            text=text,
            metadata={
                "file_path": file_path,
                "version": version,
                "class_name": class_name if in_class else None,
                "start_line": block_start_line,
                "end_line": len(lines)
            }
        ))
        
    return chunks


def chunk_text_file(content: str, file_path: str, version: str, chunk_type: str = "code_file") -> list[KnowledgeChunk]:
    """Chunk yml, properties, readme, or configuration files into overlapping line-blocks."""
    lines = content.splitlines()
    if not lines:
        return []
    if len(lines) <= 60:
        return [KnowledgeChunk(
            chunk_type=chunk_type,
            text=content,
            metadata={
                "file_path": file_path,
                "version": version,
                "start_line": 1,
                "end_line": len(lines)
            }
        )]
        
    chunks = []
    chunk_size = 40
    overlap = 10
    i = 0
    while i < len(lines):
        end = min(i + chunk_size, len(lines))
        chunk_lines = lines[i:end]
        text = "\n".join(chunk_lines).strip()
        if text:
            chunks.append(KnowledgeChunk(
                chunk_type=chunk_type,
                text=text,
                metadata={
                    "file_path": file_path,
                    "version": version,
                    "start_line": i + 1,
                    "end_line": end
                }
            ))
        i += chunk_size - overlap
    return chunks

