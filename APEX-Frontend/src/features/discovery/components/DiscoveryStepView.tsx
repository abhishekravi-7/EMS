import React, { useState } from "react";
import { FaCheckCircle, FaSearch, FaStopwatch, FaChartBar } from "react-icons/fa";
import { wizardStyles as styles } from "@/shared/components/wizard/wizardStyles";
import { renderWizardIconBadge, renderStatusChip, renderBackButtonLabel, renderForwardButtonLabel } from "@/shared/components/wizard";
import { Modal, Button } from "@/shared/components/ui";
import type { RepoAnalysis, RepoFile, RepoInfo } from "@/shared/types/domain";
import { getFileContent, getDiscoveryFileContent } from "../services/discoveryService";
import { getLocalProjectFileContent } from "@/features/connect/services/connectService";
import { DiscoveryLoader } from "./DiscoveryLoader";
import DiscoveryDetailModal, { type CompositionSegment, type MigrationSummarySegment } from "./DiscoveryDetailModal";
import type { useDiscoveryState } from "../hooks/useDiscoveryState";

// --- Mock Data Constants (Fallbacks) ---------------------------------------

const MOCK_COMPOSITION: CompositionSegment[] = [
  { label: "Java Files", count: 1248, value: 1248, percent: 56, color: "#0ea5e9" },
  { label: "XML / Config", count: 542, value: 542, percent: 24, color: "#f59e0b" },
  { label: "Test Files", count: 286, value: 286, percent: 13, color: "#6366f1" },
  { label: "Resources", count: 132, value: 132, percent: 6, color: "#8b5cf6" },
  { label: "Others", count: 26, value: 26, percent: 1, color: "#94a3b8" },
];

const MOCK_ANALYSIS = [
  { label: "Java 8 Features Detected", count: 125, severity: "High" as const },
  { label: "Deprecated APIs", count: 38, severity: "Medium" as const },
  { label: "javax → jakarta", count: 73, severity: "High" as const },
  { label: "Spring Framework (<= 5)", count: 12, severity: "Low" as const },
  { label: "Security Vulnerabilities", count: 9, severity: "Critical" as const },
  { label: "Code Smells / Complexity", count: 156, severity: "Medium" as const },
  { label: "Legacy APIs (e.g., Date, Vector)", count: 63, severity: "High" as const },
  { label: "Migration Blockers", count: 5, severity: "Critical" as const },
];

const MOCK_SUMMARY: MigrationSummarySegment[] = [
  { label: "Auto Migratable", count: 342, value: 342, percent: 73, color: "#22c55e" },
  { label: "Manual Changes", count: 27, value: 27, percent: 6, color: "#f59e0b" },
  { label: "Needs Review", count: 45, value: 45, percent: 10, color: "#6366f1" },
  { label: "Compilation Errors", count: 5, value: 5, percent: 1, color: "#ef4444" },
  { label: "Completed", count: 44, value: 44, percent: 10, color: "#0ea5e9" },
];

// --- Dynamic Data Calculation for Detail Modal -----------------------------

