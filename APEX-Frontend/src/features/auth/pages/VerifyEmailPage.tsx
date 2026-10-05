import React, { useEffect, useState, useRef } from "react";
import { useSearchParams, useLocation, useNavigate, Link } from "react-router-dom";
import { FaCheckCircle, FaExclamationCircle, FaRedo, FaShieldAlt, FaArrowLeft } from "react-icons/fa";
import { verifyEmailCode, resendVerificationCode } from "../services/authService";
import { useAuth } from "@/shared/context/AuthContext";
import AuthLayout from "../components/AuthLayout";
import "../auth.css";

const STORAGE_PENDING_EMAIL_KEY = "apex_pending_verification_email";

const VerifyEmailPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { login } = useAuth();

  // Extract email from React Router state -> URL search param -> sessionStorage
  const stateEmail = (location.state as { email?: string } | null)?.email || "";
  const queryEmail = searchParams.get("email") || "";
  const storedEmail = typeof window !== "undefined" ? sessionStorage.getItem(STORAGE_PENDING_EMAIL_KEY) || "" : "";

  const initialEmail = (stateEmail || queryEmail || storedEmail).trim().toLowerCase();

  const [email, setEmail] = useState(initialEmail);
  const [codeDigits, setCodeDigits] = useState<string[]>(["", "", "", "", "", ""]);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isVerified, setIsVerified] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Resend state & 60s cooldown timer
  const [isResending, setIsResending] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(60);
  const [resendSuccessMsg, setResendSuccessMsg] = useState<string | null>(null);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Persist resolved email into sessionStorage so browser refreshes keep state
  useEffect(() => {
    if (initialEmail) {
      setEmail(initialEmail);
      sessionStorage.setItem(STORAGE_PENDING_EMAIL_KEY, initialEmail);
    }
  }, [initialEmail]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  // Auto-focus the first empty digit input on mount
  useEffect(() => {
    if (inputRefs.current[0]) {
      inputRefs.current[0].focus();
    }
  }, []);

  const handleDigitChange = (index: number, value: string) => {
    const cleanVal = value.replace(/\D/g, "");
    if (!cleanVal) {
      const newDigits = [...codeDigits];
      newDigits[index] = "";
      setCodeDigits(newDigits);
      return;
    }

    const char = cleanVal.slice(-1);
    const newDigits = [...codeDigits];
    newDigits[index] = char;
    setCodeDigits(newDigits);
    setErrorMessage(null);

    // Auto-advance to next input
    if (index < 5 && inputRefs.current[index + 1]) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !codeDigits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pastedData) return;

    const newDigits = [...codeDigits];
    for (let i = 0; i < 6; i++) {
      newDigits[i] = pastedData[i] || "";
    }
    setCodeDigits(newDigits);
    setErrorMessage(null);

    const focusIdx = Math.min(pastedData.length, 5);
    inputRefs.current[focusIdx]?.focus();
  };

  const handleVerify = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanEmail = email.trim().toLowerCase();
    const fullCode = codeDigits.join("");

    if (!cleanEmail) {
      setErrorMessage("Please restart the signup process.");
      return;
    }

    if (fullCode.length !== 6 || !/^\d{6}$/.test(fullCode)) {
      setErrorMessage("Please enter the 6-digit verification code.");
      return;
    }

    setErrorMessage(null);
    setIsVerifying(true);

    try {
      await verifyEmailCode(cleanEmail, fullCode);
      setIsVerified(true);
      sessionStorage.removeItem(STORAGE_PENDING_EMAIL_KEY);
      setTimeout(() => {
        navigate("/signin?verified=true", { replace: true });
      }, 1200);
    } catch (err: any) {
      const msg = err.message || "Invalid verification code.";
      setErrorMessage(msg);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleResend = async () => {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) {
      setErrorMessage("Please restart the signup process.");
      return;
    }

    if (resendCooldown > 0 || isResending) return;

    setIsResending(true);
    setErrorMessage(null);
    setResendSuccessMsg(null);

    try {
      await resendVerificationCode(cleanEmail);
      setResendSuccessMsg("Verification code sent successfully.");
      setResendCooldown(60);
      setCodeDigits(["", "", "", "", "", ""]);
      if (inputRefs.current[0]) {
        inputRefs.current[0].focus();
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to resend verification code. Please try again later.");
    } finally {
      setIsResending(false);
    }
  };

  // If email cannot be resolved at all (e.g. direct entry with no prior state/storage)
  if (!email) {
    return (
      <AuthLayout mode="signin">
        <div style={{ textAlign: "center", padding: "28px 0" }}>
          <div style={{
            width: 48,
            height: 48,
            borderRadius: "50%",
            background: "#FEF2F2",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 16px",
          }}>
            <FaExclamationCircle style={{ fontSize: 24, color: "#EF4444" }} />
          </div>
          <h2 className="apex-exact-card-title">Verification Session Expired</h2>
          <p className="apex-exact-card-subtitle" style={{ marginBottom: 24 }}>
            Please restart the signup process.
          </p>
          <button
            onClick={() => navigate("/signup")}
            className="apex-login-primary-btn"
            style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8 }}
          >
            <FaArrowLeft style={{ fontSize: 13 }} />
            <span>Back to Sign Up</span>
          </button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout mode="signin">
      <div className="apex-exact-card-header">
        <div style={{
          width: 48,
          height: 48,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: "0 auto 16px",
          boxShadow: "0 4px 12px rgba(79, 70, 229, 0.15)",
        }}>
          <FaShieldAlt style={{ fontSize: 22, color: "#4F46E5" }} />
        </div>
        <h2 className="apex-exact-card-title">Verify Your Email</h2>
        <p className="apex-exact-card-subtitle">
          We sent a 6-digit verification code to:
          <br />
          <strong style={{ color: "#0f172a", fontSize: "14px", marginTop: "4px", display: "inline-block" }}>
            {email}
          </strong>
        </p>
      </div>

      {isVerified ? (
        <div style={{ textAlign: "center", padding: "28px 0" }}>
          <FaCheckCircle size={52} color="#10B981" style={{ marginBottom: 16 }} />
          <h3 style={{ margin: "0 0 8px", fontSize: 20, fontWeight: 700, color: "#0f172a" }}>
            Email Verified Successfully!
          </h3>
          <p style={{ color: "#64748b", fontSize: 14, marginBottom: 24 }}>
            Your account is now verified. Redirecting you to sign in...
          </p>
          <button
            onClick={() => navigate("/signin?verified=true", { replace: true })}
            className="apex-login-primary-btn"
          >
            Go to Sign In
          </button>
        </div>
      ) : (
        <form onSubmit={handleVerify} className="apex-exact-form">
          {errorMessage && (
            <div style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              padding: "12px 14px",
              borderRadius: 10,
              background: "#FEF2F2",
              border: "1px solid #FECACA",
              color: "#B91C1C",
              fontSize: 13,
              marginBottom: 16,
            }}>
              <FaExclamationCircle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
              <div>
                <strong>Verification Error</strong>
                <div style={{ marginTop: 2 }}>{errorMessage}</div>
              </div>
            </div>
          )}

          {resendSuccessMsg && (
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 14px",
              borderRadius: 10,
              background: "#F0FDF4",
              border: "1px solid #BBF7D0",
              color: "#166534",
              fontSize: 13,
              marginBottom: 16,
            }}>
              <FaCheckCircle size={16} style={{ flexShrink: 0 }} />
              <div>{resendSuccessMsg}</div>
            </div>
          )}

          <div style={{ marginBottom: 20 }}>
            <label className="apex-exact-label" style={{ display: "block", marginBottom: 10, textAlign: "center" }}>
              Enter 6-Digit Code
            </label>
            <div style={{ display: "flex", justifyContent: "center", gap: "8px" }} onPaste={handlePaste}>
              {codeDigits.map((digit, idx) => (
                <input
                  key={idx}
                  ref={(el) => { inputRefs.current[idx] = el; }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleDigitChange(idx, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(idx, e)}
                  style={{
                    width: "44px",
                    height: "52px",
                    textAlign: "center",
                    fontSize: "22px",
                    fontWeight: 700,
                    borderRadius: "10px",
                    border: digit ? "2px solid #4F46E5" : "1.5px solid #CBD5E1",
                    background: digit ? "#F8FAFC" : "#FFFFFF",
                    color: "#0F172A",
                    outline: "none",
                    boxShadow: digit ? "0 0 0 3px rgba(79, 70, 229, 0.12)" : "none",
                    transition: "all 0.15s ease",
                  }}
                  autoComplete="off"
                />
              ))}
            </div>
            <p style={{ textAlign: "center", color: "#64748b", fontSize: "12px", marginTop: "8px" }}>
              Expires in 10 minutes
            </p>
          </div>

          <button
            type="submit"
            disabled={isVerifying || codeDigits.some((d) => !d)}
            className="apex-login-primary-btn"
            style={{ width: "100%", height: 46 }}
          >
            {isVerifying ? "Verifying Code..." : "Verify Email"}
          </button>

          <div style={{
            marginTop: 20,
            paddingTop: 16,
            borderTop: "1px solid #F1F5F9",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}>
            <div style={{ fontSize: 13, color: "#64748b" }}>
              Didn't receive the code?
            </div>
            <button
              type="button"
              onClick={handleResend}
              disabled={resendCooldown > 0 || isResending}
              style={{
                background: "none",
                border: "none",
                color: resendCooldown > 0 ? "#94A3B8" : "#4F46E5",
                fontSize: 13,
                fontWeight: 600,
                cursor: resendCooldown > 0 ? "not-allowed" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
              }}
            >
              <FaRedo style={{ fontSize: 11, animation: isResending ? "spin 1s linear infinite" : "none" }} />
              {resendCooldown > 0
                ? `Resend Code in ${resendCooldown}s`
                : isResending
                ? "Sending Code..."
                : "Resend Verification Code"}
            </button>
            <Link
              to="/signin"
              style={{
                color: "#64748b",
                fontSize: 13,
                textDecoration: "none",
                marginTop: 4,
              }}
            >
              Back to Sign In
            </Link>
          </div>
        </form>
      )}
    </AuthLayout>
  );
};

export default VerifyEmailPage;
