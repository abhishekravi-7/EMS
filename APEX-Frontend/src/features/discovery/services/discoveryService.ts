import { authHeader, performRequest, requestJson, ABSOLUTE_URL_PATTERN } from "@/services/http/client";
import { APP_BASE_URL } from "@/services/config/env";
import type { RepoFilesResponse, FileContentResponse } from "@/features/connect/services/connectService";
import type {
  DependencyInfo,
  RepoAnalysis,
  MicroserviceEligibilityResult,
  RepoFile,
  SpringBootConversionEligibility,
  FrameworkRecommendations,
  DiscoveredApiEndpoint,
} from "@/shared/types/domain";

/* -------------------------------------------------------------------------- */
/* Discovery stage (Step 2) — POST /api/v1/discovery/{jobId}                    */
/*                                                                              */
/* Clones the connected repo into the backend workspace and analyzes it        */
/* (read-only). Returns a clean summary which we map onto the RepoAnalysis      */
/* shape the existing Discovery UI renders.                                     */
/* -------------------------------------------------------------------------- */

export interface DiscoveryDependency {
  groupId: string;
  artifactId: string;
  version: string | null;
  declaredVersion?: string | null;
  resolvedVersion?: string | null;
  versionSource?: string | null;
}

export interface DiscoveryProject {
  buildTool: string;
  currentJavaVersion: string;
  springBootVersion: string | null;
  projectType: string;
  multiModule: boolean;
  modules: string[];
  dependenciesCount: number;
  frontendDetected: boolean;
  frontendType: string | null;
  // extras used to faithfully populate the existing UI
  dependencies?: DiscoveryDependency[];
  hasTests?: boolean;
  apiEndpoints?:
    | DiscoveredApiEndpoint[]
    | {
        count?: number;
        endpoints?: DiscoveredApiEndpoint[];
      };
  apiEndpointCount?: number;
  javaFileCount?: number;
  javaFiles?: string[];
  configFileCount?: number;
  configFiles?: string[];
  otherFileCount?: number;
  otherFiles?: string[];
  jspFileCount?: number;
  jsfFileCount?: number;
  jspFiles?: string[];
  jsfFiles?: string[];
  totalFileCount?: number;
  fileMetrics?: import("@/shared/types/domain").FileMetrics;
  defaultBranch?: string;
  buildWarning?: string | null;
  frontend?: { detected: boolean; type: string; path: string | null; packageManager: string | null };
  detectedFiles?: { pomXml: boolean; buildGradle: boolean; buildGradleKts: boolean; packageJson: boolean };
  sourceLayout?: { hasSrcMain: boolean; hasSrcTest: boolean };
  springFrameworkVersion?: string | null;
  springEntryClass?: string | null;
  javaMigrationEligible?: boolean;
  javaMigrationReason?: string;
  springDetected?: boolean;
  springBootDetected?: boolean;
  springBootConversionEligible?: boolean;
  springBootUpgradeEligible?: boolean;
  eligibilityReason?: string;
  springBootConversion?: SpringBootConversionEligibility;
  frameworkRecommendations?: FrameworkRecommendations;
  frameworks?: string[];
  discoveryStages?: {
    repositoryMap?: {
      status: string;
      totalFileCount?: number;
      javaFileCount?: number;
      configFileCount?: number;
      otherFileCount?: number;
      multiModule?: boolean;
      modules?: string[];
      hasSrcMain?: boolean;
      hasSrcTest?: boolean;
      hasPomXml?: boolean;
      hasBuildGradle?: boolean;
      summary?: string;
    };
    dependencyGraph?: {
      status: string;
      buildTool?: string;
      dependencyCount?: number;
      buildPluginsCount?: number;
      bomsCount?: number;
      summary?: string;
    };
    previewSignals?: {
      status: string;
      currentJavaVersion?: string;
      buildTool?: string;
      frameworks?: string[];
      hasTests?: boolean;
      frontendDetected?: boolean;
      summary?: string;
    };
    serviceFit?: {
      status: string;
      recommendedArchitecture?: string;
      springBootConversionEligible?: boolean;
      springBootUpgradeEligible?: boolean;
      summary?: string;
    };
  };
}

