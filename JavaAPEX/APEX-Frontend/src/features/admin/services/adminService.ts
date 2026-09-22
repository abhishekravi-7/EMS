import { requestJson } from "@/services/http/client";

export interface SystemSettings {
  github_token: string;
  github_api_base_url: string;
  github_target_owner: string;
  github_target_token: string;
  huggingface_token: string;
  groq_api_key: string;
  ollama_base_url: string;
  rag_enabled: string | boolean;
  sonarqube_host_url: string;
  sonarqube_token: string;
  fossa_api_key: string;
  database_url: string;
  jwt_secret_key: string;
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
  const response = await requestJson<SystemSettingsResponse>(
    "/v1/admin/settings",
    "Failed to update admin settings",
    {
      method: "POST",
      body: { settings },
    }
  );
  return response.settings;
}
