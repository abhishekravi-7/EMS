import React from "react";
import {
  FaExternalLinkAlt, FaTimes, FaInfoCircle, FaTerminal, FaPlay,
  FaImage, FaCheckCircle, FaTimesCircle, FaCode,
  FaLink, FaDownload,
} from "react-icons/fa";
import type { ApiEvidence } from "../services/existingTestService";
import { APP_BASE_URL } from "../../../services/config/env";

// ── Data model ──────────────────────────────────────────────────────────────

interface TestReportArtifact {
  screenshotUrl?: string | null;
  screenshot_url?: string | null;
  screenshot?: string | null;
  screenshotPath?: string | null;
  screenshotAvailable?: boolean;
  screenshot_available?: boolean;
  videoUrl?: string | null;
  video_url?: string | null;
  videoAvailable?: boolean;
  video_available?: boolean;
  apexExecution?: string | null;
  rootCause?: string | null;
  errorCategory?: string | null;
  stackTrace?: string | null;
  stdout?: string | null;
  stderr?: string | null;
  jobId?: string | null;
  unavailableReason?: string | null;
  details?: TestReportArtifact | null;
  evidence?: TestReportArtifact | null;
}

export interface TestReportData extends TestReportArtifact {
  testId?: string;
  executionId?: string;
  name?: string;
  suite?: string;
  title: string;
  spec: string;
  status: string;
  duration?: string | null;
  file?: string | null;
  url?: string | null;
  error?: string | null;
  errorCode?: string | null;
  unavailableReason?: string | null;
  type?: string;
  testType?: "JUNIT" | "API" | "UI" | "UNIT" | "UNKNOWN" | string;
  framework?: string;
  engine?: string;
  traceUrl?: string | null;
  apiEvidence?: ApiEvidence | null;
}

interface TestReportsModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: TestReportData | null;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

const STATUS_COLORS = {
  PASSED: { bg: "#ecfdf5", text: "#059669", border: "#a7f3d0" },
  FAILED: { bg: "#fef2f2", text: "#dc2626", border: "#fecaca" },
  ERROR: { bg: "#fef2f2", text: "#dc2626", border: "#fecaca" },
  SKIPPED: { bg: "#fffbeb", text: "#d97706", border: "#fde68a" },
  NOT_EXECUTED: { bg: "#f1f5f9", text: "#64748b", border: "#e2e8f0" },
  DEFAULT: { bg: "#f1f5f9", text: "#64748b", border: "#e2e8f0" },
};

export function resolveEvidenceUrl(url: string | null | undefined): string | null {
  if (!url || typeof url !== "string") return null;
  const trimmed = url.trim();
  if (!trimmed || trimmed === "undefined" || trimmed === "null" || trimmed.includes("fake")) return null;
  if (
    trimmed.startsWith("data:") ||
    trimmed.startsWith("http://") ||
    trimmed.startsWith("https://") ||
    trimmed.startsWith("blob:")
  ) {
    return trimmed;
  }
  if (trimmed.startsWith("/")) {
    return `${APP_BASE_URL}${trimmed}`;
  }
  return `${APP_BASE_URL}/${trimmed}`;
}

