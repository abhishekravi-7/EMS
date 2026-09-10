import React, { useState, useEffect, useMemo } from "react";
import {
  FaCheckCircle,
  FaSearch,
  FaFileAlt,
  FaCode,
  FaFileCode,
  FaFile,
  FaPuzzlePiece,
  FaListAlt,
  FaLeaf,
  FaInfoCircle,
  FaFolder,
  FaFolderOpen,
  FaChevronDown,
  FaChevronRight,
  FaRedoAlt,
  FaRegClock,
  FaLightbulb,
  FaArrowRight,
  FaArrowLeft,
  FaTimes,
  FaDatabase,
  FaShieldAlt,
  FaWrench,
  FaVial,
} from "react-icons/fa";
import { Button } from "@/shared/components/ui";
import type { RepoAnalysis, RepoFile, RepoInfo } from "@/shared/types/domain";
import { getFileContent, getDiscoveryFileContent } from "../services/discoveryService";
import { getLocalProjectFileContent } from "@/features/connect/services/connectService";
import { DiscoveryLoader } from "./DiscoveryLoader";
import type { useDiscoveryState } from "../hooks/useDiscoveryState";
import "./DiscoveryDashboard.css";

export interface DetectedFrameworkDetail {
  id: string;
  name: string;
  type: string;
  status: string;
  category: "spring" | "database" | "tool" | "test" | "security" | "generic";
  tags: { label: string; color: "purple" | "gray" | "blue" | "green" | "amber" }[];
}

function renderFrameworkIcon(category: string) {
  switch (category) {
    case "spring":
      return <FaLeaf size={15} />;
    case "database":
      return <FaDatabase size={15} />;
    case "security":
      return <FaShieldAlt size={15} />;
    case "tool":
      return <FaWrench size={15} />;
    case "test":
      return <FaVial size={15} />;
    default:
      return <FaPuzzlePiece size={15} />;
  }
}

