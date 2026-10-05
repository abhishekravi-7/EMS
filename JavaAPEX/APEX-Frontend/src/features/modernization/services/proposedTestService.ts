import { requestJson } from "@/services/http/client";
export { formatProposedTestDisplayName } from "../utils/proposedTestFormatters";
export type { ProposedTestLike } from "../utils/proposedTestFormatters";

export type ProposedTestType = "UNIT" | "API" | "UI";
export type ProposedTestPriority = "HIGH" | "MEDIUM" | "LOW";
export type ProposedTestStatus =
  | "PROPOSED"
  | "APPROVED"
  | "REJECTED"
  | "READY"
  | "QUEUED"
  | "RUNNING"
  | "PASSED"
  | "FAILED"
  | "SKIPPED"
  | "BLOCKED"
  | "NOT_EXECUTED"
  | "APPLICATION_UNAVAILABLE";

export interface StepExecutionRecord {
  step_number: number;
  description: string;
  status: ProposedTestStatus;
  duration?: string;
  error?: string | null;
}

export interface ApiTestSpec {
  method: string;
  endpoint: string;
  headers?: Record<string, string>;
  request_body?: unknown;
  expected_status?: number;
  expected_response?: unknown;
  assertions?: string[];
}

export interface UnitTestSpec {
  target_class?: string;
  target_method?: string;
  input_data?: unknown;
  mock_data?: unknown;
  expected_output?: unknown;
  assertions?: string[];
}

export interface UiTestSpec {
  target_route?: string;
  input_fields?: Array<{ name: string; type: string }>;
  actions?: string[];
  expected_elements?: string[];
  selectors?: Record<string, string>;
  assertions?: string[];
}

export interface ExecutionEvidence {
  screenshot_url?: string | null;
  video_url?: string | null;
  logs_url?: string | null;
  screenshot_available?: boolean;
  video_available?: boolean;
  video_duration?: number | null;
  video_duration_formatted?: string | null;
  video_size?: number | null;
  recording_status?: string | null;
  trace_url?: string | null;
}

export interface ExecutionResult {
  status: ProposedTestStatus;
  duration?: string;
  executed_at?: string | null;
  stdout?: string | null;
  stderr?: string | null;
  error?: string | null;
  stack_trace?: string | null;
  actual_status_code?: number | null;
  actual_response?: unknown;
  evidence?: ExecutionEvidence;
  assertions_passed?: number;
  assertions_failed?: number;
  steps_execution?: StepExecutionRecord[];
}

export interface ProposedTestCase {
  id: string;
  title: string;
  description: string;
  type: ProposedTestType;
  priority: ProposedTestPriority;
  source: string;
  reason: string;
  preconditions?: string[];
  steps?: string[];
  expected_result: string;
  status: ProposedTestStatus;
  generation_source?: string;
  api_spec?: ApiTestSpec | null;
  unit_spec?: UnitTestSpec | null;
  ui_spec?: UiTestSpec | null;
  validation?: {
    status: string;
    issue?: string | null;
    playwright_executable?: boolean;
    evidence?: string[];
  } | null;
  execution_result?: ExecutionResult | null;
  baseline_execution_result?: ExecutionResult | null;
}

export interface ProposedTestTypeBreakdown {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  blocked?: number;
}

export interface ProposedTestPriorityBreakdown {
  high: number;
  medium: number;
  low: number;
}

export interface ProposedTestMetrics {
  total: number;
  approved: number;
  rejected: number;
  executed: number;
  passed: number;
  failed: number;
  skipped: number;
  blocked?: number;
  not_executed: number;
  gaps_count?: number;
  ai_generated_count?: number;
  brd_generated_count?: number;
  duration: string;
  pass_percentage: string;
  unit_metrics?: ProposedTestTypeBreakdown;
  api_metrics?: ProposedTestTypeBreakdown;
  ui_metrics?: ProposedTestTypeBreakdown;
  priority_metrics?: ProposedTestPriorityBreakdown;
}

