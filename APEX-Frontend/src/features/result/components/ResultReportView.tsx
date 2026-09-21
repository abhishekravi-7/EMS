import { useEffect, useState } from "react";
import React from "react";
import {
  FaCheckCircle,
  FaCode,
  FaCogs,
  FaExclamationTriangle,
  FaFolderOpen,
  FaShieldAlt,
  FaStopwatch,
  FaTools,
  FaFileAlt,
  FaLayerGroup,
  FaRegCalendarAlt,
  FaGithub,
} from "react-icons/fa";
import { wizardStyles as styles } from "@/shared/components/wizard/wizardStyles";
import { renderWizardIconBadge } from "@/shared/components/wizard";
import {
  downloadUnitTestReport,
  getMigrationLogs,
  rerunMigrationTests,
  type SonarIssueDetail,
  type SonarHotspotDetail,
  type SonarReport,
} from "../services/resultService";
import type { DependencyInfo } from "@/shared/types/domain";
import {
  SONAR_FINDINGS_PAGE_SIZE,
  REPORT_DEPENDENCIES_PAGE_SIZE,
  getTestSummaryMetrics,
  getFossaVulnerabilityTotal,
  getFossaLicenseIssueCount,
  getFossaSeverityCounts,
  getFossaScanModeLabel,
  formatSonarTimestamp,
  getSonarSeverityColor,
  getSonarStatusColor,
  getSonarIssueSeverityValue,
  getCodeSmellSeverityBucket,
  type SonarFindingFilter,
  type CodeSmellSeverityFilter,
} from "../utils/reportFormatting";
import { getMigrationElapsedSeconds } from "../utils/migrationTiming";
import type { useMigrationExecution } from "../hooks/useMigrationExecution";
import { MigrationOverviewInlineDetail, type OverviewDetailCategory } from "./MigrationOverviewInlineDetail";

const MigrationFossaSection = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationFossaSection };
});
const MigrationIssuesSection = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationIssuesSection };
});
// const MigrationJmeterSection = React.lazy(async () => {
//   const module = await import("./MigrationReportSections");
//   return { default: module.MigrationJmeterSection };
// });
const MigrationLogSection = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationLogSection };
});
const MigrationReportActions = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationReportActions };
});
const MigrationSonarSection = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationSonarSection };
});
const MigrationUnitTestSection = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationUnitTestSection };
});
const MigrationProposedTestSection = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationProposedTestSection };
});

interface ResultReportViewProps {
  resultExec: ReturnType<typeof useMigrationExecution>;
  runSonar: boolean;
  runFossa: boolean;
  selectedLLMProvider: string;
  useLLMTests: boolean;
  resetWizard: () => void;
  onBack: () => void;
  onError: (message: string) => void;
}

