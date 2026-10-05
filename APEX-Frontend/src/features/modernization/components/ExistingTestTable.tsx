import React, { useState, useMemo } from "react";
import {
  FaSearch,
  FaTable,
  FaSort,
  FaSortUp,
  FaSortDown,
  FaChevronLeft,
  FaChevronRight,
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

type SortField = "NAME" | "TYPE" | "CLASS";
type SortOrder = "ASC" | "DESC";

export function ExistingTestTable({
  testResults,
  frameworkInfo,
  onSelectTest,
  title = "Existing Tests Validation Report",
  hideHeader = false,
}: ExistingTestTableProps) {
  const [search, setSearch] = useState("");
  const pageSize = 5;
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortOrder, setSortOrder] = useState<SortOrder>("ASC");

  // Searching
  const filtered = useMemo(() => {
    let result = testResults.filter((t) => {
      if (search.trim()) {
        const q = search.toLowerCase();
        const testName = (t.test_name || t.name || t.title || "").toLowerCase();
        const testClass = (t.suite || t.spec || t.classname || "").toLowerCase();
        const testFile = (t.file || "").toLowerCase();
        const testType = classifyTestType(t).toLowerCase();
        const testFw = (t.framework || "").toLowerCase();
        return (
          testName.includes(q) ||
          testClass.includes(q) ||
          testFile.includes(q) ||
          testType.includes(q) ||
          testFw.includes(q)
        );
      }
      return true;
    });

    // Sorting
    if (sortField) {
      result = [...result].sort((a, b) => {
        let valA = "";
        let valB = "";

        if (sortField === "NAME") {
          valA = (a.test_name || a.name || a.title || "").toLowerCase();
          valB = (b.test_name || b.name || b.title || "").toLowerCase();
        } else if (sortField === "CLASS") {
          valA = (a.suite || a.file || a.classname || "").toLowerCase();
          valB = (b.suite || b.file || b.classname || "").toLowerCase();
        } else if (sortField === "TYPE") {
          valA = classifyTestType(a).toLowerCase();
          valB = classifyTestType(b).toLowerCase();
        }

        if (valA < valB) return sortOrder === "ASC" ? -1 : 1;
        if (valA > valB) return sortOrder === "ASC" ? 1 : -1;
        return 0;
      });
    }

    return result;
  }, [testResults, search, sortField, sortOrder]);

  // Pagination calculations
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedTests = filtered.slice(startIndex, startIndex + pageSize);
  const startItemNumber = filtered.length === 0 ? 0 : startIndex + 1;
  const endItemNumber = Math.min(startIndex + pageSize, filtered.length);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      if (sortOrder === "ASC") {
        setSortOrder("DESC");
      } else {
        setSortField(null);
        setSortOrder("ASC");
      }
    } else {
      setSortField(field);
      setSortOrder("ASC");
    }
  };

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) return <FaSort style={{ opacity: 0.3, fontSize: 10, marginLeft: 4 }} />;
    return sortOrder === "ASC" ? (
      <FaSortUp style={{ color: "#4f46e5", fontSize: 10, marginLeft: 4 }} />
    ) : (
      <FaSortDown style={{ color: "#4f46e5", fontSize: 10, marginLeft: 4 }} />
    );
  };

  if (testResults.length === 0) {
    return (
      <div
        style={{
          background: "#fff",
          border: "1px solid #e2e8f0",
          borderRadius: 16,
          padding: "48px 24px",
          textAlign: "center",
          boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
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
            background: "#f1f5f9",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#64748b",
            fontSize: 22,
          }}
        >
          <FaInfoCircle />
        </div>
        <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>
          No Test Cases Available
        </div>
        <div style={{ fontSize: 13, color: "#64748b", maxWidth: 360, lineHeight: 1.5 }}>
          No existing test cases were found in this repository.
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* ── 1. Report Header Bar ───────────────────────────────────────────── */}
      {!hideHeader && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 14,
            borderBottom: "1px solid #f1f5f9",
            paddingBottom: 16,
          }}
        >
          {/* Title */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "#2563eb",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 14,
              }}
            >
              <FaTable />
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: 0 }}>
              {title}
            </h3>
          </div>

          {/* Search Input on top right */}
          <div style={{ position: "relative" }}>
            <FaSearch
              style={{
                position: "absolute",
                left: 12,
                top: "50%",
                transform: "translateY(-50%)",
                color: "#94a3b8",
                fontSize: 12,
              }}
            />
            <input
              type="text"
              placeholder="Search by test name, class, or file..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setCurrentPage(1);
              }}
              style={{
                padding: "7px 12px 7px 34px",
                borderRadius: 8,
                border: "1px solid #cbd5e1",
                fontSize: 12,
                outline: "none",
                width: 280,
              }}
            />
          </div>
        </div>
      )}

      {/* ── 2. Test Cases Table ─────────────────────────────────── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {hideHeader && (
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <div style={{ position: "relative" }}>
              <FaSearch
                style={{
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "#94a3b8",
                  fontSize: 12,
                }}
              />
              <input
                type="text"
                placeholder="Search by test name, class, or type..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setCurrentPage(1);
                }}
                style={{
                  padding: "7px 12px 7px 34px",
                  borderRadius: 8,
                  border: "1px solid #cbd5e1",
                  fontSize: 12,
                  outline: "none",
                  width: 280,
                }}
              />
            </div>
          </div>
        )}

        <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, overflow: "hidden", background: "#fff", boxShadow: "0 1px 3px rgba(0,0,0,0.02)" }}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0", color: "#64748b", fontWeight: 800, fontSize: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  <th style={{ padding: "10px 14px", width: 50 }}>#</th>
                  <th
                    style={{ padding: "10px 14px", width: 220, cursor: "pointer", userSelect: "none" }}
                    onClick={() => handleSort("CLASS")}
                  >
                    <div style={{ display: "flex", alignItems: "center" }}>
                      TEST CLASS {renderSortIcon("CLASS")}
                    </div>
                  </th>
                  <th
                    style={{ padding: "10px 14px", minWidth: 220, cursor: "pointer", userSelect: "none" }}
                    onClick={() => handleSort("NAME")}
                  >
                    <div style={{ display: "flex", alignItems: "center" }}>
                      TEST NAME {renderSortIcon("NAME")}
                    </div>
                  </th>
                  <th
                    style={{ padding: "10px 14px", width: 90, cursor: "pointer", userSelect: "none" }}
                    onClick={() => handleSort("TYPE")}
                  >
                    <div style={{ display: "flex", alignItems: "center" }}>
                      TYPE {renderSortIcon("TYPE")}
                    </div>
                  </th>
                  <th style={{ padding: "10px 14px" }}>DESCRIPTION</th>
                </tr>
              </thead>
              <tbody>
                {paginatedTests.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ padding: "48px 16px", textAlign: "center" }}>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                        <FaInfoCircle size={24} style={{ color: "#94a3b8" }} />
                        <div style={{ fontSize: 14, fontWeight: 800, color: "#0f172a" }}>No test cases found</div>
                        <div style={{ fontSize: 12, color: "#64748b" }}>
                          Try changing your search query.
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : (
                  paginatedTests.map((t, idx) => {
                    const globalIndex = startIndex + idx + 1;
                    const testType = classifyTestType(t);

                    const testName = (t.test_name || t.name || t.title || "scenario").replace(/\(\s*\)$/, "");
                    const className = t.suite || t.spec || t.classname || t.file || "TestSuite";
                    const shortClass = className.split("/").pop()?.split("\\").pop()?.replace(/\.(java|kt)$/, "").split(".").pop() || className;

                    const desc =
                      t.failure_message ||
                      t.error ||
                      `Validates the "${testName}" scenario in ${shortClass}.`;

                    return (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: "1px solid #f1f5f9",
                          transition: "background 0.15s ease",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = "#f8fafc";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = "transparent";
                        }}
                      >
                        {/* Row Index */}
                        <td style={{ padding: "12px 14px", color: "#94a3b8", fontWeight: 700, fontSize: 11 }}>
                          {globalIndex}
                        </td>

                        {/* Test Class */}
                        <td
                          style={{
                            padding: "12px 14px",
                            fontFamily: "monospace",
                            color: "#475569",
                            fontSize: 11,
                            maxWidth: 220,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            fontWeight: 600,
                          }}
                          title={className}
                        >
                          {shortClass}
                        </td>

                        {/* Prominent Test Name */}
                        <td style={{ padding: "12px 14px", maxWidth: 260 }}>
                          <span
                            style={{
                              fontSize: 13,
                              fontWeight: 800,
                              color: "#0f172a",
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              display: "block",
                            }}
                            title={testName}
                          >
                            {testName}
                          </span>
                        </td>

                        {/* Type Badge */}
                        <td style={{ padding: "12px 14px" }}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 800,
                              padding: "2px 8px",
                              borderRadius: 4,
                              background: testType === "UI" ? "#f5f3ff" : testType === "API" ? "#eff6ff" : "#ecfdf5",
                              color: testType === "UI" ? "#7c3aed" : testType === "API" ? "#2563eb" : "#047857",
                              border: `1px solid ${testType === "UI" ? "#ddd6fe" : testType === "API" ? "#bfdbfe" : "#a7f3d0"}`,
                            }}
                          >
                            {testType}
                          </span>
                        </td>

                        {/* Description */}
                        <td
                          style={{
                            padding: "12px 14px",
                            color: "#64748b",
                            fontSize: 12,
                            maxWidth: 300,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
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
          </div>

          {/* Pagination Controls */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "12px 18px",
              background: "#f8fafc",
              borderTop: "1px solid #e2e8f0",
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            {/* Showing info */}
            <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>
              Showing <span style={{ color: "#0f172a", fontWeight: 800 }}>{startItemNumber}–{endItemNumber}</span> of{" "}
              <span style={{ color: "#0f172a", fontWeight: 800 }}>{filtered.length}</span> tests
              {filtered.length !== testResults.length ? ` (filtered from ${testResults.length})` : ""}
            </div>

            {/* Page Buttons */}
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                style={{
                  padding: "5px 10px",
                  borderRadius: 6,
                  border: "1px solid #e2e8f0",
                  background: currentPage === 1 ? "#f1f5f9" : "#fff",
                  color: currentPage === 1 ? "#94a3b8" : "#0f172a",
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: currentPage === 1 ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <FaChevronLeft size={9} /> Previous
              </button>

              {/* Page Number Chips */}
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter((p) => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1)
                .map((p, idx, arr) => {
                  const prev = arr[idx - 1];
                  const showEllipsis = prev && p - prev > 1;

                  return (
                    <React.Fragment key={p}>
                      {showEllipsis && <span style={{ padding: "0 4px", color: "#94a3b8", fontSize: 11 }}>...</span>}
                      <button
                        onClick={() => setCurrentPage(p)}
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: 6,
                          border: currentPage === p ? "none" : "1px solid #e2e8f0",
                          background: currentPage === p ? "#0f172a" : "#fff",
                          color: currentPage === p ? "#fff" : "#475569",
                          fontSize: 11,
                          fontWeight: 800,
                          cursor: "pointer",
                        }}
                      >
                        {p}
                      </button>
                    </React.Fragment>
                  );
                })}

              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages || totalPages === 0}
                style={{
                  padding: "5px 10px",
                  borderRadius: 6,
                  border: "1px solid #e2e8f0",
                  background: currentPage === totalPages || totalPages === 0 ? "#f1f5f9" : "#fff",
                  color: currentPage === totalPages || totalPages === 0 ? "#94a3b8" : "#0f172a",
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: currentPage === totalPages || totalPages === 0 ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                Next <FaChevronRight size={9} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
