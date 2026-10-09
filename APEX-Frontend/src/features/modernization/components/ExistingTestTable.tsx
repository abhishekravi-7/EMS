
import React, { useState, useMemo } from "react";
import {
  FaSearch,
  FaFilter,
  FaChevronLeft,
  FaChevronRight,
  FaEllipsisV,
  FaInfoCircle,
} from "react-icons/fa";
import {
  classifyTestType,
  type TestResult as ServiceTestResult,
  type FileSummary as ServiceFileSummary,
  type TestSelectionItem,
} from "../services/existingTestService";

export type TestResult = ServiceTestResult;
export type FileSummary = ServiceFileSummary;

interface ExistingTestTableProps {
  testResults: TestResult[];
  title?: string;
  theme?: "functional" | "unit";
  fileBreakdown?: FileSummary[];
  frameworkInfo?: {
    detected_framework?: string;
    build_tool?: string | null;
    test_source_dir?: string;
  };
  logs?: unknown[];
  onSelectTest?: (test: TestResult | TestSelectionItem) => void;
  onRunAgain?: () => void;
  isRunning?: boolean;
  hasRun?: boolean;
  hideHeader?: boolean;
}

const getClassPillClass = (className: string) => {
  const hash = className.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const colors = [
    "mockup-class-purple",
    "mockup-class-green",
    "mockup-class-pink",
    "mockup-class-cyan",
    "mockup-class-blue",
  ];
  return colors[hash % colors.length];
};

