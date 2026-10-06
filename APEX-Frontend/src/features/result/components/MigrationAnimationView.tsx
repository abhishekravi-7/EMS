import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  FaCheck,
  FaTimes,
  FaTerminal,
  FaEraser,
  FaTools,
  FaRedo,
} from "react-icons/fa";
import {
  LuCode,
  LuBox,
  LuShieldCheck,
  LuFolder,
  LuFileText,
} from "react-icons/lu";
import type { MigrationResult, FossaScanResult } from "../services/resultService";
import {
  buildMigrationState,
  generateStepLogs,
  generateStepCompletionLog as _generateStepCompletionLog,
  generateFinalCompletionLog as _generateFinalCompletionLog,
  STEP_NUMBER_TO_ID,
  type MigrationStepId,
  type MigrationLogEvent,
  type MigrationState,
  type SourceLocationReference,
} from "../utils/migrationStateModel";
import { SourceCodeViewerModal } from "./SourceCodeViewerModal";
import { QualityCheckDetailsModal } from "./QualityCheckDetailsModal";
import { MigrationStepper, type MigrationStepItem as StepperStepItem } from "./MigrationStepper";
import { displayError } from "@/shared/utils/llmError";
import "./MigrationAnimationView.css";
import { getMigrationElapsedSeconds } from "../utils/migrationTiming";


export interface MigrationStepConfig {
  id: number;
  stepId: MigrationStepId;
  title: string;
  description: string;
  icon: React.ComponentType<{ size?: number; className?: string; color?: string }>;
  targetProgress: number;
  activityTitle: string;
  activitySubtitle: (state: MigrationState) => string;
}

export interface MigrationAnimationViewProps {
  loading?: boolean;
  migrationJob: MigrationResult | null;
  migrationTimerNow?: number;
  animationProgress?: number;
  runFossa?: boolean;
  runSonar?: boolean;
  runTests?: boolean;
  selectedRepoName?: string;
  repoUrl?: string;
  selectedSourceVersion?: string;
  effectiveTargetVersion?: string;
  repoAnalysis?: Record<string, unknown>;
  codeChanges?: Record<string, unknown>[];
  fossaResult?: FossaScanResult | null;
  backendLogs?: string[];
  onMigrationComplete?: () => void;
  onViewReport?: () => void;
  onRetry?: () => void;
}

// Exactly 6 steps as required by the specification - reference design icons & messages
const MIGRATION_STEPS_CONFIG: MigrationStepConfig[] = [
  {
    id: 1,
    stepId: "code-version-update",
    title: "1. Code version update",
    description: "Analyzing and updating source code to target version",
    icon: LuCode,
    targetProgress: 16,
    activityTitle: "Scanning source files...",
    activitySubtitle: () => "Analyzing Java files and detecting version changes.",
  },
  {
    id: 2,
    stepId: "dependency-updates",
    title: "2. Dependencies updates",
    description: "Updating libraries and third-party dependencies",
    icon: LuBox,
    targetProgress: 32,
    activityTitle: "Updating dependencies...",
    activitySubtitle: () => "Reading pom.xml and resolving compatible libraries.",
  },
  {
    id: 3,
    stepId: "code-transformation",
    title: "3. Code fix & code transformation",
    description: "Applying automated fixes and transforming code",
    icon: FaTools,
    targetProgress: 50,
    activityTitle: "Transforming code files...",
    activitySubtitle: () => "Applying automated fixes and code transformations.",
  },
  {
    id: 4,
    stepId: "quality-check",
    title: "4. Quality check (Sonar, FOSSA)",
    description: "Running static analysis and unit tests",
    icon: LuShieldCheck,
    targetProgress: 66,
    activityTitle: "Running quality checks...",
    activitySubtitle: () => "Executing Sonar, FOSSA and JUnit checks.",
  },
  {
    id: 5,
    stepId: "code-depreciation",
    title: "5. Code Deprecation",
    description: "Analyzing and reporting deprecated code",
    icon: LuFolder,
    targetProgress: 83,
    activityTitle: "Analyzing deprecated code...",
    activitySubtitle: () => "Scanning for deprecated APIs and methods.",
  },
  {
    id: 6,
    stepId: "migration-report",
    title: "6. Generating migration report",
    description: "Compiling results and generating final report",
    icon: LuFileText,
    targetProgress: 100,
    activityTitle: "Generating migration report...",
    activitySubtitle: () => "Compiling results and preparing final report.",
  },
];

