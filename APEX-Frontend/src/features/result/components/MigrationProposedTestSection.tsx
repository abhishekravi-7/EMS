import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  FaSpinner,
  FaRedo,
  FaDownload,
  FaTerminal,
  FaTimes,
  FaExternalLinkAlt,
} from "react-icons/fa";
import {
  getProposedTestsStatus,
  getProposedTestsResults,
  runApprovedProposedTests,
  type ProposedTestCase,
  type ProposedTestMetrics,
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
  const [logs, setLogs] = useState<Array<{ ts?: string; msg?: string; level?: string }>>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const [selectedTest, setSelectedTest] = useState<ProposedTestCase | null>(null);
  const [showLogs, setShowLogs] = useState(true);
  const [selectedSources, setSelectedSources] = useState<string[] | null>(null);
  const [allureReportAvailable, setAllureReportAvailable] = useState(false);
  const [allureReportUrl, setAllureReportUrl] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logBoxRef = useRef<HTMLDivElement | null>(null);

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
        if (statusData.proposals) setProposals((prev) => (JSON.stringify(prev) === JSON.stringify(statusData.proposals) ? prev : statusData.proposals));
        if (statusData.metrics) setMetrics((prev) => (JSON.stringify(prev) === JSON.stringify(statusData.metrics) ? prev : statusData.metrics));
        if (statusData.logs) setLogs((prev) => (JSON.stringify(prev) === JSON.stringify(statusData.logs) ? prev : statusData.logs));
        if (statusData.selected_sources) setSelectedSources((prev) => (JSON.stringify(prev) === JSON.stringify(statusData.selected_sources) ? prev : statusData.selected_sources));

        if (statusData.allure_report_available !== undefined) {
          setAllureReportAvailable((prev) => (prev !== statusData.allure_report_available ? statusData.allure_report_available : prev));
          if (statusData.allure_report_url) setAllureReportUrl((prev) => (prev !== statusData.allure_report_url ? statusData.allure_report_url : prev));
        }

        if (statusData.status === "COMPLETED" || statusData.status === "FAILED") {
          if (pollRef.current) clearInterval(pollRef.current);
          setIsRunning(false);

          // Fetch final results payload
          const finalResults = await getProposedTestsResults(jobId).catch(() => null);
          if (finalResults?.test_cases) setProposals((prev) => (JSON.stringify(prev) === JSON.stringify(finalResults.test_cases) ? prev : (finalResults.test_cases || [])));
          if (finalResults?.metrics) setMetrics((prev) => (JSON.stringify(prev) === JSON.stringify(finalResults.metrics) ? prev : (finalResults.metrics || null)));
          if (finalResults?.selected_sources) setSelectedSources((prev) => (JSON.stringify(prev) === JSON.stringify(finalResults.selected_sources) ? prev : (finalResults.selected_sources || null)));
          if (finalResults?.allure_report_available !== undefined) {
            setAllureReportAvailable((prev) => (prev !== finalResults.allure_report_available ? finalResults.allure_report_available : prev));
            if (finalResults.allure_report_url) setAllureReportUrl((prev) => (prev !== finalResults.allure_report_url ? finalResults.allure_report_url : prev));
          }
        }
      } catch (err) {
        console.error("Polling proposed tests error:", err);
      }
    }, 10000); // Increased from 1s to 10s to reduce load
  }, [jobId]);

  // Load initial status and results
  useEffect(() => {
    if (!jobId) return;

    let isMounted = true;

    const loadData = async () => {
      try {
        const res = await getProposedTestsStatus(jobId);
        if (!isMounted) return;

        if (res) {
          if (res.proposals) setProposals((prev) => (JSON.stringify(prev) === JSON.stringify(res.proposals) ? prev : res.proposals));
          if (res.metrics) setMetrics((prev) => (JSON.stringify(prev) === JSON.stringify(res.metrics) ? prev : res.metrics));
          if (res.logs) setLogs((prev) => (JSON.stringify(prev) === JSON.stringify(res.logs) ? prev : res.logs));
          if (res.selected_sources) setSelectedSources((prev) => (JSON.stringify(prev) === JSON.stringify(res.selected_sources) ? prev : res.selected_sources));

          setAllureReportAvailable((prev) => (res.allure_report_available !== undefined && prev !== res.allure_report_available ? res.allure_report_available : prev));
          if (res.allure_report_url) setAllureReportUrl((prev) => (prev !== res.allure_report_url ? res.allure_report_url : prev));

          if (res.status === "RUNNING") {
            setIsRunning((prev) => (prev ? prev : true));
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

  const handleRunAgain = async () => {
    if (!jobId || isRunning) return;
    setIsRunning(true);
    setLogs([]);
    try {
      await runApprovedProposedTests(jobId, {
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

  const statusLabel = isRunning ? "running playwright tests" : executedCount > 0 ? "completed" : "awaiting first run";
  const statusColor = isRunning ? "#0284c7" : executedCount > 0 ? (failedCount === 0 ? "#10b981" : "#ef4444") : "#d97706";

  return (
    <div style={styles.reportSection}>
      {/* Section Title Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a" }}>
          Proposed Test Case Information
        </div>
      </div>

      {/* Main White Modern Container Card */}
      <div
        style={{
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: 16,
          padding: "24px",
          color: "#0f172a",
          boxShadow: "0 4px 20px -2px rgba(0, 0, 0, 0.05)",
        }}
      >
        {/* Card Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h3 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: "#0f172a", letterSpacing: "-0.02em" }}>
                Proposed Test Cases Summary
              </h3>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 900,
                  padding: "2px 8px",
                  borderRadius: 6,
                  background: "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)",
                  color: "#fff",
                  letterSpacing: "0.05em",
                }}
              >
                PLAYWRIGHT RUNNER
              </span>
            </div>
            <div style={{ fontSize: 13, color: "#64748b", marginTop: 4, fontFamily: "'JetBrains Mono', monospace" }}>
              Migrated Application Target · {totalProposed} Total Proposed Scenarios
            </div>
          </div>

          {/* Status Badge & Action Controls */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 12px",
                borderRadius: 20,
                background: isRunning ? "rgba(2, 132, 199, 0.1)" : executedCount > 0 ? (failedCount === 0 ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)") : "rgba(217, 119, 6, 0.1)",
                border: `1px solid ${isRunning ? "rgba(2, 132, 199, 0.3)" : executedCount > 0 ? (failedCount === 0 ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)") : "rgba(217, 119, 6, 0.3)"}`,
                fontSize: 12,
                fontWeight: 700,
                color: statusColor,
                fontFamily: "'JetBrains Mono', monospace",
                textTransform: "uppercase",
              }}
            >
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: statusColor }}></span>
              {statusLabel}
            </div>

            {/* Run Again Button */}
            <button
              type="button"
              onClick={handleRunAgain}
              disabled={isRunning || isLoading}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 14px",
                borderRadius: 8,
                background: isRunning ? "#94a3b8" : "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)",
                border: "none",
                color: "#fff",
                fontSize: 12,
                fontWeight: 700,
                cursor: isRunning ? "not-allowed" : "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <FaRedo className={isRunning ? "animate-spin" : ""} size={11} />
              {isRunning ? "Running Tests..." : "Run Again"}
            </button>

            {/* View Allure Report Button */}
            <button
              type="button"
              onClick={handleViewAllureReport}
              disabled={isRunning || (!allureReportAvailable && executedCount === 0)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 14px",
                borderRadius: 8,
                background: isRunning
                  ? "#f1f5f9"
                  : allureReportAvailable || executedCount > 0
                  ? "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)"
                  : "#f1f5f9",
                border: isRunning || (!allureReportAvailable && executedCount === 0) ? "1px solid #cbd5e1" : "none",
                color: isRunning || (!allureReportAvailable && executedCount === 0) ? "#94a3b8" : "#fff",
                fontSize: 12,
                fontWeight: 700,
                cursor: isRunning || (!allureReportAvailable && executedCount === 0) ? "not-allowed" : "pointer",
                transition: "all 0.15s ease",
              }}
              title={
                isRunning
                  ? "Generating Allure Report..."
                  : allureReportAvailable || executedCount > 0
                  ? "Open interactive Allure report in new tab"
                  : "No Allure report available yet"
              }
            >
              {isRunning ? (
                <>
                  <FaSpinner className="animate-spin" size={11} />
                  <span>Generating Allure Report...</span>
                </>
              ) : (
                <>
                  <FaExternalLinkAlt size={10} />
                  <span>View Allure Report</span>
                </>
              )}
            </button>

            {/* Download Report Button */}
            <button
              type="button"
              onClick={handleDownloadReport}
              disabled={isDownloading || totalProposed === 0}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 14px",
                borderRadius: 8,
                background: "#f8fafc",
                border: "1px solid #cbd5e1",
                color: "#334155",
                fontSize: 12,
                fontWeight: 700,
                cursor: isDownloading ? "not-allowed" : "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {isDownloading ? <FaSpinner className="animate-spin" size={11} /> : <FaDownload size={11} />}
              Download Report
            </button>
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

          {/* Metric Overview Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px 24px" }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#0f172a" }}>{totalProposed}</div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>TOTAL PROPOSED TESTS</div>
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#059669" }}>{passedCount}</div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>PASSED</div>
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: failedCount > 0 ? "#dc2626" : "#64748b" }}>{failedCount}</div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>FAILED</div>
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#d97706" }}>{skippedCount}</div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>SKIPPED</div>
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#64748b" }}>{notExecutedCount}</div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>NOT EXECUTED</div>
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#0284c7", fontFamily: "monospace" }}>{durationDisplay}</div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>EXECUTION DURATION</div>
            </div>
          </div>
        </div>

        {/* Source Breakdown Cards Grid (Dynamic: LLM, Functional Doc, Existing, Total) */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#475569", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 10 }}>
            Source Breakdown
          </div>
          <div style={{ display: "grid", gridTemplateColumns: existingCount > 0 ? "repeat(4, 1fr)" : "repeat(3, 1fr)", gap: 14 }}>
            {/* Card 1: LLM Generated */}
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "14px 16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 20, fontWeight: 800, color: "#0284c7" }}>{llmCount}</span>
                <span style={{ fontSize: 10, fontWeight: 800, color: "#0284c7", background: "#f0f9ff", border: "1px solid #bae6fd", padding: "2px 6px", borderRadius: 4 }}>LLM</span>
              </div>
              <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginTop: 8 }}>LLM Generated Test Cases</div>
            </div>

            {/* Card 2: Functional Testing Document */}
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "14px 16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 20, fontWeight: 800, color: "#7c3aed" }}>{functionalDocCount}</span>
                <span style={{ fontSize: 10, fontWeight: 800, color: "#7c3aed", background: "#faf5ff", border: "1px solid #d8b4fe", padding: "2px 6px", borderRadius: 4 }}>DOC</span>
              </div>
              <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginTop: 8 }}>Functional Testing Document Tests</div>
            </div>

            {/* Card 3: Existing Test Cases (if any) */}
            {existingCount > 0 && (
              <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "14px 16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 20, fontWeight: 800, color: "#059669" }}>{existingCount}</span>
                  <span style={{ fontSize: 10, fontWeight: 800, color: "#059669", background: "#ecfdf5", border: "1px solid #a7f3d0", padding: "2px 6px", borderRadius: 4 }}>EXISTING</span>
                </div>
                <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginTop: 8 }}>Existing Repository Tests</div>
              </div>
            )}

            {/* Card 4: Total Executable */}
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "14px 16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 20, fontWeight: 800, color: "#0f172a" }}>{totalProposed}</span>
                <span style={{ fontSize: 10, fontWeight: 800, color: "#475569", background: "#e2e8f0", border: "1px solid #cbd5e1", padding: "2px 6px", borderRadius: 4 }}>TOTAL</span>
              </div>
              <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginTop: 8 }}>Total Executable Tests</div>
            </div>
          </div>
        </div>

        {/* Functional Test Type Breakdown Cards Grid (API, UI, Total) */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: "#475569", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 10 }}>
            Functional Test Type Breakdown
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
            {/* Card 1: API */}
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "14px 16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 20, fontWeight: 800, color: "#0284c7" }}>{proposals.filter((p) => p.type === "API").length}</span>
                <span style={{ fontSize: 10, fontWeight: 800, color: "#0284c7", background: "#f0f9ff", border: "1px solid #bae6fd", padding: "2px 6px", borderRadius: 4 }}>API</span>
              </div>
              <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginTop: 8 }}>API Functional Tests (Playwright API)</div>
            </div>

            {/* Card 2: UI */}
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "14px 16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 20, fontWeight: 800, color: "#7c3aed" }}>{proposals.filter((p) => p.type === "UI").length}</span>
                <span style={{ fontSize: 10, fontWeight: 800, color: "#7c3aed", background: "#faf5ff", border: "1px solid #d8b4fe", padding: "2px 6px", borderRadius: 4 }}>UI</span>
              </div>
              <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginTop: 8 }}>UI Functional Tests (Playwright Browser)</div>
            </div>

            {/* Card 3: Total Functional Scenarios */}
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "14px 16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 20, fontWeight: 800, color: "#0f172a" }}>{proposals.filter((p) => p.type === "API" || p.type === "UI").length}</span>
                <span style={{ fontSize: 10, fontWeight: 800, color: "#475569", background: "#e2e8f0", border: "1px solid #cbd5e1", padding: "2px 6px", borderRadius: 4 }}>TOTAL</span>
              </div>
              <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginTop: 8 }}>Total Functional Scenarios (API + UI)</div>
            </div>
          </div>
        </div>

        {/* Executed Proposed Test Method Details Table */}
        <div style={{ marginTop: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", marginBottom: 10, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>Executed Proposed Test Method Details ({proposals.length} scenarios)</span>
            <span style={{ fontSize: 11, color: "#64748b", fontWeight: 600 }}>Click row for step assertions &amp; evidence</span>
          </div>

          <div style={{ maxHeight: 320, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 8, background: "#ffffff" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#f8fafc", color: "#475569", borderBottom: "1px solid #e2e8f0", position: "sticky", top: 0, zIndex: 2 }}>
                  <th style={{ padding: "8px 12px", width: 70, fontWeight: 700 }}>ID</th>
                  <th style={{ padding: "8px 12px", fontWeight: 700 }}>Test Name</th>
                  <th style={{ padding: "8px 12px", width: 150, fontWeight: 700 }}>Source</th>
                  <th style={{ padding: "8px 12px", width: 80, fontWeight: 700 }}>Type</th>
                  <th style={{ padding: "8px 12px", width: 100, fontWeight: 700 }}>Status</th>
                  <th style={{ padding: "8px 12px", width: 90, fontWeight: 700 }}>Duration</th>
                  <th style={{ padding: "8px 12px", width: 70, fontWeight: 700, textAlign: "center" }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={7} style={{ padding: "36px 12px", textAlign: "center", color: "#64748b" }}>
                      <FaSpinner className="animate-spin" size={18} style={{ marginBottom: 6 }} />
                      <div>Loading proposed test execution data...</div>
                    </td>
                  </tr>
                ) : proposals.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ padding: "28px 12px", textAlign: "center", color: "#64748b" }}>
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

                    const status = t.status || (t.execution_result ? t.execution_result.status : "PROPOSED");
                    const isPassed = status === "PASSED";
                    const isFailed = status === "FAILED";
                    const isSkipped = status === "SKIPPED";
                    const isRunningRow = status === "RUNNING";

                    const statusBg = isPassed
                      ? "rgba(16, 185, 129, 0.12)"
                      : isFailed
                      ? "rgba(239, 68, 68, 0.12)"
                      : isRunningRow
                      ? "rgba(2, 132, 199, 0.12)"
                      : "rgba(100, 116, 139, 0.12)";
                    const statusTextColor = isPassed
                      ? "#059669"
                      : isFailed
                      ? "#dc2626"
                      : isRunningRow
                      ? "#0284c7"
                      : "#64748b";
                    const statusBorder = isPassed
                      ? "1px solid rgba(16, 185, 129, 0.3)"
                      : isFailed
                      ? "1px solid rgba(239, 68, 68, 0.3)"
                      : isRunningRow
                      ? "1px solid rgba(2, 132, 199, 0.3)"
                      : "1px solid rgba(100, 116, 139, 0.3)";

                    const duration = t.execution_result?.duration || "--";

                    return (
                      <tr
                        key={`prop-test-${t.id}-${idx}`}
                        onClick={() => setSelectedTest(t)}
                        style={{
                          borderBottom: "1px solid #e2e8f0",
                          color: "#0f172a",
                          cursor: "pointer",
                          transition: "background 0.12s ease",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      >
                        <td style={{ padding: "8px 12px", fontFamily: "monospace", color: "#0284c7", fontWeight: 700 }}>
                          {t.id}
                        </td>
                        <td style={{ padding: "8px 12px", fontWeight: 600 }}>
                          {t.title}
                        </td>
                        <td style={{ padding: "8px 12px" }}>
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
                        <td style={{ padding: "8px 12px", fontSize: 11, color: "#64748b" }}>
                          {t.type}
                        </td>
                        <td style={{ padding: "8px 12px" }}>
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              padding: "2px 8px",
                              borderRadius: 4,
                              fontSize: 10,
                              fontWeight: 800,
                              background: statusBg,
                              color: statusTextColor,
                              border: statusBorder,
                            }}
                          >
                            {isRunningRow && <FaSpinner className="animate-spin" size={8} />}
                            {isPassed ? "✓ PASSED" : isFailed ? "✕ FAILED" : isSkipped ? "⚠ SKIPPED" : status}
                          </span>
                        </td>
                        <td style={{ padding: "8px 12px", color: "#64748b", fontSize: 11, fontFamily: "monospace" }}>
                          {duration}
                        </td>
                        <td style={{ padding: "8px 12px", textAlign: "center" }}>
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

        {/* Live Execution Logs Console */}
        <div style={{ marginTop: 24 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 8,
              cursor: "pointer",
            }}
            onClick={() => setShowLogs(!showLogs)}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, color: "#475569" }}>
              <FaTerminal size={12} style={{ color: "#0284c7" }} />
              <span>PLAYWRIGHT EXECUTION LOGS ({logs.length} entries)</span>
            </div>
            <span style={{ fontSize: 11, color: "#64748b" }}>
              {showLogs ? "Hide Console ▲" : "Show Console ▼"}
            </span>
          </div>

          {showLogs && (
            <div
              ref={logBoxRef}
              style={{
                background: "#030712",
                border: "1px solid #1f2937",
                borderRadius: 8,
                padding: "12px 14px",
                maxHeight: 200,
                overflowY: "auto",
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                lineHeight: 1.5,
                color: "#e2e8f0",
              }}
            >
              {logs.length === 0 ? (
                <div style={{ color: "#64748b", fontStyle: "italic" }}>
                  {isRunning ? "Waiting for Playwright test worker output..." : "No execution logs yet. Click 'Run Again' to execute proposed tests."}
                </div>
              ) : (
                logs.map((log, i) => (
                  <div key={`prop-log-${i}`} style={{ display: "flex", gap: 8, marginBottom: 2 }}>
                    {log.ts && <span style={{ color: "#64748b", flexShrink: 0 }}>[{log.ts}]</span>}
                    {log.level && (
                      <span
                        style={{
                          color: log.level === "ERROR" ? "#f87171" : log.level === "WARN" ? "#fbbf24" : "#38bdf8",
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        [{log.level}]
                      </span>
                    )}
                    <span style={{ wordBreak: "break-all" }}>{log.msg}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Test Details Modal / Drawer ────────────────────────────────────────── */}
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
              maxWidth: 720,
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
                    {selectedTest.status || "PROPOSED"}
                  </span>
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>
                  {selectedTest.title}
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

              {/* Error or Trace output if failed */}
              {selectedTest.execution_result?.error && (
                <div style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.25)", borderRadius: 8, padding: 12 }}>
                  <div style={{ color: "#dc2626", fontWeight: 800, fontSize: 12, marginBottom: 4 }}>
                    Execution Failure:
                  </div>
                  <pre style={{ margin: 0, fontSize: 11, color: "#b91c1c", fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
                    {selectedTest.execution_result.error}
                  </pre>
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
