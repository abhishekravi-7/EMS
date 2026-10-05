import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FaArrowLeft, FaSyncAlt, FaThLarge } from "react-icons/fa";
import { TOKEN_TRACING_DASHBOARD_URL } from "@/services/config/env";
import "./UsageDashboardPage.css";

export default function UsageDashboardPage() {
  const navigate = useNavigate();
  const [refreshKey, setRefreshKey] = useState(0);

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  return (
    <div className="usage-console-layout">
      <main className="usage-main-surface">
        <header className="usage-main-header">
          <div className="header-title-group">
            <div className="header-icon-wrap">
              <FaThLarge />
            </div>
            <div className="header-text-col">
              <h2 className="header-heading">Token Usage</h2>
              <p className="header-subtitle">Live LLM token, cost and latency traces for every AI call</p>
            </div>
          </div>

          <div className="header-actions">
            <button className="refresh-btn-modern" onClick={handleRefresh}>
              <FaSyncAlt />
              <span>Refresh</span>
            </button>
            <button className="back-btn-modern" onClick={() => navigate("/")}>
              <FaArrowLeft />
              <span>Back</span>
            </button>
          </div>
        </header>

        <div className="usage-canvas">
          <iframe
            key={refreshKey}
            src={TOKEN_TRACING_DASHBOARD_URL}
            title="Token Tracing Dashboard"
            className="usage-iframe-view"
          />
        </div>
      </main>
    </div>
  );
}
