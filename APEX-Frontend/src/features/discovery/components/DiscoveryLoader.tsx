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
      "Assess Spring Boot readiness",
      // "Assess Spring Boot & microservice readiness",
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
  const isRepoComplete = allStagesDone || repoStage?.status === "complete";
  const isJavaComplete = allStagesDone || prevStage?.status === "complete";
  const isDepComplete = allStagesDone || depStage?.status === "complete";
  const isFrameworkComplete = allStagesDone || fitStage?.status === "complete";

  // Determine active scan index based on real stage statuses or elapsed time pacing
  let activeScanIndex = 0;
  if (allStagesDone || isFrameworkComplete) {
    activeScanIndex = 3;
  } else if (fitStage?.status === "in_progress" || isDepComplete || elapsedSeconds >= 8.0) {
    activeScanIndex = 3;
  } else if (depStage?.status === "in_progress" || isJavaComplete || elapsedSeconds >= 5.0) {
    activeScanIndex = 2;
  } else if (prevStage?.status === "in_progress" || isRepoComplete || elapsedSeconds >= 2.5) {
    activeScanIndex = 1;
  } else {
    activeScanIndex = 0;
  }

  // Calculate dynamic scan progress percentages
  const getScanPercent = (idx: number, isComplete: boolean, isActive: boolean) => {
    if (isComplete || allStagesDone) return 100;
    if (!isActive) return 0;

    // Realistic stage start times (0s, 2.5s, 5.0s, 8.0s)
    const stageStart = idx === 0 ? 0 : idx === 1 ? 2.5 : idx === 2 ? 5.0 : 8.0;
    const stageElapsed = Math.max(0, elapsedSeconds - stageStart);

    if (idx < 3) {
      // Intermediate stages advance smoothly from 20% to ~88% over their allotted duration
      const duration = idx === 2 ? 3.0 : 2.5;
      const progressRatio = Math.min(1, stageElapsed / duration);
      return Math.min(88, Math.round(20 + progressRatio * 68));
    } else {
      // Framework Scan (runs until backend finishes):
      // Smoothly advance across subtasks without ever freezing at 95%/99%
      if (stageElapsed < 2.0) {
        return Math.round(15 + (stageElapsed / 2.0) * 10);
      } else if (stageElapsed < 4.5) {
        return Math.round(25 + ((stageElapsed - 2.0) / 2.5) * 25);
      } else if (stageElapsed < 7.5) {
        return Math.round(50 + ((stageElapsed - 4.5) / 3.0) * 25);
      } else {
        const extraTime = stageElapsed - 7.5;
        return Math.min(90, Math.round(75 + 15 * (1 - Math.exp(-extraTime / 8.0))));
      }
    }
  };

  const scanStates = SCANS_CONFIG.map((scan, idx) => {
    const isComplete =
      allStagesDone ||
      (idx === 3 ? isFrameworkComplete : idx < activeScanIndex);
    const isActive = !isComplete && idx === activeScanIndex;

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
  // 100% is reached ONLY when all discovery work has genuinely completed
  let calculatedOverall = 0;
  if (allStagesDone || isFrameworkComplete) {
    calculatedOverall = 100;
  } else {
    const baseProgress = activeScanIndex * 25;
    const activePercent = activeScan ? activeScan.percent : 0;
    calculatedOverall = Math.min(97, Math.max(1, Math.round(baseProgress + (activePercent / 100) * 25)));
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
                <div key={taskName} className={`discovery-subtask-row is-${taskStatus}`}>
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
