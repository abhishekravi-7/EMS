import React from "react";
import { Link, useNavigate } from "react-router-dom";
import apexLogo from "../../../assets/logo.jpg";
import {
  FaCoffee,
  FaArrowLeft,
  FaSearch,
  FaCogs,
  FaChartLine,
  FaShieldAlt,
  FaRandom,
  FaUsers,
  FaCode,
  FaChartBar
} from "react-icons/fa";
import "../auth.css";

export interface AuthLayoutProps {
  mode: "signin" | "signup";
  children: React.ReactNode;
}

/* ── 3D SVG Graphic for Sign In ── */
const SignInHeroGraphic: React.FC = () => (
  <div className="apex-3d-graphic-wrap">
    <svg width="100%" height="210" viewBox="0 0 320 210" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="signinGlass" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#e0f2fe" stopOpacity="0.75" />
        </linearGradient>
        <linearGradient id="signinLineGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#3b82f6" />
        </linearGradient>
        <linearGradient id="shieldGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#1d4ed8" />
        </linearGradient>
        <filter id="shadowGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="8" stdDeviation="12" floodColor="#2563eb" floodOpacity="0.15" />
        </filter>
      </defs>

      {/* Background Floating Cubes */}
      <rect x="250" y="20" width="24" height="24" rx="6" fill="#dbeafe" opacity="0.7" transform="rotate(15 250 20)" />
      <rect x="30" y="40" width="20" height="20" rx="5" fill="#eff6ff" opacity="0.8" transform="rotate(-12 30 40)" />

      {/* Main Glass Dashboard Panel */}
      <g filter="url(#shadowGlow)">
        <rect x="70" y="25" width="210" height="135" rx="14" fill="url(#signinGlass)" stroke="#bfdbfe" strokeWidth="1.5" />
        {/* Top Dots */}
        <circle cx="88" cy="40" r="3.5" fill="#ef4444" />
        <circle cx="98" cy="40" r="3.5" fill="#f59e0b" />
        <circle cx="108" cy="40" r="3.5" fill="#22c55e" />

        {/* Wireframe Cards */}
        <rect x="88" y="54" width="174" height="1" fill="#cbd5e1" opacity="0.5" />
        <rect x="88" y="66" width="70" height="10" rx="3" fill="#cbd5e1" opacity="0.4" />
        <rect x="88" y="82" width="100" height="8" rx="3" fill="#cbd5e1" opacity="0.3" />

        {/* Spline Wave Line Chart */}
        <path d="M 88 125 Q 120 75, 150 110 T 210 70 L 260 95" stroke="url(#signinLineGrad)" strokeWidth="3.5" strokeLinecap="round" fill="none" />
        <path d="M 88 125 Q 120 75, 150 110 T 210 70 L 260 95 L 260 145 L 88 145 Z" fill="url(#signinLineGrad)" opacity="0.1" />

        {/* Floating Mini Widgets inside */}
        <rect x="200" y="105" width="60" height="24" rx="6" fill="#ffffff" stroke="#93c5fd" strokeWidth="1" />
        <rect x="208" y="112" width="28" height="4" rx="2" fill="#2563eb" />
        <rect x="208" y="120" width="44" height="3" rx="1.5" fill="#94a3b8" />
      </g>

      {/* Base Platform Stand */}
      <ellipse cx="175" cy="172" rx="100" ry="16" fill="#bfdbfe" opacity="0.5" />
      <ellipse cx="175" cy="170" rx="90" ry="12" fill="#dbeafe" />

      {/* Foreground Glossy 3D Shield Badge */}
      <g transform="translate(30, 95)" filter="url(#shadowGlow)">
        <path d="M 32 0 C 48 0, 64 6, 64 6 C 64 36, 52 58, 32 70 C 12 58, 0 36, 0 6 C 0 6, 16 0, 32 0 Z" fill="url(#shieldGrad)" stroke="#60a5fa" strokeWidth="1.5" />
        {/* Lock Icon inside Shield */}
        <rect x="22" y="32" width="20" height="16" rx="4" fill="#ffffff" />
        <path d="M 26 32 V 25 C 26 21.7, 28.7 19, 32 19 C 35.3 19, 38 21.7, 38 25 V 32" stroke="#ffffff" strokeWidth="3" fill="none" strokeLinecap="round" />
        <circle cx="32" cy="40" r="2" fill="#1d4ed8" />
      </g>
    </svg>
  </div>
);