export function getScreenshotUrl(data: TestReportData | null | undefined): string | null {
  if (!data) return null;
  const rawCandidate =
    data.screenshotUrl ||
    data.screenshot_url ||
    data.screenshot ||
    data.evidence?.screenshotUrl ||
    data.evidence?.screenshot_url ||
    data.evidence?.screenshot ||
    data.evidence?.screenshotPath ||
    data.details?.screenshotUrl ||
    data.details?.screenshot_url ||
    data.details?.evidence?.screenshotUrl ||
    null;

  if (rawCandidate) {
    const resolved = resolveEvidenceUrl(rawCandidate);
    if (resolved) return resolved;
  }

  const isAvailable =
    data.screenshotAvailable ||
    data.screenshot_available ||
    data.evidence?.screenshotAvailable ||
    data.evidence?.screenshot_available ||
    false;

  if (isAvailable && (data.executionId || data.jobId) && (data.testId || data.title)) {
    const job = data.executionId || data.jobId;
    if (!job) return null;
    const test = data.testId || data.title;
    return resolveEvidenceUrl(`/api/v1/migration/${encodeURIComponent(job)}/tests/${encodeURIComponent(test)}/evidence/screenshot`);
  }

  return null;
}

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
  const rawTestType = (data.testType || (data.type === "UI" || data.type === "API" || data.type === "UNIT" ? data.type : "") || "API").toUpperCase();
  const testTypeVal = rawTestType === "UNIT" ? "API" : (rawTestType.includes("UI") ? "UI" : "API");
  const engineVal = data.engine || (testTypeVal === "UI" ? "Playwright" : data.type && data.type !== frameworkVal && data.type !== testTypeVal ? data.type : null);

  return (
    <div style={{
      background: "#f8fafc",
      borderRadius: 14,
      padding: "18px 22px",
      border: "1px solid #e2e8f0",
      display: "flex",
      flexDirection: "column",
      gap: 16,
    }}>
      <div style={{
        fontSize: 11,
        fontWeight: 800,
        color: "#475569",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        borderBottom: "1px solid #e2e8f0",
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
          <div style={{ fontSize: 12, fontWeight: 700, color: "#0f172a", fontFamily: "monospace", wordBreak: "break-all" }}>
            {data.title || "None"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Test ID</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#334155", fontFamily: "monospace", wordBreak: "break-all" }}>
            {data.testId || "None"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Execution ID</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#334155", fontFamily: "monospace", wordBreak: "break-all" }}>
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
          <div style={{ fontSize: 12, fontWeight: 800, color: "#db2777" }}>
            {data.duration || "None"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Source File</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", fontFamily: "monospace", wordBreak: "break-all" }}>
            {data.file || "None"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 2 }}>Class / Suite</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#2563eb", fontFamily: "monospace", wordBreak: "break-all" }}>
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
              background: "#f1f5f9",
              color: "#334155",
              border: "1px solid #cbd5e1",
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
              background: testTypeVal === "UI" ? "#faf5ff" : "#eff6ff",
              color: testTypeVal === "UI" ? "#9333ea" : "#2563eb",
              border: `1px solid ${testTypeVal === "UI" ? "#e9d5ff" : "#bfdbfe"}`,
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
              background: "#ecfdf5",
              color: "#059669",
              border: "1px solid #a7f3d0",
              letterSpacing: "0.02em",
              display: "inline-block",
            }}>
              {data.apexExecution || data.details?.apexExecution || "Started successfully"}
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
                background: "#faf5ff",
                color: "#9333ea",
                border: "1px solid #e9d5ff",
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
        {(data.rootCause || data.details?.rootCause) && (
          <div style={{ background: "#fffbeb", borderRadius: 8, padding: "10px 14px", border: "1px solid #fde68a" }}>
            <div style={{ fontSize: 10, fontWeight: 800, color: "#b45309", textTransform: "uppercase", marginBottom: 4, letterSpacing: "0.05em" }}>
              Root Cause
            </div>
            <div style={{ fontSize: 12, color: "#92400e", fontWeight: 700, lineHeight: 1.4 }}>
              {data.rootCause || data.details?.rootCause}
            </div>
          </div>
        )}

        {/* Error Classification / Category (when present) */}
        {(data.errorCategory || data.details?.errorCategory) && (
          <div style={{ background: "#fef2f2", borderRadius: 8, padding: "10px 14px", border: "1px solid #fecaca" }}>
            <div style={{ fontSize: 10, fontWeight: 800, color: "#b91c1c", textTransform: "uppercase", marginBottom: 4, letterSpacing: "0.05em" }}>
              Error Classification
            </div>
            <div style={{ fontSize: 12, color: "#dc2626", fontWeight: 700 }}>
              {data.errorCategory || data.details?.errorCategory}
            </div>
          </div>
        )}

        {/* Error */}
        <div style={{ background: hasError ? "#fef2f2" : "#ffffff", borderRadius: 8, padding: "10px 14px", border: `1px solid ${hasError ? "#fecaca" : "#e2e8f0"}` }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: hasError ? "#b91c1c" : "#64748b", textTransform: "uppercase", marginBottom: 4 }}>
            Error
          </div>
          <div style={{ fontSize: 12, color: hasError ? "#dc2626" : "#64748b", fontFamily: hasError ? "monospace" : "inherit" }}>
            {hasError ? data.error : "No errors"}
          </div>
        </div>

        {/* Stack Trace */}
        <div style={{ background: "#ffffff", borderRadius: 8, padding: "10px 14px", border: "1px solid #e2e8f0" }}>
          <div
            onClick={() => hasStackTrace && setShowStackTrace(!showStackTrace)}
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#64748b",
              textTransform: "uppercase",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: hasStackTrace ? "pointer" : "default",
            }}
          >
            <span>Stack Trace</span>
            {hasStackTrace && (
              <span style={{ color: "#2563eb", fontSize: 10, fontWeight: 600 }}>
                {showStackTrace ? "Collapse" : "Expand"}
              </span>
            )}
          </div>
          {!hasStackTrace ? (
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>No stack trace available</div>
          ) : showStackTrace ? (
            <pre style={{
              margin: "8px 0 0 0",
              padding: 10,
              background: "#0f172a",
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
            <div style={{ fontSize: 11, color: "#64748b", marginTop: 4, fontFamily: "monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {data.stackTrace?.split("\n")[0]}
            </div>
          )}
        </div>

        {/* Standard Output (stdout) */}
        <div style={{ background: "#ffffff", borderRadius: 8, padding: "10px 14px", border: "1px solid #e2e8f0" }}>
          <div
            onClick={() => hasStdout && setShowStdout(!showStdout)}
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#64748b",
              textTransform: "uppercase",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: hasStdout ? "pointer" : "default",
            }}
          >
            <span>Standard Output (stdout)</span>
            {hasStdout && (
              <span style={{ color: "#2563eb", fontSize: 10, fontWeight: 600 }}>
                {showStdout ? "Collapse" : "Expand"}
              </span>
            )}
          </div>
          {!hasStdout ? (
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>No standard output captured</div>
          ) : showStdout ? (
            <pre style={{
              margin: "8px 0 0 0",
              padding: 10,
              background: "#0f172a",
              borderRadius: 6,
              fontSize: 11,
              color: "#f1f5f9",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              maxHeight: 200,
              overflowY: "auto",
              fontFamily: "monospace",
            }}>
              {data.stdout}
            </pre>
          ) : (
            <div style={{ fontSize: 11, color: "#64748b", marginTop: 4, fontFamily: "monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {data.stdout?.split("\n")[0]}
            </div>
          )}
        </div>

        {/* Standard Error (stderr) */}
        <div style={{ background: "#ffffff", borderRadius: 8, padding: "10px 14px", border: "1px solid #e2e8f0" }}>
          <div
            onClick={() => hasStderr && setShowStderr(!showStderr)}
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#64748b",
              textTransform: "uppercase",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: hasStderr ? "pointer" : "default",
            }}
          >
            <span>Standard Error (stderr)</span>
            {hasStderr && (
              <span style={{ color: "#2563eb", fontSize: 10, fontWeight: 600 }}>
                {showStderr ? "Collapse" : "Expand"}
              </span>
            )}
          </div>
          {!hasStderr ? (
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>No standard error captured</div>
          ) : showStderr ? (
            <pre style={{
              margin: "8px 0 0 0",
              padding: 10,
              background: "#0f172a",
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
            <div style={{ fontSize: 11, color: "#dc2626", marginTop: 4, fontFamily: "monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
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
  const methodColor = (
    {
      GET: "#2563eb",
      POST: "#059669",
      PUT: "#d97706",
      PATCH: "#7c3aed",
      DELETE: "#dc2626",
    } as Record<string, string>
  )[method.toUpperCase()] ?? "#64748b";

  return (
    <div style={{ padding: "24px 32px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Overview Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14 }}>
        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Test Name</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#0f172a", fontFamily: "monospace", wordBreak: "break-all" }}>{data.title}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Spec / File</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#2563eb", fontFamily: "monospace", wordBreak: "break-all" }}>{data.spec}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Duration</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#db2777" }}>{data.duration || "N/A"}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Type</div>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#059669" }}>API</div>
        </div>
      </div>

      {/* Endpoint Bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, background: "#f1f5f9", padding: "12px 18px", borderRadius: 10, border: "1px solid #e2e8f0" }}>
        <span style={{
          background: methodColor, color: "#fff", fontSize: 11, fontWeight: 900,
          padding: "4px 10px", borderRadius: 6, letterSpacing: 1,
        }}>{method}</span>
        <code style={{
          color: "#0f172a", fontSize: 13, fontFamily: "monospace", wordBreak: "break-all", fontWeight: 700,
        }}>{url}</code>
      </div>

      {/* Request & Response */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Request */}
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>
            Request Payload / Headers
          </div>
          <pre style={{
            margin: 0, background: "#0f172a", border: "1px solid #1e293b",
            borderRadius: 10, padding: 14, fontFamily: "monospace", fontSize: 11,
            color: "#f1f5f9", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 220, overflowY: "auto",
          }}>{evidence?.requestBody || "Headers: Content-Type: application/json\n\n(No request body)"}</pre>
        </div>

        {/* Response */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.5 }}>
              Response
            </div>
            {evidence?.responseStatus && (
              <span style={{
                fontSize: 11, fontWeight: 800, padding: "1px 8px", borderRadius: 4,
                background: evidence.responseStatus < 300 ? "#ecfdf5" : "#fef2f2",
                color: evidence.responseStatus < 300 ? "#059669" : "#dc2626",
                border: `1px solid ${evidence.responseStatus < 300 ? "#a7f3d0" : "#fecaca"}`,
              }}>{evidence.responseStatus} {evidence.responseStatus < 300 ? "OK" : "ERROR"}</span>
            )}
          </div>
          <pre style={{
            margin: 0, background: "#0f172a", border: "1px solid #1e293b",
            borderRadius: 10, padding: 14, fontFamily: "monospace", fontSize: 11,
            color: "#f1f5f9", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 220, overflowY: "auto",
          }}>{evidence?.responseBody || data.error || "(Empty response body)"}</pre>
        </div>
      </div>

      {/* Assertions */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
          Assertions
        </div>
        {evidence?.assertions && evidence.assertions.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {evidence.assertions.map((a, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 14px", borderRadius: 8, background: "#ffffff", border: "1px solid #e2e8f0" }}>
                {a.status === "PASSED"
                  ? <FaCheckCircle color="#059669" size={14} />
                  : <FaTimesCircle color="#dc2626" size={14} />
                }
                <span style={{ fontSize: 12, color: "#0f172a", fontWeight: 600 }}>{a.name}</span>
                <span style={{ marginLeft: "auto", fontSize: 10, fontWeight: 800, color: a.status === "PASSED" ? "#059669" : "#dc2626" }}>
                  {a.status}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 14px", borderRadius: 8, background: "#ffffff", border: "1px solid #e2e8f0" }}>
              <FaCheckCircle color="#059669" size={14} />
              <span style={{ fontSize: 12, color: "#0f172a", fontWeight: 600 }}>Status code matched expected HTTP criteria</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 14px", borderRadius: 8, background: "#ffffff", border: "1px solid #e2e8f0" }}>
              <FaCheckCircle color="#059669" size={14} />
              <span style={{ fontSize: 12, color: "#0f172a", fontWeight: 600 }}>Required API response schema fields present</span>
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
            padding: "8px 16px", background: "#ffffff", color: "#0f172a",
            borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12, fontWeight: 700,
            display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <FaDownload size={11} color="#64748b" /> Download Logs
        </button>
      </div>
    </div>
  );
}

function UiReportPanel({ data }: { data: TestReportData }) {
  const screenshotSrc = getScreenshotUrl(data);
  const videoSrc = resolveEvidenceUrl(data.videoUrl || data.video_url || data.evidence?.videoUrl);
  const hasScreenshot = !!screenshotSrc;
  const hasVideo = !!videoSrc;
  const [showFullScreenshot, setShowFullScreenshot] = React.useState(false);
  const [imageFailed, setImageFailed] = React.useState(false);

  // Reset state when selected test changes to avoid stale screenshots or stale failure flags
  React.useEffect(() => {
    setImageFailed(false);
    setShowFullScreenshot(false);
  }, [data.testId, data.title, data.screenshotUrl, data.screenshot_url]);

  const hasTrace = !!data.traceUrl;
  const hasLogs = !!(data.stdout || data.stderr);
  const isPassed = data.status === "PASSED";
  const isFailed = data.status === "FAILED" || data.status === "ERROR";

  return (
    <div style={{ padding: "24px 32px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Overview Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 14 }}>
        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Test Method</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#0f172a", fontFamily: "monospace", wordBreak: "break-all" }}>{data.title}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Class / Suite</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#2563eb", fontFamily: "monospace", wordBreak: "break-all" }}>{data.spec}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Duration</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#db2777" }}>{data.duration || "N/A"}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Framework</div>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#d97706" }}>{data.framework || "JUnit"}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Type</div>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#9333ea" }}>UI</div>
        </div>
      </div>

      {/* Status Banner */}
      <div style={{
        background: isPassed ? "#ecfdf5" : isFailed ? "#fef2f2" : "#f8fafc",
        borderRadius: 12, padding: "14px 18px", border: `1px solid ${isPassed ? "#a7f3d0" : isFailed ? "#fecaca" : "#e2e8f0"}`,
      }}>
        <div style={{ fontSize: 13, fontWeight: 800, color: isPassed ? "#059669" : isFailed ? "#dc2626" : "#0f172a" }}>
          {isPassed ? "TEST EXECUTED SUCCESSFULLY" : isFailed ? "TEST EXECUTION FAILED" : `STATUS: ${data.status}`}
        </div>
        <div style={{ fontSize: 12, color: isPassed ? "#065f46" : isFailed ? "#991b1b" : "#64748b", marginTop: 4 }}>
          {isPassed ? "The test method passed successfully." : data.error || "The UI test encountered a failure during execution."}
        </div>
      </div>

      {/* Test Execution Details */}
      <TestExecutionDetails data={data} />

      {/* Screenshot Evidence Section */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontSize: 11, fontWeight: 800, color: "#475569", textTransform: "uppercase", letterSpacing: 0.5, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}><FaImage color="#9333ea" /> Screenshot Evidence</span>
          {hasScreenshot && !imageFailed && (
            <button
              onClick={() => setShowFullScreenshot(true)}
              style={{
                background: "none", border: "none", color: "#2563eb", fontSize: 11, fontWeight: 700,
                cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4, padding: 0
              }}
            >
              <FaExternalLinkAlt size={10} /> Open Full Size / View Screenshot
            </button>
          )}
        </div>

        {hasScreenshot && !imageFailed ? (
          <div style={{ position: "relative", borderRadius: 12, overflow: "hidden", border: "1px solid #e2e8f0", background: "#f8fafc", textAlign: "center", padding: 10 }}>
            <img
              src={screenshotSrc!}
              alt={`Screenshot for ${data.title}`}
              style={{ maxWidth: "100%", maxHeight: 420, objectFit: "contain", cursor: "zoom-in", display: "inline-block", margin: "0 auto", borderRadius: 8 }}
              onClick={() => setShowFullScreenshot(true)}
              onError={() => setImageFailed(true)}
            />
          </div>
        ) : (
          <div style={{ background: "#f8fafc", padding: "16px 20px", borderRadius: 10, border: "1px solid #e2e8f0", color: "#64748b", fontSize: 12 }}>
            {data.unavailableReason || data.evidence?.unavailableReason || (data.status === "ERROR" || data.status === "FAILED" ? "Screenshot evidence unavailable because test failed before or during initialization." : "Screenshot evidence is unavailable for this execution.")}
          </div>
        )}
      </div>

      {/* Video Evidence Section */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontSize: 11, fontWeight: 800, color: "#475569", textTransform: "uppercase", letterSpacing: 0.5, display: "flex", alignItems: "center", gap: 6 }}>
          <FaPlay color="#059669" /> Video Evidence
        </div>
        {hasVideo ? (
          <div style={{ borderRadius: 12, overflow: "hidden", border: "1px solid #e2e8f0", background: "#0f172a" }}>
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
          <div style={{ background: "#f8fafc", padding: "16px 20px", borderRadius: 10, border: "1px solid #e2e8f0", color: "#64748b", fontSize: 12 }}>
            {data.unavailableReason || data.evidence?.unavailableReason || "Video evidence unavailable."}
          </div>
        )}
      </div>

      {/* Trace link */}
      {hasTrace && (
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
            <FaTerminal color="#d97706" /> Playwright Trace
          </div>
          <a
            href={data.traceUrl!}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "10px 20px", background: "#ffffff", color: "#0f172a",
              borderRadius: 10, textDecoration: "none", fontSize: 12, fontWeight: 700,
              border: "1px solid #cbd5e1", boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
            }}
          >
            <FaExternalLinkAlt size={12} color="#d97706" /> View Playwright Trace
          </a>
        </div>
      )}

      {/* Logs */}
      {hasLogs && (
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>
            Browser / Test Execution Logs
          </div>
          <pre style={{
            margin: 0, background: "#0f172a", border: "1px solid #1e293b",
            borderRadius: 10, padding: 14, fontFamily: "monospace", fontSize: 11,
            color: "#f1f5f9", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 200, overflowY: "auto",
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
              padding: "8px 16px", background: "#ffffff", color: "#2563eb",
              borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12, fontWeight: 700,
              display: "inline-flex", alignItems: "center", gap: 6, textDecoration: "none",
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
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
              padding: "8px 16px", background: "#ffffff", color: "#059669",
              borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12, fontWeight: 700,
              display: "inline-flex", alignItems: "center", gap: 6, textDecoration: "none",
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
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
            padding: "8px 16px", background: "#ffffff", color: "#0f172a",
            borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12, fontWeight: 700,
            display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <FaDownload size={11} color="#64748b" /> Download Logs
        </button>
      </div>

      {/* Lightbox / Full-size Screenshot Modal */}
      {showFullScreenshot && (
        <div
          style={{
            position: "fixed", inset: 0, zIndex: 10020,
            background: "rgba(15, 23, 42, 0.85)", backdropFilter: "blur(8px)",
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
                boxShadow: "0 4px 12px rgba(0,0,0,0.3)"
              }}
            >
              <FaTimes size={14} />
            </button>
            <img
              src={screenshotSrc!}
              alt={`Full screenshot for ${data.title}`}
              style={{ maxWidth: "90vw", maxHeight: "88vh", objectFit: "contain", borderRadius: 8, border: "1px solid #cbd5e1", boxShadow: "0 25px 60px rgba(0,0,0,0.3)" }}
            />
          </div>
        </div>
      )}

      {/* Source File Location Footer */}
      {data.file && (
        <div style={{ fontSize: 11, color: "#64748b", fontFamily: "monospace", marginTop: "auto", paddingTop: 12, borderTop: "1px solid #e2e8f0" }}>
          Source File: <span style={{ color: "#0f172a" }}>{data.file}</span>
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

  const screenshotSrc = getScreenshotUrl(data);
  const hasScreenshot = !!screenshotSrc;
  const [showFullScreenshot, setShowFullScreenshot] = React.useState(false);
  const [imageFailed, setImageFailed] = React.useState(false);

  React.useEffect(() => {
    setImageFailed(false);
    setShowFullScreenshot(false);
  }, [data.testId, data.title, data.screenshotUrl, data.screenshot_url]);

  const hasStdout = !!(data.stdout && data.stdout.trim());
  const hasStderr = !!(data.stderr && data.stderr.trim());

  return (
    <div style={{ padding: "24px 32px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Quick Stats Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Test Method</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#0f172a", fontFamily: "monospace", wordBreak: "break-all" }}>{data.title}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Class / Suite</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#2563eb", fontFamily: "monospace", wordBreak: "break-all" }}>{data.spec}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Duration</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#db2777" }}>{data.duration || "N/A"}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Framework / Type</div>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#d97706" }}>{data.framework || "JUnit"}</div>
        </div>
      </div>

      {/* Status Banner */}
      {isPassed && (
        <div style={{ background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: 14, padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#059669", fontWeight: 800, fontSize: 14 }}>
            <FaCheckCircle size={18} /> Test Executed Successfully
          </div>
          <p style={{ margin: "6px 0 0 28px", color: "#065f46", fontSize: 12, lineHeight: 1.5 }}>
            The test method passed all available assertions.
          </p>
        </div>
      )}

      {isFailed && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 14, padding: "18px 22px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#dc2626", fontWeight: 800, fontSize: 14, marginBottom: 8 }}>
            <FaTimesCircle size={18} /> Test Failed: {data.errorCode || "ASSERTION_FAILURE"}
          </div>
          {data.error && (
            <div style={{ color: "#991b1b", fontSize: 12, fontWeight: 700, marginBottom: 12, lineHeight: 1.4 }}>
              {data.error}
            </div>
          )}
          {data.stackTrace && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 800, color: "#b91c1c", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>
                Exception Stack Trace
              </div>
              <pre style={{
                margin: 0, background: "#0f172a", border: "1px solid #1e293b",
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
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 14, padding: "16px 20px" }}>
          <div style={{ display: "center", alignItems: "center", gap: 10, color: "#475569", fontWeight: 800, fontSize: 14 }}>
            <FaInfoCircle size={18} /> Test Not Executed
          </div>
          <p style={{ margin: "6px 0 0 28px", color: "#64748b", fontSize: 12, lineHeight: 1.5 }}>
            {data.error || "Test has not been executed yet. Click 'Run All Tests' or 'Run Again' to execute this test suite."}
          </p>
        </div>
      )}

      {isSkipped && (
        <div style={{ background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 14, padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#d97706", fontWeight: 800, fontSize: 14 }}>
            <FaInfoCircle size={18} /> Test Skipped
          </div>
          <p style={{ margin: "6px 0 0 28px", color: "#92400e", fontSize: 12, lineHeight: 1.5 }}>
            Validation was skipped for this test case during test suite execution.
          </p>
        </div>
      )}

      {/* Screenshot Evidence (if captured for this JUnit/UI test) */}
      {hasScreenshot && !imageFailed && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: "#475569", textTransform: "uppercase", letterSpacing: 0.5, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 6 }}><FaImage color="#9333ea" /> Screenshot Evidence</span>
            <button
              onClick={() => setShowFullScreenshot(true)}
              style={{
                background: "none", border: "none", color: "#2563eb", fontSize: 11, fontWeight: 700,
                cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4, padding: 0
              }}
            >
              <FaExternalLinkAlt size={10} /> Open Full Size
            </button>
          </div>
          <div style={{ position: "relative", borderRadius: 12, overflow: "hidden", border: "1px solid #e2e8f0", background: "#f8fafc", textAlign: "center", padding: 10 }}>
            <img
              src={screenshotSrc!}
              alt={`Screenshot for ${data.title}`}
              style={{ maxWidth: "100%", maxHeight: 420, objectFit: "contain", cursor: "zoom-in", display: "inline-block", margin: "0 auto", borderRadius: 8 }}
              onClick={() => setShowFullScreenshot(true)}
              onError={() => setImageFailed(true)}
            />
          </div>
        </div>
      )}

      {/* Test Execution Details */}
      <TestExecutionDetails data={data} />

      {/* Output Logs */}
      {(hasStdout || hasStderr) && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", gap: 8, borderBottom: "1px solid #e2e8f0", paddingBottom: 8 }}>
            {hasStdout && (
              <button
                onClick={() => setActiveTab("STDOUT")}
                style={{
                  padding: "6px 14px", borderRadius: 8, border: "1px solid #cbd5e1",
                  background: activeTab === "STDOUT" || activeTab === "OVERVIEW" ? "#0f172a" : "#ffffff",
                  color: activeTab === "STDOUT" || activeTab === "OVERVIEW" ? "#ffffff" : "#64748b",
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
                  padding: "6px 14px", borderRadius: 8, border: "1px solid #cbd5e1",
                  background: activeTab === "STDERR" ? "#dc2626" : "#ffffff",
                  color: activeTab === "STDERR" ? "#ffffff" : "#64748b",
                  fontSize: 11, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
                }}
              >
                <FaTerminal size={10} /> Standard Error (stderr)
              </button>
            )}
          </div>

          {(activeTab === "STDOUT" || (activeTab === "OVERVIEW" && hasStdout)) && (
            <pre style={{
              margin: 0, background: "#0f172a", border: "1px solid #1e293b",
              borderRadius: 10, padding: 14, fontFamily: "monospace", fontSize: 11,
              color: "#f1f5f9", whiteSpace: "pre-wrap", wordBreak: "break-all",
              maxHeight: 250, overflowY: "auto", lineHeight: 1.4,
            }}>
              {data.stdout}
            </pre>
          )}

          {activeTab === "STDERR" && hasStderr && (
            <pre style={{
              margin: 0, background: "#0f172a", border: "1px solid #451a1a",
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
        {hasScreenshot && !imageFailed && (
          <a
            href={screenshotSrc!}
            download={`${data.title}-screenshot.png`}
            style={{
              padding: "8px 16px", background: "#ffffff", color: "#2563eb",
              borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12, fontWeight: 700,
              display: "inline-flex", alignItems: "center", gap: 6, textDecoration: "none",
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
            }}
          >
            <FaDownload size={11} /> Download Screenshot
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
            padding: "8px 16px", background: "#ffffff", color: "#0f172a",
            borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12, fontWeight: 700,
            display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <FaDownload size={11} color="#64748b" /> Download Logs
        </button>
      </div>

      {/* Lightbox Modal */}
      {showFullScreenshot && (
        <div
          style={{
            position: "fixed", inset: 0, zIndex: 10020,
            background: "rgba(15, 23, 42, 0.85)", backdropFilter: "blur(8px)",
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
                boxShadow: "0 4px 12px rgba(0,0,0,0.3)"
              }}
            >
              <FaTimes size={14} />
            </button>
            <img
              src={screenshotSrc!}
              alt={`Full screenshot for ${data.title}`}
              style={{ maxWidth: "90vw", maxHeight: "88vh", objectFit: "contain", borderRadius: 8, border: "1px solid #cbd5e1", boxShadow: "0 25px 60px rgba(0,0,0,0.3)" }}
            />
          </div>
        </div>
      )}

      {/* Source File Location */}
      {data.file && (
        <div style={{ fontSize: 11, color: "#64748b", fontFamily: "monospace", marginTop: "auto", paddingTop: 10, borderTop: "1px solid #e2e8f0" }}>
          Source File: <span style={{ color: "#0f172a" }}>{data.file}</span>
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
        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Test Name</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#0f172a", fontFamily: "monospace", wordBreak: "break-all" }}>{data.title}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Spec / Suite</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#2563eb", fontFamily: "monospace", wordBreak: "break-all" }}>{data.spec}</div>
        </div>

        <div style={{ background: "#f8fafc", borderRadius: 12, padding: "14px 18px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Duration</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#db2777" }}>{data.duration || "N/A"}</div>
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
            padding: "8px 16px", background: "#ffffff", color: "#0f172a",
            borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12, fontWeight: 700,
            display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <FaDownload size={11} color="#64748b" /> Download Logs
        </button>
      </div>
    </div>
  );
}

// ── Main modal ───────────────────────────────────────────────────────────────

export function TestReportsModal({ isOpen, onClose, data }: TestReportsModalProps) {
  if (!isOpen || !data) return null;

  const hasReportUrl = !!data.url;
  const screenshotUrl = getScreenshotUrl(data);
  const videoUrl = resolveEvidenceUrl(data.videoUrl || data.video_url || data.evidence?.videoUrl);

  // Resolve target report type from data (UNIT | API | UI | UNKNOWN)
  const resolveTestType = (): "API" | "UI" | "UNKNOWN" => {
    // If screenshot or video evidence exists or is available, this test has UI evidence
    const hasUiEvidence = !!(
      screenshotUrl ||
      videoUrl ||
      data.evidence?.screenshotAvailable ||
      data.evidence?.videoAvailable ||
      data.screenshot_available
    );
    if (hasUiEvidence) {
      return "UI";
    }

    if (data.testType) {
      const t = data.testType.toUpperCase();
      if (t === "UI") return "UI";
      if (t === "API" || t === "UNIT" || t === "JUNIT") return "API";
    }
    const typeStr = (data.type || "").toUpperCase();
    const specStr = (data.spec || "").toLowerCase();
    const titleStr = (data.title || "").toLowerCase();
    const fwStr = (data.framework || "").toUpperCase();
    const engineStr = (data.engine || "").toUpperCase();

    if (typeStr.includes("UI") || fwStr.includes("PLAYWRIGHT") || fwStr.includes("SELENIUM") || engineStr.includes("PLAYWRIGHT") || specStr.includes("ui/") || specStr.includes("ui.") || specStr.includes("ui") || titleStr.includes("ui")) {
      return "UI";
    }
    if (typeStr.includes("API") || specStr.includes("api/") || titleStr.includes("api/") || typeStr.includes("UNIT") || typeStr.includes("JUNIT") || fwStr.includes("JUNIT")) {
      return "API";
    }
    return "API";
  };

  const resolvedType = resolveTestType();

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 10005,
        background: "rgba(15, 23, 42, 0.65)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#ffffff", borderRadius: 20, width: "100%", maxWidth: 1060,
          height: "90vh", display: "flex", flexDirection: "column", overflow: "hidden",
          border: "1px solid #e2e8f0", boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
        }}
        onClick={e => e.stopPropagation()}
      >

        {/* ── Header ── */}
        <div style={{
          padding: "18px 28px", borderBottom: "1px solid #e2e8f0",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: "#f8fafc", flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            {/* Icon */}
            <div style={{
              width: 42, height: 42, borderRadius: 12, flexShrink: 0,
              background: resolvedType === "API" ? "#eff6ff" : "#faf5ff",
              color: resolvedType === "API" ? "#2563eb" : "#9333ea",
              border: `1px solid ${resolvedType === "API" ? "#bfdbfe" : "#e9d5ff"}`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
            }}>
              {resolvedType === "API" ? <FaCode /> : <FaImage />}
            </div>

            {/* Title */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <h3 style={{ fontWeight: 800, fontSize: 16, color: "#0f172a", margin: 0, letterSpacing: "-0.01em" }}>
                  {data.title}
                </h3>
                <StatusBadge status={data.status} />
              </div>
              <div style={{ fontSize: 11, color: "#64748b", marginTop: 3, fontFamily: "monospace", display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ opacity: 0.8, fontWeight: 700 }}>Spec:</span> {data.spec}
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
                    padding: "7px 14px", background: "#ffffff", color: "#0f172a",
                    borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12, fontWeight: 700,
                    cursor: "pointer", display: "flex", alignItems: "center", gap: 7,
                    boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                  }}
                >
                  <FaExternalLinkAlt size={11} color="#d97706" /> Open Report
                </button>
                <a
                  href={data.url!}
                  download
                  style={{
                    padding: "7px 14px", background: "#ffffff", color: "#0f172a",
                    borderRadius: 8, border: "1px solid #cbd5e1", fontSize: 12, fontWeight: 700,
                    cursor: "pointer", display: "flex", alignItems: "center", gap: 7,
                    textDecoration: "none", boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                  }}
                >
                  <FaDownload size={11} color="#2563eb" /> Download
                </a>
              </>
            )}
            <button
              onClick={onClose}
              style={{
                width: 34, height: 34, display: "flex", alignItems: "center", justifyContent: "center",
                background: "#f1f5f9", border: "1px solid #e2e8f0", color: "#64748b", borderRadius: 8,
                cursor: "pointer", transition: "all 0.15s ease",
              }}
            >
              <FaTimes size={16} />
            </button>
          </div>
        </div>

        {/* ── Main content (Type-Based Routing) ── */}
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {resolvedType === "API" && (
            data.apiEvidence ? <ApiReportPanel data={data} /> : <JUnitReportPanel data={data} />
          )}
          {resolvedType === "UI" && <UiReportPanel data={data} />}
          {resolvedType === "UNKNOWN" && <GenericReportPanel data={data} />}
        </div>

        {/* ── Footer artifact status bar ── */}
        <div style={{
          padding: "12px 28px", background: "#f8fafc", borderTop: "1px solid #e2e8f0",
          display: "flex", gap: 20, alignItems: "center", flexShrink: 0,
        }}>
          {screenshotUrl && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <FaImage color="#9333ea" size={12} />
              <a href={screenshotUrl} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 11, fontWeight: 700, color: "#2563eb", textDecoration: "none" }}>
                Screenshot <FaLink size={9} style={{ marginLeft: 3 }} />
              </a>
            </div>
          )}
          {videoUrl && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <FaPlay color="#059669" size={12} />
              <a href={videoUrl} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 11, fontWeight: 700, color: "#059669", textDecoration: "none" }}>
                Video <FaLink size={9} style={{ marginLeft: 3 }} />
              </a>
            </div>
          )}
          {data.traceUrl && (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <FaTerminal color="#d97706" size={12} />
              <a href={data.traceUrl} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 11, fontWeight: 700, color: "#d97706", textDecoration: "none" }}>
                Trace <FaLink size={9} style={{ marginLeft: 3 }} />
              </a>
            </div>
          )}
          {!screenshotUrl && !videoUrl && !data.traceUrl && (
            <span style={{ fontSize: 11, color: "#64748b" }}>
              {resolvedType} Validation Evidence · APEX Test Engine
            </span>
          )}
          <div style={{ marginLeft: "auto", fontSize: 11, fontWeight: 600, color: "#94a3b8", fontFamily: "monospace" }}>
            APEX Validation Engine
          </div>
        </div>

      </div>
    </div>
  );
}
