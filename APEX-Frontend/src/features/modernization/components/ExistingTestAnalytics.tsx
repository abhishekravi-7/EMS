import React from "react";
import { FaLayerGroup, FaShieldAlt, FaVial } from "react-icons/fa";

interface FileSummary {
  file: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  not_executed?: number;
}

interface ExistingTestAnalyticsProps {
  metrics: {
    total?: number;
    executed?: number;
    passed?: number;
    failed?: number;
    skipped?: number;
    not_executed?: number;
    pass_percentage?: string;
    type?: string;
  };
  fileBreakdown?: FileSummary[];
  frameworkInfo?: {
    detected_framework?: string;
    build_tool?: string;
    test_source_dir?: string;
  };
}

export function ExistingTestAnalytics({
  metrics,
  fileBreakdown = [],
  frameworkInfo,
}: ExistingTestAnalyticsProps) {
  const totalTests = metrics.total ?? 0;
  const passed = metrics.passed ?? 0;
  const failed = metrics.failed ?? 0;
  const skipped = metrics.skipped ?? 0;
  const notExecuted = metrics.not_executed ?? 0;
  const totalSuites = fileBreakdown.length > 0 ? fileBreakdown.length : 1;

  const rawPassRate = totalTests > 0 ? Math.round((passed / totalTests) * 100) : 0;

  // Donut SVG parameters
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (rawPassRate / 100) * circumference;

  // Breakdown items (Suite / Class counts)
  const topSuites = fileBreakdown.slice(0, 4);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* SECTION HEADER */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <FaVial style={{ fontSize: 18, color: "#2563eb" }} />
          <span
            style={{
              fontWeight: 800,
              fontSize: 16,
              color: "#0f172a",
              textTransform: "uppercase",
              letterSpacing: 0.5,
            }}
          >
            EXISTING TEST CASES
          </span>
        </div>
        <p style={{ fontSize: 12, color: "#64748b", margin: "4px 0 0 0" }}>
          Discovered and analyzed existing test cases from the project
        </p>
      </div>

      {/* TWO CARDS GRID */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 20,
        }}
      >
      {/* LEFT CARD: Suite Composition Breakdown */}
      <div
        style={{
          background: "#fff",
          borderRadius: 20,
          border: "1px solid #e2e8f0",
          padding: "24px",
          boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <h4 style={{ fontSize: 15, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
              <FaLayerGroup style={{ color: "#3b82f6" }} /> Suite Composition Breakdown
            </h4>
            <span style={{ fontSize: 11, fontWeight: 700, color: "#64748b", background: "#f1f5f9", padding: "2px 8px", borderRadius: 6 }}>
              {frameworkInfo?.detected_framework || metrics.type || "JUnit"}
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
            {topSuites.length > 0 ? (
              topSuites.map((s, idx) => {
                const baseName = s.file.split("/").pop()?.replace(/\.(java|js|ts|py)$/, "") || s.file;
                const pct = totalTests > 0 ? Math.round((s.total / totalTests) * 100) : 0;
                const barColor = idx === 0 ? "#2563eb" : idx === 1 ? "#7c3aed" : idx === 2 ? "#0891b2" : "#d97706";

                return (
                  <div key={idx}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: 700, color: "#334155", marginBottom: 4 }}>
                      <span style={{ fontFamily: "monospace" }}>{baseName}</span>
                      <span style={{ color: "#64748b" }}>{s.total} tests ({pct}%)</span>
                    </div>
                    <div style={{ width: "100%", height: 6, background: "#f1f5f9", borderRadius: 999, overflow: "hidden" }}>
                      <div style={{ height: "100%", background: barColor, width: `${pct}%`, transition: "width 0.4s ease" }} />
                    </div>
                  </div>
                );
              })
            ) : (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: 700, color: "#334155", marginBottom: 4 }}>
                  <span>Discovered Test Suite</span>
                  <span>{totalTests} tests (100%)</span>
                </div>
                <div style={{ width: "100%", height: 6, background: "#f1f5f9", borderRadius: 999, overflow: "hidden" }}>
                  <div style={{ height: "100%", background: "#2563eb", width: "100%" }} />
                </div>
              </div>
            )}
          </div>
        </div>

        <div style={{ paddingTop: 14, borderTop: "1px solid #f1f5f9", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Total Suites</span>
          <span style={{ fontSize: 16, fontWeight: 900, color: "#0f172a" }}>{totalSuites} {totalSuites === 1 ? "Suite" : "Suites"}</span>
        </div>
      </div>

      {/* RIGHT CARD: Risk Based Suite Coverage */}
      <div
        style={{
          background: "#fff",
          borderRadius: 20,
          border: "1px solid #e2e8f0",
          padding: "24px",
          boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <h4 style={{ fontSize: 15, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <FaShieldAlt style={{ color: "#10b981" }} /> Risk Based Suite Coverage
          </h4>
          <span style={{ fontSize: 11, fontWeight: 700, color: "#10b981", background: "#ecfdf5", padding: "2px 8px", borderRadius: 6 }}>
            Active
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-around", margin: "10px 0" }}>
          {/* Donut Chart */}
          <div style={{ position: "relative", width: 100, height: 100, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="100" height="100" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r={radius} fill="none" stroke="#f1f5f9" strokeWidth="10" />
              <circle
                cx="50"
                cy="50"
                r={radius}
                fill="none"
                stroke={failed > 0 ? "#dc2626" : "#10b981"}
                strokeWidth="10"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                transform="rotate(-90 50 50)"
                style={{ transition: "stroke-dashoffset 0.6s ease-out" }}
              />
            </svg>
            <div style={{ position: "absolute", textAlign: "center" }}>
              <div style={{ fontSize: 15, fontWeight: 900, color: "#0f172a", lineHeight: 1.1 }}>{totalTests}</div>
              <div style={{ fontSize: 9, fontWeight: 800, color: "#64748b", textTransform: "uppercase" }}>TESTS</div>
            </div>
          </div>

          {/* Risk Levels Legend */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 8, height: 8, borderRadius: 99, background: "#10b981" }} />
              <span style={{ fontSize: 11, fontWeight: 700, color: "#334155" }}>P0 Critical Pass</span>
              <span style={{ fontSize: 11, fontWeight: 800, color: "#10b981", marginLeft: "auto" }}>{passed}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 8, height: 8, borderRadius: 99, background: "#f59e0b" }} />
              <span style={{ fontSize: 11, fontWeight: 700, color: "#334155" }}>P1 High / Skipped</span>
              <span style={{ fontSize: 11, fontWeight: 800, color: "#f59e0b", marginLeft: "auto" }}>{skipped + notExecuted}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 8, height: 8, borderRadius: 99, background: "#ef4444" }} />
              <span style={{ fontSize: 11, fontWeight: 700, color: "#334155" }}>P2 Medium Fail</span>
              <span style={{ fontSize: 11, fontWeight: 800, color: "#ef4444", marginLeft: "auto" }}>{failed}</span>
            </div>
          </div>
        </div>

        <div style={{ paddingTop: 14, borderTop: "1px solid #f1f5f9", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Risk Pass Rate</span>
          <span style={{ fontSize: 16, fontWeight: 900, color: rawPassRate >= 70 ? "#10b981" : "#ef4444" }}>
            {totalTests > 0 ? `${rawPassRate}%` : "N/A"}
          </span>
        </div>
      </div>
    </div>
  </div>
);
}
