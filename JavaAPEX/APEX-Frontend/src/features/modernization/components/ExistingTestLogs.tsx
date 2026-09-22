import React, { useState } from "react";
import { FaTerminal, FaSearch, FaCopy } from "react-icons/fa";

interface LogEntry {
  ts: string;
  msg: string;
  level: string;
}

interface ExistingTestLogsProps {
  logs: LogEntry[];
}

export function ExistingTestLogs({ logs }: ExistingTestLogsProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [copied, setCopied] = useState(false);

  // Filter logs based on search query (case-insensitive)
  const filteredLogs = logs.map((log, index) => ({
    ...log,
    originalLineNumber: index + 1
  })).filter((log) => {
    if (!searchQuery) return true;
    return log.msg.toLowerCase().includes(searchQuery.toLowerCase()) || 
           log.ts.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const handleCopy = () => {
    const rawText = logs.map((log) => `[${log.ts}] [${log.level}] ${log.msg}`).join("\n");
    navigator.clipboard.writeText(rawText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header and Controls Row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <h4
            style={{
              margin: 0,
              fontSize: 14,
              fontWeight: 800,
              color: "#0f172a",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <FaTerminal style={{ color: "#38bdf8" }} />
            Existing Test Execution Output Logs
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#64748b",
                background: "#f1f5f9",
                padding: "2px 8px",
                borderRadius: 999,
              }}
            >
              {logs.length} line{logs.length !== 1 ? "s" : ""}
            </span>
          </h4>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ position: "relative" }}>
            <FaSearch
              style={{
                position: "absolute",
                left: 10,
                top: "50%",
                transform: "translateY(-50%)",
                color: "#94a3b8",
                fontSize: 12,
              }}
            />
            <input
              type="text"
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                padding: "6px 12px 6px 30px",
                borderRadius: 8,
                border: "1px solid #e2e8f0",
                fontSize: 12,
                outline: "none",
                width: 180,
                transition: "border-color 0.2s",
              }}
            />
          </div>
          <button
            onClick={handleCopy}
            style={{
              padding: "6px 12px",
              background: "#0f172a",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              fontWeight: 700,
              fontSize: 12,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              position: "relative",
            }}
          >
            <FaCopy size={11} />
            {copied ? "Logs Copied!" : "Copy Logs"}
          </button>
        </div>
      </div>

      {/* Terminal Viewport */}
      <div
        style={{
          background: "#0f172a",
          borderRadius: 12,
          border: "1px solid #334155",
          padding: 16,
          maxHeight: 450,
          overflowY: "auto",
          fontFamily: "'Fira Code', 'JetBrains Mono', 'Consolas', monospace",
          fontSize: 11,
          lineHeight: 1.6,
          boxShadow: "inset 0 4px 12px rgba(0, 0, 0, 0.4)",
        }}
      >
        {filteredLogs.length === 0 ? (
          <div style={{ padding: "40px 0", textAlign: "center", color: "#64748b" }}>
            No matching logs found.
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div
              key={log.originalLineNumber}
              style={{
                display: "flex",
                gap: 16,
                color: log.level === "ERROR" ? "#f87171" : log.level === "WARN" ? "#fbbf24" : "#e2e8f0",
              }}
            >
              {/* Line Number Column */}
              <span
                style={{
                  color: "#475569",
                  minWidth: 28,
                  textAlign: "right",
                  userSelect: "none",
                  borderRight: "1px solid #1e293b",
                  paddingRight: 8,
                }}
              >
                {log.originalLineNumber}
              </span>

              {/* Timestamp Column */}
              <span style={{ color: "#64748b", userSelect: "none" }}>{log.ts}</span>

              {/* Log Message */}
              <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-all", flex: 1 }}>
                {log.msg}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