// Helper function to parse raw backend logs into structured MigrationLogEvent items
function parseBackendLogs(
  rawLines: string[],
  _currentState: MigrationState,
  currentActiveStep: number
): MigrationLogEvent[] {
  if (!rawLines || rawLines.length === 0) {
    return [];
  }

  return rawLines.map((line, idx) => {
    const trimmed = line.trim();
    const lower = trimmed.toLowerCase();

    // 1. Determine Step (1 to 6) based on markers & content
    let step = 1;
    if (trimmed.includes("[CODE VERSION]") || lower.includes("source java") || lower.includes("target java") || lower.includes("preparing workspace") || lower.includes("preparing migrated-repo") || lower.includes("stage=code-version-update")) {
      step = 1;
    } else if (trimmed.includes("[DEPENDENCIES]") || lower.includes("dependency") || lower.includes("dependencies") || lower.includes("spring boot") || lower.includes("plugin") || lower.includes("stage=dependency-updates")) {
      step = 2;
    } else if (trimmed.includes("[TRANSFORMATION]") || lower.includes("openrewrite") || lower.includes("transformation") || lower.includes("ast") || lower.includes("javax") || lower.includes("jakarta") || lower.includes("stage=code-transformation")) {
      step = 3;
    } else if (trimmed.includes("[QUALITY CHECK]") || lower.includes("sonar") || lower.includes("fossa") || lower.includes("junit") || lower.includes("unit test") || lower.includes("jacoco") || lower.includes("surefire") || lower.includes("build validation") || lower.includes("stage=quality-check")) {
      step = 4;
    } else if (trimmed.includes("[DEPRECATION]") || lower.includes("deprecat") || lower.includes("published to") || lower.includes("publishing") || lower.includes("stage=code-depreciation")) {
      step = 5;
    } else if (trimmed.includes("[REPORT]") || lower.includes("migration report") || lower.includes("proposed tests") || lower.includes("knowledge base") || lower.includes("migration completed") || lower.includes("stage=migration-report")) {
      step = 6;
    } else {
      step = Math.min(6, Math.max(1, currentActiveStep));
    }

    const stepId = STEP_NUMBER_TO_ID[step] || "code-version-update";

    // 2. Determine Log Type
    let type: MigrationLogEvent["type"] = "INFO";
    if (lower.includes("error") || lower.includes("failed") || lower.includes("failure") || lower.includes("exception")) {
      type = "ERROR";
    } else if (lower.includes("warn") || lower.includes("deprecated") || lower.includes("notice:")) {
      type = "WARN";
    } else if (lower.includes("success") || lower.includes("completed") || lower.includes("passed")) {
      type = "SUCCESS";
    }

    // 3. Category & Clickable metadata
    let category: string | undefined;
    let clickable = false;
    let action: string | undefined;
    let target: string | undefined;

    if (step === 4 || lower.includes("sonar") || lower.includes("fossa") || lower.includes("junit") || lower.includes("jacoco")) {
      if (lower.includes("sonar")) {
        category = "sonarqube";
        clickable = true;
        action = "OPEN_SONARQUBE_RESULTS";
        target = "sonarqube";
      } else if (lower.includes("fossa")) {
        category = "fossa";
        clickable = true;
        action = "OPEN_FOSSA_RESULTS";
        target = "fossa";
      } else if (lower.includes("junit") || lower.includes("test") || lower.includes("jacoco") || lower.includes("surefire")) {
        category = "junit";
        clickable = true;
        action = "OPEN_JUNIT_RESULTS";
        target = "junit";
      }
    } else if ((step === 5 || lower.includes("deprecat")) && lower.includes("deprecat")) {
      category = "deprecation";
      clickable = true;
      action = "OPEN_DEPRECATION_RESULTS";
      target = "deprecation";
    } else if ((step === 6 || lower.includes("report") || lower.includes("completed")) && (lower.includes("report") || lower.includes("completed"))) {
      category = "migration-report";
      clickable = true;
      action = "OPEN_MIGRATION_REPORT";
      target = "report";
    }

    return {
      id: `backend-log-${idx}-${step}`,
      step,
      stepId,
      type,
      message: trimmed,
      category,
      clickable,
      action,
      target,
    };
  });
}