export interface DiscoveryResponse {
  jobId: string;
  status: string;
  message: string;
  repository: { repoUrl: string; owner: string; repoName: string; visibility: string };
  project: DiscoveryProject;
  nextStep: string;
}

export type DiscoveryStatus =
  | "DISCOVERY_COMPLETED"
  | "CONNECT_REPORT_NOT_FOUND"
  | "CLONE_FAILED"
  | "UNSUPPORTED_PROJECT"
  | "DISCOVERY_FAILED";

export class DiscoveryApiError extends Error {
  status: DiscoveryStatus | string;
  httpStatus: number;

  constructor(message: string, status: DiscoveryStatus | string, httpStatus: number) {
    super(message);
    this.name = "DiscoveryApiError";
    this.status = status;
    this.httpStatus = httpStatus;
  }
}

export interface DiscoveryAnalysisResult {
  repo_url: string;
  owner: string;
  repo: string;
  analysis: RepoAnalysis;
  discovery: DiscoveryResponse;
}

function normalizeBuildTool(buildTool: string): string | null {
  const value = (buildTool || "").toUpperCase();
  if (value === "MAVEN") return "maven";
  if (value === "GRADLE") return "gradle";
  return null;
}

function normalizeJavaVersion(version: string | null | undefined): string | null {
  if (!version) return null;
  const value = version.trim();
  return value && value.toUpperCase() !== "UNKNOWN" ? value : null;
}

