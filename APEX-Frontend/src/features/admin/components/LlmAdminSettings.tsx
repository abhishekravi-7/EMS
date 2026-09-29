import React, { useState } from "react";
import { FaBrain } from "react-icons/fa";
import type { SystemSettings } from "../services/adminService";

interface LlmAdminSettingsProps {
  settings: SystemSettings;
  onChange: (key: keyof SystemSettings, value: any) => void;
}

const AVAILABLE_FEATURES = [
  { id: "CODE_REVIEW", label: "Code Review" },
  { id: "RISK_ANALYSIS", label: "Risk Analysis" },
  { id: "RECOMMENDATION", label: "Recommendation" },
  { id: "UNIT_TESTS", label: "Unit Tests" },
];

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

export function LlmAdminSettings({ settings, onChange }: LlmAdminSettingsProps) {
  const llmEnabled = settings.llm_enabled === true || settings.llm_enabled === "true";

  let llmFeatures: string[] = [];
  try {
    llmFeatures = settings.llm_features ? JSON.parse(settings.llm_features) : [];
  } catch (e) {
    llmFeatures = [];
  }

  let groqModels: string[] = [];
  try {
    groqModels = settings.groq_models ? JSON.parse(settings.groq_models) : [];
  } catch (e) {
    groqModels = [];
  }

  let huggingfaceModels: string[] = [];
  try {
    huggingfaceModels = settings.huggingface_models ? JSON.parse(settings.huggingface_models) : [];
  } catch (e) {
    huggingfaceModels = [];
  }

  const toggleFeature = (id: string) => {
    const newFeatures = llmFeatures.includes(id)
      ? llmFeatures.filter(f => f !== id)
      : [...llmFeatures, id];
    onChange("llm_features", JSON.stringify(newFeatures));
  };

  const toggleGroqModel = (id: string) => {
    const newModels = groqModels.includes(id)
      ? groqModels.filter(m => m !== id)
      : [...groqModels, id];
    onChange("groq_models", JSON.stringify(newModels));
  };

  const toggleHuggingfaceModel = (id: string) => {
    const newModels = huggingfaceModels.includes(id)
      ? huggingfaceModels.filter(m => m !== id)
      : [...huggingfaceModels, id];
    onChange("huggingface_models", JSON.stringify(newModels));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <h3 className="card-heading-modern">
          <FaBrain style={{ color: "#2563eb", marginRight: "8px" }} />
          LLM Configuration
        </h3>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>

        {/* Enable Intelligence (Master Switch) */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div>
            <h4 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b", fontWeight: 600 }}>Configure LLM</h4>
            <p style={{ margin: "4px 0 0", fontSize: "0.875rem", color: "#64748b" }}>
              Enable Language Models and AI capabilities platform-wide.
            </p>
          </div>
          <div className="switch-row-modern" style={{ marginTop: 0 }}>
            <label className="switch-modern">
              <input
                type="checkbox"
                checked={llmEnabled}
                onChange={(e) => onChange("llm_enabled", String(e.target.checked))}
              />
              <span className="slider-modern"></span>
            </label>
            <span className="switch-label-modern" style={{ minWidth: "100px" }}>
              {llmEnabled ? "Enabled" : "Disabled"}
            </span>
          </div>
        </div>

        {/* Feature Switches */}
        <div style={{
          border: "1px solid #e2e8f0", borderRadius: "8px", padding: "20px", background: "#ffffff",
          opacity: llmEnabled ? 1 : 0.5, pointerEvents: llmEnabled ? "auto" : "none"
        }}>
          <h4 style={{ margin: "0 0 16px 0", fontSize: "1rem", color: "#334155" }}>Available Capabilities</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {AVAILABLE_FEATURES.map((feature) => (
              <label key={feature.id} style={{ display: "flex", alignItems: "center", gap: "12px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={llmFeatures.includes(feature.id)}
                  onChange={() => toggleFeature(feature.id)}
                  style={{ width: "16px", height: "16px", accentColor: "#2563eb" }}
                />
                <span style={{ fontSize: "0.9rem", color: "#475569" }}>{feature.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Groq Models */}
        <div style={{
          border: "1px solid #e2e8f0", borderRadius: "8px", padding: "20px", background: "#ffffff",
          opacity: llmEnabled ? 1 : 0.5, pointerEvents: llmEnabled ? "auto" : "none"
        }}>
          <h4 style={{ margin: "0 0 16px 0", fontSize: "1rem", color: "#334155" }}>Allowed Groq Models (Chatbot)</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {GROQ_MODELS.map((model) => (
              <label key={model.id} style={{ display: "flex", alignItems: "center", gap: "12px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={groqModels.includes(model.id)}
                  onChange={() => toggleGroqModel(model.id)}
                  style={{ width: "16px", height: "16px", accentColor: "#2563eb" }}
                />
                <span style={{ fontSize: "0.9rem", color: "#475569" }}>{model.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* HuggingFace Models */}
        <div style={{
          border: "1px solid #e2e8f0", borderRadius: "8px", padding: "20px", background: "#ffffff",
          opacity: llmEnabled ? 1 : 0.5, pointerEvents: llmEnabled ? "auto" : "none"
        }}>
          <h4 style={{ margin: "0 0 16px 0", fontSize: "1rem", color: "#334155" }}>Allowed HuggingFace Models (Code Analysis)</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {HUGGINGFACE_MODELS.map((model) => (
              <label key={model.id} style={{ display: "flex", alignItems: "center", gap: "12px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={huggingfaceModels.includes(model.id)}
                  onChange={() => toggleHuggingfaceModel(model.id)}
                  style={{ width: "16px", height: "16px", accentColor: "#2563eb" }}
                />
                <span style={{ fontSize: "0.9rem", color: "#475569" }}>{model.label}</span>
              </label>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
