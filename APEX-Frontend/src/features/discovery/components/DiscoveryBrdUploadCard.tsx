import React, { useState, useEffect, useRef } from "react";
import {
  FaFileUpload,
  FaCheckCircle,
  FaTrashAlt,
  FaExclamationTriangle,
  FaSpinner,
  FaFilePdf,
  FaFileWord,
  FaFileExcel,
  FaFileAlt,
  FaCloudUploadAlt,
  FaEye,
  FaSyncAlt,
} from "react-icons/fa";
import { buildWizardAccentVars } from "@/shared/components/wizard";
import {
  uploadBrdDocument,
  getBrdMetadata,
  deleteBrdDocument,
  getBrdDocumentBlob,
  type BrdMetadata,
} from "../services/discoveryService";

interface DiscoveryBrdUploadCardProps {
  jobId: string | null;
  styles: Record<string, React.CSSProperties>;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileFormatIcon(fileType: string) {
  const type = fileType.toUpperCase();
  if (type.includes("PDF")) return <FaFilePdf style={{ color: "#ef4444" }} />;
  if (type.includes("DOC")) return <FaFileWord style={{ color: "#2563eb" }} />;
  if (type.includes("XLS")) return <FaFileExcel style={{ color: "#16a34a" }} />;
  return <FaFileAlt style={{ color: "#059669" }} />;
}

export function DiscoveryBrdUploadCard({
  jobId,
  styles,
}: DiscoveryBrdUploadCardProps) {
  const [brdMetadata, setBrdMetadata] = useState<BrdMetadata | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isViewing, setIsViewing] = useState(false);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Fetch initial BRD metadata on mount if jobId is available
  useEffect(() => {
    if (!jobId) return;
    let isMounted = true;

    async function loadMetadata() {
      setIsLoadingMetadata(true);
      try {
        const data = await getBrdMetadata(jobId!);
        if (isMounted) {
          setBrdMetadata(data);
        }
      } catch {
        // Silently ignore if no BRD uploaded yet
      } finally {
        if (isMounted) {
          setIsLoadingMetadata(false);
        }
      }
    }

    void loadMetadata();
    return () => {
      isMounted = false;
    };
  }, [jobId]);

