import React, { useState } from "react";
import type { FullUserSettings } from "../services/adminService";
import { requestJson } from "@/services/http/client";
import { FaSpinner, FaPlay, FaCheckCircle, FaTimesCircle, FaEye, FaEyeSlash, FaBrain } from "react-icons/fa";

const GROQ_MODELS = [
  { id: "gpt-4o", label: "gpt-4o" },
  { id: "claude-3.5-sonnet", label: "claude-3.5-sonnet" },
  { id: "gemini-1.5-pro", label: "gemini-1.5-pro" },
  { id: "mixtral-8x7b", label: "mixtral-8x7b" },
  { id: "llama-3-70b", label: "llama-3-70b" },
  { id: "qwen/qwen3.8-27b", label: "qwen/qwen3.8-27b" },
];

const HUGGINGFACE_MODELS = [
  { id: "meta-llama/Llama-3.1-8B-Instruct:novita", label: "meta-llama/Llama-3.1-8B-Instruct:novita" },
];

interface LlmUserSettingsProps {
  settings: FullUserSettings;
  onChange: (key: keyof FullUserSettings, value: any) => void;
  isAdminEnabled: boolean;
  allowedGroqModelsStr?: string;
  allowedHuggingFaceModelsStr?: string;
}

export async function testUserLlmConnection(payload: { provider: string; api_key: string; selected_model: string }): Promise<{ status: string; message: string }> {
  return requestJson<{ status: string; message: string }>(
    "/v1/user/settings/llm/test",
    "Failed to test User LLM connection",
    {
      method: "POST",
      body: payload
    }
  );
}