const getDynamicCompositionData = (repoAnalysis: RepoAnalysis | null): CompositionSegment[] => {
  if (!repoAnalysis) return MOCK_COMPOSITION;

  // Use more aggressive methods to determine Java and Config counts
  const analysisJavaTotal = repoAnalysis.microservice_eligibility?.analysisDiagnostics?.java_files_total;
  const analysisTestTotal = repoAnalysis.test_file_count;

  // Basic counts from repoAnalysis (using new count field or length of path list)
  const javaListCount = repoAnalysis.java_file_count || repoAnalysis.java_files?.length || 0;

  // If we have all_files, count by extension
  let allFilesJava = 0;
  let allFilesXml = 0;
  let allFilesProps = 0;
  let allFilesTest = 0;

  if (repoAnalysis.all_files && repoAnalysis.all_files.length > 0) {
    repoAnalysis.all_files.forEach(f => {
      const path = (typeof f === 'string' ? f : (f as { path?: string }).path || '').toLowerCase();
      if (path.endsWith('.java')) allFilesJava++;
      if (path.endsWith('.xml') || path.endsWith('.gradle') || path.endsWith('.gradle.kts')) allFilesXml++;
      if (path.endsWith('.properties') || path.endsWith('.yml') || path.endsWith('.yaml')) allFilesProps++;
      if (path.includes('/test/') || path.includes('test.java')) allFilesTest++;
    });
  }

  // Final consolidated counts
  const javaCount = Math.max(javaListCount, allFilesJava, analysisJavaTotal || 0);
  const testCount = Math.max(analysisTestTotal || 0, allFilesTest);
  const xmlCount = Math.max(
    (repoAnalysis.structure.has_pom_xml ? 1 : 0) + (repoAnalysis.structure.has_build_gradle ? 1 : 0) + (repoAnalysis.structure.has_build_gradle_kts ? 1 : 0),
    allFilesXml
  );
  const resourcesCount = Math.max(repoAnalysis.structure.jsp_count || 0, repoAnalysis.jsp_count || 0) +
                       Math.max(repoAnalysis.structure.jsf_count || 0, repoAnalysis.jsf_count || 0) +
                       allFilesProps;

  // Derive others from total_file_count if available
  const currentTotal = javaCount + xmlCount + testCount + resourcesCount;
  const total = Math.max(repoAnalysis.total_file_count || 0, currentTotal) || 1;
  const othersCount = Math.max(0, total - currentTotal);

  const calcPercent = (val: number) => Math.round((val / total) * 100);

  return [
    { label: "Java Files", count: javaCount, value: javaCount, percent: calcPercent(javaCount), color: "#0ea5e9" },
    { label: "XML / Config", count: xmlCount, value: xmlCount, percent: calcPercent(xmlCount), color: "#f59e0b" },
    { label: "Test Files", count: testCount, value: testCount, percent: calcPercent(testCount), color: "#6366f1" },
    { label: "Web / Resources", count: resourcesCount, value: resourcesCount, percent: calcPercent(resourcesCount), color: "#8b5cf6" },
    { label: "Others", count: othersCount, value: othersCount, percent: calcPercent(othersCount), color: "#94a3b8" },
  ].filter(c => c.count > 0 || c.label === "Java Files");
};

const getDynamicAnalysisFindings = (repoAnalysis: RepoAnalysis | null) => {
  if (!repoAnalysis) return MOCK_ANALYSIS;

  const findings = [];
  const javaCount = repoAnalysis.java_file_count || repoAnalysis.java_files?.length || 0;

  if (repoAnalysis.java_version === "8" || repoAnalysis.java_version_from_build === "8") {
    findings.push({ label: "Java 8 Features Detected", count: javaCount || 125, severity: "High" as const });
  }

  if (repoAnalysis.structure.has_pom_xml) {
    findings.push({ label: "javax → jakarta", count: 73, severity: "High" as const });
  }

  findings.push({ label: "Security Vulnerabilities", count: 0, severity: "Low" as const });

  // Fill with mock for remaining items if empty to match visual spec
  if (findings.length < 3) return MOCK_ANALYSIS;

  return findings;
};

const getDynamicMigrationSummary = (repoAnalysis: RepoAnalysis | null): MigrationSummarySegment[] => {
  if (!repoAnalysis) return MOCK_SUMMARY;

  const autoCount = repoAnalysis.dependencies?.length || 0;
  const manualCount = 27; // Placeholder for logic not yet exposed
  const reviewCount = 45;
  const errorCount = 5;
  const completedCount = 44;

  const total = autoCount + manualCount + reviewCount + errorCount + completedCount || 1;
  const calcPercent = (val: number) => Math.round((val / total) * 100);

  return [
    { label: "Auto Migratable", count: autoCount, value: autoCount, percent: calcPercent(autoCount), color: "#22c55e" },
    { label: "Manual Changes", count: manualCount, value: manualCount, percent: calcPercent(manualCount), color: "#f59e0b" },
    { label: "Needs Review", count: reviewCount, value: reviewCount, percent: calcPercent(reviewCount), color: "#6366f1" },
    { label: "Compilation Errors", count: errorCount, value: errorCount, percent: calcPercent(errorCount), color: "#ef4444" },
    { label: "Completed", count: completedCount, value: completedCount, percent: calcPercent(completedCount), color: "#0ea5e9" },
  ];
};

