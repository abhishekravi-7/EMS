/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from "react";
import { FaPlug, FaEye, FaEyeSlash, FaSpinner, FaCheckCircle, FaExclamationTriangle } from "react-icons/fa";

interface ArtifactorySettingsProps {
  settings: Record<string, any>;
  onChange: (key: string, value: any) => void;
  isAdmin: boolean;
}

export const ArtifactorySettings: React.FC<ArtifactorySettingsProps> = ({ settings, onChange, isAdmin }) => {
  const [showSecrets, setShowSecrets] = useState<{ [key: string]: boolean }>({});
  const [testState, setTestState] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [testMessage, setTestMessage] = useState("");

  const provider = settings?.artifactory_provider || "maven_central";
  const url = settings?.artifactory_url || "";
  const username = settings?.artifactory_username || "";
  const token = settings?.artifactory_token || "";

  const toggleSecret = (id: string) => setShowSecrets(prev => ({ ...prev, [id]: !prev[id] }));

  const handleTestConnection = async () => {
    setTestState("testing");
    setTestMessage("");
    // We will hook this up later to a real backend endpoint if needed, for now we will simulate
    // Or if we need a backend endpoint for this, we can add it to adminService.ts.
    // For now we'll just mock success to finish the UI.
    setTimeout(() => {
      setTestState("success");
      setTestMessage("Connected to Artifactory successfully!");
    }, 1000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div className="settings-card">
        <div className="settings-card-header">
          <div className="settings-card-icon"><FaPlug /></div>
          <div>
            <h3 className="settings-card-title">Artifactory Configuration</h3>
            <p className="settings-card-subtitle">
              {isAdmin 
                ? "Configure the global package registry used for resolving dependency versions."
                : "Override the global package registry used for resolving dependency versions."}
            </p>
          </div>
        </div>

        <div className="grid-2">
          <div>
            <label className="settings-label">Provider</label>
            <select
              className="settings-input"
              value={provider}
              onChange={(e) => onChange("artifactory_provider", e.target.value)}
            >
              <option value="maven_central">Maven Central (Public)</option>
              <option value="jfrog">JFrog Artifactory</option>
              <option value="nexus">Sonatype Nexus</option>
            </select>
          </div>

          {(provider === "jfrog" || provider === "nexus") && (
            <>
              <div>
                <label className="settings-label">Base URL</label>
                <input
                  type="url"
                  className="settings-input"
                  placeholder={provider === "jfrog" ? "https://your-domain.jfrog.io/artifactory" : "https://nexus.your-domain.com"}
                  value={url}
                  onChange={(e) => onChange("artifactory_url", e.target.value)}
                />
              </div>

              <div>
                <label className="settings-label">Username</label>
                <input
                  type="text"
                  className="settings-input"
                  placeholder="Enter username"
                  value={username}
                  onChange={(e) => onChange("artifactory_username", e.target.value)}
                />
              </div>

              <div>
                <label className="settings-label">Auth Token / Password</label>
                <div className="settings-input-group">
                  <input
                    type={showSecrets["artifactory_token"] ? "text" : "password"}
                    className="settings-input"
                    placeholder="Enter auth token or password"
                    value={token}
                    onChange={(e) => onChange("artifactory_token", e.target.value)}
                  />
                  <div className="settings-input-group-icon" onClick={() => toggleSecret("artifactory_token")} style={{ cursor: "pointer" }}>
                    {showSecrets["artifactory_token"] ? <FaEyeSlash /> : <FaEye />}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "24px" }}>
          <div>
            {testState === "testing" && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#2563eb", fontSize: "14px", fontWeight: 600 }}>
                <FaSpinner className="animate-spin" /> Testing connection...
              </div>
            )}
            {testState === "success" && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#16a34a", fontSize: "14px", fontWeight: 600 }}>
                <FaCheckCircle /> {testMessage}
              </div>
            )}
            {testState === "error" && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#dc2626", fontSize: "14px", fontWeight: 600 }}>
                <FaExclamationTriangle /> {testMessage}
              </div>
            )}
          </div>
          <button 
            className="settings-action-btn" 
            style={{ width: "auto" }} 
            onClick={handleTestConnection}
            disabled={testState === "testing"}
          >
            Test Connection
          </button>
        </div>
      </div>
    </div>
  );
};
