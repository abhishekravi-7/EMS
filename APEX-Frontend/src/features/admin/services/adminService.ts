import { requestJson } from "@/services/http/client";

export interface SystemSettings {
  github_token: string;
  github_api_base_url: string;
  github_target_owner: string;
  github_target_token: string;
  github_client_id?: string;
  github_client_secret?: string;
  github_redirect_uri?: string;
  github_callback_url?: string;
  github_organization?: string;
  github_default_branch?: string;
  ollama_base_url: string;
  rag_enabled: string | boolean;
  sonarqube_host_url: string;
  sonarqube_token: string;
  fossa_api_key: string;
  jwt_secret_key: string;
  quality_checks_config?: string;
  ci_enabled?: string | boolean;
  cd_enabled?: string | boolean;
  test_cases_playwright_enabled?: string | boolean;
  test_cases_playwright_command?: string;
  test_cases_cypress_enabled?: string | boolean;
  test_cases_cypress_command?: string;
  test_cases_selenium_enabled?: string | boolean;
  test_cases_selenium_command?: string;
  llm_enabled?: string | boolean;
  llm_features?: string; // JSON array of features
  groq_models?: string; // JSON array of groq models
  huggingface_models?: string; // JSON array of hugging face models
  artifactory_provider?: string;
  artifactory_url?: string;
  artifactory_username?: string;
  artifactory_token?: string;
}

export interface SystemSettingsResponse {
  settings: SystemSettings;
}

/**
 * Fetch all system settings from the backend.
 */
export async function getAdminSettings(): Promise<SystemSettings> {
  const response = await requestJson<SystemSettingsResponse>(
    "/v1/admin/settings",
    "Failed to fetch admin settings"
  );
  return response.settings;
}

/**
 * Update system settings. Only the provided keys will be updated.
 */
export async function updateAdminSettings(settings: Partial<SystemSettings>): Promise<SystemSettings> {
  const stringifiedSettings: Record<string, string> = {};
  for (const [key, value] of Object.entries(settings)) {
    if (value !== undefined && value !== null) {
      stringifiedSettings[key] = String(value);
    }
  }

  const response = await requestJson<SystemSettingsResponse>(
    "/v1/admin/settings",
    "Failed to update admin settings",
    {
      method: "POST",
      body: { settings: stringifiedSettings },
    }
  );
  return response.settings;
}

export async function testAdminPlaywrightConnection(): Promise<{ status: string; message: string }> {
  return requestJson<{ status: string; message: string }>(
    "/v1/admin/settings/test-cases/playwright/test",
    "Failed to test Playwright configuration",
    { method: "POST" }
  );
}

export async function testAdminGithubConnection(): Promise<{ status: string; message: string }> {
  return requestJson<{ status: string; message: string }>(
    "/v1/admin/settings/github/test",
    "Failed to test Platform GitHub configuration",
    { method: "POST" }
  );
}
 
export interface UserGitHubConfig {
  github_account?: string;
  pat?: string;
  pat_scope?: string;
  repository?: string;
  branch?: string;
  user_access?: string;
  repo_url?: string;
  target_token?: string;
}

export interface UserSettingsResponse {
  github_config: UserGitHubConfig;
  quality_checks_values?: Record<string, unknown>;
  test_cases_values?: Record<string, unknown>;
  llm_values?: Record<string, unknown>;
  artifactory_values?: Record<string, unknown>;
  system_llm_config?: {
    llm_enabled?: boolean | string;
    groq_models?: string;
    huggingface_models?: string;
  };
  system_test_cases_config?: {
    test_cases_playwright_enabled?: boolean | string;
    test_cases_cypress_enabled?: boolean | string;
    test_cases_selenium_enabled?: boolean | string;
  };
  settings_permissions?: UserSettingsPermissions;
}

