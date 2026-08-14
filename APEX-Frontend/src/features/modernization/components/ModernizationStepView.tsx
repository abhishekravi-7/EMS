import React, { useEffect, useState, useRef, useMemo, type Dispatch, type SetStateAction } from "react";
import {
  FaFileAlt,
  FaRocket,
  FaSearch,
  FaShieldAlt,
  FaVial,
  FaPlay,
  FaStop,
  FaSpinner,
  FaTerminal,
  FaCheckCircle,
  FaTimesCircle,
  FaExclamationTriangle,
  FaClock,
  FaBolt,
  FaStepForward,
  FaBullseye,
  FaList,
  FaFolder,
  FaBox,
  FaInfoCircle,
} from "react-icons/fa";
import {
  scanExistingTests,
  runExistingTests,
  getExistingTestsStatus,
  stopExistingTests,
  resetExistingTests,
  type ExistingTestStatusResponse,
} from "../services/existingTestService";
import { ExistingTestCasesPanel } from "./ExistingTestCasesPanel";
import { ExistingTestCoverage } from "./ExistingTestCoverage";
import { ExistingTestAnalytics } from "./ExistingTestAnalytics";
import { ExistingTestTable } from "./ExistingTestTable";
import { ExistingTestLogs } from "./ExistingTestLogs";
import { ExistingTestValidationReport } from "./ExistingTestValidationReport";
import { TestReportsModal } from "./TestReportsModal";
import { wizardStyles as styles } from "@/shared/components/wizard/wizardStyles";
import { renderWizardIconBadge, renderBackButtonLabel } from "@/shared/components/wizard";
import type { RepoAnalysis, RepoInfo } from "@/shared/types/domain";
import { getFileContent } from "@/features/discovery/services/discoveryService";
import { getLocalProjectFileContent } from "@/features/connect/services/connectService";
import {
  previewFunctionalTestScope,
  getToolRecommendations,
  type FunctionalTestScopePreview,
} from "../services/modernizationService";
import type { useModernizationState } from "../hooks/useModernizationState";

const LLM_PROVIDERS = [
  { value: "groq", label: "Groq (Recommended — Llama 3.3 70B Fast)" },
  { value: "huggingface", label: "Hugging Face (Free)" },
  { value: "ollama", label: "Ollama (Local)" },
  { value: "claude", label: "Claude (Paid)" },
  { value: "gpt-4", label: "OpenAI (GPT-4)" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "offline", label: "Offline (Template)" },
];