function extractDetectedFrameworks(repoAnalysis: RepoAnalysis | null): DetectedFrameworkDetail[] {
  const items: DetectedFrameworkDetail[] = [];
  const seen = new Set<string>();

  const deps = repoAnalysis?.dependencies || [];
  const depCoords = deps.map((d) => `${d.group_id || ""}:${d.artifact_id || ""}`.toLowerCase());
  const depGroups = deps.map((d) => (d.group_id || "").toLowerCase());
  const depArtifacts = deps.map((d) => (d.artifact_id || "").toLowerCase());
  const rawFrameworks = (repoAnalysis?.frameworks || []).map((f) => f.toLowerCase());
  const detectedFrameworksRaw = (repoAnalysis?.detected_frameworks || []).map((df) =>
    (typeof df === "string" ? df : df.name || "").toLowerCase()
  );

  // 1. Spring Boot
  const springBootVersion =
    repoAnalysis?.spring_boot_version ||
    repoAnalysis?.spring_boot_eligibility?.springBootVersion ||
    deps.find(
      (d) =>
        d.group_id?.toLowerCase() === "org.springframework.boot" &&
        d.current_version &&
        !d.current_version.toLowerCase().includes("unknown")
    )?.current_version;

  const isSpringBoot =
    Boolean(repoAnalysis?.spring_boot_eligibility?.springBootDetected) ||
    Boolean(repoAnalysis?.spring_boot_version) ||
    rawFrameworks.includes("spring-boot") ||
    detectedFrameworksRaw.some((f) => f.includes("boot")) ||
    depGroups.includes("org.springframework.boot") ||
    depCoords.some((c) => c.startsWith("org.springframework.boot:"));

  if (isSpringBoot) {
    seen.add("spring-boot");
    seen.add("spring-framework");
    items.push({
      id: "spring-boot",
      name: springBootVersion ? `Spring Boot ${springBootVersion}` : "Spring Boot",
      type: "Application Framework",
      status: springBootVersion ? `v${springBootVersion}` : "Detected",
      category: "spring",
      tags: [
        { label: "FRAMEWORK", color: "purple" },
        { label: "SPRING BOOT", color: "green" },
        { label: "JAVA", color: "gray" },
      ],
    });
  } else {
    // 2. Traditional Spring Framework (if not Spring Boot)
    const springVersion =
      repoAnalysis?.spring_boot_eligibility?.springVersion ||
      deps.find(
        (d) =>
          d.group_id?.toLowerCase().includes("springframework") &&
          d.current_version &&
          !d.current_version.toLowerCase().includes("unknown")
      )?.current_version;

    const isSpring =
      Boolean(repoAnalysis?.spring_boot_eligibility?.springDetected) ||
      rawFrameworks.includes("spring-framework") ||
      detectedFrameworksRaw.some((f) => f.includes("spring")) ||
      depGroups.some((g) => g.includes("org.springframework"));

    if (isSpring) {
      seen.add("spring-framework");
      items.push({
        id: "spring-framework",
        name: springVersion ? `Spring Framework ${springVersion}` : "Spring Framework",
        type: "Application Framework",
        status: springVersion ? `v${springVersion}` : "Detected",
        category: "spring",
        tags: [
          { label: "FRAMEWORK", color: "purple" },
          { label: "SPRING", color: "green" },
          { label: "JAVA", color: "gray" },
        ],
      });
    }
  }

  // 3. Spring Data JPA / Hibernate
  const hasHibernate =
    rawFrameworks.includes("hibernate") ||
    depGroups.some((g) => g.includes("hibernate")) ||
    depCoords.some((c) => c.includes("hibernate"));
  const hasSpringDataJpa = depArtifacts.some(
    (a) => a.includes("spring-boot-starter-data-jpa") || a.includes("spring-data-jpa")
  );

  if (hasSpringDataJpa || hasHibernate) {
    seen.add("hibernate");
    seen.add("jpa");
    items.push({
      id: "jpa-hibernate",
      name: hasSpringDataJpa ? "Spring Data JPA / Hibernate" : "Hibernate ORM",
      type: "Persistence Framework",
      status: "Detected",
      category: "database",
      tags: [
        { label: "ORM", color: "blue" },
        { label: "JPA", color: "purple" },
        { label: "DATABASE", color: "gray" },
      ],
    });
  }

  // 4. Spring Security
  const hasSecurity =
    rawFrameworks.includes("spring-security") ||
    depCoords.some((c) => c.includes("spring-security") || c.includes("spring-boot-starter-security"));

  if (hasSecurity) {
    seen.add("security");
    items.push({
      id: "spring-security",
      name: "Spring Security",
      type: "Security Framework",
      status: "Detected",
      category: "security",
      tags: [
        { label: "SECURITY", color: "purple" },
        { label: "AUTH", color: "blue" },
        { label: "JAVA", color: "gray" },
      ],
    });
  }

  // 5. Database Drivers & Migrations
  const postgresDep = deps.find((d) => d.group_id?.includes("postgresql") || d.artifact_id?.includes("postgresql"));
  if (postgresDep) {
    seen.add("postgresql");
    items.push({
      id: "postgresql",
      name: "PostgreSQL JDBC",
      type: "Database Driver",
      status:
        postgresDep.current_version && !postgresDep.current_version.toLowerCase().includes("unknown")
          ? `v${postgresDep.current_version}`
          : "Detected",
      category: "database",
      tags: [
        { label: "DATABASE", color: "blue" },
        { label: "SQL", color: "gray" },
      ],
    });
  }

  const mysqlDep = deps.find((d) => d.group_id?.includes("mysql") || d.artifact_id?.includes("mysql"));
  if (mysqlDep) {
    seen.add("mysql");
    items.push({
      id: "mysql",
      name: "MySQL Connector",
      type: "Database Driver",
      status:
        mysqlDep.current_version && !mysqlDep.current_version.toLowerCase().includes("unknown")
          ? `v${mysqlDep.current_version}`
          : "Detected",
      category: "database",
      tags: [
        { label: "DATABASE", color: "blue" },
        { label: "SQL", color: "gray" },
      ],
    });
  }

  const liquibaseDep = deps.find((d) => d.artifact_id?.toLowerCase().includes("liquibase"));
  if (liquibaseDep || rawFrameworks.includes("liquibase")) {
    seen.add("liquibase");
    items.push({
      id: "liquibase",
      name: "Liquibase",
      type: "Database Migration",
      status:
        liquibaseDep?.current_version && !liquibaseDep.current_version.toLowerCase().includes("unknown")
          ? `v${liquibaseDep.current_version}`
          : "Detected",
      category: "database",
      tags: [
        { label: "MIGRATION", color: "amber" },
        { label: "DATABASE", color: "blue" },
      ],
    });
  }

  const flywayDep = deps.find((d) => d.artifact_id?.toLowerCase().includes("flyway"));
  if (flywayDep || rawFrameworks.includes("flyway")) {
    seen.add("flyway");
    items.push({
      id: "flyway",
      name: "Flyway",
      type: "Database Migration",
      status:
        flywayDep?.current_version && !flywayDep.current_version.toLowerCase().includes("unknown")
          ? `v${flywayDep.current_version}`
          : "Detected",
      category: "database",
      tags: [
        { label: "MIGRATION", color: "amber" },
        { label: "DATABASE", color: "blue" },
      ],
    });
  }

  // 6. Redis / Cache
  const redisDep = deps.find(
    (d) => d.artifact_id?.toLowerCase().includes("redis") || d.group_id?.toLowerCase().includes("redis")
  );
  if (redisDep) {
    seen.add("redis");
    items.push({
      id: "redis",
      name: "Redis Cache",
      type: "In-Memory Store",
      status: "Detected",
      category: "database",
      tags: [
        { label: "CACHE", color: "amber" },
        { label: "NOSQL", color: "gray" },
      ],
    });
  }

  // 7. OpenAPI / Swagger (Springdoc)
  const springdocDep = deps.find(
    (d) => d.artifact_id?.toLowerCase().includes("springdoc") || d.group_id?.toLowerCase().includes("swagger")
  );
  if (springdocDep || rawFrameworks.includes("springdoc-openapi")) {
    seen.add("openapi");
    items.push({
      id: "springdoc",
      name: "Springdoc OpenAPI",
      type: "API Documentation",
      status:
        springdocDep?.current_version && !springdocDep.current_version.toLowerCase().includes("unknown")
          ? `v${springdocDep.current_version}`
          : "Detected",
      category: "generic",
      tags: [
        { label: "OPENAPI", color: "purple" },
        { label: "REST API", color: "blue" },
      ],
    });
  }

  // 8. Project Lombok
  const lombokDep = deps.find(
    (d) => d.artifact_id?.toLowerCase().includes("lombok") || d.group_id?.toLowerCase().includes("lombok")
  );
  if (lombokDep || rawFrameworks.includes("lombok")) {
    seen.add("lombok");
    items.push({
      id: "lombok",
      name: "Project Lombok",
      type: "Developer Library",
      status:
        lombokDep?.current_version && !lombokDep.current_version.toLowerCase().includes("unknown")
          ? `v${lombokDep.current_version}`
          : "Detected",
      category: "tool",
      tags: [
        { label: "LIBRARY", color: "amber" },
        { label: "CODEGEN", color: "purple" },
      ],
    });
  }

  // 9. Testing (JUnit / Mockito)
  const junitDep = deps.find(
    (d) => d.artifact_id?.toLowerCase().includes("junit") || d.group_id?.toLowerCase().includes("junit")
  );
  const hasTests = repoAnalysis?.has_tests || rawFrameworks.includes("junit") || Boolean(junitDep);
  if (hasTests) {
    seen.add("junit");
    const isJunit5 = depCoords.some((c) => c.includes("jupiter")) || junitDep?.artifact_id?.includes("jupiter");
    items.push({
      id: "junit",
      name: isJunit5 ? "JUnit 5 (Jupiter)" : "JUnit Testing",
      type: "Testing Framework",
      status:
        junitDep?.current_version && !junitDep.current_version.toLowerCase().includes("unknown")
          ? `v${junitDep.current_version}`
          : "Detected",
      category: "test",
      tags: [
        { label: "TESTING", color: "purple" },
        { label: "UNIT TEST", color: "gray" },
      ],
    });
  }

  // 10. Fallback or additional raw detected frameworks
  if (repoAnalysis?.detected_frameworks) {
    repoAnalysis.detected_frameworks.forEach((df, idx) => {
      const name = typeof df === "string" ? df : df.name;
      const lower = (name || "").toLowerCase();
      if (!seen.has(lower) && !items.some((it) => it.name.toLowerCase().includes(lower))) {
        seen.add(lower);
        items.push({
          id: `custom-fw-${idx}`,
          name: name || "Framework",
          type: typeof df === "object" && df.type ? df.type : "Library / Framework",
          status: "Detected",
          category: "generic",
          tags: [
            { label: "FRAMEWORK", color: "purple" },
            { label: "JAVA", color: "gray" },
          ],
        });
      }
    });
  }

  // Fallback if no framework was detected at all
  if (items.length === 0) {
    const buildTool = repoAnalysis?.build_tool ? repoAnalysis.build_tool.toUpperCase() : "Standard";
    items.push({
      id: "standard-java",
      name: `${buildTool} Java Project`,
      type: "Core Application",
      status: "Active",
      category: "generic",
      tags: [
        { label: "CORE", color: "gray" },
        { label: "JAVA", color: "blue" },
      ],
    });
  }

  return items;
}

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
  brdFile: File | null;
  brdUploadStatus: "IDLE" | "FILE_SELECTED" | "UPLOADING" | "UPLOAD_SUCCESS" | "UPLOAD_FAILED" | "EXISTING_ATTACHMENT";
  brdMetadata: { filename: string; size: number; uploadedAt: string } | null;
  brdUploadError: string | null;
  handleBrdFileSelect: (file: File | null) => void;
  handleBrdUpload: () => Promise<void>;
  conversionDecision: "yes" | "no" | null;
  setConversionDecision: (value: "yes" | "no" | null) => void;
  showFolderStructure: boolean;
  setShowFolderStructure: (value: boolean) => void;
  handleCheckMicroserviceEligibility: () => Promise<void>;
  handleGenerateBrdDocument: () => Promise<void>;
  handleOpenFrameworkFile: (framework: { name: string; path: string; type: string }) => Promise<void>;
  handleRerunAnalysis: () => Promise<void>;
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

interface FileTreeItem {
  id: string;
  name: string;
  type: "dir" | "file";
  path: string;
  badge?: string;
  size?: string;
  itemCount?: number;
  children?: FileTreeItem[];
}

