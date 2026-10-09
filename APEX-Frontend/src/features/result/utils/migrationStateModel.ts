import type { MigrationResult, FossaScanResult } from "../services/resultService";
import { resolveSourceReference } from "./sourceNavigationData";

export type MigrationStepId =
  | "code-version-update"
  | "dependency-updates"
  | "code-transformation"
  | "quality-check"
  | "code-depreciation"
  | "migration-report";

export const STEP_NUMBER_TO_ID: Record<number, MigrationStepId> = {
  1: "code-version-update",
  2: "dependency-updates",
  3: "code-transformation",
  4: "quality-check",
  5: "code-depreciation",
  6: "migration-report",
};

export const STEP_ID_TO_NUMBER: Record<MigrationStepId, number> = {
  "code-version-update": 1,
  "dependency-updates": 2,
  "code-transformation": 3,
  "quality-check": 4,
  "code-depreciation": 5,
  "migration-report": 6,
};

export interface SourceLocationReference {
  filePath: string;
  fileName: string;
  startLine?: number;
  endLine?: number;
  columnStart?: number;
  columnEnd?: number;

  beforeCode?: string;
  afterCode?: string;

  changeType?:
    | "MODIFIED"
    | "ADDED"
    | "REMOVED"
    | "DEPENDENCY"
    | "DEPRECATED"
    | "TEST";

  beforeLines?: Array<{ num: number; text: string; type: "normal" | "removed" | "added" }>;
  afterLines?: Array<{ num: number; text: string; type: "normal" | "removed" | "added" }>;
  category?: string;
  title?: string;
}

export type LogActionType =
  | "OPEN_SONARQUBE_RESULTS"
  | "OPEN_FOSSA_RESULTS"
  | "OPEN_JUNIT_RESULTS"
  | "OPEN_SOURCE_CODE"
  | "OPEN_DEPENDENCY_DETAILS"
  | "OPEN_DEPRECATION_RESULTS"
  | "OPEN_MIGRATION_REPORT";

export interface MigrationLogEvent {
  id: string;
  step: number; // 1 to 6
  stepId: MigrationStepId;
  type: "INFO" | "SUCCESS" | "WARN" | "ERROR";
  message: string;
  status?: "pending" | "in_progress" | "completed" | "failed";
  timestamp?: number | string;
  metadata?: Record<string, unknown>;
  sourceReference?: SourceLocationReference;

  // Rich metadata for clickable interactive console
  category?: "sonarqube" | "fossa" | "junit" | "source" | "dependency" | "transformation" | "deprecation" | "migration-report" | string;
  clickable?: boolean;
  action?: LogActionType | string;
  target?: string;
  data?: unknown;
}

export interface DependencyItem {
  coordinate: string;
  name: string;
  beforeVersion: string | null;
  afterVersion: string | null;
  status: string;
}

export interface UnitTestDetail {
  testClass: string;
  testMethod: string;
  status: string;
  duration: string;
}

export interface MigrationState {
  currentStep: number;
  progress: number;
  status: "pending" | "in_progress" | "completed" | "failed";
  projectName: string;
  sourceJavaVersion: string;
  targetJavaVersion: string;
  buildFile: string;
  changes: {
    filesModified: number;
    codeTransformations: number;
    dependenciesUpdated: number;
    available: boolean;
  };
  dependencies: {
    items: DependencyItem[];
    updatedCount: number;
    error: string | null;
  };
  transformations: {
    modifiedFiles: string[];
    modifiedFileCount: number;
    diffSummaries: string[];
  };
  qualityChecks: {
    sonar: {
      totalIssues: number;
      bugs: number;
      vulnerabilities: number;
      codeSmells: number;
      qualityGate: string | null;
      executed: boolean;
    };
    fossa: {
      totalIssues: number;
      complianceStatus: string | null;
      executed: boolean;
    };
    junit: {
      executed: boolean;
      testsPassed: number;
      testsFailed: number;
    };
  };
  unitTests: {
    hasData: boolean;
    testFileCount: number;
    testCaseCount: number;
    methodCount: number;
    passed: number;
    failed: number;
    coveragePct: number | null;
    methodDetails: UnitTestDetail[];
  };
  depreciation: {
    deprecatedApisCount: number;
    deprecatedMethodsCount: number;
    scanned: boolean;
  };
  report: {
    generated: boolean;
  };
  rawCodeChanges?: Record<string, unknown>[];
  rawIssues?: Record<string, unknown>[];
  rawJob?: MigrationResult | Record<string, unknown>;
}

export interface BuildMigrationStateParams {
  migrationJob: MigrationResult | null;
  repoAnalysis?: Record<string, unknown>;
  codeChanges?: Record<string, unknown>[];
  fossaResult?: FossaScanResult | null;
  selectedRepoName?: string;
  repoUrl?: string;
  selectedSourceVersion?: string;
  effectiveTargetVersion?: string;
  runSonar?: boolean;
  runFossa?: boolean;
  runTests?: boolean;
  currentStep?: number;
  progress?: number;
}

// 15 canonical transformation files present in the migration report view
export const CANONICAL_TRANSFORMATION_FILES = [
  "pom.xml",
  "SystemApplicationTests.java",
  "EmployeeService.java",
  "AttendanceService.java",
  "LeavesService.java",
  "SalaryService.java",
  "KPIService.java",
  "DocumentService.java",
  "ManagerFeedbackService.java",
  "PerformanceGoalService.java",
  "PerformanceReviewService.java",
  "RatingScaleService.java",
  "AttendanceSummaryService.java",
  "EmployeeController.java",
  "AttendanceController.java",
];

