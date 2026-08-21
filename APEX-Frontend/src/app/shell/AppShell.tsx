import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import apexLogo from "../../assets/logo.jpg";
import { DocsPanel } from "@/features/docs";
import { SupportPanel } from "@/features/support";
import { Button } from "@/shared/components/ui";
import { useAuth } from "@/shared/context/AuthContext";
import { TOKEN_TRACING_DASHBOARD_URL } from "@/services/config/env";
import FloatingChatbot from "@/shared/components/chatbot/FloatingChatbot";
import "./AppShell.css";

const shellStyles: { [key: string]: React.CSSProperties } = {
  root: {
    minHeight: "100vh",
    width: "100%",
    margin: 0,
    padding: 0,
    background: "linear-gradient(180deg, #f8fbff 0%, #f8fafc 220px, #f8fafc 100%)",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    background: "rgba(255, 255, 255, 0.92)",
    borderBottom: "1px solid #e2e8f0",
    padding: "14px 28px 14px 100px",
    width: "100%",
    boxSizing: "border-box",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    rowGap: 10,
    position: "sticky",
    top: 0,
    zIndex: 20,
    backdropFilter: "blur(12px)",
    boxShadow: "0 10px 30px rgba(15, 23, 42, 0.04)",
  },
  main: {
    flex: 1,
    width: "100%",
    padding: 0,
    margin: 0,
  },
  content: {
    width: "100%",
    margin: 0,
    padding: 0,
  },
  footer: {
    background: "linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.96) 100%)",
    borderTop: "1px solid #e2e8f0",
    padding: "18px 28px",
    fontSize: 13,
    width: "100%",
    boxSizing: "border-box",
  },
  footerContent: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    color: "#64748b",
    gap: 16,
    flexWrap: "wrap",
  },
};

