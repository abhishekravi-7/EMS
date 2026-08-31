import React, { useState, useMemo } from "react";
import {
  FaCheck,
  FaTimes,
  FaSearch,
  FaTable,
  FaTerminal,
  FaSort,
  FaSortUp,
  FaSortDown,
  FaChevronLeft,
  FaChevronRight,
  FaInfoCircle,
  FaSpinner,
} from "react-icons/fa";
import { ExistingTestLogs } from "./ExistingTestLogs";
import type { TestResult as ServiceTestResult, FileSummary as ServiceFileSummary, TestSelectionItem } from "../services/existingTestService";

export type TestResult = ServiceTestResult;
export type FileSummary = ServiceFileSummary;

export interface LogEntry {
  ts: string;
  msg: string;
  level: string;
}

interface ExistingTestTableProps {
  testResults: TestResult[];
  title?: string;
  fileBreakdown?: FileSummary[];
  frameworkInfo?: {
    detected_framework?: string;
    build_tool?: string | null;
    test_source_dir?: string;
  };
  logs?: LogEntry[];
  onSelectTest: (test: TestResult | TestSelectionItem) => void;
  onRunAgain?: () => void;
  isRunning?: boolean;
  hasRun?: boolean;
  hideHeader?: boolean;
}

type SortField = "NAME" | "DURATION" | "STATUS" | "TYPE" | "CLASS";
type SortOrder = "ASC" | "DESC";

