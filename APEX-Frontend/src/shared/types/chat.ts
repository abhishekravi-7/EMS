export type Role = "user" | "assistant" | "system";

export interface ComparisonTableSpec {
  caption?: string;
  headers: string[];
  rows: string[][];
}

export interface SourceReference {
  title: string;
  url: string;
  excerpt?: string;
}

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  rationale?: string[];
  comparisonTable?: ComparisonTableSpec | null;
  details?: Record<string, unknown> | null;
  createdAt: string;
  sources?: SourceReference[];
}

export type ContentBlock =
  | { kind: "paragraph"; text: string }
  | { kind: "heading"; text: string; level: number }
  | { kind: "list"; items: string[]; ordered: boolean }
  | { kind: "table"; table: ComparisonTableSpec }
  | { kind: "code"; code: string; language?: string };

export interface DependencyContextItem {
  name: string;
  version?: string | null;
  status?: string | null;
  risk?: string | null;
}

export interface ProjectContext {
  projectName: string | null;
  currentJavaVersion: string | null;
  targetJavaVersion: string | null;
  totalFiles: number | null;
  frameworks: string[];
  migrationReadiness: number | null;
  migrationBlockers: number | null;
  deprecatedApis: number | null;
  legacyApis: number | null;
  securityVulnerabilities: number | null;
  codeSmells: number | null;
  buildTool: string | null;
  dependencies: DependencyContextItem[];
  hasTests: boolean | null;
  testCount: number | null;
  riskLevel?: string | null;
  // Migration execution & test cases fields
  testsRun?: number | null;
  testsPassed?: number | null;
  testsFailed?: number | null;
  existingTestCases?: number | null;
  generatedTestCases?: number | null;
  totalTestCases?: number | null;
  existingTestFiles?: number | null;
  newTestFiles?: number | null;
  coveragePct?: number | null;
  testSummary?: string | null;
  testInsights?: string[];
  filesModified?: number | null;
  issuesFixed?: number | null;
  sonarQualityGate?: string | null;
  sonarBugs?: number | null;
  rawDetails?: Record<string, unknown>;
}

export type QuestionIntent =
  | "PROJECT_OVERVIEW"
  | "REPOSITORY"
  | "FILES"
  | "DEPENDENCIES"
  | "FRAMEWORKS"
  | "JAVA_VERSION"
  | "MIGRATION_READINESS"
  | "MIGRATION_PROGRESS"
  | "MIGRATION_RISK"
  | "MIGRATION_BLOCKERS"
  | "SECURITY"
  | "DEPRECATED_APIS"
  | "LEGACY_APIS"
  | "CODE_SMELLS"
  | "COMPILATION"
  | "TESTING"
  | "MIGRATION_STRATEGY"
  | "CODE_EXPLANATION"
  | "REPORTS"
  | "GENERAL_JAVA"
  | "GENERAL_TECHNICAL"
  | "FOLLOW_UP"
  | "UNKNOWN";

export interface CentralizedProjectContext {
  project: {
    name: string;
    repository: string;
    currentJavaVersion: string;
    targetJavaVersion: string;
  };
  repository: {
    totalFiles: number;
    directories: number;
    javaFiles: number;
    configFiles: number;
    resourceFiles: number;
    otherFiles: number;
    buildTool?: string;
  };
  dependencies: {
    total: number;
    outdated: Array<{ name: string; currentVersion?: string; targetVersion?: string; status?: string }>;
    deprecated: Array<{ name: string; currentVersion?: string; note?: string }>;
    incompatible: Array<{ name: string; currentVersion?: string; issue?: string }>;
  };
  frameworks: string[];
  findings: {
    javaFeatures: string[];
    deprecatedApis: string[];
    legacyApis: string[];
    securityVulnerabilities: string[];
    codeSmells: string[];
    migrationBlockers: string[];
    compilationErrors: string[];
  };
  migration: {
    readiness: number;
    progress: number;
    currentStage: string;
    completedSteps: string[];
    activeStep: string;
    pendingSteps: string[];
    elapsedTime: string;
    riskLevel?: string;
    testsRun?: number;
    testsPassed?: number;
    testsFailed?: number;
    existingTestCases?: number;
    generatedTestCases?: number;
    coveragePct?: number;
    testSummary?: string;
  };
}

export interface SendMessageOptions {
  question: string;
  repoUrl?: string | null;
  strategyContext?: unknown;
  projectContext?: ProjectContext | null;
  appContext?: CentralizedProjectContext | null;
  history?: ChatMessage[];
  onPhase?: (phase: string) => void;
  onReferences?: (sources: SourceReference[]) => void;
  onChunk: (chunk: string) => void;
  signal?: AbortSignal;
}
