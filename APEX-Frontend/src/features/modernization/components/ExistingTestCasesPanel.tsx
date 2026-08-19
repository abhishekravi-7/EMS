import React, { useState, useMemo } from "react";
import {
  FaPlay,
} from "react-icons/fa";
import { FunctionalTestingTabs } from "./FunctionalTestingTabs";
import { ExistingTestAnalytics, type DiscoveredOrExecutedTest } from "./ExistingTestAnalytics";
import { ExistingTestCoverage } from "./ExistingTestCoverage";
import { ExistingTestTable, type TestResult } from "./ExistingTestTable";

interface TestCase {
  name: string;
  file: string;
  framework: string;
  type: string;
  category?: "UI" | "API" | "UNIT" | "INTEGRATION" | string;
  module: string;
  classname: string;
  methodname: string;
  status: string;
  priority?: string;
  test_name?: string;
  title?: string;
  suite?: string;
  spec?: string;
  test_type?: string;
  testType?: string;
  test_id?: string;
  testId?: string;
}

interface ExistingTestCasesPanelProps {
  jobId: string;
  discoveredTests: TestCase[];
  framework: string;
  onRunSelected?: (selection: TestCase[]) => void;
  onRunAll?: () => void;
  isRunning: boolean;
  onViewSuite?: (suiteName: string) => void;
  onSelectTest?: (test: any) => void;
}

export function ExistingTestCasesPanel({
  jobId,
  discoveredTests,
  framework,
  onRunSelected,
  onRunAll,
  isRunning,
  onViewSuite,
  onSelectTest,
}: ExistingTestCasesPanelProps) {
  const [activeTab, setActiveTab] = useState<"FUNCTIONAL" | "BUSINESS">("FUNCTIONAL");

  const handleRun = () => {
    if (onRunAll) {
      onRunAll();
    } else if (onRunSelected) {
      onRunSelected(discoveredTests);
    }
  };

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

    discoveredTests.forEach((t: any, idx: number) => {
      const testName = (t.test_name || t.name || t.methodname || t.title || `scenario_${idx + 1}`).replace(/\(\s*\)$/, "");
      const rawSuite = t.classname || t.suite || t.spec || t.file || "TestSuite";
      const testSuite = rawSuite.split("/").pop()?.split("\\").pop()?.replace(/\.(java|kt)$/, "").split(".").pop() || "TestSuite";
      const testFile = t.file || `${testSuite}.java`;

      const identity = `${testSuite.toLowerCase()}::${testName.toLowerCase()}`;
      if (seen.has(identity)) return;
      seen.add(identity);

      const rawType = (t.test_type || t.testType || t.type || (t.category === "UI" ? "UI" : "API")).toUpperCase();
      const displayType = rawType === "UNIT" ? "API" : rawType;

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
        statusLabel={discoveredTests.length > 0 ? "Ready to Execute" : undefined}
      />

      {/* Top Two Cards: Dynamic Suite Composition Breakdown & Risk based Suite Coverage (BEFORE Execution) */}
      <ExistingTestAnalytics
        discoveredTests={discoveredTests}
        metrics={discoveryMetrics}
        frameworkInfo={{
          detected_framework: framework || "JUnit",
          build_tool: "MAVEN",
          test_source_dir: "src/test/java",
        }}
        onViewSuite={onViewSuite}
      />

      {/* Existing Test Coverage 8-Cards Grid (Discovery State Before Execution) */}
      <ExistingTestCoverage
        metrics={discoveryMetrics}
        isExecuted={false}
        frameworkInfo={{
          detected_framework: framework || "JUnit",
          build_tool: "MAVEN",
          test_source_dir: "src/test/java",
        }}
        onRunAll={handleRun}
      />

      {/* Action Bar: Run All Tests */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "16px 20px",
          background: "#f8fafc",
          borderRadius: 14,
          border: "1px solid #e2e8f0",
        }}
      >
        <div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "#0f172a" }}>
            Ready to execute existing test cases
          </div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
            {discoveredTests.length} test{discoveredTests.length > 1 ? "s" : ""} discovered from repository analysis (0 executed)
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={isRunning || discoveredTests.length === 0}
          style={{
            padding: "10px 24px",
            background: "#0f172a",
            color: "#fff",
            borderRadius: 10,
            fontWeight: 800,
            fontSize: 13,
            border: "none",
            cursor: isRunning || discoveredTests.length === 0 ? "not-allowed" : "pointer",
            display: "flex",
            alignItems: "center",
            gap: 8,
            boxShadow: "0 2px 8px rgba(15, 23, 42, 0.15)",
          }}
        >
          <FaPlay style={{ fontSize: 10, color: "#22c55e" }} />
          Run All Tests
        </button>
      </div>

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
          onSelectTest={(t) => {
            if (onSelectTest) onSelectTest(t);
          }}
        />
      )}
    </div>
  );
}