  const handleFileSelection = async (file: File) => {
    if (!jobId) {
      setErrorMessage("No active migration job found. Please select a repository first.");
      return;
    }

    const validExtensions = [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".md"];
    const fileExt = `.${file.name.split(".").pop()?.toLowerCase() || ""}`;

    if (!validExtensions.includes(fileExt)) {
      setErrorMessage(
        `Unsupported file type '${fileExt}'. Please select a .pdf, .docx, .doc, .xlsx, .xls, .txt, or .md file.`
      );
      return;
    }

    const maxSize = 25 * 1024 * 1024; // 25 MB
    if (file.size > maxSize) {
      setErrorMessage("File exceeds maximum allowed size of 25MB.");
      return;
    }

    if (file.size === 0) {
      setErrorMessage("The selected file is empty (0 bytes).");
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);

    try {
      const metadata = await uploadBrdDocument(jobId, file);
      setBrdMetadata(metadata);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to upload BRD document.";
      setErrorMessage(msg);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      void handleFileSelection(files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      void handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const handleView = async () => {
    if (!jobId) return;
    setIsViewing(true);
    setErrorMessage(null);
    try {
      const { blob, contentType } = await getBrdDocumentBlob(jobId);
      const typedBlob = new Blob([blob], { type: contentType });
      const url = URL.createObjectURL(typedBlob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to open BRD document.";
      setErrorMessage(msg);
    } finally {
      setIsViewing(false);
    }
  };

  const handleDelete = async () => {
    if (!jobId) return;
    try {
      await deleteBrdDocument(jobId);
      setBrdMetadata(null);
      setErrorMessage(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete BRD document.";
      setErrorMessage(msg);
    }
  };

  return (
    <div
      id="discovery-brd-upload-section"
      style={{
        ...styles.documentCard,
        marginTop: 0,
        marginBottom: 0,
        background: "#ffffff",
        border: "1px solid #dbe5f3",
        borderRadius: 14,
        padding: 20,
        boxShadow: "0 8px 24px rgba(15, 23, 42, 0.04)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        boxSizing: "border-box",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span
            className="wizard-icon-badge wizard-icon-badge-sm"
            style={buildWizardAccentVars("#7c3aed")}
          >
            <FaFileUpload />
          </span>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>
                Functional Testing Requirement Document
              </div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  padding: "2px 8px",
                  borderRadius: 6,
                  background: "#f5f3ff",
                  color: "#7c3aed",
                  border: "1px solid #ddd6fe",
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                }}
              >
                Optional
              </span>
            </div>
            <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
              Upload your functional testing requirement document to automatically generate business-workflow-based Proposed Test Cases.
            </div>
          </div>
        </div>

        {brdMetadata && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                borderRadius: 8,
                background: "#ecfdf5",
                color: "#047857",
                border: "1px solid #a7f3d0",
                fontSize: 12,
                fontWeight: 800,
              }}
            >
              <FaCheckCircle /> Document Attached
            </span>
          </div>
        )}
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div
          style={{
            marginTop: 16,
            padding: "10px 14px",
            borderRadius: 10,
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#dc2626",
            fontSize: 12,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <FaExclamationTriangle />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Content Area */}
      <div style={{ marginTop: 18 }}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.md"
          style={{ display: "none" }}
          onChange={handleFileInputChange}
        />

        {isLoadingMetadata ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: 20, color: "#64748b", fontSize: 13 }}>
            <FaSpinner className="animate-spin" /> Checking for uploaded document...
          </div>
        ) : brdMetadata ? (
          /* Attached File Display */
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "16px 20px",
              borderRadius: 12,
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{ fontSize: 28, display: "flex", alignItems: "center" }}>
                {getFileFormatIcon(brdMetadata.file_type)}
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 800, color: "#0f172a" }}>
                  {brdMetadata.filename}
                </div>
                <div style={{ fontSize: 12, color: "#64748b", marginTop: 2, display: "flex", alignItems: "center", gap: 8 }}>
                  <span>{formatFileSize(brdMetadata.size_bytes)}</span>
                  <span>•</span>
                  <span>{brdMetadata.file_type} Document</span>
                  <span>•</span>
                  <span>Uploaded {new Date(brdMetadata.uploaded_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                </div>
              </div>
            </div>

            {/* Action Buttons: View, Replace, Remove */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              {/* View Action */}
              <button
                type="button"
                onClick={() => void handleView()}
                disabled={isViewing || isUploading}
                aria-label="View document"
                title="View document"
                style={{
                  padding: "6px 14px",
                  borderRadius: 8,
                  border: "1px solid #cbd5e1",
                  background: "#fff",
                  color: "#334155",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: isViewing ? "wait" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  transition: "all 0.15s ease",
                }}
              >
                {isViewing ? <FaSpinner className="animate-spin" size={12} /> : <FaEye size={13} style={{ color: "#2563eb" }} />}
                <span>View</span>
              </button>

              {/* Replace Action */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading || isViewing}
                aria-label="Replace document"
                title="Replace document"
                style={{
                  padding: "6px 14px",
                  borderRadius: 8,
                  border: "1px solid #cbd5e1",
                  background: "#fff",
                  color: "#334155",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  transition: "all 0.15s ease",
                }}
              >
                {isUploading ? <FaSpinner className="animate-spin" size={12} /> : <FaSyncAlt size={12} style={{ color: "#7c3aed" }} />}
                <span>Replace</span>
              </button>

              {/* Remove Action */}
              <button
                type="button"
                onClick={() => void handleDelete()}
                disabled={isUploading || isViewing}
                aria-label="Remove document"
                title="Remove document"
                style={{
                  padding: "6px 12px",
                  borderRadius: 8,
                  border: "1px solid #fee2e2",
                  background: "#fff5f5",
                  color: "#dc2626",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  transition: "all 0.15s ease",
                }}
              >
                <FaTrashAlt size={12} />
                <span>Remove</span>
              </button>
            </div>
          </div>
        ) : (
          /* Dropzone / Upload Action */
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            style={{
              border: `2px dashed ${isDragOver ? "#7c3aed" : "#cbd5e1"}`,
              borderRadius: 14,
              padding: "24px 20px",
              textAlign: "center",
              background: isDragOver ? "#f5f3ff" : "#f8fafc",
              transition: "all 0.15s ease",
              cursor: "pointer",
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            {isUploading ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, padding: 10 }}>
                <FaSpinner className="animate-spin" size={24} style={{ color: "#7c3aed" }} />
                <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>Uploading and validating document...</div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    background: "#f1f5f9",
                    color: "#64748b",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 20,
                  }}
                >
                  <FaCloudUploadAlt />
                </div>
                <div style={{ fontSize: 14, fontWeight: 800, color: "#0f172a" }}>
                  Drag &amp; drop your functional testing requirement document here, or <span style={{ color: "#7c3aed" }}>browse files</span>
                </div>
                <div style={{ fontSize: 12, color: "#64748b" }}>
                  Supports PDF, Word (.docx, .doc), Excel (.xlsx, .xls), Markdown (.md), and plain text (.txt) up to 25MB
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
