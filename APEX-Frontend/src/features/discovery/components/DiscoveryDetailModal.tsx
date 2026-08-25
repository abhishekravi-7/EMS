import React from "react";
import { FaArrowRight } from "react-icons/fa";
import { DonutChart } from "@/shared/components/ui";
import type { SliceItem } from "@/shared/components/ui";

// --- Types ------------------------------------------------------------------

export interface CompositionSegment extends SliceItem {
  count: number;
}

export interface AnalysisFinding {
  label: string;
  count: number;
  severity: "Low" | "Medium" | "High" | "Critical";
}

export interface MigrationSummarySegment extends SliceItem {
  count: number;
}

export interface DiscoveryDetailModalProps {
  compositionData: CompositionSegment[];
  analysisFindings: AnalysisFinding[];
  migrationSummary: MigrationSummarySegment[];
  totalFiles: number;
  totalMigrationItems: number;
  onViewAllFiles?: () => void;
  onViewFullAnalysis?: () => void;
  onViewMigrationDetails?: () => void;
}

// --- Sub-components ---------------------------------------------------------

const SeverityBadge = ({ severity }: { severity: AnalysisFinding["severity"] }) => {
  const colors: Record<string, string> = {
    Low: "#22c55e",
    Medium: "#f59e0b",
    High: "#f97316",
    Critical: "#ef4444",
  };

  return (
    <span style={{
      fontSize: "10px",
      fontWeight: 700,
      padding: "2px 8px",
      borderRadius: "999px",
      background: `${colors[severity]}15`,
      color: colors[severity],
      border: `1px solid ${colors[severity]}30`,
      textTransform: "uppercase",
      letterSpacing: "0.02em",
    }}>
      {severity}
    </span>
  );
};

const Panel = ({
  title,
  children,
  onFooterClick,
  footerText
}: {
  title: string,
  children: React.ReactNode,
  onFooterClick?: () => void,
  footerText?: string
}) => (
  <div style={{
    background: "#fff",
    borderRadius: "12px",
    padding: "24px",
    border: "1px solid #e2e8f0",
    display: "flex",
    flexDirection: "column",
    flex: 1,
    minWidth: "300px"
  }}>
    <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#1e293b", marginBottom: "20px", marginTop: 0 }}>{title}</h3>
    <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
      {children}
    </div>
    {footerText && (
      <button
        onClick={onFooterClick}
        style={{
          marginTop: "24px",
          background: "none",
          border: "none",
          color: "#6366f1",
          fontSize: "13px",
          fontWeight: 700,
          cursor: "pointer",
          textAlign: "left",
          display: "flex",
          alignItems: "center",
          gap: "4px",
          padding: 0
        }}
      >
        {footerText} <FaArrowRight size={10} />
      </button>
    )}
  </div>
);

const LegendItem = ({ color, label, count, percent }: { color: string, label: string, count: number, percent: number }) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: color }}></div>
      <span style={{ fontSize: "13px", color: "#475569", fontWeight: 500 }}>{label}</span>
    </div>
    <div style={{ fontSize: "13px", fontWeight: 700, color: "#1e293b" }}>
      {count.toLocaleString()} <span style={{ color: "#94a3b8", fontWeight: 500 }}>({percent}%)</span>
    </div>
  </div>
);

// --- Main Component ---------------------------------------------------------

const DiscoveryDetailModal: React.FC<DiscoveryDetailModalProps> = ({
  compositionData,
  analysisFindings,
  migrationSummary,
  totalFiles,
  totalMigrationItems,
  onViewAllFiles,
  onViewFullAnalysis,
  onViewMigrationDetails
}) => {
  return (
    <div style={{
      display: "flex",
      flexWrap: "wrap",
      gap: "20px",
      justifyContent: "center"
    }}>
      {/* a. Repository Composition */}
      <Panel
        title="Repository Composition"
        footerText="View all files"
        onFooterClick={onViewAllFiles}
      >
        <div style={{ marginBottom: "20px" }}>
          <DonutChart
            slices={compositionData.map(c => ({ ...c, value: c.count }))}
            total={totalFiles}
            centerLabel="Total Files"
          />
        </div>
        <div style={{ display: "grid", gap: "12px" }}>
          {compositionData.map((seg, i) => (
            <LegendItem
              key={i}
              color={seg.color}
              label={seg.label}
              count={seg.count}
              percent={seg.percent || 0}
            />
          ))}
        </div>
      </Panel>

      {/* b. Java Modernization Analysis */}
      <Panel
        title="Java Modernization Analysis"
        footerText="View full analysis"
        onFooterClick={onViewFullAnalysis}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {analysisFindings.map((finding, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: "13px", color: "#475569", fontWeight: 500 }}>{finding.label}</span>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <span style={{ fontSize: "13px", fontWeight: 800, color: "#1e293b" }}>{finding.count}</span>
                <SeverityBadge severity={finding.severity} />
              </div>
            </div>
          ))}
        </div>
      </Panel>

      {/* c. Migration Summary */}
      <Panel
        title="Migration Summary"
        footerText="View migration details"
        onFooterClick={onViewMigrationDetails}
      >
        <div style={{ marginBottom: "20px" }}>
          <DonutChart
            slices={migrationSummary.map(m => ({ ...m, value: m.count }))}
            total={totalMigrationItems}
            centerLabel="Total Items"
          />
        </div>
        <div style={{ display: "grid", gap: "12px" }}>
          {migrationSummary.map((seg, i) => (
            <LegendItem
              key={i}
              color={seg.color}
              label={seg.label}
              count={seg.count}
              percent={seg.percent || 0}
            />
          ))}
        </div>
      </Panel>
    </div>
  );
};

export default DiscoveryDetailModal;
