import React, { useState, useMemo } from "react";
import { FaInfoCircle, FaSpinner } from "react-icons/fa";
import { FunctionalTestingTabs } from "./FunctionalTestingTabs";
import { ExistingTestCoverage } from "./ExistingTestCoverage";
import { ExistingTestTable, type TestResult } from "./ExistingTestTable";
import { classifyTestType, deriveTestingTypes, type TestSelectionItem } from "../services/existingTestService";

export type TestCase = TestResult;

interface ExistingTestCasesPanelProps {
  jobId: string;
  discoveredTests: TestResult[];
  framework: string;
  onRunSelected?: (selection: TestResult[]) => void;
  onRunAll?: () => void;
  isRunning?: boolean;
  isLoading?: boolean;
  onViewSuite?: (suiteName: string) => void;
  onSelectTest?: (test: TestResult | TestSelectionItem) => void;
  runTests?: boolean;
  runFunctionalTests?: boolean;
}

export function ExistingTestCasesPanel({
  jobId,
  discoveredTests,
  framework,
  isRunning = false,
  isLoading = false,
  onViewSuite: _onViewSuite,
  onSelectTest,
  runTests = true,
  runFunctionalTests = true,
}: ExistingTestCasesPanelProps) {
  const [activeTab, setActiveTab] = useState<"FUNCTIONAL" | "BUSINESS">("FUNCTIONAL");

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

  // Split into Unit and Functional test collections using existing classification
  const {
    unitMappedTests,
    unitDiscoveredTests,
    functionalMappedTests,
    functionalDiscoveredTests,
  } = useMemo(() => {
    const unitM: TestResult[] = [];
    const funcM: TestResult[] = [];

    mappedDiscoveredTests.forEach((t) => {
      const type = classifyTestType(t);
      if (type === "Unit") {
        unitM.push(t);
      } else {
        funcM.push(t);
      }
    });

    const unitD: TestResult[] = [];
    const funcD: TestResult[] = [];

    discoveredTests.forEach((t) => {
      const type = classifyTestType(t);
      if (type === "Unit") {
        unitD.push(t);
      } else {
        funcD.push(t);
      }
    });

    return {
      unitMappedTests: unitM,
      unitDiscoveredTests: unitD,
      functionalMappedTests: funcM,
      functionalDiscoveredTests: funcD,
    };
  }, [mappedDiscoveredTests, discoveredTests]);

  // Case 4: Neither Unit Testing nor Functional Testing is selected
  if (!runTests && !runFunctionalTests) {
    return null;
  }

  if (isLoading) {
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
            background: "#eff6ff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#3b82f6",
            fontSize: 22,
          }}
        >
          <FaSpinner style={{ animation: "spin 1s linear infinite" }} />
        </div>
        <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>
          Discovering Existing Test Cases...
        </div>
        <div style={{ fontSize: 13, color: "#64748b", maxWidth: 360, lineHeight: 1.5 }}>
          Scanning repository test suites, files, and annotations.
        </div>
      </div>
    );
  }

  const unitFrameworkName = deriveTestingTypes(unitDiscoveredTests, "unit", framework);
  const functionalFrameworkName = deriveTestingTypes(functionalDiscoveredTests, "functional", framework);

  const unitDiscoveryMetrics = {
    total: unitDiscoveredTests.length,
    executed: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    not_executed: unitDiscoveredTests.length,
    duration: "—",
    pass_percentage: "—",
    type: unitFrameworkName,
    existing_coverage: "N/A",
  };

  const functionalDiscoveryMetrics = {
    total: functionalDiscoveredTests.length,
    executed: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    not_executed: functionalDiscoveredTests.length,
    duration: "—",
    pass_percentage: "—",
    type: functionalFrameworkName,
    existing_coverage: "N/A",
  };

  const renderUnitSection = () => (
    <div
      key="unit-section"
      style={{
        background: "#fff",
        borderRadius: 20,
        border: "1px solid #e2e8f0",
        padding: "20px",
        marginTop: 8,
        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
        display: "flex",
        flexDirection: "column",
        gap: 2,
      }}
    >
      <FunctionalTestingTabs
        title="Existing Unit Test Cases"
        activeTab={activeTab}
        onTabChange={setActiveTab}
        isRunning={isRunning}
        statusLabel={unitDiscoveredTests.length > 0 ? "Discovered" : undefined}
      />

      <ExistingTestCoverage
        jobId={jobId}
        title="Existing Unit Tests"
        filterMode="unit"
        metrics={unitDiscoveryMetrics}
        discoveredTests={unitDiscoveredTests}
        testResults={unitMappedTests}
        isExecuted={false}
        frameworkInfo={{
          detected_framework: unitFrameworkName,
          build_tool: "MAVEN",
          test_source_dir: "src/test/java",
        }}
      />

      {unitMappedTests.length > 0 ? (
        <ExistingTestTable
          title="Existing Unit Tests Validation Report"
          testResults={unitMappedTests}
          frameworkInfo={{
            detected_framework: unitFrameworkName,
            build_tool: "MAVEN",
            test_source_dir: "src/test/java",
          }}
          hasRun={false}
          isRunning={isRunning}
          onSelectTest={onSelectTest}
        />
      ) : (
        <div
          style={{
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            padding: "32px 24px",
            background: "#f8fafc",
            borderRadius: 12,
            border: "1px dashed #cbd5e1",
          }}
        >
          <FaInfoCircle style={{ color: "#94a3b8", fontSize: 18 }} />
          <div style={{ fontSize: 14, fontWeight: 700, color: "#334155" }}>
            No Unit Test Cases Found
          </div>
          <div style={{ fontSize: 12, color: "#64748b" }}>
            No existing Unit Test cases were found in this repository.
          </div>
        </div>
      )}
    </div>
  );

  const renderFunctionalSection = () => (
    <div
      key="functional-section"
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
      <FunctionalTestingTabs
        title="Existing Functional Test Cases"
        activeTab={activeTab}
        onTabChange={setActiveTab}
        isRunning={isRunning}
        statusLabel={functionalDiscoveredTests.length > 0 ? "Discovered" : undefined}
      />

      <ExistingTestCoverage
        jobId={jobId}
        title="Existing Functional Tests"
        filterMode="functional"
        metrics={functionalDiscoveryMetrics}
        discoveredTests={functionalDiscoveredTests}
        testResults={functionalMappedTests}
        isExecuted={false}
        frameworkInfo={{
          detected_framework: functionalFrameworkName,
          build_tool: "MAVEN",
          test_source_dir: "src/test/java",
        }}
      />

      {functionalMappedTests.length > 0 ? (
        <ExistingTestTable
          title="Existing Functional Tests Validation Report"
          testResults={functionalMappedTests}
          frameworkInfo={{
            detected_framework: functionalFrameworkName,
            build_tool: "MAVEN",
            test_source_dir: "src/test/java",
          }}
          hasRun={false}
          isRunning={isRunning}
          onSelectTest={onSelectTest}
        />
      ) : (
        <div
          style={{
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            padding: "32px 24px",
            background: "#f8fafc",
            borderRadius: 12,
            border: "1px dashed #cbd5e1",
          }}
        >
          <FaInfoCircle style={{ color: "#94a3b8", fontSize: 18 }} />
          <div style={{ fontSize: 14, fontWeight: 700, color: "#334155" }}>
            No Functional Test Cases Found
          </div>
          <div style={{ fontSize: 12, color: "#64748b" }}>
            No existing functional test cases (UI/API) were found in this repository.
          </div>
        </div>
      )}
    </div>
  );

  // Case 3: Both Unit Testing and Functional Testing are selected
  if (runTests && runFunctionalTests) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
        {renderUnitSection()}
        {renderFunctionalSection()}
      </div>
    );
  }

  // Case 1: Only Unit Testing is selected
  if (runTests) {
    return renderUnitSection();
  }

  // Case 2: Only Functional Testing is selected
  if (runFunctionalTests) {
    return renderFunctionalSection();
  }

  return null;
}