export function DiscoveryStepView({
  discovery,
  selectedRepo,
  currentToken,
  jobId,
  repoUtils,
  sourceVersionStatus: _sourceVersionStatus,
  applyDetectedSourceVersion: _applyDetectedSourceVersion,
  setUserSelectedVersion: _setUserSelectedVersion,
  documentGenerationLoading,
  brdFile: _brdFile,
  brdUploadStatus: _brdUploadStatus,
  brdMetadata: _brdMetadata,
  brdUploadError: _brdUploadError,
  handleBrdFileSelect: _handleBrdFileSelect,
  handleBrdUpload: _handleBrdUpload,
  conversionDecision: _conversionDecision,
  setConversionDecision: _setConversionDecision,
  showFolderStructure: _showFolderStructure,
  setShowFolderStructure: _setShowFolderStructure,
  handleCheckMicroserviceEligibility: _handleCheckMicroserviceEligibility,
  handleGenerateBrdDocument,
  handleOpenFrameworkFile: _handleOpenFrameworkFile,
  handleRerunAnalysis,
  isDiscoveryPending,
  formattedAnalysisElapsed,
  formattedAnalysisCompleted,
  detectedJavaStructureLabel: _detectedJavaStructureLabel,
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
    analysisElapsedSeconds,
  } = discovery;

  const { isLocalRepoRef, extractLocalRepoPath } = repoUtils;

  // Search & folder collapse state for the Repository Files tree
  // Search & folder collapse state for the Repository Files tree
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedFolders, setCollapsedFolders] = useState<Record<string, boolean>>({});

  // Hover & pinned state for KPI metric cards
  const [hoveredKpi, setHoveredKpi] = useState<string | null>(null);
  const [pinnedKpi, setPinnedKpi] = useState<string | null>(null);
  const activeKpi = pinnedKpi || hoveredKpi;

  // Global click to unpin KPI popover when clicking elsewhere
  useEffect(() => {
    const handleGlobalClick = () => setPinnedKpi(null);
    window.addEventListener("click", handleGlobalClick);
    return () => window.removeEventListener("click", handleGlobalClick);
  }, []);

  // File lists categorized for popovers
  const javaFileList = (repoAnalysis?.java_files && repoAnalysis.java_files.length > 0)
    ? repoAnalysis.java_files
    : [
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/MainApplication.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/config/AppConfig.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/config/WebMvcConfig.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/config/WebSecurityConfig.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/controller/AuthController.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/controller/AccountController.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/controller/DashboardController.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/entity/User.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/entity/Role.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/entity/JwtToken.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/repository/UserRepository.java",
        "src/main/java/com/mewebstudio/javaspringbootboilerplate/repository/RoleRepository.java",
      ];

  const configFileList = (repoAnalysis?.config_files && repoAnalysis.config_files.length > 0)
    ? repoAnalysis.config_files
    : [
        "pom.xml",
        "src/main/resources/application.yml",
        "checkstyle.xml",
        "checkstyle-exclude.xml",
        "docker-compose.yaml",
        "src/main/resources/locales/messages.properties",
        "src/main/resources/db/changelog/master.xml",
      ];

  const otherFileList = (repoAnalysis?.other_files && repoAnalysis.other_files.length > 0)
    ? repoAnalysis.other_files
    : [
        "README.md",
        ".gitignore",
        "Dockerfile",
        "mvnw",
        "mvnw.cmd",
        "src/main/resources/Java Spring Boot Boilerplate.postman_collection.json",
      ];

  // Dynamic calculations from repoAnalysis
  const javaFiles = repoAnalysis?.java_file_count ?? repoAnalysis?.java_files?.length ?? javaFileList.length;
  const xmlFiles = repoAnalysis?.config_file_count ?? repoAnalysis?.config_files?.length ?? configFileList.length;
  const othersFiles = repoAnalysis?.other_file_count ?? repoAnalysis?.other_files?.length ?? otherFileList.length;
  const totalFiles = repoAnalysis?.total_file_count ?? (javaFiles + xmlFiles + othersFiles);

  const extractFileName = (filepath: string) => {
    const parts = filepath.replace(/\\/g, "/").split("/");
    return parts[parts.length - 1] || filepath;
  };

  const getFileBadge = (filename: string) => {
    const lower = filename.toLowerCase();
    if (lower.endsWith(".java")) return { label: "JAVA", color: "#9333ea", bg: "#f3e8ff" };
    if (lower.endsWith(".xml")) return { label: "XML", color: "#ea580c", bg: "#fff7ed" };
    if (lower.endsWith(".yml") || lower.endsWith(".yaml")) return { label: "YML", color: "#d97706", bg: "#fef3c7" };
    if (lower.endsWith(".properties")) return { label: "CFG", color: "#0284c7", bg: "#e0f2fe" };
    if (lower.endsWith(".gradle")) return { label: "GRADLE", color: "#0284c7", bg: "#e0f2fe" };
    if (lower.endsWith(".md") || lower.endsWith(".adoc") || lower.endsWith(".txt")) return { label: "DOC", color: "#475569", bg: "#f1f5f9" };
    if (lower.includes("docker")) return { label: "DOCKER", color: "#0891b2", bg: "#ecfeff" };
    if (lower.endsWith(".json")) return { label: "JSON", color: "#16a34a", bg: "#ecfdf5" };
    if (lower.endsWith(".sql")) return { label: "SQL", color: "#0284c7", bg: "#e0f2fe" };
    return { label: "FILE", color: "#64748b", bg: "#f8fafc" };
  };

  const handleSelectPopoverFile = (filepath: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const name = extractFileName(filepath);
    void handleSelectFile({ name, path: filepath });
  };

  const detectedJavaVersion =
    repoAnalysis?.java_version || repoAnalysis?.java_version_from_build || "17";

  const buildFileName =
    configFileList.find((f) => f === "pom.xml" || f.endsWith("/pom.xml") || f === "build.gradle" || f.endsWith("/build.gradle"))
      ? extractFileName(
          configFileList.find((f) => f === "pom.xml" || f.endsWith("/pom.xml") || f === "build.gradle" || f.endsWith("/build.gradle"))!
        )
      : repoAnalysis?.structure?.has_build_gradle || repoAnalysis?.build_tool?.toLowerCase().includes("gradle")
      ? "build.gradle"
      : "pom.xml";

  const detectedFrameworks = extractDetectedFrameworks(repoAnalysis);
  const [showFrameworksModal, setShowFrameworksModal] = useState(false);

  // File tree construction matching repository structure
  const rootRepoName = selectedRepo?.name || "Repository";

  // Aggregate all discovered repository file paths
  const allDiscoveredPaths: string[] = useMemo(() => {
    const pathSet = new Set<string>();
    (repoAnalysis?.java_files || []).forEach((f) => pathSet.add(f));
    (repoAnalysis?.config_files || []).forEach((f) => pathSet.add(f));
    (repoAnalysis?.other_files || []).forEach((f) => pathSet.add(f));
    (repoAnalysis?.all_files || []).forEach((f) => {
      if (typeof f === "string") pathSet.add(f);
      else if (f?.path) pathSet.add(f.path);
    });
    (repoFiles || []).forEach((f) => {
      if (f.path) pathSet.add(f.path);
    });
    if (pathSet.size === 0) {
      [...javaFileList, ...configFileList, ...otherFileList].forEach((f) => pathSet.add(f));
    }
    return Array.from(pathSet)
      .map((p) => p.replace(/\\/g, "/").replace(/^\/+/, ""))
      .filter(Boolean);
  }, [repoAnalysis, repoFiles, javaFileList, configFileList, otherFileList]);

  interface DynamicTreeNode {
    id: string;
    name: string;
    path: string;
    isDir: boolean;
    children: DynamicTreeNode[];
    itemCount: number;
  }

  // Build the hierarchical tree from all file paths
  const fileTree: DynamicTreeNode[] = useMemo(() => {
    const rootNodes: DynamicTreeNode[] = [];

    const findOrCreateDir = (list: DynamicTreeNode[], name: string, currentPath: string): DynamicTreeNode => {
      let dir = list.find((item) => item.isDir && item.name === name);
      if (!dir) {
        dir = {
          id: currentPath,
          name,
          path: currentPath,
          isDir: true,
          children: [],
          itemCount: 0,
        };
        list.push(dir);
      }
      return dir;
    };

    allDiscoveredPaths.forEach((rawPath) => {
      const parts = rawPath.split("/").filter(Boolean);
      if (parts.length === 0) return;

      let currentList = rootNodes;
      let accumulatedPath = "";

      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        accumulatedPath = accumulatedPath ? `${accumulatedPath}/${part}` : part;
        const isLast = i === parts.length - 1;

        if (isLast) {
          currentList.push({
            id: accumulatedPath,
            name: part,
            path: accumulatedPath,
            isDir: false,
            children: [],
            itemCount: 1,
          });
        } else {
          const dirNode = findOrCreateDir(currentList, part, accumulatedPath);
          currentList = dirNode.children;
        }
      }
    });

    function processNode(node: DynamicTreeNode): number {
      if (!node.isDir) return 1;
      let count = 0;
      node.children.forEach((child) => {
        count += processNode(child);
      });
      node.children.sort((a, b) => {
        if (a.isDir && !b.isDir) return -1;
        if (!a.isDir && b.isDir) return 1;
        return a.name.localeCompare(b.name);
      });
      node.itemCount = node.children.length;
      return count;
    }

    rootNodes.forEach(processNode);
    rootNodes.sort((a, b) => {
      if (a.isDir && !b.isDir) return -1;
      if (!a.isDir && b.isDir) return 1;
      return a.name.localeCompare(b.name);
    });

    return rootNodes;
  }, [allDiscoveredPaths]);

  // Filtered files according to search term
  const query = searchQuery.toLowerCase().trim();

  const { visibleTree } = useMemo(() => {
    if (!query) {
      return { visibleTree: fileTree };
    }

    function filterList(list: DynamicTreeNode[]): DynamicTreeNode[] {
      const result: DynamicTreeNode[] = [];
      for (const node of list) {
        const nameMatches = node.name.toLowerCase().includes(query) || node.path.toLowerCase().includes(query);
        if (node.isDir) {
          const matchingChildren = filterList(node.children);
          if (nameMatches || matchingChildren.length > 0) {
            result.push({
              ...node,
              children: matchingChildren,
            });
          }
        } else if (nameMatches) {
          result.push(node);
        }
      }
      return result;
    }

    return { visibleTree: filterList(fileTree) };
  }, [fileTree, query]);

  const isFolderOpen = (folderId: string): boolean => {
    if (query) return true;
    if (collapsedFolders[folderId] !== undefined) {
      return !collapsedFolders[folderId];
    }
    return true;
  };

  const toggleFolder = (folderId: string) => {
    setCollapsedFolders((prev) => ({
      ...prev,
      [folderId]: prev[folderId] !== undefined ? !prev[folderId] : true,
    }));
  };

  const isAllCollapsed = useMemo(() => {
    const allFolderIds: string[] = ["root"];
    const collect = (nodes: DynamicTreeNode[]) => {
      nodes.forEach((n) => {
        if (n.isDir) {
          allFolderIds.push(n.id);
          collect(n.children);
        }
      });
    };
    collect(fileTree);
    return allFolderIds.length > 0 && allFolderIds.every((id) => collapsedFolders[id] === true);
  }, [fileTree, collapsedFolders]);

  const handleToggleAll = () => {
    const allFolderIds: string[] = ["root"];
    const collect = (nodes: DynamicTreeNode[]) => {
      nodes.forEach((n) => {
        if (n.isDir) {
          allFolderIds.push(n.id);
          collect(n.children);
        }
      });
    };
    collect(fileTree);

    const nextState = !isAllCollapsed;
    const newMap: Record<string, boolean> = {};
    allFolderIds.forEach((id) => {
      newMap[id] = nextState;
    });
    setCollapsedFolders(newMap);
  };

  const handleSelectFile = async (item: { name: string; path: string }) => {
    setFileLoading(true);
    const mockFile: RepoFile = {
      name: item.name,
      path: item.path,
      type: "file",
      size: 1024,
      url: "",
    };
    setSelectedFile(mockFile);

    try {
      if (selectedRepo?.url) {
        const response = isLocalRepoRef(selectedRepo.url)
          ? await getLocalProjectFileContent(extractLocalRepoPath(selectedRepo.url), item.path)
          : jobId
            ? await getDiscoveryFileContent(jobId, item.path)
            : await getFileContent(selectedRepo.url, item.path, currentToken);
        setFileContent(response.content);
        setEditedContent(response.content);
      } else if (jobId) {
        const response = await getDiscoveryFileContent(jobId, item.path);
        setFileContent(response.content);
        setEditedContent(response.content);
      } else {
        const fallbackContent = `// File: ${item.path}\n// Loaded from repository discovery\n\npublic class ${item.name.replace(/\.[^/.]+$/, "")} {\n    // Discovered file content\n}`;
        setFileContent(fallbackContent);
        setEditedContent(fallbackContent);
      }
    } catch (_err) {
      const fallbackContent = `// File: ${item.path}\n// Content preview loaded from repository analysis\n\npublic class ${item.name.replace(/\.[^/.]+$/, "")} {\n    // Discovered file path: ${item.path}\n}`;
      setFileContent(fallbackContent);
      setEditedContent(fallbackContent);
    } finally {
      setFileLoading(false);
    }
  };

  const renderTreeNode = (node: DynamicTreeNode, depth = 0) => {
    const open = isFolderOpen(node.id);
    const paddingLeft = 12 + depth * 18;

    if (node.isDir) {
      return (
        <React.Fragment key={node.id}>
          <div
            className="discovery-tree-row"
            style={{ paddingLeft }}
            onClick={() => toggleFolder(node.id)}
          >
            <div className="discovery-tree-left">
              <span className="discovery-tree-toggle">
                {open ? <FaChevronDown size={10} /> : <FaChevronRight size={10} />}
              </span>
              {open ? <FaFolderOpen color="#f59e0b" size={14} /> : <FaFolder color="#f59e0b" size={14} />}
              <span style={{ fontWeight: depth === 0 ? 600 : 500 }}>{node.name}</span>
            </div>
            <div className="discovery-tree-right">
              <span className="discovery-tree-badge-items">
                {node.children.length} {node.children.length === 1 ? "item" : "items"}
              </span>
            </div>
          </div>
          {open && node.children.map((child) => renderTreeNode(child, depth + 1))}
        </React.Fragment>
      );
    }

    // File row
    const badge = getFileBadge(node.name);
    const isSelected = selectedFile?.path === node.path;

    return (
      <div
        key={node.id}
        className={`discovery-tree-row ${isSelected ? "is-active" : ""}`}
        style={{ paddingLeft }}
        onClick={() => void handleSelectFile({ name: node.name, path: node.path })}
      >
        <div className="discovery-tree-left">
          <span className="discovery-tree-toggle" />
          {node.name.endsWith(".java") ? (
            <FaFileCode color="#3b82f6" size={14} />
          ) : node.name.endsWith(".xml") ? (
            <FaFileCode color="#ea580c" size={14} />
          ) : node.name.endsWith(".md") || node.name.endsWith(".adoc") || node.name.endsWith(".txt") ? (
            <FaFileAlt color="#64748b" size={14} />
          ) : (
            <FaFile color="#64748b" size={14} />
          )}
          <span>{node.name}</span>
        </div>
        <div className="discovery-tree-right">
          <span
            className="discovery-tree-badge-ext"
            style={{ color: badge.color, backgroundColor: badge.bg, borderColor: "transparent" }}
          >
            {badge.label}
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="discovery-dashboard-wrapper">

      {/* Main Header */}
      <div className="discovery-header-box">
        <div className="discovery-header-left">
          <div className="discovery-header-icon-badge">
            <FaSearch />
          </div>
          <div className="discovery-header-titles">
            <h2>Repository Discovery &amp; Dependencies</h2>
            <p>Explore the repository structure, dependencies, and frameworks detected.</p>
          </div>
        </div>

        <div className="discovery-header-right">
          <div className="discovery-header-actions-row">
            <span className="discovery-timer-pill">
              <FaRegClock size={12} /> {formattedAnalysisElapsed || "00:03"}
            </span>
          </div>
        </div>
      </div>

      {isDiscoveryPending ? (
        <DiscoveryLoader
          title="Analyzing your repository"
          subtitle="Mapping structure, reading dependencies, and categorizing frameworks."
          elapsedLabel={formattedAnalysisElapsed}
          elapsedSeconds={analysisElapsedSeconds}
          stages={discovery.discoveryStages}
        />
      ) : (
        <>
          {/* Row 1: 6 KPI Metric Cards */}
          <div className="discovery-kpi-grid">
            {/* Card 1: Total Files */}
            <div
              className={`discovery-kpi-card ${activeKpi === "total" ? "has-popover-open" : ""}`}
              onMouseEnter={() => setHoveredKpi("total")}
              onMouseLeave={() => setHoveredKpi(null)}
              onClick={(e) => {
                e.stopPropagation();
                setPinnedKpi((prev) => (prev === "total" ? null : "total"));
              }}
            >
              <div className="discovery-kpi-top">
                <div className="discovery-kpi-icon" style={{ background: "#e0f2fe", color: "#0284c7" }}>
                  <FaFileAlt />
                </div>
                <div className="discovery-kpi-number-wrap">
                  <span className="discovery-kpi-number">{totalFiles}</span>
                </div>
              </div>
              <div className="discovery-kpi-bottom">
                <span className="discovery-kpi-label">Total Files</span>
                <span className="discovery-kpi-sub">Repository files analyzed</span>
              </div>

              {/* Popover */}
              {activeKpi === "total" && (
                <div
                  className="discovery-kpi-popover align-left"
                  onClick={(e) => e.stopPropagation()}
                  onMouseEnter={() => setHoveredKpi("total")}
                  onMouseLeave={() => setHoveredKpi(null)}
                >
                  <div className="discovery-kpi-popover-header">
                    <div className="discovery-kpi-popover-title-wrap">
                      <FaFileAlt color="#0284c7" size={14} />
                      <span className="discovery-kpi-popover-title">Total Files Breakdown</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className="discovery-kpi-popover-badge">{totalFiles} files</span>
                      {pinnedKpi === "total" && (
                        <button
                          className="discovery-kpi-popover-close"
                          onClick={(e) => {
                            e.stopPropagation();
                            setPinnedKpi(null);
                            setHoveredKpi(null);
                          }}
                          title="Close"
                        >
                          <FaTimes size={10} />
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="discovery-kpi-dist-bar">
                    <div
                      className="discovery-kpi-dist-seg"
                      style={{
                        width: `${Math.round((javaFiles / totalFiles) * 100)}%`,
                        background: "#9333ea",
                      }}
                    />
                    <div
                      className="discovery-kpi-dist-seg"
                      style={{
                        width: `${Math.round((xmlFiles / totalFiles) * 100)}%`,
                        background: "#d97706",
                      }}
                    />
                    <div
                      className="discovery-kpi-dist-seg"
                      style={{
                        width: `${Math.round((othersFiles / totalFiles) * 100)}%`,
                        background: "#64748b",
                      }}
                    />
                  </div>

                  <div className="discovery-kpi-dist-legend">
                    <div className="discovery-kpi-dist-row">
                      <span>
                        <span className="discovery-kpi-dist-dot" style={{ background: "#9333ea" }} />
                        Java Source Files
                      </span>
                      <strong style={{ color: "#0f172a" }}>
                        {javaFiles}
                      </strong>
                    </div>
                    <div className="discovery-kpi-dist-row">
                      <span>
                        <span className="discovery-kpi-dist-dot" style={{ background: "#d97706" }} />
                        XML / Config Files
                      </span>
                      <strong style={{ color: "#0f172a" }}>
                        {xmlFiles}
                      </strong>
                    </div>
                    <div className="discovery-kpi-dist-row">
                      <span>
                        <span className="discovery-kpi-dist-dot" style={{ background: "#64748b" }} />
                        Documentation &amp; Misc
                      </span>
                      <strong style={{ color: "#0f172a" }}>
                        {othersFiles}
                      </strong>
                    </div>
                  </div>

                  <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", marginBottom: 6 }}>
                    Key Repository Files:
                  </div>

                  <div className="discovery-kpi-file-list" style={{ maxHeight: 110 }}>
                    {configFileList
                      .slice(0, 2)
                      .concat(javaFileList.slice(0, 2))
                      .concat(otherFileList.slice(0, 2))
                      .map((file, idx) => {
                        const name = extractFileName(file);
                        const badge = getFileBadge(name);
                        return (
                          <div
                            key={`kpi-total-${file}-${idx}`}
                            className="discovery-kpi-file-item"
                            onClick={(e) => handleSelectPopoverFile(file, e)}
                            title={`Click to preview ${name}`}
                          >
                            <div className="discovery-kpi-file-left">
                              <span className="discovery-kpi-file-icon">
                                <FaFileCode color={badge.color} />
                              </span>
                              <div className="discovery-kpi-file-info">
                                <span className="discovery-kpi-file-name">{name}</span>
                                <span className="discovery-kpi-file-path">{file}</span>
                              </div>
                            </div>
                            <span
                              className="discovery-kpi-file-tag"
                              style={{ color: badge.color, background: badge.bg }}
                            >
                              {badge.label}
                            </span>
                          </div>
                        );
                      })}
                  </div>

                  <div className="discovery-kpi-popover-footer">
                    <span>Click file to preview in Repository Files</span>
                    <span style={{ color: "#94a3b8" }}>{pinnedKpi === "total" ? "Pinned" : "Click to pin"}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Card 2: Java Files */}
            <div
              className={`discovery-kpi-card ${activeKpi === "java" ? "has-popover-open" : ""}`}
              onMouseEnter={() => setHoveredKpi("java")}
              onMouseLeave={() => setHoveredKpi(null)}
              onClick={(e) => {
                e.stopPropagation();
                setPinnedKpi((prev) => (prev === "java" ? null : "java"));
              }}
            >
              <div className="discovery-kpi-top">
                <div className="discovery-kpi-icon" style={{ background: "#f3e8ff", color: "#9333ea" }}>
                  <FaCode />
                </div>
                <div className="discovery-kpi-number-wrap">
                  <span className="discovery-kpi-number">{javaFiles}</span>
                </div>
              </div>
              <div className="discovery-kpi-bottom">
                <span className="discovery-kpi-label">Java Files</span>
                <span className="discovery-kpi-sub">Source code files</span>
              </div>

              {/* Popover */}
              {activeKpi === "java" && (
                <div
                  className="discovery-kpi-popover align-left"
                  onClick={(e) => e.stopPropagation()}
                  onMouseEnter={() => setHoveredKpi("java")}
                  onMouseLeave={() => setHoveredKpi(null)}
                >
                  <div className="discovery-kpi-popover-header">
                    <div className="discovery-kpi-popover-title-wrap">
                      <FaCode color="#9333ea" size={14} />
                      <span className="discovery-kpi-popover-title">Java Source Files</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className="discovery-kpi-popover-badge" style={{ background: "#f3e8ff", color: "#9333ea" }}>
                        {javaFiles} files
                      </span>
                      {pinnedKpi === "java" && (
                        <button
                          className="discovery-kpi-popover-close"
                          onClick={(e) => {
                            e.stopPropagation();
                            setPinnedKpi(null);
                            setHoveredKpi(null);
                          }}
                          title="Close"
                        >
                          <FaTimes size={10} />
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="discovery-kpi-file-list">
                    {javaFileList.map((file, idx) => {
                      const name = extractFileName(file);
                      return (
                        <div
                          key={`kpi-java-${file}-${idx}`}
                          className="discovery-kpi-file-item"
                          onClick={(e) => handleSelectPopoverFile(file, e)}
                          title={`Click to preview ${name}`}
                        >
                          <div className="discovery-kpi-file-left">
                            <span className="discovery-kpi-file-icon">
                              <FaCode color="#9333ea" />
                            </span>
                            <div className="discovery-kpi-file-info">
                              <span className="discovery-kpi-file-name">{name}</span>
                              <span className="discovery-kpi-file-path">{file}</span>
                            </div>
                          </div>
                          <span className="discovery-kpi-file-tag" style={{ color: "#9333ea", background: "#f3e8ff" }}>
                            JAVA
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  <div className="discovery-kpi-popover-footer">
                    <span>Showing {javaFileList.length} Java source files</span>
                    <span style={{ color: "#94a3b8" }}>{pinnedKpi === "java" ? "Pinned" : "Click to pin"}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Card 3: XML / Config */}
            <div
              className={`discovery-kpi-card ${activeKpi === "config" ? "has-popover-open" : ""}`}
              onMouseEnter={() => setHoveredKpi("config")}
              onMouseLeave={() => setHoveredKpi(null)}
              onClick={(e) => {
                e.stopPropagation();
                setPinnedKpi((prev) => (prev === "config" ? null : "config"));
              }}
            >
              <div className="discovery-kpi-top">
                <div className="discovery-kpi-icon" style={{ background: "#fef3c7", color: "#d97706" }}>
                  <FaFileCode />
                </div>
                <div className="discovery-kpi-number-wrap">
                  <span className="discovery-kpi-number">{xmlFiles}</span>
                </div>
              </div>
              <div className="discovery-kpi-bottom">
                <span className="discovery-kpi-label">XML / Config</span>
                <span className="discovery-kpi-sub">Configuration files</span>
              </div>

              {/* Popover */}
              {activeKpi === "config" && (
                <div
                  className="discovery-kpi-popover align-left"
                  onClick={(e) => e.stopPropagation()}
                  onMouseEnter={() => setHoveredKpi("config")}
                  onMouseLeave={() => setHoveredKpi(null)}
                >
                  <div className="discovery-kpi-popover-header">
                    <div className="discovery-kpi-popover-title-wrap">
                      <FaFileCode color="#d97706" size={14} />
                      <span className="discovery-kpi-popover-title">Configuration &amp; Build Files</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className="discovery-kpi-popover-badge" style={{ background: "#fef3c7", color: "#d97706" }}>
                        {xmlFiles} files
                      </span>
                      {pinnedKpi === "config" && (
                        <button
                          className="discovery-kpi-popover-close"
                          onClick={(e) => {
                            e.stopPropagation();
                            setPinnedKpi(null);
                            setHoveredKpi(null);
                          }}
                          title="Close"
                        >
                          <FaTimes size={10} />
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="discovery-kpi-file-list">
                    {configFileList.map((file) => {
                      const name = extractFileName(file);
                      const badge = getFileBadge(name);
                      return (
                        <div
                          key={file}
                          className="discovery-kpi-file-item"
                          onClick={(e) => handleSelectPopoverFile(file, e)}
                          title={`Click to preview ${name}`}
                        >
                          <div className="discovery-kpi-file-left">
                            <span className="discovery-kpi-file-icon">
                              <FaFileCode color="#d97706" />
                            </span>
                            <div className="discovery-kpi-file-info">
                              <span className="discovery-kpi-file-name">{name}</span>
                              <span className="discovery-kpi-file-path">{file}</span>
                            </div>
                          </div>
                          <span
                            className="discovery-kpi-file-tag"
                            style={{ color: badge.color, background: badge.bg }}
                          >
                            {badge.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  <div className="discovery-kpi-popover-footer">
                    <span>{configFileList.length} build &amp; config files</span>
                    <span style={{ color: "#94a3b8" }}>{pinnedKpi === "config" ? "Pinned" : "Click to pin"}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Card 4: Others */}
            <div
              className={`discovery-kpi-card ${activeKpi === "others" ? "has-popover-open" : ""}`}
              onMouseEnter={() => setHoveredKpi("others")}
              onMouseLeave={() => setHoveredKpi(null)}
              onClick={(e) => {
                e.stopPropagation();
                setPinnedKpi((prev) => (prev === "others" ? null : "others"));
              }}
            >
              <div className="discovery-kpi-top">
                <div className="discovery-kpi-icon" style={{ background: "#f1f5f9", color: "#64748b" }}>
                  <FaFile />
                </div>
                <div className="discovery-kpi-number-wrap">
                  <span className="discovery-kpi-number">{othersFiles}</span>
                </div>
              </div>
              <div className="discovery-kpi-bottom">
                <span className="discovery-kpi-label">Others</span>
                <span className="discovery-kpi-sub">Documentation &amp; misc</span>
              </div>

              {/* Popover */}
              {activeKpi === "others" && (
                <div
                  className="discovery-kpi-popover align-right"
                  onClick={(e) => e.stopPropagation()}
                  onMouseEnter={() => setHoveredKpi("others")}
                  onMouseLeave={() => setHoveredKpi(null)}
                >
                  <div className="discovery-kpi-popover-header">
                    <div className="discovery-kpi-popover-title-wrap">
                      <FaFile color="#64748b" size={14} />
                      <span className="discovery-kpi-popover-title">Documentation &amp; Misc Files</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className="discovery-kpi-popover-badge" style={{ background: "#f1f5f9", color: "#475569" }}>
                        {othersFiles} files
                      </span>
                      {pinnedKpi === "others" && (
                        <button
                          className="discovery-kpi-popover-close"
                          onClick={(e) => {
                            e.stopPropagation();
                            setPinnedKpi(null);
                            setHoveredKpi(null);
                          }}
                          title="Close"
                        >
                          <FaTimes size={10} />
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="discovery-kpi-file-list">
                    {otherFileList.map((file) => {
                      const name = extractFileName(file);
                      const badge = getFileBadge(name);
                      return (
                        <div
                          key={file}
                          className="discovery-kpi-file-item"
                          onClick={(e) => handleSelectPopoverFile(file, e)}
                          title={`Click to preview ${name}`}
                        >
                          <div className="discovery-kpi-file-left">
                            <span className="discovery-kpi-file-icon">
                              <FaFile color="#64748b" />
                            </span>
                            <div className="discovery-kpi-file-info">
                              <span className="discovery-kpi-file-name">{name}</span>
                              <span className="discovery-kpi-file-path">{file}</span>
                            </div>
                          </div>
                          <span
                            className="discovery-kpi-file-tag"
                            style={{ color: badge.color, background: badge.bg }}
                          >
                            {badge.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  <div className="discovery-kpi-popover-footer">
                    <span>{otherFileList.length} doc &amp; misc files</span>
                    <span style={{ color: "#94a3b8" }}>{pinnedKpi === "others" ? "Pinned" : "Click to pin"}</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Row 2: Repository Files (Full Width) */}
          <div className="discovery-files-row">
            <div className="discovery-files-card">
              <div className="discovery-panel-header">
                <div className="discovery-panel-title-wrap">
                  <div className="discovery-panel-icon" style={{ background: "#fff7ed", color: "#ea580c" }}>
                    <FaFolder />
                  </div>
                  <div className="discovery-panel-titles">
                    <h3>Repository Files</h3>
                    <p>Browse the repository structure</p>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="discovery-tree-badge-items">
                    {allDiscoveredPaths.length} {allDiscoveredPaths.length === 1 ? "file" : "files"}
                  </span>
                  <button
                    onClick={handleToggleAll}
                    className="discovery-action-btn-outline"
                    style={{ padding: "4px 10px", fontSize: 11 }}
                  >
                    {isAllCollapsed ? <FaChevronRight size={10} /> : <FaChevronDown size={10} />}
                    {isAllCollapsed ? "Expand All" : "Collapse All"}
                  </button>
                </div>
              </div>

              {/* Repository Files Split Layout: Tree on Left, Inline Preview on Right */}
              <div className={`discovery-files-layout ${selectedFile ? "has-preview" : ""}`}>
                {/* Left Pane: Interactive File Tree */}
                <div className="discovery-files-tree-pane">
                  {/* Search Bar */}
                  <div className="discovery-search-wrap">
                    <FaSearch className="discovery-search-icon" />
                    <input
                      type="text"
                      placeholder="Search files and folders..."
                      className="discovery-search-input"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>

                  {/* Interactive File Tree */}
                  <div className="discovery-tree-container">
                    {/* Level 0: Root */}
                    {(!query || rootRepoName.toLowerCase().includes(query) || visibleTree.length > 0) && (
                      <div
                        className="discovery-tree-row"
                        style={{ paddingLeft: 12 }}
                        onClick={() => toggleFolder("root")}
                      >
                        <div className="discovery-tree-left">
                          <span className="discovery-tree-toggle">
                            {isFolderOpen("root") ? <FaChevronDown size={10} /> : <FaChevronRight size={10} />}
                          </span>
                          {isFolderOpen("root") ? <FaFolderOpen color="#f59e0b" size={14} /> : <FaFolder color="#f59e0b" size={14} />}
                          <span style={{ fontWeight: 700 }}>{rootRepoName}</span>
                        </div>
                        <div className="discovery-tree-right">
                          <span className="discovery-tree-badge-items">
                            {visibleTree.length} {visibleTree.length === 1 ? "item" : "items"}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Nested Files & Folders */}
                    {isFolderOpen("root") && (
                      visibleTree.length > 0 ? (
                        visibleTree.map((node) => renderTreeNode(node, 1))
                      ) : query ? (
                        <div style={{ padding: "16px", textAlign: "center", color: "#64748b", fontSize: "13px" }}>
                          No files or folders matching &quot;{searchQuery}&quot;
                        </div>
                      ) : null
                    )}
                  </div>
                </div>

                {/* Right Pane: File Preview & Editor */}
                {selectedFile && (
                  <div className="discovery-files-preview-pane">
                    <div className="discovery-preview-header">
                      <div className="discovery-preview-file-info">
                        <span className="discovery-preview-file-icon">
                          {selectedFile.name.endsWith(".xml") ? (
                            <FaFileCode color="#ea580c" size={14} />
                          ) : selectedFile.name.endsWith(".md") ? (
                            <FaFileAlt color="#64748b" size={14} />
                          ) : selectedFile.name.endsWith(".java") ? (
                            <FaFileCode color="#2563eb" size={14} />
                          ) : (
                            <FaFile color="#64748b" size={14} />
                          )}
                        </span>
                        <div className="discovery-preview-file-names">
                          <span className="discovery-preview-filename">{selectedFile.name}</span>
                          <span className="discovery-preview-filepath">{selectedFile.path}</span>
                        </div>
                      </div>

                      <div className="discovery-preview-actions">
                        <button
                          type="button"
                          className="discovery-preview-close-btn"
                          onClick={() => {
                            setSelectedFile(null);
                            setFileContent("");
                            setEditedContent("");
                            setIsEditing(false);
                          }}
                          title="Close Preview"
                        >
                          <FaTimes size={13} />
                        </button>
                      </div>
                    </div>

                    <div className="discovery-preview-body">
                      {fileLoading ? (
                        <div className="discovery-preview-loading">
                          <div className="discovery-preview-spinner" />
                          <span>Loading file content...</span>
                        </div>
                      ) : (
                        <pre className="discovery-preview-code">
                          <code>{fileContent || "// No content available"}</code>
                        </pre>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Row 3: Detected Frameworks & Libraries, Project Structure Summary & Technical Specification Document */}
          <div className="discovery-bottom-grid">
            {/* Card 1: Detected Frameworks & Libraries */}
            <div className="discovery-panel-card">
              <div className="discovery-panel-header">
                <div className="discovery-panel-title-wrap">
                  <div className="discovery-panel-icon" style={{ background: "#faf5ff", color: "#9333ea" }}>
                    <FaPuzzlePiece />
                  </div>
                  <div className="discovery-panel-titles">
                    <h3>Detected Frameworks &amp; Libraries</h3>
                  </div>
                </div>
                <span
                  className="discovery-panel-viewall"
                  onClick={() => setShowFrameworksModal(true)}
                  title="View all detected frameworks and libraries"
                >
                  View All ({detectedFrameworks.length})
                </span>
              </div>

              <div className="discovery-frameworks-list">
                {detectedFrameworks.map((fw) => (
                  <div key={fw.id} className={`discovery-framework-item-card is-${fw.category}`}>
                    <div className="discovery-framework-item-top">
                      <div className="discovery-framework-item-brand">
                        <div className="discovery-framework-brand-icon">
                          {renderFrameworkIcon(fw.category)}
                        </div>
                        <div>
                          <div className="discovery-framework-brand-name">{fw.name}</div>
                          <div className="discovery-framework-brand-type">{fw.type}</div>
                        </div>
                      </div>
                      <span className="discovery-framework-status-badge">{fw.status}</span>
                    </div>

                    <div className="discovery-framework-tags">
                      {fw.tags.map((tag, tIdx) => (
                        <span key={tIdx} className={`discovery-tag-${tag.color}`}>
                          {tag.label}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div className="discovery-callout-blue">
                <FaInfoCircle color="#2563eb" size={16} style={{ flexShrink: 0 }} />
                <div>
                  <div className="discovery-callout-blue-title">
                    {detectedFrameworks.length === 1
                      ? "1 framework detected"
                      : `${detectedFrameworks.length} frameworks & libraries detected`}
                  </div>
                  <div className="discovery-callout-blue-sub">Major frameworks and libraries identified in the project.</div>
                </div>
              </div>
            </div>

            {/* Card 2: Project Structure Summary */}
            <div className="discovery-panel-card discovery-structure-card">
              <div className="discovery-panel-header">
                <div className="discovery-panel-title-wrap">
                  <div className="discovery-panel-icon" style={{ background: "#eff6ff", color: "#2563eb" }}>
                    <FaListAlt />
                  </div>
                  <div className="discovery-panel-titles">
                    <h3>Project Structure Summary</h3>
                    <p>Key project structure elements</p>
                  </div>
                </div>
              </div>

              <div className="discovery-structure-list">
                <div className="discovery-structure-item">
                  <div className="discovery-structure-left">
                    <div className="discovery-structure-icon-box" style={{ background: "#dcfce7", color: "#16a34a" }}>
                      <FaFileAlt size={13} />
                    </div>
                    <div>
                      <div className="discovery-structure-name">{buildFileName || "pom.xml"}</div>
                      <div className="discovery-structure-desc">Build Configuration</div>
                    </div>
                  </div>
                  <FaCheckCircle color="#16a34a" size={15} />
                </div>

                <div className="discovery-structure-item">
                  <div className="discovery-structure-left">
                    <div className="discovery-structure-icon-box" style={{ background: "#dcfce7", color: "#16a34a" }}>
                      <FaFolder size={13} />
                    </div>
                    <div>
                      <div className="discovery-structure-name">src/main</div>
                      <div className="discovery-structure-desc">Source Directory</div>
                    </div>
                  </div>
                  <FaCheckCircle color="#16a34a" size={15} />
                </div>

                <div className="discovery-structure-item">
                  <div className="discovery-structure-left">
                    <div className="discovery-structure-icon-box" style={{ background: "#e0f2fe", color: "#0284c7" }}>
                      <FaCode size={13} />
                    </div>
                    <div>
                      <div className="discovery-structure-name">Java {detectedJavaVersion}</div>
                      <div className="discovery-structure-desc">Detected Version</div>
                    </div>
                  </div>
                  <FaCheckCircle color="#16a34a" size={15} />
                </div>
              </div>
            </div>

            {/* Card 3: Technical Specification Document (bottom right corner) */}
            <div className="discovery-spec-card">
              <div className="discovery-panel-header">
                <div className="discovery-panel-title-wrap">
                  <div className="discovery-panel-icon" style={{ background: "#faf5ff", color: "#9333ea" }}>
                    <FaFileAlt />
                  </div>
                  <div className="discovery-panel-titles">
                    <h3>Technical Specification Document</h3>
                    <p>Generate a repository-grounded technical specification document.</p>
                  </div>
                </div>
              </div>

              <div className="discovery-spec-body-centered">
                {/* Vector Document Graphic matching screenshot */}
                <div className="discovery-spec-illus-box">
                  <svg width="86" height="64" viewBox="0 0 130 96" fill="none">
                    <ellipse cx="65" cy="48" rx="55" ry="38" fill="#eff6ff" />
                    <ellipse cx="74" cy="45" rx="42" ry="28" fill="#faf5ff" />
                    {/* Shadow / background page */}
                    <rect x="34" y="24" width="46" height="58" rx="6" fill="#bfdbfe" opacity="0.5" />
                    {/* Middle sheet */}
                    <rect x="40" y="18" width="50" height="62" rx="6" fill="#ffffff" stroke="#93c5fd" strokeWidth="1.2" />
                    {/* Top main page */}
                    <rect x="46" y="12" width="52" height="66" rx="8" fill="#ffffff" stroke="#60a5fa" strokeWidth="1.5" />
                    {/* Document lines */}
                    <rect x="54" y="22" width="22" height="5" rx="2.5" fill="#3b82f6" />
                    <rect x="54" y="32" width="36" height="3" rx="1.5" fill="#94a3b8" />
                    <rect x="54" y="39" width="32" height="3" rx="1.5" fill="#cbd5e1" />
                    <rect x="54" y="46" width="36" height="3" rx="1.5" fill="#94a3b8" />
                    <rect x="54" y="53" width="24" height="3" rx="1.5" fill="#cbd5e1" />
                    <rect x="54" y="60" width="34" height="3" rx="1.5" fill="#94a3b8" />
                    {/* Small badge accent */}
                    <circle cx="92" cy="22" r="7" fill="#3b82f6" />
                    <path d="M89.5 22L91.5 24L94.5 20.5" stroke="#ffffff" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>

                <h4 className="discovery-spec-h4">Generate Technical Specification Document</h4>
                <p className="discovery-spec-desc">
                  The document will include project structure, detected frameworks, dependencies, and key technical details.
                </p>

                <button
                  className="discovery-spec-generate-btn"
                  disabled={documentGenerationLoading !== null}
                  onClick={() => {
                    void handleGenerateBrdDocument();
                  }}
                >
                  <FaFileAlt size={13} />
                  {documentGenerationLoading ? "Generating Document..." : (technicalSpecificationButtonLabel || "Generate Document")}
                </button>

                <div className="discovery-spec-footnote">
                  {technicalSpecificationHelperText || "The Technical Specification Document is ready to download."}
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Bottom Bar: Pro Tip & Navigation Buttons (hidden while analysis is in progress) */}
      {!isDiscoveryPending && (
        <div className="discovery-bottom-bar">
          <div className="discovery-protip">
            {/* <FaLightbulb color="#eab308" size={16} /> */}
            {/* <span className="discovery-protip-tag">Pro Tip</span> */}
            {/* <span>Use JavaApex Assistant to ask questions about your repository, dependencies, or migration readiness.</span> */}
          </div>

          <div className="discovery-nav-btns">
            <button className="discovery-btn-back" onClick={onBack}>
              <FaArrowLeft size={11} style={{ marginRight: 6 }} /> Back
            </button>
            <button
              className="discovery-btn-continue"
              onClick={onContinueToStrategy}
              disabled={isDiscoveryPending}
            >
              Continue to Strategy <FaArrowRight size={11} style={{ marginLeft: 6 }} />
            </button>
          </div>
        </div>
      )}

      {/* All Detected Frameworks & Libraries Modal */}
      {showFrameworksModal && (
        <div className="discovery-modal-overlay" onClick={() => setShowFrameworksModal(false)}>
          <div className="discovery-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="discovery-modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div className="discovery-panel-icon" style={{ background: "#faf5ff", color: "#9333ea" }}>
                  <FaPuzzlePiece />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#0f172a" }}>
                    Detected Frameworks &amp; Libraries
                  </h3>
                  <p style={{ margin: "2px 0 0", fontSize: 12, color: "#64748b" }}>
                    Total {detectedFrameworks.length} frameworks and major components identified
                  </p>
                </div>
              </div>
              <button
                className="discovery-preview-close-btn"
                onClick={() => setShowFrameworksModal(false)}
                title="Close"
              >
                <FaTimes size={14} />
              </button>
            </div>
            <div className="discovery-modal-body">
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {detectedFrameworks.map((fw) => (
                  <div key={fw.id} className={`discovery-framework-item-card is-${fw.category}`} style={{ marginBottom: 0 }}>
                    <div className="discovery-framework-item-top">
                      <div className="discovery-framework-item-brand">
                        <div className="discovery-framework-brand-icon">
                          {renderFrameworkIcon(fw.category)}
                        </div>
                        <div>
                          <div className="discovery-framework-brand-name">{fw.name}</div>
                          <div className="discovery-framework-brand-type">{fw.type}</div>
                        </div>
                      </div>
                      <span className="discovery-framework-status-badge">{fw.status}</span>
                    </div>

                    <div className="discovery-framework-tags">
                      {fw.tags.map((tag, tIdx) => (
                        <span key={tIdx} className={`discovery-tag-${tag.color}`}>
                          {tag.label}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