export interface FullUserSettings {
  github_config: UserGitHubConfig;
  quality_checks_values: Record<string, unknown>;
  test_cases_values: Record<string, unknown>;
  llm_values: Record<string, unknown>;
  artifactory_values: Record<string, unknown>;
  system_llm_config?: {
    llm_enabled?: boolean | string;
    groq_models?: string;
    huggingface_models?: string;
  };
  system_test_cases_config?: {
    test_cases_playwright_enabled?: boolean | string;
    test_cases_cypress_enabled?: boolean | string;
    test_cases_selenium_enabled?: boolean | string;
  };
  settings_permissions?: UserSettingsPermissions;
}

export type DocumentPromptType = "BRD" | "TECHNICAL_SPECIFICATION";

export type DocumentGenerationPrompts = Record<DocumentPromptType, string>;

export interface DocumentGenerationPromptSettings {
  prompts: DocumentGenerationPrompts;
  savedTypes: Record<DocumentPromptType, boolean>;
}

function readDocumentGenerationPromptSettings(settings: FullUserSettings): DocumentGenerationPromptSettings {
  const qualityChecks = settings.quality_checks_values;
  const prompts: DocumentGenerationPrompts = {
    BRD:
      (typeof qualityChecks.brd_instructions === "string" ? qualityChecks.brd_instructions : undefined) ??
      (typeof qualityChecks.brd_focus_prompt === "string" ? qualityChecks.brd_focus_prompt : ""),
    TECHNICAL_SPECIFICATION:
      typeof qualityChecks.technical_specification_instructions === "string"
        ? qualityChecks.technical_specification_instructions
        : "",
  };

  return {
    prompts,
    savedTypes: {
      BRD:
        Object.prototype.hasOwnProperty.call(qualityChecks, "brd_instructions") ||
        Object.prototype.hasOwnProperty.call(qualityChecks, "brd_focus_prompt"),
      TECHNICAL_SPECIFICATION: Object.prototype.hasOwnProperty.call(
        qualityChecks,
        "technical_specification_instructions"
      ),
    },
  };
}

export async function getUserSettings(): Promise<FullUserSettings> {
  const response = await requestJson<UserSettingsResponse>(
    "/v1/user/settings/github",
    "Failed to fetch user settings"
  );
  return {
    github_config: response.github_config,
    quality_checks_values: response.quality_checks_values || {},
    test_cases_values: response.test_cases_values || {},
    llm_values: response.llm_values || {},
    artifactory_values: response.artifactory_values || {},
    system_llm_config: response.system_llm_config || {},
    system_test_cases_config: response.system_test_cases_config || {},
    settings_permissions: response.settings_permissions,
  };
}

export async function updateUserSettings(
  github_config: UserGitHubConfig,
  quality_checks_values?: Record<string, unknown>,
  test_cases_values?: Record<string, unknown>,
  llm_values?: Record<string, unknown>,
  artifactory_values?: Record<string, unknown>
): Promise<FullUserSettings> {
  const body: Record<string, unknown> = { github_config };
  if (quality_checks_values) {
    body.quality_checks_values = quality_checks_values;
  }
  if (test_cases_values) {
    body.test_cases_values = test_cases_values;
  }
  if (llm_values) {
    body.llm_values = llm_values;
  }
  if (artifactory_values) {
    body.artifactory_values = artifactory_values;
  }

  const response = await requestJson<UserSettingsResponse>(
    "/v1/user/settings/github",
    "Failed to update user settings",
    {
      method: "POST",
      body,
    }
  );
  return {
    github_config: response.github_config,
    quality_checks_values: response.quality_checks_values || {},
    test_cases_values: response.test_cases_values || {},
    llm_values: response.llm_values || {},
    artifactory_values: response.artifactory_values || {},
    system_llm_config: response.system_llm_config || {},
    system_test_cases_config: response.system_test_cases_config || {},
    settings_permissions: response.settings_permissions,
  };
}

