/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, react-hooks/exhaustive-deps */
import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  getAdminSettings,
  updateAdminSettings,
  getUserSettings,
  updateUserSettings,
  testUserGithubConnection,
  testUserSonarConnection,
  testUserFossaConnection,
  fetchUserGithubRepos,
  fetchUserGithubBranches,
  type SystemSettings,
  type UserGitHubConfig,
  type FullUserSettings,
  type GithubRepo,
  type GithubBranch
} from "../services/adminService";
import { useAuth } from "@/shared/context/AuthContext";
import {
  FaGithub, FaBrain, FaShieldAlt, FaEye, FaEyeSlash,
  FaCog, FaBriefcase, FaFlask, FaPlug, FaSpinner, FaCheckCircle, FaTimesCircle
} from "react-icons/fa";
import UserQualityChecksSettings from "../components/UserQualityChecksSettings";
import "./AdminConsolePage.css";

const TABS = [
  { id: "general", label: "General", icon: FaCog },
  { id: "business", label: "Business", icon: FaBriefcase },
  { id: "testing", label: "Testing", icon: FaFlask },
  { id: "quality", label: "Quality Gate", icon: FaShieldAlt },
  { id: "ai", label: "LLM Configuration", icon: FaBrain },
];

const INITIAL_USER_SETTINGS: FullUserSettings = {
  github_config: { github_account: "", pat: "", pat_scope: "", repository: "", branch: "", user_access: "" },
  quality_checks_values: {},
  llm_values: {}
};