const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activePanel, setActivePanel] = useState<"docs" | "support" | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, isAuthLoading, user, logout } = useAuth();

  const isStandalonePage =
    // location.pathname === "/" ||
    location.pathname === "/signin" ||
    location.pathname === "/signup";

  // Auth guard: once the real /api/auth/me check completes (isAuthLoading
  // becomes false), redirect unauthenticated users away from protected pages.
  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated && !isStandalonePage) {
      navigate("/signin", { replace: true });
    }
  }, [isAuthLoading, isAuthenticated, isStandalonePage, navigate]);

  // Hold rendering until the auth check completes to avoid firing
  // protected API calls with no session cookie.
  if (isAuthLoading && !isStandalonePage) {
    return null;
  }

  if (isStandalonePage) {
    return (
      <div style={{ minHeight: "100vh", width: "100%", background: "#f8fafc" }}>
        {children}
        <DocsPanel
          open={activePanel === "docs"}
          onClose={() => setActivePanel(null)}
          onNavigateToSupport={() => setActivePanel("support")}
        />
        <SupportPanel
          open={activePanel === "support"}
          onClose={() => setActivePanel(null)}
          onNavigateToDocs={() => setActivePanel("docs")}
        />
      </div>
    );
  }

  return (
    <div style={shellStyles.root}>
      <header style={shellStyles.header}>
        <div className="app-shell-brand" onClick={() => navigate("/")} style={{ cursor: "pointer" }}>
          <img
            src={apexLogo}
            alt="Java APEX"
            className="app-shell-logo"
            style={{ height: 38, width: "auto", objectFit: "contain", display: "block" }}
          />
        </div>
        <nav className="app-shell-nav">
          <button
            type="button"
            className="ui-nav-button"
            onClick={() => setActivePanel("docs")}
            aria-haspopup="dialog"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <span>Docs</span>
          </button>

          <button
            type="button"
            className="ui-nav-button"
            onClick={() => window.open(TOKEN_TRACING_DASHBOARD_URL, "_blank")}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="20" x2="18" y2="10"></line>
              <line x1="12" y1="20" x2="12" y2="4"></line>
              <line x1="6" y1="20" x2="6" y2="14"></line>
            </svg>
            <span>Usage</span>
          </button>

          <button
            type="button"
            className="ui-nav-button"
            onClick={() => setActivePanel("support")}
            aria-haspopup="dialog"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 18v-6a9 9 0 0 1 18 0v6"></path>
              <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path>
            </svg>
            <span>Support</span>
          </button>

          {isAuthenticated ? (
            <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 6, marginLeft: 4 }}>
              <button
                onClick={() => setShowProfileMenu(!showProfileMenu)}
                className={`ui-profile-trigger ${showProfileMenu ? "is-open" : ""}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  border: "none",
                  fontWeight: 700,
                  fontSize: 15,
                  color: "#ffffff",
                  background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                  boxShadow: "0 2px 8px rgba(37, 99, 235, 0.3)",
                  cursor: "pointer",
                }}
                title={user?.name ?? "Profile"}
                aria-expanded={showProfileMenu}
              >
                {(user?.name?.trim()?.charAt(0) || "G").toUpperCase()}
              </button>
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#64748b"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ cursor: "pointer", transition: "transform 0.2s ease", transform: showProfileMenu ? "rotate(180deg)" : "none" }}
                onClick={() => setShowProfileMenu(!showProfileMenu)}
              >
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>

              {showProfileMenu && (
                <>
                  <div
                    style={{ position: "fixed", inset: 0, zIndex: 999 }}
                    onClick={() => setShowProfileMenu(false)}
                  />
                  <div
                    style={{
                      position: "absolute",
                      top: 44,
                      right: 0,
                      width: 240,
                      background: "#fff",
                      borderRadius: 12,
                      boxShadow: "0 10px 40px rgba(0,0,0,0.15)",
                      border: "1px solid #e2e8f0",
                      zIndex: 1000,
                      overflow: "hidden",
                    }}
                  >
                    <div style={{ padding: "16px 20px", borderBottom: "1px solid #e2e8f0", background: "#f8fafc" }}>
                      <div style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>{user?.name}</div>
                      <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>{user?.email}</div>
                    </div>
                    <div style={{ padding: 12 }}>
                      <button
                        type="button"
                        className="ui-menu-button"
                        style={{
                          width: "100%",
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                          padding: "12px 16px",
                          borderRadius: 8,
                          border: "1px solid #e2e8f0",
                          background: "#fff",
                          color: "#1e293b",
                          fontSize: 14,
                          fontWeight: 500,
                        }}
                        onClick={() => {
                          setShowProfileMenu(false);
                          logout();
                          navigate("/");
                        }}
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                          <polyline points="16 17 21 12 16 7"></polyline>
                          <line x1="21" y1="12" x2="9" y2="12"></line>
                        </svg>
                        Logout
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          ) : (
            <>
              {location.pathname !== "/signin" && (
                <Button variant="ghost" size="sm" onClick={() => navigate("/signin")}>
                  Sign In
                </Button>
              )}
              {location.pathname !== "/signup" && (
                <Button variant="primary" size="sm" onClick={() => navigate("/signup")}>
                  Sign Up
                </Button>
              )}
            </>
          )}
        </nav>
      </header>

      <main style={shellStyles.main}>
        <div style={shellStyles.content}>
          {children}
        </div>
      </main>

      <footer style={shellStyles.footer}>
        <div style={shellStyles.footerContent} className="app-shell-footer-content">
          <span className="app-shell-footer-meta" data-year={new Date().getFullYear()}>
            © {new Date().getFullYear()} Powered by <a href="https://sorim.ai/" target="_blank" rel="noreferrer">Sorim.ai</a>
          </span>
          <span>© {new Date().getFullYear()} <a href="https://sorim.ai/">Sorim.ai</a></span>
        </div>
      </footer>

      <DocsPanel
        open={activePanel === "docs"}
        onClose={() => setActivePanel(null)}
        onNavigateToSupport={() => setActivePanel("support")}
      />
      <SupportPanel
        open={activePanel === "support"}
        onClose={() => setActivePanel(null)}
        onNavigateToDocs={() => setActivePanel("docs")}
      />
      <FloatingChatbot />
    </div>
  );
};

export default AppShell;
