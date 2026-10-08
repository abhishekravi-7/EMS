import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import {
  connectRepository,
  ConnectRepositoryApiError,
  getLocalProjectCapabilities,
  getRepoVisibility,
  uploadLocalProject,
  uploadLocalProjectChunk,
  type ConnectRepositoryResult,
  type LocalProjectAnalysisResponse,
  type LocalProjectCapabilities,
} from "@/features/connect/services/connectService";
import { isPrivateRepoAccessError } from "@/shared/utils/repoAccessError";
import type { RepoAnalysis, RepoFile, RepoInfo } from "@/shared/types/domain";
import {
  readPersistedValue,
  readSessionJson,
  writeSessionValue,
  WIZARD_JOB_ID_KEY,
  WIZARD_REPO_URL_KEY,
  WIZARD_SELECTED_REPO_KEY,
} from "@/shared/utils/migrationWizardStorage";

type AccessTokenValidationState = "idle" | "validating" | "valid" | "invalid";

interface UseRepositoryConnectParams {
  persistedIsPrivateRepo?: boolean;
  persistedPatToken?: string;
  setRepoAnalysis: Dispatch<SetStateAction<RepoAnalysis | null>>;
  setRepoFiles: Dispatch<SetStateAction<RepoFile[]>>;
  setStep: Dispatch<SetStateAction<number>>;
  setError: Dispatch<SetStateAction<string>>;
  resetRepositorySelectionState: () => void;
  buildLocalRepoRef: (value: string) => string;
  getPathBasename: (value: string) => string;
  isLocalRepoRef: (value: string | null | undefined) => boolean;
  loadZipSync: () => Promise<typeof import("fflate")["zipSync"]>;
}

const MAX_LOCAL_PROJECT_UPLOAD_FILES = 25000;
const MAX_LOCAL_PROJECT_UPLOAD_SIZE_BYTES = 1024 * 1024 * 1024;
const AUTO_ZIP_LOCAL_PROJECT_UPLOAD_FILES = 15000;
const AUTO_ZIP_LOCAL_PROJECT_UPLOAD_SIZE_BYTES = 150 * 1024 * 1024;
const CHUNK_UPLOAD_SIZE_BYTES = 60 * 1024 * 1024;
const WARN_LOCAL_PROJECT_UPLOAD_FILES = 500;
const WARN_LOCAL_PROJECT_UPLOAD_SIZE_BYTES = 150 * 1024 * 1024;

