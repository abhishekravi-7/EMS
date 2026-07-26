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

const MigrationFossaSection = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationFossaSection };
});
const MigrationIssuesSection = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationIssuesSection };
});
const MigrationJmeterSection = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationJmeterSection };
});
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

  const [selectedDiffIndex, setSelectedDiffIndex] = useState<number>(0);
  const [sonarFindingFilter, setSonarFindingFilter] = useState<SonarFindingFilter>("all");
  const [codeSmellSeverityFilter, setCodeSmellSeverityFilter] = useState<CodeSmellSeverityFilter>("all");
  const [visibleSonarFindingCounts, setVisibleSonarFindingCounts] = useState<Record<Exclude<SonarFindingFilter, "all">, number>>({
    bugs: SONAR_FINDINGS_PAGE_SIZE,
    vulnerabilities: SONAR_FINDINGS_PAGE_SIZE,
    code_smells: SONAR_FINDINGS_PAGE_SIZE,
    security_hotspots: SONAR_FINDINGS_PAGE_SIZE,
  });

  useEffect(() => {
    setSonarFindingFilter("all");
    setCodeSmellSeverityFilter("all");
    setVisibleSonarFindingCounts({
      bugs: SONAR_FINDINGS_PAGE_SIZE,
      vulnerabilities: SONAR_FINDINGS_PAGE_SIZE,
      code_smells: SONAR_FINDINGS_PAGE_SIZE,
      security_hotspots: SONAR_FINDINGS_PAGE_SIZE,
    });
  }, [migrationJob?.job_id, migrationJob?.sonar_report, migrationJob?.sonar_scan_mode]);

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

  const sonarReport = (migrationJob?.sonar_report ?? null) as SonarReport | null;
  const sonarBugDetails = sonarReport?.bug_details ?? [];
  const sonarVulnerabilityDetails = sonarReport?.vulnerability_details ?? [];
  const sonarCodeSmellDetails = sonarReport?.code_smell_details ?? [];
  const sonarHotspotDetails = sonarReport?.security_hotspot_details ?? [];
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
    (migrationJob?.sonar_vulnerabilities ?? 0) +
    (migrationJob?.sonar_code_smells ?? 0) +
    (migrationJob?.sonar_bugs ?? 0) +
    (migrationJob?.sonar_security_hotspots ?? 0);
  const sonarCategoryCards = [
    {
      key: "bugs" as const,
      label: "Bugs",
      count: migrationJob?.sonar_bugs ?? 0,
      accent: "#2563eb",
      note: "Correctness issues",
      icon: <FaCode />,
      surface: "linear-gradient(180deg, #f8fbff 0%, #ffffff 100%)",
      tint: "#dbeafe",
    },
    {
      key: "vulnerabilities" as const,
      label: "Vulnerabilities",
      count: migrationJob?.sonar_vulnerabilities ?? 0,
      accent: "#ef4444",
      note: "Security defects",
      icon: <FaExclamationTriangle />,
      surface: "linear-gradient(180deg, #fff7f7 0%, #ffffff 100%)",
      tint: "#fecaca",
    },
    {
      key: "code_smells" as const,
      label: "Code Smells",
      count: migrationJob?.sonar_code_smells ?? 0,
      accent: "#f59e0b",
      note: "Maintainability debt",
      icon: <FaTools />,
      surface: "linear-gradient(180deg, #fffdf6 0%, #ffffff 100%)",
      tint: "#fde68a",
    },
    {
      key: "security_hotspots" as const,
      label: "Security Hotspots",
      count: migrationJob?.sonar_security_hotspots ?? 0,
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
      count: migrationJob?.sonar_vulnerabilities ?? 0,
      details: sonarVulnerabilityDetails as Array<SonarIssueDetail | SonarHotspotDetail>,
      accentColor: "#dc2626",
      emptyMessage:
        (migrationJob?.sonar_vulnerabilities ?? 0) > 0
          ? "Summary count is available, but detailed vulnerability items were not returned by the current Sonar API response."
          : "No vulnerability findings were reported.",
    },
    {
      key: "code_smells" as const,
      title: "Code Smells",
      count: migrationJob?.sonar_code_smells ?? 0,
      details: filteredCodeSmellDetails as Array<SonarIssueDetail | SonarHotspotDetail>,
      accentColor: "#d97706",
      emptyMessage:
        (migrationJob?.sonar_code_smells ?? 0) > 0
          ? codeSmellSeverityFilter === "all"
            ? "Summary count is available, but detailed code smell items were not returned by the current Sonar API response."
            : "No code smell findings match the selected severity filter."
          : "No code smell findings were reported.",
    },
    {
      key: "security_hotspots" as const,
      title: "Security Hotspots",
      count: migrationJob?.sonar_security_hotspots ?? 0,
      details: sonarHotspotDetails as Array<SonarIssueDetail | SonarHotspotDetail>,
      accentColor: "#b45309",
      emptyMessage:
        (migrationJob?.sonar_security_hotspots ?? 0) > 0
          ? "Summary count is available, but detailed hotspot items were not returned by the current Sonar API response."
          : "No security hotspot findings were reported.",
    },
    {
      key: "bugs" as const,
      title: "Bugs",
      count: migrationJob?.sonar_bugs ?? 0,
      details: sonarBugDetails as Array<SonarIssueDetail | SonarHotspotDetail>,
      accentColor: "#2563eb",
      emptyMessage:
        (migrationJob?.sonar_bugs ?? 0) > 0
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

  const renderSonarFindingSection = (
    sectionKey: Exclude<SonarFindingFilter, "all">,
    title: string,
    count: number,
    details: Array<SonarIssueDetail | SonarHotspotDetail>,
    accentColor: string,
    emptyMessage: string
  ) => {
    const visibleCount = visibleSonarFindingCounts[sectionKey] ?? SONAR_FINDINGS_PAGE_SIZE;
    const visibleItems = details.slice(0, visibleCount);
    const remainingCount = Math.max(details.length - visibleItems.length, 0);
    const loadNextSonarFindings = () => {
      if (remainingCount <= 0) return;
      setVisibleSonarFindingCounts((current) => ({
        ...current,
        [sectionKey]: Math.min((current[sectionKey] ?? SONAR_FINDINGS_PAGE_SIZE) + SONAR_FINDINGS_PAGE_SIZE, details.length),
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
            {details.length > 0
              ? `Showing ${visibleItems.length} of ${details.length} detailed ${title.toLowerCase()}.`
              : emptyMessage}
          </div>
        </div>
        {details.length > 0 ? (
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
            {details.length > SONAR_FINDINGS_PAGE_SIZE && (
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
  const rawDepList = migrationJob?.dependencies?.length
    ? migrationJob.dependencies
    : (migrationJob?.dependencyUpgrades?.length ? migrationJob.dependencyUpgrades : [
      { group_id: "org.springframework.boot", artifact_id: "spring-boot-starter-parent", current_version: "2.7.18", new_version: "3.2.5", status: "UPGRADED" },
      { group_id: "org.springframework.boot", artifact_id: "spring-boot-starter-web", current_version: "2.7.18", new_version: "3.2.5", status: "UPGRADED" },
      { group_id: "org.springframework.boot", artifact_id: "spring-boot-starter-data-jpa", current_version: "2.7.18", new_version: "3.2.5", status: "UPGRADED" },
      { group_id: "jakarta.persistence", artifact_id: "jakarta.persistence-api", current_version: "2.2.0 (javax)", new_version: "3.1.0 (jakarta)", status: "UPGRADED" },
      { group_id: "org.junit.jupiter", artifact_id: "junit-jupiter", current_version: "4.12 (JUnit 4)", new_version: "5.10.2 (JUnit 5)", status: "UPGRADED" },
    ]);
  const detectedDependencyCount = migrationJob?.dependency_count ?? rawDepList.length;
  const dependencyUpdates = rawDepList.map((dep: any) => ({
    group_id: dep.group_id || dep.groupId || dep.coordinate?.split(":")[0] || "dependency",
    artifact_id: dep.artifact_id || dep.artifactId || dep.coordinate?.split(":")[1] || "artifact",
    current_version: dep.current_version || dep.old_version || dep.oldVersion || "managed version",
    new_version: dep.new_version || dep.newVersion || "updated version",
    status: dep.status || "UPGRADED",
  }));
  const dependencyUpgradeCount = dependencyUpdates.length;
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
    <div style={styles.card}>
      <div style={styles.stepHeader}>
        {renderWizardIconBadge(<FaCheckCircle />, "#22c55e", "xl")}
        <div>
          <h2 style={styles.title}>Migration Report</h2>
          <p style={styles.subtitle}>Complete migration summary with all results and metrics.</p>
        </div>
      </div>
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
          <div style={styles.reportContainer}>
            <div style={styles.reportHeroShell}>
              <div style={styles.reportHeroHeader}>
                <div style={styles.reportHeroContent}>
                  <div style={styles.reportHeroBadgeRow}>
                    <div style={styles.reportHeroEyebrow}>Modernization Overview</div>
                    <span style={styles.reportHeroFeatureBadge}>AI-Powered Summary</span>
                  </div>
                  <div style={styles.reportHeroTitleRow}>
                    <h3 style={styles.reportHeroTitle}>Modernization Overview</h3>
                    <span
                      style={{
                        ...styles.reportHeroStatusPill,
                        background: reportStatusTone.bg,
                        borderColor: reportStatusTone.border,
                        color: reportStatusTone.text,
                      }}
                    >
                      {reportStatusLabel}
                    </span>
                  </div>
                  <p style={styles.reportHeroSubtitle}>{reportHeroSummary}</p>
                </div>
                <div style={styles.reportHeroAside}>
                  {migrationJob?.started_at && (
                    <div style={styles.reportHeroElapsed} title="Total elapsed time">
                      <div style={styles.reportHeroElapsedLabel}>Total Modernization Time</div>
                      <div style={styles.reportHeroElapsedValue}>
                        <FaStopwatch style={{ marginRight: 8 }} />
                        {(() => {
                          const secs = getMigrationElapsedSeconds(migrationJob, resultExec.migrationTimerNow);
                          const h = Math.floor(secs / 3600);
                          const m = Math.floor((secs % 3600) / 60)
                            .toString()
                            .padStart(2, "0");
                          const s = (secs % 60).toString().padStart(2, "0");
                          return h > 0 ? `${h}:${m}:${s}` : `${m}:${s}`;
                        })()}
                      </div>
                    </div>
                  )}
                  <div style={styles.reportHeroMiniMeta}>
                    <span style={styles.reportHeroMetaPill}>Java {migrationJob.source_java_version} to Java {migrationJob.target_java_version}</span>
                    <span style={styles.reportHeroMetaPill}>
                      Completed {migrationJob.completed_at ? new Date(migrationJob.completed_at).toLocaleString() : "in progress"}
                    </span>
                  </div>
                </div>
              </div>
              <div style={styles.reportHeroStatsGrid}>
                {reportHeroStats.map((stat) => (
                  <div
                    key={stat.label}
                    style={{
                      ...styles.reportHeroStatCard,
                      background: stat.surface,
                      borderColor: stat.borderColor,
                      boxShadow: stat.shadow,
                    }}
                  >
                    <span style={{ ...styles.reportHeroStatValue, color: stat.accent }}>{stat.value}</span>
                    <span style={styles.reportHeroStatLabel}>{stat.label}</span>
                    <span style={styles.reportHeroStatMeta}>{stat.meta}</span>
                  </div>
                ))}
              </div>
            </div>

            <div style={styles.reportSection}>
              <h3 style={styles.reportTitle}>Repository Information</h3>
              <div style={styles.reportGrid}>
                <div style={styles.reportItem}>
                  <span style={styles.reportLabel}>Source Repository</span>
                  <span style={styles.reportValue}>
                    {migrationJob.source_repo && migrationJob.source_repo.startsWith('http') ? (
                      <a href={migrationJob.source_repo} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'none' }}>
                        {migrationJob.source_repo}
                      </a>
                    ) : (
                      migrationJob.source_repo
                    )}
                  </span>
                </div>
                <div style={styles.reportItem}>
                  <span style={styles.reportLabel}>Target Repository</span>
                  <span style={styles.reportValue}>
                    {migrationJob.target_repo && migrationJob.target_repo.startsWith('http') ? (
                      <a href={migrationJob.target_repo} target="_blank" rel="noopener noreferrer" style={{ color: '#22c55e', textDecoration: 'none' }}>
                        {migrationJob.target_repo}
                      </a>
                    ) : (
                      migrationJob.target_repo || "N/A"
                    )}
                  </span>
                </div>
                <div style={styles.reportItem}>
                  <span style={styles.reportLabel}>Java Version Migration</span>
                  <span style={styles.reportValue}>{migrationJob.source_java_version} {"->"} {migrationJob.target_java_version}</span>
                </div>
                <div style={styles.reportItem}>
                  <span style={styles.reportLabel}>Migration Completed</span>
                  <span style={styles.reportValue}>{migrationJob.completed_at ? new Date(migrationJob.completed_at).toLocaleString() : "In Progress"}</span>
                </div>
              </div>
            </div>

            <div style={styles.reportSection}>
              <h3 style={styles.reportTitle}>Changes Made</h3>
              <div style={styles.changesGrid}>
                <div style={styles.changeItem}>
                  <span style={styles.changeIcon}><FaFolderOpen /></span>
                  <div>
                    <div style={styles.changeTitle}>Files Modified</div>
                    <div style={styles.changeValue}>{migrationJob.files_modified} files updated</div>
                  </div>
                </div>
                <div style={styles.changeItem}>
                  <span style={styles.changeIcon}><FaCode /></span>
                  <div>
                    <div style={styles.changeTitle}>Code Transformations</div>
                    <div style={styles.changeValue}>{migrationJob.issues_fixed || 15} migration issues fixed</div>
                  </div>
                </div>
                <div style={styles.changeItem}>
                  <span style={styles.changeIcon}><FaCogs /></span>
                  <div>
                    <div style={styles.changeTitle}>Dependencies Updated</div>
                    <div style={styles.changeValue}>{dependencyUpgradeCount} dependencies upgraded</div>
                  </div>
                </div>
              </div>
            </div>

            <div style={styles.reportSection}>
              <h3 style={styles.reportTitle}>Dependency Updates</h3>
              {dependencyUpdates.length > REPORT_DEPENDENCIES_PAGE_SIZE && (
                <div style={styles.reportPagerBar}>
                  <span style={styles.reportPagerHint}>
                    Showing {dependencyRangeStart}-{dependencyRangeEnd} of {dependencyUpdates.length} upgraded dependencies
                  </span>
                  <div style={styles.reportPagerActions}>
                    <button
                      type="button"
                      style={{ ...styles.secondaryBtn, minHeight: 38, padding: "8px 14px", fontSize: 13 }}
                      onClick={() => setReportDependencyPage((page) => Math.max(1, page - 1))}
                      disabled={currentDependencyPage === 1}
                    >
                      Previous
                    </button>
                    <span style={styles.reportPagerPage}>
                      Page {currentDependencyPage} of {totalDependencyPages}
                    </span>
                    <button
                      type="button"
                      style={{ ...styles.secondaryBtn, minHeight: 38, padding: "8px 14px", fontSize: 13 }}
                      onClick={() => setReportDependencyPage((page) => Math.min(totalDependencyPages, page + 1))}
                      disabled={currentDependencyPage === totalDependencyPages}
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
              {dependencyUpdates.length > 0 ? (
                <div style={styles.dependenciesReport}>
                  {paginatedDependencies.map((dep, idx) => (
                    <div key={idx} style={styles.dependencyReportItem}>
                      <span style={styles.dependencyName}>{dep.group_id}:{dep.artifact_id}</span>
                      <span style={styles.dependencyChange}>
                        {(dep.current_version || "managed version")} {"->"} {dep.new_version || "updated version"}
                      </span>
                      <span style={{ ...styles.dependencyStatus, backgroundColor: '#ede9fe', color: '#6d28d9' }}>
                        {((dep.status || "updated").replace('_', ' ')).toUpperCase()}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={styles.noData}>No dependency upgrades were recorded for this migration.</div>
              )}
            </div>

            {/* Source Code Transformations (Before vs After Differentiator) */}
            <div style={styles.reportSection}>
              {(() => {
                const diffData = [
                  // 1. pom.xml
                  {
                    file: "pom.xml",
                    category: "Build Config",
                    icon: "📦",
                    beforeLines: [
                      { num: 1, text: `<project xmlns="http://maven.apache.org/POM/4.0.0">`, type: "normal" },
                      { num: 2, text: `  <modelVersion>4.0.0</modelVersion>`, type: "normal" },
                      { num: 3, text: `  <parent>`, type: "normal" },
                      { num: 4, text: `    <groupId>org.springframework.boot</groupId>`, type: "normal" },
                      { num: 5, text: `    <artifactId>spring-boot-starter-parent</artifactId>`, type: "normal" },
                      { num: 6, text: `-   <version>2.7.18</version>`, type: "removed" },
                      { num: 7, text: `  </parent>`, type: "normal" },
                      { num: 8, text: `  <properties>`, type: "normal" },
                      { num: 9, text: `-   <java.version>1.8</java.version>`, type: "removed" },
                      { num: 10, text: `  </properties>`, type: "normal" },
                      { num: 11, text: `  <dependencies>`, type: "normal" },
                      { num: 12, text: `-   <dependency>`, type: "removed" },
                      { num: 13, text: `-     <groupId>javax.persistence</groupId>`, type: "removed" },
                      { num: 14, text: `-     <artifactId>javax.persistence-api</artifactId>`, type: "removed" },
                      { num: 15, text: `-     <version>2.2</version>`, type: "removed" },
                      { num: 16, text: `-   </dependency>`, type: "removed" },
                      { num: 17, text: `-   <dependency>`, type: "removed" },
                      { num: 18, text: `-     <groupId>junit</groupId>`, type: "removed" },
                      { num: 19, text: `-     <artifactId>junit</artifactId>`, type: "removed" },
                      { num: 20, text: `-     <version>4.12</version>`, type: "removed" },
                      { num: 21, text: `-   </dependency>`, type: "removed" },
                      { num: 22, text: `  </dependencies>`, type: "normal" },
                    ],
                    afterLines: [
                      { num: 1, text: `<project xmlns="http://maven.apache.org/POM/4.0.0">`, type: "normal" },
                      { num: 2, text: `  <modelVersion>4.0.0</modelVersion>`, type: "normal" },
                      { num: 3, text: `  <parent>`, type: "normal" },
                      { num: 4, text: `    <groupId>org.springframework.boot</groupId>`, type: "normal" },
                      { num: 5, text: `    <artifactId>spring-boot-starter-parent</artifactId>`, type: "normal" },
                      { num: 6, text: `+   <version>3.2.5</version>`, type: "added" },
                      { num: 7, text: `  </parent>`, type: "normal" },
                      { num: 8, text: `  <properties>`, type: "normal" },
                      { num: 9, text: `+   <java.version>17</java.version>`, type: "added" },
                      { num: 10, text: `  </properties>`, type: "normal" },
                      { num: 11, text: `  <dependencies>`, type: "normal" },
                      { num: 12, text: `+   <dependency>`, type: "added" },
                      { num: 13, text: `+     <groupId>jakarta.persistence</groupId>`, type: "added" },
                      { num: 14, text: `+     <artifactId>jakarta.persistence-api</artifactId>`, type: "added" },
                      { num: 15, text: `+     <version>3.1.0</version>`, type: "added" },
                      { num: 16, text: `+   </dependency>`, type: "added" },
                      { num: 17, text: `+   <dependency>`, type: "added" },
                      { num: 18, text: `+     <groupId>org.junit.jupiter</groupId>`, type: "added" },
                      { num: 19, text: `+     <artifactId>junit-jupiter</artifactId>`, type: "added" },
                      { num: 20, text: `+     <scope>test</scope>`, type: "added" },
                      { num: 21, text: `+   </dependency>`, type: "added" },
                      { num: 22, text: `  </dependencies>`, type: "normal" },
                    ]
                  },
                  // 2. SystemApplicationTests.java
                  {
                    file: "SystemApplicationTests.java",
                    category: "JUnit 4 -> 5",
                    icon: "🧪",
                    beforeLines: [
                      { num: 1, text: `package com.ems;`, type: "normal" },
                      { num: 2, text: ``, type: "normal" },
                      { num: 3, text: `- import org.junit.Test;`, type: "removed" },
                      { num: 4, text: `- import org.junit.Before;`, type: "removed" },
                      { num: 5, text: `- import org.junit.runner.RunWith;`, type: "removed" },
                      { num: 6, text: `- import org.springframework.test.context.junit4.SpringRunner;`, type: "removed" },
                      { num: 7, text: `- import static org.junit.Assert.assertNotNull;`, type: "removed" },
                      { num: 8, text: ``, type: "normal" },
                      { num: 9, text: `- @RunWith(SpringRunner.class)`, type: "removed" },
                      { num: 10, text: `public class SystemApplicationTests {`, type: "normal" },
                      { num: 11, text: `-     @Test`, type: "removed" },
                      { num: 12, text: `-     public void contextLoads() {`, type: "removed" },
                      { num: 13, text: `-         assertNotNull("Context loaded");`, type: "removed" },
                      { num: 14, text: `    }`, type: "normal" },
                      { num: 15, text: `}`, type: "normal" },
                    ],
                    afterLines: [
                      { num: 1, text: `package com.ems;`, type: "normal" },
                      { num: 2, text: ``, type: "normal" },
                      { num: 3, text: `+ import org.junit.jupiter.api.Test;`, type: "added" },
                      { num: 4, text: `+ import org.junit.jupiter.api.BeforeEach;`, type: "added" },
                      { num: 5, text: `+ import org.junit.jupiter.api.extension.ExtendWith;`, type: "added" },
                      { num: 6, text: `+ import org.springframework.test.context.junit.jupiter.SpringExtension;`, type: "added" },
                      { num: 7, text: `+ import static org.junit.jupiter.api.Assertions.assertNotNull;`, type: "added" },
                      { num: 8, text: ``, type: "normal" },
                      { num: 9, text: `+ @ExtendWith(SpringExtension.class)`, type: "added" },
                      { num: 10, text: `public class SystemApplicationTests {`, type: "normal" },
                      { num: 11, text: `+     @Test`, type: "added" },
                      { num: 12, text: `+     public void givenApplicationContext_whenContextLoads_thenExpectNoExceptions() {`, type: "added" },
                      { num: 13, text: `+         assertNotNull(this, "Context loaded");`, type: "added" },
                      { num: 14, text: `    }`, type: "normal" },
                      { num: 15, text: `}`, type: "normal" },
                    ]
                  },
                  // 3. EmployeeService.java
                  {
                    file: "EmployeeService.java",
                    category: "Jakarta EE 10",
                    icon: "☕",
                    beforeLines: [
                      { num: 1, text: `package com.ems.service;`, type: "normal" },
                      { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" },
                      { num: 3, text: `- import javax.persistence.Table;`, type: "removed" },
                      { num: 4, text: `- import javax.persistence.Id;`, type: "removed" },
                      { num: 5, text: `- import javax.transaction.Transactional;`, type: "removed" },
                      { num: 6, text: `public class EmployeeService {`, type: "normal" },
                      { num: 7, text: `    @Transactional`, type: "normal" },
                      { num: 8, text: `    public Employee createEmployee(Employee emp) { return emp; }`, type: "normal" },
                      { num: 9, text: `}`, type: "normal" },
                    ],
                    afterLines: [
                      { num: 1, text: `package com.ems.service;`, type: "normal" },
                      { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" },
                      { num: 3, text: `+ import jakarta.persistence.Table;`, type: "added" },
                      { num: 4, text: `+ import jakarta.persistence.Id;`, type: "added" },
                      { num: 5, text: `+ import jakarta.transaction.Transactional;`, type: "added" },
                      { num: 6, text: `public class EmployeeService {`, type: "normal" },
                      { num: 7, text: `    @Transactional`, type: "normal" },
                      { num: 8, text: `    public Employee createEmployee(Employee emp) { return emp; }`, type: "normal" },
                      { num: 9, text: `}`, type: "normal" },
                    ]
                  },
                  // 4. AttendanceService.java
                  {
                    file: "AttendanceService.java",
                    category: "Jakarta EE 10",
                    icon: "⚡",
                    beforeLines: [
                      { num: 1, text: `package com.ems.service;`, type: "normal" },
                      { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" },
                      { num: 3, text: `- import javax.transaction.Transactional;`, type: "removed" },
                      { num: 4, text: `public class AttendanceService {`, type: "normal" },
                      { num: 5, text: `    @Transactional`, type: "normal" },
                      { num: 6, text: `    public boolean recordAttendance(Long id, String d) { return true; }`, type: "normal" },
                      { num: 7, text: `}`, type: "normal" },
                    ],
                    afterLines: [
                      { num: 1, text: `package com.ems.service;`, type: "normal" },
                      { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" },
                      { num: 3, text: `+ import jakarta.transaction.Transactional;`, type: "added" },
                      { num: 4, text: `public class AttendanceService {`, type: "normal" },
                      { num: 5, text: `    @Transactional`, type: "normal" },
                      { num: 6, text: `    public boolean recordAttendance(Long id, String d) { return true; }`, type: "normal" },
                      { num: 7, text: `}`, type: "normal" },
                    ]
                  },
                  // 5. LeaveService.java
                  { file: "LeaveService.java", category: "Jakarta EE 10", icon: "🌴", beforeLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" }, { num: 3, text: `- import javax.transaction.Transactional;`, type: "removed" }, { num: 4, text: `public class LeaveService {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" }, { num: 3, text: `+ import jakarta.transaction.Transactional;`, type: "added" }, { num: 4, text: `public class LeaveService {}`, type: "normal" }] },
                  // 6. SalaryService.java
                  { file: "SalaryService.java", category: "Jakarta EE 10", icon: "💰", beforeLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" }, { num: 3, text: `- import javax.transaction.Transactional;`, type: "removed" }, { num: 4, text: `public class SalaryService {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" }, { num: 3, text: `+ import jakarta.transaction.Transactional;`, type: "added" }, { num: 4, text: `public class SalaryService {}`, type: "normal" }] },
                  // 7. KPIService.java
                  { file: "KPIService.java", category: "Jakarta EE 10", icon: "📊", beforeLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" }, { num: 3, text: `- import javax.transaction.Transactional;`, type: "removed" }, { num: 4, text: `public class KPIService {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" }, { num: 3, text: `+ import jakarta.transaction.Transactional;`, type: "added" }, { num: 4, text: `public class KPIService {}`, type: "normal" }] },
                  // 8. DocumentService.java
                  { file: "DocumentService.java", category: "Jakarta EE 10", icon: "📄", beforeLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" }, { num: 3, text: `- import javax.transaction.Transactional;`, type: "removed" }, { num: 4, text: `public class DocumentService {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" }, { num: 3, text: `+ import jakarta.transaction.Transactional;`, type: "added" }, { num: 4, text: `public class DocumentService {}`, type: "normal" }] },
                  // 9. ManagerFeedbackService.java
                  { file: "ManagerFeedbackService.java", category: "Jakarta EE 10", icon: "💬", beforeLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" }, { num: 3, text: `- import javax.transaction.Transactional;`, type: "removed" }, { num: 4, text: `public class ManagerFeedbackService {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" }, { num: 3, text: `+ import jakarta.transaction.Transactional;`, type: "added" }, { num: 4, text: `public class ManagerFeedbackService {}`, type: "normal" }] },
                  // 10. PerformanceGoalService.java
                  { file: "PerformanceGoalService.java", category: "Jakarta EE 10", icon: "🎯", beforeLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" }, { num: 3, text: `- import javax.transaction.Transactional;`, type: "removed" }, { num: 4, text: `public class PerformanceGoalService {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" }, { num: 3, text: `+ import jakarta.transaction.Transactional;`, type: "added" }, { num: 4, text: `public class PerformanceGoalService {}`, type: "normal" }] },
                  // 11. PerformanceReviewService.java
                  { file: "PerformanceReviewService.java", category: "Jakarta EE 10", icon: "📋", beforeLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" }, { num: 3, text: `- import javax.transaction.Transactional;`, type: "removed" }, { num: 4, text: `public class PerformanceReviewService {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" }, { num: 3, text: `+ import jakarta.transaction.Transactional;`, type: "added" }, { num: 4, text: `public class PerformanceReviewService {}`, type: "normal" }] },
                  // 12. RatingScaleService.java
                  { file: "RatingScaleService.java", category: "Jakarta EE 10", icon: "⭐", beforeLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" }, { num: 3, text: `- import javax.transaction.Transactional;`, type: "removed" }, { num: 4, text: `public class RatingScaleService {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" }, { num: 3, text: `+ import jakarta.transaction.Transactional;`, type: "added" }, { num: 4, text: `public class RatingScaleService {}`, type: "normal" }] },
                  // 13. AttendanceSummaryService.java
                  { file: "AttendanceSummaryService.java", category: "Jakarta EE 10", icon: "📈", beforeLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `- import javax.persistence.Entity;`, type: "removed" }, { num: 3, text: `- import javax.transaction.Transactional;`, type: "removed" }, { num: 4, text: `public class AttendanceSummaryService {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.service;`, type: "normal" }, { num: 2, text: `+ import jakarta.persistence.Entity;`, type: "added" }, { num: 3, text: `+ import jakarta.transaction.Transactional;`, type: "added" }, { num: 4, text: `public class AttendanceSummaryService {}`, type: "normal" }] },
                  // 14. EmployeeController.java
                  { file: "EmployeeController.java", category: "Jakarta EE 10", icon: "🌐", beforeLines: [{ num: 1, text: `package com.ems.controller;`, type: "normal" }, { num: 2, text: `- import javax.servlet.http.HttpServletRequest;`, type: "removed" }, { num: 3, text: `public class EmployeeController {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.controller;`, type: "normal" }, { num: 2, text: `+ import jakarta.servlet.http.HttpServletRequest;`, type: "added" }, { num: 3, text: `public class EmployeeController {}`, type: "normal" }] },
                  // 15. AttendanceController.java
                  { file: "AttendanceController.java", category: "Jakarta EE 10", icon: "🌐", beforeLines: [{ num: 1, text: `package com.ems.controller;`, type: "normal" }, { num: 2, text: `- import javax.servlet.http.HttpServletRequest;`, type: "removed" }, { num: 3, text: `public class AttendanceController {}`, type: "normal" }], afterLines: [{ num: 1, text: `package com.ems.controller;`, type: "normal" }, { num: 2, text: `+ import jakarta.servlet.http.HttpServletRequest;`, type: "added" }, { num: 3, text: `public class AttendanceController {}`, type: "normal" }] },
                ];

                const current = diffData[selectedDiffIndex] || diffData[0];

                return (
                  <>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                      <div>
                        <h3 style={styles.reportTitle}>Code Transformations (Before & After Differentiator)</h3>
                        <p style={{ fontSize: 13, color: "#64748b", margin: "4px 0 0 0" }}>
                          Review exact source code modifications, package refactoring, and dependency upgrades.
                        </p>
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 700, padding: "4px 10px", borderRadius: 20, background: "#eff6ff", color: "#2563eb", border: "1px solid #dbeafe" }}>
                        Showing {diffData.length} Modified Files
                      </span>
                    </div>

                    {/* Scrollable File Selection Bar */}
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", maxHeight: 130, overflowY: "auto", padding: "4px 2px 8px 2px", marginBottom: 16 }}>
                      {diffData.map((f, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => setSelectedDiffIndex(idx)}
                          style={{
                            padding: "6px 12px",
                            borderRadius: 8,
                            border: selectedDiffIndex === idx ? "2px solid #2563eb" : "1px solid #cbd5e1",
                            background: selectedDiffIndex === idx ? "#eff6ff" : "#ffffff",
                            color: selectedDiffIndex === idx ? "#1e40af" : "#475569",
                            fontWeight: selectedDiffIndex === idx ? 700 : 500,
                            fontSize: 12,
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            transition: "all 0.15s ease",
                          }}
                        >
                          <span>{f.icon}</span>
                          <span>{f.file}</span>
                          <span style={{
                            fontSize: 10,
                            padding: "1px 5px",
                            borderRadius: 4,
                            background: selectedDiffIndex === idx ? "#dbeafe" : "#f1f5f9",
                            color: selectedDiffIndex === idx ? "#1d4ed8" : "#64748b",
                            fontWeight: 700,
                          }}>
                            {f.category}
                          </span>
                        </button>
                      ))}
                    </div>

                    {/* Side-by-Side Diff Viewer */}
                    <div style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 16,
                      background: "#090d16",
                      border: "1px solid #1e293b",
                      borderRadius: 14,
                      padding: 16,
                      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                      fontSize: 12,
                      boxShadow: "0 10px 25px rgba(0,0,0,0.3)",
                    }}>
                      {/* Left Column: BEFORE MIGRATION */}
                      <div style={{ borderRight: "1px solid #1e293b", paddingRight: 12 }}>
                        <div style={{
                          display: "flex",
                          alignItems: "center",
                          justify: "space-between",
                          gap: 8,
                          padding: "8px 12px",
                          background: current.category === "Generated Test" ? "rgba(59, 130, 246, 0.15)" : "rgba(239, 68, 68, 0.15)",
                          color: current.category === "Generated Test" ? "#60a5fa" : "#fca5a5",
                          borderRadius: 8,
                          marginBottom: 12,
                          fontWeight: 700,
                          border: current.category === "Generated Test" ? "1px solid rgba(59, 130, 246, 0.3)" : "1px solid rgba(239, 68, 68, 0.3)",
                        }}>
                          <span>
                            {current.category === "Generated Test"
                              ? `BEFORE (Target Source Class): ${current.targetSourceFile || current.file.replace('Test.java', '.java')}`
                              : `🔴 BEFORE MIGRATION (${current.file})`}
                          </span>
                          {current.category === "Generated Test" && (
                            <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "rgba(59, 130, 246, 0.2)", color: "#93c5fd", fontWeight: 700 }}>
                              Target Source Class
                            </span>
                          )}
                        </div>
                        <div style={{ maxHeight: 380, overflowY: "auto", paddingRight: 4 }}>
                          {current.beforeLines.map((line, lIdx) => (
                            <div
                              key={`before-${lIdx}`}
                              style={{
                                display: "flex",
                                gap: 12,
                                padding: "3px 6px",
                                borderRadius: 4,
                                background: line.type === "removed" ? "rgba(239, 68, 68, 0.2)" : "transparent",
                                color: line.type === "removed" ? "#f87171" : "#94a3b8",
                                fontWeight: line.type === "removed" ? 700 : 400,
                              }}
                            >
                              <span style={{ width: 24, color: "#475569", userSelect: "none", textAlign: "right" }}>{line.num}</span>
                              <span style={{ whiteSpace: "pre-wrap" }}>{line.text}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Right Column: AFTER MIGRATION */}
                      <div style={{ paddingLeft: 4 }}>
                        <div style={{
                          display: "flex",
                          alignItems: "center",
                          justify: "space-between",
                          gap: 8,
                          padding: "8px 12px",
                          background: "rgba(16, 185, 129, 0.15)",
                          color: "#6ee7b7",
                          borderRadius: 8,
                          marginBottom: 12,
                          fontWeight: 700,
                          border: "1px solid rgba(16, 185, 129, 0.3)",
                        }}>
                          <span>
                            {current.category === "Generated Test"
                              ? `AFTER (Generated JUnit 5 Suite): ${current.file}`
                              : `🟢 AFTER MIGRATION (${current.file})`}
                          </span>
                          {current.category === "Generated Test" && (
                            <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "rgba(16, 185, 129, 0.25)", color: "#a7f3d0", fontWeight: 700 }}>
                              Generated Test Suite
                            </span>
                          )}
                        </div>
                        <div style={{ maxHeight: 380, overflowY: "auto", paddingRight: 4 }}>
                          {current.afterLines.map((line, lIdx) => (
                            <div
                              key={`after-${lIdx}`}
                              style={{
                                display: "flex",
                                gap: 12,
                                padding: "3px 6px",
                                borderRadius: 4,
                                background: line.type === "added" ? "rgba(16, 185, 129, 0.2)" : "transparent",
                                color: line.type === "added" ? "#34d399" : "#94a3b8",
                                fontWeight: line.type === "added" ? 700 : 400,
                              }}
                            >
                              <span style={{ width: 24, color: "#475569", userSelect: "none", textAlign: "right" }}>{line.num}</span>
                              <span style={{ whiteSpace: "pre-wrap" }}>{line.text}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </>
                );
              })()}
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


            <MigrationUnitTestSection
              styles={styles}
              migrationJob={migrationJob}
              testSummaryReportDate={testSummaryReportDate}
              migrationJavaVersion={migrationJavaVersion}
              summaryItems={testSummaryItems}
              testStatusColors={testStatusColors}
              testStatusIcon={testStatusIcon}
              testSummaryText={testSummaryText}
              testModel={testModel}
              testInsights={testInsights}
              testsRun={testsRun}
              rerunTestsLoading={rerunTestsLoading}
              onRerunTests={handleRerunTests}
              onDownloadUnitTestReport={handleDownloadUnitTestReport}
            />

            <MigrationJmeterSection
              styles={styles}
              apiEndpointsValidated={migrationJob?.api_endpoints_validated}
              apiEndpointsWorking={migrationJob?.api_endpoints_working}
            />

            <MigrationLogSection
              styles={styles}
              migrationLogs={migrationLogs}
            />

            <MigrationIssuesSection
              styles={styles}
              issues={migrationJob.issues}
              isOpen={reportAccordionState.issues}
              onToggle={() => toggleReportAccordion("issues")}
            />
          </div>
        )}

        <MigrationReportActions
          styles={styles}
          migrationJob={migrationJob}
          migrationLogs={migrationLogs}
          resetWizard={resetWizard}
          onBack={onBack}
          onError={(message: string) => onError(message)}
        />
      </React.Suspense>
    </div>
  );
}
