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

  // Calculate overall progress percentage (prefer backend real progress)
  let fallbackOverall = 0;
  if (allStagesDone) {
    fallbackOverall = 100;
  } else {
    // Smooth fallback curve if progress polling hasn't returned yet
    if (elapsedSeconds < 3.0) fallbackOverall = Math.round(5 + (elapsedSeconds / 3.0) * 10);
    else if (elapsedSeconds < 8.0) fallbackOverall = Math.round(15 + ((elapsedSeconds - 3.0) / 5.0) * 15);
    else if (elapsedSeconds < 16.0) fallbackOverall = Math.round(30 + ((elapsedSeconds - 8.0) / 8.0) * 25);
    else if (elapsedSeconds < 30.0) fallbackOverall = Math.round(55 + ((elapsedSeconds - 16.0) / 14.0) * 30);
    else {
      const extraTime = elapsedSeconds - 30.0;
      fallbackOverall = Math.min(98, Math.round(85 + 13 * (1 - Math.exp(-extraTime / 15.0))));
    }
  }

  const activeStage = stages?.find((s) => s.status === "in_progress");
  const polledProgressPercent = customProgressPercent !== undefined ? customProgressPercent : activeStage?.progressPercent;

  const finalOverallPercent =
    polledProgressPercent !== undefined ? polledProgressPercent : fallbackOverall;

  // Determine active scan index based on real stage statuses or progress percentage
  let activeScanIndex = 0;
  if (allStagesDone || finalOverallPercent >= 100) {
    activeScanIndex = 3;
  } else if (fitStage?.status === "in_progress" || finalOverallPercent >= 75) {
    activeScanIndex = 3;
  } else if (depStage?.status === "in_progress" || finalOverallPercent >= 50) {
    activeScanIndex = 2;
  } else if (prevStage?.status === "in_progress" || finalOverallPercent >= 25) {
    activeScanIndex = 1;
  } else {
    activeScanIndex = 0;
  }

  const isRepoComplete = allStagesDone || activeScanIndex > 0 || repoStage?.status === "complete";
  const isJavaComplete = allStagesDone || activeScanIndex > 1 || prevStage?.status === "complete";
  const isDepComplete = allStagesDone || activeScanIndex > 2 || depStage?.status === "complete";
  const isFrameworkComplete = allStagesDone || (activeScanIndex === 3 && finalOverallPercent >= 100) || fitStage?.status === "complete";

  // Calculate dynamic scan progress percentages strictly synchronized with overall percentage
  const getScanPercent = (idx: number, isComplete: boolean, isActive: boolean) => {
    if (isComplete || allStagesDone) return 100;
    if (!isActive) return 0;

    const stageRangeStart = idx * 25;
    const offset = Math.max(0, finalOverallPercent - stageRangeStart);
    return Math.min(99, Math.max(0, Math.round(offset * 4)));
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
        <div className="discovery-loader-eyebrow">Repository Intelligence Engine</div>
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
        </div>/

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
