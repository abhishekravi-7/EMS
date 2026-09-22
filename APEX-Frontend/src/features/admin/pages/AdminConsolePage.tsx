import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getAdminSettings, updateAdminSettings, type SystemSettings } from "../services/adminService";
import {
  FaGithub,
  FaBrain,
  FaShieldAlt,
  FaDatabase,
  FaEye,
  FaEyeSlash,
  FaArrowLeft,
  FaSyncAlt,
  FaServer,
  FaLink,
  FaRocket,
} from "react-icons/fa";
import "./AdminConsolePage.css";

const ADMIN_RAIL_TABS = [
  { id: "github", label: "Pipeline", icon: FaGithub, category: "Infrastructure" },
  { id: "ai", label: "Intelligence", icon: FaBrain, category: "Cognitive" },
  { id: "quality", label: "Reliability", icon: FaShieldAlt, category: "Validation" },
  { id: "platform", label: "Core Hub", icon: FaDatabase, category: "System" },
];

const INITIAL_SETTINGS: SystemSettings = {
  github_token: "",
  github_api_base_url: "",
  github_target_owner: "",
  github_target_token: "",
  huggingface_token: "",
  groq_api_key: "",
  ollama_base_url: "",
  rag_enabled: false,
  sonarqube_host_url: "",
  sonarqube_token: "",
  fossa_api_key: "",
  jwt_secret_key: "",
};