export function MigrationAnimationView({
  migrationJob,
  runFossa = false,
  runSonar = false,
  runTests = true,
  selectedRepoName,
  repoUrl = "",
  selectedSourceVersion = "8",
  effectiveTargetVersion = "17",
  repoAnalysis,
  codeChanges = [],
  fossaResult = null,
  backendLogs = [],
  onMigrationComplete,
  onViewReport,
  onRetry,
}: MigrationAnimationViewProps) {
  // Derive Step States, Active Step, and Progress directly from migrationJob (Single Source of Truth)
  const { derivedStepStates, derivedActiveStep, derivedProgress } = useMemo(() => {
    const rawStatus = (migrationJob?.status || "").toLowerCase();
    const isFailed = rawStatus === "failed" || Boolean(migrationJob?.error_message);
    const isCompleted = rawStatus === "completed" || rawStatus === "success";
    const backendPct = Math.min(100, Math.max(0, migrationJob?.progress_percent ?? 0));

    // If backend provides structured stages array:
    if (Array.isArray(migrationJob?.stages) && migrationJob.stages.length >= 6) {
      const states: Record<number, "pending" | "in_progress" | "completed" | "failed"> = {};
      let actStep = 1;
      let foundActive = false;

      migrationJob.stages.forEach((stage, idx) => {
        const stepNum = idx + 1;
        states[stepNum] = stage.status;
        if (stage.status === "in_progress" || stage.status === "failed") {
          actStep = stepNum;
          foundActive = true;
        }
      });

      if (!foundActive) {
        actStep = isCompleted || backendPct >= 100 ? 6 : 1;
      }

      return {
        derivedStepStates: states,
        derivedActiveStep: actStep,
        derivedProgress: isCompleted ? 100 : backendPct,
      };
    }

    // Fallback based on backend percentage and status
    const states: Record<number, "pending" | "in_progress" | "completed" | "failed"> = {
      1: "pending",
      2: "pending",
      3: "pending",
      4: "pending",
      5: "pending",
      6: "pending",
    };

    let actStep = 1;
    if (isCompleted || backendPct >= 100) {
      states[1] = "completed";
      states[2] = "completed";
      states[3] = "completed";
      states[4] = "completed";
      states[5] = "completed";
      states[6] = "completed";
      actStep = 6;
    } else {
      const thresholds = [16, 35, 60, 80, 90, 100];
      for (let i = 0; i < 6; i++) {
        const stepNum = i + 1;
        const thresh = thresholds[i];
        const prevThresh = i === 0 ? 0 : thresholds[i - 1];

        if (backendPct >= thresh) {
          states[stepNum] = "completed";
        } else if (backendPct >= prevThresh) {
          states[stepNum] = isFailed ? "failed" : "in_progress";
          actStep = stepNum;
        } else {
          states[stepNum] = "pending";
        }
      }
    }

    return {
      derivedStepStates: states,
      derivedActiveStep: actStep,
      derivedProgress: isCompleted ? 100 : backendPct,
    };
  }, [migrationJob]);

  const activeStep = derivedActiveStep;
  const stepStates = derivedStepStates;
  const progressPercent = derivedProgress;

  const [selectedStepId, setSelectedStepId] = useState<MigrationStepId>("code-version-update");
  const [hasUserSelectedStepManually, setHasUserSelectedStepManually] = useState<boolean>(false);

  if (!hasUserSelectedStepManually && activeStep <= 6) {
    const autoStepId = STEP_NUMBER_TO_ID[activeStep];
    if (autoStepId && selectedStepId !== autoStepId) {
      setSelectedStepId(autoStepId);
    }
  }

  const [activeSourceRef, setActiveSourceRef] = useState<SourceLocationReference | null>(null);
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [activeQualityCheck, setActiveQualityCheck] = useState<{
    category: string;
    logMessage?: string;
  } | null>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Workflow stepper card ref & dynamic height synchronization
  const workflowCardRef = useRef<HTMLDivElement>(null);
  const [stepperHeight, setStepperHeight] = useState<number | null>(null);

  useEffect(() => {
    const el = workflowCardRef.current;
    if (!el) return;

    const updateHeight = () => {
      if (typeof window !== "undefined" && window.innerWidth <= 1024) {
        setStepperHeight(null);
        return;
      }
      const rectHeight = el.getBoundingClientRect().height;
      if (rectHeight > 0) {
        setStepperHeight(Math.round(rectHeight));
      }
    };

    updateHeight();

    const resizeObserver = new ResizeObserver(() => {
      updateHeight();
    });
    resizeObserver.observe(el);

    window.addEventListener("resize", updateHeight);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", updateHeight);
    };
  }, []);

  // Handle clicking any migration step
  const handleSelectStep = (clickedStepId: string) => {
    setSelectedStepId(clickedStepId as MigrationStepId);
    setHasUserSelectedStepManually(true);
    setIsUserScrolledUp(false);
    setHasNewLogsBelow(false);
    setTimeout(() => {
      const el = logsContainerRef.current;
      if (el) {
        el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      }
    }, 40);
  };

  // Generic handler for clickable logs (SonarQube, FOSSA, JUnit, Source Code, Deprecation, Report)
  const handleLogClick = (log: MigrationLogEvent) => {
    setSelectedLogId(log.id);

    if (log.action === "OPEN_SONARQUBE_RESULTS" || log.category === "sonarqube") {
      setActiveQualityCheck({
        category: "sonarqube",
        logMessage: log.message,
      });
    } else if (log.action === "OPEN_FOSSA_RESULTS" || log.category === "fossa") {
      setActiveQualityCheck({
        category: "fossa",
        logMessage: log.message,
      });
    } else if (log.action === "OPEN_JUNIT_RESULTS" || log.category === "junit") {
      setActiveQualityCheck({
        category: "junit",
        logMessage: log.message,
      });
    } else if (log.action === "OPEN_DEPRECATION_RESULTS" || log.category === "deprecation") {
      setActiveQualityCheck({
        category: "deprecation",
        logMessage: log.message,
      });
    } else if (log.action === "OPEN_SOURCE_CODE" || log.sourceReference) {
      if (log.sourceReference) {
        setActiveSourceRef(log.sourceReference);
      }
    } else if (log.action === "OPEN_MIGRATION_REPORT" || log.category === "migration-report") {
      navigateToResults();
    }
  };

  // Auto-scroll state
  const [isUserScrolledUp, setIsUserScrolledUp] = useState(false);
  const [hasNewLogsBelow, setHasNewLogsBelow] = useState(false);

  // Live Elapsed Timer
  const [startTime] = useState<number>(() => Date.now());


  // 5-Second Automatic Navigation State & Refs
  const [redirectCountdown, setRedirectCountdown] = useState<number | null>(null);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasStartedCountdownRef = useRef<boolean>(false);
  const onViewReportRef = useRef(onViewReport);
  const onMigrationCompleteRef = useRef(onMigrationComplete);

  useEffect(() => {
    onViewReportRef.current = onViewReport;
    onMigrationCompleteRef.current = onMigrationComplete;
  }, [onViewReport, onMigrationComplete]);

  // Dedicated navigation function using existing router mechanism
  const navigateToResults = () => {
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }
    if (onViewReportRef.current) {
      onViewReportRef.current();
    } else if (onMigrationCompleteRef.current) {
      onMigrationCompleteRef.current();
    }
  };

  // Backend Status Detection & Genuine Migration Status
  const backendStatus = (migrationJob?.status || "").toLowerCase();
  const isBackendFailed = backendStatus === "failed" || Boolean(migrationJob?.error_message);
  const isBackendCompleted = backendStatus === "completed" || backendStatus === "success" || (progressPercent >= 100 && backendStatus !== "running" && backendStatus !== "queued");

  // Overall Genuine Completion Condition
  const isAllComplete = isBackendCompleted && !isBackendFailed;

  // Single Completion Countdown Timer (5 seconds)
  useEffect(() => {
    if (!isAllComplete) return;
    if (hasStartedCountdownRef.current) return;

    hasStartedCountdownRef.current = true;
    Promise.resolve().then(() => {
      setRedirectCountdown(5);
    });

    countdownTimerRef.current = setInterval(() => {
      setRedirectCountdown((prev) => {
        if (prev === null || prev <= 1) return 0;
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (countdownTimerRef.current) {
        clearInterval(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }
    };
  }, [isAllComplete]);

  // Safely trigger navigation when countdown reaches 0
  useEffect(() => {
    if (redirectCountdown === 0) {
      if (countdownTimerRef.current) {
        clearInterval(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }
      navigateToResults();
    }
  }, [redirectCountdown]);

  // Single Source of Truth MigrationState
  const migrationState = useMemo<MigrationState>(() => {
    return buildMigrationState({
      migrationJob,
      repoAnalysis,
      codeChanges,
      fossaResult,
      selectedRepoName,
      repoUrl,
      selectedSourceVersion,
      effectiveTargetVersion,
      runSonar,
      runFossa,
      runTests,
      currentStep: activeStep,
      progress: progressPercent,
    });
  }, [
    migrationJob,
    repoAnalysis,
    codeChanges,
    fossaResult,
    selectedRepoName,
    repoUrl,
    selectedSourceVersion,
    effectiveTargetVersion,
    runSonar,
    runFossa,
    runTests,
    activeStep,
    progressPercent,
  ]);

  const [localTick, setLocalTick] = useState<number>(() => Date.now());
  useEffect(() => {
    if (isAllComplete || isBackendFailed) return;
    const interval = setInterval(() => {
      setLocalTick(Date.now());
    }, 1000);
    return () => clearInterval(interval);
  }, [isAllComplete, isBackendFailed]);

  const elapsedSeconds = useMemo(() => {
    return getMigrationElapsedSeconds(migrationJob, localTick, startTime);
  }, [migrationJob, localTick, startTime]);

  const formattedElapsed = useMemo(() => {
    const mins = Math.floor(elapsedSeconds / 60);
    const secs = elapsedSeconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }, [elapsedSeconds]);

  // Raw log strings from backend migration_log, props, or report
  const rawLogStrings = useMemo(() => {
    const jobLogs = Array.isArray(migrationJob?.migration_log) ? migrationJob.migration_log : [];
    const bLogs = Array.isArray(backendLogs) ? backendLogs : [];
    if (jobLogs.length >= bLogs.length && jobLogs.length > 0) {
      return jobLogs;
    }
    if (bLogs.length > 0) {
      return bLogs;
    }
    return [];
  }, [migrationJob, backendLogs]);

  // Parsed structured logs
  const logs = useMemo(() => {
    if (rawLogStrings.length > 0) {
      return parseBackendLogs(rawLogStrings, migrationState, activeStep);
    }
    return generateStepLogs(activeStep, migrationState);
  }, [rawLogStrings, migrationState, activeStep]);

  // Visible logs filtered by selected step
  const visibleLogs = useMemo(() => {
    if (!hasUserSelectedStepManually) {
      return logs;
    }
    const stepFiltered = logs.filter((log) => log.stepId === selectedStepId);
    if (stepFiltered.length > 0) {
      return stepFiltered;
    }
    return logs;
  }, [logs, selectedStepId, hasUserSelectedStepManually]);

  // Smart Scroll Position Detection & Auto-Scroll
  const handleLogsScroll = () => {
    const el = logsContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const isUp = distanceFromBottom > 45;
    setIsUserScrolledUp(isUp);
    if (!isUp) {
      setHasNewLogsBelow(false);
    }
  };

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    const el = logsContainerRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior });
      setHasNewLogsBelow(false);
      setIsUserScrolledUp(false);
    }
  };

  useEffect(() => {
    if (isUserScrolledUp) {
      setHasNewLogsBelow(true);
    } else {
      const el = logsContainerRef.current;
      if (el) {
        el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      }
    }
  }, [visibleLogs, isUserScrolledUp]);

  // Clear visible logs for the selected step
  const handleClearLogs = () => {
    setIsUserScrolledUp(false);
    setHasNewLogsBelow(false);
  };

  // Activity headlines & descriptions
  const currentStepDef = activeStep <= 6 ? MIGRATION_STEPS_CONFIG[activeStep - 1] : null;

  const activityHeadline = useMemo(() => {
    if (isBackendFailed) return "Migration failed";
    if (isAllComplete) return "Migration completed";
    return (
      migrationJob?.current_stage_name ||
      migrationJob?.current_step ||
      currentStepDef?.activityTitle ||
      "Processing migration..."
    );
  }, [isBackendFailed, isAllComplete, migrationJob?.current_stage_name, migrationJob?.current_step, currentStepDef]);

  const activityDescription = useMemo(() => {
    if (isBackendFailed) {
      return displayError(migrationJob?.error_message || "An error occurred during the migration process.");
    }
    if (isAllComplete) return "Your application has been successfully modernized.";
    return currentStepDef ? currentStepDef.activitySubtitle(migrationState) : "Please wait while we process your data.";
  }, [isBackendFailed, isAllComplete, currentStepDef, migrationState, migrationJob?.error_message]);

  // Dynamic data-driven steps for MigrationStepper
  const migrationSteps = useMemo<StepperStepItem[]>(() => {
    return MIGRATION_STEPS_CONFIG.map((step) => ({
      id: step.id,
      stepId: step.stepId,
      title: step.title,
      description: step.description,
      icon: step.icon,
      status: stepStates[step.id] || "pending",
    }));
  }, [stepStates]);

  return (
    <div className="migration-modern-layout">
      {/* ========================================================
          LEFT COLUMN: MIGRATION WORKFLOW CARD
          ======================================================== */}
      <div className="migration-workflow-card" ref={workflowCardRef}>
        {/* Header Section */}
        <div className="migration-card-header">
          <h1 className="migration-title-row">
            <span className="migration-sparkle-icon">✦</span>
            <span className="migration-title-action">Modernizing</span>{" "}
            <span className="migration-title-project">{migrationState.projectName}</span>
          </h1>

          <div className="migration-version-badge">
            <span className="v-part">Java {migrationState.sourceJavaVersion}</span>
            <span className="v-arrow">→</span>
            <span className="v-part">Java {migrationState.targetJavaVersion}</span>
          </div>

          <p className="migration-header-lead">
            We&apos;re migrating your project to a better, modern version.
            <br />
            Please wait while we process your data.
          </p>
        </div>

        {/* 6 Migration Steps Vertical Stepper Component */}
        <MigrationStepper
          steps={migrationSteps}
          currentStep={activeStep}
          selectedStepId={selectedStepId}
          onStepClick={handleSelectStep}
        />

        {/* Dynamic Progress Bar */}
        <div className="migration-progress-section">
          <div className="migration-progress-track">
            <div
              className="migration-progress-bar"
              style={{ width: `${progressPercent}%` }}
            >
              <div className="progress-shimmer" />
            </div>
          </div>
          <div className="migration-progress-number">
            {progressPercent}%
          </div>
        </div>

        {/* Current Activity Card */}
        <div className={`migration-activity-card ${isAllComplete ? "is-complete" : isBackendFailed ? "is-failed" : ""}`}>
          <div className="activity-icon-wrap">
            {isAllComplete ? (
              <div className="activity-check-circle">
                <FaCheck size={14} color="#16a34a" />
              </div>
            ) : isBackendFailed ? (
              <div className="activity-fail-circle">
                <FaTimes size={14} color="#dc2626" />
              </div>
            ) : (
              <div className="activity-spinner" />
            )}
          </div>

          <div className="activity-text-wrap">
            <div className="activity-title">{activityHeadline}</div>
            <div className="activity-desc-row">
              <span className="activity-subtitle">{activityDescription}</span>
              {elapsedSeconds > 0 && (
                <span className="activity-timer-pill">
                  • Elapsed: <strong>{formattedElapsed}</strong>
                </span>
              )}
              {isAllComplete && redirectCountdown !== null && redirectCountdown > 0 && (
                <span className="activity-redirect-pill">
                  • Redirecting to Results in <strong>{redirectCountdown}s</strong>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Actions Row when Complete or Failed */}
        {isAllComplete && onViewReport && (
          <div className="migration-complete-action-bar">
            {redirectCountdown !== null && redirectCountdown > 0 && (
              <div className="migration-countdown-badge" role="status" aria-live="polite">
                <span className="migration-countdown-pulse" />
                <span className="migration-countdown-text">
                  Redirecting to Results in {redirectCountdown} second{redirectCountdown === 1 ? "" : "s"}...
                </span>
              </div>
            )}
            <button
              type="button"
              className="migration-view-report-btn"
              onClick={navigateToResults}
              title="Click to view migration report immediately"
            >
              <span>View Migration Report</span>
            </button>
          </div>
        )}

        {isBackendFailed && onRetry && (
          <div className="migration-retry-action-bar">
            <button
              type="button"
              className="migration-retry-btn"
              onClick={onRetry}
            >
              <FaRedo size={12} />
              <span>Retry Migration</span>
            </button>
          </div>
        )}
      </div>

      {/* ========================================================
          RIGHT COLUMN: LIVE MIGRATION LOGS PANEL (SCROLL DOWN BOX)
          ======================================================== */}
      <div
        className="migration-logs-card"
        style={
          stepperHeight
            ? {
                height: `${stepperHeight}px`,
                maxHeight: `${stepperHeight}px`,
              }
            : undefined
        }
      >
        {/* Terminal Header */}
        <div className="logs-header">
          <div className="logs-header-title-group">
            <div className="terminal-icon-box">
              <FaTerminal size={14} color="#38bdf8" />
            </div>
            <div className="logs-header-text">
              <div className="logs-title">Live Migration Logs</div>
              <div className="logs-subtitle">Real-time execution logs.</div>
            </div>
          </div>

          <button
            type="button"
            className="clear-logs-btn"
            onClick={handleClearLogs}
            title="Clear logs window"
          >
            <FaEraser size={12} />
            <span>Clear Logs</span>
          </button>
        </div>

        {/* Terminal Logs Content */}
        <div
          className="logs-body"
          ref={logsContainerRef}
          onScroll={handleLogsScroll}
        >
          {visibleLogs.length === 0 ? (
            <div className="logs-empty-state">
              <span className="empty-cursor">_</span> Waiting for process logs...
            </div>
          ) : (
            visibleLogs.map((log) => {
              const hasSource = Boolean(log.sourceReference);
              const isClickable =
                Boolean(log.clickable) ||
                Boolean(log.action) ||
                hasSource ||
                log.category === "sonarqube" ||
                log.category === "fossa" ||
                log.category === "junit" ||
                log.category === "deprecation" ||
                log.category === "migration-report";

              const isSelected = selectedLogId === log.id;

              // Action label on hover
              let actionLabel = "→";
              if (log.category === "sonarqube") actionLabel = "SonarQube →";
              else if (log.category === "fossa") actionLabel = "FOSSA →";
              else if (log.category === "junit") actionLabel = "JUnit →";
              else if (log.category === "deprecation") actionLabel = "Deprecation →";
              else if (log.category === "migration-report") actionLabel = "View Report →";
              else if (hasSource && log.sourceReference) {
                actionLabel = `${log.sourceReference.fileName}${
                  log.sourceReference.startLine ? `:${log.sourceReference.startLine}` : ""
                } →`;
              }

              return (
                <div
                  key={log.id}
                  className={`log-line line-${log.type.toLowerCase()} ${
                    isClickable ? "is-clickable-log" : ""
                  } ${isSelected ? "is-selected-log" : ""}`}
                  onClick={isClickable ? () => handleLogClick(log) : undefined}
                  role={isClickable ? "button" : undefined}
                  tabIndex={isClickable ? 0 : undefined}
                  onKeyDown={
                    isClickable
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            handleLogClick(log);
                          }
                        }
                      : undefined
                  }
                  title={
                    isClickable
                      ? `Click to view details for ${log.category || log.message}`
                      : undefined
                  }
                >
                  <span className={`log-bullet bullet-${log.type.toLowerCase()}`}>●</span>
                  <span className="log-text">{log.message}</span>
                  {isClickable && (
                    <span className="log-action-arrow">
                      {actionLabel}
                    </span>
                  )}
                </div>
              );
            })
          )}
          <div ref={logsEndRef} style={{ height: 1 }} />

          {/* Floating New Logs indicator */}
          {hasNewLogsBelow && (
            <button
              type="button"
              className="new-logs-indicator"
              onClick={() => scrollToBottom("smooth")}
              title="Scroll to latest log"
            >
              ↓ New logs below
            </button>
          )}
        </div>
      </div>

      {/* Dynamic Reusable Source Code Viewer Modal */}
      <SourceCodeViewerModal
        isOpen={Boolean(activeSourceRef)}
        onClose={() => setActiveSourceRef(null)}
        sourceRef={activeSourceRef}
      />

      {/* Dynamic Quality Check Details Modal (SonarQube, FOSSA, JUnit, Deprecation) */}
      <QualityCheckDetailsModal
        isOpen={Boolean(activeQualityCheck)}
        onClose={() => setActiveQualityCheck(null)}
        category={activeQualityCheck?.category || "sonarqube"}
        logMessage={activeQualityCheck?.logMessage}
        migrationJob={migrationJob}
        migrationState={migrationState}
        fossaResult={fossaResult}
        onOpenSourceCode={(ref) => setActiveSourceRef(ref)}
        onViewReport={navigateToResults}
      />
    </div>
  );
}
