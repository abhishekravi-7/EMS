import React, { useState, useMemo, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  FaTimes,
  FaSearch,
  FaFileAlt,
  FaTools,
  FaLayerGroup,
  FaShieldAlt,
  FaCode,
  FaCheckCircle,
  FaExternalLinkAlt,
  FaCopy,
  FaCheck,
} from "react-icons/fa";

function CopyAllDependenciesButton({
  text,
  label = "Copy All",
  title = "Copy all dependencies to clipboard",
  style = {},
}: {
  text: string;
  label?: string;
  title?: string;
  style?: React.CSSProperties;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!text) return;
    void navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? "All dependencies copied!" : title}
      aria-label={copied ? "Copied All" : title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "6px 12px",
        borderRadius: "6px",
        border: "1px solid " + (copied ? "#86efac" : "#cbd5e1"),
        background: copied ? "#ecfdf5" : "#ffffff",
        color: copied ? "#166534" : "#1e293b",
        fontWeight: 600,
        fontSize: "12px",
        cursor: "pointer",
        flexShrink: 0,
        boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
        transition: "all 0.15s ease",
        ...style,
      }}
      onMouseEnter={(e) => {
        if (!copied) {
          e.currentTarget.style.background = "#f8fafc";
          e.currentTarget.style.borderColor = "#94a3b8";
        }
      }}
      onMouseLeave={(e) => {
        if (!copied) {
          e.currentTarget.style.background = "#ffffff";
          e.currentTarget.style.borderColor = "#cbd5e1";
        }
      }}
    >
      {copied ? <FaCheck size={12} style={{ color: "#166534" }} /> : <FaCopy size={12} />}
      <span>{copied ? "Copied All!" : label}</span>
    </button>
  );
}
import type { ReportDetailsResponse } from "../services/resultService";

interface MigrationReportDetailModalProps {
  isOpen: boolean;
  category: "files" | "issues" | "dependencies" | "vulnerabilities" | "transformations" | null;
  data: ReportDetailsResponse | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onSelectFileForDiff?: (filePath: string) => void;
}

const CATEGORY_CONFIG: Record<
  string,
  {
    title: string;
    singular: string;
    color: string;
    bg: string;
    icon: React.ReactNode;
    emptyText: string;
  }
> = {
  files: {
    title: "Files Modified",
    singular: "file",
    color: "#2563eb",
    bg: "#eff6ff",
    icon: <FaFileAlt />,
    emptyText: "No file details available for this migration.",
  },
  issues: {
    title: "Issues Fixed",
    singular: "issue",
    color: "#10b981",
    bg: "#ecfdf5",
    icon: <FaTools />,
    emptyText: "No issue details available.",
  },
  dependencies: {
    title: "Dependencies Updated",
    singular: "dependency",
    color: "#8b5cf6",
    bg: "#f5f3ff",
    icon: <FaLayerGroup />,
    emptyText: "No dependency update details available.",
  },
  vulnerabilities: {
    title: "Vulnerabilities",
    singular: "vulnerability",
    color: "#f97316",
    bg: "#fff7ed",
    icon: <FaShieldAlt />,
    emptyText: "No vulnerabilities found",
  },
  transformations: {
    title: "Code Transmission (Transformations)",
    singular: "transformation",
    color: "#7c3aed",
    bg: "#f5f3ff",
    icon: <FaCode />,
    emptyText: "No transformation details available.",
  },
};

