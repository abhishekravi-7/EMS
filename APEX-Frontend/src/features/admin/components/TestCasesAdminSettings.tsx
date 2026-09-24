import React, { useState } from "react";
import type { SystemSettings } from "../services/adminService";
import { testAdminPlaywrightConnection } from "../services/adminService";
import { FaSpinner, FaPlay, FaCheckCircle, FaTimesCircle, FaShieldAlt } from "react-icons/fa";

interface TestCasesAdminSettingsProps {
  settings: SystemSettings;
  onChange: (key: keyof SystemSettings, value: any) => void;
}

export function TestCasesAdminSettings({ settings, onChange }: TestCasesAdminSettingsProps) {
  const playwrightEnabled = settings.test_cases_playwright_enabled === true || settings.test_cases_playwright_enabled === "true";
  const playwrightCommand = settings.test_cases_playwright_command || "npx playwright test";

  const cypressEnabled = settings.test_cases_cypress_enabled === true || settings.test_cases_cypress_enabled === "true";
  const cypressCommand = settings.test_cases_cypress_command || "npx cypress run";

  const seleniumEnabled = settings.test_cases_selenium_enabled === true || settings.test_cases_selenium_enabled === "true";
  const seleniumCommand = settings.test_cases_selenium_command || "pytest";

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: "success" | "error"; message: string } | null>(null);

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testAdminPlaywrightConnection();
      setTestResult({ status: "success", message: res.message || "Playwright is configured correctly." });
    } catch (err: any) {
      setTestResult({ status: "error", message: err.message || "Test connection failed." });
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

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {/* Playwright Enable Toggle */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div>
              <h4 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b", fontWeight: 600 }}>Enable Playwright</h4>
              <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "#64748b" }}>
                Allow users to configure and run Playwright tests against their application.
              </p>
            </div>
            <div className="switch-row-modern" style={{ marginTop: 0 }}>
              <label className="switch-modern">
                <input
                  type="checkbox"
                  checked={playwrightEnabled}
                  onChange={(e) => onChange("test_cases_playwright_enabled", e.target.checked)}
                />
                <span className="slider-modern"></span>
              </label>
              <span className="switch-label-modern" style={{ minWidth: "100px" }}>
                {playwrightEnabled ? "Enabled" : "Disabled"}
              </span>
            </div>
          </div>

          {/* Playwright Command Config */}
          <div style={{ pointerEvents: playwrightEnabled ? "auto" : "none", opacity: playwrightEnabled ? 1 : 0.6 }}>
            <label style={{ display: "block", marginBottom: "8px", fontSize: "0.9rem", color: "#334155", fontWeight: 500 }}>
              Playwright Test Command
            </label>
            <input
              type="text"
              className="input-modern"
              value={playwrightCommand}
              onChange={(e) => onChange("test_cases_playwright_command", e.target.value)}
              disabled={!playwrightEnabled}
              placeholder="npx playwright test"
              style={{ width: "100%", maxWidth: "400px" }}
            />
          </div>
        </div>

        {/* Cypress Enable Toggle */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div>
              <h4 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b", fontWeight: 600 }}>Enable Cypress</h4>
              <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "#64748b" }}>
                Allow users to configure and run Cypress tests against their application.
              </p>
            </div>
            <div className="switch-row-modern" style={{ marginTop: 0 }}>
              <label className="switch-modern">
                <input
                  type="checkbox"
                  checked={cypressEnabled}
                  onChange={(e) => onChange("test_cases_cypress_enabled", e.target.checked)}
                />
                <span className="slider-modern"></span>
              </label>
              <span className="switch-label-modern" style={{ minWidth: "100px" }}>
                {cypressEnabled ? "Enabled" : "Disabled"}
              </span>
            </div>
          </div>

          {/* Cypress Command Config */}
          <div style={{ pointerEvents: cypressEnabled ? "auto" : "none", opacity: cypressEnabled ? 1 : 0.6 }}>
            <label style={{ display: "block", marginBottom: "8px", fontSize: "0.9rem", color: "#334155", fontWeight: 500 }}>
              Cypress Test Command
            </label>
            <input
              type="text"
              className="input-modern"
              value={cypressCommand}
              onChange={(e) => onChange("test_cases_cypress_command", e.target.value)}
              disabled={!cypressEnabled}
              placeholder="npx cypress run"
              style={{ width: "100%", maxWidth: "400px" }}
            />
          </div>
        </div>

        {/* Selenium Enable Toggle */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div>
              <h4 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b", fontWeight: 600 }}>Enable Selenium</h4>
              <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "#64748b" }}>
                Allow users to configure and run Selenium tests against their application.
              </p>
            </div>
            <div className="switch-row-modern" style={{ marginTop: 0 }}>
              <label className="switch-modern">
                <input
                  type="checkbox"
                  checked={seleniumEnabled}
                  onChange={(e) => onChange("test_cases_selenium_enabled", e.target.checked)}
                />
                <span className="slider-modern"></span>
              </label>
              <span className="switch-label-modern" style={{ minWidth: "100px" }}>
                {seleniumEnabled ? "Enabled" : "Disabled"}
              </span>
            </div>
          </div>

          {/* Selenium Command Config */}
          <div style={{ pointerEvents: seleniumEnabled ? "auto" : "none", opacity: seleniumEnabled ? 1 : 0.6 }}>
            <label style={{ display: "block", marginBottom: "8px", fontSize: "0.9rem", color: "#334155", fontWeight: 500 }}>
              Selenium Test Command
            </label>
            <input
              type="text"
              className="input-modern"
              value={seleniumCommand}
              onChange={(e) => onChange("test_cases_selenium_command", e.target.value)}
              disabled={!seleniumEnabled}
              placeholder="pytest"
              style={{ width: "100%", maxWidth: "400px" }}
            />
          </div>
        </div>

        {/* Test Result Alert */}
        {testResult && (
          <div style={{
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

        <div style={{ display: "flex", gap: "12px", marginTop: "16px", justifyContent: "flex-end" }}>
          <button
            className="deploy-btn-modern"
            onClick={handleTestConnection}
            disabled={testing || !playwrightEnabled}
            style={{ display: "flex", alignItems: "center", gap: "8px" }}
          >
            {testing ? <FaSpinner className="animate-spin" /> : <FaPlay />}
            Test Configuration
          </button>
        </div>
      </div>
    </div>
  );
}
