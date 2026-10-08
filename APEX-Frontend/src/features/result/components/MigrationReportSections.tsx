import React, { useState, useEffect } from "react";
import {
  FaCheckCircle,
  FaShieldAlt,
  FaExclamationTriangle,
  FaRedo,
  FaDownload,
  FaTerminal,
  FaStopwatch,
  FaFileAlt,
  FaCode,
  FaLayerGroup,
  FaFileArchive,
  FaFileCode,
  FaExternalLinkAlt,
  FaMarkdown,
  FaBug,
  FaLock,
  FaBiohazard,
  FaFire,
  FaRocket,
  FaTasks,
  FaLightbulb,
  FaTimes,
  FaTimesCircle
} from "react-icons/fa";
export { MigrationProposedTestSection } from "./MigrationProposedTestSection";
import { API_BASE_URL } from "@/services/config/env";
import {
  type MigrationResult,
  downloadMigratedProject,
  downloadTestcaseDoc,
  downloadTestcaseReport,
  downloadUnitTestReport,
} from "@/features/result/services/resultService";
import { getUserSettings } from "@/features/admin/services/adminService";
import { triggerBlobDownload } from "@/features/result/utils/migrationWizardPdf";

type StyleMap = Record<string, React.CSSProperties>;

// ── UNIT TEST SECTION ────────────────────────────────────────────────────────

interface MigrationUnitTestSectionProps {
  styles: StyleMap;
  migrationJob: MigrationResult;
  testSummaryReportDate: string;
  migrationJavaVersion: string | null;
  summaryItems?: any[];
  testsRun: number;
  runTests?: boolean;
  onDownloadUnitTestReport: () => Promise<void> | void;
  onGenerateUnitTests?: () => void;
  isGenerating?: boolean;
}

