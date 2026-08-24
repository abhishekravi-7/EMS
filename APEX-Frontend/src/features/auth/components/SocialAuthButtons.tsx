import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FaGithub } from "react-icons/fa";
import { signInWithGoogle, signInWithGithub } from "../services/authService";

const GoogleIcon: React.FC = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" style={{ display: "block" }}>
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
  </svg>
);

export interface SocialAuthButtonsProps {
  mode: "signin" | "signup";
}

type Provider = "google" | "github";

const SocialAuthButtons: React.FC<SocialAuthButtonsProps> = ({ mode }) => {
  const navigate = useNavigate();
  const isSignIn = mode === "signin";
  const [redirectingTo, setRedirectingTo] = useState<Provider | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSocialLogin = async (provider: Provider) => {
    if (redirectingTo) return;
    setRedirectingTo(provider);
    setError(null);

    try {
      if (provider === "google") {
        await signInWithGoogle();
      } else {
        await signInWithGithub();
      }
      navigate("/connect");
    } catch (err: any) {
      setError(err.message);
      setRedirectingTo(null);
    }
  };

  return (
    <div className="auth-social-stack">
      {error && (
        <div style={{
          fontSize: 12,
          color: "#dc2626",
          textAlign: "center",
          marginBottom: 8,
          background: "#fef2f2",
          padding: "6px",
          borderRadius: "6px",
          border: "1px solid #fecaca"
        }}>
          {error}
        </div>
      )}

      <button
        type="button"
        className="auth-social-btn"
        disabled={redirectingTo !== null}
        onClick={() => handleSocialLogin("google")}
      >
        <GoogleIcon />
        <span>{isSignIn ? "Continue with Google" : "Sign up with Google"}</span>
      </button>

      <button
        type="button"
        className="auth-social-btn"
        disabled={redirectingTo !== null}
        onClick={() => handleSocialLogin("github")}
      >
        <FaGithub size={18} />
        <span>{isSignIn ? "Continue with GitHub" : "Sign up with GitHub"}</span>
      </button>
    </div>
  );
};

export default SocialAuthButtons;
