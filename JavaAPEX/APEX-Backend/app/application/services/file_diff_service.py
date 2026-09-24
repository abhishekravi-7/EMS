"""Provides detailed side-by-side diffs and content for changed files.
"""

from __future__ import annotations

import difflib
import logging
from pathlib import Path
from typing import Any

from app.infrastructure.workspace.workspace_paths import WorkspacePaths
from app.shared import file_utils

logger = logging.getLogger(__name__)

class FileDiffService:
    def get_changed_files_summary(self, job_id: str, report: dict[str, Any]) -> list[dict[str, Any]]:
        """Return a list of changed files with metadata (no content)."""
        paths = WorkspacePaths(job_id)
        original_root = paths.original_repo_dir
        migrated_root = paths.migrated_repo_dir

        all_changed = list(report.get("modifiedFiles") or [])
        if not all_changed and original_root.exists() and migrated_root.exists():
            added, removed, modified = file_utils.diff_relative_files(original_root, migrated_root)
            all_changed = sorted({*added, *removed, *modified})

        # Gather UI transformations (JSP/JSF -> React/Angular)
        ui_transformations = report.get("uiTransformations") or []
        ui_source_files = set()
        ui_target_files = set()
        for t in ui_transformations:
            sf = (t.get("sourceFile") or t.get("file") or "").replace("\\", "/")
            tf = (t.get("targetSourceFile") or "").replace("\\", "/")
            if sf:
                ui_source_files.add(sf)
                ui_source_files.add(Path(sf).name)
            if tf:
                ui_target_files.add(tf)
                ui_target_files.add(Path(tf).name)

        results = []
        for rel_path in all_changed:
            norm_rel = rel_path.replace("\\", "/")
            # Avoid displaying unlinked JSP or raw generated target as standalone
            # diffs if they are already represented in uiTransformations.
            if norm_rel in ui_source_files or Path(norm_rel).name in ui_source_files:
                continue
            if norm_rel in ui_target_files or Path(norm_rel).name in ui_target_files:
                continue
            if "frontend/src/components" in norm_rel and ui_transformations:
                continue

            orig_path = original_root / rel_path
            mig_path = migrated_root / rel_path

            change_type = "MODIFIED"
            added_lines = 0
            removed_lines = 0

            if not orig_path.exists():
                change_type = "ADDED"
                if mig_path.exists():
                    added_lines = len(file_utils.read_text(mig_path).splitlines())
            elif not mig_path.exists():
                change_type = "DELETED"
                removed_lines = len(file_utils.read_text(orig_path).splitlines())
            else:
                # MODIFIED: calculate light diff for counts
                before_lines = file_utils.read_text(orig_path).splitlines()
                after_lines = file_utils.read_text(mig_path).splitlines()
                diff = list(difflib.unified_diff(before_lines, after_lines, lineterm=""))
                added_lines = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
                removed_lines = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

            label = self._get_label(rel_path, report)

            results.append({
                "relativePath": rel_path,
                "fileName": Path(rel_path).name,
                "changeType": change_type,
                "label": label,
                "addedLineCount": added_lines,
                "removedLineCount": removed_lines,
            })

        # Append all UI migration transformations into the changed files list
        for t in ui_transformations:
            source_file = t.get("sourceFile") or t.get("file") or ""
            target_file = t.get("targetSourceFile") or t.get("file") or ""
            results.append({
                "relativePath": source_file,
                "fileName": target_file if target_file else Path(source_file).name,
                "changeType": "ADDED",
                "label": t.get("category") or "UI Modernization",
                "addedLineCount": t.get("additions", len(t.get("afterLines") or [])),
                "removedLineCount": t.get("deletions", len(t.get("beforeLines") or [])),
                "sourceFile": source_file,
                "targetFile": target_file,
                "beforeLines": t.get("beforeLines") or [],
                "afterLines": t.get("afterLines") or [],
                "category": t.get("category") or "",
                "icon": t.get("icon") or "⚛️",
                "status": t.get("status") or "Added",
            })

        return sorted(results, key=lambda x: x["relativePath"])

    def get_file_diff(self, job_id: str, rel_path: str) -> dict[str, Any] | None:
        """Return the before/after line-by-line diff for a specific file."""
        paths = WorkspacePaths(job_id)
        try:
            if ".." in rel_path or rel_path.startswith("/"):
                 return None

            # First, check if rel_path matches an existing UI transformation record
            from app.application.services.status_service import MigrationReportStore
            report = MigrationReportStore(paths).read() or {}
            norm_rel = rel_path.replace("\\", "/").lower()
            rel_name = Path(rel_path).name.lower()

            for ui_t in report.get("uiTransformations") or []:
                sf = (ui_t.get("sourceFile") or "").replace("\\", "/").lower()
                tf = (ui_t.get("targetSourceFile") or "").replace("\\", "/").lower()
                fn = (ui_t.get("file") or "").replace("\\", "/").lower()
                if (
                    norm_rel in (sf, tf, fn)
                    or rel_name in (Path(sf).name, Path(tf).name, Path(fn).name)
                ):
                    return {
                        "relativePath": ui_t.get("sourceFile") or ui_t.get("file") or rel_path,
                        "fileName": ui_t.get("targetSourceFile") or ui_t.get("file") or rel_name,
                        "beforeLines": ui_t.get("beforeLines") or [],
                        "afterLines": ui_t.get("afterLines") or [],
                        "addedLineCount": ui_t.get("additions", len(ui_t.get("afterLines") or [])),
                        "removedLineCount": ui_t.get("deletions", len(ui_t.get("beforeLines") or [])),
                        "category": ui_t.get("category") or "",
                        "icon": ui_t.get("icon") or "⚛️",
                        "status": ui_t.get("status") or "Added",
                    }

            original_root = paths.original_repo_dir
            migrated_root = paths.migrated_repo_dir

            orig_path = original_root / rel_path
            mig_path = migrated_root / rel_path

            if not orig_path.exists() and not mig_path.exists():
                return None

            before_content = file_utils.read_text(orig_path) if orig_path.exists() else ""
            after_content = file_utils.read_text(mig_path) if mig_path.exists() else ""

            before_lines_raw = before_content.splitlines()
            after_lines_raw = after_content.splitlines()

            # Use SequenceMatcher for better alignment in side-by-side view
            sm = difflib.SequenceMatcher(None, before_lines_raw, after_lines_raw)

            before_lines = []
            after_lines = []

            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'equal':
                    for i in range(i1, i2):
                        before_lines.append({"num": i + 1, "text": before_lines_raw[i], "type": "normal"})
                    for j in range(j1, j2):
                        after_lines.append({"num": j + 1, "text": after_lines_raw[j], "type": "normal"})
                elif tag == 'replace':
                    for i in range(i1, i2):
                        before_lines.append({"num": i + 1, "text": before_lines_raw[i], "type": "removed"})
                    for j in range(j1, j2):
                        after_lines.append({"num": j + 1, "text": after_lines_raw[j], "type": "added"})
                elif tag == 'delete':
                    for i in range(i1, i2):
                        before_lines.append({"num": i + 1, "text": before_lines_raw[i], "type": "removed"})
                elif tag == 'insert':
                    for j in range(j1, j2):
                        after_lines.append({"num": j + 1, "text": after_lines_raw[j], "type": "added"})

            return {
                "relativePath": rel_path,
                "beforeLines": before_lines,
                "afterLines": after_lines,
                "addedLineCount": sum(1 for l in after_lines if l["type"] == "added"),
                "removedLineCount": sum(1 for l in before_lines if l["type"] == "removed"),
            }
        except Exception as e:
            logger.error("Error generating diff for %s: %s", rel_path, e)
            return None

    def _get_label(self, rel_path: str, report: dict[str, Any]) -> str:
        """Determine a transformation label based on evidence."""
        lower_rel = rel_path.lower().replace("\\", "/")
        if lower_rel.endswith("pom.xml") or lower_rel.endswith("build.gradle") or lower_rel.endswith("build.gradle.kts"):
            return "Build Config"

        # Check rule executions
        rule_executions = report.get("ruleExecutions") or []
        for exec_report in rule_executions:
            msg = exec_report.get("message", "")
            if rel_path in msg or rel_path in exec_report.get("filePath", ""):
                rid = exec_report.get("ruleId", "").upper()
                if "JUNIT" in rid:
                    return "JUnit 4 -> 5"
                if "JAKARTA" in rid or "JAVAX" in rid:
                    return "Jakarta EE"
                if "SPRING" in rid or "BOOT" in rid:
                    return "Spring Boot"
                if "SYNTAX" in rid or "JAVA" in rid:
                    return "Java Modernization"

        import_changes = report.get("importChanges") or []
        for ic in import_changes:
            if ic.get("file") == rel_path:
                added = ic.get("added") or []
                if any("jakarta" in str(a) for a in added):
                    return "Jakarta EE"
                return "Package Refactoring"

        if lower_rel.endswith(".java"):
            return "Source Migration"

        return "Modified"
