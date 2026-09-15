import React, { useState, useEffect, useRef } from "react";
import {
  FaTimes,
  FaCode,
  FaFileCode,
  FaExchangeAlt,
  FaListUl,
  FaExternalLinkAlt,
  FaCheck,
  FaCopy,
} from "react-icons/fa";
import type { SourceLocationReference } from "../utils/migrationStateModel";
import "./SourceCodeViewerModal.css";

export interface SourceCodeViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  sourceRef: SourceLocationReference | null;
}

export const SourceCodeViewerModal: React.FC<SourceCodeViewerModalProps> = ({
  isOpen,
  onClose,
  sourceRef,
}) => {
  const [activeTab, setActiveTab] = useState<"source" | "diff">("source");
  const [copied, setCopied] = useState(false);
  const targetLineRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  // Smooth auto-scroll to the exact target line
  useEffect(() => {
    if (isOpen && sourceRef) {
      const timer = setTimeout(() => {
        targetLineRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }, 120);
      return () => clearTimeout(timer);
    }
  }, [isOpen, sourceRef, activeTab]);

  if (!isOpen || !sourceRef) return null;

  const {
    fileName,
    filePath,
    startLine = 1,
    endLine = startLine,
    changeType = "MODIFIED",
    beforeLines = [],
    afterLines = [],
    beforeCode,
    afterCode,
    title,
  } = sourceRef;

  const hasDiffData =
    (beforeLines.length > 0 && afterLines.length > 0) ||
    Boolean(beforeCode && afterCode);

  // Prepare full source lines for the "Unified Source View"
  // If afterLines exists, it represents the transformed code file; otherwise synthesize lines from beforeCode/afterCode
  const displayLines: Array<{ num: number; text: string; isHighlighted: boolean }> =
    afterLines.length > 0
      ? afterLines.map((l) => ({
          num: l.num,
          text: l.text.replace(/^[+-]\s*/, ""),
          isHighlighted: l.num >= startLine && l.num <= endLine,
        }))
      : (afterCode || beforeCode || "")
          .split("\n")
          .map((text, idx) => {
            const lineNum = startLine + idx;
            return {
              num: lineNum,
              text,
              isHighlighted: lineNum >= startLine && lineNum <= endLine,
            };
          });

  const handleCopyCode = () => {
    const content = displayLines.map((l) => l.text).join("\n");
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const getChangeTypeBadge = (type: string) => {
    switch (type.toUpperCase()) {
      case "DEPENDENCY":
        return { label: "DEPENDENCY", color: "#38bdf8", bg: "rgba(56, 189, 248, 0.15)" };
      case "TEST":
        return { label: "TEST SUITE", color: "#a78bfa", bg: "rgba(167, 139, 250, 0.15)" };
      case "DEPRECATED":
        return { label: "DEPRECATED", color: "#f59e0b", bg: "rgba(245, 158, 11, 0.15)" };
      case "ADDED":
        return { label: "ADDED", color: "#4ade80", bg: "rgba(74, 222, 128, 0.15)" };
      case "REMOVED":
        return { label: "REMOVED", color: "#f87171", bg: "rgba(248, 113, 113, 0.15)" };
      default:
        return { label: "MODIFIED", color: "#60a5fa", bg: "rgba(96, 165, 250, 0.15)" };
    }
  };

  const badgeMeta = getChangeTypeBadge(changeType);

  return (
    <div className="source-modal-backdrop" onClick={onClose}>
      <div
        className="source-modal-container"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-modal-title"
      >
        {/* ========================================================
            HEADER
            ======================================================== */}
        <div className="source-modal-header">
          <div className="source-modal-header-left">
            <div className="source-file-icon-box">
              <FaFileCode size={18} color="#38bdf8" />
            </div>
            <div className="source-modal-title-group">
              <div className="source-modal-title-row">
                <span id="source-modal-title" className="source-file-name">
                  {fileName}
                </span>
                <span
                  className="source-type-badge"
                  style={{
                    color: badgeMeta.color,
                    background: badgeMeta.bg,
                    border: `1px solid ${badgeMeta.color}40`,
                  }}
                >
                  {badgeMeta.label}
                </span>
                <span className="source-line-badge">
                  {startLine === endLine ? `Line ${startLine}` : `Lines ${startLine}–${endLine}`}
                </span>
              </div>
              <div className="source-file-path-row">
                <span className="source-file-path" title={filePath}>
                  {filePath}
                </span>
                {title && (
                  <span className="source-custom-title">
                    • {title}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="source-modal-header-right">
            {/* View Mode Tabs */}
            {hasDiffData && (
              <div className="source-view-tabs">
                <button
                  type="button"
                  className={`source-tab-btn ${activeTab === "source" ? "is-active" : ""}`}
                  onClick={() => setActiveTab("source")}
                  title="View file source code with highlighted target line"
                >
                  <FaListUl size={12} />
                  <span>Source Code</span>
                </button>
                <button
                  type="button"
                  className={`source-tab-btn ${activeTab === "diff" ? "is-active" : ""}`}
                  onClick={() => setActiveTab("diff")}
                  title="View side-by-side Before and After diff"
                >
                  <FaExchangeAlt size={12} />
                  <span>Before &amp; After Diff</span>
                </button>
              </div>
            )}

            {/* Copy Button */}
            <button
              type="button"
              className="source-copy-btn"
              onClick={handleCopyCode}
              title="Copy code to clipboard"
            >
              {copied ? <FaCheck size={12} color="#4ade80" /> : <FaCopy size={12} />}
              <span>{copied ? "Copied!" : "Copy"}</span>
            </button>

            {/* Close Button */}
            <button
              type="button"
              className="source-modal-close-btn"
              onClick={onClose}
              aria-label="Close viewer"
              title="Close (Esc)"
            >
              <FaTimes size={16} />
            </button>
          </div>
        </div>

        {/* ========================================================
            BODY
            ======================================================== */}
        <div className="source-modal-body">
          {activeTab === "source" ? (
            /* Unified Source View with Line Numbers & Indicator */
            <div className="source-code-editor-view">
              <div className="source-editor-inner">
                {displayLines.map((line, idx) => {
                  const isFirstHighlighted =
                    line.isHighlighted &&
                    (idx === 0 || !displayLines[idx - 1]?.isHighlighted);

                  return (
                    <div
                      key={idx}
                      ref={isFirstHighlighted ? targetLineRef : undefined}
                      className={`source-code-line ${
                        line.isHighlighted ? "is-target-highlighted" : ""
                      }`}
                    >
                      {/* Line Number */}
                      <div className="source-line-number">
                        {line.num}
                      </div>

                      {/* Visual Marker */}
                      <div className="source-marker-column">
                        {line.isHighlighted ? (
                          <span className="source-arrow-marker">&gt;&gt;&gt;</span>
                        ) : (
                          <span className="source-spacer-marker">|</span>
                        )}
                      </div>

                      {/* Code Content */}
                      <div className="source-line-content">
                        <code>{line.text || " "}</code>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Side-by-Side Before & After Diff View */
            <div className="source-diff-view-grid">
              {/* Left: BEFORE */}
              <div className="source-diff-column before-column">
                <div className="source-diff-column-header before-header">
                  <span className="diff-indicator-dot red" />
                  <span>BEFORE MIGRATION ({fileName})</span>
                  <span className="diff-count-pill red">
                    {beforeLines.filter((l) => l.type === "removed").length} Removed
                  </span>
                </div>
                <div className="source-diff-lines-container">
                  {beforeLines.map((line, idx) => {
                    const isTargetLine = line.num >= startLine && line.num <= endLine;
                    return (
                      <div
                        key={`before-${idx}`}
                        className={`source-diff-row ${
                          line.type === "removed" ? "is-diff-removed" : ""
                        } ${isTargetLine ? "is-target-diff-line" : ""}`}
                      >
                        <span className="source-diff-num">{line.num}</span>
                        <span className="source-diff-prefix">
                          {line.type === "removed" ? "-" : " "}
                        </span>
                        <span className="source-diff-text">
                          {line.text.replace(/^[+-]\s*/, "") || " "}
                        </span>
                        {isTargetLine && (
                          <span className="source-diff-target-pill">
                            Targeted
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Right: AFTER */}
              <div className="source-diff-column after-column">
                <div className="source-diff-column-header after-header">
                  <span className="diff-indicator-dot green" />
                  <span>AFTER MIGRATION ({fileName})</span>
                  <span className="diff-count-pill green">
                    {afterLines.filter((l) => l.type === "added").length} Added
                  </span>
                </div>
                <div className="source-diff-lines-container">
                  {afterLines.map((line, idx) => {
                    const isTargetLine = line.num >= startLine && line.num <= endLine;
                    return (
                      <div
                        key={`after-${idx}`}
                        className={`source-diff-row ${
                          line.type === "added" ? "is-diff-added" : ""
                        } ${isTargetLine ? "is-target-diff-line" : ""}`}
                      >
                        <span className="source-diff-num">{line.num}</span>
                        <span className="source-diff-prefix">
                          {line.type === "added" ? "+" : " "}
                        </span>
                        <span className="source-diff-text">
                          {line.text.replace(/^[+-]\s*/, "") || " "}
                        </span>
                        {isTargetLine && (
                          <span className="source-diff-target-pill">
                            Targeted
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ========================================================
            FOOTER STATUS BAR
            ======================================================== */}
        <div className="source-modal-footer">
          <div className="source-footer-left">
            <span className="source-status-dot" />
            <span className="source-status-text">
              Target Reference: <strong>{fileName}</strong> (Line {startLine}
              {startLine !== endLine ? ` to ${endLine}` : ""})
            </span>
          </div>
          <div className="source-footer-right">
            <span className="source-shortcut-hint">
              Press <kbd>Esc</kbd> to close
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
