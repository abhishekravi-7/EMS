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

  // ── Search & Filter State (UI only, no logic changes) ─────────────────
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [filterMethod, setFilterMethod] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterSource, setFilterSource] = useState("all");

  const filteredProposals = proposals.filter((t) => {
    const method = t.api_spec?.method || (t.type === "API" ? "GET" : "--");
    const endpoint = t.api_spec?.endpoint || t.ui_spec?.target_route || "";
    const execStatus = t.execution_result?.status || t.baseline_execution_result?.status || t.status || "NOT_EXECUTED";
    const isDoc = t.generation_source === "BRD_DOCUMENT" || t.generation_source === "BRD_AND_AI" || t.generation_source === "FUNCTIONAL_DOC" || t.id.includes("BRD") || t.source === "BRD Document";
    const isExisting = t.generation_source === "EXISTING" || t.generation_source === "EXISTING_TESTS" || t.id.includes("EXT") || t.source === "Existing Repository";
    const sourceLbl = isExisting ? "existing" : isDoc ? "doc" : "llm";

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      if (!formatProposedTestDisplayName(t).toLowerCase().includes(q) && !endpoint.toLowerCase().includes(q) && !method.toLowerCase().includes(q) && !t.id.toLowerCase().includes(q)) return false;
    }
    if (filterType !== "all" && (t.type || "").toLowerCase() !== filterType.toLowerCase()) return false;
    if (filterMethod !== "all" && method.toLowerCase() !== filterMethod.toLowerCase()) return false;
    if (filterStatus !== "all" && execStatus.toLowerCase() !== filterStatus.toLowerCase()) return false;
    if (filterSource !== "all" && sourceLbl !== filterSource) return false;
    return true;
  });

  const hasActiveFilters = searchQuery || filterType !== "all" || filterMethod !== "all" || filterStatus !== "all" || filterSource !== "all";

  const clearFilters = () => {
    setSearchQuery("");
    setFilterType("all");
    setFilterMethod("all");
    setFilterStatus("all");
    setFilterSource("all");
  };

  return (
    <div style={{ ...styles.reportSection, background: "#f8fafc", border: "none", borderRadius: 0, padding: "0", boxShadow: "none" }}>

      {/* ── SECTION 1: HEADER CARD ─────────────────────────────────────── */}
      <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 14, padding: "20px 24px", marginBottom: 16, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
        {/* Top row: Title + KPI strip + Pass Rate + Actions */}
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>

          {/* Title block */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0, minWidth: 220 }}>
            <div style={{ background: "linear-gradient(135deg, #2563eb, #7c3aed)", color: "#fff", width: 40, height: 40, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>
              <FaFileAlt />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#0f172a", lineHeight: 1.2 }}>Proposed Test Case Information</h3>
              <p style={{ margin: "3px 0 0 0", fontSize: 12, color: "#64748b", fontWeight: 500 }}>Automatically generated test cases from your application using LLM.</p>
            </div>
          </div>

          {/* KPI Strip */}
          <div style={{ display: "flex", gap: 12, flex: 1, flexWrap: "wrap", alignItems: "center" }}>
            {[
              { label: "Total Inventory", value: totalProposed, color: "#2563eb", bg: "#eff6ff", icon: <FaListUl size={13} /> },
              { label: "Valid", value: validCount, color: "#059669", bg: "#ecfdf5", icon: <FaCheckCircle size={13} /> },
              { label: "Duplicate", value: duplicateCount, color: "#d97706", bg: "#fffbeb", icon: <FaHourglassHalf size={13} /> },
              { label: "Hallucinated", value: hallucinatedCount, color: "#7c3aed", bg: "#f5f3ff", icon: <FaMinusCircle size={13} /> },
              { label: "Invalid", value: invalidCount, color: "#dc2626", bg: "#fef2f2", icon: <FaTimesCircle size={13} /> },
            ].map((kpi, i) => (
              <div key={i} style={{ background: kpi.bg, border: `1px solid ${kpi.color}22`, borderRadius: 10, padding: "10px 14px", display: "flex", alignItems: "center", gap: 10, minWidth: 110 }}>
                <div style={{ color: kpi.color }}>{kpi.icon}</div>
                <div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: kpi.color, lineHeight: 1 }}>{kpi.value}</div>
                  <div style={{ fontSize: 10, fontWeight: 600, color: "#64748b", marginTop: 2 }}>{kpi.label}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Pass Rate Donut + Actions */}
          <div style={{ display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
            {/* Donut */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <div style={{ position: "relative", width: 80, height: 80 }}>
                <svg width="80" height="80" viewBox="0 0 80 80">
                  <circle cx="40" cy="40" r="34" fill="none" stroke="#e2e8f0" strokeWidth="8" />
                  <circle cx="40" cy="40" r="34" fill="none" stroke={passRateNum > 0 ? "#2563eb" : "#cbd5e1"} strokeWidth="8"
                    strokeDasharray={`${passRateNum * 2.136} 213.6`} strokeLinecap="round" transform="rotate(-90 40 40)" />
                </svg>
                <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>{passRateDisplay}</span>
                </div>
              </div>
              <div style={{ fontSize: 9, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>Pass Rate</div>
              <div style={{ fontSize: 10, color: "#94a3b8", textAlign: "center", maxWidth: 110, lineHeight: 1.3 }}>Execution pass percentage across Playwright test suite.</div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <button
                onClick={handleRunAgain}
                disabled={isRunning}
                style={{ background: isRunning ? "#94a3b8" : "#7c3aed", color: "#fff", border: "none", padding: "9px 18px", borderRadius: 8, fontSize: 13, fontWeight: 700, display: "flex", alignItems: "center", gap: 8, cursor: isRunning ? "default" : "pointer", whiteSpace: "nowrap" }}
              >
                {isRunning ? <FaSpinner className="animate-spin" size={11} /> : <FaPlay size={10} />}
                {isRunning ? "Running..." : "Run Again"}
              </button>
              <button
                onClick={handleViewAllureReport}
                disabled={!allureReportAvailable && executedCount === 0}
                style={{ background: allureReportAvailable || executedCount > 0 ? "#2563eb" : "#94a3b8", color: "#fff", border: "none", padding: "9px 18px", borderRadius: 8, fontSize: 13, fontWeight: 700, display: "flex", alignItems: "center", gap: 8, cursor: "pointer", whiteSpace: "nowrap" }}
              >
                <FaExternalLinkAlt size={11} /> View Allure Report
              </button>
              <button
                onClick={handleDownloadReport}
                disabled={isDownloading}
                style={{ background: "#ffffff", border: "1px solid #e2e8f0", padding: "9px 18px", borderRadius: 8, fontSize: 13, fontWeight: 700, color: "#0f172a", display: "flex", alignItems: "center", gap: 8, cursor: "pointer", whiteSpace: "nowrap" }}
              >
                {isDownloading ? <FaSpinner className="animate-spin" size={11} /> : <FaDownload size={11} />}
                {isDownloading ? "Downloading..." : "Download Report"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── SECTION 2: BREAKDOWNS ──────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
        {/* Source Breakdown */}
        <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 14, padding: "18px 20px", boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
          <h4 style={{ margin: "0 0 14px 0", fontSize: 14, fontWeight: 700, color: "#0f172a" }}>Source Breakdown</h4>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {[
              { label: "LLM Generated", value: llmCount, tag: "LLM", color: "#7c3aed", bg: "#f5f3ff", icon: <FaCode size={16} /> },
              { label: "Functional Doc", value: functionalDocCount, tag: "DOC", color: "#2563eb", bg: "#eff6ff", icon: <FaFileAlt size={16} /> },
              { label: "Total Executable", value: totalProposed, tag: "TOTAL", color: "#10b981", bg: "#ecfdf5", icon: <FaLayerGroup size={16} /> },
            ].map((item, i) => (
              <div key={i} style={{ background: item.bg, border: `1px solid ${item.color}20`, borderRadius: 10, padding: "12px 14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <div style={{ color: item.color, opacity: 0.7 }}>{item.icon}</div>
                  <span style={{ fontSize: 9, fontWeight: 800, color: item.color, background: `${item.color}15`, padding: "2px 6px", borderRadius: 4 }}>{item.tag}</span>
                </div>
                <div style={{ fontSize: 26, fontWeight: 800, color: "#0f172a", lineHeight: 1 }}>{item.value}</div>
                <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginTop: 4 }}>{item.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Functional Test Type Breakdown */}
        <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 14, padding: "18px 20px", boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
          <h4 style={{ margin: "0 0 14px 0", fontSize: 14, fontWeight: 700, color: "#0f172a" }}>Functional Test Type Breakdown</h4>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {[
              { label: "API Functional", value: apiCount, tag: "API", color: "#2563eb", bg: "#eff6ff", icon: <FaCode size={16} /> },
              { label: "UI Functional", value: uiCount, tag: "UI", color: "#7c3aed", bg: "#f5f3ff", icon: <FaFileAlt size={16} /> },
              { label: "Total Functional", value: totalProposed, tag: "TOTAL", color: "#10b981", bg: "#ecfdf5", icon: <FaLayerGroup size={16} /> },
            ].map((item, i) => (
              <div key={i} style={{ background: item.bg, border: `1px solid ${item.color}20`, borderRadius: 10, padding: "12px 14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <div style={{ color: item.color, opacity: 0.7 }}>{item.icon}</div>
                  <span style={{ fontSize: 9, fontWeight: 800, color: item.color, background: `${item.color}15`, padding: "2px 6px", borderRadius: 4 }}>{item.tag}</span>
                </div>
                <div style={{ fontSize: 26, fontWeight: 800, color: "#0f172a", lineHeight: 1 }}>{item.value}</div>
                <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginTop: 4 }}>{item.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── SECTION 3: TEST CASES TABLE ───────────────────────────────────── */}
      <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 14, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.03)", marginBottom: 16 }}>
        {/* Table Header Row */}
        <div style={{ padding: "16px 20px", borderBottom: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ background: "linear-gradient(135deg, #7c3aed, #2563eb)", color: "#fff", width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>
                <FaLayerGroup />
              </div>
              <div>
                <h4 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "#0f172a" }}>Test Cases ({totalProposed})</h4>
                <p style={{ margin: 0, fontSize: 12, color: "#64748b" }}>Manage and execute proposed test cases.</p>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            <div style={{ display: "flex", align: "center", gap: 10, fontSize: 12, fontWeight: 600, color: "#64748b" }}>
              <span style={{ color: "#059669", fontWeight: 700 }}>{validCount} Valid</span>
              <span>•</span>
              <span style={{ color: "#d97706", fontWeight: 700 }}>{duplicateCount} Duplicate</span>
              <span>•</span>
              <span style={{ color: "#dc2626", fontWeight: 700 }}>{invalidCount} Invalid</span>
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600, color: "#475569", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={proposals.length > 0 && selectedTestIds.size === proposals.length}
                onChange={handleToggleSelectAll}
                style={{ cursor: "pointer", width: 14, height: 14 }}
              />
              Select All
            </label>
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div style={{ padding: "12px 20px", borderBottom: "1px solid #f1f5f9", background: "#fafbfc", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {/* Search */}
          <div style={{ position: "relative", flex: 1, minWidth: 200 }}>
            <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#94a3b8", fontSize: 13 }}>🔍</span>
            <input
              type="text"
              placeholder="Search test cases, endpoint, method..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: "100%", padding: "7px 10px 7px 30px", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 12, color: "#0f172a", background: "#ffffff", outline: "none", boxSizing: "border-box" }}
            />
          </div>

          {/* Filters */}
          {[
            { label: "All Types", value: filterType, setter: setFilterType, opts: [["all", "All Types"], ["api", "API"], ["ui", "UI"]] },
            { label: "All Methods", value: filterMethod, setter: setFilterMethod, opts: [["all", "All Methods"], ["get", "GET"], ["post", "POST"], ["put", "PUT"], ["delete", "DELETE"]] },
            { label: "All Status", value: filterStatus, setter: setFilterStatus, opts: [["all", "All Status"], ["not_executed", "NOT_EXECUTED"], ["passed", "PASSED"], ["failed", "FAILED"], ["skipped", "SKIPPED"]] },
            { label: "All Sources", value: filterSource, setter: setFilterSource, opts: [["all", "All Sources"], ["llm", "LLM Generated"], ["doc", "Functional Doc"], ["existing", "Existing"]] },
          ].map((f, i) => (
            <select
              key={i}
              value={f.value}
              onChange={(e) => f.setter(e.target.value)}
              style={{ padding: "7px 10px", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 12, color: "#475569", background: "#ffffff", outline: "none", cursor: "pointer", minWidth: 110 }}
            >
              {f.opts.map(([val, lbl]) => <option key={val} value={val}>{lbl}</option>)}
            </select>
          ))}

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              style={{ padding: "7px 12px", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 12, color: "#2563eb", background: "#eff6ff", cursor: "pointer", fontWeight: 600, display: "flex", alignItems: "center", gap: 5, whiteSpace: "nowrap" }}
            >
              ↺ Clear Filters
            </button>
          )}
        </div>

        {/* Table */}
        <div style={{ maxHeight: 420, overflowY: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#f8fafc", color: "#475569", borderBottom: "1px solid #e2e8f0", position: "sticky", top: 0, zIndex: 2 }}>
                <th style={{ padding: "10px 12px", width: 36, textAlign: "center" }}>
                  <input type="checkbox" checked={proposals.length > 0 && selectedTestIds.size === proposals.length} onChange={handleToggleSelectAll} style={{ cursor: "pointer" }} title="Select / Deselect All Tests" />
                </th>
                <th style={{ padding: "10px 12px", width: 68, fontWeight: 700, fontSize: 11 }}>ID</th>
                <th style={{ padding: "10px 12px", fontWeight: 700, fontSize: 11 }}>Test Name</th>
                <th style={{ padding: "10px 12px", width: 120, fontWeight: 700, fontSize: 11 }}>Source</th>
                <th style={{ padding: "10px 12px", width: 50, fontWeight: 700, fontSize: 11 }}>Type</th>
                <th style={{ padding: "10px 12px", width: 65, fontWeight: 700, fontSize: 11 }}>Method</th>
                <th style={{ padding: "10px 12px", width: 160, fontWeight: 700, fontSize: 11 }}>Endpoint / Route</th>
                <th style={{ padding: "10px 12px", width: 100, fontWeight: 700, fontSize: 11 }}>Validation</th>
                <th style={{ padding: "10px 12px", width: 120, fontWeight: 700, fontSize: 11 }}>Execution Status</th>
                <th style={{ padding: "10px 12px", width: 70, fontWeight: 700, fontSize: 11 }}>Duration</th>
                <th style={{ padding: "10px 12px", width: 52, fontWeight: 700, fontSize: 11, textAlign: "center" }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={11} style={{ padding: "40px 12px", textAlign: "center", color: "#64748b" }}>
                    <FaSpinner className="animate-spin" size={18} style={{ marginBottom: 8 }} />
                    <div style={{ fontSize: 13 }}>Loading proposed test execution data...</div>
                  </td>
                </tr>
              ) : filteredProposals.length === 0 ? (
                <tr>
                  <td colSpan={11} style={{ padding: "36px 12px", textAlign: "center", color: "#94a3b8", fontSize: 13 }}>
                    {proposals.length === 0 ? "No proposed test cases found for this migration." : "No test cases match the current filters."}
                  </td>
                </tr>
              ) : (
                filteredProposals.map((t, idx) => {
                  const isDoc = t.generation_source === "BRD_DOCUMENT" || t.generation_source === "BRD_AND_AI" || t.generation_source === "FUNCTIONAL_DOC" || t.id.includes("BRD") || t.source === "BRD Document" || t.source === "BRD Business Requirement";
                  const isExisting = t.generation_source === "EXISTING" || t.generation_source === "EXISTING_TESTS" || t.id.includes("EXT") || t.source === "Existing Repository" || t.source === "Existing Repository Tests";
                  const sourceBadgeLabel = isExisting ? "Existing" : isDoc ? "Functional Doc" : "LLM Generated";
                  const sourceBadgeColor = isExisting ? "#059669" : isDoc ? "#7c3aed" : "#0284c7";
                  const sourceBadgeBg = isExisting ? "#ecfdf5" : isDoc ? "#faf5ff" : "#f0f9ff";
                  const sourceBadgeBorder = isExisting ? "#a7f3d0" : isDoc ? "#d8b4fe" : "#bae6fd";

                  const execStatus = t.execution_result?.status || t.baseline_execution_result?.status || t.status || "NOT_EXECUTED";
                  const method = t.api_spec?.method || (t.type === "API" ? "GET" : "--");
                  const endpoint = t.api_spec?.endpoint || t.ui_spec?.target_route || "--";

                  const valStatus = t.validation?.status || "VALID";
                  const valColor = valStatus === "VALID" || valStatus === "PARTIALLY_VALID" ? "#059669" : valStatus === "DUPLICATE" ? "#d97706" : valStatus === "HALLUCINATED" ? "#7c3aed" : "#dc2626";
                  const valBg = valStatus === "VALID" || valStatus === "PARTIALLY_VALID" ? "rgba(16,185,129,0.1)" : valStatus === "DUPLICATE" ? "rgba(217,119,6,0.1)" : valStatus === "HALLUCINATED" ? "rgba(124,58,237,0.1)" : "rgba(239,68,68,0.1)";
                  const valBorder = valStatus === "VALID" || valStatus === "PARTIALLY_VALID" ? "rgba(16,185,129,0.3)" : valStatus === "DUPLICATE" ? "rgba(217,119,6,0.3)" : valStatus === "HALLUCINATED" ? "rgba(124,58,237,0.3)" : "rgba(239,68,68,0.3)";

                  const renderStatusBadge = (s: string | null) => {
                    if (!s || s === "PROPOSED" || s === "APPROVED" || s === "READY" || s === "NOT_EXECUTED") {
                      return <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", background: "rgba(100,116,139,0.1)", padding: "2px 6px", borderRadius: 4, border: "1px solid rgba(100,116,139,0.2)" }}>NOT_EXECUTED</span>;
                    }
                    const isPassed = s === "PASSED";
                    const isFailed = s === "FAILED";
                    const isAppUnavailable = s === "APPLICATION_UNAVAILABLE";
                    const isSkipped = s === "SKIPPED";
                    const isRunningRow = s === "RUNNING";
                    const bg = isPassed ? "rgba(16,185,129,0.12)" : isFailed ? "rgba(239,68,68,0.12)" : isAppUnavailable ? "rgba(245,158,11,0.12)" : isRunningRow ? "rgba(2,132,199,0.12)" : "rgba(100,116,139,0.12)";
                    const color = isPassed ? "#059669" : isFailed ? "#dc2626" : isAppUnavailable ? "#d97706" : isRunningRow ? "#0284c7" : "#64748b";
                    const border = `1px solid ${isPassed ? "rgba(16,185,129,0.3)" : isFailed ? "rgba(239,68,68,0.3)" : isAppUnavailable ? "rgba(245,158,11,0.4)" : isRunningRow ? "rgba(2,132,199,0.3)" : "rgba(100,116,139,0.3)"}`;
                    return (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 3, padding: "2px 6px", borderRadius: 4, fontSize: 10, fontWeight: 800, background: bg, color, border }}>
                        {isRunningRow && <FaSpinner className="animate-spin" size={7} />}
                        {isPassed ? "✓ PASSED" : isFailed ? "✕ FAILED" : isAppUnavailable ? "⊘ UNAVAIL" : isSkipped ? "⚠ SKIPPED" : s}
                      </span>
                    );
                  };

                  const duration = t.execution_result?.duration || t.baseline_execution_result?.duration || "--";
                  const isChecked = selectedTestIds.has(t.id);

                  return (
                    <tr
                      key={`prop-test-${t.id}-${idx}`}
                      onClick={() => setSelectedTest(t)}
                      style={{ borderBottom: "1px solid #f1f5f9", color: "#0f172a", cursor: "pointer", background: isChecked ? "rgba(37,99,235,0.03)" : "transparent", transition: "background 0.1s ease" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = isChecked ? "rgba(37,99,235,0.06)" : "#f8fafc")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = isChecked ? "rgba(37,99,235,0.03)" : "transparent")}
                    >
                      <td style={{ padding: "9px 12px", textAlign: "center" }} onClick={(e) => e.stopPropagation()}>
                        <input type="checkbox" checked={isChecked} onChange={(e) => handleToggleTest(t.id, e as unknown as React.MouseEvent)} style={{ cursor: "pointer" }} />
                      </td>
                      <td style={{ padding: "9px 12px", fontFamily: "monospace", color: "#2563eb", fontWeight: 700, fontSize: 11 }}>{t.id}</td>
                      <td style={{ padding: "9px 12px", fontWeight: 600, fontSize: 12 }}>{formatProposedTestDisplayName(t)}</td>
                      <td style={{ padding: "9px 12px" }}>
                        <span style={{ fontSize: 10, fontWeight: 800, color: sourceBadgeColor, background: sourceBadgeBg, border: `1px solid ${sourceBadgeBorder}`, padding: "2px 7px", borderRadius: 5 }}>{sourceBadgeLabel}</span>
                      </td>
                      <td style={{ padding: "9px 12px", fontSize: 11, color: "#64748b", fontWeight: 600 }}>{t.type}</td>
                      <td style={{ padding: "9px 12px" }}>
                        {method !== "--" ? (
                          <span style={{ fontSize: 9, fontWeight: 800, padding: "2px 6px", borderRadius: 4, background: method === "GET" ? "#f0fdf4" : method === "POST" ? "#eff6ff" : method === "DELETE" ? "#fef2f2" : method === "PUT" ? "#fffbeb" : "#f8fafc", color: method === "GET" ? "#15803d" : method === "POST" ? "#1d4ed8" : method === "DELETE" ? "#b91c1c" : method === "PUT" ? "#b45309" : "#475569", border: "1px solid rgba(0,0,0,0.08)", fontFamily: "monospace" }}>
                            {method}
                          </span>
                        ) : <span style={{ color: "#94a3b8", fontSize: 11 }}>--</span>}
                      </td>
                      <td style={{ padding: "9px 12px", fontFamily: "monospace", fontSize: 11, color: "#334155", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={endpoint}>{endpoint}</td>
                      <td style={{ padding: "9px 12px" }}>
                        <span style={{ fontSize: 10, fontWeight: 800, color: valColor, background: valBg, border: `1px solid ${valBorder}`, padding: "2px 7px", borderRadius: 5 }}>{valStatus}</span>
                      </td>
                      <td style={{ padding: "9px 12px" }}>{renderStatusBadge(execStatus)}</td>
                      <td style={{ padding: "9px 12px", color: "#64748b", fontSize: 11, fontFamily: "monospace" }}>{duration}</td>
                      <td style={{ padding: "9px 12px", textAlign: "center" }}>
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); setSelectedTest(t); }}
                          style={{ background: "#eff6ff", border: "1px solid #bfdbfe", color: "#2563eb", cursor: "pointer", fontSize: 11, borderRadius: 6, padding: "4px 7px", display: "inline-flex", alignItems: "center" }}
                          title="View Test Details"
                        >
                          <FaExternalLinkAlt size={10} />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Table Footer */}
        <div style={{ padding: "10px 20px", borderTop: "1px solid #f1f5f9", background: "#fafbfc", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 12, color: "#64748b" }}>
            Showing {filteredProposals.length} of {proposals.length} total files
          </span>
          <button
            onClick={handleRunSelected}
            disabled={isRunning || selectedTestIds.size === 0}
            style={{ background: selectedTestIds.size > 0 && !isRunning ? "#2563eb" : "#e2e8f0", color: selectedTestIds.size > 0 && !isRunning ? "#ffffff" : "#94a3b8", border: "none", padding: "7px 16px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: selectedTestIds.size > 0 && !isRunning ? "pointer" : "default", display: "flex", alignItems: "center", gap: 7 }}
          >
            {isRunning ? <FaSpinner className="animate-spin" size={10} /> : <FaPlay size={10} />}
            Run Selected ({selectedTestIds.size})
          </button>
        </div>
      </div>

      {/* ── SECTION 4: PLAYWRIGHT LOGS ────────────────────────────────────── */}
      {logs.length > 0 && (
        <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 14, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.03)", marginBottom: 16 }}>
          {/* Log Header */}
          <div style={{ padding: "14px 20px", borderBottom: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ background: "#0f172a", color: "#10b981", width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>
                <FaTerminal />
              </div>
              <div>
                <h4 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: "#0f172a" }}>Playwright Execution Logs ({logs.length} entries)</h4>
                <p style={{ margin: 0, fontSize: 11, color: "#64748b" }}>Real-time execution logs from Playwright test suite.</p>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button
                type="button"
                onClick={handleCopyLogs}
                disabled={!logs || logs.length === 0}
                style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 7, border: "1px solid #cbd5e1", background: isLogsCopied ? "#f0fdf4" : "#f8fafc", color: isLogsCopied ? "#16a34a" : "#475569", fontSize: 12, fontWeight: 700, cursor: logs.length === 0 ? "not-allowed" : "pointer", transition: "all 0.15s ease" }}
                title="Copy Playwright execution logs to clipboard"
              >
                {isLogsCopied ? <FaCheck size={11} /> : <FaCopy size={11} />}
                {isLogsCopied ? "Copied!" : "Copy Logs"}
              </button>
              <button
                type="button"
                onClick={() => setShowLogs((v) => !v)}
                style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 7, border: "1px solid #cbd5e1", background: "#f8fafc", color: "#475569", fontSize: 12, fontWeight: 700, cursor: "pointer" }}
              >
                {showLogs ? "Hide Console ▲" : "Show Console ▼"}
              </button>
            </div>
          </div>

          {/* Log Console */}
          {showLogs && (
            <div
              ref={logBoxRef}
              style={{ background: "#0f172a", padding: "16px 20px", maxHeight: 280, overflowY: "auto", fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace", fontSize: 12, lineHeight: 1.7, color: "#e2e8f0" }}
            >
              {logs.map((log, i) => {
                const lvl = (log.level || "").toUpperCase();
                const levelColor = lvl === "ERROR" ? "#f87171" : lvl === "WARN" ? "#fbbf24" : "#34d399";
                const levelBg = lvl === "ERROR" ? "rgba(248,113,113,0.12)" : lvl === "WARN" ? "rgba(251,191,36,0.12)" : "rgba(52,211,153,0.10)";
                return (
                  <div key={i} style={{ display: "flex", gap: 12, marginBottom: 2, padding: "1px 0" }}>
                    <span style={{ color: "#475569", flexShrink: 0, fontSize: 11 }}>[{log.ts || "00:00:00"}]</span>
                    <span style={{ color: levelColor, fontWeight: 800, flexShrink: 0, fontSize: 10, background: levelBg, padding: "1px 5px", borderRadius: 3, alignSelf: "flex-start", marginTop: 2 }}>{lvl || "INFO"}</span>
                    <span style={{ color: "#cbd5e1", wordBreak: "break-all" }}>{log.msg}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── MODAL ─────────────────────────────────────────────────────────── */}
      {selectedTest && (
        <div
          style={{ position: "fixed", inset: 0, zIndex: 9999, background: "rgba(15, 23, 42, 0.6)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}
          onClick={() => setSelectedTest(null)}
        >
          <div
            style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 16, maxWidth: 780, width: "100%", maxHeight: "88vh", display: "flex", flexDirection: "column", boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)", color: "#0f172a", overflow: "hidden" }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{ padding: "16px 20px", borderBottom: "1px solid #e2e8f0", background: "#f8fafc", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ fontFamily: "monospace", fontSize: 11, fontWeight: 900, background: "#0284c7", color: "#ffffff", padding: "2px 6px", borderRadius: 4 }}>{selectedTest.id}</span>
                  <span style={{ fontSize: 10, fontWeight: 800, background: "#e2e8f0", padding: "2px 8px", borderRadius: 4, color: "#475569" }}>{selectedTest.type}</span>
                  <span style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px", borderRadius: 4, background: selectedTest.status === "PASSED" ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)", color: selectedTest.status === "PASSED" ? "#059669" : "#dc2626" }}>
                    Migrated: {selectedTest.status || "PROPOSED"}
                  </span>
                  {selectedTest.baseline_execution_result && (
                    <span style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px", borderRadius: 4, background: selectedTest.baseline_execution_result.status === "PASSED" ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)", color: selectedTest.baseline_execution_result.status === "PASSED" ? "#059669" : "#dc2626" }}>
                      Baseline: {selectedTest.baseline_execution_result.status}
                    </span>
                  )}
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>{formatProposedTestDisplayName(selectedTest)}</h3>
              </div>
              <button type="button" onClick={() => setSelectedTest(null)} style={{ background: "#e2e8f0", border: "none", color: "#475569", borderRadius: "50%", width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
                <FaTimes size={13} />
              </button>
            </div>

            {/* Modal Scrollable Content */}
            <div style={{ padding: "20px", overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase" }}>Description</div>
                <p style={{ fontSize: 13, color: "#334155", margin: "4px 0 0 0", lineHeight: 1.5 }}>{selectedTest.description || selectedTest.reason}</p>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 800, color: "#475569", textTransform: "uppercase", marginBottom: 6 }}>Pre-Migration Baseline (Source)</div>
                  <div style={{ fontSize: 12, color: "#334155", display: "flex", flexDirection: "column", gap: 4 }}>
                    <div><span style={{ fontWeight: 600 }}>Status: </span><span style={{ fontWeight: 800, color: selectedTest.baseline_execution_result?.status === "PASSED" ? "#059669" : selectedTest.baseline_execution_result?.status === "FAILED" ? "#dc2626" : "#64748b" }}>{selectedTest.baseline_execution_result?.status || "Not Executed / Skipped"}</span></div>
                    <div><span style={{ fontWeight: 600 }}>Duration: </span><span>{selectedTest.baseline_execution_result?.duration || "--"}</span></div>
                    {selectedTest.baseline_execution_result?.error && (
                      <div style={{ marginTop: 6, background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", borderRadius: 6, padding: 8 }}>
                        <div style={{ color: "#dc2626", fontWeight: 700, fontSize: 11 }}>Baseline Error:</div>
                        <pre style={{ margin: "4px 0 0 0", fontSize: 10, color: "#b91c1c", fontFamily: "monospace", whiteSpace: "pre-wrap" }}>{selectedTest.baseline_execution_result.error}</pre>
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 800, color: "#475569", textTransform: "uppercase", marginBottom: 6 }}>Post-Migration (Target)</div>
                  <div style={{ fontSize: 12, color: "#334155", display: "flex", flexDirection: "column", gap: 4 }}>
                    <div><span style={{ fontWeight: 600 }}>Status: </span><span style={{ fontWeight: 800, color: selectedTest.execution_result?.status === "PASSED" ? "#059669" : selectedTest.execution_result?.status === "FAILED" ? "#dc2626" : "#64748b" }}>{selectedTest.execution_result?.status || selectedTest.status || "Pending / Not Run"}</span></div>
                    <div><span style={{ fontWeight: 600 }}>Duration: </span><span>{selectedTest.execution_result?.duration || "--"}</span></div>
                    {selectedTest.execution_result?.error && (
                      <div style={{ marginTop: 6, background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", borderRadius: 6, padding: 8 }}>
                        <div style={{ color: "#dc2626", fontWeight: 700, fontSize: 11 }}>Migrated Error:</div>
                        <pre style={{ margin: "4px 0 0 0", fontSize: 10, color: "#b91c1c", fontFamily: "monospace", whiteSpace: "pre-wrap" }}>{selectedTest.execution_result.error}</pre>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {selectedTest.steps && selectedTest.steps.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", marginBottom: 6 }}>Playwright Test Steps</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {selectedTest.steps.map((s, idx) => (
                      <div key={`step-${idx}`} style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, padding: "8px 12px", fontSize: 12, display: "flex", alignItems: "center", gap: 8, color: "#0f172a" }}>
                        <span style={{ fontFamily: "monospace", fontSize: 11, color: "#0284c7", fontWeight: 700 }}>#{idx + 1}</span>
                        <span>{s}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedTest.execution_result?.stdout && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", marginBottom: 4 }}>Execution Log</div>
                  <pre style={{ background: "#030712", border: "1px solid #1f2937", borderRadius: 8, padding: 12, fontSize: 11, color: "#94a3b8", fontFamily: "monospace", whiteSpace: "pre-wrap", maxHeight: 160, overflowY: "auto", margin: 0 }}>
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