const isEnterpriseGithub = (url: string) => {
  const match = url.match(/^https?:\/\/(www\.)?github\.([^.]+)\.com\//i);
  return match && match[2] !== "" && match[2] !== "com";
};

const normalizeGithubUrl = (url: string): { valid: boolean; normalizedUrl: string; message: string } => {
  if (!url.trim()) {
    return { valid: false, normalizedUrl: "", message: "URL is required" };
  }

  let normalized = url.trim();

  // Explicit check for other git hosting providers (GitLab, Bitbucket, Azure, etc.)
  if (/(?:https?:\/\/)?(?:www\.)?(?:gitlab\.com|bitbucket\.org|dev\.azure\.com)/i.test(normalized)) {
    return {
      valid: false,
      normalizedUrl: "",
      message: "Only GitHub repositories are supported.",
    };
  }

  // Strip URL fragments (#...) and query strings (?...) — never part of a repo path
  normalized = normalized.replace(/[#?].*$/, "");
  normalized = normalized.replace(/\/tree\/[^/]+.*$/, "");
  normalized = normalized.replace(/\/blob\/[^/]+.*$/, "");
  normalized = normalized.replace(/\/src\/.*$/, "");
  normalized = normalized.replace(/\/$/, "");
  normalized = normalized.replace(/\.git$/, "");

  const isGithubUrl = /^https?:\/\/(www\.)?github\.com\/[^/]+\/[^/\s]+$/i.test(normalized);
  const isEnterpriseUrl = /^https?:\/\/(www\.)?github\.[^/]+\.com\/[^/]+\/[^/\s]+$/i.test(normalized);
  const isShortFormat = /^[^/:\s]+\/[^/:\s]+$/.test(normalized) && !normalized.includes(".");

  if (/^https?:\/\//i.test(normalized) && !isGithubUrl && !isEnterpriseUrl) {
    return {
      valid: false,
      normalizedUrl: "",
      message: "Only GitHub repositories are supported.",
    };
  }

  if (isGithubUrl || isEnterpriseUrl || isShortFormat) {
    if (url !== normalized) {
      return {
        valid: true,
        normalizedUrl: normalized,
        message: "URL normalized (removed tree/blob paths)",
      };
    }
    return { valid: true, normalizedUrl: normalized, message: "" };
  }

  return {
    valid: false,
    normalizedUrl: "",
    message: "Invalid URL format. Use: https://github.com/owner/repo or owner/repo",
  };
};

/**
 * Build the URL sent to `POST /api/v1/connect`. The Connect backend currently
 * handles github.com repositories only; for GitLab / GitHub Enterprise / other
 * refs this returns null and the caller keeps the existing (non-backend) flow.
 */
const buildConnectUrl = (value: string): string | null => {
  const normalized = value.trim();
  if (!normalized) return null;

  if (/^https?:\/\//i.test(normalized)) {
    return /(^|\/\/)(www\.)?github\.com\//i.test(normalized) ? normalized : null;
  }

  // Short "owner/repo" form -> expand to a canonical github.com URL.
  if (/^[^/\s]+\/[^/\s]+$/.test(normalized)) {
    return `https://github.com/${normalized}`;
  }

  return null;
};

export function useRepositoryConnect({
  persistedIsPrivateRepo,
  persistedPatToken,
  setRepoAnalysis,
  setRepoFiles,
  setStep,
  setError,
  resetRepositorySelectionState,
  buildLocalRepoRef,
  getPathBasename,
  isLocalRepoRef,
  loadZipSync,
}: UseRepositoryConnectParams) {
  const [repoUrl, setRepoUrl] = useState(() => {
    if (typeof window === "undefined") return "";
    return readPersistedValue(WIZARD_REPO_URL_KEY) || "";
  });
  const [selectedRepo, setSelectedRepo] = useState<RepoInfo | null>(() =>
    readSessionJson<RepoInfo>(WIZARD_SELECTED_REPO_KEY)
  );
  const [githubToken, setGithubToken] = useState("");
  const [githubUserLogin] = useState("");
  const [isPrivateRepo, setIsPrivateRepo] = useState(persistedIsPrivateRepo ?? false);
  const [patToken, setPatToken] = useState(persistedPatToken ?? "");
  const [repoVisibility, setRepoVisibility] = useState<"unknown" | "checking" | "public" | "private" | "not_found">("unknown");
  const [repoErrorMessage, setRepoErrorMessage] = useState("");
  const [isPatModeOpen, setIsPatModeOpen] = useState(false);
  const [jobId, setJobId] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    const activeRepo = readSessionJson<RepoInfo>(WIZARD_SELECTED_REPO_KEY);
    if (!activeRepo || !activeRepo.url) return "";
    return readPersistedValue(WIZARD_JOB_ID_KEY) || "";
  });
  const [connecting, setConnecting] = useState(false);
  // Caches the last successful connect (keyed by url+token) so validating and
  // then continuing does not create a duplicate migration job.
  const lastConnectRef = useRef<{ url: string; token: string; result: ConnectRepositoryResult } | null>(null);
  const lastCheckedUrlRef = useRef<string>("");
  const [repoAccessCheckLoading, setRepoAccessCheckLoading] = useState(false);
  const [accessTokenValidationState, setAccessTokenValidationState] =
    useState<AccessTokenValidationState>("idle");
  const [accessTokenValidationMessage, setAccessTokenValidationMessage] = useState("");
  const [localProjectCapabilities, setLocalProjectCapabilities] = useState<LocalProjectCapabilities | null>(null);
  const [localProjectCapabilitiesLoading, setLocalProjectCapabilitiesLoading] = useState(false);
  const [localProjectUploadFiles, setLocalProjectUploadFiles] = useState<File[]>([]);
  const [localProjectUploadLoading, setLocalProjectUploadLoading] = useState(false);
  const [localProjectUploadCompressing, setLocalProjectUploadCompressing] = useState(false);
  const [localProjectUploadError, setLocalProjectUploadError] = useState("");
  const [localProjectUploadWarning, setLocalProjectUploadWarning] = useState("");

  const urlValidation = repoUrl ? normalizeGithubUrl(repoUrl) : { valid: false, normalizedUrl: "", message: "" };
  const showEnterpriseToken = repoUrl && isEnterpriseGithub(urlValidation.normalizedUrl || repoUrl);
  const activeAccessToken = (showEnterpriseToken ? githubToken : patToken).trim();
  const repositoryNeedsAuthentication = Boolean(showEnterpriseToken || isPrivateRepo);
  const currentToken = useMemo(() => {
    if (showEnterpriseToken) return githubToken.trim();
    if (isPrivateRepo) return patToken.trim() || githubToken.trim();
    if (githubToken.trim()) return githubToken.trim();
    if (patToken.trim()) return patToken.trim();
    return "";
  }, [githubToken, patToken, showEnterpriseToken, isPrivateRepo]);
  const shouldShowPatInput = Boolean(showEnterpriseToken || isPatModeOpen);

  const lastValidatedTokenRef = useRef<{ url: string; token: string; state: AccessTokenValidationState } | null>(null);
  const activeValidationTokenRef = useRef<string>("");

  const resetAccessTokenValidationState = useCallback(() => {
    setAccessTokenValidationState("idle");
    setAccessTokenValidationMessage("");
    lastValidatedTokenRef.current = null;
  }, []);

  // Debounced repository visibility detection (only runs when the repository URL changes)
  useEffect(() => {
    if (!urlValidation.valid) {
      lastCheckedUrlRef.current = "";
      setRepoVisibility("unknown");
      setRepoErrorMessage("");
      setRepoAccessCheckLoading(false);
      lastConnectRef.current = null;
      return;
    }

    const normalizedUrl = urlValidation.normalizedUrl;

    // Avoid re-running visibility check if this URL was already checked
    if (lastCheckedUrlRef.current === normalizedUrl) {
      return;
    }

    if (showEnterpriseToken) {
      lastCheckedUrlRef.current = normalizedUrl;
      setRepoVisibility("private");
      setRepoErrorMessage("");
      setIsPrivateRepo(true);
      setIsPatModeOpen(true);
      setRepoAccessCheckLoading(false);
      return;
    }

    lastCheckedUrlRef.current = normalizedUrl;
    let cancelled = false;
    setRepoAccessCheckLoading(true);
    setRepoVisibility("checking");
    setRepoErrorMessage("");

    const timer = setTimeout(() => {
      getRepoVisibility(normalizedUrl)
        .then((visibility) => {
          if (cancelled) return;
          if (visibility.visibility === "not_found") {
            setRepoVisibility("not_found");
            setIsPrivateRepo(false);
            setIsPatModeOpen(false);
            setRepoErrorMessage(visibility.message || "Repository not found. Please check the URL.");
            return;
          }
          if (visibility.requires_token || visibility.visibility === "private" || visibility.visibility === "private_or_inaccessible") {
            setRepoVisibility("private");
            setIsPrivateRepo(true);
            setIsPatModeOpen(true);
            setRepoErrorMessage("");
            setError("");
            resetAccessTokenValidationState();
          } else {
            setRepoVisibility("public");
            setIsPrivateRepo(false);
            setIsPatModeOpen(false);
            setRepoErrorMessage("");
            setError("");
          }
        })
        .catch((err) => {
          if (cancelled) return;
          const isNotFound = err?.status === 404;
          const isUrlError = err?.status === 400;
          const message = err instanceof Error ? err.message : "";

          if (isNotFound) {
            setRepoVisibility("not_found");
            setIsPrivateRepo(false);
            setIsPatModeOpen(false);
            setRepoErrorMessage(message || "Repository not found. Please check the URL.");
            return;
          }

          const isPrivate = !isUrlError && isPrivateRepoAccessError(message);
          if (isPrivate) {
            setRepoVisibility("private");
            setIsPrivateRepo(true);
            setIsPatModeOpen(true);
            setRepoErrorMessage("");
            resetAccessTokenValidationState();
          } else {
            setRepoVisibility("not_found");
            setIsPrivateRepo(false);
            setIsPatModeOpen(false);
            setRepoErrorMessage(message || "Failed to verify repository.");
          }
        })
        .finally(() => {
          if (!cancelled) {
            setRepoAccessCheckLoading(false);
          }
        });
    }, 500);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [urlValidation.valid, urlValidation.normalizedUrl, showEnterpriseToken, setError, resetAccessTokenValidationState]);

  const persistConnectResult = (result: ConnectRepositoryResult, connectUrl: string, token: string) => {
    setJobId(result.jobId);
    writeSessionValue(WIZARD_JOB_ID_KEY, result.jobId);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(WIZARD_JOB_ID_KEY);
    }
    lastConnectRef.current = { url: connectUrl, token, result };
  };

  const executeAccessTokenValidate = useCallback(async (tokenToValidate?: string) => {
    if (!urlValidation.valid) return;

    const token = (tokenToValidate !== undefined ? tokenToValidate : activeAccessToken).trim();

    if (!token) {
      setAccessTokenValidationState("invalid");
      setAccessTokenValidationMessage(
        showEnterpriseToken
          ? "Enter a GitHub Personal Access Token before validating this GitHub Enterprise repository."
          : "Enter a GitHub Personal Access Token with repo scope before validating this private repository."
      );
      return;
    }

    const normalizedUrl = urlValidation.normalizedUrl;
    if (
      lastValidatedTokenRef.current?.url === normalizedUrl &&
      lastValidatedTokenRef.current?.token === token &&
      lastValidatedTokenRef.current?.state === "valid"
    ) {
      return;
    }

    activeValidationTokenRef.current = token;
    setAccessTokenValidationState("validating");
    setAccessTokenValidationMessage("Validating PAT...");

    const connectUrl = buildConnectUrl(normalizedUrl);

    // github.com repositories are validated through the Connect backend, which
    // also creates the migration job (reused on Continue). Other refs keep the
    // existing visibility check.
    if (connectUrl) {
      try {
        const result = await connectRepository(connectUrl, token);
        if (activeValidationTokenRef.current !== token) return;
        persistConnectResult(result, connectUrl, token);
        const detectedPrivateRepo = result.repoVisibility === "PRIVATE";
        setIsPrivateRepo(detectedPrivateRepo);
        setRepoVisibility(detectedPrivateRepo ? "private" : "public");
        setRepoErrorMessage("");
        setError("");
        setAccessTokenValidationState("valid");
        setAccessTokenValidationMessage(
          detectedPrivateRepo
            ? "Token validated. Private repository access confirmed."
            : "Token validated. Repository access confirmed."
        );
        lastValidatedTokenRef.current = { url: normalizedUrl, token, state: "valid" };
      } catch (err) {
        if (activeValidationTokenRef.current !== token) return;
        const message = err instanceof Error ? err.message : "We couldn't validate this token yet.";
        setAccessTokenValidationState("invalid");
        setAccessTokenValidationMessage(message);
        lastValidatedTokenRef.current = { url: normalizedUrl, token, state: "invalid" };
      }
      return;
    }

    try {
      const visibility = await getRepoVisibility(normalizedUrl, token);
      if (activeValidationTokenRef.current !== token) return;
      const detectedPrivateRepo =
        visibility.requires_token ||
        visibility.visibility === "private" ||
        visibility.visibility === "private_or_inaccessible";

      setIsPrivateRepo(detectedPrivateRepo);
      setError("");
      setAccessTokenValidationState("valid");
      setAccessTokenValidationMessage(
        showEnterpriseToken
          ? "Token validated. Repository authentication looks ready."
          : detectedPrivateRepo
            ? "Token validated. Private repository access looks ready."
            : "Token validated. Repository access looks ready."
      );
      lastValidatedTokenRef.current = { url: normalizedUrl, token, state: "valid" };
    } catch (err) {
      if (activeValidationTokenRef.current !== token) return;
      const message = err instanceof Error ? err.message : "We couldn't validate this token yet.";
      setAccessTokenValidationState("invalid");
      setAccessTokenValidationMessage(
        isPrivateRepoAccessError(message)
          ? "We couldn't verify private repository access. Check that the PAT is correct and includes repo scope."
          : message
      );
      lastValidatedTokenRef.current = { url: normalizedUrl, token, state: "invalid" };
    }
  }, [
    activeAccessToken,
    urlValidation.valid,
    urlValidation.normalizedUrl,
    showEnterpriseToken,
    setError,
  ]);

  const handleAccessTokenValidate = useCallback(async () => {
    await executeAccessTokenValidate(activeAccessToken);
  }, [executeAccessTokenValidate, activeAccessToken]);

  // Debounced automatic PAT validation when user enters or edits a PAT
  useEffect(() => {
    if (!urlValidation.valid || !shouldShowPatInput || !activeAccessToken) {
      if (!activeAccessToken) {
        lastValidatedTokenRef.current = null;
        activeValidationTokenRef.current = "";
      }
      return;
    }

    const currentTokenVal = activeAccessToken;
    const currentUrl = urlValidation.normalizedUrl;

    if (
      lastValidatedTokenRef.current?.url === currentUrl &&
      lastValidatedTokenRef.current?.token === currentTokenVal &&
      lastValidatedTokenRef.current?.state === "valid"
    ) {
      return;
    }

    const timer = setTimeout(() => {
      void executeAccessTokenValidate(currentTokenVal);
    }, 600);

    return () => {
      clearTimeout(timer);
    };
  }, [
    activeAccessToken,
    urlValidation.valid,
    urlValidation.normalizedUrl,
    shouldShowPatInput,
    executeAccessTokenValidate,
  ]);


  const handleRepositoryContinue = async () => {
    if (!urlValidation.valid) return;

    if (repoVisibility === "not_found") {
      setError(repoErrorMessage || "Repository not found. Please verify the URL.");
      return;
    }

    const normalizedUrl = urlValidation.normalizedUrl;
    const token = currentToken.trim();

    if (showEnterpriseToken && !token) {
      setError("");
      setAccessTokenValidationState("invalid");
      setAccessTokenValidationMessage("Enter a GitHub Personal Access Token to analyze this GitHub Enterprise repository.");
      return;
    }

    if ((isPrivateRepo || repoVisibility === "private") && !token) {
      setError("");
      setIsPatModeOpen(true);
      setAccessTokenValidationState("invalid");
      setAccessTokenValidationMessage("This is a private repository. Please provide a GitHub PAT to continue.");
      return;
    }

    // For github.com repositories, verify access and create the migration job
    // via the Connect backend before advancing. Navigation only happens on
    // success. Reuse a previously validated connect to avoid duplicate jobs.
    const connectUrl = buildConnectUrl(normalizedUrl);
    const cached = lastConnectRef.current;
    const alreadyConnected = Boolean(connectUrl && cached?.url === connectUrl && cached?.token === (token || ""));

    if (!alreadyConnected) {
      // Clear old repository selection state and previous job before initiating a new connection
      resetRepositorySelectionState();
    }

    if (connectUrl) {
      if (!alreadyConnected) {
        setConnecting(true);
        setError("");
        try {
          const result = await connectRepository(connectUrl, token || undefined);
          persistConnectResult(result, connectUrl, token || "");
          const isPriv = result.repoVisibility === "PRIVATE";
          setIsPrivateRepo(isPriv);
          setRepoVisibility(isPriv ? "private" : "public");
          setRepoErrorMessage("");
        } catch (err) {
          setConnecting(false);
          const accessStatus =
            err instanceof ConnectRepositoryApiError ? err.accessStatus : "SERVICE_ERROR";
          const message =
            err instanceof Error ? err.message : "We couldn't verify the repository right now.";

          if (accessStatus === "ACCESS_DENIED") {
            setRepoVisibility("private");
            setIsPrivateRepo(true);
            setIsPatModeOpen(true);
            resetAccessTokenValidationState();
            setAccessTokenValidationState("invalid");
            setAccessTokenValidationMessage(message || "Invalid PAT or access denied. Please provide a valid GitHub PAT with repo scope.");
          } else if (accessStatus === "NOT_FOUND") {
            setRepoVisibility("not_found");
            setIsPrivateRepo(false);
            setIsPatModeOpen(false);
            setRepoErrorMessage(message || "Repository not found. Please check the URL.");
            setError(message || "Repository not found. Please check the URL.");
          } else {
            setError(message);
          }
          return; // do not navigate on failure
        }
        setConnecting(false);
      }
    }
    const finalResult = lastConnectRef.current?.result;
    
    setSelectedRepo({
      name: normalizedUrl.split("/").pop() || "",
      full_name: normalizedUrl
        .replace(/^https?:\/\/(www\.)?github\.com\//, "")
        .replace(/^https?:\/\/(www\.)?gitlab\.com\//, ""),
      url: normalizedUrl,
      default_branch: "main",
      language: "Java",
      description: "",
    });

    if (finalResult?.isAlreadyMigrated) {
      setStep(7);
    } else {
      setStep(2);
    }
  };

  const shouldCompressLocalProjectUpload = (files: File[]) => {
    if (files.length === 1 && files[0].name.toLowerCase().endsWith(".zip")) {
      return false;
    }
    return files.length > 1;
  };

  const zipLocalProjectFiles = async (files: File[]): Promise<Blob> => {
    const entries: Record<string, Uint8Array> = {};
    for (const file of files) {
      const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
      const arrayBuffer = await file.arrayBuffer();
      entries[relativePath || file.name] = new Uint8Array(arrayBuffer);
    }
    const zipSync = await loadZipSync();
    const zipped = zipSync(entries, { level: 3 });
    const zipBytes = new Uint8Array(zipped.byteLength);
    zipBytes.set(zipped);
    return new Blob([zipBytes], { type: "application/zip" });
  };

  const handleLocalProjectFilesChange = (files: FileList | null) => {
    if (!files || files.length === 0) {
      setLocalProjectUploadFiles([]);
      setLocalProjectUploadError("Please select a project folder or ZIP archive.");
      setLocalProjectUploadWarning("");
      return;
    }

    const fileArray = Array.from(files);
    const totalSize = fileArray.reduce((sum, file) => sum + file.size, 0);

    // If single file selected, check if user tried to upload non-zip
    if (fileArray.length === 1 && !fileArray[0].name.toLowerCase().endsWith(".zip") && !(fileArray[0] as File & { webkitRelativePath?: string }).webkitRelativePath) {
      setLocalProjectUploadFiles([]);
      setLocalProjectUploadError("Please select a valid ZIP archive (.zip) or a project folder.");
      setLocalProjectUploadWarning("");
      return;
    }

    if (fileArray.length > MAX_LOCAL_PROJECT_UPLOAD_FILES || totalSize > MAX_LOCAL_PROJECT_UPLOAD_SIZE_BYTES) {
      setLocalProjectUploadFiles(fileArray);
      setLocalProjectUploadError(
        `Selected folder is too large to upload directly (${fileArray.length} files, ${(totalSize / (1024 * 1024)).toFixed(1)} MB). Please upload a ZIP archive instead.`
      );
      setLocalProjectUploadWarning("");
      setError("");
      return;
    }

    const isSingleZip = fileArray.length === 1 && fileArray[0].name.toLowerCase().endsWith(".zip");
    const shouldCompress = !isSingleZip && shouldCompressLocalProjectUpload(fileArray);
    let warningMessage = "";
    if (shouldCompress) {
      warningMessage = `Selected folder contains ${fileArray.length} files and ${(totalSize / (1024 * 1024)).toFixed(1)} MB. It will be compressed to ZIP before uploading to improve reliability.`;
    } else if (fileArray.length > WARN_LOCAL_PROJECT_UPLOAD_FILES || totalSize > WARN_LOCAL_PROJECT_UPLOAD_SIZE_BYTES) {
      warningMessage = `Selected folder contains ${fileArray.length} files and ${(totalSize / (1024 * 1024)).toFixed(1)} MB. Upload may take a long time, but it is allowed.`;
    }

    setLocalProjectUploadFiles(fileArray);
    setLocalProjectUploadError("");
    setLocalProjectUploadWarning(warningMessage);
    setError("");

    if (selectedRepo && isLocalRepoRef(selectedRepo.url)) {
      setSelectedRepo(null);
      setRepoAnalysis(null);
    }
  };

  const handleLocalProjectUpload = async () => {
    if (localProjectUploadFiles.length === 0 || localProjectUploadError) return;

    setLocalProjectUploadLoading(true);
    setLocalProjectUploadCompressing(false);
    setLocalProjectUploadError("");
    setLocalProjectUploadWarning("");
    setError("");

    const localFiles = localProjectUploadFiles;
    const isSingleZip = localFiles.length === 1 && localFiles[0].name.toLowerCase().endsWith(".zip");
    const shouldCompress = !isSingleZip && shouldCompressLocalProjectUpload(localFiles);

    const uploadFiles = async (zip: boolean) => {
      const formData = new FormData();
      if (isSingleZip) {
        formData.append("zip_file", localFiles[0], localFiles[0].name);
      } else if (zip) {
        setLocalProjectUploadCompressing(true);
        const zipBlob = await zipLocalProjectFiles(localFiles);

        if (zipBlob.size > CHUNK_UPLOAD_SIZE_BYTES) {
          const totalChunks = Math.ceil(zipBlob.size / CHUNK_UPLOAD_SIZE_BYTES);
          const uploadId = globalThis.crypto?.randomUUID?.() ?? `upload-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
          let finalResponse: LocalProjectAnalysisResponse | null = null;

          for (let index = 0; index < totalChunks; index++) {
            const start = index * CHUNK_UPLOAD_SIZE_BYTES;
            const end = Math.min(start + CHUNK_UPLOAD_SIZE_BYTES, zipBlob.size);
            const chunkBlob = zipBlob.slice(start, end);
            const result = await uploadLocalProjectChunk(
              uploadId,
              index + 1,
              totalChunks,
              chunkBlob,
              "local-project.zip",
            );

            if (index === totalChunks - 1) {
              finalResponse = result as LocalProjectAnalysisResponse;
            }
          }

          if (!finalResponse) {
            throw new Error("Failed to complete chunked upload");
          }

          return finalResponse;
        }

        formData.append("zip_file", zipBlob, "local-project.zip");
        setLocalProjectUploadCompressing(false);
      } else {
        localFiles.forEach((file) => formData.append("files", file, (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name));
      }

      return uploadLocalProject(formData);
    };

    let result: LocalProjectAnalysisResponse | undefined;
    let attemptedZipRetry = false;
    try {
      result = await uploadFiles(shouldCompress);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to upload local project";
      const isNetworkFailure =
        message === "Failed to fetch" ||
        message.includes("ERR_HTTP2_PROTOCOL_ERROR") ||
        message.includes("NetworkError");

      if (!shouldCompress && !isSingleZip && !attemptedZipRetry && isNetworkFailure && localFiles.length > 1) {
        attemptedZipRetry = true;
        try {
          result = await uploadFiles(true);
        } catch (retryErr) {
          const retryMessage = retryErr instanceof Error ? retryErr.message : "Failed to upload local project";
          setLocalProjectUploadError(
            retryMessage === "Failed to fetch"
              ? "Upload failed due to browser or network limits. Try uploading a ZIP archive directly."
              : retryMessage
          );
        }
      } else {
        setLocalProjectUploadError(
          message === "Failed to fetch"
            ? "Upload failed due to browser or network limits. Try uploading a ZIP archive directly."
            : message
        );
      }
    } finally {
      setLocalProjectUploadCompressing(false);
      setLocalProjectUploadLoading(false);
    }

    if (!result) return;

    const uploadedRepoUrl = result.project_path?.startsWith("local://")
      ? result.project_path
      : result.repo_url?.startsWith("local://")
        ? result.repo_url
        : buildLocalRepoRef(result.project_path || result.project_name || "uploaded-project");

    // Clear old job state before setting new job state
    resetRepositorySelectionState();

    if (result.jobId) {
      setJobId(result.jobId);
      writeSessionValue(WIZARD_JOB_ID_KEY, result.jobId);
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(WIZARD_JOB_ID_KEY);
      }
    }

    setSelectedRepo({
      name: result.project_name || getPathBasename(localProjectUploadFiles[0]?.webkitRelativePath || localProjectUploadFiles[0]?.name || "uploaded-project"),
      full_name: uploadedRepoUrl,
      url: uploadedRepoUrl,
      default_branch: "local",
      language: "Java",
      description: "Uploaded local project",
    });

    if (result.analysis) {
      setRepoAnalysis(result.analysis);
    } else {
      setRepoAnalysis(null);
    }
    setRepoFiles([]);
    setStep(2);
  };

  useEffect(() => {
    let cancelled = false;
    setLocalProjectCapabilitiesLoading(true);
    getLocalProjectCapabilities()
      .then((capabilities) => {
        if (!cancelled) {
          setLocalProjectCapabilities(capabilities);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLocalProjectCapabilities(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLocalProjectCapabilitiesLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return {
    repoUrl,
    setRepoUrl,
    selectedRepo,
    setSelectedRepo,
    githubToken,
    setGithubToken,
    githubUserLogin,
    isPrivateRepo,
    setIsPrivateRepo,
    repoVisibility,
    setRepoVisibility,
    repoErrorMessage,
    setRepoErrorMessage,
    isPatModeOpen,
    setIsPatModeOpen,
    patToken,
    setPatToken,
    jobId,
    setJobId,
    connecting,
    repoAccessCheckLoading,
    setRepoAccessCheckLoading,
    accessTokenValidationState,
    setAccessTokenValidationState,
    accessTokenValidationMessage,
    setAccessTokenValidationMessage,
    localProjectCapabilities,
    localProjectCapabilitiesLoading,
    localProjectUploadFiles,
    setLocalProjectUploadFiles,
    localProjectUploadLoading,
    localProjectUploadCompressing,
    localProjectUploadError,
    setLocalProjectUploadError,
    localProjectUploadWarning,
    setLocalProjectUploadWarning,
    urlValidation,
    showEnterpriseToken,
    activeAccessToken,
    repositoryNeedsAuthentication,
    currentToken,
    shouldShowPatInput,
    resetAccessTokenValidationState,
    handleAccessTokenValidate,
    handleRepositoryContinue,
    handleLocalProjectFilesChange,
    handleLocalProjectUpload,
  };
}