export async function saveUserSettings(fullSettings: FullUserSettings): Promise<FullUserSettings> {
  return updateUserSettings(
    fullSettings.github_config || {},
    fullSettings.quality_checks_values || {},
    fullSettings.test_cases_values || {},
    fullSettings.llm_values || {},
    fullSettings.artifactory_values || {}
  );
}

export async function getDocumentGenerationPromptSettings(): Promise<DocumentGenerationPromptSettings> {
  return readDocumentGenerationPromptSettings(await getUserSettings());
}

export async function saveDocumentGenerationPrompt(
  promptType: DocumentPromptType,
  prompt: string
): Promise<DocumentGenerationPromptSettings> {
  const currentSettings = await getUserSettings();
  const qualityChecksValues: Record<string, unknown> = { ...currentSettings.quality_checks_values };

  if (promptType === "BRD") {
    qualityChecksValues.brd_instructions = prompt;
    qualityChecksValues.brd_focus_prompt = prompt;
  } else {
    qualityChecksValues.technical_specification_instructions = prompt;
  }

  const savedSettings = await saveUserSettings({
    ...currentSettings,
    quality_checks_values: qualityChecksValues,
  });
  const confirmedSettings = readDocumentGenerationPromptSettings(savedSettings);
  if (confirmedSettings.prompts[promptType] !== prompt || !confirmedSettings.savedTypes[promptType]) {
    throw new Error("The saved document prompt could not be confirmed by the server.");
  }

  return confirmedSettings;
}
 
export async function testUserPlaywrightConnection(baseUrl: string): Promise<{ status: string; message: string }> {
  return requestJson<{ status: string; message: string }>(
    "/v1/user/settings/test-cases/playwright/test",
    "Failed to test User Playwright connection",
    {
      method: "POST",
      body: { base_url: baseUrl }
    }
  );
}
 
export async function getQualityChecksAdminConfig(): Promise<{quality_checks_config: string; ci_enabled?: boolean; cd_enabled?: boolean}> {
  return requestJson<{quality_checks_config: string; ci_enabled?: boolean; cd_enabled?: boolean}>(
    "/v1/user/settings/quality-checks-config",
    "Failed to fetch Quality Checks Admin Configuration"
  );
}
 
 
export async function testUserGithubConnection(): Promise<{status: string, message: string}> {
  return requestJson<{status: string, message: string}>(
    "/v1/user/settings/github/test",
    "User GitHub Connection Test Failed",
    { method: "POST" }
  );
}

export async function testUserSonarqubeConnection(payload: { url: string; token: string; project_key?: string; org?: string }): Promise<{ status: string; message: string }> {
  return requestJson<{ status: string; message: string }>(
    "/v1/user/settings/sonarqube/test",
    "Failed to test SonarQube connection",
    {
      method: "POST",
      body: payload
    }
  );
}

export async function testUserSonarConnection(payload: {
  sonarqube_url?: string;
  auth_token?: string;
  project_key?: string;
  sonar_organization?: string;
  url?: string;
  token?: string;
  org?: string;
}): Promise<{ status: string; message: string }> {
  return testUserSonarqubeConnection({
    url: payload.sonarqube_url || payload.url || "",
    token: payload.auth_token || payload.token || "",
    project_key: payload.project_key,
    org: payload.sonar_organization || payload.org,
  });
}

export async function testUserFossaConnection(payload: { api_key?: string; fossa_api_key?: string }): Promise<{ status: string; message: string }> {
  const apiKey = payload.api_key || payload.fossa_api_key || "";
  return requestJson<{ status: string; message: string }>(
    "/v1/user/settings/fossa/test",
    "Failed to test FOSSA connection",
    {
      method: "POST",
      body: { api_key: apiKey }
    }
  );
}

 
export interface GithubRepo {
  id: number;
  name: string;
  full_name: string;
  owner: string;
  private: boolean;
}

export interface GithubBranch {
  name: string;
}