/* ── 3D SVG Graphic for Sign Up ── */
const SignUpHeroGraphic: React.FC = () => (
  <div className="apex-3d-graphic-wrap">
    <svg width="100%" height="220" viewBox="0 0 320 220" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="neonRing" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#a855f7" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
        <linearGradient id="terminalBg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0f172a" />
          <stop offset="100%" stopColor="#090d16" />
        </linearGradient>
        <filter id="neonGlow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="0" stdDeviation="8" floodColor="#a855f7" floodOpacity="0.5" />
        </filter>
      </defs>

      {/* Neon Pedestal Ring */}
      <ellipse cx="160" cy="180" rx="100" ry="24" fill="none" stroke="url(#neonRing)" strokeWidth="3" filter="url(#neonGlow)" />
      <ellipse cx="160" cy="180" rx="80" ry="18" fill="url(#neonRing)" opacity="0.15" />

      {/* Main Code Terminal Window */}
      <g transform="translate(60, 20)">
        <rect x="0" y="0" width="200" height="135" rx="14" fill="url(#terminalBg)" stroke="#334155" strokeWidth="1.5" />
        {/* Header Bar */}
        <path d="M 0 14 C 0 6.3 6.3 0 14 0 L 186 0 C 193.7 0 200 6.3 200 14 L 200 24 L 0 24 Z" fill="#1e293b" />
        <circle cx="14" cy="12" r="3.5" fill="#ef4444" />
        <circle cx="24" cy="12" r="3.5" fill="#f59e0b" />
        <circle cx="34" cy="12" r="3.5" fill="#22c55e" />

        {/* Code Syntax Lines */}
        <text x="16" y="44" fontFamily="monospace" fontSize="11" fill="#c084fc">public class <tspan fill="#38bdf8">Apex</tspan> &#123;</text>
        <text x="28" y="62" fontFamily="monospace" fontSize="11" fill="#4ade80">@Modernize</text>
        <text x="28" y="80" fontFamily="monospace" fontSize="11" fill="#f43f5e">public void <tspan fill="#fbbf24">migrate</tspan>() &#123;</text>
        <text x="40" y="98" fontFamily="monospace" fontSize="11" fill="#94a3b8">// AI agent active</text>
        <text x="28" y="116" fontFamily="monospace" fontSize="11" fill="#f43f5e">&#125;</text>
        <text x="16" y="128" fontFamily="monospace" fontSize="11" fill="#c084fc">&#125;</text>
      </g>

      {/* Floating Badge 1: Top Right (Gear) */}
      <g transform="translate(240, 25)" filter="url(#neonGlow)">
        <rect x="0" y="0" width="38" height="38" rx="10" fill="#1e1b4b" stroke="#6366f1" strokeWidth="1.5" />
        <foreignObject x="9" y="8" width="20" height="20">
          <FaCogs style={{ color: "#818cf8", fontSize: 18 }} />
        </foreignObject>
      </g>

      {/* Floating Badge 2: Middle Right (Code </>) */}
      <g transform="translate(260, 95)">
        <rect x="0" y="0" width="40" height="40" rx="10" fill="#1e293b" stroke="#38bdf8" strokeWidth="1.5" />
        <foreignObject x="10" y="10" width="20" height="20">
          <FaCode style={{ color: "#38bdf8", fontSize: 18 }} />
        </foreignObject>
      </g>

      {/* Floating Badge 3: Bottom Left (Chart) */}
      <g transform="translate(25, 120)">
        <rect x="0" y="0" width="38" height="38" rx="10" fill="#0f172a" stroke="#60a5fa" strokeWidth="1.5" />
        <foreignObject x="9" y="9" width="20" height="20">
          <FaChartBar style={{ color: "#60a5fa", fontSize: 18 }} />
        </foreignObject>
      </g>
    </svg>
  </div>
);

