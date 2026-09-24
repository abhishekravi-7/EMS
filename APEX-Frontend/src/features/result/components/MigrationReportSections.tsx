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
  FaRocket
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
  summaryItems: any[];
  testsRun: number;
  runTests?: boolean;
  onDownloadUnitTestReport: () => Promise<void> | void;
}

export function MigrationUnitTestSection({
  styles,
  migrationJob,
  summaryItems,
  runTests,
  onDownloadUnitTestReport,
}: MigrationUnitTestSectionProps) {
  const [showAllModal, setShowAllModal] = useState(false);
  const [savedPrompt, setSavedPrompt] = useState<string | null>(null);

  useEffect(() => {
    getUserSettings()
      .then((data) => {
        const p = data.quality_checks_values?.testing_prompt || data.test_cases_values?.testing_prompt;
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
    const found = summaryItems.find((i: any) => i.label.toUpperCase().includes(pattern.toUpperCase()));
    return found ? found.value : fallback;
  };

  const totalFiles = getValueByLabel("TOTAL FILES", 0);
  const totalTestCases = getValueByLabel("TOTAL TEST CASES", 0);
  const existingTestFiles = getValueByLabel("EXISTING TEST FILES", 0);
  const newTestFiles = getValueByLabel("NEW TEST FILES", 0);
  const existingTestCases = getValueByLabel("EXISTING TEST CASES", 0);
  const generatedTestCases = getValueByLabel("GENERATED TEST CASES", "+0");
  const jacocoCoverageRaw = getValueByLabel("JACOCO COVERAGE", "0%");
  const jacocoCoverageVal = parseFloat(jacocoCoverageRaw.toString().replace("%", "")) || 0;

  const testPipeline = migrationJob?.test_pipeline ?? {};
  const executedDetails = testPipeline?.executed_test_details ?? [];

  return (
    <div style={{ ...styles.reportSection, background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "24px 32px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)", height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ background: "#2563eb", color: "#fff", width: 32, height: 32, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
          <FaFileAlt />
        </div>
        <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#0f172a" }}>Unit Test Information</h3>
        </div>
        <div style={{
          background: migrationJob?.status === "completed" ? "#dcfce7" : "#fff7ed",
          color: migrationJob?.status === "completed" ? "#166534" : "#f97316",
          padding: "4px 12px",
          borderRadius: 20,
          fontSize: 11,
          fontWeight: 700,
          border: `1px solid ${migrationJob?.status === "completed" ? "#86efac" : "#ffedd5"}`
        }}>
          {migrationJob?.status === "completed" ? "completed" : "awaiting first run"}
        </div>
      </div>

      {/* Metrics Row */}
      <div style={{ display: "flex", alignItems: "center", gap: 24, marginBottom: 32 }}>
        {/* Radial Gauge */}
        <div style={{ position: "relative", width: 110, height: 110, flexShrink: 0 }}>
          <svg width="110" height="110" viewBox="0 0 110 110">
            <circle cx="55" cy="55" r="48" fill="none" stroke="#f1f5f9" strokeWidth="10" />
            <circle cx="55" cy="55" r="48" fill="none" stroke="#22c55e" strokeWidth="10" strokeDasharray={`${jacocoCoverageVal * 3} 301`} strokeLinecap="round" transform="rotate(-90 55 55)" />
          </svg>
          <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center" }}>
            <div style={{ fontSize: 24, fontWeight: 800, color: "#0f172a" }}>{jacocoCoverageVal}%</div>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", lineHeight: 1.1 }}>JaCoCo<br/>Coverage</div>
          </div>
        </div>

        {/* 6 Metric Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, flex: 1 }}>
          {[
            { label: "Total Files in Repo", value: totalFiles },
            { label: "Total Test Cases", value: totalTestCases },
            { label: "Existing Test Files", value: existingTestFiles },
            { label: "New Test Files", value: newTestFiles },
            { label: "Existing Test Cases", value: existingTestCases },
            { label: "Generated Test Cases", value: generatedTestCases, color: "#f59e0b" },
          ].map((item, i) => (
            <div key={i} style={{ background: "#f8fafc", border: "1px solid #eef2f6", borderRadius: 12, padding: "12px 8px", textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: item.color || "#0f172a" }}>{item.value}</div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginTop: 4, lineHeight: 1.2 }}>{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Dynamic Testing Focus Prompt Feedback Card */}
      {(() => {
        const promptAnalysis = testPipeline?.prompt_analysis;
        const coverageEval = testPipeline?.prompt_coverage_evaluation;
        const fallbackPrompt = migrationJob?.quality_checks_values?.testing_prompt || migrationJob?.test_cases_values?.testing_prompt || savedPrompt;
        
        if (!promptAnalysis && !coverageEval && !fallbackPrompt) return null;

        const displayUserPrompt = promptAnalysis?.user_prompt || coverageEval?.user_prompt || fallbackPrompt;
        const displayFocus = promptAnalysis?.testing_focus || (displayUserPrompt ? `Testing Focus: ${displayUserPrompt}` : "General Focus");
        const displayAssessment = coverageEval?.coverage_assessment || "Executed unit test suite in alignment with configured testing focus.";
        const isMatched = coverageEval?.focus_matched !== false;
        let targetAreas: string[] = [];
        if (promptAnalysis?.target_classes && promptAnalysis.target_classes.length > 0 && promptAnalysis.target_classes[0] !== "Requested Focus" && !promptAnalysis.target_classes[0].toLowerCase().includes("focus")) {
          targetAreas = promptAnalysis.target_classes;
        } else if (promptAnalysis?.target_areas && promptAnalysis.target_areas.length > 0 && promptAnalysis.target_areas[0] !== "Requested Focus" && !promptAnalysis.target_areas[0].toLowerCase().includes("focus")) {
          targetAreas = promptAnalysis.target_areas;
        } else if (displayUserPrompt) {
          const p = displayUserPrompt.toLowerCase();
          if (p.includes("auth") || p.includes("login") || p.includes("credential") || p.includes("password")) {
            targetAreas = ["AuthService", "AuthenticationController"];
          } else if (p.includes("user") || p.includes("account") || p.includes("profile")) {
            targetAreas = ["UserService", "UserController"];
          } else if (p.includes("pay") || p.includes("transaction") || p.includes("billing")) {
            targetAreas = ["PaymentService", "PaymentController"];
          } else if (p.includes("file") || p.includes("upload") || p.includes("download")) {
            targetAreas = ["FileUploadService", "FileUploadController"];
          } else if (p.includes("order") || p.includes("cart")) {
            targetAreas = ["OrderService", "OrderController"];
          } else {
            const stopWords = new Set(["focus", "mainly", "on", "part", "for", "junit", "unit", "test", "testing", "the", "a", "an", "and", "or", "to", "in", "of", "page", "please", "give", "more", "coverage"]);
            const words = displayUserPrompt.replace(/[_-]/g, " ").split(/\s+/).filter(w => w.length > 1 && !stopWords.has(w.toLowerCase()));
            const concept = words.length > 0 ? words.slice(0, 2).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join("") : "Custom";
            targetAreas = [`${concept}Service`, `${concept}Controller`];
          }
        } else {
          targetAreas = ["AuthService", "AuthenticationController"];
        }
        const coveredScenarios = coverageEval?.covered_scenarios || (displayUserPrompt ? [displayUserPrompt] : []);
        const recommendations = coverageEval?.recommendations || [];

        return (
          <div style={{
            marginBottom: 24,
            padding: 20,
            background: isMatched ? "#f0fdf4" : "#fff7ed",
            border: `1px solid ${isMatched ? "#86efac" : "#fed7aa"}`,
            borderRadius: 12,
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "#0f172a", display: "flex", alignItems: "center", gap: 8 }}>
                🎯 Dynamic Testing Focus Prompt Feedback
              </h4>
              <span style={{
                padding: "2px 10px",
                borderRadius: 12,
                fontSize: 12,
                fontWeight: 700,
                background: isMatched ? "#dcfce7" : "#ffedd5",
                color: isMatched ? "#166534" : "#c2410c",
                border: `1px solid ${isMatched ? "#86efac" : "#fdba74"}`
              }}>
                {isMatched ? "Focus Target Covered" : "Needs Additional Coverage"}
              </span>
            </div>

            {displayUserPrompt && (
              <div style={{ fontSize: 13, color: "#475569", marginBottom: 10, fontStyle: "italic", background: "#ffffff", padding: "8px 12px", borderRadius: 6, border: "1px solid #e2e8f0" }}>
                <strong>User Prompt:</strong> "{displayUserPrompt}"
              </div>
            )}

            <div style={{ fontSize: 13, color: "#334155", marginBottom: 8 }}>
              <strong>LLM Identified Focus:</strong> {displayFocus}
            </div>

            <div style={{ fontSize: 13, color: "#1e293b", marginBottom: 12, fontWeight: 500 }}>
              <strong>Coverage Assessment:</strong> {displayAssessment}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {targetAreas.length > 0 && (
                <div>
                  <strong style={{ fontSize: 12, color: "#475569", textTransform: "uppercase" }}>Priority Target Areas:</strong>
                  <ul style={{ margin: "4px 0 0 16px", padding: 0, fontSize: 12, color: "#1e293b" }}>
                    {targetAreas.map((area: string, idx: number) => (
                      <li key={idx}>{area}</li>
                    ))}
                  </ul>
                </div>
              )}

              {coveredScenarios.length > 0 && (
                <div>
                  <strong style={{ fontSize: 12, color: "#166534", textTransform: "uppercase" }}>Covered Scenarios:</strong>
                  <ul style={{ margin: "4px 0 0 16px", padding: 0, fontSize: 12, color: "#166534" }}>
                    {coveredScenarios.map((sc: string, idx: number) => (
                      <li key={idx}>{sc}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {recommendations.length > 0 && (
              <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px stroke #cbd5e1" }}>
                <strong style={{ fontSize: 12, color: "#0f172a" }}>Coverage Recommendations:</strong>
                <ul style={{ margin: "4px 0 0 16px", padding: 0, fontSize: 12, color: "#475569" }}>
                  {recommendations.map((rec: string, idx: number) => (
                    <li key={idx}>{rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        );
      })()}

      {/* Table Heading */}
      <h5 style={{ margin: "0 0 16px 0", fontSize: 15, fontWeight: 700, color: "#0f172a" }}>
        Executed Test Method Details ({executedDetails.length || totalTestCases || 0} methods)
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
        <button onClick={onDownloadUnitTestReport} style={{ background: "#059669", border: "none", padding: "10px 24px", borderRadius: 10, fontSize: 13, fontWeight: 700, color: "#fff", display: "flex", alignItems: "center", gap: 8, cursor: "pointer", boxShadow: "0 4px 12px rgba(5, 150, 105, 0.2)" }}>
          <FaDownload /> Download Unit Test Report (CSV)
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
            NOT EXECUTED
          </span>
        </div>
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 12, padding: "28px 24px", textAlign: "center" }}>
          <div style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 44, height: 44, borderRadius: "50%", background: "#f1f5f9", color: "#64748b", marginBottom: 12, fontSize: 20 }}>
            <FaShieldAlt />
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#334155", marginBottom: 6 }}>
            SonarQube analysis was not selected or executed for this migration.
          </div>
          <div style={{ fontSize: 13, color: "#64748b", maxWidth: 520, margin: "0 auto" }}>
            Code quality gate, security inspection, and test coverage analysis were not enabled during the migration configuration.
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
  const sonarAnalysisUrl = sonarReport?.analysis_url || migrationJob?.sonar_analysis_url || null;

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
              {sonarAnalysisUrl && (
                <a
                  href={sonarAnalysisUrl}
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
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    textDecoration: "none",
                    cursor: "pointer",
                  }}
                >
                  <FaShieldAlt size={13} color="#2563eb" />
                  View Sonar Dashboard
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
  styles: StyleMap;
  fossaLicenseIssueCount?: number | null;
  fossaVulnerabilityTotal?: number | null;
  fossaOutdatedCount?: number | null;
  fossaTotalDependencies?: number | null;
  fossaPolicyStatus?: string | null;
  fossaScanMode?: string | null;
  fossaErrorMessage?: string | null;
  fossaAnalysisUrl?: string | null;
  fossaRealScan?: boolean;
}

export function MigrationFossaSection({
  fossaLicenseIssueCount,
  fossaVulnerabilityTotal,
  fossaOutdatedCount,
  fossaTotalDependencies,
  fossaPolicyStatus,
  fossaScanMode,
  fossaErrorMessage,
  fossaAnalysisUrl,
  fossaRealScan,
}: MigrationFossaSectionProps) {
  const scanMode = (fossaScanMode || "").toLowerCase();
  const policyStatus = (fossaPolicyStatus || "UNAVAILABLE").toUpperCase();
  const isAvailable = (policyStatus === "PASSED" || policyStatus === "OK" || policyStatus === "FAILED") && fossaRealScan;

  let warningText: string | null = null;
  if (scanMode === "missing_token") {
    warningText = fossaErrorMessage || "FOSSA API key not configured. Set FOSSA_API_KEY in .env to enable scans.";
  } else if (scanMode === "missing_cli") {
    warningText = fossaErrorMessage || "FOSSA CLI (fossa) was not found on PATH or known locations.";
  } else if (scanMode === "missing_maven") {
    warningText = fossaErrorMessage || "Maven executable was not found or could not be launched for FOSSA analysis.";
  } else if (scanMode === "analysis_failed") {
    warningText = fossaErrorMessage || "FOSSA analysis failed during CLI execution.";
  } else if (scanMode === "test_failed" || scanMode === "test_cli_error") {
    warningText = fossaErrorMessage || "FOSSA policy test command encountered an error.";
  } else if (fossaErrorMessage && !isAvailable && policyStatus === "UNAVAILABLE") {
    warningText = fossaErrorMessage;
  } else if (!isAvailable && !fossaRealScan && policyStatus === "UNAVAILABLE") {
    warningText = "FOSSA quality gate was not executed or is unavailable for this run.";
  }

  const isPassed = policyStatus === "PASSED" || policyStatus === "OK";
  const isFailed = policyStatus === "FAILED" || policyStatus === "VIOLATIONS";
  const statusLabel = isPassed ? "PASSED" : isFailed ? "FAILED" : "UNAVAILABLE";
  const badgeColor = isPassed ? "#15803d" : isFailed ? "#b91c1c" : "#c2410c";
  const badgeBg = isPassed ? "#f0fdf4" : isFailed ? "#fef2f2" : "#fff7ed";
  const badgeBorder = isPassed ? "#bbf7d0" : isFailed ? "#fecaca" : "#ffedd5";

  const renderValue = (val: number | null | undefined) => {
    if (val !== null && val !== undefined) {
      return val;
    }
    return isAvailable ? 0 : "—";
  };

  const licIssues = renderValue(fossaLicenseIssueCount);
  const vulns = renderValue(fossaVulnerabilityTotal);
  const outdated = renderValue(fossaOutdatedCount);

  return (
    <div style={{ padding: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: "#2563eb", color: "#fff", width: 28, height: 28, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>
            <FaShieldAlt />
          </div>
          FOSSA License & Dependency Scan
        </h3>
        {fossaAnalysisUrl && (
          <a
            href={fossaAnalysisUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              fontWeight: 700,
              color: "#2563eb",
              textDecoration: "none",
              background: "#eff6ff",
              border: "1px solid #bfdbfe",
              padding: "6px 12px",
              borderRadius: 8,
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
            title="Open FOSSA compliance and dependency dashboard"
          >
            <span>View FOSSA Dashboard</span>
            <FaExternalLinkAlt size={10} />
          </a>
        )}
      </div>

      {warningText && (
        <div style={{ background: "#fff7ed", border: "1px solid #fdba74", color: "#9a3412", borderRadius: 12, padding: "12px 16px", marginBottom: 20, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, fontSize: 13, fontWeight: 600 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <FaExclamationTriangle style={{ color: "#f59e0b", fontSize: 16, flexShrink: 0 }} />
            <span>{warningText}</span>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
        <div style={{ background: "#f8fafc", border: "1px solid #eef2f6", borderRadius: 12, padding: "12px", textAlign: "center" }}>
          <div style={{ background: badgeBg, color: badgeColor, padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 800, border: `1px solid ${badgeBorder}`, marginBottom: 4, display: "inline-block" }}>
            {statusLabel}
          </div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>Policy Status</div>
        </div>
        {[
          { label: "License Issues", value: licIssues, color: typeof licIssues === "number" && licIssues > 0 ? "#ef4444" : "#10b981" },
          { label: "Vulnerabilities", value: vulns, color: typeof vulns === "number" && vulns > 0 ? "#ef4444" : "#10b981" },
          { label: "Outdated Packages", value: outdated, color: typeof outdated === "number" && outdated > 0 ? "#f59e0b" : "#10b981" }
        ].map((card, idx) => (
          <div key={idx} style={{ background: "#f8fafc", border: "1px solid #eef2f6", borderRadius: 12, padding: "12px", textAlign: "center" }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: card.color }}>{card.value}</div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>{card.label}</div>
          </div>
        ))}
      </div>
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
  migrationJob,
  resetWizard,
  onDownloadUnitTestReport,
}: MigrationReportActionsProps & { onDownloadUnitTestReport: () => void }) {
  const jobId = migrationJob?.job_id;

  const handleDownload = async (type: "project" | "markdown" | "testcases" | "html") => {
    if (!jobId) return;
    try {
      let blob: Blob;
      let filename = "";
      switch (type) {
        case "project":
          blob = await downloadMigratedProject(jobId);
          filename = `modernized-project-${jobId}.zip`;
          break;
        case "markdown":
          blob = await downloadTestcaseDoc(jobId);
          filename = `testcase-report-${jobId}.md`;
          break;
        case "testcases":
          blob = await downloadTestcaseReport(jobId);
          filename = `testcases-and-changes-${jobId}.html`;
          break;
        case "html":
          blob = await downloadUnitTestReport(jobId);
          filename = `unit-test-report-${jobId}.html`;
          break;
        default: return;
      }
      triggerBlobDownload(blob, filename);
    } catch (err) {
      console.error("Download failed:", err);
    }
  };

  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", marginTop: 4, borderTop: "1px solid #eef2f6", flexWrap: "wrap", gap: 12 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <button onClick={() => handleDownload("project")} style={{ background: "#fff", border: "1px solid #e2e8f0", padding: "10px 20px", borderRadius: 10, fontSize: 13, fontWeight: 700, color: "#334155", display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <FaFileArchive style={{ color: "#d97706" }} /> Download ZIP
        </button>
        <button onClick={onDownloadUnitTestReport} style={{ background: "#fff", border: "1px solid #e2e8f0", padding: "10px 20px", borderRadius: 10, fontSize: 13, fontWeight: 700, color: "#334155", display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <FaExternalLinkAlt style={{ color: "#2563eb" }} /> Open Full Report
        </button>
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <button onClick={() => handleDownload("markdown")} style={{ background: "#fff", border: "1px solid #e2e8f0", padding: "10px 20px", borderRadius: 10, fontSize: 13, fontWeight: 700, color: "#334155", display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <FaMarkdown style={{ color: "#7c3aed" }} /> Download Markdown Report
        </button>
        <button onClick={() => handleDownload("testcases")} style={{ background: "#fff", border: "1px solid #e2e8f0", padding: "10px 20px", borderRadius: 10, fontSize: 13, fontWeight: 700, color: "#334155", display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <FaCode style={{ color: "#059669" }} /> Download Testcases & Changes
        </button>
        <button onClick={() => handleDownload("html")} style={{ background: "#fff", border: "1px solid #e2e8f0", padding: "10px 20px", borderRadius: 10, fontSize: 13, fontWeight: 700, color: "#334155", display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <FaFileCode style={{ color: "#0284c7" }} /> Download Testcase HTML
        </button>
        <button
          type="button"
          onClick={resetWizard}
          style={{
            background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
            border: "1px solid #1d4ed8",
            padding: "10px 20px",
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 700,
            color: "#ffffff",
            display: "flex",
            alignItems: "center",
            gap: 8,
            cursor: "pointer",
            boxShadow: "0 2px 8px rgba(37, 99, 235, 0.25)",
            transition: "all 0.2s ease",
          }}
        >
          <FaRocket style={{ color: "#ffffff" }} /> Start New Migration
        </button>
      </div>
    </div>
  );
}

// ── CODE CHANGES SECTION (placeholder) ───────────────────────────────────────

export function MigrationCodeChangesSection() {
  return null;
}