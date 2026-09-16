import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  FaSpinner,
  FaRedo,
  FaDownload,
  FaTerminal,
  FaTimes,
  FaExternalLinkAlt,
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
        const res = await getProposedTestsStatus(jobId);
        if (!isMounted) return;

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

  const passRateNum = executedCount > 0 ? Math.round((passedCount / executedCount) * 100) : 100;
  const passRateDisplay = `${passRateNum}%`;
  const durationDisplay = metrics?.duration || "0.0s";

  const statusLabel = isRunning ? "RUNNING" : executedCount > 0 ? "COMPLETED" : "AWAITING RUN";

  // Breakdown Calculations
  const apiCount = proposals.filter(p => p.type === "API").length;
  const uiCount = proposals.filter(p => p.type === "UI").length;

  const llmCount = proposals.filter(p => p.generation_source !== "BRD_DOCUMENT" && p.generation_source !== "EXISTING").length;
  const docCount = proposals.filter(p => p.generation_source === "BRD_DOCUMENT").length;

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

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            background: "#ecfdf5",
            color: "#059669",
            padding: "6px 16px",
            borderRadius: 20,
            fontSize: 12,
            fontWeight: 800,
            border: "1px solid #a7f3d0",
            display: "flex",
            alignItems: "center",
            gap: 8
          }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#059669" }} />
            {statusLabel}
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

        {/* TOP CARDS GRID (REDUCED HEIGHT) */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12, flex: 1 }}>
          {[
            { label: "Total Proposed Tests", value: totalProposed, color: "#2563eb", icon: <FaListUl />, bg: "#eff6ff" },
            { label: "Passed", value: passedCount, color: "#10b981", icon: <FaCheckCircle />, bg: "#f0fdf4" },
            { label: "Failed", value: failedCount, color: "#ef4444", icon: <FaTimesCircle />, bg: "#fef2f2" },
            { label: "Skipped", value: skippedCount, color: "#f59e0b", icon: <FaHourglassHalf />, bg: "#fffbeb" },
            { label: "Not Executed", value: notExecutedCount, color: "#64748b", icon: <FaMinusCircle />, bg: "#f8fafc" },
            { label: "Execution Duration", value: durationDisplay, color: "#7c3aed", icon: <FaClock />, bg: "#f5f3ff" }
          ].map((m, i) => (
            <div key={i} style={{ background: m.bg, border: "1px solid rgba(0,0,0,0.03)", borderRadius: 12, padding: "12px 4px", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <div style={{ background: `${m.color}15`, color: m.color, width: 22, height: 22, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10 }}>
                {m.icon}
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#0f172a" }}>{m.value}</div>
              <div style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", lineHeight: 1.2 }}>{m.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── BREAKDOWNS AREA (GRID 2-COL) ─────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32, marginBottom: 48 }}>
        {/* Source Breakdown Section */}
        <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <h4 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "#0f172a" }}>Source Breakdown</h4>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            {[
                { label: "LLM Generated", value: llmCount, tag: "LLM", color: "#7c3aed", bg: "#f5f3ff" },
                { label: "Functional Doc", value: docCount, tag: "DOC", color: "#2563eb", bg: "#eff6ff" },
                { label: "Total Executable", value: totalProposed, tag: "TOTAL", color: "#10b981", bg: "#f0fdf4" },
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
          <h4 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "#0f172a" }}>Executed Test Method Details ({proposals.length} scenarios)</h4>
        </div>
        <div style={{ border: "1px solid #eef2f6", borderRadius: 16, overflowY: "auto", background: "#ffffff", boxShadow: "0 2px 12px rgba(0,0,0,0.02)", maxHeight: 350 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead style={{ background: "#f8fafc", borderBottom: "1px solid #eef2f6", position: "sticky", top: 0, zIndex: 10 }}>
              <tr>
                <th style={{ padding: "16px 20px", textAlign: "left", color: "#64748b", fontWeight: 600 }}>Test ID</th>
                <th style={{ padding: "16px 20px", textAlign: "left", color: "#64748b", fontWeight: 600 }}>Scenario Title</th>
                <th style={{ padding: "16px 20px", textAlign: "center", color: "#64748b", fontWeight: 600 }}>Source</th>
                <th style={{ padding: "16px 20px", textAlign: "center", color: "#64748b", fontWeight: 600 }}>Type</th>
                <th style={{ padding: "16px 20px", textAlign: "center", color: "#64748b", fontWeight: 600 }}>Status</th>
                <th style={{ padding: "16px 20px", textAlign: "right", color: "#64748b", fontWeight: 600 }}>Duration</th>
              </tr>
            </thead>
            <tbody>
              {proposals.map((t, idx) => (
                <tr key={idx} onClick={() => setSelectedTest(t)} style={{ borderBottom: "1px solid #f1f5f9", cursor: "pointer", transition: "background 0.1s" }} onMouseEnter={e => e.currentTarget.style.background="#f8fafc"} onMouseLeave={e => e.currentTarget.style.background="transparent"}>
                  <td style={{ padding: "16px 20px", color: "#7c3aed", fontWeight: 700, fontFamily: "monospace" }}>{t.id}</td>
                  <td style={{ padding: "16px 20px", color: "#0f172a", fontWeight: 500 }}>{t.title}</td>
                  <td style={{ padding: "16px 20px", textAlign: "center" }}>
                    <span style={{ fontSize: 10, fontWeight: 800, color: "#2563eb", background: "#eff6ff", padding: "3px 10px", borderRadius: 6, border: "1px solid #dbeafe" }}>
                      {t.generation_source === "BRD_DOCUMENT" ? "BRD Doc" : t.generation_source === "EXISTING" ? "Repo" : "LLM"}
                    </span>
                  </td>
                  <td style={{ padding: "16px 20px", textAlign: "center" }}><span style={{ color: "#64748b", fontWeight: 600, fontSize: 11 }}>{t.type}</span></td>
                  <td style={{ padding: "16px 20px", textAlign: "center" }}>
                    <span style={{ background: t.status === "PASSED" ? "#ecfdf5" : "#fee2e2", color: t.status === "PASSED" ? "#059669" : "#dc2626", padding: "4px 12px", borderRadius: 20, fontSize: 10, fontWeight: 800, border: `1px solid ${t.status === "PASSED" ? "#a7f3d0" : "#fecaca"}` }}>
                      {t.status === "PASSED" ? "✓ PASSED" : "✕ FAILED"}
                    </span>
                  </td>
                  <td style={{ padding: "16px 20px", textAlign: "right", color: "#64748b", fontFamily: "monospace" }}>{t.execution_result?.duration || "0.17s"}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
            <button onClick={() => setShowLogs(!showLogs)} style={{ background: "none", border: "none", color: "#2563eb", fontSize: 12, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
              {showLogs ? "Hide Console ▲" : "Show Console ▼"}
            </button>
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
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          width: "100vw",
          height: "100vh",
          zIndex: 10000000,
          background: "rgba(15, 23, 42, 0.75)",
          backdropFilter: "blur(12px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "20px",
          pointerEvents: "auto"
        }} onClick={() => setSelectedTest(null)}>
           <div style={{
             background: "#fff",
             borderRadius: 24,
             maxWidth: 800,
             width: "90%",
             maxHeight: "85vh",
             overflow: "hidden",
             display: "flex",
             flexDirection: "column",
             boxShadow: "0 50px 100px -20px rgba(0, 0, 0, 0.6)",
             position: "relative",
             zIndex: 10000001
           }} onClick={e => e.stopPropagation()}>
              <div style={{ padding: "24px 32px", borderBottom: "1px solid #f1f5f9", display: "flex", justifyContent: "space-between", alignItems: "flex-start", background: "#f8fafc" }}>
                 <div>
                    <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
                      <span style={{ fontSize: 10, fontWeight: 900, background: "#7c3aed", color: "#fff", padding: "2px 8px", borderRadius: 4 }}>{selectedTest.id}</span>
                      <span style={{ fontSize: 10, fontWeight: 800, background: "#e2e8f0", color: "#64748b", padding: "2px 8px", borderRadius: 4 }}>{selectedTest.type}</span>
                    </div>
                    <h4 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#0f172a" }}>{selectedTest.title}</h4>
                 </div>
                 <button onClick={() => setSelectedTest(null)} style={{ background: "#fff", border: "1px solid #e2e8f0", width: 40, height: 40, borderRadius: "50%", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b", transition: "all 0.2s" }} onMouseEnter={e => e.currentTarget.style.borderColor = "#cbd5e1"} onMouseLeave={e => e.currentTarget.style.borderColor = "#e2e8f0"}><FaTimes /></button>
              </div>
              <div style={{ padding: "32px", overflowY: "auto", flex: 1 }}>
                 <div style={{ marginBottom: 28 }}>
                    <div style={{ fontSize: 11, fontWeight: 800, color: "#94a3b8", marginBottom: 8, letterSpacing: "0.05em" }}>SCENARIO DESCRIPTION</div>
                    <p style={{ margin: 0, fontSize: 15, color: "#334155", lineHeight: 1.7 }}>{selectedTest.description || selectedTest.reason}</p>
                 </div>
                 {selectedTest.steps && selectedTest.steps.length > 0 && (
                   <div style={{ marginBottom: 28 }}>
                      <div style={{ fontSize: 11, fontWeight: 800, color: "#94a3b8", marginBottom: 16, letterSpacing: "0.05em" }}>VALIDATION STEPS</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                         {selectedTest.steps.map((s, idx) => (
                           <div key={idx} style={{ display: "flex", gap: 16, padding: "14px 18px", background: "#f8fafc", borderRadius: 12, fontSize: 14, border: "1px solid #f1f5f9" }}>
                              <span style={{ color: "#7c3aed", fontWeight: 800, fontFamily: "monospace" }}>{idx + 1}</span>
                              <span style={{ color: "#0f172a", fontWeight: 500 }}>{s}</span>
                           </div>
                         ))}
                      </div>
                   </div>
                 )}
                 {selectedTest.execution_result?.stdout && (
                    <div>
                       <div style={{ fontSize: 11, fontWeight: 800, color: "#94a3b8", marginBottom: 12, letterSpacing: "0.05em" }}>RUNNER STDOUT</div>
                       <pre style={{ margin: 0, background: "#0f172a", color: "#94a3b8", padding: "20px", borderRadius: 12, fontSize: 12, overflowX: "auto", fontFamily: "'JetBrains Mono', monospace", lineHeight: 1.6 }}>{selectedTest.execution_result.stdout}</pre>
                    </div>
                 )}
              </div>
           </div>
        </div>
      )}
    </div>
  );
}