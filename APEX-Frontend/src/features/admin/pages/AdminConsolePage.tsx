import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  getAdminSettings,
  updateAdminSettings,
  getUserSettings,
  updateUserSettings,
  testAdminGithubConnection,
  testUserGithubConnection,
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
  FaGithub,
  FaBrain,
  FaShieldAlt,
  FaEye,
  FaEyeSlash,
  FaArrowLeft,
  FaSyncAlt,
  FaCog,
  FaLink,
} from "react-icons/fa";
import QualityChecksSettings from "../components/QualityChecksSettings";
import UserQualityChecksSettings from "../components/UserQualityChecksSettings";
import { TestCasesAdminSettings } from "../components/TestCasesAdminSettings";
import { TestCasesUserSettings } from "../components/TestCasesUserSettings";
import { LlmAdminSettings } from "../components/LlmAdminSettings";
import { LlmUserSettings } from "../components/LlmUserSettings";
import "./AdminConsolePage.css";
 
const ADMIN_RAIL_TABS = [
  { id: "github", label: "GitHub", icon: FaGithub, category: "Infrastructure" },
  { id: "quality", label: "Quality Checks", icon: FaShieldAlt, category: "Validation" },
  { id: "testcases", label: "Test Cases", icon: FaShieldAlt, category: "Testing" },
  { id: "ai", label: "Intelligence", icon: FaBrain, category: "Cognitive" },
];
 
const USER_RAIL_TABS = [
  { id: "github", label: "GitHub", icon: FaGithub, category: "Personal Settings" },
  { id: "user_quality", label: "Quality Checks", icon: FaShieldAlt, category: "Personal Settings" },
  { id: "testcases", label: "Test Cases", icon: FaShieldAlt, category: "Personal Settings" },
  { id: "ai", label: "Intelligence", icon: FaBrain, category: "Personal Settings" },
];
 
const INITIAL_SETTINGS: SystemSettings = {
  github_token: "",
  github_api_base_url: "",
  github_target_owner: "",
  github_target_token: "",
  github_client_id: "",
  github_client_secret: "",
  github_callback_url: "",
  github_organization: "",
  github_default_branch: "",
  ollama_base_url: "",
  rag_enabled: false,
  sonarqube_host_url: "",
  sonarqube_token: "",
  fossa_api_key: "",
  jwt_secret_key: "",
  quality_checks_config: "",
};
 
const INITIAL_USER_SETTINGS: FullUserSettings = {
  github_config: {
    github_account: "",
    pat: "",
    pat_scope: "",
    repository: "",
    branch: "",
    user_access: "",
  },
  quality_checks_values: {}
};
 