export interface ProposedTestStatusResponse {
  job_id: string;
  status: "IDLE" | "RUNNING" | "COMPLETED" | "FAILED";
  progress?: {
    total: number;
    completed: number;
  };
  allure_report_available?: boolean;
  allure_report_url?: string | null;
  playwright_report_available?: boolean;
  playwright_report_url?: string | null;
  selected_sources?: string[];
  metrics?: ProposedTestMetrics;
  logs?: Array<{ ts: string; msg: string; level: string }>;
  proposals?: ProposedTestCase[];
}

export interface ProposedTestResultsResponse {
  job_id: string;
  status: string;
  allure_report_available?: boolean;
  allure_report_url?: string | null;
  playwright_report_available?: boolean;
  playwright_report_url?: string | null;
  selected_sources?: string[];
  metrics?: ProposedTestMetrics;
  test_cases: ProposedTestCase[];
}

// ── API Functions ─────────────────────────────────────────────────────────────

export function getAllureReportUrl(jobId: string): string {
  return `/api/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/allure-report/index.html`;
}

export async function generateProposedTests(jobId: string): Promise<ProposedTestCase[]> {
  return requestJson<ProposedTestCase[]>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/generate`,
    "Failed to generate proposed test cases",
    { method: "POST" }
  );
}

export async function getProposedTests(jobId: string): Promise<ProposedTestCase[]> {
  return requestJson<ProposedTestCase[]>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests`,
    "Failed to fetch proposed test cases"
  );
}

export async function getProposedTest(jobId: string, testId: string): Promise<ProposedTestCase> {
  return requestJson<ProposedTestCase>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/${encodeURIComponent(testId)}`,
    "Failed to fetch proposed test case details"
  );
}

export async function updateProposedTest(
  jobId: string,
  testId: string,
  updates: Partial<ProposedTestCase>
): Promise<ProposedTestCase> {
  return requestJson<ProposedTestCase>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/${encodeURIComponent(testId)}`,
    "Failed to update proposed test case",
    {
      method: "PUT",
      body: updates,
    }
  );
}

export async function approveProposedTest(jobId: string, testId: string): Promise<ProposedTestCase> {
  return requestJson<ProposedTestCase>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/${encodeURIComponent(testId)}/approve`,
    "Failed to approve proposed test case",
    { method: "POST" }
  );
}

export async function rejectProposedTest(jobId: string, testId: string): Promise<ProposedTestCase> {
  return requestJson<ProposedTestCase>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/${encodeURIComponent(testId)}/reject`,
    "Failed to reject proposed test case",
    { method: "POST" }
  );
}

export async function bulkSetProposedTestStatus(
  jobId: string,
  testIds: string[],
  status: ProposedTestStatus
): Promise<ProposedTestCase[]> {
  return requestJson<ProposedTestCase[]>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/bulk-status`,
    "Failed to update test statuses",
    {
      method: "POST",
      body: { test_ids: testIds, status },
    }
  );
}

export interface ProposedTestRunResponse {
  status?: string;
  jobId?: string;
  message?: string;
  [key: string]: unknown;
}

export async function runApprovedProposedTests(
  jobId: string,
  payload?: { sources?: string[]; test_ids?: string[] }
): Promise<ProposedTestRunResponse> {
  return requestJson<ProposedTestRunResponse>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/run`,
    "Failed to run approved proposed tests",
    {
      method: "POST",
      body: payload,
    }
  );
}

export async function getProposedTestsStatus(jobId: string): Promise<ProposedTestStatusResponse> {
  return requestJson<ProposedTestStatusResponse>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/status`,
    "Failed to fetch proposed tests status"
  );
}

export async function getProposedTestsResults(jobId: string): Promise<ProposedTestResultsResponse> {
  return requestJson<ProposedTestResultsResponse>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/results`,
    "Failed to fetch proposed test results"
  );
}

export interface AppReadinessResponse {
  job_id: string;
  base_url: string;
  ready: boolean;
  port: number;
  http_status?: number | null;
  health_endpoint?: string | null;
  error?: string | null;
  elapsed_seconds?: number;
  build_status?: string;
  build_success?: boolean | null;
  app_startup_status?: string;
  app_readiness_status_stored?: string;
  app_pid?: number | null;
}

