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
  FaDownload,
  FaTerminal,
  FaBug,
  FaTasks,
  FaFileArchive,
  FaFileCode,
  FaMarkdown,
  FaLock,
  FaRocket,
  FaSpinner,
  FaArrowRight,
} from "react-icons/fa";
import { wizardStyles as styles } from "@/shared/components/wizard/wizardStyles";
import { renderWizardIconBadge } from "@/shared/components/wizard";
import {
  downloadUnitTestReport,
  downloadMigratedProject,
  downloadProposedTestReport,
  getMigrationFileDiff,
  getMigrationLogs,
  rerunMigrationTests,
  getMigrationDetail,
  getMigrationReportDetails,
  type ReportDetailsResponse,
  type SonarIssueDetail,
  type SonarHotspotDetail,
  type SonarReport,
} from "../services/resultService";
import { MigrationReportDetailModal } from "./MigrationReportDetailModal";
import { compareSemVer, getMinimumBaselineForJava } from "@/features/modernization/components/DetectedDependenciesTable";
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
  dependencyAnalysis?: any;
  runSonar: boolean;
  runFossa: boolean;
  runTests?: boolean;
  runFunctionalTests?: boolean;
  selectedLLMProvider: string;
  useLLMTests: boolean;
  isJUnitOnly?: boolean;
  resetWizard: () => void;
  onBack: () => void;
  onError: (message: string) => void;
}

function CopyAllDependenciesButton({
  text,
  label = "Copy All",
  title = "Copy all dependencies to clipboard",
  style = {},
}: {
  text: string;
  label?: string;
  title?: string;
  style?: React.CSSProperties;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!text) return;
    void navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? "All dependencies copied!" : title}
      aria-label={copied ? "Copied All" : title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "6px 12px",
        borderRadius: "6px",
        border: "1px solid " + (copied ? "#86efac" : "#cbd5e1"),
        background: copied ? "#ecfdf5" : "#ffffff",
        color: copied ? "#166534" : "#1e293b",
        fontWeight: 600,
        fontSize: "12px",
        cursor: "pointer",
        flexShrink: 0,
        boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
        transition: "all 0.15s ease",
        ...style,
      }}
      onMouseEnter={(e) => {
        if (!copied) {
          e.currentTarget.style.background = "#f8fafc";
          e.currentTarget.style.borderColor = "#94a3b8";
        }
      }}
      onMouseLeave={(e) => {
        if (!copied) {
          e.currentTarget.style.background = "#ffffff";
          e.currentTarget.style.borderColor = "#cbd5e1";
        }
      }}
    >
      {copied ? <FaCheck size={12} style={{ color: "#166534" }} /> : <FaCopy size={12} />}
      <span>{copied ? "Copied All!" : label}</span>
    </button>
  );
}

