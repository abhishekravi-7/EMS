import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  FaCheck,
  FaTimes,
  FaTerminal,
  FaEraser,
  FaTools,
  FaArrowRight,
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
  generateStepCompletionLog,
  generateFinalCompletionLog,
  STEP_NUMBER_TO_ID,
  type MigrationStepId,
  type MigrationLogEvent,
  type MigrationState,
  type SourceLocationReference,
} from "../utils/migrationStateModel";
import { SourceCodeViewerModal } from "./SourceCodeViewerModal";
import { QualityCheckDetailsModal } from "./QualityCheckDetailsModal";
import { MigrationStepper, type MigrationStepItem as StepperStepItem } from "./MigrationStepper";
import "./MigrationAnimationView.css";

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
  repoAnalysis?: any;
  codeChanges?: any[];
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
    title: "4. Quality check (Sonar, FOSSA, Unit check - JUnit)",
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
  // Step Engine & State Machine
  const [activeStep, setActiveStep] = useState<number>(1);
  const [selectedStepId, setSelectedStepId] = useState<MigrationStepId>("code-version-update");
  const [hasUserSelectedStepManually, setHasUserSelectedStepManually] = useState<boolean>(false);

  const [stepStates, setStepStates] = useState<Record<number, "pending" | "in_progress" | "completed" | "failed">>({
    1: "in_progress",
    2: "pending",
    3: "pending",
    4: "pending",
    5: "pending",
    6: "pending",
  });

  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [logs, setLogs] = useState<MigrationLogEvent[]>([]);
  const [activeSourceRef, setActiveSourceRef] = useState<SourceLocationReference | null>(null);
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [activeQualityCheck, setActiveQualityCheck] = useState<{
    category: string;
    logMessage?: string;
  } | null>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const isMountedRef = useRef(true);

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

  // When activeStep advances, automatically follow if user hasn't clicked a step manually
  useEffect(() => {
    if (!hasUserSelectedStepManually && activeStep <= 6) {
      const autoStepId = STEP_NUMBER_TO_ID[activeStep];
      if (autoStepId) {
        setSelectedStepId(autoStepId);
      }
    }
  }, [activeStep, hasUserSelectedStepManually]);

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

  // Derive visible logs dynamically from central migration log state
  const visibleLogs = useMemo(() => {
    return logs.filter((log) => log.stepId === selectedStepId);
  }, [logs, selectedStepId]);

  // Auto-scroll state
  const [isUserScrolledUp, setIsUserScrolledUp] = useState(false);
  const [hasNewLogsBelow, setHasNewLogsBelow] = useState(false);

  // Live Elapsed Timer
  const [startTime] = useState<number>(() => Date.now());
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);

  // 5-Second Automatic Navigation State & Refs
  const [redirectCountdown, setRedirectCountdown] = useState<number | null>(null);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasStartedCountdownRef = useRef<boolean>(false);
  const onViewReportRef = useRef(onViewReport);
  onViewReportRef.current = onViewReport;

  const onMigrationCompleteRef = useRef(onMigrationComplete);
  onMigrationCompleteRef.current = onMigrationComplete;

  // Dedicated navigation function using existing router mechanism
  const navigateToResults = () => {
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }
    onMigrationCompleteRef.current?.();
    onViewReportRef.current?.();
  };

  // Backend Status Detection & Genuine Migration Status
  const backendStatus = (migrationJob?.status || "").toLowerCase();
  const isBackendFailed = backendStatus === "failed" || Boolean(migrationJob?.error_message);
  const isBackendCompleted = backendStatus === "completed";

  // Check if all 6 steps are genuinely completed in the stepper
  const allStepsCompleted = useMemo(() => {
    return (
      stepStates[1] === "completed" &&
      stepStates[2] === "completed" &&
      stepStates[3] === "completed" &&
      stepStates[4] === "completed" &&
      stepStates[5] === "completed" &&
      stepStates[6] === "completed"
    );
  }, [stepStates]);

  // Genuine migration status determination
  const migrationStatus: "pending" | "in_progress" | "completed" | "failed" = useMemo(() => {
    if (isBackendFailed) return "failed";
    if (migrationJob) {
      if (backendStatus === "completed") return "completed";
      if (backendStatus === "failed") return "failed";
      return "in_progress";
    }
    // Offline / client simulation mode: genuinely completed only when all 6 steps finished and progress 100%
    if (activeStep > 6 && allStepsCompleted && progressPercent >= 100) {
      return "completed";
    }
    return "in_progress";
  }, [isBackendFailed, migrationJob, backendStatus, activeStep, allStepsCompleted, progressPercent]);

  // Overall Genuine Completion Condition:
  // Step 1..6 = completed, overallProgress = 100, migrationStatus = "completed", !failed
  const isAllComplete = useMemo(() => {
    return (
      allStepsCompleted &&
      progressPercent >= 100 &&
      migrationStatus === "completed" &&
      !isBackendFailed
    );
  }, [allStepsCompleted, progressPercent, migrationStatus, isBackendFailed]);

  const isFinished = isAllComplete || (isBackendCompleted && allStepsCompleted);

  // Single Completion Countdown Timer (5 seconds)
  useEffect(() => {
    // ONLY start countdown when all completion criteria are strictly met
    if (!isAllComplete) return;
    if (hasStartedCountdownRef.current) return;

    hasStartedCountdownRef.current = true;
    setRedirectCountdown(5);

    countdownTimerRef.current = setInterval(() => {
      setRedirectCountdown((prev) => {
        if (prev === null) return null;
        if (prev <= 1) {
          if (countdownTimerRef.current) {
            clearInterval(countdownTimerRef.current);
            countdownTimerRef.current = null;
          }
          navigateToResults();
          return 0;
        }
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

  const migrationStateRef = useRef(migrationState);
  migrationStateRef.current = migrationState;

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (isFinished || isBackendFailed) return;
    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [isFinished, isBackendFailed, startTime]);

  const formattedElapsed = useMemo(() => {
    const mins = Math.floor(elapsedSeconds / 60);
    const secs = elapsedSeconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }, [elapsedSeconds]);

  // Progressive Log & Step Execution State Machine
  const activeStepRef = useRef(activeStep);
  activeStepRef.current = activeStep;

  useEffect(() => {
    if (isBackendFailed) {
      setStepStates((prev) => ({
        ...prev,
        [activeStepRef.current]: "failed",
      }));
      setLogs((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          step: activeStepRef.current,
          stepId: STEP_NUMBER_TO_ID[activeStepRef.current] || "code-version-update",
          message: `ERROR  ${migrationJob?.error_message || "Migration process encountered an unrecoverable failure."}`,
          type: "ERROR",
        },
      ]);
      return;
    }

    if (activeStep > 6) {
      setProgressPercent(100);
      onMigrationCompleteRef.current?.();
      setStepStates({
        1: "completed",
        2: "completed",
        3: "completed",
        4: "completed",
        5: "completed",
        6: "completed",
      });
      return;
    }

    const currentStepConfig = MIGRATION_STEPS_CONFIG[activeStep - 1];
    if (!currentStepConfig) return;

    // Dynamically produce the step logs from migrationState (Single Source of Truth)
    const currentState = migrationStateRef.current;
    const stepEvents = generateStepLogs(activeStep, currentState);
    let lineIndex = 0;
    let cancelled = false;

    const prevTarget = activeStep === 1 ? 0 : MIGRATION_STEPS_CONFIG[activeStep - 2].targetProgress;
    const currentTarget = currentStepConfig.targetProgress;
    const progressRange = currentTarget - prevTarget;

    // Step lines appear progressively like a real-time enterprise terminal
    const intervalTime = 700;

    const timer = setInterval(() => {
      if (cancelled || !isMountedRef.current) return;

      if (lineIndex < stepEvents.length) {
        const newLog = stepEvents[lineIndex];
        setLogs((prev) => [...prev, newLog]);

        const fraction = (lineIndex + 1) / stepEvents.length;
        const nextProg = Math.min(
          currentTarget,
          Math.max(prevTarget + Math.round(fraction * progressRange), 0)
        );
        setProgressPercent((prevProg) => Math.max(prevProg, nextProg));

        lineIndex++;
      } else {
        clearInterval(timer);

        // Step completion log event
        const compLog = generateStepCompletionLog(activeStep, currentState);
        setLogs((prev) => [...prev, compLog]);
        setProgressPercent(currentTarget);

        const nextStep = activeStep + 1;
        setStepStates((prev) => ({
          ...prev,
          [activeStep]: "completed",
          ...(nextStep <= 6 ? { [nextStep]: "in_progress" } : {}),
        }));

        if (nextStep <= 6) {
          setTimeout(() => {
            if (!cancelled && isMountedRef.current) {
              setActiveStep(nextStep);
            }
          }, 900);
        } else {
          setTimeout(() => {
            if (!cancelled && isMountedRef.current) {
              setActiveStep(7);
              setProgressPercent(100);
              onMigrationCompleteRef.current?.();
              const finalLog = generateFinalCompletionLog();
              setLogs((prev) => [...prev, finalLog]);
            }
          }, 1000);
        }
      }
    }, intervalTime);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeStep, isBackendFailed]);

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

  // Clear visible logs for the selected step without resetting migration results or progress
  const handleClearLogs = () => {
    setLogs((prev) => prev.filter((log) => log.stepId !== selectedStepId));
    setHasNewLogsBelow(false);
  };

  // Activity headlines & descriptions
  const currentStepDef = activeStep <= 6 ? MIGRATION_STEPS_CONFIG[activeStep - 1] : null;

  const activityHeadline = useMemo(() => {
    if (isBackendFailed) return "Migration failed";
    if (isAllComplete) return "Migration completed";
    if (allStepsCompleted && progressPercent >= 100) return "Finalizing migration...";
    return currentStepDef?.activityTitle || "Processing migration...";
  }, [isBackendFailed, isAllComplete, allStepsCompleted, progressPercent, currentStepDef]);

  const activityDescription = useMemo(() => {
    if (isBackendFailed) return migrationJob?.error_message || "An error occurred during the migration process.";
    if (isAllComplete) return "Your application has been successfully modernized.";
    if (allStepsCompleted && progressPercent >= 100) return "Waiting for backend services to confirm final report generation.";
    return currentStepDef ? currentStepDef.activitySubtitle(migrationState) : "Please wait while we process your data.";
  }, [isBackendFailed, isAllComplete, allStepsCompleted, progressPercent, currentStepDef, migrationState, migrationJob?.error_message]);

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
