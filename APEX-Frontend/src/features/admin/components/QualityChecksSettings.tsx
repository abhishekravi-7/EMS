import React, { useState, useEffect } from "react";
import { FaPlus, FaTrash } from "react-icons/fa";

interface FieldConfig {
  id: string;
  name: string;
  visible: boolean;
  required: boolean;
  defaultValue?: string;
}

interface QualityCheckConfig {
  name: string;
  description: string;
  enabled: boolean;
  required: boolean;
  execution_enabled: boolean;
  fields: FieldConfig[];
}

interface QualityChecksSettingsProps {
  configString: string;
  onChange: (newConfig: string) => void;
}

const DEFAULT_CONFIG: Record<string, QualityCheckConfig> = {
  SONARQUBE: {
    name: "SonarQube",
    description: "Static code analysis to detect bugs, code smells, and security vulnerabilities.",
    enabled: true,
    required: false,
    execution_enabled: true,
    fields: [
      { id: "sonarqube_url", name: "SonarQube URL", visible: true, required: true, defaultValue: "https://sonarcloud.io" },
      { id: "auth_token", name: "Authentication Token", visible: true, required: true },
      { id: "project_key", name: "Project Key", visible: true, required: false },
      { id: "sonar_organization", name: "Sonar Organisation", visible: true, required: false }
    ],
  },
  FOSSA: {
    name: "FOSSA",
    description: "Open source dependency management and license compliance scanning.",
    enabled: true,
    required: false,
    execution_enabled: true,
    fields: [
      { id: "fossa_api_key", name: "FOSSA API Key", visible: true, required: true },
      { id: "fossa_endpoint", name: "FOSSA Endpoint", visible: true, required: false }
    ],
  },
  RUN_UNIT_TEST_SUITE: {
    name: "Run Unit Test Suite",
    description: "Execute the project's internal unit test suite during migration.",
    enabled: true,
    required: false,
    execution_enabled: true,
    fields: [
      { id: "test_command", name: "Test Command / Configuration", visible: true, required: false },
    ],
  },
  FUNCTIONAL_TESTING: {
    name: "Functional Testing",
    description: "Generate and execute functional API and UI tests for the migrated application.",
    enabled: true,
    required: false,
    execution_enabled: true,
    fields: [
      { id: "functional_test_command", name: "Test Command / Configuration", visible: true, required: false },
    ],
  },
};

