/**
 * Cross-feature domain DTOs shared by connect/discovery/strategy/modernization.
 */

export interface RepoInfo {
  name: string;
  full_name: string;
  url: string;
  default_branch: string;
  language: string | null;
  description: string | null;
}

export interface RepoFile {
  name: string;
  path: string;
  type: 'file' | 'dir';
  size: number;
  url: string;
}

export interface DiscoveredApiEndpoint {
  id?: string;
  httpMethod: string;
  method?: string;
  path: string;
  urlPath?: string;
  endpoint?: string;
  controller?: string;
  className?: string;
  handlerMethod?: string;
  methodName?: string;
  sourceFile?: string;
  file?: string;
  module?: string;
  framework?: string;
  detectionStatus?: string;
}

export interface UserResponse {
  id: number | string;
  userId?: number | string;
  fullName: string;
  email: string;
  role: string;
  isActive: boolean;
  isEmailVerified: boolean;
  createdAt: string;
  lastLoginAt: string | null;
}

export interface DependencyInfo {
  group_id: string;
  artifact_id: string;
  current_version: string;
  new_version: string | null;
  status: string;
  declaredVersion?: string | null;
  resolvedVersion?: string | null;
  versionSource?: string | null;
  direct?: boolean;
  transitive?: boolean;
  scope?: string | null;
  parent?: string | null;
  introduced_by?: string | null;
  type?: string | null;
  module?: string | null;
}

export interface DetectedFramework {
  name: string;
  path: string;
  type: string;
}

/**
 * Spring -> Spring Boot conversion eligibility, computed by the backend from
 * the actual cloned-and-analyzed repository (never from the URL, repo name,
 * or mock data). Drives whether the Strategy step's conversion card is
 * enabled/disabled and what it displays.
 */
export interface SpringBootConversionEligibility {
  repositoryAnalyzed: boolean;
  javaMigrationEligible: boolean;
  javaMigrationReason: string;
  springDetected: boolean;
  springBootDetected: boolean;
  springVersion: string | null;
  springBootVersion: string | null;
  buildTool: string;
  springBootConversionEligible: boolean;
  springBootUpgradeEligible: boolean;
  eligibilityReason: string;
}

export interface FrameworkRecommendationItem {
  framework: "React" | "Angular" | string;
  targetVersion: string;
  availableVersions?: string[];
  compatibility: string;
  architecture?: string;
  routing?: string;
  isRecommended: boolean;
  reasons: string[];
  constraints: string[];
  currentVersion?: string | null;
}

export interface FrameworkRecommendations {
  react?: FrameworkRecommendationItem;
  angular?: FrameworkRecommendationItem;
}

export interface ViewTechnologyIndicator {
  id: string;
  label: string;
  detected: boolean;
  variant?: "green" | "blue" | "gray" | string;
}

export interface ViewTechnologyData {
  jspDetected: boolean;
  jspFileCount: number;
  jsfDetected: boolean;
  jsfFileCount: number;
  hasJspViews: boolean;
  hasJspTags: boolean;
  hasJstl: boolean;
  hasJsfXhtml: boolean;
  hasManagedBeans: boolean;
  hasExpressionLanguage: boolean;
  indicators: ViewTechnologyIndicator[];
  summaryMessage: string;
}

export interface FileCategoryCounts {
  java: number;
  java_test: number;
  jsp: number;
  jsf: number;
  react: number;
  angular: number;
  javascript: number;
  typescript: number;
  css: number;
  html: number;
  xml: number;
  configuration: number;
  resources: number;
  documentation: number;
  scripts: number;
  sql: number;
  other: number;
}

export interface FileMetrics {
  total: number;
  categories: FileCategoryCounts;
  category_files?: Record<string, string[]>;
}