export default function AdminConsolePage() {
  const navigate = useNavigate();
  const { currentUser } = useAuth();
 
  const isSuperAdmin = currentUser?.role === "SUPERADMIN";
 
  const [showSecrets, setShowSecrets] = useState<{ [key: string]: boolean }>({});
 
  // State for SUPERADMIN
  const [settings, setSettings] = useState<SystemSettings>(INITIAL_SETTINGS);
  // State for USER
  const [userSettings, setUserSettings] = useState<FullUserSettings>(INITIAL_USER_SETTINGS);
 
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
 
  const [availableRepos, setAvailableRepos] = useState<GithubRepo[]>([]);
  const [availableBranches, setAvailableBranches] = useState<GithubBranch[]>([]);
  const [isLoadingRepos, setIsLoadingRepos] = useState(false);
  const [isLoadingBranches, setIsLoadingBranches] = useState(false);
 
  useEffect(() => {
    async function fetchSettings() {
      try {
        setIsLoading(true);
        if (isSuperAdmin) {
          const data = await getAdminSettings();
          setSettings(data);
        } else {
          const userData = await getUserSettings();
          setUserSettings(userData);
          // Pass test cases flags into the settings object so TestCasesUserSettings can read them
          setSettings(prev => ({
            ...prev,
            ...(userData.system_test_cases_config || {})
          }));
        }
      } catch (err) {
        setError("Failed to load settings. Please check your permissions.");
        console.error("Failed to load settings:", err);
      } finally {
        setIsLoading(false);
      }
    }
    if (currentUser) {
      fetchSettings();
    }
  }, [isSuperAdmin, currentUser]);
 
  useEffect(() => {
    if (!isSuperAdmin && userSettings.github_config?.pat) {
      setIsLoadingRepos(true);
      fetchUserGithubRepos()
        .then(repos => setAvailableRepos(repos))
        .catch(err => console.error("Failed to fetch repos", err))
        .finally(() => setIsLoadingRepos(false));
    }
  }, [isSuperAdmin, userSettings.github_config?.pat]);
 
  useEffect(() => {
    if (!isSuperAdmin && userSettings.github_config?.repository && availableRepos.length > 0) {
      const selectedRepo = availableRepos.find(r => r.full_name === userSettings.github_config?.repository);
      if (selectedRepo && userSettings.github_config?.pat) {
        setIsLoadingBranches(true);
        fetchUserGithubBranches(selectedRepo.owner, selectedRepo.name)
          .then(branches => setAvailableBranches(branches))
          .catch(err => console.error("Failed to fetch branches", err))
          .finally(() => setIsLoadingBranches(false));
      }
    }
  }, [isSuperAdmin, userSettings.github_config?.repository, availableRepos, userSettings.github_config?.pat]);
 
  const toggleSecret = (id: string) => {
    setShowSecrets(prev => ({ ...prev, [id]: !prev[id] }));
  };
 
  const handleFieldChange = (key: keyof SystemSettings, value: string | boolean) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };
 
  const handleUserFieldChange = (key: keyof UserGitHubConfig, value: string) => {
    setUserSettings(prev => ({
      ...prev,
      github_config: { ...prev.github_config, [key]: value }
    }));
  };
 
  const handleUserSettingChange = (key: keyof FullUserSettings, value: any) => {
    setUserSettings(prev => ({ ...prev, [key]: value }));
  };
 
  const handleDeploy = async () => {
    setIsSaving(true);
    setError(null);
    try {
      if (isSuperAdmin) {
        await updateAdminSettings(settings);
      } else {
        await updateUserSettings(userSettings.github_config, userSettings.quality_checks_values, userSettings.test_cases_values, userSettings.llm_values);
        // Notify other components (e.g. chatbot) that settings have been saved
        window.dispatchEvent(new CustomEvent("javaapex:settings-saved"));
      }
    } catch (err) {
      setError("Failed to save configuration.");
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };
 
  const handleTestConnection = async () => {
    setIsSaving(true);
    setError(null);
    try {
      if (isSuperAdmin) {
        // Save first so test uses latest
        await updateAdminSettings(settings);
        const res = await testAdminGithubConnection();
        alert(res.message);
      } else {
        await updateUserSettings(userSettings.github_config, userSettings.quality_checks_values, userSettings.test_cases_values, userSettings.llm_values);
        // Notify other components that settings have been saved
        window.dispatchEvent(new CustomEvent("javaapex:settings-saved"));
        const res = await testUserGithubConnection();
        alert(res.message);
      }
    } catch (err: any) {
      setError(err.message || "Failed to test connection.");
    } finally {
      setIsSaving(false);
    }
  };
 
  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="admin-loading-state">
          <div className="spinner-modern"></div>
          <span>Fetching configuration...</span>
        </div>
      );
    }
 
    if (isSuperAdmin) {
      return (
        <div className="admin-content-stacked">
          {/* GitHub Section */}
          <div className="admin-config-card">
            <h3 className="card-heading-modern">
              <FaGithub style={{ color: "#2563eb", marginRight: "8px" }} />
              Platform GitHub Configuration
            </h3>
            <div className="field-grid-three">
              <div className="field-modern">
                <label className="label-modern">GitHub Client ID</label>
                <input
                  type="text"
                  className="input-modern"
                  value={settings.github_client_id || ""}
                  onChange={(e) => handleFieldChange("github_client_id", e.target.value)}
                />
              </div>
              <div className="field-modern">
                <label className="label-modern">GitHub Client Secret</label>
                <div className="input-wrap-modern">
                  <input
                    type={showSecrets["github_client_secret"] ? "text" : "password"}
                    className="input-modern"
                    value={settings.github_client_secret || ""}
                    onChange={(e) => handleFieldChange("github_client_secret", e.target.value)}
                  />
                  <div className="toggle-modern" onClick={() => toggleSecret("github_client_secret")}>
                    {showSecrets["github_client_secret"] ? <FaEyeSlash /> : <FaEye />}
                  </div>
                </div>
              </div>
              <div className="field-modern">
                <label className="label-modern">Callback / Redirect URL</label>
                <input
                  type="text"
                  className="input-modern"
                  value={settings.github_redirect_uri || ""}
                  onChange={(e) => handleFieldChange("github_redirect_uri", e.target.value)}
                />
              </div>
              <div className="field-modern">
                <label className="label-modern">GitHub Organization</label>
                <input
                  type="text"
                  className="input-modern"
                  value={settings.github_target_owner || ""}
                  onChange={(e) => handleFieldChange("github_target_owner", e.target.value)}
                />
              </div>
 
              <div className="field-modern">
                <label className="label-modern">Default Branch</label>
                <input
                  type="text"
                  className="input-modern"
                  value={settings.github_default_branch || ""}
                  onChange={(e) => handleFieldChange("github_default_branch", e.target.value)}
                />
              </div>
            </div>
            <div style={{ marginTop: "16px", display: "flex", gap: "12px", justifyContent: "flex-end" }}>
               <button className="deploy-btn-modern" onClick={handleTestConnection}>
                 Test Connection
               </button>
            </div>
          </div>
 
          {/* Quality Checks Section */}
          <div className="admin-config-card">
            <h3 className="card-heading-modern">
              <FaShieldAlt style={{ color: "#2563eb", marginRight: "8px" }} />
              Quality Checks Configuration
            </h3>
            <QualityChecksSettings
              configString={settings.quality_checks_config || ""}
              onChange={(newConfig) => handleFieldChange("quality_checks_config", newConfig)}
            />
          </div>
 
          {/* Test Cases Section */}
          <div className="admin-config-card">
            <TestCasesAdminSettings
              settings={settings}
              onChange={handleFieldChange}
            />
          </div>
 
          {/* AI / LLM Section */}
          <div className="admin-config-card">
            <LlmAdminSettings
              settings={settings}
              onChange={handleFieldChange}
            />
          </div>
         
          <div className="admin-config-card">
            <h3 className="card-heading-modern">
              <FaLink style={{ color: "#2563eb", marginRight: "8px" }} />
              Contextual RAG
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
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
    } else {
      // User Settings
      return (
        <div className="admin-content-stacked">
          {/* GitHub Section */}
          <div className="user-config-card">
            <h3 className="card-heading-modern">
              <FaGithub style={{ color: "#2563eb", marginRight: "8px" }} />
              Personal GitHub Settings
            </h3>
            <div className="field-grid-three">
              <div className="field-modern">
                <label className="label-modern">GitHub Account (Username)</label>
                <input
                  type="text"
                  className="input-modern"
                  value={userSettings.github_config.github_account || ""}
                  onChange={(e) => handleUserFieldChange("github_account", e.target.value)}
                />
              </div>
              <div className="field-modern">
                <label className="label-modern">Personal Access Token (PAT)</label>
                <div className="input-wrap-modern">
                  <input
                    type={showSecrets["pat"] ? "text" : "password"}
                    className="input-modern"
                    value={userSettings.github_config.pat || ""}
                    onChange={(e) => handleUserFieldChange("pat", e.target.value)}
                  />
                  <div className="toggle-modern" onClick={() => toggleSecret("pat")}>
                    {showSecrets["pat"] ? <FaEyeSlash /> : <FaEye />}
                  </div>
                </div>
              </div>
 
              <div className="field-modern">
                <label className="label-modern">Default Repository</label>
                <select
                  className="input-modern"
                  value={userSettings.github_config.repository || ""}
                  onChange={(e) => handleUserFieldChange("repository", e.target.value)}
                  disabled={isLoadingRepos || availableRepos.length === 0}
                >
                  <option value="">{isLoadingRepos ? "Loading..." : "Select Repository"}</option>
                  {availableRepos.map(repo => (
                    <option key={repo.id} value={repo.full_name}>{repo.full_name}</option>
                  ))}
                </select>
              </div>
              <div className="field-modern">
                <label className="label-modern">Default Branch</label>
                <select
                  className="input-modern"
                  value={userSettings.github_config.branch || ""}
                  onChange={(e) => handleUserFieldChange("branch", e.target.value)}
                  disabled={isLoadingBranches || availableBranches.length === 0}
                >
                  <option value="">{isLoadingBranches ? "Loading..." : "Select Branch"}</option>
                  {availableBranches.map(branch => (
                    <option key={branch.name} value={branch.name}>{branch.name}</option>
                  ))}
                </select>
              </div>
              <div className="field-modern">
                <label className="label-modern">Access Level</label>
                <select
                  className="input-modern"
                  value={userSettings.github_config.user_access || ""}
                  onChange={(e) => handleUserFieldChange("user_access", e.target.value)}
                >
                  <option value="">Select Access</option>
                  <option value="read">Read</option>
                  <option value="write">Write</option>
                </select>
              </div>
            </div>
            <div style={{ marginTop: "16px", display: "flex", gap: "12px", justifyContent: "flex-end" }}>
               <button className="deploy-btn-modern" onClick={handleTestConnection}>
                 Test Connection
               </button>
            </div>
          </div>
 
          {/* Quality Checks Section */}
          <UserQualityChecksSettings
            settings={userSettings}
            onChange={setUserSettings}
          />
 
          {/* Test Cases Section */}
          <div className="user-config-card">
            <TestCasesUserSettings
              settings={userSettings}
              adminSettings={settings}
              onChange={(key, value) => {
                setUserSettings((prev) => ({
                  ...prev,
                  [key]: value
                }));
              }}
            />
          </div>
 
          {/* AI / LLM Section */}
          <div className="user-config-card">
            <LlmUserSettings
              settings={userSettings}
              onChange={handleUserSettingChange}
              isAdminEnabled={
                userSettings.system_llm_config?.llm_enabled === true ||
                userSettings.system_llm_config?.llm_enabled === "true"
              }
              allowedGroqModelsStr={userSettings.system_llm_config?.groq_models}
              allowedHuggingFaceModelsStr={userSettings.system_llm_config?.huggingface_models}
            />
          </div>
        </div>
      );
    }
  };
 
  return (
    <div className="admin-console-layout">
      <main className="admin-main-surface">
        <header className="admin-main-header">
          <div className="header-title-group">
            <div className="header-symbol-wrap">
              <FaCog size={22} />
            </div>
            <div className="header-text-stack">
              <h2 className="header-heading">
                Settings
              </h2>
            </div>
          </div>
 
          <div className="header-actions">
            <button
              className="deploy-btn-modern"
              onClick={handleDeploy}
              disabled={isSaving || isLoading}
            >
              {isSaving ? (
                <>
                  <div className="spinner-small"></div>
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <span>Save Configuration</span>
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
 
        <div className="admin-scroll-canvas">
          {renderContent()}
        </div>
      </main>
    </div>
  );
}
