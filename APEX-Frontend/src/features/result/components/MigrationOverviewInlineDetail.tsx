import React, { useState, useMemo, useEffect } from "react";
import {
  FaFileAlt,
  FaCode,
  FaShieldAlt,
  FaSearch,
  FaCheckCircle,
} from "react-icons/fa";
import type { MigrationResult } from "../services/resultService";
import { getMigrationFileDiff } from "../services/resultService";
import type { PreviewFileDiff } from "@/features/modernization/services/modernizationService";
import "./MigrationOverviewInlineDetail.css";

export type OverviewDetailCategory = "files" | "transformations" | "dependencies";

export interface NormalizedDependencyItem {
  group_id: string;
  artifact_id: string;
  current_version: string;
  new_version: string;
  status: string;
  reason?: string;
  scope?: string;
}

export interface MigrationOverviewInlineDetailProps {
  category: OverviewDetailCategory;
  migrationJob: MigrationResult | null;
  dependencyUpdates?: NormalizedDependencyItem[];
}

interface DiffDisplayRow {
  beforeNum?: number | string;
  afterNum?: number | string;
  sign: string;
  type: "normal" | "added" | "removed";
  text: string;
}

function buildDiffDisplayRows(
  beforeLines: Array<{ num: number; text: string; type: string }>,
  afterLines: Array<{ num: number; text: string; type: string }>
): DiffDisplayRow[] {
  if ((!beforeLines || beforeLines.length === 0) && (!afterLines || afterLines.length === 0)) {
    return [];
  }

  if (!beforeLines || beforeLines.length === 0) {
    return (afterLines || []).map((l) => ({
      afterNum: l.num,
      sign: "+",
      type: "added",
      text: l.text,
    }));
  }

  if (!afterLines || afterLines.length === 0) {
    return (beforeLines || []).map((l) => ({
      beforeNum: l.num,
      sign: "-",
      type: "removed",
      text: l.text,
    }));
  }

  let bIdx = 0;
  let aIdx = 0;
  const rows: DiffDisplayRow[] = [];

  while (bIdx < beforeLines.length || aIdx < afterLines.length) {
    const b = beforeLines[bIdx];
    const a = afterLines[aIdx];

    if (b && b.type === "normal" && a && a.type === "normal") {
      rows.push({
        beforeNum: b.num,
        afterNum: a.num,
        sign: " ",
        type: "normal",
        text: a.text,
      });
      bIdx++;
      aIdx++;
    } else if (b && b.type === "removed") {
      rows.push({
        beforeNum: b.num,
        sign: "-",
        type: "removed",
        text: b.text,
      });
      bIdx++;
    } else if (a && a.type === "added") {
      rows.push({
        afterNum: a.num,
        sign: "+",
        type: "added",
        text: a.text,
      });
      aIdx++;
    } else if (b && !a) {
      rows.push({
        beforeNum: b.num,
        sign: b.type === "removed" ? "-" : " ",
        type: b.type === "removed" ? "removed" : "normal",
        text: b.text,
      });
      bIdx++;
    } else if (a && !b) {
      rows.push({
        afterNum: a.num,
        sign: a.type === "added" ? "+" : " ",
        type: a.type === "added" ? "added" : "normal",
        text: a.text,
      });
      aIdx++;
    } else {
      if (b) {
        rows.push({
          beforeNum: b.num,
          sign: b.type === "removed" ? "-" : " ",
          type: (b.type as any) || "normal",
          text: b.text,
        });
        bIdx++;
      }
      if (a) {
        rows.push({
          afterNum: a.num,
          sign: a.type === "added" ? "+" : " ",
          type: (a.type as any) || "normal",
          text: a.text,
        });
        aIdx++;
      }
    }
  }

  return rows;
}

