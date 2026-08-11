/**
 * ExistingTestCasesPanel — discover, select, and run existing test cases
 * in the repository being migrated.
 *
 * Redesigned to feature a professional two-column enterprise/CRM-style test management layout.
 * Left Panel: Search, statistics, and list of discovered classes.
 * Right Panel: Selected test cases list, execution controls, progress, and results.
 */

import { useEffect, useState, useRef, useCallback } from "react";
import { FaFlask, FaSearch, FaChevronDown, FaChevronRight, FaTimes, FaRegFolderOpen } from "react-icons/fa";
import type { RepoAnalysis } from "@/shared/types/domain";
import {
    discoverExistingTests,
    runExistingTests,
    getExistingTestStatus,
    type TestDiscoveryResult,
    type ExistingTestRunStatus,
} from "../services/existingTestService";

// ── Props ────────────────────────────────────────────────────────────────────

interface ExistingTestCasesPanelProps {
    jobId: string | null;
    repoAnalysis: RepoAnalysis | null;
}

// ── Component ────────────────────────────────────────────────────────────────

export function ExistingTestCasesPanel({
    jobId,
    repoAnalysis,
}: ExistingTestCasesPanelProps) {
    // Discovery state
    const [discovery, setDiscovery] = useState<TestDiscoveryResult | null>(null);
    const [discoveryLoading, setDiscoveryLoading] = useState(false);
    const [discoveryError, setDiscoveryError] = useState<string | null>(null);

    // Selection state
    const [selectedClasses, setSelectedClasses] = useState<Set<string>>(new Set());

    // Search state
    const [searchQuery, setSearchQuery] = useState("");

    // Execution state
    const [runStatus, setRunStatus] = useState<ExistingTestRunStatus | null>(null);
    const [runLoading, setRunLoading] = useState(false);
    const [runError, setRunError] = useState<string | null>(null);

    // Logs modal
    const [showLogs, setShowLogs] = useState(false);

    // Expanded test classes (show/hide method list)
    const [expandedClasses, setExpandedClasses] = useState<Set<string>>(new Set());

    // Polling ref (so we can clear on unmount)
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // ── Auto-discover on mount ──────────────────────────────────────────────

    useEffect(() => {
        if (!jobId) return;
        doDiscover();
        return () => {
            if (pollingRef.current) clearInterval(pollingRef.current);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [jobId]);

    const doDiscover = useCallback(async () => {
        if (!jobId) return;
        setDiscoveryLoading(true);
        setDiscoveryError(null);
        try {
            const result = await discoverExistingTests(jobId);
            setDiscovery(result);
            if (result.error) {
                setDiscoveryError(result.error);
            }
            // Auto-select all discovered classes
            if (result.tests.length > 0) {
                setSelectedClasses(new Set(result.tests.map((t) => t.id)));
                setExpandedClasses(new Set(result.tests.slice(0, 3).map((t) => t.id)));
            }
        } catch (err) {
            setDiscoveryError(
                err instanceof Error ? err.message : "Failed to discover test cases"
            );
        } finally {
            setDiscoveryLoading(false);
        }
    }, [jobId]);

    // ── Selection helpers ───────────────────────────────────────────────────

    const toggleClass = (id: string) => {
        setSelectedClasses((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const selectAll = () => {
        if (!discovery) return;
        setSelectedClasses(new Set(discovery.tests.map((t) => t.id)));
    };

    const clearAll = () => setSelectedClasses(new Set());

    const toggleExpand = (id: string) => {
        setExpandedClasses((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    // ── Run tests ───────────────────────────────────────────────────────────

    const handleRunTests = async () => {
        if (!jobId || selectedClasses.size === 0) return;
        setRunLoading(true);
        setRunError(null);
        setRunStatus({
            status: "RUNNING",
            total: 0,
            passed: 0,
            failed: 0,
            skipped: 0,
            results: [],
            logs: ["Starting execution..."],
            error: null
        });

        try {
            await runExistingTests(jobId, Array.from(selectedClasses));
            startPolling();
        } catch (err) {
            setRunError(err instanceof Error ? err.message : "Failed to start tests");
            setRunStatus(null);
            setRunLoading(false);
        }
    };

    const startPolling = () => {
        if (pollingRef.current) clearInterval(pollingRef.current);
        pollingRef.current = setInterval(async () => {
            if (!jobId) return;
            try {
                const status = await getExistingTestStatus(jobId);
                setRunStatus(status);
                if (status.status === "COMPLETED" || status.status === "FAILED") {
                    if (pollingRef.current) clearInterval(pollingRef.current);
                    pollingRef.current = null;
                    setRunLoading(false);
                    if (status.error) setRunError(status.error);
                }
            } catch {
                // Silently retry on transient failure
            }
        }, 2000);
    };

    // ── Don't render if no jobId ────────────────────────────────────────────

    if (!jobId) return null;
    if (!jobId) return null;

    const tests = discovery?.tests ?? [];
    const isRunning = runStatus?.status === "RUNNING";
    const isDone = runStatus?.status === "COMPLETED";
    const isError = runStatus?.status === "FAILED";

    // Filter test classes based on search query
    const filteredTests = tests.filter((tc) =>
        tc.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tc.className.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Statistics calculation
    const totalTestsCount = tests.reduce((acc, tc) => acc + tc.methods.length, 0);
    const selectedTestsCount = tests
        .filter((tc) => selectedClasses.has(tc.id))
        .reduce((acc, tc) => acc + tc.methods.length, 0);

    const statsTotal = totalTestsCount;
    const statsExecuted = runStatus ? runStatus.executed : 0;
    const statsPassed = runStatus ? runStatus.passed : 0;

    return (
        <div
            style={{
                background: "#f8fafc",
                borderRadius: 12,
                border: "1px solid #e2e8f0",
                padding: "24px",
                marginBottom: 24,
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
            }}
        >
            {/* ── Header ── */}
            <div
                style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 16,
                }}
            >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <FaFlask style={{ fontSize: 18, color: "#7c3aed" }} />
                    <span style={{ fontWeight: 800, fontSize: 17, color: "#0f172a" }}>
                        Existing Test Cases
                    </span>
                    {discovery && tests.length > 0 && (
                        <span
                            style={{
                                fontSize: 11,
                                fontWeight: 700,
                                padding: "2px 8px",
                                borderRadius: 9999,
                                background: "#f3e8ff",
                                color: "#7c3aed",
                            }}
                        >
                            {tests.length} class{tests.length !== 1 ? "es" : ""}
                        </span>
                    )}
                </div>
                {discovery && (
                    <button
                        onClick={doDiscover}
                        disabled={discoveryLoading}
                        style={{
                            padding: "6px 14px",
                            borderRadius: 6,
                            border: "1px solid #cbd5e1",
                            background: "#fff",
                            cursor: discoveryLoading ? "not-allowed" : "pointer",
                            fontSize: 12,
                            fontWeight: 700,
                            color: "#475569",
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                            transition: "all 0.15s ease",
                        }}
                        onMouseEnter={(e) => {
                            if (!discoveryLoading) e.currentTarget.style.background = "#f8fafc";
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.background = "#fff";
                        }}
                    >
                        {discoveryLoading ? "⏳ Scanning…" : "↻ Re-scan Repository"}
                    </button>
                )}
            </div>

            {/* ── Framework / Build Tool badges ── */}
            {discovery && !discoveryError && (
                <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
                    <span
                        style={{
                            fontSize: 11,
                            fontWeight: 700,
                            padding: "4px 10px",
                            borderRadius: 6,
                            background: "#eff6ff",
                            color: "#1d4ed8",
                        }}
                    >
                        {discovery.framework || "JUnit 5"}
                    </span>
                    <span
                        style={{
                            fontSize: 11,
                            fontWeight: 700,
                            padding: "4px 10px",
                            borderRadius: 6,
                            background: "#f0fdf4",
                            color: "#166534",
                        }}
                    >
                        {discovery.buildTool || "Maven"}
                    </span>
                </div>
            )}

            {/* ── Loading state ── */}
            {discoveryLoading && !discovery && (
                <div
                    style={{
                        textAlign: "center",
                        padding: "36px 0",
                        color: "#64748b",
                        fontSize: 13,
                        border: "1px dashed #e2e8f0",
                        borderRadius: 8,
                        background: "#fff",
                    }}
                >
                    ⏳ Scanning repository for existing test cases…
                </div>
            )}

            {/* ── Error state ── */}
            {discoveryError && !tests.length && (
                <div
                    style={{
                        padding: "14px 16px",
                        borderRadius: 8,
                        background: "#fffbeb",
                        border: "1px solid #fef3c7",
                        fontSize: 12,
                        color: "#b45309",
                        lineHeight: 1.6,
                    }}
                >
                    ℹ️ {discoveryError}
                </div>
            )}

            {/* ── Main Content: Two Column Layout ── */}
            {tests.length > 0 && (
                <div
                    className="test-cases-layout"
                    style={{
                        display: "grid",
                        gridTemplateColumns: "minmax(300px, 42%) 1fr",
                        gap: "24px",
                    }}
                >
                    {/* ── LEFT PANEL: Test Browser (approx 42%) ── */}
                    <div
                        style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 16,
                            background: "#ffffff",
                            padding: "20px",
                            borderRadius: 10,
                            border: "1px solid #e2e8f0",
                            boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
                            maxHeight: "620px",
                            boxSizing: "border-box",
                        }}
                    >
                        {/* Panel Title */}
                        <div
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 8,
                                borderBottom: "1px solid #f1f5f9",
                                paddingBottom: 10,
                            }}
                        >
                            <span style={{ fontSize: 13, fontWeight: 750, color: "#475569", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                                Test Browser
                            </span>
                        </div>

                        {/* Search Box */}
                        <div style={{ position: "relative" }}>
                            <FaSearch
                                style={{
                                    position: "absolute",
                                    left: 12,
                                    top: "50%",
                                    transform: "translateY(-50%)",
                                    color: "#94a3b8",
                                    fontSize: 13,
                                }}
                            />
                            <input
                                type="text"
                                placeholder="Search test classes..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                style={{
                                    width: "100%",
                                    padding: "8px 12px 8px 34px",
                                    borderRadius: 6,
                                    border: "1px solid #cbd5e1",
                                    fontSize: 13,
                                    outline: "none",
                                    boxSizing: "border-box",
                                }}
                            />
                        </div>

                        {/* Statistics Grid */}
                        <div
                            style={{
                                display: "grid",
                                gridTemplateColumns: "repeat(3, 1fr)",
                                gap: 0,
                                background: "#f8fafc",
                                borderRadius: 8,
                                border: "1px solid #e2e8f0",
                                textAlign: "center",
                                overflow: "hidden",
                            }}
                        >
                            <div style={{ padding: "10px 4px", borderRight: "1px solid #e2e8f0" }}>
                                <div style={{ fontSize: 18, fontWeight: 800, color: "#1e293b" }}>
                                    {statsTotal}
                                </div>
                                <div style={{ fontSize: 9, color: "#64748b", textTransform: "uppercase", fontWeight: 700, marginTop: 2, letterSpacing: "0.5px" }}>
                                    Discovered
                                </div>
                            </div>
                            <div style={{ padding: "10px 4px", borderRight: "1px solid #e2e8f0" }}>
                                <div style={{ fontSize: 18, fontWeight: 800, color: "#7c3aed" }}>
                                    {statsExecuted}
                                </div>
                                <div style={{ fontSize: 9, color: "#64748b", textTransform: "uppercase", fontWeight: 700, marginTop: 2, letterSpacing: "0.5px" }}>
                                    Executed
                                </div>
                            </div>
                            <div style={{ padding: "10px 4px" }}>
                                <div style={{ fontSize: 18, fontWeight: 800, color: "#22c55e" }}>
                                    {statsPassed}
                                </div>
                                <div style={{ fontSize: 9, color: "#64748b", textTransform: "uppercase", fontWeight: 700, marginTop: 2, letterSpacing: "0.5px" }}>
                                    Passed
                                </div>
                            </div>
                        </div>

                        {/* Selection controls */}
                        <div style={{ display: "flex", gap: 12, fontSize: 11, padding: "0 2px" }}>
                            <button
                                onClick={selectAll}
                                style={{
                                    background: "none",
                                    border: "none",
                                    color: "#7c3aed",
                                    fontWeight: 700,
                                    cursor: "pointer",
                                    padding: 0,
                                }}
                            >
                                Select All
                            </button>
                            <span style={{ color: "#cbd5e1" }}>|</span>
                            <button
                                onClick={clearAll}
                                style={{
                                    background: "none",
                                    border: "none",
                                    color: "#64748b",
                                    fontWeight: 700,
                                    cursor: "pointer",
                                    padding: 0,
                                }}
                            >
                                Clear Selection
                            </button>
                        </div>

                        {/* Test class list container with controlled scrolling */}
                        <div
                            style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: 10,
                                flex: 1,
                                overflowY: "auto",
                                paddingRight: "4px",
                                minHeight: 0,
                            }}
                        >
                            {filteredTests.map((tc) => {
                                const isSelected = selectedClasses.has(tc.id);
                                const isExpanded = expandedClasses.has(tc.id);
                                const classResults =
                                    runStatus?.results.filter(
                                        (mr) =>
                                            mr.test_class === tc.className ||
                                            mr.test_class.endsWith("." + tc.id)
                                    ) ?? [];
                                const classDone = classResults.length > 0;
                                const classAllPassed =
                                    classDone && classResults.every((r) => r.status === "PASSED");
                                const classHasFailed =
                                    classDone && classResults.some((r) => r.status === "FAILED" || r.status === "ERROR");

                                // Extract package vs class parts for clean styling
                                const lastDotIndex = tc.id.lastIndexOf(".");
                                const packagePart = lastDotIndex !== -1 ? tc.id.substring(0, lastDotIndex + 1) : "";
                                const classPart = lastDotIndex !== -1 ? tc.id.substring(lastDotIndex + 1) : tc.id;

                                return (
                                    <div
                                        key={tc.id}
                                        style={{
                                            background: isSelected ? "#fbfbfe" : "#ffffff",
                                            border: isSelected ? "1px solid #c084fc" : "1px solid #e2e8f0",
                                            borderRadius: 8,
                                            overflow: "hidden",
                                            transition: "all 0.15s ease",
                                            boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
                                            flexShrink: 0,
                                        }}
                                    >
                                        {/* Class header line */}
                                        <div
                                            style={{
                                                display: "flex",
                                                alignItems: "flex-start",
                                                padding: "10px 12px",
                                                cursor: "pointer",
                                                userSelect: "none",
                                            }}
                                            onClick={() => toggleClass(tc.id)}
                                        >
                                            <input
                                                type="checkbox"
                                                checked={isSelected}
                                                onChange={() => toggleClass(tc.id)}
                                                onClick={(e) => e.stopPropagation()}
                                                style={{
                                                    marginTop: 3,
                                                    marginRight: 10,
                                                    width: 14,
                                                    height: 14,
                                                    accentColor: "#7c3aed",
                                                    cursor: "pointer",
                                                }}
                                            />
                                            
                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                {/* Class Name */}
                                                <div
                                                    style={{
                                                        fontWeight: 700,
                                                        fontSize: 12.5,
                                                        color: isSelected ? "#6b21a8" : "#1e293b",
                                                        wordBreak: "break-all",
                                                        overflowWrap: "anywhere",
                                                        whiteSpace: "normal",
                                                        lineHeight: 1.4,
                                                    }}
                                                >
                                                    {tc.id}
                                                </div>
                                                
                                                {/* File Path */}
                                                <div
                                                    style={{
                                                        fontSize: 10,
                                                        color: "#94a3b8",
                                                        fontFamily: "monospace",
                                                        marginTop: 3,
                                                        wordBreak: "break-all",
                                                        overflowWrap: "anywhere",
                                                        whiteSpace: "normal",
                                                        display: "flex",
                                                        alignItems: "center",
                                                        gap: 4,
                                                    }}
                                                >
                                                    <FaRegFolderOpen size={10} style={{ flexShrink: 0 }} />
                                                    {tc.filePath}
                                                </div>
                                            </div>

                                            {/* Count and Chevron on Right */}
                                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: 10, flexShrink: 0 }}>
                                                <span style={{ fontSize: 11, color: "#64748b", fontWeight: 600 }}>
                                                    {tc.methods.length}
                                                </span>
                                                <span
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        toggleExpand(tc.id);
                                                    }}
                                                    style={{
                                                        color: "#94a3b8",
                                                        display: "flex",
                                                        alignItems: "center",
                                                        padding: "2px",
                                                        cursor: "pointer",
                                                    }}
                                                >
                                                    {isExpanded ? <FaChevronDown size={10} /> : <FaChevronRight size={10} />}
                                                </span>
                                            </div>
                                        </div>

                                        {/* Class status indicator */}
                                        {classDone && (
                                            <div
                                                style={{
                                                    padding: "0 12px 8px 38px",
                                                    fontSize: 11,
                                                    fontWeight: 700,
                                                    color: classAllPassed
                                                        ? "#166534"
                                                        : classHasFailed
                                                            ? "#dc2626"
                                                            : "#475569",
                                                }}
                                            >
                                                {classAllPassed
                                                    ? `✓ ${classResults.length}/${classResults.length} passed`
                                                    : classHasFailed
                                                        ? `✗ ${classResults.filter((r) => r.status === "FAILED" || r.status === "ERROR").length} failed`
                                                        : `${classResults.length} results`}
                                            </div>
                                        )}

                                        {/* Expansion details */}
                                        {isExpanded && (
                                            <div
                                                style={{
                                                    borderTop: "1px solid #f1f5f9",
                                                    padding: "10px 12px 10px 38px",
                                                    background: "#fdfdfd",
                                                }}
                                            >
                                                {tc.methods.length > 0 && (
                                                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 16px" }}>
                                                        {tc.methods.map((method) => {
                                                            const methodResult = classResults.find(
                                                                (mr) => mr.test_method === method
                                                            );
                                                            const statusIcon = methodResult
                                                                 ? methodResult.status === "PASSED"
                                                                     ? "✓"
                                                                     : methodResult.status === "FAILED" || methodResult.status === "ERROR"
                                                                         ? "✗"
                                                                         : "○"
                                                                 : "○";
                                                            const statusColor = methodResult
                                                                ? methodResult.status === "PASSED"
                                                                    ? "#22c55e"
                                                                    : methodResult.status === "FAILED" || methodResult.status === "ERROR"
                                                                        ? "#ef4444"
                                                                        : "#94a3b8"
                                                                : "#94a3b8";

                                                            return (
                                                                <div
                                                                    key={method}
                                                                    style={{
                                                                        display: "flex",
                                                                        alignItems: "center",
                                                                        gap: 6,
                                                                        fontSize: 11,
                                                                        color: "#475569",
                                                                        fontFamily: "'JetBrains Mono', monospace",
                                                                        whiteSpace: "nowrap",
                                                                    }}
                                                                >
                                                                    <span
                                                                        style={{
                                                                            color: statusColor,
                                                                            fontWeight: 700,
                                                                            fontSize: 11,
                                                                        }}
                                                                    >
                                                                        {statusIcon}
                                                                    </span>
                                                                    <span>
                                                                        {method}
                                                                    </span>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* ── RIGHT PANEL: Execution & Selected Tests (approx 58%) ── */}
                    <div
                        style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 16,
                            background: "#ffffff",
                            padding: "20px",
                            borderRadius: 10,
                            border: "1px solid #e2e8f0",
                            boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
                        }}
                    >
                        {/* Top action toolbar */}
                        <div
                            style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                background: "#f8fafc",
                                border: "1px solid #e2e8f0",
                                borderRadius: 8,
                                padding: "10px 14px",
                            }}
                        >
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <span style={{ fontWeight: 700, fontSize: 12.5, color: "#1e293b" }}>
                                    ☑ {selectedTestsCount} test{selectedTestsCount !== 1 ? "s" : ""} selected
                                </span>
                                {selectedClasses.size > 0 && (
                                    <button
                                        onClick={clearAll}
                                        style={{
                                            background: "none",
                                            border: "none",
                                            color: "#64748b",
                                            fontSize: 11,
                                            fontWeight: 700,
                                            cursor: "pointer",
                                            textDecoration: "underline",
                                            padding: 0,
                                        }}
                                    >
                                        Clear Selection
                                    </button>
                                )}
                            </div>
                            <button
                                onClick={handleRunTests}
                                disabled={selectedClasses.size === 0 || isRunning}
                                style={{
                                    padding: "6px 14px",
                                    borderRadius: 6,
                                    border: "none",
                                    background:
                                        selectedClasses.size === 0 || isRunning
                                            ? "#cbd5e1"
                                            : "#7c3aed",
                                    color: "#fff",
                                    fontWeight: 700,
                                    fontSize: 12,
                                    cursor:
                                        selectedClasses.size === 0 || isRunning
                                            ? "not-allowed"
                                            : "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 6,
                                    transition: "background 0.15s ease",
                                }}
                            >
                                {isRunning ? (
                                    <span>⏳ Running Tests...</span>
                                ) : (
                                    <span>▶ Run Selected Tests ({selectedTestsCount})</span>
                                )}
                            </button>
                        </div>

                        {/* Selected Tests Header */}
                        <div style={{ fontSize: 13, fontWeight: 750, color: "#475569", textTransform: "uppercase", letterSpacing: "0.5px", borderBottom: "1px solid #f1f5f9", paddingBottom: 10 }}>
                            Selected Tests ({selectedClasses.size} classes)
                        </div>

                        {/* Selected Test details with scrollbar */}
                        <div
                            style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: 12,
                                maxHeight: "420px",
                                overflowY: "auto",
                                overflowX: "hidden",
                                paddingRight: "4px",
                            }}
                        >
                            {selectedClasses.size === 0 ? (
                                <div style={{ color: "#94a3b8", fontSize: 12, margin: "40px auto", textAlign: "center" }}>
                                    No classes selected. Choose classes on the left to include them.
                                </div>
                            ) : (
                                tests
                                    .filter((tc) => selectedClasses.has(tc.id))
                                    .map((tc) => {
                                        const classResults =
                                            runStatus?.results.filter(
                                                (mr) =>
                                                    mr.test_class === tc.className ||
                                                    mr.test_class.endsWith("." + tc.id)
                                            ) ?? [];
                                        const classDone = classResults.length > 0;
                                        const classAllPassed =
                                            classDone && classResults.every((r) => r.status === "PASSED");
                                        const classHasFailed =
                                            classDone && classResults.some((r) => r.status === "FAILED" || r.status === "ERROR");

                                        return (
                                            <div
                                                key={`sel-${tc.id}`}
                                                style={{
                                                    border: "1px solid #e2e8f0",
                                                    borderRadius: 8,
                                                    padding: "10px",
                                                    background: "#ffffff",
                                                    minWidth: 0,
                                                    wordBreak: "break-word",
                                                    overflowWrap: "anywhere",
                                                }}
                                            >
                                                <div
                                                    style={{
                                                        display: "flex",
                                                        alignItems: "flex-start",
                                                        justifyContent: "space-between",
                                                        gap: 8,
                                                    }}
                                                >
                                                    <span
                                                        style={{
                                                            fontWeight: 700,
                                                            fontSize: 12.5,
                                                            color: "#334155",
                                                            wordBreak: "break-all",
                                                            overflowWrap: "anywhere",
                                                            whiteSpace: "normal"
                                                        }}
                                                    >
                                                        ☑ {tc.id}
                                                    </span>
                                                    {classDone && (
                                                        <span
                                                            style={{
                                                                fontSize: 10.5,
                                                                fontWeight: 700,
                                                                color: classAllPassed
                                                                    ? "#166534"
                                                                    : classHasFailed
                                                                        ? "#dc2626"
                                                                        : "#475569",
                                                                marginTop: 2,
                                                                flexShrink: 0
                                                            }}
                                                        >
                                                            {classAllPassed
                                                                ? `✓ ${classResults.length}/${classResults.length} passed`
                                                                : classHasFailed
                                                                    ? `✗ ${classResults.filter((r) => r.status === "FAILED" || r.status === "ERROR").length} failed`
                                                                    : `${classResults.length} results`}
                                                        </span>
                                                    )}
                                                </div>
                                                <div
                                                    style={{
                                                        fontSize: 10,
                                                        color: "#94a3b8",
                                                        fontFamily: "monospace",
                                                        margin: "2px 0 6px 0",
                                                        wordBreak: "break-all",
                                                        overflowWrap: "anywhere",
                                                        whiteSpace: "normal"
                                                    }}
                                                >
                                                    {tc.filePath}
                                                </div>
                                                
                                                {/* Selected methods layout */}
                                                <div
                                                    style={{
                                                        display: "grid",
                                                        gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
                                                        gap: "4px 10px",
                                                        paddingLeft: 4,
                                                        borderTop: "1px solid #f8fafc",
                                                        paddingTop: 6,
                                                    }}
                                                >
                                                    {tc.methods.map((method) => {
                                                        const methodResult = classResults.find(
                                                            (mr) => mr.test_method === method
                                                        );
                                                        const isPassed = methodResult?.status === "PASSED";
                                                        const isFailed = methodResult?.status === "FAILED" || methodResult?.status === "ERROR";
                                                        const isSkipped = methodResult?.status === "SKIPPED";
                                                        
                                                        const statusIcon = isPassed
                                                            ? "✓"
                                                            : isFailed
                                                                ? "✗"
                                                                : isSkipped
                                                                    ? "○"
                                                                    : isRunning
                                                                        ? "●"
                                                                        : "○";

                                                        const statusColor = isPassed
                                                            ? "#22c55e"
                                                            : isFailed
                                                                ? "#ef4444"
                                                                : isSkipped
                                                                    ? "#f97316"
                                                                    : isRunning
                                                                        ? "#7c3aed"
                                                                        : "#94a3b8";

                                                        return (
                                                            <div
                                                                key={`sel-m-${method}`}
                                                                style={{
                                                                    display: "flex",
                                                                    alignItems: "center",
                                                                    gap: 6,
                                                                    fontSize: 11,
                                                                    fontFamily: "monospace",
                                                                    color: isPassed ? "#166534" : "#475569",
                                                                }}
                                                            >
                                                                <span style={{ color: statusColor, fontWeight: 700 }}>
                                                                    {statusIcon}
                                                                </span>
                                                                <span>{method}</span>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        );
                                    })
                            )}
                        </div>

                        {/* Running Overlay indicator */}
                        {isRunning && (
                            <div
                                style={{
                                    padding: "10px 14px",
                                    borderRadius: 6,
                                    background: "#f5f3ff",
                                    border: "1px solid #ddd6fe",
                                    fontSize: 11.5,
                                    color: "#6d28d9",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 8,
                                }}
                            >
                                <span>⏳</span>
                                <strong>Running Tests…</strong>
                            </div>
                        )}

                        {/* Execution Error banner */}
                        {(isError || runError) && runStatus?.error !== "LOMBOK_JDK_INCOMPATIBILITY" && runStatus?.error !== "BUILD_FAILED" && (
                            <div
                                style={{
                                    padding: "10px 14px",
                                    borderRadius: 6,
                                    background: "#fef2f2",
                                    border: "1px solid #fecaca",
                                    fontSize: 11.5,
                                    color: "#dc2626",
                                    lineHeight: 1.5,
                                }}
                            >
                                ⚠️ {runError || runStatus?.error || "Test execution encountered an error."}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* ── Test Execution Result Section ── */}
            {runStatus && (isDone || isRunning || isError) && (
                <div
                    style={{
                        marginTop: 20,
                        border: "1px solid #e2e8f0",
                        borderRadius: 10,
                        overflow: "hidden",
                        background: "#ffffff",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
                    }}
                >
                    {/* Header Bar */}
                    <div
                        style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "16px 20px",
                            background: "#f8fafc",
                            borderBottom: "1px solid #e2e8f0",
                        }}
                    >
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <span style={{ fontWeight: 750, fontSize: 13, color: "#475569", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                                Test Execution Result
                            </span>
                            {(runStatus.error === "LOMBOK_JDK_INCOMPATIBILITY" || runStatus.error === "BUILD_FAILED") && (
                                <span style={{
                                    fontSize: 10,
                                    fontWeight: 700,
                                    padding: "2px 8px",
                                    borderRadius: 4,
                                    background: "#fee2e2",
                                    color: "#dc2626",
                                    textTransform: "uppercase"
                                }}>
                                    Build Status: FAILED
                                </span>
                            )}
                        </div>
                        {runStatus && (isDone || isRunning) && (
                            <div style={{ display: "flex", gap: 16 }}>
                                <span style={{ fontSize: 11.5, fontWeight: 600, color: "#475569" }}>
                                    Executed: <strong>{runStatus.executed}</strong>
                                </span>
                                <span style={{ fontSize: 11.5, fontWeight: 600, color: "#22c55e" }}>
                                    Passed: <strong>{runStatus.passed}</strong>
                                </span>
                                <span style={{ fontSize: 11.5, fontWeight: 600, color: runStatus.failed > 0 ? "#ef4444" : "#64748b" }}>
                                    Failed: <strong>{runStatus.failed}</strong>
                                </span>
                                <span style={{ fontSize: 11.5, fontWeight: 600, color: runStatus.skipped > 0 ? "#ea580c" : "#64748b" }}>
                                    Skipped: <strong>{runStatus.skipped}</strong>
                                </span>
                            </div>
                        )}
                    </div>

                    {/* State 1: NOT STARTED ── Handled in right panel */}

                    {/* State 2: RUNNING */}
                    {isRunning && (
                        <div style={{ padding: "20px 20px" }}>
                            <div
                                style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    fontSize: 11.5,
                                    color: "#64748b",
                                    marginBottom: 8,
                                }}
                            >
                                <strong>Running tests...</strong>
                                <span>In progress</span>
                            </div>
                            <div
                                style={{
                                    width: "100%",
                                    height: 8,
                                    background: "#e2e8f0",
                                    borderRadius: 4,
                                    overflow: "hidden",
                                }}
                            >
                                <div
                                    style={{
                                        width: `${selectedTestsCount > 0 ? Math.min(100, Math.round((runStatus.executed / selectedTestsCount) * 100)) : 50}%`,
                                        height: "100%",
                                        background: "#7c3aed",
                                        borderRadius: 4,
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* State 3: DONE */}
                    {isDone && runStatus && (
                        <>
                            {/* Build failed banner ── when executed === 0 or error matches build failure */}
                            {(runStatus.executed === 0 || runStatus.error === "LOMBOK_JDK_INCOMPATIBILITY" || runStatus.error === "BUILD_FAILED") ? (
                                <div
                                    style={{
                                        margin: "20px",
                                        padding: "20px",
                                        borderRadius: 8,
                                        background: "#fef2f2",
                                        border: "1px solid #fecaca",
                                        fontSize: 12.5,
                                        color: "#dc2626",
                                        display: "flex",
                                        flexDirection: "column",
                                        gap: 12,
                                        alignItems: "center",
                                        textAlign: "center",
                                    }}
                                >
                                    <span style={{ fontSize: 24 }}>⚠️</span>
                                    <div style={{ fontWeight: 800, fontSize: 14 }}>Build Failed</div>
                                    <div style={{ color: "#7f1d1d", fontSize: 12, maxWidth: 500, lineHeight: 1.6 }}>
                                        The project could not compile, so the selected tests were not executed. Check the build logs below for details.
                                    </div>
                                </div>
                            ) : (
                                <>
                                    {/* Progress Bar & Status text */}
                                    <div style={{ padding: "16px 20px 8px 20px" }}>
                                        <div
                                            style={{
                                                display: "flex",
                                                justifyContent: "space-between",
                                                fontSize: 11.5,
                                                color: "#64748b",
                                                marginBottom: 8,
                                            }}
                                        >
                                            <span>{runStatus.failed > 0 ? "Tests completed with failures" : "All tests completed"}</span>
                                            <span style={{ fontWeight: 700 }}>100%</span>
                                        </div>
                                        <div
                                            style={{
                                                width: "100%",
                                                height: 8,
                                                background: "#e2e8f0",
                                                borderRadius: 4,
                                                overflow: "hidden",
                                            }}
                                        >
                                            <div
                                                style={{
                                                    width: "100%",
                                                    height: "100%",
                                                    background: runStatus.failed > 0 ? "#ef4444" : "#22c55e",
                                                    borderRadius: 4,
                                                }}
                                            />
                                        </div>
                                    </div>

                                    {/* Results List grouped by Class */}
                                    <div
                                        style={{
                                            maxHeight: "220px",
                                            overflowY: "auto",
                                            padding: "8px 20px",
                                        }}
                                    >
                                        {tests
                                            .filter((tc) => selectedClasses.has(tc.id))
                                            .map((tc) => {
                                                const classResults = runStatus.results.filter(
                                                    (mr) =>
                                                        mr.test_class === tc.className ||
                                                        mr.test_class.endsWith("." + tc.id)
                                                );
                                                if (classResults.length === 0) return null;

                                                const passedCount = classResults.filter((r) => r.status === "PASSED").length;
                                                const totalCount = classResults.length;
                                                const totalDuration = classResults.reduce(
                                                    (sum, r) => sum + r.execution_time_seconds,
                                                    0
                                                );

                                                return (
                                                    <div
                                                        key={`res-row-${tc.id}`}
                                                        style={{
                                                            display: "flex",
                                                            alignItems: "center",
                                                            justifyContent: "space-between",
                                                            padding: "10px 0",
                                                            borderBottom: "1px solid #f1f5f9",
                                                            fontSize: 12,
                                                        }}
                                                    >
                                                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                                            <span style={{ color: passedCount === totalCount ? "#22c55e" : "#ef4444", fontWeight: 700 }}>
                                                                {passedCount === totalCount ? "✓" : "✗"}
                                                            </span>
                                                            <span style={{ fontWeight: 700, color: "#334155" }}>
                                                                {tc.id}
                                                            </span>
                                                        </div>
                                                        <div style={{ display: "flex", gap: 16, color: "#64748b" }}>
                                                            <span style={{ fontWeight: 600 }}>{passedCount} passed</span>
                                                            {totalDuration > 0 && (
                                                                <span style={{ fontFamily: "monospace" }}>
                                                                    {totalDuration.toFixed(3)}s
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                    </div>
                                </>
                            )}

                            {/* View Detailed Logs button */}
                            {runStatus.logs.length > 0 && (
                                <div
                                    style={{
                                        padding: "12px 20px",
                                        borderTop: "1px solid #e2e8f0",
                                        textAlign: "right",
                                    }}
                                >
                                    <button
                                        onClick={() => setShowLogs(true)}
                                        style={{
                                            padding: "6px 14px",
                                            borderRadius: 6,
                                            border: "1px solid #cbd5e1",
                                            background: "#fff",
                                            cursor: "pointer",
                                            fontSize: 11,
                                            fontWeight: 700,
                                            color: "#475569",
                                            transition: "all 0.15s ease",
                                        }}
                                        onMouseEnter={(e) => {
                                            e.currentTarget.style.background = "#f8fafc";
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.background = "#fff";
                                        }}
                                    >
                                        {runStatus.executed === 0 ? "View Build Logs" : "View Detailed Logs"}
                                    </button>
                                </div>
                            )}
                        </>
                    )}

                    {/* State 4: ERROR */}
                    {isError && (
                        <div style={{ padding: "20px 20px", color: "#dc2626", fontSize: 12.5 }}>
                            <div style={{ fontWeight: 700, marginBottom: 6 }}>Test execution failed</div>
                            <div>
                                {runError || runStatus?.error || "An error occurred during test execution."}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ── Logs modal ──────────────────────────────────────────────── */}
            {showLogs && runStatus && (
                <div
                    style={{
                        position: "fixed",
                        inset: 0,
                        zIndex: 10001,
                        background: "rgba(15,23,42,0.7)",
                        backdropFilter: "blur(4px)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        padding: 20,
                    }}
                    onClick={() => setShowLogs(false)}
                >
                    <div
                        style={{
                            background: "#fff",
                            borderRadius: 14,
                            maxWidth: 900,
                            width: "100%",
                            maxHeight: "85vh",
                            display: "flex",
                            flexDirection: "column",
                            boxShadow: "0 25px 80px rgba(0,0,0,0.35)",
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div
                            style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                padding: "16px 20px",
                                borderBottom: "1px solid #e2e8f0",
                                background: "linear-gradient(135deg, #0f172a, #1e293b)",
                                borderRadius: "14px 14px 0 0",
                            }}
                        >
                            <span style={{ fontWeight: 700, fontSize: 14, color: "#fff" }}>
                                📋 Test Execution Logs
                            </span>
                            <button
                                onClick={() => setShowLogs(false)}
                                style={{
                                    background: "rgba(255,255,255,0.15)",
                                    border: "none",
                                    color: "#fff",
                                    width: 30,
                                    height: 30,
                                    borderRadius: 8,
                                    cursor: "pointer",
                                    fontSize: 16,
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                }}
                            >
                                ✕
                            </button>
                        </div>
                        <div
                            style={{
                                overflow: "auto",
                                flex: 1,
                                background: "#0d1117",
                                padding: 16,
                            }}
                        >
                            <pre
                                style={{
                                    margin: 0,
                                    fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
                                    fontSize: 12,
                                    lineHeight: 1.6,
                                    color: "#e2e8f0",
                                    whiteSpace: "pre-wrap",
                                    wordBreak: "break-all",
                                }}
                            >
                                {runStatus.logs.join("\n") || "No log output captured."}
                            </pre>
                        </div>
                        <div
                            style={{
                                display: "flex",
                                justifyContent: "flex-end",
                                padding: "12px 20px",
                                borderTop: "1px solid #e2e8f0",
                                background: "#f8fafc",
                                borderRadius: "0 0 14px 14px",
                            }}
                        >
                            <button
                                onClick={() => setShowLogs(false)}
                                style={{
                                    padding: "8px 20px",
                                    borderRadius: 8,
                                    border: "1px solid #e2e8f0",
                                    background: "#fff",
                                    cursor: "pointer",
                                    fontSize: 13,
                                    fontWeight: 600,
                                    color: "#475569",
                                }}
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
