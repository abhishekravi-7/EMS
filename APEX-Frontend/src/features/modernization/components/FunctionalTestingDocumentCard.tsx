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
} from "@/features/discovery/services/discoveryService";

interface FunctionalTestingDocumentCardProps {
  jobId: string;
  onDocumentChange?: (metadata: BrdMetadata | null) => void;
}

const ALLOWED_EXTENSIONS = [".xlsx", ".xls", ".pdf", ".docx"] as const;

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
  return <FaFileWord style={{ color: "#7c3aed" }} />;
}

export function FunctionalTestingDocumentCard({
  jobId,
  onDocumentChange,
}: FunctionalTestingDocumentCardProps) {
  const [metadata, setMetadata] = useState<BrdMetadata | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isViewing, setIsViewing] = useState(false);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Fetch document metadata for the current jobId on mount and when jobId changes
  useEffect(() => {
    if (!jobId) {
      setMetadata(null);
      return;
    }
    let isMounted = true;

    async function loadJobDocument() {
      setIsLoadingMetadata(true);
      setErrorMessage(null);
      try {
        const data = await getBrdMetadata(jobId);
        if (isMounted) {
          setMetadata(data);
          onDocumentChange?.(data);
        }
      } catch {
        if (isMounted) {
          setMetadata(null);
        }
      } finally {
        if (isMounted) {
          setIsLoadingMetadata(false);
        }
      }
    }

    void loadJobDocument();
    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const validateFile = (file: File): string | null => {
    if (!jobId) {
      return "No active migration job found. Please connect or select a repository first.";
    }

    const nameParts = file.name.split(".");
    const ext = nameParts.length > 1 ? `.${nameParts.pop()?.toLowerCase()}` : "";

    if (!ALLOWED_EXTENSIONS.includes(ext as (typeof ALLOWED_EXTENSIONS)[number])) {
      return `Unsupported file type '${ext || "unknown"}'. Only Excel (.xlsx, .xls), PDF (.pdf), and Word (.docx) files are supported for Functional Testing Documents.`;
    }

    // MIME type check where provided by browser
    if (file.type) {
      const mime = file.type.toLowerCase();
      if (
        mime.startsWith("image/") ||
        mime.startsWith("video/") ||
        mime.startsWith("audio/") ||
        mime === "text/plain" ||
        mime === "text/csv" ||
        mime === "application/x-msdownload" ||
        mime === "application/x-sh"
      ) {
        return `Unsupported file format. The file '${file.name}' cannot be used as a Functional Testing Document.`;
      }
    }

    if (file.size === 0) {
      return "The selected file is empty (0 bytes). Please select a valid document.";
    }

    const maxSize = 25 * 1024 * 1024; // 25 MB
    if (file.size > maxSize) {
      return "The selected file exceeds the maximum allowed size of 25MB.";
    }

    return null;
  };

  const handleProcessFile = async (file: File) => {
    const validationError = validateFile(file);
    if (validationError) {
      setErrorMessage(validationError);
      setSuccessMessage(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await uploadBrdDocument(jobId, file);
      setMetadata(res);
      setSuccessMessage("Functional Testing Document uploaded successfully.");
      onDocumentChange?.(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to upload Functional Testing Document.";
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
      void handleProcessFile(files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      void handleProcessFile(e.dataTransfer.files[0]);
    }
  };

  const handleView = async () => {
    if (!jobId) return;
    setIsViewing(true);
    setErrorMessage(null);
    try {
      const { blob, contentType } = await getBrdDocumentBlob(jobId);
      const typedBlob = new Blob([blob], { type: contentType || "application/octet-stream" });
      const url = URL.createObjectURL(typedBlob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to open Functional Testing Document.";
      setErrorMessage(msg);
    } finally {
      setIsViewing(false);
    }
  };

  const handleRemove = async () => {
    if (!jobId) return;
    try {
      await deleteBrdDocument(jobId);
      setMetadata(null);
      setSuccessMessage(null);
      setErrorMessage(null);
      onDocumentChange?.(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to remove Functional Testing Document.";
      setErrorMessage(msg);
    }
  };

  return (
    <div
      id="functional-testing-document-section"
      style={{
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        borderRadius: 16,
        padding: "20px 24px",
        marginTop: 28,
        marginBottom: 24,
        boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
        boxSizing: "border-box",
      }}
    >
      {/* Hidden Native File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx,.xls,.pdf,.docx"
        style={{ display: "none" }}
        onChange={handleFileInputChange}
        aria-label="Upload Functional Testing Document input"
      />

      {/* Header Section */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <span
            className="wizard-icon-badge wizard-icon-badge-sm"
            style={{
              ...buildWizardAccentVars("#2563eb"),
              marginTop: 2,
              flexShrink: 0,
            }}
          >
            <FaFileUpload />
          </span>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h3
                style={{
                  margin: 0,
                  fontSize: 16,
                  fontWeight: 800,
                  color: "#0f172a",
                  lineHeight: 1.3,
                }}
              >
                Functional Testing Document
              </h3>
            </div>
            <div
              style={{
                fontSize: 13,
                color: "#64748b",
                marginTop: 4,
                lineHeight: 1.4,
              }}
            >
              Upload a document containing functional test scenarios for this migration.
            </div>
          </div>
        </div>

        {metadata && (
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

      {/* Success Notification Alert */}
      {successMessage && (
        <div
          style={{
            marginTop: 14,
            padding: "10px 14px",
            borderRadius: 10,
            background: "#f0fdf4",
            border: "1px solid #bbf7d0",
            color: "#166534",
            fontSize: 12,
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <FaCheckCircle style={{ color: "#22c55e", flexShrink: 0 }} />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Error Notification Alert */}
      {errorMessage && (
        <div
          style={{
            marginTop: 14,
            padding: "10px 14px",
            borderRadius: 10,
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#dc2626",
            fontSize: 12,
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <FaExclamationTriangle style={{ color: "#ef4444", flexShrink: 0 }} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Content Area */}
      <div style={{ marginTop: 16 }}>
        {isLoadingMetadata ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "18px 20px",
              color: "#64748b",
              fontSize: 13,
            }}
          >
            <FaSpinner className="animate-spin" /> Checking for uploaded document...
          </div>
        ) : metadata ? (
          /* Uploaded File Display with View, Replace, Remove */
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "14px 18px",
              borderRadius: 12,
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 200, flex: 1 }}>
              <div style={{ fontSize: 26, display: "flex", alignItems: "center", flexShrink: 0 }}>
                {getFileFormatIcon(metadata.file_type || "")}
              </div>
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 800,
                    color: "#0f172a",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                  title={metadata.filename}
                >
                  {metadata.filename}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: "#64748b",
                    marginTop: 2,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    flexWrap: "wrap",
                  }}
                >
                  <span>{formatFileSize(metadata.size_bytes ?? 0)}</span>
                  <span>•</span>
                  <span>{metadata.file_type || "Document"} Document</span>
                  <span>•</span>
                  <span>
                    Uploaded{" "}
                    {new Date(metadata.uploaded_at || Date.now()).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
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
                aria-label="View functional testing document"
                title="View document in new tab"
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
                {isViewing ? (
                  <FaSpinner className="animate-spin" size={12} />
                ) : (
                  <FaEye size={13} style={{ color: "#2563eb" }} />
                )}
                <span>View</span>
              </button>

              {/* Replace Action */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading || isViewing}
                aria-label="Replace functional testing document"
                title="Select another document to replace current"
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
                {isUploading ? (
                  <FaSpinner className="animate-spin" size={12} />
                ) : (
                  <FaSyncAlt size={12} style={{ color: "#7c3aed" }} />
                )}
                <span>Replace</span>
              </button>

              {/* Remove Action */}
              <button
                type="button"
                onClick={() => void handleRemove()}
                disabled={isUploading || isViewing}
                aria-label="Remove functional testing document"
                title="Remove current document"
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
          /* Empty / Upload Prompt Area */
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            style={{
              border: `2px dashed ${isDragOver ? "#2563eb" : "#cbd5e1"}`,
              borderRadius: 12,
              padding: "20px 24px",
              textAlign: "center",
              background: isDragOver ? "#eff6ff" : "#f8fafc",
              transition: "all 0.15s ease",
              cursor: isUploading ? "wait" : "pointer",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 10,
            }}
            onClick={() => {
              if (!isUploading) {
                fileInputRef.current?.click();
              }
            }}
            role="region"
            aria-label="Functional Testing Document upload area"
          >
            {isUploading ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 0",
                  color: "#2563eb",
                  fontWeight: 700,
                  fontSize: 13,
                }}
              >
                <FaSpinner className="animate-spin" size={18} />
                <span>Uploading Functional Testing Document...</span>
              </div>
            ) : (
              <>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                  style={{
                    padding: "8px 20px",
                    borderRadius: 8,
                    border: "none",
                    background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                    color: "#fff",
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    boxShadow: "0 2px 8px rgba(37, 99, 235, 0.25)",
                    transition: "all 0.15s ease",
                  }}
                  aria-label="Upload Document"
                >
                  <FaFileUpload size={13} />
                  <span>Upload Document</span>
                </button>

                <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                  Supported: <strong style={{ color: "#475569" }}>Excel (.xlsx, .xls)</strong>,{" "}
                  <strong style={{ color: "#475569" }}>PDF (.pdf)</strong>,{" "}
                  <strong style={{ color: "#475569" }}>Word (.docx)</strong>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