const getConfidenceColor = (percentage: number) => {
  if (percentage >= 80) return "#22c55e";
  if (percentage >= 60) return "#3b82f6";
  if (percentage >= 40) return "#f59e0b";
  return "#ef4444";
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
  repoUrl,
  currentToken,
  functionalTestToolMethod,
  setFunctionalTestToolMethod,
  functionalTestingTools,
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
    useLLMTests,
    setUseLLMTests,
    selectedLLMProvider,
    setSelectedLLMProvider,
    runSonar,
    setRunSonar,
    runFossa,
    setRunFossa,
  } = modernization;
  const { isLocalRepoRef, extractLocalRepoPath } = repoUtils;

  // --- Existing Test execution states replicated from Prova ---
  const [isRunningExisting, setIsRunningExisting] = useState(false);
  const [existingTotal, setExistingTotal] = useState<number | null>(null);
  const [existingFramework, setExistingFramework] = useState<string | null>(null);
  const [discoveredTests, setDiscoveredTests] = useState<any[]>([]);
  const [existingElapsedTime, setExistingElapsedTime] = useState(0);
  const [existingLogs, setExistingLogs] = useState<{ ts: string; msg: string; level: string }[]>([]);
  const [existingExecResult, setExistingExecResult] = useState<any | null>(null);
  const [showExistingLogs, setShowExistingLogs] = useState(false);
  const [showValidationReport, setShowValidationReport] = useState(false);
  const [validationFilter, setValidationFilter] = useState("ALL");
  const [validationSearch, setValidationSearch] = useState("");
  const [expandedFailures, setExpandedFailures] = useState<Record<number, boolean>>({});
  const [showTestDetailModal, setShowTestDetailModal] = useState(false);
  const [testDetailReport, setTestDetailReport] = useState<{
    name: string;
    suite: string;
    status: string;
    url?: string | null;
    type?: string;
    screenshotUrl?: string | null;
    videoUrl?: string | null;
    traceUrl?: string | null;
    apiEvidence?: any;
    error?: string | null;
    errorCode?: string | null;
  } | null>(null);

  const existingLogRef = useRef<HTMLDivElement | null>(null);
  const existingPollRef = useRef<any>(null);

  // Live timer for existing test execution / analysis
  useEffect(() => {
    let timer: any = null;
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

  const formatElapsedTime = (totalSecs: number) => {
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

  const activeTestResults = useMemo(() => {
    if (existingExecResult?.test_results && existingExecResult.test_results.length > 0 && !isRunningExisting) {
      return existingExecResult.test_results;
    }

    if (discoveredTests.length === 0) return [];

    const completedResults = existingExecResult?.test_results || [];
    const completedMap = new Map();
    completedResults.forEach((r: any) => {
      const key = `${r.suite || ""}:${r.test_name || ""}`;
      completedMap.set(key, r);
    });

    let foundRunning = false;
    return discoveredTests.map((t: any, idx: number) => {
      const testName = t.name || t.methodname || `testMethod${idx}`;
      const testSuite = t.classname || t.file?.split("/").pop() || "TestSuite";
      const key = `${testSuite}:${testName}`;

      if (completedMap.has(key)) {
        return completedMap.get(key);
      }

      if (isRunningExisting) {
        if (!foundRunning) {
          foundRunning = true;
          return {
            test_name: testName,
            suite: testSuite,
            status: "RUNNING",
            duration: "Running...",
            file: t.file || `${testSuite}.java`,
            type: t.type || existingFramework || "JUnit",
            failure_message: null,
          };
        } else {
          return {
            test_name: testName,
            suite: testSuite,
            status: "PENDING",
            duration: "--",
            file: t.file || `${testSuite}.java`,
            type: t.type || existingFramework || "JUnit",
            failure_message: null,
          };
        }
      }

      return {
        test_name: testName,
        suite: testSuite,
        status: "PENDING",
        duration: "--",
        file: t.file || `${testSuite}.java`,
        type: t.type || existingFramework || "JUnit",
        failure_message: null,
      };
    });
  }, [discoveredTests, existingExecResult, isRunningExisting, existingFramework]);

  // Auto-scroll live log box
  useEffect(() => {
    if (existingLogRef.current) {
      existingLogRef.current.scrollTop = existingLogRef.current.scrollHeight;
    }
  }, [existingLogs]);

  // Scan on mount or jobId changes
  useEffect(() => {
    if (!jobId) return;

    const loadState = async () => {
      try {
        const status = await getExistingTestsStatus(jobId).catch(() => null);
        if (status && status.status !== "IDLE" && status.status !== "STOPPED") {
          if (status.logs) setExistingLogs(status.logs);
          if (status.result) {
            setExistingExecResult(status.result);
            if (status.result.metrics?.total != null) setExistingTotal(status.result.metrics.total);
            if (status.result.metrics?.type) setExistingFramework(status.result.metrics.type);
          }
          if (status.status === "RUNNING" || status.status === "IN_PROGRESS") {
            setIsRunningExisting(true);
            setShowExistingLogs(true);
            if (existingPollRef.current) clearInterval(existingPollRef.current);
            existingPollRef.current = setInterval(async () => {
              try {
                const liveStatus = await getExistingTestsStatus(jobId);
                if (liveStatus.logs) setExistingLogs(liveStatus.logs);
                if (liveStatus.result) {
                  setExistingExecResult(liveStatus.result);
                  if (liveStatus.result.metrics?.total != null) setExistingTotal(liveStatus.result.metrics.total);
                  if (liveStatus.result.metrics?.type) setExistingFramework(liveStatus.result.metrics.type);
                }
                if (liveStatus.status === "COMPLETED" || liveStatus.status === "FAILED" || liveStatus.status === "ERROR" || liveStatus.status === "STOPPED") {
                  clearInterval(existingPollRef.current);
                  setIsRunningExisting(false);
                  setTimeout(() => setShowExistingLogs(false), 2000);
                }
              } catch (e) {
                console.error(e);
              }
            }, 800);
          } else {
            setIsRunningExisting(false);
            setShowExistingLogs(false);
          }
        } else {
          setExistingTotal(null);
          setExistingFramework(null);
          setExistingExecResult(null);
          setExistingLogs([]);
          setShowExistingLogs(false);
          setIsRunningExisting(false);
          if (existingPollRef.current) clearInterval(existingPollRef.current);
          
          scanExistingTests(jobId)
            .then(data => {
              const total = data.total ?? 0;
              setExistingTotal(total);
              setExistingFramework(data.framework || null);
              setDiscoveredTests(data.test_cases || []);
            })
            .catch(() => {
              setExistingTotal(0);
            });
        }
      } catch (err) {
        console.error("Failed to load existing tests status:", err);
      }
    };
    
    loadState();

    return () => {
      if (existingPollRef.current) clearInterval(existingPollRef.current);
    };
  }, [jobId]);

  const handleStopExistingTests = async () => {
    if (!jobId) return;
    try {
      await stopExistingTests(jobId);
      if (existingPollRef.current) clearInterval(existingPollRef.current);
      setIsRunningExisting(false);
      const finalStatus = await getExistingTestsStatus(jobId).catch(() => ({}) as any);
      if (finalStatus.logs) setExistingLogs(finalStatus.logs);
    } catch (err) {
      console.error('Failed to stop existing tests:', err);
    }
  };

  const handleRunExistingTests = async (selection: any[] = []) => {
    if (!jobId || isRunningExisting) return;

    setIsRunningExisting(true);
    setExistingExecResult(null);
    setExistingLogs([]);
    setShowExistingLogs(true);

    if (existingPollRef.current) clearInterval(existingPollRef.current);
    existingPollRef.current = setInterval(async () => {
      try {
        const status = await getExistingTestsStatus(jobId);
        if (status.logs) {
          setExistingLogs(status.logs);
        }
        if (status.result) {
          setExistingExecResult(status.result);
          if (status.result.metrics?.total != null)
            setExistingTotal(status.result.metrics.total);
          if (status.result.metrics?.type)
            setExistingFramework(status.result.metrics.type);
        }
        if (
          status.status === "COMPLETED" ||
          status.status === "FAILED" ||
          status.status === "ERROR" ||
          status.status === "STOPPED"
        ) {
          clearInterval(existingPollRef.current);
          setIsRunningExisting(false);
        }
      } catch (err) {
        console.error(err);
      }
    }, 800);

    try {
      const res = await runExistingTests(jobId, selection);
      if (res?.status === 'RUNNING' || res?.started === true) {
        return;
      }
      clearInterval(existingPollRef.current);
      const finalStatus = await getExistingTestsStatus(jobId).catch(() => ({}) as any);
      if (finalStatus.logs) setExistingLogs(finalStatus.logs);
      if (res?.metrics?.total != null) setExistingTotal(res.metrics.total);
      if (res?.metrics?.type) setExistingFramework(res.metrics.type);
      setTimeout(() => setShowExistingLogs(false), 2000);
      if (res) {
        setExistingExecResult(res);
      }
    } catch (err) {
      clearInterval(existingPollRef.current);
      console.error('Failed to execute existing tests:', err);
      setShowExistingLogs(false);
      setIsRunningExisting(false);
    }
  };

  const [selectedTestToolFilter, setSelectedTestToolFilter] = useState<string | null>(null);
  const [viewingTestFile, setViewingTestFile] = useState<{ name: string; path: string; content: string } | null>(null);
  const [testFileLoading, setTestFileLoading] = useState(false);
  const [hoveredToolId, setHoveredToolId] = useState<string | null>(null);
  const [toolRecommendations, setToolRecommendations] = useState<Record<string, { passage: string }> | null>(null);
  const [toolRecsLoading, setToolRecsLoading] = useState(false);
  const [scopePreview, setScopePreview] = useState<FunctionalTestScopePreview | null>(null);
  const [scopePreviewLoading, setScopePreviewLoading] = useState(false);
  const [scopePreviewError, setScopePreviewError] = useState<string | null>(null);


  // Fetch LLM-generated tool recommendation passages once when this step mounts
  useEffect(() => {
    if (!repoAnalysis) return;
    const toolIds = functionalTestingTools.map((t) => t.id);
    if (toolIds.length === 0) return;
    setToolRecsLoading(true);
    const projectName = repoAnalysis.name || repoAnalysis.full_name || "Project";
    const allFiles = (repoAnalysis?.all_files ?? []).map((f) =>
      typeof f === "string" ? f : (f?.path || "")
    );
    const depArtifacts = (repoAnalysis.dependencies ?? []).map((d) => d.artifact_id || "");
    const lightContext = {
      build_tool: repoAnalysis.build_tool,
      detected_frameworks: repoAnalysis.detected_frameworks,
      api_endpoints: repoAnalysis.api_endpoints,
      dependencies: repoAnalysis.dependencies?.slice(0, 30),
      all_file_names: allFiles.slice(0, 200),
      dep_artifacts: depArtifacts.slice(0, 20),
    };
    getToolRecommendations(projectName, lightContext, toolIds)
      .then((res) => {
        if (res?.recommendations) setToolRecommendations(res.recommendations);
      })
      .catch(() => {
        setToolRecommendations({});
      })
      .finally(() => setToolRecsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-fetch scope preview when this step mounts, so tables show content immediately
  useEffect(() => {
    if (scopePreview || scopePreviewLoading || !repoAnalysis) return;
    const autoFetch = async () => {
      setScopePreviewLoading(true);
      try {
        const endpoints = repoAnalysis?.api_endpoints || [];
        const uiRoutes = repoAnalysis?.uiRoutes || [];
        const pageData = repoAnalysis?.page_data || {};
        const result = await previewFunctionalTestScope(
          selectedRepo?.name || repoUrl.split("/").pop()?.replace(".git", "") || "Project",
          endpoints, uiRoutes, pageData,
          functionalTestToolMethod.length > 0 ? functionalTestToolMethod : [],
          repoUrl, currentToken || "",
        );
        setScopePreview(result);
      } catch {
        // Silent fail — user can still click Download to retry
      } finally {
        setScopePreviewLoading(false);
      }
    };
    autoFetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const apiEndpointCount = repoAnalysis?.api_endpoints?.length ?? 0;
  void apiEndpointCount;

  return (
    <div style={styles.card}>
      <div style={styles.stepHeader}>
        {renderWizardIconBadge(<FaRocket />, "#f59e0b", "xl")}
        <div>
          <h2 style={styles.title}>Build Modernization &amp; Migration</h2>
          <p style={styles.subtitle}>Execute the upgrade using automation tools and refactor legacy components</p>
        </div>
      </div>

      {/* ── CI / CD & Quality Gates ─────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20, marginTop: 28, marginBottom: 32 }}>
        <div style={{
          background: "#fff",
          borderRadius: 14,
          border: "1px solid #e2e8f0",
          padding: "24px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 8,
          position: "relative",
        }}>
          <span style={{
            position: "absolute", top: 12, right: 14,
            fontSize: 9, fontWeight: 700, color: "#94a3b8",
            background: "#f1f5f9", padding: "3px 8px", borderRadius: 6,
            textTransform: "uppercase", letterSpacing: 0.5,
          }}>Coming Soon</span>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 18, color: "#0f172a" }}>⚙️</span>
            <span style={{ fontWeight: 700, fontSize: 15, color: "#0f172a" }}>Continuous Integration</span>
          </div>
          <span style={{ fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>
            Automated build and artifact generation pipeline.
          </span>
        </div>

        <div style={{
          background: "#fff",
          borderRadius: 14,
          border: "1px solid #e2e8f0",
          padding: "24px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 8,
          position: "relative",
        }}>
          <span style={{
            position: "absolute", top: 12, right: 14,
            fontSize: 9, fontWeight: 700, color: "#94a3b8",
            background: "#f1f5f9", padding: "3px 8px", borderRadius: 6,
            textTransform: "uppercase", letterSpacing: 0.5,
          }}>Coming Soon</span>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 18, color: "#0f172a" }}>🚀</span>
            <span style={{ fontWeight: 700, fontSize: 15, color: "#0f172a" }}>Continuous Delivery</span>
          </div>
          <span style={{ fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>
            Automated deployment across staging environments.
          </span>
        </div>

        <div style={{
          background: "#f8fafc",
          borderRadius: 14,
          border: "1px solid #e2e8f0",
          padding: "24px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 18, color: "#64748b" }}>🛡️</span>
              <span style={{ fontWeight: 700, fontSize: 15, color: "#64748b" }}>Quality Gates</span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <div
              onClick={() => setRunSonar(!runSonar)}
              style={{
                flex: 1, padding: "10px 12px", borderRadius: 10,
                border: `2px solid ${runSonar ? "#22c55e" : "#cbd5e1"}`,
                background: runSonar ? "#f0fdf4" : "#f1f5f9",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 12, color: runSonar ? "#166534" : "#64748b", marginBottom: 2 }}>
                <FaSearch style={{ marginRight: 6, fontSize: 10, color: runSonar ? "#166534" : "#94a3b8" }} />
                SonarQube
              </div>
              <div style={{ fontSize: 10, color: runSonar ? "#15803d" : "#94a3b8", lineHeight: 1.4 }}>
                Static analysis for bug and vulnerability detection.
              </div>
              <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: runSonar ? "#22c55e" : "#94a3b8" }} />
                <span style={{ fontSize: 10, fontWeight: 700, color: runSonar ? "#166534" : "#94a3b8" }}>
                  {runSonar ? "ACTIVE" : "INACTIVE"}
                </span>
              </div>
            </div>
            <div
              onClick={() => setRunFossa(!runFossa)}
              style={{
                flex: 1, padding: "10px 12px", borderRadius: 10,
                border: `2px solid ${runFossa ? "#22c55e" : "#cbd5e1"}`,
                background: runFossa ? "#f0fdf4" : "#f1f5f9",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 12, color: runFossa ? "#166534" : "#64748b", marginBottom: 2 }}>
                <FaShieldAlt style={{ marginRight: 6, fontSize: 10, color: runFossa ? "#166534" : "#94a3b8" }} />
                FOSSA
              </div>
              <div style={{ fontSize: 10, color: runFossa ? "#15803d" : "#94a3b8", lineHeight: 1.4 }}>
                Open-source license compliance and security.
              </div>
              <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: runFossa ? "#22c55e" : "#94a3b8" }} />
                <span style={{ fontSize: 10, fontWeight: 700, color: runFossa ? "#166534" : "#94a3b8" }}>
                  {runFossa ? "ACTIVE" : "INACTIVE"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Test Suites Selection ───────────────────────────── */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
          <FaVial style={{ fontSize: 18, color: "#0f172a" }} />
          <span style={{ fontWeight: 800, fontSize: 18, color: "#0f172a" }}>Test Suites Selection</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 24 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 12,
            padding: "14px 18px", borderRadius: 12,
            border: `2px solid ${runTests ? "#22c55e" : "#e2e8f0"}`,
            background: runTests ? "#f0fdf4" : "#fff",
            cursor: "pointer", transition: "all 0.15s ease",
          }}
            onClick={() => setRunTests(!runTests)}
          >
            <input
              type="checkbox" checked={runTests}
              onChange={(e) => setRunTests(e.target.checked)}
              style={{ width: 18, height: 18, accentColor: "#22c55e", cursor: "pointer" }}
            />
            <div>
              <div style={{ fontWeight: 700, fontSize: 14, color: "#0f172a" }}>Run Unit Test Suite</div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                Execute automated unit tests after migration to verify functionality.
              </div>
            </div>
            <span style={{
              marginLeft: "auto", fontSize: 10, fontWeight: 700,
              padding: "3px 10px", borderRadius: 6,
              background: "#dcfce7", color: "#166534",
            }}>RECOMMENDED</span>
          </div>

          {runTests && (
            <div style={{
              padding: "14px 18px", borderRadius: 12,
              border: "1px solid #e2e8f0", background: "#f8fafc",
            }}>
              <label style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <input
                  type="checkbox" checked={useLLMTests}
                  onChange={(e) => setUseLLMTests(e.target.checked)}
                  style={{ width: 16, height: 16, accentColor: "#3b82f6" }}
                />
                <span style={{ fontWeight: 600, fontSize: 13, color: "#1e293b" }}>Use LLM Test Generator</span>
              </label>
              <div style={{ maxWidth: 320 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 4, display: "block" }}>LLM Provider</label>
                <select
                  style={{ ...styles.select, width: "100%", backgroundColor: useLLMTests ? "#fff" : "#f1f5f9" }}
                  value={selectedLLMProvider}
                  onChange={(e) => setSelectedLLMProvider(e.target.value)}
                  disabled={!useLLMTests}
                >
                  {LLM_PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Existing Test Cases Browser (only before execution) */}
        {discoveredTests.length > 0 && !existingExecResult && !isRunningExisting && (
          <ExistingTestCasesPanel
            jobId={jobId}
            discoveredTests={discoveredTests}
            framework={existingFramework || "JUnit"}
            onRunAll={() => handleRunExistingTests()}
            onRunSelected={() => handleRunExistingTests()}
            isRunning={isRunningExisting}
          />
        )}

        {/* RUNNING STATE: SHOW ONLY EXECUTION PROGRESS & LIVE EXECUTION LOGS */}
        {isRunningExisting && (
          <div style={{ display: "flex", flexDirection: "column", gap: 24, marginTop: 24 }}>
            {/* Header + Progress Bar */}
            <div style={{
              padding: "20px 24px",
              borderRadius: 14,
              border: "1px solid #e2e8f0",
              background: "#fff",
            }}>
              <h3 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: "0 0 12px 0" }}>
                Existing Test Cases
              </h3>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#475569", display: "flex", alignItems: "center", gap: 6 }}>
                  <FaSpinner className="animate-spin" style={{ color: "#2563eb" }} /> Test execution in progress ({formatElapsedTime(existingElapsedTime)})...
                </span>
                <span style={{ fontSize: 11, fontFamily: "monospace", fontWeight: 700, color: "#64748b" }}>
                  {executedTestLogsCount} / {existingTotal || discoveredTests.length} ({testProgressPercent}%)
                </span>
              </div>
              <div style={{ width: "100%", height: 8, background: "#e2e8f0", borderRadius: 999, overflow: "hidden" }}>
                <div style={{ height: "100%", background: "linear-gradient(90deg, #2563eb, #3b82f6)", width: `${testProgressPercent}%`, transition: "width 0.3s ease" }} />
              </div>
            </div>

            {/* LIVE EXECUTION LOGS */}
            <ExistingTestLogs logs={existingLogs} />
          </div>
        )}

        {/* COMPLETED STATE: SHOW ANALYTICS, COVERAGE, AND VALIDATION REPORT */}
        {!isRunningExisting && existingExecResult && (
          <div style={{ display: "flex", flexDirection: "column", gap: 24, marginTop: 24 }}>
            {/* 1. TOP ANALYTICS AREA (Suite Composition & Risk Coverage) */}
            <ExistingTestAnalytics
              metrics={existingExecResult.metrics || {}}
              fileBreakdown={existingExecResult.file_breakdown || []}
              frameworkInfo={existingExecResult.framework_info}
            />

            {/* 2. EXISTING TEST COVERAGE (8 Metric Cards) */}
            <ExistingTestCoverage
              metrics={existingExecResult.metrics || {}}
              frameworkInfo={existingExecResult.framework_info}
              onRunAll={() => handleRunExistingTests()}
              onOpenReport={() => setShowValidationReport(true)}
            />

            {/* 3. EXISTING TESTS VALIDATION REPORT CARD */}
            {existingExecResult.test_results && existingExecResult.test_results.length > 0 && (
              <div style={{
                background: "#fff",
                borderRadius: 20,
                border: "1px solid #e2e8f0",
                padding: "24px",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)"
              }}>
                <ExistingTestTable
                  title="Existing Tests Validation Report"
                  testResults={existingExecResult.test_results}
                  fileBreakdown={existingExecResult.file_breakdown || []}
                  frameworkInfo={existingExecResult.framework_info}
                  logs={existingLogs}
                  onSelectTest={(t: any) => {
                    const scUrl = t.screenshot_url || t.screenshotUrl || t.evidence?.screenshotUrl || null;
                    const vidUrl = t.video_url || t.videoUrl || t.evidence?.videoUrl || null;
                    setTestDetailReport({
                      testId: t.test_id || t.testId || `${t.suite}#${t.test_name}`,
                      executionId: t.execution_id || t.executionId || jobId,
                      title: t.test_name || t.name || t.title,
                      name: t.test_name || t.name || t.title,
                      spec: t.suite || t.spec || t.file,
                      suite: t.suite || t.spec || t.file,
                      status: t.status,
                      duration: t.duration || "0.0s",
                      file: t.file,
                      url: t.report_url,
                      type: t.type || "JUnit",
                      testType: t.test_type || t.testType || (t.category === "UI" ? "UI" : t.category === "API" ? "API" : "UNIT"),
                      framework: t.framework || existingExecResult?.framework_info?.build_tool || existingExecResult?.framework_info?.detected_framework || "JUnit",
                      screenshotUrl: scUrl,
                      videoUrl: vidUrl,
                      evidence: t.evidence || {
                        screenshotAvailable: !!scUrl,
                        screenshotUrl: scUrl,
                        videoAvailable: !!vidUrl,
                        videoUrl: vidUrl,
                      },
                      traceUrl: t.trace_url,
                      apiEvidence: t.api_evidence,
                      error: t.failure_message || t.details?.error || t.error || null,
                      errorCode: t.status === "FAILED" ? "TEST_FAILED" : t.status === "ERROR" ? "BUILD_ERROR" : t.status === "NOT_EXECUTED" ? "NOT_EXECUTED" : undefined,
                      stackTrace: t.stack_trace || t.details?.stackTrace || t.stackTrace || null,
                      stdout: t.stdout || t.details?.stdout || null,
                      stderr: t.stderr || t.details?.stderr || null,
                    });
                    setShowTestDetailModal(true);
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/*
        <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: 24 }}>
          <p style={{
            fontSize: 13, color: "#64748b", marginBottom: 20,
            textAlign: "center", textTransform: "uppercase", letterSpacing: 1.2, fontWeight: 600,
          }}>
            Select Functional Testing Tool
          </p>

          {repoAnalysis && (repoAnalysis.test_file_count ?? 0) > 0 && (
            <div style={{ marginBottom: 18 }}>
              <div style={{
                display: "flex", alignItems: "center", gap: 10, marginBottom: 12,
              }}>
                <span style={{ fontSize: 16 }}>🧪</span>
                <span style={{ fontWeight: 700, fontSize: 14, color: "#0f172a" }}>
                  Existing Test Files ({repoAnalysis.test_file_count})
                </span>
              </div>
              <div style={{
                display: "flex", gap: 10, flexWrap: "wrap",
              }}>
                {(repoAnalysis.test_file_breakdown ?? []).map((cat) => {
                  const iconMap: Record<string, string> = {
                    MOCK_MVC: "🌱", REST_ASSURED: "🔗",
                    JUNIT5: "🧪", JUNIT4: "🧪", JUNIT: "🧪",
                    SPRING_BOOT_TEST: "📦",
                    PLAYWRIGHT: "🎭", SELENIUM: "🌐",
                    CYPRESS: "🟢", E2E: "📁",
                    TEST_FRAMEWORK: "🧪", FUNCTIONAL_TEST: "📋",
                  };
                  const colorMap: Record<string, string> = {
                    MOCK_MVC: "#3b82f6", REST_ASSURED: "#f59e0b",
                    JUNIT5: "#8b5cf6", JUNIT4: "#8b5cf6", JUNIT: "#8b5cf6",
                    SPRING_BOOT_TEST: "#06b6d4",
                    PLAYWRIGHT: "#22c55e", SELENIUM: "#f97316",
                    CYPRESS: "#14b8a6", E2E: "#3b82f6",
                    TEST_FRAMEWORK: "#8b5cf6", FUNCTIONAL_TEST: "#94a3b8",
                  };
                  const icon = iconMap[cat.tool] || "📄";
                  const color = colorMap[cat.tool] || "#64748b";
                  return (
                    <div key={cat.tool} onClick={() => setSelectedTestToolFilter(cat.tool)} style={{
                      display: "flex", alignItems: "center", gap: 8,
                      padding: "8px 14px", borderRadius: 10,
                      background: `${color}0d`,
                      border: `1px solid ${color}30`,
                      cursor: "pointer",
                      transition: "box-shadow 0.15s, transform 0.15s",
                    }}
                      onMouseEnter={(e) => { e.currentTarget.style.boxShadow = `0 0 0 2px ${color}40`; e.currentTarget.style.transform = "translateY(-1px)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.transform = "none"; }}
                    >
                      <span style={{ fontSize: 16 }}>{icon}</span>
                      <span style={{ fontWeight: 700, fontSize: 16, color }}>{cat.count}</span>
                      <span style={{ fontSize: 12, color: "#475569", fontWeight: 500 }}>{cat.label}</span>
                      <span style={{
                        fontSize: 9, textTransform: "uppercase", fontWeight: 600,
                        padding: "1px 5px", borderRadius: 3,
                        background: cat.type === "functional" ? "#f0fdf4" : "#eff6ff",
                        color: cat.type === "functional" ? "#15803d" : "#1d4ed8",
                        marginLeft: 2,
                      }}>
                        {cat.type === "functional" ? "E2E" : "Unit"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {selectedTestToolFilter && (
            <div style={{
              position: "fixed", inset: 0, zIndex: 10000,
              background: "rgba(15,23,42,0.6)", backdropFilter: "blur(4px)",
              display: "flex", alignItems: "center", justifyContent: "center",
              padding: 20,
            }} onClick={() => setSelectedTestToolFilter(null)}>
              <div style={{
                background: "#fff", borderRadius: 14, maxWidth: 700, width: "100%",
                maxHeight: "80vh", display: "flex", flexDirection: "column",
                boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
              }} onClick={(e) => e.stopPropagation()}>
                <div style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "16px 20px", borderBottom: "1px solid #e2e8f0",
                  background: "linear-gradient(135deg, #0f172a, #1e293b)",
                  borderRadius: "14px 14px 0 0",
                }}>
                  <span style={{ fontWeight: 700, fontSize: 15, color: "#fff" }}>
                    🧪 {repoAnalysis?.test_file_breakdown?.find(c => c.tool === selectedTestToolFilter)?.label ?? selectedTestToolFilter} Files
                  </span>
                  <button onClick={() => setSelectedTestToolFilter(null)} style={{
                    background: "rgba(255,255,255,0.15)", border: "none", color: "#fff",
                    width: 30, height: 30, borderRadius: 8, cursor: "pointer",
                    fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center",
                  }}>✕</button>
                </div>
                <div style={{ overflow: "auto", padding: 12, flex: 1 }}>
                  {(() => {
                    const cat = repoAnalysis?.test_file_breakdown?.find(c => c.tool === selectedTestToolFilter);
                    const filePaths = repoAnalysis?.test_file_list
                      ? repoAnalysis.test_file_list.filter(f => f.tool === selectedTestToolFilter).map(f => f.path)
                      : (cat?.files ?? []);
                    return filePaths.length > 0 ? filePaths.map((fp, i) => (
                      <div key={i} onClick={async () => {
                        setTestFileLoading(true);
                        setViewingTestFile({ name: fp.split("/").pop() || fp, path: fp, content: "" });
                        try {
                          const repoUrlValue = selectedRepo?.url ?? "";
                          const resp = isLocalRepoRef(repoUrlValue)
                            ? await getLocalProjectFileContent(extractLocalRepoPath(repoUrlValue), fp)
                            : await getFileContent(repoUrlValue, fp, currentToken);
                          setViewingTestFile((prev) => prev ? { ...prev, content: resp.content } : null);
                        } catch {
                          setViewingTestFile((prev) => prev ? { ...prev, content: "// Error loading file" } : null);
                        } finally {
                          setTestFileLoading(false);
                        }
                      }} style={{
                        display: "flex", alignItems: "center", gap: 10,
                        padding: "10px 14px", borderRadius: 8, cursor: "pointer",
                        border: "1px solid #e2e8f0", marginBottom: 6,
                        transition: "background 0.1s",
                      }}
                        onMouseEnter={(e) => e.currentTarget.style.background = "#f1f5f9"}
                        onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                      >
                        <span style={{ fontSize: 14 }}>📄</span>
                        <span style={{ fontSize: 13, color: "#0f172a", flex: 1, fontFamily: "monospace" }}>{fp}</span>
                        <span style={{ fontSize: 11, color: "#64748b" }}>Click to view</span>
                      </div>
                    )) : <p style={{ textAlign: "center", color: "#94a3b8", padding: 20, fontSize: 13 }}>No files listed</p>;
                  })()}
                </div>
              </div>
            </div>
          )}
          {viewingTestFile && (
            <div style={{
              position: "fixed", inset: 0, zIndex: 10001,
              background: "rgba(15,23,42,0.7)", backdropFilter: "blur(4px)",
              display: "flex", alignItems: "center", justifyContent: "center",
              padding: 20,
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
            </div>
          )}

          <div style={{
            display: "grid",
            gridTemplateColumns: `repeat(${Math.min(functionalTestingTools.length || 1, 5)}, 1fr)`,
            gap: 16,
          }}>
            {functionalTestingTools.map((tool) => {
              const isSelected = functionalTestToolMethod.includes(tool.id);
              const isHovered = hoveredToolId === tool.id;
              const confidenceColor = getConfidenceColor(tool.confidence);
              const circleColor = isSelected ? "#2563eb" : isHovered ? confidenceColor : "#cbd5e1";
              void circleColor;

              const toggleTool = (id: string) => {
                setFunctionalTestToolMethod(prev =>
                  prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
                );
              };

              return (
                <div
                  key={tool.id}
                  onClick={() => toggleTool(tool.id)}
                  onMouseEnter={() => setHoveredToolId(tool.id)}
                  onMouseLeave={() => setHoveredToolId(null)}
                  style={{
                    background: isSelected
                      ? "linear-gradient(180deg, #eff6ff 0%, #fff 100%)"
                      : isHovered
                        ? "linear-gradient(180deg, #f8fafc 0%, #fff 100%)"
                        : "#fff",
                    borderRadius: 14,
                    border: `2px solid ${isSelected ? "#2563eb" : isHovered ? confidenceColor + "66" : "#e2e8f0"}`,
                    padding: "22px 16px 16px",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    textAlign: "center",
                    cursor: "pointer",
                    transition: "all 0.35s cubic-bezier(0.4,0,0.2,1)",
                    transform: isSelected
                      ? "translateY(-6px) scale(1.02)"
                      : isHovered
                        ? "translateY(-4px) scale(1.01)"
                        : "translateY(0) scale(1)",
                    boxShadow: isSelected
                      ? "0 8px 28px rgba(37,99,235,0.18), 0 2px 8px rgba(37,99,235,0.08)"
                      : isHovered
                        ? `0 8px 24px ${confidenceColor}22, 0 2px 8px rgba(0,0,0,0.06)`
                        : "0 1px 3px rgba(0,0,0,0.06)",
                  }}
                >
                  <div style={{
                    width: 44, height: 44, borderRadius: 12,
                    background: isSelected ? "#dbeafe" : isHovered ? `${confidenceColor}15` : "#f1f5f9",
                    display: "flex",
                    alignItems: "center", justifyContent: "center",
                    marginBottom: 12, fontSize: 20, color: "#475569",
                    transition: "all 0.3s ease",
                    transform: isHovered ? "scale(1.1)" : "scale(1)",
                  }}>
                    {tool.id === "PLAYWRIGHT" && "🎭"}
                    {tool.id === "REST_ASSURED" && "🔗"}
                    {tool.id === "MOCK_MVC" && "🌱"}
                    {tool.id === "SELENIUM" && "🌐"}
                    {tool.id === "SCHEMATHESIS" && "📋"}
                  </div>

                  <h4 style={{
                    fontWeight: 700, fontSize: 13, color: "#0f172a", marginBottom: 6, lineHeight: 1.3,
                    transition: "color 0.25s ease",
                  }}>
                    {tool.name}
                  </h4>

                  <p style={{
                    fontSize: 11, color: "#64748b", lineHeight: 1.5, marginBottom: 14, minHeight: 44,
                    transition: "color 0.25s ease",
                  }}>
                    {tool.description}
                  </p>

                  {toolRecsLoading && !toolRecommendations && (
                    <div style={{ fontSize: 10, color: "#94a3b8", textAlign: "center", marginBottom: 8 }}>
                      Generating recommendation...
                    </div>
                  )}
                  {toolRecommendations?.[tool.id]?.passage && (
                    <div style={{
                      fontSize: 10, color: "#475569", lineHeight: 1.5, marginBottom: 10, padding: "6px 8px",
                      background: "#f8fafc", borderRadius: 6, borderLeft: "3px solid #3b82f6",
                      textAlign: "left",
                    }}>
                      {toolRecommendations[tool.id].passage}
                    </div>
                  )}

                  {(() => {
                    const toolAliases: Record<string, string[]> = {
                      PLAYWRIGHT: ["PLAYWRIGHT", "E2E", "CYPRESS", "TEST_FRAMEWORK", "FUNCTIONAL_TEST"],
                      SELENIUM: ["SELENIUM"],
                      MOCK_MVC: ["MOCK_MVC"],
                      REST_ASSURED: ["REST_ASSURED"],
                      SCHEMATHESIS: ["SCHEMATHESIS"],
                    };
                    const aliases = toolAliases[tool.id] || [tool.id];
                    const hasExisting = repoAnalysis?.test_file_breakdown?.some(b => aliases.includes(b.tool) && b.count > 0);
                    return isSelected && hasExisting ? (
                      <div style={{
                        fontSize: 9, color: "#b45309", lineHeight: 1.4, marginBottom: 8, padding: "5px 7px",
                        background: "#fffbeb", borderRadius: 5, border: "1px solid #fde68a",
                        textAlign: "left",
                      }}>
                        ⚠️ Test files already exist — only validation will run
                      </div>
                    ) : null;
                  })()}

                  <button
                    style={{
                      marginTop: 14, width: "100%", padding: "9px 0",
                      borderRadius: 8, fontWeight: 700, fontSize: 12,
                      border: "none",
                      background: isSelected
                        ? "#22c55e"
                        : isHovered
                          ? `${confidenceColor}18`
                          : "#fff",
                      color: isSelected ? "#fff" : isHovered ? confidenceColor : "#64748b",
                      boxShadow: isSelected
                        ? "0 2px 8px rgba(34,197,94,0.25)"
                        : `inset 0 0 0 1.5px ${isHovered ? confidenceColor + "44" : "#e2e8f0"}`,
                      cursor: "pointer",
                      transition: "all 0.3s cubic-bezier(0.4,0,0.2,1)",
                      transform: isHovered && !isSelected ? "scale(1.04)" : "scale(1)",
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleTool(tool.id);
                    }}
                  >
                    {isSelected ? "✓ Selected" : "Select"}
                  </button>
                </div>
              );
            })}
          </div>

          {functionalTestToolMethod.length > 0 && (
            <div style={{ textAlign: "center", marginTop: 16 }}>
              <button
                onClick={() => setFunctionalTestToolMethod([])}
                style={{
                  background: "none", border: "none",
                  color: "#3b82f6", fontSize: 12, fontWeight: 600,
                  cursor: "pointer", textDecoration: "underline",
                }}
              >
                Reset to Auto Recommendation
              </button>
            </div>
          )}

          {(() => {
            const toolAliases: Record<string, string[]> = {
              PLAYWRIGHT: ["PLAYWRIGHT", "E2E", "CYPRESS", "TEST_FRAMEWORK", "FUNCTIONAL_TEST"],
              SELENIUM: ["SELENIUM"],
              MOCK_MVC: ["MOCK_MVC"],
              REST_ASSURED: ["REST_ASSURED"],
              SCHEMATHESIS: ["SCHEMATHESIS"],
            };
            const toolsWithExistingTests = functionalTestToolMethod.filter(toolId => {
              const aliases = toolAliases[toolId] || [toolId];
              return repoAnalysis?.test_file_breakdown?.some(b => aliases.includes(b.tool) && b.count > 0);
            });
            if (toolsWithExistingTests.length === 0) return null;
            return (
              <div style={{
                marginTop: 12, padding: "10px 14px", borderRadius: 8,
                background: "#fffbeb", border: "1px solid #fde68a",
                display: "flex", alignItems: "flex-start", gap: 8,
              }}>
                <span style={{ fontSize: 14, flexShrink: 0 }}>⚠️</span>
                <div style={{ fontSize: 11, color: "#92400e", lineHeight: 1.5 }}>
                  <strong>Caution:</strong> The following selected tool(s) already have existing test files in the project. Test generation will be skipped and only file validation will be performed:{' '}
                  {toolsWithExistingTests.map((t, i) => (
                    <span key={t} style={{ fontWeight: 600 }}>
                      {i > 0 && ", "}{t}
                    </span>
                  ))}
                  .
                </div>
              </div>
            );
          })()}
        </div>
        */}
      </div>

      {repoAnalysis?.functional_test_files && repoAnalysis.functional_test_files.count > 0 && (
        <div style={{
          background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0",
          padding: "20px 24px", marginBottom: 24,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <span style={{ fontSize: 18 }}>📋</span>
            <span style={{ fontWeight: 700, fontSize: 15, color: "#0f172a" }}>
              Existing Functional Test Files ({repoAnalysis.functional_test_files.count})
            </span>
          </div>
          <div style={{
            display: "flex", flexDirection: "column", gap: 6,
            maxHeight: 300, overflowY: "auto",
          }}>
            {repoAnalysis.functional_test_files.files.map((file, idx) => {
              const toolColors: Record<string, { icon: string; color: string; label: string }> = {
                PLAYWRIGHT: { icon: "🎭", color: "#22c55e", label: "Playwright" },
                CYPRESS: { icon: "🟢", color: "#14b8a6", label: "Cypress" },
                SELENIUM: { icon: "🌐", color: "#f97316", label: "Selenium" },
                E2E: { icon: "📁", color: "#3b82f6", label: "E2E" },
                TEST_FRAMEWORK: { icon: "🧪", color: "#8b5cf6", label: "Test Framework" },
                FUNCTIONAL_TEST: { icon: "📋", color: "#94a3b8", label: "Functional Test" },
              };
              const tc = toolColors[file.tool] || { icon: "📄", color: "#64748b", label: file.tool };
              const depVersion = repoAnalysis?.dependencies?.find(d =>
                file.tool === "SELENIUM" && (d.artifact_id?.toLowerCase().includes("selenium") || d.group_id?.toLowerCase().includes("selenium"))
              )?.current_version;

              return (
                <div key={idx} onClick={async () => {
                  setTestFileLoading(true);
                  setViewingTestFile({ name: file.path.split("/").pop() || file.path, path: file.path, content: "" });
                  try {
                    const repoUrlValue = selectedRepo?.url ?? "";
                    const resp = isLocalRepoRef(repoUrlValue)
                      ? await getLocalProjectFileContent(extractLocalRepoPath(repoUrlValue), file.path)
                      : await getFileContent(repoUrlValue, file.path, currentToken);
                    setViewingTestFile((prev) => prev ? { ...prev, content: resp.content } : null);
                  } catch {
                    setViewingTestFile((prev) => prev ? { ...prev, content: "// Error loading file" } : null);
                  } finally {
                    setTestFileLoading(false);
                  }
                }} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "8px 12px", borderRadius: 8, cursor: "pointer",
                  background: idx % 2 === 0 ? "#f8fafc" : "#fff",
                  border: "1px solid #f1f5f9",
                  transition: "background 0.1s",
                }}
                  onMouseEnter={(e) => e.currentTarget.style.background = "#eef2ff"}
                  onMouseLeave={(e) => e.currentTarget.style.background = idx % 2 === 0 ? "#f8fafc" : "#fff"}
                >
                  <span style={{ fontSize: 14 }}>{tc.icon}</span>
                  <span style={{
                    fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                    padding: "2px 6px", borderRadius: 4,
                    background: `${tc.color}18`, color: tc.color,
                    minWidth: 60, textAlign: "center",
                  }}>
                    {tc.label}
                  </span>
                  <code style={{
                    fontSize: 11, color: "#334155", fontFamily: "'JetBrains Mono', monospace",
                    flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {file.path}
                  </code>
                  <span style={{
                    fontSize: 10, color: "#94a3b8", fontFamily: "'JetBrains Mono', monospace",
                    minWidth: 40, textAlign: "right",
                  }}>
                    {depVersion || "-"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/*

      <div style={{
        background: "#fff",
        borderRadius: 14,
        border: "1px solid #e2e8f0",
        padding: "20px 24px",
        marginBottom: 24,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
          <FaFileAlt style={{ fontSize: 16, color: "#0f172a" }} />
          <span style={{ fontWeight: 700, fontSize: 15, color: "#0f172a" }}>Functional Test Scope Documents</span>
        </div>
        <p style={{ fontSize: 12, color: "#64748b", lineHeight: 1.6, marginBottom: 16 }}>
          Download a business-friendly overview of the test cases that will be generated and validated
          for your project. These documents describe the scope in clear business language for stakeholder review.
        </p>
        <div style={{
          display: "grid",
          gridTemplateColumns: hasUI ? "1fr 1fr" : "1fr",
          gap: 16,
          marginTop: 4,
        }}>
          {hasUI && (
          <div style={{
            background: "#fff",
            borderRadius: 12,
            border: "1px solid #e2e8f0",
            overflow: "hidden",
          }}>
            <div style={{
              padding: "10px 14px",
              fontWeight: 700,
              fontSize: 13,
              color: "#0f172a",
              borderBottom: "1px solid #e2e8f0",
              background: "#f1f5f9",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}>
              <span style={{ fontSize: 14 }}>🖥️</span> UI Test Cases
              <button
                disabled={scopePreviewLoading}
                onClick={async () => {
                  if (scopePreviewLoading) return;
                  try {
                    setScopePreviewLoading(true);
                    setScopePreviewError(null);
                    const endpoints = repoAnalysis?.api_endpoints || [];
                    const uiRoutes = repoAnalysis?.uiRoutes || [];
                    const pageData = repoAnalysis?.page_data || {};
                    const result = await previewFunctionalTestScope(
                      selectedRepo?.name || repoUrl.split("/").pop()?.replace(".git", "") || "Project",
                      endpoints, uiRoutes, pageData,
                      functionalTestToolMethod.length > 0 ? functionalTestToolMethod : [],
                      repoUrl, currentToken || "",
                    );
                    const blob = new Blob([result.uiScopeHtml], { type: "text/html" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `ui-test-scope-${(selectedRepo?.name || "project").replace(/[^a-zA-Z0-9_-]/g, "-").toLowerCase()}.html`;
                    a.click();
                    URL.revokeObjectURL(url);
                    setScopePreview(result);
                  } catch (err) {
                    setScopePreviewError(err instanceof Error ? err.message : "Failed to generate scope document");
                  } finally {
                    setScopePreviewLoading(false);
                  }
                }}
                style={{
                  marginLeft: "auto",
                  padding: "3px 10px",
                  borderRadius: 6,
                  fontWeight: 600,
                  fontSize: 10,
                  border: "none",
                  background: scopePreview ? "#2563eb" : "#e2e8f0",
                  color: scopePreview ? "#fff" : "#94a3b8",
                  cursor: scopePreviewLoading ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                {scopePreviewLoading ? "⏳" : "📄"} Download
              </button>
            </div>
            <div style={{ maxHeight: 260, overflowY: "auto" }}>
              {scopePreviewLoading && !scopePreview ? (
                <div style={{ padding: "20px 8px", textAlign: "center", color: "#94a3b8", fontSize: 11 }}>
                  ⏳ Analyzing UI pages...
                </div>
              ) : scopePreview?.uiTestCases?.length ? (
                scopePreview.uiTestCases.slice(0, 20).map((tc) => (
                  <div key={`ui-${tc.id}`} style={{
                    padding: "10px 14px",
                    borderBottom: "1px solid #e8edf2",
                    fontSize: 12,
                    lineHeight: 1.7,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span style={{ color: "#94a3b8", fontSize: 10, fontWeight: 600, minWidth: 20 }}>#{tc.id}</span>
                      <code style={{ fontSize: 11, color: "#1e293b", background: "#f1f5f9", padding: "1px 6px", borderRadius: 3 }}>{tc.route}</code>
                      <span style={{
                        fontSize: 10, fontWeight: 600, padding: "1px 6px", borderRadius: 3,
                        background: tc.type === "SPA" || tc.type === "Angular" ? "#dbeafe" : "#f1f5f9",
                        color: tc.type === "SPA" || tc.type === "Angular" ? "#1d4ed8" : "#64748b",
                      }}>{tc.type}</span>
                    </div>
                    <div style={{ color: "#0f172a", fontSize: 13, lineHeight: 1.7, marginBottom: 4 }}>{tc.scenario}</div>
                    <div style={{ display: "flex", gap: 12, fontSize: 11, color: "#64748b", flexWrap: "wrap" }}>
                      {tc.fields !== "Page load only" && <span>📋 {tc.fields}</span>}
                      {tc.actions !== "Navigate" && <span>▶️ {tc.actions}</span>}
                      {tc.hasTable && <span style={{ color: "#2563eb" }}>📊 Table</span>}
                      {!tc.hasForm && !tc.hasTable && <span>👁️ Page view</span>}
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ padding: "20px 8px", textAlign: "center", color: "#94a3b8", fontSize: 11 }}>
                  Click <strong>Download</strong> above to generate UI test cases
                </div>
              )}
            </div>
          </div>
          )}

          <div style={{
            background: "#fff",
            borderRadius: 12,
            border: "1px solid #e2e8f0",
            overflow: "hidden",
          }}>
            <div style={{
              padding: "10px 14px",
              fontWeight: 700,
              fontSize: 13,
              color: "#0f172a",
              borderBottom: "1px solid #e2e8f0",
              background: "#f1f5f9",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}>
              <span style={{ fontSize: 14 }}>🔌</span> API Test Cases
              <button
                disabled={scopePreviewLoading}
                onClick={async () => {
                  if (scopePreviewLoading) return;
                  try {
                    setScopePreviewLoading(true);
                    setScopePreviewError(null);
                    const endpoints = repoAnalysis?.api_endpoints || [];
                    const uiRoutes = repoAnalysis?.uiRoutes || [];
                    const pageData = repoAnalysis?.page_data || {};
                    const result = await previewFunctionalTestScope(
                      selectedRepo?.name || repoUrl.split("/").pop()?.replace(".git", "") || "Project",
                      endpoints, uiRoutes, pageData,
                      functionalTestToolMethod.length > 0 ? functionalTestToolMethod : [],
                      repoUrl, currentToken || "",
                    );
                    const blob = new Blob([result.apiScopeHtml], { type: "text/html" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `api-test-scope-${(selectedRepo?.name || "project").replace(/[^a-zA-Z0-9_-]/g, "-").toLowerCase()}.html`;
                    a.click();
                    URL.revokeObjectURL(url);
                    setScopePreview(result);
                  } catch (err) {
                    setScopePreviewError(err instanceof Error ? err.message : "Failed to generate scope document");
                  } finally {
                    setScopePreviewLoading(false);
                  }
                }}
                style={{
                  marginLeft: "auto",
                  padding: "3px 10px",
                  borderRadius: 6,
                  fontWeight: 600,
                  fontSize: 10,
                  border: "none",
                  background: scopePreview ? "#16a34a" : "#e2e8f0",
                  color: scopePreview ? "#fff" : "#94a3b8",
                  cursor: scopePreviewLoading ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                {scopePreviewLoading ? "⏳" : "🔗"} Download
              </button>
            </div>
            <div style={{ maxHeight: 260, overflowY: "auto" }}>
              {(() => {
                const apiCases = scopePreview?.apiTestCases || localApiTestCases;
                if (scopePreviewLoading && !scopePreview) {
                  return <div style={{ padding: "20px 8px", textAlign: "center", color: "#94a3b8", fontSize: 11 }}>⏳ Analyzing API endpoints...</div>;
                }
                if (!apiCases?.length) {
                  return <div style={{ padding: "20px 8px", textAlign: "center", color: "#94a3b8", fontSize: 11 }}>Click <strong>Download</strong> above to generate API test cases</div>;
                }
                return apiCases.slice(0, 20).map((tc) => {
                  const methodColors: Record<string, string> = {
                    GET: "#2563eb", POST: "#16a34a", PUT: "#f59e0b",
                    PATCH: "#8b5cf6", DELETE: "#ef4444",
                  };
                  return (
                    <div key={`api-${tc.id}`} style={{
                      padding: "10px 14px",
                      borderBottom: "1px solid #e8edf2",
                      fontSize: 12,
                      lineHeight: 1.7,
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <span style={{ color: "#94a3b8", fontSize: 10, fontWeight: 600, minWidth: 20 }}>#{tc.id}</span>
                        <span style={{
                          display: "inline-block", padding: "1px 6px", borderRadius: 3, fontSize: 10, fontWeight: 700,
                          color: "#fff", background: methodColors[tc.method] || "#64748b",
                        }}>{tc.method}</span>
                        <code style={{ fontSize: 11, color: "#1e293b", background: "#f1f5f9", padding: "1px 6px", borderRadius: 3 }}>{tc.path}</code>
                        <span style={{ fontSize: 10, color: "#64748b" }}>— {tc.controller}</span>
                      </div>
                      <div style={{ color: "#0f172a", fontSize: 13, lineHeight: 1.7, marginBottom: 4 }}>{tc.scenario}</div>
                      <div style={{ display: "flex", gap: 12, fontSize: 11, color: "#64748b", flexWrap: "wrap" }}>
                        <span>Expected: <span style={{
                          fontWeight: 600, padding: "1px 5px", borderRadius: 3,
                          background: tc.expectedStatus < 300 ? "#dcfce7" : "#fef2f2",
                          color: tc.expectedStatus < 300 ? "#166534" : "#dc2626",
                        }}>{tc.expectedStatus}</span></span>
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          </div>
        </div>
        {scopePreview && (
          <div style={{
            marginTop: 12, padding: "8px 12px", borderRadius: 8,
            background: "#f0fdf4", border: "1px solid #bbf7d0",
            fontSize: 11, color: "#166534",
          }}>
            ✓ Generated: {scopePreview.uiTestCount} UI tests + {scopePreview.apiTestCount} API tests
          </div>
        )}
        {scopePreviewError && (
          <div style={{
            marginTop: 12, padding: "10px 14px", borderRadius: 8,
            background: "#fef2f2", border: "1px solid #fecaca",
            fontSize: 12, color: "#dc2626",
          }}>
            ⚠ {scopePreviewError}
          </div>
        )}
      </div>
      */}


      {/* Test Validation Report Modal */}
      {showValidationReport && existingExecResult && (
        <ExistingTestValidationReport
          metrics={existingExecResult.metrics || {}}
          frameworkInfo={existingExecResult.framework_info}
          testResults={existingExecResult.test_results || []}
          fileBreakdown={existingExecResult.file_breakdown || []}
          logs={existingLogs}
          onClose={() => setShowValidationReport(false)}
          onSelectTest={(t: any) => {
            setTestDetailReport({
              testId: t.test_id || t.testId || `${t.suite}#${t.test_name}`,
              executionId: t.execution_id || t.executionId || jobId,
              name: t.test_name,
              suite: t.suite,
              status: t.status,
              duration: t.duration,
              file: t.file,
              url: t.report_url,
              type: t.type,
              testType: t.test_type || t.testType,
              framework: t.framework || existingExecResult?.framework_info?.build_tool || existingExecResult?.framework_info?.detected_framework,
              screenshotUrl: t.screenshot_url,
              videoUrl: t.video_url,
              traceUrl: t.trace_url,
              apiEvidence: t.api_evidence,
              error: t.failure_message || t.details?.error,
              errorCode: t.status === "FAILED" ? "TEST_FAILED" : t.status === "ERROR" ? "BUILD_ERROR" : t.status === "NOT_EXECUTED" ? "NOT_EXECUTED" : undefined,
              stackTrace: t.stack_trace || t.details?.stackTrace,
              stdout: t.stdout || t.details?.stdout,
              stderr: t.stderr || t.details?.stderr,
            });
            setShowTestDetailModal(true);
          }}
        />
      )}

      <TestReportsModal
        isOpen={showTestDetailModal}
        onClose={() => setShowTestDetailModal(false)}
        data={testDetailReport ? {
          testId: testDetailReport.testId,
          executionId: testDetailReport.executionId,
          title: testDetailReport.name,
          spec: testDetailReport.suite,
          status: testDetailReport.status,
          duration: testDetailReport.duration,
          file: testDetailReport.file,
          url: testDetailReport.url,
          error: testDetailReport.error,
          errorCode: testDetailReport.errorCode,
          type: testDetailReport.type,
          testType: testDetailReport.testType,
          framework: testDetailReport.framework,
          stackTrace: testDetailReport.stackTrace,
          stdout: testDetailReport.stdout,
          stderr: testDetailReport.stderr,
          screenshotUrl: testDetailReport.screenshotUrl,
          videoUrl: testDetailReport.videoUrl,
          traceUrl: testDetailReport.traceUrl,
          apiEvidence: testDetailReport.apiEvidence,
        } : null}
      />

      <div style={styles.btnRow}>
        <button style={styles.secondaryBtn} onClick={onBack}>{renderBackButtonLabel()}</button>
        <button style={{ ...styles.primaryBtn, opacity: loading ? 0.5 : 1 }} onClick={onStartMigration} disabled={loading}>
          {loading ? "Starting..." : "Start Migration"}
        </button>
      </div>
    </div>
  );
}
