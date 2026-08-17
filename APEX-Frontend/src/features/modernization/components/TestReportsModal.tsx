import React from "react";
import {
  FaExternalLinkAlt, FaTimes, FaInfoCircle, FaTerminal, FaPlay,
  FaImage, FaProjectDiagram, FaCheckCircle, FaTimesCircle, FaCode,
  FaLink, FaDownload,
} from "react-icons/fa";
import type { ApiEvidence } from "../services/existingTestService";

// ── Data model ──────────────────────────────────────────────────────────────

export interface TestReportData {
  testId?: string;
  executionId?: string;
  title: string;
  spec: string;
  status: string;
  duration?: string | null;
  file?: string | null;
  url?: string | null;
  error?: string | null;
  errorCode?: string | null;
  errorCategory?: string | null;
  rootCause?: string | null;
  apexExecution?: string | null;
  unavailableReason?: string | null;
  stackTrace?: string | null;
  stdout?: string | null;
  stderr?: string | null;
  type?: string;
  testType?: "JUNIT" | "API" | "UI" | "UNIT" | "UNKNOWN" | string;
  framework?: string;
  engine?: string;
  // UI evidence
  screenshotUrl?: string | null;
  videoUrl?: string | null;
  traceUrl?: string | null;
  // API evidence
  apiEvidence?: ApiEvidence | null;
  evidence?: any;
}

interface TestReportsModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: TestReportData | null;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

const STATUS_COLORS = {
  PASSED: { bg: "#064e3b", text: "#34d399", border: "#065f46" },
  FAILED: { bg: "#451a1a", text: "#f87171", border: "#7f1d1d" },
  ERROR: { bg: "#451a1a", text: "#f87171", border: "#7f1d1d" },
  SKIPPED: { bg: "#451a03", text: "#fbbf24", border: "#78350f" },
  NOT_EXECUTED: { bg: "#1e293b", text: "#94a3b8", border: "#475569" },
  DEFAULT: { bg: "#1e293b", text: "#94a3b8", border: "#334155" },
};

const METHOD_COLORS: Record<string, string> = {
  GET: "#3b82f6", POST: "#10b981", PUT: "#f59e0b",
  PATCH: "#8b5cf6", DELETE: "#ef4444",
};

function StatusBadge({ status }: { status: string }) {
  const c = STATUS_COLORS[status as keyof typeof STATUS_COLORS] ?? STATUS_COLORS.DEFAULT;
  const label = status === "NOT_EXECUTED" ? "NOT EXECUTED" : status;
  return (
    <span style={{
      fontSize: 10, fontWeight: 900, padding: "3px 10px", borderRadius: 6,
      textTransform: "uppercase", letterSpacing: "0.05em",
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
    }}>{label}</span>
  );
}

// ── Test Execution Details Component ────────────────────────────────────────