export async function fetchUserGithubRepos(): Promise<GithubRepo[]> {
  return requestJson<GithubRepo[]>(
    "/v1/user/settings/github/repos",
    "Failed to fetch GitHub repositories"
  );
}

export async function fetchUserGithubBranches(owner: string, repo: string): Promise<GithubBranch[]> {
  return requestJson<GithubBranch[]>(
    `/v1/user/settings/github/repos/${owner}/${repo}/branches`,
    "Failed to fetch GitHub branches"
  );
}

export interface PredefinedJUnitPrompt {
  id: string;
  title: string;
  prompt: string;
  description: string;
}

export async function getPredefinedJUnitPrompts(): Promise<PredefinedJUnitPrompt[]> {
  return requestJson<PredefinedJUnitPrompt[]>(
    "/v1/unit-tests/predefined-prompts",
    "Failed to fetch predefined JUnit prompts"
  );
}

export interface TestingPromptAnalysisResult {
  user_prompt?: string;
  testing_focus: string;
  testing_objective?: string;
  coverage_target?: string;
  target_areas: string[];
  target_classes: string[];
  target_methods: string[];
  business_logic_areas?: string[];
  execution_paths?: string[];
  branches?: string[];
  edge_cases: string[];
  negative_scenarios?: string[];
  exception_scenarios?: string[];
  coverage_gaps?: string[];
  priority: string[];
  priority_areas?: string[];
  scenarios: string[];
  additional_tests_required?: string[];
}

export async function analyzeTestingPrompt(
  manualPrompt?: string,
  selectedPredefinedPrompts?: string[],
  projectContext?: string
): Promise<TestingPromptAnalysisResult> {
  return requestJson<TestingPromptAnalysisResult>(
    "/v1/unit-tests/analyze-prompt",
    "Failed to analyze testing prompt",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        manual_prompt: manualPrompt,
        selected_predefined_prompts: selectedPredefinedPrompts,
        prompt: manualPrompt,
        project_context: projectContext,
      }),
    }
  );
}

export interface UserSettingsPermissions {
  llm_settings: boolean;
  quality_checks: boolean;
  unit_testing: boolean;
  functional_testing: boolean;
  brd_testing: boolean;
  test_connection: boolean;
  artifactory: boolean;
}

export interface AdminUser {
  id: string | number;
  _id: string | number;
  full_name: string;
  email: string;
  role: string;
  settings_permissions: UserSettingsPermissions;
  created_at?: string;
}

export interface UserEffectivePermissionsResponse {
  user_id: string | number;
  role: string;
  permissions: UserSettingsPermissions;
  effective: UserSettingsPermissions;
}

export async function getAdminUsers(): Promise<AdminUser[]> {
  const res = await requestJson<{ users: AdminUser[] }>(
    "/v1/admin/users",
    "Failed to fetch admin users list"
  );
  return res.users || [];
}

export async function getAdminUserPermissions(userId: string | number): Promise<UserSettingsPermissions> {
  const encodedId = encodeURIComponent(String(userId));
  const res = await requestJson<{ permissions: UserSettingsPermissions }>(
    `/v1/admin/users/${encodedId}/permissions`,
    "Failed to fetch user permissions"
  );
  return res.permissions;
}

export async function updateAdminUserPermissions(
  userId: string | number,
  permissions: UserSettingsPermissions
): Promise<{ status: string; message: string; permissions: UserSettingsPermissions }> {
  const encodedId = encodeURIComponent(String(userId));
  return requestJson<{ status: string; message: string; permissions: UserSettingsPermissions }>(
    `/v1/admin/users/${encodedId}/permissions`,
    "Failed to update user permissions",
    {
      method: "PUT",
      body: { permissions },
    }
  );
}

export async function getMySettingsPermissions(): Promise<UserEffectivePermissionsResponse> {
  return requestJson<UserEffectivePermissionsResponse>(
    "/v1/user/me/settings-permissions",
    "Failed to fetch user settings permissions"
  );
}
