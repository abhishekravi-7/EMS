import React, { useEffect, useState, useRef, useMemo, type Dispatch, type SetStateAction } from "react";
import { createPortal } from "react-dom";
import { FaRocket, FaInfoCircle, FaSearch, FaShieldAlt, FaVial, FaPen, FaFileAlt, FaFlask } from "react-icons/fa";
import {
  scanExistingTests,
  getCachedExistingTests,
  runExistingTests,
  getExistingTestsStatus,
  stopExistingTests,
  type TestResult,
  type TestSelectionItem,
  type ExistingTestRunResponse,
  type ApiEvidence,
} from "../services/existingTestService";
import { ExistingTestCasesPanel } from "./ExistingTestCasesPanel";
import { ExistingTestCoverage } from "./ExistingTestCoverage";
import { ExistingTestTable } from "./ExistingTestTable";
import { ExistingTestLogs } from "./ExistingTestLogs";
import { ExistingTestValidationReport } from "./ExistingTestValidationReport";
import { FunctionalTestingTabs } from "./FunctionalTestingTabs";
import { FunctionalTestingDocumentCard } from "./FunctionalTestingDocumentCard";
import { ProposedTestCasesPanel } from "./ProposedTestCasesPanel";
import { runApprovedProposedTests } from "../services/proposedTestService";
import { TestReportsModal, type TestReportData } from "./TestReportsModal";
import { wizardStyles as styles } from "@/shared/components/wizard/wizardStyles";
import { renderWizardIconBadge, renderBackButtonLabel, renderForwardButtonLabel } from "@/shared/components/wizard";
import type { RepoAnalysis, RepoInfo } from "@/shared/types/domain";
import type { FunctionalTestScopePreview } from "../services/modernizationService";
import { getLocalProjectFileContent } from "@/features/connect/services/connectService";
import { getFileContent } from "@/features/discovery/services/discoveryService";
import type { useModernizationState } from "../hooks/useModernizationState";
import { getUserSettings, getQualityChecksAdminConfig } from "@/features/admin/services/adminService";

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
  selectedRepo: RepoInfo | null;
  repoUrl: string;
  currentToken: string;
  functionalTestToolMethod: string[];
  setFunctionalTestToolMethod: Dispatch<SetStateAction<string[]>>;
  functionalTestingTools: FunctionalTestingTool[];
  hasUI: boolean;
  localApiTestCases: FunctionalTestScopePreview["apiTestCases"];
  loading: boolean;
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
  selectedRepo,
  repoUrl: _repoUrl,
  currentToken,
  functionalTestToolMethod: _functionalTestToolMethod,
  setFunctionalTestToolMethod: _setFunctionalTestToolMethod,
  functionalTestingTools: _functionalTestingTools,
  hasUI,
  localApiTestCases,
  loading,
  repoUtils,
  onBack,
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

  const { isLocalRepoRef, extractLocalRepoPath } = repoUtils;
  const [viewingTestFile, setViewingTestFile] = useState<{ name: string; path: string; content?: string } | null>(null);
  const [testFileLoading, setTestFileLoading] = useState(false);

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
  const [adminConfig, setAdminConfig] = useState<any[]>([]);
  const [isAdminConfigLoading, setIsAdminConfigLoading] = useState(true);
  const [isUserSettingsLoading, setIsUserSettingsLoading] = useState(true);
  const [adminConfigError, setAdminConfigError] = useState<string | null>(null);
  const [userSettingsError, setUserSettingsError] = useState<string | null>(null);



  // Proposed tests
  const [proposedTests, setProposedTests] = useState<any[]>([]);
  const [existingElapsedTime, setExistingElapsedTime] = useState(0);
  const [existingLogs, setExistingLogs] = useState<{ ts: string; msg: string; level: string }[]>([]);
  const [existingExecResult, setExistingExecResult] = useState<ExistingTestRunResponse | null>(null);
  const [_showExistingLogs, setShowExistingLogs] = useState(false);
  const [showValidationReport, setShowValidationReport] = useState(false);
  const [_validationFilter, _setValidationFilter] = useState("ALL");
  const [_validationSearch, _setValidationSearch] = useState("");
  const [_expandedFailures, _setExpandedFailures] = useState<Record<number, boolean>>({});
  const [showTestDetailModal, setShowTestDetailModal] = useState(false);
  const [testDetailReport, setTestDetailReport] = useState<TestReportData | null>(null);
  const [showQualityGateReminder, setShowQualityGateReminder] = useState(false);

  const handleStartMigrationClick = () => {
    if (loading) return;
    if (!runSonar || !runFossa) {
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
  const existingPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  const testProgressPercent = (existingTotal && existingTotal - 1 > 0)
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
        const qc = settings.quality_checks_values || {};
        const sonarConf = Boolean(qc.sonarqube_url && qc.auth_token);
        const fossaConf = Boolean(qc.fossa_api_key);
        setIsSonarConfigured(sonarConf);
        setIsFossaConfigured(fossaConf);
        const cycodeConf = Boolean(qc.cycode_client_id && qc.cycode_client_secret);
        setIsCycodeConfigured(cycodeConf);
        if (!cycodeConf) setRunCycode(false);

        // Check LLM configuration
        const llm = settings.llm_values || {};
        const groqOk = Boolean(llm.groq_api_key && llm.groq_model);
        const hfOk = Boolean(llm.huggingface_api_key && llm.huggingface_model);
        const ollamaOk = Boolean(llm.ollama_url);
        setIsLlmConfiguredMod(groqOk || hfOk || ollamaOk);

        // Auto-disable if not configured
        if (!sonarConf) setRunSonar(false);
        if (!fossaConf) setRunFossa(false);
      } catch (err: any) {
        if (!isMounted) return;
        console.error("Failed to fetch user settings:", err);
        setUserSettingsError("Failed to fetch user settings");
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
          let parsed: any = rawConfig;
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
          setAdminConfig(configArray);

          // Auto-disable state if not authorized globally
          const sonarGlobal = configArray.find((c: any) => c.name === "SonarQube")?.enabled;
          const fossaGlobal = configArray.find((c: any) => c.name === "FOSSA")?.enabled;
          const testsGlobal = configArray.find((c: any) => c.name === "Run Unit Test Suite")?.enabled;

          if (sonarGlobal === false) setRunSonar(false);
          if (fossaGlobal === false) setRunFossa(false);
          const cycodeConfig = configArray.find((c: any) => c.name === "Cycode");
          if (!cycodeConfig?.enabled || cycodeConfig.execution_enabled === false) setRunCycode(false);
          if (testsGlobal === false) setRunTests(false);
        } else {
          setAdminConfig([]);
        }
      } catch (err: any) {
        if (!isMounted) return;
        console.error("Failed to fetch quality checks admin config:", err);
        setAdminConfigError("Failed to fetch quality checks admin configuration");
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
  }, []);

  const isQualityChecksLoading = isAdminConfigLoading || isUserSettingsLoading;
  const isSonarEnabledGlobally = Boolean(adminConfig.find((c: any) => c.name === "SonarQube")?.enabled);
  const isFossaEnabledGlobally = Boolean(adminConfig.find((c: any) => c.name === "FOSSA")?.enabled);
  const isTestsEnabledGlobally = Boolean(adminConfig.find((c: any) => c.name === "Run Unit Test Suite")?.enabled);

  const isSonarAvailable = !isQualityChecksLoading && !adminConfigError && isSonarEnabledGlobally && isSonarConfigured;
  const isFossaAvailable = !isQualityChecksLoading && !adminConfigError && isFossaEnabledGlobally && isFossaConfigured;
  const isTestsAvailable = !isAdminConfigLoading && !adminConfigError && isTestsEnabledGlobally;

  const getSonarSubtitle = () => {
    if (isQualityChecksLoading) return "Checking authorization...";
    if (adminConfigError) return "Unable to verify admin authorization.";
    if (!isSonarEnabledGlobally) return "Not authorized by Super Admin.";
    if (!isSonarConfigured) return "Not configured. Set up in User Settings.";
    return "Static analysis for bug and vulnerability detection.";
  };

  const cycodeConfig = adminConfig.find((c: any) => c.name === "Cycode");
  const isCycodeAvailable = !isQualityChecksLoading && !adminConfigError && !userSettingsError &&
    Boolean(cycodeConfig?.enabled) && cycodeConfig?.execution_enabled !== false && isCycodeConfigured;
  useEffect(() => {
    if (!isQualityChecksLoading && !isCycodeAvailable) setRunCycode(false);
  }, [isQualityChecksLoading, isCycodeAvailable, setRunCycode]);
  const cycodeSubtitle = isQualityChecksLoading ? "Checking authorization..."
    : adminConfigError ? "Unable to verify admin authorization."
    : userSettingsError ? "Unable to verify user settings."
    : !cycodeConfig?.enabled ? "Not authorized by Super Admin."
    : cycodeConfig.execution_enabled === false ? "Execution disabled by Super Admin."
    : !isCycodeConfigured ? "Not configured. Set up in User Settings."
    : "Scan migrated code for secrets and security issues.";

  const getFossaSubtitle = () => {
    if (isQualityChecksLoading) return "Checking authorization...";
    if (adminConfigError) return "Unable to verify admin authorization.";
    if (!isFossaEnabledGlobally) return "Not authorized by Super Admin.";
    if (!isFossaConfigured) return "Not configured. Set up in User Settings.";
    return "Open-source license compliance and security.";
  };

  const getTestsSubtitle = () => {
    if (isAdminConfigLoading) return "Checking authorization...";
    if (adminConfigError) return "Unable to verify admin authorization.";
    if (!isTestsEnabledGlobally) return "Not authorized by Super Admin.";
    return "Execute discovered unit tests in the repository.";
  };

  const apiEndpointCount = repoAnalysis?.api_endpoints?.length ?? 0;
  void apiEndpointCount;

  return (
    <>
      <div style={styles.card}>
      <div style={styles.stepHeader}>
        {renderWizardIconBadge(<FaRocket />, "#f59e0b", "xl")}
        <div>
          <h2 style={styles.title}>Build Modernization &amp; Migration</h2>
        </div>
      </div>

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

      {/* ── Quality Gates & Test Suites Selection (3 Equal Cards in 1 Row) ── */}
      <div style={{ marginBottom: 28, marginTop: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <FaShieldAlt style={{ fontSize: 18, color: "#0f172a" }} />
          <span style={{ fontWeight: 800, fontSize: 18, color: "#0f172a" }}>Quality Gates</span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
          {/* 1. SonarQube */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "14px 18px",
              borderRadius: 12,
              border: `2px solid ${runSonar && isSonarAvailable ? "#22c55e" : "#e2e8f0"}`,
              background: runSonar && isSonarAvailable ? "#f0fdf4" : (isSonarAvailable ? "#fff" : "#f8fafc"),
              cursor: isSonarAvailable ? "pointer" : "not-allowed",
              transition: "all 0.15s ease",
              minHeight: 88,
              opacity: isSonarAvailable ? 1 : 0.6,
            }}
            onClick={() => {
              if (isSonarAvailable) setRunSonar(!runSonar);
            }}
          >
            <input
              type="checkbox"
              checked={runSonar && isSonarAvailable}
              disabled={!isSonarAvailable}
              onChange={(e) => {
                e.stopPropagation();
                if (isSonarAvailable) setRunSonar(e.target.checked);
              }}
              style={{ width: 18, height: 18, accentColor: "#22c55e", cursor: isSonarAvailable ? "pointer" : "not-allowed", flexShrink: 0 }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: "#0f172a", display: "flex", alignItems: "center", gap: 8 }}>
                <FaSearch style={{ fontSize: 12, color: runSonar && isSonarAvailable ? "#166534" : "#64748b", flexShrink: 0 }} />
                <span>SonarQube</span>
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2, lineHeight: 1.3 }}>
                {getSonarSubtitle()}
              </div>
            </div>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 10,
                fontWeight: 700,
                padding: "3px 10px",
                borderRadius: 6,
                background: runSonar && isSonarAvailable ? "#dcfce7" : "#f1f5f9",
                color: runSonar && isSonarAvailable ? "#166534" : "#64748b",
                flexShrink: 0,
              }}
            >
              RECOMMENDED
            </span>
          </div>

          {/* 2. FOSSA */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "14px 18px",
              borderRadius: 12,
              border: `2px solid ${runFossa && isFossaAvailable ? "#22c55e" : "#e2e8f0"}`,
              background: runFossa && isFossaAvailable ? "#f0fdf4" : (isFossaAvailable ? "#fff" : "#f8fafc"),
              cursor: isFossaAvailable ? "pointer" : "not-allowed",
              transition: "all 0.15s ease",
              minHeight: 88,
              opacity: isFossaAvailable ? 1 : 0.6,
            }}
            onClick={() => {
              if (isFossaAvailable) setRunFossa(!runFossa);
            }}
          >
            <input
              type="checkbox"
              checked={runFossa && isFossaAvailable}
              disabled={!isFossaAvailable}
              onChange={(e) => {
                e.stopPropagation();
                if (isFossaAvailable) setRunFossa(e.target.checked);
              }}
              style={{ width: 18, height: 18, accentColor: "#22c55e", cursor: isFossaAvailable ? "pointer" : "not-allowed", flexShrink: 0 }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: "#0f172a", display: "flex", alignItems: "center", gap: 8 }}>
                <FaShieldAlt style={{ fontSize: 12, color: runFossa && isFossaAvailable ? "#166534" : "#64748b", flexShrink: 0 }} />
                <span>FOSSA</span>
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2, lineHeight: 1.3 }}>
                {getFossaSubtitle()}
              </div>
            </div>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 10,
                fontWeight: 700,
                padding: "3px 10px",
                borderRadius: 6,
                background: runFossa && isFossaAvailable ? "#dcfce7" : "#f1f5f9",
                color: runFossa && isFossaAvailable ? "#166534" : "#64748b",
                flexShrink: 0,
              }}
            >
              RECOMMENDED
            </span>
          </div>

          <label style={{
            display: "flex", alignItems: "center", gap: 12, padding: "14px 18px", borderRadius: 12,
            border: `2px solid ${runCycode && isCycodeAvailable ? "#6366f1" : "#e2e8f0"}`,
            background: runCycode && isCycodeAvailable ? "#eef2ff" : "#f8fafc",
            cursor: isCycodeAvailable ? "pointer" : "not-allowed", minHeight: 88,
            opacity: isCycodeAvailable ? 1 : 0.6,
          }}>
            <input type="checkbox" aria-label="Run Cycode security scans"
              checked={runCycode && isCycodeAvailable} disabled={!isCycodeAvailable}
              onChange={(event) => setRunCycode(event.target.checked)}
              style={{ width: 18, height: 18, accentColor: "#6366f1", flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: "#0f172a", display: "flex", alignItems: "center", gap: 8 }}>
                <FaShieldAlt aria-hidden="true" /><span>Cycode</span>
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2, lineHeight: 1.3 }}>{cycodeSubtitle}</div>
            </div>
            <span style={{ fontSize: 10, fontWeight: 700, padding: "3px 8px", borderRadius: 6,
              color: "#4338ca", background: "#e0e7ff", flexShrink: 0 }}>
              {runCycode && isCycodeAvailable ? "ENABLED" : "OPTIONAL"}
            </span>
          </label>

          {/* 3. Run Unit Test Suite */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "14px 18px",
              borderRadius: 12,
              border: `2px solid ${runTests && isTestsAvailable ? "#22c55e" : "#e2e8f0"}`,
              background: runTests && isTestsAvailable ? "#f0fdf4" : (isTestsAvailable ? "#fff" : "#f8fafc"),
              cursor: isTestsAvailable ? "pointer" : "not-allowed",
              transition: "all 0.15s ease",
              minHeight: 88,
              opacity: isTestsAvailable ? 1 : 0.6,
            }}
            onClick={() => {
              if (isTestsAvailable) setRunTests(!runTests);
            }}
          >
            <input
              type="checkbox"
              checked={runTests && isTestsAvailable}
              disabled={!isTestsAvailable}
              onChange={(e) => {
                e.stopPropagation();
                if (isTestsAvailable) setRunTests(e.target.checked);
              }}
              style={{ width: 18, height: 18, accentColor: "#22c55e", cursor: isTestsAvailable ? "pointer" : "not-allowed", flexShrink: 0 }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: "#0f172a", display: "flex", alignItems: "center", gap: 8 }}>
                <FaFileAlt style={{ fontSize: 12, color: runTests && isTestsAvailable ? "#166534" : "#64748b", flexShrink: 0 }} />
                <span>Run Unit Test Suite</span>
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2, lineHeight: 1.3 }}>
                {getTestsSubtitle()}
              </div>
            </div>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 10,
                fontWeight: 700,
                padding: "3px 10px",
                borderRadius: 6,
                background: runTests && isTestsAvailable ? "#dcfce7" : "#f1f5f9",
                color: runTests && isTestsAvailable ? "#166534" : "#64748b",
                flexShrink: 0,
              }}
            >
              RECOMMENDED
            </span>
          </div>

          {/* 4. Functional Testing */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "14px 18px",
              borderRadius: 12,
              border: `2px solid ${runFunctionalTests ? "#6366f1" : "#e2e8f0"}`,
              background: runFunctionalTests ? "#eef2ff" : "#f8fafc",
              cursor: "pointer",
              transition: "all 0.15s ease",
              minHeight: 88,
            }}
            onClick={() => setRunFunctionalTests(!runFunctionalTests)}
          >
            <input
              type="checkbox"
              checked={runFunctionalTests}
              onChange={(e) => {
                e.stopPropagation();
                setRunFunctionalTests(e.target.checked);
              }}
              style={{ width: 18, height: 18, accentColor: "#6366f1", cursor: "pointer", flexShrink: 0 }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: "#0f172a", display: "flex", alignItems: "center", gap: 8 }}>
                <FaFlask style={{ fontSize: 12, color: runFunctionalTests ? "#4338ca" : "#64748b", flexShrink: 0 }} />
                <span>Functional Testing</span>
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2, lineHeight: 1.3 }}>
                {runFunctionalTests
                  ? "Upload & run functional test scenarios from a document."
                  : "Functional testing disabled — document upload hidden."}
              </div>
            </div>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 10,
                fontWeight: 700,
                padding: "3px 10px",
                borderRadius: 6,
                background: runFunctionalTests ? "#e0e7ff" : "#f1f5f9",
                color: runFunctionalTests ? "#4338ca" : "#64748b",
                flexShrink: 0,
              }}
            >
              {runFunctionalTests ? "ENABLED" : "DISABLED"}
            </span>
          </div>
        </div>
      </div>

      {/* Existing Test Cases Section (Discovered Only - No Execution) */}
      <ExistingTestCasesPanel
        jobId={jobId}
        discoveredTests={discoveredTests}
        framework={existingFramework || "JUnit"}
        isRunning={false}
        isLoading={isLoadingDiscoveredTests}
        onSelectTest={(t: TestResult | TestSelectionItem) => {
          setTestDetailReport(buildTestDetailReport(t, "NOT_EXECUTED"));
          setShowTestDetailModal(true);
        }}
      />

      {/* Functional Testing Document Upload Section — only shown when enabled */}
      {runFunctionalTests && <FunctionalTestingDocumentCard jobId={jobId} />}

      {/* Test Validation Report Modal */}
      {showValidationReport && existingExecResult && (
        <ExistingTestValidationReport
          metrics={existingExecResult.metrics || {}}
          frameworkInfo={existingExecResult.framework_info}
          testResults={displayTestResults}
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
                {loading ? "Starting..." : "Continue Migration"}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      </div>

      <div style={styles.btnRow} className="modernization-nav-btn-row">
        <button style={styles.secondaryBtn} onClick={onBack}>{renderBackButtonLabel()}</button>
        <button
          style={{ ...styles.primaryBtn, opacity: loading ? 0.5 : 1 }}
          onClick={handleStartMigrationClick}
          disabled={loading}
        >
          {renderForwardButtonLabel(loading ? "Starting..." : "Start Migration")}
        </button>
      </div>
    </>
  );
}
