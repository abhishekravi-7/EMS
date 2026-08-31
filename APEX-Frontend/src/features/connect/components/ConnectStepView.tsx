import React, { useRef } from "react";
import {
  FaCheckCircle,
  FaCode,
  FaCoffee,
  FaExclamationTriangle,
  FaFileAlt,
  FaFileCode,
  FaFlask,
  FaFolderOpen,
  FaGithub,
  FaInfoCircle,
  FaLock,
  FaProjectDiagram,
  FaRocket,
  FaSearch,
  FaShieldAlt,
} from "react-icons/fa";
import type { useRepositoryConnect } from "../hooks/useRepositoryConnect";
import "../pages/ConnectPage.css";

interface ConnectStepViewProps {
  connect: ReturnType<typeof useRepositoryConnect>;
  onError: (message: string) => void;
  onClearRepoAnalysis: () => void;
}

export function ConnectStepView({ connect, onError, onClearRepoAnalysis }: ConnectStepViewProps) {
  const {
    repoUrl,
    setRepoUrl,
    setSelectedRepo,
    githubToken,
    setGithubToken,
    setIsPrivateRepo,
    patToken,
    setPatToken,
    connecting,
    repoAccessCheckLoading,
    accessTokenValidationState,
    accessTokenValidationMessage,
    localProjectCapabilities,
    localProjectCapabilitiesLoading,
    localProjectUploadFiles,
    localProjectUploadLoading,
    localProjectUploadCompressing,
    localProjectUploadError,
    localProjectUploadWarning,
    urlValidation,
    showEnterpriseToken,
    activeAccessToken,
    repositoryNeedsAuthentication,
    shouldShowPatInput,
    resetAccessTokenValidationState,
    handleAccessTokenValidate,
    handleRepositoryContinue,
    handleLocalProjectFilesChange,
    handleLocalProjectUpload,
  } = connect;

  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const zipInputRef = useRef<HTMLInputElement | null>(null);

  const authenticationBannerText = showEnterpriseToken
    ? "GitHub Enterprise repository detected - authentication required"
    : "Private repository detected - authentication required";
  const tokenCardTitle = showEnterpriseToken
    ? "Enterprise Repository - Enter Personal Access Token"
    : "Private Repository - Enter Personal Access Token";
  const tokenDescription = showEnterpriseToken
    ? "This repository requires authentication. Provide a GitHub Personal Access Token before analysis."
    : "This repository requires authentication. Provide a GitHub Personal Access Token with repo scope.";
  const tokenStatusColor =
    accessTokenValidationState === "valid"
      ? "#166534"
      : accessTokenValidationState === "invalid"
        ? "#b45309"
        : "#9a3412";
  const tokenStatusIcon =
    accessTokenValidationState === "valid"
      ? <FaCheckCircle />
      : accessTokenValidationState === "invalid"
        ? <FaExclamationTriangle />
        : <FaInfoCircle />;

  return (
    <div className="page-connect" data-step="connect">
      {/* Background Watermarks & Decorative Patterns */}
      <div className="connect-bg-watermarks" aria-hidden="true">
        {/* Left Java Watermark */}
        <div className="connect-watermark-left">
          <svg width="84" height="84" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8h1a4 4 0 0 1 0 8h-1" />
            <path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z" />
            <line x1="6" y1="1" x2="6" y2="4" />
            <line x1="10" y1="1" x2="10" y2="4" />
            <line x1="14" y1="1" x2="14" y2="4" />
          </svg>
          <div style={{ fontSize: 13, fontWeight: 700, opacity: 0.6, marginTop: 4, letterSpacing: 1 }}>&lt;/&gt;</div>
        </div>

        {/* Right Code Braces Watermark */}
        <div className="connect-watermark-right">
          <div style={{ fontSize: 48, fontWeight: 300, fontFamily: "monospace", opacity: 0.7 }}>{`{ }`}</div>
          <div style={{ fontSize: 13, fontWeight: 700, opacity: 0.6, marginTop: 4, textAlign: "right", letterSpacing: 1 }}>&lt;/&gt;</div>
        </div>

        {/* Constellation Network Nodes */}
        <svg className="connect-network-canvas" viewBox="0 0 1000 600" preserveAspectRatio="none">
          <g stroke="#3b82f6" strokeWidth="1" opacity="0.35">
            <line x1="80" y1="120" x2="160" y2="180" />
            <line x1="160" y1="180" x2="140" y2="280" />
            <line x1="160" y1="180" x2="220" y2="150" />
            <line x1="220" y1="150" x2="280" y2="220" />
            <line x1="140" y1="280" x2="200" y2="340" />
            <line x1="200" y1="340" x2="280" y2="220" />

            <line x1="780" y1="140" x2="860" y2="190" />
            <line x1="860" y1="190" x2="940" y2="160" />
            <line x1="860" y1="190" x2="880" y2="280" />
            <line x1="880" y1="280" x2="940" y2="340" />
            <line x1="880" y1="280" x2="800" y2="240" />
          </g>
          <g fill="#3b82f6" opacity="0.45">
            <circle cx="80" cy="120" r="3.5" />
            <circle cx="160" cy="180" r="4.5" />
            <circle cx="140" cy="280" r="3.5" />
            <circle cx="220" cy="150" r="3" />
            <circle cx="280" cy="220" r="4" />
            <circle cx="200" cy="340" r="3.5" />

            <circle cx="780" cy="140" r="3" />
            <circle cx="860" cy="190" r="4.5" />
            <circle cx="940" cy="160" r="3.5" />
            <circle cx="880" cy="280" r="4" />
            <circle cx="940" cy="340" r="3" />
            <circle cx="800" cy="240" r="3.5" />
          </g>
        </svg>
      </div>

      <div className="connect-content-wrapper">
        {/* Hero Title & Subtitle */}
        <div className="connect-hero">
          <h1 className="connect-hero-title">
            Start Your <span className="connect-hero-emphasized">Migration</span> Journey
          </h1>
          <p className="connect-hero-subtitle">
            Analyze your Java project with <span className="connect-hero-highlight">APEX intelligence</span> and modernize with confidence.
          </p>
        </div>

        {/* Action Cards: GitHub Repository & Upload Local Project */}
        <div className="connect-cards-container">
          {/* Card 1: Connect GitHub Repository */}
          <div className="connect-action-card">
            <div className="connect-card-accent-github" />
            <div className="connect-card-icon-badge is-blue">
              <FaGithub size={30} />
            </div>
            <h2 className="connect-card-heading">Connect GitHub Repository</h2>
            <p className="connect-card-desc">
              Connect your GitHub repository to analyze and discover project insights.
            </p>

            <div className="connect-card-input-box">
              <input
                type="text"
                className="connect-text-input"
                value={repoUrl}
                onChange={(e) => {
                  setRepoUrl(e.target.value);
                  setSelectedRepo(null);
                  onClearRepoAnalysis();
                  setIsPrivateRepo(false);
                  setPatToken("");
                  resetAccessTokenValidationState();
                  onError("");
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && urlValidation.valid) {
                    void handleRepositoryContinue();
                  }
                }}
                placeholder="https://github.com/owner/repository"
                style={{
                  borderColor: urlValidation.valid ? "#22c55e" : repoUrl ? "#ef4444" : "#cbd5e1",
                }}
              />

              {/* URL Validation Message */}
              {repoUrl && (
                <div style={{
                  fontSize: 11,
                  color: urlValidation.valid ? "#16a34a" : "#dc2626",
                  marginTop: 6,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 4
                }}>
                  {urlValidation.valid ? <FaCheckCircle size={12} /> : <FaExclamationTriangle size={12} />}
                  <span>{urlValidation.valid ? "Valid repository URL" : "Invalid URL format"}</span>
                </div>
              )}

              {!shouldShowPatInput && (
                <div style={{ fontSize: 11, color: "#64748b", marginTop: 8, display: "flex", justifyContent: "center", gap: 6, flexWrap: "wrap" }}>
                  <span>Public repository or</span>
                  <button
                    type="button"
                    onClick={() => {
                      setIsPrivateRepo(true);
                      resetAccessTokenValidationState();
                      onError("");
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#2563eb",
                      cursor: "pointer",
                      fontSize: 11,
                      fontWeight: 600,
                      padding: 0,
                      textDecoration: "underline",
                    }}
                  >
                    Need a PAT?
                  </button>
                </div>
              )}

              {repoAccessCheckLoading && !shouldShowPatInput && (
                <div style={{ fontSize: 11, color: "#2563eb", marginTop: 6 }}>
                  Checking repository access...
                </div>
              )}

              {shouldShowPatInput && (
                <div style={{ marginTop: 12, textAlign: "left", width: "100%" }}>
                  <div
                    style={{
                      border: "1px solid #fbbf24",
                      borderRadius: 12,
                      padding: 12,
                      background: "#fffbeb",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: 12, fontWeight: 700, color: "#9a3412" }}>
                      <FaLock size={12} />
                      <span>{tokenCardTitle}</span>
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      <input
                        type="password"
                        style={{
                          flex: 1,
                          padding: "6px 10px",
                          borderRadius: 6,
                          border: "1px solid #cbd5e1",
                          fontSize: 12,
                          background: "#ffffff",
                        }}
                        value={showEnterpriseToken ? githubToken : patToken}
                        onChange={(e) => {
                          resetAccessTokenValidationState();
                          if (showEnterpriseToken) {
                            setGithubToken(e.target.value);
                          } else {
                            setPatToken(e.target.value);
                          }
                        }}
                        placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                        autoComplete="off"
                      />
                      <button
                        type="button"
                        style={{
                          padding: "6px 12px",
                          borderRadius: 6,
                          background: "#2563eb",
                          color: "#ffffff",
                          border: "none",
                          fontSize: 12,
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                        disabled={accessTokenValidationState === "validating"}
                        onClick={() => void handleAccessTokenValidate()}
                      >
                        {accessTokenValidationState === "validating" ? "..." : "Validate"}
                      </button>
                    </div>
                    <div style={{ fontSize: 11, color: tokenStatusColor, marginTop: 6, display: "flex", alignItems: "center", gap: 4 }}>
                      {tokenStatusIcon}
                      <span>{accessTokenValidationMessage || "Provide a PAT with repo scope."}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <button
              type="button"
              className="connect-primary-btn is-blue"
              disabled={
                connecting ||
                !urlValidation.valid ||
                (shouldShowPatInput && accessTokenValidationState !== "valid")
              }
              onClick={() => void handleRepositoryContinue()}
            >
              <span>{connecting ? "Verifying repository..." : "Connect Repository"}</span>
              <span style={{ fontSize: 16 }}>→</span>
            </button>
          </div>

          {/* Center OR Badge */}
          <div className="connect-or-separator">
            <div className="connect-or-circle">OR</div>
          </div>

          {/* Card 2: Upload Local Project */}
          <div className="connect-action-card">
            <div className="connect-card-accent-upload" />
            <div className="connect-card-icon-badge is-green">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                <line x1="12" y1="11" x2="12" y2="17"></line>
                <polyline points="9 14 12 11 15 14"></polyline>
              </svg>
            </div>
            <h2 className="connect-card-heading">Upload Local Project</h2>
            <p className="connect-card-desc">
              Upload a ZIP file or select a folder from your machine to get started.
            </p>

            {/* Hidden Inputs for folder & zip */}
            <input
              ref={(el) => {
                if (el) {
                  folderInputRef.current = el;
                  el.setAttribute("webkitdirectory", "");
                  el.setAttribute("directory", "");
                }
              }}
              type="file"
              multiple
              style={{ display: "none" }}
              onChange={(e) => handleLocalProjectFilesChange(e.target.files)}
            />
            <input
              ref={zipInputRef}
              type="file"
              accept=".zip"
              style={{ display: "none" }}
              onChange={(e) => handleLocalProjectFilesChange(e.target.files)}
            />

            <div className="connect-upload-options">
              <button
                type="button"
                className="connect-upload-pill"
                onClick={() => folderInputRef.current?.click()}
              >
                <FaFolderOpen />
                <span>Select Folder</span>
              </button>
              <button
                type="button"
                className="connect-upload-pill"
                onClick={() => zipInputRef.current?.click()}
              >
                <FaFileAlt />
                <span>Select ZIP</span>
              </button>
            </div>

            {localProjectUploadFiles.length > 0 && (
              <div style={{ fontSize: 12, color: "#166534", marginBottom: 10, fontWeight: 600 }}>
                ✓ Selected {localProjectUploadFiles.length} file{localProjectUploadFiles.length === 1 ? "" : "s"}
              </div>
            )}
            {localProjectUploadWarning && (
              <div style={{ fontSize: 11, color: "#b45309", marginBottom: 8 }}>{localProjectUploadWarning}</div>
            )}
            {localProjectUploadCompressing && (
              <div style={{ fontSize: 11, color: "#0f766e", marginBottom: 8 }}>Compressing files...</div>
            )}
            {localProjectUploadError && (
              <div style={{ fontSize: 11, color: "#b91c1c", marginBottom: 8 }}>{localProjectUploadError}</div>
            )}

            <button
              type="button"
              className="connect-primary-btn is-green"
              disabled={
                localProjectUploadLoading ||
                localProjectCapabilities?.enabled === false
              }
              onClick={() => {
                if (localProjectUploadFiles.length > 0) {
                  void handleLocalProjectUpload();
                } else {
                  folderInputRef.current?.click();
                }
              }}
            >
              <span>
                {localProjectUploadLoading
                  ? "Uploading..."
                  : localProjectUploadFiles.length > 0
                    ? "Upload Project"
                    : "Upload Project"}
              </span>
              <span style={{ fontSize: 16 }}>→</span>
            </button>
          </div>
        </div>

        {/* APEX Migration Engine Process Section */}
        <div className="connect-engine-section">
          <div className="connect-engine-badge-wrap">
            <span className="connect-engine-badge">
              APEX Migration Engine
            </span>
          </div>

          <div className="connect-engine-steps-row">
            {/* 1. Analyze */}
            <div className="connect-engine-step">
              <div className="connect-engine-step-icon is-analyze">
                <FaSearch />
              </div>
              <div className="connect-engine-step-info">
                <span className="connect-engine-step-title">Analyze</span>
                <span className="connect-engine-step-desc">Deep scan of your codebase</span>
              </div>
            </div>

            <div className="connect-engine-arrow">→</div>

            {/* 2. Understand */}
            <div className="connect-engine-step">
              <div className="connect-engine-step-icon is-understand">
                <FaProjectDiagram />
              </div>
              <div className="connect-engine-step-info">
                <span className="connect-engine-step-title">Understand</span>
                <span className="connect-engine-step-desc">Dependencies &amp; impact analysis</span>
              </div>
            </div>

            <div className="connect-engine-arrow">→</div>

            {/* 3. Strategize */}
            <div className="connect-engine-step">
              <div className="connect-engine-step-icon is-strategize">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                </svg>
              </div>
              <div className="connect-engine-step-info">
                <span className="connect-engine-step-title">Strategize</span>
                <span className="connect-engine-step-desc">Smart migration recommendations</span>
              </div>
            </div>

            <div className="connect-engine-arrow">→</div>

            {/* 4. Modernize */}
            <div className="connect-engine-step">
              <div className="connect-engine-step-icon is-modernize">
                <FaRocket />
              </div>
              <div className="connect-engine-step-info">
                <span className="connect-engine-step-title">Modernize</span>
                <span className="connect-engine-step-desc">Automated &amp; guided modernization</span>
              </div>
            </div>

            <div className="connect-engine-arrow">→</div>

            {/* 5. Validate */}
            <div className="connect-engine-step">
              <div className="connect-engine-step-icon is-validate">
                <FaShieldAlt />
              </div>
              <div className="connect-engine-step-info">
                <span className="connect-engine-step-title">Validate</span>
                <span className="connect-engine-step-desc">Test and verify migration success</span>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Grid: Project Intelligence & Migration Readiness (Temporarily Hidden) */}
        {/*
        <div className="connect-bottom-grid">
          <div className="connect-bottom-card">
            <div>
              <div className="connect-bottom-card-header">
                <span className="connect-bottom-card-title">Project Intelligence</span>
                <span className="connect-sample-preview-tag">(Sample Preview)</span>
                <FaInfoCircle className="connect-info-icon" title="Project Intelligence Preview" />
              </div>

              <div className="connect-metrics-row">
                <div className="connect-metric-subcard">
                  <div className="connect-metric-icon" style={{ color: "#2563eb" }}>
                    <FaCoffee />
                  </div>
                  <span className="connect-metric-label">Java Version</span>
                  <span className="connect-metric-value" style={{ color: "#2563eb" }}>8</span>
                  <span className="connect-metric-subtext">Detected</span>
                </div>

                <div className="connect-metric-subcard">
                  <div className="connect-metric-icon" style={{ color: "#ea580c", fontWeight: 900, fontStyle: "italic" }}>
                    M
                  </div>
                  <span className="connect-metric-label">Build Tool</span>
                  <span className="connect-metric-value" style={{ color: "#ea580c", fontSize: 16 }}>Maven</span>
                  <span className="connect-metric-subtext">pom.xml detected</span>
                </div>

                <div className="connect-metric-subcard">
                  <div className="connect-metric-icon" style={{ color: "#16a34a" }}>
                    <FaFlask />
                  </div>
                  <span className="connect-metric-label">Test Framework</span>
                  <span className="connect-metric-value" style={{ color: "#16a34a", fontSize: 16 }}>JUnit</span>
                  <span className="connect-metric-subtext" style={{ color: "#16a34a" }}>124 Tests</span>
                </div>

                <div className="connect-metric-subcard">
                  <div className="connect-metric-icon" style={{ color: "#7c3aed" }}>
                    <FaFileCode />
                  </div>
                  <span className="connect-metric-label">Total Files</span>
                  <span className="connect-metric-value" style={{ color: "#7c3aed" }}>386</span>
                  <span className="connect-metric-subtext">Source Files</span>
                </div>

                <div className="connect-metric-subcard">
                  <div className="connect-metric-icon" style={{ color: "#0d9488" }}>
                    <FaCode />
                  </div>
                  <span className="connect-metric-label">Frameworks</span>
                  <span className="connect-metric-value" style={{ color: "#0d9488", fontSize: 14 }}>Spring Boot</span>
                  <span className="connect-metric-subtext">+ 3 more</span>
                </div>
              </div>
            </div>

            <div className="connect-card-action-link" onClick={() => {}}>
              <span>View Detailed Analysis</span>
              <span>→</span>
            </div>
          </div>

          <div className="connect-bottom-card">
            <div>
              <div className="connect-bottom-card-header">
                <span className="connect-bottom-card-title">Migration Readiness</span>
                <FaInfoCircle className="connect-info-icon" title="Readiness based on dependency and framework compatibility" />
              </div>

              <div className="connect-readiness-body">
                <div className="connect-readiness-gauge-col">
                  <div className="connect-readiness-gauge-wrap">
                    <svg width="96" height="96" viewBox="0 0 96 96">
                      <circle
                        cx="48"
                        cy="48"
                        r="40"
                        fill="none"
                        stroke="#f1f5f9"
                        strokeWidth="8"
                      />
                      <circle
                        cx="48"
                        cy="48"
                        r="40"
                        fill="none"
                        stroke="#16a34a"
                        strokeWidth="8"
                        strokeDasharray={251.2}
                        strokeDashoffset={251.2 * (1 - 0.87)}
                        strokeLinecap="round"
                        transform="rotate(-90 48 48)"
                      />
                    </svg>
                    <span className="connect-gauge-center-text">87%</span>
                  </div>
                  <span className="connect-readiness-status-badge">
                    <FaRocket size={12} />
                    <span>High Readiness</span>
                  </span>
                </div>

                <div className="connect-readiness-checklist">
                  <div className="connect-checklist-item">
                    <FaCheckCircle className="connect-checklist-item is-check" />
                    <span>Java version detected</span>
                  </div>
                  <div className="connect-checklist-item">
                    <FaCheckCircle className="connect-checklist-item is-check" />
                    <span>Build system detected</span>
                  </div>
                  <div className="connect-checklist-item">
                    <FaCheckCircle className="connect-checklist-item is-check" />
                    <span>Test framework detected</span>
                  </div>
                  <div className="connect-checklist-item">
                    <FaExclamationTriangle className="connect-checklist-item is-warn" />
                    <span>3 Deprecated dependencies</span>
                  </div>
                  <div className="connect-checklist-item">
                    <FaExclamationTriangle className="connect-checklist-item is-warn" />
                    <span>2 Potential risks</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="connect-card-action-link" onClick={() => {}}>
              <span>View Details</span>
              <span>→</span>
            </div>
          </div>
        </div>
        */}
      </div>
    </div>
  );
}
