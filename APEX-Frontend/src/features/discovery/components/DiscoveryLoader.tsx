import React from "react";
import {
  FaFolder,
  FaCoffee,
  FaProjectDiagram,
  FaCube,
  FaCheckCircle,
  FaClock,
  FaRegClock,
  FaFileAlt,
  FaArrowRight,
} from "react-icons/fa";
import type { DiscoveryStageState } from "../hooks/useDiscoveryState";

interface DiscoveryLoaderProps {
  title?: string;
  subtitle?: string;
  elapsedLabel?: string | null;
  elapsedSeconds?: number;
  compact?: boolean;
  stages?: DiscoveryStageState[];
  currentStepDetail?: string;
  progressPercent?: number;
}

interface ScanDefinition {
  id: "repository_scan" | "java_version_scan" | "dependencies_scan" | "framework_scan";
  label: string;
  subtitle: string;
  icon: React.ReactNode;
  subtasks: string[];
  calloutTitle: string;
  calloutDescription: string;
}

const SCANS_CONFIG: ScanDefinition[] = [
  {
    id: "repository_scan",
    label: "Repository Scan",
    subtitle: "Analyzing repository structure, files, and configuration.",
    icon: <FaFolder />,
    subtasks: [
      "Scan repository structure",
      "Identify source files",
      "Detect modules and packages",
      "Analyze configuration files",
      "Repository metadata extraction",
    ],
    calloutTitle: "Scanning repository structure...",
    calloutDescription: "Please wait while we analyze the repository structure and files.",
  },
  {
    id: "java_version_scan",
    label: "Java Version Scan",
    subtitle: "Detecting Java version and compatible versions.",
    icon: <FaCoffee />,
    subtasks: [
      "Inspect build configuration (pom.xml / build.gradle)",
      "Detect source and target Java bytecode versions",
      "Analyze compiler plugins & toolchain settings",
      "Evaluate modern Java LTS target compatibility",
    ],
    calloutTitle: "Detecting Java version & compiler settings...",
    calloutDescription: "Inspecting bytecode version, build plugins, and compatibility matrix.",
  },
  {
    id: "dependencies_scan",
    label: "Dependencies Scan",
    subtitle: "Scanning all project dependencies.",
    icon: <FaProjectDiagram />,
    subtasks: [
      "Parse direct & transitive dependency trees",
      "Analyze third-party libraries & versions",
      "Identify deprecated or obsolete dependencies",
      "Check security CVEs and modern replacements",
    ],
    calloutTitle: "Scanning project dependencies...",
    calloutDescription: "Evaluating libraries, frameworks, and transitive dependency trees.",
  },
  {
    id: "framework_scan",
    label: "Framework Scan",
    subtitle: "Detecting frameworks and their versions.",
    icon: <FaCube />,
    subtasks: [
      "Identify core frameworks (Spring / Jakarta / JEE)",
      "Detect ORM & database drivers (Hibernate, JPA, JDBC)",
      "Detect web and REST service layers",
      "Assess Spring Boot & microservice readiness",
    ],
    calloutTitle: "Detecting frameworks & service fit...",
    calloutDescription: "Analyzing framework annotations, configuration files, and service patterns.",
  },
];

function CircularProgressIndicator({ percent, size = 66, strokeWidth = 5 }: { percent: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percent / 100) * circumference;

  return (
    <div className="discovery-circular-progress" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          className="discovery-circular-bg"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
        />
        <circle
          className="discovery-circular-fg"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="discovery-circular-text">{percent}%</div>
    </div>
  );
}