export function LlmUserSettings({ settings, onChange, isAdminEnabled, allowedGroqModelsStr, allowedHuggingFaceModelsStr }: LlmUserSettingsProps) {
  const llmValues = settings.llm_values || {};
  // State for Groq
  const [testingGroq, setTestingGroq] = useState(false);
  const [testResultGroq, setTestResultGroq] = useState<{ status: "success" | "error"; message: string } | null>(null);
  const [showGroqSecret, setShowGroqSecret] = useState(false);

  // State for HuggingFace
  const [testingHF, setTestingHF] = useState(false);
  const [testResultHF, setTestResultHF] = useState<{ status: "success" | "error"; message: string } | null>(null);
  const [showHFSecret, setShowHFSecret] = useState(false);

  let allowedGroqModels: string[] = [];
  try {
    allowedGroqModels = allowedGroqModelsStr ? JSON.parse(allowedGroqModelsStr) : [];
  } catch (e) {
    allowedGroqModels = [];
  }

  let allowedHuggingFaceModels: string[] = [];
  try {
    allowedHuggingFaceModels = allowedHuggingFaceModelsStr ? JSON.parse(allowedHuggingFaceModelsStr) : [];
  } catch (e) {
    allowedHuggingFaceModels = [];
  }

  if (!isAdminEnabled) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "16px", padding: "24px", border: "1px solid #e2e8f0", borderRadius: "8px", background: "#f8fafc", textAlign: "center" }}>
        <h3 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b", fontWeight: 600 }}>LLM Configuration</h3>
        <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "#64748b" }}>
          LLM features are currently disabled by the system administrator.
        </p>
      </div>
    );
  }

  const handleTestConnection = async (provider: "groq" | "huggingface") => {
    const apiKey = llmValues[`${provider}_api_key`];
    const model = llmValues[`${provider}_model`];

    if (!apiKey) {
      alert(`Please enter an API Key for ${provider}.`);
      return;
    }

    if (provider === "groq") {
      setTestingGroq(true);
      setTestResultGroq(null);
    } else {
      setTestingHF(true);
      setTestResultHF(null);
    }

    try {
      const res = await testUserLlmConnection({
        provider: provider,
        api_key: apiKey || "",
        selected_model: model || ""
      });
      if (provider === "groq") {
        setTestResultGroq({ status: "success", message: res.message || "Connected to Groq successfully." });
      } else {
        setTestResultHF({ status: "success", message: res.message || "Connected to HuggingFace successfully." });
      }
    } catch (err: any) {
      if (provider === "groq") {
        setTestResultGroq({ status: "error", message: err.message || "Connection failed." });
      } else {
        setTestResultHF({ status: "error", message: err.message || "Connection failed." });
      }
    } finally {
      if (provider === "groq") {
        setTestingGroq(false);
      } else {
        setTestingHF(false);
      }
    }
  };

  const updateLlmValue = (key: string, value: string) => {
    onChange("llm_values", { ...llmValues, [key]: value });
  };

  return (
    <div>
      <div className="settings-card-header" style={{ marginBottom: "20px" }}>
        <div className="settings-card-icon"><FaBrain /></div>
        <div>
          <h3 className="settings-card-title">LLM Configuration</h3>
          <p className="settings-card-subtitle">Manage intelligence providers, models, and features.</p>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
        
        {/* Groq Configuration */}
        <div>
          <h4 style={{ margin: "0 0 16px 0", fontSize: "16px", fontWeight: 700, color: "#0f172a" }}>
            Groq Configuration (Chatbot)
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            
            <div>
              <label className="settings-label">MODEL</label>
              <select
                className="settings-select"
                value={llmValues.groq_model || ""}
                onChange={(e) => updateLlmValue("groq_model", e.target.value)}
              >
                <option value="">Select Model</option>
                {(allowedGroqModels.length > 0 ? allowedGroqModels : GROQ_MODELS.map(gm => gm.id)).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="settings-label">API KEY</label>
              <div className="settings-input-group">
                <input
                  type={showGroqSecret ? "text" : "password"}
                  className="settings-input"
                  value={llmValues.groq_api_key || ""}
                  onChange={(e) => updateLlmValue("groq_api_key", e.target.value)}
                  placeholder="Enter your Groq API Key"
                />
                <div className="settings-input-group-icon" onClick={() => setShowGroqSecret(!showGroqSecret)}>
                  {showGroqSecret ? <FaEyeSlash /> : <FaEye />}
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "12px", marginTop: "8px" }}>
              {testResultGroq && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.9rem", color: testResultGroq.status === "success" ? "#16a34a" : "#dc2626", fontWeight: 500 }}>
                  {testResultGroq.status === "success" ? <FaCheckCircle /> : <FaTimesCircle />}
                  {testResultGroq.message}
                </div>
              )}
              <button
                onClick={() => handleTestConnection("groq")}
                disabled={testingGroq || !llmValues.groq_api_key}
                className="settings-action-btn" 
                style={{ width: "auto" }}
              >
                {testingGroq ? <FaSpinner className="animate-spin" /> : <FaPlay size={12} />}
                <span style={{ marginLeft: "6px" }}>{testingGroq ? "Testing..." : "Test Connection"}</span>
              </button>
            </div>

          </div>
        </div>

        {/* HuggingFace Configuration */}
        <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: "20px" }}>
          <h4 style={{ margin: "0 0 16px 0", fontSize: "16px", fontWeight: 700, color: "#0f172a" }}>
            HuggingFace Configuration (Code Analysis)
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            
            <div>
              <label className="settings-label">MODEL</label>
              <select
                className="settings-select"
                value={llmValues.huggingface_model || ""}
                onChange={(e) => updateLlmValue("huggingface_model", e.target.value)}
              >
                <option value="">Select Model</option>
                {(allowedHuggingFaceModels.length > 0 ? allowedHuggingFaceModels : HUGGINGFACE_MODELS.map(hm => hm.id)).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="settings-label">API KEY</label>
              <div className="settings-input-group">
                <input
                  type={showHFSecret ? "text" : "password"}
                  className="settings-input"
                  value={llmValues.huggingface_api_key || ""}
                  onChange={(e) => updateLlmValue("huggingface_api_key", e.target.value)}
                  placeholder="Enter your HuggingFace API Key"
                />
                <div className="settings-input-group-icon" onClick={() => setShowHFSecret(!showHFSecret)}>
                  {showHFSecret ? <FaEyeSlash /> : <FaEye />}
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "12px", marginTop: "8px" }}>
              {testResultHF && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.9rem", color: testResultHF.status === "success" ? "#16a34a" : "#dc2626", fontWeight: 500 }}>
                  {testResultHF.status === "success" ? <FaCheckCircle /> : <FaTimesCircle />}
                  {testResultHF.message}
                </div>
              )}
              <button
                onClick={() => handleTestConnection("huggingface")}
                disabled={testingHF || !llmValues.huggingface_api_key}
                className="settings-action-btn" 
                style={{ width: "auto" }}
              >
                {testingHF ? <FaSpinner className="animate-spin" /> : <FaPlay size={12} />}
                <span style={{ marginLeft: "6px" }}>{testingHF ? "Testing..." : "Test Connection"}</span>
              </button>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}
