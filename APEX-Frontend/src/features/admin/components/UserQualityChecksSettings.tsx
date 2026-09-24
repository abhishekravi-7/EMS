import React, { useState, useEffect } from "react";
import { FaShieldAlt, FaEye, FaEyeSlash, FaFlask, FaSpinner, FaLightbulb, FaCheckCircle } from "react-icons/fa";
import { getQualityChecksAdminConfig, analyzeTestingPrompt, type FullUserSettings, type TestingPromptAnalysisResult } from "../services/adminService";

const TEST_SCENARIO_SUGGESTIONS = [
  {
    id: "happy-path",
    label: "Happy Path Testing",
    prompt: "Generate positive end-to-end scenarios covering the main business workflows of the application. Verify that valid user inputs result in the expected outcomes."
  },
  {
    id: "negative-testing",
    label: "Negative & Validation Testing",
    prompt: "Generate negative test scenarios by providing invalid, missing, or unexpected inputs. Verify that the application displays appropriate validation messages and handles errors correctly."
  },
  {
    id: "edge-case",
    label: "Edge Case Testing",
    prompt: "Generate edge-case scenarios for boundary values, empty inputs, maximum and minimum values, unusual combinations of inputs, and other conditions that could expose unexpected application behavior."
  },
  {
    id: "role-permission",
    label: "Role & Permission Testing",
    prompt: "Generate functional test scenarios for different user roles and permissions. Verify that each role can access only the features and actions they are authorized to use, and that unauthorized operations are properly restricted."
  },
  {
    id: "e2e-workflow",
    label: "End-to-End Workflow Testing",
    prompt: "Generate complete end-to-end functional test scenarios that follow realistic business workflows across multiple pages or features. Validate the data and expected outcome at each important step."
  }
];

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

  const currentPrompt = settings.quality_checks_values?.testing_prompt || settings.test_cases_values?.testing_prompt || "";

  const [analyzingPrompt, setAnalyzingPrompt] = useState(false);
  const [promptAnalysis, setPromptAnalysis] = useState<TestingPromptAnalysisResult | null>(null);
  const [promptAnalysisErr, setPromptAnalysisErr] = useState<string | null>(null);

  const handlePromptChange = (val: string) => {
    onChange((prev) => ({
      ...prev,
      quality_checks_values: {
        ...(prev.quality_checks_values || {}),
        testing_prompt: val,
      },
      test_cases_values: {
        ...(prev.test_cases_values || {}),
        testing_prompt: val,
      },
    }));
    setPromptAnalysis(null);
  };

  const handleAnalyzePrompt = async (promptOverride?: string) => {
    const targetPrompt = (typeof promptOverride === "string" ? promptOverride : currentPrompt).trim();
    if (!targetPrompt) {
      alert("Please enter a testing focus prompt first.");
      return;
    }

    setAnalyzingPrompt(true);
    setPromptAnalysis(null);
    setPromptAnalysisErr(null);
    try {
      const res = await analyzeTestingPrompt(targetPrompt);
      setPromptAnalysis(res);
      onChange((prev) => ({
        ...prev,
        quality_checks_values: {
          ...(prev.quality_checks_values || {}),
          testing_prompt: targetPrompt,
        },
        test_cases_values: {
          ...(prev.test_cases_values || {}),
          testing_prompt: targetPrompt,
        },
      }));
    } catch (err: any) {
      setPromptAnalysisErr(err.message || "Failed to analyze prompt.");
    } finally {
      setAnalyzingPrompt(false);
    }
  };

  const currentFunctionalCustomPrompt = settings.quality_checks_values?.functional_custom_prompt || "";
  const selectedFunctionalSuggestions = settings.quality_checks_values?.functional_testing_suggestions ?? TEST_SCENARIO_SUGGESTIONS.map(s => s.id);

  const [analyzingFunctionalPrompt, setAnalyzingFunctionalPrompt] = useState(false);
  const [functionalPromptAnalysis, setFunctionalPromptAnalysis] = useState<TestingPromptAnalysisResult | null>(null);
  const [functionalPromptAnalysisErr, setFunctionalPromptAnalysisErr] = useState<string | null>(null);

  const handleFunctionalCustomPromptChange = (val: string) => {
    onChange((prev) => ({
      ...prev,
      quality_checks_values: {
        ...(prev.quality_checks_values || {}),
        functional_custom_prompt: val,
      },
    }));
    setFunctionalPromptAnalysis(null);
  };

  const handleSuggestionToggle = (id: string, checked: boolean) => {
    const newSelection = checked 
      ? [...selectedFunctionalSuggestions, id] 
      : selectedFunctionalSuggestions.filter((sid: string) => sid !== id);
    
    onChange((prev) => ({
      ...prev,
      quality_checks_values: {
        ...(prev.quality_checks_values || {}),
        functional_testing_suggestions: newSelection,
      },
    }));
    setFunctionalPromptAnalysis(null);
  };

  const getCombinedFunctionalPrompt = () => {
    const suggestionPrompts = TEST_SCENARIO_SUGGESTIONS
      .filter(s => selectedFunctionalSuggestions.includes(s.id))
      .map(s => s.prompt);
    
    let combined = suggestionPrompts.join("\n\n");
    if (currentFunctionalCustomPrompt.trim()) {
      combined += (combined ? "\n\n" : "") + currentFunctionalCustomPrompt.trim();
    }
    return combined;
  };

  const handleAnalyzeFunctionalPrompt = async () => {
    const targetPrompt = getCombinedFunctionalPrompt();
    if (!targetPrompt) {
      alert("Please select at least one suggestion or enter a custom prompt.");
      return;
    }

    setAnalyzingFunctionalPrompt(true);
    setFunctionalPromptAnalysis(null);
    setFunctionalPromptAnalysisErr(null);
    try {
      const res = await analyzeTestingPrompt(targetPrompt);
      setFunctionalPromptAnalysis(res);
      onChange((prev) => ({
        ...prev,
        quality_checks_values: {
          ...(prev.quality_checks_values || {}),
          functional_testing_prompt: targetPrompt, // Final combined prompt sent downstream
        },
      }));
    } catch (err: any) {
      setFunctionalPromptAnalysisErr(err.message || "Failed to analyze prompt.");
    } finally {
      setAnalyzingFunctionalPrompt(false);
    }
  };

  useEffect(() => {
    if (currentPrompt.trim() && !promptAnalysis && !analyzingPrompt) {
      analyzeTestingPrompt(currentPrompt.trim())
        .then((res) => setPromptAnalysis(res))
        .catch(() => {});
    }
  }, [currentPrompt]);

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
      const newValues = { ...(settings.quality_checks_values || {}) };

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
  }, [isLoading, adminConfig, settings.quality_checks_values, onChange]);

  const handleValueChange = (id: string, value: string) => {
    onChange((prev) => ({
      ...prev,
      quality_checks_values: {
        ...(prev.quality_checks_values || {}),
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

  const renderFunctionalPromptSection = () => {
    const hasAnyPrompt = selectedFunctionalSuggestions.length > 0 || currentFunctionalCustomPrompt.trim();
    return (
    <div style={{ marginTop: "20px", padding: "20px", borderRadius: "8px", border: "1px solid #cbd5e1", backgroundColor: "#f8fafc" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <h4 style={{ margin: 0, fontSize: "1.05rem", color: "#1e293b", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
          <FaFlask style={{ color: "#2563eb" }} />
          Functional Testing Custom Prompt Suggestions
        </h4>
        <span style={{
          padding: "4px 12px",
          borderRadius: "20px",
          fontSize: "0.75rem",
          fontWeight: 700,
          backgroundColor: hasAnyPrompt ? "#dcfce7" : "#f1f5f9",
          color: hasAnyPrompt ? "#166534" : "#64748b",
          border: `1px solid ${hasAnyPrompt ? "#86efac" : "#cbd5e1"}`
        }}>
          {hasAnyPrompt ? "✓ ACTIVE & CONFIGURED" : "STANDARD SUITE (NO PROMPT)"}
        </span>
      </div>

      <div style={{ marginBottom: "16px" }}>
        <h5 style={{ margin: "0 0 8px", fontSize: "0.9rem", color: "#1e293b" }}>Suggested Test Scenarios</h5>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {TEST_SCENARIO_SUGGESTIONS.map(suggestion => (
            <label key={suggestion.id} style={{ display: "flex", alignItems: "flex-start", gap: "8px", fontSize: "0.85rem", color: "#475569", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={selectedFunctionalSuggestions.includes(suggestion.id)}
                onChange={(e) => handleSuggestionToggle(suggestion.id, e.target.checked)}
                style={{ marginTop: "3px" }}
              />
              <span style={{ display: "flex", flexDirection: "column" }}>
                <strong style={{ color: "#1e293b" }}>{suggestion.label}</strong>
                <span style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "2px" }}>{suggestion.prompt}</span>
              </span>
            </label>
          ))}
        </div>
      </div>

      <p style={{ margin: "0 0 8px", fontSize: "0.9rem", color: "#1e293b", fontWeight: 600 }}>
        Custom Prompt (Optional)
      </p>

      <textarea
        className="input-modern"
        rows={3}
        value={currentFunctionalCustomPrompt}
        onChange={(e) => handleFunctionalCustomPromptChange(e.target.value)}
        placeholder="Add any additional areas or scenarios to cover (e.g., Focus mainly on user checkout flows, payment processing)..."
        style={{ width: "100%", padding: "12px", borderRadius: "6px", fontSize: "0.9rem", border: "1px solid #cbd5e1", backgroundColor: "#ffffff" }}
      />

      <div style={{ marginTop: "12px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <span style={{ fontSize: "0.8rem", color: "#64748b", fontStyle: "italic" }}>
          The selected suggestions and your custom prompt will be combined to generate functional tests.
        </span>

        <button
          className="back-btn-modern"
          onClick={() => handleAnalyzeFunctionalPrompt()}
          disabled={analyzingFunctionalPrompt || !hasAnyPrompt}
          type="button"
          style={{ display: "flex", alignItems: "center", gap: "8px", background: "#2563eb", color: "#ffffff", border: "none", padding: "8px 16px", borderRadius: "6px", fontWeight: 600, cursor: "pointer" }}
        >
          {analyzingFunctionalPrompt ? <FaSpinner className="animate-spin" /> : <FaLightbulb />}
          Generate Functional Tests
        </button>
      </div>

      {functionalPromptAnalysisErr && (
        <div style={{ marginTop: "12px", padding: "12px", borderRadius: "6px", background: "#fef2f2", border: "1px solid #fca5a5", color: "#991b1b", fontSize: "0.85rem" }}>
          {functionalPromptAnalysisErr}
        </div>
      )}

      {functionalPromptAnalysis && (
        <div style={{ marginTop: "16px", padding: "16px", borderRadius: "8px", background: "#f0fdf4", border: "1px solid #86efac" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px", color: "#166534", fontWeight: 700, fontSize: "0.9rem" }}>
            <FaCheckCircle style={{ color: "#16a34a" }} />
            LLM Dynamic Analysis Result (Configured Focus)
          </div>
          <p style={{ margin: "0 0 8px", fontSize: "0.85rem", color: "#15803d", fontWeight: 600 }}>
            Focus Identified: {functionalPromptAnalysis.testing_focus}
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", fontSize: "0.8rem", color: "#1e293b" }}>
            <div>
              <strong>Target Areas / Endpoints:</strong> {(functionalPromptAnalysis.target_areas && functionalPromptAnalysis.target_areas.length > 0 && functionalPromptAnalysis.target_areas[0] !== "Requested Focus") ? functionalPromptAnalysis.target_areas.join(", ") : (functionalPromptAnalysis.target_classes?.join(", ") || "API Endpoints, UI Workflows")}
            </div>
            <div>
              <strong>Priority Scenarios:</strong> {functionalPromptAnalysis.scenarios?.join(", ") || "Standard"}
            </div>
          </div>
          {functionalPromptAnalysis.edge_cases?.length > 0 && (
            <div style={{ marginTop: "6px", fontSize: "0.8rem", color: "#1e293b" }}>
              <strong>Edge Cases:</strong> {functionalPromptAnalysis.edge_cases.join(", ")}
            </div>
          )}
          <div style={{ marginTop: "8px", fontSize: "0.75rem", color: "#15803d", fontStyle: "italic", borderTop: "1px stroke #86efac", paddingTop: "6px" }}>
            ✓ Verified: When you start migration, Functional test generation will automatically prioritize these scenarios.
          </div>
        </div>
      )}
    </div>
    );
  };

  const renderPromptSection = () => (
    <div style={{ marginTop: "20px", padding: "20px", borderRadius: "8px", border: "1px solid #cbd5e1", backgroundColor: "#f8fafc" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <h4 style={{ margin: 0, fontSize: "1.05rem", color: "#1e293b", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
          <FaFlask style={{ color: "#2563eb" }} />
          Run Unit Test Suite Focus Prompt (JUnit)
        </h4>
        <span style={{
          padding: "4px 12px",
          borderRadius: "20px",
          fontSize: "0.75rem",
          fontWeight: 700,
          backgroundColor: currentPrompt.trim() ? "#dcfce7" : "#f1f5f9",
          color: currentPrompt.trim() ? "#166534" : "#64748b",
          border: `1px solid ${currentPrompt.trim() ? "#86efac" : "#cbd5e1"}`
        }}>
          {currentPrompt.trim() ? "✓ ACTIVE & CONFIGURED" : "STANDARD SUITE (NO PROMPT)"}
        </span>
      </div>

      <p style={{ margin: "0 0 12px", fontSize: "0.875rem", color: "#64748b" }}>
        Describe what areas, components, or scenarios should receive focused testing coverage during JUnit test generation & execution.
      </p>

      <textarea
        className="input-modern"
        rows={3}
        value={currentPrompt}
        onChange={(e) => handlePromptChange(e.target.value)}
        placeholder="Describe what areas or scenarios should receive more testing coverage (e.g., Focus mainly on login functionality and invalid credentials, password validation, and error handling)..."
        style={{ width: "100%", padding: "12px", borderRadius: "6px", fontSize: "0.9rem", border: "1px solid #cbd5e1", backgroundColor: "#ffffff" }}
      />

      <div style={{ marginTop: "12px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <span style={{ fontSize: "0.8rem", color: "#64748b", fontStyle: "italic" }}>
          The LLM dynamically determines target classes, priority scenarios, and edge cases from your prompt.
        </span>

        <button
          className="back-btn-modern"
          onClick={handleAnalyzePrompt}
          disabled={analyzingPrompt || !currentPrompt.trim()}
          type="button"
          style={{ display: "flex", alignItems: "center", gap: "8px", background: "#2563eb", color: "#ffffff", border: "none", padding: "8px 16px", borderRadius: "6px", fontWeight: 600, cursor: "pointer" }}
        >
          {analyzingPrompt ? <FaSpinner className="animate-spin" /> : <FaLightbulb />}
          Analyze & Preview Focus
        </button>
      </div>

      {promptAnalysisErr && (
        <div style={{ marginTop: "12px", padding: "12px", borderRadius: "6px", background: "#fef2f2", border: "1px solid #fca5a5", color: "#991b1b", fontSize: "0.85rem" }}>
          {promptAnalysisErr}
        </div>
      )}

      {promptAnalysis && (
        <div style={{ marginTop: "16px", padding: "16px", borderRadius: "8px", background: "#f0fdf4", border: "1px solid #86efac" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px", color: "#166534", fontWeight: 700, fontSize: "0.9rem" }}>
            <FaCheckCircle style={{ color: "#16a34a" }} />
            LLM Dynamic Analysis Result (Configured Focus)
          </div>
          <p style={{ margin: "0 0 8px", fontSize: "0.85rem", color: "#15803d", fontWeight: 600 }}>
            Focus Identified: {promptAnalysis.testing_focus}
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", fontSize: "0.8rem", color: "#1e293b" }}>
            <div>
              <strong>Target Areas / Classes:</strong> {(promptAnalysis.target_areas && promptAnalysis.target_areas.length > 0 && promptAnalysis.target_areas[0] !== "Requested Focus") ? promptAnalysis.target_areas.join(", ") : (promptAnalysis.target_classes?.join(", ") || "AuthService, AuthenticationController")}
            </div>
            <div>
              <strong>Priority Scenarios:</strong> {promptAnalysis.scenarios?.join(", ") || "Standard"}
            </div>
          </div>
          {promptAnalysis.edge_cases?.length > 0 && (
            <div style={{ marginTop: "6px", fontSize: "0.8rem", color: "#1e293b" }}>
              <strong>Edge Cases:</strong> {promptAnalysis.edge_cases.join(", ")}
            </div>
          )}
          <div style={{ marginTop: "8px", fontSize: "0.75rem", color: "#15803d", fontStyle: "italic", borderTop: "1px stroke #86efac", paddingTop: "6px" }}>
            ✓ Verified: When you start migration, JUnit test generation will automatically prioritize these scenarios.
          </div>
        </div>
      )}
    </div>
  );

  let renderedPromptInCheck = false;
  let renderedFunctionalPromptInCheck = false;

  return (
    <div className="admin-content-stacked">
      {enabledChecks.map((check: any, index: number) => {
        const visibleFields = Array.isArray(check.fields) ? check.fields.filter((f: any) => f.visible) : [];
        const isUnitTestCheck = (check.id || "").toLowerCase().includes("unit") || 
                              (check.name || "").toLowerCase().includes("unit") || 
                              ((check.name || "").toLowerCase().includes("test") && !(check.name || "").toLowerCase().includes("functional"));
        const isFunctionalTestCheck = (check.id || "").toLowerCase().includes("functional") || 
                                      (check.name || "").toLowerCase().includes("functional");

        if (isUnitTestCheck) {
          renderedPromptInCheck = true;
        }
        if (isFunctionalTestCheck) {
          renderedFunctionalPromptInCheck = true;
        }

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

                  const value = settings.quality_checks_values?.[field.id] !== undefined 
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
            {isFunctionalTestCheck && renderFunctionalPromptSection()}
          </div>
        );
      })}

      {!renderedPromptInCheck && (
        <div className="user-config-card">
          <h3 className="card-heading-modern">
            <FaShieldAlt style={{ color: "#2563eb" }} />
            Run Unit Test Suite (JUnit)
          </h3>
          {renderPromptSection()}
        </div>
      )}
      
      {!renderedFunctionalPromptInCheck && (
        <div className="user-config-card">
          <h3 className="card-heading-modern">
            <FaShieldAlt style={{ color: "#2563eb" }} />
            Functional Testing
          </h3>
          {renderFunctionalPromptSection()}
        </div>
      )}
    </div>
  );
}