export function ExistingTestTable({
  testResults,
  frameworkInfo,
  logs = [],
  onSelectTest,
  title = "Existing Tests Validation Report",
  onRunAgain: _onRunAgain,
  isRunning: _isRunning = false,
  hasRun: _hasRun = false,
  hideHeader = false,
}: ExistingTestTableProps) {
  const [viewMode, setViewMode] = useState<"TABLE" | "LOGS">("TABLE");
  const [filter, setFilter] = useState<"ALL" | "PASSED" | "FAILED" | "SKIPPED">("ALL");
  const [search, setSearch] = useState("");
  const pageSize = 10;
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortOrder, setSortOrder] = useState<SortOrder>("ASC");

  const buildTool = (frameworkInfo?.build_tool || "MAVEN").toUpperCase();
  const testSourceDir = frameworkInfo?.test_source_dir || "src/test/java";

  // Canonical counts computed directly from testResults
  const counts = useMemo(() => {
    const res = { total: 0, passed: 0, failed: 0, skipped: 0, not_executed: 0 };
    testResults.forEach((t) => {
      res.total++;
      const st = (t.status || "NOT_EXECUTED").toUpperCase();
      if (st === "PASSED") res.passed++;
      else if (st === "FAILED" || st === "ERROR") res.failed++;
      else if (st === "SKIPPED" || st === "NOT_EXECUTED" || st === "NOT EXECUTED" || st === "PENDING") res.skipped++;
      else res.not_executed++;
    });
    return res;
  }, [testResults]);

  const executedCount = counts.passed + counts.failed + counts.skipped;
  const passRateVal = (counts.passed + counts.failed) > 0 ? `${((counts.passed / (counts.passed + counts.failed)) * 100).toFixed(1)}%` : (executedCount > 0 ? `${((counts.passed / executedCount) * 100).toFixed(1)}%` : "—");

  // Filtering & searching
  const filtered = useMemo(() => {
    let result = testResults.filter((t) => {
      const st = (t.status || "NOT_EXECUTED").toUpperCase();
      if (filter === "PASSED" && st !== "PASSED") return false;
      if (filter === "FAILED" && st !== "FAILED" && st !== "ERROR") return false;
      if (filter === "SKIPPED" && st !== "SKIPPED" && st !== "NOT_EXECUTED" && st !== "NOT EXECUTED" && st !== "PENDING") return false;

      if (search.trim()) {
        const q = search.toLowerCase();
        const testName = (t.test_name || t.name || t.title || "").toLowerCase();
        const testClass = (t.suite || t.spec || "").toLowerCase();
        const testFile = (t.file || "").toLowerCase();
        const rawType = (t.test_type || t.testType || t.type || "").toUpperCase();
        const testType = (rawType === "UNIT" ? "API" : rawType).toLowerCase();
        const testFw = (t.framework || "").toLowerCase();
        return (
          testName.includes(q) ||
          testClass.includes(q) ||
          testFile.includes(q) ||
          testType.includes(q) ||
          testFw.includes(q)
        );
      }
      return true;
    });

    // Sorting
    if (sortField) {
      result = [...result].sort((a, b) => {
        let valA = "";
        let valB = "";

        if (sortField === "NAME") {
          valA = (a.test_name || a.name || a.title || "").toLowerCase();
          valB = (b.test_name || b.name || b.title || "").toLowerCase();
        } else if (sortField === "CLASS") {
          valA = (a.suite || a.file || "").toLowerCase();
          valB = (b.suite || b.file || "").toLowerCase();
        } else if (sortField === "STATUS") {
          valA = (a.status || "").toLowerCase();
          valB = (b.status || "").toLowerCase();
        } else if (sortField === "TYPE") {
          const rawA = (a.test_type || a.testType || a.type || "").toUpperCase();
          const rawB = (b.test_type || b.testType || b.type || "").toUpperCase();
          valA = (rawA === "UNIT" ? "API" : rawA).toLowerCase();
          valB = (rawB === "UNIT" ? "API" : rawB).toLowerCase();
        } else if (sortField === "DURATION") {
          const numA = parseFloat((a.duration || "0").replace(/[^0-9.]/g, "")) || 0;
          const numB = parseFloat((b.duration || "0").replace(/[^0-9.]/g, "")) || 0;
          return sortOrder === "ASC" ? numA - numB : numB - numA;
        }

        if (valA < valB) return sortOrder === "ASC" ? -1 : 1;
        if (valA > valB) return sortOrder === "ASC" ? 1 : -1;
        return 0;
      });
    }

    return result;
  }, [testResults, filter, search, sortField, sortOrder]);

  // Pagination calculations
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedTests = filtered.slice(startIndex, startIndex + pageSize);
  const startItemNumber = filtered.length === 0 ? 0 : startIndex + 1;
  const endItemNumber = Math.min(startIndex + pageSize, filtered.length);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      if (sortOrder === "ASC") {
        setSortOrder("DESC");
      } else {
        setSortField(null);
        setSortOrder("ASC");
      }
    } else {
      setSortField(field);
      setSortOrder("ASC");
    }
  };

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) return <FaSort style={{ opacity: 0.3, fontSize: 10, marginLeft: 4 }} />;
    return sortOrder === "ASC" ? (
      <FaSortUp style={{ color: "#4f46e5", fontSize: 10, marginLeft: 4 }} />
    ) : (
      <FaSortDown style={{ color: "#4f46e5", fontSize: 10, marginLeft: 4 }} />
    );
  };

  if (testResults.length === 0) {
    return (
      <div
        style={{
          background: "#fff",
          border: "1px solid #e2e8f0",
          borderRadius: 16,
          padding: "48px 24px",
          textAlign: "center",
          boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 12,
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: "50%",
            background: "#f1f5f9",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#64748b",
            fontSize: 22,
          }}
        >
          <FaInfoCircle />
        </div>
        <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>
          No Test Cases Available
        </div>
        <div style={{ fontSize: 13, color: "#64748b", maxWidth: 360, lineHeight: 1.5 }}>
          No existing test cases were found in this repository.
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* ── 1. Report Header Bar ───────────────────────────────────────────── */}
      {!hideHeader && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 14,
            borderBottom: "1px solid #f1f5f9",
            paddingBottom: 16,
          }}
        >
          {/* Title & Badges */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 10,
                background: "#4f46e5",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 16,
              }}
            >
              <FaTable />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <h3 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>
                  {title}
                </h3>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 800,
                    padding: "2px 8px",
                    borderRadius: 6,
                    background: "#f0fdf4",
                    color: "#16a34a",
                    border: "1px solid #bbf7d0",
                  }}
                >
                  {buildTool}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: 6,
                    background: "#f8fafc",
                    color: "#64748b",
                    border: "1px solid #e2e8f0",
                    fontFamily: "monospace",
                  }}
                >
                  {testSourceDir}
                </span>
              </div>
            </div>
          </div>

          {/* Right Circular Pass Rate Badge, Run Again Button & View Toggle */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {/* Circular Pass Rate Badge */}
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "50%",
                border: "3px solid #10b981",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                textAlign: "center",
              }}
            >
              <span style={{ fontSize: 10, fontWeight: 900, color: "#0f172a", lineHeight: 1 }}>{passRateVal}</span>
              <span style={{ fontSize: 7, fontWeight: 800, color: "#10b981", textTransform: "uppercase", marginTop: 1 }}>
                PASS RATE
              </span>
            </div>

            {/* Segmented Toggle: Test Cases Table / Execution Logs */}
            <div
              style={{
                display: "inline-flex",
                borderRadius: 8,
                border: "1px solid #e2e8f0",
                background: "#fff",
                padding: 2,
              }}
            >
              <button
                onClick={() => setViewMode("TABLE")}
                style={{
                  padding: "6px 14px",
                  borderRadius: 6,
                  border: viewMode === "TABLE" ? "1px solid #ddd6fe" : "none",
                  background: viewMode === "TABLE" ? "#f5f3ff" : "transparent",
                  color: viewMode === "TABLE" ? "#6d28d9" : "#64748b",
                  fontWeight: 800,
                  fontSize: 12,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <FaTable size={12} /> Test Cases Table
              </button>

              <button
                onClick={() => setViewMode("LOGS")}
                style={{
                  padding: "6px 14px",
                  borderRadius: 6,
                  border: viewMode === "LOGS" ? "1px solid #ddd6fe" : "none",
                  background: viewMode === "LOGS" ? "#f5f3ff" : "transparent",
                  color: viewMode === "LOGS" ? "#6d28d9" : "#64748b",
                  fontWeight: 800,
                  fontSize: 12,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <FaTerminal size={12} /> Execution Logs {logs.length > 0 ? `(${logs.length})` : ""}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── VIEW MODE 1: TEST CASES TABLE ─────────────────────────────────── */}
      {viewMode === "TABLE" || hideHeader ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Controls: Filter Pills & Search */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
            {/* Filter Pills */}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {[
                { key: "ALL", label: `All ${counts.total}` },
                { key: "PASSED", label: `✓ Passed ${counts.passed}`, count: counts.passed, color: "#16a34a", bg: "#f0fdf4", border: "#bbf7d0" },
                { key: "FAILED", label: `✕ Failed ${counts.failed}`, count: counts.failed, color: "#dc2626", bg: "#fef2f2", border: "#fecaca" },
                { key: "SKIPPED", label: `⏸ Skipped ${counts.skipped}`, count: counts.skipped, color: "#64748b", bg: "#f8fafc", border: "#e2e8f0" },
              ].map((p) => {
                const isActive = filter === p.key;
                return (
                  <button
                    key={p.key}
                    onClick={() => {
                      setFilter(p.key as "ALL" | "PASSED" | "FAILED" | "SKIPPED");
                      setCurrentPage(1);
                    }}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 20,
                      border: isActive ? "none" : "1px solid #e2e8f0",
                      background: isActive ? "#0f172a" : "#fff",
                      color: isActive ? "#fff" : "#475569",
                      fontSize: 12,
                      fontWeight: 800,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      boxShadow: isActive ? "0 2px 6px rgba(15, 23, 42, 0.2)" : "none",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>

            {/* Search Input */}
            <div style={{ position: "relative" }}>
              <FaSearch
                style={{
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "#94a3b8",
                  fontSize: 12,
                }}
              />
              <input
                type="text"
                placeholder="Search by test name, class, or file..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setCurrentPage(1);
                }}
                style={{
                  padding: "7px 12px 7px 34px",
                  borderRadius: 8,
                  border: "1px solid #cbd5e1",
                  fontSize: 12,
                  outline: "none",
                  width: 260,
                }}
              />
            </div>
          </div>

          {/* Main Table */}
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, overflow: "hidden", background: "#fff", boxShadow: "0 1px 3px rgba(0,0,0,0.02)" }}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0", color: "#64748b", fontWeight: 800, fontSize: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>
                    <th style={{ padding: "10px 14px", width: 40 }}>#</th>
                    <th
                      style={{ padding: "10px 14px", width: 110, cursor: "pointer", userSelect: "none" }}
                      onClick={() => handleSort("STATUS")}
                    >
                      <div style={{ display: "flex", alignItems: "center" }}>
                        STATUS {renderSortIcon("STATUS")}
                      </div>
                    </th>
                    <th
                      style={{ padding: "10px 14px", width: 180, cursor: "pointer", userSelect: "none" }}
                      onClick={() => handleSort("CLASS")}
                    >
                      <div style={{ display: "flex", alignItems: "center" }}>
                        TEST CLASS {renderSortIcon("CLASS")}
                      </div>
                    </th>
                    <th
                      style={{ padding: "10px 14px", minWidth: 200, cursor: "pointer", userSelect: "none" }}
                      onClick={() => handleSort("NAME")}
                    >
                      <div style={{ display: "flex", alignItems: "center" }}>
                        TEST NAME {renderSortIcon("NAME")}
                      </div>
                    </th>
                    <th
                      style={{ padding: "10px 14px", width: 80, cursor: "pointer", userSelect: "none" }}
                      onClick={() => handleSort("TYPE")}
                    >
                      <div style={{ display: "flex", alignItems: "center" }}>
                        TYPE {renderSortIcon("TYPE")}
                      </div>
                    </th>
                    <th style={{ padding: "10px 14px" }}>DESCRIPTION</th>
                    <th
                      style={{ padding: "10px 14px", width: 90, textAlign: "right", cursor: "pointer", userSelect: "none" }}
                      onClick={() => handleSort("DURATION")}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end" }}>
                        DURATION {renderSortIcon("DURATION")}
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedTests.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ padding: "48px 16px", textAlign: "center" }}>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                          <FaInfoCircle size={24} style={{ color: "#94a3b8" }} />
                          <div style={{ fontSize: 14, fontWeight: 800, color: "#0f172a" }}>No test cases found</div>
                          <div style={{ fontSize: 12, color: "#64748b" }}>
                            Try changing your search query or filter selection.
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    paginatedTests.map((t, idx) => {
                      const globalIndex = startIndex + idx + 1;
                      const st = (t.status || "PASSED").toUpperCase();
                      const isPassed = st === "PASSED";
                      const isFailed = st === "FAILED" || st === "ERROR";
                      const isSkipped = st === "SKIPPED";
                      const isInProgress = st === "IN_PROGRESS" || st === "RUNNING" || st === "IN PROGRESS";
                      const isNotExecuted = !isPassed && !isFailed && !isSkipped && !isInProgress;

                      const badgeBg = isPassed
                        ? "#f0fdf4"
                        : isFailed
                        ? "#fef2f2"
                        : isInProgress
                        ? "#eff6ff"
                        : "#f8fafc";

                      const badgeColor = isPassed
                        ? "#16a34a"
                        : isFailed
                        ? "#dc2626"
                        : isInProgress
                        ? "#2563eb"
                        : "#64748b";

                      const badgeBorder = isPassed
                        ? "#bbf7d0"
                        : isFailed
                        ? "#fecaca"
                        : isInProgress
                        ? "#bfdbfe"
                        : "#e2e8f0";

                      const rawType = (t.test_type || t.testType || t.type || (t.category === "UI" ? "UI" : t.category === "API" ? "API" : "UNIT")).toUpperCase();
                      const testType = rawType === "UNIT" ? "API" : rawType;

                      const testName = t.test_name || t.name || t.title || "scenario";
                      const className = t.suite || t.spec || t.file || "TestSuite";
                      const shortClass = className.split(".").pop() || className;

                      const desc =
                        t.failure_message ||
                        t.error ||
                        `Validates the "${testName}" scenario in ${shortClass}.`;

                      return (
                        <tr
                          key={idx}
                          onClick={() => onSelectTest(t)}
                          style={{
                            borderBottom: "1px solid #f1f5f9",
                            cursor: "pointer",
                            background: isFailed ? "#fffafb" : isInProgress ? "#f8faff" : "transparent",
                            transition: "background 0.15s ease",
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = isFailed ? "#fef2f2" : isInProgress ? "#eff6ff" : "#f8fafc";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = isFailed ? "#fffafb" : isInProgress ? "#f8faff" : "transparent";
                          }}
                        >
                          {/* Row Index */}
                          <td style={{ padding: "12px 14px", color: "#94a3b8", fontWeight: 700, fontSize: 11 }}>
                            {globalIndex}
                          </td>

                          {/* Status Badge */}
                          <td style={{ padding: "12px 14px" }}>
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 800,
                                padding: "3px 8px",
                                borderRadius: 6,
                                background: badgeBg,
                                color: badgeColor,
                                border: `1px solid ${badgeBorder}`,
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                              }}
                            >
                              {isPassed && <FaCheck size={9} />}
                              {isFailed && <FaTimes size={9} />}
                              {isSkipped && <span>⏸</span>}
                              {isInProgress && <FaSpinner className="animate-spin" size={9} />}
                              {isNotExecuted && <span>⊘</span>}
                              {isPassed ? "PASSED" : isFailed ? "FAILED" : isInProgress ? "IN PROGRESS" : isSkipped ? "SKIPPED" : "NOT EXECUTED"}
                            </span>
                          </td>

                          {/* Test Class */}
                          <td
                            style={{
                              padding: "12px 14px",
                              fontFamily: "monospace",
                              color: "#475569",
                              fontSize: 11,
                              maxWidth: 180,
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                            title={className}
                          >
                            {shortClass}
                          </td>

                          {/* Prominent Test Name */}
                          <td style={{ padding: "12px 14px", maxWidth: 260 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <span
                                style={{
                                  fontSize: 13,
                                  fontWeight: 800,
                                  color: "#0f172a",
                                  whiteSpace: "nowrap",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                  display: "block",
                                }}
                                title={testName}
                              >
                                {testName}
                              </span>
                            </div>
                          </td>

                          {/* Type Badge */}
                          <td style={{ padding: "12px 14px" }}>
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 800,
                                padding: "2px 6px",
                                borderRadius: 4,
                                background: testType === "UI" ? "#f5f3ff" : "#ecfdf5",
                                color: testType === "UI" ? "#7c3aed" : "#047857",
                                border: `1px solid ${testType === "UI" ? "#ddd6fe" : "#a7f3d0"}`,
                              }}
                            >
                              {testType}
                            </span>
                          </td>

                          {/* Description */}
                          <td
                            style={{
                              padding: "12px 14px",
                              color: "#64748b",
                              fontSize: 11,
                              maxWidth: 240,
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                            title={desc}
                          >
                            {desc}
                          </td>

                          {/* Duration */}
                          <td style={{ padding: "12px 14px", textAlign: "right", color: "#64748b", fontWeight: 700, fontSize: 11 }}>
                            {isNotExecuted ? "—" : (t.duration && t.duration !== "--" ? t.duration : "—")}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "12px 18px",
                background: "#f8fafc",
                borderTop: "1px solid #e2e8f0",
                flexWrap: "wrap",
                gap: 10,
              }}
            >
              {/* Showing info */}
              <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>
                Showing <span style={{ color: "#0f172a", fontWeight: 800 }}>{startItemNumber}–{endItemNumber}</span> of{" "}
                <span style={{ color: "#0f172a", fontWeight: 800 }}>{filtered.length}</span> tests
                {filtered.length !== testResults.length ? ` (filtered from ${testResults.length})` : ""}
              </div>

              {/* Page Buttons */}
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  style={{
                    padding: "5px 10px",
                    borderRadius: 6,
                    border: "1px solid #e2e8f0",
                    background: currentPage === 1 ? "#f1f5f9" : "#fff",
                    color: currentPage === 1 ? "#94a3b8" : "#0f172a",
                    fontSize: 11,
                    fontWeight: 700,
                    cursor: currentPage === 1 ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  <FaChevronLeft size={9} /> Previous
                </button>

                {/* Page Number Chips */}
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter((p) => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1)
                  .map((p, idx, arr) => {
                    const prev = arr[idx - 1];
                    const showEllipsis = prev && p - prev > 1;

                    return (
                      <React.Fragment key={p}>
                        {showEllipsis && <span style={{ padding: "0 4px", color: "#94a3b8", fontSize: 11 }}>...</span>}
                        <button
                          onClick={() => setCurrentPage(p)}
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: 6,
                            border: currentPage === p ? "none" : "1px solid #e2e8f0",
                            background: currentPage === p ? "#0f172a" : "#fff",
                            color: currentPage === p ? "#fff" : "#475569",
                            fontSize: 11,
                            fontWeight: 800,
                            cursor: "pointer",
                          }}
                        >
                          {p}
                        </button>
                      </React.Fragment>
                    );
                  })}

                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages || totalPages === 0}
                  style={{
                    padding: "5px 10px",
                    borderRadius: 6,
                    border: "1px solid #e2e8f0",
                    background: currentPage === totalPages || totalPages === 0 ? "#f1f5f9" : "#fff",
                    color: currentPage === totalPages || totalPages === 0 ? "#94a3b8" : "#0f172a",
                    fontSize: 11,
                    fontWeight: 700,
                    cursor: currentPage === totalPages || totalPages === 0 ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  Next <FaChevronRight size={9} />
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* ── VIEW MODE 2: EXECUTION LOGS ──────────────────────────────────── */
        <div>
          <ExistingTestLogs logs={logs} />
        </div>
      )}
    </div>
  );
}