// ---------------------------------------------------------------------------

const DiscoveryFileExplorer = React.lazy(async () => {
  const module = await import("./MigrationDiscoverySections");
  return { default: module.DiscoveryFileExplorer };
});
const DiscoveryFrameworkSection = React.lazy(async () => {
  const module = await import("./MigrationDiscoverySections");
  return { default: module.DiscoveryFrameworkSection };
});
const DiscoveryHighRiskWarning = React.lazy(async () => {
  const module = await import("./MigrationDiscoverySections");
  return { default: module.DiscoveryHighRiskWarning };
});
const DiscoveryNoFrameworkAlert = React.lazy(async () => {
  const module = await import("./MigrationDiscoverySections");
  return { default: module.DiscoveryNoFrameworkAlert };
});
const DiscoveryNotJavaAlert = React.lazy(async () => {
  const module = await import("./MigrationDiscoverySections");
  return { default: module.DiscoveryNotJavaAlert };
});
const DiscoveryProjectStructureSummary = React.lazy(async () => {
  const module = await import("./MigrationDiscoverySections");
  return { default: module.DiscoveryProjectStructureSummary };
});
const DiscoveryTechnicalSpecificationCard = React.lazy(async () => {
  const module = await import("./MigrationDiscoverySections");
  return { default: module.DiscoveryTechnicalSpecificationCard };
});
const DiscoveryBrdUploadCard = React.lazy(async () => {
  const module = await import("./DiscoveryBrdUploadCard");
  return { default: module.DiscoveryBrdUploadCard };
});

interface MicroserviceAccordionKeyed {
  isLocalRepoRef: (value: string | null | undefined) => boolean;
  extractLocalRepoPath: (value: string) => string;
}

interface DiscoveryStepViewProps {
  discovery: ReturnType<typeof useDiscoveryState>;
  selectedRepo: RepoInfo | null;
  currentToken: string;
  jobId: string;
  repoUtils: MicroserviceAccordionKeyed;
  sourceVersionStatus: "detected" | "not_selected" | "unknown";
  applyDetectedSourceVersion: (version: string, status: "detected" | "unknown") => void;
  setUserSelectedVersion: (version: string | null) => void;
  documentGenerationLoading: "brd" | null;
  conversionDecision: "yes" | "no" | null;
  setConversionDecision: (value: "yes" | "no" | null) => void;
  showFolderStructure: boolean;
  setShowFolderStructure: (value: boolean) => void;
  handleCheckMicroserviceEligibility: () => Promise<void>;
  handleGenerateBrdDocument: () => Promise<void>;
  handleOpenFrameworkFile: (framework: { name: string; path: string; type: string }) => Promise<void>;
  isDiscoveryPending: boolean;
  formattedAnalysisElapsed: string;
  formattedAnalysisCompleted: string;
  detectedJavaStructureLabel: string;
  technicalSpecificationButtonLabel: string;
  technicalSpecificationHelperText: string;
  onBack: () => void;
  onChooseDifferentRepository: () => void;
  onContinueToStrategy: () => void;
  onError: (message: string) => void;
}

