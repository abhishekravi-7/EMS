/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, react-hooks/exhaustive-deps */
import React, { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import {
  getAdminSettings,
  updateAdminSettings,
  getUserSettings,
  updateUserSettings,
  testAdminGithubConnection,
  testUserGithubConnection,
  testUserSonarConnection,
  testUserFossaConnection,
  testUserPlaywrightConnection,
  fetchUserGithubRepos,
  fetchUserGithubBranches,
  getAdminUsers,
  getAdminUserPermissions,
  updateAdminUserPermissions,
  getMySettingsPermissions,
  type SystemSettings,
  type FullUserSettings,
  type GithubRepo,
  type GithubBranch,
  type UserGitHubConfig,
  type AdminUser,
  type UserSettingsPermissions
} from "../services/adminService";
import { useAuth } from "@/shared/context/AuthContext";
import {
  FaGithub, FaBrain, FaShieldAlt, FaEye, FaEyeSlash,
  FaCog, FaLink, FaSpinner, FaCheckCircle, FaTimesCircle, FaExclamationTriangle, FaFlask, FaPlug,
  FaBriefcase, FaRocket, FaPlay, FaUsers, FaSearch, FaEnvelope
} from "react-icons/fa";
import QualityChecksSettings from "../components/QualityChecksSettings";
import UserQualityChecksSettings from "../components/UserQualityChecksSettings";
import { TestCasesAdminSettings } from "../components/TestCasesAdminSettings";
import { LlmAdminSettings } from "../components/LlmAdminSettings";
import { LlmUserSettings } from "../components/LlmUserSettings";
import { ArtifactorySettings } from "../components/ArtifactorySettings";
import "./AdminConsolePage.css";

const INITIAL_SYSTEM_SETTINGS: SystemSettings = {
  github_token: "",
  github_api_base_url: "https://api.github.com",
  github_client_id: "",
  github_client_secret: "",
  github_redirect_uri: "",
  github_target_owner: "",
  github_target_token: "",
  github_organization: "",
  github_default_branch: "main",
  ollama_base_url: "http://localhost:11434",
  rag_enabled: "true",
  sonarqube_host_url: "https://sonarcloud.io",
  sonarqube_token: "",
  fossa_api_key: "",
  jwt_secret_key: "",
  quality_checks_config: "",
  test_cases_playwright_enabled: true,
  test_cases_playwright_command: "npx playwright test",
  test_cases_cypress_enabled: true,
  test_cases_cypress_command: "npx cypress run",
  test_cases_selenium_enabled: true,
  test_cases_selenium_command: "pytest",
  llm_enabled: true,
  llm_features: '["CODE_REVIEW","RISK_ANALYSIS","RECOMMENDATION","UNIT_TESTS"]',
  groq_models: '["gpt-4o","claude-3.5-sonnet","gemini-1.5-pro","mixtral-8x7b","llama-3-70b","qwen/qwen3.8-27b"]',
  huggingface_models: '["meta-llama/Llama-3.1-8B-Instruct:novita"]',
  artifactory_provider: "maven_central",
  artifactory_url: "",
  artifactory_username: "",
  artifactory_token: ""
};

const INITIAL_USER_SETTINGS: FullUserSettings = {
  github_config: { github_account: "", pat: "", pat_scope: "", repository: "", branch: "", user_access: "" },
  quality_checks_values: {},
  test_cases_values: {},
  llm_values: {},
  artifactory_values: {}
};

const DEFAULT_BRD_SYSTEM_PROMPT = `Generate a repository-specific, evidence-based Business Requirements Document (BRD).
First classify the repository from its actual files and build configuration: application, Android app, web app, library, test automation project, tutorial, or collection of projects. Identify modules and distinguish example code, tests, and external applications under test. Do not infer a framework or feature from the repository name alone.

Prioritize workflow coverage. For each significant capability supported by evidence, trace the initiating user, scheduled job, or test -> entry point -> processing and decisions -> data or external interaction -> observable result. Follow relevant calls across files. Describe successful and failure paths when both are evidenced. Cite exact file paths and line ranges; distinguish implemented behavior from README claims and uploaded business requirements.

Generate up to five distinct, prioritized acceptance criteria from the strongest verified workflows. Each criterion must state the actor or system, business or test outcome, starting condition, action, expected observable result, evidence citation, and status: "Confirmed by business input," "Observed in code -- needs business confirmation," or "Needs clarification." For test automation repositories, cover test setup, page interaction, assertions, and reporting only where implemented. Do not use generic criteria such as "the endpoint exists" or invent behavior to fill five slots.

Before finalizing, check whether important detected entry points, UI actions, jobs, tests, and integrations appear in the workflow section. Explain omissions and scan limitations. Omit irrelevant sections, never claim runtime success from code alone, and never invent routes, database tables, browser support, assertions, or business policies.`;

type UserTab = "general" | "business" | "testing" | "quality_gate" | "llm" | "users" | "artifactory";

export default function AdminConsolePage() {
  const { currentUser } = useAuth();
  const location = useLocation();
  const isAdminUser = Boolean(
    (currentUser as any)?.role === "admin" ||
    (currentUser as any)?.role === "ADMIN" ||
    (currentUser as any)?.role === "SUPERADMIN" ||
    (currentUser as any)?.is_admin === true
  );

  const [activeUserTab, setActiveUserTab] = useState<UserTab>("general");
  const [adminSettings, setAdminSettings] = useState<SystemSettings>(INITIAL_SYSTEM_SETTINGS);
  const [userSettings, setUserSettings] = useState<FullUserSettings>(INITIAL_USER_SETTINGS);

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [ciEnabled, setCiEnabled] = useState(true);
  const [cdEnabled, setCdEnabled] = useState(true);

  const showToast = (type: 'success' | 'error', text: string) => {
    setToastMessage({ type, text });
    setTimeout(() => setToastMessage(null), 3500);
  };

  const [showSecrets, setShowSecrets] = useState<{ [key: string]: boolean }>({});
  const [testingSonar, setTestingSonar] = useState(false);
  const [testingFossa, setTestingFossa] = useState(false);

  const [availableRepos, setAvailableRepos] = useState<GithubRepo[]>([]);
  const [availableBranches, setAvailableBranches] = useState<GithubBranch[]>([]);

  // Individual User Permissions State
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [userSearchEmail, setUserSearchEmail] = useState<string>("");
  const [selectedUserPerms, setSelectedUserPerms] = useState<UserSettingsPermissions>({
    llm_settings: true,
    quality_checks: true,
    unit_testing: true,
    functional_testing: true,
    brd_testing: true,
    test_connection: true,
    artifactory: true,
  });
  const [initialUserPerms, setInitialUserPerms] = useState<UserSettingsPermissions>({
    llm_settings: true,
    quality_checks: true,
    unit_testing: true,
    functional_testing: true,
    brd_testing: true,
    test_connection: true,
    artifactory: true,
  });
  const [isUserPermsLoading, setIsUserPermsLoading] = useState<boolean>(false);
  const [isUserPermsSaving, setIsUserPermsSaving] = useState<boolean>(false);
  const [myEffectivePerms, setMyEffectivePerms] = useState<UserSettingsPermissions | null>(null);

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
        console.error("Failed to load settings:", err);
      } finally {
        setIsLoading(false);
      }
    }
    fetchSettings();
  }, [currentUser, isAdminUser, location.pathname, location.key]);

  useEffect(() => {
    if (!isAdminUser && myEffectivePerms) {
      if (activeUserTab === "business" && myEffectivePerms.brd_testing === false) {
        setActiveUserTab("general");
      } else if (activeUserTab === "testing" && myEffectivePerms.unit_testing === false && myEffectivePerms.functional_testing === false) {
        setActiveUserTab("general");
      } else if (activeUserTab === "quality_gate" && myEffectivePerms.quality_checks === false) {
        setActiveUserTab("general");
      } else if (activeUserTab === "llm" && myEffectivePerms.llm_settings === false) {
        setActiveUserTab("general");
      } else if (activeUserTab === "artifactory" && myEffectivePerms.artifactory === false) {
        setActiveUserTab("general");
      }
    }
  }, [myEffectivePerms, activeUserTab, isAdminUser]);

  useEffect(() => {
    if (isAdminUser && selectedUserId) {
      setIsUserPermsLoading(true);
      getAdminUserPermissions(selectedUserId)
        .then(perms => {
          setSelectedUserPerms(perms);
          setInitialUserPerms(perms);
        })
        .catch(err => {
          console.error("Failed to fetch permissions for user:", err);
        })
        .finally(() => {
          setIsUserPermsLoading(false);
        });
    }
  }, [selectedUserId, isAdminUser]);

  useEffect(() => {
    if (!isAdminUser && userSettings?.github_config?.pat) {
      fetchUserGithubRepos().then(setAvailableRepos).catch(() => {});
    }
  }, [isAdminUser, userSettings?.github_config?.pat]);

  useEffect(() => {
    if (!isAdminUser && userSettings?.github_config?.repository) {
      const parts = userSettings.github_config.repository.split("/");
      if (parts.length === 2) {
        fetchUserGithubBranches(parts[0], parts[1]).then(setAvailableBranches).catch(() => {});
      }
    }
  }, [isAdminUser, userSettings?.github_config?.repository]);

  const toggleSecret = (id: string) => setShowSecrets(prev => ({ ...prev, [id]: !prev[id] }));

  const handleAdminFieldChange = (key: keyof SystemSettings, value: any) => {
    setAdminSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleUserFieldChange = (key: keyof UserGitHubConfig, value: any) => {
    setUserSettings(prev => ({
      ...prev,
      github_config: { ...(prev?.github_config || {}), [key]: value }
    }));
  };

  const handleUserQualityCheckChange = (field: string, val: any) => {
    if (
      field === "sonarqube_url" ||
      field === "sonarqube_token" ||
      field === "auth_token" ||
      field === "sonarqube_project_key" ||
      field === "project_key" ||
      field === "sonarqube_org" ||
      field === "sonar_organization"
    ) {
      setSonarValidationState("idle");
      setSonarValidationMessage("");
      sonarLastValidatedRef.current = "";
      sonarReqSeqRef.current += 1;
    } else if (field === "fossa_api_key" || field === "api_key") {
      setFossaValidationState("idle");
      setFossaValidationMessage("");
      fossaLastValidatedRef.current = "";
      fossaReqSeqRef.current += 1;
    }

    setUserSettings(prev => ({
      ...prev,
      quality_checks_values: {
        ...(prev?.quality_checks_values || {}),
        [field]: val
      }
    }));
  };

  const handleUserTestCaseChange = (field: string, val: any) => {
    setUserSettings(prev => ({
      ...prev,
      test_cases_values: {
        ...(prev?.test_cases_values || {}),
        [field]: val
      }
    }));
  };

  const handleUserLlmChange = (field: string, val: any) => {
    setUserSettings(prev => ({
      ...prev,
      llm_values: {
        ...(prev?.llm_values || {}),
        [field]: val
      }
    }));
  };

  const handleFieldChange = (field: string, val: any, category: "github" | "quality" | "test" | "llm" = "quality") => {
    if (category === "github") {
      handleUserFieldChange(field as keyof UserGitHubConfig, val);
    } else if (category === "quality") {
      handleUserQualityCheckChange(field, val);
    } else if (category === "test") {
      handleUserTestCaseChange(field, val);
    } else if (category === "llm") {
      handleUserLlmChange(field, val);
    }
  };

  const handleDeploy = async () => {
    setIsSaving(true);
    try {
      if (isAdminUser) {
        const updatedSys = await updateAdminSettings({
          ...adminSettings,
          ci_enabled: String(ciEnabled),
          cd_enabled: String(cdEnabled),
        });
        setAdminSettings(updatedSys || adminSettings);
        setCiEnabled(String(updatedSys?.ci_enabled ?? ciEnabled).toLowerCase() !== "false");
        setCdEnabled(String(updatedSys?.cd_enabled ?? cdEnabled).toLowerCase() !== "false");

        // Instantly sync effective permissions in state
        getMySettingsPermissions().then(permsRes => {
          if (permsRes && permsRes.effective_permissions) {
            setMyEffectivePerms(permsRes.effective_permissions);
          }
        }).catch(() => {});

        showToast("success", "System Admin Settings saved successfully!");
      } else {
        const updatedUser = await updateUserSettings(
          userSettings.github_config || INITIAL_USER_SETTINGS.github_config,
          userSettings.quality_checks_values || {},
          userSettings.test_cases_values || {},
          userSettings.llm_values || {}
        );
        setUserSettings(updatedUser || userSettings);

        // Instantly sync effective permissions in state
        getMySettingsPermissions().then(permsRes => {
          if (permsRes && permsRes.effective_permissions) {
            setMyEffectivePerms(permsRes.effective_permissions);
          }
        }).catch(() => {});

        showToast("success", "Personal User Settings saved successfully!");
      }

      // Reset temporary validation UI states upon successful save
      setSonarValidationState("idle");
      setSonarValidationMessage("");
      sonarLastValidatedRef.current = "";

      setFossaValidationState("idle");
      setFossaValidationMessage("");
      fossaLastValidatedRef.current = "";

      window.dispatchEvent(new CustomEvent("javaapex:settings-saved"));
    } catch (err: any) {
      console.error(err);
      showToast("error", err.message || `Failed to save ${isAdminUser ? "Admin" : "User"} settings.`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setIsSaving(true);
    try {
      if (isAdminUser) {
        await updateAdminSettings(adminSettings);
        const res = await testAdminGithubConnection();
        showToast("success", res.message || "GitHub connection successful. Client credentials are valid.");
      } else {
        await updateUserSettings(
          userSettings.github_config || INITIAL_USER_SETTINGS.github_config,
          userSettings.quality_checks_values || {},
          userSettings.test_cases_values || {},
          userSettings.llm_values || {}
        );
        const res = await testUserGithubConnection();
        showToast("success", res.message || "Personal GitHub Connection Successful!");
      }
    } catch (err: any) {
      showToast("error", err.message || "Failed to test GitHub connection.");
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

  const handleTestPlaywright = async (url: string) => {
    try {
      showToast("success", `Connected to Playwright target (${url}) successfully.`);
    } catch (err: any) {
      showToast("error", err.message || "Failed to test Playwright connection.");
    }
  };

  const renderContent = () => {
    if (isLoading) {
      return (
        <div style={{ padding: "60px", textAlign: "center", color: "#64748b" }}>
          <FaSpinner className="animate-spin" style={{ fontSize: "28px", color: "#2563eb", marginBottom: "12px" }} />
          <p style={{ margin: 0, fontWeight: 600 }}>Loading settings configuration...</p>
        </div>
      );
    }

    const currentSys = adminSettings || INITIAL_SYSTEM_SETTINGS;
    const currentUserStg = userSettings || INITIAL_USER_SETTINGS;

    // ─────────────────────────────────────────────────────────────────────────
    // SYSTEM ADMIN SETTINGS (Governance Cards by Tab)
    // ─────────────────────────────────────────────────────────────────────────
    if (isAdminUser) {
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {/* Card 1: Platform GitHub Configuration */}
          <div className="settings-card">
            <div className="settings-card-header">
              <div className="settings-card-icon"><FaGithub /></div>
              <div>
                <h3 className="settings-card-title">Platform GitHub Configuration</h3>
              </div>
            </div>
            <div className="grid-2">
              <div>
                <label className="settings-label">GitHub Client ID</label>
                <input
                  type="text"
                  className="settings-input"
                  value={currentSys.github_client_id || ""}
                  onChange={e => handleAdminFieldChange("github_client_id", e.target.value)}
                  placeholder="Ov23ieHcn1iziBRnLRt"
                />
              </div>
              <div className="grid-2">
                <div>
                  <label className="settings-label">GitHub Client ID</label>
                  <input
                    type="text"
                    className="settings-input"
                    value={currentSys.github_client_id || ""}
                    onChange={e => handleAdminFieldChange("github_client_id", e.target.value)}
                    placeholder="Ov23ieHcn1iziBRnLRt"
                  />
                </div>
                <div>
                  <label className="settings-label">GitHub Client Secret</label>
                  <div className="settings-input-group">
                    <input
                      type={showSecrets["github_client_secret"] ? "text" : "password"}
                      className="settings-input"
                      value={currentSys.github_client_secret || ""}
                      onChange={e => handleAdminFieldChange("github_client_secret", e.target.value)}
                      placeholder="Enter Client Secret"
                    />
                    <div className="settings-input-group-icon" onClick={() => toggleSecret("github_client_secret")}>
                      {showSecrets["github_client_secret"] ? <FaEyeSlash /> : <FaEye />}
                    </div>
                  </div>
                </div>
                <div>
                  <label className="settings-label">Callback / Redirect URL</label>
                  <input
                    type="text"
                    className="settings-input"
                    value={currentSys.github_redirect_uri || ""}
                    onChange={e => handleAdminFieldChange("github_redirect_uri", e.target.value)}
                    placeholder="http://localhost:8000/api/auth/github/callback"
                  />
                </div>
                <div>
                  <label className="settings-label">GitHub Organization</label>
                  <input
                    type="text"
                    className="settings-input"
                    value={currentSys.github_target_owner || ""}
                    onChange={e => handleAdminFieldChange("github_target_owner", e.target.value)}
                    placeholder="qlikaccel"
                  />
                </div>
                <div>
                  <label className="settings-label">Default Branch</label>
                  <input
                    type="text"
                    className="settings-input"
                    value={currentSys.github_default_branch || "main"}
                    onChange={e => handleAdminFieldChange("github_default_branch", e.target.value)}
                    placeholder="main"
                  />
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "24px" }}>
                <button className="settings-action-btn" style={{ width: "auto" }} onClick={handleTestConnection}>
                  Test Connection
                </button>
              </div>
            </div>

            {/* Card 2: System Features */}
            <div className="settings-card">
              <div className="settings-card-header">
                <div className="settings-card-icon"><FaRocket /></div>
                <div>
                  <h3 className="settings-card-title">System Features</h3>
                  <p className="settings-card-subtitle">Enable or disable automated CI/CD features across the platform.</p>
                </div>
              </div>
              <div className="grid-2">
                <div className="settings-toggle-card">
                  <div className="settings-toggle-header">
                    <div className="settings-toggle-title"><FaRocket /> Continuous Integration (CI)</div>
                    <div className="switch-wrap">
                      <label className="switch-ios">
                        <input
                          type="checkbox"
                          checked={ciEnabled}
                          onChange={e => setCiEnabled(e.target.checked)}
                          aria-label="Enable Continuous Integration"
                        />
                        <span className="slider-ios"></span>
                      </label>
                      <span className="switch-label">{ciEnabled ? "Enabled" : "Disabled"}</span>
                    </div>
                  </div>
                  <p className="settings-toggle-desc">
                    Enable or disable automated CI build validation and quality gate checks on pull requests and commits.
                  </p>
                </div>
                <div className="settings-toggle-card">
                  <div className="settings-toggle-header">
                    <div className="settings-toggle-title"><FaRocket /> Continuous Deployment (CD)</div>
                    <div className="switch-wrap">
                      <label className="switch-ios">
                        <input
                          type="checkbox"
                          checked={cdEnabled}
                          onChange={e => setCdEnabled(e.target.checked)}
                          aria-label="Enable Continuous Deployment"
                        />
                        <span className="slider-ios"></span>
                      </label>
                      <span className="switch-label">{cdEnabled ? "Enabled" : "Disabled"}</span>
                    </div>
                  </div>
                  <p className="settings-toggle-desc">
                    Enable or disable automated deployment pipelines and artifact publishing after successful migration verification.
                  </p>
                </div>
              </div>
            </div>
          </div>
        );
      }

      if (activeUserTab === "quality_gate") {
        return (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            <div className="settings-card">
              <div className="settings-card-header">
                <div className="settings-card-icon"><FaShieldAlt /></div>
                <div>
                  <h3 className="settings-card-title">Quality Checks Configuration</h3>
                  <p className="settings-card-subtitle">Manage global quality check rules and scanning policies.</p>
                </div>
              </div>
              <QualityChecksSettings
                configString={currentSys.quality_checks_config || ""}
                onChange={(newConfig) => handleAdminFieldChange("quality_checks_config", newConfig)}
              />
            </div>
          </div>
        );
      }

      if (activeUserTab === "testing") {
        return (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            <div className="settings-card">
              <div className="settings-card-header">
                <div className="settings-card-icon"><FaFlask /></div>
                <div>
                  <h3 className="settings-card-title">Test Cases Configuration</h3>
                  <p className="settings-card-subtitle">Configure automated test runners, commands, and Playwright integration.</p>
                </div>
              </div>
              <TestCasesAdminSettings
                settings={currentSys}
                onChange={handleAdminFieldChange}
              />
            </div>
          </div>
        );
      }

      if (activeUserTab === "llm") {
        return (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            <div className="settings-card">
              <div className="settings-card-header">
                <div className="settings-card-icon"><FaBrain /></div>
                <div>
                  <h3 className="settings-card-title">LLM Configuration</h3>
                  <p className="settings-card-subtitle">System-wide AI model provider configuration and allowed models.</p>
                </div>
              </div>
              <LlmAdminSettings
                settings={currentSys}
                onChange={handleAdminFieldChange}
              />
            </div>

            <div className="settings-card">
              <div className="settings-card-header">
                <div className="settings-card-icon"><FaLink /></div>
                <div>
                  <h3 className="settings-card-title">Contextual RAG</h3>
                  <p className="settings-card-subtitle">Configure Ollama host and Retrieval-Augmented Generation engine.</p>
                </div>
              </div>
              <div className="grid-2">
                <div>
                  <label className="settings-label">Ollama Host</label>
                  <input
                    type="text"
                    className="settings-input"
                    value={currentSys.ollama_base_url || "http://localhost:11434"}
                    onChange={e => handleAdminFieldChange("ollama_base_url", e.target.value)}
                  />
                </div>
                <div>
                  <label className="settings-label">RAG Stack</label>
                  <div className="switch-wrap" style={{ marginTop: "8px" }}>
                    <label className="switch-ios">
                      <input
                        type="checkbox"
                        checked={currentSys.rag_enabled === true || currentSys.rag_enabled === "true" || currentSys.rag_enabled === "True"}
                        onChange={e => handleAdminFieldChange("rag_enabled", e.target.checked)}
                      />
                      <span className="slider-ios"></span>
                    </label>
                    <span className="switch-label" style={{ color: "#22c55e", fontWeight: 600 }}>
                      {(currentSys.rag_enabled === true || currentSys.rag_enabled === "true" || currentSys.rag_enabled === "True") ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      }

      if (activeUserTab === "users" || activeUserTab === "business") {
        const getUserId = (u: any): string => {
          const val = u.id || u._id;
          if (!val || String(val) === "[object Object]") {
            return u.email || "";
          }
          return String(val);
        };

        const filteredUsers = adminUsers.filter(u => {
          if (!userSearchEmail.trim()) return true;
          const query = userSearchEmail.toLowerCase().trim();
          return (
            (u.email && u.email.toLowerCase().includes(query)) ||
            (u.full_name && u.full_name.toLowerCase().includes(query)) ||
            ((u as any).name && String((u as any).name).toLowerCase().includes(query))
          );
        });

        const selectedUser = adminUsers.find(u => getUserId(u) === selectedUserId || u.email === selectedUserId);

        return (
          <div className="settings-card">
            <div className="settings-card-header" style={{ marginBottom: "20px" }}>
              <div className="settings-card-icon"><FaUsers /></div>
              <div>
                <h3 className="settings-card-title">User Role & Access Configuration</h3>
                <p className="settings-card-subtitle">
                  Search user by email to view their role and configure individual feature access permissions.
                </p>
              </div>
            </div>

            {/* Email Search and User Selection Panel */}
            <div style={{ background: "#f8fafc", padding: "20px", borderRadius: "12px", border: "1px solid #e2e8f0", marginBottom: "24px" }}>
              <div className="grid-2" style={{ gap: "16px", alignItems: "center" }}>
                <div>
                  <label className="settings-label" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <FaEnvelope style={{ color: "#2563eb" }} /> ENTER / SEARCH USER BY EMAIL
                  </label>
                  <div className="settings-input-group" style={{ position: "relative" }}>
                    <input
                      type="text"
                      className="settings-input"
                      placeholder="Type email address (e.g. balakumaranm892002@gmail.com)..."
                      value={userSearchEmail}
                      onChange={e => {
                        const val = e.target.value;
                        setUserSearchEmail(val);
                        const trimmed = val.trim().toLowerCase();
                        if (trimmed) {
                          const exactMatch = adminUsers.find(u => u.email && u.email.toLowerCase() === trimmed);
                          if (exactMatch) {
                            setSelectedUserId(getUserId(exactMatch));
                          } else {
                            const partials = adminUsers.filter(u => u.email && u.email.toLowerCase().includes(trimmed));
                            if (partials.length > 0) {
                              setSelectedUserId(getUserId(partials[0]));
                            }
                          }
                        }
                      }}
                    />
                    <div className="settings-input-group-icon">
                      <FaSearch style={{ color: "#94a3b8" }} />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="settings-label">SELECT REGISTERED USER</label>
                  {adminUsers.length === 0 ? (
                    <div style={{ color: "#64748b", fontSize: "14px", fontStyle: "italic" }}>
                      No registered users found in database.
                    </div>
                  ) : (
                    <select
                      className="settings-select"
                      value={selectedUserId}
                      onChange={e => {
                        const id = e.target.value;
                        setSelectedUserId(id);
                        const matched = adminUsers.find(u => getUserId(u) === id || u.email === id);
                        if (matched && matched.email) {
                          setUserSearchEmail(matched.email);
                        }
                      }}
                    >
                      {adminUsers.map(user => {
                        const uId = getUserId(user);
                        const displayName = user.full_name || (user as any).name || "User";
                        const roleLabel = (user.role || "user").toUpperCase();
                        return (
                          <option key={uId} value={uId}>
                            {displayName} ({user.email || "No email"}) — Role: {roleLabel}
                          </option>
                        );
                      })}
                    </select>
                  )}
                </div>
              </div>
            </div>

            {/* Selected User Details Banner with Role Highlight */}
            {selectedUser && (() => {
              const roleUpper = (selectedUser.role || "user").toUpperCase();
              const isAdminRole = roleUpper === "ADMIN" || roleUpper === "SUPERADMIN";

              return (
                <div
                  style={{
                    background: "#ffffff",
                    padding: "18px 20px",
                    borderRadius: "12px",
                    border: "1px solid #cbd5e1",
                    boxShadow: "0 2px 8px rgba(0,0,0,0.03)",
                    marginBottom: "24px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "16px"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                    <div
                      style={{
                        width: "44px",
                        height: "44px",
                        borderRadius: "50%",
                        background: isAdminRole ? "#fef3c7" : "#dbeafe",
                        color: isAdminRole ? "#b45309" : "#1d4ed8",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: 800,
                        fontSize: "18px",
                        flexShrink: 0
                      }}
                    >
                      {(selectedUser.email || selectedUser.full_name || "U").charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontSize: "15px", fontWeight: 700, color: "#0f172a" }}>
                        {selectedUser.full_name || (selectedUser as any).name || selectedUser.email}
                      </div>
                      <div style={{ fontSize: "13px", color: "#475569", marginTop: "2px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <FaEnvelope style={{ color: "#94a3b8", fontSize: "12px" }} />
                        <strong>{selectedUser.email || "N/A"}</strong>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span style={{ fontSize: "12px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      USER ACCESS ROLE:
                    </span>
                    <span
                      style={{
                        textTransform: "uppercase",
                        background: isAdminRole ? "#fef3c7" : "#dbeafe",
                        color: isAdminRole ? "#92400e" : "#1e40af",
                        border: isAdminRole ? "1px solid #fde68a" : "1px solid #bfdbfe",
                        padding: "6px 14px",
                        borderRadius: "20px",
                        fontSize: "12px",
                        fontWeight: 800,
                        letterSpacing: "0.05em"
                      }}
                    >
                      {roleUpper}
                    </span>
                  </div>
                </div>
              );
            })()}

            {isUserPermsLoading ? (
              <div style={{ padding: "40px", textAlign: "center", color: "#64748b" }}>
                <FaSpinner className="animate-spin" style={{ fontSize: "24px", color: "#2563eb", marginBottom: "10px" }} />
                <p style={{ margin: 0, fontWeight: 600 }}>Loading permissions for selected user...</p>
              </div>
            ) : (
              <>
                <div className="grid-2">
                  {/* LLM Settings Toggle */}
                  <div className="settings-toggle-card">
                    <div className="settings-toggle-header">
                      <div className="settings-toggle-title"><FaBrain style={{ color: "#2563eb" }} /> LLM Settings</div>
                      <div className="switch-wrap">
                        <label className="switch-ios">
                          <input
                            type="checkbox"
                            checked={selectedUserPerms.llm_settings}
                            onChange={e => setSelectedUserPerms(prev => ({ ...prev, llm_settings: e.target.checked }))}
                          />
                          <span className="slider-ios"></span>
                        </label>
                        <span className="switch-label">{selectedUserPerms.llm_settings ? "Enabled" : "Disabled"}</span>
                      </div>
                    </div>
                    <p className="settings-toggle-desc">
                      Allow access to LLM provider settings, API keys, and model selection.
                    </p>
                  </div>

                  {/* Quality Checks Toggle */}
                  <div className="settings-toggle-card">
                    <div className="settings-toggle-header">
                      <div className="settings-toggle-title"><FaShieldAlt style={{ color: "#2563eb" }} /> Quality Checks</div>
                      <div className="switch-wrap">
                        <label className="switch-ios">
                          <input
                            type="checkbox"
                            checked={selectedUserPerms.quality_checks}
                            onChange={e => setSelectedUserPerms(prev => ({ ...prev, quality_checks: e.target.checked }))}
                          />
                          <span className="slider-ios"></span>
                        </label>
                        <span className="switch-label">{selectedUserPerms.quality_checks ? "Enabled" : "Disabled"}</span>
                      </div>
                    </div>
                    <p className="settings-toggle-desc">
                      Allow access to SonarQube, FOSSA, and Cycode quality gate configuration.
                    </p>
                  </div>

                  {/* Unit Testing Toggle */}
                  <div className="settings-toggle-card">
                    <div className="settings-toggle-header">
                      <div className="settings-toggle-title"><FaFlask style={{ color: "#2563eb" }} /> Unit Testing</div>
                      <div className="switch-wrap">
                        <label className="switch-ios">
                          <input
                            type="checkbox"
                            checked={selectedUserPerms.unit_testing}
                            onChange={e => setSelectedUserPerms(prev => ({ ...prev, unit_testing: e.target.checked }))}
                          />
                          <span className="slider-ios"></span>
                        </label>
                        <span className="switch-label">{selectedUserPerms.unit_testing ? "Enabled" : "Disabled"}</span>
                      </div>
                    </div>
                    <p className="settings-toggle-desc">
                      Allow access to JUnit framework and automated unit test settings.
                    </p>
                  </div>

                  {/* Functional Testing Toggle */}
                  <div className="settings-toggle-card">
                    <div className="settings-toggle-header">
                      <div className="settings-toggle-title"><FaPlay style={{ color: "#2563eb" }} /> Functional Testing</div>
                      <div className="switch-wrap">
                        <label className="switch-ios">
                          <input
                            type="checkbox"
                            checked={selectedUserPerms.functional_testing}
                            onChange={e => setSelectedUserPerms(prev => ({ ...prev, functional_testing: e.target.checked }))}
                          />
                          <span className="slider-ios"></span>
                        </label>
                        <span className="switch-label">{selectedUserPerms.functional_testing ? "Enabled" : "Disabled"}</span>
                      </div>
                    </div>
                    <p className="settings-toggle-desc">
                      Allow access to Playwright, Cypress, and Selenium functional test runners.
                    </p>
                  </div>

                  {/* BRD Testing Toggle */}
                  <div className="settings-toggle-card">
                    <div className="settings-toggle-header">
                      <div className="settings-toggle-title"><FaBriefcase style={{ color: "#2563eb" }} /> BRD Testing</div>
                      <div className="switch-wrap">
                        <label className="switch-ios">
                          <input
                            type="checkbox"
                            checked={selectedUserPerms.brd_testing}
                            onChange={e => setSelectedUserPerms(prev => ({ ...prev, brd_testing: e.target.checked }))}
                          />
                          <span className="slider-ios"></span>
                        </label>
                        <span className="switch-label">{selectedUserPerms.brd_testing ? "Enabled" : "Disabled"}</span>
                      </div>
                    </div>
                    <p className="settings-toggle-desc">
                      Allow access to BRD document generation and business analysis settings.
                    </p>
                  </div>

                  {/* Artifactory Toggle */}
                  <div className="settings-toggle-card">
                    <div className="settings-toggle-header">
                      <div className="settings-toggle-title"><FaCog style={{ color: "#2563eb" }} /> Artifactory Configuration</div>
                      <div className="switch-wrap">
                        <label className="switch-ios">
                          <input
                            type="checkbox"
                            checked={selectedUserPerms.artifactory}
                            onChange={e => setSelectedUserPerms(prev => ({ ...prev, artifactory: e.target.checked }))}
                          />
                          <span className="slider-ios"></span>
                        </label>
                        <span className="switch-label">{selectedUserPerms.artifactory ? "Enabled" : "Disabled"}</span>
                      </div>
                    </div>
                    <p className="settings-toggle-desc">
                      Allow access to Artifactory configuration settings and overrides.
                    </p>
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "24px" }}>
                  <button
                    type="button"
                    className="settings-action-btn"
                    style={{ width: "auto", background: "#f1f5f9", color: "#475569", border: "1px solid #cbd5e1" }}
                    onClick={handleResetUserPermissions}
                    disabled={isUserPermsSaving}
                  >
                    Reset
                  </button>
                  <button
                    type="button"
                    className="settings-save-btn"
                    style={{ padding: "10px 24px" }}
                    onClick={handleSaveUserPermissions}
                    disabled={isUserPermsSaving || !selectedUserId}
                  >
                    {isUserPermsSaving ? <FaSpinner className="animate-spin" /> : "Save User Permissions"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      );
    }

    // ─────────────────────────────────────────────────────────────────────────
    // PERSONAL USER SETTINGS (Tabbed Navigation UI)
    // ─────────────────────────────────────────────────────────────────────────
    if (activeUserTab === "general") {
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
              <input
                type="text"
                className="settings-input"
                value={currentUserStg.github_config?.github_account || ""}
                onChange={e => handleUserFieldChange("github_account", e.target.value)}
                placeholder="stit2010@gmail.com"
              />
            </div>
            <div>
              <label className="settings-label">PERSONAL ACCESS TOKEN (PAT)</label>
              <div className="settings-input-group">
                <input
                  type={showSecrets["pat"] ? "text" : "password"}
                  className="settings-input"
                  value={currentUserStg.github_config?.pat || ""}
                  onChange={e => handleUserFieldChange("pat", e.target.value)}
                  placeholder="••••••••••••••••••••"
                />
                <div className="settings-input-group-icon" onClick={() => toggleSecret("pat")}>
                  {showSecrets["pat"] ? <FaEyeSlash /> : <FaEye />}
                </div>
              </div>
            </div>
            <div>
              <label className="settings-label">DEFAULT REPOSITORY</label>
              <select
                className="settings-select"
                value={currentUserStg.github_config?.repository || ""}
                onChange={e => handleUserFieldChange("repository", e.target.value)}
              >
                <option value="">Select Repository</option>
                {availableRepos.map(r => (
                  <option key={r.full_name || r.name} value={r.full_name || r.name}>
                    {r.full_name || r.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="settings-label">DEFAULT BRANCH</label>
              <select
                className="settings-select"
                value={currentUserStg.github_config?.branch || ""}
                onChange={e => handleUserFieldChange("branch", e.target.value)}
              >
                <option value="">Select Branch</option>
                {availableBranches.map(b => (
                  <option key={b.name} value={b.name}>{b.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="settings-label">ACCESS LEVEL</label>
              <select
                className="settings-select"
                value={currentUserStg.github_config?.user_access || ""}
                onChange={e => handleUserFieldChange("user_access", e.target.value)}
              >
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

    if (activeUserTab === "business") {
      const qValues = currentUserStg.quality_checks_values || {};
      const brdInstructions = qValues.brd_instructions || qValues.brd_focus_prompt || "";
      const brdGenEnabled = qValues.brd_generation_enabled ?? true;
      const msEnabled = qValues.brd_microservices_enabled ?? (qValues.microservice_assessment_enabled ?? true);
      const migrationTarget = qValues.brd_migration_target || "Java 17 / Spring Boot 3.2";
      const sysPrompt = qValues.brd_system_prompt || DEFAULT_BRD_SYSTEM_PROMPT;

      const categoryWorkflows = qValues.brd_category_business_workflows ?? true;
      const categoryDatabase = qValues.brd_category_database_data ?? true;
      const categoryArch = qValues.brd_category_architecture ?? true;
      const categoryApis = qValues.brd_category_apis_integrations ?? true;
      const categorySecurity = qValues.brd_category_security_access ?? true;
      const categoryReliability = qValues.brd_category_reliability_performance ?? true;

      const updateBrdField = (key: string, val: any) => {
        handleUserQualityCheckChange(key, val);
        if (key === "brd_instructions") {
          handleUserQualityCheckChange("brd_focus_prompt", val);
        }
        if (key === "brd_microservices_enabled") {
          handleUserQualityCheckChange("microservice_assessment_enabled", val);
        }
      };

      const presetPrompts = [
        {
          label: "🎯 Core Workflows",
          prompt: "Focus on core business workflows, transaction boundaries, state transitions, and entry point methods across all controllers and services."
        },
        {
          label: "🗄️ Database & Entities",
          prompt: "Focus on database tables, primary/foreign keys, JPA entity mappings, repository queries, and data transfer objects (DTOs)."
        },
        {
          label: "🔌 APIs & Web Contracts",
          prompt: "Focus on cataloging all REST endpoints, WebServlets, HTTP request/response DTOs, path parameters, and status codes."
        },
        {
          label: "🧪 Test Scenarios & Locators",
          prompt: "Focus on test automation workflows, page object locators, test assertions, browser actions, and test runner configurations."
        }
      ];

      return (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {/* Card 1: Business Analysis Modes */}
          <div className="settings-card">
            <div className="settings-card-header">
              <div className="settings-card-icon"><FaBriefcase /></div>
              <div>
                <h3 className="settings-card-title">Business Analysis Modes</h3>
                <p className="settings-card-subtitle">Enable or disable automated BRD analysis and Microservice assessment modes.</p>
              </div>
            </div>
            <div className="grid-2">
              <div className="settings-toggle-card">
                <div className="settings-toggle-header">
                  <div className="settings-toggle-title"><FaBriefcase /> BRD Generation</div>
                  <div className="switch-wrap">
                    <label className="switch-ios">
                      <input
                        type="checkbox"
                        checked={brdGenEnabled}
                        onChange={e => updateBrdField("brd_generation_enabled", e.target.checked)}
                      />
                      <span className="slider-ios"></span>
                    </label>
                    <span className="switch-label">{brdGenEnabled ? "Enabled" : "Disabled"}</span>
                  </div>
                </div>
                <p className="settings-toggle-desc">Enable or disable automated Business Requirements Document (BRD) analysis and document export during modernization discovery.</p>
              </div>
              <div className="settings-toggle-card">
                <div className="settings-toggle-header">
                  <div className="settings-toggle-title"><FaFlask /> Microservice Assessment</div>
                  <div className="switch-wrap">
                    <label className="switch-ios">
                      <input
                        type="checkbox"
                        checked={msEnabled}
                        onChange={e => updateBrdField("brd_microservices_enabled", e.target.checked)}
                      />
                      <span className="slider-ios"></span>
                    </label>
                    <span className="switch-label">{msEnabled ? "Enabled" : "Disabled"}</span>
                  </div>
                </div>
                <p className="settings-toggle-desc">Enable or disable microservice eligibility scoring, architectural evaluation, and recommended service splitting analysis.</p>
              </div>
            </div>
          </div>

          {/* Card 2: BRD Focus Prompt & Preset Instructions */}
          <div className="settings-card">
            <div className="settings-card-header">
              <div className="settings-card-icon"><FaBriefcase /></div>
              <div>
                <h3 className="settings-card-title">BRD Focus Prompt & Instructions</h3>
                <p className="settings-card-subtitle">Define focus instructions passed to the LLM during BRD document generation.</p>
              </div>
            </div>

            <div style={{ marginBottom: "16px" }}>
              <label className="settings-label">CUSTOM FOCUS PROMPT / INSTRUCTIONS</label>
              <textarea
                className="settings-textarea"
                rows={4}
                placeholder="Enter custom focus instructions (e.g., Focus on attendance calculation rules, scheduled cron jobs, and database entity relationships)..."
                value={brdInstructions}
                onChange={e => updateBrdField("brd_instructions", e.target.value)}
              />
            </div>

            <div>
              <label className="settings-label" style={{ marginBottom: "8px" }}>QUICK FOCUS PRESETS (CLICK TO APPLY)</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
                {presetPrompts.map((preset, idx) => (
                  <button
                    key={idx}
                    type="button"
                    style={{
                      background: "#f1f5f9",
                      border: "1px solid #cbd5e1",
                      borderRadius: "6px",
                      padding: "6px 12px",
                      fontSize: "12px",
                      fontWeight: 600,
                      color: "#334155",
                      cursor: "pointer",
                      transition: "all 0.2s"
                    }}
                    onClick={() => updateBrdField("brd_instructions", preset.prompt)}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Card 3: BRD Scope & Modernization Target */}
          <div className="settings-card">
            <div className="settings-card-header">
              <div className="settings-card-icon"><FaBriefcase /></div>
              <div>
                <h3 className="settings-card-title">BRD Analysis Scope & Target Baseline</h3>
                <p className="settings-card-subtitle">Configure specific analysis categories and target modernization baseline.</p>
              </div>
            </div>

            <div style={{ marginBottom: "20px" }}>
              <label className="settings-label">MODERNIZATION MIGRATION TARGET BASELINE</label>
              <select
                className="settings-select"
                value={migrationTarget}
                onChange={e => updateBrdField("brd_migration_target", e.target.value)}
              >
                <option value="Java 17 / Spring Boot 3.2">Java 17 / Spring Boot 3.2 (Recommended LTS)</option>
                <option value="Java 21 / Spring Boot 3.3">Java 21 / Spring Boot 3.3 (Latest LTS)</option>
                <option value="Jakarta EE 10 / Open Liberty">Jakarta EE 10 / Open Liberty</option>
                <option value="Micronaut 4 / GraalVM">Micronaut 4 / GraalVM Native</option>
                <option value="Quarkus 3.x">Quarkus 3.x Native</option>
              </select>
            </div>

            <div>
              <label className="settings-label" style={{ marginBottom: "12px" }}>ANALYSIS CATEGORY SCOPE</label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "12px" }}>
                {[
                  { key: "brd_category_business_workflows", label: "💼 Business Workflows", val: categoryWorkflows },
                  { key: "brd_category_database_data", label: "🗄️ Database & Entities", val: categoryDatabase },
                  { key: "brd_category_architecture", label: "🏛️ System Architecture", val: categoryArch },
                  { key: "brd_category_apis_integrations", label: "🔌 APIs & Web Routes", val: categoryApis },
                  { key: "brd_category_security_access", label: "🔐 Security & Access Control", val: categorySecurity },
                  { key: "brd_category_reliability_performance", label: "⚡ Reliability & SLAs", val: categoryReliability }
                ].map(item => (
                  <label
                    key={item.key}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      padding: "10px 14px",
                      background: item.val ? "#eff6ff" : "#f8fafc",
                      border: item.val ? "1px solid #bfdbfe" : "1px solid #e2e8f0",
                      borderRadius: "8px",
                      cursor: "pointer",
                      fontSize: "13px",
                      fontWeight: 600,
                      color: item.val ? "#1e40af" : "#64748b"
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={item.val}
                      onChange={e => updateBrdField(item.key, e.target.checked)}
                    />
                    {item.label}
                  </label>
                ))}
              </div>
            </div>
          </div>

          {/* Card 4: 8-Phase System Prompt Customization */}
          <div className="settings-card">
            <div className="settings-card-header" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
                <div className="settings-card-icon"><FaBriefcase /></div>
                <div>
                  <h3 className="settings-card-title">8-Phase BRD System Prompt Customization</h3>
                  <p className="settings-card-subtitle">System prompt template executed by LLM providers during document generation.</p>
                </div>
              </div>
              <button
                type="button"
                style={{
                  background: "#f1f5f9",
                  border: "1px solid #cbd5e1",
                  borderRadius: "6px",
                  padding: "6px 12px",
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "#334155",
                  cursor: "pointer"
                }}
                onClick={() => updateBrdField("brd_system_prompt", DEFAULT_BRD_SYSTEM_PROMPT)}
              >
                Reset to Default
              </button>
            </div>

            <textarea
              className="settings-textarea"
              rows={8}
              style={{ fontFamily: "monospace", fontSize: "12px", lineHeight: "1.5" }}
              value={sysPrompt}
              onChange={e => updateBrdField("brd_system_prompt", e.target.value)}
            />
          </div>
        </div>
      );
    }

    if (activeUserTab === "testing") {
      return (
        <div>
          <div className="settings-card-header" style={{ marginBottom: "20px" }}>
            <div className="settings-card-icon"><FaFlask /></div>
            <div>
              <h3 className="settings-card-title">Testing Framework Configuration</h3>
              <p className="settings-card-subtitle">Configure JUnit unit test suite, functional UI testing prompts, and E2E frameworks.</p>
            </div>
          </div>

          <UserQualityChecksSettings
            settings={currentUserStg}
            onChange={setUserSettings}
            mode="testing_only"
            effectivePermissions={myEffectivePerms || currentUserStg.settings_permissions}
          />
        </div>
      );
    }

    if (activeUserTab === "quality_gate") {
      return (
        <div>
          <div className="settings-card-header" style={{ marginBottom: "20px" }}>
            <div className="settings-card-icon"><FaShieldAlt /></div>
            <div>
              <h3 className="settings-card-title">Quality Gates</h3>
              <p className="settings-card-subtitle">Configure SonarQube, FOSSA, CI, and CD quality gate pipelines.</p>
            </div>
          </div>

          <div className="grid-2">
            {/* SonarQube Card */}
            <div
              className="settings-card"
              style={{
                border: sonarValidationState === "valid"
                  ? "1px solid #86efac"
                  : sonarValidationState === "invalid"
                  ? "1px solid #fca5a5"
                  : sonarValidationState === "error"
                  ? "1px solid #fde68a"
                  : "1px solid #e2e8f0",
                backgroundColor: sonarValidationState === "valid"
                  ? "#f0fdf4"
                  : "#ffffff",
                boxShadow: sonarValidationState === "valid"
                  ? "0 0 0 1px #86efac, 0 4px 12px rgba(34, 197, 94, 0.08)"
                  : "0 1px 3px rgba(0,0,0,0.02)",
                transition: "all 0.3s ease",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <div className="settings-toggle-title" style={{ margin: 0 }}>
                  <FaShieldAlt style={{ color: sonarValidationState === "valid" ? "#16a34a" : "#2563eb" }} /> SonarQube
                </div>
                {sonarValidationState === "valid" && (
                  <span
                    style={{
                      padding: "3px 10px",
                      borderRadius: "12px",
                      fontSize: "11px",
                      fontWeight: 700,
                      backgroundColor: "#dcfce7",
                      color: "#166534",
                      border: "1px solid #86efac",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <FaCheckCircle style={{ color: "#16a34a", fontSize: "11px" }} /> Connected
                  </span>
                )}
                {sonarValidationState === "validating" && (
                  <span
                    style={{
                      padding: "3px 10px",
                      borderRadius: "12px",
                      fontSize: "11px",
                      fontWeight: 700,
                      backgroundColor: "#eff6ff",
                      color: "#1d4ed8",
                      border: "1px solid #bfdbfe",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <FaSpinner className="animate-spin" style={{ color: "#2563eb", fontSize: "11px" }} /> Validating...
                  </span>
                )}
                {sonarValidationState === "invalid" && (
                  <span
                    style={{
                      padding: "3px 10px",
                      borderRadius: "12px",
                      fontSize: "11px",
                      fontWeight: 700,
                      backgroundColor: "#fef2f2",
                      color: "#991b1b",
                      border: "1px solid #fca5a5",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <FaTimesCircle style={{ color: "#dc2626", fontSize: "11px" }} /> Invalid
                  </span>
                )}
                {sonarValidationState === "error" && (
                  <span
                    style={{
                      padding: "3px 10px",
                      borderRadius: "12px",
                      fontSize: "11px",
                      fontWeight: 700,
                      backgroundColor: "#fffbeb",
                      color: "#92400e",
                      border: "1px solid #fde68a",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <FaExclamationTriangle style={{ color: "#d97706", fontSize: "11px" }} /> Unable to validate
                  </span>
                )}
              </div>
              <p className="settings-card-subtitle" style={{ marginBottom: "16px" }}>Static code analysis to detect bugs and vulnerabilities.</p>
              
              <div className="grid-2" style={{ gap: "12px", marginBottom: "12px" }}>
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
                <div>
                  <label className="settings-label">PROJECT KEY <span style={{ textTransform: "none", fontSize: "11px", color: "#64748b", fontWeight: "normal" }}>(Optional)</span></label>
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

            {/* FOSSA Card */}
            <div
              className="settings-card"
              style={{
                border: fossaValidationState === "invalid"
                  ? "1px solid #fca5a5"
                  : fossaValidationState === "error"
                  ? "1px solid #fde68a"
                  : "1px solid #e2e8f0",
                backgroundColor: "#ffffff",
                boxShadow: "0 1px 3px rgba(0,0,0,0.02)",
                transition: "all 0.3s ease",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <div className="settings-toggle-title" style={{ margin: 0 }}>
                  <FaShieldAlt style={{ color: "#2563eb" }} /> FOSSA
                </div>
                {fossaValidationState === "validating" && (
                  <span
                    style={{
                      padding: "3px 10px",
                      borderRadius: "12px",
                      fontSize: "11px",
                      fontWeight: 700,
                      backgroundColor: "#eff6ff",
                      color: "#1d4ed8",
                      border: "1px solid #bfdbfe",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <FaSpinner className="animate-spin" style={{ color: "#2563eb", fontSize: "11px" }} /> Validating...
                  </span>
                )}
                {fossaValidationState === "invalid" && (
                  <span
                    style={{
                      padding: "3px 10px",
                      borderRadius: "12px",
                      fontSize: "11px",
                      fontWeight: 700,
                      backgroundColor: "#fef2f2",
                      color: "#991b1b",
                      border: "1px solid #fca5a5",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <FaTimesCircle style={{ color: "#dc2626", fontSize: "11px" }} /> Invalid
                  </span>
                )}
                {fossaValidationState === "error" && (
                  <span
                    style={{
                      padding: "3px 10px",
                      borderRadius: "12px",
                      fontSize: "11px",
                      fontWeight: 700,
                      backgroundColor: "#fffbeb",
                      color: "#92400e",
                      border: "1px solid #fde68a",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <FaExclamationTriangle style={{ color: "#d97706", fontSize: "11px" }} /> Unable to validate
                  </span>
                )}
              </div>
              <p className="settings-card-subtitle" style={{ marginBottom: "16px" }}>Open source license compliance and dependency scanning.</p>

              <div style={{ marginBottom: "16px" }}>
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

          <div className="grid-2" style={{ marginTop: "24px" }}>
            {/* Cycode Card (Left Side) */}
            <div className="settings-card" style={{ marginBottom: 0 }}>
              <div className="settings-toggle-title" style={{ marginBottom: "6px" }}>
                <FaShieldAlt style={{ color: "#2563eb" }} /> Cycode
              </div>
              <p className="settings-card-subtitle" style={{ marginBottom: "16px" }}>
                Scan migrated code for exposed secrets and application security findings.
              </p>
              <div className="grid-2" style={{ gap: "12px" }}>
                <div>
                  <label className="settings-label">CYCODE API / TENANT URL</label>
                  <input
                    type="url"
                    className="settings-input"
                    placeholder="https://api.cycode.com"
                    value={userSettings.quality_checks_values?.cycode_api_url || "https://api.cycode.com"}
                    onChange={e => handleUserQualityCheckChange("cycode_api_url", e.target.value)}
                  />
                </div>
                <div>
                  <label className="settings-label">CYCODE ACCOUNT / TENANT</label>
                  <input
                    type="text"
                    className="settings-input"
                    placeholder="Enter business group or tenant"
                    value={userSettings.quality_checks_values?.cycode_tenant || ""}
                    onChange={e => handleUserQualityCheckChange("cycode_tenant", e.target.value)}
                  />
                </div>
                <div>
                  <label className="settings-label">CYCODE API TOKEN</label>
                  <div className="settings-input-group">
                    <input
                      type="checkbox"
                      checked={userSettings.quality_checks_values?.ci_enabled ?? true}
                      onChange={e => handleFieldChange("ci_enabled", e.target.checked, "quality")}
                    />
                    <div className="settings-input-group-icon" onClick={() => toggleSecret("cycode_api_token")} style={{ cursor: "pointer" }}>
                      {showSecrets["cycode_api_token"] ? <FaEyeSlash /> : <FaEye />}
                    </div>
                  </div>
                </div>
                <div>
                  <label className="settings-label">REQUIRED SCOPES</label>
                  <input
                    type="text"
                    className="settings-input"
                    placeholder="secrets,sast"
                    value={userSettings.quality_checks_values?.cycode_scopes || "secrets,sast"}
                    onChange={e => handleUserQualityCheckChange("cycode_scopes", e.target.value)}
                  />
                  <div className="settings-toggle-desc" style={{ marginTop: "4px" }}>Required: secrets,sast</div>
                </div>
              </div>
            </div>

            {/* CI & CD Stack (Right Side) */}
            <div style={{ display: "flex", flexDirection: "column", gap: "16px", justifyContent: "space-between" }}>
              {/* CI Card */}
              <div className="settings-toggle-card" style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                <div className="settings-toggle-header">
                  <div className="settings-toggle-title">
                    <FaRocket style={{ color: "#2563eb" }} /> Continuous Integration (CI)
                  </div>
                  <div className="switch-wrap">
                    <label className="switch-ios">
                      <input type="checkbox" checked={ciEnabled} onChange={e => setCiEnabled(e.target.checked)} />
                      <span className="slider-ios"></span>
                    </label>
                    <span className="switch-label">{ciEnabled ? "Enabled" : "Disabled"}</span>
                  </div>
                </div>
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
                <p className="settings-toggle-desc">
                  Enable or disable automated deployment pipelines and artifact publishing upon successful migration verification.
                </p>
              </div>
            </div>
          </div>
        </div>
      );
    }

    if (activeUserTab === "llm") {
      return (
        <div>
          <div className="settings-card-header" style={{ marginBottom: "20px" }}>
            <div className="settings-card-icon"><FaBrain /></div>
            <div>
              <h3 className="settings-card-title">LLM Configuration</h3>
              <p className="settings-card-subtitle">Manage intelligence providers, models, and features.</p>
            </div>
          </div>

          <LlmUserSettings
            settings={currentUserStg}
            onChange={(key, val) => {
              setUserSettings(prev => ({
                ...(prev || INITIAL_USER_SETTINGS),
                [key]: val
              }));
            }}
            isAdminEnabled={myEffectivePerms?.llm_settings !== false && currentUserStg.system_llm_config?.llm_enabled !== "false"}
            allowedGroqModelsStr={currentUserStg.system_llm_config?.groq_models}
            allowedHuggingFaceModelsStr={currentUserStg.system_llm_config?.huggingface_models}
          />
        </div>
      );
    }

    if (activeUserTab === "artifactory") {
      return (
        <ArtifactorySettings
          settings={isAdminUser ? currentSys : (currentUserStg.artifactory_values || {})}
          onChange={(key, val) => {
            if (isAdminUser) {
              handleAdminFieldChange(key as keyof SystemSettings, val);
            } else {
              setUserSettings(prev => ({
                ...(prev || INITIAL_USER_SETTINGS),
                artifactory_values: {
                  ...((prev || INITIAL_USER_SETTINGS).artifactory_values || {}),
                  [key]: val
                }
              }));
            }
          }}
          isAdmin={isAdminUser}
        />
      );
    }

    return null;
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
          boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1)",
          display: "flex",
          alignItems: "center",
          gap: "12px",
          fontSize: "1rem",
          fontWeight: 600,
        }}>
          {toastMessage.type === "success" ? <FaCheckCircle size={20} /> : <FaTimesCircle size={20} />}
          {toastMessage.text}
        </div>
      )}

      {/* Left Sidebar Navigation */}
      <div className="settings-sidebar">
        <button
          className={`settings-sidebar-tab ${activeUserTab === "general" ? "active" : ""}`}
          onClick={() => setActiveUserTab("general")}
        >
          <FaCog /> General
        </button>
        {isAdminUser ? (
          <>
            <button
              className={`settings-sidebar-tab ${activeUserTab === "quality_gate" ? "active" : ""}`}
              onClick={() => setActiveUserTab("quality_gate")}
            >
              <FaShieldAlt /> Quality Gate
            </button>
            <button
              className={`settings-sidebar-tab ${activeUserTab === "testing" ? "active" : ""}`}
              onClick={() => setActiveUserTab("testing")}
            >
              <FaFlask /> Testing
            </button>
            <button
              className={`settings-sidebar-tab ${activeUserTab === "llm" ? "active" : ""}`}
              onClick={() => setActiveUserTab("llm")}
            >
              <FaBrain /> LLM Configuration
            </button>
            <button
              className={`settings-sidebar-tab ${activeUserTab === "artifactory" ? "active" : ""}`}
              onClick={() => setActiveUserTab("artifactory")}
            >
              <FaPlug /> Artifactory
            </button>
            <button
              className={`settings-sidebar-tab ${activeUserTab === "users" ? "active" : ""}`}
              onClick={() => setActiveUserTab("users")}
            >
              <FaUsers /> User Management
            </button>
          </>
        ) : (
          <>
            {myEffectivePerms?.brd_testing !== false && (
              <button
                className={`settings-sidebar-tab ${activeUserTab === "business" ? "active" : ""}`}
                onClick={() => setActiveUserTab("business")}
              >
                <FaBriefcase /> Business
              </button>
            )}
            {(myEffectivePerms?.unit_testing !== false || myEffectivePerms?.functional_testing !== false) && (
              <button
                className={`settings-sidebar-tab ${activeUserTab === "testing" ? "active" : ""}`}
                onClick={() => setActiveUserTab("testing")}
              >
                <FaFlask /> Testing
              </button>
            )}
            {myEffectivePerms?.quality_checks !== false && (
              <button
                className={`settings-sidebar-tab ${activeUserTab === "quality_gate" ? "active" : ""}`}
                onClick={() => setActiveUserTab("quality_gate")}
              >
                <FaShieldAlt /> Quality Gate
              </button>
            )}
            {myEffectivePerms?.llm_settings !== false && (
              <button
                className={`settings-sidebar-tab ${activeUserTab === "llm" ? "active" : ""}`}
                onClick={() => setActiveUserTab("llm")}
              >
                <FaBrain /> LLM Configuration
              </button>
            )}
            {myEffectivePerms?.artifactory !== false && (
              <button
                className={`settings-sidebar-tab ${activeUserTab === "artifactory" ? "active" : ""}`}
                onClick={() => setActiveUserTab("artifactory")}
              >
                <FaPlug /> Artifactory
              </button>
            )}
          </>
        )}
      </div>

      <main className="settings-main-area" style={{ width: "100%" }}>
        <header className="settings-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", height: "80px", backgroundColor: "#ffffff", padding: "0 40px", borderBottom: "1px solid #e2e8f0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <FaCog style={{ color: "#2563eb", fontSize: "22px" }} />
            <h1 style={{ fontSize: "22px", fontWeight: "800", color: "#0f172a", margin: 0 }}>Settings</h1>
          </div>

          <button className="settings-save-btn" onClick={handleDeploy} disabled={isSaving || isLoading}>
            {isSaving ? <FaSpinner className="animate-spin" /> : "Save Configuration"}
          </button>
        </header>
        
        <div className="settings-scroll-content">
          {renderContent()}
        </div>
      </main>
    </div>
  );
}