/** Map the backend discovery summary onto the RepoAnalysis the Discovery UI reads. */
export function mapDiscoveryToRepoAnalysis(response: DiscoveryResponse): RepoAnalysis {
  const { repository, project } = response;
  const javaVersion = normalizeJavaVersion(project.currentJavaVersion);
  const springBootEligibility: SpringBootConversionEligibility | undefined =
    project.springBootConversion ??
    (typeof project.javaMigrationEligible === "boolean"
      ? {
          repositoryAnalyzed: true,
          javaMigrationEligible: project.javaMigrationEligible,
          javaMigrationReason: project.javaMigrationReason ?? "",
          springDetected: Boolean(project.springDetected),
          springBootDetected: Boolean(project.springBootDetected),
          springVersion: project.springFrameworkVersion ?? null,
          springBootVersion: project.springBootVersion ?? null,
          buildTool: project.buildTool,
          springBootConversionEligible: Boolean(project.springBootConversionEligible),
          springBootUpgradeEligible: Boolean(project.springBootUpgradeEligible),
          eligibilityReason: project.eligibilityReason ?? "",
        }
      : undefined);
  const dependencies: DependencyInfo[] = (project.dependencies ?? []).map((dep) => ({
    group_id: dep.groupId,
    artifact_id: dep.artifactId,
    current_version: dep.version ?? "",
    new_version: null,
    status: "detected",
    declaredVersion: dep.declaredVersion,
    resolvedVersion: dep.resolvedVersion,
    versionSource: dep.versionSource,
  }));

    const rawOtherFiles: string[] = project.otherFiles ?? (project as { other_files?: string[] }).other_files ?? [];
    const cleanOtherFiles = rawOtherFiles.filter((f: string) => {
      const lower = (typeof f === "string" ? f : "").toLowerCase();
      return (
        !lower.endsWith(".jsp") &&
        !lower.endsWith(".jspf") &&
        !lower.endsWith(".jspx") &&
        !lower.endsWith(".xhtml") &&
        !lower.endsWith(".jsf")
      );
    });
    const cleanOtherCount =
      cleanOtherFiles.length !== rawOtherFiles.length
        ? cleanOtherFiles.length
        : (project.otherFileCount ?? cleanOtherFiles.length);

    type ExtraProjectFields = {
      java_files?: string[];
      config_files?: string[];
      file_metrics?: unknown;
      viewTechnologies?: unknown;
      view_technologies?: unknown;
    };
    const extraProj = project as ExtraProjectFields;

    return {
      name: repository.repoName,
      full_name: `${repository.owner}/${repository.repoName}`,
      default_branch: project.defaultBranch || "main",
      language: "Java",
      build_tool: normalizeBuildTool(project.buildTool),
      java_version: javaVersion,
      java_version_from_build: javaVersion,
      spring_boot_version: project.springBootVersion ?? null,
      java_files: project.javaFiles ?? extraProj.java_files ?? [],
      java_file_count: project.javaFileCount ?? (project.javaFiles?.length || 0),
      config_files: project.configFiles ?? extraProj.config_files ?? [],
      config_file_count: project.configFileCount ?? (project.configFiles?.length || 0),
      other_files: cleanOtherFiles,
      other_file_count: cleanOtherCount,
      total_file_count: project.totalFileCount,
      file_metrics: (project.fileMetrics ?? extraProj.file_metrics) as RepoAnalysis["file_metrics"],
      jsp_count: project.jspFileCount,
      jsf_count: project.jsfFileCount,
      jsp_files: project.jspFiles ?? [],
      jsf_files: project.jsfFiles ?? [],
      view_technologies: (extraProj.viewTechnologies ?? extraProj.view_technologies ?? undefined) as RepoAnalysis["view_technologies"],
    has_tests: Boolean(project.hasTests),
    dependencies,
    ...(() => {
      const rawApiEndpoints = (project.apiEndpoints ?? extraProj.api_endpoints ?? extraProj.apiEndpoints) as
        | DiscoveredApiEndpoint[]
        | { count?: number; endpoints?: DiscoveredApiEndpoint[] }
        | undefined;
      let apiEndpointsList: DiscoveredApiEndpoint[] = [];
      let apiEndpointCount = 0;

      if (Array.isArray(rawApiEndpoints)) {
        apiEndpointsList = rawApiEndpoints;
        apiEndpointCount = typeof project.apiEndpointCount === "number"
          ? project.apiEndpointCount
          : rawApiEndpoints.length;
      } else if (rawApiEndpoints && typeof rawApiEndpoints === "object") {
        if (Array.isArray(rawApiEndpoints.endpoints)) {
          apiEndpointsList = rawApiEndpoints.endpoints;
        }
        apiEndpointCount = typeof rawApiEndpoints.count === "number"
          ? rawApiEndpoints.count
          : (typeof project.apiEndpointCount === "number" ? project.apiEndpointCount : apiEndpointsList.length);
      } else if (typeof project.apiEndpointCount === "number") {
        apiEndpointCount = project.apiEndpointCount;
      }

      const normalizedApiEndpoints: DiscoveredApiEndpoint[] = apiEndpointsList.map((ep, idx) => ({
        id: ep.id || `${ep.controller || ep.className || "Controller"}:${ep.methodName || ep.handlerMethod || "method"}:${ep.httpMethod || ep.method || "GET"}:${ep.path || ep.urlPath || ep.endpoint || ""}:${idx}`,
        httpMethod: (ep.httpMethod || ep.method || "GET").toUpperCase(),
        method: (ep.httpMethod || ep.method || "GET").toUpperCase(),
        path: ep.path || ep.urlPath || ep.endpoint || "/",
        urlPath: ep.urlPath || ep.path || ep.endpoint || "/",
        endpoint: ep.endpoint || ep.path || ep.urlPath || "/",
        controller: ep.controller || ep.className || "Controller",
        className: ep.className || ep.controller || "Controller",
        handlerMethod: ep.handlerMethod || ep.methodName || "",
        methodName: ep.methodName || ep.handlerMethod || "",
        sourceFile: ep.sourceFile || ep.file || "",
        file: ep.file || ep.sourceFile || "",
        module: ep.module || "",
        framework: ep.framework || "Spring Boot",
        detectionStatus: ep.detectionStatus || "DETECTED",
      }));

      return {
        api_endpoints: normalizedApiEndpoints,
        api_endpoint_count: apiEndpointCount || normalizedApiEndpoints.length,
      };
    })(),
    detected_frameworks: (project.frameworks ?? []).map((f) => ({
      name: f,
      path: project.detectedFiles?.pomXml ? "pom.xml" : "build.gradle",
      type: "FRAMEWORK",
    })),
    frameworks: project.frameworks ?? [],
    structure: {
      has_pom_xml: Boolean(project.detectedFiles?.pomXml),
      has_build_gradle: Boolean(project.detectedFiles?.buildGradle),
      has_build_gradle_kts: Boolean(project.detectedFiles?.buildGradleKts),
      has_src_main: Boolean(project.sourceLayout?.hasSrcMain),
      has_src_test: Boolean(project.sourceLayout?.hasSrcTest),
      jsp_count: project.jspFileCount,
      jsf_count: project.jsfFileCount,
    },
    spring_boot_eligibility: springBootEligibility,
    framework_recommendations: project.frameworkRecommendations,
    discovery_stages: project.discoveryStages,
  };
}

