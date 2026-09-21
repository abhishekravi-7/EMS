import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  FaSpinner,
  FaRedo,
  FaDownload,
  FaTerminal,
  FaTimes,
  FaExternalLinkAlt,
  FaCopy,
  FaCheck,
  FaCheckCircle,
  FaPlay,
  FaCode,
  FaFileAlt,
  FaLayerGroup,
  FaListUl,
  FaTimesCircle,
  FaHourglassHalf,
  FaMinusCircle,
  FaClock,
} from "react-icons/fa";
import {
  getProposedTestsStatus,
  getProposedTestsResults,
  runApprovedProposedTests,
  formatProposedTestDisplayName,
  getProposedTestComparison,
  type ProposedTestCase,
  type ProposedTestMetrics,
  type ProposedTestComparisonResponse,
} from "@/features/modernization/services/proposedTestService";
import { downloadProposedTestReport } from "@/features/result/services/resultService";
import { triggerBlobDownload } from "@/features/result/utils/migrationWizardPdf";
import type { MigrationResult } from "@/features/result/services/resultService";

type StyleMap = Record<string, React.CSSProperties>;

interface MigrationProposedTestSectionProps {
  styles: StyleMap;
  migrationJob: MigrationResult;
}

export function MigrationProposedTestSection({
  styles,
  migrationJob,
}: MigrationProposedTestSectionProps) {
  const jobId = migrationJob?.job_id || "";
  const [proposals, setProposals] = useState<ProposedTestCase[]>([]);
  const [metrics, setMetrics] = useState<ProposedTestMetrics | null>(null);
  const [comparison, setComparison] = useState<ProposedTestComparisonResponse | null>(null);
  const [logs, setLogs] = useState<Array<{ ts?: string; msg?: string; level?: string }>>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const [selectedTest, setSelectedTest] = useState<ProposedTestCase | null>(null);
  const [showLogs, setShowLogs] = useState(true);
  const [selectedSources, setSelectedSources] = useState<string[] | null>(null);
  const [allureReportAvailable, setAllureReportAvailable] = useState(false);
  const [allureReportUrl, setAllureReportUrl] = useState<string | null>(null);
  const [isLogsCopied, setIsLogsCopied] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logBoxRef = useRef<HTMLDivElement | null>(null);

  const handleCopyLogs = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!logs || logs.length === 0) return;
    const text = logs
      .map((log) => `${log.ts ? `[${log.ts}] ` : ""}${log.level ? `[${log.level}] ` : ""}${log.msg || ""}`)
      .join("\n");
    navigator.clipboard
      .writeText(text)
      .then(() => {
        setIsLogsCopied(true);
        setTimeout(() => setIsLogsCopied(false), 2000);
      })
      .catch((err) => {
        console.error("Failed to copy execution logs:", err);
      });
  };

  // Auto-scroll execution logs
  useEffect(() => {
    if (logBoxRef.current) {
      logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
    }
  }, [logs]);

  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const statusData = await getProposedTestsStatus(jobId);
        if (statusData.proposals) setProposals(statusData.proposals);
        if (statusData.metrics) setMetrics(statusData.metrics);
        if (statusData.logs) setLogs(statusData.logs);
        if (statusData.selected_sources) setSelectedSources(statusData.selected_sources);
        if (statusData.allure_report_available !== undefined) {
          setAllureReportAvailable(statusData.allure_report_available);
          if (statusData.allure_report_url) setAllureReportUrl(statusData.allure_report_url);
        }

        if (statusData.status === "COMPLETED" || statusData.status === "FAILED") {
          if (pollRef.current) clearInterval(pollRef.current);
          setIsRunning(false);

          // Fetch final results payload
          const finalResults = await getProposedTestsResults(jobId).catch(() => null);
          if (finalResults?.test_cases) setProposals(finalResults.test_cases);
          if (finalResults?.metrics) setMetrics(finalResults.metrics);
          if (finalResults?.selected_sources) setSelectedSources(finalResults.selected_sources);
          if (finalResults?.allure_report_available !== undefined) {
            setAllureReportAvailable(finalResults.allure_report_available);
            if (finalResults.allure_report_url) setAllureReportUrl(finalResults.allure_report_url);
          }

          // Fetch comparison against pre-migration baseline
          const compData = await getProposedTestComparison(jobId).catch(() => null);
          if (compData) setComparison(compData);
        }
      } catch (err) {
        console.error("Polling proposed tests error:", err);
      }
    }, 1000);
  }, [jobId]);

  // Load initial status and results
  useEffect(() => {
    if (!jobId) return;

    let isMounted = true;
    setIsLoading(true);

    const loadData = async () => {
      try {
        const [res, compData] = await Promise.all([
          getProposedTestsStatus(jobId).catch(() => null),
          getProposedTestComparison(jobId).catch(() => null),
        ]);
        if (!isMounted) return;

        if (compData) setComparison(compData);

        if (res) {
          if (res.proposals) setProposals(res.proposals);
          if (res.metrics) setMetrics(res.metrics);
          if (res.logs) setLogs(res.logs);
          if (res.selected_sources) setSelectedSources(res.selected_sources);
          if (res.allure_report_available !== undefined) {
            setAllureReportAvailable(res.allure_report_available);
            if (res.allure_report_url) setAllureReportUrl(res.allure_report_url);
          }

          if (res.status === "RUNNING") {
            setIsRunning(true);
            startPolling();
          }
        }
      } catch (err) {
        console.error("Failed to load proposed tests status:", err);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    loadData();

    return () => {
      isMounted = false;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [jobId, startPolling]);

  const [selectedTestIds, setSelectedTestIds] = useState<Set<string>>(new Set());

  // Auto-select valid tests by default on initial load
  useEffect(() => {
    if (proposals.length > 0 && selectedTestIds.size === 0) {
      const validIds = proposals
        .filter((p) => !p.validation || p.validation.playwright_executable !== false)
        .map((p) => p.id);
      setSelectedTestIds(new Set(validIds.length > 0 ? validIds : proposals.map((p) => p.id)));
    }
  }, [proposals]);

  const handleToggleSelectAll = () => {
    if (selectedTestIds.size === proposals.length) {
      setSelectedTestIds(new Set());
    } else {
      setSelectedTestIds(new Set(proposals.map((p) => p.id)));
    }
  };

  const handleToggleTest = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedTestIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleRunSelected = async () => {
    if (!jobId || isRunning || selectedTestIds.size === 0) return;
    setIsRunning(true);
    setLogs([]);
    try {
      await runApprovedProposedTests(jobId, {
        test_ids: Array.from(selectedTestIds),
      });
      startPolling();
    } catch (err) {
      console.error("Failed to trigger Playwright execution for selected tests:", err);
      setIsRunning(false);
    }
  };

  const handleRunAgain = async () => {
    if (!jobId || isRunning) return;
    setIsRunning(true);
    setLogs([]);
    try {
      await runApprovedProposedTests(jobId, {
        test_ids: selectedTestIds.size > 0 ? Array.from(selectedTestIds) : undefined,
        sources: selectedSources && selectedSources.length > 0 ? selectedSources : undefined,
      });
      startPolling();
    } catch (err) {
      console.error("Failed to trigger Playwright execution:", err);
      setIsRunning(false);
    }
  };

  const handleViewAllureReport = () => {
    const url = allureReportUrl || `/api/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/allure-report/index.html`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const handleDownloadReport = async () => {
    if (!jobId || isDownloading) return;
    setIsDownloading(true);
    try {
      const blob = await downloadProposedTestReport(jobId);
      triggerBlobDownload(blob, `proposed-test-report-${jobId}.json`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to download proposed tests report.");
    } finally {
      setIsDownloading(false);
    }
  };

  const totalProposed = metrics?.total ?? proposals.length;
  const executedCount = metrics?.executed ?? proposals.filter((p) => p.status === "PASSED" || p.status === "FAILED" || p.status === "SKIPPED").length;
  const passedCount = metrics?.passed ?? proposals.filter((p) => p.status === "PASSED").length;
  const failedCount = metrics?.failed ?? proposals.filter((p) => p.status === "FAILED").length;
  const skippedCount = metrics?.skipped ?? proposals.filter((p) => p.status === "SKIPPED").length;
  const notExecutedCount = metrics?.not_executed ?? Math.max(0, totalProposed - executedCount);

  // Validation Breakdown Counts (Inventory is fully preserved)
  const validCount = proposals.filter((p) => !p.validation || p.validation.status === "VALID" || p.validation.status === "PARTIALLY_VALID").length;
  const duplicateCount = proposals.filter((p) => p.validation?.status === "DUPLICATE").length;
  const hallucinatedCount = proposals.filter((p) => p.validation?.status === "HALLUCINATED").length;
  const invalidCount = proposals.filter((p) => p.validation?.status === "INVALID").length;

  const passRateNum = executedCount > 0 ? Math.round((passedCount / executedCount) * 100) : 0;
  const passRateDisplay = `${passRateNum}%`;
  const durationDisplay = metrics?.duration || "0.0s";

  // Dynamic source breakdown counts
  const functionalDocCount = proposals.filter(
    (p) =>
      p.generation_source === "BRD_DOCUMENT" ||
      p.generation_source === "BRD_AND_AI" ||
      p.generation_source === "FUNCTIONAL_DOC" ||
      p.id.includes("BRD") ||
      p.source === "BRD Document" ||
      p.source === "BRD Business Requirement"
  ).length;

  const existingCount = proposals.filter(
    (p) =>
      p.generation_source === "EXISTING" ||
      p.generation_source === "EXISTING_TESTS" ||
      p.id.includes("EXT") ||
      p.source === "Existing Repository" ||
      p.source === "Existing Repository Tests"
  ).length;

  const llmCount = Math.max(0, totalProposed - functionalDocCount - existingCount);

  const statusLabel = isRunning ? "running baseline tests" : executedCount > 0 ? "completed" : "ready for baseline run";
  const statusColor = isRunning ? "#0284c7" : executedCount > 0 ? (failedCount === 0 ? "#10b981" : "#ef4444") : "#d97706";

  // Breakdown Calculations
  const apiCount = proposals.filter(p => p.type === "API").length;
  const uiCount = proposals.filter(p => p.type === "UI").length;


  return (
    <div style={{ ...styles.reportSection, background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "24px 32px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
      {/* ── TOP HEADER AREA ────────────────────────────────────────────────── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: "#2563eb", color: "#fff", width: 32, height: 32, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
            <FaFileAlt />
          </div>
          <h3 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#0f172a" }}>Proposed Test Case Information</h3>
        </div>

        {/* Validation Inventory Summary Strip */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 12,
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: 10,
            padding: "12px 16px",
            marginBottom: 20,
          }}
        >
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>{totalProposed}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>TOTAL INVENTORY</div>
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, color: "#059669" }}>{validCount}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>VALID</div>
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, color: "#d97706" }}>{duplicateCount}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>DUPLICATE</div>
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, color: "#7c3aed" }}>{hallucinatedCount}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>HALLUCINATED</div>
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, color: "#dc2626" }}>{invalidCount}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>INVALID</div>
          </div>
        </div>

        {/* Radial Pass Rate Gauge & Metric Overview Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 24, paddingBottom: 24, borderBottom: "1px solid #e2e8f0", marginBottom: 24, alignItems: "center" }}>
          {/* Radial Ring */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
            <div
              style={{
                position: "relative",
                width: 110,
                height: 110,
                borderRadius: "50%",
                background: `conic-gradient(#10b981 0% ${passRateNum}%, #e2e8f0 ${passRateNum}% 100%)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  width: 88,
                  height: 88,
                  borderRadius: "50%",
                  background: "#ffffff",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <div style={{ fontSize: 20, fontWeight: 800, color: "#0f172a" }}>{passRateDisplay}</div>
                <div style={{ fontSize: 9, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>
                  PASS RATE
                </div>
              </div>
            </div>
            <div style={{ fontSize: 11, color: "#64748b", marginTop: 8, textAlign: "center", lineHeight: 1.3 }}>
              Execution pass percentage across Playwright test suite.
            </div>
          </div>
          <button
            onClick={handleRunAgain}
            disabled={isRunning}
            style={{
              background: "#7c3aed",
              color: "#fff",
              border: "none",
              padding: "8px 20px",
              borderRadius: 10,
              fontSize: 13,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: 8,
              cursor: isRunning ? "default" : "pointer",
            }}
          >
            <FaPlay size={10} /> Run Again
          </button>
          <button
            onClick={handleViewAllureReport}
            disabled={!allureReportAvailable && executedCount === 0}
            style={{
              background: "#2563eb",
              color: "#fff",
              border: "none",
              padding: "8px 20px",
              borderRadius: 10,
              fontSize: 13,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: 8,
              cursor: "pointer",
            }}
          >
             <FaExternalLinkAlt size={12} /> View Allure Report
          </button>
          <button
            onClick={handleDownloadReport}
            style={{
              background: "#fff",
              border: "1px solid #e2e8f0",
              padding: "8px 20px",
              borderRadius: 10,
              fontSize: 13,
              fontWeight: 700,
              color: "#0f172a",
              display: "flex",
              alignItems: "center",
              gap: 8,
              cursor: "pointer"
            }}
          >
             <FaDownload /> Download Report
          </button>
        </div>
      </div>

      {/* ── CORE PERFORMANCE BLOCK ───────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", gap: 32, marginBottom: 40, background: "#fbfcfd", padding: "20px", borderRadius: 16, border: "1px solid #f1f5f9" }}>
        {/* Gauge */}
        <div style={{ textAlign: "center", flexShrink: 0, borderRight: "1px solid #eef2f6", paddingRight: 20 }}>
          <div style={{ position: "relative", width: 110, height: 110, margin: "0 auto" }}>
            <svg width="110" height="110" viewBox="0 0 110 110">
              <circle cx="55" cy="55" r="48" fill="none" stroke="#e2e8f0" strokeWidth="10" />
              <circle cx="55" cy="55" r="48" fill="none" stroke="#10b981" strokeWidth="10" strokeDasharray={`${passRateNum * 3.01} 301`} strokeLinecap="round" transform="rotate(-90 55 55)" />
            </svg>
            <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#0f172a" }}>{passRateDisplay}</div>
              <div style={{ fontSize: 8, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Pass Rate</div>
            </div>
          </div>
        </div>

        {/* Source Application Diagnostics & Pre-Migration Status */}
        {comparison?.source_status && (
          <div
            style={{
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderRadius: 12,
              padding: "16px 20px",
              marginBottom: 20,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: "#1e293b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Source Application (Pre-Migration Baseline)
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 800,
                    padding: "2px 8px",
                    borderRadius: 6,
                    background: comparison.source_status.readiness_status === "READY" ? "rgba(16, 185, 129, 0.15)" : "rgba(245, 158, 11, 0.15)",
                    color: comparison.source_status.readiness_status === "READY" ? "#059669" : "#d97706",
                    border: `1px solid ${comparison.source_status.readiness_status === "READY" ? "rgba(16, 185, 129, 0.3)" : "rgba(245, 158, 11, 0.3)"}`,
                  }}
                >
                  {comparison.source_status.readiness_status === "READY" ? "✓ SOURCE READY" : "⚠ SOURCE NOT READY"}
                </span>
              </div>
              {comparison.source_status.base_url && (
                <div style={{ fontSize: 12, color: "#64748b", fontFamily: "monospace" }}>
                  URL: <span style={{ color: "#0284c7", fontWeight: 700 }}>{comparison.source_status.base_url}</span>
                </div>
              )}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 14px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: comparison.source_status.build_success ? "#059669" : "#dc2626" }}>
                  {comparison.source_status.build_success ? "✓ BUILD SUCCESS" : "✕ BUILD FAILED"}
                </div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>Build Status</div>
              </div>
              <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 14px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: comparison.source_status.startup_status === "STARTED" ? "#059669" : "#d97706" }}>
                  {comparison.source_status.startup_status || "NOT STARTED"}
                </div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>Startup Status</div>
              </div>
              <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 14px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: comparison.source_status.readiness_status === "READY" ? "#059669" : "#d97706" }}>
                  {comparison.source_status.readiness_status || "NOT STARTED"}
                </div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>Readiness Status</div>
              </div>
              <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 14px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: comparison.baseline_available ? "#0284c7" : "#64748b" }}>
                  {comparison.baseline_available ? "✓ EXECUTED" : "NOT EXECUTED"}
                </div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>Baseline Tests</div>
              </div>
            </div>

            {/* If there was a startup or readiness diagnostic error */}
            {comparison.source_status.error && (
              <div
                style={{
                  marginTop: 12,
                  background: "rgba(239, 68, 68, 0.06)",
                  border: "1px solid rgba(239, 68, 68, 0.2)",
                  borderRadius: 8,
                  padding: "10px 14px",
                  fontSize: 12,
                  color: "#b91c1c",
                }}
              >
                <div style={{ fontWeight: 800, marginBottom: 2 }}>Source Application Diagnostic:</div>
                <div style={{ whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: 11 }}>{comparison.source_status.error}</div>
              </div>
            )}
          </div>
        )}

        {/* Pre-Migration Baseline vs. Migrated Target Comparison Card */}
        {comparison && comparison.baseline_available && (
          <div
            style={{
              background: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
              border: "1px solid #cbd5e1",
              borderRadius: 12,
              padding: "16px 20px",
              marginBottom: 24,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: "#1e293b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Pre-Migration Baseline vs. Migrated Parity
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 800,
                    padding: "2px 8px",
                    borderRadius: 6,
                    background: comparison.regressions_count === 0 ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
                    color: comparison.regressions_count === 0 ? "#059669" : "#dc2626",
                    border: `1px solid ${comparison.regressions_count === 0 ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
                  }}
                >
                  {comparison.regressions_count === 0 ? "✓ 0 REGRESSIONS" : `⚠ ${comparison.regressions_count} REGRESSION${comparison.regressions_count > 1 ? "S" : ""}`}
                </span>
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#475569" }}>
                Parity Rate: <span style={{ color: (comparison.parity_percentage || "").includes("100") || (comparison.parity_percentage || "").includes("9") ? "#059669" : "#d97706", fontSize: 14, fontWeight: 800 }}>{comparison.parity_percentage || "0%"}</span>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
              <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 14px" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#0284c7" }}>{comparison.baseline_metrics?.passed ?? 0} / {comparison.baseline_metrics?.executed ?? 0}</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>Baseline Passed</div>
              </div>
              <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 14px" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#059669" }}>{comparison.target_metrics?.passed ?? 0} / {comparison.target_metrics?.executed ?? 0}</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>Migrated Passed</div>
              </div>
              <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 14px" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#059669" }}>{comparison.preserved_passed_count ?? 0}</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>Parity Maintained</div>
              </div>
              <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 14px" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: (comparison.regressions_count ?? 0) > 0 ? "#dc2626" : "#64748b" }}>{comparison.regressions_count ?? 0}</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>Regressions</div>
              </div>
              <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 14px" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#7c3aed" }}>{comparison.improvements_count ?? 0}</div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>Improvements</div>
              </div>
            </div>
          </div>
        )}

        {/* Source Breakdown Cards Grid */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#475569", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 10 }}>
            Source Breakdown
          </div>
          <div style={{ display: "grid", gridTemplateColumns: existingCount > 0 ? "repeat(4, 1fr)" : "repeat(3, 1fr)", gap: 14 }}>
            {[
              { value: llmCount, label: "LLM Generated", color: "#0284c7", bg: "#f0f9ff", borderColor: "#bae6fd", tag: "LLM" },
              { value: functionalDocCount, label: "BRD / Functional Doc", color: "#7c3aed", bg: "#f5f3ff", borderColor: "#c4b5fd", tag: "DOC" },
              ...(existingCount > 0 ? [{ value: existingCount, label: "Existing Tests", color: "#059669", bg: "#f0fdf4", borderColor: "#86efac", tag: "EXISTING" }] : []),
              { value: totalProposed, label: "Total Executable", color: "#0f172a", bg: "#f8fafc", borderColor: "#e2e8f0", tag: "TOTAL" },
            ].map((card, idx) => (
              <div key={idx} style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "14px 16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 20, fontWeight: 800, color: card.color }}>{card.value}</span>
                  <span style={{ fontSize: 10, fontWeight: 800, color: card.color, background: card.bg, border: `1px solid ${card.borderColor}`, padding: "2px 6px", borderRadius: 4 }}>{card.tag}</span>
                </div>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", lineHeight: 1.2, marginTop: 6 }}>{card.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── BREAKDOWNS AREA (GRID 2-COL) ─────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 32, marginBottom: 48 }}>

        {/* Type Breakdown Section */}
        <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <h4 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "#0f172a" }}>Functional Test Type Breakdown</h4>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            {[
                { label: "API Functional", value: apiCount, tag: "API", color: "#2563eb", bg: "#eff6ff" },
                { label: "UI Functional", value: uiCount, tag: "UI", color: "#7c3aed", bg: "#f5f3ff" },
                { label: "Total Functional", value: totalProposed, tag: "TOTAL", color: "#10b981", bg: "#f0fdf4" },
            ].map((item, i) => (
                <div key={i} style={{ background: item.bg, border: "1px solid #eef2f6", borderRadius: 12, padding: "12px", display: "flex", flexDirection: "column", gap: 8, boxShadow: "0 2px 8px rgba(0,0,0,0.02)" }}>
                    <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "flex-start" }}>
                        <span style={{ fontSize: 7, fontWeight: 800, color: item.color, background: `${item.color}10`, padding: "2px 6px", borderRadius: 4 }}>{item.tag}</span>
                    </div>
                    <div>
                        <div style={{ fontSize: 24, fontWeight: 800, color: "#0f172a" }}>{item.value}</div>
                        <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>{item.label}</div>
                    </div>
                </div>
            ))}
            </div>
        </div>
      </div>

      {/* ── TABLE AREA (TOPIC STYLE) ──────────────────────────────────────── */}
      <div style={{ marginBottom: 40 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <div style={{ background: "#7c3aed", color: "#fff", width: 24, height: 24, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12 }}>
            <FaLayerGroup />
          </div>

          <div style={{ maxHeight: 420, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 8, background: "#ffffff" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#f8fafc", color: "#475569", borderBottom: "1px solid #e2e8f0", position: "sticky", top: 0, zIndex: 2 }}>
                  <th style={{ padding: "8px 10px", width: 35, textAlign: "center" }}>
                    <input
                      type="checkbox"
                      checked={proposals.length > 0 && selectedTestIds.size === proposals.length}
                      onChange={handleToggleSelectAll}
                      style={{ cursor: "pointer" }}
                      title="Select / Deselect All Tests"
                    />
                  </th>
                  <th style={{ padding: "8px 10px", width: 65, fontWeight: 700 }}>ID</th>
                  <th style={{ padding: "8px 10px", fontWeight: 700 }}>Test Name</th>
                  <th style={{ padding: "8px 10px", width: 110, fontWeight: 700 }}>Source</th>
                  <th style={{ padding: "8px 10px", width: 50, fontWeight: 700 }}>Type</th>
                  <th style={{ padding: "8px 10px", width: 60, fontWeight: 700 }}>Method</th>
                  <th style={{ padding: "8px 10px", width: 150, fontWeight: 700 }}>Endpoint / Route</th>
                  <th style={{ padding: "8px 10px", width: 100, fontWeight: 700 }}>Validation</th>
                  <th style={{ padding: "8px 10px", width: 110, fontWeight: 700 }}>Execution Status</th>
                  <th style={{ padding: "8px 10px", width: 70, fontWeight: 700 }}>Duration</th>
                  <th style={{ padding: "8px 10px", width: 50, fontWeight: 700, textAlign: "center" }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={11} style={{ padding: "36px 12px", textAlign: "center", color: "#64748b" }}>
                      <FaSpinner className="animate-spin" size={18} style={{ marginBottom: 6 }} />
                      <div>Loading proposed test execution data...</div>
                    </td>
                  </tr>
                ) : proposals.length === 0 ? (
                  <tr>
                    <td colSpan={11} style={{ padding: "28px 12px", textAlign: "center", color: "#64748b" }}>
                      No proposed test cases found for this migration.
                    </td>
                  </tr>
                ) : (
                  proposals.map((t, idx) => {
                    const isDoc =
                      t.generation_source === "BRD_DOCUMENT" ||
                      t.generation_source === "BRD_AND_AI" ||
                      t.generation_source === "FUNCTIONAL_DOC" ||
                      t.id.includes("BRD") ||
                      t.source === "BRD Document" ||
                      t.source === "BRD Business Requirement";

                    const isExisting =
                      t.generation_source === "EXISTING" ||
                      t.generation_source === "EXISTING_TESTS" ||
                      t.id.includes("EXT") ||
                      t.source === "Existing Repository" ||
                      t.source === "Existing Repository Tests";

                    const sourceBadgeLabel = isExisting ? "Existing" : isDoc ? "Functional Doc" : "LLM Generated";
                    const sourceBadgeColor = isExisting ? "#059669" : isDoc ? "#7c3aed" : "#0284c7";
                    const sourceBadgeBg = isExisting ? "#ecfdf5" : isDoc ? "#faf5ff" : "#f0f9ff";
                    const sourceBadgeBorder = isExisting ? "#a7f3d0" : isDoc ? "#d8b4fe" : "#bae6fd";

                    const execStatus = t.execution_result?.status || t.baseline_execution_result?.status || t.status || "NOT_EXECUTED";
                    const method = t.api_spec?.method || (t.type === "API" ? "GET" : "--");
                    const endpoint = t.api_spec?.endpoint || t.ui_spec?.target_route || "--";

                    const valStatus = t.validation?.status || "VALID";
                    const valColor =
                      valStatus === "VALID" || valStatus === "PARTIALLY_VALID"
                        ? "#059669"
                        : valStatus === "DUPLICATE"
                        ? "#d97706"
                        : valStatus === "HALLUCINATED"
                        ? "#7c3aed"
                        : "#dc2626";
                    const valBg =
                      valStatus === "VALID" || valStatus === "PARTIALLY_VALID"
                        ? "rgba(16, 185, 129, 0.1)"
                        : valStatus === "DUPLICATE"
                        ? "rgba(217, 119, 6, 0.1)"
                        : valStatus === "HALLUCINATED"
                        ? "rgba(124, 58, 237, 0.1)"
                        : "rgba(239, 68, 68, 0.1)";
                    const valBorder =
                      valStatus === "VALID" || valStatus === "PARTIALLY_VALID"
                        ? "rgba(16, 185, 129, 0.3)"
                        : valStatus === "DUPLICATE"
                        ? "rgba(217, 119, 6, 0.3)"
                        : valStatus === "HALLUCINATED"
                        ? "rgba(124, 58, 237, 0.3)"
                        : "rgba(239, 68, 68, 0.3)";

                    const renderStatusBadge = (s: string | null) => {
                      if (!s || s === "PROPOSED" || s === "APPROVED" || s === "READY" || s === "NOT_EXECUTED") {
                        return (
                          <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", background: "rgba(100, 116, 139, 0.1)", padding: "2px 6px", borderRadius: 4 }}>
                            NOT_EXECUTED
                          </span>
                        );
                      }
                      const isPassed = s === "PASSED";
                      const isFailed = s === "FAILED";
                      const isAppUnavailable = s === "APPLICATION_UNAVAILABLE";
                      const isSkipped = s === "SKIPPED";
                      const isRunningRow = s === "RUNNING";

                      const bg = isPassed
                        ? "rgba(16, 185, 129, 0.12)"
                        : isFailed
                        ? "rgba(239, 68, 68, 0.12)"
                        : isAppUnavailable
                        ? "rgba(245, 158, 11, 0.12)"
                        : isRunningRow
                        ? "rgba(2, 132, 199, 0.12)"
                        : "rgba(100, 116, 139, 0.12)";
                      const color = isPassed
                        ? "#059669"
                        : isFailed
                        ? "#dc2626"
                        : isAppUnavailable
                        ? "#d97706"
                        : isRunningRow
                        ? "#0284c7"
                        : "#64748b";
                      const border = isPassed
                        ? "1px solid rgba(16, 185, 129, 0.3)"
                        : isFailed
                        ? "1px solid rgba(239, 68, 68, 0.3)"
                        : isAppUnavailable
                        ? "1px solid rgba(245, 158, 11, 0.4)"
                        : isRunningRow
                        ? "1px solid rgba(2, 132, 199, 0.3)"
                        : "1px solid rgba(100, 116, 139, 0.3)";

                      return (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 3,
                            padding: "2px 6px",
                            borderRadius: 4,
                            fontSize: 10,
                            fontWeight: 800,
                            background: bg,
                            color,
                            border,
                          }}
                        >
                          {isRunningRow && <FaSpinner className="animate-spin" size={7} />}
                          {isPassed
                            ? "✓ PASSED"
                            : isFailed
                            ? "✕ FAILED"
                            : isAppUnavailable
                            ? "⊘ UNAVAIL"
                            : isSkipped
                            ? "⚠ SKIPPED"
                            : s}
                        </span>
                      );
                    };

                    const duration = t.execution_result?.duration || t.baseline_execution_result?.duration || "--";
                    const isChecked = selectedTestIds.has(t.id);

                    return (
                      <tr
                        key={`prop-test-${t.id}-${idx}`}
                        onClick={() => setSelectedTest(t)}
                        style={{
                          borderBottom: "1px solid #e2e8f0",
                          color: "#0f172a",
                          cursor: "pointer",
                          background: isChecked ? "rgba(2, 132, 199, 0.02)" : "transparent",
                          transition: "background 0.12s ease",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = isChecked ? "rgba(2, 132, 199, 0.05)" : "#f8fafc")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = isChecked ? "rgba(2, 132, 199, 0.02)" : "transparent")}
                      >
                        <td style={{ padding: "8px 10px", textAlign: "center" }} onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => handleToggleTest(t.id, e as unknown as React.MouseEvent)}
                            style={{ cursor: "pointer" }}
                          />
                        </td>
                        <td style={{ padding: "8px 10px", fontFamily: "monospace", color: "#0284c7", fontWeight: 700 }}>
                          {t.id}
                        </td>
                        <td style={{ padding: "8px 10px", fontWeight: 600 }}>
                          {formatProposedTestDisplayName(t)}
                        </td>
                        <td style={{ padding: "8px 10px" }}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 800,
                              color: sourceBadgeColor,
                              background: sourceBadgeBg,
                              border: `1px solid ${sourceBadgeBorder}`,
                              padding: "2px 6px",
                              borderRadius: 4,
                            }}
                          >
                            {sourceBadgeLabel}
                          </span>
                        </td>
                        <td style={{ padding: "8px 10px", fontSize: 11, color: "#64748b" }}>
                          {t.type}
                        </td>
                        <td style={{ padding: "8px 10px" }}>
                          {method !== "--" ? (
                            <span
                              style={{
                                fontSize: 9,
                                fontWeight: 800,
                                padding: "2px 5px",
                                borderRadius: 3,
                                background: method === "GET" ? "#f0fdf4" : method === "POST" ? "#eff6ff" : method === "DELETE" ? "#fef2f2" : "#f8fafc",
                                color: method === "GET" ? "#15803d" : method === "POST" ? "#1d4ed8" : method === "DELETE" ? "#b91c1c" : "#475569",
                                border: "1px solid rgba(0,0,0,0.08)",
                                fontFamily: "monospace",
                              }}
                            >
                              {method}
                            </span>
                          ) : (
                            <span style={{ color: "#94a3b8" }}>--</span>
                          )}
                        </td>
                        <td style={{ padding: "8px 10px", fontFamily: "monospace", fontSize: 11, color: "#334155", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={endpoint}>
                          {endpoint}
                        </td>
                        <td style={{ padding: "8px 10px" }}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 800,
                              color: valColor,
                              background: valBg,
                              border: `1px solid ${valBorder}`,
                              padding: "2px 6px",
                              borderRadius: 4,
                            }}
                          >
                            {valStatus}
                          </span>
                        </td>
                        <td style={{ padding: "8px 10px" }}>
                          {renderStatusBadge(execStatus)}
                        </td>
                        <td style={{ padding: "8px 10px", color: "#64748b", fontSize: 11, fontFamily: "monospace" }}>
                          {duration}
                        </td>
                        <td style={{ padding: "8px 10px", textAlign: "center" }}>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedTest(t);
                            }}
                            style={{
                              background: "transparent",
                              border: "none",
                              color: "#0284c7",
                              cursor: "pointer",
                              fontSize: 12,
                            }}
                            title="View Test Details"
                          >
                            <FaExternalLinkAlt size={11} />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── CONSOLE TOGGLE AREA (TOPIC STYLE) ────────────────────────────────── */}
      {logs.length > 0 && (
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ background: "#7c3aed", color: "#fff", width: 24, height: 24, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12 }}>
                <FaTerminal />
              </div>
              <h4 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "#0f172a" }}>PLAYWRIGHT EXECUTION LOGS ({logs.length} entries)</h4>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <button
                type="button"
                onClick={handleCopyLogs}
                disabled={!logs || logs.length === 0}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  padding: "3px 10px",
                  borderRadius: 6,
                  border: "1px solid #cbd5e1",
                  background: isLogsCopied ? "#f0fdf4" : "#f8fafc",
                  color: isLogsCopied ? "#16a34a" : "#475569",
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: !logs || logs.length === 0 ? "not-allowed" : "pointer",
                  opacity: !logs || logs.length === 0 ? 0.6 : 1,
                  transition: "all 0.15s ease",
                }}
                title="Copy Playwright execution logs to clipboard"
              >
                {isLogsCopied ? <FaCheck size={11} /> : <FaCopy size={11} />}
                <span>{isLogsCopied ? "Copied!" : "Copy Logs"}</span>
              </button>
              <span style={{ fontSize: 11, color: "#64748b" }}>
                {showLogs ? "Hide Console ▲" : "Show Console ▼"}
              </span>
            </div>
          </div>
          {showLogs && (
            <div ref={logBoxRef} style={{ background: "#0f172a", borderRadius: 16, padding: "24px", maxHeight: 250, overflowY: "auto", fontFamily: "'JetBrains Mono', monospace", fontSize: 12, lineHeight: 1.6, color: "#e2e8f0", border: "1px solid #1e293b", boxShadow: "inset 0 4px 20px rgba(0,0,0,0.3)" }}>
              {logs.map((log, i) => (
                <div key={i} style={{ marginBottom: 4, display: "flex", gap: 16 }}>
                  <span style={{ color: "#475569", flexShrink: 0 }}>[{log.ts || "00:00:00"}]</span>
                  <span style={{ color: log.level === "ERROR" ? "#f87171" : "#3b82f6", fontWeight: 700, flexShrink: 0 }}>[{log.level}]</span>
                  <span style={{ wordBreak: "break-all" }}>{log.msg}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── FOOTER ACTIONS ─────────────────────────────────────────────────── */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
      </div>

      {/* ── MODAL ─────────────────────────────────────────────────────────── */}
      {selectedTest && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            background: "rgba(15, 23, 42, 0.6)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 20,
          }}
          onClick={() => setSelectedTest(null)}
        >
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: 16,
              maxWidth: 780,
              width: "100%",
              maxHeight: "88vh",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
              color: "#0f172a",
              overflow: "hidden",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: "16px 20px",
                borderBottom: "1px solid #e2e8f0",
                background: "#f8fafc",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ fontFamily: "monospace", fontSize: 11, fontWeight: 900, background: "#0284c7", color: "#ffffff", padding: "2px 6px", borderRadius: 4 }}>
                    {selectedTest.id}
                  </span>
                  <span style={{ fontSize: 10, fontWeight: 800, background: "#e2e8f0", padding: "2px 8px", borderRadius: 4, color: "#475569" }}>
                    {selectedTest.type}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 800,
                      padding: "2px 8px",
                      borderRadius: 4,
                      background: selectedTest.status === "PASSED" ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)",
                      color: selectedTest.status === "PASSED" ? "#059669" : "#dc2626",
                    }}
                  >
                    Migrated: {selectedTest.status || "PROPOSED"}
                  </span>
                  {selectedTest.baseline_execution_result && (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 800,
                        padding: "2px 8px",
                        borderRadius: 4,
                        background: selectedTest.baseline_execution_result.status === "PASSED" ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)",
                        color: selectedTest.baseline_execution_result.status === "PASSED" ? "#059669" : "#dc2626",
                      }}
                    >
                      Baseline: {selectedTest.baseline_execution_result.status}
                    </span>
                  )}
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>
                  {formatProposedTestDisplayName(selectedTest)}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedTest(null)}
                style={{
                  background: "#e2e8f0",
                  border: "none",
                  color: "#475569",
                  borderRadius: "50%",
                  width: 28,
                  height: 28,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
              >
                <FaTimes size={13} />
              </button>
            </div>

            {/* Modal Scrollable Content */}
            <div style={{ padding: "20px", overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Description & Target */}
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase" }}>Description</div>
                <p style={{ fontSize: 13, color: "#334155", margin: "4px 0 0 0", lineHeight: 1.5 }}>
                  {selectedTest.description || selectedTest.reason}
                </p>
              </div>

              {/* Side-by-Side Baseline vs Migrated Execution Result Card */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {/* Source Baseline Column */}
                <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 800, color: "#475569", textTransform: "uppercase", marginBottom: 6 }}>
                    Pre-Migration Baseline (Source)
                  </div>
                  <div style={{ fontSize: 12, color: "#334155", display: "flex", flexDirection: "column", gap: 4 }}>
                    <div>
                      <span style={{ fontWeight: 600 }}>Status: </span>
                      <span style={{ fontWeight: 800, color: selectedTest.baseline_execution_result?.status === "PASSED" ? "#059669" : selectedTest.baseline_execution_result?.status === "FAILED" ? "#dc2626" : "#64748b" }}>
                        {selectedTest.baseline_execution_result?.status || "Not Executed / Skipped"}
                      </span>
                    </div>
                    <div>
                      <span style={{ fontWeight: 600 }}>Duration: </span>
                      <span>{selectedTest.baseline_execution_result?.duration || "--"}</span>
                    </div>
                    {selectedTest.baseline_execution_result?.error && (
                      <div style={{ marginTop: 6, background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", borderRadius: 6, padding: 8 }}>
                        <div style={{ color: "#dc2626", fontWeight: 700, fontSize: 11 }}>Baseline Error:</div>
                        <pre style={{ margin: "4px 0 0 0", fontSize: 10, color: "#b91c1c", fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
                          {selectedTest.baseline_execution_result.error}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>

                {/* Target Migrated Column */}
                <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 800, color: "#475569", textTransform: "uppercase", marginBottom: 6 }}>
                    Post-Migration (Target)
                  </div>
                  <div style={{ fontSize: 12, color: "#334155", display: "flex", flexDirection: "column", gap: 4 }}>
                    <div>
                      <span style={{ fontWeight: 600 }}>Status: </span>
                      <span style={{ fontWeight: 800, color: selectedTest.execution_result?.status === "PASSED" ? "#059669" : selectedTest.execution_result?.status === "FAILED" ? "#dc2626" : "#64748b" }}>
                        {selectedTest.execution_result?.status || selectedTest.status || "Pending / Not Run"}
                      </span>
                    </div>
                    <div>
                      <span style={{ fontWeight: 600 }}>Duration: </span>
                      <span>{selectedTest.execution_result?.duration || "--"}</span>
                    </div>
                    {selectedTest.execution_result?.error && (
                      <div style={{ marginTop: 6, background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", borderRadius: 6, padding: 8 }}>
                        <div style={{ color: "#dc2626", fontWeight: 700, fontSize: 11 }}>Migrated Error:</div>
                        <pre style={{ margin: "4px 0 0 0", fontSize: 10, color: "#b91c1c", fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
                          {selectedTest.execution_result.error}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Execution Steps */}
              {selectedTest.steps && selectedTest.steps.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", marginBottom: 6 }}>
                    Playwright Test Steps
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {selectedTest.steps.map((s, idx) => (
                      <div
                        key={`step-${idx}`}
                        style={{
                          background: "#f8fafc",
                          border: "1px solid #e2e8f0",
                          borderRadius: 6,
                          padding: "8px 12px",
                          fontSize: 12,
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          color: "#0f172a",
                        }}
                      >
                        <span style={{ fontFamily: "monospace", fontSize: 11, color: "#0284c7", fontWeight: 700 }}>
                          #{idx + 1}
                        </span>
                        <span>{s}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Stdout / Logs output */}
              {selectedTest.execution_result?.stdout && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", marginBottom: 4 }}>
                    Execution Log
                  </div>
                  <pre
                    style={{
                      background: "#030712",
                      border: "1px solid #1f2937",
                      borderRadius: 8,
                      padding: 12,
                      fontSize: 11,
                      color: "#94a3b8",
                      fontFamily: "monospace",
                      whiteSpace: "pre-wrap",
                      maxHeight: 160,
                      overflowY: "auto",
                      margin: 0,
                    }}
                  >
                    {selectedTest.execution_result.stdout}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
