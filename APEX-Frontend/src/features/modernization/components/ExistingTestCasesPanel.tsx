import React, { useState, useMemo } from "react";
import {
  FaCheckSquare,
  FaSquare,
  FaChevronDown,
  FaChevronRight,
  FaPlay,
  FaSearch,
  FaFlask,
  FaBox,
  FaList,
} from "react-icons/fa";

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
}

interface ExistingTestCasesPanelProps {
  jobId: string;
  discoveredTests: TestCase[];
  framework: string;
  onRunSelected?: (selection: TestCase[]) => void;
  onRunAll?: () => void;
  isRunning: boolean;
}

export function ExistingTestCasesPanel({
  jobId,
  discoveredTests,
  framework,
  onRunSelected,
  onRunAll,
  isRunning,
}: ExistingTestCasesPanelProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(new Set());

  // Group tests by classname
  const groupedByClass = useMemo(() => {
    const groups: Record<string, TestCase[]> = {};
    discoveredTests.forEach((t) => {
      const cls = t.classname || t.module || "Unknown Class";
      if (!groups[cls]) groups[cls] = [];
      groups[cls].push(t);
    });
    return groups;
  }, [discoveredTests]);

  const filteredClasses = useMemo(() => {
    if (!searchQuery) return Object.keys(groupedByClass);
    const query = searchQuery.toLowerCase();
    return Object.keys(groupedByClass).filter((cls) =>
      cls.toLowerCase().includes(query) ||
      groupedByClass[cls].some((t) => t.name.toLowerCase().includes(query))
    );
  }, [groupedByClass, searchQuery]);

  const toggleExpand = (cls: string) => {
    const newSet = new Set(expandedClasses);
    if (newSet.has(cls)) newSet.delete(cls);
    else newSet.add(cls);
    setExpandedClasses(newSet);
  };

  const handleRun = () => {
    if (onRunAll) {
      onRunAll();
    } else if (onRunSelected) {
      onRunSelected(discoveredTests);
    }
  };

  const getDisplayType = (test: TestCase): string => {
    const fw = (test.framework || "").toLowerCase();
    const type = (test.type || "").toLowerCase();
    const category = (test.category || "").toLowerCase();

    if (category === "ui") return "UI";
    if (category === "api") return "API";

    if (category === "unit") {
      if (fw.includes("jest")) return "Jest";
      if (fw.includes("vitest")) return "Vitest";
      if (fw.includes("junit")) return "JUnit";
      return test.type || "Unit";
    }

    if (fw.includes("playwright") || type.includes("playwright")) {
      return type.includes("api") ? "Playwright API" : "Playwright UI";
    }

    if (fw.includes("jest") || framework.includes("react testing library") || type === "jest") {
      return "Jest";
    }

    if (fw.includes("vitest") || type === "vitest") return "Vitest";
    if (fw.includes("junit") || fw.includes("spring") || type === "junit") return "JUnit";
    if (fw.includes("cypress") || type.includes("cypress")) return "Cypress UI";
    if (type === "api" || type.includes("api")) return "API";

    return test.type || "Unknown";
  };

  return (
    <div style={{
      background: "#fff",
      borderRadius: 20,
      border: "1px solid #e2e8f0",
      padding: "24px",
      marginTop: 24,
      boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 800, color: "#0f172a", display: "flex", alignItems: "center", gap: 10 }}>
            <FaFlask style={{ color: "#3b82f6" }} /> Existing Test Cases
          </h3>
          <p style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
            Discovered {discoveredTests.length} tests across {Object.keys(groupedByClass).length} classes
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{
            padding: "4px 12px", borderRadius: 8, background: "#eff6ff", color: "#1d4ed8",
            fontSize: 11, fontWeight: 700, border: "1px solid #dbeafe"
          }}>
            {framework}
          </span>
          <button
            onClick={handleRun}
            disabled={isRunning || discoveredTests.length === 0}
            style={{
              padding: "9px 22px", background: "#0f172a", color: "#fff",
              borderRadius: 10, fontWeight: 800, fontSize: 13, border: "none",
              cursor: isRunning || discoveredTests.length === 0 ? "not-allowed" : "pointer",
              opacity: isRunning || discoveredTests.length === 0 ? 0.6 : 1,
              display: "flex", alignItems: "center", gap: 8, transition: "all 0.2s"
            }}
          >
            <FaPlay style={{ fontSize: 10, color: "#22c55e" }} />
            Run All Tests
          </button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <div style={{ position: "relative", flex: 1 }}>
          <FaSearch style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "#94a3b8", fontSize: 14 }} />
          <input
            type="text"
            placeholder="Search classes or methods..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%", padding: "10px 12px 10px 40px", borderRadius: 12,
              border: "1px solid #e2e8f0", fontSize: 13, outline: "none",
              transition: "border-color 0.2s"
            }}
          />
        </div>
      </div>

      <div style={{
        maxHeight: 400, overflowY: "auto", border: "1px solid #f1f5f9",
        borderRadius: 14, background: "#f8fafc", padding: "8px"
      }}>
        {filteredClasses.length === 0 ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#94a3b8" }}>
            <FaBox size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
            <p>No tests found matching your search</p>
          </div>
        ) : (
          filteredClasses.map((cls) => {
            const tests = groupedByClass[cls];
            const isExpanded = expandedClasses.has(cls);

            return (
              <div key={cls} style={{ marginBottom: 4, background: "#fff", borderRadius: 10, border: "1px solid #f1f5f9", overflow: "hidden" }}>
                <div style={{
                  display: "flex", alignItems: "center", padding: "10px 14px",
                  cursor: "pointer", transition: "background 0.2s"
                }} onClick={() => toggleExpand(cls)}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: "#1e293b", fontFamily: "monospace" }}>{cls}</span>
                    <span style={{ fontSize: 10, color: "#64748b", background: "#f1f5f9", padding: "2px 8px", borderRadius: 4, fontWeight: 700 }}>
                      {tests.length} {tests.length === 1 ? "test" : "tests"}
                    </span>
                  </div>
                  {isExpanded ? <FaChevronDown size={12} color="#94a3b8" /> : <FaChevronRight size={12} color="#94a3b8" />}
                </div>

                {isExpanded && (
                  <div style={{ borderTop: "1px solid #f1f5f9", background: "#fafafa" }}>
                    {tests.map((t, idx) => {
                      const displayType = getDisplayType(t);
                      const typeLower = displayType.toLowerCase();

                      const isUI = typeLower === "ui" || typeLower.includes("playwright ui") || typeLower.includes("cypress ui");
                      const isAPI = typeLower === "api" || typeLower.includes("playwright api");
                      const color = isUI ? "#7c3aed" : isAPI ? "#059669" : "#64748b";

                      return (
                        <div key={idx} style={{
                          display: "flex", alignItems: "center", padding: "8px 14px 8px 24px",
                          borderBottom: "1px solid #f1f5f9"
                        }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 12, fontWeight: 600, color: "#334155" }}>{t.name}</div>
                            <div style={{ display: "flex", gap: 8, marginTop: 2, alignItems: "center" }}>
                              <span style={{ fontSize: 9, color, fontWeight: 800, textTransform: "uppercase" }}>
                                {displayType}
                              </span>
                              <span style={{ fontSize: 9, color: "#94a3b8" }}>{t.file}</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 20 }}>
          <div style={{ textAlign: "left" }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>{discoveredTests.length}</div>
            <div style={{ fontSize: 9, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Discovered Tests</div>
          </div>
        </div>
      </div>
    </div>
  );
}