const AuthLayout: React.FC<AuthLayoutProps> = ({ mode, children }) => {
  const navigate = useNavigate();
  const isSignIn = mode === "signin";

  return (
    <div className={`apex-auth-page ${isSignIn ? "apex-auth-page--signin" : "apex-auth-page--signup"}`}>
      {/* ── Top Header ── */}
      <header className="apex-auth-topbar">
        <div className="apex-auth-topbar-brand" onClick={() => navigate("/")} style={{ cursor: "pointer" }}>
          <img
            src={apexLogo}
            alt="Java APEX"
            style={{ height: 38, width: "auto", objectFit: "contain", display: "block" }}
          />
        </div>

        {/* <Link to="/" className="apex-auth-back-btn">
          <FaArrowLeft style={{ fontSize: 11 }} />
          <span>Back to Home</span>
        </Link> */}
      </header>

      {/* ── Main Content Container ── */}
      <main className="apex-auth-main">
        <div className="apex-auth-container">
          {/* Left Hero Card */}
          {isSignIn ? (
            <div className="apex-auth-hero-card apex-auth-hero-card--signin">
              <div className="apex-auth-hero-content">
                <h1 className="apex-auth-hero-title">
                  Welcome <span style={{ color: "#2563eb" }}>back!</span>
                </h1>
                <p className="apex-auth-hero-sub">
                  Sign in to continue your Java modernization journey with Java APEX.
                </p>

                <div className="apex-auth-features">
                  <div className="apex-auth-feature-item">
                    <div className="apex-auth-feature-icon"><FaSearch /></div>
                    <div>
                      <div className="apex-auth-feature-title">AI-Powered Analysis</div>
                      <div className="apex-auth-feature-desc">Analyze and assess your codebase with intelligent insights</div>
                    </div>
                  </div>

                  <div className="apex-auth-feature-item">
                    <div className="apex-auth-feature-icon"><FaCogs /></div>
                    <div>
                      <div className="apex-auth-feature-title">Automated Migration</div>
                      <div className="apex-auth-feature-desc">Migrate with confidence using AI-driven recommendations</div>
                    </div>
                  </div>

                  <div className="apex-auth-feature-item">
                    <div className="apex-auth-feature-icon"><FaChartLine /></div>
                    <div>
                      <div className="apex-auth-feature-title">Smart Reporting</div>
                      <div className="apex-auth-feature-desc">Get detailed reports and track your modernization progress</div>
                    </div>
                  </div>

                  <div className="apex-auth-feature-item">
                    <div className="apex-auth-feature-icon"><FaShieldAlt /></div>
                    <div>
                      <div className="apex-auth-feature-title">Secure &amp; Reliable</div>
                      <div className="apex-auth-feature-desc">Enterprise-grade security to keep your code safe</div>
                    </div>
                  </div>
                </div>

                {/* Vector 3D Graphic */}
                <SignInHeroGraphic />

                <div className="apex-auth-security-note">
                  <FaShieldAlt style={{ color: "#2563eb", flexShrink: 0, fontSize: 13 }} />
                  <span>Your data is secure with enterprise-grade encryption and best practices.</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="apex-auth-hero-card apex-auth-hero-card--signup">
              <div className="apex-auth-hero-content">
                <h1 className="apex-auth-hero-title" style={{ color: "#ffffff" }}>
                  Create your<br />
                  <span style={{ color: "#60a5fa" }}>Java APEX</span> account
                </h1>
                <p className="apex-auth-hero-sub" style={{ color: "#93c5fd" }}>
                  Get started with AI-powered Java modernization in minutes.
                </p>

                <div className="apex-auth-features">
                  <div className="apex-auth-feature-item">
                    <div className="apex-auth-feature-icon apex-auth-feature-icon--dark"><FaCogs /></div>
                    <div>
                      <div className="apex-auth-feature-title" style={{ color: "#ffffff" }}>AI-Driven Modernization</div>
                      <div className="apex-auth-feature-desc" style={{ color: "#cbd5e1" }}>Leverage AI to modernize your legacy Java applications</div>
                    </div>
                  </div>

                  <div className="apex-auth-feature-item">
                    <div className="apex-auth-feature-icon apex-auth-feature-icon--dark"><FaRandom /></div>
                    <div>
                      <div className="apex-auth-feature-title" style={{ color: "#ffffff" }}>End-to-End Automation</div>
                      <div className="apex-auth-feature-desc" style={{ color: "#cbd5e1" }}>From analysis to migration, we automate it all</div>
                    </div>
                  </div>

                  <div className="apex-auth-feature-item">
                    <div className="apex-auth-feature-icon apex-auth-feature-icon--dark"><FaChartLine /></div>
                    <div>
                      <div className="apex-auth-feature-title" style={{ color: "#ffffff" }}>Actionable Insights</div>
                      <div className="apex-auth-feature-desc" style={{ color: "#cbd5e1" }}>Clear recommendations and detailed reports</div>
                    </div>
                  </div>

                  <div className="apex-auth-feature-item">
                    <div className="apex-auth-feature-icon apex-auth-feature-icon--dark"><FaUsers /></div>
                    <div>
                      <div className="apex-auth-feature-title" style={{ color: "#ffffff" }}>Collaborate Seamlessly</div>
                      <div className="apex-auth-feature-desc" style={{ color: "#cbd5e1" }}>Invite your team and work together securely</div>
                    </div>
                  </div>
                </div>

                {/* Vector 3D Graphic */}
                <SignUpHeroGraphic />
              </div>
            </div>
          )}

          {/* Right Auth Card Form */}
          <div className="apex-auth-card-wrap">
            <div className="apex-auth-card">
              {children}
            </div>
          </div>
        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="apex-auth-footer">
        <div>© {new Date().getFullYear()} Java APEX. All rights reserved.</div>
        <div className="apex-auth-footer-links">
          <a href="#privacy" className="apex-auth-footer-link">Privacy Policy</a>
          <a href="#terms" className="apex-auth-footer-link">Terms of Service</a>
          <a href="#support" className="apex-auth-footer-link">Support</a>
        </div>
      </footer>
    </div>
  );
};

export default AuthLayout;