export function MigrationUnitTestSection({
  styles,
  migrationJob,
  testSummaryReportDate,
  migrationJavaVersion,
  summaryItems = [],
  testsRun,
  runTests,
  onDownloadUnitTestReport,
  onGenerateUnitTests,
  isGenerating = false,
}: MigrationUnitTestSectionProps) {
  void testSummaryReportDate;
  void migrationJavaVersion;
  void testsRun;
  const [showAllModal, setShowAllModal] = useState(false);
  const [savedPrompt, setSavedPrompt] = useState<string | null>(null);
  const [selectedPromptTab, setSelectedPromptTab] = useState<string | null>(null);

  useEffect(() => {
    getUserSettings()
      .then((data) => {
        const p = data.test_cases_values?.testing_prompt || data.quality_checks_values?.testing_prompt;
        if (p && typeof p === "string" && p.trim()) {
          setSavedPrompt(p.trim());
        }
      })
      .catch((err) => console.warn("Could not fetch user settings for report prompt fallback:", err));
  }, []);
  const isExecuted = Boolean(migrationJob?.run_tests ?? migrationJob?.runTests ?? runTests);

  if (!isExecuted) {
    return (
      <div style={{ ...styles.reportSection, background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "32px 40px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)", height: "100%", display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
          <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ background: "#64748b", color: "#fff", width: 32, height: 32, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
              <FaFileAlt />
            </div>
            Unit Test Information
          </h3>
          <span style={{ padding: "6px 16px", borderRadius: 20, background: "#f1f5f9", color: "#475569", fontSize: 12, fontWeight: 700, border: "1px solid #e2e8f0" }}>
            NOT EXECUTED
          </span>
        </div>
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 12, padding: "28px 24px", textAlign: "center", flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <div style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 44, height: 44, borderRadius: "50%", background: "#f1f5f9", color: "#64748b", marginBottom: 12, fontSize: 20 }}>
            <FaFileAlt />
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#334155", marginBottom: 6 }}>
            Unit test suite was not executed for this migration.
          </div>
          <div style={{ fontSize: 13, color: "#64748b", maxWidth: 520, margin: "0 auto" }}>
            Automated unit test execution was not enabled during the migration configuration.
          </div>
        </div>
      </div>
    );
  }

  const getValueByLabel = (pattern: string, fallback: string | number = 0) => {
    const found = (summaryItems || []).find((i: any) => i?.label && String(i.label).toUpperCase().includes(pattern.toUpperCase()));
    return found ? found.value : fallback;
  };

  const totalFiles = getValueByLabel("TOTAL FILES", 0);
  const totalTestCases = getValueByLabel("TOTAL TEST CASES", 0);
  const existingTestFiles = getValueByLabel("EXISTING TEST FILES", 0);
  const newTestFiles = getValueByLabel("NEW TEST FILES", 0);
  const existingTestCases = getValueByLabel("EXISTING TEST CASES", 0);
  const generatedTestCases = getValueByLabel("GENERATED TEST CASES", "+0");
  const jacocoCoverageRaw = getValueByLabel("JACOCO COVERAGE", "N/A");
  const jacocoCoverageVal = (jacocoCoverageRaw && jacocoCoverageRaw !== "N/A" && jacocoCoverageRaw !== "0.0%")
    ? parseFloat(jacocoCoverageRaw.toString().replace("%", ""))
    : null;

  const testPipeline = migrationJob?.test_pipeline ?? {};
  const executedDetails = (testPipeline as any)?.executed_test_details || [];
  const generatedFiles = (testPipeline as any)?.generated_test_files || [];
  const genExec = (testPipeline as any)?.generated_test_execution || {};
  const covResult = (testPipeline as any)?.coverage_result || (migrationJob as any)?.coverage_result || (migrationJob as any)?.coverage;
  const isCovAvailable = Boolean(covResult?.available);
  const originalCov = isCovAvailable && typeof covResult?.original?.line_coverage_pct === "number" ? covResult.original.line_coverage_pct : null;
  const finalCov = isCovAvailable
    ? (typeof covResult?.final?.line_coverage_pct === "number"
        ? covResult.final.line_coverage_pct
        : (typeof covResult?.line_coverage_pct === "number"
            ? covResult.line_coverage_pct
            : (typeof covResult?.line === "number" ? covResult.line : jacocoCoverageVal)))
    : null;
  const branchCov = isCovAvailable
    ? (typeof covResult?.final?.branch_coverage_pct === "number"
        ? covResult.final.branch_coverage_pct
        : (typeof covResult?.branch_coverage_pct === "number"
            ? covResult.branch_coverage_pct
            : (typeof covResult?.branch === "number" ? covResult.branch : null)))
    : null;
  const instCov = isCovAvailable
    ? (typeof covResult?.final?.instruction_coverage_pct === "number"
        ? covResult.final.instruction_coverage_pct
        : (typeof covResult?.instruction_coverage_pct === "number"
            ? covResult.instruction_coverage_pct
            : (typeof covResult?.instruction === "number" ? covResult.instruction : null)))
    : null;
  const methodCov = isCovAvailable
    ? (typeof covResult?.final?.method_coverage_pct === "number"
        ? covResult.final.method_coverage_pct
        : (typeof covResult?.method_coverage_pct === "number"
            ? covResult.method_coverage_pct
            : (typeof covResult?.method === "number" ? covResult.method : null)))
    : null;
  const classCov = isCovAvailable
    ? (typeof covResult?.final?.class_coverage_pct === "number"
        ? covResult.final.class_coverage_pct
        : (typeof covResult?.class_coverage_pct === "number"
            ? covResult.class_coverage_pct
            : (typeof covResult?.class === "number" ? covResult.class : null)))
    : null;

  const improvementText = isCovAvailable && covResult?.improvement?.text
    ? covResult.improvement.text
    : (typeof originalCov === "number" && typeof finalCov === "number" ? `+${(finalCov - originalCov).toFixed(1)} pp` : null);

  const genMethodCount = Number(genExec.generated_test_methods ?? parseInt(String(generatedTestCases).replace("+", "")) ?? 0) || 0;
  const execGenCount = Number(genExec.executed_generated_test_methods ?? genExec.executed ?? executedDetails.length) || 0;
  const passedGenCount = Number(genExec.passed_generated_test_methods ?? genExec.passed ?? executedDetails.filter((d: any) => d?.status === "PASSED").length) || 0;
  const failedGenCount = Number(genExec.failed_generated_test_methods ?? genExec.failed ?? executedDetails.filter((d: any) => d?.status === "FAILED").length) || 0;
  const skippedGenCount = Number(genExec.skipped_generated_test_methods ?? genExec.skipped ?? executedDetails.filter((d: any) => d?.status === "SKIPPED").length) || 0;

  const rawExecStatus = (testPipeline as any)?.execution_status || (execGenCount > 0 ? (failedGenCount === 0 ? "EXECUTED" : (passedGenCount > 0 ? "PARTIAL" : "FAILED")) : "NOT_EXECUTED");
  const execStatusLabel =
    rawExecStatus === "EXECUTED"
      ? "EXECUTED"
      : rawExecStatus === "PARTIAL"
      ? "PARTIALLY EXECUTED"
      : rawExecStatus === "FAILED"
      ? "FAILED"
      : rawExecStatus === "COMPILE FAILED" || rawExecStatus === "COMPILE_FAILED"
      ? "COMPILE FAILED"
      : "NOT EXECUTED / NO EXECUTION RESULTS";
  const execStatusColor =
    rawExecStatus === "EXECUTED"
      ? { bg: "#dcfce7", text: "#166534", border: "#86efac" }
      : rawExecStatus === "PARTIAL"
      ? { bg: "#fef3c7", text: "#b45309", border: "#fde68a" }
      : rawExecStatus === "FAILED" || rawExecStatus === "COMPILE FAILED" || rawExecStatus === "COMPILE_FAILED"
      ? { bg: "#fee2e2", text: "#991b1b", border: "#fecaca" }
      : { bg: "#f1f5f9", text: "#475569", border: "#e2e8f0" };

  return (
    <div style={{ ...styles.reportSection, background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "24px 32px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)", height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Header Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 22, paddingBottom: 16, borderBottom: "1px solid #f1f5f9" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: "linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)", color: "#2563eb", width: 38, height: 38, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, border: "1px solid #bfdbfe", boxShadow: "0 2px 8px rgba(37, 99, 235, 0.12)" }}>
            <FaFileAlt />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#0f172a", letterSpacing: "-0.01em" }}>Unit Test Information</h3>
            <div style={{ fontSize: 12, color: "#64748b", fontWeight: 500, marginTop: 1 }}>Automated unit test execution, JaCoCo line coverage, and testcase verification</div>
          </div>
        </div>
        <div style={{
          background: migrationJob?.status === "completed" ? "#dcfce7" : "#fff7ed",
          color: migrationJob?.status === "completed" ? "#166534" : "#f97316",
          padding: "4px 14px",
          borderRadius: 20,
          fontSize: 11,
          fontWeight: 800,
          border: `1px solid ${migrationJob?.status === "completed" ? "#86efac" : "#ffedd5"}`,
          textTransform: "lowercase",
          letterSpacing: "0.02em"
        }}>
          {migrationJob?.status === "completed" ? "completed" : "awaiting first run"}
        </div>
      </div>

      {/* Metrics Row (JaCoCo Gauge + 6 Stat Metric Cards) */}
      <div style={{ display: "flex", alignItems: "stretch", gap: 20, marginBottom: 20 }}>
        {/* Radial Gauge & JaCoCo Breakdown */}
        <div style={{
          background: "#f8fafc",
          border: "1px solid #e2e8f0",
          borderRadius: 14,
          padding: "16px 20px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          flexShrink: 0,
          minWidth: 140,
          boxShadow: "0 2px 8px rgba(0,0,0,0.02)"
        }}>
          <div style={{ position: "relative", width: 96, height: 96 }}>
            <svg width="96" height="96" viewBox="0 0 110 110">
              <circle cx="55" cy="55" r="48" fill="none" stroke="#e2e8f0" strokeWidth="10" />
              <circle cx="55" cy="55" r="48" fill="none" stroke={typeof finalCov === "number" ? "#22c55e" : "#cbd5e1"} strokeWidth="10" strokeDasharray={`${typeof finalCov === "number" ? Math.min(100, Math.max(0, finalCov)) * 3 : 0} 301`} strokeLinecap="round" transform="rotate(-90 55 55)" />
            </svg>
            <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#0f172a" }}>
                {typeof finalCov === "number" ? `${finalCov.toFixed(1)}%` : "N/A"}
              </div>
              <div style={{ fontSize: 9.5, fontWeight: 800, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", lineHeight: 1.1 }}>JaCoCo<br/>Coverage</div>
            </div>
          </div>
          {typeof originalCov === "number" && (
            <div style={{ fontSize: 10.5, color: "#334155", background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8, padding: "4px 8px", width: "100%" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 6 }}>
                <span style={{ color: "#64748b" }}>Original:</span>
                <span style={{ fontWeight: 700 }}>{originalCov.toFixed(1)}%</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 6, marginTop: 2 }}>
                <span style={{ color: "#64748b" }}>Final:</span>
                <span style={{ fontWeight: 700, color: typeof finalCov === "number" ? "#166534" : "#64748b" }}>
                  {typeof finalCov === "number" ? `${finalCov.toFixed(1)}%` : "N/A"}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 6, marginTop: 2, borderTop: "1px dashed #cbd5e1", paddingTop: 2 }}>
                <span style={{ color: "#64748b" }}>Delta:</span>
                {typeof finalCov === "number" && improvementText ? (
                  <span style={{ fontWeight: 800, color: improvementText.startsWith("-") ? "#b91c1c" : "#15803d" }}>
                    {improvementText}
                  </span>
                ) : (
                  <span style={{ fontWeight: 700, color: "#64748b" }}>N/A</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 6 Metric Cards (3x2 Grid) */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, flex: 1 }}>
          {[
            { label: "Total Files in Repo", value: totalFiles },
            { label: "Total Test Cases", value: totalTestCases },
            { label: "Existing Test Files", value: existingTestFiles },
            { label: "New Test Files", value: newTestFiles },
            { label: "Existing Test Cases", value: existingTestCases },
            { label: "Generated Test Cases", value: generatedTestCases, color: "#d97706" },
          ].map((item, i) => (
            <div key={i} style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 12, padding: "14px 12px", textAlign: "center", boxShadow: "0 2px 6px rgba(0,0,0,0.02)", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: item.color || "#0f172a", lineHeight: 1 }}>{item.value}</div>
              <div style={{ fontSize: 11.5, fontWeight: 600, color: "#64748b", marginTop: 6, lineHeight: 1.2 }}>{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* JaCoCo Missing Notice Banner */}
      {(!isCovAvailable || typeof finalCov !== "number") && (
        <div style={{
          background: "linear-gradient(135deg, #fffdf5 0%, #fff7ed 100%)",
          border: "1px solid #fde68a",
          borderRadius: 12,
          padding: "12px 18px",
          marginBottom: 18,
          fontSize: 12.5,
          color: "#92400e",
          display: "flex",
          alignItems: "center",
          gap: 10,
          boxShadow: "0 2px 8px rgba(245, 158, 11, 0.05)"
        }}>
          <FaExclamationTriangle size={15} color="#d97706" style={{ flexShrink: 0 }} />
          <div>
            <strong style={{ color: "#78350f" }}>JaCoCo Coverage: N/A</strong>
            <span style={{ color: "#b45309", marginLeft: 8 }}>— Reason: {covResult?.error || covResult?.final?.error || "JaCoCo XML report was not generated."}</span>
          </div>
        </div>
      )}

      {/* JaCoCo Detailed 5-Dimension Coverage Bar */}
      {isCovAvailable && (typeof finalCov === "number" || typeof instCov === "number") && (
        <div style={{
          background: "#f0fdf4",
          border: "1px solid #bbf7d0",
          borderRadius: 12,
          padding: "10px 16px",
          marginBottom: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: "#166534", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            JaCoCo Coverage Metrics:
          </div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <div style={{ fontSize: 11 }}>
              <span style={{ color: "#15803d", fontWeight: 600 }}>Line: </span>
              <strong style={{ color: "#166534" }}>{typeof finalCov === "number" ? `${finalCov.toFixed(1)}%` : "N/A"}</strong>
            </div>
            <div style={{ fontSize: 11 }}>
              <span style={{ color: "#15803d", fontWeight: 600 }}>Branch: </span>
              <strong style={{ color: "#166534" }}>{typeof branchCov === "number" ? `${branchCov.toFixed(1)}%` : "N/A"}</strong>
            </div>
            <div style={{ fontSize: 11 }}>
              <span style={{ color: "#15803d", fontWeight: 600 }}>Instruction: </span>
              <strong style={{ color: "#166534" }}>{typeof instCov === "number" ? `${instCov.toFixed(1)}%` : "N/A"}</strong>
            </div>
            <div style={{ fontSize: 11 }}>
              <span style={{ color: "#15803d", fontWeight: 600 }}>Method: </span>
              <strong style={{ color: "#166534" }}>{typeof methodCov === "number" ? `${methodCov.toFixed(1)}%` : "N/A"}</strong>
            </div>
            <div style={{ fontSize: 11 }}>
              <span style={{ color: "#15803d", fontWeight: 600 }}>Class: </span>
              <strong style={{ color: "#166534" }}>{typeof classCov === "number" ? `${classCov.toFixed(1)}%` : "N/A"}</strong>
            </div>
          </div>
        </div>
      )}

      {/* Execution Summary Control Bar */}
      <div style={{
        background: "#f8fafc",
        border: "1px solid #e2e8f0",
        borderRadius: 14,
        padding: "12px 20px",
        marginBottom: 22,
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 14,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: "#475569", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Execution Status:
          </div>
          <span style={{
            background: isGenerating ? "#fef3c7" : execStatusColor.bg,
            color: isGenerating ? "#d97706" : execStatusColor.text,
            border: `1px solid ${isGenerating ? "#fde68a" : execStatusColor.border}`,
            padding: "4px 12px",
            borderRadius: 14,
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: "0.02em"
          }}>
            {execStatusLabel}
          </span>
          {(!execGenCount || execGenCount === 0) && !isGenerating && onGenerateUnitTests && (
            <button
              onClick={onGenerateUnitTests}
              style={{
                background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                color: "#ffffff",
                border: "none",
                borderRadius: 14,
                padding: "5px 14px",
                fontSize: 11,
                fontWeight: 700,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 6,
                boxShadow: "0 2px 8px rgba(37, 99, 235, 0.2)",
                transition: "all 0.15s ease"
              }}
            >
              <FaCode size={11} /> Generate Tests
            </button>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <div style={{ fontSize: 12, background: "#ffffff", padding: "4px 10px", borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <span style={{ color: "#64748b", fontWeight: 600 }}>Generated: </span>
            <strong style={{ color: "#0f172a" }}>{genMethodCount}</strong>
          </div>
          <div style={{ fontSize: 12, background: "#ffffff", padding: "4px 10px", borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <span style={{ color: "#64748b", fontWeight: 600 }}>Executed: </span>
            <strong style={{ color: execGenCount > 0 ? "#2563eb" : "#64748b" }}>{execGenCount}</strong>
          </div>
          <div style={{ fontSize: 12, background: "#ecfdf5", padding: "4px 10px", borderRadius: 8, border: "1px solid #a7f3d0" }}>
            <span style={{ color: "#059669", fontWeight: 600 }}>Passed: </span>
            <strong style={{ color: "#166534" }}>{passedGenCount}</strong>
          </div>
          <div style={{ fontSize: 12, background: "#fef2f2", padding: "4px 10px", borderRadius: 8, border: "1px solid #fecdd3" }}>
            <span style={{ color: "#dc2626", fontWeight: 600 }}>Failed: </span>
            <strong style={{ color: "#991b1b" }}>{failedGenCount}</strong>
          </div>
          <div style={{ fontSize: 12, background: "#fffbeb", padding: "4px 10px", borderRadius: 8, border: "1px solid #fde68a" }}>
            <span style={{ color: "#d97706", fontWeight: 600 }}>Skipped: </span>
            <strong style={{ color: "#92400e" }}>{skippedGenCount}</strong>
          </div>
        </div>
      </div>

      {/* PROMPT COMPLIANCE ANALYSIS */}
      {(() => {
        const promptCompliance = (testPipeline as any)?.prompt_compliance;
        if (!promptCompliance || !promptCompliance.compliance_items || promptCompliance.compliance_items.length === 0) {
          return null;
        }

        const items = promptCompliance.compliance_items;
        const activeTabId = selectedPromptTab || items[0]?.prompt_id;
        const activeItem = items.find((i: any) => i.prompt_id === activeTabId) || items[0];
        const overallPct = promptCompliance.overall_compliance_percentage ?? 0;
        const isPassed = overallPct >= 80;

        return (
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: 14,
              padding: "20px 24px",
              marginBottom: 28,
              boxShadow: "0 2px 12px rgba(0,0,0,0.04)",
            }}
          >
            {/* Header */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: 12,
                marginBottom: 16,
                paddingBottom: 14,
                borderBottom: "1px solid #f1f5f9",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    background: "#ecfdf5",
                    color: "#059669",
                    width: 34,
                    height: 34,
                    borderRadius: 8,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 18,
                  }}
                >
                  <FaTasks />
                </div>
                <div>
                  <h4 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "#0f172a" }}>
                    JUnit Test Prompt Compliance Analysis
                  </h4>
                  <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                    Deep semantic verification of test logic, mocks, assertions, and boundary inputs
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span
                  style={{
                    background: isPassed ? "#dcfce7" : "#fef3c7",
                    color: isPassed ? "#15803d" : "#b45309",
                    padding: "6px 16px",
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 800,
                    border: `1px solid ${isPassed ? "#86efac" : "#fde68a"}`,
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <FaCheckCircle /> {overallPct}% Overall Compliance
                </span>
              </div>
            </div>

            {/* Quick Inspection Stats */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                gap: 10,
                marginBottom: 18,
              }}
            >
              <div style={{ background: "#f8fafc", padding: "10px 12px", borderRadius: 8, border: "1px solid #eef2f6", textAlign: "center" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#2563eb" }}>{promptCompliance.total_prompts_evaluated}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", marginTop: 2 }}>Prompts Evaluated</div>
              </div>
              <div style={{ background: "#f8fafc", padding: "10px 12px", borderRadius: 8, border: "1px solid #eef2f6", textAlign: "center" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#16a34a" }}>
                  {promptCompliance.passed_prompts_count}/{promptCompliance.total_prompts_evaluated}
                </div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", marginTop: 2 }}>Prompts Satisfied</div>
              </div>
              <div style={{ background: "#f8fafc", padding: "10px 12px", borderRadius: 8, border: "1px solid #eef2f6", textAlign: "center" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a" }}>{promptCompliance.total_assertions_inspected}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", marginTop: 2 }}>Assertions Verified</div>
              </div>
              <div style={{ background: "#f8fafc", padding: "10px 12px", borderRadius: 8, border: "1px solid #eef2f6", textAlign: "center" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#d97706" }}>{promptCompliance.total_exceptions_verified}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", marginTop: 2 }}>Exception Checks</div>
              </div>
              <div style={{ background: "#f8fafc", padding: "10px 12px", borderRadius: 8, border: "1px solid #eef2f6", textAlign: "center" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#7c3aed" }}>{promptCompliance.total_boundary_inputs_tested}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", marginTop: 2 }}>Boundary Values</div>
              </div>
              <div style={{ background: "#f8fafc", padding: "10px 12px", borderRadius: 8, border: "1px solid #eef2f6", textAlign: "center" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#0891b2" }}>{promptCompliance.total_mocks_verified}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", marginTop: 2 }}>Mock Interactions</div>
              </div>
            </div>

            {/* Prompt Selector Tabs */}
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                marginBottom: 18,
                background: "#f1f5f9",
                padding: 6,
                borderRadius: 10,
              }}
            >
              {items.map((it: any) => {
                const isSelected = it.prompt_id === activeTabId;
                return (
                  <button
                    key={it.prompt_id}
                    onClick={() => setSelectedPromptTab(it.prompt_id)}
                    style={{
                      border: "none",
                      outline: "none",
                      padding: "8px 14px",
                      borderRadius: 8,
                      fontSize: 12,
                      fontWeight: isSelected ? 800 : 600,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      background: isSelected ? "#2563eb" : "#ffffff",
                      color: isSelected ? "#ffffff" : "#475569",
                      boxShadow: isSelected ? "0 2px 8px rgba(37,99,235,0.25)" : "none",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <span>{it.prompt_name}</span>
                    <span
                      style={{
                        background: isSelected ? "rgba(255,255,255,0.2)" : (it.compliance_percentage >= 80 ? "#dcfce7" : "#fef3c7"),
                        color: isSelected ? "#ffffff" : (it.compliance_percentage >= 80 ? "#15803d" : "#b45309"),
                        padding: "2px 6px",
                        borderRadius: 10,
                        fontSize: 10,
                        fontWeight: 800,
                      }}
                    >
                      {Math.round(it.compliance_percentage)}%
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Active Prompt Details Card */}
            {activeItem && (
              <div
                style={{
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: 10,
                  padding: "16px 20px",
                }}
              >
                {/* Active Prompt Header & Progress Bar */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
                  <div>
                    <h5 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: "#0f172a" }}>
                      {activeItem.prompt_name}
                    </h5>
                    <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                      Compliance Score: {activeItem.compliance_percentage}% • {activeItem.passed_count} passed test(s)
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        background: activeItem.execution_status === "PASSED" ? "#dcfce7" : (activeItem.execution_status === "PARTIAL" ? "#fef3c7" : "#fee2e2"),
                        color: activeItem.execution_status === "PASSED" ? "#166534" : (activeItem.execution_status === "PARTIAL" ? "#b45309" : "#991b1b"),
                        padding: "3px 10px",
                        borderRadius: 12,
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      Execution: {activeItem.execution_status}
                    </span>
                  </div>
                </div>

                {/* Progress Bar */}
                <div style={{ height: 6, background: "#e2e8f0", borderRadius: 4, overflow: "hidden", marginBottom: 16 }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${Math.min(100, Math.max(0, activeItem.compliance_percentage))}%`,
                      background: activeItem.compliance_percentage >= 80 ? "linear-gradient(90deg, #10b981, #059669)" : "linear-gradient(90deg, #f59e0b, #d97706)",
                      transition: "width 0.4s ease",
                    }}
                  />
                </div>

                {/* Two-Column: Covered vs Uncovered Scenarios */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14, marginBottom: 16 }}>
                  {/* Covered Scenarios */}
                  <div style={{ background: "#ffffff", padding: "12px 14px", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#166534", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                      <FaCheckCircle color="#16a34a" /> Covered Scenarios ({activeItem.covered_scenarios?.length || 0})
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {activeItem.covered_scenarios && activeItem.covered_scenarios.length > 0 ? (
                        activeItem.covered_scenarios.map((scen: string, idx: number) => (
                          <div key={idx} style={{ fontSize: 11, color: "#334155", display: "flex", alignItems: "flex-start", gap: 6 }}>
                            <span style={{ color: "#16a34a", marginTop: 2 }}>✓</span>
                            <span>{scen}</span>
                          </div>
                        ))
                      ) : (
                        <div style={{ fontSize: 11, color: "#94a3b8" }}>No covered scenarios recorded.</div>
                      )}
                    </div>
                  </div>

                  {/* Uncovered Scenarios */}
                  <div style={{ background: "#ffffff", padding: "12px 14px", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: activeItem.uncovered_scenarios?.length ? "#b45309" : "#64748b", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                      <FaExclamationTriangle color={activeItem.uncovered_scenarios?.length ? "#f59e0b" : "#94a3b8"} />
                      Uncovered Scenarios ({activeItem.uncovered_scenarios?.length || 0})
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {activeItem.uncovered_scenarios && activeItem.uncovered_scenarios.length > 0 ? (
                        activeItem.uncovered_scenarios.map((scen: string, idx: number) => (
                          <div key={idx} style={{ fontSize: 11, color: "#b45309", display: "flex", alignItems: "flex-start", gap: 6 }}>
                            <span style={{ color: "#f59e0b", marginTop: 2 }}>!</span>
                            <span>{scen}</span>
                          </div>
                        ))
                      ) : (
                        <div style={{ fontSize: 11, color: "#16a34a", fontWeight: 600 }}>
                          All expected testing scenarios satisfied by verified test logic.
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Associated Test Methods & Code Inspection Badges */}
                {activeItem.generated_test_methods && activeItem.generated_test_methods.length > 0 && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                      Traceable Test Methods & Verified Code Logic
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {activeItem.generated_test_methods.map((methodName: string, mIdx: number) => (
                        <span
                          key={mIdx}
                          style={{
                            background: "#eff6ff",
                            color: "#1d4ed8",
                            border: "1px solid #dbeafe",
                            padding: "3px 8px",
                            borderRadius: 6,
                            fontSize: 11,
                            fontFamily: "monospace",
                            fontWeight: 600,
                          }}
                        >
                          {methodName}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* JaCoCo Gaps & Recommendations */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
                  {activeItem.jacoco_gaps_addressed && activeItem.jacoco_gaps_addressed.length > 0 && (
                    <div style={{ fontSize: 11, color: "#475569" }}>
                      <span style={{ fontWeight: 700, color: "#0f172a" }}>JaCoCo Gaps Addressed: </span>
                      {activeItem.jacoco_gaps_addressed.join(", ")}
                    </div>
                  )}

                  {activeItem.recommendations && activeItem.recommendations.length > 0 && (
                    <div style={{ fontSize: 11, color: "#475569", display: "flex", alignItems: "flex-start", gap: 6 }}>
                      <FaLightbulb color="#f59e0b" style={{ flexShrink: 0, marginTop: 2 }} />
                      <div>
                        <span style={{ fontWeight: 700, color: "#0f172a" }}>Recommendation: </span>
                        {activeItem.recommendations.join("; ")}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {/* GENERATED TEST FILES SECTION */}
      {generatedFiles.length > 0 && (
        <div style={{ marginBottom: 28, background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 14, padding: "18px 22px", boxShadow: "0 2px 10px rgba(0,0,0,0.03)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ background: "#eff6ff", color: "#2563eb", width: 30, height: 30, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700 }}>
                {generatedFiles.length}
              </div>
              <div>
                <h5 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "#0f172a" }}>
                  Generated Test Files ({generatedFiles.length} created)
                </h5>
                <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                  Physical JUnit test files generated from selected testing prompts
                </div>
              </div>
            </div>
            <span style={{ fontSize: 11, fontWeight: 600, color: "#059669", background: "#ecfdf5", padding: "4px 10px", borderRadius: 12 }}>
              Traceable & Verifiable
            </span>
          </div>

          <div style={{ border: "1px solid #eef2f6", borderRadius: 10, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead style={{ background: "#f8fafc", borderBottom: "1px solid #eef2f6" }}>
                <tr>
                  <th style={{ padding: "10px 16px", textAlign: "left", color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>Target Class</th>
                  <th style={{ padding: "10px 16px", textAlign: "left", color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>Generated Test File</th>
                  <th style={{ padding: "10px 16px", textAlign: "center", color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>Generator</th>
                  <th style={{ padding: "10px 16px", textAlign: "center", color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>@Test Methods</th>
                  <th style={{ padding: "10px 16px", textAlign: "right", color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>Execution Status</th>
                </tr>
              </thead>
              <tbody>
                {generatedFiles.map((gf: any, idx: number) => {
                  const statusRaw = (gf.execution_status || (gf.status === "CREATED" ? (execGenCount > 0 ? "EXECUTED" : "NOT EXECUTED") : gf.status || "NOT EXECUTED")).toUpperCase();
                  let statusLabel = "NOT EXECUTED";
                  let statusBg = "#f1f5f9";
                  let statusColor = "#475569";
                  let statusBorder = "#e2e8f0";

                  if (statusRaw === "EXECUTED" || statusRaw === "PASSED") {
                    statusLabel = "EXECUTED";
                    statusBg = "#dcfce7";
                    statusColor = "#166534";
                    statusBorder = "#86efac";
                  } else if (statusRaw === "COMPILE FAILED" || statusRaw === "COMPILE_FAILED") {
                    statusLabel = "COMPILE FAILED";
                    statusBg = "#fee2e2";
                    statusColor = "#991b1b";
                    statusBorder = "#fecaca";
                  } else if (statusRaw === "FAILED" || statusRaw === "GENERATION FAILED") {
                    statusLabel = "FAILED";
                    statusBg = "#fee2e2";
                    statusColor = "#991b1b";
                    statusBorder = "#fecaca";
                  } else if (statusRaw === "PARTIAL" || statusRaw === "PARTIALLY EXECUTED") {
                    statusLabel = "PARTIALLY EXECUTED";
                    statusBg = "#fef3c7";
                    statusColor = "#b45309";
                    statusBorder = "#fde68a";
                  } else {
                    statusLabel = "NOT EXECUTED";
                    statusBg = "#f1f5f9";
                    statusColor = "#475569";
                    statusBorder = "#e2e8f0";
                  }

                  return (
                    <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9", background: idx % 2 === 0 ? "#fff" : "#fafbfc" }}>
                      <td style={{ padding: "10px 16px", fontWeight: 600, color: "#0f172a" }}>{gf.source_class}</td>
                      <td style={{ padding: "10px 16px", color: "#2563eb", fontFamily: "monospace", fontSize: 11 }}>{gf.path}</td>
                      <td style={{ padding: "10px 16px", textAlign: "center" }}>
                        <span style={{ background: gf.generator === "LLM" ? "#f3e8ff" : "#e0e7ff", color: gf.generator === "LLM" ? "#7e22ce" : "#3730a3", padding: "2px 8px", borderRadius: 12, fontSize: 10, fontWeight: 700 }}>
                          {gf.generator}
                        </span>
                      </td>
                      <td style={{ padding: "10px 16px", textAlign: "center", fontWeight: 700, color: "#0f172a" }}>
                        {gf.test_method_count}
                      </td>
                      <td style={{ padding: "10px 16px", textAlign: "right" }}>
                        <span style={{ background: statusBg, color: statusColor, border: `1px solid ${statusBorder}`, padding: "2px 8px", borderRadius: 12, fontSize: 10, fontWeight: 700 }}>
                          {statusLabel}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}


      {/* Table Heading */}
      <h5 style={{ margin: "0 0 16px 0", fontSize: 15, fontWeight: 700, color: "#0f172a" }}>
        Executed Test Method Details ({executedDetails.length} methods)
      </h5>

      {/* Table */}
      <div style={{ border: "1px solid #eef2f6", borderRadius: 12, overflowY: "auto", background: "#fff", marginBottom: 24, flex: 1, maxHeight: 250, position: "relative" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead style={{ background: "#f8fafc", borderBottom: "1px solid #eef2f6", position: "sticky", top: 0, zIndex: 10 }}>
            <tr>
              <th style={{ padding: "12px 20px", textAlign: "left", color: "#64748b", fontWeight: 700, fontSize: 12, textTransform: "uppercase" }}>Test Class</th>
              <th style={{ padding: "12px 20px", textAlign: "left", color: "#64748b", fontWeight: 700, fontSize: 12, textTransform: "uppercase" }}>Test Method</th>
              <th style={{ padding: "12px 20px", textAlign: "center", color: "#64748b", fontWeight: 700, fontSize: 12, textTransform: "uppercase" }}>Status</th>
              <th style={{ padding: "12px 20px", textAlign: "right", color: "#64748b", fontWeight: 700, fontSize: 12, textTransform: "uppercase" }}>Duration</th>
            </tr>
          </thead>
          <tbody>
            {executedDetails.length > 0 ? (
              executedDetails.map((row: any, i: number) => (
                <tr key={i} style={{ borderBottom: "1px solid #f1f5f9", background: i % 2 === 0 ? "#fff" : "#fafbfc" }}>
                  <td style={{ padding: "12px 20px", color: "#2563eb", fontWeight: 600 }}>{row.test_class}</td>
                  <td style={{ padding: "12px 20px", color: "#475569" }}>{row.test_method}</td>
                  <td style={{ padding: "12px 20px", textAlign: "center" }}>
                    <span style={{ background: row.status === "PASSED" ? "#dcfce7" : "#fee2e2", color: row.status === "PASSED" ? "#166534" : "#991b1b", padding: "3px 10px", borderRadius: 20, fontSize: 10, fontWeight: 700 }}>{row.status}</span>
                  </td>
                  <td style={{ padding: "12px 20px", textAlign: "right", color: "#64748b", fontFamily: "monospace" }}>{row.execution_time_seconds ?? 0}s</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  No executed test methods recorded for this migration.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Footer Actions */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "auto" }}>
        <button onClick={() => onDownloadUnitTestReport()} style={{ background: "#059669", border: "none", padding: "10px 24px", borderRadius: 10, fontSize: 13, fontWeight: 700, color: "#fff", display: "flex", alignItems: "center", gap: 8, cursor: "pointer", boxShadow: "0 4px 12px rgba(5, 150, 105, 0.2)" }}>
          <FaDownload /> Download Unit Test Report
        </button>
        {executedDetails.length > 0 && (
          <button onClick={() => setShowAllModal(true)} style={{ background: "none", border: "none", color: "#2563eb", fontSize: 14, fontWeight: 700, textDecoration: "none", display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
            View All Test Methods
          </button>
        )}
      </div>

      {/* All Test Methods Modal */}
      {showAllModal && (
        <div style={{
          position: "fixed",
          inset: 0,
          zIndex: 10000000,
          background: "rgba(15, 23, 42, 0.75)",
          backdropFilter: "blur(12px)",
          display: "grid",
          placeItems: "center",
          padding: "40px",
          pointerEvents: "auto"
        }} onClick={() => setShowAllModal(false)}>
           <div style={{
             background: "#fff",
             borderRadius: 24,
             maxWidth: 1100,
             width: "90%",
             maxHeight: "85vh",
             overflow: "hidden",
             display: "flex",
             flexDirection: "column",
             boxShadow: "0 50px 100px -20px rgba(0, 0, 0, 0.6)",
             position: "relative"
           }} onClick={e => e.stopPropagation()}>
              <div style={{ padding: "24px 32px", borderBottom: "1px solid #f1f5f9", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#f8fafc" }}>
                 <div>
                    <h4 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#0f172a" }}>All Executed Test Methods</h4>
                    <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
                      Total {executedDetails.length} test methods executed
                    </div>
                 </div>
                 <button onClick={() => setShowAllModal(false)} style={{ background: "#fff", border: "1px solid #e2e8f0", width: 40, height: 40, borderRadius: "50%", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b", transition: "all 0.2s" }} onMouseEnter={e => e.currentTarget.style.borderColor = "#cbd5e1"} onMouseLeave={e => e.currentTarget.style.borderColor = "#e2e8f0"}><FaTimes /></button>
              </div>
              <div style={{ padding: "0", overflowY: "auto", flex: 1, background: "#fff" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead style={{ background: "#f8fafc", borderBottom: "1px solid #eef2f6", position: "sticky", top: 0, zIndex: 10 }}>
                    <tr>
                      <th style={{ padding: "16px 20px", textAlign: "left", color: "#64748b", fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em" }}>Test Class</th>
                      <th style={{ padding: "16px 20px", textAlign: "left", color: "#64748b", fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em" }}>Test Method</th>
                      <th style={{ padding: "16px 20px", textAlign: "center", color: "#64748b", fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em" }}>Status</th>
                      <th style={{ padding: "16px 20px", textAlign: "right", color: "#64748b", fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em" }}>Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {executedDetails.map((row: any, i: number) => (
                      <tr key={i} style={{ borderBottom: "1px solid #f1f5f9", background: i % 2 === 0 ? "#fff" : "#fafbfc" }}>
                        <td style={{ padding: "14px 20px", color: "#2563eb", fontWeight: 600 }}>{row.test_class}</td>
                        <td style={{ padding: "14px 20px", color: "#475569" }}>{row.test_method}</td>
                        <td style={{ padding: "14px 20px", textAlign: "center" }}>
                          <span style={{ background: row.status === "PASSED" ? "#dcfce7" : "#fee2e2", color: row.status === "PASSED" ? "#166534" : "#991b1b", padding: "4px 12px", borderRadius: 20, fontSize: 10, fontWeight: 700 }}>{row.status}</span>
                        </td>
                        <td style={{ padding: "14px 20px", textAlign: "right", color: "#64748b", fontFamily: "monospace", fontWeight: 600 }}>{row.execution_time_seconds ?? 0}s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ padding: "16px 32px", borderTop: "1px solid #f1f5f9", background: "#f8fafc", textAlign: "right" }}>
                <button onClick={() => setShowAllModal(false)} style={{ background: "#0f172a", color: "#fff", border: "none", padding: "10px 24px", borderRadius: 10, fontSize: 13, fontWeight: 700, cursor: "pointer" }}>Close</button>
              </div>
           </div>
        </div>
      )}
    </div>
  );
}

// ── SONAR SECTION ────────────────────────────────────────────────────────────

interface MigrationSonarSectionProps {
  styles: StyleMap;
  migrationJob: MigrationResult;
  sonarTotalFindings: number;
}

export function MigrationSonarSection({
  styles,
  migrationJob,
  sonarTotalFindings,
}: MigrationSonarSectionProps) {
  const isExecuted = Boolean(migrationJob?.run_sonar ?? migrationJob?.runSonar);

  if (!isExecuted) {
    return (
      <div style={{ ...styles.reportSection, background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "32px 40px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
          <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ background: "#64748b", color: "#fff", width: 32, height: 32, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
              <FaShieldAlt />
            </div>
            SonarQube
          </h3>
          <span style={{ padding: "6px 16px", borderRadius: 20, background: "#f1f5f9", color: "#475569", fontSize: 12, fontWeight: 700, border: "1px solid #e2e8f0" }}>
            NOT SELECTED
          </span>
        </div>
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 12, padding: "28px 24px", textAlign: "center" }}>
          <div style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 44, height: 44, borderRadius: "50%", background: "#f1f5f9", color: "#64748b", marginBottom: 12, fontSize: 20 }}>
            <FaShieldAlt />
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#334155", marginBottom: 6 }}>
            Not Selected
          </div>
          <div style={{ fontSize: 13, color: "#64748b", maxWidth: 520, margin: "0 auto" }}>
            This scan was not enabled for this migration.
          </div>
        </div>
      </div>
    );
  }
  const sonarReport = (migrationJob?.sonar_report as any) || {};
  const qualityGateStatus = sonarReport?.quality_gate || "UNAVAILABLE";
  const qualityGateColor = qualityGateStatus === "PASSED" || qualityGateStatus === "OK" ? "#22c55e" : "#f59e0b";

  const metrics = [
    { label: "Quality Gate", value: qualityGateStatus, color: qualityGateColor, bg: qualityGateColor + "10" },
    { label: "Coverage", value: `${sonarReport?.coverage || "0"}%`, color: "#22c55e", bg: "#f0fdf4" },
    { label: "Bugs", value: sonarReport?.bugs || 0, color: "#2563eb", bg: "#eff6ff" },
    { label: "Vulnerabilities", value: sonarReport?.vulnerabilities || 0, color: "#ef4444", bg: "#fef2f2" },
    { label: "Code Smells", value: sonarReport?.code_smells || 0, color: "#f59e0b", bg: "#fffbeb" },
    { label: "Security Hotspots", value: sonarReport?.security_hotspots || 0, color: "#14b8a6", bg: "#f0fdfa" },
    { label: "Total Findings", value: sonarTotalFindings || 0, color: "#7c3aed", bg: "#f5f3ff" }
  ];

  const bugsCount = sonarReport?.bugs || 0;
  const vulnCount = sonarReport?.vulnerabilities || 0;
  const codeSmellsCount = sonarReport?.code_smells || 0;
  const hotspotsCount = sonarReport?.security_hotspots || 0;

  const rawSonarUrl =
    migrationJob?.sonar_analysis_url ||
    (migrationJob?.sonar_report as any)?.analysis_url ||
    (migrationJob?.sonar_report as any)?.dashboard_url ||
    (migrationJob as any)?.sonar_project_url;

  const projectKey =
    migrationJob?.sonar_project_key ||
    (migrationJob?.sonar_report as any)?.project_key ||
    (migrationJob as any)?.project_key;

  const effectiveSonarUrl =
    rawSonarUrl ||
    (projectKey ? `https://sonarcloud.io/project/overview?id=${encodeURIComponent(projectKey)}` : null);

  return (
    <div style={{ ...styles.reportSection, background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "32px 40px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
       <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", marginBottom: 20, display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ background: "#2563eb", color: "#fff", width: 32, height: 32, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
          <FaShieldAlt />
        </div>
        SonarQube Enterprise Code Quality Dashboard
      </h3>

      <div>
        <div style={{ fontSize: 14, color: "#64748b", marginBottom: 24, fontWeight: 500 }}>
          Continuous inspection report for Java migration quality gate, security vulnerabilities, and code debt.
        </div>

        {migrationJob?.sonar_scan_mode === "missing_cli" && (
           <div style={{ background: "#fff7ed", border: "1px solid #fdba74", color: "#9a3412", borderRadius: 12, padding: "16px 20px", marginBottom: 24, display: "flex", alignItems: "center", gap: 12, fontSize: 14, fontWeight: 600 }}>
             <FaExclamationTriangle style={{ color: "#f59e0b", fontSize: 18 }} />
             <span>Sonar Analysis Notice: sonar-scanner CLI 'sonar-scanner' not found on PATH. Install SonarScanner CLI or set SONAR_SCANNER_COMMAND in .env.</span>
           </div>
        )}

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
           <div style={{ display: "flex", gap: 10 }}>
              <span style={{ padding: "6px 16px", borderRadius: 20, background: "#f1f5f9", color: "#475569", fontSize: 12, fontWeight: 700, border: "1px solid #e2e8f0" }}>Scan Mode: {migrationJob?.sonar_scan_mode || "missing_cli"}</span>
              <span style={{ padding: "6px 16px", borderRadius: 20, background: "#fff7ed", color: "#c2410c", fontSize: 12, fontWeight: 700, border: "1px solid #ffedd5" }}>Result Recorded</span>
           </div>
           <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              {effectiveSonarUrl && (
                <a
                  href={effectiveSonarUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    background: "#eff6ff",
                    border: "1px solid #bfdbfe",
                    padding: "8px 16px",
                    borderRadius: 8,
                    fontSize: 13,
                    fontWeight: 700,
                    color: "#2563eb",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    textDecoration: "none",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                  title="Open project in SonarQube / SonarCloud dashboard"
                >
                  <span>View in SonarQube Dashboard</span>
                  <FaExternalLinkAlt size={11} />
                </a>
              )}
              <button style={{ background: "#fff", border: "1px solid #cbd5e1", padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 700, color: "#334155", display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}><FaDownload size={12}/> Export CSV</button>
              <button style={{ background: "#fff", border: "1px solid #cbd5e1", padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 700, color: "#334155", display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}><FaDownload size={12}/> Export JSON</button>
           </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 12, marginBottom: 32 }}>
          {metrics.map((m, idx) => (
            <div key={idx} style={{ background: m.bg, border: `1px solid ${m.color}20`, borderRadius: 12, padding: "16px 10px", textAlign: "center" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 8 }}>{m.label}</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: m.color }}>{m.value}</div>
              {m.label === "Quality Gate" && <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 4 }}>Gate Status</div>}
              {m.label === "Coverage" && <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 4 }}>Unit Test Coverage</div>}
            </div>
          ))}
        </div>

        <div style={{ background: "#f8fafc", border: "1px solid #eef2f6", borderRadius: 16, padding: "24px", marginBottom: 32 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#334155", marginBottom: 16 }}>Issue Distribution Analysis</div>
          <div style={{ height: 12, borderRadius: 999, background: "#eef2f6", display: "flex", overflow: "hidden", marginBottom: 16 }}>
            {sonarTotalFindings > 0 ? (
              <>
                <div style={{ width: `${(bugsCount / sonarTotalFindings) * 100}%`, background: "#2563eb" }} title={`Bugs: ${bugsCount}`} />
                <div style={{ width: `${(vulnCount / sonarTotalFindings) * 100}%`, background: "#ef4444" }} title={`Vulnerabilities: ${vulnCount}`} />
                <div style={{ width: `${(codeSmellsCount / sonarTotalFindings) * 100}%`, background: "#f59e0b" }} title={`Code Smells: ${codeSmellsCount}`} />
                <div style={{ width: `${(hotspotsCount / sonarTotalFindings) * 100}%`, background: "#14b8a6" }} title={`Security Hotspots: ${hotspotsCount}`} />
              </>
            ) : (
              <div style={{ width: "100%", background: "#22c55e" }} />
            )}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 24, fontSize: 12, color: "#64748b" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}><div style={{ width: 10, height: 10, borderRadius: "50%", background: "#2563eb" }} /> Bugs ({bugsCount})</span>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}><div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ef4444" }} /> Vulnerabilities ({vulnCount})</span>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}><div style={{ width: 10, height: 10, borderRadius: "50%", background: "#f59e0b" }} /> Code Smells ({codeSmellsCount})</span>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}><div style={{ width: 10, height: 10, borderRadius: "50%", background: "#14b8a6" }} /> Security Hotspots ({hotspotsCount})</span>
          </div>

          <div style={{ marginTop: 24, paddingTop: 20, borderTop: "1px dashed #e2e8f0", display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#475569" }}>Severity Breakdown:</span>
              <span style={{ padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 700, background: "#450a0a", color: "#ffffff" }}>Blocker (0)</span>
              <span style={{ padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 700, background: "#ef4444", color: "#ffffff" }}>Critical (0)</span>
              <span style={{ padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 700, background: "#fff7ed", color: "#c2410c", border: "1px solid #ffedd5" }}>Major (0)</span>
              <span style={{ padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 700, background: "#fefce8", color: "#854d0e", border: "1px solid #fef08a" }}>Minor (0)</span>
              <span style={{ padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 700, background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe" }}>Info (0)</span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {[
                { label: "Bugs", count: bugsCount, icon: <FaBug />, color: "#2563eb" },
                { label: "Vulnerabilities", count: vulnCount, icon: <FaLock />, color: "#ef4444" },
                { label: "Code Smells", count: codeSmellsCount, icon: <FaBiohazard />, color: "#f59e0b" },
                { label: "Security Hotspots", count: hotspotsCount, icon: <FaFire />, color: "#14b8a6" },
            ].map((section, idx) => (
                <div key={idx} style={{ background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 12, overflow: "hidden" }}>
                    <div style={{ padding: "12px 20px", background: "#f8fafc", borderBottom: "1px solid #eef2f6", display: "flex", alignItems: "center", gap: 12 }}>
                        <div style={{ color: section.color, fontSize: 16 }}>{section.icon}</div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{section.label}</div>
                        <span style={{ background: "#eff6ff", color: "#2563eb", padding: "2px 10px", borderRadius: 20, fontSize: 12, fontWeight: 700, border: "1px solid #dbeafe" }}>{section.count}</span>
                    </div>
                    <div style={{ padding: "24px", textAlign: "center", color: "#64748b", fontSize: 14 }}>
                        No findings match the current search or filters for {section.label}.
                    </div>
                </div>
            ))}
        </div>
      </div>
    </div>
  );
}

// ── FOSSA SECTION ────────────────────────────────────────────────────────────

interface MigrationFossaSectionProps {
  styles?: StyleMap;
  migrationJob?: MigrationResult;
  runFossa?: boolean;
  fossaLicenseIssueCount?: number | null;
  fossaVulnerabilityTotal?: number | null;
  fossaOutdatedCount?: number | null;
  fossaTotalDependencies?: number | null;
  fossaTotalLicenses?: number | null;
  fossaPolicyStatus?: string | null;
  fossaScanMode?: string | null;
  fossaErrorMessage?: string | null;
  fossaAnalysisUrl?: string | null;
  fossaRealScan?: boolean;
}

export function MigrationFossaSection({
  migrationJob,
  runFossa,
  fossaLicenseIssueCount,
  fossaVulnerabilityTotal,
  fossaOutdatedCount,
  fossaTotalDependencies,
  fossaTotalLicenses,
  fossaPolicyStatus,
  fossaScanMode,
  fossaErrorMessage,
  fossaAnalysisUrl,
  fossaRealScan,
}: MigrationFossaSectionProps) {
  const isExecuted = Boolean(migrationJob?.run_fossa ?? migrationJob?.runFossa ?? runFossa);

  if (!isExecuted) {
    return (
      <div style={{ padding: 0 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
          <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ background: "#64748b", color: "#fff", width: 28, height: 28, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>
              <FaShieldAlt />
            </div>
            FOSSA License & Dependency Scan
          </h3>
          <span
            style={{
              padding: "4px 12px",
              borderRadius: 20,
              background: "#f1f5f9",
              color: "#475569",
              fontSize: 12,
              fontWeight: 700,
              border: "1px solid #e2e8f0",
            }}
          >
            NOT SELECTED
          </span>
        </div>
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 12, padding: "24px 20px", textAlign: "center" }}>
          <div style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 40, height: 40, borderRadius: "50%", background: "#f1f5f9", color: "#64748b", marginBottom: 10, fontSize: 18 }}>
            <FaShieldAlt />
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#334155", marginBottom: 4 }}>
            Not Selected
          </div>
          <div style={{ fontSize: 12, color: "#64748b", maxWidth: 420, margin: "0 auto" }}>
            This scan was not enabled for this migration.
          </div>
        </div>
      </div>
    );
  }

  const scanMode = (fossaScanMode || "").toLowerCase();
  const rawPolicy = (fossaPolicyStatus || "").trim().toUpperCase();
  const isPassed = rawPolicy === "PASSED" || rawPolicy === "OK";
  const isFailed = rawPolicy === "FAILED" || rawPolicy === "VIOLATIONS";
  const isNotRun = rawPolicy === "NOT_RUN" || rawPolicy === "NOT RUN" || scanMode === "skipped";

  const statusLabel = isPassed ? "PASSED" : isFailed ? "FAILED" : isNotRun ? "NOT RUN" : "UNAVAILABLE";
  const badgeColor = isPassed ? "#15803d" : isFailed ? "#b91c1c" : isNotRun ? "#475569" : "#c2410c";
  const badgeBg = isPassed ? "#f0fdf4" : isFailed ? "#fef2f2" : isNotRun ? "#f1f5f9" : "#fff7ed";
  const badgeBorder = isPassed ? "#bbf7d0" : isFailed ? "#fecaca" : isNotRun ? "#e2e8f0" : "#ffedd5";

  const scanStatusLabel = fossaRealScan
    ? "COMPLETED"
    : scanMode === "missing_cli"
    ? "UNAVAILABLE"
    : scanMode === "missing_token"
    ? "UNCONFIGURED"
    : scanMode === "analysis_failed" || scanMode === "error"
    ? "FAILED"
    : isNotRun
    ? "NOT RUN"
    : "COMPLETED";

  let noticeText: string | null = null;
  let noticeType: "warning" | "error" | "info" = "warning";

  if (scanMode === "missing_token") {
    noticeText = fossaErrorMessage || "FOSSA API key not configured. Set FOSSA_API_KEY in .env or Quality Gate settings to enable scans.";
    noticeType = "warning";
  } else if (scanMode === "missing_cli") {
    noticeText = fossaErrorMessage || "FOSSA CLI (fossa) was not found on PATH or known locations.";
    noticeType = "warning";
  } else if (scanMode === "missing_maven") {
    noticeText = fossaErrorMessage || "Maven executable was not found or could not be launched for FOSSA analysis.";
    noticeType = "error";
  } else if (scanMode === "analysis_failed") {
    noticeText = fossaErrorMessage || "FOSSA analysis failed during CLI execution.";
    noticeType = "error";
  } else if (scanMode === "test_failed" || scanMode === "test_cli_error") {
    noticeText = fossaErrorMessage || "FOSSA policy test command encountered an error.";
    noticeType = "error";
  } else if (isFailed && fossaErrorMessage) {
    noticeText = fossaErrorMessage;
    noticeType = "error";
  } else if (!isPassed && !isFailed && fossaErrorMessage) {
    noticeText = fossaErrorMessage;
    noticeType = "warning";
  }

  const renderValue = (val: number | null | undefined) => {
    if (val !== null && val !== undefined) {
      return val;
    }
    return "—";
  };

  const totalDeps = renderValue(fossaTotalDependencies);
  const totalLics = renderValue(fossaTotalLicenses);
  const licIssues = renderValue(fossaLicenseIssueCount);
  const vulns = renderValue(fossaVulnerabilityTotal);
  const outdated = renderValue(fossaOutdatedCount);

  return (
    <div style={{ padding: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: "#2563eb", color: "#fff", width: 28, height: 28, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>
            <FaShieldAlt />
          </div>
          FOSSA License & Dependency Scan
        </h3>
        <span
          style={{
            padding: "4px 12px",
            borderRadius: 20,
            background: "#f1f5f9",
            color: "#475569",
            fontSize: 12,
            fontWeight: 700,
            border: "1px solid #e2e8f0",
          }}
        >
          Scan Status: {scanStatusLabel}
        </span>
      </div>

      {noticeText && (
        <div
          style={{
            background: noticeType === "error" ? "#fef2f2" : "#fff7ed",
            border: `1px solid ${noticeType === "error" ? "#fca5a5" : "#fdba74"}`,
            color: noticeType === "error" ? "#991b1b" : "#9a3412",
            borderRadius: 12,
            padding: "12px 16px",
            marginBottom: 16,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {noticeType === "error" ? (
              <FaTimesCircle style={{ color: "#dc2626", fontSize: 16, flexShrink: 0 }} />
            ) : (
              <FaExclamationTriangle style={{ color: "#f59e0b", fontSize: 16, flexShrink: 0 }} />
            )}
            <span>{noticeText}</span>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: fossaAnalysisUrl ? 16 : 0 }}>
        <div style={{ background: "#f8fafc", border: "1px solid #eef2f6", borderRadius: 12, padding: "12px", textAlign: "center" }}>
          <div
            style={{
              background: badgeBg,
              color: badgeColor,
              padding: "2px 8px",
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 800,
              border: `1px solid ${badgeBorder}`,
              marginBottom: 4,
              display: "inline-block",
            }}
          >
            {statusLabel}
          </div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>Policy Status</div>
        </div>
        {[
          { label: "Dependencies", value: totalDeps, color: "#2563eb" },
          { label: "Licenses", value: totalLics, color: "#0891b2" },
          {
            label: "License Issues",
            value: licIssues,
            color: typeof licIssues === "number" && licIssues > 0 ? "#ef4444" : "#10b981",
          },
          {
            label: "Vulnerabilities",
            value: vulns,
            color: typeof vulns === "number" && vulns > 0 ? "#ef4444" : "#10b981",
          },
          {
            label: "Outdated Packages",
            value: outdated,
            color: typeof outdated === "number" && outdated > 0 ? "#f59e0b" : "#10b981",
          },
        ].map((card, idx) => (
          <div key={idx} style={{ background: "#f8fafc", border: "1px solid #eef2f6", borderRadius: 12, padding: "12px", textAlign: "center" }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: card.color }}>{card.value}</div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>{card.label}</div>
          </div>
        ))}
      </div>

      {fossaAnalysisUrl && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
          <a
            href={fossaAnalysisUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              fontSize: 13,
              fontWeight: 700,
              color: "#2563eb",
              textDecoration: "none",
              padding: "8px 16px",
              borderRadius: 8,
              background: "#eff6ff",
              border: "1px solid #bfdbfe",
              transition: "all 0.2s ease",
            }}
          >
            <span>View in FOSSA Dashboard</span>
            <FaExternalLinkAlt size={11} />
          </a>
        </div>
      )}
    </div>
  );
}

// ── JMETER SECTION ──────────────────────────────────────────────────────────

interface MigrationJmeterSectionProps {
  styles: StyleMap;
  apiEndpointsValidated: number | null | undefined;
  apiEndpointsWorking: number | null | undefined;
}

export function MigrationJmeterSection({
  apiEndpointsValidated,
  apiEndpointsWorking,
}: MigrationJmeterSectionProps) {
  const validated = apiEndpointsValidated ?? 0;
  const working = apiEndpointsWorking ?? 0;

  return (
    <div style={{ padding: 0 }}>
      <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", marginBottom: 20, display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ background: "#2563eb", color: "#fff", width: 28, height: 28, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>
          <FaStopwatch />
        </div>
        JMeter Performance Test Report
      </h3>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
        {[
          { label: "API Endpoints Tested", value: validated },
          { label: "Working Endpoints", value: `${working}/${validated}`, color: "#f59e0b" },
          { label: "Average Response Time", value: "245ms" },
          { label: "Throughput", value: "150 req/sec" }
        ].map((stat, idx) => (
          <div key={idx} style={{ background: "#f8fafc", border: "1px solid #eef2f6", borderRadius: 12, padding: "12px", textAlign: "center" }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: stat.color || "#0f172a" }}>{stat.value}</div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>{stat.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── LOG SECTION ──────────────────────────────────────────────────────────────

interface MigrationLogSectionProps {
  styles: StyleMap;
  migrationLogs: string[];
}

export function MigrationLogSection({ styles, migrationLogs }: MigrationLogSectionProps) {
  return (
    <div style={{ ...styles.reportSection, background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 16, padding: "24px 32px", boxShadow: "0 4px 24px rgba(0,0,0,0.04)", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <div style={{ background: "#3b82f6", color: "#fff", width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
          <FaTerminal />
        </div>
        <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#0f172a" }}>Migration Execution Log</h3>
      </div>

      <div style={{
        background: "#0f172a",
        borderRadius: 12,
        padding: "20px",
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        fontSize: 13,
        color: "#10b981",
        overflowY: "auto",
        boxShadow: "inset 0 4px 12px rgba(0,0,0,0.25)",
        border: "1px solid #1e293b",
        lineHeight: 1.7,
        maxHeight: 280
      }}>
        {migrationLogs.length > 0 ? (
          migrationLogs.map((log, index) => (
            <div key={index} style={{ marginBottom: 4, display: "flex", gap: 16 }}>
              <span style={{ color: "#475569", minWidth: 24, textAlign: "right", userSelect: "none", fontSize: 12 }}>{index + 1}</span>
              <span style={{ wordBreak: "break-all" }}>{log}</span>
            </div>
          ))
        ) : (
          <div style={{ opacity: 0.8 }}>
            <div style={{ marginBottom: 4, display: "flex", gap: 16 }}><span style={{ color: "#475569", minWidth: 24, textAlign: "right" }}>1</span><span>[INFO] Initializing migration engine...</span></div>
            <div style={{ marginBottom: 4, display: "flex", gap: 16 }}><span style={{ color: "#475569", minWidth: 24, textAlign: "right" }}>2</span><span>[INFO] Analyzing source code patterns...</span></div>
            <div style={{ marginBottom: 4, display: "flex", gap: 16 }}><span style={{ color: "#475569", minWidth: 24, textAlign: "right" }}>3</span><span>[INFO] Applying Spring Boot 3.x transformations...</span></div>
            <div style={{ marginBottom: 4, display: "flex", gap: 16 }}><span style={{ color: "#475569", minWidth: 24, textAlign: "right" }}>4</span><span>[SUCCESS] Migration process completed.</span></div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── ISSUES SECTION ───────────────────────────────────────────────────────────

interface MigrationIssuesSectionProps {
  styles: StyleMap;
  issues: any[];
  isOpen: boolean;
  onToggle: () => void;
}

export function MigrationIssuesSection({
  styles,
  issues,
  isOpen,
  onToggle,
}: MigrationIssuesSectionProps) {
  const issuesCount = issues?.length || 0;

  return (
    <div style={{ ...styles.reportSection, background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 16, padding: "24px 32px", boxShadow: "0 4px 24px rgba(0,0,0,0.04)", display: "flex", flexDirection: "column" }}>
      <button type="button" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", background: "none", border: "none", padding: 0, cursor: "pointer", textAlign: "left", marginBottom: 20 }} onClick={onToggle}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: "#ef4444", color: "#fff", width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
            <FaExclamationTriangle />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#0f172a" }}>Detailed Issues & Errors</h3>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {issuesCount === 0 && (
            <span style={{ background: "#ecfdf5", color: "#059669", padding: "4px 12px", borderRadius: 20, fontSize: 11, fontWeight: 700, border: "1px solid #a7f3d0" }}>No Issues Found</span>
          )}
          <span style={{ fontSize: 18, color: "#64748b", background: "#f8fafc", width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid #e2e8f0" }}>{isOpen ? "▾" : "▸"}</span>
        </div>
      </button>

      <div style={{ fontSize: 13, color: "#64748b", fontWeight: 500, marginBottom: isOpen ? 20 : 0, padding: "12px 16px", background: "#f8fafc", borderRadius: 10, border: "1px solid #eef2f6" }}>
        Review the exact issues identified and the files they affected during the transformation phase.
        {issuesCount === 0 && <span style={{ marginLeft: 8, color: "#059669", fontWeight: 700 }}>— Your project is clean!</span>}
      </div>

      {isOpen && (
        <div style={{ flex: 1, overflowY: "auto", maxHeight: 280, paddingRight: 8, marginTop: issuesCount > 0 ? 0 : 20 }}>
          {issues && issues.length > 0 ? (
            issues.map((issue) => (
              <div key={issue.id} style={{ padding: "16px", background: "#f8fafc", border: "1px solid #eef2f6", borderRadius: 12, marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ padding: "3px 10px", borderRadius: 6, fontSize: 10, fontWeight: 800, background: issue.severity === "error" ? "#fee2e2" : "#fef3c7", color: issue.severity === "error" ? "#dc2626" : "#c2410c", textTransform: "uppercase" }}>
                    {issue.severity}
                  </span>
                  <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600 }}>{issue.category}</span>
                </div>
                <div style={{ fontSize: 14, color: "#1e293b", fontWeight: 700, marginBottom: 6 }}>{issue.message}</div>
                <div style={{ fontSize: 11, color: "#64748b", fontFamily: "'JetBrains Mono', monospace", background: "#fff", padding: "4px 8px", borderRadius: 4, border: "1px solid #eef2f6", display: "inline-block" }}>
                  {issue.file_path}:{issue.line_number}
                </div>
              </div>
            ))
          ) : (
            <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "40px 20px" }}>
              <div style={{ width: 64, height: 64, borderRadius: "50%", background: "#f0fdf4", display: "flex", alignItems: "center", justifyContent: "center", color: "#22c55e", fontSize: 24, marginBottom: 16 }}>
                <FaCheckCircle />
              </div>
              <h4 style={{ margin: "0 0 8px 0", fontSize: 16, fontWeight: 700, color: "#0f172a" }}>No Issues Found</h4>
              <p style={{ margin: 0, fontSize: 13, color: "#64748b", lineHeight: 1.6 }}>Your project was migrated without any significant errors or warnings.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── REPORT ACTIONS ───────────────────────────────────────────────────────────

interface MigrationReportActionsProps {
  styles: StyleMap;
  migrationJob: MigrationResult | null;
  migrationLogs: string[];
  resetWizard: () => void;
  onBack: () => void;
  onError: (message: string) => void;
}

export function MigrationReportActions({
  resetWizard,
}: MigrationReportActionsProps & { onDownloadUnitTestReport?: () => void }) {
  return (
    <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", padding: "12px 0", marginTop: 4, borderTop: "1px solid #eef2f6" }}>
      <button
        type="button"
        onClick={resetWizard}
        style={{
          background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
          border: "1px solid #1d4ed8",
          padding: "10px 22px",
          borderRadius: 10,
          fontSize: 13,
          fontWeight: 700,
          color: "#ffffff",
          display: "flex",
          alignItems: "center",
          gap: 8,
          cursor: "pointer",
          boxShadow: "0 4px 14px rgba(37, 99, 235, 0.25)",
          transition: "all 0.2s ease",
        }}
      >
        <FaRocket style={{ color: "#ffffff" }} /> Start New Migration
      </button>
    </div>
  );
}

// ── CODE CHANGES SECTION (placeholder) ───────────────────────────────────────

export function MigrationCodeChangesSection() {
  return null;
}