/**
 * Run discovery for a job. Reads the response body on both success and error so
 * the backend's clean status/message are always surfaced. Returns the mapped
 * RepoAnalysis (plus the raw discovery summary) for the Discovery UI.
 */
export async function runDiscovery(
  jobId: string,
  githubToken?: string,
  forceRefresh?: boolean
): Promise<DiscoveryAnalysisResult> {
  const response = await performRequest(`/v1/discovery/${encodeURIComponent(jobId)}`, {
    method: "POST",
    body: {
      githubToken: githubToken?.trim() ? githubToken.trim() : undefined,
      forceRefresh: Boolean(forceRefresh),
    },
  });

  const data = (await response.json().catch(() => null)) as
    | (Partial<DiscoveryResponse> & { status?: string; message?: string })
    | null;

  if (!response.ok || !data || data.status !== "DISCOVERY_COMPLETED" || !data.project) {
    const status = (data?.status as DiscoveryStatus) ?? "DISCOVERY_FAILED";
    const message = data?.message ?? "Repository discovery failed. Please try again.";
    throw new DiscoveryApiError(message, status, response.status);
  }

  const discovery = data as DiscoveryResponse;
  return {
    repo_url: discovery.repository.repoUrl,
    owner: discovery.repository.owner,
    repo: discovery.repository.repoName,
    analysis: mapDiscoveryToRepoAnalysis(discovery),
    discovery,
  };
}

export interface DiscoveryProgressResponse {
  jobId: string;
  status: string;
  stage: string;
  progressPercent: number;
  detail: string;
  activeStageId?: import("../hooks/useDiscoveryState").DiscoveryStageId;
}

export async function getDiscoveryProgress(jobId: string): Promise<DiscoveryProgressResponse | null> {
  try {
    return await requestJson<DiscoveryProgressResponse>(
      `/v1/discovery/${encodeURIComponent(jobId)}/progress`,
      "Failed to fetch discovery progress"
    );
  } catch {
    return null;
  }
}

interface MicroserviceEligibilityAnalysisSnapshot {
  build_tool: string | null;
  java_file_count: number;
  has_tests: boolean;
  dependencies: DependencyInfo[];
  structure: RepoAnalysis["structure"];
}

function buildMicroserviceEligibilityAnalysisSnapshot(repoAnalysis: RepoAnalysis): MicroserviceEligibilityAnalysisSnapshot {
  return {
    build_tool: repoAnalysis.build_tool ?? null,
    java_file_count: repoAnalysis.java_files?.length ?? 0,
    has_tests: repoAnalysis.has_tests,
    dependencies: repoAnalysis.dependencies || [],
    structure: repoAnalysis.structure,
  };
}

