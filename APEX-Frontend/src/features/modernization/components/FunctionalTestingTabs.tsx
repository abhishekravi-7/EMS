import React from "react";
import { FaSpinner } from "react-icons/fa";

interface FunctionalTestingTabsProps {
  activeTab: "FUNCTIONAL" | "BUSINESS";
  onTabChange: (tab: "FUNCTIONAL" | "BUSINESS") => void;
  isRunning?: boolean;
  elapsedTime?: number;
  statusLabel?: string;
}

export function FunctionalTestingTabs({
  activeTab,
  onTabChange,
  isRunning = false,
  elapsedTime = 0,
  statusLabel,
}: FunctionalTestingTabsProps) {
  const formatTime = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = sec % 60;
    return `${String(mins).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderBottom: "1px solid #e2e8f0",
        marginBottom: 20,
        paddingBottom: 0,
      }}
    >
      {/* Top Left Navigation Tabs */}
      <div style={{ display: "flex", gap: 28 }}>
        <button
          onClick={() => onTabChange("FUNCTIONAL")}
          style={{
            background: "none",
            border: "none",
            padding: "10px 4px 14px 4px",
            fontSize: 15,
            fontWeight: 800,
            color: activeTab === "FUNCTIONAL" ? "#6d28d9" : "#64748b",
            borderBottom: activeTab === "FUNCTIONAL" ? "3px solid #6d28d9" : "3px solid transparent",
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
        >
          Functional Testing Summary
        </button>

        <button
          onClick={() => onTabChange("BUSINESS")}
          style={{
            background: "none",
            border: "none",
            padding: "10px 4px 14px 4px",
            fontSize: 15,
            fontWeight: 700,
            color: activeTab === "BUSINESS" ? "#6d28d9" : "#64748b",
            borderBottom: activeTab === "BUSINESS" ? "3px solid #6d28d9" : "3px solid transparent",
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
        >
          {/*Business Report Summary*/}
        </button>
      </div>

      {/* Top Right Status Pill */}
      {isRunning ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "5px 14px",
            borderRadius: 20,
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            color: "#1d4ed8",
            fontSize: 12,
            fontWeight: 700,
          }}
        >
          <FaSpinner className="animate-spin" size={12} style={{ color: "#2563eb" }} />
          <span>Analyzing... ({formatTime(elapsedTime)})</span>
        </div>
      ) : statusLabel ? (
        <div
          style={{
            padding: "4px 12px",
            borderRadius: 20,
            background: "#f1f5f9",
            color: "#475569",
            fontSize: 12,
            fontWeight: 700,
          }}
        >
          {statusLabel}
        </div>
      ) : null}
    </div>
  );
}
