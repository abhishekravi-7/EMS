import React, { useRef, useState, useEffect } from "react";
import {
  FaCheckCircle,
  FaExclamationTriangle,
  FaFileAlt,
  FaFolderOpen,
  FaFolder,
  FaJava,
  FaCodeBranch,
  FaGithub,
  FaInfoCircle,
  FaLock,
  FaProjectDiagram,
  FaRocket,
  FaSearch,
  FaShieldAlt,
  FaFlask,
  FaPlayCircle,
  FaLink,
} from "react-icons/fa";
import { useAuth } from "@/shared/context/AuthContext";
import { getUserSettings } from "@/features/admin/services/adminService";
import {
  useRepositoryConnect,
  normalizeGithubUrl,
  buildConnectUrl,
  isEnterpriseGithub,
} from "../hooks/useRepositoryConnect";
import {
  fetchRecentRepositories,
  getRepoVisibility,
  connectRepository,
  type RecentRepository,
} from "../services/connectService";
import { isPrivateRepoAccessError } from "@/shared/utils/repoAccessError";
import "../pages/ConnectPage.css";

interface ConnectStepViewProps {
  connect: ReturnType<typeof useRepositoryConnect>;
  onError: (message: string) => void;
  onClearRepoAnalysis: () => void;
}

export function ConnectStepView({ connect, onError, onClearRepoAnalysis }: ConnectStepViewProps) {
  const { currentUser } = useAuth();
  const [recentRepos, setRecentRepos] = useState<RecentRepository[]>([]);
  const [loadingRecent, setLoadingRecent] = useState(true);

  useEffect(() => {
    fetchRecentRepositories()
      .then(data => {
        setRecentRepos(Array.isArray(data) ? data.slice(0, 5) : []);
        setLoadingRecent(false);
      })
      .catch(err => {
        console.error("Failed to load recent repos:", err);
        setLoadingRecent(false);
      });
  }, []);
  const {
    repoUrl,
    setRepoUrl,
    isJUnitOnly,
    setIsJUnitOnly,
    selectedRepo,
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
    localProjectUploadFiles,
    localProjectUploadLoading,
    localProjectUploadCompressing,
    localProjectUploadError,
    localProjectUploadWarning,
    urlValidation,
    showEnterpriseToken,
    repoVisibility,
    repoErrorMessage,
    setIsPatModeOpen,
    shouldShowPatInput,
    resetAccessTokenValidationState,
    handleAccessTokenValidate,
    handleRepositoryContinue,
    handleLocalProjectFilesChange,
    handleLocalProjectUpload,
    isLocalRepoRef,
  } = connect;

  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const zipInputRef = useRef<HTMLInputElement | null>(null);
  const tokenCardTitle = showEnterpriseToken ? "Enterprise Access Token" : "Personal Access Token";

  const tokenStatusColor =
    accessTokenValidationState === "valid"
      ? "#166534"
      : accessTokenValidationState === "invalid"
        ? "#b45309"
        : accessTokenValidationState === "validating"
          ? "#2563eb"
          : "#9a3412";
  const tokenStatusIcon =
    accessTokenValidationState === "valid"
      ? <FaCheckCircle />
      : accessTokenValidationState === "invalid"
        ? <FaExclamationTriangle />
        : <FaInfoCircle />;

  const isLocalProject = Boolean(
    isLocalRepoRef(selectedRepo?.url) ||
    isLocalRepoRef(repoUrl) ||
    localProjectUploadFiles.length > 0
  );

  // Track which card is active so the other ones dim
  const [activeCard, setActiveCard] = React.useState<"github" | "upload" | "junit" | null>(() => {
    if (isJUnitOnly) return "junit";
    if (repoUrl.trim() && !isLocalRepoRef(repoUrl)) return "github";
    if (localProjectUploadFiles.length > 0 || isLocalRepoRef(selectedRepo?.url)) return "upload";
    return null;
  });
  const [junitInputMode, setJunitInputMode] = React.useState<"github" | "upload">(
    isJUnitOnly && (isLocalProject || !repoUrl.trim() || isLocalRepoRef(repoUrl)) ? "upload" : "github"
  );

  // Dedicated independent state for JUnit Card (Card 3)
  const [junitRepoUrl, setJunitRepoUrl] = useState<string>("");
  const [junitRepoVisibility, setJunitRepoVisibility] = useState<"unknown" | "checking" | "public" | "private" | "not_found">("unknown");
  const [junitRepoErrorMessage, setJunitRepoErrorMessage] = useState("");
  const [junitRepoAccessCheckLoading, setJunitRepoAccessCheckLoading] = useState(false);
  const [junitPatToken, setJunitPatToken] = useState("");
  const [junitIsPatModeOpen, setJunitIsPatModeOpen] = useState(false);
  const [junitIsPrivateRepo, setJunitIsPrivateRepo] = useState(false);
  const [junitAccessTokenValidationState, setJunitAccessTokenValidationState] = useState<"idle" | "validating" | "valid" | "invalid">("idle");
  const [junitAccessTokenValidationMessage, setJunitAccessTokenValidationMessage] = useState("");

  const junitUrlValidation = React.useMemo(() => {
    return junitRepoUrl.trim() ? normalizeGithubUrl(junitRepoUrl) : { valid: false, normalizedUrl: "", message: "" };
  }, [junitRepoUrl]);

  const junitShowEnterpriseToken = Boolean(junitRepoUrl.trim() && isEnterpriseGithub(junitUrlValidation.normalizedUrl || junitRepoUrl));
  const junitShouldShowPatInput = Boolean(junitShowEnterpriseToken || junitIsPatModeOpen || junitIsPrivateRepo);

  // Debounced repository visibility detection for JUnit Card
  useEffect(() => {
    if (!junitUrlValidation.valid) {
      setJunitRepoVisibility("unknown");
      setJunitRepoErrorMessage("");
      setJunitRepoAccessCheckLoading(false);
      return;
    }

    const normalizedUrl = junitUrlValidation.normalizedUrl;

    if (junitShowEnterpriseToken) {
      setJunitRepoVisibility("private");
      setJunitRepoErrorMessage("");
      setJunitIsPrivateRepo(true);
      setJunitIsPatModeOpen(true);
      setJunitRepoAccessCheckLoading(false);
      return;
    }

    let cancelled = false;
    setJunitRepoAccessCheckLoading(true);
    setJunitRepoVisibility("checking");
    setJunitRepoErrorMessage("");

    const timer = setTimeout(() => {
      getRepoVisibility(normalizedUrl)
        .then((visibility) => {
          if (cancelled) return;
          if (visibility.visibility === "not_found") {
            setJunitRepoVisibility("not_found");
            setJunitIsPrivateRepo(false);
            setJunitIsPatModeOpen(false);
            setJunitRepoErrorMessage(visibility.message || "Repository not found. Please check the URL.");
            return;
          }
          if (visibility.requires_token || visibility.visibility === "private" || visibility.visibility === "private_or_inaccessible") {
            setJunitRepoVisibility("private");
            setJunitIsPrivateRepo(true);
            setJunitIsPatModeOpen(true);
            setJunitRepoErrorMessage("");
            setJunitAccessTokenValidationState("idle");
            setJunitAccessTokenValidationMessage("");
          } else {
            setJunitRepoVisibility("public");
            setJunitIsPrivateRepo(false);
            setJunitIsPatModeOpen(false);
            setJunitRepoErrorMessage("");
          }
        })
        .catch((err) => {
          if (cancelled) return;
          const isNotFound = err?.status === 404;
          const isUrlError = err?.status === 400;
          const message = err instanceof Error ? err.message : "";
          if (isNotFound) {
            setJunitRepoVisibility("not_found");
            setJunitIsPrivateRepo(false);
            setJunitIsPatModeOpen(false);
            setJunitRepoErrorMessage(message || "Repository not found. Please check the URL.");
          } else if (!isUrlError && isPrivateRepoAccessError(message)) {
            setJunitRepoVisibility("private");
            setJunitIsPrivateRepo(true);
            setJunitIsPatModeOpen(true);
            setJunitRepoErrorMessage("");
            setJunitAccessTokenValidationState("idle");
            setJunitAccessTokenValidationMessage("");
          } else {
            setJunitRepoVisibility("not_found");
            setJunitIsPrivateRepo(false);
            setJunitIsPatModeOpen(false);
            setJunitRepoErrorMessage(message || "Failed to verify repository.");
          }
        })
        .finally(() => {
          if (!cancelled) {
            setJunitRepoAccessCheckLoading(false);
          }
        });
    }, 500);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [junitUrlValidation.valid, junitUrlValidation.normalizedUrl, junitShowEnterpriseToken]);

  const handleJunitAccessTokenValidate = async () => {
    if (!junitUrlValidation.valid) return;
    const token = junitPatToken.trim();
    if (!token) {
      setJunitAccessTokenValidationState("invalid");
      setJunitAccessTokenValidationMessage("Enter a GitHub Personal Access Token with repo scope.");
      return;
    }
    setJunitAccessTokenValidationState("validating");
    setJunitAccessTokenValidationMessage("Validating PAT...");
    try {
      const connectUrl = buildConnectUrl(junitUrlValidation.normalizedUrl);
      if (connectUrl) {
        const result = await connectRepository(connectUrl, token);
        const detectedPrivate = result.repoVisibility === "PRIVATE";
        setJunitIsPrivateRepo(detectedPrivate);
        setJunitRepoVisibility(detectedPrivate ? "private" : "public");
        setJunitAccessTokenValidationState("valid");
        setJunitAccessTokenValidationMessage("Token validated successfully.");
      }
    } catch (err: unknown) {
      setJunitAccessTokenValidationState("invalid");
      const message = err instanceof Error ? err.message : "Invalid PAT or repository access denied.";
      setJunitAccessTokenValidationMessage(message);
    }
  };

  const renderJunitPatInputSection = (buttonBgColor: string = "#7c3aed") => (
    <div style={{ marginTop: 12, textAlign: "left", width: "100%" }}>
      <div
        style={{
          border: "1px solid #c4b5fd",
          borderRadius: 12,
          padding: 12,
          background: "#faf5ff",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, color: "#6b21a8" }}>
            <FaLock size={12} />
            <span>{junitShowEnterpriseToken ? "Enterprise Access Token" : "Personal Access Token"}</span>
          </div>
          <button
            type="button"
            onClick={() => {
              setJunitIsPatModeOpen(false);
              setJunitAccessTokenValidationState("idle");
              setJunitAccessTokenValidationMessage("");
            }}
            style={{
              background: "none",
              border: "none",
              color: "#6b21a8",
              cursor: "pointer",
              fontSize: 11,
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 6px",
              borderRadius: 4,
            }}
            title="Return to normal repository view"
          >
            <span>← Back</span>
          </button>
        </div>

        <p style={{ fontSize: 11, color: "#581c87", margin: "0 0 8px 0", lineHeight: 1.4 }}>
          {junitShowEnterpriseToken
            ? "A GitHub Enterprise token is required to access this repository."
            : "A Personal Access Token (PAT) with repo scope is required to access a private repository."}
        </p>

        <div style={{ display: "flex", width: "100%", gap: 8 }}>
          <input
            type="password"
            style={{
              flex: 1,
              minWidth: 0,
              boxSizing: "border-box",
              padding: "6px 10px",
              borderRadius: 6,
              border: `1px solid ${
                junitAccessTokenValidationState === "valid"
                  ? "#22c55e"
                  : junitAccessTokenValidationState === "invalid"
                    ? "#ef4444"
                    : "#cbd5e1"
              }`,
              fontSize: 12,
              background: "#ffffff",
            }}
            value={junitPatToken}
            onChange={(e) => {
              setJunitAccessTokenValidationState("idle");
              setJunitAccessTokenValidationMessage("");
              setJunitPatToken(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void handleJunitAccessTokenValidate();
              }
            }}
            placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
            autoComplete="off"
          />
          <button
            type="button"
            onClick={() => void handleJunitAccessTokenValidate()}
            disabled={
              junitAccessTokenValidationState === "validating" ||
              !junitPatToken.trim()
            }
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              background: junitAccessTokenValidationState === "valid" ? "#16a34a" : buttonBgColor,
              color: "#ffffff",
              border: "none",
              fontWeight: 600,
              fontSize: 12,
              cursor: (junitAccessTokenValidationState === "validating" || !junitPatToken.trim()) ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
              opacity: (junitAccessTokenValidationState === "validating" || !junitPatToken.trim()) ? 0.6 : 1,
              transition: "background 0.2s ease",
            }}
          >
            {junitAccessTokenValidationState === "validating" ? "Validating..." : junitAccessTokenValidationState === "valid" ? "Validated ✓" : "Validate"}
          </button>
        </div>
        <div style={{ fontSize: 11, color: junitAccessTokenValidationState === "valid" ? "#166534" : junitAccessTokenValidationState === "invalid" ? "#b45309" : "#6b21a8", marginTop: 6, display: "flex", alignItems: "center", gap: 4 }}>
          {junitAccessTokenValidationState === "valid" ? <FaCheckCircle /> : junitAccessTokenValidationState === "invalid" ? <FaExclamationTriangle /> : <FaInfoCircle />}
          <span>{junitAccessTokenValidationMessage || "Provide a PAT with repo scope."}</span>
        </div>
      </div>
    </div>
  );

  const renderPatInputSection = (buttonBgColor: string = "#2563eb") => (
    <div style={{ marginTop: 12, textAlign: "left", width: "100%" }}>
      <div
        style={{
          border: "1px solid #fbbf24",
          borderRadius: 12,
          padding: 12,
          background: "#fffbeb",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, color: "#9a3412" }}>
            <FaLock size={12} />
            <span>{tokenCardTitle}</span>
          </div>
          <button
            type="button"
            onClick={() => {
              setIsPatModeOpen(false);
              resetAccessTokenValidationState();
              onError("");
            }}
            style={{
              background: "none",
              border: "none",
              color: "#92400e",
              cursor: "pointer",
              fontSize: 11,
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 6px",
              borderRadius: 4,
            }}
            title="Return to normal repository view"
          >
            <span>← Back</span>
          </button>
        </div>

        <p style={{ fontSize: 11, color: "#78350f", margin: "0 0 8px 0", lineHeight: 1.4 }}>
          {showEnterpriseToken
            ? "A GitHub Enterprise token is required to analyze this repository."
            : "A Personal Access Token (PAT) with repo scope is required to access a private repository."}
        </p>

        <div style={{ display: "flex", width: "100%", gap: 8 }}>
          <input
            type="password"
            style={{
              flex: 1,
              minWidth: 0,
              boxSizing: "border-box",
              padding: "6px 10px",
              borderRadius: 6,
              border: `1px solid ${
                accessTokenValidationState === "valid"
                  ? "#22c55e"
                  : accessTokenValidationState === "invalid"
                    ? "#ef4444"
                    : "#cbd5e1"
              }`,
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
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void handleAccessTokenValidate();
              }
            }}
            onBlur={() => {
              if ((showEnterpriseToken ? githubToken : patToken).trim() && accessTokenValidationState === "idle") {
                void handleAccessTokenValidate();
              }
            }}
            placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
            autoComplete="off"
          />
          <button
            type="button"
            onClick={() => void handleAccessTokenValidate()}
            disabled={
              accessTokenValidationState === "validating" ||
              !(showEnterpriseToken ? githubToken : patToken).trim()
            }
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              background: accessTokenValidationState === "valid" ? "#16a34a" : buttonBgColor,
              color: "#ffffff",
              border: "none",
              fontWeight: 600,
              fontSize: 12,
              cursor: (accessTokenValidationState === "validating" || !(showEnterpriseToken ? githubToken : patToken).trim()) ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
              opacity: (accessTokenValidationState === "validating" || !(showEnterpriseToken ? githubToken : patToken).trim()) ? 0.6 : 1,
              transition: "background 0.2s ease",
            }}
          >
            {accessTokenValidationState === "validating" ? "Validating..." : accessTokenValidationState === "valid" ? "Validated ✓" : "Validate"}
          </button>
        </div>
        <div style={{ fontSize: 11, color: tokenStatusColor, marginTop: 6, display: "flex", alignItems: "center", gap: 4 }}>
          {tokenStatusIcon}
          <span>{accessTokenValidationMessage || "Provide a PAT with repo scope."}</span>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8, paddingTop: 6, borderTop: "1px solid #fde68a" }}>
          <button
            type="button"
            onClick={() => {
              setIsPatModeOpen(false);
              resetAccessTokenValidationState();
              onError("");
            }}
            style={{
              background: "none",
              border: "none",
              color: "#475569",
              cursor: "pointer",
              fontSize: 11,
              fontWeight: 600,
              padding: 0,
            }}
          >
            Use repository without PAT
          </button>
          {(showEnterpriseToken ? githubToken : patToken) && (
            <button
              type="button"
              onClick={() => {
                if (showEnterpriseToken) setGithubToken("");
                else setPatToken("");
                resetAccessTokenValidationState();
              }}
              style={{
                background: "none",
                border: "none",
                color: "#dc2626",
                cursor: "pointer",
                fontSize: 11,
                fontWeight: 500,
                padding: 0,
              }}
            >
              Clear PAT
            </button>
          )}
        </div>
      </div>
    </div>
  );

  // Handle user settings pre-filling
  React.useEffect(() => {
    let isMounted = true;
    if (currentUser) {
      getUserSettings().then((settings) => {
        if (isMounted) {
          const isLocal = isLocalRepoRef(selectedRepo?.url) || isLocalRepoRef(repoUrl) || localProjectUploadFiles.length > 0;
          if (!repoUrl && !isLocal && settings.github_config?.repo_url) {
            setRepoUrl(settings.github_config.repo_url);
          }
          const token = settings.github_config?.pat || settings.github_config?.target_token;
          if (!patToken && !isLocal && token && token !== "********" && !token.startsWith("****************")) {
            setPatToken(token);
            setIsPrivateRepo(true);
          }
        }
      }).catch(err => {
        console.error("Failed to load user settings for connect page prepopulation:", err);
      });
    }
    return () => { isMounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser]);

  // Update active card based on inputs
  React.useEffect(() => {
    // If user has focused or typed in a specific card, don't clobber it if that card has input
    if (activeCard === "junit") {
      if (junitRepoUrl.trim() || (junitInputMode === "upload" && localProjectUploadFiles.length > 0)) {
        return;
      }
    } else if (activeCard === "upload") {
      if (localProjectUploadFiles.length > 0) {
        return;
      }
    } else if (activeCard === "github") {
      if (repoUrl.trim() && !isLocalRepoRef(repoUrl)) {
        return;
      }
    }

    if (repoUrl.trim() && !isLocalRepoRef(repoUrl)) {
      setActiveCard("github");
    } else if (junitRepoUrl.trim()) {
      setActiveCard("junit");
    } else if (localProjectUploadFiles.length > 0) {
      setActiveCard("upload");
    } else {
      setActiveCard(null);
    }
  }, [repoUrl, junitRepoUrl, localProjectUploadFiles.length, junitInputMode, activeCard, isLocalRepoRef]);

  const isGithubDisabled = activeCard === "upload" || activeCard === "junit";
  const isUploadDisabled = activeCard === "github" || activeCard === "junit";
  const isJunitDisabled = activeCard === "github" || activeCard === "upload";
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
        </div>

        {/* Action Cards: GitHub Repository & Upload Local Project */}
        <div className="connect-cards-container">
          {/* Card 1: Connect GitHub Repository */}
          <div
            className={`connect-action-card${isGithubDisabled ? " is-card-disabled" : ""}`}
            style={{
              opacity: isGithubDisabled ? 0.6 : 1,
              filter: isGithubDisabled ? "grayscale(100%)" : "none",
              cursor: isGithubDisabled ? "pointer" : "default",
              transition: "opacity 0.2s ease, filter 0.2s ease",
            }}
            onClick={() => {
              if (isGithubDisabled) {
                setActiveCard("github");
              }
            }}
          >
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
                value={isLocalRepoRef(repoUrl) ? "" : repoUrl}
                onFocus={() => {
                  setActiveCard("github");
                }}
                onChange={(e) => {
                  setRepoUrl(e.target.value);
                  setSelectedRepo(null);
                  onClearRepoAnalysis();
                  setIsPrivateRepo(false);
                  setIsPatModeOpen(false);
                  setPatToken("");
                  resetAccessTokenValidationState();
                  onError("");
                  setActiveCard(e.target.value.trim() ? "github" : null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && urlValidation.valid) {
                    void handleRepositoryContinue();
                  }
                }}
                placeholder="https://github.com/owner/repository"
                style={{
                  borderColor: repoUrl.trim() && !isLocalRepoRef(repoUrl) && (!urlValidation.valid || repoVisibility === "not_found")
                    ? "#ef4444"
                    : repoVisibility === "public" || repoVisibility === "private"
                      ? "#22c55e"
                      : repoUrl.trim() && !isLocalRepoRef(repoUrl)
                        ? "#94a3b8"
                        : "#cbd5e1",
                }}
              />

              {/* Pre-input PAT helper when URL is empty */}
              {!repoUrl && !shouldShowPatInput && (
                <div style={{ marginTop: 6, display: "flex", justifyContent: "center", alignItems: "center", minHeight: 20, fontSize: 11, color: "#64748b", gap: 6 }}>
                  
                  <button
                    type="button"
                    onClick={() => {
                      setIsPatModeOpen(true);
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
                   
                  </button>
                </div>
              )}

              {/* URL Validation & Visibility Message in One Line */}
              {repoUrl && !isLocalRepoRef(repoUrl) && (
                <div style={{ marginTop: 6, display: "flex", justifyContent: "center", alignItems: "center", minHeight: 20 }}>
                  {!urlValidation.valid ? (
                    <div style={{
                      fontSize: 11,
                      color: "#dc2626",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      fontWeight: 600,
                    }}>
                      <FaExclamationTriangle size={12} />
                      <span>{urlValidation.message || "Invalid repository URL"}</span>
                    </div>
                  ) : repoAccessCheckLoading || repoVisibility === "checking" ? (
                    <div style={{
                      fontSize: 11,
                      color: "#2563eb",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      fontWeight: 600,
                    }}>
                      <FaInfoCircle size={11} />
                      <span>Checking repository visibility...</span>
                    </div>
                  ) : repoVisibility === "not_found" ? (
                    <div style={{
                      fontSize: 11,
                      color: "#dc2626",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      fontWeight: 600,
                    }}>
                      <FaExclamationTriangle size={12} />
                      <span>{repoErrorMessage || "Repository not found. Please check the URL."}</span>
                    </div>
                  ) : repoVisibility === "private" ? (
                    <div style={{
                      fontSize: 11,
                      color: "#b45309",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      fontWeight: 600,
                      flexWrap: "wrap",
                      justifyContent: "center",
                    }}>
                      <span style={{ color: "#16a34a", display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <FaCheckCircle size={12} />
                        <span>Valid repository URL</span>
                      </span>
                      <span style={{ color: "#94a3b8" }}>•</span>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <FaLock size={10} />
                        <span>Private repository — PAT required</span>
                      </span>
                      {!shouldShowPatInput && (
                        <button
                          type="button"
                          onClick={() => {
                            setIsPatModeOpen(true);
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
                            marginLeft: 4,
                          }}
                        >
                          Need a PAT?
                        </button>
                      )}
                    </div>
                  ) : repoVisibility === "public" ? (
                    <div style={{
                      fontSize: 11,
                      color: "#16a34a",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      fontWeight: 600,
                      flexWrap: "wrap",
                      justifyContent: "center",
                    }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <FaCheckCircle size={12} />
                        <span>Valid repository URL</span>
                      </span>
                      <span style={{ color: "#94a3b8" }}>•</span>
                      <span>Public repository — no PAT required</span>
                    </div>
                  ) : (
                    <div style={{
                      fontSize: 11,
                      color: "#16a34a",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      fontWeight: 600,
                      flexWrap: "wrap",
                      justifyContent: "center",
                    }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <FaCheckCircle size={12} />
                        <span>Valid repository URL</span>
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* PAT Input Section */}
              {shouldShowPatInput && activeCard !== "junit" && renderPatInputSection("#2563eb")}
            </div>

            <button
              type="button"
              className="connect-primary-btn is-blue"
              disabled={
                connecting ||
                !urlValidation.valid ||
                repoVisibility === "not_found" ||
                repoVisibility === "checking" ||
                (shouldShowPatInput && accessTokenValidationState !== "valid")
              }
              onClick={() => {
                setIsJUnitOnly(false);
                void handleRepositoryContinue();
              }}
            >
              <span>{connecting ? "Verifying repository..." : "Connect Repository"}</span>
            </button>
          </div>

          {/* Center OR Badge */}
          <div className="connect-or-separator">
            <div className="connect-or-circle">OR</div>
          </div>

          {/* Card 2: Upload Local Project */}
          <div
            className={`connect-action-card${isUploadDisabled ? " is-card-disabled" : ""}`}
            style={{
              opacity: isUploadDisabled ? 0.6 : 1,
              filter: isUploadDisabled ? "grayscale(100%)" : "none",
              cursor: isUploadDisabled ? "pointer" : "default",
              transition: "opacity 0.2s ease, filter 0.2s ease",
            }}
            onClick={() => {
              if (isUploadDisabled) {
                setActiveCard("upload");
              }
            }}
          >
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
                  (el as unknown as Record<string, boolean>).webkitdirectory = true;
                }
              }}
              type="file"
              multiple
              style={{ display: "none" }}
              onClick={(e) => {
                (e.target as HTMLInputElement).value = "";
              }}
              onChange={(e) => { handleLocalProjectFilesChange(e.target.files); }}
            />
            <input
              ref={zipInputRef}
              type="file"
              accept=".zip,application/zip,application/x-zip-compressed"
              style={{ display: "none" }}
              onClick={(e) => {
                (e.target as HTMLInputElement).value = "";
              }}
              onChange={(e) => { handleLocalProjectFilesChange(e.target.files); }}
            />

            {/* Wrapped in same class as GitHub URL input box for vertical alignment */}
            <div className="connect-card-input-box" style={{ marginBottom: 43 }}>
              <div className="connect-upload-options" style={{ marginBottom: 0 }}>
                <button
                  type="button"
                  className="connect-upload-pill"
                  onClick={() => {
                    setActiveCard("upload");
                    folderInputRef.current?.click();
                  }}
                >
                  <FaFolderOpen />
                  <span>Select Folder</span>
                </button>
                <button
                  type="button"
                  className="connect-upload-pill"
                  onClick={() => {
                    setActiveCard("upload");
                    zipInputRef.current?.click();
                  }}
                >
                  <FaFileAlt />
                  <span>Select ZIP</span>
                </button>
              </div>
            </div>

            {activeCard === "upload" && localProjectUploadFiles.length > 0 && (
              <div style={{ fontSize: 12, color: "#166534", marginBottom: 10, fontWeight: 600 }}>
                ✓ Selected {localProjectUploadFiles.length} file{localProjectUploadFiles.length === 1 ? "" : "s"}
              </div>
            )}
            {activeCard === "upload" && localProjectUploadWarning && (
              <div style={{ fontSize: 11, color: "#b45309", marginBottom: 8 }}>{localProjectUploadWarning}</div>
            )}
            {activeCard === "upload" && localProjectUploadCompressing && (
              <div style={{ fontSize: 11, color: "#0f766e", marginBottom: 8 }}>Compressing files...</div>
            )}
            {activeCard === "upload" && localProjectUploadError && (
              <div style={{ fontSize: 11, color: "#b91c1c", marginBottom: 8 }}>{localProjectUploadError}</div>
            )}

            <button
              type="button"
              className="connect-primary-btn is-green"
              disabled={
                activeCard !== "upload" ||
                localProjectUploadFiles.length === 0 ||
                localProjectUploadLoading ||
                localProjectCapabilities?.enabled === false
              }
              onClick={() => {
                setIsJUnitOnly(false);
                if (localProjectUploadFiles.length > 0) {
                  void handleLocalProjectUpload();
                }
              }}
              title={
                localProjectUploadFiles.length === 0
                  ? "Please select a folder or ZIP file above first"
                  : "Upload selected project files"
              }
            >
              <span>
                {localProjectUploadLoading && activeCard === "upload"
                  ? "Uploading..."
                  : activeCard === "upload" && localProjectUploadFiles.length > 0
                    ? `Upload Project (${localProjectUploadFiles.length} file${localProjectUploadFiles.length === 1 ? "" : "s"})`
                    : "Upload Project"}
              </span>
            </button>
          </div>

          {/* Center OR Badge */}
          <div className="connect-or-separator">
            <div className="connect-or-circle">OR</div>
          </div>

          {/* Card 3: JUnit Test Engineering */}
          <div
            className={`connect-action-card${isJunitDisabled ? " is-card-disabled" : ""}`}
            style={{
              opacity: isJunitDisabled ? 0.6 : 1,
              filter: isJunitDisabled ? "grayscale(100%)" : "none",
              cursor: isJunitDisabled ? "pointer" : "default",
              transition: "opacity 0.2s ease, filter 0.2s ease",
            }}
            onClick={() => {
              if (isJunitDisabled) {
                setActiveCard("junit");
              }
            }}
          >
            <div className="connect-card-accent-junit" />
            <FaFileAlt style={{ position: "absolute", top: 16, right: 16, fontSize: 50, opacity: 0.08, color: "#7c3aed", pointerEvents: "none" }} />
            <div className="connect-card-icon-badge is-purple">
              <FaFlask size={28} />
            </div>
            <h2 className="connect-card-heading">JUnit Test</h2>
            <p className="connect-card-desc">
              Generate, execute and analyze JUnit tests for your Java project.
            </p>

            {/* Input Options: GitHub URL or ZIP Upload Toggle */}
            <div className="connect-card-input-box">
              <div style={{ display: "flex", gap: 6, marginBottom: 8, width: "100%" }}>
                <button
                  type="button"
                  onClick={() => setJunitInputMode("github")}
                  style={{
                    flex: 1,
                    padding: "4px 8px",
                    borderRadius: 6,
                    fontSize: 10.5,
                    fontWeight: 700,
                    border: "1px solid",
                    borderColor: junitInputMode === "github" ? "#7c3aed" : "#cbd5e1",
                    background: junitInputMode === "github" ? "#f3e8ff" : "#ffffff",
                    color: junitInputMode === "github" ? "#7c3aed" : "#64748b",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 4,
                  }}
                >
                  <FaGithub size={11} /> GitHub URL
                </button>
                <button
                  type="button"
                  onClick={() => setJunitInputMode("upload")}
                  style={{
                    flex: 1,
                    padding: "4px 8px",
                    borderRadius: 6,
                    fontSize: 10.5,
                    fontWeight: 700,
                    border: "1px solid",
                    borderColor: junitInputMode === "upload" ? "#7c3aed" : "#cbd5e1",
                    background: junitInputMode === "upload" ? "#f3e8ff" : "#ffffff",
                    color: junitInputMode === "upload" ? "#7c3aed" : "#64748b",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 4,
                  }}
                >
                  <FaFolderOpen size={11} /> Upload ZIP / Folder
                </button>
              </div>

              {junitInputMode === "github" ? (
                <div>
                  <input
                    type="text"
                    className="connect-text-input"
                    value={junitRepoUrl}
                    onFocus={() => {
                      setActiveCard("junit");
                    }}
                    onChange={(e) => {
                      const val = e.target.value;
                      setJunitRepoUrl(val);
                      setJunitIsPrivateRepo(false);
                      setJunitIsPatModeOpen(false);
                      setJunitPatToken("");
                      setJunitAccessTokenValidationState("idle");
                      setJunitAccessTokenValidationMessage("");
                      onError("");
                      setActiveCard(val.trim() ? "junit" : null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && junitUrlValidation.valid) {
                        setIsJUnitOnly(true);
                        void handleRepositoryContinue(junitUrlValidation.normalizedUrl || junitRepoUrl, junitPatToken, true);
                      }
                    }}
                    placeholder="https://github.com/owner/repository"
                    style={{
                      borderColor: junitRepoUrl.trim() && (!junitUrlValidation.valid || junitRepoVisibility === "not_found")
                        ? "#ef4444"
                        : junitRepoVisibility === "public" || junitRepoVisibility === "private"
                          ? "#22c55e"
                          : junitRepoUrl.trim()
                            ? "#94a3b8"
                            : "#cbd5e1",
                    }}
                  />
                  {junitRepoUrl.trim() && (
                    <div style={{ marginTop: 4, display: "flex", justifyContent: "center", alignItems: "center", minHeight: 18 }}>
                      {!junitUrlValidation.valid ? (
                        <div style={{ fontSize: 10.5, color: "#dc2626", display: "inline-flex", alignItems: "center", gap: 4, fontWeight: 600 }}>
                          <FaExclamationTriangle size={11} />
                          <span>{junitUrlValidation.message || "Invalid repository URL"}</span>
                        </div>
                      ) : junitRepoAccessCheckLoading || junitRepoVisibility === "checking" ? (
                        <div style={{ fontSize: 10.5, color: "#7c3aed", display: "inline-flex", alignItems: "center", gap: 4, fontWeight: 600 }}>
                          <FaInfoCircle size={10} />
                          <span>Checking repository visibility...</span>
                        </div>
                      ) : junitRepoVisibility === "not_found" ? (
                        <div style={{ fontSize: 10.5, color: "#dc2626", display: "inline-flex", alignItems: "center", gap: 4, fontWeight: 600 }}>
                          <FaExclamationTriangle size={11} />
                          <span>{junitRepoErrorMessage || "Repository not found."}</span>
                        </div>
                      ) : junitRepoVisibility === "private" ? (
                        <div style={{ fontSize: 10.5, color: "#b45309", display: "inline-flex", alignItems: "center", gap: 6, fontWeight: 600, flexWrap: "wrap", justifyContent: "center" }}>
                          <span style={{ color: "#16a34a", display: "inline-flex", alignItems: "center", gap: 4 }}>
                            <FaCheckCircle size={11} />
                            <span>Valid repository URL</span>
                          </span>
                          <span style={{ color: "#94a3b8" }}>•</span>
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                            <FaLock size={10} />
                            <span>Private repository — PAT required</span>
                          </span>
                          {!junitShouldShowPatInput && (
                            <button
                              type="button"
                              onClick={() => {
                                setJunitIsPatModeOpen(true);
                                setJunitAccessTokenValidationState("idle");
                                onError("");
                              }}
                              style={{
                                background: "none",
                                border: "none",
                                color: "#7c3aed",
                                cursor: "pointer",
                                fontSize: 10.5,
                                fontWeight: 600,
                                padding: 0,
                                textDecoration: "underline",
                                marginLeft: 2,
                              }}
                            >
                              Need a PAT?
                            </button>
                          )}
                        </div>
                      ) : junitRepoVisibility === "public" ? (
                        <div style={{ fontSize: 10.5, color: "#16a34a", display: "inline-flex", alignItems: "center", gap: 6, fontWeight: 600, flexWrap: "wrap", justifyContent: "center" }}>
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                            <FaCheckCircle size={11} />
                            <span>Valid repository URL</span>
                          </span>
                          <span style={{ color: "#94a3b8" }}>•</span>
                          <span>Public repository — no PAT required</span>
                        </div>
                      ) : null}
                    </div>
                  )}
                  {/* PAT Input Section for JUnit Card */}
                  {junitShouldShowPatInput && activeCard === "junit" && renderJunitPatInputSection("#7c3aed")}
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div className="connect-upload-options" style={{ marginBottom: 0 }}>
                    <button
                      type="button"
                      className="connect-upload-pill"
                      onClick={() => {
                        setActiveCard("junit");
                        folderInputRef.current?.click();
                      }}
                    >
                      <FaFolderOpen />
                      <span>Select Folder</span>
                    </button>
                    <button
                      type="button"
                      className="connect-upload-pill"
                      onClick={() => {
                        setActiveCard("junit");
                        zipInputRef.current?.click();
                      }}
                    >
                      <FaFileAlt />
                      <span>Select ZIP</span>
                    </button>
                  </div>
                  {activeCard === "junit" && localProjectUploadFiles.length > 0 && (
                    <div style={{ fontSize: 11, color: "#7c3aed", marginTop: 2, fontWeight: 600 }}>
                      ✓ Selected {localProjectUploadFiles.length} file{localProjectUploadFiles.length === 1 ? "" : "s"}
                    </div>
                  )}
                  {activeCard === "junit" && localProjectUploadWarning && (
                    <div style={{ fontSize: 11, color: "#b45309", marginTop: 2 }}>{localProjectUploadWarning}</div>
                  )}
                  {activeCard === "junit" && localProjectUploadCompressing && (
                    <div style={{ fontSize: 11, color: "#0f766e", marginTop: 2 }}>Compressing files...</div>
                  )}
                  {activeCard === "junit" && localProjectUploadError && (
                    <div style={{ fontSize: 11, color: "#b91c1c", marginTop: 2 }}>{localProjectUploadError}</div>
                  )}
                </div>
              )}
            </div>

            {/* Action Button */}
            <button
              type="button"
              className="connect-primary-btn is-purple"
              disabled={
                connecting ||
                localProjectUploadLoading ||
                (junitInputMode === "github" && (
                  activeCard !== "junit" ||
                  !junitUrlValidation.valid ||
                  junitRepoVisibility === "not_found" ||
                  junitRepoVisibility === "checking" ||
                  (junitShouldShowPatInput && junitAccessTokenValidationState !== "valid")
                )) ||
                (junitInputMode === "upload" && (activeCard !== "junit" || localProjectUploadFiles.length === 0))
              }
              onClick={() => {
                setIsJUnitOnly(true);
                if (junitInputMode === "github") {
                  void handleRepositoryContinue(junitUrlValidation.normalizedUrl || junitRepoUrl, junitPatToken, true);
                } else {
                  if (localProjectUploadFiles.length > 0) {
                    void handleLocalProjectUpload(true);
                  }
                }
              }}
            >
              <FaPlayCircle size={15} />
              <span>{connecting || localProjectUploadLoading ? "Preparing JUnit tests..." : "Start JUnit Testing →"}</span>
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


      {/* RECENT REPOSITORIES TABLE */}
      <div style={{ width: "100%", maxWidth: "1520px", margin: "24px auto 0", backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #e2e8f0", overflow: "hidden", boxShadow: "0 2px 12px rgba(15, 23, 42, 0.03)" }}>
        <div style={{ padding: "12px 24px", borderBottom: "1px solid #e2e8f0" }}>
          <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "#1e293b" }}>Recent Repositories</h3>
        </div>
        
        {loadingRecent ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#64748b" }}>Loading recent repositories...</div>
        ) : recentRepos.length === 0 ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#64748b" }}>No recent repositories found.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.875rem" }}>
              <thead style={{ backgroundColor: "#f8fafc", color: "#64748b", fontWeight: 600, borderBottom: "1px solid #e2e8f0" }}>
                <tr>
                  <th style={{ padding: "12px 24px", whiteSpace: "nowrap" }}>Repository Name</th>
                  <th style={{ padding: "12px 24px" }}>Owner</th>
                  <th style={{ padding: "12px 24px", whiteSpace: "nowrap" }}>Tech Stack</th>
                  <th style={{ padding: "12px 24px" }}>Components</th>
                  <th style={{ padding: "12px 24px", whiteSpace: "nowrap" }}>Default Branch</th>
                  <th style={{ padding: "12px 24px" }}>Visibility</th>
                  <th style={{ padding: "12px 24px", whiteSpace: "nowrap" }}>Last Updated</th>
                </tr>
              </thead>
              <tbody>
                {recentRepos.slice(0, 5).map((repo, idx) => (
                  <tr key={repo.jobId || idx} style={{ borderBottom: idx === Math.min(recentRepos.length, 5) - 1 ? "none" : "1px solid #f1f5f9" }}>
                    <td style={{ padding: "12px 24px", color: "#0f172a", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "32px", height: "32px", backgroundColor: "#eff6ff", borderRadius: "8px", color: "#3b82f6" }}>
                        <FaFolder size={14} />
                      </div>
                      {repo.repositoryName}
                    </td>
                    <td style={{ padding: "12px 24px", color: "#64748b" }}>{repo.owner}</td>
                    <td style={{ padding: "12px 24px", color: "#64748b", display: "flex", alignItems: "center", gap: "6px" }}>
                      <FaJava color="#ea580c" />
                      {repo.techStack}
                    </td>
                    <td style={{ padding: "12px 24px", color: "#64748b" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <FaFileAlt color="#94a3b8" />
                        {repo.componentsCount}
                      </div>
                    </td>
                    <td style={{ padding: "12px 24px" }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "4px 10px", backgroundColor: "#f1f5f9", color: "#475569", borderRadius: "16px", fontSize: "0.8rem", fontWeight: 500 }}>
                        <FaCodeBranch size={12} />
                        {repo.defaultBranch}
                      </span>
                    </td>
                    <td style={{ padding: "12px 24px" }}>
                      <span style={{ display: "inline-block", padding: "4px 12px", backgroundColor: repo.visibility.toLowerCase() === "private" ? "#fef3c7" : "#e0f2fe", color: repo.visibility.toLowerCase() === "private" ? "#d97706" : "#0284c7", borderRadius: "16px", fontSize: "0.8rem", fontWeight: 600 }}>
                        {repo.visibility}
                      </span>
                    </td>
                    <td style={{ padding: "12px 24px", color: "#64748b" }}>{repo.lastUpdatedFormatted}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
