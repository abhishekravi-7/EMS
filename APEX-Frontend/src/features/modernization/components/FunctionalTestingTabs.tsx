import React from "react";
import { FaSpinner } from "react-icons/fa";

interface FunctionalTestingTabsProps {
  title?: string;
  activeTab?: "FUNCTIONAL" | "BUSINESS";
  onTabChange?: (tab: "FUNCTIONAL" | "BUSINESS") => void;
  isRunning?: boolean;
  elapsedTime?: number;
  statusLabel?: string;
}

export function FunctionalTestingTabs({
  title = "Existing Test Cases",
  isRunning = false,
  elapsedTime = 0,
  statusLabel = "Discovered",
}: FunctionalTestingTabsProps) {
  const formatTime = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = sec % 60;
    return `${String(mins).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
  };

  const titleColor = title.toLowerCase().includes("unit")
    ? "#1e40af"
    : title.toLowerCase().includes("functional")
    ? "#4338ca"
    : "#6d28d9";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 8,
      }}
    >
      <h3
        style={{
          fontSize: 16,
          fontWeight: 900,
          color: titleColor,
          margin: 0,
        }}
      >
        {title}
      </h3>

      {isRunning ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "4px 12px",
            borderRadius: 6,
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            color: "#1d4ed8",
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          <FaSpinner className="animate-spin" size={11} style={{ color: "#2563eb" }} />
          <span>Analyzing... ({formatTime(elapsedTime)})</span>
        </div>
      ) : statusLabel ? (
        <div
          style={{
            padding: "3px 10px",
            borderRadius: 6,
            background: "#fff",
            border: "1px solid #e2e8f0",
            color: "#64748b",
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          {statusLabel}
        </div>
      ) : null}
    </div>
  );
}