export default function QualityChecksSettings({ configString, onChange }: QualityChecksSettingsProps) {
  const [configs, setConfigs] = useState<Record<string, QualityCheckConfig>>(() => {
    try {
      if (configString) {
        const parsed = JSON.parse(configString);
        return { ...DEFAULT_CONFIG, ...parsed };
      }
    } catch (e) {
      console.error("Failed to parse quality checks config", e);
    }
    return DEFAULT_CONFIG;
  });

  useEffect(() => {
    try {
      if (configString) {
        const parsed = JSON.parse(configString);
        setConfigs({ ...DEFAULT_CONFIG, ...parsed });
      }
    } catch (e) {
      console.error("Failed to sync quality checks config", e);
    }
  }, [configString]);

  const updateConfig = (key: string, updates: Partial<QualityCheckConfig>) => {
    const currentCheck = configs[key] || DEFAULT_CONFIG[key] || { name: key, description: "", enabled: true, required: false, execution_enabled: true, fields: [] };
    const newConfigs = { ...configs, [key]: { ...currentCheck, ...updates } };
    setConfigs(newConfigs);
    onChange(JSON.stringify(newConfigs));
  };

  const updateField = (configKey: string, fieldIndex: number, updates: Partial<FieldConfig>) => {
    const check = configs[configKey];
    if (!check) return;
    const newFields = [...(check.fields || [])];
    if (newFields[fieldIndex]) {
      newFields[fieldIndex] = { ...newFields[fieldIndex], ...updates };
      updateConfig(configKey, { fields: newFields });
    }
  };

  const addField = (configKey: string) => {
    const check = configs[configKey] || { name: configKey, description: "", enabled: true, required: false, execution_enabled: true, fields: [] };
    const newFieldId = `custom_field_${Date.now()}`;
    const newFields = [...(check.fields || []), { id: newFieldId, name: "New Field", visible: true, required: false }];
    updateConfig(configKey, { fields: newFields });
  };

  const removeField = (configKey: string, fieldIndex: number) => {
    const check = configs[configKey];
    if (!check) return;
    const newFields = (check.fields || []).filter((_, i) => i !== fieldIndex);
    updateConfig(configKey, { fields: newFields });
  };

  const safeConfigs = configs || DEFAULT_CONFIG;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px", marginTop: "16px" }}>
      {Object.entries(safeConfigs).map(([key, check]) => {
        const isEnabled = Boolean(check?.enabled);
        const fieldsList = check?.fields || [];

        return (
          <div 
            key={key} 
            style={{ 
              border: "1px solid #e2e8f0", 
              borderRadius: "8px", 
              padding: "20px",
              background: "#ffffff",
              opacity: isEnabled ? 1 : 0.6,
              transition: "opacity 0.2s"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
              <div>
                <h4 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b", fontWeight: 600 }}>{check?.name || key}</h4>
                <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "#64748b" }}>{check?.description || ""}</p>
              </div>
              <div className="switch-row-modern" style={{ marginTop: 0 }}>
                <label className="switch-modern">
                  <input
                    type="checkbox"
                    checked={isEnabled}
                    onChange={(e) => updateConfig(key, { enabled: e.target.checked })}
                  />
                  <span className="slider-modern"></span>
                </label>
                <span className="switch-label-modern" style={{ minWidth: "100px" }}>
                  {isEnabled ? "Enabled" : "Disabled"}
                </span>
              </div>
            </div>

            <div style={{ pointerEvents: isEnabled ? "auto" : "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", borderBottom: "1px solid #e2e8f0", paddingBottom: "8px" }}>
                <h5 style={{ margin: 0, fontSize: "0.95rem", color: "#334155" }}>User Configuration Fields</h5>
                <button 
                  className="back-btn-modern" 
                  onClick={() => addField(key)}
                  style={{ padding: "4px 8px", fontSize: "0.8rem", height: "auto" }}
                  disabled={!isEnabled}
                >
                  <FaPlus style={{ fontSize: "10px" }} />
                  <span>Add Field</span>
                </button>
              </div>

              {fieldsList.length === 0 ? (
                <div style={{ fontSize: "0.875rem", color: "#94a3b8", fontStyle: "italic", padding: "12px 0" }}>
                  No fields configured.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {fieldsList.map((field, index) => (
                    <div key={field.id || index} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: "12px", alignItems: "center", background: "#f8fafc", padding: "8px 12px", borderRadius: "6px" }}>
                      <input
                        type="text"
                        className="input-modern"
                        value={field.name || ""}
                        onChange={(e) => updateField(key, index, { name: e.target.value })}
                        style={{ padding: "6px 10px" }}
                        disabled={!isEnabled}
                      />
                      
                      <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem", color: "#475569", cursor: isEnabled ? "pointer" : "default" }}>
                        <input 
                          type="checkbox" 
                          checked={Boolean(field.visible)}
                          onChange={(e) => updateField(key, index, { visible: e.target.checked })}
                          disabled={!isEnabled}
                        />
                        Visible
                      </label>

                      <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem", color: "#475569", cursor: isEnabled ? "pointer" : "default" }}>
                        <input 
                          type="checkbox" 
                          checked={Boolean(field.required)}
                          onChange={(e) => updateField(key, index, { required: e.target.checked })}
                          disabled={!isEnabled}
                        />
                        Required
                      </label>

                      <button 
                        onClick={() => removeField(key, index)}
                        style={{ background: "none", border: "none", color: "#ef4444", cursor: isEnabled ? "pointer" : "default", padding: "4px" }}
                        disabled={!isEnabled}
                        title="Remove field"
                      >
                        <FaTrash />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
