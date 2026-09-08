import { requestJson } from "@/services/http/client";

export type ProposedTestType = "UNIT" | "API" | "UI";
export type ProposedTestPriority = "HIGH" | "MEDIUM" | "LOW";
export type ProposedTestStatus =
  | "PROPOSED"
  | "APPROVED"
  | "REJECTED"
  | "READY"
  | "RUNNING"
  | "PASSED"
  | "FAILED"
  | "SKIPPED"
  | "NOT_EXECUTED";

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
  execution_result?: ExecutionResult | null;
}

export interface ProposedTestTypeBreakdown {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
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