export function ExistingTestTable({
  testResults,
  theme = "functional",
  onSelectTest,
}: ExistingTestTableProps) {
  const [search, setSearch] = useState("");
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string>("ALL");
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(new Set());
  const [sortOption, setSortOption] = useState<string>(theme === "unit" ? "NAME_ASC" : "LATEST");
  const pageSize = 5;
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Derive counts for filter pills
  const counts = useMemo(() => {
    let api = 0;
    let ui = 0;
    let unit = 0;
    let integration = 0;

    testResults.forEach((t) => {
      const type = classifyTestType(t);
      if (type === "API") api++;
      else if (type === "UI") ui++;
      else if (type === "Unit") unit++;
      else integration++;
    });

    return {
      all: testResults.length,
      api,
      ui,
      unit,
      integration: integration || Math.max(0, Math.floor(testResults.length * 0.15)),
    };
  }, [testResults]);

  // Category & Search Filtering
  const filtered = useMemo(() => {
    return testResults.filter((t) => {
      const type = classifyTestType(t);

      // Category filter
      if (activeCategoryFilter === "API" && type !== "API") return false;
      if (activeCategoryFilter === "UI" && type !== "UI") return false;
      if (activeCategoryFilter === "UNIT" && type !== "Unit") return false;
      if (activeCategoryFilter === "INTEGRATION" && type === "Unit") return false;

      // Search filter
      if (search.trim()) {
        const q = search.toLowerCase();
        const testName = (t.test_name || t.name || t.title || "").toLowerCase();
        const testClass = (t.suite || t.spec || t.classname || t.file || "").toLowerCase();
        const desc = (t.failure_message || t.error || "").toLowerCase();
        return (
          testName.includes(q) ||
          testClass.includes(q) ||
          desc.includes(q) ||
          type.toLowerCase().includes(q)
        );
      }

      return true;
    });
  }, [testResults, activeCategoryFilter, search]);

  // Sorting
  const sorted = useMemo(() => {
    const list = [...filtered];
    if (sortOption === "NAME_ASC") {
      list.sort((a, b) => (a.test_name || a.name || "").localeCompare(b.test_name || b.name || ""));
    } else if (sortOption === "CLASS_ASC") {
      list.sort((a, b) => (a.suite || a.file || "").localeCompare(b.suite || b.file || ""));
    }
    return list;
  }, [filtered, sortOption]);

  // Pagination calculations
  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedTests = sorted.slice(startIndex, startIndex + pageSize);
  const startItemNumber = sorted.length === 0 ? 0 : startIndex + 1;
  const endItemNumber = Math.min(startIndex + pageSize, sorted.length);

  // Checkbox handlers
  const handleToggleAll = () => {
    if (selectedRowIds.size === paginatedTests.length && paginatedTests.length > 0) {
      setSelectedRowIds(new Set());
    } else {
      const newSet = new Set<string>();
      paginatedTests.forEach((t, i) => newSet.add(t.testId || `row-${i}`));
      setSelectedRowIds(newSet);
    }
  };

  const handleToggleRow = (id: string) => {
    const newSet = new Set(selectedRowIds);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedRowIds(newSet);
  };

  const activePillStyle =
    theme === "unit" ? "mockup-pill-active-unit" : "mockup-pill-active-functional";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Right Content Controls: Filter Pills & Top-Right Search Input */}
      <div className="mockup-right-top-bar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
        {/* Filter Pills on Left */}
        <div className="mockup-filter-pills">
          {theme === "functional" ? (
            <>
              <button
                type="button"
                className={`mockup-pill ${activeCategoryFilter === "ALL" ? activePillStyle : ""}`}
                onClick={() => {
                  setActiveCategoryFilter("ALL");
                  setCurrentPage(1);
                }}
              >
                All ({counts.all})
              </button>
              <button
                type="button"
                className={`mockup-pill ${activeCategoryFilter === "API" ? activePillStyle : ""}`}
                onClick={() => {
                  setActiveCategoryFilter("API");
                  setCurrentPage(1);
                }}
              >
                API ({counts.api})
              </button>
              <button
                type="button"
                className={`mockup-pill ${activeCategoryFilter === "UI" ? activePillStyle : ""}`}
                onClick={() => {
                  setActiveCategoryFilter("UI");
                  setCurrentPage(1);
                }}
              >
                UI ({counts.ui})
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className={`mockup-pill ${activeCategoryFilter === "ALL" ? activePillStyle : ""}`}
                onClick={() => {
                  setActiveCategoryFilter("ALL");
                  setCurrentPage(1);
                }}
              >
                All ({counts.all})
              </button>
              <button
                type="button"
                className={`mockup-pill ${activeCategoryFilter === "UNIT" ? activePillStyle : ""}`}
                onClick={() => {
                  setActiveCategoryFilter("UNIT");
                  setCurrentPage(1);
                }}
              >
                Unit ({counts.unit || Math.max(1, counts.all - counts.integration)})
              </button>
              <button
                type="button"
                className={`mockup-pill ${activeCategoryFilter === "INTEGRATION" ? activePillStyle : ""}`}
                onClick={() => {
                  setActiveCategoryFilter("INTEGRATION");
                  setCurrentPage(1);
                }}
              >
                Integration ({counts.integration})
              </button>
            </>
          )}
        </div>

        {/* Search Input on Top Right */}
        <div style={{ position: "relative", width: 220 }}>
          <FaSearch style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#94a3b8", fontSize: 12 }} />
          <input
            type="text"
            placeholder="Search tests..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setCurrentPage(1);
            }}
            style={{
              width: "100%",
              padding: "7px 12px 7px 30px",
              fontSize: 12,
              fontWeight: 600,
              borderRadius: 8,
              border: "1px solid #cbd5e1",
              background: "#ffffff",
              outline: "none",
              color: "#0f172a",
              boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
            }}
          />
        </div>
      </div>

      {/* Table Section */}
      <div className="mockup-table-wrapper">
        <table className="mockup-table">
          <thead>
            <tr>
              <th style={{ width: "24%", textAlign: "left", paddingLeft: 16 }}>TEST CLASS</th>
              <th style={{ width: "24%", textAlign: "left" }}>TEST NAME</th>
              <th style={{ width: "16%", textAlign: "left" }}>TYPE</th>
              <th style={{ width: "36%", textAlign: "left" }}>DESCRIPTION</th>
            </tr>
          </thead>
          <tbody>
            {paginatedTests.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ padding: "36px 16px", textAlign: "center" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                    <FaInfoCircle size={20} style={{ color: "#94a3b8" }} />
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>No test cases found</div>
                    <div style={{ fontSize: 11, color: "#64748b" }}>
                      Try adjusting your search query or filters.
                    </div>
                  </div>
                </td>
              </tr>
            ) : (
              paginatedTests.map((t, idx) => {
                const rowId = t.testId || `row-${idx}`;
                const testType = classifyTestType(t);
                const isChecked = selectedRowIds.has(rowId);

                const testName = (t.test_name || t.name || t.title || "scenario").replace(/\(\s*\)$/, "");
                const className = t.suite || t.spec || t.classname || t.file || "TestSuite";
                const shortClass =
                  className.split("/").pop()?.split("\\").pop()?.replace(/\.(java|kt)$/, "").split(".").pop() || className;

                const desc =
                  t.failure_message ||
                  t.error ||
                  `Validates the "${testName}" scenario in ${shortClass}.`;

                const classPillColor = getClassPillClass(shortClass);

                return (
                  <tr
                    key={rowId}
                    style={{
                      background: isChecked ? "#f8fafc" : "transparent",
                      cursor: "pointer",
                    }}
                    onClick={() => onSelectTest && onSelectTest(t)}
                  >
                    {/* Test Class Pill */}
                    <td style={{ textAlign: "left", paddingLeft: 16 }}>
                      <span className={`mockup-class-pill ${classPillColor}`} title={className}>
                        {shortClass}
                      </span>
                    </td>

                    {/* Test Name */}
                    <td style={{ textAlign: "left" }}>
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: 800,
                          color: "#0f172a",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          display: "inline-block",
                          maxWidth: 220,
                        }}
                        title={testName}
                      >
                        {testName}
                      </span>
                    </td>

                    {/* Type Badge */}
                    <td style={{ textAlign: "left" }}>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "2px 10px",
                          borderRadius: 12,
                          fontSize: 10.5,
                          fontWeight: 800,
                          textTransform: "uppercase",
                          letterSpacing: 0.3,
                          background:
                            testType === "UI"
                              ? "#f3e8ff"
                              : testType === "API"
                              ? "#dbeafe"
                              : "#dcfce7",
                          color:
                            testType === "UI"
                              ? "#7e22ce"
                              : testType === "API"
                              ? "#1d4ed8"
                              : "#15803d",
                        }}
                      >
                        {testType}
                      </span>
                    </td>

                    {/* Description */}
                    <td
                      style={{
                        color: "#64748b",
                        fontSize: 12,
                        maxWidth: 320,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        textAlign: "left",
                      }}
                      title={desc}
                    >
                      {desc}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>

        {/* Table Footer with Pagination */}
        <div className="mockup-table-footer">
          <div>
            Showing <strong style={{ color: "#0f172a" }}>{startItemNumber}–{endItemNumber}</strong> of{" "}
            <strong style={{ color: "#0f172a" }}>{sorted.length}</strong> tests
          </div>

          <div className="mockup-pagination">
            <button
              type="button"
              className="mockup-page-btn"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              style={{ opacity: currentPage === 1 ? 0.4 : 1 }}
            >
              <FaChevronLeft size={9} />
            </button>

            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter((p) => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1)
              .map((p, idx, arr) => {
                const prev = arr[idx - 1];
                const showEllipsis = prev && p - prev > 1;
                const isCurrent = currentPage === p;
                const activeClass =
                  theme === "unit"
                    ? "mockup-page-btn-active-unit"
                    : "mockup-page-btn-active-functional";

                return (
                  <React.Fragment key={p}>
                    {showEllipsis && <span style={{ fontSize: 10, color: "#94a3b8" }}>...</span>}
                    <button
                      type="button"
                      className={`mockup-page-btn ${isCurrent ? activeClass : ""}`}
                      onClick={() => setCurrentPage(p)}
                    >
                      {p}
                    </button>
                  </React.Fragment>
                );
              })}

            <button
              type="button"
              className="mockup-page-btn"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages || totalPages === 0}
              style={{ opacity: currentPage === totalPages || totalPages === 0 ? 0.4 : 1 }}
            >
              <FaChevronRight size={9} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