export type GithubDocumentType = "brd" | "kt";

export interface GithubDocumentRequest {
  repo_url?: string;
  repository_url?: string;
  source_repo_url?: string;
  token?: string;
  github_token?: string;
  job_id?: string;
  migration_job_id?: string;
  source_repo?: string;
  target_repo?: string | null;
  source_java_version?: string;
  target_java_version?: string;
  document_type?: string;
  analysis?: Record<string, unknown>;
}

export interface LocalProjectDocumentRequest extends GithubDocumentRequest {
  analysis: Record<string, unknown>;
}

export interface GithubDocumentResponse {
  html?: string;
  url?: string;
  filename: string;
}

function extractGithubDocumentHtml(data: Record<string, unknown>): string | undefined {
  const nestedData = data.data && typeof data.data === "object"
    ? (data.data as Record<string, unknown>)
    : undefined;
  const htmlCandidates = [
    data.html,
    data.document_html,
    data.html_content,
    data.content,
    data.document,
    data.markup,
    nestedData?.html,
    nestedData?.document_html,
    nestedData?.content,
  ];

  const htmlCandidate = htmlCandidates.find(
    (candidate): candidate is string => typeof candidate === "string" && candidate.trim().length > 0
  );

  return htmlCandidate;
}

function extractGithubDocumentUrl(data: Record<string, unknown>): string | undefined {
  const nestedData = data.data && typeof data.data === "object"
    ? (data.data as Record<string, unknown>)
    : undefined;
  const urlCandidates = [
    data.url,
    data.document_url,
    data.download_url,
    data.file_url,
    nestedData?.url,
    nestedData?.document_url,
    nestedData?.download_url,
  ];

  const urlCandidate = urlCandidates.find(
    (candidate): candidate is string => typeof candidate === "string" && candidate.trim().length > 0
  );

  return urlCandidate;
}

function resolveDocumentUrl(url: string | undefined): string | undefined {
  if (!url || !url.trim()) {
    return undefined;
  }

  return ABSOLUTE_URL_PATTERN.test(url)
    ? url
    : new URL(url.replace(/^\/+/, ""), `${APP_BASE_URL}/`).toString();
}

// List files in a repository (works for public repos without token). The GitHub
// PAT, when present, is sent as an Authorization header, never in the query string.
export async function listRepoFiles(repoUrl: string, token: string = "", path: string = ""): Promise<RepoFilesResponse> {
  return requestJson<RepoFilesResponse>("/github/list-files", "Failed to list files", {
    query: { repo_url: repoUrl, path },
    headers: authHeader(token),
  });
}

// Get file content (works for public repos without token). The GitHub PAT, when
// present, is sent as an Authorization header, never in the query string.
export async function getFileContent(repoUrl: string, filePath: string, token: string = ""): Promise<FileContentResponse> {
  return requestJson<FileContentResponse>("/github/file-content", "Failed to get file content", {
    query: { repo_url: repoUrl, file_path: filePath },
    headers: authHeader(token),
  });
}

/* -------------------------------------------------------------------------- */
/* Repository Files (Discovery page) — GET /api/v1/discovery/{jobId}/files      */
/* and GET /api/v1/discovery/{jobId}/file                                       */
/*                                                                              */
/* Reads the repository clone Discovery already made on disk (original-repo),  */
/* rather than re-fetching from GitHub. Works for any repo Discovery has run   */
/* on, with no GitHub API calls/rate limits. Folder contents are fetched one   */
/* level at a time (lazy), so large repos stay fast.                           */
/* -------------------------------------------------------------------------- */

export interface DiscoveryFilesResponse {
  jobId: string;
  path: string;
  files: RepoFile[];
}

