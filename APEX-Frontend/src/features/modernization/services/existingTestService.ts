import { requestJson } from "@/services/http/client";

// ── Individual test result ────────────────────────────────────────────────────

export interface ApiEvidence {
  method: string;
  url: string;
  requestBody?: string | null;
  responseStatus: number;
  responseBody?: string | null;
  assertions: { name: string; status: "PASSED" | "FAILED" | string }[];
}

export interface TestResult {
  test_id?: string;
  testId?: string;
  execution_id?: string;
  executionId?: string;
  test_name: string;
  suite: string;
  status: "PASSED" | "FAILED" | "SKIPPED" | "ERROR" | "NOT_EXECUTED";
  duration: string;
  file: string;
  type?: string;
  test_type?: "JUNIT" | "API" | "UI" | "UNKNOWN" | string;
  testType?: "JUNIT" | "API" | "UI" | "UNKNOWN" | string;
  framework?: string;
  engine?: string;
  failure_message?: string | null;
  stack_trace?: string | null;
  stdout?: string | null;
  stderr?: string | null;
  error_category?: string | null;
  errorCategory?: string | null;
  error_code?: string | null;
  errorCode?: string | null;
  root_cause?: string | null;
  rootCause?: string | null;
  apex_execution?: string | null;
  apexExecution?: string | null;
  unavailable_reason?: string | null;
  unavailableReason?: string | null;
  details?: {
    stdout?: string | null;
    stderr?: string | null;
    error?: string | null;
    stackTrace?: string | null;
    errorCategory?: string | null;
    rootCause?: string | null;
    apexExecution?: string | null;
  } | null;
  report_url?: string | null;
  screenshot_url?: string | null;
  screenshotUrl?: string | null;
  video_url?: string | null;
  videoUrl?: string | null;
  trace_url?: string | null;
  traceUrl?: string | null;
  api_evidence?: ApiEvidence | null;
  apiEvidence?: ApiEvidence | null;
  evidence?: any;
}

// ── File breakdown ────────────────────────────────────────────────────────────

export interface FileSummary {
  file: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  not_executed?: number;
}

// ── Report availability ───────────────────────────────────────────────────────

export interface ReportAvailabilityEntry {
  available: boolean;
  report_url?: string | null;
  download_url?: string | null;
  label?: string;
}

export interface ReportAvailability {
  surefire?: ReportAvailabilityEntry;
  playwright?: ReportAvailabilityEntry;
  allure?: ReportAvailabilityEntry;
}

// ── Scan response ─────────────────────────────────────────────────────────────

export interface ExistingTestScanResponse {
  testCasesFound?: number;
  status?: "READY" | "NO_TESTS_FOUND" | string;
  message?: string;
  tests?: any[];
  total: number;
  framework: string;
  test_cases: any[];
}

// ── Status response ───────────────────────────────────────────────────────────

export interface ExistingTestStatusResponse {
  status: "IDLE" | "RUNNING" | "IN_PROGRESS" | "COMPLETED" | "FAILED" | "ERROR" | "STOPPED" | "NO_TESTS_FOUND";
  executed: boolean;
  logs: { ts: string; msg: string; level: string }[];
  result?: {
    status: string;
    executed: boolean;
    testCasesFound?: number;
    message?: string;
    tests?: any[];
    metrics?: {
      total: number;
      executed?: number;
      passed: number;
      failed: number;
      skipped: number;
      not_executed?: number;
      duration: string;
      pass_percentage: string;
      type: string;
      existing_coverage: string;
      execution_status?: string;
      compilation_error?: string | null;
    };
    framework_info?: {
      detected_framework: string;
      build_tool: string | null;
      test_source_dir: string;
    };
    test_results: TestResult[];
    file_breakdown?: FileSummary[];
    report_availability?: ReportAvailability;
  };
}

// ── API functions ─────────────────────────────────────────────────────────────

export async function scanExistingTests(jobId: string): Promise<ExistingTestScanResponse> {
  return requestJson<ExistingTestScanResponse>(
    `/v1/existing-tests/scan/${encodeURIComponent(jobId)}`,
    "Failed to scan existing tests"
  );
}

export async function runExistingTests(jobId: string, testSelection: any[] | null = null): Promise<any> {
  const selectionArray = Array.isArray(testSelection)
    ? testSelection.map((t) => ({
        name: t.name || t.methodname || "",
        suite: t.suite || t.classname || t.module || ""
      }))
    : [];

  return requestJson<any>(
    `/v1/existing-tests/run/${encodeURIComponent(jobId)}`,
    "Failed to run existing tests",
    {
      method: "POST",
      body: selectionArray
    }
  );
}

export async function getExistingTestsStatus(jobId: string): Promise<ExistingTestStatusResponse> {
  return requestJson<ExistingTestStatusResponse>(
    `/v1/existing-tests/status/${encodeURIComponent(jobId)}`,
    "Failed to fetch test status"
  );
}

export async function resetExistingTests(jobId: string): Promise<{ reset: boolean }> {
  return requestJson<{ reset: boolean }>(
    `/v1/existing-tests/reset/${encodeURIComponent(jobId)}`,
    "Failed to reset existing tests",
    { method: "DELETE" }
  );
}

export async function stopExistingTests(jobId: string): Promise<{ stopped: boolean }> {
  return requestJson<{ stopped: boolean }>(
    `/v1/existing-tests/stop/${encodeURIComponent(jobId)}`,
    "Failed to stop existing tests",
    { method: "POST" }
  );
}
