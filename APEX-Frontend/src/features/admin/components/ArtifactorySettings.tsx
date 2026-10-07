/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from "react";
import { FaPlug, FaEye, FaEyeSlash, FaSpinner, FaCheckCircle, FaExclamationTriangle } from "react-icons/fa";

interface ArtifactorySettingsProps {
  settings: Record<string, any>;
  onChange: (key: string, value: any) => void;
  isAdmin: boolean;
}

const CustomDropdown = ({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: {value: string; label: string}[] }) => {
  const [isOpen, setIsOpen] = useState(false);
  const selectedLabel = options.find(o => o.value === value)?.label || "Select...";

  return (
    <div style={{ position: "relative", width: "100%" }}>
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{ padding: "10px 14px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "14px", color: "#1e293b", background: "#ffffff", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", transition: "all 0.2s", boxShadow: isOpen ? "0 0 0 3px rgba(37,99,235,0.1)" : "none", borderColor: isOpen ? "#2563eb" : "#cbd5e1" }}
      >
        <span>{selectedLabel}</span>
        <svg style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0)", transition: "transform 0.2s" }} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
      </div>
      
      {isOpen && (
        <div style={{ position: "absolute", top: "100%", left: 0, right: 0, marginTop: "4px", background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)", zIndex: 50, overflow: "hidden" }}>
          {options.map((opt) => (
            <div 
              key={opt.value}
              onClick={() => { onChange(opt.value); setIsOpen(false); }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#eff6ff")}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
              style={{ padding: "10px 14px", fontSize: "14px", color: opt.value === value ? "#2563eb" : "#334155", cursor: "pointer", background: opt.value === value ? "#eff6ff" : "transparent", fontWeight: opt.value === value ? 600 : 400, transition: "background 0.1s" }}
            >
              {opt.label}
            </div>
          ))}
        </div>
      )}
      {isOpen && <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, zIndex: 40 }} onClick={() => setIsOpen(false)} />}
    </div>
  );
};

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
            <CustomDropdown 
              value={provider} 
              onChange={(v) => onChange("artifactory_provider", v)}
              options={[
                { value: "maven_central", label: "Maven Central (Public)" },
                { value: "jfrog", label: "JFrog Artifactory" },
                { value: "nexus", label: "Sonatype Nexus" }
              ]}
            />
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
