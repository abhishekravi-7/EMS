import React, { useState, useMemo } from "react";
import { FaTimes } from "react-icons/fa";
import type { TestResult, FileSummary, TestSelectionItem } from "../services/existingTestService";

export type DiscoveredOrExecutedTest = TestResult;
export type { FileSummary };

interface SuiteSummary extends FileSummary {
  tests: DiscoveredOrExecutedTest[];
}

interface ExistingTestAnalyticsProps {
  metrics?: {
    total?: number;
    executed?: number;
    passed?: number;
    failed?: number;
    skipped?: number;
    not_executed?: number;
    pass_percentage?: string;
    type?: string;
    existing_coverage?: string;
    execution_status?: string;
    compilation_error?: string | null;
  };
  fileBreakdown?: FileSummary[];
  discoveredTests?: (TestResult | TestSelectionItem)[];
  testResults?: TestResult[];
  frameworkInfo?: {
    detected_framework?: string;
    build_tool?: string | null;
    test_source_dir?: string;
  };
  onViewSuite?: (suiteName: string) => void;
  onSelectTest?: (test: TestResult | TestSelectionItem) => void;
}

interface SliceItem {
  label: string;
  value: number;
  percentage: string;
  color: string;
}

function renderDonutChart(
  slices: SliceItem[],
  total: number,
  centerLabel = "TESTS",
  size = 140,
  outerRadius = 56,
  innerRadius = 38
) {
  const cx = size / 2;
  const cy = size / 2;
  const strokeWidth = outerRadius - innerRadius;
  const midRadius = (outerRadius + innerRadius) / 2;

  const nonZeroSlices = slices.filter((s) => s.value > 0);

  let chartContent: React.ReactNode;

  if (total === 0 || nonZeroSlices.length === 0) {
    chartContent = (
      <circle
        cx={cx}
        cy={cy}
        r={midRadius}
        fill="none"
        stroke="#f1f5f9"
        strokeWidth={strokeWidth}
      />
    );
  } else if (nonZeroSlices.length === 1) {
    const single = nonZeroSlices[0];
    chartContent = (
      <circle
        cx={cx}
        cy={cy}
        r={midRadius}
        fill="none"
        stroke={single.color}
        strokeWidth={strokeWidth}
      />
    );
  } else {
    let accumulatedAngle = -Math.PI / 2;
    const paths: React.ReactNode[] = [];

    slices.forEach((slice, idx) => {
      if (slice.value <= 0) return;
      const sliceAngle = (slice.value / total) * 2 * Math.PI;
      const startAngle = accumulatedAngle;
      const endAngle = accumulatedAngle + sliceAngle;
      accumulatedAngle = endAngle;

      const x1Outer = cx + outerRadius * Math.cos(startAngle);
      const y1Outer = cy + outerRadius * Math.sin(startAngle);
      const x2Outer = cx + outerRadius * Math.cos(endAngle);
      const y2Outer = cy + outerRadius * Math.sin(endAngle);

      const x1Inner = cx + innerRadius * Math.cos(endAngle);
      const y1Inner = cy + innerRadius * Math.sin(endAngle);
      const x2Inner = cx + innerRadius * Math.cos(startAngle);
      const y2Inner = cy + innerRadius * Math.sin(startAngle);

      const largeArcFlag = sliceAngle > Math.PI ? 1 : 0;

      const d = `
        M ${x1Outer} ${y1Outer}
        A ${outerRadius} ${outerRadius} 0 ${largeArcFlag} 1 ${x2Outer} ${y2Outer}
        L ${x1Inner} ${y1Inner}
        A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 0 ${x2Inner} ${y2Inner}
        Z
      `;

      paths.push(
        <path
          key={idx}
          d={d}
          fill={slice.color}
          stroke="#ffffff"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      );
    });

    chartContent = paths;
  }

  return (
    <div style={{ position: "relative", width: size, height: size, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {chartContent}
      </svg>
      <div style={{ position: "absolute", textAlign: "center", pointerEvents: "none" }}>
        <div style={{ fontSize: 20, fontWeight: 900, color: "#0f172a", lineHeight: 1 }}>{total}</div>
        <div style={{ fontSize: 8, fontWeight: 800, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.8, marginTop: 3 }}>
          {centerLabel}
        </div>
      </div>
    </div>
  );
}

export function ExistingTestAnalytics({
  metrics = {},
  fileBreakdown = [],
  discoveredTests = [],
  testResults = [],
  frameworkInfo: _frameworkInfo,
  onViewSuite,
  onSelectTest,
}: ExistingTestAnalyticsProps) {
  const [riskMode, setRiskMode] = useState<"PRIORITY" | "TYPE">("TYPE");
  const [selectedSuiteModal, setSelectedSuiteModal] = useState<{ name: string; tests: DiscoveredOrExecutedTest[] } | null>(null);

  // Canonical pool of tests: prefer executed testResults if available, else discoveredTests
  const canonicalTests = useMemo(() => {
    if (testResults && testResults.length > 0) return testResults;
    return discoveredTests || [];
  }, [testResults, discoveredTests]);

  // ── 1. Dynamic Suite Composition ──
  const { suitesList, totalDiscoveredCount } = useMemo((): { suitesList: SuiteSummary[]; totalDiscoveredCount: number } => {
    if (canonicalTests.length > 0) {
      const groupMap: Record<string, { total: number; passed: number; failed: number; skipped: number; tests: TestResult[] }> = {};

      canonicalTests.forEach((t) => {
        const rawSuite = String(t.classname || t.suite || t.module || t.file || "ProjectApplicationTests");
        const suiteName = rawSuite.split("/").pop()?.split("\\").pop()?.replace(/\.(java|js|ts|py)$/, "") || rawSuite;
        if (!groupMap[suiteName]) {
          groupMap[suiteName] = { total: 0, passed: 0, failed: 0, skipped: 0, tests: [] };
        }
        groupMap[suiteName].total += 1;
        groupMap[suiteName].tests.push(t);
        const st = String(t.status || "").toUpperCase();
        if (st === "PASSED") groupMap[suiteName].passed += 1;
        else if (st === "FAILED" || st === "ERROR") groupMap[suiteName].failed += 1;
        else if (st === "SKIPPED") groupMap[suiteName].skipped += 1;
      });

      const list: SuiteSummary[] = Object.entries(groupMap).map(([name, data]) => ({
        file: name,
        total: data.total,
        passed: data.passed,
        failed: data.failed,
        skipped: data.skipped,
        tests: data.tests,
      }));

      return { suitesList: list, totalDiscoveredCount: canonicalTests.length };
    }

    if (fileBreakdown.length > 0) {
      const total = fileBreakdown.reduce((acc, f) => acc + f.total, 0);
      const list: SuiteSummary[] = fileBreakdown.map((fb) => ({
        ...fb,
        tests: canonicalTests.filter((t) => {
          const raw = String(t.classname || t.suite || t.module || t.file || "");
          const sn = raw.split("/").pop()?.split("\\").pop()?.replace(/\.(java|js|ts|py)$/, "") || raw;
          const fn = String(fb.file).split("/").pop()?.split("\\").pop()?.replace(/\.(java|js|ts|py)$/, "") || String(fb.file);
          return sn.toLowerCase() === fn.toLowerCase() || raw.toLowerCase().includes(fn.toLowerCase());
        }),
      }));
      return { suitesList: list, totalDiscoveredCount: total || metrics.total || 0 };
    }

    const fallbackTotal = metrics.total ?? 0;
    return {
      suitesList: fallbackTotal > 0 ? [{ file: "ProjectApplicationTests.java", total: fallbackTotal, passed: metrics.passed ?? 0, failed: metrics.failed ?? 0, skipped: metrics.skipped ?? 0, tests: canonicalTests as DiscoveredOrExecutedTest[] }] : [],
      totalDiscoveredCount: fallbackTotal,
    };
  }, [canonicalTests, fileBreakdown, metrics.total, metrics.passed, metrics.failed, metrics.skipped]);

  const totalSuites = suitesList.length > 0 ? suitesList.length : (totalDiscoveredCount > 0 ? 1 : 0);

  // ── 2. Dynamic Type Breakdown (UNIT, API, UI) ──
  const { unitCount, apiCount, uiCount } = useMemo(() => {
    if (canonicalTests.length > 0) {
      let unit = 0;
      let api = 0;
      let ui = 0;

      canonicalTests.forEach((t) => {
        const rawType = String(t.test_type || t.testType || t.type || (t.category === "UI" ? "UI" : "API")).toUpperCase();
        if (rawType.includes("UI") || rawType.includes("E2E") || rawType.includes("PLAYWRIGHT") || rawType.includes("CYPRESS") || rawType.includes("SELENIUM")) {
          ui++;
        } else if (rawType.includes("INTEGRATION") || rawType.includes("API") || rawType.includes("REST") || rawType.includes("HTTP")) {
          api++;
        } else {
          unit++;
        }
      });

      return { unitCount: unit, apiCount: api, uiCount: ui };
    }

    return { unitCount: totalDiscoveredCount, apiCount: 0, uiCount: 0 };
  }, [canonicalTests, totalDiscoveredCount]);

  // ── 3. Dynamic Priority / Risk Breakdown ──
  const { p0Count, p1Count, p2Count, p3Count } = useMemo(() => {
    if (canonicalTests.length > 0) {
      let p0 = 0;
      let p1 = 0;
      let p2 = 0;
      let p3 = 0;

      canonicalTests.forEach((t) => {
        const p = String(t.priority || "").toUpperCase();
        if (p === "P0" || p.includes("CRITICAL")) p0++;
        else if (p === "P1" || p.includes("HIGH")) p1++;
        else if (p === "P2" || p.includes("MEDIUM")) p2++;
        else if (p === "P3" || p.includes("LOW")) p3++;
        else p2++; // Functional business test standard priority
      });

      return { p0Count: p0, p1Count: p1, p2Count: p2, p3Count: p3 };
    }

    return { p0Count: 0, p1Count: 0, p2Count: totalDiscoveredCount, p3Count: 0 };
  }, [canonicalTests, totalDiscoveredCount]);

  const totalTests = totalDiscoveredCount;

  // Display mapping: combine UNIT into API for display purposes only
  const displayedApiCount = apiCount + unitCount;
  const displayedUiCount = uiCount;

  const apiPct = totalTests > 0 ? ((displayedApiCount / totalTests) * 100).toFixed(1) : "0.0";
  const uiPct = totalTests > 0 ? ((displayedUiCount / totalTests) * 100).toFixed(1) : "0.0";

  const p0Pct = totalTests > 0 ? ((p0Count / totalTests) * 100).toFixed(1) : "0.0";
  const p1Pct = totalTests > 0 ? ((p1Count / totalTests) * 100).toFixed(1) : "0.0";
  const p2Pct = totalTests > 0 ? ((p2Count / totalTests) * 100).toFixed(1) : "0.0";
  const p3Pct = totalTests > 0 ? ((p3Count / totalTests) * 100).toFixed(1) : "0.0";

  const typeSlices: SliceItem[] = [
    { label: "API", value: displayedApiCount, percentage: apiPct, color: "#059669" },
    { label: "UI", value: displayedUiCount, percentage: uiPct, color: "#7c3aed" },
  ];

  const prioritySlices: SliceItem[] = [
    { label: "P0 Critical", value: p0Count, percentage: p0Pct, color: "#ef4444" },
    { label: "P1 High", value: p1Count, percentage: p1Pct, color: "#f59e0b" },
    { label: "P2 Medium", value: p2Count, percentage: p2Pct, color: "#0ea5e9" },
    { label: "P3 Low", value: p3Count, percentage: p3Pct, color: "#8b5cf6" },
  ];

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 20,
        marginBottom: 24,
      }}
    >
      {/* ── CARD 1: Suite Composition Breakdown ─────────────────────────────── */}
      <div
        style={{
          background: "#fff",
          borderRadius: 20,
          border: "1px solid #e2e8f0",
          padding: "24px 28px",
          boxShadow: "0 2px 8px rgba(0, 0, 0, 0.04)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          minHeight: 250,
        }}
      >
        <div>
          {/* Header */}
          <h3
            style={{
              fontSize: 16,
              fontWeight: 800,
              color: "#5b21b6",
              margin: "0 0 24px 0",
              textAlign: "center",
            }}
          >
            Suite Composition Breakdown
          </h3>

          {/* Suites List inside a Scrollable Container (Shows ~7-8 suites at a time) */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 14,
              maxHeight: 240,
              overflowY: "auto",
              paddingRight: 6,
              scrollbarWidth: "thin",
              scrollbarColor: "#cbd5e1 transparent",
            }}
          >
            {suitesList.map((s, idx) => {
              const baseName = s.file.split("/").pop()?.split("\\").pop()?.replace(/\.(java|js|ts|py)$/, "") || "API CONTRACTS";
              const suiteNameUpper = baseName.replace(/Tests?$/, "").toUpperCase() || "API CONTRACTS";
              const pct = totalDiscoveredCount > 0 ? Math.round((s.total / totalDiscoveredCount) * 100) : 100;

              return (
                <div key={idx} style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  {/* Suite Name */}
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 800,
                      color: "#1e293b",
                      width: 140,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      textTransform: "uppercase",
                      letterSpacing: 0.3,
                    }}
                    title={baseName}
                  >
                    {suiteNameUpper}
                  </span>

                  {/* Horizontal Bar with % badge */}
                  <div
                    style={{
                      flex: 1,
                      height: 18,
                      background: "#f1f5f9",
                      borderRadius: 12,
                      overflow: "hidden",
                      position: "relative",
                      display: "flex",
                      alignItems: "center",
                    }}
                  >
                    <div
                      style={{
                        width: `${pct}%`,
                        height: "100%",
                        background: "linear-gradient(90deg, #0284c7, #0ea5e9)",
                        borderRadius: 12,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "flex-end",
                        paddingRight: 6,
                        transition: "width 0.5s ease",
                      }}
                    >
                      <span style={{ fontSize: 9, fontWeight: 900, color: "#fff" }}>{pct}%</span>
                    </div>
                  </div>

                  {/* Count & View Link */}
                  <div style={{ display: "flex", alignItems: "center", gap: 6, width: 75, justifyContent: "flex-end" }}>
                    <span style={{ fontSize: 13, fontWeight: 800, color: "#0f172a" }}>{s.total}</span>
                    <button
                      onClick={() => {
                        if (onViewSuite) {
                          onViewSuite(s.file);
                        }
        setSelectedSuiteModal({ name: baseName, tests: s.tests || [] });
                      }}
                      style={{
                        border: "none",
                        background: "transparent",
                        fontSize: 11,
                        fontWeight: 700,
                        color: "#7c3aed",
                        cursor: "pointer",
                        padding: 0,
                      }}
                    >
                      View →
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Bottom Total Suites Count */}
        <div style={{ textAlign: "center", paddingTop: 14, borderTop: "1px solid #f1f5f9", marginTop: 10 }}>
          <div style={{ fontSize: 10, fontWeight: 800, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.5 }}>
            Total Suites
          </div>
          <div style={{ fontSize: 22, fontWeight: 900, color: "#0f172a", marginTop: 2 }}>{totalSuites}</div>
        </div>
      </div>

      {/* ── CARD 2: Risk based Suite Coverage ───────────────────────────────── */}
      <div
        style={{
          background: "#fff",
          borderRadius: 20,
          border: "1px solid #e2e8f0",
          padding: "24px 28px",
          boxShadow: "0 2px 8px rgba(0, 0, 0, 0.04)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          minHeight: 250,
        }}
      >
        <div>
          {/* Header with Priority / Type Switcher */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 16,
            }}
          >
            <h3
              style={{
                fontSize: 16,
                fontWeight: 800,
                color: "#5b21b6",
                margin: 0,
              }}
            >
              Risk based Suite Coverage
            </h3>

            {/* Switcher: By Priority / By Type */}
            <div
              style={{
                display: "flex",
                background: "#f1f5f9",
                borderRadius: 8,
                padding: 3,
                gap: 2,
              }}
            >
              <button
                onClick={() => setRiskMode("PRIORITY")}
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  border: "none",
                  background: riskMode === "PRIORITY" ? "#6d28d9" : "transparent",
                  color: riskMode === "PRIORITY" ? "#fff" : "#64748b",
                  fontWeight: 800,
                  fontSize: 11,
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                By Priority
              </button>
              <button
                onClick={() => setRiskMode("TYPE")}
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  border: "none",
                  background: riskMode === "TYPE" ? "#6d28d9" : "transparent",
                  color: riskMode === "TYPE" ? "#fff" : "#64748b",
                  fontWeight: 800,
                  fontSize: 11,
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                By Type
              </button>
            </div>
          </div>

          {/* Chart & Legend Grid */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-around", marginTop: 4 }}>
            {/* PIE / DONUT CHART with 72 TESTS centered */}
            {riskMode === "PRIORITY"
              ? renderDonutChart(prioritySlices, totalTests)
              : renderDonutChart(typeSlices, totalTests)}

            {/* Right Legend with Counts and Exact Percentages */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 185 }}>
              {/* Header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  paddingBottom: 6,
                  borderBottom: "1px solid #f1f5f9",
                  fontSize: 10,
                  fontWeight: 800,
                  color: "#94a3b8",
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                }}
              >
                <span>{riskMode === "PRIORITY" ? "TYPE/RISK" : "TYPE"}</span>
                <span style={{ display: "flex", gap: 18 }}>
                  <span style={{ minWidth: 32, textAlign: "right" }}>TESTS</span>
                  <span style={{ minWidth: 40, textAlign: "right" }}>%</span>
                </span>
              </div>

              {/* Rows */}
              {(riskMode === "PRIORITY" ? prioritySlices : typeSlices).map((item, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: item.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 11, fontWeight: 700, color: "#334155" }}>{item.label}</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
                    <span style={{ fontSize: 11, fontWeight: 800, color: "#0f172a", minWidth: 32, textAlign: "right" }}>
                      {item.value}
                    </span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: "#64748b", minWidth: 40, textAlign: "right" }}>
                      {item.percentage}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── SUITE DETAILS MODAL ─────────────────────────────────────────── */}
      {selectedSuiteModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            background: "rgba(15, 23, 42, 0.65)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
          onClick={() => setSelectedSuiteModal(null)}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 20,
              maxWidth: 760,
              width: "100%",
              maxHeight: "88vh",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
              overflow: "hidden",
              border: "1px solid #e2e8f0",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: "20px 24px",
                borderBottom: "1px solid #e2e8f0",
                background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)",
                color: "#fff",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <span style={{ fontSize: 10, fontWeight: 900, background: "rgba(255,255,255,0.15)", padding: "2px 8px", borderRadius: 4, color: "#c4b5fd" }}>
                  SUITE DETAILS
                </span>
                <h3 style={{ fontSize: 18, fontWeight: 900, color: "#fff", margin: "4px 0 0 0" }}>
                  {selectedSuiteModal.name}
                </h3>
              </div>
              <button
                onClick={() => setSelectedSuiteModal(null)}
                style={{
                  background: "rgba(255, 255, 255, 0.1)",
                  border: "1px solid rgba(255, 255, 255, 0.2)",
                  color: "#fff",
                  borderRadius: "50%",
                  width: 32,
                  height: 32,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  fontSize: 14,
                }}
              >
                <FaTimes />
              </button>
            </div>

            <div style={{ padding: "20px 24px", overflowY: "auto", display: "flex", flexDirection: "column", gap: 10 }}>
              {selectedSuiteModal.tests.length === 0 ? (
                <div style={{ padding: "24px", textAlign: "center", color: "#64748b", fontSize: 13 }}>
                  No test cases found for this suite.
                </div>
              ) : (
                selectedSuiteModal.tests.map((st, sIdx) => {
                  const testTitle = (st.test_name || st.name || st.title || st.methodname || `scenario_${sIdx + 1}`).replace(/\(\s*\)$/, "");
                  const testDesc = (st.status === "FAILED" || st.status === "ERROR") && (st.failure_message || st.error)
                    ? (st.failure_message || st.error)
                    : st.file || st.spec || st.classname || `Validates ${selectedSuiteModal.name} test scenario`;
                  const stStatus = (st.status || "NOT_EXECUTED").toUpperCase();
                  const rawType = (st.test_type || st.testType || st.category || st.type || "API").toUpperCase();
                  const displayType = rawType === "UNIT" ? "API" : (rawType.includes("UI") ? "UI" : "API");

                  return (
                    <div
                      key={sIdx}
                      onClick={() => {
                        if (onSelectTest) {
                          const selectedTest: TestResult = {
                            test_name: st.test_name || st.name || st.title || `scenario_${sIdx + 1}`,
                            name: st.name || st.test_name || st.title || `scenario_${sIdx + 1}`,
                            title: st.title || st.test_name || st.name || `scenario_${sIdx + 1}`,
                            suite: st.suite || st.spec || st.classname || selectedSuiteModal.name,
                            spec: st.spec || st.suite || st.classname || selectedSuiteModal.name,
                            status: (st.status || "NOT_EXECUTED") as TestResult["status"],
                            duration: st.duration || "—",
                            file: st.file || selectedSuiteModal.name,
                            error: st.failure_message || st.error || null,
                            failure_message: st.failure_message || st.error || null,
                            framework: st.framework || undefined,
                          };
                          setSelectedSuiteModal(null);
                          onSelectTest(selectedTest);
                        }
                      }}
                      style={{
                        padding: "12px 16px",
                        borderRadius: 10,
                        border: "1px solid #e2e8f0",
                        background: "#f8fafc",
                        cursor: onSelectTest ? "pointer" : "default",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        transition: "all 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "#f1f5f9";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "#f8fafc";
                      }}
                    >
                      <div style={{ flex: 1, paddingRight: 16 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                          <span style={{ fontSize: 13, fontWeight: 800, color: "#0f172a" }}>{testTitle}</span>
                          <span style={{
                            fontSize: 9,
                            fontWeight: 800,
                            padding: "2px 6px",
                            borderRadius: 4,
                            background: displayType === "UI" ? "#faf5ff" : "#eff6ff",
                            color: displayType === "UI" ? "#9333ea" : "#2563eb",
                            border: `1px solid ${displayType === "UI" ? "#e9d5ff" : "#bfdbfe"}`,
                          }}>
                            {displayType}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: "#64748b", marginTop: 3, fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 520 }}>
                          {testDesc}
                        </div>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
                        {st.status && (
                          <span style={{
                            fontSize: 10,
                            fontWeight: 800,
                            padding: "2px 8px",
                            borderRadius: 6,
                            background: stStatus === "PASSED" ? "#ecfdf5" : stStatus === "FAILED" || stStatus === "ERROR" ? "#fef2f2" : stStatus === "SKIPPED" ? "#fffbeb" : "#f1f5f9",
                            color: stStatus === "PASSED" ? "#059669" : stStatus === "FAILED" || stStatus === "ERROR" ? "#dc2626" : stStatus === "SKIPPED" ? "#d97706" : "#64748b",
                            border: `1px solid ${stStatus === "PASSED" ? "#a7f3d0" : stStatus === "FAILED" || stStatus === "ERROR" ? "#fecaca" : stStatus === "SKIPPED" ? "#fde68a" : "#e2e8f0"}`,
                          }}>
                            {stStatus === "NOT_EXECUTED" ? "NOT EXECUTED" : stStatus}
                          </span>
                        )}

                        {onSelectTest && (
                          <button
                            style={{
                              border: "none",
                              background: "transparent",
                              color: "#7c3aed",
                              fontWeight: 800,
                              fontSize: 11,
                              cursor: "pointer",
                              padding: 0,
                            }}
                          >
                            Details →
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