export interface RepoAnalysis {
  name: string;
  full_name: string;
  default_branch: string;
  language: string | null;
  build_tool: string | null;
  java_version: string | null;
  java_version_from_build?: string | null;
  // List of discovered Java source file paths
  java_files?: string[];
  java_file_count?: number;
  config_files?: string[];
  config_file_count?: number;
  other_files?: string[];
  other_file_count?: number;
  total_file_count?: number;
  file_metrics?: FileMetrics;
  jsp_files?: string[];
  jsf_files?: string[];
  jsp_count?: number;
  jsf_count?: number;
  view_technologies?: ViewTechnologyData;
  detected_frameworks?: DetectedFramework[];
  frameworks?: string[];
  spring_boot_version?: string | null;
  has_tests: boolean;
  test_file_count?: number;
  unit_test_file_count?: number;
  functional_test_files?: {
    count: number;
    files: { path: string; tool: string }[];
    tools_detected: string[];
  };
  test_file_breakdown?: {
    tool: string;
    label: string;
    count: number;
    type: "unit" | "functional";
    files: string[];
  }[];
  test_file_list?: { path: string; tool: string }[];
  dependencies: DependencyInfo[];
  frontend_dependencies?: DependencyInfo[];
  dependency_resolution_status?: string | null;
  dependency_resolution_message?: string | null;
  api_endpoints?: DiscoveredApiEndpoint[];
  api_endpoint_count?: number;
  // Optional extras consumed by the wizard/modernization views (populated by
  // some analysis paths, absent in others).
  all_files?: Array<string | { path?: string }>;
  uiRoutes?: Array<{ route: string; source_file?: string; page_type?: string; component?: string }>;
  page_data?: Record<string, unknown>;
  structure: {
    has_pom_xml: boolean;
    has_build_gradle: boolean;
    has_src_main: boolean;
    has_src_test: boolean;
    has_build_gradle_kts: boolean;
    jsp_count?: number;
    jsf_count?: number;
  };
  // backend-provided microservice eligibility assessment
  microservice_eligibility?: MicroserviceEligibilityResult;
  // backend-provided Spring -> Spring Boot conversion eligibility (Discovery stage)
  spring_boot_eligibility?: SpringBootConversionEligibility;
  // backend-provided dynamic framework target version recommendations
  framework_recommendations?: FrameworkRecommendations;
  discovery_stages?: Record<string, unknown>;
  services?: Array<Record<string, unknown>>;
  classes?: Array<Record<string, unknown>>;
  ui_workflows?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface MicroserviceScoreBreakdown {
  name: string;
  score: number;
  weight: number;
  summary: string;
}

export interface MicroserviceServiceCandidate {
  name: string;
  packages: string[];
  evidence: string[];
  scaling_signals: string[];
  external_integrations: string[];
  transactional: boolean;
}

export interface MicroserviceDetailedEligibilityReport {
  project_structure: string[];
  package_structure: string[];
  module_boundaries: string[];
  dependency_coupling: string[];
  database_access_patterns: string[];
  communication_analysis: string[];
  deployment_independence: string[];
  scalability_indicators: string[];
}

export interface MicroserviceAnalysisDiagnostics {
  java_files_total: number;
  java_files_scanned: number;
  package_count: number;
  detected_modules: number;
  cross_module_dependencies: number;
  circular_dependencies: number;
  external_integration_count: number;
  scan_truncated: boolean;
}

export interface MicroserviceEligibilityResult {
  projectName: string;
  score: number;
  eligibility: string;
  recommendedArchitecture: string;
  summary: string;
  strengths: string[];
  risks: string[];
  serviceCandidates: MicroserviceServiceCandidate[];
  couplingIssues: string[];
  databaseConcerns: string[];
  scalingCandidates: string[];
  recommendedMigrationStrategy: string[];
  observations: string[];
  scoreBreakdown?: MicroserviceScoreBreakdown[];
  detailedEligibilityReport?: MicroserviceDetailedEligibilityReport;
  architecturalObservations?: string[];
  analysisDiagnostics?: MicroserviceAnalysisDiagnostics;
  reportGeneratedAt?: string;
  metadata?: Record<string, unknown>;
}
