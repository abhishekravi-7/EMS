import React from "react";
import { useNavigate } from "react-router-dom";
import IsometricHeroDiagram from "./IsometricHeroDiagram";
import TransparentLogo from "./TransparentLogo";
import "../landing_exact.css";
import "../auth.css";

export interface AuthLayoutProps {
  mode: "signin" | "signup";
  children: React.ReactNode;
}

const AuthLayout: React.FC<AuthLayoutProps> = ({ children }) => {
  const navigate = useNavigate();

  return (
    <div className="apex-exact-viewport">
      {/* Full-Page Background — Precisely matching the reference image layout in Blue Theme */}
      <div className="apex-full-bg-layer" aria-hidden="true">
        <svg
          viewBox="0 0 1920 1080"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          preserveAspectRatio="none"
          className="apex-full-bg-svg"
        >
          <defs>
            {/* Top-Right Diagonal Ribbons Gradients (Blue Theme) */}
            <linearGradient id="diagRibbon1" x1="100%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#93C5FD" stopOpacity="0.45" />
              <stop offset="50%" stopColor="#BFDBFE" stopOpacity="0.30" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>

            <linearGradient id="diagRibbon2" x1="100%" y1="0%" x2="20%" y2="80%">
              <stop offset="0%" stopColor="#60A5FA" stopOpacity="0.38" />
              <stop offset="60%" stopColor="#93C5FD" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>

            <linearGradient id="diagRibbon3" x1="100%" y1="20%" x2="30%" y2="100%">
              <stop offset="0%" stopColor="#BFDBFE" stopOpacity="0.35" />
              <stop offset="70%" stopColor="#DBEAFE" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>

            {/* Bottom-Left Fluid Waves Gradients (Blue Theme) */}
            <linearGradient id="waveBlue1" x1="0%" y1="100%" x2="60%" y2="40%">
              <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.40" />
              <stop offset="45%" stopColor="#60A5FA" stopOpacity="0.25" />
              <stop offset="85%" stopColor="#93C5FD" stopOpacity="0.10" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>

            <linearGradient id="waveBlue2" x1="0%" y1="100%" x2="50%" y2="30%">
              <stop offset="0%" stopColor="#2563EB" stopOpacity="0.45" />
              <stop offset="40%" stopColor="#3B82F6" stopOpacity="0.30" />
              <stop offset="80%" stopColor="#60A5FA" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>

            <linearGradient id="waveBlue3" x1="0%" y1="100%" x2="40%" y2="10%">
              <stop offset="0%" stopColor="#1D4ED8" stopOpacity="0.30" />
              <stop offset="50%" stopColor="#0EA5E9" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>

            {/* Ambient radial softness */}
            <radialGradient id="ambientBL" cx="0%" cy="100%" r="60%">
              <stop offset="0%"  stopColor="#3B82F6" stopOpacity="0.15" />
              <stop offset="55%" stopColor="#93C5FD" stopOpacity="0.05" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0"   />
            </radialGradient>
            <radialGradient id="ambientTR" cx="100%" cy="0%" r="52%">
              <stop offset="0%"  stopColor="#DBEAFE" stopOpacity="0.35" />
              <stop offset="55%" stopColor="#EFF6FF" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0"   />
            </radialGradient>
          </defs>

          {/* ── 1. Ambient corner glows ── */}
          <rect x="0" y="0" width="1920" height="1080" fill="url(#ambientBL)" />
          <rect x="0" y="0" width="1920" height="1080" fill="url(#ambientTR)" />

          {/* ── 2. Top-Right Diagonal Light Ribbons / Streaks (Exact alignment to uploaded image) ── */}
          <path
            d="M 1320 0 L 1680 0 L 1920 240 L 1920 600 Z"
            fill="url(#diagRibbon1)"
          />
          <path
            d="M 1600 0 L 1920 0 L 1920 320 Z"
            fill="url(#diagRibbon2)"
          />
          <path
            d="M 1150 0 L 1320 0 L 1920 600 L 1920 770 Z"
            fill="url(#diagRibbon3)"
          />
          <path
            d="M 1580 520 L 1920 860 L 1920 1080 L 1760 1080 Z"
            fill="url(#diagRibbon1)"
            opacity="0.6"
          />

          {/* ── 3. Bottom-Left Little Overlapping Waves (Exact alignment to uploaded image) ── */}
          {/* Background Little Wave */}
          <path
            d="M -20 1090 L -20 650 C 150 630, 250 820, 500 850 C 650 870, 750 950, 950 1090 Z"
            fill="url(#waveBlue1)"
          />
          {/* Middle Little Wave */}
          <path
            d="M -20 1090 L -20 780 C 120 750, 220 900, 420 940 C 580 970, 680 1030, 850 1090 Z"
            fill="url(#waveBlue2)"
          />
          {/* Foreground Little Wave */}
          <path
            d="M -20 1090 L -20 900 C 80 880, 160 980, 320 1020 C 450 1050, 550 1070, 650 1090 Z"
            fill="url(#waveBlue3)"
          />
        </svg>
      </div>

      <div className="apex-exact-wrapper">
        {/* Main Two-Column Layout */}
        <main className="apex-exact-grid">
          {/* Left Column (Marketing) */}
          <div className="apex-exact-left-col">
            {/* Top Logo - Sized bigger with equal top & bottom whitespace */}
            <div
              className="apex-top-logo-only-bar"
              onClick={() => navigate("/")}
              role="button"
              tabIndex={0}
            >
              <TransparentLogo height={68} />
            </div>

            <div className="apex-exact-left-top">
              {/* Headline */}
              <div className="apex-exact-headline">
                <h1 className="apex-exact-headline-line1">Accelerate Your</h1>
                <h1 className="apex-exact-headline-line2">Modernization Journey</h1>
              </div>

              {/* Subtext */}
              <p className="apex-exact-subtext">
                AI-driven insights. Automated modernization.<br />
                Measurable results.
              </p>


              {/* Visualization Diagram (Full prominent width with stat card removed) */}
              <div className="apex-exact-visual-row" style={{ flexGrow: 1, display: 'flex', alignItems: 'center' }}>
                <div className="apex-exact-diagram-box" style={{
                  padding: '0',
                  display: 'flex',
                  justifyContent: 'flex-start',
                  alignItems: 'center',
                  width: '100%',
                  height: '100%'
                }}>
                  <IsometricHeroDiagram />
                </div>
              </div>
            </div>
          </div>

          {/* Right Column (Login Card) */}
          <div className="apex-exact-right-col">
            <div className="apex-exact-login-card">
              {/* Inner Card Content */}
              <div className="apex-exact-card-inner">
                {children}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default AuthLayout;