export async function getAppReadiness(jobId: string): Promise<AppReadinessResponse> {
  return requestJson<AppReadinessResponse>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/app-readiness`,
    "Failed to check app readiness"
  );
}

export interface TestComparisonItem {
  id: string;
  title: string;
  type: ProposedTestType;
  source: string;
  baseline_status: ProposedTestStatus;
  target_status: ProposedTestStatus;
  match: boolean;
  is_regression: boolean;
  is_improvement: boolean;
  baseline_duration: string;
  target_duration: string;
}

export interface ProposedTestComparisonResponse {
  job_id: string;
  baseline_available: boolean;
  target_available: boolean;
  baseline_metrics: ProposedTestMetrics;
  target_metrics: ProposedTestMetrics;
  parity_percentage: string;
  regressions_count: number;
  improvements_count: number;
  preserved_passed_count: number;
  source_status: {
    build_success?: boolean;
    startup_status?: string;
    readiness_status?: string;
    base_url?: string | null;
    error?: string | null;
  };
  target_status: {
    app_ready?: boolean;
    error?: string | null;
  };
  test_comparisons: TestComparisonItem[];
}

export async function getProposedTestBaseline(jobId: string): Promise<ProposedTestResultsResponse> {
  return requestJson<ProposedTestResultsResponse>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/baseline`,
    "Failed to fetch baseline proposed test results"
  );
}

export async function runProposedTestBaseline(
  jobId: string,
  buildTool = "MAVEN"
): Promise<ProposedTestResultsResponse> {
  return requestJson<ProposedTestResultsResponse>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/baseline/run?build_tool=${encodeURIComponent(buildTool)}`,
    "Failed to run baseline proposed tests",
    { method: "POST" }
  );
}

export async function getProposedTestComparison(jobId: string): Promise<ProposedTestComparisonResponse> {
  return requestJson<ProposedTestComparisonResponse>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/comparison`,
    "Failed to fetch proposed test comparison"
  );
}

export interface ProposedTestReportResponse {
  job_id: string;
  test_id: string;
  title: string;
  type: string;
  source: string;
  status: string;
  description?: string;
  steps?: string[];
  preconditions?: string[];
  expected_result?: string;
  api_spec?: ApiTestSpec | null;
  ui_spec?: UiTestSpec | null;
  execution_result?: ExecutionResult | null;
  baseline_execution_result?: ExecutionResult | null;
  api_trace?: any;
  browser_log?: string | null;
  has_artifacts: boolean;
  report_available: boolean;
}

export async function getProposedTestReport(
  jobId: string,
  testId: string
): Promise<ProposedTestReportResponse> {
  return requestJson<ProposedTestReportResponse>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/${encodeURIComponent(testId)}/report`,
    "Failed to fetch proposed test report"
  );
}

export interface InlinePromptDiff {
  intent: "ADD" | "MODIFY" | "REMOVE" | "REGENERATE-SCOPED" | "CLARIFICATION_NEEDED";
  added: ProposedTestCase[];
  modified: Array<{ id: string; changed_fields: Record<string, any> }>;
  removed: string[];
  skipped_as_duplicate: Array<{ attempted_scenario: string; duplicate_of_id: string }>;
  unmet_requests: Array<{ requested: string; reason_not_fulfilled: string }>;
  clarification_needed: string | null;
}

export async function previewInlinePrompt(
  jobId: string,
  prompt: string
): Promise<InlinePromptDiff> {
  return requestJson<InlinePromptDiff>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/inline-prompt/preview`,
    "Failed to preview inline prompt diff",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    }
  );
}

export async function applyInlinePrompt(
  jobId: string,
  diff: InlinePromptDiff
): Promise<ProposedTestCase[]> {
  return requestJson<ProposedTestCase[]>(
    `/v1/migration/${encodeURIComponent(jobId)}/proposed-tests/inline-prompt/apply`,
    "Failed to apply inline prompt diff",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ diff }),
    }
  );
}

