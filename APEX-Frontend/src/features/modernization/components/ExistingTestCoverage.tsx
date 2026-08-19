import React from "react";
import {
  FaVial,
  FaCheckCircle,
  FaTimesCircle,
  FaFlask,
  FaClock,
  FaBolt,
  FaStepForward,
  FaBullseye,
  FaPlay,
} from "react-icons/fa";
import type { DiscoveredOrExecutedTest } from "./ExistingTestAnalytics";

interface MetricCardProps {
  label: string;
  value: string | number;
  color: string;
  bgColor: string;
  icon: React.ReactNode;
}

function MetricCard({ label, value, color, bgColor, icon }: MetricCardProps) {
  const displayValue = value !== undefined && value !== null && value !== "" ? value : "--";

  return (
    <div
      style={{
        background: bgColor,
        border: `1px solid ${color}15`,
        borderRadius: 12,
        padding: "16px 20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        transition: "transform 0.2s, box-shadow 0.2s",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: "#64748b",
            textTransform: "uppercase",
            letterSpacing: 0.5,
            marginBottom: 6,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {label}
        </div>
        <div
          style={{
            fontSize: 20,
            fontWeight: 900,
            color: color,
            lineHeight: 1.2,
          }}
        >
          {displayValue}
        </div>
      </div>
      <div
        style={{
          width: 38,
          height: 38,
          borderRadius: 8,
          background: "rgba(0, 0, 0, 0.02)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: color,
          fontSize: 16,
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
    </div>
  );
}

interface ExistingTestCoverageProps {
  metrics: {
    total?: number;
    executed?: number;
    passed?: number;
    failed?: number;
    skipped?: number;
    not_executed?: number;
    duration?: string;
    pass_percentage?: string;
    type?: string;
    existing_coverage?: string;
    execution_status?: string;
    compilation_error?: string | null;
  };
  discoveredTests?: DiscoveredOrExecutedTest[];
  testResults?: DiscoveredOrExecutedTest[];
  isExecuted?: boolean;
  frameworkInfo?: {
    detected_framework?: string;
    build_tool?: string;
    test_source_dir?: string;
  };
  onRunAll: () => void;
  onOpenReport?: () => void;
}

export function ExistingTestCoverage({
  metrics,
  discoveredTests = [],
  testResults = [],
  frameworkInfo,
  onRunAll,
  onOpenReport,
}: ExistingTestCoverageProps) {
  // Use canonical discovered dataset count (from testResults/discoveredTests/metrics)
  const canonicalTotal = (testResults && testResults.length > 0)
    ? testResults.length
    : (discoveredTests && discoveredTests.length > 0)
    ? discoveredTests.length
    : (metrics.total ?? 0);

  const total = canonicalTotal;
  const passed = metrics.passed ?? 0;
  const failed = metrics.failed ?? 0;
  const skipped = metrics.skipped ?? 0;
  const executed = metrics.executed ?? (passed + failed + skipped);
  const notExecuted = metrics.not_executed !== undefined && metrics.not_executed !== null && metrics.not_executed > 0
    ? metrics.not_executed
    : Math.max(0, total - executed);

  const rawPassRate = executed > 0 ? Math.round((passed / executed) * 100) : 0;
  const passRateStr = executed > 0 ? (metrics.pass_percentage || `${rawPassRate}%`) : "N/A";
  const coverageStr = metrics.existing_coverage || "N/A";
  const durationStr = metrics.duration || "0.0s";
  
  // Framework string handling
  const frameworkName = frameworkInfo?.detected_framework || metrics.type || "JUnit";

  return (
    <div
      style={{
        marginTop: 24,
        marginBottom: 24,
        padding: "24px 28px",
        borderRadius: 18,
        border: "1px solid #e2e8f0",
        background: "#fff",
        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
      }}
    >
      {/* Header section */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
          flexWrap: "wrap",
          gap: 16,
        }}
      >
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
            Existing Test Coverage
          </span>
        </div>
      <div style={{ display: "flex", gap: 10 }}>
          {onOpenReport && (
            <button
              onClick={onOpenReport}
              style={{
                padding: "8px 16px",
                background: "#ffffff",
                color: "#2563eb",
                border: "1px solid #bfdbfe",
                borderRadius: 8,
                fontWeight: 700,
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              Open Report
            </button>
          )}
          <button
            onClick={onRunAll}
            style={{
              padding: "8px 16px",
              background: "#f8fafc",
              color: "#334155",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              fontWeight: 700,
              fontSize: 12,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 8,
              transition: "background 0.2s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "#f8fafc")}
          >
            <FaPlay style={{ color: "#22c55e", fontSize: 10 }} /> Run All Again
          </button>
        </div>
      </div>

      {/* Grid containing the 8 Metric Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <MetricCard
          label="Discovered Tests"
          value={total}
          color="#2563eb"
          bgColor="rgba(37, 99, 235, 0.05)"
          icon={<FaVial />}
        />
        <MetricCard
          label="Passed"
          value={passed}
          color="#16a34a"
          bgColor="rgba(22, 163, 74, 0.05)"
          icon={<FaCheckCircle />}
        />
        <MetricCard
          label="Failed"
          value={failed}
          color="#dc2626"
          bgColor="rgba(220, 38, 38, 0.05)"
          icon={<FaTimesCircle />}
        />
        <MetricCard
          label="Testing Types"
          value={frameworkName}
          color="#d97706"
          bgColor="rgba(217, 119, 6, 0.05)"
          icon={<FaFlask />}
        />
        <MetricCard
          label="Duration"
          value={durationStr}
          color="#c026d3"
          bgColor="rgba(192, 38, 211, 0.05)"
          icon={<FaClock />}
        />
        <MetricCard
          label="Pass Rate"
          value={passRateStr}
          color={executed === 0 ? "#64748b" : rawPassRate >= 70 ? "#16a34a" : "#dc2626"}
          bgColor={executed === 0 ? "rgba(100, 116, 139, 0.05)" : rawPassRate >= 70 ? "rgba(22, 163, 74, 0.05)" : "rgba(220, 38, 38, 0.05)"}
          icon={<FaBolt />}
        />
        <MetricCard
          label="Skipped / Not Executed"
          value={skipped + notExecuted}
          color="#7c3aed"
          bgColor="rgba(124, 58, 237, 0.05)"
          icon={<FaStepForward />}
        />
        <MetricCard
          label="Coverage"
          value={coverageStr}
          color="#0891b2"
          bgColor="rgba(8, 145, 178, 0.05)"
          icon={<FaBullseye />}
        />
      </div>

      {/* Distribution visual progress bar */}
      {total > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>
              Pass Rate Distribution
            </span>
            <span style={{ fontSize: 11, fontWeight: 700, color: "#64748b" }}>
              {executed > 0
                ? `${passed} passed · ${skipped} skipped · ${failed} failed`
                : `${total} discovered · 0 executed (${notExecuted > 0 ? "build/compilation error" : "not run"})`}
            </span>
          </div>
          {executed > 0 ? (
            <div
              style={{
                width: "100%",
                height: 6,
                background: "#f1f5f9",
                borderRadius: 999,
                overflow: "hidden",
                display: "flex",
              }}
            >
              <div
                style={{
                  height: "100%",
                  background: "#16a34a",
                  width: `${(passed / executed) * 100}%`,
                  transition: "width 0.4s ease-out",
                }}
              />
              <div
                style={{
                  height: "100%",
                  background: "#dc2626",
                  width: `${(failed / executed) * 100}%`,
                  transition: "width 0.4s ease-out",
                }}
              />
              <div
                style={{
                  height: "100%",
                  background: "#7c3aed",
                  width: `${(skipped / executed) * 100}%`,
                  transition: "width 0.4s ease-out",
                }}
              />
            </div>
          ) : (
            <div
              style={{
                width: "100%",
                height: 6,
                background: "#e2e8f0",
                borderRadius: 999,
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}
