import React, { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { FaLock, FaEye, FaEyeSlash } from "react-icons/fa";
import { confirmPasswordReset } from "../services/authService";
import AuthLayout from "../components/AuthLayout";

const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setErrorMsg("Invalid or missing reset token.");
      setStatus("error");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMsg("Passwords do not match.");
      setStatus("error");
      return;
    }

    setStatus("loading");
    setErrorMsg("");

    try {
      await confirmPasswordReset(token, password);
      setStatus("success");
    } catch (err: unknown) {
      console.error("Failed to reset password:", err);
      const errMsg = err instanceof Error ? err.message : "Failed to reset password. The link might be expired.";
      setErrorMsg(errMsg);
      setStatus("error");
    }
  };

  return (
    <AuthLayout mode="signin">
      <div className="apex-exact-card-header">
        <h2 className="apex-exact-card-title">Create New Password</h2>
        <p className="apex-exact-card-subtitle">
          Please enter your new password below.
        </p>
      </div>

      {status === "success" ? (
        <div style={{ textAlign: "center", padding: "20px 0" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
          <h3 style={{ margin: "0 0 8px", fontSize: 18, fontWeight: 700, color: "#0f172a" }}>
            Password Reset Successfully
          </h3>
          <p style={{ color: "#64748b", fontSize: 14, marginBottom: 20 }}>
            Your password has been changed. You can now login with your new password.
          </p>
          <button
            onClick={() => navigate("/signin")}
            className="apex-login-primary-btn"
          >
            Go to Login
          </button>
        </div>
      ) : (
        <form className="apex-exact-form" onSubmit={handleSubmit}>
          {status === "error" && (
            <div style={{
              padding: "8px 12px", borderRadius: 10, background: "#FEF2F2",
              border: "1px solid #FECACA", color: "#B91C1C", fontSize: 12, marginBottom: 16,
            }}>
              {errorMsg}
            </div>
          )}

          <div className="apex-exact-field">
            <label htmlFor="password" className="apex-exact-label">
              New Password
            </label>
            <div className="apex-exact-input-wrap">
              <FaLock className="apex-exact-input-icon" />
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="Enter new password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="apex-exact-input apex-exact-input-pass"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="apex-exact-eye-btn"
              >
                {showPassword ? <FaEyeSlash size={15} /> : <FaEye size={15} />}
              </button>
            </div>
          </div>

          <div className="apex-exact-field" style={{ marginBottom: 24 }}>
            <label htmlFor="confirmPassword" className="apex-exact-label">
              Confirm New Password
            </label>
            <div className="apex-exact-input-wrap">
              <FaLock className="apex-exact-input-icon" />
              <input
                id="confirmPassword"
                type={showConfirmPassword ? "text" : "password"}
                placeholder="Confirm new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                className="apex-exact-input apex-exact-input-pass"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="apex-exact-eye-btn"
              >
                {showConfirmPassword ? <FaEyeSlash size={15} /> : <FaEye size={15} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={status === "loading"}
            className="apex-login-primary-btn"
          >
            {status === "loading" ? "Resetting..." : "Reset Password"}
          </button>
        </form>
      )}
    </AuthLayout>
  );
};

export default ResetPasswordPage;
