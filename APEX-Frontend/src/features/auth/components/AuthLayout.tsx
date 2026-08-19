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
  FaChartBar,
  FaClipboard,
  FaBolt,
  FaLink
} from "react-icons/fa";
import "../auth.css";

export interface AuthLayoutProps {
  mode: "signin" | "signup";
  children: React.ReactNode;
}

const HexTile = ({ x, y, size = 1, icon: Icon, color, label, isCenter = false }: any) => {
  const R = 45 * size; // Radius
  const W = R * 0.866;
  const H = R * 0.5;
  const depth = 12 * size;

  // Hexagon Top Face Points
  const topPoints = `0,-${H} ${W},-${H/2} ${W},${H/2} 0,${H} -${W},${H/2} -${W},-${H/2}`;
  // Hexagon Left Face Points
  const leftPoints = `-${W},${H/2} 0,${H} 0,${H+depth} -${W},${H/2+depth}`;
  // Hexagon Right Face Points
  const rightPoints = `0,${H} ${W},${H/2} ${W},${H/2+depth} 0,${H+depth}`;

  return (
    <g transform={`translate(${x}, ${y})`}>
      <filter id={`shadow-${label}`}>
        <feDropShadow dx="0" dy="12" stdDeviation="15" floodColor={color} floodOpacity="0.25" />
      </filter>
      
      {/* Shadow */}
      <polygon points={topPoints} fill="#cbd5e1" filter="blur(8px)" opacity="0.6" transform={`translate(0, ${depth + 20})`} />
      
      {/* Left Face */}
      <polygon points={leftPoints} fill="#f1f5f9" />
      {/* Right Face */}
      <polygon points={rightPoints} fill="#e2e8f0" />
      {/* Top Face */}
      <polygon points={topPoints} fill="#ffffff" stroke="#e2e8f0" strokeWidth="1.5" filter={`url(#shadow-${label})`} />
      
      {/* Highlight edge */}
      <polyline points={`-${W},${H/2} 0,${H} ${W},${H/2}`} fill="none" stroke="#ffffff" strokeWidth="2" />
      
      <foreignObject x={-W} y={-H - (isCenter ? 15 : 10)} width={W * 2} height={H * 2 + depth}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', pointerEvents: 'none' }}>
          <Icon size={isCenter ? 36 : 22} style={{ color }} />
          <span style={{ fontSize: isCenter ? 14 : 11, fontWeight: 700, color: '#0f172a', marginTop: 6 }}>{label}</span>
        </div>
      </foreignObject>
    </g>
  );
};

const SignInHeroGraphic: React.FC = () => (
  <div className="apex-3d-graphic-wrap" style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <svg width="100%" height="400" viewBox="0 0 500 400" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ overflow: 'visible', marginTop: '-20px' }}>
      
      {/* Ground lines (circuit board effect) */}
      <g stroke="#bfdbfe" strokeWidth="1.5" opacity="0.6">
        {/* Horizontal */}
        <line x1="50" y1="200" x2="450" y2="200" />
        <circle cx="50" cy="200" r="3" fill="#bfdbfe" />
        <circle cx="450" cy="200" r="3" fill="#bfdbfe" />
        
        {/* Diagonal */}
        <line x1="100" y1="100" x2="250" y2="200" />
        <line x1="400" y1="100" x2="250" y2="200" />
        <line x1="100" y1="300" x2="250" y2="200" />
        <line x1="400" y1="300" x2="250" y2="200" />
        
        {/* Circuit dots */}
        <circle cx="100" cy="100" r="3" fill="#bfdbfe" />
        <circle cx="400" cy="100" r="3" fill="#bfdbfe" />
        <circle cx="100" cy="300" r="3" fill="#bfdbfe" />
        <circle cx="400" cy="300" r="3" fill="#bfdbfe" />
      </g>

      {/* Tiles */}
      <HexTile x={250} y={90} icon={FaSearch} color="#3b82f6" label="Discovery" />
      <HexTile x={360} y={150} icon={FaClipboard} color="#f59e0b" label="Strategy" />
      <HexTile x={360} y={260} icon={FaBolt} color="#f97316" label="Modernization" />
      <HexTile x={140} y={260} icon={FaChartBar} color="#10b981" label="Summary" />
      <HexTile x={140} y={150} icon={FaLink} color="#6366f1" label="Connect" />

      {/* Center Tile */}
      <HexTile x={250} y={200} size={1.5} icon={FaCogs} color="#2563eb" label="LLM" isCenter={true} />
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

  if (isSignIn) {
    return (
      <div className="apex-auth-page new-signin-layout">
        <div className="new-signin-left">
          <div className="new-signin-left-content">
            {/* Branding Top */}
            <div className="new-signin-brand">
              <div className="new-signin-logo" onClick={() => navigate("/")} style={{ cursor: "pointer", marginBottom: '8px' }}>
                <img
                  src={apexLogo}
                  alt="Java APEX"
                  style={{ height: 42, width: "auto", objectFit: "contain", display: "block" }}
                />
              </div>
              <div className="new-signin-tagline" style={{ fontSize: '18px', fontWeight: 600, color: '#0f172a' }}>AI-Powered Accelerator</div>
            </div>

            {/* Headings */}
            <div className="new-signin-headings">
              <h1 className="new-signin-title">Accelerate Your</h1>
              <h1 className="new-signin-title-blue">Modernization Journey</h1>
              <p className="new-signin-subtext">
                AI-driven insights. Automated modernization.<br/>Measurable results.
              </p>
            </div>

            {/* Center Graphic */}
            <div className="new-signin-graphic">
              <SignInHeroGraphic />
            </div>

            {/* Footer */}
            <div className="new-signin-footer">
              <a href="http://www.javaapex.com" target="_blank" rel="noreferrer">www.javaapex.com</a>
              <span className="powered-by">powered by <strong>SORIM.AI</strong></span>
            </div>
          </div>
        </div>
        <div className="new-signin-right">
          <div className="apex-auth-card">
            {children}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="apex-auth-page apex-auth-page--signup">
      {/* ── Top Header ── */}
      <header className="apex-auth-topbar">
        <div className="apex-auth-topbar-brand" onClick={() => navigate("/")} style={{ cursor: "pointer" }}>
          <img
            src={apexLogo}
            alt="Java APEX"
            style={{ height: 38, width: "auto", objectFit: "contain", display: "block" }}
          />
        </div>
      </header>

      {/* ── Main Content Container ── */}
      <main className="apex-auth-main">
        <div className="apex-auth-container">
          {/* Left Hero Card */}
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
