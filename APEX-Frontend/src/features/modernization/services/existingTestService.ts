import { requestJson } from "@/services/http/client";

export interface ExistingTestClass {
    id: string;
    className: string;
    filePath: string;
    framework: string;
    methods: string[];
}

export interface TestDiscoveryResult {
    framework: string;
    buildTool: string;
    tests: ExistingTestClass[];
    error: string | null;
}

export interface TestResultDetail {
    test_class: string;
    test_method: string;
    status: string;
    execution_time_seconds: number;
    error_message: string | null;
}

export interface ExistingTestRunStatus {
    status: "IDLE" | "RUNNING" | "COMPLETED" | "FAILED";
    discovered: number;
    executed: number;
    passed: number;
    failed: number;
    skipped: number;
    results: TestResultDetail[];
    logs: string[];
    error: string | null;
}

export async function discoverExistingTests(jobId: string): Promise<TestDiscoveryResult> {
    return requestJson<TestDiscoveryResult>(
        `/v1/existing-tests/discover/${encodeURIComponent(jobId)}`,
        "Failed to discover existing test cases"
    );
}

export async function runExistingTests(jobId: string, testClasses: string[]): Promise<ExistingTestRunStatus> {
    return requestJson<ExistingTestRunStatus>(
        `/v1/existing-tests/run/${encodeURIComponent(jobId)}`,
        "Failed to start existing tests",
        {
            method: "POST",
            body: { testClasses }
        }
    );
}

export async function getExistingTestStatus(jobId: string): Promise<ExistingTestRunStatus> {
    return requestJson<ExistingTestRunStatus>(
        `/v1/existing-tests/status/${encodeURIComponent(jobId)}`,
        "Failed to get existing test execution status"
    );
}