export const MigrationReportDetailModal: React.FC<MigrationReportDetailModalProps> = ({
  isOpen,
  category,
  data,
  loading,
  error,
  onClose,
  onSelectFileForDiff,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [prevKey, setPrevKey] = useState<{ category: string | null; isOpen: boolean }>({ category: null, isOpen: false });
  if (prevKey.category !== category || prevKey.isOpen !== isOpen) {
    setPrevKey({ category, isOpen });
    if (searchQuery !== "") {
      setSearchQuery("");
    }
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const config = category ? CATEGORY_CONFIG[category] || CATEGORY_CONFIG.files : CATEGORY_CONFIG.files;
  const items = useMemo(() => data?.items || [], [data?.items]);

  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return items;
    const q = searchQuery.toLowerCase().trim();
    return items.filter((item) => {
      return Object.values(item).some((val) => {
        if (typeof val === "string") return val.toLowerCase().includes(q);
        if (typeof val === "number") return String(val).includes(q);
        return false;
      });
    });
  }, [items, searchQuery]);

  if (!isOpen || !category) return null;

  const modalContent = (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 99999,
        background: "rgba(15, 23, 42, 0.65)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        boxSizing: "border-box",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#ffffff",
          borderRadius: 16,
          maxWidth: 1050,
          width: "100%",
          maxHeight: "88vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 25px 80px rgba(0, 0, 0, 0.3)",
          border: "1px solid #e2e8f0",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "18px 24px",
            borderBottom: "1px solid #e2e8f0",
            background: "#ffffff",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: config.bg,
                color: config.color,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 20,
              }}
            >
              {config.icon}
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h3
                  style={{
                    margin: 0,
                    fontSize: 18,
                    fontWeight: 800,
                    color: "#0f172a",
                  }}
                >
                  {config.title}
                </h3>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    padding: "3px 10px",
                    borderRadius: 20,
                    background: config.bg,
                    color: config.color,
                    border: `1px solid ${config.color}30`,
                  }}
                >
                  {data?.total ?? items.length} {items.length === 1 ? config.singular : `${config.singular}s`}
                </span>
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2, fontWeight: 500 }}>
                Actual underlying records from migration result
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            {category === "dependencies" && items.length > 0 && (
              <CopyAllDependenciesButton
                text={items
                  .map((item: any) => `${item.name || `${item.group_id}:${item.artifact_id}`} (${item.old_version || item.current_version || ""} -> ${item.new_version || ""})`)
                  .join("\n")}
                label="Copy All"
              />
            )}
            {/* Search Input */}
            <div style={{ position: "relative", width: 260 }}>
              <input
                type="text"
                placeholder={`Search ${config.title.toLowerCase()}...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 14px 8px 36px",
                  borderRadius: 10,
                  border: "1px solid #cbd5e1",
                  fontSize: 13,
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
              <FaSearch
                style={{
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "#94a3b8",
                  fontSize: 13,
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  style={{
                    position: "absolute",
                    right: 8,
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    color: "#94a3b8",
                    cursor: "pointer",
                    padding: 4,
                  }}
                >
                  ✕
                </button>
              )}
            </div>

            {/* Close Button */}
            <button
              onClick={onClose}
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                background: "#f1f5f9",
                border: "none",
                color: "#64748b",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 14,
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#e2e8f0";
                e.currentTarget.style.color = "#0f172a";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#f1f5f9";
                e.currentTarget.style.color = "#64748b";
              }}
              aria-label="Close"
            >
              <FaTimes />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px", minHeight: 280 }}>
          {loading ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "60px 20px",
                color: "#64748b",
              }}
            >
              <div
                style={{
                  width: 36,
                  height: 36,
                  border: `3px solid ${config.color}20`,
                  borderTopColor: config.color,
                  borderRadius: "50%",
                  marginBottom: 16,
                }}
              />
              <span style={{ fontSize: 14, fontWeight: 600 }}>Loading migration records...</span>
            </div>
          ) : error ? (
            <div
              style={{
                padding: 40,
                textAlign: "center",
                color: "#dc2626",
                background: "#fef2f2",
                borderRadius: 12,
                margin: "20px 0",
              }}
            >
              <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>Error loading records</div>
              <div style={{ fontSize: 13 }}>{error}</div>
            </div>
          ) : items.length === 0 ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "60px 20px",
                textAlign: "center",
              }}
            >
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: "50%",
                  background: category === "vulnerabilities" ? "#ecfdf5" : "#f1f5f9",
                  color: category === "vulnerabilities" ? "#059669" : "#94a3b8",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 24,
                  marginBottom: 16,
                }}
              >
                {category === "vulnerabilities" ? <FaCheckCircle /> : config.icon}
              </div>
              <h4 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 700, color: "#1e293b" }}>
                {config.emptyText}
              </h4>
              <p style={{ margin: 0, fontSize: 13, color: "#64748b", maxWidth: 450, lineHeight: 1.5 }}>
                {category === "vulnerabilities"
                  ? "All security scans and dependency checks completed cleanly. Zero vulnerabilities detected."
                  : `No specific ${category} records were found in this migration's execution result.`}
              </p>
            </div>
          ) : filteredItems.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>
              <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>No matching records found</div>
              <div style={{ fontSize: 13 }}>No results matched &quot;{searchQuery}&quot;</div>
            </div>
          ) : (
            <>
              {/* Category-Specific Table Renderers */}
              {category === "files" && (
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #f1f5f9" }}>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 40 }}>#</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>File Path</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>File Name</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 110, textAlign: "center" }}>Change Type</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 130 }}>Line Changes</th>
                      {onSelectFileForDiff && (
                        <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 100, textAlign: "center" }}>Action</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item, idx) => {
                      const changeType = (item.change_type || item.status || "MODIFIED").toUpperCase();
                      const isAdded = changeType === "ADDED";
                      const isDeleted = changeType === "DELETED";
                      return (
                        <tr
                          key={idx}
                          style={{
                            borderBottom: "1px solid #f1f5f9",
                            background: idx % 2 === 0 ? "#ffffff" : "#fbfdff",
                          }}
                        >
                          <td style={{ padding: "12px 14px", fontSize: 12, color: "#94a3b8", fontWeight: 600 }}>{idx + 1}.</td>
                          <td style={{ padding: "12px 14px", fontSize: 13, color: "#0f172a", fontFamily: "monospace", wordBreak: "break-all" }}>
                            {item.path}
                          </td>
                          <td style={{ padding: "12px 14px", fontSize: 13, color: "#1e293b", fontWeight: 600 }}>
                            {item.file_name}
                          </td>
                          <td style={{ padding: "12px 14px", textAlign: "center" }}>
                            <span
                              style={{
                                fontSize: 11,
                                fontWeight: 700,
                                padding: "3px 8px",
                                borderRadius: 6,
                                background: isAdded ? "#dcfce7" : isDeleted ? "#fee2e2" : "#dbeafe",
                                color: isAdded ? "#059669" : isDeleted ? "#dc2626" : "#1d4ed8",
                              }}
                            >
                              {item.status || item.change_type}
                            </span>
                          </td>
                          <td style={{ padding: "12px 14px", fontSize: 12, fontWeight: 600 }}>
                            <span style={{ color: "#10b981" }}>+{item.additions ?? 0}</span>
                            <span style={{ color: "#ef4444", marginLeft: 8 }}>-{item.deletions ?? 0}</span>
                          </td>
                          {onSelectFileForDiff && (
                            <td style={{ padding: "12px 14px", textAlign: "center" }}>
                              <button
                                type="button"
                                onClick={() => {
                                  onSelectFileForDiff(item.path);
                                  onClose();
                                }}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 4,
                                  padding: "4px 10px",
                                  borderRadius: 6,
                                  background: "#eff6ff",
                                  border: "1px solid #bfdbfe",
                                  color: "#2563eb",
                                  fontSize: 11,
                                  fontWeight: 700,
                                  cursor: "pointer",
                                }}
                              >
                                <FaExternalLinkAlt size={10} /> View Diff
                              </button>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}

              {category === "issues" && (
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #f1f5f9" }}>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 40 }}>#</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 170 }}>Issue Type</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>File & Line</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Description</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 100, textAlign: "center" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item, idx) => (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: "1px solid #f1f5f9",
                          background: idx % 2 === 0 ? "#ffffff" : "#fbfdff",
                        }}
                      >
                        <td style={{ padding: "12px 14px", fontSize: 12, color: "#94a3b8", fontWeight: 600 }}>{idx + 1}.</td>
                        <td style={{ padding: "12px 14px", fontSize: 12, fontWeight: 700, color: "#0f172a" }}>
                          <span
                            style={{
                              background: "#ecfdf5",
                              color: "#059669",
                              padding: "2px 8px",
                              borderRadius: 4,
                              border: "1px solid #a7f3d0",
                            }}
                          >
                            {item.type || "Migration Issue"}
                          </span>
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 12, fontFamily: "monospace", color: "#334155", wordBreak: "break-all" }}>
                          {item.file}
                          {item.line && item.line > 0 && <span style={{ color: "#2563eb", fontWeight: 700 }}>:{item.line}</span>}
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 13, color: "#1e293b", lineHeight: 1.4 }}>
                          <div>{item.description}</div>
                          {item.fix && (
                            <div style={{ fontSize: 11, color: "#059669", fontWeight: 600, marginTop: 2 }}>
                              Fix: {item.fix}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "12px 14px", textAlign: "center" }}>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              padding: "3px 8px",
                              borderRadius: 6,
                              background: "#dcfce7",
                              color: "#059669",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                            }}
                          >
                            <FaCheckCircle size={10} />
                            {item.status || "fixed"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {category === "dependencies" && (
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #f1f5f9" }}>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 40 }}>#</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Dependency</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", textAlign: "center" }}>Old Version</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", textAlign: "center" }}>New Version</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 120 }}>File</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 100, textAlign: "center" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item, idx) => (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: "1px solid #f1f5f9",
                          background: idx % 2 === 0 ? "#ffffff" : "#fbfdff",
                        }}
                      >
                        <td style={{ padding: "12px 14px", fontSize: 12, color: "#94a3b8", fontWeight: 600 }}>{idx + 1}.</td>
                        <td style={{ padding: "12px 14px", fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                          {item.name}
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 13, color: "#64748b", textAlign: "center" }}>
                          {item.old_version}
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 13, color: "#059669", fontWeight: 700, textAlign: "center" }}>
                          {item.new_version}
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 12, fontFamily: "monospace", color: "#64748b" }}>
                          {item.file || "pom.xml"}
                        </td>
                        <td style={{ padding: "12px 14px", textAlign: "center" }}>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              padding: "3px 8px",
                              borderRadius: 6,
                              background: "#ecfdf5",
                              color: "#059669",
                              border: "1px solid #a7f3d0",
                            }}
                          >
                            {item.status || "UPGRADED"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {category === "vulnerabilities" && (
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #f1f5f9" }}>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 40 }}>#</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Package / Component</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Identifier / Rule</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", textAlign: "center" }}>Severity</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", textAlign: "center" }}>Affected</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", textAlign: "center" }}>Fixed In</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item, idx) => (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: "1px solid #f1f5f9",
                          background: idx % 2 === 0 ? "#ffffff" : "#fbfdff",
                        }}
                      >
                        <td style={{ padding: "12px 14px", fontSize: 12, color: "#94a3b8", fontWeight: 600 }}>{idx + 1}.</td>
                        <td style={{ padding: "12px 14px", fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                          {item.package}
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 12, fontFamily: "monospace", color: "#334155" }}>
                          {item.identifier}
                        </td>
                        <td style={{ padding: "12px 14px", textAlign: "center" }}>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              padding: "3px 8px",
                              borderRadius: 6,
                              background: "#fee2e2",
                              color: "#dc2626",
                            }}
                          >
                            {item.severity}
                          </span>
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 12, color: "#64748b", textAlign: "center" }}>
                          {item.affected_version}
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 12, color: "#059669", fontWeight: 700, textAlign: "center" }}>
                          {item.fixed_version}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {category === "transformations" && (
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #f1f5f9" }}>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 40 }}>#</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 180 }}>Transformation Type</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Source File</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Target File</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 100, textAlign: "center" }}>Status</th>
                      <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 110 }}>Line Diff</th>
                      {onSelectFileForDiff && (
                        <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", width: 100, textAlign: "center" }}>Action</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item, idx) => (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: "1px solid #f1f5f9",
                          background: idx % 2 === 0 ? "#ffffff" : "#fbfdff",
                        }}
                      >
                        <td style={{ padding: "12px 14px", fontSize: 12, color: "#94a3b8", fontWeight: 600 }}>{idx + 1}.</td>
                        <td style={{ padding: "12px 14px", fontSize: 12, fontWeight: 700, color: "#7c3aed" }}>
                          <span
                            style={{
                              background: "#f5f3ff",
                              color: "#7c3aed",
                              padding: "2px 8px",
                              borderRadius: 4,
                              border: "1px solid #ede9fe",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {item.transformation_type}
                          </span>
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 12, fontFamily: "monospace", color: "#334155", wordBreak: "break-all" }}>
                          <span style={{ fontSize: 10, color: "#94a3b8", display: "block", textTransform: "uppercase" }}>
                            {item.source_framework}
                          </span>
                          {item.source_file}
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 12, fontFamily: "monospace", color: "#0f172a", fontWeight: 600, wordBreak: "break-all" }}>
                          <span style={{ fontSize: 10, color: "#2563eb", display: "block", textTransform: "uppercase" }}>
                            {item.target_framework}
                          </span>
                          {item.target_file}
                        </td>
                        <td style={{ padding: "12px 14px", textAlign: "center" }}>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              padding: "3px 8px",
                              borderRadius: 6,
                              background: item.status === "Added" ? "#dcfce7" : "#dbeafe",
                              color: item.status === "Added" ? "#059669" : "#1d4ed8",
                            }}
                          >
                            {item.status || "Transformed"}
                          </span>
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 12, fontWeight: 600 }}>
                          <span style={{ color: "#10b981" }}>+{item.additions ?? 0}</span>
                          <span style={{ color: "#ef4444", marginLeft: 8 }}>-{item.deletions ?? 0}</span>
                        </td>
                        {onSelectFileForDiff && (
                          <td style={{ padding: "12px 14px", textAlign: "center" }}>
                            <button
                              type="button"
                              onClick={() => {
                                onSelectFileForDiff(item.source_file || item.target_file);
                                onClose();
                              }}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                                padding: "4px 10px",
                                borderRadius: 6,
                                background: "#eff6ff",
                                border: "1px solid #bfdbfe",
                                color: "#2563eb",
                                fontSize: 11,
                                fontWeight: 700,
                                cursor: "pointer",
                              }}
                            >
                              <FaExternalLinkAlt size={10} /> View Diff
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "14px 24px",
            borderTop: "1px solid #e2e8f0",
            background: "#f8fafc",
          }}
        >
          <div style={{ fontSize: 12, color: "#64748b", fontWeight: 500 }}>
            Showing {filteredItems.length} of {items.length} total {config.singular}s
          </div>
          <button
            onClick={onClose}
            style={{
              padding: "8px 20px",
              borderRadius: 8,
              border: "1px solid #cbd5e1",
              background: "#ffffff",
              color: "#334155",
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
              transition: "all 0.15s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "#f1f5f9";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "#ffffff";
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined"
    ? createPortal(modalContent, document.body)
    : modalContent;
};
