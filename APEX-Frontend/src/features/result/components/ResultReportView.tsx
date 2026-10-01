import { useEffect, useState } from "react";
import { MigrationCycodeSection } from "./MigrationCycodeSection";
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
  FaCopy,
  FaCheck,
  FaExternalLinkAlt,
} from "react-icons/fa";
import { wizardStyles as styles } from "@/shared/components/wizard/wizardStyles";
import { renderWizardIconBadge } from "@/shared/components/wizard";
import {
  downloadUnitTestReport,
  getMigrationFileDiff,
  getMigrationLogs,
  rerunMigrationTests,
  getMigrationReportDetails,
  type ReportDetailsResponse,
  type SonarIssueDetail,
  type SonarHotspotDetail,
  type SonarReport,
} from "../services/resultService";
import { MigrationReportDetailModal } from "./MigrationReportDetailModal";
import type { DependencyInfo } from "@/shared/types/domain";
import {
  SONAR_FINDINGS_PAGE_SIZE,
  REPORT_DEPENDENCIES_PAGE_SIZE,
  getTestSummaryMetrics,
  getFossaVulnerabilityTotal,
  getFossaLicenseIssueCount,
  getFossaSeverityCounts,
  getFossaScanModeLabel,
  getRepositoryLink,
  isLocalPath,
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
import { FrameworkPageSandbox } from "./FrameworkPageSandbox";

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
const MigrationProposedTestSection = React.lazy(async () => {
  const module = await import("./MigrationReportSections");
  return { default: module.MigrationProposedTestSection };
});

interface ResultReportViewProps {
  resultExec: ReturnType<typeof useMigrationExecution>;
  repoAnalysis?: any;
  runSonar: boolean;
  runFossa: boolean;
  runTests?: boolean;
  runFunctionalTests?: boolean;
  selectedLLMProvider: string;
  useLLMTests: boolean;
  resetWizard: () => void;
  onBack: () => void;
  onError: (message: string) => void;
}

export function ResultReportView({
  resultExec,
  repoAnalysis,
  runSonar,
  runFossa,
  runTests,
  runFunctionalTests,
  selectedLLMProvider,
  useLLMTests,
  resetWizard,
  onBack,
  onError,
}: ResultReportViewProps) {
  // Derive file counts from repoAnalysis using same logic as DiscoveryStepView
  const discoveryJavaFiles: number = repoAnalysis?.java_file_count ?? repoAnalysis?.java_files?.length ?? 0;
  const discoveryJspFiles: number = repoAnalysis?.jsp_file_count ?? repoAnalysis?.jsp_count ?? repoAnalysis?.structure?.jsp_count ?? repoAnalysis?.jsp_files?.length ?? 0;
  const discoveryJsfFiles: number = repoAnalysis?.jsf_file_count ?? repoAnalysis?.jsf_count ?? repoAnalysis?.structure?.jsf_count ?? repoAnalysis?.jsf_files?.length ?? 0;
  const discoveryXmlFiles: number = repoAnalysis?.config_file_count ?? repoAnalysis?.config_files?.length ?? 0;
  const discoveryOtherFiles: number = repoAnalysis?.other_file_count ?? repoAnalysis?.other_files?.length ?? 0;
  const discoveryTotalFiles: number = (repoAnalysis?.total_file_count ?? (discoveryJavaFiles + discoveryXmlFiles + discoveryJspFiles + discoveryJsfFiles + discoveryOtherFiles)) || 0;
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

  const [selectedDiffIndex, setSelectedDiffIndex] = useState<number>(0);
  const [loadedFileDiffs, setLoadedFileDiffs] = useState<Record<string, {
    beforeLines: Array<{ num: number; text: string; type: string }>;
    afterLines: Array<{ num: number; text: string; type: string }>;
  }>>({});
  const [fileDiffError, setFileDiffError] = useState<string | null>(null);
  const [fileDiffLoading, setFileDiffLoading] = useState(false);
  const [copiedDiffCode, setCopiedDiffCode] = useState(false);
  const [sandboxEntry, setSandboxEntry] = useState<{ fileName: string; code: Array<{ text: string }>; css: string } | null>(null);
  const [dependencySearchQuery, setDependencySearchQuery] = useState("");
  const [sonarFindingFilter, setSonarFindingFilter] = useState<SonarFindingFilter>("all");
  const [codeSmellSeverityFilter, setCodeSmellSeverityFilter] = useState<CodeSmellSeverityFilter>("all");
  const [visibleSonarFindingCounts, setVisibleSonarFindingCounts] = useState<Record<Exclude<SonarFindingFilter, "all">, number>>({
    bugs: SONAR_FINDINGS_PAGE_SIZE,
    vulnerabilities: SONAR_FINDINGS_PAGE_SIZE,
    code_smells: SONAR_FINDINGS_PAGE_SIZE,
    security_hotspots: SONAR_FINDINGS_PAGE_SIZE,
  });

  // Category Detail Modal State & Client-Side Cache
  const [detailModalCategory, setDetailModalCategory] = useState<
    "files" | "issues" | "dependencies" | "vulnerabilities" | "transformations" | null
  >(null);
  const [detailModalLoading, setDetailModalLoading] = useState(false);
  const [detailModalError, setDetailModalError] = useState<string | null>(null);
  const [reportDetailsCache, setReportDetailsCache] = useState<Record<string, ReportDetailsResponse>>({});

  const handleOpenReportDetails = async (
    category: "files" | "issues" | "dependencies" | "vulnerabilities" | "transformations"
  ) => {
    setDetailModalCategory(category);
    setDetailModalError(null);

    // If already in client-side cache, reuse immediately with zero network delay
    if (reportDetailsCache[category]) {
      return;
    }

    if (!migrationJob?.job_id) {
      setDetailModalError("Migration job ID not found.");
      return;
    }

    setDetailModalLoading(true);
    try {
      const details = await getMigrationReportDetails(migrationJob.job_id, category);
      setReportDetailsCache((prev) => ({
        ...prev,
        [category]: details,
      }));
    } catch (err: any) {
      setDetailModalError(err?.message || "Failed to load migration details.");
    } finally {
      setDetailModalLoading(false);
    }
  };

  const diffData = React.useMemo(() => {
    const rawFileDiffs: any[] = migrationJob?.file_diffs ?? [];
    const javaFileDiffEntries = rawFileDiffs.map((fd: any) => {
      const changeType: string = (fd.changeType ?? "MODIFIED").toUpperCase();
      const relativePath = (fd.relativePath ?? fd.fileName ?? "").replace(/\\/g, "/");
      const loadedDiff = loadedFileDiffs[relativePath];
      const status: "Modified" | "Added" | "Removed" =
        changeType === "ADDED" ? "Added" :
        changeType === "DELETED" ? "Removed" :
        "Modified";
      return {
        file: fd.fileName ?? fd.relativePath ?? "",
        relativePath,
        label: fd.label,
        status,
        additions: fd.addedLineCount ?? 0,
        deletions: fd.removedLineCount ?? 0,
        beforeLines: (loadedDiff?.beforeLines ?? fd.beforeLines ?? []) as Array<{ num: number; text: string; type: string }>,
        afterLines: (loadedDiff?.afterLines ?? fd.afterLines ?? []) as Array<{ num: number; text: string; type: string }>,
      };
    });

    const rawUiTransformations: any[] = migrationJob?.uiTransformations ?? [];
    const uiDiffEntries = rawUiTransformations.map((t: any) => ({
      file: t.targetSourceFile ?? t.file ?? "",
      sourceFile: t.sourceFile ?? t.file ?? "",
      category: t.category ?? "",
      icon: t.icon ?? "⚛️",
      status: (t.status ?? "Added") as "Modified" | "Added" | "Removed",
      additions: t.additions ?? (t.afterLines?.length ?? 0),
      deletions: t.deletions ?? 0,
      beforeLines: (t.beforeLines ?? []) as Array<{ num: number; text: string; type: string }>,
      afterLines: (t.afterLines ?? []) as Array<{ num: number; text: string; type: string }>,
    }));

    const mergedEntries: Array<{
      file: string;
      status: "Modified" | "Added" | "Removed";
      additions: number;
      deletions: number;
      beforeLines: Array<{ num: number; text: string; type: string }>;
      afterLines: Array<{ num: number; text: string; type: string }>;
      [key: string]: any;
    }> = [];
    const seenFileKeys = new Set<string>();

    for (const entry of [...javaFileDiffEntries, ...uiDiffEntries]) {
      const key = (entry.sourceFile || entry.relativePath || entry.file || "").toLowerCase().replace(/\\/g, "/");
      if (!key || seenFileKeys.has(key)) {
        continue;
      }
      seenFileKeys.add(key);
      mergedEntries.push(entry);
    }
    return mergedEntries;
  }, [migrationJob?.file_diffs, migrationJob?.uiTransformations, loadedFileDiffs]);

  const modifiedFilesBreakdown = React.useMemo(() => {
    if (!diffData || diffData.length === 0) return "";
    let javaCount = 0;
    let jspCount = 0;
    let xmlCount = 0;
    let uiCount = 0;
    let otherCount = 0;

    for (const item of diffData) {
      const p = (item.relativePath || item.sourceFile || item.file || "").toLowerCase();
      if (p.endsWith(".java")) {
        javaCount++;
      } else if (p.endsWith(".jsp") || p.endsWith(".jspf") || p.endsWith(".jspx") || p.endsWith(".xhtml") || p.endsWith(".jsf")) {
        jspCount++;
      } else if (p.endsWith(".xml") || p.endsWith(".gradle") || p.endsWith(".properties") || p.endsWith(".yaml") || p.endsWith(".yml")) {
        xmlCount++;
      } else if (p.endsWith(".tsx") || p.endsWith(".jsx") || p.endsWith(".ts") || p.endsWith(".js") || p.endsWith(".css") || p.endsWith(".html") || p.includes("frontend/")) {
        uiCount++;
      } else {
        otherCount++;
      }
    }

    const parts: string[] = [];
    if (javaCount > 0) parts.push(`${javaCount} Java`);
    if (jspCount > 0) parts.push(`${jspCount} JSP/JSF`);
    if (uiCount > 0) parts.push(`${uiCount} Modern UI`);
    if (xmlCount > 0) parts.push(`${xmlCount} Config/XML`);
    if (otherCount > 0) parts.push(`${otherCount} Other`);

    return parts.join(" · ");
  }, [diffData]);

  const handleSelectFileForDiff = (filePath: string) => {
    const norm = filePath.replace(/\\/g, "/").toLowerCase();
    const base = norm.split("/").pop();
    const idx = diffData.findIndex((d) => {
      const dPath = (d.sourceFile || d.relativePath || d.file || "").replace(/\\/g, "/").toLowerCase();
      return dPath === norm || (base && dPath.endsWith("/" + base)) || (base && d.file.toLowerCase() === base);
    });
    if (idx >= 0) {
      setSelectedDiffIndex(idx);
      const item = diffData[idx];
      if (item && !item.category && item.relativePath) {
        void loadFileDiff(item.relativePath);
      }
      const diffEl = document.getElementById("source-code-transformations-section");
      if (diffEl) {
        diffEl.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  };

  const handleCopyDiffCode = async (afterLines: Array<{ text: string }>) => {
    const code = afterLines
      .map((line) => line.text.replace(/^[+-]\s*/, ""))
      .join("\n");
    try {
      await navigator.clipboard.writeText(code);
      setCopiedDiffCode(true);
      window.setTimeout(() => setCopiedDiffCode(false), 1600);
    } catch {
      setCopiedDiffCode(false);
    }
  };

  const loadFileDiff = async (path: string) => {
    const normalizedPath = path.replace(/\\/g, "/");
    if (!normalizedPath || loadedFileDiffs[normalizedPath] || !migrationJob?.job_id) return;

    setFileDiffLoading(true);
    setFileDiffError(null);
    try {
      const diff = await getMigrationFileDiff(migrationJob.job_id, normalizedPath);
      setLoadedFileDiffs((previous) => ({
        ...previous,
        [normalizedPath]: {
          beforeLines: diff.beforeLines ?? [],
          afterLines: diff.afterLines ?? [],
        },
      }));
    } catch {
      setFileDiffError(`Unable to load the diff for ${normalizedPath}.`);
    } finally {
      setFileDiffLoading(false);
    }
  };

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

  const handleDownloadUnitTestReport = async (format: string = "html") => {
    if (!migrationJob) return;
    try {
      const isCsv = format === "csv";
      const blob = await downloadUnitTestReport(migrationJob.job_id, isCsv ? "csv" : "html");
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `unit-test-report-${migrationJob.job_id}.${isCsv ? "csv" : "html"}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to download unit test report");
    }
  };

  const handleShowReactUi = (
    entry: { file?: string; targetSourceFile?: string; afterLines?: Array<{ text: string }> },
    e?: React.MouseEvent
  ) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const rawTarget = entry.targetSourceFile ?? entry.file ?? "MigratedPage.tsx";
    if (sandboxEntry && sandboxEntry.fileName === rawTarget) {
      setSandboxEntry(null);
      return;
    }

    const allUiFiles = (migrationJob?.uiTransformations ?? []).map((t: any) => ({
      fileName: t.targetSourceFile ?? t.file ?? "MigratedPage.tsx",
      code: (t.afterLines ?? []) as Array<{ text: string }>,
    }));

    let targetFileName = rawTarget;
    let targetCode = entry.afterLines;

    // If a stylesheet was passed, route to first actual UI component
    if (rawTarget.toLowerCase().endsWith(".css")) {
      const firstComponent = allUiFiles.find((f: any) => !f.fileName.toLowerCase().endsWith(".css"));
      if (firstComponent && firstComponent.code.length > 0) {
        targetFileName = firstComponent.fileName;
        targetCode = firstComponent.code;
      }
    }

    if (!targetCode?.length) {
      onError("The selected page has no previewable markup.");
      return;
    }
    const mainEl = document.querySelector(".wizard-main-content");
    const prevScrollTop = mainEl ? mainEl.scrollTop : 0;

    const cssFromUi = (migrationJob.uiTransformations ?? [])
      .filter((transformation: any) => String(transformation.targetSourceFile ?? transformation.file ?? "").toLowerCase().endsWith(".css"))
      .flatMap((transformation: any) => transformation.afterLines ?? [])
      .map((line: { text?: string }) => line.text ?? "")
      .join("\n");

    const cssFromDiffs = diffData
      .filter((f) => String(f.file || "").toLowerCase().endsWith(".css"))
      .flatMap((f) => f.afterLines ?? [])
      .map((line: { text?: string }) => line.text ?? "")
      .join("\n");

    const css = [cssFromUi, cssFromDiffs].filter(Boolean).join("\n");

    setSandboxEntry({
      fileName: targetFileName,
      code: targetCode,
      css,
    });

    if (mainEl && mainEl.scrollTop !== prevScrollTop) {
      mainEl.scrollTop = prevScrollTop;
    }
    requestAnimationFrame(() => {
      if (mainEl && mainEl.scrollTop !== prevScrollTop) {
        mainEl.scrollTop = prevScrollTop;
      }
    });
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
    | {
        available?: boolean;
        line_coverage_pct?: number;
        line_coverage?: number;
        original?: { line_coverage_pct?: number };
        final?: { line_coverage_pct?: number };
        improvement?: { text?: string };
      }
    | undefined;
  const jacocoCoverageAvailable = coverageResult?.available;
  const jacocoCoveragePct =
    jacocoCoverageAvailable === false
      ? null
      : coverageResult?.final?.line_coverage_pct ?? coverageResult?.line_coverage_pct ?? coverageResult?.line_coverage ?? null;
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
      value: typeof jacocoCoveragePct === "number" ? `${jacocoCoveragePct.toFixed(1)}%` : "N/A",
    },
  ];

  // framework_migrations push — executed after reportHeroStats is declared below


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
      resolvedTargetVersion?: string | null;
      status?: string | null;
    };
    return {
      group_id: source.group_id || source.groupId || source.coordinate?.split(":")[0] || "dependency",
      artifact_id: source.artifact_id || source.artifactId || source.coordinate?.split(":")[1] || "artifact",
      current_version: source.current_version || source.old_version || source.oldVersion || source.sourceVersion || "managed version",
      new_version: (source.new_version || source.newVersion || (source as any).resolvedTargetVersion || "updated version") as string,
      status: source.status || "UPGRADED",
    };
  });
  const dependencyUpgradeCount = dependencyUpdates.length;

  const filteredDependencies = dependencyUpdates.filter(dep =>
    dep.group_id.toLowerCase().includes(dependencySearchQuery.toLowerCase()) ||
    dep.artifact_id.toLowerCase().includes(dependencySearchQuery.toLowerCase())
  );

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
      meta: discoveryTotalFiles > 0
        ? `${migrationJob?.files_modified ?? 0} of ${discoveryTotalFiles} repo files updated`
        : `Java ${migrationJob?.source_java_version ?? "?"} -> Java ${migrationJob?.target_java_version ?? "?"}`,
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

  // Append framework migration stats (JSP/JSF) after the base array is initialized
  if (migrationJob?.framework_migrations && migrationJob.framework_migrations.length > 0) {
    migrationJob.framework_migrations.forEach((fm) => {
      let filesMigrated = fm.files_migrated;
      if (migrationJob.uiTransformations && migrationJob.uiTransformations.length > 0) {
        if (fm.source_framework.toUpperCase() === "JSP") {
          const jspCount = migrationJob.uiTransformations.filter((t: any) => {
            const filename = (t.sourceFile || t.file || "").toLowerCase();
            if (filename) return filename.endsWith(".jsp") || filename.endsWith(".jspf") || filename.endsWith(".jspx");
            return t.category?.startsWith("JSP");
          }).length;
          if (jspCount > 0) filesMigrated = jspCount;
        } else if (fm.source_framework.toUpperCase() === "JSF") {
          const jsfCount = migrationJob.uiTransformations.filter((t: any) => {
            const filename = (t.sourceFile || t.file || "").toLowerCase();
            if (filename) return filename.endsWith(".jsf") || filename.endsWith(".xhtml");
            return t.category?.startsWith("JSF");
          }).length;
          if (jsfCount > 0) filesMigrated = jsfCount;
        }
      }
      reportHeroStats.push({
        label: `${fm.source_framework.toUpperCase()} FILES MIGRATED`,
        value: String(filesMigrated),
        accent: "#d946ef",
        meta: `${fm.source_framework.toUpperCase()} -> ${fm.target_framework ?? "Modern"} components`,
        surface: "linear-gradient(180deg, #fdf4ff 0%, #fae8ff 100%)",
        borderColor: "#f5d0fe",
        shadow: "0 16px 30px rgba(217, 70, 239, 0.12)",
      });
    });
  }
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
            {(() => {
              const baseStats = [
                {
                  icon: <FaFileAlt />, count: migrationJob?.files_modified ?? 0, label: "Files Modified",
                  meta: migrationJob?.files_modified === 0 ? "No files were modified during migration" : `${migrationJob?.files_modified} files updated`,
                  color: "#2563eb", bg: "#eff6ff",
                  category: "files" as const,
                },
                {
                  icon: <FaTools />, count: migrationJob?.issues_fixed ?? 0, label: "Issues Fixed",
                  meta: "All migration issues resolved",
                  color: "#10b981", bg: "#ecfdf5",
                  category: "issues" as const,
                },
                {
                  icon: <FaLayerGroup />, count: dependencyUpgradeCount, label: "Dependencies Updated",
                  meta: "Total dependencies updated",
                  color: "#8b5cf6", bg: "#f5f3ff",
                  category: "dependencies" as const,
                },
                {
                  icon: <FaShieldAlt />, count: reportedVulnerabilityCount ?? 0, label: "Vulnerabilities",
                  meta: "No active vulnerabilities found",
                  color: "#f97316", bg: "#fff7ed",
                  category: "vulnerabilities" as const,
                }
              ];

              const allStats = baseStats;

              return (
                <div style={{
                  display: "grid",
                  gridTemplateColumns: `repeat(${allStats.length}, minmax(0, 1fr))`,
                  gap: 12,
                  marginBottom: 12,
                  width: "100%"
                }}>
                  {allStats.map((stat, idx) => (
                    <div
                      key={idx}
                      onClick={() => void handleOpenReportDetails(stat.category)}
                      title={`Click to view details for ${stat.label}`}
                      style={{
                        background: "#ffffff",
                        border: `1px solid ${stat.color}15`,
                        borderRadius: 16,
                        padding: "16px 20px",
                        display: "flex",
                        gap: 16,
                        alignItems: "center",
                        boxShadow: `0 8px 30px -10px ${stat.color}25`,
                        position: 'relative',
                        overflow: 'hidden',
                        cursor: "pointer",
                        transition: "transform 0.15s ease, box-shadow 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = "translateY(-2px)";
                        e.currentTarget.style.boxShadow = `0 12px 35px -8px ${stat.color}40`;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = "translateY(0)";
                        e.currentTarget.style.boxShadow = `0 8px 30px -10px ${stat.color}25`;
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
              );
            })()}

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
                      icon: isLocalPath(migrationJob.source_repo) ? <FaFolderOpen /> : <FaGithub />,
                      isLink: true
                    },
                    {
                      label: "Target Repository",
                      value: migrationJob.target_repo,
                      icon: isLocalPath(migrationJob.target_repo) ? <FaFolderOpen /> : <FaGithub />,
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
                          {item.isLink && item.value ? (
                            (() => {
                              const link = getRepositoryLink(item.value);
                              return link ? (
                                <a href={link} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'none' }}>{item.value}</a>
                              ) : (item.value);
                            })()
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

                {(() => {
                  const transformationsCount =
                    migrationJob?.transformations_count ??
                    (migrationJob?.uiTransformations?.length ?? 0);
                  const overviewCards = [
                    {
                      icon: <FaFileAlt />,
                      title: "Files Modified",
                      desc: discoveryTotalFiles > 0
                        ? `${migrationJob.files_modified ?? 0} of ${discoveryTotalFiles} total files`
                        : "Code files updated during migration",
                      value: migrationJob.files_modified ?? 0,
                      footer: modifiedFilesBreakdown || (
                        discoveryTotalFiles > 0
                          ? `${discoveryJavaFiles} Java · ${discoveryJspFiles + discoveryJsfFiles} JSP/JSF · ${discoveryXmlFiles} XML`
                          : migrationJob.files_modified === 0 ? "No files modified" : `${migrationJob.files_modified} files updated`
                      ),
                      color: "#2563eb", bg: "#eff6ff", border: "#dbeafe", glow: "rgba(37,99,235,0.05)",
                      category: "files" as const,
                    },
                    {
                      icon: <FaCode />,
                      title: "Code Transmission",
                      desc: "Code transformation and migration logic applied",
                      value: transformationsCount,
                      footer: `${transformationsCount} transformations completed`,
                      color: "#7c3aed", bg: "#f5f3ff", border: "#ede9fe", glow: "rgba(124,58,237,0.05)",
                      category: "transformations" as const,
                    },
                    {
                      icon: <FaShieldAlt />,
                      title: "Dependency Updated",
                      desc: "Libraries and dependencies upgraded",
                      value: dependencyUpgradeCount,
                      footer: `${dependencyUpgradeCount} dependencies updated`,
                      color: "#10b981", bg: "#ecfdf5", border: "#d1fae5", glow: "rgba(16,185,129,0.05)",
                      category: "dependencies" as const,
                    }
                  ];

                  return (
                    <div style={{ display: "grid", gridTemplateColumns: `repeat(${overviewCards.length}, minmax(0, 1fr))`, gap: 12 }}>
                      {overviewCards.map((item, idx) => (
                    <div
                      key={idx}
                      onClick={() => void handleOpenReportDetails(item.category)}
                      title={`Click to view details for ${item.title}`}
                      style={{
                        background: item.bg,
                        border: `1px solid ${item.border}`,
                        borderRadius: 16,
                        padding: "16px 20px",
                        display: "flex",
                        flexDirection: "column",
                        position: "relative",
                        overflow: "hidden",
                        cursor: "pointer",
                        transition: "transform 0.15s ease, box-shadow 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = "translateY(-2px)";
                        e.currentTarget.style.boxShadow = `0 12px 30px -8px ${item.color}35`;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = "translateY(0)";
                        e.currentTarget.style.boxShadow = "none";
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
                      ))}
                    </div>
                  );
                })()}
              </div>
            </div>

            {/* Row: Dependency Updates (Full Width) */}
            <div style={{ background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "24px 28px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)", marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24 }}>
                    <FaLayerGroup />
                  </div>
                  <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#0f172a" }}>Dependency Updates</h3>
                  <span style={{
                    background: "#ecfdf5",
                    color: "#059669",
                    fontSize: 12,
                    fontWeight: 700,
                    padding: "2px 10px",
                    borderRadius: 20,
                    border: "1px solid #a7f3d0"
                  }}>
                    {dependencyUpgradeCount} Updated
                  </span>
                </div>

                <div style={{ position: "relative", width: 280 }}>
                  <input
                    type="text"
                    placeholder="Search dependencies..."
                    value={dependencySearchQuery}
                    onChange={(e) => setDependencySearchQuery(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "10px 16px 10px 40px",
                      borderRadius: 10,
                      border: "1px solid #e2e8f0",
                      fontSize: 13,
                      background: "#fff",
                      outline: "none",
                      boxShadow: "0 2px 8px rgba(0,0,0,0.05)"
                    }}
                  />
                  <div style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "#64748b", fontSize: 14 }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                  </div>
                </div>
              </div>

              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", width: 40 }}>#</th>
                      <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase" }}>Dependency</th>
                      <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", textAlign: "center" }}>Current Version</th>
                      <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", textAlign: "center" }}>Updated Version</th>
                      <th style={{ padding: "12px 16px", fontSize: 11, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", width: 120, textAlign: "center" }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredDependencies.length > 0 ? (
                      filteredDependencies.map((dep, idx) => (
                        <tr key={idx} style={{
                          backgroundColor: idx % 2 === 0 ? "#ffffff" : "#fbfdff",
                          borderBottom: "1px solid #f8fafc"
                        }}>
                  <td style={{ padding: "14px 16px", fontSize: 13, color: "#94a3b8", fontWeight: 500 }}>{idx + 1}.</td>
                  <td style={{ padding: "14px 16px", fontSize: 14, color: "#0f172a", fontWeight: 600 }}>
                    {dep.group_id}:{dep.artifact_id}
                  </td>
                  <td style={{ padding: "14px 16px", fontSize: 14, color: "#64748b", fontWeight: 500, textAlign: "center" }}>{dep.current_version}</td>
                  <td style={{ padding: "14px 16px", fontSize: 14, color: "#64748b", fontWeight: 500, textAlign: "center" }}>{dep.new_version}</td>
                  <td style={{ padding: "14px 16px", textAlign: "center" }}>
                    <span style={{
                      backgroundColor: "#ecfdf5",
                      color: "#059669",
                      fontSize: 11,
                      fontWeight: 700,
                      padding: "4px 10px",
                      borderRadius: "20px",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      border: "1px solid #a7f3d0"
                    }}>
                      <FaCheckCircle style={{ fontSize: 12 }} />
                      Updated
                    </span>
                  </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} style={{ padding: "40px", textAlign: "center", color: "#64748b", fontStyle: "italic", fontSize: 14 }}>
                          No dependency upgrades were recorded for this migration.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Source Code Transformations (GitHub-style Diff Layout) */}
            <div id="source-code-transformations-section" style={{ background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, overflow: "hidden", boxShadow: "0 4px 20px rgba(0,0,0,0.03)", marginBottom: 16 }}>
              {(() => {
                const current = diffData[selectedDiffIndex] || diffData[0];
                const modifiedCount = diffData.filter(f => f.status === "Modified").length;
                const addedCount = diffData.filter(f => f.status === "Added").length;
                const removedCount = diffData.filter(f => f.status === "Removed").length;

                return (
                  <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", height: 600 }}>
                    {/* Left Sidebar */}
                    <div style={{ background: "#ffffff", borderRight: "1px solid #e2e8f0", display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
                      <div style={{ padding: "24px", flexShrink: 0 }}>
                        <h3 style={{ margin: "0 0 16px 0", fontSize: 15, fontWeight: 800, color: "#0f172a" }}>Changed Files ({diffData.length})</h3>
                        <div style={{ display: "flex", gap: 14 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, color: "#2563eb" }}>
                            <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center", color: "#ffffff", fontSize: 8 }}>✔</div> {modifiedCount} Modified
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, color: "#10b981" }}>
                            <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#10b981", display: "flex", alignItems: "center", justifyContent: "center", color: "#ffffff", fontSize: 8 }}>+</div> {addedCount} Added
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, color: "#ef4444" }}>
                            <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#ef4444", display: "flex", alignItems: "center", justifyContent: "center", color: "#ffffff", fontSize: 8 }}>-</div> {removedCount} Removed
                          </div>
                        </div>
                      </div>

                      <div style={{ flex: 1, overflowY: "auto", borderTop: "1px solid #f1f5f9", minHeight: 0 }}>
                        {diffData.length === 0 ? (
                          <div style={{ padding: "32px 24px", textAlign: "center", color: "#94a3b8", fontSize: 13, fontStyle: "italic" }}>
                            {migrationJob?.status === "completed"
                              ? "No file changes recorded for this migration."
                              : "Migration in progress — file changes will appear here when complete."}
                          </div>
                        ) : diffData.map((file, idx) => (
                          <div
                            key={idx}
                            onClick={() => {
                              setSelectedDiffIndex(idx);
                              if (!file.category && file.relativePath) {
                                void loadFileDiff(file.relativePath);
                              }
                            }}
                            style={{
                              padding: "12px 24px",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              cursor: "pointer",
                              background: selectedDiffIndex === idx ? "#eff6ff" : "transparent",
                              transition: "all 0.15s",
                              borderLeft: selectedDiffIndex === idx ? "4px solid #2563eb" : "4px solid transparent"
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: 10, overflow: "hidden" }}>
                              <FaFileAlt style={{ color: file.category ? "#7c3aed" : "#2563eb", fontSize: 16, opacity: 0.8 }} />
                              <div style={{ overflow: "hidden" }}>
                                <span style={{
                                  fontSize: 13,
                                  fontWeight: selectedDiffIndex === idx ? 700 : 500,
                                  color: selectedDiffIndex === idx ? "#1d4ed8" : "#334155",
                                  whiteSpace: "nowrap",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                  display: "block",
                                }}>
                                  {file.file}
                                </span>
                                {file.category && (
                                  <span style={{ fontSize: 10, color: "#7c3aed", fontWeight: 700 }}>
                                    {file.category}
                                  </span>
                                )}
                              </div>
                            </div>
                            <span style={{
                              fontSize: 10,
                              fontWeight: 700,
                              padding: "2px 8px",
                              borderRadius: 6,
                              background: file.status === "Modified" ? "#dbeafe" : file.status === "Added" ? "#dcfce7" : "#fee2e2",
                              color: file.status === "Modified" ? "#1d4ed8" : file.status === "Added" ? "#059669" : "#dc2626",
                              flexShrink: 0,
                              marginLeft: 8,
                            }}>
                              {file.status}
                            </span>
                          </div>
                        ))}
                      </div>

                      <div style={{ padding: "16px", textAlign: "center", fontSize: 12, color: "#64748b", borderTop: "1px solid #f1f5f9", background: "#f8fafc", fontWeight: 600, flexShrink: 0 }}>
                        Click on a file to view changes
                      </div>
                    </div>

                    {/* Right Diff View */}
                    <div style={{ background: "#ffffff", display: "flex", flexDirection: "column", overflow: "hidden" }}>
                      {current ? (
                        <>
                          {/* Header */}
                          <div style={{ padding: "16px 28px", borderBottom: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#ffffff" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                              <FaCode style={{ color: current.category ? "#7c3aed" : "#2563eb", fontSize: 18 }} />
                              <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "#0f172a" }}>{current.file}</h4>
                              <span style={{
                                fontSize: 10,
                                fontWeight: 700,
                                padding: "2px 8px",
                                borderRadius: 6,
                                background: current.status === "Modified" ? "#dcfce7" : current.status === "Added" ? "#dcfce7" : "#fee2e2",
                                color: current.status === "Modified" ? "#059669" : current.status === "Added" ? "#059669" : "#dc2626",
                              }}>
                                {current.status}
                              </span>
                              {current.category && (
                                <span style={{
                                  fontSize: 10,
                                  fontWeight: 700,
                                  padding: "2px 8px",
                                  borderRadius: 6,
                                  background: "#f5f3ff",
                                  color: "#7c3aed",
                                  border: "1px solid #e9d5ff",
                                }}>
                                  {current.icon && <>{current.icon}&nbsp;</>}{current.category}
                                </span>
                              )}
                              {current.sourceFile && current.sourceFile !== current.file && (
                                <span style={{ fontSize: 11, color: "#64748b", fontFamily: "monospace" }}>
                                  from: {current.sourceFile}
                                </span>
                              )}
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
                              <div style={{ fontSize: 12, fontWeight: 700 }}>
                                <span style={{ color: "#10b981" }}>+ {current.additions ?? 0} additions</span>
                                <span style={{ color: "#ef4444", marginLeft: 12 }}>- {current.deletions ?? 0} deletions</span>
                              </div>
                              <button
                                type="button"
                                onClick={() => void handleCopyDiffCode(current.afterLines ?? [])}
                                title={copiedDiffCode ? "Code copied" : "Copy generated code"}
                                aria-label={copiedDiffCode ? "Code copied" : "Copy generated code"}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  width: 30,
                                  height: 30,
                                  padding: 0,
                                  border: "1px solid #cbd5e1",
                                  borderRadius: 6,
                                  background: copiedDiffCode ? "#ecfdf5" : "#ffffff",
                                  color: copiedDiffCode ? "#059669" : "#475569",
                                  cursor: "pointer",
                                }}
                              >
                                {copiedDiffCode ? <FaCheck size={12} /> : <FaCopy size={12} />}
                              </button>
                              {Boolean(
                                current &&
                                !String(current.file || "").toLowerCase().endsWith(".css") &&
                                !String(current.file || "").toLowerCase().endsWith(".java") &&
                                !String(current.file || "").toLowerCase().endsWith(".xml") &&
                                !String(current.file || "").toLowerCase().endsWith(".json") &&
                                !String(current.file || "").toLowerCase().endsWith(".sql") &&
                                !String(current.file || "").toLowerCase().endsWith(".properties") &&
                                (
                                  current.category?.toLowerCase().includes("jsp") ||
                                  current.category?.toLowerCase().includes("jsf") ||
                                  current.category?.toLowerCase().includes("ui") ||
                                  current.category?.toLowerCase().includes("angular") ||
                                  current.category?.toLowerCase().includes("react") ||
                                  /\.(tsx|jsx|vue|html)$/i.test(current.file || "") ||
                                  (/\.component\.ts$/i.test(current.file || "")) ||
                                  Boolean(current.targetSourceFile && /\.(tsx|jsx|ts|html)$/i.test(current.targetSourceFile))
                                )
                              ) && (
                                <button
                                  type="button"
                                  onClick={(e) => handleShowReactUi(current, e)}
                                  title="Show the migrated UI preview"
                                  aria-label="Show the migrated UI preview"
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: 6,
                                    height: 30,
                                    padding: "0 10px",
                                    border: "1px solid #bfdbfe",
                                    borderRadius: 6,
                                    background: "#eff6ff",
                                    color: "#1d4ed8",
                                    cursor: "pointer",
                                    fontSize: 12,
                                    fontWeight: 700,
                                  }}
                                >
                                  <FaExternalLinkAlt size={11} />
                                  View UI
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Content Area */}
                          <div style={{ flex: 1, overflow: "auto", background: "#ffffff" }}>
                            {fileDiffLoading && !current.beforeLines?.length && !current.afterLines?.length ? (
                              <div style={{ padding: 32, color: "#64748b", textAlign: "center" }}>
                                Loading file diff...
                              </div>
                            ) : fileDiffError && !current.beforeLines?.length && !current.afterLines?.length ? (
                              <div style={{ padding: 32, color: "#b91c1c", textAlign: "center" }}>
                                {fileDiffError}
                              </div>
                            ) : (
                            <>
                            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>
                              <tbody>
                                {[
                                  ...(current.beforeLines ?? []).map(l => ({ ...l, origin: 'before' })),
                                  ...(current.afterLines ?? []).map(l => ({ ...l, origin: 'after' }))
                                ].sort((a,b) => a.num - b.num).map((line, idx) => {
                                  const isRemoved = line.type === 'removed';
                                  const isAdded = line.type === 'added';
                                  const bgColor = isRemoved ? "#fff1f2" : isAdded ? "#f0fdf4" : "transparent";
                                  const sign = isRemoved ? "-" : isAdded ? "+" : " ";
                                  const textColor = isRemoved ? "#991b1b" : isAdded ? "#166534" : "#475569";

                                  return (
                                    <tr key={idx} style={{ background: bgColor, borderBottom: "1px solid rgba(0,0,0,0.02)" }}>
                                      <td style={{ width: 45, padding: "2px 10px", textAlign: "right", color: "#94a3b8", background: "rgba(0,0,0,0.02)", userSelect: "none", borderRight: "1px solid #e2e8f0" }}>{line.origin === 'before' ? line.num : ""}</td>
                                      <td style={{ width: 45, padding: "2px 10px", textAlign: "right", color: "#94a3b8", background: "rgba(0,0,0,0.02)", userSelect: "none", borderRight: "1px solid #e2e8f0" }}>{line.origin === 'after' ? line.num : line.type === 'normal' ? line.num : ""}</td>
                                      <td style={{ width: 30, padding: "2px 0", textAlign: "center", color: textColor, fontWeight: 800, userSelect: "none" }}>{sign}</td>
                                      <td style={{ padding: "2px 12px", color: textColor, whiteSpace: "pre-wrap", flex: 1 }}>{line.text.replace(/^[+-]\s*/, '')}</td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                            {(((current.beforeLines?.length ?? 0) === 0) && ((current.afterLines?.length ?? 0) === 0)) && (
                              <div style={{ padding: 60, textAlign: "center", color: "#94a3b8", fontStyle: "italic" }}>
                                Select a modified file from the sidebar to view detailed transformations.
                              </div>
                            )}
                            </>
                            )}
                          </div>
                        </>
                      ) : (
                        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#94a3b8", padding: 40 }}>
                          <FaCode style={{ fontSize: 36, color: "#cbd5e1", marginBottom: 12 }} />
                          <div style={{ fontSize: 14, fontWeight: 600, color: "#64748b" }}>No files to display</div>
                          <div style={{ fontSize: 12, marginTop: 4 }}>
                            {migrationJob?.status === "completed"
                              ? "No file changes were recorded for this migration."
                              : "File transformations will appear here once available."}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>

            {migrationJob.run_cycode && <MigrationCycodeSection report={migrationJob.cycode_report} />}

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
                    runTests={Boolean(migrationJob.run_tests ?? migrationJob.runTests ?? runTests)}
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
                        migrationJob={migrationJob}
                        runFossa={Boolean(migrationJob.run_fossa ?? migrationJob.runFossa ?? runFossa)}
                        fossaLicenseIssueCount={migrationJob.fossa_license_issues ?? (migrationJob.fossa_report as any)?.license_issues ?? (migrationJob as any)?.license_issues}
                        fossaVulnerabilityTotal={migrationJob.fossa_vulnerabilities ?? (migrationJob.fossa_report as any)?.vulnerabilities ?? (migrationJob.fossa_report as any)?.vulnerability_count}
                        fossaOutdatedCount={migrationJob.fossa_outdated_dependencies ?? (migrationJob.fossa_report as any)?.outdated_dependencies ?? (migrationJob as any)?.outdated_packages}
 
                        fossaTotalDependencies={migrationJob.fossa_total_dependencies ?? (migrationJob.fossa_report as any)?.total_dependencies ?? (migrationJob as any)?.dependencies}
 
                        fossaTotalLicenses={(migrationJob as any)?.fossa_total_licenses ?? (migrationJob.fossa_report as any)?.total_licenses ?? (migrationJob.fossa_report as any)?.license_count ?? (migrationJob.fossa_report as any)?.licenses ?? (migrationJob as any)?.licenses}
 
                        fossaPolicyStatus={migrationJob.fossa_policy_status || (migrationJob.fossa_report as any)?.policy_status || (migrationJob as any)?.status}
                        fossaScanMode={migrationJob.fossa_scan_mode || (migrationJob.fossa_report as any)?.scan_mode}
                        fossaErrorMessage={migrationJob.fossa_error_message || (migrationJob.fossa_report as any)?.error_message}
                        fossaAnalysisUrl={fossaAnalysisUrl || migrationJob.fossa_analysis_url || (migrationJob.fossa_report as any)?.analysis_url || (migrationJob as any)?.project_url}
                        fossaRealScan={Boolean(fossaIsRealScan || migrationJob.fossa_real_scan || (migrationJob.fossa_report as any)?.real_scan)}
                      />
                   </div>

                   <div style={{ height: 1, background: "#f1f5f9" }} />

                   <div style={{ flex: 1 }}>
                     <MigrationJmeterSection
                        styles={{...styles, reportSection: { padding: 0, border: 'none', background: 'transparent', boxShadow: 'none' }}}
                        apiEndpointsValidated={0}
                        apiEndpointsWorking={0}
                      />
                   </div>
                </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 16 }}>
                {/* Proposed Test Case Information — only shown when Functional Testing was enabled */}
                {(runFunctionalTests ?? migrationJob.run_functional_tests ?? true) && (
                  <MigrationProposedTestSection
                    styles={styles}
                    migrationJob={migrationJob}
                  />
                )}

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
        {sandboxEntry && (
          <FrameworkPageSandbox
            fileName={sandboxEntry.fileName}
            code={sandboxEntry.code}
            css={sandboxEntry.css}
            allFiles={(migrationJob?.uiTransformations ?? []).map((t: any) => ({
              fileName: t.targetSourceFile ?? t.file ?? "MigratedPage.tsx",
              code: (t.afterLines ?? []) as Array<{ text: string }>,
            }))}
            onClose={() => setSandboxEntry(null)}
          />
        )}
        <MigrationReportDetailModal
          isOpen={detailModalCategory !== null}
          category={detailModalCategory}
          data={detailModalCategory ? reportDetailsCache[detailModalCategory] ?? null : null}
          loading={detailModalLoading}
          error={detailModalError}
          onClose={() => setDetailModalCategory(null)}
          onSelectFileForDiff={handleSelectFileForDiff}
        />
      </React.Suspense>
    </div>
  );
}
