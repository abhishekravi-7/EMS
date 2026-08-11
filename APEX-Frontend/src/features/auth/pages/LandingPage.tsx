import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FaGithub,
  FaCoffee,
  FaSearch,
  FaCogs,
  FaRocket,
  FaCode,
  FaShieldAlt,
  FaChartLine,
  FaLink,
  FaBullseye,
  FaCheckCircle,
  FaChevronRight,
  FaChevronLeft,
  FaArrowRight,
  FaPlay,
  FaTools,
  FaBoxes,
  FaLayerGroup,
  FaTwitter,
  FaLinkedin,
  FaYoutube
} from "react-icons/fa";
import { GITHUB_AUTH_LOGIN_URL } from "@/services/config/env";
import "../../landing/pages/LandingPageDesign.css";

const LOGO_CLOUD = [
  { name: "Java", icon: <FaCoffee style={{ color: "#e76f51" }} /> },
  { name: "Spring Boot", icon: <span style={{ color: "#6a994e", fontWeight: 900 }}>🍃</span> },
  { name: "Maven", icon: <span style={{ color: "#c1121f", fontWeight: 900 }}>M</span> },
  { name: "Gradle", icon: <span style={{ color: "#028090", fontWeight: 900 }}>🐘</span> },
  { name: "JUnit 5", icon: <span style={{ color: "#2563eb", fontWeight: 900 }}>🧪</span> },
  { name: "Docker", icon: <span style={{ color: "#0077b6", fontWeight: 900 }}>🐳</span> },
  { name: "Kubernetes", icon: <span style={{ color: "#326ce5", fontWeight: 900 }}>☸️</span> },
];

const WORKFLOW_STEPS = [
  { num: 1, icon: <FaLink />, title: "Connect", desc: "Connect your GitHub repository securely" },
  { num: 2, icon: <FaSearch />, title: "Discover", desc: "AI scans and analyzes your codebase" },
  { num: 3, icon: <FaBullseye />, title: "Plan", desc: "Get a smart migration strategy and roadmap" },
  { num: 4, icon: <FaRocket />, title: "Modernize", desc: "Automated code refactoring and dependency updates" },
  { num: 5, icon: <FaShieldAlt />, title: "Validate", desc: "Run tests, security scans and quality checks" },
  { num: 6, icon: <FaCheckCircle />, title: "Deploy", desc: "Get reports and deploy with confidence" },
];

const FEATURES = [
  {
    icon: <FaCode />,
    title: "Java Version Upgrade",
    desc: "Upgrade Java 8/11/17 to the latest LTS versions with automated compatibility analysis."
  },
  {
    icon: <FaLayerGroup />,
    title: "Framework Modernization",
    desc: "Migrate Spring Boot 2.x to 3.x and modernize legacy frameworks seamlessly."
  },
  {
    icon: <FaTools />,
    title: "Build Tool Migration",
    desc: "Migrate between Maven, Gradle and other build tools automatically with AI."
  },
  {
    icon: <FaBoxes />,
    title: "Dependency Updates",
    desc: "Detect vulnerable or outdated dependencies and update them safely."
  },
];

const AI_AGENTS = [
  {
    icon: "🤖",
    title: "Discovery Agent",
    desc: "Analyzes repository, code structure and dependencies",
    bg: "#eff6ff",
    color: "#2563eb"
  },
  {
    icon: "🍃",
    title: "Strategy Agent",
    desc: "Creates optimal migration plan and risk assessment",
    bg: "#f0fdf4",
    color: "#16a34a"
  },
  {
    icon: "⚙️",
    title: "Migration Agent",
    desc: "Refactors code, updates dependencies and configurations",
    bg: "#fef3c7",
    color: "#d97706"
  },
  {
    icon: "💻",
    title: "Testing Agent",
    desc: "Generates JUnit tests with high coverage and edge cases",
    bg: "#f3e8ff",
    color: "#7c3aed"
  },
  {
    icon: "📋",
    title: "Report Agent",
    desc: "Generates detailed reports and actionable recommendations",
    bg: "#fae8ff",
    color: "#c026d3"
  },
];