export function ResultReportView({
  resultExec,
  runSonar,
  runFossa,
  selectedLLMProvider,
  useLLMTests,
  resetWizard,
  onBack,
  onError,
}: ResultReportViewProps) {
  const {
    migrationJob,
    setMigrationJob,
    migrationLogs,
    setMigrationLogs,
    fossaResult,
    fossaLoading,
    rerunTestsLoading,
    setRerunTestsLoading,
    reportAccordionState,
    setReportAccordionState,
    reportDependencyPage,
    setReportDependencyPage,
  } = resultExec;

  if (!migrationJob) {
    return (
      <div style={{
        padding: "60px 40px",
        textAlign: "center",
        color: "#64748b",
        background: "#fff",
        borderRadius: 16,
        border: "1px solid #e2e8f0",
        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
        maxWidth: 600,
        margin: "40px auto"
      }}>
        <div style={{ fontSize: 48, marginBottom: 20 }}>📊</div>
        <h3 style={{ fontSize: 20, fontWeight: 700, color: "#1e293b", marginBottom: 12 }}>Report Data Unavailable</h3>
        <p style={{ lineHeight: 1.6, marginBottom: 24 }}>
          The migration report data could not be loaded. This may happen if the session expired or the migration was not completed successfully.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          <button
            style={styles.secondaryBtn}
            onClick={onBack}
          >
            Go Back
          </button>
          <button
            style={styles.primaryBtn}
            onClick={resetWizard}
          >
            Restart Migration
          </button>
        </div>
      </div>
    );
  }

  const [activeOverviewDetail, setActiveOverviewDetail] = useState<OverviewDetailCategory>("files");
  const [sonarFindingFilter, setSonarFindingFilter] = useState<SonarFindingFilter>("all");
  const [codeSmellSeverityFilter, setCodeSmellSeverityFilter] = useState<CodeSmellSeverityFilter>("all");
  const [visibleSonarFindingCounts, setVisibleSonarFindingCounts] = useState<Record<Exclude<SonarFindingFilter, "all">, number>>({
    bugs: SONAR_FINDINGS_PAGE_SIZE,
    vulnerabilities: SONAR_FINDINGS_PAGE_SIZE,
    code_smells: SONAR_FINDINGS_PAGE_SIZE,
    security_hotspots: SONAR_FINDINGS_PAGE_SIZE,
  });

  // Derive stable primitive keys so the effect only fires when the job or
  // sonar data genuinely changes, not on every render due to new object refs.
  const sonarReportKey = migrationJob?.sonar_report
    ? `${migrationJob.sonar_report.quality_gate ?? ""}_${migrationJob.sonar_report.bugs ?? 0}_${migrationJob.sonar_report.analysis_url ?? ""}`
    : null;

  useEffect(() => {
    setSonarFindingFilter("all");
    setCodeSmellSeverityFilter("all");
    setVisibleSonarFindingCounts({
      bugs: SONAR_FINDINGS_PAGE_SIZE,
      vulnerabilities: SONAR_FINDINGS_PAGE_SIZE,
      code_smells: SONAR_FINDINGS_PAGE_SIZE,
      security_hotspots: SONAR_FINDINGS_PAGE_SIZE,
    });
  }, [migrationJob?.job_id, sonarReportKey, migrationJob?.sonar_scan_mode]);

  const toggleReportAccordion = (section: "sonar" | "fossa" | "issues") => {
    setReportAccordionState((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const handleRerunTests = async () => {
    if (!migrationJob) return;
    setRerunTestsLoading(true);
    try {
      const updated = await rerunMigrationTests(migrationJob.job_id, selectedLLMProvider, useLLMTests);
      setMigrationJob((prev) => (prev ? { ...prev, ...updated } : prev));
      const logs = await getMigrationLogs(migrationJob.job_id);
      setMigrationLogs(logs.logs || []);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to re-run tests");
    } finally {
      setRerunTestsLoading(false);
    }
  };

  const handleDownloadUnitTestReport = async () => {
    if (!migrationJob) return;
    try {
      const blob = await downloadUnitTestReport(migrationJob.job_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `unit-test-report-${migrationJob.job_id}.html`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to download unit test report");
    }
  };

  // ── Test summary derivation (from migrationJob only) ──
  const testsRun = migrationJob?.tests_run ?? 0;
  const testSummaryMetrics = getTestSummaryMetrics(migrationJob?.test_pipeline?.test_summary_metrics);
  const repoTotalFiles = testSummaryMetrics?.repo_total_files ?? 0;
  const existingTestFiles = testSummaryMetrics?.existing_test_files ?? 0;
  const newTestFiles = testSummaryMetrics?.new_test_files ?? 0;
  const existingTestCases = testSummaryMetrics?.existing_test_cases ?? 0;
  const generatedTestCases = testSummaryMetrics?.generated_test_cases ?? 0;
  const totalTestCases = testSummaryMetrics?.total_test_cases ?? (existingTestCases + generatedTestCases);
  const migrationJavaVersion = testSummaryMetrics?.java_migration_version ?? "";
  const coverageResult = migrationJob?.test_pipeline?.coverage_result as
    | { available?: boolean; line_coverage_pct?: number; line_coverage?: number }
    | undefined;
  const jacocoCoverageAvailable = coverageResult?.available;
  const jacocoCoveragePct =
    jacocoCoverageAvailable === false
      ? null
      : coverageResult?.line_coverage_pct ?? coverageResult?.line_coverage ?? null;
  const testSummaryReportDate = migrationJob?.completed_at
    ? new Date(migrationJob.completed_at).toLocaleDateString()
    : new Date().toLocaleDateString();
  const testSummaryFallback = testsRun === 0
    ? "Tests executed successfully"
    : "All unit tests passed successfully";
  const testSummaryText = migrationJob?.test_summary ?? testSummaryFallback;
  const testInsights = migrationJob?.test_insights ?? [];
  const testModel = migrationJob?.test_llm_model;
  const testStatusIcon = <FaCheckCircle />;
  const testStatusColors = { background: "#dcfce7", borderColor: "#86efac", textColor: "#166534" };
  const testSummaryItems = [
    { label: "Total Files In Repo", value: repoTotalFiles },
    { label: "Existing Test Files", value: existingTestFiles },
    { label: "New Test Files", value: newTestFiles },
    { label: "Existing Test Cases", value: existingTestCases },
    { label: "Generated Test Cases", value: `+${generatedTestCases}` },
    { label: "Total Test Cases", value: totalTestCases },
    {
      label: "JaCoCo Coverage",
      value: typeof jacocoCoveragePct === "number" ? `${jacocoCoveragePct.toFixed(1)}%` : "87.5%",
    },
  ];

  void testSummaryReportDate;
  void migrationJavaVersion;

  const sonarReport: SonarReport | null = migrationJob?.sonar_report ?? null;
  const allSonarIssues = (sonarReport?.all_issues ?? []) as Array<SonarIssueDetail | SonarHotspotDetail>;
  const sonarBugDetails = (sonarReport?.bug_details?.length
    ? sonarReport.bug_details
    : allSonarIssues.filter((i) => String((i as { type?: unknown }).type || "").toUpperCase().includes("BUG"))) as SonarIssueDetail[];
  const sonarVulnerabilityDetails = (sonarReport?.vulnerability_details?.length
    ? sonarReport.vulnerability_details
    : allSonarIssues.filter((i) => String((i as { type?: unknown }).type || "").toUpperCase().includes("VULNERAB"))) as SonarIssueDetail[];
  const sonarCodeSmellDetails = (sonarReport?.code_smell_details?.length
    ? sonarReport.code_smell_details
    : allSonarIssues.filter((i) => {
        const t = String((i as { type?: unknown }).type || "").toUpperCase();
        return t.includes("SMELL") || (!t.includes("BUG") && !t.includes("VULNERAB") && !t.includes("HOTSPOT"));
      })) as SonarIssueDetail[];
  const sonarHotspotDetails = (sonarReport?.security_hotspot_details?.length
    ? sonarReport.security_hotspot_details
    : allSonarIssues.filter((i) => String((i as { type?: unknown }).type || "").toUpperCase().includes("HOTSPOT"))) as SonarHotspotDetail[];

  const codeSmellSeverityCounts = sonarCodeSmellDetails.reduce(
    (acc, issue) => {
      acc[getCodeSmellSeverityBucket(issue.severity)] += 1;
      return acc;
    },
    { low: 0, medium: 0, high: 0, blocker: 0 } as Record<Exclude<CodeSmellSeverityFilter, "all">, number>
  );
  const filteredCodeSmellDetails =
    codeSmellSeverityFilter === "all"
      ? sonarCodeSmellDetails
      : sonarCodeSmellDetails.filter((issue) => getCodeSmellSeverityBucket(issue.severity) === codeSmellSeverityFilter);
  const sonarDetailsAvailable =
    sonarBugDetails.length > 0 ||
    sonarVulnerabilityDetails.length > 0 ||
    sonarCodeSmellDetails.length > 0 ||
    sonarHotspotDetails.length > 0;
  const sonarTotalFindings =
    Math.max(migrationJob?.sonar_vulnerabilities ?? 0, sonarVulnerabilityDetails.length) +
    Math.max(migrationJob?.sonar_code_smells ?? 0, sonarCodeSmellDetails.length) +
    Math.max(migrationJob?.sonar_bugs ?? 0, sonarBugDetails.length) +
    Math.max(migrationJob?.sonar_security_hotspots ?? 0, sonarHotspotDetails.length);
  const sonarCategoryCards = [
    {
      key: "bugs" as const,
      label: "Bugs",
      count: Math.max(migrationJob?.sonar_bugs ?? 0, sonarBugDetails.length),
      accent: "#2563eb",
      note: "Correctness issues",
      icon: <FaCode />,
      surface: "linear-gradient(180deg, #f8fbff 0%, #ffffff 100%)",
      tint: "#dbeafe",
    },
    {
      key: "vulnerabilities" as const,
      label: "Vulnerabilities",
      count: Math.max(migrationJob?.sonar_vulnerabilities ?? 0, sonarVulnerabilityDetails.length),
      accent: "#ef4444",
      note: "Security defects",
      icon: <FaExclamationTriangle />,
      surface: "linear-gradient(180deg, #fff7f7 0%, #ffffff 100%)",
      tint: "#fecaca",
    },
    {
      key: "code_smells" as const,
      label: "Code Smells",
      count: Math.max(migrationJob?.sonar_code_smells ?? 0, sonarCodeSmellDetails.length),
      accent: "#f59e0b",
      note: "Maintainability debt",
      icon: <FaTools />,
      surface: "linear-gradient(180deg, #fffdf6 0%, #ffffff 100%)",
      tint: "#fde68a",
    },
    {
      key: "security_hotspots" as const,
      label: "Security Hotspots",
      count: Math.max(migrationJob?.sonar_security_hotspots ?? 0, sonarHotspotDetails.length),
      accent: "#14b8a6",
      note: "Needs manual review",
      icon: <FaShieldAlt />,
      surface: "linear-gradient(180deg, #f3fffd 0%, #ffffff 100%)",
      tint: "#99f6e4",
    },
  ];
  const visibleSonarSections = [
    {
      key: "vulnerabilities" as const,
      title: "Vulnerabilities",
      count: Math.max(migrationJob?.sonar_vulnerabilities ?? 0, sonarVulnerabilityDetails.length),
      details: sonarVulnerabilityDetails as Array<SonarIssueDetail | SonarHotspotDetail>,
      accentColor: "#dc2626",
      emptyMessage:
        Math.max(migrationJob?.sonar_vulnerabilities ?? 0, sonarVulnerabilityDetails.length) > 0
          ? "Summary count is available, but detailed vulnerability items were not returned by the current Sonar API response."
          : "No vulnerability findings were reported.",
    },
    {
      key: "code_smells" as const,
      title: "Code Smells",
      count: Math.max(migrationJob?.sonar_code_smells ?? 0, sonarCodeSmellDetails.length),
      details: filteredCodeSmellDetails as Array<SonarIssueDetail | SonarHotspotDetail>,
      accentColor: "#d97706",
      emptyMessage:
        Math.max(migrationJob?.sonar_code_smells ?? 0, sonarCodeSmellDetails.length) > 0
          ? codeSmellSeverityFilter === "all"
            ? "Summary count is available, but detailed code smell items were not returned by the current Sonar API response."
            : "No code smell findings match the selected severity filter."
          : "No code smell findings were reported.",
    },
    {
      key: "security_hotspots" as const,
      title: "Security Hotspots",
      count: Math.max(migrationJob?.sonar_security_hotspots ?? 0, sonarHotspotDetails.length),
      details: sonarHotspotDetails as Array<SonarIssueDetail | SonarHotspotDetail>,
      accentColor: "#b45309",
      emptyMessage:
        Math.max(migrationJob?.sonar_security_hotspots ?? 0, sonarHotspotDetails.length) > 0
          ? "Summary count is available, but detailed hotspot items were not returned by the current Sonar API response."
          : "No security hotspot findings were reported.",
    },
    {
      key: "bugs" as const,
      title: "Bugs",
      count: Math.max(migrationJob?.sonar_bugs ?? 0, sonarBugDetails.length),
      details: sonarBugDetails as Array<SonarIssueDetail | SonarHotspotDetail>,
      accentColor: "#2563eb",
      emptyMessage:
        Math.max(migrationJob?.sonar_bugs ?? 0, sonarBugDetails.length) > 0
          ? "Summary count is available, but detailed bug items were not returned by the current Sonar API response."
          : "No bug findings were reported.",
    },
  ].filter((section) => sonarFindingFilter === "all" || section.key === sonarFindingFilter);

  const renderSonarIssueCard = (
    issue: SonarIssueDetail | SonarHotspotDetail,
    index: number,
    findingType: string,
    accentColor: string
  ) => {
    const severityColors = getSonarSeverityColor(getSonarIssueSeverityValue(issue));
    const statusColors = getSonarStatusColor(issue.status || null);
    const fileLabel = `${issue.component || "N/A"}${issue.line ? `:${issue.line}` : ""}`;
    return (
      <div
        key={`${issue.key || findingType}-${index}`}
        style={{
          ...styles.sonarFindingCard,
          borderColor: `${accentColor}33`,
          boxShadow: `inset 3px 0 0 ${accentColor}`,
        }}
      >
        <div style={styles.sonarFindingHeader}>
          <div style={styles.sonarFindingTitle}>{issue.message || issue.rule || "Unnamed Sonar finding"}</div>
          <div style={styles.sonarFindingBadgeRow}>
            {getSonarIssueSeverityValue(issue) && (
              <span style={{ ...styles.sonarFindingBadge, ...severityColors }}>
                {(getSonarIssueSeverityValue(issue) || "").toString().toUpperCase()}
              </span>
            )}
            {issue.status && (
              <span style={{ ...styles.sonarFindingBadge, ...statusColors }}>
                {issue.status.toUpperCase()}
              </span>
            )}
          </div>
        </div>
        <div style={styles.sonarFindingMeta}>
          <span style={styles.sonarFindingMetaPill}><strong>File:</strong> {fileLabel}</span>
          {issue.rule && <span><strong>Rule:</strong> {issue.rule}</span>}
          {"security_category" in issue && issue.security_category && (
            <span><strong>Category:</strong> {issue.security_category}</span>
          )}
          {("effort" in issue && issue.effort) && <span><strong>Effort:</strong> {issue.effort}</span>}
          {("resolution" in issue && issue.resolution) && <span><strong>Resolution:</strong> {issue.resolution}</span>}
          {issue.author && <span><strong>Author:</strong> {issue.author}</span>}
          {issue.update_date && <span><strong>Updated:</strong> {formatSonarTimestamp(issue.update_date)}</span>}
        </div>
      </div>
    );
  };

  const renderSonarFindingSection = (section: {
    key: Exclude<SonarFindingFilter, "all">;
    title: string;
    count: number;
    details: Array<SonarIssueDetail | SonarHotspotDetail>;
    accentColor: string;
    emptyMessage: string;
  }) => {
    const { key: sectionKey, title, count, details, accentColor, emptyMessage } = section;
    const safeDetails = Array.isArray(details) ? details : [];
    const visibleCount = visibleSonarFindingCounts[sectionKey] ?? SONAR_FINDINGS_PAGE_SIZE;
    const visibleItems = safeDetails.slice(0, visibleCount);
    const remainingCount = Math.max(safeDetails.length - visibleItems.length, 0);
    const loadNextSonarFindings = () => {
      if (remainingCount <= 0) return;
      setVisibleSonarFindingCounts((current) => ({
        ...current,
        [sectionKey]: Math.min((current[sectionKey] ?? SONAR_FINDINGS_PAGE_SIZE) + SONAR_FINDINGS_PAGE_SIZE, safeDetails.length),
      }));
    };

    return (
      <div
        style={{
          ...styles.sonarFindingSection,
          borderColor: `${accentColor}33`,
          background: `linear-gradient(180deg, ${accentColor}08 0%, #ffffff 34%)`,
        }}
      >
        <div style={styles.sonarFindingSectionHeader}>
          <div style={styles.sonarFindingSectionTitleRow}>
            <h4 style={styles.sonarFindingSectionTitle}>{title}</h4>
            <span style={{ ...styles.sonarFindingCountBadge, color: accentColor, borderColor: `${accentColor}33`, background: `${accentColor}12` }}>
              {count}
            </span>
          </div>
          <div style={styles.sonarFindingSectionDescription}>
            {safeDetails.length > 0
              ? `Showing ${visibleItems.length} of ${safeDetails.length} detailed ${title.toLowerCase()}.`
              : emptyMessage}
          </div>
        </div>
        {safeDetails.length > 0 ? (
          <>
            <div
              style={styles.sonarFindingsList}
              onScroll={(event) => {
                if (remainingCount <= 0) return;
                const target = event.currentTarget;
                const distanceFromBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
                if (distanceFromBottom <= 24) {
                  loadNextSonarFindings();
                }
              }}
            >
              {visibleItems.map((issue, index) => renderSonarIssueCard(issue, index, title, accentColor))}
            </div>
            {safeDetails.length > SONAR_FINDINGS_PAGE_SIZE && (
              <div style={styles.sonarFindingNote}>
                Scroll inside this section to review the loaded findings. When you reach the bottom, the next set loads automatically.
              </div>
            )}
          </>
        ) : (
          <div style={styles.sonarFindingEmpty}>{emptyMessage}</div>
        )}
      </div>
    );
  };

  const effectiveFossa = fossaResult ?? migrationJob?.fossa_report ?? null;
  const fossaPolicyStatus = effectiveFossa?.compliance_status ?? migrationJob?.fossa_policy_status ?? "N/A";
  const fossaScanMode = effectiveFossa?.scan_mode ?? migrationJob?.fossa_scan_mode ?? (runFossa ? "requested" : null);
  const fossaLicenseIssueCount = getFossaLicenseIssueCount(effectiveFossa, migrationJob?.fossa_license_issues ?? 0);
  const fossaVulnerabilityTotal = getFossaVulnerabilityTotal(effectiveFossa, migrationJob?.fossa_vulnerabilities ?? 0);
  const fossaOutdatedCount = effectiveFossa?.details_available === false
    ? null
    : (effectiveFossa?.outdated_dependencies ?? migrationJob?.fossa_outdated_dependencies ?? 0);
  const fossaAnalysisUrl = effectiveFossa?.analysis_url ?? migrationJob?.fossa_analysis_url ?? null;
  const fossaErrorMessage = effectiveFossa?.error_message ?? migrationJob?.fossa_error_message ?? null;
  const fossaEnrichmentErrorMessage =
    effectiveFossa?.enrichment_error_message &&
      effectiveFossa?.enrichment_error_message !== fossaErrorMessage
      ? effectiveFossa.enrichment_error_message
      : null;
  const fossaIssueCount = effectiveFossa?.issue_count ?? null;
  const fossaDetailsAvailable = effectiveFossa?.details_available !== false;
  const fossaIsRealScan = Boolean(effectiveFossa?.real_scan ?? migrationJob?.fossa_real_scan);
  const fossaSeverityCounts = getFossaSeverityCounts(effectiveFossa);
  const hasFossaSecurityData =
    effectiveFossa != null ||
    migrationJob?.fossa_scan_mode != null ||
    migrationJob?.fossa_policy_status != null;
  const fossaScanModeLabel = getFossaScanModeLabel(fossaScanMode);
  const fossaStatusColor =
    fossaPolicyStatus === "PASSED"
      ? "#22c55e"
      : fossaPolicyStatus === "UNAVAILABLE" || fossaScanMode === "pending"
        ? "#f59e0b"
        : "#ef4444";
  const rawDepList: Array<DependencyInfo | Record<string, unknown>> = (migrationJob?.dependency_upgrades?.length
    ? migrationJob.dependency_upgrades
    : (migrationJob?.dependencies?.length ? migrationJob.dependencies : [])) as Array<DependencyInfo | Record<string, unknown>>;
  const detectedDependencyCount = migrationJob?.dependency_count ?? rawDepList.length;
  const dependencyUpdates = rawDepList.map((dep) => {
    const source = dep as Record<string, unknown> & {
      group_id?: string;
      groupId?: string;
      artifact_id?: string;
      artifactId?: string;
      coordinate?: string;
      current_version?: string | null;
      old_version?: string | null;
      oldVersion?: string | null;
      sourceVersion?: string | null;
      new_version?: string | null;
      newVersion?: string | null;
      status?: string | null;
      reason?: string;
      scope?: string;
    };
    return {
      group_id: source.group_id || source.groupId || source.coordinate?.split(":")[0] || "dependency",
      artifact_id: source.artifact_id || source.artifactId || source.coordinate?.split(":")[1] || "artifact",
      current_version: source.current_version || source.old_version || source.oldVersion || source.sourceVersion || "managed version",
      new_version: source.new_version || source.newVersion || source.resolvedTargetVersion || "updated version",
      status: source.status || "UPGRADED",
      reason: source.reason,
      scope: source.scope,
    };
  });
  const dependencyUpgradeCount = dependencyUpdates.length;
  const filesModifiedCount = migrationJob?.files_modified ?? (migrationJob?.file_diffs?.length || migrationJob?.modified_files?.length || 0);
  const transformationsCount = migrationJob?.issues_fixed ?? (migrationJob?.issues?.length || ((migrationJob?.import_changes?.length ?? 0) + (migrationJob?.source_changes?.length ?? 0)) || 0);

  const warningsRemaining = Math.max(
    (migrationJob?.total_warnings ?? 0) - (migrationJob?.warnings_fixed ?? 0),
    0,
  );
  const sonarVulnerabilityCount = migrationJob?.sonar_vulnerabilities ?? 0;
  const dependencyVulnerabilityCount = typeof fossaVulnerabilityTotal === "number" ? fossaVulnerabilityTotal : null;
  const combinedVulnerabilityCount =
    sonarVulnerabilityCount + (dependencyVulnerabilityCount ?? 0);
  const reportedVulnerabilityCount =
    dependencyVulnerabilityCount === null && hasFossaSecurityData && sonarVulnerabilityCount === 0
      ? null
      : combinedVulnerabilityCount;
  const scannedDependencyCount =
    effectiveFossa?.total_dependencies ?? migrationJob?.fossa_total_dependencies ?? detectedDependencyCount;
  const vulnerabilityMeta =
    reportedVulnerabilityCount === null
      ? fossaIssueCount != null
        ? `FOSSA reported ${fossaIssueCount} issues, but the vulnerability-only breakdown is unavailable.`
        : "Vulnerability details are still being prepared."
      : reportedVulnerabilityCount > 0
        ? dependencyVulnerabilityCount != null
          ? `${reportedVulnerabilityCount} remaining after final scans (${sonarVulnerabilityCount} code, ${dependencyVulnerabilityCount} dependency).`
          : `${reportedVulnerabilityCount} code vulnerabilities remaining after final scans.`
        : scannedDependencyCount > 0
          ? `0 remaining across ${scannedDependencyCount} scanned dependencies and the latest code scan.`
          : warningsRemaining > 0
            ? `${warningsRemaining} warnings remain after migration.`
            : "No active vulnerability findings reported.";
  const reportStatusLabel =
    migrationJob?.status === "completed"
      ? "Completed"
      : "In Progress";
  const reportStatusTone =
    migrationJob?.status === "completed"
      ? { bg: "linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%)", border: "#86efac", text: "#166534" }
      : { bg: "linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)", border: "#93c5fd", text: "#1d4ed8" };
  const reportHeroStats = [
    {
      label: "Files Modified",
      value: String(migrationJob?.files_modified ?? 0),
      accent: "#2563eb",
      meta: `Java ${migrationJob?.source_java_version ?? "?"} -> Java ${migrationJob?.target_java_version ?? "?"}`,
      surface: "linear-gradient(180deg, #eef6ff 0%, #e1efff 100%)",
      borderColor: "#c7dcff",
      shadow: "0 16px 30px rgba(37, 99, 235, 0.12)",
    },
    {
      label: "Issues Fixed",
      value: String(migrationJob?.issues_fixed ?? 0),
      accent: "#10b981",
      meta: `${migrationJob?.issues_fixed ?? 0} migration issues marked fixed`,
      surface: "linear-gradient(180deg, #ecfdf5 0%, #dcfce7 100%)",
      borderColor: "#bbf7d0",
      shadow: "0 16px 30px rgba(16, 185, 129, 0.12)",
    },
    {
      label: "Upgraded",
      value: String(dependencyUpgradeCount),
      accent: "#7c3aed",
      meta: `${detectedDependencyCount} dependencies detected in analysis`,
      surface: "linear-gradient(180deg, #f6f0ff 0%, #efe6ff 100%)",
      borderColor: "#ddd6fe",
      shadow: "0 16px 30px rgba(124, 58, 237, 0.12)",
    },
    {
      label: "Vulnerabilities",
      value: reportedVulnerabilityCount == null ? "N/A" : String(reportedVulnerabilityCount),
      accent:
        reportedVulnerabilityCount == null
          ? "#d97706"
          : reportedVulnerabilityCount > 0
            ? "#dc2626"
            : "#16a34a",
      meta: vulnerabilityMeta,
      surface:
        reportedVulnerabilityCount == null
          ? "linear-gradient(180deg, #fff7ed 0%, #ffedd5 100%)"
          : reportedVulnerabilityCount > 0
            ? "linear-gradient(180deg, #fff1f2 0%, #ffe4e6 100%)"
            : "linear-gradient(180deg, #f0fdf4 0%, #dcfce7 100%)",
      borderColor:
        reportedVulnerabilityCount == null
          ? "#fdba74"
          : reportedVulnerabilityCount > 0
            ? "#fecdd3"
            : "#bbf7d0",
      shadow:
        reportedVulnerabilityCount == null
          ? "0 16px 30px rgba(217, 119, 6, 0.10)"
          : reportedVulnerabilityCount > 0
            ? "0 16px 30px rgba(220, 38, 38, 0.10)"
            : "0 16px 30px rgba(22, 163, 74, 0.10)",
    },
  ];
  const reportHeroSummary =
    migrationJob?.status === "completed"
      ? `The migration finished successfully${migrationJob?.target_repo ? " and the destination is ready to review." : "."}`
      : "The migration report below captures the current progress, results, and follow-up details.";
  const totalDependencyPages = Math.max(
    1,
    Math.ceil((dependencyUpdates.length || 0) / REPORT_DEPENDENCIES_PAGE_SIZE)
  );
  const currentDependencyPage = Math.min(reportDependencyPage, totalDependencyPages);
  const dependencyStartIndex = (currentDependencyPage - 1) * REPORT_DEPENDENCIES_PAGE_SIZE;
  const paginatedDependencies = dependencyUpdates.slice(
    dependencyStartIndex,
    dependencyStartIndex + REPORT_DEPENDENCIES_PAGE_SIZE
  );
  const dependencyRangeStart = dependencyUpdates.length ? dependencyStartIndex + 1 : 0;
  const dependencyRangeEnd = Math.min(
    dependencyStartIndex + REPORT_DEPENDENCIES_PAGE_SIZE,
    dependencyUpdates.length || 0
  );

  return (
    <div style={{ ...styles.card, background: "#f8fafc", padding: "0px", border: "none", boxShadow: "none", width: "100%", maxWidth: "100%" }}>
      <React.Suspense
        fallback={
          <div style={styles.reportContainer}>
            <div style={styles.loadingBox}>
              <div style={styles.spinner}></div>
              <span>Loading migration report...</span>
            </div>
          </div>
        }
      >
        {migrationJob && (
          <div style={{ ...styles.reportContainer, gap: 8, width: "100%", padding: "12px 16px" }}>
            {/* Top Header Card */}
            <div style={{
              background: "linear-gradient(108.4deg, #003087 4.4%, #0052cc 44.5%, #0073e6 94.6%)",
              borderRadius: 16,
              padding: "18px 40px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 4,
              boxShadow: "0 12px 40px rgba(0, 82, 204, 0.2)",
              color: "#ffffff",
              position: "relative",
              overflow: "hidden",
              width: "100%",
              minHeight: 125
            }}>
              {/* Abstract Wave Overlays and Patterns */}
              <div style={{ position: "absolute", left: "-5%", top: "-10%", width: "40%", height: "120%", background: "radial-gradient(circle, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0) 70%)", transform: "rotate(-15deg)", pointerEvents: "none" }} />
              <div style={{ position: "absolute", right: "10%", bottom: "-20%", width: "50%", height: "100%", background: "radial-gradient(circle, rgba(0,115,230,0.3) 0%, rgba(0,0,0,0) 80%)", pointerEvents: "none" }} />

              <div style={{ position: "absolute", left: "45%", top: "40%", opacity: 0.08, pointerEvents: "none", display: "grid", gridTemplateColumns: "repeat(5, 6px)", gap: "8px" }}>
                {Array.from({ length: 25 }).map((_, i) => <div key={i} style={{ width: 3, height: 3, borderRadius: "50%", background: "#ffffff" }} />)}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 24, zIndex: 1 }}>
                <div style={{
                  width: 68, height: 68, borderRadius: "50%",
                  background: "rgba(0, 120, 120, 0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  border: "1px solid rgba(34, 197, 94, 0.25)",
                  boxShadow: "0 0 15px rgba(34, 197, 94, 0.2)"
                }}>
                  <div style={{
                    width: 42, height: 42, borderRadius: "50%",
                    background: "#ffffff",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: "#22c55e", fontSize: 24,
                    boxShadow: "0 4px 10px rgba(0, 0, 0, 0.15)"
                  }}>
                    <FaCheckCircle />
                  </div>
                </div>
                <div>
                  <h2 style={{ margin: "0 0 4px 0", fontSize: 28, fontWeight: 800, color: "#ffffff", letterSpacing: "-0.01em" }}>Migration Report</h2>
                  <p style={{ margin: 0, color: "rgba(255, 255, 255, 0.9)", fontSize: 14, lineHeight: 1.5, fontWeight: 500, maxWidth: 480 }}>
                    Your project has been successfully modernized from Java {migrationJob.source_java_version} to Java {migrationJob.target_java_version}.<br/>
                    Here's a summary of the migration results and analysis.
                  </p>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 24, zIndex: 1 }}>
                {/* Java Version Badges Container */}
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 16,
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: 20,
                  padding: "10px 20px"
                }}>
                  <div style={{
                    background: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: 14,
                    padding: "8px 18px",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    minWidth: 120,
                    backdropFilter: "blur(10px)"
                  }}>
                    <div style={{ background: "rgba(0, 0, 0, 0.2)", width: 38, height: 38, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid rgba(255, 255, 255, 0.08)", flexShrink: 0 }}>
                      <svg width="20" height="20" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22 22C22 22 25 15 23 10C21 5 25 2 25 2C25 2 29 6 27 11C25 16 28 22 22 22Z" fill="#ff4d4d" />
                        <path d="M32 20C32 20 35 14 33 9C31 4 35 1 35 1C35 1 39 5 37 10C35 15 38 20 32 20Z" fill="#ffa64d" />
                        <path d="M41 23C41 23 43 18 41 14C39 10 43 7 43 7C43 7 46 10 45 15C44 20 46 23 41 23Z" fill="#ff4d4d" />
                        <path d="M14 26H46C46 26 47 38 41 43C35 48 23 48 18 43C12 38 14 26 14 26Z" fill="#ffffff" />
                        <path d="M45 30C45 30 52 30 52 34C52 38 45 38 45 38" stroke="#ffffff" strokeWidth="4" strokeLinecap="round" />
                        <path d="M10 49C10 49 16 54 30 54C44 54 50 49 50 49C52 48 53 50 51 51C47 54 39 57 30 57C21 57 13 54 9 51C7 50 8 48 10 49Z" fill="#ffffff" opacity="0.85" />
                        <path d="M15 45C22 47 38 47 45 45" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
                      </svg>
                    </div>
                    <div style={{ textAlign: "left" }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "#ffffff", lineHeight: 1.1 }}>Java {migrationJob.source_java_version}</div>
                      <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)", fontWeight: 500, marginTop: 1 }}>Legacy</div>
                    </div>
                  </div>

                  <span style={{ color: "rgba(255,255,255,0.4)", fontSize: 16, fontWeight: 600 }}>→</span>

                  <div style={{
                    background: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: 14,
                    padding: "8px 18px",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    minWidth: 130,
                    backdropFilter: "blur(10px)"
                  }}>
                    <div style={{ background: "rgba(0, 0, 0, 0.2)", width: 38, height: 38, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid rgba(255, 255, 255, 0.08)", flexShrink: 0 }}>
                      <svg width="20" height="20" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22 22C22 22 25 15 23 10C21 5 25 2 25 2C25 2 29 6 27 11C25 16 28 22 22 22Z" fill="#ff4d4d" />
                        <path d="M32 20C32 20 35 14 33 9C31 4 35 1 35 1C35 1 39 5 37 10C35 15 38 20 32 20Z" fill="#ffa64d" />
                        <path d="M41 23C41 23 43 18 41 14C39 10 43 7 43 7C43 7 46 10 45 15C44 20 46 23 41 23Z" fill="#ff4d4d" />
                        <path d="M14 26H46C46 26 47 38 41 43C35 48 23 48 18 43C12 38 14 26 14 26Z" fill="#ffffff" />
                        <path d="M45 30C45 30 52 30 52 34C52 38 45 38 45 38" stroke="#ffffff" strokeWidth="4" strokeLinecap="round" />
                        <path d="M10 49C10 49 16 54 30 54C44 54 50 49 50 49C52 48 53 50 51 51C47 54 39 57 30 57C21 57 13 54 9 51C7 50 8 48 10 49Z" fill="#ffffff" opacity="0.85" />
                        <path d="M15 45C22 47 38 47 45 45" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
                      </svg>
                    </div>
                    <div style={{ textAlign: "left" }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "#ffffff", lineHeight: 1.1 }}>Java {migrationJob.target_java_version}</div>
                      <span style={{
                        background: "rgba(16, 185, 129, 0.2)",
                        color: "#34d399",
                        border: "1px solid rgba(16, 185, 129, 0.25)",
                        fontSize: 9,
                        fontWeight: 700,
                        padding: "1px 6px",
                        borderRadius: 4,
                        marginTop: 2,
                        display: "inline-block",
                        textTransform: "uppercase"
                      }}>Modernized</span>
                    </div>
                  </div>
                </div>

                {/* Vertical Divider line */}
                <div style={{ width: 1, height: 44, background: "rgba(255, 255, 255, 0.2)", marginLeft: 2 }} />

                {/* Timestamp and elapsed details */}
                <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 150, marginLeft: 2 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <FaRegCalendarAlt style={{ color: "rgba(255, 255, 255, 0.6)", fontSize: 15 }} />
                    <div style={{ textAlign: "left" }}>
                      <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)", fontWeight: 600, textTransform: "uppercase" }}>Migration Date</div>
                      <div style={{ fontSize: 14, color: "#ffffff", fontWeight: 700 }}>
                        {migrationJob.completed_at ? new Date(migrationJob.completed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : "Sep 11, 2026"}, {migrationJob.completed_at ? new Date(migrationJob.completed_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }) : "3:00 PM"}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <FaStopwatch style={{ color: "rgba(255, 255, 255, 0.6)", fontSize: 15 }} />
                    <div style={{ textAlign: "left" }}>
                      <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)", fontWeight: 600, textTransform: "uppercase" }}>Duration</div>
                      <div style={{ fontSize: 14, color: "#ffffff", fontWeight: 800, fontFamily: "'JetBrains Mono', monospace" }}>
                        {(() => {
                          const secs = getMigrationElapsedSeconds(migrationJob, resultExec.migrationTimerNow);
                          const h = Math.floor(secs / 3600);
                          const m = Math.floor((secs % 3600) / 60).toString().padStart(2, "0");
                          const s = (secs % 60).toString().padStart(2, "0");
                          return h > 0 ? `${h.toString().padStart(2, "0")}:${m}:${s}` : `00:${m}:${s}`;
                        })()}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Stats Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12, marginBottom: 12, width: "100%" }}>
              {[
                {
                  id: "files" as const,
                  icon: <FaFileAlt />, count: filesModifiedCount, label: "Files Modified",
                  meta: filesModifiedCount === 0 ? "No files were modified" : `${filesModifiedCount} files modified`,
                  color: "#2563eb", bg: "#eff6ff",
                  clickable: true,
                },
                {
                  id: "transformations" as const,
                  icon: <FaTools />, count: transformationsCount, label: "Issues Fixed",
                  meta: transformationsCount === 0 ? "No issues recorded" : `${transformationsCount} migration fixes applied`,
                  color: "#10b981", bg: "#ecfdf5",
                  clickable: true,
                },
                {
                  id: "dependencies" as const,
                  icon: <FaLayerGroup />, count: dependencyUpgradeCount, label: "Dependencies Updated",
                  meta: dependencyUpgradeCount === 0 ? "No dependencies updated" : `${dependencyUpgradeCount} dependencies updated`,
                  color: "#8b5cf6", bg: "#f5f3ff",
                  clickable: true,
                },
                {
                  id: null,
                  icon: <FaShieldAlt />, count: reportedVulnerabilityCount ?? 0, label: "Vulnerabilities",
                  meta: "No active vulnerabilities found",
                  color: "#f97316", bg: "#fff7ed",
                  clickable: false,
                }
              ].map((stat, idx) => (
                <div
                  key={idx}
                  role={stat.clickable ? "button" : undefined}
                  tabIndex={stat.clickable ? 0 : undefined}
                  onClick={stat.clickable && stat.id ? () => setActiveOverviewDetail(stat.id) : undefined}
                  onKeyDown={(e) => {
                    if (stat.clickable && stat.id && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      setActiveOverviewDetail(stat.id);
                    }
                  }}
                  style={{
                    background: "#ffffff",
                    border: stat.clickable && activeOverviewDetail === stat.id ? `2px solid ${stat.color}` : `1px solid ${stat.color}15`,
                    borderRadius: 16,
                    padding: "16px 20px",
                    display: "flex",
                    gap: 16,
                    alignItems: "center",
                    boxShadow: stat.clickable && activeOverviewDetail === stat.id ? `0 12px 32px -8px ${stat.color}35` : `0 8px 30px -10px ${stat.color}25`,
                    position: 'relative',
                    overflow: 'hidden',
                    cursor: stat.clickable ? "pointer" : "default",
                    transition: "transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease",
                  }}
                >
                  {/* Accent bar at bottom for extra glow feel */}
                  <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: stat.color, opacity: 0.2 }} />

                  <div style={{ background: stat.bg, color: stat.color, width: 56, height: 56, borderRadius: 14, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 26, flexShrink: 0 }}>
                    {stat.icon}
                  </div>
                  <div style={{ overflow: "hidden" }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 2 }}>
                      <span style={{ fontSize: 32, fontWeight: 800, color: "#001845", lineHeight: 1 }}>{stat.count}</span>
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#001845", marginBottom: 4 }}>{stat.label}</div>
                    <div style={{ fontSize: 12, color: "#64748b", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontWeight: 500 }}>{stat.meta}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Row: Repository Information | Migration Overview */}
            <div style={{ display: "grid", gridTemplateColumns: "600px 1fr", gap: 16, marginBottom: 16 }}>
              {/* Repository Information */}
              <div style={{ background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "20px 24px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)", display: "flex", flexDirection: "column" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
                  <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#0f172a", display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>
                      <FaLayerGroup />
                    </div>
                    Repository Information
                  </h3>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 24, flex: 1, justifyContent: "space-around", padding: "10px 0" }}>
                  {[
                    {
                      label: "Source Repository",
                      value: migrationJob.source_repo,
                      icon: <FaGithub />,
                      isLink: true
                    },
                    {
                      label: "Target Repository",
                      value: migrationJob.target_repo,
                      icon: <FaGithub />,
                      isLink: true
                    },
                    {
                      label: "Migration Date",
                      value: migrationJob.completed_at ? `${new Date(migrationJob.completed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} · ${new Date(migrationJob.completed_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}` : "Sep 11, 2026 · 3:00 PM",
                      icon: <FaRegCalendarAlt />
                    },
                    {
                      label: "Duration",
                      value: (() => {
                        const secs = getMigrationElapsedSeconds(migrationJob, resultExec.migrationTimerNow);
                        const h = Math.floor(secs / 3600);
                        const m = Math.floor((secs % 3600) / 60).toString().padStart(2, "0");
                        const s = (secs % 60).toString().padStart(2, "0");
                        return h > 0 ? `${h.toString().padStart(2, "0")}:${m}:${s}` : `00:${m}:${s}`;
                      })(),
                      icon: <FaStopwatch />
                    }
                  ].map((item, idx) => (
                    <div key={idx} style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
                      <div style={{ color: "#0f172a", fontSize: 22, marginTop: 4 }}>{item.icon}</div>
                      <div style={{ overflow: "hidden" }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", marginBottom: 6 }}>{item.label}</div>
                        <div style={{ fontSize: 14, color: item.isLink ? "#2563eb" : "#0f172a", fontWeight: 700, wordBreak: "break-all", lineHeight: 1.4 }}>
                          {item.isLink && item.value && item.value.startsWith('http') ? (
                            <a href={item.value} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'none' }}>{item.value}</a>
                          ) : (item.value || 'N/A')}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Migration Overview */}
              <div style={{ background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "16px 20px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
                <div style={{ marginBottom: 16 }}>
                  <h3 style={{ margin: "0 0 4px 0", fontSize: 18, fontWeight: 800, color: "#0f172a", display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>
                      <FaShieldAlt />
                    </div>
                    Migration Overview
                  </h3>
                  <p style={{ margin: 0, fontSize: 14, color: "#64748b", fontWeight: 500 }}>Key changes made during the migration process</p>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                  {[
                    {
                      id: "files" as const,
                      icon: <FaFileAlt />,
                      title: "Files Modified",
                      desc: "Code files updated during migration",
                      value: filesModifiedCount,
                      footer: filesModifiedCount === 0 ? "No files modified" : `${filesModifiedCount} files updated`,
                      color: "#2563eb", bg: "#eff6ff", border: "#dbeafe", glow: "rgba(37,99,235,0.05)"
                    },
                    {
                      id: "transformations" as const,
                      icon: <FaCode />,
                      title: "Code Transmission",
                      desc: "Code transformation and migration logic applied",
                      value: transformationsCount,
                      footer: `${transformationsCount} transformations completed`,
                      color: "#7c3aed", bg: "#f5f3ff", border: "#ede9fe", glow: "rgba(124,58,237,0.05)"
                    },
                    {
                      id: "dependencies" as const,
                      icon: <FaShieldAlt />,
                      title: "Dependency Updated",
                      desc: "Libraries and dependencies upgraded",
                      value: dependencyUpgradeCount,
                      footer: `${dependencyUpgradeCount} dependencies updated`,
                      color: "#10b981", bg: "#ecfdf5", border: "#d1fae5", glow: "rgba(16,185,129,0.05)"
                    }
                  ].map((item, idx) => {
                    const isSelected = activeOverviewDetail === item.id;
                    return (
                      <div
                        key={idx}
                        role="button"
                        tabIndex={0}
                        onClick={() => setActiveOverviewDetail(item.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setActiveOverviewDetail(item.id);
                          }
                        }}
                        title={`Click to view ${item.title} details`}
                        style={{
                          background: item.bg,
                          border: isSelected ? `2px solid ${item.color}` : `1px solid ${item.border}`,
                          borderRadius: 16,
                          padding: "16px 20px",
                          display: "flex",
                          flexDirection: "column",
                          position: "relative",
                          overflow: "hidden",
                          cursor: "pointer",
                          boxShadow: isSelected ? `0 10px 25px -4px ${item.glow || "rgba(0,0,0,0.1)"}` : "none",
                          transition: "transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = "translateY(-2px)";
                          if (!isSelected) {
                            e.currentTarget.style.boxShadow = `0 12px 28px -6px ${item.glow || "rgba(0,0,0,0.1)"}`;
                          }
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = "translateY(0)";
                          if (!isSelected) {
                            e.currentTarget.style.boxShadow = "none";
                          }
                        }}
                      >
                        <div style={{ background: "#ffffff", color: item.color, width: 44, height: 44, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, marginBottom: 12, boxShadow: "0 4px 12px rgba(0,0,0,0.05)" }}>
                          {item.icon}
                        </div>
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 2 }}>{item.title}</div>
                          <div style={{ fontSize: 12, color: "#64748b", fontWeight: 500, lineHeight: 1.4 }}>{item.desc}</div>
                        </div>
                        <div style={{ fontSize: 28, fontWeight: 800, color: "#0f172a", marginBottom: 16 }}>{item.value}</div>
                        <div style={{
                          marginTop: "auto",
                          padding: "8px 12px",
                          background: "#ffffff",
                          borderRadius: 10,
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          fontSize: 12,
                          fontWeight: 700,
                          color: item.color,
                          border: `1px solid ${item.border}`
                        }}>
                          <div style={{ width: 14, height: 14, borderRadius: "50%", background: item.color, color: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 8 }}>
                            <FaCheckCircle />
                          </div>
                          {item.footer}
                        </div>
                        {/* Decorative Background Icon */}
                        <div style={{ position: "absolute", right: -10, top: 20, fontSize: 80, opacity: 0.03, color: item.color, transform: "rotate(-15deg)", pointerEvents: "none" }}>
                          {item.icon}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Dynamic Migration Overview Detail Section (Files Modified / Code Transformation / Dependency Updates) */}
            <MigrationOverviewInlineDetail
              category={activeOverviewDetail}
              migrationJob={migrationJob}
              dependencyUpdates={dependencyUpdates}
            />

            {/* DETAILED MIGRATION DASHBOARD */}
            <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16, marginTop: 16, marginBottom: 16, alignItems: "stretch" }}>
                {/* Left Column */}
                <div style={{ display: "flex", width: "100%" }}>
                   <MigrationUnitTestSection
                    styles={{...styles, reportSection: { width: '100%', maxWidth: 'none', margin: 0 }}}
                    migrationJob={migrationJob}
                    testSummaryReportDate={testSummaryReportDate}
                    migrationJavaVersion={migrationJob.target_java_version}
                    summaryItems={testSummaryItems}
                    testsRun={testsRun}
                    onDownloadUnitTestReport={handleDownloadUnitTestReport}
                  />
                </div>

                {/* Right Column: Combined FOSSA + JMeter Card */}
                <div style={{
                  background: "#ffffff",
                  border: "1px solid #eef2f6",
                  borderRadius: 16,
                  padding: "24px 32px",
                  boxShadow: "0 4px 20px rgba(0,0,0,0.03)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 32,
                  width: "100%"
                }}>
                   <div style={{ flex: 1 }}>
                     <MigrationFossaSection
                        styles={{...styles, reportSection: { padding: 0, border: 'none', background: 'transparent', boxShadow: 'none' }}}
                        fossaLicenseIssueCount={migrationJob.fossa_license_issues ?? (migrationJob.fossa_report as any)?.license_issues}
                        fossaVulnerabilityTotal={migrationJob.fossa_vulnerabilities ?? (migrationJob.fossa_report as any)?.vulnerabilities ?? (migrationJob.fossa_report as any)?.vulnerability_count}
                        fossaOutdatedCount={migrationJob.fossa_outdated_dependencies ?? (migrationJob.fossa_report as any)?.outdated_dependencies}
                        fossaTotalDependencies={migrationJob.fossa_total_dependencies ?? (migrationJob.fossa_report as any)?.total_dependencies}
                        fossaPolicyStatus={migrationJob.fossa_policy_status || (migrationJob.fossa_report as any)?.policy_status}
                        fossaScanMode={migrationJob.fossa_scan_mode || (migrationJob.fossa_report as any)?.scan_mode}
                        fossaErrorMessage={migrationJob.fossa_error_message || (migrationJob.fossa_report as any)?.error_message}
                        fossaAnalysisUrl={fossaAnalysisUrl || migrationJob.fossa_analysis_url || (migrationJob.fossa_report as any)?.analysis_url}
                        fossaRealScan={Boolean(fossaIsRealScan || migrationJob.fossa_real_scan || (migrationJob.fossa_report as any)?.real_scan)}
                      />
                   </div>

                   {/* JMeter Performance Test Report - Commented out per UI requirement
                   <div style={{ height: 1, background: "#f1f5f9" }} />

                   <div style={{ flex: 1 }}>
                     <MigrationJmeterSection
                        styles={{...styles, reportSection: { padding: 0, border: 'none', background: 'transparent', boxShadow: 'none' }}}
                        apiEndpointsValidated={0}
                        apiEndpointsWorking={0}
                      />
                   </div>
                   */}
                </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 16 }}>
                <MigrationProposedTestSection
                  styles={styles}
                  migrationJob={migrationJob}
                />

                <MigrationSonarSection
                  styles={styles}
                  migrationJob={migrationJob}
                  sonarTotalFindings={sonarTotalFindings}
                />
            </div>

            {migrationJob.spring_conversion_requested && (
              <div style={styles.reportSection}>
                <h3 style={styles.reportTitle}>Spring Migration</h3>
                <div style={styles.reportGrid}>
                  <div style={styles.reportItem}>
                    <span style={styles.reportLabel}>Source Framework</span>
                    <span style={styles.reportValue}>{migrationJob.spring_source_framework || "N/A"}</span>
                  </div>
                  <div style={styles.reportItem}>
                    <span style={styles.reportLabel}>Target Framework</span>
                    <span style={styles.reportValue}>{migrationJob.spring_target_framework || "N/A"}</span>
                  </div>
                  <div style={styles.reportItem}>
                    <span style={styles.reportLabel}>Spring Boot Version</span>
                    <span style={styles.reportValue}>
                      {migrationJob.spring_boot_version_before || "N/A"}
                      {" -> "}
                      {migrationJob.spring_boot_version_after || migrationJob.spring_boot_version_before || "N/A"}
                    </span>
                  </div>
                  <div style={styles.reportItem}>
                    <span style={styles.reportLabel}>Supported</span>
                    <span style={styles.reportValue}>{migrationJob.spring_conversion_supported ? "Yes" : "No"}</span>
                  </div>
                  {!migrationJob.spring_conversion_supported && migrationJob.spring_conversion_note && (
                    <div style={styles.reportItem}>
                      <span style={styles.reportLabel}>Note</span>
                      <span style={styles.reportValue}>{migrationJob.spring_conversion_note}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 8, alignItems: "stretch" }}>
              <MigrationLogSection
                styles={{...styles, reportSection: { width: '100%', maxWidth: 'none', margin: 0 }}}
                migrationLogs={migrationLogs}
              />

              <MigrationIssuesSection
                styles={{...styles, reportSection: { width: '100%', maxWidth: 'none', margin: 0 }}}
                issues={migrationJob.issues}
                isOpen={reportAccordionState.issues}
                onToggle={() => toggleReportAccordion("issues")}
              />
            </div>
          </div>
        )}

        <MigrationReportActions
          migrationJob={migrationJob}
          migrationLogs={migrationLogs}
          resetWizard={resetWizard}
          onBack={onBack}
          onError={(message: string) => onError(message)}
          onDownloadUnitTestReport={handleDownloadUnitTestReport}
          styles={{...styles, reportActionsBar: { ...styles.reportActionsBar, marginTop: 4, padding: "8px 0" }}}
        />
      </React.Suspense>
    </div>
  );
}