export function ResultReportView({
  resultExec,
  repoAnalysis,
  dependencyAnalysis,
  runSonar,
  runFossa,
  runTests,
  runFunctionalTests,
  selectedLLMProvider,
  useLLMTests,
  isJUnitOnly = false,
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

  useEffect(() => {
    let pollInterval: ReturnType<typeof setInterval>;
    const rawExecStatus = (migrationJob?.test_pipeline as any)?.execution_status;
    if (rawExecStatus === "IN_PROGRESS" && migrationJob?.job_id) {
      pollInterval = setInterval(async () => {
        try {
          const updatedJob = await getMigrationDetail(migrationJob.job_id);
          if (updatedJob) {
            setMigrationJob(updatedJob);
          }
        } catch (e) {
          console.error("Failed to poll migration job details", e);
        }
      }, 5000);
    }
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [migrationJob?.job_id, (migrationJob?.test_pipeline as any)?.execution_status, setMigrationJob]);

  const [activeTab, setActiveTab] = useState<
    "general" | "unit-test" | "functional-test" | "sonarqube" | "fossa" | "logs-issues" | "reports"
  >(isJUnitOnly ? "unit-test" : "general");
  const [selectedDiffIndex, setSelectedDiffIndex] = useState<number>(0);
  const [loadedFileDiffs, setLoadedFileDiffs] = useState<Record<string, {
    beforeLines: Array<{ num: number; text: string; type: string }>;
    afterLines: Array<{ num: number; text: string; type: string }>;
  }>>({});
  const [fileDiffError, setFileDiffError] = useState<string | null>(null);
  const [fileDiffLoading, setFileDiffLoading] = useState(false);
  const [copiedDiffCode, setCopiedDiffCode] = useState(false);
  const [copiedRepo, setCopiedRepo] = useState<"source" | "target" | null>(null);

  const handleCopyRepo = (text: string, type: "source" | "target") => {
    if (!text) return;
    void navigator.clipboard.writeText(text);
    setCopiedRepo(type);
    window.setTimeout(() => setCopiedRepo(null), 1800);
  };
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

  // Determine if this is a Java 21 repository flow
  const isJava21 = React.useMemo(() => {
    if ((repoAnalysis as any)?.isJava21 || (migrationJob as any)?.isJava21) return true;
    const rawVersion = (
      repoAnalysis?.java_version ||
      repoAnalysis?.current_java_version ||
      migrationJob?.source_java_version ||
      (migrationJob as any)?.javaVersion ||
      ""
    ).toString().trim().toLowerCase();
    return rawVersion === "21" || rawVersion === "java 21" || rawVersion === "1.21" || rawVersion.includes("jdk21") || rawVersion.includes("jdk 21");
  }, [repoAnalysis, migrationJob]);

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

  const handleDownloadFunctionalTestReport = async () => {
    if (!migrationJob) return;
    try {
      const blob = await downloadProposedTestReport(migrationJob.job_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `proposed-test-report-${migrationJob.job_id}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to download functional test report");
    }
  };

  const handleDownloadMigratedProjectZip = async () => {
    if (!migrationJob) return;
    try {
      const blob = await downloadMigratedProject(migrationJob.job_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `modernized-project-${migrationJob.job_id}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to download migrated project ZIP");
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
  const rawDepList: Array<DependencyInfo | Record<string, unknown>> = (
    migrationJob?.dependency_upgrades?.length
      ? migrationJob.dependency_upgrades
      : (migrationJob?.dependencies?.length
        ? migrationJob.dependencies
        : (dependencyAnalysis?.dependencies?.length
          ? dependencyAnalysis.dependencies
          : (repoAnalysis?.dependencies?.length
            ? repoAnalysis.dependencies
            : [])))
  ) as Array<DependencyInfo | Record<string, unknown>>;

  const detectedDependencyCount = migrationJob?.dependency_count ?? rawDepList.length;

  const analyzedMap = new Map<string, any>();
  if (dependencyAnalysis?.dependencies) {
    for (const item of dependencyAnalysis.dependencies) {
      if (item.id) analyzedMap.set(item.id.toLowerCase(), item);
      if (item.group && item.artifact) {
        analyzedMap.set(`${item.group}:${item.artifact}`.toLowerCase(), item);
      }
      if (item.artifact) {
        analyzedMap.set(item.artifact.toLowerCase(), item);
      }
    }
  }

  const dependencyUpdates = rawDepList.map((dep) => {
    const source = dep as Record<string, unknown> & {
      id?: string;
      group?: string;
      group_id?: string;
      groupId?: string;
      artifact?: string;
      artifact_id?: string;
      artifactId?: string;
      coordinate?: string;
      current_version?: string | null;
      version?: string | null;
      resolved_version?: string | null;
      old_version?: string | null;
      oldVersion?: string | null;
      sourceVersion?: string | null;
      new_version?: string | null;
      newVersion?: string | null;
      recommended_version?: string | null;
      resolvedTargetVersion?: string | null;
      status?: string | null;
      upgrade_status?: string | null;
    };

    const gid = source.group_id || source.groupId || source.group || source.coordinate?.split(":")[0] || "dependency";
    const aid = source.artifact_id || source.artifactId || source.artifact || source.coordinate?.split(":")[1] || "artifact";
    const currentVer = source.current_version || source.version || source.resolved_version || source.old_version || source.oldVersion || source.sourceVersion || "managed version";

    const coord = `${gid}:${aid}`.toLowerCase();
    const analysisMatch = analyzedMap.get(coord) || analyzedMap.get(aid.toLowerCase()) || analyzedMap.get(gid.toLowerCase());

    let newVer = source.new_version || source.newVersion || source.recommended_version || (source as any).resolvedTargetVersion || analysisMatch?.recommended_version;

    const targetJavaNum = parseInt(String(migrationJob?.target_java_version || repoAnalysis?.target_java_version || "17").replace(/\D/g, "") || "17", 10);
    const baseline = getMinimumBaselineForJava(targetJavaNum);
    const gidL = gid.toLowerCase();
    const aidL = aid.toLowerCase();

    let baselineFloor = "";
    if (gidL.includes("springframework.boot") || aidL.includes("spring-boot")) {
      baselineFloor = baseline.boot;
    } else if (gidL.includes("springframework") || aidL.includes("spring")) {
      baselineFloor = baseline.fw;
    } else if (aidL.includes("log4j") || gidL.includes("log4j")) {
      baselineFloor = baseline.log4j;
    } else if (aidL.includes("logback")) {
      baselineFloor = baseline.logback;
    } else if (aidL.includes("slf4j")) {
      baselineFloor = baseline.slf4j;
    } else if (aidL.includes("snakeyaml") || gidL.includes("org.yaml")) {
      baselineFloor = baseline.snakeyaml;
    } else if (aidL.includes("jackson") || gidL.includes("jackson")) {
      baselineFloor = baseline.jackson;
    } else if (gidL.includes("hibernate") || aidL.includes("hibernate")) {
      baselineFloor = targetJavaNum >= 17 ? "6.4.4.Final" : "5.6.15.Final";
    }

    const isValidCurrent = currentVer && currentVer !== "managed version" && currentVer !== "Unknown";

    if (!newVer || newVer === "Not Determined" || newVer === "updated version" || newVer === "Unknown") {
      if (isValidCurrent && baselineFloor) {
        if (compareSemVer(currentVer, baselineFloor) >= 0) {
          newVer = currentVer;
        } else {
          newVer = baselineFloor;
        }
      } else if (baselineFloor) {
        newVer = baselineFloor;
      } else if (isValidCurrent) {
        newVer = currentVer;
      } else {
        newVer = "Updated";
      }
    } else if (isValidCurrent && newVer !== "N/A" && compareSemVer(currentVer, newVer) > 0) {
      // Golden Rule: Never allow an unintended downgrade in the final report
      newVer = currentVer;
    }

    let status = source.status || source.upgrade_status || "UPGRADED";
    if (isValidCurrent && newVer && compareSemVer(currentVer, newVer) === 0) {
      status = "ALREADY COMPATIBLE";
    } else if (isValidCurrent && newVer && compareSemVer(currentVer, newVer) < 0) {
      status = "UPGRADED";
    }

    return {
      group_id: gid,
      artifact_id: aid,
      current_version: currentVer,
      new_version: newVer,
      status,
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
              <span>{isJUnitOnly ? "Loading JUnit test summary..." : "Loading migration report..."}</span>
            </div>
          </div>
        }
      >
        {migrationJob && isJUnitOnly && (
          <div style={{ width: "100%", padding: "14px 20px" }}>
            <MigrationUnitTestSection
              styles={{...styles, reportSection: { width: '100%', maxWidth: 'none', margin: 0 }}}
              migrationJob={migrationJob}
              repoAnalysis={repoAnalysis}
              isJUnitOnly={true}
              testSummaryReportDate={testSummaryReportDate}
              migrationJavaVersion={migrationJob.target_java_version}
              summaryItems={testSummaryItems}
              testsRun={testsRun}
              runTests={Boolean(migrationJob.run_tests ?? migrationJob.runTests ?? runTests)}
              onDownloadUnitTestReport={handleDownloadUnitTestReport}
              onGenerateUnitTests={handleRerunTests}
              isGenerating={rerunTestsLoading}
            />
          </div>
        )}

        {migrationJob && !isJUnitOnly && (
          <div style={{ ...styles.reportContainer, gap: 6, width: "100%", padding: "6px 12px" }}>
            {/* Top Header Card */}
            <div style={{
              background: "linear-gradient(108.4deg, #003087 4.4%, #0052cc 44.5%, #0073e6 94.6%)",
              borderRadius: 14,
              padding: "12px 24px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 8,
              boxShadow: "0 8px 30px rgba(0, 82, 204, 0.18)",
              color: "#ffffff",
              position: "relative",
              overflow: "hidden",
              width: "100%",
              minHeight: 92
            }}>
              {/* Abstract Wave Overlays and Patterns */}
              <div style={{ position: "absolute", left: "-5%", top: "-10%", width: "40%", height: "120%", background: "radial-gradient(circle, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0) 70%)", transform: "rotate(-15deg)", pointerEvents: "none" }} />
              <div style={{ position: "absolute", right: "10%", bottom: "-20%", width: "50%", height: "100%", background: "radial-gradient(circle, rgba(0,115,230,0.3) 0%, rgba(0,0,0,0) 80%)", pointerEvents: "none" }} />

              <div style={{ position: "absolute", left: "45%", top: "40%", opacity: 0.08, pointerEvents: "none", display: "grid", gridTemplateColumns: "repeat(5, 6px)", gap: "8px" }}>
                {Array.from({ length: 25 }).map((_, i) => <div key={i} style={{ width: 3, height: 3, borderRadius: "50%", background: "#ffffff" }} />)}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 16, zIndex: 1 }}>
                <div style={{
                  width: 52, height: 52, borderRadius: "50%",
                  background: "rgba(0, 120, 120, 0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  border: "1px solid rgba(34, 197, 94, 0.25)",
                  boxShadow: "0 0 12px rgba(34, 197, 94, 0.2)"
                }}>
                  <div style={{
                    width: 34, height: 34, borderRadius: "50%",
                    background: "#ffffff",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: "#22c55e", fontSize: 20,
                    boxShadow: "0 3px 8px rgba(0, 0, 0, 0.15)"
                  }}>
                    <FaCheckCircle />
                  </div>
                </div>
                <div>
                  <h2 style={{ margin: "0 0 2px 0", fontSize: 24, fontWeight: 800, color: "#ffffff", letterSpacing: "-0.01em" }}>
                    {isJUnitOnly ? "JUnit Test Summary" : "Migration Report"}
                  </h2>
                  <p style={{ margin: 0, color: "rgba(255, 255, 255, 0.9)", fontSize: 13, lineHeight: 1.4, fontWeight: 500, maxWidth: 460 }}>
                    {isJUnitOnly
                      ? "JUnit test suite execution summary and test coverage analysis for your project."
                      : `Your project has been successfully modernized from Java ${migrationJob.source_java_version} to Java ${migrationJob.target_java_version}.`}
                  </p>
                </div>
              </div>

              {!isJUnitOnly && (
                <div style={{ display: "flex", alignItems: "center", gap: 18, zIndex: 1 }}>
                  {/* Java Version Badges Container */}
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    background: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: 16,
                    padding: "6px 14px"
                  }}>
                    <div style={{
                      background: "rgba(255, 255, 255, 0.06)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      borderRadius: 10,
                      padding: "6px 12px",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      minWidth: 105,
                      backdropFilter: "blur(8px)"
                    }}>
                      <div style={{ background: "rgba(0, 0, 0, 0.2)", width: 30, height: 30, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid rgba(255, 255, 255, 0.08)", flexShrink: 0 }}>
                        <svg width="16" height="16" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
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
                        <div style={{ fontSize: 14, fontWeight: 700, color: "#ffffff", lineHeight: 1.1 }}>Java {migrationJob.source_java_version}</div>
                        <div style={{ fontSize: 10, color: "rgba(255, 255, 255, 0.5)", fontWeight: 500, marginTop: 1 }}>Legacy</div>
                      </div>
                    </div>

                    <span style={{ color: "rgba(255,255,255,0.4)", fontSize: 14, fontWeight: 600 }}>→</span>

                    <div style={{
                      background: "rgba(255, 255, 255, 0.06)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      borderRadius: 10,
                      padding: "6px 12px",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      minWidth: 115,
                      backdropFilter: "blur(8px)"
                    }}>
                      <div style={{ background: "rgba(0, 0, 0, 0.2)", width: 30, height: 30, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid rgba(255, 255, 255, 0.08)", flexShrink: 0 }}>
                        <svg width="16" height="16" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
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
                        <div style={{ fontSize: 14, fontWeight: 700, color: "#ffffff", lineHeight: 1.1 }}>Java {migrationJob.target_java_version}</div>
                        <span style={{
                          background: "rgba(16, 185, 129, 0.2)",
                          color: "#34d399",
                          border: "1px solid rgba(16, 185, 129, 0.25)",
                          fontSize: 8.5,
                          fontWeight: 700,
                          padding: "1px 5px",
                          borderRadius: 4,
                          marginTop: 1,
                          display: "inline-block",
                          textTransform: "uppercase"
                        }}>Modernized</span>
                      </div>
                    </div>
                  </div>

                  {/* Vertical Divider line */}
                  <div style={{ width: 1, height: 38, background: "rgba(255, 255, 255, 0.2)" }} />

                  {/* Timestamp and elapsed details */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 5, minWidth: 135 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <FaRegCalendarAlt style={{ color: "rgba(255, 255, 255, 0.6)", fontSize: 13 }} />
                      <div style={{ textAlign: "left" }}>
                        <div style={{ fontSize: 10, color: "rgba(255, 255, 255, 0.5)", fontWeight: 600, textTransform: "uppercase" }}>Migration Date</div>
                        <div style={{ fontSize: 12.5, color: "#ffffff", fontWeight: 700 }}>
                          {migrationJob.completed_at ? new Date(migrationJob.completed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : "Sep 11, 2026"}, {migrationJob.completed_at ? new Date(migrationJob.completed_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }) : "3:00 PM"}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <FaStopwatch style={{ color: "rgba(255, 255, 255, 0.6)", fontSize: 13 }} />
                      <div style={{ textAlign: "left" }}>
                        <div style={{ fontSize: 10, color: "rgba(255, 255, 255, 0.5)", fontWeight: 600, textTransform: "uppercase" }}>Duration</div>
                        <div style={{ fontSize: 13, color: "#ffffff", fontWeight: 800, fontFamily: "'JetBrains Mono', monospace" }}>
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
              )}
            </div>

            {/* Single-Line Top Metrics Grid (5 Cards in 1 Row) */}
            {!isJUnitOnly && (() => {
              const transformationsCount = migrationJob?.transformations_count ?? (migrationJob?.uiTransformations?.length ?? 0);

              const topHeroRowStats = [
                {
                  key: "files",
                  icon: <FaFileAlt />,
                  count: migrationJob?.files_modified ?? 0,
                  label: "Files Modified",
                  meta: discoveryTotalFiles > 0 ? `${migrationJob?.files_modified ?? 0} of ${discoveryTotalFiles} files updated` : `${migrationJob?.files_modified ?? 0} files modified`,
                  color: "#2563eb",
                  bg: "#eff6ff",
                  targetTab: "general" as const,
                  category: "files" as const,
                },
                {
                  key: "issues",
                  icon: <FaTools />,
                  count: migrationJob?.issues_fixed ?? 0,
                  label: "Issues Fixed",
                  meta: "All migration issues resolved",
                  color: "#10b981",
                  bg: "#ecfdf5",
                  targetTab: "logs-issues" as const,
                  category: "issues" as const,
                },
                {
                  key: "dependencies",
                  icon: <FaLayerGroup />,
                  count: dependencyUpgradeCount,
                  label: "Dependencies Updated",
                  meta: `${detectedDependencyCount} total dependencies detected`,
                  color: "#8b5cf6",
                  bg: "#f5f3ff",
                  targetTab: "general" as const,
                  category: "dependencies" as const,
                },
                {
                  key: "transmission",
                  icon: <FaCode />,
                  count: transformationsCount,
                  label: "Code Transmission",
                  meta: `${transformationsCount} transformations completed`,
                  color: "#d946ef",
                  bg: "#fdf4ff",
                  targetTab: "general" as const,
                  category: "transformations" as const,
                },
                {
                  key: "vulnerabilities",
                  icon: <FaShieldAlt />,
                  count: reportedVulnerabilityCount == null ? "N/A" : reportedVulnerabilityCount,
                  label: "Vulnerabilities",
                  meta: vulnerabilityMeta,
                  color: reportedVulnerabilityCount == null ? "#d97706" : reportedVulnerabilityCount > 0 ? "#dc2626" : "#16a34a",
                  bg: reportedVulnerabilityCount == null ? "#fff7ed" : reportedVulnerabilityCount > 0 ? "#fff1f2" : "#f0fdf4",
                  targetTab: "sonarqube" as const,
                  category: "vulnerabilities" as const,
                },
              ];

              return (
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
                  gap: 8,
                  marginBottom: 8,
                  width: "100%"
                }}>
                  {topHeroRowStats.map((stat) => (
                    <div
                      key={stat.key}
                      onClick={() => {
                        setActiveTab(stat.targetTab);
                        void handleOpenReportDetails(stat.category);
                      }}
                      title={`Click to open ${stat.label} details`}
                      style={{
                        background: "#ffffff",
                        border: `1px solid ${stat.color}25`,
                        borderRadius: 14,
                        padding: "10px 14px",
                        display: "flex",
                        gap: 10,
                        alignItems: "center",
                        boxShadow: `0 4px 18px -6px ${stat.color}18`,
                        position: "relative",
                        overflow: "hidden",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = "translateY(-2px)";
                        e.currentTarget.style.boxShadow = `0 8px 24px -4px ${stat.color}30`;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = "translateY(0)";
                        e.currentTarget.style.boxShadow = `0 4px 18px -6px ${stat.color}18`;
                      }}
                    >
                      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 3, background: stat.color, opacity: 0.35 }} />
                      <div style={{ background: stat.bg, color: stat.color, width: 40, height: 40, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 19, flexShrink: 0 }}>
                        {stat.icon}
                      </div>
                      <div style={{ overflow: "hidden" }}>
                        <div style={{ fontSize: 22, fontWeight: 800, color: "#0f172a", lineHeight: 1, marginBottom: 2 }}>{stat.count}</div>
                        <div style={{ fontSize: 12.5, fontWeight: 700, color: "#1e293b", marginBottom: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{stat.label}</div>
                        <div style={{ fontSize: 10.5, color: "#64748b", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontWeight: 500 }}>{stat.meta}</div>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}

            {/* Smart Connected Repository Transformation Pipeline (Placed Above Tabs) */}
            {!isJUnitOnly && (
              <div style={{
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: 16,
                padding: "14px 18px",
                boxShadow: "0 4px 20px rgba(0, 48, 135, 0.04)",
                position: "relative",
                overflow: "hidden",
                marginBottom: 4
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ background: "linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)", color: "#2563eb", width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, border: "1px solid #bfdbfe" }}>
                      <FaLayerGroup />
                    </div>
                    <div>
                      <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "#0f172a" }}>
                        {isJUnitOnly ? "JUnit Test Case Generator" : "Repository Information"}
                      </h3>
                      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 500 }}>
                        {isJUnitOnly ? "Connected repository — Generate and execute Unit Tests for your workspace" : "Connected source and modernized target workspace architecture"}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{
                      background: "linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%)",
                      color: "#166534",
                      fontSize: 11,
                      fontWeight: 800,
                      padding: "3px 12px",
                      borderRadius: 20,
                      border: "1px solid #86efac",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 5
                    }}>
                      <FaCheckCircle size={11} /> {isJUnitOnly ? "JUnit Mode Active" : "Modernized"}
                    </span>
                  </div>
                </div>

                {/* Pipeline Flow Grid */}
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto 1fr",
                  gap: 16,
                  alignItems: "center",
                  background: "#f8fafc",
                  border: "1px solid #f1f5f9",
                  borderRadius: 14,
                  padding: "12px 16px"
                }}>
                  {/* Source Repo Card */}
                  <div style={{
                    background: "#ffffff",
                    border: "1px solid #e2e8f0",
                    borderRadius: 12,
                    padding: "10px 14px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                    boxShadow: "0 2px 8px rgba(0,0,0,0.02)"
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>
                        <span style={{ color: "#475569", fontSize: 14 }}>
                          {isLocalPath(migrationJob.source_repo) ? <FaFolderOpen /> : <FaGithub />}
                        </span>
                        Source Repository
                      </div>
                      <span style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px", borderRadius: 6, background: "#f1f5f9", color: "#475569", border: "1px solid #e2e8f0" }}>
                        Java {migrationJob.source_java_version || "?"} Legacy
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#1e293b", wordBreak: "break-all", fontFamily: "'JetBrains Mono', monospace" }}>
                        {migrationJob.source_repo || "N/A"}
                      </div>
                      <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                        <button
                          type="button"
                          onClick={() => handleCopyRepo(migrationJob.source_repo, "source")}
                          title={copiedRepo === "source" ? "Copied!" : "Copy Source Repo Path"}
                          style={{
                            background: copiedRepo === "source" ? "#dcfce7" : "#f1f5f9",
                            color: copiedRepo === "source" ? "#166534" : "#64748b",
                            border: "1px solid #cbd5e1",
                            borderRadius: 6,
                            width: 28,
                            height: 28,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            transition: "all 0.15s ease"
                          }}
                        >
                          {copiedRepo === "source" ? <FaCheck size={11} /> : <FaCopy size={11} />}
                        </button>
                        {!isLocalPath(migrationJob.source_repo) && getRepositoryLink(migrationJob.source_repo) && (
                          <a
                            href={getRepositoryLink(migrationJob.source_repo)!}
                            target="_blank"
                            rel="noopener noreferrer"
                            title="Open Source Repository"
                            style={{
                              background: "#eff6ff",
                              color: "#2563eb",
                              border: "1px solid #bfdbfe",
                              borderRadius: 6,
                              width: 28,
                              height: 28,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              textDecoration: "none"
                            }}
                          >
                            <FaExternalLinkAlt size={10} />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Center Flow Connector */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "0 6px" }}>
                    <div style={{ width: 28, height: 2, background: "linear-gradient(90deg, #93c5fd 0%, #2563eb 100%)", borderRadius: 2 }} />
                    <div style={{
                      width: 30,
                      height: 30,
                      borderRadius: "50%",
                      background: "linear-gradient(135deg, #003087 0%, #0052cc 100%)",
                      color: "#ffffff",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      boxShadow: "0 4px 12px rgba(0, 82, 204, 0.28)",
                      border: "2px solid #ffffff",
                      flexShrink: 0
                    }}>
                      <FaArrowRight size={12} />
                    </div>
                    <div style={{ width: 28, height: 2, background: "linear-gradient(90deg, #2563eb 0%, #86efac 100%)", borderRadius: 2 }} />
                  </div>

                  {/* Target Repo Card */}
                  <div style={{
                    background: "#ffffff",
                    border: "1px solid #86efac",
                    borderRadius: 12,
                    padding: "10px 14px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                    boxShadow: "0 2px 12px rgba(34, 197, 94, 0.08)"
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, color: "#15803d", textTransform: "uppercase" }}>
                        <span style={{ color: "#16a34a", fontSize: 14 }}>
                          {isLocalPath(migrationJob.target_repo) ? <FaFolderOpen /> : <FaGithub />}
                        </span>
                        Target Repository
                      </div>
                      <span style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px", borderRadius: 6, background: "#dcfce7", color: "#166534", border: "1px solid #86efac" }}>
                        Java {migrationJob.target_java_version || "?"} Modernized
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#2563eb", wordBreak: "break-all", fontFamily: "'JetBrains Mono', monospace" }}>
                        {migrationJob.target_repo || "N/A"}
                      </div>
                      <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                        <button
                          type="button"
                          onClick={() => handleCopyRepo(migrationJob.target_repo, "target")}
                          title={copiedRepo === "target" ? "Copied!" : "Copy Target Repo Path"}
                          style={{
                            background: copiedRepo === "target" ? "#dcfce7" : "#f1f5f9",
                            color: copiedRepo === "target" ? "#166534" : "#64748b",
                            border: "1px solid #cbd5e1",
                            borderRadius: 6,
                            width: 28,
                            height: 28,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            transition: "all 0.15s ease"
                          }}
                        >
                          {copiedRepo === "target" ? <FaCheck size={11} /> : <FaCopy size={11} />}
                        </button>
                        {!isLocalPath(migrationJob.target_repo) && getRepositoryLink(migrationJob.target_repo) && (
                          <a
                            href={getRepositoryLink(migrationJob.target_repo)!}
                            target="_blank"
                            rel="noopener noreferrer"
                            title="Open Target Repository"
                            style={{
                              background: "#eff6ff",
                              color: "#2563eb",
                              border: "1px solid #bfdbfe",
                              borderRadius: 6,
                              width: 28,
                              height: 28,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              textDecoration: "none"
                            }}
                          >
                            <FaExternalLinkAlt size={10} />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Animated & Unique Tab Navigation Bar */}
            {!isJUnitOnly && (
              <div className="animated-tab-bar">
                {[
                  { id: "general", label: "General", icon: <FaFileAlt />, badge: `${migrationJob?.files_modified ?? 0} files` },
                  { id: "unit-test", label: "Unit Test", icon: <FaCheckCircle />, badge: testsRun > 0 ? `${totalTestCases} tests` : undefined },
                  { id: "functional-test", label: "Functional Test", icon: <FaTasks />, badge: (runFunctionalTests ?? migrationJob.run_functional_tests ?? true) ? "Playwright Logs" : undefined },
                  { id: "sonarqube", label: "SonarQube", icon: <FaBug />, badge: sonarTotalFindings > 0 ? `${sonarTotalFindings}` : "Passed" },
                  { id: "fossa", label: "FOSSA", icon: <FaShieldAlt />, badge: fossaPolicyStatus },
                  { id: "logs-issues", label: "Logs & Issues", icon: <FaTerminal />, badge: migrationJob.issues?.length ? `${migrationJob.issues.length}` : undefined },
                  { id: "reports", label: "Reports", icon: <FaDownload /> },
                ].map((tab) => {
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveTab(tab.id as any)}
                      className={`animated-tab-button ${isActive ? "is-active" : ""}`}
                    >
                      <span className="animated-tab-icon">{tab.icon}</span>
                      <span>{tab.label}</span>
                      {tab.badge && (
                        <span className="animated-tab-badge">
                          {tab.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
            <div className="animated-tab-bar">
              {[
                { id: "general", label: "General", icon: <FaFileAlt />, badge: `${migrationJob?.files_modified ?? 0} files` },
                { id: "unit-test", label: "Unit Test", icon: <FaCheckCircle />, badge: testsRun > 0 ? `${totalTestCases} tests` : undefined },
                { id: "functional-test", label: "Functional Test", icon: <FaTasks />, badge: (runFunctionalTests ?? migrationJob.run_functional_tests) ? "Playwright Logs" : undefined },
                { id: "sonarqube", label: "SonarQube", icon: <FaBug />, badge: sonarTotalFindings > 0 ? `${sonarTotalFindings}` : "Passed" },
                { id: "fossa", label: "FOSSA", icon: <FaShieldAlt />, badge: fossaPolicyStatus },
                { id: "logs-issues", label: "Logs & Issues", icon: <FaTerminal />, badge: migrationJob.issues?.length ? `${migrationJob.issues.length}` : undefined },
                { id: "reports", label: "Reports", icon: <FaDownload /> },
              ]
              .filter((tab) => {
                if (tab.id === "unit-test") return Boolean(migrationJob?.run_tests ?? migrationJob?.runTests ?? runTests);
                if (tab.id === "functional-test") return Boolean(migrationJob?.run_functional_tests ?? runFunctionalTests);
                if (tab.id === "sonarqube") return Boolean(migrationJob?.run_sonar ?? migrationJob?.runSonar ?? runSonar);
                if (tab.id === "fossa") return Boolean(migrationJob?.run_fossa ?? migrationJob?.runFossa ?? runFossa);
                return true;
              })
              .map((tab) => {
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`animated-tab-button ${isActive ? "is-active" : ""}`}
                  >
                    <span className="animated-tab-icon">{tab.icon}</span>
                    <span>{tab.label}</span>
                    {tab.badge && (
                      <span className="animated-tab-badge">
                        {tab.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* TAB CONTENTS */}

            {/* TAB 1: GENERAL TAB (Contains Dependencies Updated & Changed Files with proper subheadings) */}
            {activeTab === "general" && (
              <div className="tab-panel-container" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {/* Dependencies Updated Card (Scrollable Inside Card) */}
                <div style={{ background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "20px 24px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div style={{ color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>
                        <FaLayerGroup />
                      </div>
                      <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: "#0f172a" }}>Dependencies Updated</h3>
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
                      {dependencyUpdates.length > 0 && (
                        <CopyAllDependenciesButton
                          text={dependencyUpdates
                            .map((dep) => `${dep.group_id}:${dep.artifact_id} (${dep.current_version} -> ${dep.new_version})`)
                            .join("\n")}
                          label="Copy All"
                        />
                      )}
                    </div>

                    <div style={{ position: "relative", width: 260 }}>
                      <input
                        type="text"
                        placeholder="Search dependencies..."
                        value={dependencySearchQuery}
                        onChange={(e) => setDependencySearchQuery(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "8px 14px 8px 36px",
                          borderRadius: 8,
                          border: "1px solid #cbd5e1",
                          fontSize: 12,
                          background: "#fff",
                          outline: "none",
                        }}
                      />
                      <div style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "#64748b", fontSize: 12 }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                      </div>
                    </div>
                  </div>

                  {/* Scrollable Container Inside Card */}
                  <div style={{ maxHeight: 320, overflowY: "auto", border: "1px solid #f1f5f9", borderRadius: 10 }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                      <thead style={{ position: "sticky", top: 0, background: "#f8fafc", zIndex: 1 }}>
                        <tr style={{ borderBottom: "1px solid #e2e8f0" }}>
                          <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", width: 40 }}>#</th>
                          <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase" }}>Dependency Coordinate</th>
                          <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", textAlign: "center" }}>Current Version</th>
                          <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", textAlign: "center" }}>Updated Version</th>
                          <th style={{ padding: "10px 14px", fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", width: 110, textAlign: "center" }}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredDependencies.length > 0 ? (
                          filteredDependencies.map((dep, idx) => (
                            <tr key={idx} style={{
                              backgroundColor: idx % 2 === 0 ? "#ffffff" : "#fbfdff",
                              borderBottom: "1px solid #f8fafc"
                            }}>
                              <td style={{ padding: "10px 14px", fontSize: 12, color: "#94a3b8", fontWeight: 500 }}>{idx + 1}.</td>
                              <td style={{ padding: "10px 14px", fontSize: 13, color: "#0f172a", fontWeight: 600 }}>
                                {dep.group_id}:{dep.artifact_id}
                              </td>
                              <td style={{ padding: "10px 14px", fontSize: 13, color: "#64748b", fontWeight: 500, textAlign: "center" }}>{dep.current_version}</td>
                              <td style={{ padding: "10px 14px", fontSize: 13, color: "#166534", fontWeight: 700, textAlign: "center" }}>{dep.new_version}</td>
                              <td style={{ padding: "10px 14px", textAlign: "center" }}>
                                <span style={{
                                  backgroundColor: "#ecfdf5",
                                  color: "#059669",
                                  fontSize: 10,
                                  fontWeight: 700,
                                  padding: "3px 8px",
                                  borderRadius: "12px",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 4,
                                  border: "1px solid #a7f3d0"
                                }}>
                                  <FaCheckCircle style={{ fontSize: 10 }} />
                                  Updated
                                </span>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={5} style={{ padding: "30px", textAlign: "center", color: "#64748b", fontStyle: "italic", fontSize: 13 }}>
                              No matching dependencies found.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Changed Files & Code Diff Viewer */}
                <div id="source-code-transformations-section" style={{ background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, overflow: "hidden", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
                  <div style={{ padding: "14px 20px", borderBottom: "1px solid #eef2f6", background: "#f8fafc", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ background: "#eff6ff", color: "#2563eb", width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, border: "1px solid #bfdbfe" }}>
                        <FaFileCode />
                      </div>
                      <div>
                        <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: "#0f172a" }}>Changed Files</h3>
                        <div style={{ fontSize: 11, color: "#64748b", fontWeight: 500 }}>Inspect transformed source files and side-by-side code diffs</div>
                      </div>
                    </div>
                    <span style={{ background: "#dbeafe", color: "#1d4ed8", fontSize: 11, fontWeight: 700, padding: "2px 10px", borderRadius: 20, border: "1px solid #bfdbfe" }}>
                      {diffData.length} Files Transformed
                    </span>
                  </div>
                  {(() => {
                    const current = diffData[selectedDiffIndex] || diffData[0];
                    const modifiedCount = diffData.filter(f => f.status === "Modified").length;
                    const addedCount = diffData.filter(f => f.status === "Added").length;
                    const removedCount = diffData.filter(f => f.status === "Removed").length;

                    return (
                      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", height: 560 }}>
                        {/* Sidebar */}
                        <div style={{ background: "#ffffff", borderRight: "1px solid #e2e8f0", display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
                          <div style={{ padding: "18px 20px", flexShrink: 0 }}>
                            <h3 style={{ margin: "0 0 12px 0", fontSize: 14, fontWeight: 800, color: "#0f172a" }}>Changed Files ({diffData.length})</h3>
                            <div style={{ display: "flex", gap: 10 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, fontWeight: 700, color: "#2563eb" }}>
                                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center", color: "#ffffff", fontSize: 7 }}>✔</div> {modifiedCount} Modified
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, fontWeight: 700, color: "#10b981" }}>
                                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#10b981", display: "flex", alignItems: "center", justifyContent: "center", color: "#ffffff", fontSize: 7 }}>+</div> {addedCount} Added
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, fontWeight: 700, color: "#ef4444" }}>
                                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#ef4444", display: "flex", alignItems: "center", justifyContent: "center", color: "#ffffff", fontSize: 7 }}>-</div> {removedCount} Removed
                              </div>
                            </div>
                          </div>

                          <div style={{ flex: 1, overflowY: "auto", borderTop: "1px solid #f1f5f9", minHeight: 0 }}>
                            {diffData.length === 0 ? (
                              <div style={{ padding: "24px 16px", textAlign: "center", color: "#94a3b8", fontSize: 12, fontStyle: "italic" }}>
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
                                  padding: "10px 18px",
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  cursor: "pointer",
                                  background: selectedDiffIndex === idx ? "#eff6ff" : "transparent",
                                  transition: "all 0.15s",
                                  borderLeft: selectedDiffIndex === idx ? "4px solid #2563eb" : "4px solid transparent"
                                }}
                              >
                                <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden" }}>
                                  <FaFileAlt style={{ color: file.category ? "#7c3aed" : "#2563eb", fontSize: 14, opacity: 0.8 }} />
                                  <div style={{ overflow: "hidden" }}>
                                    <span style={{
                                      fontSize: 12,
                                      fontWeight: selectedDiffIndex === idx ? 700 : 500,
                                      color: selectedDiffIndex === idx ? "#1d4ed8" : "#334155",
                                      whiteSpace: "nowrap",
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      display: "block",
                                    }}>
                                      {file.file}
                                    </span>
                                  </div>
                                </div>
                                <span style={{
                                  fontSize: 9,
                                  fontWeight: 700,
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                  background: file.status === "Modified" ? "#dbeafe" : file.status === "Added" ? "#dcfce7" : "#fee2e2",
                                  color: file.status === "Modified" ? "#1d4ed8" : file.status === "Added" ? "#059669" : "#dc2626",
                                  flexShrink: 0,
                                  marginLeft: 6,
                                }}>
                                  {file.status}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Diff View */}
                        <div style={{ background: "#ffffff", display: "flex", flexDirection: "column", overflow: "hidden" }}>
                          {current ? (
                            <>
                              <div style={{ padding: "12px 20px", borderBottom: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#ffffff" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                                  <FaCode style={{ color: current.category ? "#7c3aed" : "#2563eb", fontSize: 16 }} />
                                  <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{current.file}</h4>
                                  <span style={{
                                    fontSize: 10,
                                    fontWeight: 700,
                                    padding: "2px 6px",
                                    borderRadius: 4,
                                    background: current.status === "Modified" ? "#dcfce7" : current.status === "Added" ? "#dcfce7" : "#fee2e2",
                                    color: current.status === "Modified" ? "#059669" : current.status === "Added" ? "#059669" : "#dc2626",
                                  }}>
                                    {current.status}
                                  </span>
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                                  <div style={{ fontSize: 11, fontWeight: 700 }}>
                                    <span style={{ color: "#10b981" }}>+ {current.additions ?? 0} additions</span>
                                    <span style={{ color: "#ef4444", marginLeft: 10 }}>- {current.deletions ?? 0} deletions</span>
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => void handleCopyDiffCode(current.afterLines ?? [])}
                                    title="Copy generated code"
                                    style={{
                                      display: "inline-flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      width: 28,
                                      height: 28,
                                      border: "1px solid #cbd5e1",
                                      borderRadius: 6,
                                      background: copiedDiffCode ? "#ecfdf5" : "#ffffff",
                                      color: copiedDiffCode ? "#059669" : "#475569",
                                      cursor: "pointer",
                                    }}
                                  >
                                    {copiedDiffCode ? <FaCheck size={11} /> : <FaCopy size={11} />}
                                  </button>
                                  {Boolean(
                                    current &&
                                    !String(current.file || "").toLowerCase().endsWith(".css") &&
                                    !String(current.file || "").toLowerCase().endsWith(".java") &&
                                    !String(current.file || "").toLowerCase().endsWith(".xml") &&
                                    !String(current.file || "").toLowerCase().endsWith(".json") &&
                                    (
                                      current.category?.toLowerCase().includes("jsp") ||
                                      current.category?.toLowerCase().includes("jsf") ||
                                      current.category?.toLowerCase().includes("ui") ||
                                      /\.(tsx|jsx|vue|html)$/i.test(current.file || "")
                                    )
                                  ) && (
                                    <button
                                      type="button"
                                      onClick={(e) => handleShowReactUi(current, e)}
                                      style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: 4,
                                        height: 28,
                                        padding: "0 10px",
                                        border: "1px solid #bfdbfe",
                                        borderRadius: 6,
                                        background: "#eff6ff",
                                        color: "#1d4ed8",
                                        cursor: "pointer",
                                        fontSize: 11,
                                        fontWeight: 700,
                                      }}
                                    >
                                      <FaExternalLinkAlt size={10} />
                                      View UI
                                    </button>
                                  )}
                                </div>
                              </div>

                              <div style={{ flex: 1, overflow: "auto", background: "#ffffff" }}>
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
                                          <td style={{ width: 40, padding: "2px 8px", textAlign: "right", color: "#94a3b8", background: "rgba(0,0,0,0.02)", userSelect: "none", borderRight: "1px solid #e2e8f0" }}>{line.origin === 'before' ? line.num : ""}</td>
                                          <td style={{ width: 40, padding: "2px 8px", textAlign: "right", color: "#94a3b8", background: "rgba(0,0,0,0.02)", userSelect: "none", borderRight: "1px solid #e2e8f0" }}>{line.origin === 'after' ? line.num : line.type === 'normal' ? line.num : ""}</td>
                                          <td style={{ width: 24, padding: "2px 0", textAlign: "center", color: textColor, fontWeight: 800, userSelect: "none" }}>{sign}</td>
                                          <td style={{ padding: "2px 10px", color: textColor, whiteSpace: "pre-wrap" }}>{line.text.replace(/^[+-]\s*/, '')}</td>
                                        </tr>
                                      );
                                    })}
                                  </tbody>
                                </table>
                              </div>
                            </>
                          ) : (
                            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#94a3b8" }}>
                              <FaCode style={{ fontSize: 32, color: "#cbd5e1", marginBottom: 8 }} />
                              <div style={{ fontSize: 13, fontWeight: 600, color: "#64748b" }}>Select a file to view code diff</div>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>
            )}

            {/* TAB 2: UNIT TEST TAB */}
            {activeTab === "unit-test" && (
              <div className="tab-panel-container" style={{ width: "100%" }}>
                <MigrationUnitTestSection
                  styles={{...styles, reportSection: { width: '100%', maxWidth: 'none', margin: 0 }}}
                  migrationJob={migrationJob}
                  repoAnalysis={repoAnalysis}
                  isJUnitOnly={false}
                  testSummaryReportDate={testSummaryReportDate}
                  migrationJavaVersion={migrationJob.target_java_version}
                  summaryItems={testSummaryItems}
                  testsRun={testsRun}
                  runTests={Boolean(migrationJob.run_tests ?? migrationJob.runTests ?? runTests)}
                  onDownloadUnitTestReport={handleDownloadUnitTestReport}
                  onGenerateUnitTests={handleRerunTests}
                  isGenerating={rerunTestsLoading}
                />
              </div>
            )}

            {/* TAB 3: FUNCTIONAL TEST TAB */}
            {activeTab === "functional-test" && (
              <div className="tab-panel-container" style={{ width: "100%" }}>
                <MigrationProposedTestSection
                  styles={styles}
                  migrationJob={migrationJob}
                />
              </div>
            )}

            {/* TAB 4: SONARQUBE TAB */}
            {activeTab === "sonarqube" && (
              <div className="tab-panel-container" style={{ width: "100%" }}>
                <MigrationSonarSection
                  styles={styles}
                  migrationJob={migrationJob}
                  sonarTotalFindings={sonarTotalFindings}
                />
              </div>
            )}

            {/* TAB 5: FOSSA TAB */}
            {activeTab === "fossa" && (
              <div className="tab-panel-container" style={{ background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "24px 32px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
                <MigrationFossaSection
                  styles={{...styles, reportSection: { padding: 0, border: 'none', background: 'transparent', boxShadow: 'none' }}}
                  migrationJob={migrationJob}
                  runFossa={Boolean(migrationJob.run_fossa ?? migrationJob.runFossa ?? runFossa)}
                  fossaLicenseIssueCount={migrationJob.fossa_license_issues ?? (migrationJob.fossa_report as Record<string, unknown>)?.license_issues as number ?? (migrationJob as Record<string, unknown>)?.license_issues as number}
                  fossaVulnerabilityTotal={migrationJob.fossa_vulnerabilities ?? (migrationJob.fossa_report as Record<string, unknown>)?.vulnerabilities as number ?? (migrationJob.fossa_report as Record<string, unknown>)?.vulnerability_count as number}
                  fossaOutdatedCount={migrationJob.fossa_outdated_dependencies ?? (migrationJob.fossa_report as Record<string, unknown>)?.outdated_dependencies as number ?? (migrationJob as Record<string, unknown>)?.outdated_packages as number}
                  fossaTotalDependencies={migrationJob.fossa_total_dependencies ?? (migrationJob.fossa_report as Record<string, unknown>)?.total_dependencies as number ?? (migrationJob as Record<string, unknown>)?.dependencies as number}
                  fossaTotalLicenses={(migrationJob as Record<string, unknown>)?.fossa_total_licenses as number ?? (migrationJob.fossa_report as Record<string, unknown>)?.total_licenses as number ?? (migrationJob.fossa_report as Record<string, unknown>)?.license_count as number ?? (migrationJob.fossa_report as Record<string, unknown>)?.licenses as number ?? (migrationJob as Record<string, unknown>)?.licenses as number}
                  fossaPolicyStatus={migrationJob.fossa_policy_status || (migrationJob.fossa_report as Record<string, unknown>)?.policy_status as string || (migrationJob as Record<string, unknown>)?.status as string}
                  fossaScanMode={migrationJob.fossa_scan_mode || (migrationJob.fossa_report as Record<string, unknown>)?.scan_mode as string}
                  fossaErrorMessage={migrationJob.fossa_error_message || (migrationJob.fossa_report as Record<string, unknown>)?.error_message as string}
                  fossaAnalysisUrl={fossaAnalysisUrl || migrationJob.fossa_analysis_url || (migrationJob.fossa_report as Record<string, unknown>)?.analysis_url as string || (migrationJob as Record<string, unknown>)?.project_url as string}
                  fossaRealScan={Boolean(fossaIsRealScan || migrationJob.fossa_real_scan || (migrationJob.fossa_report as Record<string, unknown>)?.real_scan)}
                />
              </div>
            )}

            {/* TAB 6: LOGS & ISSUES TAB */}
            {activeTab === "logs-issues" && (
              <div className="tab-panel-container" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "stretch" }}>
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
            )}

            {/* TAB 7: REPORTS TAB */}
            {activeTab === "reports" && (
              <div className="tab-panel-container" style={{ background: "#ffffff", border: "1px solid #eef2f6", borderRadius: 16, padding: "24px 32px", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
                <div style={{ marginBottom: 24 }}>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 18, fontWeight: 800, color: "#0f172a", display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ color: "#2563eb", fontSize: 22 }}>
                      <FaDownload />
                    </div>
                    Reports
                  </h3>
                  <p style={{ margin: 0, fontSize: 13, color: "#64748b", fontWeight: 500 }}>
                    Access and download the unit test report and the migrated project ZIP archive.
                  </p>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16, marginBottom: 24 }}>
                  {[
                    {
                      title: "Unit Test",
                      desc: "Full JaCoCo unit test execution and line coverage report",
                      format: "HTML Document",
                      icon: <FaFileCode style={{ color: "#0284c7" }} />,
                      actionLabel: "Download Unit Test Report",
                      action: () => handleDownloadUnitTestReport(),
                      bg: "#f0f9ff",
                      border: "#bae6fd"
                    },
                    {
                      title: "Download ZIP",
                      desc: "Complete migrated project codebase packaged as a downloadable ZIP archive",
                      format: "ZIP Archive",
                      icon: <FaFileArchive style={{ color: "#d97706" }} />,
                      actionLabel: "Download ZIP",
                      action: () => handleDownloadMigratedProjectZip(),
                      bg: "#fffbeb",
                      border: "#fde68a"
                    },
                  ].map((card, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: card.bg,
                        border: `1px solid ${card.border}`,
                        borderRadius: 14,
                        padding: "20px",
                        display: "flex",
                        flexDirection: "column",
                        gap: 12,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <div style={{ width: 42, height: 42, borderRadius: 10, background: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}>
                          {card.icon}
                        </div>
                        <span style={{ fontSize: 10, fontWeight: 800, padding: "3px 8px", borderRadius: 12, background: "#ffffff", color: "#475569", border: `1px solid ${card.border}` }}>
                          {card.format}
                        </span>
                      </div>
                      <div>
                        <h4 style={{ margin: "0 0 4px 0", fontSize: 15, fontWeight: 700, color: "#0f172a" }}>{card.title}</h4>
                        <p style={{ margin: 0, fontSize: 12, color: "#64748b", lineHeight: 1.4 }}>{card.desc}</p>
                      </div>
                      <button
                        type="button"
                        onClick={card.action}
                        style={{
                          marginTop: "auto",
                          padding: "9px 16px",
                          borderRadius: 8,
                          border: `1px solid ${card.border}`,
                          background: "#ffffff",
                          color: "#0f172a",
                          fontWeight: 700,
                          fontSize: 12,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 6,
                          cursor: "pointer",
                          boxShadow: "0 2px 6px rgba(0,0,0,0.04)",
                        }}
                      >
                        <FaDownload size={11} />
                        {card.actionLabel}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Bottom Action Footer Bar (Present Under ALL Tabs) */}
            <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: 14, marginTop: 12, width: "100%" }}>
              <MigrationReportActions
                migrationJob={migrationJob}
                migrationLogs={migrationLogs}
                resetWizard={resetWizard}
                onBack={onBack}
                onError={(message: string) => onError(message)}
                onDownloadUnitTestReport={handleDownloadUnitTestReport}
                styles={{...styles, reportActionsBar: { ...styles.reportActionsBar, marginTop: 4, padding: "8px 0" }}}
              />
            </div>
          </div>
        )}

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