export interface DiscoveryFileContentResponse {
  jobId: string;
  filePath: string;
  content: string;
  size: number;
}

export async function listDiscoveryFiles(jobId: string, path: string = ""): Promise<DiscoveryFilesResponse> {
  return requestJson<DiscoveryFilesResponse>(
    `/v1/discovery/${encodeURIComponent(jobId)}/files`,
    "Failed to list repository files",
    { query: { path } }
  );
}

export async function getDiscoveryFileContent(jobId: string, path: string): Promise<DiscoveryFileContentResponse> {
  return requestJson<DiscoveryFileContentResponse>(
    `/v1/discovery/${encodeURIComponent(jobId)}/file`,
    "Failed to load file content",
    { query: { path } }
  );
}

export async function getMicroserviceEligibility(
  repoUrl: string,
  token: string = "",
  repoAnalysis?: RepoAnalysis,
): Promise<MicroserviceEligibilityResult> {
  return requestJson<MicroserviceEligibilityResult>(
    "/github/microservice-eligibility",
    "Failed to get microservice eligibility",
    {
      method: "POST",
      body: {
        repo_url: repoUrl,
        token,
        analysis: repoAnalysis ? buildMicroserviceEligibilityAnalysisSnapshot(repoAnalysis) : undefined,
      },
    }
  );
}

// Real static analysis over the job's already-cloned repository (Discovery
// workspace) — detects controllers/services/repositories/entities, groups
// them into per-controller business chunks via their actual dependency
// graph, and scores each chunk. No GitHub API calls, no mock data.
export async function getDiscoveryMicroserviceEligibility(jobId: string): Promise<MicroserviceEligibilityResult> {
  return requestJson<MicroserviceEligibilityResult>(
    `/v1/discovery/${encodeURIComponent(jobId)}/microservice-eligibility`,
    "Failed to get microservice eligibility"
  );
}

export async function getLocalProjectMicroserviceEligibility(
  projectPath: string,
  repoAnalysis?: RepoAnalysis,
): Promise<MicroserviceEligibilityResult> {
  return requestJson<MicroserviceEligibilityResult>(
    "/local-project/microservice-eligibility",
    "Failed to get local project microservice eligibility",
    {
      method: "POST",
      body: {
        project_path: projectPath,
        analysis: repoAnalysis ? buildMicroserviceEligibilityAnalysisSnapshot(repoAnalysis) : undefined,
      },
    }
  );
}

export async function generateGithubDocument(
  documentType: GithubDocumentType,
  request: GithubDocumentRequest
): Promise<GithubDocumentResponse> {
  const response = await performRequest(`/github/generate-${documentType}-document`, {
    method: "POST",
    body: request,
  });

  const contentType = response.headers.get("content-type") || "";
  const bodyText = await response.text();
  const fallbackMessage = `Failed to generate ${documentType.toUpperCase()} document`;

  if (!response.ok) {
    if (contentType.includes("application/json")) {
      try {
        const data = JSON.parse(bodyText);
        const detail = data?.detail || data?.message || data?.error;
        throw new Error(
          typeof detail === "string" && detail.trim().length > 0 ? detail : fallbackMessage
        );
      } catch {
        throw new Error(bodyText || fallbackMessage);
      }
    }

    throw new Error(bodyText || fallbackMessage);
  }

  const repoNameCandidate =
    request.source_repo ||
    request.repository_url ||
    request.repo_url ||
    "repository";
  const repoName = repoNameCandidate
    .split("/")
    .filter(Boolean)
    .pop()
    ?.replace(/\.git$/i, "") || "repository";
  const filename = `${repoName.toUpperCase()}-TECHNICAL-DOCUMENT.html`;

  if (contentType.includes("application/json")) {
    const data = bodyText ? JSON.parse(bodyText) : {};
    const html = extractGithubDocumentHtml(data);
    const url = extractGithubDocumentUrl(data);

    if (!html && !url) {
      throw new Error(
        `${documentType.toUpperCase()} document endpoint responded without HTML or download URL`
      );
    }

    return {
      html,
      url: resolveDocumentUrl(url),
      filename:
        typeof data?.filename === "string" && data.filename.trim().length > 0
          ? data.filename
          : filename,
    };
  }

  if (!bodyText.trim()) {
    throw new Error(`${documentType.toUpperCase()} document endpoint returned empty content`);
  }

  return {
    html: bodyText,
    filename,
  };
}