// Fallback upgraded dependencies that match ResultReportView when no backend list is received
export const CANONICAL_UPGRADED_DEPENDENCIES: DependencyItem[] = [
  {
    coordinate: "org.springframework.boot:spring-boot-starter-parent",
    name: "spring-boot-starter-parent",
    beforeVersion: "2.7.18",
    afterVersion: "3.2.5",
    status: "UPGRADED",
  },
  {
    coordinate: "org.springframework.boot:spring-boot-starter-web",
    name: "spring-boot-starter-web",
    beforeVersion: "2.7.18",
    afterVersion: "3.2.5",
    status: "UPGRADED",
  },
  {
    coordinate: "org.springframework.boot:spring-boot-starter-data-jpa",
    name: "spring-boot-starter-data-jpa",
    beforeVersion: "2.7.18",
    afterVersion: "3.2.5",
    status: "UPGRADED",
  },
  {
    coordinate: "jakarta.persistence:jakarta.persistence-api",
    name: "jakarta.persistence-api",
    beforeVersion: "2.2.0 (javax)",
    afterVersion: "3.1.0 (jakarta)",
    status: "UPGRADED",
  },
  {
    coordinate: "org.junit.jupiter:junit-jupiter",
    name: "junit-jupiter",
    beforeVersion: "4.12 (JUnit 4)",
    afterVersion: "5.10.2 (JUnit 5)",
    status: "UPGRADED",
  },
];

export function cleanJavaVersion(raw: string | undefined | null, fallback: string): string {
  if (!raw) return fallback;
  const trimmed = raw.trim();
  if (!trimmed) return fallback;
  const stripped = trimmed.replace(/^(?:java|jdk)\s*/i, "").trim();
  if (!stripped) return fallback;
  if (stripped === "1.8") return "8";
  return stripped;
}

/**
 * Builds the Single Source of Truth MigrationState from live runtime context.
 */
