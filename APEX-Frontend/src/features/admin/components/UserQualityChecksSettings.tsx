import React, { useState, useEffect } from "react";
import { FaShieldAlt, FaEye, FaEyeSlash, FaFlask, FaSpinner, FaLightbulb, FaCheckCircle } from "react-icons/fa";
import { getQualityChecksAdminConfig, analyzeTestingPrompt, type FullUserSettings, type TestingPromptAnalysisResult } from "../services/adminService";

interface UserQualityChecksSettingsProps {
  settings: FullUserSettings;
  onChange: React.Dispatch<React.SetStateAction<FullUserSettings>>;
}

export default function UserQualityChecksSettings({
  settings,
  onChange,
}: UserQualityChecksSettingsProps) {
  const [adminConfig, setAdminConfig] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSecrets, setShowSecrets] = useState<{ [key: string]: boolean }>({});

  const currentPrompt = settings?.quality_checks_values?.testing_prompt || settings?.test_cases_values?.testing_prompt || "";

  const [analyzingPrompt, setAnalyzingPrompt] = useState(false);
  const [promptAnalysis, setPromptAnalysis] = useState<TestingPromptAnalysisResult | null>(null);
  const [promptAnalysisErr, setPromptAnalysisErr] = useState<string | null>(null);

  const selectedPredefinedPrompts: string[] = Array.isArray(settings?.quality_checks_values?.selected_predefined_prompts)
    ? settings.quality_checks_values.selected_predefined_prompts
    : [];

  const [predefinedPrompts] = useState<any[]>([
    {
      id: "comprehensive_junit_coverage",
      title: "Comprehensive JUnit Coverage",
      prompt: "Analyze the entire application and create comprehensive JUnit test coverage across the repository...",
      description: "Provides broad repository-level JUnit coverage by dynamically analyzing application code, identifying important testable areas, and using JaCoCo results to improve meaningful coverage toward the 80–90% target."
    },
    {
      id: "business_logic_functional_paths",
      title: "Business Logic & Functional Paths",
      prompt: "Analyze the repository and generate JUnit tests that provide broad coverage of the application's core business logic...",
      description: "Focuses JUnit testing on meaningful application behavior and core execution paths while dynamically identifying business logic from the repository."
    },
    {
      id: "branch_condition_edge_case",
      title: "Branch, Condition & Edge-Case Coverage",
      prompt: "Analyze the entire repository and generate JUnit tests that maximize meaningful coverage of conditional logic...",
      description: "Strengthens JUnit coverage by dynamically identifying conditional branches, decision paths, boundaries, and edge cases that may otherwise remain untested."
    },
    {
      id: "exception_negative_scenario",
      title: "Exception & Negative Scenario Coverage",
      prompt: "Analyze the repository and create comprehensive JUnit tests for error handling, exception paths...",
      description: "Improves JUnit coverage of error handling and failure paths while maintaining coverage of normal application behavior."
    },
    {
      id: "jacoco_dynamic_coverage_gap",
      title: "JaCoCo Dynamic Coverage Gap Analysis",
      prompt: "Analyze the existing JUnit tests and JaCoCo coverage report for the entire repository...",
      description: "Uses the actual JaCoCo report together with source-code analysis to dynamically identify and close meaningful JUnit coverage gaps."
    }
  ]);

  const [activeModalPrompt, setActiveModalPrompt] = useState<any | null>(null);

  const handleTogglePredefinedPrompt = (promptId: string) => {
    const currentSelected: string[] = Array.isArray(settings?.quality_checks_values?.selected_predefined_prompts)
      ? settings.quality_checks_values.selected_predefined_prompts
      : [];
    const nextSelected = currentSelected.includes(promptId)
      ? currentSelected.filter((id) => id !== promptId)
      : [...currentSelected, promptId];

    onChange((prev) => ({
      ...prev,
      quality_checks_values: {
        ...(prev?.quality_checks_values || {}),
        selected_predefined_prompts: nextSelected,
      },
    }));
    setPromptAnalysis(null);
  };

  const handlePromptChange = (val: string) => {
    onChange((prev) => ({
      ...prev,
      quality_checks_values: {
        ...(prev?.quality_checks_values || {}),
        testing_prompt: val,
      },
      test_cases_values: {
        ...(prev?.test_cases_values || {}),
        testing_prompt: val,
      },
    }));
    setPromptAnalysis(null);
  };

  const handleAnalyzePrompt = async () => {
    const hasManual = Boolean(currentPrompt.trim());
    const hasPredefined = selectedPredefinedPrompts.length > 0;

    if (!hasManual && !hasPredefined) {
      alert("Please select at least one predefined prompt or enter a manual testing prompt.");
      return;
    }

    setAnalyzingPrompt(true);
    setPromptAnalysis(null);
    setPromptAnalysisErr(null);
    try {
      const res = await analyzeTestingPrompt(currentPrompt, selectedPredefinedPrompts);
      setPromptAnalysis(res);
    } catch (err: any) {
      setPromptAnalysisErr(err.message || "Failed to analyze prompt.");
    } finally {
      setAnalyzingPrompt(false);
    }
  };

  useEffect(() => {
    if ((currentPrompt.trim() || selectedPredefinedPrompts.length > 0) && !promptAnalysis && !analyzingPrompt) {
      analyzeTestingPrompt(currentPrompt, selectedPredefinedPrompts)
        .then((res) => setPromptAnalysis(res))
        .catch(() => {});
    }
  }, [currentPrompt, selectedPredefinedPrompts.length]);

  useEffect(() => {
    const fetchAdminConfig = async () => {
      try {
        const response = await getQualityChecksAdminConfig();
        const rawConfig = response.quality_checks_config;
        if (rawConfig) {
          let parsed: any = rawConfig;
          if (typeof parsed === "string") {
            try {
              parsed = JSON.parse(parsed);
            } catch (pErr) {
              console.warn("First JSON.parse failed, rawConfig:", rawConfig);
            }
          }
          if (typeof parsed === "string") {
            try {
              parsed = JSON.parse(parsed);
            } catch (pErr) {
              console.warn("Second JSON.parse failed:", parsed);
            }
          }
          const configArray = Array.isArray(parsed)
            ? parsed
            : (typeof parsed === "object" && parsed !== null ? Object.values(parsed) : []);
          setAdminConfig(configArray);
        } else {
          setAdminConfig([]);
        }
      } catch (err: any) {
        console.error("Failed to fetch quality checks admin config:", err);
        setError("Failed to load admin configuration for Quality Checks.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchAdminConfig();
  }, []);

  // Pre-fill default values into the state
  useEffect(() => {
    if (!isLoading && adminConfig.length > 0) {
      let changed = false;
      const newValues = { ...(settings?.quality_checks_values || {}) };

      adminConfig.forEach((check: any) => {
        if (check.enabled && Array.isArray(check.fields)) {
          check.fields.forEach((field: any) => {
            if (field.defaultValue && newValues[field.id] === undefined) {
              newValues[field.id] = field.defaultValue;
              changed = true;
            }
          });
        }
      });

      if (changed) {
        onChange((prev) => ({
          ...prev,
          quality_checks_values: newValues,
        }));
      }
    }
  }, [isLoading, adminConfig, settings?.quality_checks_values, onChange]);

  const handleValueChange = (id: string, value: string) => {
    onChange((prev) => ({
      ...prev,
      quality_checks_values: {
        ...(prev?.quality_checks_values || {}),
        [id]: value,
      },
    }));
  };

  const toggleSecret = (id: string) => {
    setShowSecrets((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  if (isLoading) {
    return (
      <div className="admin-loading-state">
        <div className="spinner-modern"></div>
        <span>Loading Quality Checks configuration...</span>
      </div>
    );
  }

  if (error) {
    return <div style={{ color: "#ef4444", padding: "16px" }}>{error}</div>;
  }

  const enabledChecks = Array.isArray(adminConfig) ? adminConfig.filter((check: any) => check.enabled) : [];
  const hasAnyActivePrompt = selectedPredefinedPrompts.length > 0 || currentPrompt.trim().length > 0;

  const hasUnitTestCheckInConfig = enabledChecks.some((check: any) => {
    const cId = (check.id || "").toLowerCase();
    const cName = (check.name || "").toLowerCase();
    return cId.includes("unit") || cName.includes("unit") || cName.includes("test");
  });

  const renderPromptSection = () => (
    <div style={{ marginTop: "20px", padding: "20px", borderRadius: "8px", border: "1px solid #cbd5e1", backgroundColor: "#f8fafc" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <h4 style={{ margin: 0, fontSize: "1.05rem", color: "#1e293b", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
          <FaFlask style={{ color: "#2563eb" }} />
          Run Unit Test Suite Focus Prompt (JUnit)
        </h4>
        <span style={{
          padding: "4px 12px",
          borderRadius: "20px",
          fontSize: "0.75rem",
          fontWeight: 700,
          backgroundColor: hasAnyActivePrompt ? "#dcfce7" : "#f1f5f9",
          color: hasAnyActivePrompt ? "#166534" : "#64748b",
          border: `1px solid ${hasAnyActivePrompt ? "#86efac" : "#cbd5e1"}`
        }}>
          {hasAnyActivePrompt ? `✓ ${selectedPredefinedPrompts.length} PREDEFINED + MANUAL` : "STANDARD SUITE (NO PROMPT)"}
        </span>
      </div>

      {/* SECTION 1: PREDEFINED JUNIT PROMPTS CHECKBOXES */}
      <div style={{ marginBottom: "20px", padding: "16px", borderRadius: "8px", backgroundColor: "#ffffff", border: "1px solid #e2e8f0" }}>
        <h5 style={{ margin: "0 0 8px", fontSize: "0.95rem", color: "#1e293b", fontWeight: 700 }}>
          JUnit Coverage Prompts
        </h5>
        <p style={{ margin: "0 0 12px", fontSize: "0.825rem", color: "#64748b" }}>
          Select one or more predefined prompts below to guide dynamic JUnit coverage targets:
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {predefinedPrompts.map((p) => {
            const isChecked = selectedPredefinedPrompts.includes(p.id);
            return (
              <div
                key={p.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  borderRadius: "6px",
                  border: isChecked ? "1px solid #2563eb" : "1px solid #e2e8f0",
                  backgroundColor: isChecked ? "#eff6ff" : "#f8fafc",
                  transition: "all 0.15s ease-in-out"
                }}
              >
                <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer", flex: 1, fontWeight: isChecked ? 600 : 500, color: "#1e293b", fontSize: "0.88rem" }}>
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => handleTogglePredefinedPrompt(p.id)}
                    style={{ width: "16px", height: "16px", accentColor: "#2563eb", cursor: "pointer" }}
                  />
                  <span>{p.title}</span>
                </label>

                <button
                  type="button"
                  onClick={() => setActiveModalPrompt(p)}
                  title="View Description"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    background: "transparent",
                    border: "1px solid #cbd5e1",
                    borderRadius: "4px",
                    padding: "4px 8px",
                    fontSize: "0.78rem",
                    color: "#2563eb",
                    cursor: "pointer",
                    fontWeight: 600
                  }}
                >
                  <FaEye style={{ color: "#2563eb" }} />
                  <span>[Eye]</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* SECTION 2: MANUAL USER PROMPT TEXTAREA */}
      <div style={{ marginBottom: "12px" }}>
        <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 600, color: "#1e293b", marginBottom: "6px" }}>
          Manual User Prompt (Optional)
        </label>
        <textarea
          className="input-modern"
          rows={3}
          value={currentPrompt}
          onChange={(e) => handlePromptChange(e.target.value)}
          placeholder="Enter custom testing requirements (e.g. Focus additional testing on authentication, repository and connection-related functionality)..."
          style={{ width: "100%", padding: "12px", borderRadius: "6px", fontSize: "0.9rem", border: "1px solid #cbd5e1", backgroundColor: "#ffffff" }}
        />
      </div>

      {/* Test Coverage Increment Card */}
      {(() => {
        const count = selectedPredefinedPrompts.length;
        const hasManual = Boolean(currentPrompt && currentPrompt.trim());
        const hasComp = selectedPredefinedPrompts.includes("comprehensive_junit_coverage");
        const hasBiz = selectedPredefinedPrompts.includes("business_logic_functional_paths");
        const hasBranch = selectedPredefinedPrompts.includes("branch_condition_edge_case");
        const hasExc = selectedPredefinedPrompts.includes("exception_negative_scenario");
        const hasJacoco = selectedPredefinedPrompts.includes("jacoco_dynamic_coverage_gap");

        let targetText = "80% Baseline Target Coverage";
        let description = "Default baseline JUnit testing configuration will generate standard unit test cases across repository classes.";

        if (count >= 3 || (hasComp && count >= 2) || (count >= 2 && hasJacoco)) {
          targetText = "90% - 95% Maximum Target Coverage (+30% Increment)";
          description = "Multiple selected prompts will execute comprehensive repository analysis, targeting core business services, branch conditions, exception handlers, and JaCoCo coverage gaps for maximum code coverage.";
        } else if (hasComp || count >= 2) {
          targetText = "85% - 90%+ Target Coverage (+25% Increment)";
          description = "Selected prompts will generate multi-scenario JUnit test cases targeting repository services, controllers, and edge cases to achieve 85-90%+ code coverage.";
        } else if (hasJacoco) {
          targetText = "85% - 88% Target Coverage (+20% Increment)";
          description = "JaCoCo Dynamic Coverage Gap prompt targets uncovered execution lines and missed branch conditions across the repository.";
        } else if (hasBiz) {
          targetText = "82% - 85% Target Coverage (+15% Increment)";
          description = "Business Logic & Functional Paths prompt targets core service execution, domain calculation rules, and primary application workflows.";
        } else if (hasBranch) {
          targetText = "82% - 85% Target Coverage (+15% Increment)";
          description = "Branch, Condition & Edge-Case prompt targets validator rules, decision logic, loop boundaries, and edge-case input variations.";
        } else if (hasExc) {
          targetText = "82% - 85% Target Coverage (+15% Increment)";
          description = "Exception & Negative Scenario prompt targets error handlers, validation rejections, security checks, and null pointer protection.";
        } else if (hasManual) {
          targetText = "80% - 85% Target Coverage (+15% Custom Increment)";
          description = "Custom manual prompt guidance will isolate specific repository classes and target scenarios matching your custom requirements.";
        }

        return (
          <div style={{ marginTop: "16px", padding: "16px 20px", borderRadius: "10px", background: "#f0fdf4", border: "1px solid #86efac", boxShadow: "0 2px 6px rgba(16, 185, 129, 0.05)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px", flexWrap: "wrap", gap: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#166534", fontWeight: 700, fontSize: "0.95rem" }}>
                <FaCheckCircle style={{ color: "#16a34a" }} />
                Expected JUnit Test Coverage Target
              </div>
              <span style={{ background: "#dcfce7", color: "#15803d", border: "1px solid #86efac", padding: "4px 12px", borderRadius: "14px", fontSize: "0.82rem", fontWeight: 700, transition: "all 0.2s ease" }}>
                {targetText}
              </span>
            </div>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "#15803d", lineHeight: 1.5 }}>
              {description}
            </p>
          </div>
        );
      })()}

      {/* PROMPT DESCRIPTION MODAL */}
      {activeModalPrompt && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(15, 23, 42, 0.6)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 9999,
            padding: "20px"
          }}
          onClick={() => setActiveModalPrompt(null)}
        >
          <div
            style={{
              backgroundColor: "#ffffff",
              borderRadius: "10px",
              maxWidth: "520px",
              width: "100%",
              padding: "24px",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
              border: "1px solid #cbd5e1"
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
              <h4 style={{ margin: 0, fontSize: "1.1rem", color: "#2563eb", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px" }}>
                <FaFlask style={{ color: "#2563eb" }} />
                {activeModalPrompt.title}
              </h4>
              <button
                type="button"
                onClick={() => setActiveModalPrompt(null)}
                style={{ background: "none", border: "none", fontSize: "1.2rem", cursor: "pointer", color: "#64748b" }}
              >
                ✕
              </button>
            </div>

            <div style={{ marginBottom: "16px", padding: "12px", backgroundColor: "#f8fafc", borderRadius: "6px", borderLeft: "4px solid #2563eb" }}>
              <strong style={{ display: "block", fontSize: "0.85rem", color: "#1e293b", marginBottom: "4px" }}>Description:</strong>
              <p style={{ margin: 0, fontSize: "0.875rem", color: "#475569", lineHeight: 1.5 }}>
                {activeModalPrompt.description}
              </p>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setActiveModalPrompt(null)}
                style={{
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  padding: "8px 18px",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  cursor: "pointer"
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

  return (
    <div className="admin-content-stacked">
      {enabledChecks.map((check: any, index: number) => {
        const visibleFields = Array.isArray(check.fields) ? check.fields.filter((f: any) => f.visible) : [];
        const isUnitTestCheck = (check.id || "").toLowerCase().includes("unit") || 
                              (check.name || "").toLowerCase().includes("unit") || 
                              (check.name || "").toLowerCase().includes("test");

        return (
          <div key={check.id || index} className="user-config-card">
            <h3 className="card-heading-modern">
              <FaShieldAlt style={{ color: "#2563eb" }} />
              {check.name}
            </h3>
            {check.description && (
              <p style={{ color: "#64748b", fontSize: "0.875rem", marginBottom: "16px" }}>
                {check.description}
              </p>
            )}

            {visibleFields.length === 0 ? (
              <p style={{ color: "#64748b", fontSize: "0.875rem" }}>
                No configuration fields required for this check.
              </p>
            ) : (
              <div className="field-grid-three">
                {visibleFields.map((field: any) => {
                  const isSecret = field.id.toLowerCase().includes("token") || 
                                   field.id.toLowerCase().includes("key") || 
                                   field.id.toLowerCase().includes("secret") ||
                                   field.id.toLowerCase().includes("password");

                  const value = settings?.quality_checks_values?.[field.id] !== undefined 
                                  ? settings.quality_checks_values[field.id] 
                                  : (field.defaultValue || "");

                  return (
                    <div className="field-modern" key={field.id}>
                      <label className="label-modern">
                        {field.name}
                        {field.required && <span style={{ color: "#ef4444", marginLeft: "4px" }}>*</span>}
                      </label>
                      
                      {isSecret ? (
                        <div className="input-wrap-modern">
                          <input
                            type={showSecrets[field.id] ? "text" : "password"}
                            className="input-modern"
                            value={value}
                            onChange={(e) => handleValueChange(field.id, e.target.value)}
                            placeholder={field.required ? "Required" : "Optional"}
                          />
                          <div
                            className="toggle-modern"
                            onClick={() => toggleSecret(field.id)}
                          >
                            {showSecrets[field.id] ? <FaEyeSlash /> : <FaEye />}
                          </div>
                        </div>
                      ) : (
                        <input
                          type="text"
                          className="input-modern"
                          value={value}
                          onChange={(e) => handleValueChange(field.id, e.target.value)}
                          placeholder={field.required ? "Required" : "Optional"}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {isUnitTestCheck && renderPromptSection()}
          </div>
        );
      })}

      {!hasUnitTestCheckInConfig && (
        <div className="user-config-card">
          <h3 className="card-heading-modern">
            <FaShieldAlt style={{ color: "#2563eb" }} />
            Run Unit Test Suite (JUnit)
          </h3>
          {renderPromptSection()}
        </div>
      )}
    </div>
  );
}