export default function AdminConsolePage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("github");
  const [showSecrets, setShowSecrets] = useState<{ [key: string]: boolean }>({});
  const [settings, setSettings] = useState<SystemSettings>(INITIAL_SETTINGS);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSettings() {
      try {
        setIsLoading(true);
        const data = await getAdminSettings();
        setSettings(data);
      } catch (err) {
        setError("Failed to load settings. Please check your permissions.");
        console.error("Failed to load admin settings:", err);
      } finally {
        setIsLoading(false);
      }
    }
    fetchSettings();
  }, []);

  const toggleSecret = (id: string) => {
    setShowSecrets(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleFieldChange = (key: keyof SystemSettings, value: string | boolean) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleDeploy = async () => {
    try {
      setIsSaving(true);
      setError(null);
      await updateAdminSettings(settings);
      alert("Settings deployed and applied successfully.");
    } catch (err) {
      setError("Failed to update settings.");
      console.error("Failed to update admin settings:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const currentTab = ADMIN_RAIL_TABS.find(t => t.id === activeTab) || ADMIN_RAIL_TABS[0];

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="admin-loading-state">
          <div className="spinner-modern"></div>
          <span>Fetching configuration...</span>
        </div>
      );
    }

    switch (activeTab) {
      case "github":
        return (
          <div className="admin-content-grid">
            <div className="admin-config-card">
              <h3 className="card-heading-modern">
                <FaGithub style={{ color: "#2563eb" }} />
                Source Connection
              </h3>
              <div className="field-group-modern">
                <div className="field-modern">
                  <label className="label-modern">Analysis Token</label>
                  <div className="input-wrap-modern">
                    <input
                      type={showSecrets["github_token"] ? "text" : "password"}
                      className="input-modern"
                      value={settings.github_token}
                      onChange={(e) => handleFieldChange("github_token", e.target.value)}
                    />
                    <div className="toggle-modern" onClick={() => toggleSecret("github_token")}>
                      {showSecrets["github_token"] ? <FaEyeSlash /> : <FaEye />}
                    </div>
                  </div>
                </div>
                <div className="field-modern">
                  <label className="label-modern">API Endpoint</label>
                  <input
                    type="text"
                    className="input-modern"
                    value={settings.github_api_base_url}
                    onChange={(e) => handleFieldChange("github_api_base_url", e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="admin-config-card">
              <h3 className="card-heading-modern">
                <FaRocket style={{ color: "#2563eb" }} />
                Target Publication
              </h3>
              <div className="field-group-modern">
                <div className="field-modern">
                  <label className="label-modern">Destination Owner</label>
                  <input
                    type="text"
                    className="input-modern"
                    value={settings.github_target_owner}
                    onChange={(e) => handleFieldChange("github_target_owner", e.target.value)}
                  />
                </div>
                <div className="field-modern">
                  <label className="label-modern">Publishing Token</label>
                  <div className="input-wrap-modern">
                    <input
                      type={showSecrets["github_target_token"] ? "text" : "password"}
                      className="input-modern"
                      value={settings.github_target_token}
                      onChange={(e) => handleFieldChange("github_target_token", e.target.value)}
                    />
                    <div className="toggle-modern" onClick={() => toggleSecret("github_target_token")}>
                      {showSecrets["github_target_token"] ? <FaEyeSlash /> : <FaEye />}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case "ai":
        return (
          <div className="admin-content-grid">
            <div className="admin-config-card">
              <h3 className="card-heading-modern">
                <FaBrain style={{ color: "#2563eb" }} />
                Intelligence Engines
              </h3>
              <div className="field-group-modern">
                <div className="field-modern">
                  <label className="label-modern">Analysis Engine (LLM_1)</label>
                  <div className="input-wrap-modern">
                    <input
                      type={showSecrets["llm_1"] ? "text" : "password"}
                      className="input-modern"
                      value={settings.huggingface_token}
                      onChange={(e) => handleFieldChange("huggingface_token", e.target.value)}
                    />
                    <div className="toggle-modern" onClick={() => toggleSecret("llm_1")}>
                      {showSecrets["llm_1"] ? <FaEyeSlash /> : <FaEye />}
                    </div>
                  </div>
                </div>
                <div className="field-modern">
                  <label className="label-modern">Strategy Engine (LLM_2)</label>
                  <div className="input-wrap-modern">
                    <input
                      type={showSecrets["llm_2"] ? "text" : "password"}
                      className="input-modern"
                      value={settings.groq_api_key}
                      onChange={(e) => handleFieldChange("groq_api_key", e.target.value)}
                    />
                    <div className="toggle-modern" onClick={() => toggleSecret("llm_2")}>
                      {showSecrets["llm_2"] ? <FaEyeSlash /> : <FaEye />}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="admin-config-card">
              <h3 className="card-heading-modern">
                <FaLink style={{ color: "#2563eb" }} />
                Contextual RAG
              </h3>
              <div className="field-group-modern">
                <div className="field-modern">
                  <label className="label-modern">Ollama Host</label>
                  <input
                    type="text"
                    className="input-modern"
                    value={settings.ollama_base_url}
                    onChange={(e) => handleFieldChange("ollama_base_url", e.target.value)}
                  />
                </div>
                <div className="field-modern">
                  <label className="label-modern">RAG Stack</label>
                  <div className="switch-row-modern">
                    <label className="switch-modern">
                      <input
                        type="checkbox"
                        checked={settings.rag_enabled === true || settings.rag_enabled === "True"}
                        onChange={(e) => handleFieldChange("rag_enabled", e.target.checked)}
                      />
                      <span className="slider-modern"></span>
                    </label>
                    <span className="switch-label-modern">
                      {settings.rag_enabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case "quality":
        return (
          <div className="admin-content-grid">
            <div className="admin-config-card" style={{ gridColumn: "span 2" }}>
              <h3 className="card-heading-modern">
                <FaShieldAlt style={{ color: "#2563eb" }} />
                Reliability Gates
              </h3>
              <div className="field-grid-three">
                <div className="field-modern">
                  <label className="label-modern">Sonar Host</label>
                  <input
                    type="text"
                    className="input-modern"
                    value={settings.sonarqube_host_url}
                    onChange={(e) => handleFieldChange("sonarqube_host_url", e.target.value)}
                  />
                </div>
                <div className="field-modern">
                  <label className="label-modern">Sonar Token</label>
                  <div className="input-wrap-modern">
                    <input
                      type={showSecrets["sonar"] ? "text" : "password"}
                      className="input-modern"
                      value={settings.sonarqube_token}
                      onChange={(e) => handleFieldChange("sonarqube_token", e.target.value)}
                    />
                    <div className="toggle-modern" onClick={() => toggleSecret("sonar")}>
                      {showSecrets["sonar"] ? <FaEyeSlash /> : <FaEye />}
                    </div>
                  </div>
                </div>
                <div className="field-modern">
                  <label className="label-modern">FOSSA API Key</label>
                  <div className="input-wrap-modern">
                    <input
                      type={showSecrets["fossa"] ? "text" : "password"}
                      className="input-modern"
                      value={settings.fossa_api_key}
                      onChange={(e) => handleFieldChange("fossa_api_key", e.target.value)}
                    />
                    <div className="toggle-modern" onClick={() => toggleSecret("fossa")}>
                      {showSecrets["fossa"] ? <FaEyeSlash /> : <FaEye />}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case "platform":
        return (
          <div className="admin-content-grid">
            <div className="admin-config-card" style={{ gridColumn: "span 2" }}>
              <h3 className="card-heading-modern">
                <FaServer style={{ color: "#2563eb" }} />
                Infrastructure Hub
              </h3>
              <div className="field-group-modern">
                <div className="field-modern">
                  <label className="label-modern">JWT Authentication Secret</label>
                  <div className="input-wrap-modern">
                    <input
                      type={showSecrets["jwt"] ? "text" : "password"}
                      className="input-modern"
                      value={settings.jwt_secret_key}
                      onChange={(e) => handleFieldChange("jwt_secret_key", e.target.value)}
                    />
                    <div className="toggle-modern" onClick={() => toggleSecret("jwt")}>
                      {showSecrets["jwt"] ? <FaEyeSlash /> : <FaEye />}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="admin-console-layout">
      {/* Sidebar Rail - Matches Main Page Style */}
      <aside className="admin-rail-sidebar">
        <div className="admin-rail-steps">
          {ADMIN_RAIL_TABS.map((tab) => {
            const isCurrent = activeTab === tab.id;
            return (
              <div
                key={tab.id}
                className={`admin-rail-item ${isCurrent ? "is-active" : ""}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <div className="admin-rail-icon-wrap">
                  <tab.icon size={18} />
                </div>

                <div className="admin-rail-details-reveal">
                  <div className="admin-rail-text-col">
                    <span className="admin-rail-title">{tab.label}</span>
                    <span className="admin-rail-subtitle">{tab.category}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="admin-sidebar-footer">
          <div style={{ fontSize: 11, color: "#94a3b8", textAlign: "center" }}>
            © 2026 Powered by <strong style={{ color: "#2563eb" }}>Sorim.ai</strong>
          </div>
        </div>
      </aside>

      <main className="admin-main-surface">
        <header className="admin-main-header">
          <div className="header-title-group">
            <div className="header-symbol-wrap">
              <currentTab.icon size={22} />
            </div>
            <div className="header-text-stack">
              <span className="header-eyebrow">{currentTab.category}</span>
              <h2 className="header-heading">{currentTab.label} Config</h2>
            </div>
          </div>

          <div className="header-actions">
            <button className="back-btn-modern" onClick={() => navigate("/")} disabled={isSaving}>
              <FaArrowLeft />
              <span>Back</span>
            </button>
            <button
              className="deploy-btn-modern"
              onClick={handleDeploy}
              disabled={isSaving || isLoading}
            >
              {isSaving ? (
                <>
                  <div className="spinner-small"></div>
                  <span>Deploying...</span>
                </>
              ) : (
                <>
                  <FaSyncAlt />
                  <span>Deploy</span>
                </>
              )}
            </button>
          </div>
        </header>

        {error && (
          <div className="admin-error-banner">
            <FaShieldAlt />
            <span>{error}</span>
            <button onClick={() => setError(null)}>×</button>
          </div>
        )}

        <div className="admin-scroll-canvas" key={activeTab}>
          {renderContent()}
        </div>
      </main>
    </div>
  );
}