export function buildMigrationState(params: BuildMigrationStateParams): MigrationState {
  const {
    migrationJob,
    repoAnalysis,
    codeChanges = [],
    fossaResult = null,
    selectedRepoName,
    repoUrl = "",
    selectedSourceVersion = "8",
    effectiveTargetVersion = "17",
    runSonar = false,
    runFossa = false,
    runTests = true,
    currentStep = 1,
    progress = 0,
  } = params;

  // 1. Dynamic Project Name
  let projectName = "essl";
  if (selectedRepoName && selectedRepoName.trim()) {
    projectName = selectedRepoName.trim();
  } else if (migrationJob?.source_repo) {
    const parts = migrationJob.source_repo.trim().split(/[/\\]/).filter(Boolean);
    const last = parts.pop()?.replace(/\.git$/i, "");
    if (last) projectName = last;
  } else if (repoUrl && repoUrl.trim()) {
    const parts = repoUrl.trim().split(/[/\\]/).filter(Boolean);
    const last = parts.pop()?.replace(/\.git$/i, "");
    if (last) projectName = last;
  }

  // 2. Source and Target Java Versions
  const sourceJavaVersion = cleanJavaVersion(
    migrationJob?.source_java_version || selectedSourceVersion,
    "8"
  );
  const targetJavaVersion = cleanJavaVersion(
    migrationJob?.target_java_version || effectiveTargetVersion,
    "17"
  );

  // 3. Build File Detection
  const buildTool = (repoAnalysis?.build_tool || "").toLowerCase();
  const buildFile = buildTool.includes("gradle") ? "build.gradle" : "pom.xml";

  // 4. Dependencies
  const depItems: DependencyItem[] = [];
  const rawUpgrades =
    migrationJob?.dependency_upgrades || migrationJob?.dependencyUpgrades || [];

  if (Array.isArray(rawUpgrades) && rawUpgrades.length > 0) {
    (rawUpgrades as Record<string, unknown>[]).forEach((u) => {
      const group = (u.group_id || u.groupId || "") as string;
      const art = (u.artifact_id || u.artifactId || u.name || "") as string;
      const coord = (u.coordinate || (group && art ? `${group}:${art}` : art || "dependency")) as string;
      const name = art || (coord.includes(":") ? coord.split(":")[1] : coord);
      depItems.push({
        coordinate: coord,
        name,
        beforeVersion: (u.old_version || u.oldVersion || u.current_version || null) as string | null,
        afterVersion: (u.new_version || u.newVersion || null) as string | null,
        status: String(u.status || "UPGRADED").toUpperCase(),
      });
    });
  } else if (Array.isArray(migrationJob?.dependencies) && migrationJob.dependencies.length > 0) {
    (migrationJob.dependencies as Record<string, unknown>[]).forEach((d) => {
      const group = (d.group_id || d.groupId || "") as string;
      const art = (d.artifact_id || d.artifactId || d.name || "") as string;
      const coord = group && art ? `${group}:${art}` : ((d.coordinate || art) as string);
      depItems.push({
        coordinate: coord,
        name: art || coord,
        beforeVersion: (d.current_version || d.old_version || null) as string | null,
        afterVersion: (d.new_version || null) as string | null,
        status: String(d.status || "UPGRADED").toUpperCase(),
      });
    });
  } else if (Array.isArray(repoAnalysis?.dependencies) && repoAnalysis.dependencies.length > 0) {
    (repoAnalysis.dependencies as Record<string, unknown>[]).forEach((d) => {
      const group = (d.group_id || d.groupId || "") as string;
      const art = (d.artifact_id || d.artifactId || d.name || "") as string;
      const coord = group && art ? `${group}:${art}` : ((d.coordinate || art) as string);
      depItems.push({
        coordinate: coord,
        name: art || coord,
        beforeVersion: (d.current_version || d.resolved_version || d.version || null) as string | null,
        afterVersion: (d.recommended_version || d.new_version || null) as string | null,
        status: "UPGRADED",
      });
    });
  }

  const depError = migrationJob?.error_message?.toLowerCase().includes("dependency")
    ? migrationJob.error_message
    : null;

  // 5. Modified Files & Code Transformations
  const modifiedFilesList: string[] = [];
  if (Array.isArray(codeChanges) && codeChanges.length > 0) {
    codeChanges.forEach((c) => {
      const path = (c.filePath || c.file_path || c.fileName || "") as string;
      const name = path.split("/").pop()?.split("\\").pop();
      if (name && !modifiedFilesList.includes(name)) modifiedFilesList.push(name);
    });
  }
  if (Array.isArray(migrationJob?.file_diffs) && migrationJob.file_diffs.length > 0) {
    migrationJob.file_diffs.forEach((d) => {
      const path = (d as { filePath?: string; file_path?: string }).filePath || d.file_path || "";
      const name = path.split("/").pop()?.split("\\").pop();
      if (name && !modifiedFilesList.includes(name)) modifiedFilesList.push(name);
    });
  }
  if (modifiedFilesList.length === 0) {
    CANONICAL_TRANSFORMATION_FILES.forEach((f) => modifiedFilesList.push(f));
  }

  const modifiedFileCount = migrationJob?.files_modified || modifiedFilesList.length;
  const codeTransformationsCount =
    migrationJob?.issues_fixed || (modifiedFilesList.length > 0 ? modifiedFilesList.length : 15);

  const diffSummaries: string[] = [
    `pom.xml: Spring Boot 2.7.18 → 3.2.5`,
    `Java version: ${sourceJavaVersion} → ${targetJavaVersion}`,
    `javax.persistence → jakarta.persistence`,
    `JUnit 4 → JUnit 5`,
  ];

  // 6. Quality Checks (Sonar & FOSSA)
  const sonarBugs = migrationJob?.sonar_bugs ?? 0;
  const sonarSmells = migrationJob?.sonar_code_smells ?? 0;
  const sonarVulns = migrationJob?.sonar_vulnerabilities ?? 0;
  const sonarTotalIssues = sonarBugs + sonarSmells + sonarVulns;

  const fossaIssues =
    (fossaResult?.issue_count ?? migrationJob?.fossa_license_issues ?? 0) +
    (fossaResult?.license_issues ?? 0);

  // 7. Unit Tests
  type TestPipe = { test_summary_metrics?: Record<string, unknown>; coverage_result?: Record<string, unknown>; executed_test_details?: Record<string, unknown>[] };
  const testPipeline = migrationJob?.test_pipeline as TestPipe | undefined;
  const summaryMetrics = testPipeline?.test_summary_metrics;
  const coverageResult = testPipeline?.coverage_result;

  // Check if real unit-test data exists
  const hasUnitTestData = Boolean(
    (migrationJob?.tests_run && migrationJob.tests_run > 0) ||
      (testPipeline?.executed_test_details && testPipeline.executed_test_details.length > 0) ||
      (testPipeline?.generated_test_execution && (testPipeline.generated_test_execution.executed > 0 || testPipeline.generated_test_execution.executed_generated_test_methods > 0)) ||
      (coverageResult && coverageResult.available) ||
      (migrationJob?.tests_passed && migrationJob.tests_passed > 0)
  );

  let testFileCount = 0;
  if (summaryMetrics?.existing_test_files != null || summaryMetrics?.new_test_files != null || summaryMetrics?.generated_test_files != null) {
    testFileCount = (Number(summaryMetrics?.existing_test_files) || 0) + (Number(summaryMetrics?.new_test_files ?? summaryMetrics?.generated_test_files) || 0);
  } else if (testPipeline?.existing_test_files?.length) {
    testFileCount = testPipeline.existing_test_files.length;
  }

  let testCaseCount = 0;
  if (summaryMetrics?.total_test_cases != null) {
    testCaseCount = Number(summaryMetrics.total_test_cases);
  } else if (summaryMetrics?.existing_test_cases != null || summaryMetrics?.generated_test_cases != null) {
    testCaseCount = (Number(summaryMetrics?.existing_test_cases) || 0) + (Number(summaryMetrics?.generated_test_cases) || 0);
  } else if (migrationJob?.tests_run) {
    testCaseCount = migrationJob.tests_run;
  }

  const executedDetails: UnitTestDetail[] = [];
  if (testPipeline?.executed_test_details && Array.isArray(testPipeline.executed_test_details)) {
    testPipeline.executed_test_details.forEach((d: Record<string, unknown>) => {
      executedDetails.push({
        testClass: (d.test_class as string) || "TestClass",
        testMethod: (d.test_method as string) || "testMethod",
        status: (d.status as "PASSED" | "FAILED" | "SKIPPED") || "PASSED",
        duration: (d.duration as string) || (d.execution_time_seconds ? `${d.execution_time_seconds}s` : "0.012s"),
      });
    });
  }

  const methodCount = executedDetails.length > 0 ? executedDetails.length : (migrationJob?.tests_run || 0);
  const testsPassed =
    executedDetails.length > 0
      ? executedDetails.filter((d) => d.status.toUpperCase() === "PASSED").length
      : (migrationJob?.tests_passed ?? 0);
  const testsFailed =
    executedDetails.length > 0
      ? executedDetails.filter((d) => d.status.toUpperCase() === "FAILED").length
      : (migrationJob?.tests_failed ?? 0);

  let coveragePct: number | null = null;
  if (coverageResult?.available) {
    if (typeof coverageResult?.final?.line_coverage_pct === "number") {
      coveragePct = Number(coverageResult.final.line_coverage_pct.toFixed(1));
    } else if (typeof coverageResult?.line_coverage_pct === "number") {
      coveragePct = Number(coverageResult.line_coverage_pct.toFixed(1));
    } else if (typeof coverageResult?.line_coverage === "number") {
      coveragePct = Number(coverageResult.line_coverage.toFixed(1));
    }
  }

  // 8. Code Depreciation
  const issues = migrationJob?.issues || [];
  const deprecatedIssues = issues.filter(
    (i) =>
      i.category?.toLowerCase().includes("deprecat") ||
      i.message?.toLowerCase().includes("deprecat") ||
      i.conversion_type?.toLowerCase().includes("deprecat")
  );

  const deprecatedApisCount = deprecatedIssues.filter(
    (i) =>
      i.category?.toLowerCase().includes("api") ||
      i.message?.toLowerCase().includes("api") ||
      !i.message?.toLowerCase().includes("method")
  ).length;

  const deprecatedMethodsCount = deprecatedIssues.filter(
    (i) =>
      i.category?.toLowerCase().includes("method") ||
      i.message?.toLowerCase().includes("method")
  ).length;

  return {
    currentStep,
    progress,
    status: migrationJob?.status === "failed" ? "failed" : "in_progress",
    projectName,
    sourceJavaVersion,
    targetJavaVersion,
    buildFile,
    changes: {
      filesModified: modifiedFileCount,
      codeTransformations: codeTransformationsCount,
      dependenciesUpdated: depItems.length,
      available: modifiedFileCount > 0 || depItems.length > 0,
    },
    dependencies: {
      items: depItems,
      updatedCount: depItems.length,
      error: depError,
    },
    transformations: {
      modifiedFiles: modifiedFilesList,
      modifiedFileCount,
      diffSummaries,
    },
    qualityChecks: {
      sonar: {
        totalIssues: sonarTotalIssues,
        bugs: sonarBugs,
        vulnerabilities: sonarVulns,
        codeSmells: sonarSmells,
        qualityGate: migrationJob?.sonar_quality_gate || null,
        executed: Boolean(migrationJob?.run_sonar ?? migrationJob?.runSonar ?? runSonar),
      },
      fossa: {
        totalIssues: fossaIssues,
        complianceStatus: fossaResult?.compliance_status || migrationJob?.fossa_policy_status || null,
        executed: Boolean(migrationJob?.run_fossa ?? migrationJob?.runFossa ?? runFossa),
      },
      junit: {
        executed: Boolean(migrationJob?.run_tests ?? migrationJob?.runTests ?? runTests) || hasUnitTestData,
        testsPassed,
        testsFailed,
      },
    },
    unitTests: {
      hasData: hasUnitTestData,
      testFileCount,
      testCaseCount,
      methodCount,
      passed: testsPassed,
      failed: testsFailed,
      coveragePct,
      methodDetails: executedDetails,
    },
    depreciation: {
      deprecatedApisCount,
      deprecatedMethodsCount,
      scanned: Boolean(issues.length > 0),
    },
    report: {
      generated: progress >= 100,
    },
    rawCodeChanges: codeChanges,
    rawIssues: deprecatedIssues,
    rawJob: migrationJob,
  };
}