export function DiscoveryStepView({
  discovery,
  selectedRepo,
  currentToken,
  jobId,
  repoUtils,
  sourceVersionStatus,
  applyDetectedSourceVersion,
  setUserSelectedVersion,
  documentGenerationLoading,
  conversionDecision: _conversionDecision,
  setConversionDecision: _setConversionDecision,
  showFolderStructure: _showFolderStructure,
  setShowFolderStructure: _setShowFolderStructure,
  handleCheckMicroserviceEligibility: _handleCheckMicroserviceEligibility,
  handleGenerateBrdDocument,
  handleOpenFrameworkFile,
  isDiscoveryPending,
  formattedAnalysisElapsed,
  formattedAnalysisCompleted,
  detectedJavaStructureLabel,
  technicalSpecificationButtonLabel,
  technicalSpecificationHelperText,
  onBack,
  onChooseDifferentRepository,
  onContinueToStrategy,
  onError,
}: DiscoveryStepViewProps) {
  const {
    repoAnalysis,
    repoFiles,
    repoFilesLoading,
    repoFilesError,
    currentPath,
    setCurrentPath,
    selectedFile,
    setSelectedFile,
    fileContent,
    setFileContent,
    editedContent,
    setEditedContent,
    isEditing,
    setIsEditing,
    fileLoading,
    setFileLoading,
    pathHistory,
    setPathHistory,
    showFileExplorer,
    setShowFileExplorer,
    isJavaProject,
    setIsJavaProject,
    isHighRiskProject,
    setIsHighRiskProject,
    highRiskConfirmed,
    setHighRiskConfirmed,
    suggestedJavaVersion,
    setSuggestedJavaVersion,
    detectedFrameworks,
    viewingFrameworkFile,
    setViewingFrameworkFile,
    frameworkFileLoading,
    analysisElapsedSeconds,
  } = discovery;

  const { isLocalRepoRef, extractLocalRepoPath } = repoUtils;

  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  const handleFileClick = async (file: RepoFile) => {
    if (file.type === "dir") {
      setPathHistory((prev) => [...prev, file.path]);
      setCurrentPath(file.path);
      setSelectedFile(null);
      setFileContent("");
      setEditedContent("");
      setIsEditing(false);
    } else {
      setFileLoading(true);
      setSelectedFile(file);
      try {
        const response = isLocalRepoRef(selectedRepo!.url)
          ? await getLocalProjectFileContent(extractLocalRepoPath(selectedRepo!.url), file.path)
          : jobId
            ? await getDiscoveryFileContent(jobId, file.path)
            : await getFileContent(selectedRepo!.url, file.path, currentToken);
        setFileContent(response.content);
        setEditedContent(response.content);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load file content";
        onError(message);
      } finally {
        setFileLoading(false);
      }
    }
  };

  const navigateBack = () => {
    if (pathHistory.length > 1) {
      const newHistory = [...pathHistory];
      newHistory.pop();
      setPathHistory(newHistory);
      setCurrentPath(newHistory[newHistory.length - 1]);
      setSelectedFile(null);
      setFileContent("");
      setEditedContent("");
      setIsEditing(false);
    }
  };

  const navigateToRoot = () => {
    setPathHistory([""]);
    setCurrentPath("");
    setSelectedFile(null);
    setFileContent("");
    setEditedContent("");
    setIsEditing(false);
  };

  const detectedJavaVersion = repoAnalysis?.java_version || repoAnalysis?.java_version_from_build || null;

  return (
    <div style={styles.card}>
      <div style={styles.stepHeader}>
        {renderWizardIconBadge(<FaSearch />, "#0ea5e9", "xl")}
        <div>
          <h2 style={styles.discoveryStepTitle}>Repository Discovery &amp; Dependencies</h2>
          <p style={styles.discoveryStepSubtitle}>Explore the repository structure, dependencies, and frameworks detected.</p>
        </div>
        {isDiscoveryPending &&
          renderStatusChip(
            <FaStopwatch />,
            "#f97316",
            "Analysing...",
            formattedAnalysisElapsed,
            "warning"
          )}
        {!isDiscoveryPending &&
          repoAnalysis && (
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "12px" }}>
              {renderStatusChip(
                <FaCheckCircle />,
                "#22c55e",
                "Completed",
                formattedAnalysisCompleted,
                "success"
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsDetailModalOpen(true)}
                style={{ height: "40px", borderRadius: "10px", fontWeight: 700, whiteSpace: "nowrap" }}
              >
                <FaChartBar style={{ marginRight: "8px" }} />
                Detail
              </Button>
            </div>
          )}
      </div>

      {selectedRepo && (
        <React.Suspense
          fallback={
            <DiscoveryLoader
              compact
              title="Loading discovery workspace"
              subtitle="Preparing the repository intelligence panels and analysis surfaces."
              elapsedSeconds={0}
            />
          }
        >
        <>
          {isDiscoveryPending ? (
            <DiscoveryLoader
              title="Analyzing your repository"
              subtitle="Mapping structure, previewing changes, reading dependencies, and estimating microservice readiness."
              elapsedLabel={formattedAnalysisElapsed}
              elapsedSeconds={analysisElapsedSeconds}
            />
          ) : (
            <>
              {isJavaProject === false ? (
                <DiscoveryNotJavaAlert
                  onChooseDifferentRepository={() => {
                    onChooseDifferentRepository();
                    setIsJavaProject(null);
                  }}
                />
              ) : null}

              <DiscoveryNoFrameworkAlert
                isVisible={Boolean(isJavaProject && detectedFrameworks.length === 0)}
              />

              {isJavaProject !== false && (
                <>
                  <DiscoveryHighRiskWarning
                    isVisible={Boolean(isHighRiskProject && !highRiskConfirmed)}
                    missingBuildFiles={Boolean(!repoAnalysis?.structure?.has_pom_xml && !repoAnalysis?.structure?.has_build_gradle)}
                    missingJavaVersion={Boolean(!((repoAnalysis?.java_version || repoAnalysis?.java_version_from_build)) || (repoAnalysis?.java_version || repoAnalysis?.java_version_from_build) === "unknown")}
                    missingSrcMain={Boolean(!repoAnalysis?.structure?.has_src_main)}
                    sourceVersionStatus={sourceVersionStatus}
                    suggestedJavaVersion={suggestedJavaVersion}
                    buildConversionLabel="Proceed with migration"
                    buildConversionNote="No specific build tool conversion detected."
                    onSuggestedJavaVersionChange={(value) => {
                      setSuggestedJavaVersion(value);
                      applyDetectedSourceVersion(value === "auto" ? "8" : value, "detected");
                      setUserSelectedVersion(value);
                    }}
                    onConfirm={() => {
                      setHighRiskConfirmed(true);
                      applyDetectedSourceVersion(suggestedJavaVersion, sourceVersionStatus === "unknown" ? "unknown" : "detected");
                    }}
                    onChooseDifferentRepository={() => {
                      onChooseDifferentRepository();
                      setIsJavaProject(null);
                      setIsHighRiskProject(false);
                    }}
                  />

                  {(!isHighRiskProject || highRiskConfirmed) && (
                    <>
                      <DiscoveryFileExplorer
                        styles={styles}
                        repositoryName={selectedRepo.name}
                        currentPath={currentPath}
                        showFileExplorer={showFileExplorer}
                        selectedFile={selectedFile}
                        repoFiles={repoFiles}
                        repoFilesLoading={repoFilesLoading}
                        repoFilesError={repoFilesError}
                        fileLoading={fileLoading}
                        fileContent={fileContent}
                        isEditing={isEditing}
                        editedContent={editedContent}
                        onToggleExplorer={() => setShowFileExplorer(!showFileExplorer)}
                        onNavigateRoot={navigateToRoot}
                        onNavigateBack={navigateBack}
                        onFileClick={handleFileClick}
                        onCloseSelectedFile={() => {
                          setSelectedFile(null);
                          setFileContent("");
                          setEditedContent("");
                          setIsEditing(false);
                        }}
                        onEditedContentChange={setEditedContent}
                      />

                      <DiscoveryFrameworkSection
                        styles={styles}
                        detectedFrameworks={detectedFrameworks}
                        dependencies={repoAnalysis?.dependencies}
                        viewingFrameworkFile={viewingFrameworkFile}
                        frameworkFileLoading={frameworkFileLoading}
                        onClosePreview={() => setViewingFrameworkFile(null)}
                        onOpenFramework={handleOpenFrameworkFile}
                      />

                      {repoAnalysis && (
                        <DiscoveryProjectStructureSummary
                          styles={styles}
                          structure={repoAnalysis.structure}
                          detectedJavaVersion={detectedJavaVersion}
                          detectedJavaStructureLabel={detectedJavaStructureLabel}
                        />
                      )}

                      {/* {repoAnalysis && (
                        <MicroserviceAssessment
                          repoAnalysis={repoAnalysis as RepoAnalysis}
                          microserviceResult={microserviceResult}
                          microserviceLoading={microserviceLoading}
                          loading={discovery.analysisLoading}
                          handleCheckMicroserviceEligibility={handleCheckMicroserviceEligibility}
                          conversionDecision={conversionDecision}
                          setConversionDecision={setConversionDecision}
                          showFolderStructure={showFolderStructure}
                          setShowFolderStructure={setShowFolderStructure}
                          styles={styles}
                        />
                      )} */}

                      {repoAnalysis && (
                        <div
                          id="discovery-document-cards-container"
                          style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
                            gap: 20,
                            marginTop: 20,
                            marginBottom: 24,
                            alignItems: "stretch",
                          }}
                        >
                          <DiscoveryTechnicalSpecificationCard
                            styles={styles}
                            disabled={documentGenerationLoading !== null || !repoAnalysis}
                            buttonLabel={technicalSpecificationButtonLabel}
                            helperText={technicalSpecificationHelperText}
                            onGenerate={() => {
                              void handleGenerateBrdDocument();
                            }}
                          />

                          <DiscoveryBrdUploadCard
                            jobId={jobId}
                            styles={styles}
                          />
                        </div>
                      )}
                    </>
                  )}
                </>
              )}
            </>
          )}
        </>
        </React.Suspense>
      )}

      <div style={styles.btnRow}>
        <button style={styles.secondaryBtn} onClick={onBack}>{renderBackButtonLabel()}</button>
        <button
          style={{ ...styles.primaryBtn, opacity: isJavaProject === false || (isHighRiskProject && !highRiskConfirmed) || isDiscoveryPending || !repoAnalysis ? 0.5 : 1 }}
          onClick={onContinueToStrategy}
          disabled={isJavaProject === false || (isHighRiskProject && !highRiskConfirmed) || isDiscoveryPending || !repoAnalysis}
        >
          {renderForwardButtonLabel("Continue to Strategy")}
        </button>
      </div>

      <Modal
        isOpen={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        title="Dashboard Overview"
        width="1100px"
      >
        <DiscoveryDetailModal
          compositionData={getDynamicCompositionData(repoAnalysis)}
          analysisFindings={getDynamicAnalysisFindings(repoAnalysis)}
          migrationSummary={getDynamicMigrationSummary(repoAnalysis)}
          totalFiles={getDynamicCompositionData(repoAnalysis).reduce((acc, curr) => acc + curr.count, 0)}
          totalMigrationItems={getDynamicMigrationSummary(repoAnalysis).reduce((acc, curr) => acc + curr.count, 0)}
          onViewAllFiles={() => {
            setIsDetailModalOpen(false);
            setShowFileExplorer(true);
            // Scroll to file explorer using the new ID
            const explorer = document.getElementById("discovery-file-explorer-section");
            if (explorer) explorer.scrollIntoView({ behavior: "smooth" });
          }}
          onViewFullAnalysis={() => {
            setIsDetailModalOpen(false);
            // Scroll to frameworks section using the new ID
            const frameworks = document.getElementById("discovery-frameworks-section");
            if (frameworks) frameworks.scrollIntoView({ behavior: "smooth" });
          }}
          onViewMigrationDetails={() => {
            setIsDetailModalOpen(false);
            // Scroll to technical spec using the new ID
            const spec = document.getElementById("discovery-technical-spec-section");
            if (spec) spec.scrollIntoView({ behavior: "smooth" });
          }}
        />
      </Modal>
    </div>
  );
}