export const MigrationOverviewInlineDetail: React.FC<MigrationOverviewInlineDetailProps> = ({
  category,
  migrationJob,
  dependencyUpdates = [],
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [diffCache, setDiffCache] = useState<
    Record<
      string,
      {
        beforeLines: Array<{ num: number; text: string; type: string }>;
        afterLines: Array<{ num: number; text: string; type: string }>;
        additions?: number;
        deletions?: number;
      }
    >
  >({});
  const [loadingDiffPath, setLoadingDiffPath] = useState<string | null>(null);

  // ==========================================
  // 1. FILES MODIFIED DATA (TABLE VIEW)
  // ==========================================
  const filesList = useMemo(() => {
    if (!migrationJob) return [];

    if (migrationJob.file_diffs && migrationJob.file_diffs.length > 0) {
      return migrationJob.file_diffs.map((diff: PreviewFileDiff) => {
        const relPath = diff.relativePath || diff.fileName || "";
        const parts = relPath.split(/[/\\]/);
        const fileName = diff.fileName || parts[parts.length - 1] || relPath;
        const ext = fileName.includes(".") ? fileName.split(".").pop()?.toUpperCase() || "" : "";
        return {
          path: relPath,
          fileName,
          extension: ext ? `.${ext}` : "FILE",
          status: (diff.changeType || "MODIFIED").toUpperCase(),
          additions: diff.addedLineCount ?? 0,
          deletions: diff.removedLineCount ?? 0,
          label: diff.label,
        };
      });
    }

    if (migrationJob.modified_files && migrationJob.modified_files.length > 0) {
      return migrationJob.modified_files.map((filePath: string) => {
        const parts = filePath.split(/[/\\]/);
        const fileName = parts[parts.length - 1] || filePath;
        const ext = fileName.includes(".") ? fileName.split(".").pop()?.toUpperCase() || "" : "";
        return {
          path: filePath,
          fileName,
          extension: ext ? `.${ext}` : "FILE",
          status: "MODIFIED",
          additions: 0,
          deletions: 0,
          label: undefined,
        };
      });
    }

    return [];
  }, [migrationJob]);

  const filteredFiles = useMemo(() => {
    if (!searchQuery.trim()) return filesList;
    const q = searchQuery.toLowerCase();
    return filesList.filter(
      (f) => f.path.toLowerCase().includes(q) || f.fileName.toLowerCase().includes(q)
    );
  }, [filesList, searchQuery]);

  // ==========================================
  // 2. CODE TRANSMISSION / CHANGED FILES DATA
  // ==========================================
  const changedFilesList = useMemo(() => {
    if (!migrationJob) return [];
    const fileMap = new Map<
      string,
      {
        path: string;
        fileName: string;
        status: "Modified" | "Added" | "Removed";
        additions: number;
        deletions: number;
        label?: string;
        beforeLines?: Array<{ num: number; text: string; type: string }>;
        afterLines?: Array<{ num: number; text: string; type: string }>;
      }
    >();

    // 1. file_diffs from report
    if (migrationJob.file_diffs && migrationJob.file_diffs.length > 0) {
      migrationJob.file_diffs.forEach((diff: any) => {
        const relPath = diff.relativePath || diff.fileName || diff.file_path || "";
        if (!relPath) return;
        const parts = relPath.split(/[/\\]/);
        const fileName = diff.fileName || parts[parts.length - 1] || relPath;
        const rawType = (diff.changeType || diff.status || diff.type || "MODIFIED").toUpperCase();
        const status: "Modified" | "Added" | "Removed" =
          rawType === "ADDED" || rawType === "CREATED"
            ? "Added"
            : rawType === "DELETED" || rawType === "REMOVED"
            ? "Removed"
            : "Modified";
        const additions = diff.addedLineCount ?? diff.additions ?? 0;
        const deletions = diff.removedLineCount ?? diff.deletions ?? 0;

        let beforeLines = diff.beforeLines;
        let afterLines = diff.afterLines;
        if (!beforeLines && !afterLines && (diff.old_content != null || diff.new_content != null)) {
          if (diff.old_content) {
            beforeLines = diff.old_content
              .split("\n")
              .map((t: string, i: number) => ({ num: i + 1, text: t, type: "removed" }));
          }
          if (diff.new_content) {
            afterLines = diff.new_content
              .split("\n")
              .map((t: string, i: number) => ({ num: i + 1, text: t, type: "added" }));
          }
        }

        fileMap.set(relPath, {
          path: relPath,
          fileName,
          status,
          additions,
          deletions,
          label: diff.label,
          beforeLines,
          afterLines,
        });
      });
    }

    // 2. modified_files list
    if (migrationJob.modified_files && migrationJob.modified_files.length > 0) {
      migrationJob.modified_files.forEach((filePath: string) => {
        if (!filePath || fileMap.has(filePath)) return;
        const parts = filePath.split(/[/\\]/);
        const fileName = parts[parts.length - 1] || filePath;
        fileMap.set(filePath, {
          path: filePath,
          fileName,
          status: "Modified",
          additions: 0,
          deletions: 0,
        });
      });
    }

    // 3. import_changes
    if (migrationJob.import_changes && migrationJob.import_changes.length > 0) {
      migrationJob.import_changes.forEach((ic: any) => {
        const filePath = ic.file;
        if (!filePath) return;
        const parts = filePath.split(/[/\\]/);
        const fileName = parts[parts.length - 1] || filePath;
        const added = ic.added || [];
        const removed = ic.removed || [];
        if (!fileMap.has(filePath)) {
          fileMap.set(filePath, {
            path: filePath,
            fileName,
            status: "Modified",
            additions: added.length,
            deletions: removed.length,
            beforeLines: removed.map((r: string, i: number) => ({
              num: i + 1,
              text: `import ${r};`,
              type: "removed",
            })),
            afterLines: added.map((a: string, i: number) => ({
              num: i + 1,
              text: `import ${a};`,
              type: "added",
            })),
          });
        }
      });
    }

    // 4. source_changes
    if (migrationJob.source_changes && migrationJob.source_changes.length > 0) {
      migrationJob.source_changes.forEach((sc: any) => {
        const filePath = sc.file;
        if (!filePath || fileMap.has(filePath)) return;
        const parts = filePath.split(/[/\\]/);
        const fileName = parts[parts.length - 1] || filePath;
        fileMap.set(filePath, {
          path: filePath,
          fileName,
          status: "Modified",
          additions: sc.linesChanged ?? sc.lines_changed ?? 0,
          deletions: 0,
        });
      });
    }

    // 5. issues
    if (migrationJob.issues && migrationJob.issues.length > 0) {
      migrationJob.issues.forEach((issue: any) => {
        const filePath = issue.file_path;
        if (!filePath || filePath === "Project source" || fileMap.has(filePath)) return;
        const parts = filePath.split(/[/\\]/);
        const fileName = parts[parts.length - 1] || filePath;
        fileMap.set(filePath, {
          path: filePath,
          fileName,
          status: "Modified",
          additions: issue.suggested_fix ? issue.suggested_fix.split("\n").length : 0,
          deletions: issue.code_snippet ? issue.code_snippet.split("\n").length : 0,
          beforeLines: issue.code_snippet
            ? issue.code_snippet
                .split("\n")
                .map((t: string, i: number) => ({
                  num: (issue.line_number || 1) + i,
                  text: t,
                  type: "removed",
                }))
            : undefined,
          afterLines: issue.suggested_fix
            ? issue.suggested_fix
                .split("\n")
                .map((t: string, i: number) => ({
                  num: (issue.line_number || 1) + i,
                  text: t,
                  type: "added",
                }))
            : undefined,
        });
      });
    }

    return Array.from(fileMap.values());
  }, [migrationJob]);

  const modifiedCount = useMemo(
    () => changedFilesList.filter((f) => f.status === "Modified").length,
    [changedFilesList]
  );
  const addedCount = useMemo(
    () => changedFilesList.filter((f) => f.status === "Added").length,
    [changedFilesList]
  );
  const removedCount = useMemo(
    () => changedFilesList.filter((f) => f.status === "Removed").length,
    [changedFilesList]
  );

  const filteredChangedFiles = useMemo(() => {
    if (!searchQuery.trim()) return changedFilesList;
    const q = searchQuery.toLowerCase();
    return changedFilesList.filter(
      (f) => f.path.toLowerCase().includes(q) || f.fileName.toLowerCase().includes(q)
    );
  }, [changedFilesList, searchQuery]);

  // Keep selection synchronized with current list
  useEffect(() => {
    if (filteredChangedFiles.length > 0) {
      const stillExists = filteredChangedFiles.some((f) => f.path === selectedFilePath);
      if (!stillExists) {
        setSelectedFilePath(filteredChangedFiles[0].path);
      }
    }
  }, [filteredChangedFiles, selectedFilePath]);

  const activeFile = useMemo(() => {
    if (filteredChangedFiles.length === 0) return null;
    return (
      filteredChangedFiles.find((f) => f.path === selectedFilePath) ||
      filteredChangedFiles[0]
    );
  }, [filteredChangedFiles, selectedFilePath]);

  // Async diff fetcher for active file
  useEffect(() => {
    if (!activeFile || !migrationJob?.job_id) return;
    const filePath = activeFile.path;

    if (
      diffCache[filePath] ||
      (activeFile.beforeLines && activeFile.beforeLines.length > 0) ||
      (activeFile.afterLines && activeFile.afterLines.length > 0)
    ) {
      return;
    }

    setLoadingDiffPath(filePath);
    getMigrationFileDiff(migrationJob.job_id, filePath)
      .then((res) => {
        if (res && (res.beforeLines || res.afterLines)) {
          setDiffCache((prev) => ({
            ...prev,
            [filePath]: {
              beforeLines: res.beforeLines || [],
              afterLines: res.afterLines || [],
              additions: res.addedLineCount,
              deletions: res.removedLineCount,
            },
          }));
        }
      })
      .catch((err) => {
        console.warn("Could not load diff for", filePath, err);
      })
      .finally(() => {
        setLoadingDiffPath(null);
      });
  }, [activeFile, migrationJob?.job_id, diffCache]);

  const currentBeforeLines =
    diffCache[activeFile?.path || ""]?.beforeLines || activeFile?.beforeLines || [];
  const currentAfterLines =
    diffCache[activeFile?.path || ""]?.afterLines || activeFile?.afterLines || [];
  const currentAdditions =
    diffCache[activeFile?.path || ""]?.additions ?? activeFile?.additions ?? 0;
  const currentDeletions =
    diffCache[activeFile?.path || ""]?.deletions ?? activeFile?.deletions ?? 0;

  const diffRows = useMemo(() => {
    return buildDiffDisplayRows(currentBeforeLines, currentAfterLines);
  }, [currentBeforeLines, currentAfterLines]);

  // ==========================================
  // 3. DEPENDENCIES UPDATED DATA
  // ==========================================
  const rawDeps = useMemo(() => {
    if (dependencyUpdates && dependencyUpdates.length > 0) {
      return dependencyUpdates;
    }
    const fromJob = migrationJob?.dependency_upgrades || migrationJob?.dependencies || [];
    return fromJob.map((dep: any) => ({
      group_id: dep.group_id || dep.groupId || dep.coordinate?.split(":")[0] || "dependency",
      artifact_id: dep.artifact_id || dep.artifactId || dep.coordinate?.split(":")[1] || "artifact",
      current_version:
        dep.current_version ||
        dep.old_version ||
        dep.oldVersion ||
        dep.sourceVersion ||
        "managed version",
      new_version:
        dep.new_version ||
        dep.newVersion ||
        dep.resolvedTargetVersion ||
        "updated version",
      status: dep.status || "Updated",
      reason: dep.reason,
      scope: dep.scope,
    }));
  }, [dependencyUpdates, migrationJob]);

  const filteredDependencies = useMemo(() => {
    if (!searchQuery.trim()) return rawDeps;
    const q = searchQuery.toLowerCase();
    return rawDeps.filter(
      (d) =>
        d.group_id.toLowerCase().includes(q) ||
        d.artifact_id.toLowerCase().includes(q) ||
        d.current_version.toLowerCase().includes(q) ||
        d.new_version.toLowerCase().includes(q)
    );
  }, [rawDeps, searchQuery]);

  const categoryConfig = {
    files: {
      title: "Files Modified Details",
      icon: <FaFileAlt />,
      colorClass: "files",
      pillClass: "blue",
      countText: `${filesList.length} ${filesList.length === 1 ? "File" : "Files"}`,
      searchPlaceholder: "Search modified files...",
    },
    transformations: {
      title: "Changed Files",
      icon: <FaCode />,
      colorClass: "transformations",
      pillClass: "purple",
      countText: `${changedFilesList.length} ${
        changedFilesList.length === 1 ? "File" : "Files"
      }`,
      searchPlaceholder: "Search changed files...",
    },
    dependencies: {
      title: "Dependency Updates",
      icon: <FaShieldAlt />,
      colorClass: "dependencies",
      pillClass: "green",
      countText: `${rawDeps.length} Updated`,
      searchPlaceholder: "Search dependencies...",
    },
  }[category];

  return (
    <div className="moid-section-container">
      {/* Header */}
      <div className="moid-header">
        <div className="moid-header-left">
          <div className={`moid-icon-box ${categoryConfig.colorClass}`}>
            {categoryConfig.icon}
          </div>
          <h3 className="moid-title">
            {categoryConfig.title}
            <span className={`moid-count-pill ${categoryConfig.pillClass}`}>
              {categoryConfig.countText}
            </span>
          </h3>

          {/* If category is transformations (Code Transmission), show summary pills */}
          {category === "transformations" && (
            <div className="moid-summary-counts">
              <div className="moid-summary-pill modified">
                <span className="moid-pill-dot modified" />
                {modifiedCount} Modified
              </div>
              <div className="moid-summary-pill added">
                <span className="moid-pill-dot added" />
                {addedCount} Added
              </div>
              <div className="moid-summary-pill removed">
                <span className="moid-pill-dot removed" />
                {removedCount} Removed
              </div>
            </div>
          )}
        </div>

        <div className="moid-search-box">
          <FaSearch className="moid-search-icon" />
          <input
            type="text"
            className="moid-search-input"
            placeholder={categoryConfig.searchPlaceholder}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Table Content */}
      <div className="moid-table-wrap">
        {/* =================================================== */}
        {/* 1. FILES MODIFIED DETAILS                           */}
        {/* Columns: # | FILE NAME & PATH | TYPE | STATUS | CHANGES */}
        {/* =================================================== */}
        {category === "files" && (
          <table className="moid-table">
            <thead>
              <tr>
                <th style={{ width: 44 }}>#</th>
                <th>FILE NAME &amp; PATH</th>
                <th style={{ width: 100, textAlign: "center" }}>TYPE</th>
                <th style={{ width: 120, textAlign: "center" }}>STATUS</th>
                <th style={{ width: 120, textAlign: "right" }}>CHANGES</th>
              </tr>
            </thead>
            <tbody>
              {filteredFiles.length > 0 ? (
                filteredFiles.map((file, idx) => (
                  <tr
                    key={idx}
                    style={{
                      backgroundColor: idx % 2 === 0 ? "#ffffff" : "#fbfdff",
                    }}
                  >
                    <td style={{ color: "#94a3b8", fontWeight: 600 }}>{idx + 1}.</td>
                    <td>
                      <div className="moid-file-name">{file.fileName}</div>
                      <div className="moid-file-path">{file.path}</div>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className="moid-badge ext">{file.extension}</span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span
                        className={`moid-badge ${
                          file.status === "ADDED"
                            ? "added"
                            : file.status === "DELETED"
                            ? "deleted"
                            : "modified"
                        }`}
                      >
                        {file.status}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      {file.additions > 0 || file.deletions > 0 ? (
                        <span className="moid-churn">
                          {file.additions > 0 && (
                            <span className="add">+{file.additions}</span>
                          )}
                          {file.deletions > 0 && (
                            <span className="del">-{file.deletions}</span>
                          )}
                        </span>
                      ) : (
                        <span style={{ color: "#64748b", fontSize: 12, fontWeight: 600 }}>
                          MODIFIED
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr className="moid-empty-row">
                  <td colSpan={5}>
                    {searchQuery.trim()
                      ? `No modified files matched "${searchQuery}".`
                      : "No files were modified during migration."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}

        {/* =================================================== */}
        {/* 2. CODE TRANSMISSION: CHANGED FILES + CODE DIFF VIEW*/}
        {/* =================================================== */}
        {category === "transformations" && (
          <div className="moid-diff-viewer-grid">
            {/* Left Sidebar: Changed Files List */}
            <div className="moid-diff-sidebar">
              <div className="moid-diff-sidebar-header">
                <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                  Changed Files ({filteredChangedFiles.length})
                </div>
              </div>

              <div className="moid-diff-file-list">
                {filteredChangedFiles.length > 0 ? (
                  filteredChangedFiles.map((file, idx) => {
                    const isSelected = activeFile?.path === file.path;
                    return (
                      <div
                        key={idx}
                        className={`moid-diff-file-item ${isSelected ? "selected" : ""}`}
                        onClick={() => setSelectedFilePath(file.path)}
                      >
                        <div className="moid-diff-file-meta">
                          <FaFileAlt className="moid-diff-file-icon" />
                          <div className="moid-diff-file-text-col">
                            <span
                              className="moid-diff-file-name"
                              title={file.fileName}
                            >
                              {file.fileName}
                            </span>
                            {file.path && file.path !== file.fileName && (
                              <span
                                className="moid-diff-file-subpath"
                                title={file.path}
                              >
                                {file.path}
                              </span>
                            )}
                          </div>
                        </div>

                        <span
                          className={`moid-badge ${
                            file.status === "Modified"
                              ? "modified"
                              : file.status === "Added"
                              ? "added"
                              : "deleted"
                          }`}
                        >
                          {file.status}
                        </span>
                      </div>
                    );
                  })
                ) : (
                  <div style={{ padding: "32px 16px", textAlign: "center", color: "#94a3b8", fontSize: 13 }}>
                    {searchQuery.trim()
                      ? `No files matching "${searchQuery}"`
                      : "No changed files available"}
                  </div>
                )}
              </div>

              <div className="moid-diff-sidebar-footer">
                Click on a file to view code changes
              </div>
            </div>

            {/* Right: Code Changes / Diff View */}
            <div className="moid-diff-content-view">
              {activeFile ? (
                <>
                  {/* File Header */}
                  <div className="moid-diff-content-header">
                    <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                      <FaCode style={{ color: "#2563eb", fontSize: 16, flexShrink: 0 }} />
                      <h4
                        style={{
                          margin: 0,
                          fontSize: 14,
                          fontWeight: 700,
                          color: "#0f172a",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                        title={activeFile.path || activeFile.fileName}
                      >
                        {activeFile.fileName}
                      </h4>
                      <span
                        className={`moid-badge ${
                          activeFile.status === "Modified"
                            ? "modified"
                            : activeFile.status === "Added"
                            ? "added"
                            : "deleted"
                        }`}
                      >
                        {activeFile.status}
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 14, flexShrink: 0 }}>
                      <span style={{ color: "#059669", fontSize: 12, fontWeight: 700 }}>
                        +{currentAdditions} additions
                      </span>
                      <span style={{ color: "#dc2626", fontSize: 12, fontWeight: 700 }}>
                        -{currentDeletions} deletions
                      </span>
                    </div>
                  </div>

                  {/* Diff Table / Content Area */}
                  <div className="moid-diff-table-container">
                    {loadingDiffPath === activeFile.path ? (
                      <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 13 }}>
                        Loading code diff for {activeFile.fileName}...
                      </div>
                    ) : diffRows.length > 0 ? (
                      <table className="moid-diff-table">
                        <tbody>
                          {diffRows.map((line, idx) => {
                            const isRemoved = line.type === "removed";
                            const isAdded = line.type === "added";
                            const rowClass = isRemoved
                              ? "diff-row-removed"
                              : isAdded
                              ? "diff-row-added"
                              : "diff-row-normal";

                            return (
                              <tr key={idx} className={rowClass}>
                                <td className="diff-col-num">
                                  {line.beforeNum != null ? line.beforeNum : ""}
                                </td>
                                <td className="diff-col-num">
                                  {line.afterNum != null ? line.afterNum : ""}
                                </td>
                                <td className="diff-col-sign">{line.sign}</td>
                                <td className="diff-col-code">
                                  {line.text.replace(/^[+-]\s*/, "")}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    ) : (
                      <div style={{ padding: 48, textAlign: "center", color: "#94a3b8", fontStyle: "italic", fontSize: 13 }}>
                        No line-level changes recorded for this file.
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div style={{ padding: 60, textAlign: "center", color: "#94a3b8", fontStyle: "italic" }}>
                  Select a changed file from the list to view transformations.
                </div>
              )}
            </div>
          </div>
        )}

        {/* =================================================== */}
        {/* 3. DEPENDENCY UPDATES                               */}
        {/* Columns: # | DEPENDENCY | CURRENT VERSION | UPDATED VERSION | STATUS */}
        {/* =================================================== */}
        {category === "dependencies" && (
          <div className="moid-dependencies-scroll-container">
            <table className="moid-table moid-sticky-table">
              <thead>
                <tr>
                  <th style={{ width: 44 }}>#</th>
                  <th>DEPENDENCY</th>
                  <th style={{ textAlign: "center", width: 170 }}>CURRENT VERSION</th>
                  <th style={{ textAlign: "center", width: 170 }}>UPDATED VERSION</th>
                  <th style={{ width: 120, textAlign: "center" }}>STATUS</th>
                </tr>
              </thead>
              <tbody>
                {filteredDependencies.length > 0 ? (
                  filteredDependencies.map((dep, idx) => (
                    <tr
                      key={idx}
                      style={{
                        backgroundColor: idx % 2 === 0 ? "#ffffff" : "#fbfdff",
                      }}
                    >
                      <td style={{ color: "#94a3b8", fontWeight: 600 }}>{idx + 1}.</td>
                      <td>
                        <div style={{ fontWeight: 700, color: "#0f172a" }}>
                          {dep.group_id}:{dep.artifact_id}
                        </div>
                        {dep.reason && (
                          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                            {dep.reason}
                          </div>
                        )}
                      </td>
                      <td
                        style={{
                          textAlign: "center",
                          fontFamily: "'JetBrains Mono', monospace",
                          color: "#64748b",
                          fontSize: 14,
                        }}
                      >
                        {dep.current_version}
                      </td>
                      <td
                        style={{
                          textAlign: "center",
                          fontFamily: "'JetBrains Mono', monospace",
                          color: "#059669",
                          fontWeight: 700,
                          fontSize: 14,
                        }}
                      >
                        {dep.new_version}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <span className="moid-badge upgraded">
                          <FaCheckCircle style={{ fontSize: 10 }} />
                          {dep.status || "Updated"}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr className="moid-empty-row">
                    <td colSpan={5}>
                      {searchQuery.trim()
                        ? `No dependency entries matched "${searchQuery}".`
                        : "No dependency updates were recorded."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
