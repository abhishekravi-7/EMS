import React, { useState } from "react";
import { FaFileAlt } from "react-icons/fa";
import { ExistingTestTable, type TestResult } from "./ExistingTestTable";
import { ExistingTestLogs } from "./ExistingTestLogs";

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

interface ExistingTestValidationReportProps {
  metrics: {
    total?: number;
    executed?: number;
    passed?: number;
    failed?: number;
    skipped?: number;
    not_executed?: number;
    duration?: string;
    pass_percentage?: string;
    execution_status?: string;
    compilation_error?: string | null;
  };
  frameworkInfo?: {
    detected_framework?: string;
    build_tool?: string;
    test_source_dir?: string;
  };
  testResults: TestResult[];
  fileBreakdown?: FileSummary[];
  logs: LogEntry[];
  onSelectTest: (test: TestResult) => void;
  onClose: () => void;
  onRunAgain?: () => void;
  isRunning?: boolean;
  hasRun?: boolean;
}

export function ExistingTestValidationReport({
  metrics,
  frameworkInfo,
  testResults,
  fileBreakdown = [],
  logs,
  onSelectTest,
  onClose,
  onRunAgain,
  isRunning = false,
  hasRun = true,
}: ExistingTestValidationReportProps) {
  const [activeTab, setActiveTab] = useState<"TABLE" | "LOGS">("TABLE");

  const executed = metrics.executed ?? (metrics.passed ?? 0) + (metrics.failed ?? 0) + (metrics.skipped ?? 0);
  const passed = metrics.passed ?? 0;
  const failed = metrics.failed ?? 0;
  const passRateVal = executed > 0 ? (passed / executed) * 100 : 0;
  const passRateStr = executed > 0 ? metrics.pass_percentage || `${passRateVal.toFixed(1)}%` : "N/A";

  const buildTool = (frameworkInfo?.build_tool || "MAVEN").toUpperCase();
  const testDir = frameworkInfo?.test_source_dir || "src/test/java";
  const execStatus = metrics.execution_status || (metrics.compilation_error ? "ERROR" : failed > 0 ? "FAILED" : "SUCCESS");

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10000,
        background: "rgba(15, 23, 42, 0.6)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 24,
          maxWidth: 1000,
          width: "100%",
          height: "85vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 50px rgba(0, 0, 0, 0.15)",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "20px 28px",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "linear-gradient(135deg, #0f172a, #1e293b)",
            color: "#fff",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <FaFileAlt style={{ fontSize: 20, color: "#38bdf8" }} />
            <div>
              <h3 style={{ fontSize: 16, fontWeight: 800, margin: 0, color: "#fff" }}>
                Existing Tests Validation Report
              </h3>
              <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
                <span
                  style={{
                    background: "rgba(255, 255, 255, 0.08)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: 4,
                    padding: "2px 8px",
                    fontSize: 10,
                    fontWeight: 700,
                    color: "#e2e8f0",
                  }}
                >
                  {buildTool}
                </span>
                <span
                  style={{
                    background: "rgba(255, 255, 255, 0.08)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: 4,
                    padding: "2px 8px",
                    fontSize: 10,
                    fontWeight: 700,
                    color: execStatus === "NO_TESTS_FOUND" ? "#94a3b8" : execStatus === "ERROR" ? "#fca5a5" : execStatus === "FAILED" ? "#fcd34d" : "#86efac",
                    borderStyle: "solid",
                    borderColor: execStatus === "NO_TESTS_FOUND" ? "rgba(148, 163, 184, 0.4)" : execStatus === "ERROR" ? "rgba(239, 68, 68, 0.4)" : execStatus === "FAILED" ? "rgba(245, 158, 11, 0.4)" : "rgba(34, 197, 94, 0.4)",
                  }}
                >
                  STATUS: {execStatus}
                </span>
                <span
                  style={{
                    background: "rgba(255, 255, 255, 0.08)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: 4,
                    padding: "2px 8px",
                    fontSize: 10,
                    fontWeight: 700,
                    color: "#94a3b8",
                    fontFamily: "monospace",
                  }}
                >
                  {testDir}
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            {/* Circular Pass Rate Indicator */}
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ position: "relative", width: 44, height: 44 }}>
                <svg width="44" height="44" viewBox="0 0 36 36">
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth="3.5"
                  />
                  {executed > 0 && (
                    <path
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      fill="none"
                      stroke={passRateVal >= 70 ? "#10b981" : "#ef4444"}
                      strokeWidth="3.5"
                      strokeDasharray={`${passRateVal}, 100`}
                      strokeLinecap="round"
                      style={{ transition: "stroke-dasharray 0.5s ease" }}
                    />
                  )}
                </svg>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: executed > 0 ? 9 : 8,
                    fontWeight: 900,
                    color: executed === 0 ? "#94a3b8" : passRateVal >= 70 ? "#34d399" : "#f87171",
                  }}
                >
                  {executed > 0 ? `${Math.round(passRateVal)}%` : "N/A"}
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: "#f8fafc" }}>
                  {passRateStr} PASS RATE
                </span>
                <span style={{ fontSize: 9, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>
                  Result Status
                </span>
              </div>
            </div>

            {/* Close Button */}
            <button
              onClick={onClose}
              style={{
                background: "rgba(255, 255, 255, 0.1)",
                border: "none",
                color: "#fff",
                width: 32,
                height: 32,
                borderRadius: 8,
                cursor: "pointer",
                fontSize: 14,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "background 0.2s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255, 255, 255, 0.2)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(255, 255, 255, 0.1)")}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Tab Selection Bar */}
        <div
          style={{
            padding: "12px 28px",
            borderBottom: "1px solid #e2e8f0",
            background: "#f8fafc",
            display: "flex",
            gap: 12,
            alignItems: "center",
            flexShrink: 0,
          }}
        >
          <button
            onClick={() => setActiveTab("TABLE")}
            style={{
              padding: "8px 16px",
              fontSize: 12,
              fontWeight: 700,
              borderRadius: 8,
              border: "1px solid #e2e8f0",
              cursor: "pointer",
              background: activeTab === "TABLE" ? "#0f172a" : "#fff",
              color: activeTab === "TABLE" ? "#fff" : "#475569",
              transition: "all 0.15s ease",
            }}
          >
            Test Cases Table
          </button>
          <button
            onClick={() => setActiveTab("LOGS")}
            style={{
              padding: "8px 16px",
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
              transition: "all 0.15s ease",
            }}
          >
            Execution Logs
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                background: activeTab === "LOGS" ? "rgba(255, 255, 255, 0.2)" : "#f1f5f9",
                color: activeTab === "LOGS" ? "#fff" : "#64748b",
                padding: "1px 6px",
                borderRadius: 999,
              }}
            >
              {logs.length}
            </span>
          </button>
        </div>

        {/* Main Panel Content Area */}
        <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
          {metrics.compilation_error && (
            <div
              style={{
                marginBottom: 20,
                padding: "16px 20px",
                borderRadius: 14,
                background: "#fef2f2",
                border: "1px solid #fecaca",
                color: "#991b1b",
              }}
            >
              <div style={{ fontWeight: 800, fontSize: 13, marginBottom: 8, display: "flex", alignItems: "center", gap: 8, textTransform: "uppercase" }}>
                ⚠️ Compilation Error — Tests Did Not Execute
              </div>
              <pre
                style={{
                  margin: 0,
                  fontSize: 11,
                  fontFamily: "'Fira Code', 'Consolas', monospace",
                  whiteSpace: "pre-wrap",
                  background: "#fff",
                  padding: 14,
                  borderRadius: 10,
                  border: "1px solid #fca5a5",
                  maxHeight: 180,
                  overflowY: "auto",
                  color: "#7f1d1d",
                  lineHeight: 1.4,
                }}
              >
                {metrics.compilation_error}
              </pre>
            </div>
          )}

          {activeTab === "TABLE" ? (
            <ExistingTestTable
              testResults={testResults}
              fileBreakdown={fileBreakdown}
              frameworkInfo={frameworkInfo}
              onSelectTest={onSelectTest}
              logs={logs}
              isRunning={isRunning}
              hasRun={hasRun}
              hideHeader={true}
            />
          ) : (
            <ExistingTestLogs logs={logs} />
          )}
        </div>
      </div>
    </div>
  );
}
