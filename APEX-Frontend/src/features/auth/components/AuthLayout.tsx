import React from "react";
import { useNavigate } from "react-router-dom";
import apexLogo from "../../../assets/logo.jpg";
import {
  FaSearch,
  FaCogs,
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

interface HexTileProps {
  x: number;
  y: number;
  size?: number;
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
  color: string;
  label: string;
  isCenter?: boolean;
}

const HexTile = ({ x, y, size = 1, icon: Icon, color, label, isCenter = false }: HexTileProps) => {
  const R = 45 * size; // Radius
  const W = R * 0.866;
  const H = R * 0.5;
  const depth = 12 * size;

  // Hexagon Top Face Points
  const topPoints = `0,-${H} ${W},-${H / 2} ${W},${H / 2} 0,${H} -${W},${H / 2} -${W},-${H / 2}`;
  // Hexagon Left Face Points
  const leftPoints = `-${W},${H / 2} 0,${H} 0,${H + depth} -${W},${H / 2 + depth}`;
  // Hexagon Right Face Points
  const rightPoints = `0,${H} ${W},${H / 2} ${W},${H / 2 + depth} 0,${H + depth}`;

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
      <polyline points={`-${W},${H / 2} 0,${H} ${W},${H / 2}`} fill="none" stroke="#ffffff" strokeWidth="2" />

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

const AuthLayout: React.FC<AuthLayoutProps> = ({ mode, children }) => {
  const navigate = useNavigate();

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
                style={{ height: 48, width: "auto", objectFit: "contain", display: "block" }}
              />
            </div>
            <div className="new-signin-tagline" style={{ fontSize: '18px', fontWeight: 600, color: '#0f172a' }}>AI-Powered Accelerator</div>
          </div>

          {/* Headings */}
          <div className="new-signin-headings">
            <h1 className="new-signin-title">Accelerate Your</h1>
            <h1 className="new-signin-title-blue">Modernization Journey</h1>
            <p className="new-signin-subtext">
              AI-driven insights. Automated modernization.<br />Measurable results.
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
        <div className={`apex-auth-card ${mode === "signup" ? "signup-card-custom" : ""}`}>
          {children}
        </div>
      </div>
    </div>
  );
};


export default AuthLayout;