export async function generateLocalProjectDocument(
  request: LocalProjectDocumentRequest
): Promise<GithubDocumentResponse> {
  const response = await requestJson<GithubDocumentResponse>(
    "/local-project/generate-brd-document",
    "Failed to generate BRD document",
    {
      method: "POST",
      body: request,
    }
  );
  return {
    ...response,
    url: resolveDocumentUrl(response.url),
  };
}

export interface BrdMetadata {
  job_id?: string;
  filename: string;
  file_type?: string;
  size_bytes?: number;
  size?: number;
  uploaded_at?: string;
  uploadedAt?: string;
  status?: string;
}

export async function uploadBrdDocument(jobId: string, file: File): Promise<BrdMetadata> {
  const formData = new FormData();
  formData.append("file", file);

  return requestJson<BrdMetadata>(
    `/v1/discovery/${encodeURIComponent(jobId)}/brd`,
    "Failed to upload BRD document",
    {
      method: "POST",
      body: formData,
    }
  );
}

export const uploadBrd = uploadBrdDocument;

export async function getBrdMetadata(jobId: string): Promise<BrdMetadata | null> {
  try {
    const res = await requestJson<BrdMetadata & { status?: string }>(
      `/v1/discovery/${encodeURIComponent(jobId)}/brd`,
      "Failed to fetch BRD metadata"
    );
    if (!res || res.status === "NONE") return null;
    return res;
  } catch {
    return null;
  }
}

export async function deleteBrdDocument(jobId: string): Promise<{ status: string; job_id: string }> {
  return requestJson<{ status: string; job_id: string }>(
    `/v1/discovery/${encodeURIComponent(jobId)}/brd`,
    "Failed to remove BRD document",
    {
      method: "DELETE",
    }
  );
}

export async function getBrdDocumentBlob(jobId: string): Promise<{ blob: Blob; contentType: string }> {
  const response = await performRequest(`/v1/discovery/${encodeURIComponent(jobId)}/brd/file`);
  if (!response.ok) {
    throw new Error("Failed to load BRD document for viewing.");
  }
  const contentType = response.headers.get("content-type") || "application/octet-stream";
  const blob = await response.blob();
  return { blob, contentType };
}

export interface DashboardStatsResponse {
  repositoryId: string;
  jobId: string;
  repositoryName: string;
  repositoryComposition: {
    totalFiles: number;
    javaFiles: number;
    xmlConfigFiles: number;
    otherFiles: number;
  };
  modernizationAnalysis: {
    sourceJavaVersion: string;
    javaVersionFeatureCount: number;
    deprecatedApiCount?: number;
    javaxMigrationCount?: number;
    oldSpringUsageCount?: number;
    securityVulnerabilityCount?: number;
    codeSmellCount?: number;
    legacyApiCount?: number;
    migrationBlockerCount?: number;
  };
  migrationSummary: {
    status: string;
    totalItems: number;
    autoMigratable: number;
    manualChanges: number;
    needsReview: number;
    compilationErrors: number;
    completed: number;
  };
  generatedAt: string;
}

export async function getDashboardStats(jobId: string): Promise<DashboardStatsResponse> {
  return requestJson<DashboardStatsResponse>(
    `/v1/discovery/${encodeURIComponent(jobId)}/dashboard-stats`,
    "Failed to fetch dashboard statistics"
  );
}