const TESTIMONIALS = [
  {
    quote: "Java APEX reduced our migration effort by nearly 60%. The AI-generated tests saved us hundreds of hours.",
    name: "Anurag Kumar",
    role: "Senior Architect, Ford",
    avatar: "AK",
    company: "Ford"
  },
  {
    quote: "The insights and reports are excellent. It's like having a senior engineer review your entire codebase.",
    name: "Priya Nair",
    role: "Tech Lead, TCS",
    avatar: "PN",
    company: "tcs"
  },
  {
    quote: "Seamless experience from analysis to deployment. Highly recommended for large enterprise apps.",
    name: "Rahul Verma",
    role: "Engineering Manager, Infosys",
    avatar: "RV",
    company: "Infosys"
  }
];

const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTestimonial, setActiveTestimonial] = useState(0);

  const handleStartFree = () => {
    navigate("/signup");
  };

  const handleSignIn = () => {
    navigate("/signin");
  };

  const handleExploreDashboard = () => {
    navigate("/signup");
  };

  const handleGitHubClick = () => {
    window.open(GITHUB_AUTH_LOGIN_URL || "https://github.com", "_blank");
  };

  return (
    <div className="apex-landing-root">
      {/* ── Top Navbar ── */}
      <header className="apex-navbar-wrap">
        <div className="apex-container">
          <nav className="apex-navbar">
            <div className="apex-logo" onClick={() => navigate("/")}>
              <div className="apex-logo-icon">
                <FaCoffee />
              </div>
              <div>
                <span className="apex-logo-text-java">Java </span>
                <span className="apex-logo-text-apex">APEX</span>
              </div>
            </div>

            <ul className="apex-nav-links">
              <li><a href="#features" className="apex-nav-link">Features ▾</a></li>
              <li><a href="#solutions" className="apex-nav-link">Solutions ▾</a></li>
              <li><a href="#pricing" className="apex-nav-link">Pricing</a></li>
              <li><a href="#docs" className="apex-nav-link">Docs</a></li>
              <li><a href="#resources" className="apex-nav-link">Resources ▾</a></li>
            </ul>

            <div className="apex-nav-actions">
              <a href="https://github.com" target="_blank" rel="noreferrer" className="apex-github-badge">
                <FaGithub style={{ fontSize: 14 }} />
                <span>GitHub</span>
                <span style={{ opacity: 0.6, fontSize: 11 }}>★ 1.2k</span>
              </a>
              <button type="button" className="apex-btn-signin" onClick={handleSignIn}>
                Sign In
              </button>
              <button type="button" className="apex-btn-primary" onClick={handleStartFree}>
                Start Free
              </button>
            </div>
          </nav>
        </div>
      </header>

      {/* ── Hero Section ── */}
      <section className="apex-hero-section">
        <div className="apex-container">
          <div className="apex-hero-grid">
            <div>
              <div className="apex-pill-eyebrow">
                <span>⚡</span> AI-POWERED MODERNIZATION PLATFORM
              </div>

              <h1 className="apex-hero-title">
                Modernize.<br />
                Migrate. Accelerate.<br />
                With <span className="apex-gradient-text">Java APEX</span>
              </h1>

              <p className="apex-hero-desc">
                Java APEX helps you analyze, assess and modernize your Java applications with AI.
                From version upgrades to framework migration, test generation, security checks and reporting — all in one platform.
              </p>

              <div className="apex-hero-cta-group">
                <button type="button" className="apex-btn-primary" style={{ padding: "14px 28px", fontSize: 15 }} onClick={handleStartFree}>
                  Start Free <FaArrowRight style={{ fontSize: 13 }} />
                </button>
                <button type="button" className="apex-btn-secondary" style={{ padding: "14px 24px", fontSize: 15 }} onClick={() => navigate("/discovery")}>
                  Watch Demo <FaPlay style={{ fontSize: 11, color: "#2563eb" }} />
                </button>
              </div>

              <div className="apex-trust-badges">
                <span className="apex-trust-badge-item">✓ No credit card required</span>
                <span className="apex-trust-badge-item">✓ Trusted by developers</span>
                <span className="apex-trust-badge-item">✓ SOC2 Ready</span>
              </div>
            </div>

            {/* Interactive Hero Flow Diagram */}
            <div className="apex-diagram-card">
              <svg className="apex-diagram-svg-wrap" viewBox="0 0 500 320" fill="none">
                <path d="M 120 160 C 150 160, 160 50, 190 50" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" />
                <path d="M 120 160 C 150 160, 160 105, 190 105" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" />
                <path d="M 120 160 L 190 160" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" />
                <path d="M 120 160 C 150 160, 160 215, 190 215" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" />
                <path d="M 120 160 C 150 160, 160 270, 190 270" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" />

                <path d="M 380 50 C 400 50, 400 160, 420 160" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" />
                <path d="M 380 105 C 400 105, 400 160, 420 160" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" />
                <path d="M 380 160 L 420 160" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" />
                <path d="M 380 215 C 400 215, 400 160, 420 160" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" />
                <path d="M 380 270 C 400 270, 400 160, 420 160" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" />
              </svg>

              <div className="apex-diagram-flex">
                {/* Node 1: GitHub */}
                <div className="apex-node-github">
                  <div className="apex-node-github-icon">
                    <FaGithub />
                  </div>
                  <div className="apex-node-github-label">GitHub Repository</div>
                </div>

                {/* Center Node Stack */}
                <div className="apex-pipeline-stack">
                  <div className="apex-pipeline-item">
                    <div className="apex-pipeline-icon"><FaSearch /></div>
                    <div>
                      <div className="apex-pipeline-title">Discovery</div>
                      <div className="apex-pipeline-sub">AI analyzes your codebase</div>
                    </div>
                  </div>

                  <div className="apex-pipeline-item">
                    <div className="apex-pipeline-icon"><FaCogs /></div>
                    <div>
                      <div className="apex-pipeline-title">Strategy</div>
                      <div className="apex-pipeline-sub">AI creates migration plan</div>
                    </div>
                  </div>

                  <div className="apex-pipeline-item">
                    <div className="apex-pipeline-icon"><FaRocket /></div>
                    <div>
                      <div className="apex-pipeline-title">Migration</div>
                      <div className="apex-pipeline-sub">Automated refactoring</div>
                    </div>
                  </div>

                  <div className="apex-pipeline-item">
                    <div className="apex-pipeline-icon"><FaCode /></div>
                    <div>
                      <div className="apex-pipeline-title">Testing</div>
                      <div className="apex-pipeline-sub">AI generates JUnit tests</div>
                    </div>
                  </div>

                  <div className="apex-pipeline-item">
                    <div className="apex-pipeline-icon"><FaShieldAlt /></div>
                    <div>
                      <div className="apex-pipeline-title">Validation</div>
                      <div className="apex-pipeline-sub">Security & quality checks</div>
                    </div>
                  </div>
                </div>

                {/* Node 3: Results */}
                <div className="apex-node-results">
                  <div className="apex-node-results-icon">
                    <FaChartLine />
                  </div>
                  <div className="apex-node-results-title">Results &amp; Reports</div>
                  <div className="apex-node-results-sub">Actionable insights and reports</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Logo Cloud ── */}
      <section className="apex-logo-cloud-wrap">
        <div className="apex-container">
          <div className="apex-logo-cloud-title">Trusted by modern engineering teams</div>
          <div className="apex-logo-cloud-grid">
            {LOGO_CLOUD.map((item) => (
              <div key={item.name} className="apex-logo-card">
                <span>{item.icon}</span>
                <span>{item.name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="apex-section" id="how-it-works">
        <div className="apex-container">
          <div className="apex-section-header">
            <div className="apex-section-badge">HOW IT WORKS</div>
            <h2 className="apex-section-title">A simple AI-driven workflow</h2>
            <p className="apex-section-subtitle">From repository to modernization in minutes.</p>
          </div>

          <div className="apex-workflow-grid">
            {WORKFLOW_STEPS.map((step) => (
              <div key={step.title} className="apex-workflow-card">
                <div className="apex-workflow-icon-wrap">
                  {step.icon}
                  <span className="apex-workflow-step-num">{step.num}</span>
                </div>
                <div className="apex-workflow-title">{step.title}</div>
                <div className="apex-workflow-desc">{step.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="apex-section" id="features" style={{ background: "#f8fafc" }}>
        <div className="apex-container">
          <div className="apex-section-header">
            <div className="apex-section-badge">FEATURES</div>
            <h2 className="apex-section-title">Everything you need to modernize Java applications</h2>
          </div>

          <div className="apex-features-grid">
            {FEATURES.map((feat) => (
              <div key={feat.title} className="apex-feature-card">
                <div>
                  <div className="apex-feature-icon-box">
                    {feat.icon}
                  </div>
                  <h3 className="apex-feature-card-title">{feat.title}</h3>
                  <p className="apex-feature-card-desc">{feat.desc}</p>
                </div>
                <div>
                  <span className="apex-feature-link" onClick={handleStartFree}>
                    Learn more <FaChevronRight style={{ fontSize: 10 }} />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Dashboard Overview Dark Section ── */}
      <section className="apex-section">
        <div className="apex-container">
          <div className="apex-dashboard-dark-wrap">
            <div className="apex-dashboard-dark-grid">
              <div>
                <div className="apex-dashboard-left-badge">DASHBOARD OVERVIEW</div>
                <h2 className="apex-dashboard-left-title">
                  Complete visibility.<br />
                  Actionable insights.
                </h2>
                <p className="apex-dashboard-left-desc">
                  Track migration progress, test coverage, vulnerabilities and quality metrics in real-time.
                </p>
                <button type="button" className="apex-btn-primary" style={{ padding: "12px 24px" }} onClick={handleExploreDashboard}>
                  Explore Dashboard <FaArrowRight style={{ fontSize: 12 }} />
                </button>
              </div>

              {/* Dark UI Mockup Window */}
              <div className="apex-mockup-window">
                <div className="apex-mockup-header">
                  <div className="apex-mockup-brand">
                    <FaCoffee style={{ color: "#2563eb" }} />
                    <span>Java APEX</span>
                    <span style={{ fontSize: 12, fontWeight: 500, color: "#64748b", marginLeft: 8 }}>Dashboard</span>
                  </div>
                  <span style={{ fontSize: 11, color: "#64748b" }}>Overview of your modernization projects</span>
                </div>

                <div className="apex-mockup-stats-row">
                  <div className="apex-mockup-stat-card">
                    <div className="apex-mockup-stat-lbl">Total Projects</div>
                    <div className="apex-mockup-stat-val">12</div>
                  </div>
                  <div className="apex-mockup-stat-card">
                    <div className="apex-mockup-stat-lbl">In Progress</div>
                    <div className="apex-mockup-stat-val" style={{ color: "#f59e0b" }}>7</div>
                  </div>
                  <div className="apex-mockup-stat-card">
                    <div className="apex-mockup-stat-lbl">Completed</div>
                    <div className="apex-mockup-stat-val" style={{ color: "#22c55e" }}>5</div>
                  </div>
                  <div className="apex-mockup-stat-card">
                    <div className="apex-mockup-stat-lbl">Success Rate</div>
                    <div className="apex-mockup-stat-val" style={{ color: "#38bdf8" }}>92%</div>
                  </div>
                </div>

                <div className="apex-mockup-widgets-grid">
                  <div className="apex-mockup-widget">
                    <div className="apex-mockup-widget-title">Migration Progress</div>

                    <div className="apex-progress-item">
                      <div className="apex-progress-meta">
                        <span>Payment Service (Java 8 → 17)</span>
                        <span style={{ color: "#38bdf8", fontWeight: 700 }}>85%</span>
                      </div>
                      <div className="apex-progress-track">
                        <div className="apex-progress-fill" style={{ width: "85%" }} />
                      </div>
                    </div>

                    <div className="apex-progress-item">
                      <div className="apex-progress-meta">
                        <span>Order Service (Spring Boot 2 → 3)</span>
                        <span style={{ color: "#22c55e", fontWeight: 700 }}>72%</span>
                      </div>
                      <div className="apex-progress-track">
                        <div className="apex-progress-fill" style={{ width: "72%", background: "linear-gradient(90deg, #16a34a, #4ade80)" }} />
                      </div>
                    </div>

                    <div className="apex-progress-item" style={{ marginBottom: 0 }}>
                      <div className="apex-progress-meta">
                        <span>Inventory Service (Java 11 → 21)</span>
                        <span style={{ color: "#60a5fa", fontWeight: 700 }}>90%</span>
                      </div>
                      <div className="apex-progress-track">
                        <div className="apex-progress-fill" style={{ width: "90%" }} />
                      </div>
                    </div>
                  </div>

                  <div className="apex-mockup-widget">
                    <div className="apex-mockup-widget-title">JUnit Coverage</div>
                    <div className="apex-donut-wrap">
                      <div className="apex-donut-circle">
                        <div className="apex-donut-inner">
                          <span className="apex-donut-val">89%</span>
                          <span className="apex-donut-lbl">Overall Coverage</span>
                        </div>
                      </div>
                      <div style={{ marginTop: 12, display: "flex", gap: 12, fontSize: 10, color: "#94a3b8" }}>
                        <div><strong style={{ color: "#fff" }}>12,843</strong> Lines Covered</div>
                        <div><strong style={{ color: "#fff" }}>1,248</strong> Tests Generated</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── AI Capabilities ── */}
      <section className="apex-section" id="solutions">
        <div className="apex-container">
          <div className="apex-section-header">
            <div className="apex-section-badge">AI CAPABILITIES</div>
            <h2 className="apex-section-title">Powered by specialized AI agents</h2>
          </div>

          <div className="apex-agents-chain">
            {AI_AGENTS.map((agent, idx) => (
              <React.Fragment key={agent.title}>
                <div className="apex-agent-card">
                  <div className="apex-agent-icon-box" style={{ background: agent.bg, color: agent.color }}>
                    {agent.icon}
                  </div>
                  <div className="apex-agent-title">{agent.title}</div>
                  <div className="apex-agent-desc">{agent.desc}</div>
                </div>
                {idx < AI_AGENTS.length - 1 && (
                  <div style={{ textAlign: "center", color: "#cbd5e1", fontSize: 18 }}>➔</div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </section>

      {/* ── Testimonials ── */}
      <section className="apex-section" style={{ background: "#f8fafc" }}>
        <div className="apex-container">
          <div className="apex-section-header">
            <div className="apex-section-badge">TRUSTED BY DEVELOPERS</div>
            <h2 className="apex-section-title">Loved by engineering teams</h2>
          </div>

          <div className="apex-testimonial-carousel">
            {TESTIMONIALS.map((t) => (
              <div key={t.name} className="apex-testimonial-card">
                <div>
                  <div className="apex-testimonial-quote-mark">“</div>
                  <p className="apex-testimonial-quote">{t.quote}</p>
                </div>
                <div className="apex-testimonial-author-row">
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div className="apex-author-avatar">{t.avatar}</div>
                    <div>
                      <div className="apex-author-name">{t.name}</div>
                      <div className="apex-author-role">{t.role}</div>
                    </div>
                  </div>
                  <div className="apex-company-logo">{t.company}</div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 16 }}>
            {TESTIMONIALS.map((_, idx) => (
              <span
                key={idx}
                onClick={() => setActiveTestimonial(idx)}
                style={{
                  width: activeTestimonial === idx ? 24 : 8,
                  height: 8,
                  borderRadius: 4,
                  background: activeTestimonial === idx ? "#2563eb" : "#cbd5e1",
                  cursor: "pointer",
                  transition: "all 0.2s ease"
                }}
              />
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section className="apex-container">
        <div className="apex-cta-banner">
          <div className="apex-cta-left">
            <div className="apex-cta-icon-wrap">🚀</div>
            <div>
              <h2 className="apex-cta-title">Ready to modernize your Java applications?</h2>
              <p className="apex-cta-sub">Start your free trial today. No credit card required.</p>
            </div>
          </div>
          <div className="apex-cta-btns">
            <button type="button" className="apex-btn-cta-white" onClick={handleStartFree}>
              Start Free →
            </button>
            <button type="button" className="apex-btn-cta-purple" onClick={() => navigate("/discovery")}>
              Book a Demo
            </button>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="apex-footer-wrap">
        <div className="apex-container">
          <div className="apex-footer-grid">
            <div>
              <div className="apex-footer-brand-title">
                <FaCoffee style={{ color: "#2563eb" }} />
                <span>Java APEX</span>
              </div>
              <p className="apex-footer-brand-desc">
                AI-powered platform to modernize, migrate and accelerate your Java applications.
              </p>
              <div className="apex-footer-socials">
                <a href="https://github.com" target="_blank" rel="noreferrer" className="apex-footer-social-icon"><FaGithub /></a>
                <a href="https://linkedin.com" target="_blank" rel="noreferrer" className="apex-footer-social-icon"><FaLinkedin /></a>
                <a href="https://twitter.com" target="_blank" rel="noreferrer" className="apex-footer-social-icon"><FaTwitter /></a>
                <a href="https://youtube.com" target="_blank" rel="noreferrer" className="apex-footer-social-icon"><FaYoutube /></a>
              </div>
            </div>

            <div>
              <div className="apex-footer-col-title">Product</div>
              <ul className="apex-footer-links">
                <li><a href="#features" className="apex-footer-link">Features</a></li>
                <li><a href="#solutions" className="apex-footer-link">Solutions</a></li>
                <li><a href="#pricing" className="apex-footer-link">Pricing</a></li>
                <li><a href="#roadmap" className="apex-footer-link">Roadmap</a></li>
              </ul>
            </div>

            <div>
              <div className="apex-footer-col-title">Resources</div>
              <ul className="apex-footer-links">
                <li><a href="#docs" className="apex-footer-link">Documentation</a></li>
                <li><a href="#blog" className="apex-footer-link">Blog</a></li>
                <li><a href="#cases" className="apex-footer-link">Case Studies</a></li>
                <li><a href="#help" className="apex-footer-link">Help Center</a></li>
              </ul>
            </div>

            <div>
              <div className="apex-footer-col-title">Company</div>
              <ul className="apex-footer-links">
                <li><a href="#about" className="apex-footer-link">About Us</a></li>
                <li><a href="#careers" className="apex-footer-link">Careers</a></li>
                <li><a href="#contact" className="apex-footer-link">Contact Us</a></li>
                <li><a href="#privacy" className="apex-footer-link">Privacy Policy</a></li>
              </ul>
            </div>

            <div>
              <div className="apex-footer-col-title">Legal</div>
              <ul className="apex-footer-links">
                <li><a href="#terms" className="apex-footer-link">Terms of Service</a></li>
                <li><a href="#security" className="apex-footer-link">Security</a></li>
                <li><a href="#compliance" className="apex-footer-link">Compliance</a></li>
              </ul>
            </div>
          </div>

          <div className="apex-footer-bottom">
            © {new Date().getFullYear()} Java APEX. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
