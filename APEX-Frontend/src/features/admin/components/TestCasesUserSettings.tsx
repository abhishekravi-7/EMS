import React, { useState } from "react";
import type { FullUserSettings } from "../services/adminService";
import { testUserPlaywrightConnection } from "../services/adminService";
import { FaSpinner, FaPlay, FaCheckCircle, FaTimesCircle } from "react-icons/fa";

interface TestCasesUserSettingsProps {
  settings: FullUserSettings;
  onChange: (key: keyof FullUserSettings, value: any) => void;
  isAdminEnabled: boolean;
}

export function TestCasesUserSettings({ settings, onChange, isAdminEnabled }: TestCasesUserSettingsProps) {
  const playwrightBaseUrl = settings.test_cases_values?.playwright_base_url || "";

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: "success" | "error"; message: string } | null>(null);

  if (!isAdminEnabled) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "16px", padding: "24px", border: "1px solid #e2e8f0", borderRadius: "8px", background: "#f8fafc", textAlign: "center" }}>
        <h3 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b", fontWeight: 600 }}>Test Cases Configuration</h3>
        <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "#64748b" }}>
          Playwright is not enabled by the system administrator. Please contact your admin to enable this feature.
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
        <h3 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b", fontWeight: 600 }}>Playwright Configuration</h3>
        <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "#64748b" }}>
          Configure your local application URL for Playwright tests to run against.
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div>
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
            disabled={false}
            placeholder="http://host.docker.internal:3000"
            style={{ width: "100%", maxWidth: "400px" }}
          />
          <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "#94a3b8" }}>
            The URL where your local application is running. For Docker networking, use <code>http://host.docker.internal:PORT</code>.
          </p>
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
    </div>
  );
}