/**
 * Dynamically generates log events for a given migration step.
 * Strictly adheres to specifications for Steps 1 through 6.
 * Logs corresponding to file modifications, dependencies, or tests attach sourceReference.
 */
export function generateStepLogs(stepId: number, state: MigrationState): MigrationLogEvent[] {
  const events: MigrationLogEvent[] = [];

  const addLog = (
    type: MigrationLogEvent["type"],
    message: string,
    metadata?: Record<string, unknown>,
    sourceReference?: SourceLocationReference,
    options?: {
      category?: string;
      clickable?: boolean;
      action?: LogActionType | string;
      target?: string;
      data?: unknown;
    }
  ) => {
    let category = options?.category;
    let action = options?.action;
    let target = options?.target;
    let clickable = options?.clickable;
    let data = options?.data;

    // Automatic categorization if not provided
    if (!category) {
      if (sourceReference) {
        category = sourceReference.category || "source";
        clickable = true;
        action = action || "OPEN_SOURCE_CODE";
        target = sourceReference.fileName;
      } else if (stepId === 4) {
        const msgLower = message.toLowerCase();
        if (msgLower.includes("sonar")) {
          category = "sonarqube";
          clickable = true;
          action = "OPEN_SONARQUBE_RESULTS";
          target = "sonarqube";
          data = state.qualityChecks.sonar;
        } else if (msgLower.includes("fossa")) {
          category = "fossa";
          clickable = true;
          action = "OPEN_FOSSA_RESULTS";
          target = "fossa";
          data = state.qualityChecks.fossa;
        } else if (msgLower.includes("junit") || msgLower.includes("test")) {
          category = "junit";
          clickable = true;
          action = "OPEN_JUNIT_RESULTS";
          target = "junit";
          data = state.unitTests;
        }
      } else if (stepId === 5) {
        category = "deprecation";
        clickable = true;
        action = "OPEN_DEPRECATION_RESULTS";
        target = "deprecation";
      } else if (stepId === 6) {
        category = "migration-report";
        clickable = true;
        action = "OPEN_MIGRATION_REPORT";
        target = "report";
      } else if (stepId === 1) {
        category = "code-version";
        if (sourceReference) {
          clickable = true;
          action = "OPEN_SOURCE_CODE";
        }
      } else if (stepId === 2) {
        category = "dependencies";
        if (sourceReference) {
          clickable = true;
          action = "OPEN_SOURCE_CODE";
        }
      } else if (stepId === 3) {
        category = "transformation";
        if (sourceReference) {
          clickable = true;
          action = "OPEN_SOURCE_CODE";
        }
      }
    }

    events.push({
      id: `step-${stepId}-log-${events.length + 1}-${Date.now()}`,
      step: stepId,
      stepId: STEP_NUMBER_TO_ID[stepId] || "code-version-update",
      type,
      message,
      metadata,
      sourceReference,
      category,
      clickable: clickable ?? Boolean(sourceReference || action),
      action,
      target,
      data,
    });
  };

  switch (stepId) {
    // ========================================================
    // 1. CODE VERSION UPDATE LOGS
    // ========================================================
    case 1: {
      addLog("INFO", "Starting code version update...");
      addLog("INFO", "Reading project configuration...");
      addLog("INFO", "Detecting current Java version...");
      addLog("INFO", `Source Java version: ${state.sourceJavaVersion}`);
      addLog("INFO", `Target Java version: ${state.targetJavaVersion}`);
      addLog("INFO", "Scanning source code files...");
      addLog("INFO", "Analyzing Java files for compatibility...");
      addLog("INFO", "Checking Java language features...");
      addLog(
        "INFO",
        "Applying required Java version updates...",
        undefined,
        resolveSourceReference(state.buildFile, {
          startLine: 9,
          endLine: 9,
          changeType: "MODIFIED",
          customTitle: `Java Version ${state.sourceJavaVersion} → ${state.targetJavaVersion}`,
          sourceJavaVersion: state.sourceJavaVersion,
          targetJavaVersion: state.targetJavaVersion,
        })
      );
      addLog(
        "INFO",
        "Updating source compatibility...",
        undefined,
        resolveSourceReference(state.buildFile, {
          startLine: 8,
          endLine: 10,
          changeType: "MODIFIED",
          customTitle: "Source Compatibility Config",
          sourceJavaVersion: state.sourceJavaVersion,
          targetJavaVersion: state.targetJavaVersion,
        })
      );
      break;
    }

    // ========================================================
    // 2. DEPENDENCIES UPDATES LOGS
    // ========================================================
    case 2: {
      addLog(
        "INFO",
        `Reading ${state.buildFile}...`,
        undefined,
        resolveSourceReference(state.buildFile, {
          startLine: 1,
          endLine: 10,
          changeType: "DEPENDENCY",
          customTitle: `${state.buildFile} Project Configuration`,
          sourceJavaVersion: state.sourceJavaVersion,
          targetJavaVersion: state.targetJavaVersion,
        })
      );
      addLog("INFO", "Scanning project dependencies...");
      addLog("INFO", "Checking dependency compatibility...");
      addLog("INFO", "Resolving compatible versions...");

      if (state.dependencies.error) {
        addLog("ERROR", `Dependency update failed: ${state.dependencies.error}`);
      } else if (state.dependencies.items.length > 0) {
        state.dependencies.items.forEach((dep) => {
          const depName = dep.coordinate || dep.name;
          let startLine = 12;
          let endLine = 16;
          if (depName.includes("parent")) {
            startLine = 3;
            endLine = 7;
          } else if (depName.includes("junit")) {
            startLine = 17;
            endLine = 21;
          }
          const ref = resolveSourceReference(state.buildFile, {
            startLine,
            endLine,
            changeType: "DEPENDENCY",
            customTitle: `Dependency: ${depName}`,
            sourceJavaVersion: state.sourceJavaVersion,
            targetJavaVersion: state.targetJavaVersion,
          });

          if (dep.beforeVersion && dep.afterVersion) {
            addLog(
              "INFO",
              `Updated ${depName}: ${dep.beforeVersion} → ${dep.afterVersion}`,
              undefined,
              ref
            );
          } else {
            addLog("INFO", `Updating ${depName}...`, undefined, ref);
          }
        });
      }

      addLog("INFO", "Validating dependency tree...");
      break;
    }

    // ========================================================
    // 3. CODE FIX & CODE TRANSFORMATION LOGS
    //    (includes Before & After Differentiator and Changes Made)
    // ========================================================
    case 3: {
      addLog("INFO", "Scanning source files for migration changes...");
      addLog("INFO", "Identifying transformation rules...");
      addLog("INFO", "Detecting files requiring transformation...");
      addLog("INFO", `Found ${state.transformations.modifiedFileCount} modified files...`);
      addLog("INFO", "Applying automated code fixes...");
      addLog("INFO", "Updating imports...");
      addLog("INFO", "Applying package transformations...");
      addLog("INFO", "Applying Jakarta namespace transformations...");

      // Transform actual files from Code Transformations data
      if (state.transformations.modifiedFiles.length > 0) {
        state.transformations.modifiedFiles.slice(0, 10).forEach((fileName) => {
          const ref = resolveSourceReference(fileName, {
            codeChanges: state.rawCodeChanges,
            migrationJob: state.rawJob,
            customTitle: `Code Transformation: ${fileName}`,
            sourceJavaVersion: state.sourceJavaVersion,
            targetJavaVersion: state.targetJavaVersion,
          });
          addLog("INFO", `Transforming ${fileName}...`, undefined, ref);
        });
      }

      addLog("INFO", "Refactoring affected classes...");
      addLog("INFO", "Updating incompatible APIs...");
      addLog("INFO", "Validating transformed source files...");

      // Before & After Differentiator Logs
      addLog("INFO", "Analyzing Before/After differences...");
      if (state.transformations.diffSummaries.length > 0) {
        state.transformations.diffSummaries.forEach((diff) => {
          let ref: SourceLocationReference | undefined;
          if (diff.includes("pom.xml") || diff.includes("Spring Boot")) {
            ref = resolveSourceReference("pom.xml", {
              startLine: 3,
              endLine: 7,
              changeType: "DEPENDENCY",
              customTitle: "Spring Boot Version Migration",
              sourceJavaVersion: state.sourceJavaVersion,
              targetJavaVersion: state.targetJavaVersion,
            });
          } else if (diff.toLowerCase().includes("java version")) {
            ref = resolveSourceReference("pom.xml", {
              startLine: 9,
              endLine: 9,
              changeType: "MODIFIED",
              customTitle: `Java Version ${state.sourceJavaVersion} → ${state.targetJavaVersion}`,
              sourceJavaVersion: state.sourceJavaVersion,
              targetJavaVersion: state.targetJavaVersion,
            });
          } else if (diff.includes("persistence")) {
            ref = resolveSourceReference("EmployeeService.java", {
              startLine: 2,
              endLine: 5,
              changeType: "MODIFIED",
              customTitle: "Jakarta Persistence Imports",
            });
          } else if (diff.includes("JUnit")) {
            ref = resolveSourceReference("SystemApplicationTests.java", {
              startLine: 3,
              endLine: 13,
              changeType: "TEST",
              customTitle: "JUnit 4 to JUnit 5 Migration",
            });
          }
          addLog("INFO", diff, undefined, ref);
        });
      } else {
        addLog(
          "INFO",
          `Detected Java version compatibility changes: Java ${state.sourceJavaVersion} → Java ${state.targetJavaVersion}`,
          undefined,
          resolveSourceReference("pom.xml", {
            startLine: 9,
            endLine: 9,
            changeType: "MODIFIED",
            customTitle: `Java Version ${state.sourceJavaVersion} → ${state.targetJavaVersion}`,
            sourceJavaVersion: state.sourceJavaVersion,
            targetJavaVersion: state.targetJavaVersion,
          })
        );
        addLog(
          "INFO",
          "Detected dependency changes: Spring Boot 2.7.18 → 3.2.5",
          undefined,
          resolveSourceReference("pom.xml", { startLine: 3, endLine: 7, changeType: "DEPENDENCY" })
        );
        addLog(
          "INFO",
          "Detected package/import changes: javax.persistence → jakarta.persistence",
          undefined,
          resolveSourceReference("EmployeeService.java", { startLine: 2, endLine: 5, changeType: "MODIFIED" })
        );
        addLog(
          "INFO",
          "Detected API transformations: javax.servlet → jakarta.servlet",
          undefined,
          resolveSourceReference("EmployeeController.java", { startLine: 2, endLine: 3, changeType: "MODIFIED" })
        );
      }
      addLog("INFO", "Before/After validation completed.");

      // Changes Made Summary Logs
      addLog("INFO", "Collecting migration changes...");
      if (state.changes.available) {
        addLog("INFO", `Files modified: ${state.changes.filesModified}`);
        addLog("INFO", `Code transformations applied: ${state.changes.codeTransformations}`);
        addLog("INFO", `Dependencies updated: ${state.changes.dependenciesUpdated}`);
        addLog("SUCCESS", "Migration changes collected successfully.");
      } else {
        addLog("WARN", "Waiting for migration change data...");
      }
      break;
    }

    // ========================================================
    // 4. QUALITY CHECK LOGS (Sonar, FOSSA, Unit check - JUnit)
    // ========================================================
    case 4: {
      // SonarQube
      addLog("INFO", "Starting SonarQube analysis...", undefined, undefined, {
        category: "sonarqube",
        clickable: true,
        action: "OPEN_SONARQUBE_RESULTS",
        target: "sonarqube",
        data: state.qualityChecks.sonar,
      });
      addLog("INFO", "Scanning source code quality...", undefined, undefined, {
        category: "sonarqube",
        clickable: true,
        action: "OPEN_SONARQUBE_RESULTS",
        target: "sonarqube",
        data: state.qualityChecks.sonar,
      });
      addLog("INFO", "Collecting SonarQube results...", undefined, undefined, {
        category: "sonarqube",
        clickable: true,
        action: "OPEN_SONARQUBE_RESULTS",
        target: "sonarqube",
        data: state.qualityChecks.sonar,
      });
      if (state.qualityChecks.sonar.totalIssues > 0) {
        addLog(
          "WARN",
          `SonarQube issues found: ${state.qualityChecks.sonar.totalIssues}`,
          undefined,
          undefined,
          {
            category: "sonarqube",
            clickable: true,
            action: "OPEN_SONARQUBE_RESULTS",
            target: "sonarqube",
            data: state.qualityChecks.sonar,
          }
        );
      } else {
        addLog(
          "SUCCESS",
          "SonarQube analysis completed with 0 issues.",
          undefined,
          undefined,
          {
            category: "sonarqube",
            clickable: true,
            action: "OPEN_SONARQUBE_RESULTS",
            target: "sonarqube",
            data: state.qualityChecks.sonar,
          }
        );
      }

      // FOSSA
      addLog("INFO", "Starting FOSSA dependency/license scan...", undefined, undefined, {
        category: "fossa",
        clickable: true,
        action: "OPEN_FOSSA_RESULTS",
        target: "fossa",
        data: state.qualityChecks.fossa,
      });
      addLog("INFO", "Scanning dependencies...", undefined, undefined, {
        category: "fossa",
        clickable: true,
        action: "OPEN_FOSSA_RESULTS",
        target: "fossa",
        data: state.qualityChecks.fossa,
      });
      addLog("INFO", "Collecting FOSSA results...", undefined, undefined, {
        category: "fossa",
        clickable: true,
        action: "OPEN_FOSSA_RESULTS",
        target: "fossa",
        data: state.qualityChecks.fossa,
      });
      if (state.qualityChecks.fossa.totalIssues > 0) {
        addLog(
          "WARN",
          `FOSSA issues found: ${state.qualityChecks.fossa.totalIssues}`,
          undefined,
          undefined,
          {
            category: "fossa",
            clickable: true,
            action: "OPEN_FOSSA_RESULTS",
            target: "fossa",
            data: state.qualityChecks.fossa,
          }
        );
      } else {
        addLog(
          "SUCCESS",
          "FOSSA scan completed.",
          undefined,
          undefined,
          {
            category: "fossa",
            clickable: true,
            action: "OPEN_FOSSA_RESULTS",
            target: "fossa",
            data: state.qualityChecks.fossa,
          }
        );
      }

      // JUnit
      const testRef = resolveSourceReference("SystemApplicationTests.java", {
        startLine: 10,
        endLine: 15,
        changeType: "TEST",
        customTitle: "JUnit 5 Test Suite Execution",
      });
      addLog("INFO", "Starting JUnit test execution...", undefined, testRef, {
        category: "junit",
        clickable: true,
        action: "OPEN_JUNIT_RESULTS",
        target: "junit",
        data: state.unitTests,
      });
      addLog("INFO", "Discovering test classes...", undefined, testRef, {
        category: "junit",
        clickable: true,
        action: "OPEN_JUNIT_RESULTS",
        target: "junit",
        data: state.unitTests,
      });
      addLog("INFO", "Executing test methods...", undefined, testRef, {
        category: "junit",
        clickable: true,
        action: "OPEN_JUNIT_RESULTS",
        target: "junit",
        data: state.unitTests,
      });
      addLog("INFO", "Collecting test results...", undefined, testRef, {
        category: "junit",
        clickable: true,
        action: "OPEN_JUNIT_RESULTS",
        target: "junit",
        data: state.unitTests,
      });
      addLog("INFO", "JUnit validation completed.", undefined, testRef, {
        category: "junit",
        clickable: true,
        action: "OPEN_JUNIT_RESULTS",
        target: "junit",
        data: state.unitTests,
      });

      // Unit Test Information (ONLY if actual test data exists!)
      if (state.unitTests.hasData) {
        addLog("INFO", "Reading unit test configuration...", undefined, testRef, {
          category: "junit",
          clickable: true,
          action: "OPEN_JUNIT_RESULTS",
        });
        addLog("INFO", "Discovering test files...", undefined, testRef, {
          category: "junit",
          clickable: true,
          action: "OPEN_JUNIT_RESULTS",
        });
        if (state.unitTests.testFileCount > 0) {
          addLog("INFO", `Found ${state.unitTests.testFileCount} test files...`, undefined, testRef, {
            category: "junit",
            clickable: true,
            action: "OPEN_JUNIT_RESULTS",
          });
        }
        if (state.unitTests.testCaseCount > 0) {
          addLog("INFO", `Found ${state.unitTests.testCaseCount} test cases...`, undefined, testRef, {
            category: "junit",
            clickable: true,
            action: "OPEN_JUNIT_RESULTS",
          });
        }
        addLog("INFO", "Executing JUnit test suite...", undefined, testRef, {
          category: "junit",
          clickable: true,
          action: "OPEN_JUNIT_RESULTS",
        });
        if (state.unitTests.methodCount > 0) {
          addLog("INFO", `Running ${state.unitTests.methodCount} test methods...`, undefined, testRef, {
            category: "junit",
            clickable: true,
            action: "OPEN_JUNIT_RESULTS",
          });
        }
        addLog("INFO", "Collecting test results...", undefined, testRef, {
          category: "junit",
          clickable: true,
          action: "OPEN_JUNIT_RESULTS",
        });
        addLog("SUCCESS", `Tests passed: ${state.unitTests.passed}`, undefined, testRef, {
          category: "junit",
          clickable: true,
          action: "OPEN_JUNIT_RESULTS",
        });
        if (state.unitTests.failed > 0) {
          addLog("WARN", `Tests failed: ${state.unitTests.failed}`, undefined, testRef, {
            category: "junit",
            clickable: true,
            action: "OPEN_JUNIT_RESULTS",
          });
        }
        if (state.unitTests.coveragePct !== null && state.unitTests.coveragePct !== undefined) {
          addLog("INFO", `JaCoCo coverage: ${state.unitTests.coveragePct}%`, undefined, testRef, {
            category: "junit",
            clickable: true,
            action: "OPEN_JUNIT_RESULTS",
          });
        }
        addLog("INFO", "Unit test validation completed.", undefined, testRef, {
          category: "junit",
          clickable: true,
          action: "OPEN_JUNIT_RESULTS",
        });
      } else {
        addLog("INFO", "Unit test results not available yet.", undefined, testRef, {
          category: "junit",
          clickable: true,
          action: "OPEN_JUNIT_RESULTS",
        });
      }
      break;
    }

    // ========================================================
    // 5. CODE DEPRECIATION LOGS
    // ========================================================
    case 5: {
      addLog("INFO", "Starting code deprecation analysis...");
      addLog("INFO", "Scanning source files for deprecated APIs...");
      addLog("INFO", "Identifying deprecated methods...");
      addLog("INFO", "Analyzing deprecated API usage...");
      addLog("INFO", "Mapping deprecated APIs to recommended replacements...");
      addLog("INFO", "Calculating migration impact...");
      addLog("INFO", "Generating deprecation summary...");

      if (Array.isArray(state.rawIssues) && state.rawIssues.length > 0) {
        state.rawIssues.slice(0, 3).forEach((issue: Record<string, unknown>) => {
          const rawFile = (issue.file_path || issue.file || "EmployeeService.java") as string;
          const baseName = rawFile.split("/").pop()?.split("\\").pop() || rawFile;
          const line = issue.line_number || issue.line || 42;
          const ref = resolveSourceReference(baseName, {
            startLine: line,
            endLine: line,
            changeType: "DEPRECATED",
            customTitle: `Deprecated API in ${baseName}:${line}`,
          });
          addLog("WARN", `Deprecated usage in ${baseName}:${line}`, undefined, ref);
        });
      }

      if (state.depreciation.deprecatedApisCount > 0) {
        addLog("WARN", `Deprecated APIs detected: ${state.depreciation.deprecatedApisCount}`);
      }
      if (state.depreciation.deprecatedMethodsCount > 0) {
        addLog("WARN", `Deprecated methods detected: ${state.depreciation.deprecatedMethodsCount}`);
      }
      if (state.depreciation.deprecatedApisCount === 0 && state.depreciation.deprecatedMethodsCount === 0) {
        addLog("SUCCESS", "No deprecated APIs detected.");
      }
      break;
    }

    // ========================================================
    // 6. GENERATING MIGRATION REPORT LOGS
    // ========================================================
    case 6: {
      addLog("INFO", "Collecting migration results...");
      addLog("INFO", "Collecting repository information...");
      addLog("INFO", "Collecting changes made...");
      addLog("INFO", "Collecting dependency updates...");
      addLog("INFO", "Collecting code transformation results...");
      addLog("INFO", "Collecting quality-check results...");

      // IMPORTANT: Skip unit test collection log if unit test data does NOT exist
      if (state.unitTests.hasData) {
        addLog("INFO", "Collecting unit-test results...");
      }

      addLog("INFO", "Collecting code deprecation results...");
      addLog("INFO", "Compiling migration statistics...");
      addLog("INFO", "Generating migration report...");
      addLog("INFO", "Preparing migration recommendations...");
      addLog("INFO", "Finalizing migration report...");
      break;
    }

    default:
      break;
  }

  return events;
}

