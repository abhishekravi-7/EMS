import React, { useState, useMemo } from "react";
import { FaCheckCircle, FaTimesCircle, FaExclamationTriangle, FaSearch } from "react-icons/fa";
import { ExistingTestLogs } from "./ExistingTestLogs";

interface TestResult {
  test_name: string;
  suite: string;
  status: "PASSED" | "FAILED" | "SKIPPED" | "ERROR" | "NOT_EXECUTED" | "RUNNING" | "PENDING";
  duration: string;
  file: string;
  type?: string;
  test_type?: string;
  failure_message?: string | null;
}

interface FileSummary {
  file: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  not_executed?: number;
}

interface LogEntry {
  ts: string;
  msg: string;
  level: string;
}

interface ExistingTestTableProps {
  testResults: TestResult[];
  fileBreakdown?: FileSummary[];
  frameworkInfo?: {
    detected_framework?: string;
    build_tool?: string;
    test_source_dir?: string;
  };
  logs?: LogEntry[];
  onSelectTest: (test: TestResult) => void;
  title?: string;
}

export function ExistingTestTable({
  testResults,
  fileBreakdown = [],
  frameworkInfo,
  logs = [],
  onSelectTest,
  title = "Existing Tests Validation Report",
}: ExistingTestTableProps) {
  const [activeTab, setActiveTab] = useState<"TABLE" | "LOGS">("TABLE");
  const [filter, setFilter] = useState<"ALL" | "PASSED" | "FAILED" | "RUNNING" | "PENDING" | "SKIPPED" | "NOT_EXECUTED">("ALL");
  const [search, setSearch] = useState("");

  const buildTool = (frameworkInfo?.build_tool || "MAVEN").toUpperCase();
  const frameworkName = (frameworkInfo?.detected_framework || "JUNIT").toUpperCase();

  // Counts for filters
  const counts = useMemo(() => {
    const res = { total: 0, passed: 0, failed: 0, skipped: 0, not_executed: 0, running: 0, pending: 0 };
    testResults.forEach((t) => {
      res.total++;
      if (t.status === "PASSED") res.passed++;
      else if (t.status === "FAILED" || t.status === "ERROR") res.failed++;
      else if (t.status === "SKIPPED") res.skipped++;
      else if (t.status === "RUNNING") res.running++;
      else if (t.status === "PENDING") res.pending++;
      else if (t.status === "NOT_EXECUTED") res.not_executed++;
    });
    return res;
  }, [testResults]);

  const executedCount = counts.passed + counts.failed + counts.skipped;
  const passRateVal = executedCount > 0 ? ((counts.passed / executedCount) * 100).toFixed(1) : "N/A";

  // Filtered and searched test cases
  const filtered = useMemo(() => {
    return testResults.filter((t) => {
      // Status Filter
      if (filter !== "ALL") {
        if (filter === "PASSED" && t.status !== "PASSED") return false;
        if (filter === "FAILED" && t.status !== "FAILED" && t.status !== "ERROR") return false;
        if (filter === "RUNNING" && t.status !== "RUNNING") return false;
        if (filter === "PENDING" && t.status !== "PENDING") return false;
        if (filter === "SKIPPED" && t.status !== "SKIPPED") return false;
        if (filter === "NOT_EXECUTED" && t.status !== "NOT_EXECUTED") return false;
      }

      // Search Box Filter
      if (search.trim()) {
        const q = search.toLowerCase();
        const testName = (t.test_name || "").toLowerCase();
        const testClass = (t.suite || "").toLowerCase();
        const testFile = (t.file || "").toLowerCase();
        return testName.includes(q) || testClass.includes(q) || testFile.includes(q);
      }
      return true;
    });
  }, [testResults, filter, search]);

  const hasFailed = counts.failed > 0;
  const hasNotExecuted = counts.not_executed > 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      
      {/* Report Header Bar */}
      {title && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h3 style={{ fontSize: 17, fontWeight: 800, color: "#0f172a", margin: 0, letterSpacing: "-0.01em" }}>
                {title}
              </h3>
              <span style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px", borderRadius: 6, background: "#eff6ff", color: "#1d4ed8", border: "1px solid #dbeafe", textTransform: "uppercase" }}>
                {buildTool}
              </span>
              <span style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px", borderRadius: 6, background: "#f0fdf4", color: "#166534", border: "1px solid #bbf7d0", textTransform: "uppercase" }}>
                {frameworkName}
              </span>
            </div>
            <p style={{ fontSize: 12, color: "#64748b", margin: "4px 0 0 0" }}>
              Comprehensive execution metrics across discovered test suites
            </p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 17, fontWeight: 900, color: counts.failed > 0 ? "#dc2626" : "#16a34a" }}>
                {passRateVal}{passRateVal !== "N/A" ? "%" : ""}
              </div>
              <div style={{ fontSize: 9, fontWeight: 800, color: "#64748b", textTransform: "uppercase" }}>
                PASS RATE
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TABS BAR: Test Cases Table & Execution Logs */}
      <div style={{ display: "flex", gap: 10, borderBottom: "1px solid #e2e8f0", paddingBottom: 12 }}>
        <button
          onClick={() => setActiveTab("TABLE")}
          style={{
            padding: "8px 18px",
            fontSize: 12,
            fontWeight: 700,
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            cursor: "pointer",
            background: activeTab === "TABLE" ? "#0f172a" : "#fff",
            color: activeTab === "TABLE" ? "#fff" : "#475569",
            boxShadow: activeTab === "TABLE" ? "0 2px 4px rgba(0,0,0,0.1)" : "none",
            transition: "all 0.15s ease",
          }}
        >
          Test Cases Table
        </button>
        <button
          onClick={() => setActiveTab("LOGS")}
          style={{
            padding: "8px 18px",
            fontSize: 12,
            fontWeight: 700,
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            cursor: "pointer",
            background: activeTab === "LOGS" ? "#0f172a" : "#fff",
            color: activeTab === "LOGS" ? "#fff" : "#475569",
            display: "flex",
            alignItems: "center",
            gap: 6,
            boxShadow: activeTab === "LOGS" ? "0 2px 4px rgba(0,0,0,0.1)" : "none",
            transition: "all 0.15s ease",
          }}
        >
          Execution Logs
          {logs && logs.length > 0 && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 800,
                background: activeTab === "LOGS" ? "rgba(255, 255, 255, 0.2)" : "#f1f5f9",
                color: activeTab === "LOGS" ? "#fff" : "#64748b",
                padding: "1px 6px",
                borderRadius: 999,
              }}
            >
              {logs.length}
            </span>
          )}
        </button>
      </div>

      {activeTab === "LOGS" ? (
        <ExistingTestLogs logs={logs} />
      ) : (
        <>
          {/* 1. TEST CASE FILTER BAR */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 12,
              paddingBottom: 4,
              borderBottom: "1px solid #f1f5f9",
            }}
          >
            <div style={{ display: "flex", background: "#f1f5f9", borderRadius: 8, padding: 2, flexWrap: "wrap", gap: 2 }}>
              {([
                { key: "ALL", label: `All (${counts.total})` },
                { key: "PASSED", label: `Passed (${counts.passed})` },
                { key: "FAILED", label: `Failed (${counts.failed})` },
                ...(counts.running > 0 ? [{ key: "RUNNING" as const, label: `Running (${counts.running})` }] : []),
                ...(counts.pending > 0 ? [{ key: "PENDING" as const, label: `Pending (${counts.pending})` }] : []),
                { key: "SKIPPED", label: `Skipped (${counts.skipped})` },
                ...(counts.not_executed > 0 ? [{ key: "NOT_EXECUTED" as const, label: `Not Executed (${counts.not_executed})` }] : []),
              ] as const).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setFilter(tab.key)}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 6,
                    border: "none",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    background: filter === tab.key ? "#fff" : "transparent",
                    color: filter === tab.key ? "#0f172a" : "#64748b",
                    boxShadow: filter === tab.key ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                    transition: "all 0.15s",
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Search Box */}
            <div style={{ position: "relative", minWidth: 240 }}>
              <FaSearch style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#94a3b8", fontSize: 12 }} />
              <input
                type="text"
                placeholder="Search test name or class..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{
                  padding: "7px 12px 7px 32px",
                  fontSize: 12,
                  borderRadius: 8,
                  border: "1px solid #e2e8f0",
                  outline: "none",
                  width: "100%",
                }}
              />
            </div>
          </div>

          {/* 2. EXECUTED TEST CASES TABLE CONTAINER (With fixed/max-height internal scrolling) */}
          <div style={{ maxHeight: 420, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12 }}>
              <thead style={{ position: "sticky", top: 0, zIndex: 2, background: "#f8fafc" }}>
                <tr style={{ borderBottom: "1px solid #e2e8f0", color: "#475569", fontWeight: 700 }}>
                  <th style={{ padding: "12px 16px", width: 40 }}>#</th>
                  <th style={{ padding: "12px 16px", width: 120 }}>STATUS</th>
                  <th style={{ padding: "12px 16px" }}>TEST CLASS</th>
                  <th style={{ padding: "12px 16px" }}>TEST NAME</th>
                  <th style={{ padding: "12px 16px", width: 90 }}>TYPE</th>
                  <th style={{ padding: "12px 16px" }}>DESCRIPTION</th>
                  <th style={{ padding: "12px 16px", width: 100 }}>DURATION</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ padding: 32, textAlign: "center", color: "#94a3b8" }}>
                      No matching test cases found.
                    </td>
                  </tr>
                ) : (
                  filtered.map((t, idx) => {
                    const isRunning = t.status === "RUNNING";
                    const isPending = t.status === "PENDING";
                    const isPassed = t.status === "PASSED";
                    const isSkipped = t.status === "SKIPPED";
                    const isNotExecuted = t.status === "NOT_EXECUTED";

                    const badgeColor = isRunning ? "#1d4ed8" : isPending ? "#64748b" : isPassed ? "#15803d" : isSkipped ? "#b45309" : isNotExecuted ? "#475569" : "#b91c1c";
                    const badgeBg = isRunning ? "#eff6ff" : isPending ? "#f8fafc" : isPassed ? "#dcfce7" : isSkipped ? "#fef3c7" : isNotExecuted ? "#f1f5f9" : "#fde8e8";
                    const displayStatus = isRunning ? "RUNNING" : isPending ? "PENDING" : isNotExecuted ? "NOT EXECUTED" : isPassed ? "✓ PASSED" : isSkipped ? "○ SKIPPED" : t.status === "ERROR" ? "! ERROR" : "✕ FAILED";
                    const testTypeDisplay = t.test_type || t.type || "JUnit";

                    // Generate clean descriptions
                    const desc = isRunning
                      ? `Executing scenario "${t.test_name}"...`
                      : isPending
                      ? `Pending execution for "${t.test_name}".`
                      : isPassed
                      ? `Validates the "${t.test_name}" scenario successfully.`
                      : isSkipped
                      ? `Skipped validation for "${t.test_name}".`
                      : isNotExecuted
                      ? (t.failure_message || `Maven compilation failed before "${t.test_name}" could execute.`)
                      : t.failure_message
                      ? t.failure_message.slice(0, 100) + (t.failure_message.length > 100 ? "..." : "")
                      : `Validation failed in "${t.test_name}".`;

                    const durationDisplay = isRunning ? "Running..." : isPending ? "--" : isNotExecuted ? "N/A" : (t.duration || "0.0s");

                    return (
                      <tr
                        key={idx}
                        onClick={() => onSelectTest(t)}
                        style={{
                          borderBottom: "1px solid #f1f5f9",
                          cursor: "pointer",
                          transition: "background 0.15s",
                          background: isRunning ? "rgba(37, 99, 235, 0.06)" : "transparent",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = isRunning ? "rgba(37, 99, 235, 0.1)" : "#f8fafc")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = isRunning ? "rgba(37, 99, 235, 0.06)" : "transparent")}
                      >
                        <td style={{ padding: "12px 16px", color: "#64748b" }}>{idx + 1}</td>
                        <td style={{ padding: "12px 16px" }}>
                          <span
                            style={{
                              display: "inline-block",
                              padding: "2px 8px",
                              borderRadius: 4,
                              fontSize: 10,
                              fontWeight: 700,
                              color: badgeColor,
                              background: badgeBg,
                              textTransform: "uppercase",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {displayStatus}
                          </span>
                        </td>
                        <td
                          style={{
                            padding: "12px 16px",
                            fontFamily: "'Fira Code', 'Consolas', monospace",
                            color: "#0f172a",
                            fontSize: 11,
                            maxWidth: 240,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                          title={t.suite}
                        >
                          {t.suite}
                        </td>
                        <td style={{ padding: "12px 16px", fontWeight: 600, color: isRunning ? "#1d4ed8" : "#1e293b" }}>
                          {t.test_name}
                        </td>
                        <td style={{ padding: "12px 16px" }}>
                          <span
                            style={{
                              fontSize: 9,
                              fontWeight: 800,
                              padding: "1.5px 5.5px",
                              borderRadius: 4,
                              background: testTypeDisplay.toLowerCase().includes("ui") ? "#eff6ff" : testTypeDisplay.toLowerCase().includes("api") ? "#f0fdf4" : "#f1f5f9",
                              color: testTypeDisplay.toLowerCase().includes("ui") ? "#2563eb" : testTypeDisplay.toLowerCase().includes("api") ? "#16a34a" : "#475569",
                              border: `1px solid ${testTypeDisplay.toLowerCase().includes("ui") ? "#dbeafe" : testTypeDisplay.toLowerCase().includes("api") ? "#dcfce7" : "#e2e8f0"}`,
                              textTransform: "uppercase",
                            }}
                          >
                            {testTypeDisplay}
                          </span>
                        </td>
                        <td style={{ padding: "12px 16px", color: isRunning ? "#2563eb" : "#64748b", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {desc}
                        </td>
                        <td style={{ padding: "12px 16px", color: isRunning ? "#2563eb" : "#64748b", fontWeight: isRunning ? 700 : 400 }}>{durationDisplay}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* 3. EXECUTION SUMMARY FOOTER */}
          <div
            style={{
              background: hasFailed ? "#fef2f2" : hasNotExecuted ? "#f8fafc" : "#f0fdf4",
              border: `1px solid ${hasFailed ? "#fecaca" : hasNotExecuted ? "#cbd5e1" : "#bbf7d0"}`,
              borderRadius: 12,
              padding: "16px 20px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {hasFailed ? (
                <FaTimesCircle style={{ color: "#ef4444", fontSize: 18 }} />
              ) : hasNotExecuted ? (
                <FaExclamationTriangle style={{ color: "#64748b", fontSize: 18 }} />
              ) : (
                <FaCheckCircle style={{ color: "#22c55e", fontSize: 18 }} />
              )}
              <div>
                <div style={{ fontWeight: 800, fontSize: 13, color: hasFailed ? "#991b1b" : hasNotExecuted ? "#334155" : "#166534", textTransform: "uppercase" }}>
                  {hasFailed
                    ? `${counts.failed} TESTS FAILED`
                    : hasNotExecuted
                    ? `EXECUTION ERROR: ${counts.not_executed} TESTS NOT EXECUTED`
                    : `${counts.total} TESTS PASSED`}
                </div>
                <div style={{ fontSize: 11, color: hasFailed ? "#b91c1c" : hasNotExecuted ? "#64748b" : "#15803d", marginTop: 2 }}>
                  {counts.passed} passed · {counts.skipped} skipped · {counts.failed} failed · {counts.not_executed} not executed
                </div>
              </div>
            </div>
            <div style={{ fontSize: 11, color: "#64748b", fontFamily: "monospace" }}>
              {new Date().toLocaleString()}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