export default function AdminConsolePage() {
  const { currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState("general");
  
  const [userSettings, setUserSettings] = useState<FullUserSettings>(INITIAL_USER_SETTINGS);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  const showToast = (type: 'success' | 'error', text: string) => {
    setToastMessage({ type, text });
    setTimeout(() => setToastMessage(null), 3500);
  };

  const [showSecrets, setShowSecrets] = useState<{ [key: string]: boolean }>({});
  const [testingSonar, setTestingSonar] = useState(false);
  const [testingFossa, setTestingFossa] = useState(false);

  const [availableRepos, setAvailableRepos] = useState<GithubRepo[]>([]);
  const [availableBranches, setAvailableBranches] = useState<GithubBranch[]>([]);

  useEffect(() => {
    async function fetchSettings() {
      try {
        setIsLoading(true);
        const userData = await getUserSettings();
        if (!userData.quality_checks_values?.sonarqube_url) {
          userData.quality_checks_values = {
            ...(userData.quality_checks_values || {}),
            sonarqube_url: "https://sonarcloud.io"
          };
        }
        setUserSettings(userData);
      } catch (err) {
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    }
    if (currentUser) fetchSettings();
  }, [currentUser]);

  useEffect(() => {
    fetchUserGithubRepos().then(setAvailableRepos).catch(() => {});
  }, []);

  useEffect(() => {
    if (userSettings.github_config?.repository) {
      const parts = userSettings.github_config.repository.split("/");
      if (parts.length === 2) {
        fetchUserGithubBranches(parts[0], parts[1]).then(setAvailableBranches).catch(() => {});
      }
    }
  }, [userSettings.github_config?.repository]);

  const toggleSecret = (id: string) => setShowSecrets(prev => ({ ...prev, [id]: !prev[id] }));

  const handleFieldChange = (key: string, value: any, category: 'github' | 'quality' | 'llm' = 'github') => {
    setUserSettings(prev => {
      if (category === 'github') return { ...prev, github_config: { ...prev.github_config, [key]: value } };
      if (category === 'quality') return { ...prev, quality_checks_values: { ...prev.quality_checks_values, [key]: value } };
      if (category === 'llm') return { ...prev, llm_values: { ...prev.llm_values, [key]: value } };
      return prev;
    });
  };

  const handleDeploy = async () => {
    setIsSaving(true);
    try {
      await updateUserSettings(userSettings.github_config, userSettings.quality_checks_values, userSettings.test_cases_values, userSettings.llm_values);
      window.dispatchEvent(new CustomEvent("javaapex:settings-saved"));
      showToast("success", "Settings saved successfully!");
    } catch (err) {
      console.error(err);
      showToast("error", "Failed to save settings.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setIsSaving(true);
    try {
      await updateUserSettings(userSettings.github_config, userSettings.quality_checks_values, userSettings.test_cases_values, userSettings.llm_values);
      const res = await testUserGithubConnection();
      showToast("success", res.message);
    } catch (err: any) {
      showToast("error", err.message || "Failed to test connection.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestSonarConnection = async () => {
    setTestingSonar(true);
    try {
      await updateUserSettings(
        userSettings.github_config,
        userSettings.quality_checks_values,
        userSettings.test_cases_values,
        userSettings.llm_values
      );
      const res = await testUserSonarConnection({
        sonarqube_url: userSettings.quality_checks_values?.sonarqube_url,
        auth_token: userSettings.quality_checks_values?.auth_token,
        project_key: userSettings.quality_checks_values?.project_key,
        sonar_organization: userSettings.quality_checks_values?.sonar_organization,
      });
      showToast("success", res.message || "SonarQube connection successful.");
    } catch (err: any) {
      showToast("error", err.message || "Failed to connect to SonarQube.");
    } finally {
      setTestingSonar(false);
    }
  };

  const handleTestFossaConnection = async () => {
    setTestingFossa(true);
    try {
      await updateUserSettings(
        userSettings.github_config,
        userSettings.quality_checks_values,
        userSettings.test_cases_values,
        userSettings.llm_values
      );
      const res = await testUserFossaConnection({
        fossa_api_key: userSettings.quality_checks_values?.fossa_api_key,
      });
      showToast("success", res.message || "FOSSA connection successful.");
    } catch (err: any) {
      showToast("error", err.message || "Failed to connect to FOSSA.");
    } finally {
      setTestingFossa(false);
    }
  };

  const renderTabContent = () => {
    if (activeTab === "general") {
      return (
        <div className="settings-card">
          <div className="settings-card-header">
            <div className="settings-card-icon"><FaGithub /></div>
            <div>
              <h3 className="settings-card-title">GitHub Integration</h3>
              <p className="settings-card-subtitle">Configure your GitHub credentials and repository defaults.</p>
            </div>
          </div>
          <div className="grid-2">
            <div>
              <label className="settings-label">GITHUB ACCOUNT (USERNAME)</label>
              <input type="text" className="settings-input" value={userSettings.github_config?.github_account || ""} onChange={e => handleFieldChange("github_account", e.target.value)} />
            </div>
            <div>
              <label className="settings-label">PERSONAL ACCESS TOKEN (PAT)</label>
              <div className="settings-input-group">
                <input type={showSecrets["pat"] ? "text" : "password"} className="settings-input" value={userSettings.github_config?.pat || ""} onChange={e => handleFieldChange("pat", e.target.value)} />
                <div className="settings-input-group-icon" onClick={() => toggleSecret("pat")}>
                  {showSecrets["pat"] ? <FaEyeSlash /> : <FaEye />}
                </div>
              </div>
            </div>
            <div>
              <label className="settings-label">DEFAULT REPOSITORY</label>
              <select className="settings-select" value={userSettings.github_config?.repository || ""} onChange={e => handleFieldChange("repository", e.target.value)}>
                <option value="">Select Repository</option>
                {availableRepos.map(r => <option key={r.full_name} value={r.full_name}>{r.full_name}</option>)}
              </select>
            </div>
            <div>
              <label className="settings-label">DEFAULT BRANCH</label>
              <select className="settings-select" value={userSettings.github_config?.branch || ""} onChange={e => handleFieldChange("branch", e.target.value)}>
                <option value="">Select Branch</option>
                {availableBranches.map(b => <option key={b.name} value={b.name}>{b.name}</option>)}
              </select>
            </div>
            <div>
              <label className="settings-label">ACCESS LEVEL</label>
              <select className="settings-select" value={userSettings.github_config?.user_access || ""} onChange={e => handleFieldChange("user_access", e.target.value)}>
                <option value="">Select Access</option>
                <option value="read">Read</option>
                <option value="write">Write</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "24px" }}>
            <button className="settings-action-btn" style={{ width: "auto" }} onClick={handleTestConnection}>
              <FaPlug /> Test Connection
            </button>
          </div>
        </div>
      );
    }
    
    if (activeTab === "business") {
      return (
        <div className="settings-card">
          <div className="settings-card-header">
            <div className="settings-card-icon"><FaBriefcase /></div>
            <div>
              <h3 className="settings-card-title">Business Analysis Configuration</h3>
              <p className="settings-card-subtitle">Enable or disable BRD generation and Microservice assessment modes.</p>
            </div>
          </div>
          <div className="grid-2">
            <div className="settings-toggle-card">
              <div className="settings-toggle-header">
                <div className="settings-toggle-title"><FaBriefcase /> BRD Generation</div>
                <div className="switch-wrap">
                  <label className="switch-ios">
                    <input type="checkbox" defaultChecked={true} />
                    <span className="slider-ios"></span>
                  </label>
                  <span className="switch-label">Enabled</span>
                </div>
              </div>
              <p className="settings-toggle-desc">Enable or disable automated Business Requirements Document (BRD) analysis and document export during modernization discovery.</p>
            </div>
            <div className="settings-toggle-card">
              <div className="settings-toggle-header">
                <div className="settings-toggle-title"><FaFlask /> Microservice Assessment</div>
                <div className="switch-wrap">
                  <label className="switch-ios">
                    <input type="checkbox" defaultChecked={true} />
                    <span className="slider-ios"></span>
                  </label>
                  <span className="switch-label">Enabled</span>
                </div>
              </div>
              <p className="settings-toggle-desc">Enable or disable microservice eligibility scoring, architectural evaluation, and recommended service splitting analysis.</p>
            </div>
          </div>
        </div>
      );
    }

    if (activeTab === "testing") {
      return (
        <div className="settings-card">
          <div className="settings-card-header">
            <div className="settings-card-icon"><FaFlask /></div>
            <div>
              <h3 className="settings-card-title">Testing Framework Configuration</h3>
              <p className="settings-card-subtitle">Configure JUnit unit test suite and functional UI testing frameworks.</p>
            </div>
          </div>
          <UserQualityChecksSettings 
            settings={userSettings} 
            onChange={setUserSettings} 
            mode="testing_only" 
          />
        </div>
      );
    }

    if (activeTab === "quality") {
      return (
        <div className="settings-card">
          <div className="settings-card-header">
            <div className="settings-card-icon"><FaShieldAlt /></div>
            <div>
              <h3 className="settings-card-title">Quality Gate / CI & CD & Compliance</h3>
              <p className="settings-card-subtitle">Configure SonarQube, FOSSA, CI, and CD quality gate pipelines.</p>
            </div>
          </div>
          <div className="grid-2" style={{ marginBottom: "20px" }}>
            <div className="settings-toggle-card">
              <div className="settings-toggle-title" style={{ marginBottom: "12px" }}><FaShieldAlt /> SonarQube</div>
              <p className="settings-toggle-desc" style={{ marginBottom: "16px" }}>Static code analysis to detect bugs and vulnerabilities.</p>
              <div className="grid-2">
                <div>
                  <label className="settings-label">SONARQUBE URL</label>
                  <input
                    type="text"
                    className="settings-input"
                    value={userSettings.quality_checks_values?.sonarqube_url ?? "https://sonarcloud.io"}
                    onChange={e => handleFieldChange("sonarqube_url", e.target.value, "quality")}
                    placeholder="https://sonarcloud.io"
                  />
                </div>
                <div>
                  <label className="settings-label">AUTH TOKEN</label>
                  <div className="settings-input-group">
                    <input
                      type={showSecrets["sonar_auth_token"] ? "text" : "password"}
                      className="settings-input"
                      value={userSettings.quality_checks_values?.auth_token || ""}
                      onChange={e => handleFieldChange("auth_token", e.target.value, "quality")}
                      placeholder="Enter SonarQube token"
                    />
                    <div className="settings-input-group-icon" onClick={() => toggleSecret("sonar_auth_token")}>
                      {showSecrets["sonar_auth_token"] ? <FaEyeSlash /> : <FaEye />}
                    </div>
                  </div>
                </div>
              </div>
              <div className="grid-2" style={{ marginTop: "16px", marginBottom: "16px" }}>
                <div>
                  <label className="settings-label">PROJECT KEY</label>
                  <input
                    type="text"
                    className="settings-input"
                    value={userSettings.quality_checks_values?.project_key || ""}
                    onChange={e => handleFieldChange("project_key", e.target.value, "quality")}
                    placeholder="Enter project key"
                  />
                </div>
                <div>
                  <label className="settings-label">SONAR ORGANISATION</label>
                  <input
                    type="text"
                    className="settings-input"
                    value={userSettings.quality_checks_values?.sonar_organization || ""}
                    onChange={e => handleFieldChange("sonar_organization", e.target.value, "quality")}
                    placeholder="Enter org key"
                  />
                </div>
              </div>
              <button
                className="settings-action-btn"
                onClick={handleTestSonarConnection}
                disabled={testingSonar}
                type="button"
              >
                {testingSonar ? <FaSpinner className="animate-spin" /> : <FaPlug />} Test Connection
              </button>
            </div>
            
            <div className="settings-toggle-card">
              <div className="settings-toggle-title" style={{ marginBottom: "12px" }}><FaShieldAlt /> FOSSA</div>
              <p className="settings-toggle-desc" style={{ marginBottom: "16px" }}>Open source license compliance and dependency scanning.</p>
              <div>
                <label className="settings-label">FOSSA API KEY</label>
                <div className="settings-input-group" style={{ marginBottom: "16px" }}>
                  <input
                    type={showSecrets["fossa_api_key"] ? "text" : "password"}
                    className="settings-input"
                    value={userSettings.quality_checks_values?.fossa_api_key || ""}
                    onChange={e => handleFieldChange("fossa_api_key", e.target.value, "quality")}
                    placeholder="Enter FOSSA API Key"
                  />
                  <div className="settings-input-group-icon" onClick={() => toggleSecret("fossa_api_key")}>
                    {showSecrets["fossa_api_key"] ? <FaEyeSlash /> : <FaEye />}
                  </div>
                </div>
              </div>
              <div style={{ marginTop: "auto" }}>
                <button
                  className="settings-action-btn"
                  onClick={handleTestFossaConnection}
                  disabled={testingFossa}
                  type="button"
                >
                  {testingFossa ? <FaSpinner className="animate-spin" /> : <FaPlug />} Test Connection
                </button>
              </div>
            </div>
          </div>
          
          <div className="grid-2">
            <div className="settings-toggle-card">
              <div className="settings-toggle-header">
                <div className="settings-toggle-title"><FaFlask /> Continuous Integration (CI)</div>
                <div className="switch-wrap">
                  <label className="switch-ios">
                    <input
                      type="checkbox"
                      checked={userSettings.quality_checks_values?.ci_enabled ?? true}
                      onChange={e => handleFieldChange("ci_enabled", e.target.checked, "quality")}
                    />
                    <span className="slider-ios"></span>
                  </label>
                  <span className="switch-label">Enabled</span>
                </div>
              </div>
              <p className="settings-toggle-desc">Enable or disable automated CI build validation and quality gate checks on pull requests and commits.</p>
            </div>
            <div className="settings-toggle-card">
              <div className="settings-toggle-header">
                <div className="settings-toggle-title"><FaFlask /> Continuous Deployment (CD)</div>
                <div className="switch-wrap">
                  <label className="switch-ios">
                    <input
                      type="checkbox"
                      checked={userSettings.quality_checks_values?.cd_enabled ?? true}
                      onChange={e => handleFieldChange("cd_enabled", e.target.checked, "quality")}
                    />
                    <span className="slider-ios"></span>
                  </label>
                  <span className="switch-label">Enabled</span>
                </div>
              </div>
              <p className="settings-toggle-desc">Enable or disable automated deployment pipelines and artifact publishing upon successful migration verification.</p>
            </div>
          </div>
        </div>
      );
    }

    if (activeTab === "ai") {
      return (
        <div className="settings-card">
          <div className="settings-card-header">
            <div className="settings-card-icon"><FaBrain /></div>
            <div>
              <h3 className="settings-card-title">LLM Configuration</h3>
                <p className="settings-card-subtitle">Manage Intelligence providers, models, and features.</p>
              </div>
            </div>
            
            <div style={{ marginBottom: "24px" }}>
              <h4 style={{ fontSize: "16px", fontWeight: 700, margin: "0 0 16px 0", color: "#0f172a" }}>LLM 1</h4>
              <label className="settings-label">MODEL</label>
              <select 
                className="settings-select" 
                style={{ marginBottom: "16px" }}
                value={userSettings.llm_values?.llm1_model || ""}
                onChange={e => handleFieldChange("llm1_model", e.target.value, "llm")}
              >
                <option value="">Select Model</option>
                <option value="gpt-4o">gpt-4o</option>
                <option value="claude-3.5-sonnet">claude-3.5-sonnet</option>
                <option value="meta-llama/Llama-3.1-8B-Instruct">meta-llama/Llama-3.1-8B-Instruct</option>
                <option value="meta-llama/Llama-3.1-8B-Instruct:novita">meta-llama/Llama-3.1-8B-Instruct:novita</option>
                <option value="qwen/qwen3.8-27b">qwen/qwen3.8-27b</option>
              </select>
              <label className="settings-label">API KEY</label>
              <div className="settings-input-group">
                <input 
                  type={showSecrets["llm1_api_key"] ? "text" : "password"} 
                  className="settings-input" 
                  placeholder="Enter your API Key"
                  value={userSettings.llm_values?.llm1_api_key || ""}
                  onChange={e => handleFieldChange("llm1_api_key", e.target.value, "llm")}
                />
                <div className="settings-input-group-icon" onClick={() => toggleSecret("llm1_api_key")} style={{ cursor: "pointer" }}>
                  {showSecrets["llm1_api_key"] ? <FaEyeSlash /> : <FaEye />}
                </div>
              </div>
            </div>
            
            <div>
              <h4 style={{ fontSize: "16px", fontWeight: 700, margin: "0 0 16px 0", color: "#0f172a" }}>LLM 2</h4>
              <label className="settings-label">MODEL</label>
              <select 
                className="settings-select" 
                style={{ marginBottom: "16px" }}
                value={userSettings.llm_values?.llm2_model || ""}
                onChange={e => handleFieldChange("llm2_model", e.target.value, "llm")}
              >
                <option value="">Select Model</option>
                <option value="gpt-4o">gpt-4o</option>
                <option value="claude-3.5-sonnet">claude-3.5-sonnet</option>
                <option value="meta-llama/Llama-3.1-8B-Instruct">meta-llama/Llama-3.1-8B-Instruct</option>
                <option value="meta-llama/Llama-3.1-8B-Instruct:novita">meta-llama/Llama-3.1-8B-Instruct:novita</option>
                <option value="qwen/qwen3.8-27b">qwen/qwen3.8-27b</option>
              </select>
              <label className="settings-label">API KEY</label>
              <div className="settings-input-group">
                <input 
                  type={showSecrets["llm2_api_key"] ? "text" : "password"} 
                  className="settings-input" 
                  placeholder="Enter your API Key"
                  value={userSettings.llm_values?.llm2_api_key || ""}
                  onChange={e => handleFieldChange("llm2_api_key", e.target.value, "llm")}
                />
                <div className="settings-input-group-icon" onClick={() => toggleSecret("llm2_api_key")} style={{ cursor: "pointer" }}>
                  {showSecrets["llm2_api_key"] ? <FaEyeSlash /> : <FaEye />}
                </div>
              </div>
                      </div>
        </div>
      );
    }
  };

  return (
    <div className="settings-page-container">
      {toastMessage && (
        <div style={{
          position: "fixed",
          top: "32px",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 9999,
          backgroundColor: toastMessage.type === "success" ? "#10b981" : "#ef4444",
          color: "white",
          padding: "14px 28px",
          borderRadius: "8px",
          boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
          display: "flex",
          alignItems: "center",
          gap: "12px",
          fontSize: "1rem",
          fontWeight: 600,
          transition: "all 0.3s ease-in-out",
          animation: "toast-slide-down 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards"
        }}>
          {toastMessage.type === "success" ? <FaCheckCircle size={20} /> : <FaTimesCircle size={20} />}
          {toastMessage.text}
        </div>
      )}
      <style>{`
        @keyframes toast-slide-down {
          0% { opacity: 0; transform: translate(-50%, -20px); }
          100% { opacity: 1; transform: translate(-50%, 0); }
        }
      `}</style>

      <aside className="settings-sidebar">
        <div style={{ marginBottom: "16px" }}>
        </div>
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`settings-sidebar-tab ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <tab.icon />
            {tab.label}
          </button>
        ))}
      </aside>

      <main className="settings-main-area">
        <header className="settings-header">
          <h1>Settings</h1>
          <button className="settings-save-btn" onClick={handleDeploy} disabled={isSaving || isLoading}>
            {isSaving ? <FaSpinner className="animate-spin" /> : "Save Configuration"}
          </button>
        </header>
        
        <div className="settings-scroll-content">
          {isLoading ? (
            <div style={{ padding: "40px", textAlign: "center", color: "#64748b" }}><FaSpinner className="animate-spin" /> Loading...</div>
          ) : (
            renderTabContent()
          )}
        </div>
      </main>
    </div>
  );
}
