import React, { useEffect, useState, useRef, useMemo, type Dispatch, type SetStateAction } from "react";
import { createPortal } from "react-dom";
import { FaRocket, FaSearch, FaShieldAlt, FaFileAlt, FaFlask, FaCopy,FaCheck, FaPlus } from "react-icons/fa";
import {
  scanExistingTests,
  getCachedExistingTests,
  classifyTestType,
  type TestResult,
  type TestSelectionItem,
  type ExistingTestRunResponse,
  type ApiEvidence,
} from "../services/existingTestService";
import { ExistingTestCasesPanel } from "./ExistingTestCasesPanel";
import { ExistingTestValidationReport } from "./ExistingTestValidationReport";
import { DetectedDependenciesTable } from "./DetectedDependenciesTable";
import { TestReportsModal, type TestReportData } from "./TestReportsModal";
import { wizardStyles as styles } from "@/shared/components/wizard/wizardStyles";
import { renderWizardIconBadge, renderForwardButtonLabel } from "@/shared/components/wizard";
import type { RepoAnalysis, RepoInfo } from "@/shared/types/domain";
import type { DependencyAnalysisResponse } from "@/features/strategy/services/strategyService";
import type { FunctionalTestScopePreview } from "../services/modernizationService";
import type { useModernizationState } from "../hooks/useModernizationState";
import { getUserSettings, saveUserSettings, getQualityChecksAdminConfig, type FullUserSettings } from "@/features/admin/services/adminService";

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
        padding: "5px 10px",
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

const _LLM_PROVIDERS = [
  { value: "groq", label: "Groq (Recommended — Llama 3.3 70B Fast)" },
  { value: "huggingface", label: "Hugging Face (Free)" },
  { value: "ollama", label: "Ollama (Local)" },
  { value: "claude", label: "Claude (Paid)" },
  { value: "gpt-4", label: "OpenAI (GPT-4)" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "offline", label: "Offline (Template)" },
];

const _getConfidenceColor = (percentage: number) => {
  if (percentage >= 80) return "#22c55e";
  if (percentage >= 60) return "#3b82f6";
  if (percentage >= 40) return "#f59e0b";
  return "#ef4444";
};

// Normalized identity helpers for test deduplication
const normalizeSuiteName = (suite?: string, file?: string, classname?: string): string => {
  const raw = classname || suite || file || "";
  const base = raw.split("/").pop()?.split("\\").pop()?.replace(/\.(java|kt|groovy|ts|js)$/i, "") || "";
  const parts = base.split(".");
  return parts[parts.length - 1].trim().toLowerCase();
};

const normalizeMethodName = (name?: string, methodname?: string, title?: string, test_name?: string): string => {
  const raw = test_name || methodname || name || title || "";
  const base = raw.replace(/\(\s*\)$/, "").trim();
  const parts = base.split(".");
  return parts[parts.length - 1].trim().toLowerCase();
};

const computeTestIdentity = (item: { suite?: string; file?: string; classname?: string; name?: string; methodname?: string; title?: string; test_name?: string }): string => {
  const s = normalizeSuiteName(item.suite, item.file, item.classname);
  const m = normalizeMethodName(item.name, item.methodname, item.title, item.test_name);
  return `${s}::${m}`;
};

// Helper to parse live logs and extract completed test statuses during execution
const parseLiveLogs = (
  logs: { ts?: string; msg?: string; level?: string }[]
) => {
  const completedMap = new Map<string, { status: string; duration?: string; error?: string | null }>();

  for (const log of logs) {
    const msg = (log.msg || "").trim();
    if (!msg) continue;

    // 1. APEX standard: [MAVEN-TEST-RESULT] test=Suite.method status=PASSED
    const apexMatch = msg.match(/\[(?:MAVEN-TEST-RESULT|TEST-RESULT)\]\s+test=([^\s]+)\s+status=([A-Z_]+)/i);
    if (apexMatch) {
      const fullTest = apexMatch[1];
      const rawStatus = apexMatch[2].toUpperCase();
      const st = rawStatus === "ERROR" ? "FAILED" : rawStatus;
      const parts = fullTest.split(".");
      const mName = parts.pop() || "";
      const sName = parts.pop() || "";
      const s = normalizeSuiteName(sName);
      const m = normalizeMethodName(mName);
      if (m) {
        if (s) completedMap.set(`${s}::${m}`, { status: st });
        completedMap.set(m, { status: st });
      }
      continue;
    }

    // 2. Numbered progress: [1/2] com.example.DemoTest.test02 PASSED (0.42s)
    const numberedMatch = msg.match(/^\[\d+\/\d+\]\s+([^\s]+)\s+(PASSED|FAILED|ERROR|SKIPPED)(?:\s+\(([\d.]+s?)\))?/i);
    if (numberedMatch) {
      const fullTest = numberedMatch[1];
      const rawStatus = numberedMatch[2].toUpperCase();
      const st = rawStatus === "ERROR" ? "FAILED" : rawStatus;
      const dur = numberedMatch[3] || undefined;
      const parts = fullTest.split(".");
      const mName = parts.pop() || "";
      const sName = parts.pop() || "";
      const s = normalizeSuiteName(sName);
      const m = normalizeMethodName(mName);
      if (m) {
        if (s) completedMap.set(`${s}::${m}`, { status: st, duration: dur });
        completedMap.set(m, { status: st, duration: dur });
      }
      continue;
    }

    // 3. PyTest format: path/test_file.py::test_name PASSED
    const pytestMatch = msg.match(/([^\s:]+\.[a-zA-Z0-9]+)::([^\s]+)\s+(PASSED|FAILED|ERROR|SKIPPED)/i);
    if (pytestMatch) {
      const sName = pytestMatch[1];
      const mName = pytestMatch[2];
      const rawStatus = pytestMatch[3].toUpperCase();
      const st = rawStatus === "ERROR" ? "FAILED" : rawStatus;
      const s = normalizeSuiteName(sName);
      const m = normalizeMethodName(mName);
      if (m) {
        if (s) completedMap.set(`${s}::${m}`, { status: st });
        completedMap.set(m, { status: st });
      }
      continue;
    }
  }

  return completedMap;
};

export interface FunctionalTestingTool {
  id: string;
  name: string;
  description: string;
  confidence: number;
  reason: string;
  color: string;
  tag: string;
}

interface ModernizationStepViewProps {
  jobId: string;
  modernization: ReturnType<typeof useModernizationState>;
  repoAnalysis: RepoAnalysis | null;
  dependencyAnalysis: DependencyAnalysisResponse | null;
  targetJavaVersion: string | null;
  selectedRepo: RepoInfo | null;
  repoUrl: string;
  currentToken: string;
  functionalTestToolMethod: string[];
  setFunctionalTestToolMethod: Dispatch<SetStateAction<string[]>>;
  functionalTestingTools: FunctionalTestingTool[];
  hasUI: boolean;
  localApiTestCases: FunctionalTestScopePreview["apiTestCases"];
  loading: boolean;
  startMigrationStatusText?: string;
  repoUtils: {
    isLocalRepoRef: (value: string | null | undefined) => boolean;
    extractLocalRepoPath: (value: string) => string;
  };
  onBack: () => void;
  onStartMigration: () => void;
}

