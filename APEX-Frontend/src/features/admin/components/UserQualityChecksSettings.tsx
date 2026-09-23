import React, { useState, useEffect } from "react";
import { FaShieldAlt, FaEye, FaEyeSlash } from "react-icons/fa";
import { getQualityChecksAdminConfig, type FullUserSettings } from "../services/adminService";
 
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
 
  if (enabledChecks.length === 0) {
    return (
      <div className="admin-content-stacked">
        <div className="user-config-card">
          <h3 className="card-heading-modern">
            <FaShieldAlt style={{ color: "#2563eb" }} />
            Quality Checks
          </h3>
          <p style={{ color: "#64748b", marginTop: "12px" }}>
            No quality checks have been enabled by the Super Admin.
          </p>
        </div>
      </div>
    );
  }
 
  return (
    <div className="admin-content-stacked">
      {enabledChecks.map((check: any, index: number) => {
        const visibleFields = Array.isArray(check.fields) ? check.fields.filter((f: any) => f.visible) : [];
 
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
          </div>
        );
      })}
    </div>
  );
}
 