function TestExecutionDetails({ data }: { data: TestReportData }) {
  const [showStackTrace, setShowStackTrace] = React.useState(false);
  const [showStdout, setShowStdout] = React.useState(false);
  const [showStderr, setShowStderr] = React.useState(false);

  const hasError = !!(data.error && data.error.trim());
  const hasStackTrace = !!(data.stackTrace && data.stackTrace.trim());
  const hasStdout = !!(data.stdout && data.stdout.trim());
  const hasStderr = !!(data.stderr && data.stderr.trim());

  const frameworkVal = data.framework || "JUnit";
  const rawTestType = (data.testType || (data.type === "UI" || data.type === "API" || data.type === "UNIT" ? data.type : "") || "UNIT").toUpperCase();
  const testTypeVal = rawTestType.includes("UI") ? "UI" : rawTestType.includes("API") ? "API" : "UNIT";
  const engineVal = data.engine || (testTypeVal === "UI" ? "Playwright" : data.type && data.type !== frameworkVal && data.type !== testTypeVal ? data.type : null);

  return (
    <div style={{
      background: "#1e293b",
      borderRadius: 14,
      padding: "18px 22px",
      border: "1px solid #334155",
      display: "flex",
      flexDirection: "column",
      gap: 16,
    }}>
      <div style={{
        fontSize: 11,
        fontWeight: 800,
        color: "#94a3b8",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        borderBottom: "1px solid #334155",
        paddingBottom: 8,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <span>Test Execution Details</span>
        <span style={{ fontSize: 10, color: "#64748b", textTransform: "none", fontWeight: 600 }}>APEX Test Discovery &amp; Execution</span>
      </div>

      {/* Multi-Column Grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
        gap: "14px 20px",
      }}>
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Test Name</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#38bdf8", fontFamily: "monospace", wordBreak: "break-all" }}>
            {data.title || "None"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Test ID</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#cbd5e1", fontFamily: "monospace", wordBreak: "break-all" }}>
            {data.testId || "None"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Execution ID</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#cbd5e1", fontFamily: "monospace", wordBreak: "break-all" }}>
            {data.executionId || "None"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Status</div>
          <div style={{ marginTop: 2 }}>
            <StatusBadge status={data.status} />
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Duration</div>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#f472b6" }}>
            {data.duration || "None"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Source File</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", fontFamily: "monospace", wordBreak: "break-all" }}>
            {data.file || "None"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Class / Suite</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#7dd3fc", fontFamily: "monospace", wordBreak: "break-all" }}>
            {data.spec || "None"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Framework</div>
          <div style={{ marginTop: 2 }}>
            <span style={{
              fontSize: 10,
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: 6,
              background: "#334155",
              color: "#e2e8f0",
              border: "1px solid #475569",
              letterSpacing: "0.02em",
              display: "inline-block",
            }}>
              {frameworkVal}
            </span>
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Test Type</div>
          <div style={{ marginTop: 2 }}>
            <span style={{
              fontSize: 9,
              fontWeight: 800,
              padding: "2px 8px",
              borderRadius: 4,
              background: testTypeVal === "UI" ? "#1e1b4b" : testTypeVal === "API" ? "#083344" : "#1e293b",
              color: testTypeVal === "UI" ? "#a78bfa" : testTypeVal === "API" ? "#38bdf8" : "#94a3b8",
              border: `1px solid ${testTypeVal === "UI" ? "#3730a3" : testTypeVal === "API" ? "#155e75" : "#334155"}`,
              letterSpacing: "0.04em",
              display: "inline-block",
            }}>
              {testTypeVal}
            </span>
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>APEX Execution</div>
          <div style={{ marginTop: 2, display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{
              fontSize: 10,
              fontWeight: 800,
              padding: "2px 8px",
              borderRadius: 6,
              background: "#064e3b",
              color: "#34d399",
              border: "1px solid #065f46",
              letterSpacing: "0.02em",
              display: "inline-block",
            }}>
              {data.apexExecution || (data as any)?.details?.apexExecution || "Started successfully"}
            </span>
          </div>
        </div>

        {engineVal && (
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Engine</div>
            <div style={{ marginTop: 2 }}>
              <span style={{
                fontSize: 10,
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: 6,
                background: "#1e1b4b",
                color: "#c084fc",
                border: "1px solid #4c1d95",
                letterSpacing: "0.02em",
                display: "inline-block",
              }}>
                {engineVal}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Expandable Sections for Error, Root Cause, Category, Stack Trace, stdout, stderr */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 4 }}>
        {/* Root Cause (when present) */}
        {(data.rootCause || (data as any)?.details?.rootCause) && (
          <div style={{ background: "#451a03", borderRadius: 8, padding: "10px 14px", border: "1px solid #78350f" }}>
            <div style={{ fontSize: 10, fontWeight: 800, color: "#fbbf24", textTransform: "uppercase", marginBottom: 4, letterSpacing: "0.05em" }}>
              Root Cause
            </div>
            <div style={{ fontSize: 12, color: "#fef08a", fontWeight: 700, lineHeight: 1.4 }}>
              {data.rootCause || (data as any)?.details?.rootCause}
            </div>
          </div>
        )}

        {/* Error Classification / Category (when present) */}
        {(data.errorCategory || (data as any)?.details?.errorCategory) && (
          <div style={{ background: "#1e293b", borderRadius: 8, padding: "10px 14px", border: "1px solid #334155" }}>
            <div style={{ fontSize: 10, fontWeight: 800, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4, letterSpacing: "0.05em" }}>
              Error Classification
            </div>
            <div style={{ fontSize: 12, color: "#f87171", fontWeight: 700 }}>
              {data.errorCategory || (data as any)?.details?.errorCategory}
            </div>
          </div>
        )}

        {/* Error */}
        <div style={{ background: "#0f172a", borderRadius: 8, padding: "10px 14px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>
            Error
          </div>
          <div style={{ fontSize: 12, color: hasError ? "#fca5a5" : "#64748b", fontFamily: hasError ? "monospace" : "inherit" }}>
            {hasError ? data.error : "No errors"}
          </div>
        </div>

        {/* Stack Trace */}
        <div style={{ background: "#0f172a", borderRadius: 8, padding: "10px 14px", border: "1px solid #334155" }}>
          <div
            onClick={() => hasStackTrace && setShowStackTrace(!showStackTrace)}
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#94a3b8",
              textTransform: "uppercase",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: hasStackTrace ? "pointer" : "default",
            }}
          >
            <span>Stack Trace</span>
            {hasStackTrace && (
              <span style={{ color: "#38bdf8", fontSize: 10, fontWeight: 600 }}>
                {showStackTrace ? "Collapse" : "Expand"}
              </span>
            )}
          </div>
          {!hasStackTrace ? (
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>No stack trace available</div>
          ) : showStackTrace ? (
            <pre style={{
              margin: "8px 0 0 0",
              padding: 10,
              background: "#020617",
              borderRadius: 6,
              fontSize: 11,
              color: "#fca5a5",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              maxHeight: 200,
              overflowY: "auto",
              fontFamily: "monospace",
            }}>
              {data.stackTrace}
            </pre>
          ) : (
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4, fontFamily: "monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {data.stackTrace?.split("\n")[0]}
            </div>
          )}
        </div>

        {/* Standard Output (stdout) */}
        <div style={{ background: "#0f172a", borderRadius: 8, padding: "10px 14px", border: "1px solid #334155" }}>
          <div
            onClick={() => hasStdout && setShowStdout(!showStdout)}
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#94a3b8",
              textTransform: "uppercase",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: hasStdout ? "pointer" : "default",
            }}
          >
            <span>Standard Output (stdout)</span>
            {hasStdout && (
              <span style={{ color: "#38bdf8", fontSize: 10, fontWeight: 600 }}>
                {showStdout ? "Collapse" : "Expand"}
              </span>
            )}
          </div>
          {!hasStdout ? (
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>No standard output captured</div>
          ) : showStdout ? (
            <pre style={{
              margin: "8px 0 0 0",
              padding: 10,
              background: "#020617",
              borderRadius: 6,
              fontSize: 11,
              color: "#e2e8f0",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              maxHeight: 200,
              overflowY: "auto",
              fontFamily: "monospace",
            }}>
              {data.stdout}
            </pre>
          ) : (
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4, fontFamily: "monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {data.stdout?.split("\n")[0]}
            </div>
          )}
        </div>

        {/* Standard Error (stderr) */}
        <div style={{ background: "#0f172a", borderRadius: 8, padding: "10px 14px", border: "1px solid #334155" }}>
          <div
            onClick={() => hasStderr && setShowStderr(!showStderr)}
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#94a3b8",
              textTransform: "uppercase",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: hasStderr ? "pointer" : "default",
            }}
          >
            <span>Standard Error (stderr)</span>
            {hasStderr && (
              <span style={{ color: "#38bdf8", fontSize: 10, fontWeight: 600 }}>
                {showStderr ? "Collapse" : "Expand"}
              </span>
            )}
          </div>
          {!hasStderr ? (
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>No standard error captured</div>
          ) : showStderr ? (
            <pre style={{
              margin: "8px 0 0 0",
              padding: 10,
              background: "#020617",
              borderRadius: 6,
              fontSize: 11,
              color: "#fca5a5",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              maxHeight: 200,
              overflowY: "auto",
              fontFamily: "monospace",
            }}>
              {data.stderr}
            </pre>
          ) : (
            <div style={{ fontSize: 11, color: "#fca5a5", marginTop: 4, fontFamily: "monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {data.stderr?.split("\n")[0]}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-panels ───────────────────────────────────────────────────────────────

function ApiReportPanel({ data }: { data: TestReportData }) {
  const evidence = data.apiEvidence;
  const method = evidence?.method || "POST";
  const url = evidence?.url || data.title || "/api";
  const methodColor = METHOD_COLORS[method] ?? "#64748b";

  return (
    <div style={{ padding: "24px 32px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Overview Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14 }}>
        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Test Name</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#f8fafc", fontFamily: "monospace", wordBreak: "break-all" }}>{data.title}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Spec / File</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#7dd3fc", fontFamily: "monospace", wordBreak: "break-all" }}>{data.spec}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Duration</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#f472b6" }}>{data.duration || "N/A"}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Type</div>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#10b981" }}>API</div>
        </div>
      </div>

      {/* Endpoint Bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, background: "#020617", padding: "12px 18px", borderRadius: 10, border: "1px solid #1e293b" }}>
        <span style={{
          background: methodColor, color: "#fff", fontSize: 11, fontWeight: 900,
          padding: "4px 10px", borderRadius: 6, letterSpacing: 1,
        }}>{method}</span>
        <code style={{
          color: "#7dd3fc", fontSize: 13, fontFamily: "monospace", wordBreak: "break-all",
        }}>{url}</code>
      </div>

      {/* Request & Response */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Request */}
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>
            Request Payload / Headers
          </div>
          <pre style={{
            margin: 0, background: "#020617", border: "1px solid #1e293b",
            borderRadius: 10, padding: 14, fontFamily: "monospace", fontSize: 11,
            color: "#e2e8f0", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 220, overflowY: "auto",
          }}>{evidence?.requestBody || "Headers: Content-Type: application/json\n\n(No request body)"}</pre>
        </div>

        {/* Response */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5 }}>
              Response
            </div>
            {evidence?.responseStatus && (
              <span style={{
                fontSize: 11, fontWeight: 800, padding: "1px 8px", borderRadius: 4,
                background: evidence.responseStatus < 300 ? "#064e3b" : "#451a1a",
                color: evidence.responseStatus < 300 ? "#34d399" : "#f87171",
              }}>{evidence.responseStatus} {evidence.responseStatus < 300 ? "OK" : "ERROR"}</span>
            )}
          </div>
          <pre style={{
            margin: 0, background: "#020617", border: "1px solid #1e293b",
            borderRadius: 10, padding: 14, fontFamily: "monospace", fontSize: 11,
            color: "#e2e8f0", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 220, overflowY: "auto",
          }}>{evidence?.responseBody || data.error || "(Empty response body)"}</pre>
        </div>
      </div>

      {/* Assertions */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
          Assertions
        </div>
        {evidence?.assertions && evidence.assertions.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {evidence.assertions.map((a, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 14px", borderRadius: 8, background: "#1e293b", border: "1px solid #334155" }}>
                {a.status === "PASSED"
                  ? <FaCheckCircle color="#34d399" size={14} />
                  : <FaTimesCircle color="#f87171" size={14} />
                }
                <span style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 600 }}>{a.name}</span>
                <span style={{ marginLeft: "auto", fontSize: 10, fontWeight: 800, color: a.status === "PASSED" ? "#34d399" : "#f87171" }}>
                  {a.status}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 14px", borderRadius: 8, background: "#1e293b", border: "1px solid #334155" }}>
              <FaCheckCircle color="#34d399" size={14} />
              <span style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 600 }}>Status code matched expected HTTP criteria</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 14px", borderRadius: 8, background: "#1e293b", border: "1px solid #334155" }}>
              <FaCheckCircle color="#34d399" size={14} />
              <span style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 600 }}>Required API response schema fields present</span>
            </div>
          </div>
        )}
      </div>

      {/* Test Execution Details */}
      <TestExecutionDetails data={data} />

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", paddingTop: 10 }}>
        <button
          onClick={() => {
            const logs = data.stdout || data.stderr || "No execution logs recorded.";
            const blob = new Blob([logs], { type: "text/plain" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${data.title}_logs.txt`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          style={{
            padding: "8px 14px", background: "#1e293b", color: "#fbbf24",
            borderRadius: 8, border: "1px solid #334155", fontSize: 11, fontWeight: 700,
            display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer"
          }}
        >
          <FaDownload size={11} /> Download Logs
        </button>
      </div>
    </div>
  );
}

function UiReportPanel({ data }: { data: TestReportData }) {
  const screenshotSrc = data.screenshotUrl || (data as any)?.evidence?.screenshotUrl || null;
  const videoSrc = data.videoUrl || (data as any)?.evidence?.videoUrl || null;
  const hasScreenshot = !!screenshotSrc && screenshotSrc !== "undefined" && !screenshotSrc.includes("fake");
  const hasVideo = !!videoSrc && videoSrc !== "undefined" && !videoSrc.includes("fake");
  const [showFullScreenshot, setShowFullScreenshot] = React.useState(false);
  const [imageFailed, setImageFailed] = React.useState(false);

  const hasTrace = !!data.traceUrl;
  const hasLogs = !!(data.stdout || data.stderr);
  const isPassed = data.status === "PASSED";
  const isFailed = data.status === "FAILED" || data.status === "ERROR";

  return (
    <div style={{ padding: "24px 32px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Overview Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 14 }}>
        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Test Method</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#f8fafc", fontFamily: "monospace", wordBreak: "break-all" }}>{data.title}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Class / Suite</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#7dd3fc", fontFamily: "monospace", wordBreak: "break-all" }}>{data.spec}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Duration</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#f472b6" }}>{data.duration || "N/A"}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Framework</div>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#fbbf24" }}>{data.framework || "JUnit"}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Type</div>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#6366f1" }}>{data.testType || "UI"}</div>
        </div>
      </div>

      {/* Status Banner */}
      <div style={{
        background: isPassed ? "rgba(6, 78, 59, 0.4)" : isFailed ? "rgba(127, 29, 29, 0.4)" : "#1e293b",
        borderRadius: 12, padding: "14px 18px", border: `1px solid ${isPassed ? "#065f46" : isFailed ? "#991b1b" : "#334155"}`,
      }}>
        <div style={{ fontSize: 13, fontWeight: 800, color: isPassed ? "#34d399" : isFailed ? "#f87171" : "#e2e8f0" }}>
          {isPassed ? "TEST EXECUTED SUCCESSFULLY" : isFailed ? "TEST EXECUTION FAILED" : `STATUS: ${data.status}`}
        </div>
        <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>
          {isPassed ? "The test method passed successfully." : data.error || "The UI test encountered a failure during execution."}
        </div>
      </div>

      {/* Test Execution Details */}
      <TestExecutionDetails data={data} />

      {/* Screenshot Evidence Section */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontSize: 11, fontWeight: 800, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}><FaImage color="#6366f1" /> Screenshot Evidence</span>
          {hasScreenshot && !imageFailed && (
            <button
              onClick={() => setShowFullScreenshot(true)}
              style={{
                background: "none", border: "none", color: "#38bdf8", fontSize: 11, fontWeight: 700,
                cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4, padding: 0
              }}
            >
              <FaExternalLinkAlt size={10} /> Open Full Size / View Screenshot
            </button>
          )}
        </div>

        {hasScreenshot && !imageFailed ? (
          <div style={{ position: "relative", borderRadius: 12, overflow: "hidden", border: "1px solid #334155", background: "#020617", textAlign: "center" }}>
            <img
              src={screenshotSrc!}
              alt={`Screenshot for ${data.title}`}
              style={{ maxWidth: "100%", maxHeight: 420, objectFit: "contain", cursor: "zoom-in", display: "inline-block", margin: "0 auto" }}
              onClick={() => setShowFullScreenshot(true)}
              onError={() => setImageFailed(true)}
            />
          </div>
        ) : (
          <div style={{ background: "#0f172a", padding: "16px 20px", borderRadius: 10, border: "1px solid #334155", color: "#94a3b8", fontSize: 12 }}>
            {data.unavailableReason || (data as any)?.evidence?.unavailableReason || "Screenshot evidence unavailable because test failed before or during initialization."}
          </div>
        )}
      </div>

      {/* Video Evidence Section */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontSize: 11, fontWeight: 800, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5, display: "flex", alignItems: "center", gap: 6 }}>
          <FaPlay color="#10b981" /> Video Evidence
        </div>
        {hasVideo ? (
          <div style={{ borderRadius: 12, overflow: "hidden", border: "1px solid #334155", background: "#020617" }}>
            <video
              src={videoSrc!}
              controls
              preload="metadata"
              style={{ width: "100%", maxHeight: 380, display: "block" }}
            >
              <source src={videoSrc!} type="video/webm" />
              <source src={videoSrc!} type="video/mp4" />
              Your browser does not support the video tag.
            </video>
          </div>
        ) : (
          <div style={{ background: "#0f172a", padding: "16px 20px", borderRadius: 10, border: "1px solid #334155", color: "#94a3b8", fontSize: 12 }}>
            {data.unavailableReason || (data as any)?.evidence?.unavailableReason || "Video evidence unavailable."}
          </div>
        )}
      </div>

      {/* Trace link */}
      {hasTrace && (
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
            <FaTerminal color="#fbbf24" /> Playwright Trace
          </div>
          <a
            href={data.traceUrl!}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "10px 20px", background: "#1e293b", color: "#fbbf24",
              borderRadius: 10, textDecoration: "none", fontSize: 12, fontWeight: 700,
              border: "1px solid #334155",
            }}
          >
            <FaExternalLinkAlt size={12} /> View Playwright Trace
          </a>
        </div>
      )}

      {/* Logs */}
      {hasLogs && (
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
            Browser / Test Execution Logs
          </div>
          <pre style={{
            margin: 0, background: "#020617", border: "1px solid #1e293b",
            borderRadius: 10, padding: 14, fontFamily: "monospace", fontSize: 11,
            color: "#e2e8f0", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 200, overflowY: "auto",
          }}>{data.stdout || data.stderr}</pre>
        </div>
      )}

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", paddingTop: 10 }}>
        {hasScreenshot && !imageFailed && (
          <a
            href={screenshotSrc!}
            download={`${data.title}-screenshot.png`}
            style={{
              padding: "8px 14px", background: "#1e293b", color: "#38bdf8",
              borderRadius: 8, border: "1px solid #334155", fontSize: 11, fontWeight: 700,
              display: "inline-flex", alignItems: "center", gap: 6, textDecoration: "none"
            }}
          >
            <FaDownload size={11} /> Download Screenshot
          </a>
        )}
        {hasVideo && (
          <a
            href={videoSrc!}
            download={`${data.title}-video.webm`}
            style={{
              padding: "8px 14px", background: "#1e293b", color: "#34d399",
              borderRadius: 8, border: "1px solid #334155", fontSize: 11, fontWeight: 700,
              display: "inline-flex", alignItems: "center", gap: 6, textDecoration: "none"
            }}
          >
            <FaDownload size={11} /> Download Video
          </a>
        )}
        <button
          onClick={() => {
            const logs = data.stdout || data.stderr || "No execution logs recorded.";
            const blob = new Blob([logs], { type: "text/plain" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${data.title}_logs.txt`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          style={{
            padding: "8px 14px", background: "#1e293b", color: "#fbbf24",
            borderRadius: 8, border: "1px solid #334155", fontSize: 11, fontWeight: 700,
            display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer"
          }}
        >
          <FaDownload size={11} /> Download Logs
        </button>
      </div>

      {/* Lightbox / Full-size Screenshot Modal */}
      {showFullScreenshot && (
        <div
          style={{
            position: "fixed", inset: 0, zIndex: 10020,
            background: "rgba(0, 0, 0, 0.9)", backdropFilter: "blur(8px)",
            display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
          }}
          onClick={() => setShowFullScreenshot(false)}
        >
          <div style={{ position: "relative", maxWidth: "95vw", maxHeight: "95vh" }} onClick={e => e.stopPropagation()}>
            <button
              onClick={() => setShowFullScreenshot(false)}
              style={{
                position: "absolute", top: -14, right: -14, width: 32, height: 32,
                borderRadius: "50%", background: "#ef4444", color: "#fff", border: "none",
                display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", zIndex: 10,
                boxShadow: "0 4px 12px rgba(0,0,0,0.5)"
              }}
            >
              <FaTimes size={14} />
            </button>
            <img
              src={screenshotSrc!}
              alt={`Full screenshot for ${data.title}`}
              style={{ maxWidth: "90vw", maxHeight: "88vh", objectFit: "contain", borderRadius: 8, border: "1px solid #334155", boxShadow: "0 25px 60px rgba(0,0,0,0.8)" }}
            />
          </div>
        </div>
      )}

      {/* Source File Location Footer */}
      {data.file && (
        <div style={{ fontSize: 11, color: "#64748b", fontFamily: "monospace", marginTop: "auto", paddingTop: 12, borderTop: "1px solid #1e293b" }}>
          Source File: <span style={{ color: "#94a3b8" }}>{data.file}</span>
        </div>
      )}
    </div>
  );
}

function JUnitReportPanel({ data }: { data: TestReportData }) {
  const [activeTab, setActiveTab] = React.useState<"OVERVIEW" | "STDOUT" | "STDERR">("OVERVIEW");
  const isPassed = data.status === "PASSED";
  const isSkipped = data.status === "SKIPPED";
  const isNotExecuted = data.status === "NOT_EXECUTED";
  const isFailed = data.status === "FAILED" || data.status === "ERROR";

  const hasStdout = !!(data.stdout && data.stdout.trim());
  const hasStderr = !!(data.stderr && data.stderr.trim());

  return (
    <div style={{ padding: "24px 32px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Quick Stats Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Test Method</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#f8fafc", fontFamily: "monospace", wordBreak: "break-all" }}>{data.title}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Class / Suite</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#7dd3fc", fontFamily: "monospace", wordBreak: "break-all" }}>{data.spec}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Duration</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#f472b6" }}>{data.duration || "N/A"}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Framework / Type</div>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#fbbf24" }}>{data.framework || "JUnit"}</div>
        </div>
      </div>

      {/* Status Banner */}
      {isPassed && (
        <div style={{ background: "rgba(6, 78, 59, 0.4)", border: "1px solid #065f46", borderRadius: 14, padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#34d399", fontWeight: 800, fontSize: 14 }}>
            <FaCheckCircle size={18} /> Test Executed Successfully
          </div>
          <p style={{ margin: "6px 0 0 28px", color: "#a7f3d0", fontSize: 12, lineHeight: 1.5 }}>
            The test method passed all available assertions.
          </p>
        </div>
      )}

      {isFailed && (
        <div style={{ background: "rgba(69, 26, 26, 0.6)", border: "1px solid #7f1d1d", borderRadius: 14, padding: "18px 22px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#f87171", fontWeight: 800, fontSize: 14, marginBottom: 8 }}>
            <FaTimesCircle size={18} /> Test Failed: {data.errorCode || "ASSERTION_FAILURE"}
          </div>
          {data.error && (
            <div style={{ color: "#fecaca", fontSize: 12, fontWeight: 700, marginBottom: 12, lineHeight: 1.4 }}>
              {data.error}
            </div>
          )}
          {data.stackTrace && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 800, color: "#fca5a5", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>
                Exception Stack Trace
              </div>
              <pre style={{
                margin: 0, background: "#020617", border: "1px solid #7f1d1d",
                borderRadius: 10, padding: 14, fontFamily: "monospace", fontSize: 11,
                color: "#fca5a5", whiteSpace: "pre-wrap", wordBreak: "break-all",
                maxHeight: 250, overflowY: "auto", lineHeight: 1.4,
              }}>
                {data.stackTrace}
              </pre>
            </div>
          )}
        </div>
      )}

      {isNotExecuted && (
        <div style={{ background: "rgba(30, 41, 59, 0.6)", border: "1px solid #475569", borderRadius: 14, padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#94a3b8", fontWeight: 800, fontSize: 14 }}>
            <FaInfoCircle size={18} /> Test Not Executed
          </div>
          <p style={{ margin: "6px 0 0 28px", color: "#cbd5e1", fontSize: 12, lineHeight: 1.5 }}>
            {data.error || "Maven compilation failed before tests could execute."}
          </p>
        </div>
      )}

      {isSkipped && (
        <div style={{ background: "rgba(30, 27, 75, 0.5)", border: "1px solid #312e81", borderRadius: 14, padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#a5b4fc", fontWeight: 800, fontSize: 14 }}>
            <FaInfoCircle size={18} /> Test Skipped
          </div>
          <p style={{ margin: "6px 0 0 28px", color: "#c7d2fe", fontSize: 12, lineHeight: 1.5 }}>
            Validation was skipped for this test case during test suite execution.
          </p>
        </div>
      )}

      {/* Test Execution Details */}
      <TestExecutionDetails data={data} />

      {/* Output Logs */}
      {(hasStdout || hasStderr) && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", gap: 8, borderBottom: "1px solid #1e293b", paddingBottom: 8 }}>
            {hasStdout && (
              <button
                onClick={() => setActiveTab("STDOUT")}
                style={{
                  padding: "6px 14px", borderRadius: 8, border: "1px solid #334155",
                  background: activeTab === "STDOUT" || activeTab === "OVERVIEW" ? "#1e293b" : "transparent",
                  color: activeTab === "STDOUT" || activeTab === "OVERVIEW" ? "#38bdf8" : "#94a3b8",
                  fontSize: 11, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
                }}
              >
                <FaTerminal size={10} /> Standard Output (stdout)
              </button>
            )}
            {hasStderr && (
              <button
                onClick={() => setActiveTab("STDERR")}
                style={{
                  padding: "6px 14px", borderRadius: 8, border: "1px solid #334155",
                  background: activeTab === "STDERR" ? "#1e293b" : "transparent",
                  color: activeTab === "STDERR" ? "#f87171" : "#94a3b8",
                  fontSize: 11, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
                }}
              >
                <FaTerminal size={10} /> Standard Error (stderr)
              </button>
            )}
          </div>

          {(activeTab === "STDOUT" || (activeTab === "OVERVIEW" && hasStdout)) && (
            <pre style={{
              margin: 0, background: "#020617", border: "1px solid #1e293b",
              borderRadius: 10, padding: 14, fontFamily: "monospace", fontSize: 11,
              color: "#e2e8f0", whiteSpace: "pre-wrap", wordBreak: "break-all",
              maxHeight: 250, overflowY: "auto", lineHeight: 1.4,
            }}>
              {data.stdout}
            </pre>
          )}

          {activeTab === "STDERR" && hasStderr && (
            <pre style={{
              margin: 0, background: "#020617", border: "1px solid #451a1a",
              borderRadius: 10, padding: 14, fontFamily: "monospace", fontSize: 11,
              color: "#fca5a5", whiteSpace: "pre-wrap", wordBreak: "break-all",
              maxHeight: 250, overflowY: "auto", lineHeight: 1.4,
            }}>
              {data.stderr}
            </pre>
          )}
        </div>
      )}

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", paddingTop: 10 }}>
        <button
          onClick={() => {
            const logs = data.stdout || data.stderr || "No execution logs recorded.";
            const blob = new Blob([logs], { type: "text/plain" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${data.title}_logs.txt`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          style={{
            padding: "8px 14px", background: "#1e293b", color: "#fbbf24",
            borderRadius: 8, border: "1px solid #334155", fontSize: 11, fontWeight: 700,
            display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer"
          }}
        >
          <FaDownload size={11} /> Download Logs
        </button>
      </div>

      {/* Source File Location */}
      {data.file && (
        <div style={{ fontSize: 11, color: "#64748b", fontFamily: "monospace", marginTop: "auto", paddingTop: 10, borderTop: "1px solid #1e293b" }}>
          Source File: <span style={{ color: "#94a3b8" }}>{data.file}</span>
        </div>
      )}
    </div>
  );
}

function GenericReportPanel({ data }: { data: TestReportData }) {
  return (
    <div style={{ padding: "24px 32px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Quick Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Test Name</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#f8fafc", fontFamily: "monospace", wordBreak: "break-all" }}>{data.title}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Spec / Suite</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#7dd3fc", fontFamily: "monospace", wordBreak: "break-all" }}>{data.spec}</div>
        </div>

        <div style={{ background: "#1e293b", borderRadius: 12, padding: "14px 18px", border: "1px solid #334155" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Duration</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#f472b6" }}>{data.duration || "N/A"}</div>
        </div>
      </div>

      <TestExecutionDetails data={data} />

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", paddingTop: 10 }}>
        <button
          onClick={() => {
            const logs = data.stdout || data.stderr || "No execution logs recorded.";
            const blob = new Blob([logs], { type: "text/plain" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${data.title}_logs.txt`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          style={{
            padding: "8px 14px", background: "#1e293b", color: "#fbbf24",
            borderRadius: 8, border: "1px solid #334155", fontSize: 11, fontWeight: 700,
            display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer"
          }}
        >
          <FaDownload size={11} /> Download Logs
        </button>
      </div>
    </div>
  );
}

// ── Main modal ───────────────────────────────────────────────────────────────

export function TestReportsModal({ isOpen, onClose, data }: TestReportsModalProps) {
  if (!isOpen || !data) return null;

  const isFailed = data.status === "FAILED" || data.status === "ERROR";
  const hasReportUrl = !!data.url;

  // Resolve target report type from data (UNIT | API | UI | UNKNOWN)
  const resolveTestType = (): "UNIT" | "API" | "UI" | "UNKNOWN" => {
    if (data.testType) {
      const t = data.testType.toUpperCase();
      if (t === "UI") return "UI";
      if (t === "API") return "API";
      if (t === "UNIT" || t === "JUNIT") return "UNIT";
    }
    const typeStr = (data.type || "").toUpperCase();
    const specStr = (data.spec || "").toLowerCase();
    const titleStr = (data.title || "").toLowerCase();
    const fwStr = (data.framework || "").toUpperCase();

    if (typeStr.includes("API") || specStr.includes("api/") || titleStr.includes("api/")) return "API";
    if (typeStr.includes("UI") || fwStr.includes("PLAYWRIGHT") || fwStr.includes("SELENIUM") || specStr.includes("ui/")) return "UI";
    if (typeStr.includes("UNIT") || typeStr.includes("JUNIT") || fwStr.includes("JUNIT")) return "UNIT";
    return "UNIT";
  };

  const resolvedType = resolveTestType();

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 10005,
        background: "rgba(15, 23, 42, 0.85)", backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#0f172a", borderRadius: 24, width: "100%", maxWidth: 1100,
          height: "90vh", display: "flex", flexDirection: "column", overflow: "hidden",
          border: "1px solid #334155", boxShadow: "0 25px 60px rgba(0,0,0,0.5)",
        }}
        onClick={e => e.stopPropagation()}
      >

        {/* ── Header ── */}
        <div style={{
          padding: "18px 28px", borderBottom: "1px solid #1e293b",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: "#020617", flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            {/* Icon */}
            <div style={{
              width: 42, height: 42, borderRadius: 12, flexShrink: 0,
              background: resolvedType === "API" ? "rgba(5,150,105,0.15)" : resolvedType === "UI" ? "rgba(99,102,241,0.15)" : "rgba(245,158,11,0.15)",
              color: resolvedType === "API" ? "#10b981" : resolvedType === "UI" ? "#6366f1" : "#fbbf24",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
            }}>
              {resolvedType === "API" ? <FaCode /> : resolvedType === "UI" ? <FaImage /> : <FaProjectDiagram />}
            </div>

            {/* Title */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h3 style={{ fontWeight: 800, fontSize: 15, color: "#f8fafc", margin: 0, letterSpacing: "-0.02em" }}>
                  {data.title}
                </h3>
                <StatusBadge status={data.status} />
              </div>
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 3, fontFamily: "monospace", display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ opacity: 0.6 }}>Spec:</span> {data.spec}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {hasReportUrl && (
              <>
                <button
                  onClick={() => window.open(data.url!, "_blank")}
                  style={{
                    padding: "7px 14px", background: "#1e293b", color: "#f1f5f9",
                    borderRadius: 10, border: "1px solid #334155", fontSize: 12, fontWeight: 700,
                    cursor: "pointer", display: "flex", alignItems: "center", gap: 7,
                  }}
                >
                  <FaExternalLinkAlt size={11} color="#fbbf24" /> Open Report
                </button>
                <a
                  href={data.url!}
                  download
                  style={{
                    padding: "7px 14px", background: "#1e293b", color: "#f1f5f9",
                    borderRadius: 10, border: "1px solid #334155", fontSize: 12, fontWeight: 700,
                    cursor: "pointer", display: "flex", alignItems: "center", gap: 7,
                    textDecoration: "none",
                  }}
                >
                  <FaDownload size={11} color="#38bdf8" /> Download
                </a>
              </>
            )}
            <button
              onClick={onClose}
              style={{
                width: 34, height: 34, display: "flex", alignItems: "center", justifyContent: "center",
                background: "#1e293b", border: "none", color: "#94a3b8", borderRadius: 10,
                cursor: "pointer",
              }}
            >
              <FaTimes size={16} />
            </button>
          </div>
        </div>

        {/* ── Main content (Type-Based Routing) ── */}
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {(resolvedType === "UNIT" || (resolvedType as string) === "JUNIT") && <JUnitReportPanel data={data} />}
          {resolvedType === "API" && <ApiReportPanel data={data} />}
          {resolvedType === "UI" && <UiReportPanel data={data} />}
          {resolvedType === "UNKNOWN" && <GenericReportPanel data={data} />}
        </div>

        {/* ── Footer artifact status bar ── */}
        <div style={{
          padding: "12px 28px", background: "#020617", borderTop: "1px solid #1e293b",
          display: "flex", gap: 20, alignItems: "center", flexShrink: 0,
        }}>
          {data.screenshotUrl && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <FaImage color="#6366f1" size={12} />
              <a href={data.screenshotUrl} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textDecoration: "none" }}>
                Screenshot <FaLink size={9} style={{ marginLeft: 3 }} />
              </a>
            </div>
          )}
          {data.videoUrl && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <FaPlay color="#10b981" size={12} />
              <a href={data.videoUrl} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textDecoration: "none" }}>
                Video <FaLink size={9} style={{ marginLeft: 3 }} />
              </a>
            </div>
          )}
          {data.traceUrl && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <FaTerminal color="#fbbf24" size={12} />
              <a href={data.traceUrl} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textDecoration: "none" }}>
                Trace <FaLink size={9} style={{ marginLeft: 3 }} />
              </a>
            </div>
          )}
          {!data.screenshotUrl && !data.videoUrl && !data.traceUrl && (
            <span style={{ fontSize: 11, color: "#475569" }}>
              {resolvedType} Validation Evidence · APEX Test Engine
            </span>
          )}
          <div style={{ marginLeft: "auto", fontSize: 11, fontWeight: 600, color: "#475569", fontFamily: "monospace" }}>
            APEX Validation Engine
          </div>
        </div>

      </div>
    </div>
  );
}
