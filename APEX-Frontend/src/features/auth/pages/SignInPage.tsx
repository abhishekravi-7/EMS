import React, { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { signInWithGoogle, signInWithGithub, resetPassword, signIn, resendVerification } from "../services/authService";
import AuthLayout from "../components/AuthLayout";
import { useAuth } from "@/shared/context/AuthContext";
import { FaRegEnvelope, FaCheckCircle } from "react-icons/fa";
import { getOAuthErrorMessage } from "../oauthErrorMessages";

const GoogleIcon: React.FC = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" style={{ display: "block" }}>
    <path
      fill="#4285F4"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="#34A853"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="#FBBC05"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
    />
    <path
      fill="#EA4335"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
    />
  </svg>
);

// ── Forgot Password Modal ─────────────────────────────────────────────────────
const ForgotPasswordModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "sent" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("loading");
    setErrorMsg("");
    try {
      const cleanEmail = email.trim().toLowerCase();
      await resetPassword(cleanEmail);
      setStatus("sent");
    } catch (err: unknown) {
      console.error("Password reset error details:", err);
      const errMsg = err instanceof Error ? err.message : "Unable to send reset email. Please ensure the email is correct.";
      setErrorMsg(errMsg);
      setStatus("error");
    }
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 999,
        backdropFilter: "blur(4px)",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#fff", borderRadius: 20, padding: "36px 32px", width: 380,
          boxShadow: "0 24px 60px rgba(79,70,229,0.15)", position: "relative",
          userSelect: "none", cursor: "default"
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          style={{
            position: "absolute", top: 14, right: 16, background: "none",
            border: "none", fontSize: 20, cursor: "pointer", color: "#94a3b8",
          }}
        >×</button>

        {status === "sent" ? (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📧</div>
            <h3 style={{ margin: "0 0 8px", fontSize: 20, fontWeight: 800, color: "#0f172a" }}>
              Check your inbox
            </h3>
            <p style={{ color: "#64748b", fontSize: 14, lineHeight: 1.5 }}>
              We sent a password reset link to <strong>{email}</strong>. Check your email and follow the link to reset your password.
            </p>
            <button
              onClick={onClose}
              style={{
                marginTop: 20, width: "100%", height: 44, borderRadius: 11,
                background: "#4F46E5", border: "none", color: "#fff",
                fontWeight: 700, fontSize: 15, cursor: "pointer",
              }}
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <h3 style={{ margin: "0 0 6px", fontSize: 20, fontWeight: 800, color: "#0f172a" }}>
              Reset your password
            </h3>
            <p style={{ color: "#64748b", fontSize: 13.5, marginBottom: 20 }}>
              Enter your email address and we'll send you a link to reset your password.
            </p>

            {status === "error" && (
              <div style={{
                padding: "8px 12px", borderRadius: 8, background: "#fef2f2",
                border: "1px solid #fecaca", color: "#b91c1c", fontSize: 12, marginBottom: 12,
              }}>
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleReset}>
              <div className="apex-exact-input-wrap" style={{ marginBottom: 16 }}>
                <FaRegEnvelope className="apex-exact-input-icon" />
                <input
                  id="reset-email"
                  type="email"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="apex-exact-input"
                  autoFocus
                />
              </div>
              <button
                type="submit"
                disabled={status === "loading"}
                className="apex-login-primary-btn"
              >
                {status === "loading" ? "Sending..." : "Send Reset Link"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
};

// ── SignInPage ────────────────────────────────────────────────────────────────
const SignInPage: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isUnverifiedEmail, setIsUnverifiedEmail] = useState(false);
  const [resendStatus, setResendStatus] = useState<"idle" | "sending" | "sent">("idle");
  const [successNotice, setSuccessNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showForgotModal, setShowForgotModal] = useState(false);

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, isAuthenticated, isAuthLoading } = useAuth();

  // Handle URL query parameters for OAuth and email verification outcomes
  useEffect(() => {
    const verifiedParam = searchParams.get("verified");
    if (verifiedParam === "true") {
      setSuccessNotice("Your email has been successfully verified! Please log in.");
    }

    const verifyErrorParam = searchParams.get("verify_error");
    if (verifyErrorParam) {
      setError("Email verification link was invalid or has expired. You can request a new one below.");
      setIsUnverifiedEmail(true);
    }
    const sessionExpiredParam = searchParams.get("session_expired");
    if (sessionExpiredParam === "true") {
      setError("Your session has expired. Please sign in again.");
    }

    const oauthErrorCode = searchParams.get("oauth_error");
    if (oauthErrorCode) {
      setError(getOAuthErrorMessage(oauthErrorCode));
    }
  }, [searchParams]);

  // If already authenticated, redirect to application
  useEffect(() => {
    if (!isAuthLoading && isAuthenticated) {
      navigate("/connect", { replace: true });
    }
  }, [isAuthenticated, isAuthLoading, navigate]);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsUnverifiedEmail(false);
    setResendStatus("idle");

    const trimmedEmail = email.trim().toLowerCase();
    const emailRegex = /^[a-zA-Z0-9]+(?:[._%+-][a-zA-Z0-9]+)*@[a-zA-Z0-9]+(?:[.-][a-zA-Z0-9]+)*\.[a-zA-Z]{2,}$/;
    if (!trimmedEmail || !emailRegex.test(trimmedEmail)) {
      setError("Please enter a valid email address.");
      return;
    }

    if (!password) {
      setError("Please enter your password.");
      return;
    }

    setLoading(true);

    try {
      const user = await signIn({ email: trimmedEmail, password });
      console.log("[SignIn] Email sign in success:", user.email);
      login(user);
      navigate("/connect", { replace: true });
    } catch (err: unknown) {
      console.error("[SignIn] Email sign in error:", err);
      const errorObj = err as { message?: string; status?: string };
      const errMsg = errorObj.message || "Invalid email or password.";
      if (errMsg.toLowerCase().includes("verify your email") || errMsg.toLowerCase().includes("not verified") || errorObj.status === "EMAIL_NOT_VERIFIED") {
        const cleanEmail = trimmedEmail.toLowerCase();
        sessionStorage.setItem("apex_pending_verification_email", cleanEmail);
        navigate("/verify-email", { state: { email: cleanEmail } });
        return;
      }
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    if (!email.trim()) return;
    setResendStatus("sending");
    try {
      await resendVerification(email.trim().toLowerCase());
      setResendStatus("sent");
    } catch (err: unknown) {
      console.error("Resend verification error:", err);
      const errMsg = err instanceof Error ? err.message : "Failed to resend verification code. Please try again.";
      setError(errMsg);
    }
  };

  const handleGoogleSignIn = async () => {
    setError(null);
    try {
      await signInWithGoogle("signin");
    } catch (err: unknown) {
      console.error("[SignIn] Google sign in error:", err);
      const errMsg = err instanceof Error ? err.message : "Google sign in failed.";
      setError(errMsg);
    }
  };

  const handleGithubSignIn = async () => {
    setError(null);
    try {
      await signInWithGithub("signin");
    } catch (err: unknown) {
      console.error("[SignIn] GitHub sign in error:", err);
      const errMsg = err instanceof Error ? err.message : "GitHub sign in failed.";
      setError(errMsg);
    }
  };

  return (
    <>
      {showForgotModal && <ForgotPasswordModal onClose={() => setShowForgotModal(false)} />}

      <AuthLayout mode="signin">
        {/* Animated Human Avatar Icon at Top with Glowing Halo */}
        <div className="apex-card-avatar-wrapper">
          <div className="apex-avatar-glow-halo" />
          <div className="apex-card-avatar-circle">
            <div className="apex-avatar-pulse-ring" />
            <FaUser className="apex-card-avatar-icon" />
          </div>
        </div>

        {/* Header */}
        <div className="apex-exact-card-header">
          <h2 className="apex-exact-card-title">Welcome Back!</h2>
          <p className="apex-exact-card-subtitle">
            Login to access your migration projects
          </p>
        </div>

        {successNotice && (
          <div
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              background: "#ECFDF5",
              border: "1px solid #A7F3D0",
              color: "#065F46",
              fontSize: 13,
              marginBottom: 16,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <FaCheckCircle color="#10B981" size={16} />
            <span>{successNotice}</span>
          </div>
        )}

        {error && (
          <div
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              background: "#FEF2F2",
              border: "1px solid #FECACA",
              color: "#B91C1C",
              fontSize: 13,
              marginBottom: 16,
            }}
          >
            <div>{error}</div>
            {isUnverifiedEmail && (
              <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
                {resendStatus === "sent" ? (
                  <span style={{ color: "#065F46", fontWeight: 600, fontSize: 13 }}>
                    ✓ Verification code sent successfully.
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={handleResendVerification}
                    disabled={resendStatus === "sending"}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#4F46E5",
                      fontWeight: 700,
                      textDecoration: "underline",
                      cursor: "pointer",
                      padding: 0,
                      fontSize: 13,
                    }}
                  >
                    {resendStatus === "sending" ? "Sending..." : "Resend Verification Code"}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() =>
                    navigate("/verify-email", {
                      state: { email: email.trim().toLowerCase() },
                    })
                  }
                  style={{
                    background: "#4F46E5",
                    border: "none",
                    color: "#FFFFFF",
                    fontWeight: 600,
                    borderRadius: 6,
                    padding: "4px 10px",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  Enter Verification Code →
                </button>
              </div>
            )}
          </div>
        )}

        <form className="apex-exact-form" onSubmit={handleSignIn}>
          {/* Email Address */}
          <div className="apex-exact-field">
            <label htmlFor="email" className="apex-exact-label">
              Email Address
            </label>
            <div className="apex-exact-input-wrap">
              <FaRegEnvelope className="apex-exact-input-icon" />
              <input
                id="email"
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="apex-exact-input"
              />
            </div>
          </div>

          {/* Password */}
          <div className="apex-exact-field">
            <label htmlFor="password" className="apex-exact-label">
              Password
            </label>
            <div className="apex-exact-input-wrap">
              <FaLock className="apex-exact-input-icon" />
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="apex-exact-input apex-exact-input-pass"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label="Toggle password visibility"
                className="apex-exact-eye-btn"
              >
                {showPassword ? <FaEyeSlash size={15} /> : <FaEye size={15} />}
              </button>
            </div>
          </div>

          {/* Forgot Password */}
          <div className="apex-remember-forgot-row" style={{ justifyContent: "flex-end" }}>
            <button
              type="button"
              onClick={() => setShowForgotModal(true)}
              className="apex-exact-forgot-link"
              style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
            >
              Forgot Password?
            </button>
          </div>

          {/* Primary Login Button */}
          <button
            type="submit"
            disabled={loading}
            className="apex-login-primary-btn"
          >
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>

        {/* or Divider */}
        <div className="apex-exact-divider-row">
          <div className="apex-exact-divider-line" />
          <span className="apex-exact-divider-text">or</span>
          <div className="apex-exact-divider-line" />
        </div>

        {/* Social Login Buttons */}
        <div className="apex-exact-social-group">
          <button
            type="button"
            onClick={handleGoogleSignIn}
            className="apex-exact-social-btn"
          >
            <GoogleIcon />
            <span>Login with Google</span>
          </button>

          <button
            type="button"
            onClick={handleGithubSignIn}
            className="apex-exact-social-btn"
          >
            <FaGithub color="#181717" size={17} />
            <span>Login with GitHub</span>
          </button>
        </div>

        {/* Card Footer */}
        <div className="apex-exact-card-footer">
          Don&apos;t have an account?{" "}
          <span
            onClick={() => navigate("/signup")}
            className="apex-exact-signup-link"
          >
            Sign Up
          </span>
        </div>
      </AuthLayout>
    </>
  );
};

export default SignInPage;
