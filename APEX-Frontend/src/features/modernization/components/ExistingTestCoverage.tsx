import React, { useState, useEffect, useMemo } from "react";
import {
  FaVial,
  FaFlask,
  FaDesktop,
  FaFileAlt,
  FaSpinner,
  FaLayerGroup,
  FaCode,
  FaCog,
  FaPen,
} from "react-icons/fa";
import { classifyTestType, deriveTestingTypes, type TestResult, type TestSelectionItem } from "../services/existingTestService";
import { getBrdMetadata, getBrdDocumentBlob } from "@/features/discovery/services/discoveryService";

interface MetricCardProps {
  label: string;
  value: string | number;
  color: string;
  bgColor: string;
  icon: React.ReactNode;
}

function MetricCard({ label, value, color, bgColor, icon }: MetricCardProps) {
  const displayValue = value !== undefined && value !== null && value !== "" ? value : "0";

  return (
    <div
      style={{
        background: bgColor,
        border: `1px solid ${color}15`,
        borderRadius: 12,
        padding: "16px 18px",
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
            fontWeight: 800,
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
          width: 36,
          height: 36,
          borderRadius: 8,
          background: "rgba(0, 0, 0, 0.02)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: color,
          fontSize: 15,
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
    </div>
  );
}

interface ExistingTestCoverageProps {
  jobId?: string;
  title?: string;
  filterMode?: "all" | "unit" | "functional";
  metrics?: {
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
  discoveredTests?: (TestResult | TestSelectionItem)[];
  testResults?: TestResult[];
  isExecuted?: boolean;
  frameworkInfo?: {
    detected_framework?: string;
    build_tool?: string | null;
    test_source_dir?: string;
  };
  onRunAll?: () => void;
  onOpenReport?: () => void;
}

export function ExistingTestCoverage({
  jobId,
  title,
  filterMode = "all",
  metrics = {},
  discoveredTests = [],
  testResults = [],
  frameworkInfo,
  onRunAll: _onRunAll,
  onOpenReport,
}: ExistingTestCoverageProps) {
  const [hasDocument, setHasDocument] = useState(false);
  const [isViewingDocument, setIsViewingDocument] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setHasDocument(false);
      return;
    }
    let isMounted = true;
    async function checkDoc() {
      try {
        const meta = await getBrdMetadata(jobId!);
        if (isMounted && meta && meta.filename) {
          setHasDocument(true);
        } else if (isMounted) {
          setHasDocument(false);
        }
      } catch {
        if (isMounted) setHasDocument(false);
      }
    }
    void checkDoc();
    return () => {
      isMounted = false;
    };
  }, [jobId]);

  const handleViewDocument = async () => {
    if (!jobId || isViewingDocument) return;
    setIsViewingDocument(true);
    setDocError(null);
    try {
      const { blob, contentType } = await getBrdDocumentBlob(jobId);
      const typedBlob = new Blob([blob], { type: contentType });
      const url = URL.createObjectURL(typedBlob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch {
      setDocError("Failed to open the Functional Testing Document.");
      setTimeout(() => setDocError(null), 5000);
    } finally {
      setIsViewingDocument(false);
    }
  };

  // Canonical tests pool
  const allTests = useMemo(() => {
    if (testResults && testResults.length > 0) return testResults;
    if (discoveredTests && discoveredTests.length > 0) return discoveredTests;
    return [];
  }, [testResults, discoveredTests]);

  const total = allTests.length || (metrics.total ?? 0);
  const frameworkName = useMemo(() => {
    return deriveTestingTypes(
      allTests,
      filterMode,
      frameworkInfo?.detected_framework || metrics.type
    );
  }, [allTests, filterMode, frameworkInfo?.detected_framework, metrics.type]);

  // Dynamic test-type counts calculated directly from actual discovered existing test cases
  const { apiCount, uiCount, unitCount } = useMemo(() => {
    let api = 0;
    let ui = 0;
    let unit = 0;

    allTests.forEach((t) => {
      const type = classifyTestType(t);
      if (type === "API") {
        api++;
      } else if (type === "UI") {
        ui++;
      } else {
        unit++;
      }
    });

    return { apiCount: api, uiCount: ui, unitCount: unit };
  }, [allTests]);

  const headerTitle = title || (filterMode === "unit" ? "Existing Unit Tests" : filterMode === "functional" ? "Existing Functional Tests" : "Existing Tests");
  const iconColor = filterMode === "functional" ? "#6366f1" : "#2563eb";

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
          marginBottom: 20,
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <FaPen style={{ fontSize: 16, color: iconColor }} />
          <span
            style={{
              fontWeight: 900,
              fontSize: 16,
              color: "#0f172a",
            }}
          >
            {headerTitle}
          </span>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {hasDocument && (
            <button
              type="button"
              onClick={() => void handleViewDocument()}
              disabled={isViewingDocument}
              style={{
                padding: "8px 16px",
                background: "#ffffff",
                color: "#7c3aed",
                border: "1px solid #ddd6fe",
                borderRadius: 8,
                fontWeight: 700,
                fontSize: 12,
                cursor: isViewingDocument ? "wait" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                transition: "all 0.15s ease",
              }}
              title="View Functional Testing Document"
              aria-label="View Functional Testing Document"
            >
              {isViewingDocument ? (
                <FaSpinner className="animate-spin" size={12} />
              ) : (
                <FaFileAlt size={12} style={{ color: "#7c3aed" }} />
              )}
              <span>View Document</span>
            </button>
          )}
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
        </div>
      </div>

      {docError && (
        <div
          style={{
            marginBottom: 16,
            padding: "8px 14px",
            borderRadius: 8,
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#dc2626",
            fontSize: 12,
          }}
        >
          ⚠ {docError}
        </div>
      )}

      {/* Grid containing metrics corresponding to the selected mode */}
      {filterMode === "unit" ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 16,
          }}
        >
          <MetricCard
            label="Total Unit Tests"
            value={unitCount}
            color="#2563eb"
            bgColor="rgba(37, 99, 235, 0.05)"
            icon={<FaLayerGroup />}
          />
          <MetricCard
            label="Testing Types"
            value={frameworkName}
            color="#d97706"
            bgColor="rgba(217, 119, 6, 0.05)"
            icon={<FaCode />}
          />
          <MetricCard
            label="Unit Tests"
            value={unitCount}
            color="#059669"
            bgColor="rgba(5, 150, 105, 0.05)"
            icon={<FaCog />}
          />
        </div>
      ) : filterMode === "functional" ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 16,
          }}
        >
          <MetricCard
            label="Total Functional Tests"
            value={apiCount + uiCount}
            color="#6366f1"
            bgColor="rgba(99, 102, 241, 0.05)"
            icon={<FaLayerGroup />}
          />
          <MetricCard
            label="Testing Types"
            value={frameworkName}
            color="#d97706"
            bgColor="rgba(217, 119, 6, 0.05)"
            icon={<FaCode />}
          />
          <MetricCard
            label="API Tests"
            value={apiCount}
            color="#0284c7"
            bgColor="rgba(2, 132, 199, 0.05)"
            icon={<FaFlask />}
          />
          <MetricCard
            label="UI Tests"
            value={uiCount}
            color="#7c3aed"
            bgColor="rgba(124, 58, 237, 0.05)"
            icon={<FaDesktop />}
          />
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 16,
          }}
        >
          <MetricCard
            label="Total Tests"
            value={total}
            color="#2563eb"
            bgColor="rgba(37, 99, 235, 0.05)"
            icon={<FaLayerGroup />}
          />
          <MetricCard
            label="Testing Types"
            value={frameworkName}
            color="#d97706"
            bgColor="rgba(217, 119, 6, 0.05)"
            icon={<FaCode />}
          />
          <MetricCard
            label="API Tests"
            value={apiCount}
            color="#0284c7"
            bgColor="rgba(2, 132, 199, 0.05)"
            icon={<FaFlask />}
          />
          <MetricCard
            label="UI Tests"
            value={uiCount}
            color="#7c3aed"
            bgColor="rgba(124, 58, 237, 0.05)"
            icon={<FaDesktop />}
          />
          <MetricCard
            label="Unit Tests"
            value={unitCount}
            color="#059669"
            bgColor="rgba(5, 150, 105, 0.05)"
            icon={<FaCog />}
          />
        </div>
      )}
    </div>
  );
}
