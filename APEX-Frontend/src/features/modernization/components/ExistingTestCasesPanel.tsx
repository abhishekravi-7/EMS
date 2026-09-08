import React, { useState, useMemo } from "react";
import { FaInfoCircle } from "react-icons/fa";
import { FunctionalTestingTabs } from "./FunctionalTestingTabs";
import { ExistingTestCoverage } from "./ExistingTestCoverage";
import { ExistingTestTable, type TestResult } from "./ExistingTestTable";
import { classifyTestType } from "../services/existingTestService";

export type TestCase = TestResult;

interface ExistingTestCasesPanelProps {
  jobId: string;
  discoveredTests: TestResult[];
  framework: string;
  onRunSelected?: (selection: TestResult[]) => void;
  onRunAll?: () => void;
  isRunning?: boolean;
  onViewSuite?: (suiteName: string) => void;
  onSelectTest?: (test: TestResult) => void;
}

export function ExistingTestCasesPanel({
  jobId,
  discoveredTests,
  framework,
  isRunning = false,
  onViewSuite: _onViewSuite,
  onSelectTest: _onSelectTest,
}: ExistingTestCasesPanelProps) {
  const [activeTab, setActiveTab] = useState<"FUNCTIONAL" | "BUSINESS">("FUNCTIONAL");

  const discoveryMetrics = {
    total: discoveredTests.length,
    executed: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    not_executed: discoveredTests.length,
    duration: "—",
    pass_percentage: "—",
    type: framework || "JUnit",
    existing_coverage: "N/A",
  };

  // Map discovered test cases to TestResult format with NOT_EXECUTED status and duration "—"
  const mappedDiscoveredTests: TestResult[] = useMemo(() => {
    const seen = new Set<string>();
    const list: TestResult[] = [];

    discoveredTests.forEach((t: TestCase, idx: number) => {
      const testName = (t.test_name || t.name || t.methodname || t.title || `scenario_${idx + 1}`).replace(/\(\s*\)$/, "");
      const rawSuite = t.classname || t.suite || t.spec || t.file || "TestSuite";
      const testSuite = rawSuite.split("/").pop()?.split("\\").pop()?.replace(/\.(java|kt)$/, "").split(".").pop() || "TestSuite";
      const testFile = t.file || `${testSuite}.java`;

      const identity = `${testSuite.toLowerCase()}::${testName.toLowerCase()}`;
      if (seen.has(identity)) return;
      seen.add(identity);

      const displayType = classifyTestType(t);

      list.push({
        testId: t.test_id || t.testId || `TEST-${idx + 1}`,
        test_name: testName,
        name: testName,
        title: testName,
        suite: testSuite,
        spec: testSuite,
        status: "NOT_EXECUTED",
        duration: "—",
        file: testFile,
        type: displayType,
        testType: displayType,
        test_type: displayType,
        category: displayType,
        framework: t.framework || framework || "JUnit",
        error: null,
        failure_message: null,
      });
    });

    return list;
  }, [discoveredTests, framework]);

  if (discoveredTests.length === 0) {
    return (
      <div
        style={{
          background: "#fff",
          borderRadius: 20,
          border: "1px solid #e2e8f0",
          padding: "48px 24px",
          marginTop: 24,
          boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 12,
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: "50%",
            background: "#f1f5f9",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#64748b",
            fontSize: 22,
          }}
        >
          <FaInfoCircle />
        </div>
        <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>
          No Test Cases Available
        </div>
        <div style={{ fontSize: 13, color: "#64748b", maxWidth: 360, lineHeight: 1.5 }}>
          No existing test cases were found in this repository.
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        background: "#fff",
        borderRadius: 20,
        border: "1px solid #e2e8f0",
        padding: "28px",
        marginTop: 24,
        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
        display: "flex",
        flexDirection: "column",
        gap: 20,
      }}
    >
      {/* Top Tabs: Functional Testing Summary & Business Report Summary */}
      <FunctionalTestingTabs
        activeTab={activeTab}
        onTabChange={setActiveTab}
        isRunning={isRunning}
        statusLabel={discoveredTests.length > 0 ? "Discovered" : undefined}
      />

      {/* Existing Test Coverage 8-Cards Grid (Discovered State) */}
      <ExistingTestCoverage
        jobId={jobId}
        metrics={discoveryMetrics}
        discoveredTests={discoveredTests}
        testResults={mappedDiscoveredTests}
        isExecuted={false}
        frameworkInfo={{
          detected_framework: framework || "JUnit",
          build_tool: "MAVEN",
          test_source_dir: "src/test/java",
        }}
      />

      {/* Existing Tests Validation Report Table (Showing All Discovered Tests with NOT EXECUTED Status) */}
      {mappedDiscoveredTests.length > 0 && (
        <ExistingTestTable
          title="Existing Tests Validation Report"
          testResults={mappedDiscoveredTests}
          frameworkInfo={{
            detected_framework: framework || "JUnit",
            build_tool: "MAVEN",
            test_source_dir: "src/test/java",
          }}
          hasRun={false}
          isRunning={isRunning}
        />
      )}
    </div>
  );
}
