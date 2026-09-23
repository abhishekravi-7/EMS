import React, { useState } from "react";
import type { FullUserSettings, SystemSettings } from "../services/adminService";
import { testUserPlaywrightConnection } from "../services/adminService";
import { FaSpinner, FaPlay, FaCheckCircle, FaTimesCircle, FaShieldAlt } from "react-icons/fa";

interface TestCasesUserSettingsProps {
  settings: FullUserSettings;
  onChange: (key: keyof FullUserSettings, value: any) => void;
  adminSettings: SystemSettings;
}

export function TestCasesUserSettings({ settings, onChange, adminSettings }: TestCasesUserSettingsProps) {
  const playwrightEnabled = adminSettings.test_cases_playwright_enabled === true || adminSettings.test_cases_playwright_enabled === "true";
  const cypressEnabled = adminSettings.test_cases_cypress_enabled === true || adminSettings.test_cases_cypress_enabled === "true";
  const seleniumEnabled = adminSettings.test_cases_selenium_enabled === true || adminSettings.test_cases_selenium_enabled === "true";
  
  const playwrightBaseUrl = settings.test_cases_values?.playwright_base_url || "";
  const cypressBaseUrl = settings.test_cases_values?.cypress_base_url || "";
  const seleniumBaseUrl = settings.test_cases_values?.selenium_base_url || "";

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: "success" | "error"; message: string } | null>(null);

  if (!playwrightEnabled && !cypressEnabled && !seleniumEnabled) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "16px", padding: "24px", border: "1px solid #e2e8f0", borderRadius: "8px", background: "#f8fafc", textAlign: "center" }}>
        <h3 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b", fontWeight: 600 }}>Test Cases Configuration</h3>
        <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "#64748b" }}>
          No test frameworks are enabled by the system administrator. Please contact your admin to enable testing features.
        </p>
      </div>
    );
  }

  const handleTestConnection = async () => {
    if (!playwrightBaseUrl) {
      alert("Please enter an Application / Base URL.");
      return;
    }

    setTesting(true);
    setTestResult(null);
    try {
      const res = await testUserPlaywrightConnection(playwrightBaseUrl);
      setTestResult({ status: "success", message: res.message || "Connected to application successfully." });
    } catch (err: any) {
      setTestResult({ status: "error", message: err.message || "Connection failed." });
    } finally {
      setTesting(false);
    }
  };



  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px", marginTop: "16px" }}>
      <div>
        <h3 className="card-heading-modern">
          <FaShieldAlt style={{ color: "#2563eb", marginRight: "8px" }} />
          Test Cases Configuration
        </h3>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
        {playwrightEnabled && (
          <div>
            <h4 style={{ margin: 0, fontSize: "1.05rem", color: "#1e293b", fontWeight: 600, marginBottom: "8px" }}>Playwright</h4>
            <label style={{ display: "block", marginBottom: "8px", fontSize: "0.9rem", color: "#334155", fontWeight: 500 }}>
              Application Base URL
            </label>
            <input
              type="url"
              className="input-modern"
              value={playwrightBaseUrl}
              onChange={(e) => {
                onChange("test_cases_values", {
                  ...settings.test_cases_values,
                  playwright_base_url: e.target.value
                });
              }}
              placeholder="http://host.docker.internal:3000"
              style={{ width: "100%", maxWidth: "400px" }}
            />
            
            {/* Test Result Alert */}
            {testResult && (
              <div style={{
                marginTop: "16px",
                padding: "16px",
                borderRadius: "8px",
                border: `1px solid ${testResult.status === "success" ? "#86efac" : "#fca5a5"}`,
                backgroundColor: testResult.status === "success" ? "#f0fdf4" : "#fef2f2",
                display: "flex",
                alignItems: "flex-start",
                gap: "12px"
              }}>
                {testResult.status === "success" ? (
                  <FaCheckCircle style={{ color: "#16a34a", marginTop: "2px" }} />
                ) : (
                  <FaTimesCircle style={{ color: "#dc2626", marginTop: "2px" }} />
                )}
                <div>
                  <h5 style={{ margin: 0, color: testResult.status === "success" ? "#166534" : "#991b1b", fontWeight: 600 }}>
                    {testResult.status === "success" ? "Connection Successful" : "Connection Failed"}
                  </h5>
                  <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: testResult.status === "success" ? "#15803d" : "#b91c1c" }}>
                    {testResult.message}
                  </p>
                </div>
              </div>
            )}

            <div style={{ display: "flex", gap: "12px", marginTop: "16px" }}>
              <button
                className="back-btn-modern"
                onClick={handleTestConnection}
                disabled={testing || !playwrightBaseUrl}
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                {testing ? <FaSpinner className="animate-spin" /> : <FaPlay />}
                Test Connection
              </button>
            </div>
          </div>
        )}

        {cypressEnabled && (
          <div>
            <h4 style={{ margin: 0, fontSize: "1.05rem", color: "#1e293b", fontWeight: 600, marginBottom: "8px" }}>Cypress</h4>
            <label style={{ display: "block", marginBottom: "8px", fontSize: "0.9rem", color: "#334155", fontWeight: 500 }}>
              Application Base URL
            </label>
            <input
              type="url"
              className="input-modern"
              value={cypressBaseUrl}
              onChange={(e) => {
                onChange("test_cases_values", {
                  ...settings.test_cases_values,
                  cypress_base_url: e.target.value
                });
              }}
              placeholder="http://host.docker.internal:3000"
              style={{ width: "100%", maxWidth: "400px" }}
            />
          </div>
        )}

        {seleniumEnabled && (
          <div>
            <h4 style={{ margin: 0, fontSize: "1.05rem", color: "#1e293b", fontWeight: 600, marginBottom: "8px" }}>Selenium</h4>
            <label style={{ display: "block", marginBottom: "8px", fontSize: "0.9rem", color: "#334155", fontWeight: 500 }}>
              Application Base URL
            </label>
            <input
              type="url"
              className="input-modern"
              value={seleniumBaseUrl}
              onChange={(e) => {
                onChange("test_cases_values", {
                  ...settings.test_cases_values,
                  selenium_base_url: e.target.value
                });
              }}
              placeholder="http://host.docker.internal:3000"
              style={{ width: "100%", maxWidth: "400px" }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
