/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, react-hooks/exhaustive-deps */
import React, { useState, useEffect } from "react";
import { FaShieldAlt, FaEye, FaEyeSlash, FaFlask, FaSpinner, FaLightbulb, FaCheckCircle } from "react-icons/fa";
import { getQualityChecksAdminConfig, analyzeTestingPrompt, testUserPlaywrightConnection, type FullUserSettings, type TestingPromptAnalysisResult } from "../services/adminService";

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
  mode?: "all" | "testing_only";
}

const JUNIT_PREDEFINED_PROMPTS = [
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
  ];

export default function UserQualityChecksSettings({
  settings: rawSettings,
  onChange,
  mode = "all"
}: UserQualityChecksSettingsProps) {
  const settings = rawSettings || ({
    github_config: {},
    quality_checks_values: {},
    test_cases_values: {},
    llm_values: {},
  } as any);

  const [adminConfig, setAdminConfig] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSecrets, setShowSecrets] = useState<{ [key: string]: boolean }>({});

  const currentPrompt = settings?.test_cases_values?.testing_prompt ?? settings?.quality_checks_values?.testing_prompt ?? "";

  const [analyzingPrompt, setAnalyzingPrompt] = useState(false);
  const [promptAnalysis, setPromptAnalysis] = useState<TestingPromptAnalysisResult | null>(null);
  const [promptAnalysisErr, setPromptAnalysisErr] = useState<string | null>(null);

  const selectedPredefinedPrompts: string[] =
    settings?.test_cases_values?.selected_predefined_prompts ??
    settings?.quality_checks_values?.selected_predefined_prompts ??
    JUNIT_PREDEFINED_PROMPTS.map(p => p.id);

  const [activeModalPrompt, setActiveModalPrompt] = useState<any | null>(null);

  const [testingPlaywright, setTestingPlaywright] = useState(false);
  const [playwrightStatusMsg, setPlaywrightStatusMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleTestPlaywrightConnection = async () => {
    const url = (settings?.test_cases_values?.playwright_base_url || "").trim();
    if (!url) {
      setPlaywrightStatusMsg({
        type: "error",
        text: "Please enter an Application Base URL before testing connection."
      });
      return;
    }
    setTestingPlaywright(true);
    setPlaywrightStatusMsg(null);
    try {
      const res = await testUserPlaywrightConnection(url);
      setPlaywrightStatusMsg({ type: "success", text: res.message || "Playwright test connection successful" });
    } catch (err: any) {
      setPlaywrightStatusMsg({
        type: "error",
        text: err.message || "Failed to reach Application Base URL. Ensure your target web application server is running and accessible."
      });
    } finally {
      setTestingPlaywright(false);
    }
  };

  const handleTogglePredefinedPrompt = (promptId: string) => {
    const currentSelected: string[] =
      settings?.test_cases_values?.selected_predefined_prompts ??
      settings?.quality_checks_values?.selected_predefined_prompts ??
      JUNIT_PREDEFINED_PROMPTS.map(p => p.id);
    const nextSelected = currentSelected.includes(promptId)
      ? currentSelected.filter((id) => id !== promptId)
      : [...currentSelected, promptId];

    onChange((prev) => {
      const updatedQc = { ...(prev?.quality_checks_values || {}) };
      delete updatedQc.selected_predefined_prompts;
      delete updatedQc.selectedPredefinedPrompts;

      return {
        ...prev,
        quality_checks_values: updatedQc,
        test_cases_values: {
          ...(prev?.test_cases_values || {}),
          selected_predefined_prompts: nextSelected,
        },
      };
    });
    setPromptAnalysis(null);
  };

  const handlePromptChange = (val: string) => {
    onChange((prev) => {
      const updatedQc = { ...(prev?.quality_checks_values || {}) };
      delete updatedQc.testing_prompt;
      delete updatedQc.testingPrompt;
      delete updatedQc.junit_prompt;
      delete updatedQc.junitPrompt;

      return {
        ...prev,
        quality_checks_values: updatedQc,
        test_cases_values: {
          ...(prev?.test_cases_values || {}),
          testing_prompt: val,
        },
      };
    });
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

  const currentFunctionalCustomPrompt = settings?.quality_checks_values?.functional_custom_prompt || "";
  const selectedFunctionalSuggestions = settings?.quality_checks_values?.functional_testing_suggestions ?? TEST_SCENARIO_SUGGESTIONS.map(s => s.id);

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

  const renderFunctionalPromptSection = () => {
    const hasAnyPrompt = selectedFunctionalSuggestions.length > 0 || currentFunctionalCustomPrompt.trim().length > 0;
    return (
      <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "16px" }}>
        {/* PREDEFINED FUNCTIONAL PROMPTS CHECKBOXES */}
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
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

        {/* MANUAL USER PROMPT TEXTAREA */}
        <div>
          <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 600, color: "#1e293b", marginBottom: "6px" }}>
            Custom Prompt (Optional)
          </label>
          <textarea
            className="input-modern"
            rows={3}
            value={currentFunctionalCustomPrompt}
            onChange={(e) => handleFunctionalCustomPromptChange(e.target.value)}
            placeholder="Add any additional areas or scenarios to cover (e.g., Focus mainly on user checkout flows, payment processing)..."
            style={{ width: "100%", padding: "12px", borderRadius: "6px", fontSize: "0.9rem", border: "1px solid #cbd5e1", backgroundColor: "#ffffff" }}
          />
        </div>

        <div style={{ marginTop: "4px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
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
          <div style={{ padding: "12px", borderRadius: "6px", background: "#fef2f2", border: "1px solid #fca5a5", color: "#991b1b", fontSize: "0.85rem" }}>
            {functionalPromptAnalysisErr}
          </div>
        )}
      </div>
    );
  };

  const renderPromptSection = () => (
    <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* PREDEFINED JUNIT PROMPTS CHECKBOXES */}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {JUNIT_PREDEFINED_PROMPTS.map(p => (
          <label key={p.id} style={{ display: "flex", alignItems: "flex-start", gap: "8px", fontSize: "0.85rem", color: "#475569", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={selectedPredefinedPrompts.includes(p.id)}
              onChange={() => handleTogglePredefinedPrompt(p.id)}
              style={{ marginTop: "3px" }}
            />
            <span style={{ display: "flex", flexDirection: "column" }}>
              <strong style={{ color: "#1e293b" }}>{p.title}</strong>
              <span style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "2px" }}>{p.description}</span>
            </span>
          </label>
        ))}
      </div>

      {/* MANUAL USER PROMPT TEXTAREA */}
      <div>
        <label style={{ display: "block", fontSize: "0.875rem", fontWeight: 600, color: "#1e293b", marginBottom: "6px" }}>
          Custom Prompt (Optional)
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

      <div style={{ marginTop: "4px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <span style={{ fontSize: "0.8rem", color: "#64748b", fontStyle: "italic" }}>
          The selected suggestions and your custom prompt will be combined to generate JUnit tests.
        </span>

        <button
          className="back-btn-modern"
          onClick={() => handleAnalyzePrompt()}
          disabled={analyzingPrompt || !hasAnyActivePrompt}
          type="button"
          style={{ display: "flex", alignItems: "center", gap: "8px", background: "#2563eb", color: "#ffffff", border: "none", padding: "8px 16px", borderRadius: "6px", fontWeight: 600, cursor: "pointer" }}
        >
          {analyzingPrompt ? <FaSpinner className="animate-spin" /> : <FaLightbulb />}
          Generate JUnit Tests
        </button>
      </div>

      {promptAnalysisErr && (
        <div style={{ padding: "12px", borderRadius: "6px", background: "#fef2f2", border: "1px solid #fca5a5", color: "#991b1b", fontSize: "0.85rem" }}>
          {promptAnalysisErr}
        </div>
      )}

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



  let renderedFunctionalPromptInCheck = false;

  if (mode === "testing_only") {
    return (
      <div className="grid-2">
        <div className="settings-toggle-card">
          <div className="settings-toggle-header" style={{ marginBottom: "16px" }}>
            <div className="settings-toggle-title">
              <FaShieldAlt style={{ color: "#2563eb", marginRight: "8px" }} />
              JUnit Unit Testing
            </div>
          </div>
          <p className="settings-toggle-desc" style={{ marginBottom: "16px" }}>Configure JUnit test focus, predefined coverage prompts, and custom instructions for AI test generation.</p>
          {renderPromptSection()}
        </div>
        
        <div className="settings-toggle-card">
          <div className="settings-toggle-header" style={{ marginBottom: "16px" }}>
            <div className="settings-toggle-title">
              <FaShieldAlt style={{ color: "#2563eb", marginRight: "8px" }} />
              Functional Testing
            </div>
          </div>
          <p className="settings-toggle-desc" style={{ marginBottom: "16px" }}>Configure functional testing focus, scenario suggestions, and custom instructions for automated test generation.</p>
          {renderFunctionalPromptSection()}
        </div>
      
        <div className="settings-toggle-card">
          <div className="settings-toggle-header" style={{ marginBottom: "16px" }}>
            <div className="settings-toggle-title">
              <FaFlask style={{ color: "#2563eb", marginRight: "8px" }} />
              Playwright E2E Testing
            </div>
          </div>
          <p className="settings-toggle-desc" style={{ marginBottom: "16px" }}>
            Configure Playwright end-to-end browser testing framework and target application base URL.
          </p>
          
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#1e293b", marginBottom: "6px" }}>
                APPLICATION BASE URL
              </label>
              <input
                type="text"
                className="input-modern"
                value={settings?.test_cases_values?.playwright_base_url || ""}
                onChange={(e) => {
                  const val = e.target.value;
                  onChange(prev => ({
                    ...prev,
                    test_cases_values: {
                      ...(prev.test_cases_values || {}),
                      playwright_base_url: val
                    }
                  }));
                }}
                placeholder="e.g. http://localhost:3000"
                style={{ width: "100%", padding: "10px", borderRadius: "6px", border: "1px solid #cbd5e1", backgroundColor: "#ffffff", fontSize: "0.9rem" }}
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <button
                type="button"
                className="back-btn-modern"
                disabled={testingPlaywright}
                onClick={handleTestPlaywrightConnection}
                style={{ display: "flex", alignItems: "center", gap: "8px", background: "#2563eb", color: "#ffffff", border: "none", padding: "8px 16px", borderRadius: "6px", fontWeight: 600, cursor: "pointer", fontSize: "0.85rem" }}
              >
                {testingPlaywright ? <FaSpinner className="animate-spin" /> : <FaFlask />}
                Test Connection
              </button>
            </div>

            {playwrightStatusMsg && (
              <div style={{
                padding: "10px 14px",
                borderRadius: "6px",
                fontSize: "0.85rem",
                background: playwrightStatusMsg.type === "success" ? "#f0fdf4" : "#fef2f2",
                border: `1px solid ${playwrightStatusMsg.type === "success" ? "#86efac" : "#fca5a5"}`,
                color: playwrightStatusMsg.type === "success" ? "#166534" : "#991b1b"
              }}>
                {playwrightStatusMsg.text}
              </div>
            )}
          </div>
        </div>
</div>
    );
  }

  return (
    <div className="admin-content-stacked">
      {enabledChecks.map((check: any, index: number) => {
        const visibleFields = Array.isArray(check.fields)
          ? check.fields.filter(
              (f: any) =>
                f.visible &&
                f.id !== "project_key" &&
                f.id !== "sonar_project_key" &&
                f.id !== "sonarqube_project_key"
            )
          : [];
        const isUnitTestCheck = (check.id || "").toLowerCase().includes("unit") || 
                              (check.name || "").toLowerCase().includes("unit") || 
                              ((check.name || "").toLowerCase().includes("test") && !(check.name || "").toLowerCase().includes("functional"));
        const isFunctionalTestCheck = (check.id || "").toLowerCase().includes("functional") || 
                                      (check.name || "").toLowerCase().includes("functional");

        if (isFunctionalTestCheck) {
          renderedFunctionalPromptInCheck = true;
        }

        return (
          <div key={check.id || index} className="user-config-card" style={{ marginBottom: "20px" }}>
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
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px", marginBottom: "12px" }}>
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
                      <label className="label-modern" style={{ display: "block", marginBottom: "6px", fontSize: "0.85rem", fontWeight: 600, color: "#1e293b" }}>
                        {field.name}
                        {field.required && <span style={{ color: "#ef4444", marginLeft: "4px" }}>*</span>}
                      </label>
                      
                      {isSecret ? (
                        <div className="input-wrap-modern" style={{ position: "relative", display: "flex", alignItems: "center" }}>
                          <input
                            type={showSecrets[field.id] ? "text" : "password"}
                            className="input-modern"
                            value={value}
                            onChange={(e) => handleValueChange(field.id, e.target.value)}
                            placeholder={field.required ? "Required" : "Optional"}
                            style={{ paddingRight: "40px", width: "100%", padding: "10px 12px", borderRadius: "6px", border: "1px solid #cbd5e1", backgroundColor: "#ffffff", fontSize: "0.9rem" }}
                          />
                          <button
                            type="button"
                            className="toggle-modern"
                            onClick={() => toggleSecret(field.id)}
                            style={{ position: "absolute", right: "12px", background: "none", border: "none", cursor: "pointer", color: "#64748b", display: "flex", alignItems: "center", padding: 0 }}
                            title={showSecrets[field.id] ? "Hide secret key" : "Show secret key"}
                          >
                            {showSecrets[field.id] ? <FaEyeSlash size={15} /> : <FaEye size={15} />}
                          </button>
                        </div>
                      ) : (
                        <input
                          type="text"
                          className="input-modern"
                          value={value}
                          onChange={(e) => handleValueChange(field.id, e.target.value)}
                          placeholder={field.required ? "Required" : "Optional"}
                          style={{ width: "100%", padding: "10px 12px", borderRadius: "6px", border: "1px solid #cbd5e1", backgroundColor: "#ffffff", fontSize: "0.9rem" }}
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

      {!hasUnitTestCheckInConfig && (
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

  
