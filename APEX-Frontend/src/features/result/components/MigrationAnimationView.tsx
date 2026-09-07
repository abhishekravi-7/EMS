import React from "react";
import {
  FaSearch,
  FaProjectDiagram,
  FaCode,
  FaPencilAlt,
  FaFileAlt,
  FaCheck,
  FaVial,
} from "react-icons/fa";
import type { MigrationResult } from "../services/resultService";
import { getMigrationElapsedSeconds } from "../utils/migrationTiming";
import javaApexCup from "@/assets/javaapex-cup.png";
import javaApexWordmark from "@/assets/javaapex-wordmark.png";
import "./MigrationAnimationView.css";

interface MigrationAnimationViewProps {
  loading: boolean;
  migrationJob: MigrationResult | null;
  migrationTimerNow: number;
  animationProgress: number;
  runFossa: boolean;
  runSonar: boolean;
  runTests: boolean;
  selectedRepoName: string | undefined;
  repoUrl: string;
  selectedSourceVersion: string;
  effectiveTargetVersion: string;
}

export function MigrationAnimationView({
  loading,
  migrationJob,
  migrationTimerNow,
  animationProgress,
  runFossa,
  runSonar,
  runTests,
  selectedRepoName,
  repoUrl,
  selectedSourceVersion,
  effectiveTargetVersion,
}: MigrationAnimationViewProps) {
  // Extract dynamic repository name with robust fallbacks
  const dynamicRepoName = React.useMemo(() => {
    if (selectedRepoName && selectedRepoName.trim()) {
      return selectedRepoName.trim();
    }
    if (migrationJob?.source_repo) {
      const parts = migrationJob.source_repo.trim().split(/[/\\]/).filter(Boolean);
      const last = parts.pop()?.replace(/\.git$/i, "");
      if (last) return last;
    }
    if (repoUrl && repoUrl.trim()) {
      const parts = repoUrl.trim().split(/[/\\]/).filter(Boolean);
      const last = parts.pop()?.replace(/\.git$/i, "");
      if (last) return last;
    }
    return "Java Project";
  }, [selectedRepoName, migrationJob?.source_repo, repoUrl]);

  // Clean and normalize Java version strings (e.g. "Java 21" -> "21", "1.8" -> "8")
  const formatJavaVersion = (raw: string | undefined | null, fallback: string): string => {
    if (!raw) return fallback;
    const trimmed = raw.trim();
    if (!trimmed) return fallback;
    const stripped = trimmed.replace(/^(?:java|jdk)\s*/i, "").trim();
    if (!stripped) return fallback;
    if (stripped === "1.8") return "8";
    return stripped;
  };

  const dynamicSourceVersion = React.useMemo(() => {
    return formatJavaVersion(
      migrationJob?.source_java_version || selectedSourceVersion,
      "8"
    );
  }, [migrationJob?.source_java_version, selectedSourceVersion]);

  const dynamicTargetVersion = React.useMemo(() => {
    return formatJavaVersion(
      migrationJob?.target_java_version || effectiveTargetVersion,
      "21"
    );
  }, [migrationJob?.target_java_version, effectiveTargetVersion]);

  // Elapsed migration duration
  const elapsedSeconds = React.useMemo(() => {
    return getMigrationElapsedSeconds(migrationJob, migrationTimerNow);
  }, [migrationJob, migrationTimerNow]);

  const formattedElapsed = React.useMemo(() => {
    const mins = Math.floor(elapsedSeconds / 60);
    const secs = elapsedSeconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }, [elapsedSeconds]);

  // Migration status and dynamic pipeline calculations
  const isInitializingMigration = loading && !migrationJob?.job_id;
  const actualBackendProgress = migrationJob?.progress_percent ?? 0;
  const isCompleted = migrationJob?.status === "completed" || actualBackendProgress >= 100;

  // Compute the current active pipeline stage (0 to 4, or 5 if completed)
  const activeStageIndex = React.useMemo(() => {
    if (isCompleted) return 5;

    const rawStep = (migrationJob?.current_step || "").toLowerCase();
    const rawStatus = (migrationJob?.status || "").toLowerCase();
    const combined = `${rawStep} ${rawStatus}`;

    // 1. Keyword-based stage inference from backend status & step description
    let textStage = -1;
    if (
      combined.includes("publish") ||
      combined.includes("report") ||
      combined.includes("push") ||
      combined.includes("summar")
    ) {
      textStage = 4;
    } else if (
      combined.includes("validat") ||
      combined.includes("test") ||
      combined.includes("sonar") ||
      combined.includes("fossa") ||
      combined.includes("quality") ||
      combined.includes("compiler")
    ) {
      textStage = 3;
    } else if (
      combined.includes("recipe") ||
      combined.includes("openrewrite") ||
      combined.includes("transform") ||
      combined.includes("source change") ||
      combined.includes("import change") ||
      combined.includes("refactor")
    ) {
      textStage = 2;
    } else if (
      combined.includes("dependenc") ||
      combined.includes("pom") ||
      combined.includes("gradle") ||
      combined.includes("library") ||
      combined.includes("package")
    ) {
      textStage = 1;
    } else if (
      combined.includes("clone") ||
      combined.includes("analy") ||
      combined.includes("prepar") ||
      combined.includes("queue") ||
      combined.includes("workspace") ||
      combined.includes("start")
    ) {
      textStage = 0;
    } else if (combined.includes("migrat")) {
      textStage = (actualBackendProgress >= 45 || elapsedSeconds >= 32) ? 2 : 1;
    }

    // 2. Progress percentage mapping
    const refProgress = Math.max(actualBackendProgress, animationProgress);
    let progressStage = 0;
    if (refProgress >= 90) progressStage = 4;
    else if (refProgress >= 70) progressStage = 3;
    else if (refProgress >= 45) progressStage = 2;
    else if (refProgress >= 20) progressStage = 1;
    else progressStage = 0;

    // 3. Natural progressive fallback from elapsed seconds to keep pipeline responsive
    let elapsedStage = 0;
    if (elapsedSeconds >= 60) elapsedStage = 3;
    else if (elapsedSeconds >= 32) elapsedStage = 2;
    else if (elapsedSeconds >= 12) elapsedStage = 1;

    if (combined.includes("analy") || combined.includes("clone") || isInitializingMigration) {
      elapsedStage = 0;
    }

    const candidate = Math.max(textStage, progressStage, elapsedStage, 0);
    return Math.min(candidate, 4);
  }, [isCompleted, migrationJob?.current_step, migrationJob?.status, actualBackendProgress, animationProgress, elapsedSeconds, isInitializingMigration]);

  // Unified dynamic progress percentage harmonized with active stage and elapsed duration
  const effectiveProgress = React.useMemo(() => {
    if (isCompleted) return 100;
    if (isInitializingMigration) return 10;

    const stageBases = [10, 30, 52, 74, 92];
    const stageCeilings = [28, 50, 72, 88, 98];

    const stageIdx = Math.min(Math.max(activeStageIndex, 0), 4);
    const base = stageBases[stageIdx] ?? 10;
    const ceiling = stageCeilings[stageIdx] ?? 98;

    // Smooth bounded forward drift based on elapsed duration (never resets or drops backward)
    const drift = Math.min(Math.floor(elapsedSeconds * 0.35), ceiling - base);
    const calculated = Math.max(actualBackendProgress, animationProgress, base + drift);

    return Math.min(Math.max(calculated, 10), isCompleted ? 100 : 99);
  }, [isCompleted, isInitializingMigration, activeStageIndex, actualBackendProgress, animationProgress, elapsedSeconds]);

  // Strictly sequential step status calculation (earlier steps MUST be completed, exactly one in-progress)
  const getStepStatus = React.useCallback(
    (index: number): "completed" | "in-progress" | "pending" => {
      if (isCompleted || activeStageIndex > index) {
        return "completed";
      }
      if (activeStageIndex === index) {
        return "in-progress";
      }
      return "pending";
    },
    [isCompleted, activeStageIndex]
  );

  const step1Status = getStepStatus(0); // Analyzing Source Code
  const step2Status = getStepStatus(1); // Updating Dependencies
  const step3Status = getStepStatus(2); // Applying Code Transformations
  const step4Status = getStepStatus(3); // Running Tests & Quality Checks
  const step5Status = getStepStatus(4); // Generating Migration Report

  // Connecting lines are active as each previous step completes
  const line0Active = isCompleted || activeStageIndex >= 1;
  const line1Active = isCompleted || activeStageIndex >= 2;
  const line2Active = isCompleted || activeStageIndex >= 3;
  const line3Active = isCompleted || activeStageIndex >= 4;

  const qualityVisible = isCompleted || activeStageIndex >= 3 || effectiveProgress >= 65;
  const qualityComplete = isCompleted || activeStageIndex >= 4 || step4Status === "completed";

  // Dynamic active task headline
  const dynamicStepHeadline = React.useMemo(() => {
    if (isCompleted) return "Migration completed successfully!";
    if (migrationJob?.current_step && migrationJob.current_step.trim()) {
      return migrationJob.current_step;
    }
    if (isInitializingMigration) {
      return "Creating migration job and preparing workspace...";
    }
    const defaultHeadlines = [
      "Analyzing repository source code and build structure...",
      "Updating dependencies and library compatibility...",
      "Applying automated OpenRewrite recipes and code transformations...",
      "Validating build compilation, running tests & quality gates...",
      "Finalizing documentation and generating comprehensive migration report...",
    ];
    return defaultHeadlines[Math.min(activeStageIndex, 4)];
  }, [isCompleted, migrationJob?.current_step, isInitializingMigration, activeStageIndex]);

  // Replay animation support for Java APEX logo
  const [isReplayingLogo, setIsReplayingLogo] = React.useState(false);

  const handleReplayLogo = React.useCallback(() => {
    setIsReplayingLogo(true);
    const timer = setTimeout(() => setIsReplayingLogo(false), 850);
    return () => clearTimeout(timer);
  }, []);

  React.useEffect(() => {
    (window as unknown as { replayJavaApexLogo?: () => void }).replayJavaApexLogo = () => {
      const stage = document.getElementById("logoStage");
      if (stage) {
        stage.classList.remove("replay");
        void stage.offsetWidth;
        stage.classList.add("replay");
      }
    };
  }, []);

  return (
    <div className="migration-loader-card">
      {/* Decorative Organic Waves */}
      <svg className="migration-bg-wave-tl" viewBox="0 0 320 260" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M-40 -40 C60 20 120 100 80 180 C40 240 -20 250 -40 260 Z" fill="url(#waveGradTL)" />
        <defs>
          <linearGradient id="waveGradTL" x1="0" y1="0" x2="200" y2="200" gradientUnits="userSpaceOnUse">
            <stop stopColor="#dbeafe" stopOpacity="0.6" />
            <stop offset="1" stopColor="#e0e7ff" stopOpacity="0.1" />
          </linearGradient>
        </defs>
      </svg>

      <svg className="migration-bg-wave-bl" viewBox="0 0 360 240" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M-40 240 C40 180 140 160 220 200 C280 230 330 220 360 240 Z" fill="url(#waveGradBL)" />
        <defs>
          <linearGradient id="waveGradBL" x1="0" y1="200" x2="300" y2="200" gradientUnits="userSpaceOnUse">
            <stop stopColor="#93c5fd" stopOpacity="0.35" />
            <stop offset="1" stopColor="#c7d2fe" stopOpacity="0.05" />
          </linearGradient>
        </defs>
      </svg>

      <svg className="migration-bg-wave-br" viewBox="0 0 340 220" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M340 220 C280 160 180 140 100 180 C40 210 0 210 -20 220 Z" fill="url(#waveGradBR)" />
        <defs>
          <linearGradient id="waveGradBR" x1="340" y1="220" x2="100" y2="150" gradientUnits="userSpaceOnUse">
            <stop stopColor="#bfdbfe" stopOpacity="0.4" />
            <stop offset="1" stopColor="#e0e7ff" stopOpacity="0.05" />
          </linearGradient>
        </defs>
      </svg>

      {/* Top Right Dot Matrix */}
      <svg className="migration-bg-dots" width="96" height="96" viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg">
        {[0, 1, 2, 3, 4, 5].map((row) =>
          [0, 1, 2, 3, 4, 5].map((col) => (
            <circle
              key={`dot-${row}-${col}`}
              cx={10 + col * 15}
              cy={10 + row * 15}
              r="2.2"
              fill="#93c5fd"
              opacity={0.55}
            />
          ))
        )}
      </svg>

      {/* Header Section */}
      <div className="migration-header-section">
        {/* Animated Java APEX Logo */}
        <div
          className={`logo-stage ${isReplayingLogo ? "replay" : ""}`}
          id="logoStage"
          aria-label="Java APEX"
          onClick={handleReplayLogo}
          title="Click to replay animation"
        >
          <div className="logo">
            <img
              className="cup"
              src={javaApexCup}
              alt="Java APEX cup icon"
            />
            <div className="wordmark-wrap">
              <img
                className="wordmark"
                src={javaApexWordmark}
                alt="Java APEX"
              />
            </div>
          </div>
        </div>

        {/* Dynamic Project Title: Modernizing {repoName} */}
        <h1 className="migration-modernizing-title">
          <span className="migration-title-purple">Modernizing</span>{" "}
          <span className="migration-title-reponame">{dynamicRepoName}</span>
        </h1>

        {/* Dynamic Version Converter Badge: Java X → Java Y */}
        <div className="migration-version-pill">
          <span>Java {dynamicSourceVersion}</span>
          <span className="migration-version-arrow">→</span>
          <span>Java {dynamicTargetVersion}</span>
        </div>

        {/* Subtitle */}
        <p className="migration-header-subtitle">
          We&apos;re migrating your project to a better, modern version.
          <br />
          Please wait while we process your data.
        </p>
      </div>

      {/* Horizontal Pipeline Stepper (5 stages) */}
      <div className="migration-pipeline-wrap">
        {/* Step 1: Analyzing Source Code */}
        <div className={`migration-step-node migration-step-${step1Status}`}>
          <div className="migration-node-circle-wrap">
            <div className="migration-node-circle migration-circle-step-1">
              <FaSearch className="migration-circle-icon icon-step-1" />
            </div>
            {step1Status === "in-progress" && (
              <>
                <div className="migration-node-active-ring migration-ring-step-1" />
                <div className="migration-node-active-pulse migration-pulse-step-1" />
              </>
            )}
            {step1Status === "completed" && (
              <div className="migration-node-check-badge migration-badge-step-1">
                <FaCheck size={9} color="#ffffff" />
              </div>
            )}
          </div>
          <div className="migration-node-title">
            <span>Analyzing</span>
            <span>Source Code</span>
          </div>
          <div className={`migration-node-status migration-status-${step1Status}`}>
            {step1Status === "completed" ? "Completed" : step1Status === "in-progress" ? "In Progress" : "Pending"}
          </div>
        </div>

        <div className={`migration-pipeline-line ${line0Active ? "migration-line-active-0" : "migration-line-pending"}`}>
          {line0Active && <div className="migration-line-stream beam-0" />}
        </div>

        {/* Step 2: Updating Dependencies */}
        <div className={`migration-step-node migration-step-${step2Status}`}>
          <div className="migration-node-circle-wrap">
            <div className="migration-node-circle migration-circle-step-2">
              <FaProjectDiagram className="migration-circle-icon icon-step-2" />
            </div>
            {step2Status === "in-progress" && (
              <>
                <div className="migration-node-active-ring migration-ring-step-2" />
                <div className="migration-node-active-pulse migration-pulse-step-2" />
              </>
            )}
            {step2Status === "completed" && (
              <div className="migration-node-check-badge migration-badge-step-2">
                <FaCheck size={9} color="#ffffff" />
              </div>
            )}
          </div>
          <div className="migration-node-title">
            <span>Updating</span>
            <span>Dependencies</span>
          </div>
          <div className={`migration-node-status migration-status-${step2Status}`}>
            {step2Status === "completed" ? "Completed" : step2Status === "in-progress" ? "In Progress" : "Pending"}
          </div>
        </div>

        <div className={`migration-pipeline-line ${line1Active ? "migration-line-active-1" : "migration-line-pending"}`}>
          {line1Active && <div className="migration-line-stream beam-1" />}
        </div>

        {/* Step 3: Applying Code Transformations */}
        <div className={`migration-step-node migration-step-${step3Status}`}>
          <div className="migration-node-circle-wrap">
            <div className="migration-node-circle migration-circle-step-3">
              <FaCode className="migration-circle-icon icon-step-3" />
            </div>
            {step3Status === "in-progress" && (
              <>
                <div className="migration-node-active-ring migration-ring-step-3" />
                <div className="migration-node-active-pulse migration-pulse-step-3" />
              </>
            )}
            {step3Status === "completed" && (
              <div className="migration-node-check-badge migration-badge-step-3">
                <FaCheck size={9} color="#ffffff" />
              </div>
            )}
          </div>
          <div className="migration-node-title">
            <span>Applying Code</span>
            <span>Transformations</span>
          </div>
          <div className={`migration-node-status migration-status-${step3Status}`}>
            {step3Status === "completed" ? "Completed" : step3Status === "in-progress" ? "In Progress" : "Pending"}
          </div>
        </div>

        <div className={`migration-pipeline-line ${line2Active ? "migration-line-active-2" : "migration-line-pending"}`}>
          {line2Active && <div className="migration-line-stream beam-2" />}
        </div>

        {/* Step 4: Running Tests & Quality Checks */}
        <div className={`migration-step-node migration-step-${step4Status}`}>
          <div className="migration-node-circle-wrap">
            <div className="migration-node-circle migration-circle-step-4">
              <FaPencilAlt className="migration-circle-icon icon-step-4" />
            </div>
            {step4Status === "in-progress" && (
              <>
                <div className="migration-node-active-ring migration-ring-step-4" />
                <div className="migration-node-active-pulse migration-pulse-step-4" />
              </>
            )}
            {step4Status === "completed" && (
              <div className="migration-node-check-badge migration-badge-step-4">
                <FaCheck size={9} color="#ffffff" />
              </div>
            )}
          </div>
          <div className="migration-node-title">
            <span>Running Tests &amp;</span>
            <span>Quality Checks</span>
          </div>
          <div className={`migration-node-status migration-status-${step4Status}`}>
            {step4Status === "completed" ? "Completed" : step4Status === "in-progress" ? "In Progress" : "Pending"}
          </div>
        </div>

        <div className={`migration-pipeline-line ${line3Active ? "migration-line-active-3" : "migration-line-pending"}`}>
          {line3Active && <div className="migration-line-stream beam-3" />}
        </div>

        {/* Step 5: Generating Migration Report */}
        <div className={`migration-step-node migration-step-${step5Status}`}>
          <div className="migration-node-circle-wrap">
            <div className="migration-node-circle migration-circle-step-5">
              <FaFileAlt className="migration-circle-icon icon-step-5" />
            </div>
            {step5Status === "in-progress" && (
              <>
                <div className="migration-node-active-ring migration-ring-step-5" />
                <div className="migration-node-active-pulse migration-pulse-step-5" />
              </>
            )}
            {step5Status === "completed" && (
              <div className="migration-node-check-badge migration-badge-step-5">
                <FaCheck size={9} color="#ffffff" />
              </div>
            )}
          </div>
          <div className="migration-node-title">
            <span>Generating</span>
            <span>Migration Report</span>
          </div>
          <div className={`migration-node-status migration-status-${step5Status}`}>
            {step5Status === "completed" ? "Completed" : step5Status === "in-progress" ? "In Progress" : "Pending"}
          </div>
        </div>
      </div>

      {/* Progress Bar Section */}
      <div className="migration-progressbar-row">
        <div className="migration-progressbar-track">
          <div
            className="migration-progressbar-fill"
            style={{ width: `${effectiveProgress}%` }}
          >
            <div className="migration-progressbar-shimmer" />
            <div className="migration-progressbar-glow-tip" />
          </div>
        </div>
        <div className="migration-progressbar-label">{effectiveProgress}%</div>
      </div>

      {/* Sub-Task Status Pill Card */}
      <div className="migration-subtask-card">
        {isCompleted ? (
          <div className="migration-subtask-check-icon">
            <FaCheck size={13} color="#16a34a" />
          </div>
        ) : (
          <div className="migration-ring-spinner" />
        )}
        <div className="migration-subtask-divider" />
        <div className="migration-subtask-content">
          <div className="migration-subtask-headline">{dynamicStepHeadline}</div>
          <div className="migration-subtask-subtext">
            <span>{isCompleted ? "All modernization tasks finished." : "This may take a few moments."}</span>
            {elapsedSeconds > 0 && (
              <span className="migration-subtask-timer">
                • Elapsed: {formattedElapsed}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Info notices for initial loading and cloning */}
      {isInitializingMigration && (
        <div style={{ marginTop: 16, color: "#2563eb", fontSize: 13, textAlign: "center" }}>
          ℹ️ Loading migration session. Large repositories can take a moment to prepare...
        </div>
      )}
      {migrationJob?.status === "cloning" && (
        <div style={{ marginTop: 16, color: "#f59e0b", fontSize: 13, textAlign: "center" }}>
          ℹ️ Cloning repository... this may take a few moments for large codebases. Please wait.
        </div>
      )}

      {/* Footer Tagline & Brand Signature */}
      <div className="migration-footer-quote">
        {/* <div className="migration-footer-quote-line" /> */}
        {/* <span>Modern code today. A stronger tomorrow.</span> */}
        {/* <div className="migration-footer-quote-line" /> */}
      </div>

      <div className="migration-footer-brand">
        <span className="dot dot-1" />
        <span className="dot dot-2" />
        <span className="dot dot-3" />
        <span className="dot dot-4" />
        <span className="brand-name">Java APEX</span>
      </div>

      {/* Functional Test Results Panel (MockMvc / Playwright / Selenium) */}
      {(qualityVisible || qualityComplete) && (() => {
        const functionalTesting = migrationJob?.test_pipeline?.functional_testing ?? migrationJob?.functional_pipeline ?? null;
        const runners = functionalTesting?.execution?.runners ?? [];
        const mockMvcRunners = runners.filter((r) =>
          r.tool === "MOCK_MVC" || r.tool?.toLowerCase().includes("mock") || r.tool?.toLowerCase().includes("springmvc")
        );
        const uiRunners = runners.filter((r) =>
          r.tool === "PLAYWRIGHT" || r.tool === "SELENIUM" || r.tool?.toLowerCase() === "playwright" || r.tool?.toLowerCase() === "selenium"
        );
        const springTestCases = functionalTesting?.test_cases ?? [];
        const filteredSpringTestCases = springTestCases.filter((tc) =>
          tc.tool === "MOCK_MVC" || tc.tool?.toLowerCase().includes("mock") || tc.tool?.toLowerCase().includes("spring")
        );
        if (runners.length === 0 && filteredSpringTestCases.length === 0) return null;
        const totalTests = runners.reduce((s: number, r) => s + (r.tests_run ?? 0), 0);
        const totalPassed = runners.reduce((s: number, r) => s + (r.tests_passed ?? 0), 0);
        const renderRunnerRow = (runner: (typeof runners)[number], idx: number) => (
          <div key={`runner-${idx}`} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "10px 14px", borderRadius: 10, border: "1px solid #bbf7d0", background: "#f0fdf4" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
              <span style={{ fontSize: 16 }}>{runner.status === "passed" ? "✅" : runner.status === "skipped" ? "⏭️" : "⚠️"}</span>
              <span style={{ fontWeight: 700, color: "#0f172a", fontSize: 13 }}>{runner.tool || "Tool"}</span>
              <span style={{ fontSize: 12, color: runner.status === "passed" ? "#166534" : runner.status === "skipped" ? "#6b7280" : "#dc2626", fontWeight: 600, textTransform: "uppercase" }}>{runner.status === "passed" ? "PASSED" : runner.status === "failed" ? "FAILED" : runner.status === "skipped" ? "SKIPPED" : runner.status || "EXECUTED"}</span>
              {runner.execution_mode && (
                <span style={{ fontSize: 11, color: "#64748b" }}>({runner.execution_mode === "internal_validation" ? "source validated" : "container validated"})</span>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              {runner.tests_run != null && runner.tests_run > 0 && (
                <>
                  <span style={{ fontSize: 12, color: "#64748b" }}>
                    <strong style={{ color: "#16a34a" }}>{runner.tests_passed ?? 0}</strong>/{runner.tests_run} passed
                  </span>
                  {(runner.tests_failed ?? 0) > 0 && (
                    <span style={{ fontSize: 12, color: "#dc2626", fontWeight: 600 }}>
                      {runner.tests_failed} failed
                    </span>
                  )}
                </>
              )}
              {runner.output_tail && (
                <span style={{ fontSize: 11, color: "#64748b", fontStyle: "italic", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{runner.output_tail}</span>
              )}
            </div>
          </div>
        );
        return (
          <div style={{ marginTop: 24, border: "1px solid #bfdbfe", borderRadius: 16, background: "#f8fbff", overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 18px", background: "linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)", borderBottom: "1px solid #bfdbfe" }}>
              <FaVial style={{ fontSize: 16, color: "#2563eb" }} />
              <span style={{ fontWeight: 700, fontSize: 14, color: "#1e40af" }}>Functional Test Results</span>
              {runners.length > 0 && (
                <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 12, padding: "3px 10px", borderRadius: 999, background: runners.every(r => r.status === "passed") ? "#dcfce7" : "#fef3c7", color: runners.every(r => r.status === "passed") ? "#166534" : "#92400e", fontWeight: 700 }}>
                    {runners.every(r => r.status === "passed") ? "✅ All Passed" : "⚠️ Issues Found"}
                  </span>
                </span>
              )}
            </div>
            <div style={{ padding: "16px 18px" }}>
              {mockMvcRunners.length > 0 && (
                <div style={{ marginBottom: uiRunners.length > 0 ? 16 : 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>MockMvc &amp; Spring MVC</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {mockMvcRunners.map((runner, idx: number) => renderRunnerRow(runner, idx))}
                  </div>
                </div>
              )}
              {uiRunners.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Playwright / Selenium</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {uiRunners.map((runner, idx: number) => renderRunnerRow(runner, idx))}
                  </div>
                </div>
              )}
              {totalTests > 0 && (
                <div style={{ display: "flex", gap: 16, marginTop: 12, flexWrap: "wrap" }}>
                  <div style={{ padding: "10px 16px", borderRadius: 10, background: "#ffffff", border: "1px solid #e2e8f0", textAlign: "center", flex: 1, minWidth: 100 }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: "#0f172a" }}>{totalTests}</div>
                    <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, textTransform: "uppercase" }}>Tests Run</div>
                  </div>
                  <div style={{ padding: "10px 16px", borderRadius: 10, background: "#f0fdf4", border: "1px solid #bbf7d0", textAlign: "center", flex: 1, minWidth: 100 }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: "#16a34a" }}>{totalPassed}</div>
                    <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, textTransform: "uppercase" }}>Passed</div>
                  </div>
                  <div style={{ padding: "10px 16px", borderRadius: 10, background: totalTests - totalPassed > 0 ? "#fef2f2" : "#ffffff", border: `1px solid ${totalTests - totalPassed > 0 ? "#fecaca" : "#e2e8f0"}`, textAlign: "center", flex: 1, minWidth: 100 }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: totalTests - totalPassed > 0 ? "#dc2626" : "#64748b" }}>{totalTests - totalPassed}</div>
                    <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, textTransform: "uppercase" }}>Failed</div>
                  </div>
                  {totalTests > 0 && (
                    <div style={{ padding: "10px 16px", borderRadius: 10, background: "#ffffff", border: "1px solid #e2e8f0", textAlign: "center", flex: 1, minWidth: 100 }}>
                      <div style={{ fontSize: 22, fontWeight: 800, color: totalPassed === totalTests ? "#16a34a" : "#d97706" }}>{Math.round((totalPassed / totalTests) * 100)}%</div>
                      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, textTransform: "uppercase" }}>Success Rate</div>
                    </div>
                  )}
                </div>
              )}
              {filteredSpringTestCases.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Test Cases</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {filteredSpringTestCases.slice(0, 10).map((tc, idx: number) => (
                      <div key={`spring-tc-${idx}`} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", borderRadius: 8, border: "1px solid #e2e8f0", background: "#fff" }}>
                        <span style={{ fontSize: 14, color: tc.status === "passed" ? "#16a34a" : tc.status === "failed" ? "#dc2626" : "#64748b" }}>
                          {tc.status === "passed" ? "✅" : tc.status === "failed" ? "❌" : "⏳"}
                        </span>
                        <span style={{ fontWeight: 600, fontSize: 12, color: "#0f172a", flex: 1 }}>
                          {tc.name || `${tc.method || "GET"} ${tc.path || tc.route || tc.schema || "/"}`}
                        </span>
                        {tc.expectedStatus && (
                          <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, background: "#eff6ff", color: "#1d4ed8", fontWeight: 600 }}>{tc.expectedStatus}</span>
                        )}
                        <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, background: tc.status === "passed" ? "#dcfce7" : tc.status === "failed" ? "#fee2e2" : "#f1f5f9", color: tc.status === "passed" ? "#166534" : tc.status === "failed" ? "#991b1b" : "#475569", fontWeight: 600, textTransform: "uppercase" }}>
                          {tc.status || "GENERATED"}
                        </span>
                        {tc.validation_reason && (
                          <span style={{ fontSize: 11, color: "#64748b", fontStyle: "italic", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{tc.validation_reason}</span>
                        )}
                      </div>
                    ))}
                    {filteredSpringTestCases.length > 10 && (
                      <div style={{ fontSize: 11, color: "#64748b", textAlign: "center", padding: 4 }}>
                        +{filteredSpringTestCases.length - 10} more test cases
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
