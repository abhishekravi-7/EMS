import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { FaEnvelope, FaArrowRight } from "react-icons/fa";
import { useAuth } from "@/shared/context/AuthContext";
import AuthLayout from "../components/AuthLayout";
import SocialAuthButtons from "../components/SocialAuthButtons";
import PasswordInput from "../components/PasswordInput";
import { signIn } from "../services/authService";
import { useAuthForm, type FormErrors } from "../hooks/useAuthForm";
import { getOAuthErrorMessage } from "../oauthErrorMessages";
import "../auth.css";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface SignInValues {
  email: string;
  password: string;
}

function validateSignIn(values: SignInValues): FormErrors<SignInValues> {
  const errors: FormErrors<SignInValues> = {};

  if (!values.email.trim()) {
    errors.email = "Email is required.";
  } else if (!EMAIL_PATTERN.test(values.email.trim())) {
    errors.email = "Enter a valid email address.";
  }

  if (!values.password) {
    errors.password = "Password is required.";
  }

  return errors;
}

const SignInPage: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [searchParams] = useSearchParams();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    const oauthErrorCode = searchParams.get("oauth_error");
    if (oauthErrorCode) {
      setApiError(getOAuthErrorMessage(oauthErrorCode));
      navigate("/signin", { replace: true });
    }
  }, [searchParams, navigate]);

  const { values, errors, setField, handleSubmit } = useAuthForm<SignInValues>({
    initialValues: { email: "", password: "" },
    validate: validateSignIn,
    onValid: async (formValues) => {
      if (isSubmitting) return;

      setApiError(null);
      setIsSubmitting(true);
      try {
        await signIn({
          email: formValues.email.trim(),
          password: formValues.password,
        });
        navigate("/connect");
      } catch (err: any) {
        setApiError(err.message || "Sign in failed. Please try again.");
      } finally {
        setIsSubmitting(false);
      }
    },
  });

  return (
    <AuthLayout mode="signin">
      <div className="apex-form-header">
        <h2 className="apex-form-title">Sign in to your account</h2>
        <p className="apex-form-subtitle">Enter your credentials to access your account</p>
      </div>

      {apiError && <div className="auth-notice auth-notice--error">{apiError}</div>}

      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {/* Email Field */}
        <div className="auth-field">
          <label className="auth-label" htmlFor="email">
            Email address
          </label>
          <div className="auth-input-wrap">
            <span className="auth-input-left-icon">
              <FaEnvelope size={14} style={{ color: "#94a3b8" }} />
            </span>
            <input
              id="email"
              name="email"
              type="email"
              className={`auth-input has-left-icon ${errors.email ? "auth-input--error" : ""}`}
              placeholder="Enter your email"
              value={values.email}
              onChange={(e) => setField("email", e.target.value)}
              autoComplete="email"
              disabled={isSubmitting}
            />
          </div>
          {errors.email && <span className="auth-error-text">{errors.email}</span>}
        </div>

        {/* Password Field */}
        <PasswordInput
          label="Password"
          name="password"
          value={values.password}
          onChange={(v) => setField("password", v)}
          placeholder="Enter your password"
          error={errors.password}
          autoComplete="current-password"
          disabled={isSubmitting}
        />

        {/* Forgot Password Link */}
        <div className="auth-forgot-row">
          <button
            type="button"
            className="auth-link-forgot"
            title="Password reset is coming soon"
            disabled
          >
            Forgot password?
          </button>
        </div>

        {/* Primary CTA */}
        <button
          type="submit"
          className="apex-btn-auth-primary"
          disabled={isSubmitting}
        >
          <span>{isSubmitting ? "Signing in..." : "Sign In"}</span>
          {!isSubmitting && <FaArrowRight style={{ fontSize: 13 }} />}
        </button>
      </form>

      <div className="auth-divider">or continue with</div>
      <SocialAuthButtons mode="signin" />

      <p className="auth-footer-note">
        Don&apos;t have an account? <Link to="/signup" className="apex-auth-switch-link">Sign up</Link>
      </p>
    </AuthLayout>
  );
};

export default SignInPage;