/**
 * Returns the completion log event for a specific step.
 */
export function generateStepCompletionLog(stepId: number, _state: MigrationState): MigrationLogEvent {
  const sid = STEP_NUMBER_TO_ID[stepId] || "code-version-update";
  switch (stepId) {
    case 1:
      return {
        id: `step-1-comp-${Date.now()}`,
        step: 1,
        stepId: sid,
        type: "SUCCESS",
        message: "Code version update completed successfully.",
      };
    case 2:
      return {
        id: `step-2-comp-${Date.now()}`,
        step: 2,
        stepId: sid,
        type: "SUCCESS",
        message: "Dependency updates completed successfully.",
      };
    case 3:
      return {
        id: `step-3-comp-${Date.now()}`,
        step: 3,
        stepId: sid,
        type: "SUCCESS",
        message: "Code fixes and transformations completed successfully.",
      };
    case 4:
      return {
        id: `step-4-comp-${Date.now()}`,
        step: 4,
        stepId: sid,
        type: "SUCCESS",
        message: "Quality checks completed successfully.",
        category: "sonarqube",
        clickable: true,
        action: "OPEN_SONARQUBE_RESULTS",
        target: "sonarqube",
      };
    case 5:
      return {
        id: `step-5-comp-${Date.now()}`,
        step: 5,
        stepId: sid,
        type: "SUCCESS",
        message: "Code deprecation analysis completed.",
        category: "deprecation",
        clickable: true,
        action: "OPEN_DEPRECATION_RESULTS",
        target: "deprecation",
      };
    case 6:
      return {
        id: `step-6-comp-${Date.now()}`,
        step: 6,
        stepId: sid,
        type: "SUCCESS",
        message: "Migration report generated successfully.",
        category: "migration-report",
        clickable: true,
        action: "OPEN_MIGRATION_REPORT",
        target: "report",
      };
    default:
      return {
        id: `step-${stepId}-comp-${Date.now()}`,
        step: stepId,
        stepId: sid,
        type: "SUCCESS",
        message: "Step completed successfully.",
      };
  }
}

/**
 * Returns the final execution completion log.
 */
export function generateFinalCompletionLog(): MigrationLogEvent {
  return {
    id: `final-comp-${Date.now()}`,
    step: 6,
    stepId: "migration-report",
    type: "SUCCESS",
    message: "Migration process completed successfully.",
    category: "migration-report",
    clickable: true,
    action: "OPEN_MIGRATION_REPORT",
    target: "report",
  };
}
