import React, { useState } from "react";
import type { FullUserSettings, SystemSettings } from "../services/adminService";
import { testUserPlaywrightConnection } from "../services/adminService";
import { FaSpinner, FaPlay, FaCheckCircle, FaTimesCircle } from "react-icons/fa";

interface TestCasesUserSettingsProps {
  settings: FullUserSettings;
  onChange: (key: keyof FullUserSettings, value: unknown) => void;
  adminSettings: SystemSettings;
}

export function TestCasesUserSettings({ settings, onChange, adminSettings }: TestCasesUserSettingsProps) {
  const sysTestConfig = settings?.system_test_cases_config || {};
  const playwrightEnabled =
    adminSettings?.test_cases_playwright_enabled === undefined ||
    adminSettings?.test_cases_playwright_enabled === true ||
    adminSettings?.test_cases_playwright_enabled === "true" ||
    sysTestConfig.test_cases_playwright_enabled === true ||
    sysTestConfig.test_cases_playwright_enabled === "true";

  const cypressEnabled =
    adminSettings?.test_cases_cypress_enabled === undefined ||
    adminSettings?.test_cases_cypress_enabled === true ||
    adminSettings?.test_cases_cypress_enabled === "true" ||
    sysTestConfig.test_cases_cypress_enabled === true ||
    sysTestConfig.test_cases_cypress_enabled === "true";

  const seleniumEnabled =
    adminSettings?.test_cases_selenium_enabled === undefined ||
    adminSettings?.test_cases_selenium_enabled === true ||
    adminSettings?.test_cases_selenium_enabled === "true" ||
    sysTestConfig.test_cases_selenium_enabled === true ||
    sysTestConfig.test_cases_selenium_enabled === "true";

  const playwrightBaseUrl = settings.test_cases_values?.playwright_base_url || "";
  const cypressBaseUrl = settings.test_cases_values?.cypress_base_url || "";
  const seleniumBaseUrl = settings.test_cases_values?.selenium_base_url || "";

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: "success" | "error"; message: string } | null>(null);

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
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Connection failed.";
      setTestResult({ status: "error", message: errMsg });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>


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