export function DiscoveryLoader({
  title = "Analyzing your repository",
  subtitle = "Scanning repository structure, Java version, dependencies, and frameworks to build a comprehensive analysis.",
  elapsedLabel,
  elapsedSeconds = 0,
  compact = false,
  stages,
  currentStepDetail,
  progressPercent: customProgressPercent,
}: DiscoveryLoaderProps) {
  // Map stages if passed from backend/state
  const repoStage = stages?.find((s) => s.id === "repository_map");
  const prevStage = stages?.find((s) => s.id === "preview_signals");
  const depStage = stages?.find((s) => s.id === "dependency_graph");
  const fitStage = stages?.find((s) => s.id === "service_fit");

  const allStagesDone = Boolean(stages && stages.length > 0 && stages.every((s) => s.status === "complete"));

  // Determine status & percentage for each of the 4 scans
  // Scan 0: Repository Scan
  const isRepoComplete = allStagesDone || repoStage?.status === "complete";
  const isRepoActive = !isRepoComplete && (repoStage?.status === "in_progress" || (!stages && elapsedSeconds < 0.7));

  // Scan 1: Java Version Scan
  const isJavaComplete = allStagesDone || prevStage?.status === "complete";
  const isJavaActive = !isJavaComplete && (prevStage?.status === "in_progress" || (!stages && elapsedSeconds >= 0.7 && elapsedSeconds < 1.4) || isRepoComplete);

  // Scan 2: Dependencies Scan
  const isDepComplete = allStagesDone || depStage?.status === "complete";
  const isDepActive = !isDepComplete && (depStage?.status === "in_progress" || (!stages && elapsedSeconds >= 1.4 && elapsedSeconds < 2.1) || isJavaComplete);

  // Scan 3: Framework Scan
  const isFrameworkComplete = allStagesDone || fitStage?.status === "complete";
  const isFrameworkActive = !isFrameworkComplete && (fitStage?.status === "in_progress" || (!stages && elapsedSeconds >= 2.1) || isDepComplete);

  // Determine active scan index (0 to 3)
  let activeScanIndex = 0;
  if (allStagesDone || isFrameworkComplete) {
    activeScanIndex = 3;
  } else if (isFrameworkActive) {
    activeScanIndex = 3;
  } else if (isDepActive) {
    activeScanIndex = 2;
  } else if (isJavaActive) {
    activeScanIndex = 1;
  } else {
    activeScanIndex = 0;
  }

  // Calculate dynamic scan progress percentages
  const getScanPercent = (idx: number, isComplete: boolean, isActive: boolean) => {
    if (isComplete || allStagesDone) return 100;
    if (!isActive) return 0;
    const stageElapsed = Math.max(0, elapsedSeconds - idx * 0.7);
    return Math.min(95, Math.max(30, Math.round(40 + Math.min(55, stageElapsed * 45))));
  };

  const scanStates = SCANS_CONFIG.map((scan, idx) => {
    const isComplete =
      idx === 0 ? isRepoComplete : idx === 1 ? isJavaComplete : idx === 2 ? isDepComplete : isFrameworkComplete;
    const isActive =
      idx === 0 ? isRepoActive : idx === 1 ? isJavaActive : idx === 2 ? isDepActive : isFrameworkActive;

    const status: "completed" | "in_progress" | "pending" = isComplete
      ? "completed"
      : isActive
        ? "in_progress"
        : "pending";

    const percent = getScanPercent(idx, isComplete, isActive);
    return {
      ...scan,
      status,
      percent,
    };
  });

  const activeScan = scanStates[activeScanIndex];

  // Calculate overall progress percentage
  const completedScansCount = scanStates.filter((s) => s.status === "completed").length;
  let calculatedOverall = 0;
  if (allStagesDone || completedScansCount === 4) {
    calculatedOverall = 100;
  } else {
    const baseProgress = completedScansCount * 25;
    const activePercent = activeScan ? activeScan.percent : 0;
    calculatedOverall = Math.min(99, Math.round(baseProgress + (activePercent / 100) * 25));
  }

  const finalOverallPercent =
    customProgressPercent !== undefined ? customProgressPercent : calculatedOverall;

  // Calculate active subtask index within active scan
  const activeSubtasks = activeScan.subtasks;
  const activeSubtaskIdx =
    activeScan.status === "completed"
      ? activeSubtasks.length - 1
      : Math.min(activeSubtasks.length - 1, Math.floor((activeScan.percent / 100) * activeSubtasks.length));

  return (
    <div className={`discovery-analysis-container${compact ? " is-compact" : ""}`}>
      {/* Top Header Card Info */}
      <div className="discovery-analysis-header">
        <div className="discovery-loader-eyebrow">
          Repository Intelligence Engine
          {elapsedLabel ? <span className="discovery-loader-timer">{elapsedLabel}</span> : null}
        </div>
        <div className="discovery-loader-title">{title}</div>
        <div className="discovery-loader-subtitle">{subtitle}</div>
      </div>

      {/* Horizontal Flow Row */}
      <div className="discovery-flow-row">
        <CircularProgressIndicator percent={finalOverallPercent} />

        <div className="discovery-flow-cards-wrap">
          {scanStates.map((scan, idx) => {
            const isLast = idx === scanStates.length - 1;
            const badgeLabel =
              scan.status === "completed"
                ? "COMPLETED"
                : scan.status === "in_progress"
                  ? "IN PROGRESS"
                  : "PENDING";

            return (
              <React.Fragment key={scan.id}>
                <div className={`discovery-flow-card is-${scan.status}`}>
                  <div className="discovery-flow-card-icon">{scan.icon}</div>
                  <div className="discovery-flow-card-content">
                    <div className="discovery-flow-card-top">
                      <span className="discovery-flow-card-title">{scan.label}</span>
                      <span className={`discovery-flow-badge is-${scan.status}`}>{badgeLabel}</span>
                    </div>
                    <div className="discovery-flow-card-subtitle">{scan.subtitle}</div>
                  </div>
                </div>

                {!isLast && (
                  <div className="discovery-flow-arrow" aria-hidden="true">
                    <FaArrowRight />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Progressive Detailed Scan Panel */}
      <div className="discovery-detail-panel">
        <div className="discovery-detail-header">
          <div className="discovery-detail-header-left">
            <div className="discovery-detail-icon">{activeScan.icon}</div>
            <div className="discovery-detail-titles">
              <h3 className="discovery-detail-title">{activeScan.label}</h3>
              <p className="discovery-detail-subtitle">{activeScan.subtitle}</p>
            </div>
          </div>
          <div className="discovery-detail-pct-badge">{activeScan.percent}%</div>
        </div>

        <div className="discovery-detail-body">
          {/* Subtasks list */}
          <div className="discovery-subtasks-list">
            {activeScan.subtasks.map((taskName, idx) => {
              let taskStatus: "completed" | "in_progress" | "pending" = "pending";
              if (activeScan.status === "completed") {
                taskStatus = "completed";
              } else if (activeScan.status === "in_progress") {
                if (idx < activeSubtaskIdx) taskStatus = "completed";
                else if (idx === activeSubtaskIdx) taskStatus = "in_progress";
                else taskStatus = "pending";
              }

              return (
                <div key={`${taskName}-${idx}`} className={`discovery-subtask-row is-${taskStatus}`}>
                  <div className="discovery-subtask-left">
                    {taskStatus === "completed" ? (
                      <FaCheckCircle className="discovery-subtask-icon is-completed" />
                    ) : taskStatus === "in_progress" ? (
                      <FaClock className="discovery-subtask-icon is-in-progress" />
                    ) : (
                      <FaRegClock className="discovery-subtask-icon is-pending" />
                    )}
                    <span className="discovery-subtask-name">{taskName}</span>
                  </div>
                  <span className={`discovery-subtask-badge is-${taskStatus}`}>
                    {taskStatus === "completed"
                      ? "Completed"
                      : taskStatus === "in_progress"
                        ? "In Progress"
                        : "Pending"}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Callout Detail Box */}
          <div className="discovery-callout-box">
            <div className="discovery-callout-icon-wrap">
              <FaFileAlt className="discovery-callout-icon" />
            </div>
            <div className="discovery-callout-content">
              <div className="discovery-callout-title">
                {activeScan.status === "completed"
                  ? `${activeScan.label} Complete`
                  : `${activeScan.subtasks[activeSubtaskIdx]}...`}
              </div>
              <div className="discovery-callout-desc">
                {currentStepDetail || activeScan.calloutDescription}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
