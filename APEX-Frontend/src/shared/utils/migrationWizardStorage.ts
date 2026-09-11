import type { MigrationResult } from "@/features/result/services/resultService";

export interface PersistedWizardFormState {
  maxVisitedIndicatorStep: number;
  isPrivateRepo: boolean;
  patToken: string;
  currentPath: string;
  targetRepoName: string;
  targetRepoNamesByApproach?: {
    fork: string;
    branch: string;
    local: string;
  };
  targetRepoNameEditedByApproach?: {
    fork: boolean;
    branch: boolean;
    local: boolean;
  };
  targetRepoTimestamp: string;
  selectedSourceVersion: string;
  selectedTargetVersion: string;
  selectedConversions: string[];
  runTests: boolean;
  runSonar: boolean;
  runFossa: boolean;
  fixBusinessLogic: boolean;
  selectedTestSources?: { llm: boolean; functionalDoc: boolean; existing: boolean };
  functionalTestToolMethod?: string[];
  functionalTestExecutionMode?: string;
  migrationApproach: string;
  riskLevel: string;
  selectedFrameworks: string[];
  isJavaProject: boolean | null;
  pathHistory: string[];
  isHighRiskProject: boolean;
  highRiskConfirmed: boolean;
  suggestedJavaVersion: string;
  detectedFrameworks: { name: string; path: string; type: string }[];
  userSelectedVersion: string | null;
  sourceVersionStatus: "detected" | "not_selected" | "unknown";
  updateSourceVersion: boolean;
  analysisCompletedSeconds: number;
}

export const WIZARD_REPO_URL_KEY = "migration_wizard_repo_url";
export const WIZARD_SELECTED_REPO_KEY = "migration_wizard_selected_repo";
export const WIZARD_REPO_ANALYSIS_KEY = "migration_wizard_repo_analysis";
export const WIZARD_FORM_STATE_KEY = "migration_wizard_form_state";
export const WIZARD_MIGRATION_JOB_KEY = "migration_wizard_migration_job";
// Job id created by the Connect stage (POST /api/v1/connect), reused downstream.
export const WIZARD_JOB_ID_KEY = "migration_wizard_job_id";
export const WIZARD_DISCOVERY_COMPLETED_KEY = "migration_wizard_discovery_completed";
export const WIZARD_STRATEGY_COMPLETED_KEY = "migration_wizard_strategy_completed";
export const WIZARD_MIGRATION_COMPLETED_KEY = "migration_wizard_migration_completed";
const LEGACY_WIZARD_LOCAL_PROJECT_PATH_KEY = "migration_wizard_local_project_path";

export const WIZARD_STORAGE_KEYS = [
  WIZARD_REPO_URL_KEY,
  WIZARD_SELECTED_REPO_KEY,
  WIZARD_REPO_ANALYSIS_KEY,
  WIZARD_FORM_STATE_KEY,
  WIZARD_MIGRATION_JOB_KEY,
  WIZARD_JOB_ID_KEY,
  WIZARD_DISCOVERY_COMPLETED_KEY,
  WIZARD_STRATEGY_COMPLETED_KEY,
  WIZARD_MIGRATION_COMPLETED_KEY,
];

export const getScopedRepoAnalysisKey = (repoUrlOrJobId?: string | null): string => {
  if (!repoUrlOrJobId) return WIZARD_REPO_ANALYSIS_KEY;
  return `${WIZARD_REPO_ANALYSIS_KEY}_${encodeURIComponent(repoUrlOrJobId.trim())}`;
};

export const getScopedStepUnlockKey = (baseKey: string, repoUrlOrJobId?: string | null): string => {
  if (!repoUrlOrJobId) return baseKey;
  return `${baseKey}_${encodeURIComponent(repoUrlOrJobId.trim())}`;
};

export const readPersistedValue = (key: string) => {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(key);
};

export const writeSessionValue = (key: string, value: string) => {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(key, value);
};

export const removeSessionValue = (key: string) => {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(key);
};

export const readSessionJson = <T,>(key: string): T | null => {
  if (typeof window === "undefined") return null;

  try {
    const raw = readPersistedValue(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
};

export const writeSessionJson = (key: string, value: unknown) => {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(key, JSON.stringify(value));
};

export const clearLegacyWizardStorage = () => {
  if (typeof window === "undefined") return;
  [...WIZARD_STORAGE_KEYS, LEGACY_WIZARD_LOCAL_PROJECT_PATH_KEY].forEach((key) =>
    window.localStorage.removeItem(key)
  );
};

export const clearWizardStorage = () => {
  if (typeof window === "undefined") return;
  [...WIZARD_STORAGE_KEYS, LEGACY_WIZARD_LOCAL_PROJECT_PATH_KEY].forEach((key) =>
    window.sessionStorage.removeItem(key)
  );
  try {
    for (let i = window.sessionStorage.length - 1; i >= 0; i--) {
      const key = window.sessionStorage.key(i);
      if (
        key &&
        (key.startsWith(WIZARD_DISCOVERY_COMPLETED_KEY) ||
          key.startsWith(WIZARD_STRATEGY_COMPLETED_KEY) ||
          key.startsWith(WIZARD_REPO_ANALYSIS_KEY))
      ) {
        window.sessionStorage.removeItem(key);
      }
    }
  } catch {
    // Ignore storage errors
  }
  clearLegacyWizardStorage();
};

export const buildPersistedMigrationJob = (job: MigrationResult): MigrationResult => ({
  ...job,
  job_id: job.job_id || (job as any).jobId || "",
  dependencies: [],
  migration_log: [],
  file_diffs: [],
  issues: [],
  sonar_report: null,
  fossa_report: null,
  test_pipeline: null,
});