export function ModernizationStepView({
  jobId,
  modernization,
  repoAnalysis,
  dependencyAnalysis,
  targetJavaVersion,
  selectedRepo: _selectedRepo,
  repoUrl: _repoUrl,
  currentToken: _currentToken,
  functionalTestToolMethod: _functionalTestToolMethod,
  setFunctionalTestToolMethod: _setFunctionalTestToolMethod,
  functionalTestingTools: _functionalTestingTools,
  hasUI: _hasUI,
  localApiTestCases: _localApiTestCases,
  loading,
  startMigrationStatusText,
  repoUtils,
  onBack: _onBack,
  onStartMigration,
}: ModernizationStepViewProps) {
  const {
    runTests,
    setRunTests,
    useLLMTests: _useLLMTests,
    setUseLLMTests: _setUseLLMTests,
    selectedLLMProvider: _selectedLLMProvider,
    setSelectedLLMProvider: _setSelectedLLMProvider,
    runSonar,
    setRunSonar,
    runFossa,
    setRunFossa,
    runCycode,
    setRunCycode,
    runFunctionalTests,
    setRunFunctionalTests,
  } = modernization;

  const { isLocalRepoRef: _isLocalRepoRef, extractLocalRepoPath: _extractLocalRepoPath } = repoUtils;
  const [viewingTestFile, setViewingTestFile] = useState<{ name: string; path: string; content?: string } | null>(null);
  const [_testFileLoading, _setTestFileLoading] = useState(false);

  // --- Existing Test execution states replicated from Prova ---
  const cachedScan = jobId ? getCachedExistingTests(jobId) : null;
  const [isRunningExisting, setIsRunningExisting] = useState(false);
  const [hasExistingTestsRun, setHasExistingTestsRun] = useState(false);
  const [existingTotal, setExistingTotal] = useState<number | null>(() =>
    cachedScan ? (cachedScan.total ?? cachedScan.test_cases?.length ?? 0) : null
  );
  const [existingFramework, setExistingFramework] = useState<string | null>(() => cachedScan?.framework || null);
  const [discoveredTests, setDiscoveredTests] = useState<TestSelectionItem[]>(() => cachedScan?.test_cases || []);
  const [isLoadingDiscoveredTests, setIsLoadingDiscoveredTests] = useState(false);
  const [isSonarConfigured, setIsSonarConfigured] = useState(true);
  const [isCycodeConfigured, setIsCycodeConfigured] = useState(false);
  const [isFossaConfigured, setIsFossaConfigured] = useState(false);
  const [isLlmConfiguredMod, setIsLlmConfiguredMod] = useState<boolean | null>(null);
  const [adminConfig, setAdminConfig] = useState<Record<string, unknown>[]>([]);
  const [isAdminConfigLoading, setIsAdminConfigLoading] = useState(true);
  const [isUserSettingsLoading, setIsUserSettingsLoading] = useState(true);
  const [adminConfigError, setAdminConfigError] = useState<string | null>(null);
  const [userSettingsError, setUserSettingsError] = useState<string | null>(null);
  const [ciEnabled, setCiEnabled] = useState(true);
  const [cdEnabled, setCdEnabled] = useState(true);



  // Proposed tests
  const [_proposedTests, _setProposedTests] = useState<Record<string, unknown>[]>([]);
  const [_existingElapsedTime, setExistingElapsedTime] = useState(0);
  const [existingLogs, setExistingLogs] = useState<{ ts: string; msg: string; level: string }[]>([]);
  const [existingExecResult, setExistingExecResult] = useState<ExistingTestRunResponse | null>(null);
  const [_showExistingLogs, _setShowExistingLogs] = useState(false);
  const [showValidationReport, setShowValidationReport] = useState(false);
  const [_validationFilter, _setValidationFilter] = useState("ALL");
  const [_validationSearch, _setValidationSearch] = useState("");
  const [_expandedFailures, _setExpandedFailures] = useState<Record<number, boolean>>({});
  const [showTestDetailModal, setShowTestDetailModal] = useState(false);
  const [testDetailReport, setTestDetailReport] = useState<TestReportData | null>(null);
  const [showQualityGateReminder, setShowQualityGateReminder] = useState(false);

  const handleStartMigrationClick = () => {
    if (loading) return;
    if (ciEnabled && (!runSonar || !runFossa)) {
      setShowQualityGateReminder(true);
      return;
    }
    onStartMigration();
  };

  const handleConfirmContinueMigration = () => {
    setShowQualityGateReminder(false);
    onStartMigration();
  };

  // Lock body scroll when confirmation popup is active on long scrollable pages
  useEffect(() => {
    if (showQualityGateReminder) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [showQualityGateReminder]);

  const existingLogRef = useRef<HTMLDivElement | null>(null);
  const _existingPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Live timer for existing test execution / analysis
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    if (isRunningExisting) {
      setExistingElapsedTime(0);
      const startTime = Date.now();
      timer = setInterval(() => {
        setExistingElapsedTime(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
    } else {
      setExistingElapsedTime(0);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isRunningExisting]);

  const _formatElapsedTime = (totalSecs: number) => {
    const mins = Math.floor((totalSecs || 0) / 60);
    const secs = (totalSecs || 0) % 60;
    return `${String(mins).padStart(2, '0')}m ${String(secs).padStart(2, '0')}s`;
  };

  const executedTestLogsCount = existingLogs.filter(log =>
    /^\[\d+\/\d+\]/.test(log.msg || "")
  ).length;

  const _testProgressPercent = (existingTotal && existingTotal - 1 > 0)
    ? Math.min(100, Math.round((executedTestLogsCount / existingTotal) * 100))
    : (isRunningExisting ? 10 : 0);

  const buildTestDetailReport = (t: TestResult, defaultStatus?: string): TestReportData => {
    const scUrl = t.screenshot_url || t.screenshotUrl || t.evidence?.screenshotUrl || null;
    const vidUrl = t.video_url || t.videoUrl || t.evidence?.videoUrl || null;
    const formattedLogs = Array.isArray(existingLogs) && existingLogs.length > 0
      ? existingLogs.map((l: string | { ts?: string; level?: string; msg?: string }) => typeof l === "string" ? l : `[${l.ts || ""}] [${l.level || "INFO"}] ${l.msg || ""}`).join("\n")
      : (typeof existingLogs === "string" ? existingLogs : undefined);

    return {
      testId: String(t.test_id || t.testId || `${t.suite || t.spec || t.file || ""}#${t.test_name || t.name || t.title || ""}`),
      executionId: String(t.execution_id || t.executionId || jobId),
      title: String(t.test_name || t.name || t.title || "Test"),
      name: String(t.test_name || t.name || t.title || "Test"),
      spec: String(t.suite || t.spec || t.file || ""),
      suite: String(t.suite || t.spec || t.file || ""),
      status: String(t.status || defaultStatus || "PASSED"),
      duration: String(t.duration || "0.0s"),
      file: t.file ? String(t.file) : undefined,
      url: t.report_url ? String(t.report_url) : undefined,
      type: String(t.type || "JUnit"),
      testType: String(((t.test_type || t.testType || t.category || "API") as string).toUpperCase() === "UNIT" ? "API" : (t.test_type || t.testType || (t.category === "UI" ? "UI" : "API"))),
      framework: String(t.framework || existingExecResult?.framework_info?.build_tool || existingExecResult?.framework_info?.detected_framework || existingFramework || "JUnit"),
      screenshotUrl: scUrl ? String(scUrl) : null,
      videoUrl: vidUrl ? String(vidUrl) : null,
      traceUrl: t.trace_url ? String(t.trace_url) : undefined,
      apiEvidence: t.api_evidence as ApiEvidence | null | undefined,
      evidence: (t.evidence || {
        screenshotAvailable: !!scUrl,
        screenshotUrl: scUrl ? String(scUrl) : null,
        videoAvailable: !!vidUrl,
        videoUrl: vidUrl ? String(vidUrl) : null,
      }) as Record<string, unknown> | null | undefined,
      error: (t.failure_message || t.details?.error || t.error || null) as string | null,
      errorCode: (t.status === "FAILED" ? "TEST_FAILED" : t.status === "ERROR" ? "BUILD_ERROR" : t.status === "NOT_EXECUTED" ? "NOT_EXECUTED" : undefined),
      stackTrace: (t.stack_trace || t.details?.stackTrace || t.stackTrace || null) as string | null,
      stdout: (t.stdout || t.details?.stdout || null) as string | null,
      stderr: (t.stderr || t.details?.stderr || null) as string | null,
      rawLogs: (t.rawLogs || formattedLogs) as string | undefined,
      logs: existingLogs,
    };
  };

  // Single unified, deduplicated list of test cases throughout lifecycle
  const displayTestResults: TestResult[] = useMemo(() => {
    const executedList: TestResult[] = existingExecResult?.test_results || [];

    if (discoveredTests.length === 0 && executedList.length === 0) {
      return [];
    }

    const execByKey = new Map<string, TestResult>();
    const execByMethod = new Map<string, TestResult>();

    executedList.forEach((r: TestResult) => {
      const fullKey = computeTestIdentity(r);
      execByKey.set(fullKey, r);

      const m = normalizeMethodName(r.name, r.methodname, r.title, r.test_name);
      if (m && !execByMethod.has(m)) {
        execByMethod.set(m, r);
      }
    });

    // Use discoveredTests as the canonical baseline so every discovered test appears exactly once
    const baseList: Array<TestSelectionItem | TestResult> = discoveredTests.length > 0 ? discoveredTests : executedList;

    // Parse live logs ONLY for in-flight execution when still actively running
    const liveCompletedMap = isRunningExisting ? parseLiveLogs(existingLogs) : new Map();

    const matchedExecKeys = new Set<string>();
    let foundRunning = false;

    const merged: TestResult[] = baseList.map((dt: TestSelectionItem | TestResult, idx: number) => {
      const fullKey = computeTestIdentity(dt);
      const m = normalizeMethodName(dt.name, dt.methodname, dt.title, dt.test_name);

      const testSuite = dt.classname?.split(".").pop() || dt.suite || dt.spec || dt.file?.split("/").pop()?.replace(/\.(java|kt)$/, "") || "TestSuite";
      const testName = (dt.methodname || dt.name || dt.test_name || dt.title || `scenario_${idx + 1}`).replace(/\(\s*\)$/, "");
      const testFile = dt.file || `${testSuite}.java`;
      const rawType = (dt.test_type || dt.testType || dt.type || (dt.category === "UI" ? "UI" : "API")).toUpperCase();
      const displayType = rawType === "UNIT" ? "API" : rawType;

      // 1. Actual execution result from backend (highest priority)
      let matchedExec = execByKey.get(fullKey);
      if (!matchedExec && m && execByMethod.has(m)) {
        matchedExec = execByMethod.get(m);
      }

      if (matchedExec) {
        matchedExecKeys.add(computeTestIdentity(matchedExec));
        const rawStatus = (matchedExec.status || "NOT_EXECUTED").toUpperCase();
        const st = rawStatus === "ERROR" ? "FAILED" : rawStatus;

        const scUrl = (matchedExec.screenshot_url || matchedExec.screenshotUrl || (typeof matchedExec.evidence?.screenshotUrl === "string" ? matchedExec.evidence.screenshotUrl : null) || dt.screenshot_url || dt.screenshotUrl || (typeof dt.evidence?.screenshotUrl === "string" ? dt.evidence.screenshotUrl : null) || null) as string | null;
        const vidUrl = (matchedExec.video_url || matchedExec.videoUrl || (typeof matchedExec.evidence?.videoUrl === "string" ? matchedExec.evidence.videoUrl : null) || dt.video_url || dt.videoUrl || (typeof dt.evidence?.videoUrl === "string" ? dt.evidence.videoUrl : null) || null) as string | null;
        const trUrl = (matchedExec.trace_url || matchedExec.traceUrl || dt.trace_url || dt.traceUrl || null) as string | null;
        const apiEv = matchedExec.api_evidence || matchedExec.apiEvidence || dt.api_evidence || dt.apiEvidence || null;
        const ev = matchedExec.evidence || dt.evidence || (scUrl || vidUrl ? {
          screenshotAvailable: !!scUrl,
          screenshotUrl: scUrl,
          videoAvailable: !!vidUrl,
          videoUrl: vidUrl,
        } : null);

        return {
          testId: String(dt.test_id || dt.testId || matchedExec.test_id || matchedExec.testId || `TEST-${idx + 1}`),
          test_name: testName,
          name: testName,
          title: testName,
          suite: testSuite,
          spec: testSuite,
          file: testFile,
          type: displayType,
          testType: displayType,
          status: st,
          duration: matchedExec.duration && matchedExec.duration !== "--" ? matchedExec.duration : (st === "PASSED" || st === "FAILED" ? "0.50s" : "—"),
          framework: dt.framework || matchedExec.framework || existingFramework || "JUnit",
          failure_message: matchedExec.failure_message || matchedExec.error || null,
          error: matchedExec.failure_message || matchedExec.error || null,
          stack_trace: matchedExec.stack_trace || null,
          stdout: matchedExec.stdout || null,
          stderr: matchedExec.stderr || null,
          screenshot_url: scUrl,
          screenshotUrl: scUrl,
          video_url: vidUrl,
          videoUrl: vidUrl,
          trace_url: trUrl,
          traceUrl: trUrl,
          api_evidence: apiEv,
          apiEvidence: apiEv,
          evidence: ev,
          unavailable_reason: (matchedExec.unavailable_reason || matchedExec.unavailableReason || dt.unavailable_reason || dt.unavailableReason || null) as string | null,
          unavailableReason: (matchedExec.unavailable_reason || matchedExec.unavailableReason || dt.unavailable_reason || dt.unavailableReason || null) as string | null,
          details: matchedExec.details || dt.details || null,
        };
      }

      // 2. Live completed result from logs (during active running only)
      if (isRunningExisting) {
        const liveCompleted = liveCompletedMap.get(fullKey) || (m ? liveCompletedMap.get(m) : null);
        if (liveCompleted) {
          return {
            testId: String(dt.test_id || dt.testId || `TEST-${idx + 1}`),
            test_name: testName,
            name: testName,
            title: testName,
            suite: testSuite,
            spec: testSuite,
            file: testFile,
            type: displayType,
            testType: displayType,
            status: liveCompleted.status,
            duration: liveCompleted.duration || "0.45s",
            framework: dt.framework || existingFramework || "JUnit",
            error: liveCompleted.error || (liveCompleted.status === "FAILED" ? "Test execution failed." : null),
            failure_message: liveCompleted.error || (liveCompleted.status === "FAILED" ? "Test execution failed." : null),
            screenshot_url: dt.screenshot_url || dt.screenshotUrl || null,
            screenshotUrl: dt.screenshot_url || dt.screenshotUrl || null,
            video_url: dt.video_url || dt.videoUrl || null,
            videoUrl: dt.video_url || dt.videoUrl || null,
            trace_url: dt.trace_url || null,
            api_evidence: dt.api_evidence || null,
            evidence: dt.evidence || null,
          };
        }

        // 3. If actively running and not yet finished, mark exactly the FIRST unfinished test as IN_PROGRESS
        if (!foundRunning) {
          foundRunning = true;
          return {
            testId: String(dt.test_id || dt.testId || `TEST-${idx + 1}`),
            test_name: testName,
            name: testName,
            title: testName,
            suite: testSuite,
            spec: testSuite,
            file: testFile,
            type: displayType,
            testType: displayType,
            status: "IN_PROGRESS",
            duration: "Running...",
            framework: dt.framework || existingFramework || "JUnit",
            error: null,
            failure_message: null,
            screenshot_url: dt.screenshot_url || dt.screenshotUrl || null,
            screenshotUrl: dt.screenshot_url || dt.screenshotUrl || null,
            video_url: dt.video_url || dt.videoUrl || null,
            videoUrl: dt.video_url || dt.videoUrl || null,
            trace_url: dt.trace_url || null,
            api_evidence: dt.api_evidence || null,
            evidence: dt.evidence || null,
          };
        }
      }

      // 4. Default / unexecuted status — NEVER default to PASSED
      return {
        testId: String(dt.test_id || dt.testId || `TEST-${idx + 1}`),
        test_name: testName,
        name: testName,
        title: testName,
        suite: testSuite,
        spec: testSuite,
        file: testFile,
        type: displayType,
        testType: displayType,
        status: "NOT_EXECUTED",
        duration: "—",
        framework: dt.framework || existingFramework || "JUnit",
        error: null,
        failure_message: null,
        screenshot_url: dt.screenshot_url || dt.screenshotUrl || null,
        screenshotUrl: dt.screenshot_url || dt.screenshotUrl || null,
        video_url: dt.video_url || dt.videoUrl || null,
        videoUrl: dt.video_url || dt.videoUrl || null,
        trace_url: dt.trace_url || null,
        api_evidence: dt.api_evidence || null,
        evidence: dt.evidence || null,
      };
    });

    // If any executed test wasn't part of discoveredTests, append it once
    executedList.forEach((r: TestResult, rIdx: number) => {
      const key = computeTestIdentity(r);
      if (!matchedExecKeys.has(key)) {
        const testSuite = r.suite || r.spec || r.file?.split("/").pop()?.replace(/\.(java|kt)$/, "") || "TestSuite";
        const testName = (r.test_name || r.name || r.title || `test_${rIdx + 1}`).replace(/\(\s*\)$/, "");
        const rawType = (r.test_type || r.testType || r.type || "API").toUpperCase();
        const displayType = rawType === "UNIT" ? "API" : rawType;
        const scUrl = (r.screenshot_url || r.screenshotUrl || (typeof r.evidence?.screenshotUrl === "string" ? r.evidence.screenshotUrl : null) || null) as string | null;
        const vidUrl = (r.video_url || r.videoUrl || (typeof r.evidence?.videoUrl === "string" ? r.evidence.videoUrl : null) || null) as string | null;
        const trUrl = (r.trace_url || r.traceUrl || null) as string | null;
        const apiEv = r.api_evidence || r.apiEvidence || null;
        const ev = r.evidence || (scUrl || vidUrl ? {
          screenshotAvailable: !!scUrl,
          screenshotUrl: scUrl,
          videoAvailable: !!vidUrl,
          videoUrl: vidUrl,
        } : null);

        merged.push({
          testId: String(r.test_id || r.testId || `TEST-EXEC-${rIdx + 1}`),
          test_name: testName,
          name: testName,
          title: testName,
          suite: testSuite,
          spec: testSuite,
          file: r.file || `${testSuite}.java`,
          type: displayType,
          testType: displayType,
          status: (r.status || "NOT_EXECUTED").toUpperCase(),
          duration: r.duration && r.duration !== "--" ? r.duration : "0.50s",
          framework: r.framework || existingFramework || "JUnit",
          failure_message: r.failure_message || r.error || null,
          error: r.failure_message || r.error || null,
          stack_trace: r.stack_trace || null,
          stdout: r.stdout || null,
          stderr: r.stderr || null,
          screenshot_url: scUrl,
          screenshotUrl: scUrl,
          video_url: vidUrl,
          videoUrl: vidUrl,
          trace_url: trUrl,
          traceUrl: trUrl,
          api_evidence: apiEv,
          apiEvidence: apiEv,
          evidence: ev,
          unavailable_reason: (r.unavailable_reason || r.unavailableReason || null) as string | null,
          unavailableReason: (r.unavailable_reason || r.unavailableReason || null) as string | null,
          details: r.details || null,
        });
      }
    });

    return merged;
  }, [discoveredTests, existingExecResult, isRunningExisting, existingFramework, existingLogs]);

  // Auto-scroll live log box
  useEffect(() => {
    if (existingLogRef.current) {
      existingLogRef.current.scrollTop = existingLogRef.current.scrollHeight;
    }
  }, [existingLogs]);

  // Reset previous execution, logs, and report states when jobId changes
  useEffect(() => {
    setExistingExecResult(null);
    setExistingLogs([]);
    setHasExistingTestsRun(false);
    setShowValidationReport(false);
    setIsRunningExisting(false);
    setExistingElapsedTime(0);
    setTestDetailReport(null);
    setShowTestDetailModal(false);
  }, [jobId]);

  // Scan existing tests from repository on mount or when jobId changes
  useEffect(() => {
    if (!jobId) {
      setIsLoadingDiscoveredTests(false);
      setExistingTotal(null);
      setExistingFramework(null);
      setDiscoveredTests([]);
      return;
    }

    const cached = getCachedExistingTests(jobId);
    if (cached && (cached.total > 0 || (cached.test_cases && cached.test_cases.length > 0))) {
      const tests = cached.test_cases || cached.tests || [];
      const total = cached.total ?? cached.testCasesFound ?? tests.length;
      setExistingTotal(total);
      setExistingFramework(cached.framework || "JUnit");
      setDiscoveredTests(tests);
      setIsLoadingDiscoveredTests(false);
      return;
    }

    setIsLoadingDiscoveredTests(true);
    scanExistingTests(jobId, true)
      .then((data) => {
        const tests = data.test_cases || data.tests || [];
        const total = data.total ?? data.testCasesFound ?? tests.length;
        setExistingTotal(total);
        setExistingFramework(data.framework || "JUnit");
        setDiscoveredTests(tests);
      })
      .catch((err) => {
        console.error("Failed to scan existing repository tests:", err);
        setExistingTotal(0);
        setDiscoveredTests([]);
      })
      .finally(() => {
        setIsLoadingDiscoveredTests(false);
      });
  }, [jobId]);

  const [fullUserSettings, setFullUserSettings] = useState<FullUserSettings | null>(null);

  const _handleUserSettingsChange: Dispatch<SetStateAction<FullUserSettings>> = (action) => {
    setFullUserSettings((prev) => {
      const base = prev || ({
        user_id: "default",
        github_values: {},
        quality_checks_values: {},
        test_cases_values: {},
        llm_values: {},
        created_at: "",
        updated_at: "",
      } as unknown as FullUserSettings);
      const next = typeof action === "function" ? action(base) : action;
      if (next) {
        saveUserSettings(next).catch((err) => console.warn("Auto-saving prompt settings notice:", err));
        if (typeof window !== "undefined") {
          (window as unknown as { __javaapex_user_settings?: FullUserSettings }).__javaapex_user_settings = next;
        }
      }
      return next;
    });
  };

  // Fetch user settings and global admin quality gate authorizations
  useEffect(() => {
    let isMounted = true;

    const fetchConfigAndSettings = async () => {
      // 1. Fetch User Settings
      setIsUserSettingsLoading(true);
      setUserSettingsError(null);
      try {
        const settings = await getUserSettings();
        if (!isMounted) return;
        setFullUserSettings(settings);
        if (typeof window !== "undefined") {
          (window as unknown as { __javaapex_user_settings?: FullUserSettings }).__javaapex_user_settings = settings;
        }
        const qc = settings.quality_checks_values || {};
        const sonarUrl = qc.sonarqube_url || qc.sonar_url || qc.sonar_host_url || qc.host_url || qc.url;
        const sonarToken = qc.auth_token || qc.sonar_token || qc.sonarqube_token || qc.token || qc.api_key;
        const fossaToken = qc.fossa_api_key || qc.fossa_token || qc.fossaToken || qc.api_key || qc.token;
        const sonarConf = Boolean(sonarUrl || sonarToken);
        const fossaConf = Boolean(fossaToken);
        setIsSonarConfigured(sonarConf);
        setIsFossaConfigured(fossaConf);
        const cycodeConf = Boolean(qc.cycode_client_id && qc.cycode_client_secret);
        setIsCycodeConfigured(cycodeConf);
        if (!cycodeConf) setRunCycode(false);

        // Check LLM configuration
        const llm = settings.llm_values || {};
        const genericLlm1Configured =
 
  Boolean(llm.llm1_api_key && llm.llm1_model);
 
 
 
const genericLlm2Configured =
 
  Boolean(llm.llm2_api_key && llm.llm2_model);
 
 
 
const groqConfigured =
 
  Boolean(llm.groq_api_key && llm.groq_model);
 
 
 
const huggingFaceConfigured =
 
  Boolean(llm.huggingface_api_key && llm.huggingface_model);
 
 
 
const ollamaConfigured =
 
  Boolean(llm.ollama_url);
 
 
 
setIsLlmConfiguredMod(
 
  genericLlm1Configured ||
 
  genericLlm2Configured ||
 
  groqConfigured ||
 
  huggingFaceConfigured ||
 
  ollamaConfigured
 
);
 
      } catch (err: unknown) {
        if (!isMounted) return;
        console.warn("Failed to fetch user settings (fallback to defaults):", err);
      } finally {
        if (isMounted) setIsUserSettingsLoading(false);
      }

      // 2. Fetch Global Admin Quality Check Config
      setIsAdminConfigLoading(true);
      setAdminConfigError(null);
      try {
        const res = await getQualityChecksAdminConfig();
        if (!isMounted) return;
        const rawConfig = res.quality_checks_config;
        if (rawConfig) {
          let parsed: unknown = rawConfig;
          if (typeof parsed === "string") {
            try {
              parsed = JSON.parse(parsed);
            } catch {
              // ignore
            }
          }
          if (typeof parsed === "string") {
            try {
              parsed = JSON.parse(parsed);
            } catch {
              // ignore
            }
          }
          const configArray = Array.isArray(parsed)
            ? parsed
            : (typeof parsed === "object" && parsed !== null ? Object.values(parsed) : []);
          setAdminConfig(configArray as Record<string, unknown>[]);
          const ciIsEnabled = String(res.ci_enabled ?? "true").toLowerCase() !== "false";
          const cdIsEnabled = String(res.cd_enabled ?? "true").toLowerCase() !== "false";
          setCiEnabled(ciIsEnabled);
          setCdEnabled(cdIsEnabled);
          // Quality gates are available only when both CI and CD are enabled.
          // Clear any previous selections when either pipeline is disabled so
          // hidden checks cannot still be submitted with the migration.
          if (!ciIsEnabled || !cdIsEnabled) {
            setRunSonar(false);
            setRunFossa(false);
            setRunCycode(false);
            setRunTests(false);
          }

          // Auto-disable state if not authorized globally
          type CheckItem = { name?: string; enabled?: boolean; execution_enabled?: boolean };
          const sonarGlobal = (configArray as CheckItem[]).find((c) => c.name === "SonarQube")?.enabled;
          const fossaGlobal = (configArray as CheckItem[]).find((c) => c.name === "FOSSA")?.enabled;
          const testsGlobal = (configArray as CheckItem[]).find((c) => c.name === "Run Unit Test Suite")?.enabled;

          if (sonarGlobal === false) setRunSonar(false);
          if (fossaGlobal === false) setRunFossa(false);
          const cycodeConfig = (configArray as CheckItem[]).find((c) => c.name === "Cycode");
          if (!cycodeConfig?.enabled || cycodeConfig.execution_enabled === false) setRunCycode(false);
          if (testsGlobal === false) setRunTests(false);
        } else {
          setAdminConfig([]);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        console.warn("Failed to fetch quality checks admin config (fallback to defaults):", err);
      } finally {
        if (isMounted) setIsAdminConfigLoading(false);
      }
    };

    fetchConfigAndSettings();

    const handleSettingsSaved = () => {
      fetchConfigAndSettings();
    };

    window.addEventListener("javaapex:settings-saved", handleSettingsSaved);
    return () => {
      isMounted = false;
      window.removeEventListener("javaapex:settings-saved", handleSettingsSaved);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional fetch on mount
  }, []);

  type CheckConfig = { name?: string; enabled?: boolean; execution_enabled?: boolean };
  const isQualityChecksLoading = isAdminConfigLoading || isUserSettingsLoading;
  const isSonarEnabledGlobally = Boolean((adminConfig as CheckConfig[]).find((c) => c.name === "SonarQube")?.enabled);
  const isFossaEnabledGlobally = Boolean((adminConfig as CheckConfig[]).find((c) => c.name === "FOSSA")?.enabled);
  const isTestsEnabledGlobally = Boolean((adminConfig as CheckConfig[]).find((c) => c.name === "Run Unit Test Suite")?.enabled);

  const isQualityChecksPermitted = fullUserSettings?.settings_permissions?.quality_checks !== false;
  const isUnitTestPermitted = fullUserSettings?.settings_permissions?.unit_testing !== false;
  const isFunctionalTestPermitted = fullUserSettings?.settings_permissions?.functional_testing !== false;

  const isSonarAvailable = !isQualityChecksLoading && !adminConfigError && isQualityChecksPermitted && isSonarEnabledGlobally && isSonarConfigured;
  const isFossaAvailable = !isQualityChecksLoading && !adminConfigError && isQualityChecksPermitted && isFossaEnabledGlobally && isFossaConfigured;
  const isTestsAvailable = !isAdminConfigLoading && !isUserSettingsLoading && !adminConfigError && isUnitTestPermitted && isTestsEnabledGlobally;
  const isFunctionalTestAvailable = !isUserSettingsLoading && isFunctionalTestPermitted;

  const getSonarSubtitle = () => {
    if (isQualityChecksLoading) return "Checking authorization...";
    if (adminConfigError) return "Unable to verify admin authorization.";
    if (!isQualityChecksPermitted) return "Quality Checks disabled by Admin.";
    if (!isSonarEnabledGlobally) return "Not authorized by Super Admin.";
    if (!isSonarConfigured) return "Not configured. Set up in User Settings.";
    return "Static analysis for bug and vulnerability detection.";
  };

  const cycodeConfig = (adminConfig as CheckConfig[]).find((c) => c.name === "Cycode");
  const isCycodeAvailable = !isQualityChecksLoading && !adminConfigError && !userSettingsError &&
    isQualityChecksPermitted && Boolean(cycodeConfig?.enabled) && cycodeConfig?.execution_enabled !== false && isCycodeConfigured;

  useEffect(() => {
    if (!isQualityChecksLoading) {
      if (!isSonarAvailable) setRunSonar(false);
      if (!isFossaAvailable) setRunFossa(false);
      if (!isCycodeAvailable) setRunCycode(false);
    }
  }, [isQualityChecksLoading, isSonarAvailable, isFossaAvailable, isCycodeAvailable, setRunSonar, setRunFossa, setRunCycode]);

  useEffect(() => {
    if (!isAdminConfigLoading && !isUserSettingsLoading && !isTestsAvailable) {
      setRunTests(false);
    }
  }, [isAdminConfigLoading, isUserSettingsLoading, isTestsAvailable, setRunTests]);

  useEffect(() => {
    if (!isUserSettingsLoading && !isFunctionalTestAvailable) {
      setRunFunctionalTests(false);
    }
  }, [isUserSettingsLoading, isFunctionalTestAvailable, setRunFunctionalTests]);

  const cycodeSubtitle = isQualityChecksLoading ? "Checking authorization..."
    : adminConfigError ? "Unable to verify admin authorization."
    : userSettingsError ? "Unable to verify user settings."
    : !isQualityChecksPermitted ? "Quality Checks disabled by Admin."
    : !cycodeConfig?.enabled ? "Not authorized by Super Admin."
    : cycodeConfig.execution_enabled === false ? "Execution disabled by Super Admin."
    : !isCycodeConfigured ? "Not configured. Set up in User Settings."
    : "Scan migrated code for secrets and security issues.";

  const getFossaSubtitle = () => {
    if (isQualityChecksLoading) return "Checking authorization...";
    if (adminConfigError) return "Unable to verify admin authorization.";
    if (!isQualityChecksPermitted) return "Quality Checks disabled by Admin.";
    if (!isFossaEnabledGlobally) return "Not authorized by Super Admin.";
    if (!isFossaConfigured) return "Not configured. Set up in User Settings.";
    return "Open-source license compliance and security.";
  };

  const getTestsSubtitle = () => {
    if (isAdminConfigLoading || isUserSettingsLoading) return "Checking authorization...";
    if (adminConfigError) return "Unable to verify admin authorization.";
    if (!isUnitTestPermitted) return "Unit Testing disabled by Admin.";
    if (!isTestsEnabledGlobally) return "Not authorized by Super Admin.";
    return "Execute discovered unit tests in the repository.";
  };

  const apiEndpointCount = repoAnalysis?.api_endpoints?.length ?? 0;
  void apiEndpointCount;

  const hasNoTestPermissions = !isUserSettingsLoading && !isQualityChecksPermitted && !isUnitTestPermitted && !isFunctionalTestPermitted;

  return (
    <div className="discovery-dashboard-wrapper page-modernization">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 14, marginBottom: 24, paddingTop: 6 }}>
        <div className="mod-topic-header-icon">
          <span className="mod-rocket-icon-animated"><FaRocket /></span>
        </div>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a", letterSpacing: "-0.01em" }}>
          Build Modernization &amp; Migration
        </h2>
      </div>

      {hasNoTestPermissions && (
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "80px 20px",
          textAlign: "center",
        }}>
          <button
            style={{
              ...styles.primaryBtn,
              padding: "16px 40px",
              fontSize: "16px",
              fontWeight: 700,
              borderRadius: "10px",
              boxShadow: "0 10px 25px -5px rgba(37, 99, 235, 0.4)",
              opacity: loading ? 0.5 : 1,
              cursor: loading ? "not-allowed" : "pointer",
            }}
            onClick={handleStartMigrationClick}
            disabled={loading}
          >
            {renderForwardButtonLabel(loading ? (startMigrationStatusText || "Preparing migration...") : "Start Migration")}
          </button>
        </div>
      )}

      {/* LLM Not Configured Warning Banner */}
      {isLlmConfiguredMod === false && (
        <div style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 10,
          background: "#fffbeb",
          border: "1.5px solid #fde68a",
          borderRadius: 10,
          padding: "12px 16px",
          marginBottom: 20,
          fontSize: 13,
          color: "#92400e",
          lineHeight: 1.5,
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 1 }}>
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <div>
            <strong>LLM not configured.</strong> Migration uses AI to generate modernized code.
            Please go to <strong>User Settings → Intelligence</strong> and configure an AI provider (Groq, Hugging Face, or Ollama) before starting migration.
          </div>
        </div>
      )}

      {!cdEnabled && (
        <div style={{
          background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: 10,
          padding: "10px 16px", marginBottom: 16, fontSize: 13, color: "#475569",
        }}>
          Continuous Deployment is disabled in Settings. Deployment and artifact publishing are unavailable for this migration.
        </div>
      )}

      {/* ── Quality Gates & Test Suites Selection (Rendered only when permitted) ── */}
      {ciEnabled && cdEnabled && (isQualityChecksPermitted || isUnitTestPermitted || isFunctionalTestPermitted) && (
        <div className="mod-qgate-row-panel">
          <div className="mod-qgate-row-header">
            <div className="mod-qgate-row-title">
              <span style={{ fontWeight: 800, fontSize: 17, color: "#0f172a", letterSpacing: "-0.2px" }}>
                Quality Gates
              </span>
            </div>
          </div>

          <div className="mod-qgate-single-row">
            {/* 1. SonarQube */}
            {isQualityChecksPermitted && (
              <div
                className={`mod-qgate-pill-card ${runSonar && isSonarAvailable ? "mod-qgate-pill-active" : ""} ${!isSonarAvailable ? "mod-qgate-pill-disabled" : ""}`}
                onClick={() => {
                  if (isSonarAvailable) setRunSonar(!runSonar);
                }}
              >
                <div className="mod-qgate-pill-top">
                  <div className="mod-qgate-pill-icon">
                    <FaSearch />
                  </div>
                  <div className={`mod-qgate-morph-btn ${runSonar && isSonarAvailable ? "mod-qgate-morph-btn-active" : ""}`}>
                    {runSonar && isSonarAvailable ? <FaCheck /> : <FaPlus />}
                  </div>
                </div>
                <div className="mod-qgate-pill-body">
                  <div className="mod-qgate-pill-name">SonarQube</div>
                  <div className="mod-qgate-pill-sub">{getSonarSubtitle()}</div>
                </div>
              </div>
            )}

            {/* 2. FOSSA */}
            {isQualityChecksPermitted && (
              <div
                className={`mod-qgate-pill-card ${runFossa && isFossaAvailable ? "mod-qgate-pill-active" : ""} ${!isFossaAvailable ? "mod-qgate-pill-disabled" : ""}`}
                onClick={() => {
                  if (isFossaAvailable) setRunFossa(!runFossa);
                }}
              >
                <div className="mod-qgate-pill-top">
                  <div className="mod-qgate-pill-icon">
                    <FaShieldAlt />
                  </div>
                  <div className={`mod-qgate-morph-btn ${runFossa && isFossaAvailable ? "mod-qgate-morph-btn-active" : ""}`}>
                    {runFossa && isFossaAvailable ? <FaCheck /> : <FaPlus />}
                  </div>
                </div>
                <div className="mod-qgate-pill-body">
                  <div className="mod-qgate-pill-name">FOSSA</div>
                  <div className="mod-qgate-pill-sub">{getFossaSubtitle()}</div>
                </div>
              </div>
            )}

            {/* 3. Cycode */}
            {isQualityChecksPermitted && (
              <div
                className={`mod-qgate-pill-card ${runCycode && isCycodeAvailable ? "mod-qgate-pill-active" : ""} ${!isCycodeAvailable ? "mod-qgate-pill-disabled" : ""}`}
                onClick={() => {
                  if (isCycodeAvailable) setRunCycode(!runCycode);
                }}
              >
                <div className="mod-qgate-pill-top">
                  <div className="mod-qgate-pill-icon">
                    <FaShieldAlt />
                  </div>
                  <div className={`mod-qgate-morph-btn ${runCycode && isCycodeAvailable ? "mod-qgate-morph-btn-active" : ""}`}>
                    {runCycode && isCycodeAvailable ? <FaCheck /> : <FaPlus />}
                  </div>
                </div>
                <div className="mod-qgate-pill-body">
                  <div className="mod-qgate-pill-name">Cycode</div>
                  <div className="mod-qgate-pill-sub">{cycodeSubtitle}</div>
                </div>
              </div>
            )}

            {/* 4. Run Unit Test Suite */}
            {isUnitTestPermitted && (
              <div
                className={`mod-qgate-pill-card ${runTests && isTestsAvailable ? "mod-qgate-pill-active" : ""} ${!isTestsAvailable ? "mod-qgate-pill-disabled" : ""}`}
                onClick={() => {
                  if (isTestsAvailable) setRunTests(!runTests);
                }}
              >
                <div className="mod-qgate-pill-top">
                  <div className="mod-qgate-pill-icon">
                    <FaFileAlt />
                  </div>
                  <div className={`mod-qgate-morph-btn ${runTests && isTestsAvailable ? "mod-qgate-morph-btn-active" : ""}`}>
                    {runTests && isTestsAvailable ? <FaCheck /> : <FaPlus />}
                  </div>
                </div>
                <div className="mod-qgate-pill-body">
                  <div className="mod-qgate-pill-name">Run Unit Test Suite</div>
                  <div className="mod-qgate-pill-sub">{getTestsSubtitle()}</div>
                </div>
              </div>
            )}

            {/* 5. Functional Testing */}
            {isFunctionalTestPermitted && (
              <div
                className={`mod-qgate-pill-card ${runFunctionalTests && isFunctionalTestAvailable ? "mod-qgate-pill-active" : ""} ${!isFunctionalTestAvailable ? "mod-qgate-pill-disabled" : ""}`}
                onClick={() => {
                  if (isFunctionalTestAvailable) setRunFunctionalTests(!runFunctionalTests);
                }}
              >
                <div className="mod-qgate-pill-top">
                  <div className="mod-qgate-pill-icon">
                    <FaFlask />
                  </div>
                  <div className={`mod-qgate-morph-btn ${runFunctionalTests && isFunctionalTestAvailable ? "mod-qgate-morph-btn-active" : ""}`}>
                    {runFunctionalTests && isFunctionalTestAvailable ? <FaCheck /> : <FaPlus />}
                  </div>
                </div>
                <div className="mod-qgate-pill-body">
                  <div className="mod-qgate-pill-name">Functional Testing</div>
                  <div className="mod-qgate-pill-sub">
                    {runFunctionalTests
                      ? "Upload & run functional test scenarios"
                      : "Functional testing disabled"}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Existing Test Cases Section (Discovered Only - Filtered by Quality Gate Selection) */}
      {(isUnitTestPermitted || isFunctionalTestPermitted) && (
        <ExistingTestCasesPanel
          jobId={jobId}
          discoveredTests={discoveredTests}
          framework={existingFramework || "JUnit"}
          isRunning={false}
          isLoading={isLoadingDiscoveredTests}
          runTests={runTests}
          runFunctionalTests={runFunctionalTests}
          onSelectTest={(t: TestResult | TestSelectionItem) => {
            setTestDetailReport(buildTestDetailReport(t, "NOT_EXECUTED"));
            setShowTestDetailModal(true);
          }}
        />
      )}

      {/* Detected technologies and their planned version changes */}
      {(() => {
        const analyzedById = new Map((dependencyAnalysis?.dependencies || []).map((item) => [item.id.toLowerCase(), item]));
        const groups: Record<string, { name: string; current: string; target: string; status: string; javaCompatibility: string; frameworkCompatibility: string; reason: string; confidence: string }[]> = {
          Framework: [],
          Library: [],
          Dependency: [],
        };
        const groupColors: Record<string, { text: string; background: string; border: string }> = {
          Framework: { text: "#1d4ed8", background: "#eff6ff", border: "#bfdbfe" },
          Library: { text: "#047857", background: "#ecfdf5", border: "#a7f3d0" },
          Dependency: { text: "#b45309", background: "#fffbeb", border: "#fde68a" },
        };
        (repoAnalysis?.dependencies || []).forEach((dependency) => {
          const coordinate = `${dependency.group_id || ""}:${dependency.artifact_id || ""}`.toLowerCase();
          const analysis = analyzedById.get(coordinate);
          const category = (analysis?.category || "").toLowerCase();
          const group = category === "framework" ? "Framework"
            : ["persistence", "security", "database", "testing", "logging", "web", "utility"].includes(category) ? "Library"
            : "Dependency";
          groups[group].push({
            name: dependency.group_id ? `${dependency.group_id}:${dependency.artifact_id}` : dependency.artifact_id || "Dependency",
            current: dependency.current_version || "Unknown",
            target: analysis?.recommended_version || "Not Determined",
            status: analysis?.upgrade_status || "UNKNOWN",
            javaCompatibility: analysis?.java_compatibility || "Unknown",
            frameworkCompatibility: analysis?.framework_compatibility || "Unknown",
            reason: analysis?.upgrade_reason || "The dependency analysis did not return an upgrade explanation.",
            confidence: analysis?.upgrade_confidence || "Low",
          });
        });
        const javaCurrent = repoAnalysis?.java_version || repoAnalysis?.java_version_from_build;
        const total = Object.values(groups).reduce((sum, rows) => sum + rows.length, 0) + (javaCurrent ? 1 : 0);
        return (
          <section style={{ margin: "22px 0", border: "1px solid #e2e8f0", borderRadius: 16, background: "#fff", boxShadow: "0 2px 5px rgba(15,23,42,.06)", overflow: "hidden" }}>
            <div style={{ padding: "18px 20px", borderBottom: "1px solid #eef2f7", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <div><h3 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "#1e40af" }}>Detected Versions &amp; Upgrade Recommendations</h3><p style={{ margin: "5px 0 0", color: "#64748b", fontSize: 12 }}>Detected versions come from the repository. Upgrade targets are LLM suggestions for the selected Java version.</p></div>
              <span style={{ padding: "4px 9px", borderRadius: 7, background: "#eff6ff", color: "#2563eb", fontSize: 11, fontWeight: 700 }}>{total} items</span>
            </div>
            <div style={{ padding: "4px 20px" }}>
              {javaCurrent && <div style={{ padding: "14px 0", borderBottom: "1px solid #f1f5f9", display: "grid", gridTemplateColumns: "minmax(180px, 1.5fr) minmax(110px, .7fr) minmax(110px, 1fr) 26px minmax(120px, 1fr)", gap: 12, alignItems: "center" }}><strong>Java</strong><span style={{ color: "#64748b", fontSize: 12 }}>Runtime</span><span>{javaCurrent}</span><span style={{ color: "#2563eb" }}>→</span><strong style={{ color: "#047857" }}>{targetJavaVersion || "Not selected"}</strong></div>}
              {total > 0 && <div style={{ display: "grid", gridTemplateColumns: "minmax(180px, 1.5fr) minmax(110px, 1fr) 26px minmax(140px, 1fr)", gap: 12, padding: "12px 0 4px", color: "#64748b", fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: ".04em" }}><span>Detected component</span><span>Current version</span><span aria-hidden="true"> </span><span>Upgrade recommendation</span></div>}
              {Object.entries(groups).map(([group, rows]) => rows.length > 0 && <div key={group} style={{ padding: "14px 0 4px" }}>
                <h4 style={{ display: "inline-flex", alignItems: "center", margin: "0 0 4px", padding: "5px 10px", borderRadius: 7, border: `1px solid ${groupColors[group].border}`, background: groupColors[group].background, color: groupColors[group].text, fontSize: 12, fontWeight: 800 }}>{group} ({rows.length})</h4>
                {rows.map((row) => <div key={row.name} style={{ display: "grid", gridTemplateColumns: "minmax(180px, 1.5fr) minmax(110px, 1fr) 26px minmax(140px, 1fr)", alignItems: "center", gap: 12, padding: "12px 0", borderBottom: "1px solid #f1f5f9" }}>
                  <strong style={{ color: "#1e293b", fontSize: 13, overflowWrap: "anywhere" }}>{row.name}</strong><span style={{ color: "#475569", fontSize: 13 }}>{row.current}</span><span aria-hidden="true" style={{ color: "#2563eb", fontWeight: 800 }}>→</span><span title={`${row.reason} Java: ${row.javaCompatibility}. Framework: ${row.frameworkCompatibility}. Confidence: ${row.confidence}.`} style={{ color: row.target === "Not Determined" ? "#94a3b8" : "#047857", fontSize: 13 }}><strong>{row.target}</strong><small style={{ display: "block", marginTop: 3, color: "#64748b", fontSize: 10 }}>{row.status.replaceAll("_", " ")} · Java {row.javaCompatibility} · {row.confidence} confidence</small></span>
                </div>)}
              </div>)}
              {total === 0 && <div style={{ padding: "26px 0", textAlign: "center", color: "#64748b", fontSize: 13 }}>No Java version or dependencies were detected for this repository.</div>}
              {total > 0 && dependencyAnalysis?.provider_used && <p style={{ margin: "12px 0", color: "#94a3b8", fontSize: 11 }}>Recommendations generated by {dependencyAnalysis.provider_used} for Java {targetJavaVersion || "target not selected"}.</p>}
            </div>
          </section>
        );
      })()}

      {/* Test Validation Report Modal */}
      {showValidationReport && existingExecResult && (
        <ExistingTestValidationReport
          metrics={existingExecResult.metrics || {}}
          frameworkInfo={existingExecResult.framework_info}
          testResults={
            runTests && !runFunctionalTests
              ? displayTestResults.filter((t) => classifyTestType(t) === "Unit")
              : !runTests && runFunctionalTests
              ? displayTestResults.filter((t) => classifyTestType(t) === "UI" || classifyTestType(t) === "API")
              : displayTestResults
          }
          fileBreakdown={existingExecResult.file_breakdown || []}
          logs={existingLogs}
          onClose={() => setShowValidationReport(false)}
          onRunAgain={() => {}}
          isRunning={isRunningExisting}
          hasRun={hasExistingTestsRun}
          onSelectTest={(t: TestResult | TestSelectionItem) => {
            setTestDetailReport(buildTestDetailReport(t));
            setShowTestDetailModal(true);
          }}
        />
      )}

      {viewingTestFile && typeof document !== "undefined" && createPortal(
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0, width: "100vw", height: "100vh",
          zIndex: 99999, background: "rgba(15,23,42,0.7)", backdropFilter: "blur(4px)",
          display: "flex", alignItems: "center", justifyContent: "center",
          padding: 20, boxSizing: "border-box",
        }} onClick={() => setViewingTestFile(null)}>
          <div style={{
            background: "#fff", borderRadius: 14, maxWidth: 900, width: "100%",
            maxHeight: "85vh", display: "flex", flexDirection: "column",
            boxShadow: "0 25px 80px rgba(0,0,0,0.35)",
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "16px 20px", borderBottom: "1px solid #e2e8f0",
              background: "linear-gradient(135deg, #0f172a, #1e293b)",
              borderRadius: "14px 14px 0 0",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 16 }}>📄</span>
                <span style={{ fontWeight: 700, fontSize: 14, color: "#fff", fontFamily: "monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {viewingTestFile.name}
                </span>
                <span style={{ fontSize: 11, color: "#94a3b8", fontFamily: "monospace", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {viewingTestFile.path}
                </span>
                <span style={{ fontSize: 10, background: "#22c55e30", color: "#22c55e", padding: "2px 7px", borderRadius: 4, fontWeight: 600, whiteSpace: "nowrap" }}>
                  READ ONLY
                </span>
              </div>
              <button onClick={() => setViewingTestFile(null)} style={{
                background: "rgba(255,255,255,0.15)", border: "none", color: "#fff",
                width: 30, height: 30, borderRadius: 8, cursor: "pointer",
                fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center",
              }}>✕</button>
            </div>
            <div style={{ overflow: "auto", flex: 1, background: "#0d1117", padding: 16 }}>
              {testFileLoading ? (
                <div style={{ textAlign: "center", padding: 40, color: "#94a3b8" }}>Loading...</div>
              ) : (
                <pre style={{
                  margin: 0, fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
                  fontSize: 13, lineHeight: 1.6, color: "#e2e8f0", whiteSpace: "pre-wrap", wordBreak: "break-all",
                }}>{viewingTestFile.content || "// File content unavailable"}</pre>
              )}
            </div>
            <div style={{
              display: "flex", justifyContent: "flex-end", padding: "12px 20px",
              borderTop: "1px solid #e2e8f0", background: "#f8fafc",
              borderRadius: "0 0 14px 14px",
            }}>
              <button onClick={() => setViewingTestFile(null)} style={{
                padding: "8px 20px", borderRadius: 8, border: "1px solid #e2e8f0",
                background: "#fff", cursor: "pointer", fontSize: 13, fontWeight: 600,
                color: "#475569",
              }}>Close</button>
            </div>
          </div>
        </div>,
        document.body
      )}

      <TestReportsModal
        isOpen={showTestDetailModal}
        onClose={() => setShowTestDetailModal(false)}
        data={testDetailReport}
      />

      {/* ── Quality Gates Reminder Modal (Confirmation Popup) ── */}
      {showQualityGateReminder && typeof document !== "undefined" && createPortal(
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            width: "100vw",
            height: "100vh",
            background: "rgba(15, 23, 42, 0.65)",
            backdropFilter: "blur(4px)",
            WebkitBackdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 99999,
            padding: "16px",
            boxSizing: "border-box",
          }}
          onClick={() => setShowQualityGateReminder(false)}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 16,
              width: "100%",
              maxWidth: 480,
              maxHeight: "min(90vh, 540px)",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25), 0 10px 20px -5px rgba(0, 0, 0, 0.1)",
              border: "1px solid #e2e8f0",
              overflow: "hidden",
              animation: "modFadeUp 0.25s cubic-bezier(0.16, 1, 0.3, 1) both",
              margin: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "20px 24px",
                borderBottom: "1px solid #f1f5f9",
                background: "#fffbeb",
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: "#fef3c7",
                  color: "#d97706",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 20,
                  flexShrink: 0,
                }}
              >
                <FaShieldAlt />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: "#92400e" }}>
                  Quality Gates Not Selected
                </h3>
                <span style={{ fontSize: 12, color: "#b45309", fontWeight: 500 }}>
                  Migration Configuration Reminder
                </span>
              </div>
            </div>

            {/* Modal Body */}
            <div
              style={{
                padding: "24px",
                color: "#334155",
                fontSize: 14,
                lineHeight: 1.6,
                overflowY: "auto",
                flex: "1 1 auto",
              }}
            >
              <p style={{ margin: 0, marginBottom: 10, fontWeight: 500 }}>
                SonarQube and/or FOSSA quality gates have not been selected.
              </p>
              <p style={{ margin: 0, color: "#64748b", fontSize: 13 }}>
                Would you like to continue without enabling them?
              </p>
            </div>

            {/* Modal Footer */}
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: 12,
                padding: "16px 24px",
                background: "#f8fafc",
                borderTop: "1px solid #e2e8f0",
                flexShrink: 0,
              }}
            >
              <button
                type="button"
                onClick={() => setShowQualityGateReminder(false)}
                style={{
                  padding: "10px 18px",
                  borderRadius: 8,
                  border: "1px solid #cbd5e1",
                  background: "#fff",
                  color: "#475569",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                Go Back
              </button>
              <button
                type="button"
                onClick={handleConfirmContinueMigration}
                disabled={loading}
                style={{
                  padding: "10px 20px",
                  borderRadius: 8,
                  border: "none",
                  background: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
                  color: "#fff",
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: "pointer",
                  boxShadow: "0 4px 12px rgba(217, 119, 6, 0.25)",
                  transition: "all 0.15s ease",
                }}
              >
                {loading ? (startMigrationStatusText || "Preparing migration...") : "Continue Migration"}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
      {!hasNoTestPermissions && (
        <div style={{ ...styles.btnRow, justifyContent: "flex-end" }} className="modernization-nav-btn-row">
          <button
            style={{ ...styles.primaryBtn, opacity: loading ? 0.5 : 1 }}
            onClick={handleStartMigrationClick}
            disabled={loading}
          >
            {renderForwardButtonLabel(loading ? (startMigrationStatusText || "Preparing migration...") : "Start Migration")}
          </button>
        </div>
      )}
    </div>
  );
}
