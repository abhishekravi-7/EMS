import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { FaUser, FaEnvelope, FaCheck, FaArrowRight } from "react-icons/fa";
import { Button } from "@/shared/components/ui";
import AuthLayout from "../components/AuthLayout";
import SocialAuthButtons from "../components/SocialAuthButtons";
import PasswordInput from "../components/PasswordInput";
import { signUp } from "../services/authService";
import { useAuthForm, type FormErrors } from "../hooks/useAuthForm";
import { getOAuthErrorMessage } from "../oauthErrorMessages";
import "../auth.css";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 8;
const MAX_PASSWORD_LENGTH = 128;
const HAS_UPPERCASE = /[A-Z]/;
const HAS_LOWERCASE = /[a-z]/;
const HAS_DIGIT = /\d/;
const HAS_SPECIAL_CHARACTER = /[^A-Za-z0-9]/;

interface SignUpValues {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

function validateSignUp(values: SignUpValues): FormErrors<SignUpValues> {
  const errors: FormErrors<SignUpValues> = {};

  if (!values.fullName.trim()) {
    errors.fullName = "Full name is required.";
  }

  if (!values.email.trim()) {
    errors.email = "Email is required.";
  } else if (!EMAIL_PATTERN.test(values.email.trim())) {
    errors.email = "Enter a valid email address.";
  }

  if (!values.password) {
    errors.password = "Password is required.";
  } else if (values.password.length < MIN_PASSWORD_LENGTH || values.password.length > MAX_PASSWORD_LENGTH) {
    errors.password = `Password must be between ${MIN_PASSWORD_LENGTH} and ${MAX_PASSWORD_LENGTH} characters.`;
  } else if (!HAS_UPPERCASE.test(values.password)) {
    errors.password = "Password must contain at least one uppercase letter.";
  } else if (!HAS_LOWERCASE.test(values.password)) {
    errors.password = "Password must contain at least one lowercase letter.";
  } else if (!HAS_DIGIT.test(values.password)) {
    errors.password = "Password must contain at least one number.";
  } else if (!HAS_SPECIAL_CHARACTER.test(values.password)) {
    errors.password = "Password must contain at least one special character.";
  }

  if (!values.confirmPassword) {
    errors.confirmPassword = "Please confirm your password.";
  } else if (values.confirmPassword !== values.password) {
    errors.confirmPassword = "Passwords do not match.";
  }

  return errors;
}

function getPasswordStrength(password: string): { label: string; score: number; color: string } {
  if (!password) return { label: "Weak", score: 0, color: "#ef4444" };
  let score = 0;
  if (password.length >= 8) score++;
  if (HAS_UPPERCASE.test(password) && HAS_LOWERCASE.test(password)) score++;
  if (HAS_DIGIT.test(password)) score++;
  if (HAS_SPECIAL_CHARACTER.test(password)) score++;

  if (score <= 1) return { label: "Weak", score: 1, color: "#ef4444" };
  if (score <= 3) return { label: "Medium", score: 2, color: "#f59e0b" };
  return { label: "Strong", score: 4, color: "#22c55e" };
}

const SignUpPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    const oauthErrorCode = searchParams.get("oauth_error");
    if (oauthErrorCode) {
      setApiError(getOAuthErrorMessage(oauthErrorCode));
      navigate("/signup", { replace: true });
    }
  }, [searchParams, navigate]);

  const { values, errors, setField, handleSubmit } = useAuthForm<SignUpValues>({
    initialValues: { fullName: "", email: "", password: "", confirmPassword: "" },
    validate: validateSignUp,
    onValid: async (formValues) => {
      if (isSubmitting) return;

      if (!agreeTerms) {
        setApiError("Please agree to the Terms of Service and Privacy Policy.");
        return;
      }

      setApiError(null);
      setIsSubmitting(true);
      try {
        await signUp({
          fullName: formValues.fullName.trim(),
          email: formValues.email.trim(),
          password: formValues.password,
          confirmPassword: formValues.confirmPassword,
        });
        setSubmitted(true);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Sign up failed. Please try again.";
        setApiError(message);
      } finally {
        setIsSubmitting(false);
      }
    },
  });

  const strength = getPasswordStrength(values.password);

  if (submitted) {
    return (
      <AuthLayout mode="signup">
        <div className="auth-success">
          <div className="auth-success-icon">
            <FaCheck />
          </div>
          <h2 className="auth-success-title">Account created!</h2>
          <p className="auth-success-text">
            Your account has been created successfully. Sign in to start your migration journey.
          </p>
          <Button variant="primary" fullWidth onClick={() => navigate("/signin")}>
            Go to Sign In
          </Button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout mode="signup">
      <div className="apex-form-header">
        <h2 className="apex-form-title">Create your account</h2>
        <p className="apex-form-subtitle">Enter your details to get started</p>
      </div>

      {apiError && <div className="auth-notice auth-notice--error">{apiError}</div>}

      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {/* Full Name */}
        <div className="auth-field">
          <label className="auth-label" htmlFor="fullName">
            Full name
          </label>
          <div className="auth-input-wrap">
            <span className="auth-input-left-icon">
              <FaUser size={14} style={{ color: "#94a3b8" }} />
            </span>
            <input
              id="fullName"
              name="fullName"
              type="text"
              className={`auth-input auth-input--with-icon ${errors.fullName ? "auth-input--error" : ""}`}
              placeholder="Enter your full name"
              value={values.fullName}
              onChange={(e) => setField("fullName", e.target.value)}
              autoComplete="name"
              disabled={isSubmitting}
            />
          </div>
          {errors.fullName && <span className="auth-error-text">{errors.fullName}</span>}
        </div>

        {/* Email */}
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
              className={`auth-input auth-input--with-icon ${errors.email ? "auth-input--error" : ""}`}
              placeholder="Enter your email"
              value={values.email}
              onChange={(e) => setField("email", e.target.value)}
              autoComplete="email"
              disabled={isSubmitting}
            />
          </div>
          {errors.email && <span className="auth-error-text">{errors.email}</span>}
        </div>

        {/* Password */}
        <div>
          <PasswordInput
            label="Password"
            name="password"
            value={values.password}
            onChange={(v) => setField("password", v)}
            placeholder="Create a strong password"
            error={errors.password}
            disabled={isSubmitting}
          />
          {/* Password Strength Indicator */}
          {values.password.length > 0 && (
            <div className="apex-password-strength-wrap">
              <div className="apex-strength-bars">
                <span className={`apex-strength-bar ${strength.score >= 1 ? "active" : ""}`} style={{ background: strength.score >= 1 ? strength.color : "#e2e8f0" }} />
                <span className={`apex-strength-bar ${strength.score >= 2 ? "active" : ""}`} style={{ background: strength.score >= 2 ? strength.color : "#e2e8f0" }} />
                <span className={`apex-strength-bar ${strength.score >= 3 ? "active" : ""}`} style={{ background: strength.score >= 3 ? strength.color : "#e2e8f0" }} />
                <span className={`apex-strength-bar ${strength.score >= 4 ? "active" : ""}`} style={{ background: strength.score >= 4 ? strength.color : "#e2e8f0" }} />
              </div>
              <div className="apex-strength-label">
                Password strength: <strong style={{ color: strength.color }}>{strength.label}</strong>
              </div>
            </div>
          )}
        </div>

        {/* Confirm Password */}
        <PasswordInput
          label="Confirm password"
          name="confirmPassword"
          value={values.confirmPassword}
          onChange={(v) => setField("confirmPassword", v)}
          placeholder="Confirm your password"
          error={errors.confirmPassword}
          disabled={isSubmitting}
        />

        {/* Terms Checkbox */}
        <div className="auth-terms-checkbox-wrap">
          <input
            type="checkbox"
            id="agreeTerms"
            checked={agreeTerms}
            onChange={(e) => setAgreeTerms(e.target.checked)}
          />
          <label htmlFor="agreeTerms">
            I agree to the <a href="#terms">Terms of Service</a> and <a href="#privacy">Privacy Policy</a>
          </label>
        </div>

        {/* Primary CTA */}
        <button
          type="submit"
          className="apex-btn-auth-primary"
          disabled={isSubmitting}
        >
          <span>{isSubmitting ? "Creating account..." : "Create Account"}</span>
          {!isSubmitting && <FaArrowRight style={{ fontSize: 13 }} />}
        </button>
      </form>

      <div className="auth-divider">or sign up with</div>
      <SocialAuthButtons mode="signup" />

      <p className="auth-footer-note">
        Already have an account? <Link to="/signin" className="apex-auth-switch-link">Sign in</Link>
      </p>
    </AuthLayout>
  );
};

export default SignUpPage;
