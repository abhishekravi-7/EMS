import React, { useState, useMemo, useEffect } from "react";
import { FaSearch, FaChevronLeft, FaChevronRight, FaCheckCircle, FaExclamationTriangle, FaExchangeAlt, FaShieldAlt } from "react-icons/fa";

export type DependencyAction =
  | "UPGRADE"
  | "MAJOR UPGRADE"
  | "REPLACE"
  | "REMOVE"
  | "ALREADY COMPATIBLE"
  | "MANUAL REVIEW";

export type MigrationRisk = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface DependencyRowItem {
  dependency: string; // group:artifact
  currentVersion: string;
  targetDependency: string; // Target coordinate or "Not Required"
  targetVersion: string;
  action: DependencyAction;
  reasoning: string;
  sourceChanges: string;
  risk: MigrationRisk;
  group: "Framework" | "Library" | "Dependency" | "Runtime";
  dependencyType: string; // DIRECT or TRANSITIVE
  isJavaxToJakarta: boolean;
}

interface DetectedDependenciesTableProps {
  repoAnalysis?: any;
  dependencyAnalysis?: any;
  targetJavaVersion?: string;
  allDepsText: string;
  CopyAllDependenciesButton: React.ComponentType<{ text: string; label?: string }>;
}

const CATEGORY_COLORS: Record<string, { text: string; background: string; border: string }> = {
  Framework: { text: "#1d4ed8", background: "#eff6ff", border: "#bfdbfe" },
  Library: { text: "#047857", background: "#ecfdf5", border: "#a7f3d0" },
  Dependency: { text: "#b45309", background: "#fffbeb", border: "#fde68a" },
  Runtime: { text: "#6d28d9", background: "#f5f3ff", border: "#ddd6fe" },
};

const ACTION_CONFIG: Record<DependencyAction, { text: string; background: string; border: string; label: string }> = {
  "MAJOR UPGRADE": { text: "#6d28d9", background: "#f5f3ff", border: "#ddd6fe", label: "MAJOR UPGRADE" },
  UPGRADE: { text: "#1d4ed8", background: "#eff6ff", border: "#bfdbfe", label: "UPGRADE" },
  "ALREADY COMPATIBLE": { text: "#047857", background: "#ecfdf5", border: "#a7f3d0", label: "ALREADY COMPATIBLE" },
  REPLACE: { text: "#b45309", background: "#fffbeb", border: "#fde68a", label: "REPLACE" },
  REMOVE: { text: "#dc2626", background: "#fef2f2", border: "#fecaca", label: "REMOVE" },
  "MANUAL REVIEW": { text: "#c2410c", background: "#fff7ed", border: "#ffedd5", label: "MANUAL REVIEW" },
};

const RISK_CONFIG: Record<MigrationRisk, { text: string; background: string; border: string }> = {
  CRITICAL: { text: "#991b1b", background: "#fef2f2", border: "#fecaca" },
  HIGH: { text: "#c2410c", background: "#fff7ed", border: "#ffedd5" },
  MEDIUM: { text: "#b45309", background: "#fffbeb", border: "#fde68a" },
  LOW: { text: "#047857", background: "#ecfdf5", border: "#a7f3d0" },
};

export function compareSemVer(v1: string, v2: string): number {
  if (v1 === v2) return 0;
  if (!v1 && !v2) return 0;
  if (!v1) return -1;
  if (!v2) return 1;

  const parseParts = (v: string) => {
    return (v || "")
      .replace(/^[vV]/, "")
      .split(/[-._]/)
      .map((part) => {
        const num = parseInt(part, 10);
        return isNaN(num) ? part.toLowerCase() : num;
      });
  };

  const p1 = parseParts(v1);
  const p2 = parseParts(v2);
  const maxLen = Math.max(p1.length, p2.length);

  for (let i = 0; i < maxLen; i++) {
    const a = p1[i] ?? 0;
    const b = p2[i] ?? 0;
    if (typeof a === "number" && typeof b === "number") {
      if (a !== b) return a - b;
    } else {
      const sa = String(a);
      const sb = String(b);
      if (sa !== sb) return sa.localeCompare(sb);
    }
  }
  return 0;
}

export interface JavaBaselineFloor {
  boot: string;
  fw: string;
  data: string;
  logback: string;
  log4j: string;
  slf4j: string;
  snakeyaml: string;
  jackson: string;
  tomcat: string;
  mysql: string;
  security: string;
  annotation: string;
  validation: string;
  jupiter: string;
  mockito: string;
  lombok: string;
  hibernate: string;
}

export function getMinimumBaselineForJava(javaNum: number): JavaBaselineFloor {
  if (javaNum >= 25) {
    return {
      boot: "3.4.0",
      fw: "6.2.0",
      data: "2024.0.0",
      logback: "1.5.12",
      log4j: "2.24.1",
      slf4j: "2.0.16",
      snakeyaml: "2.3",
      jackson: "2.17.2",
      tomcat: "10.1.33",
      mysql: "9.0.0",
      security: "6.4.0",
      annotation: "3.0.0",
      validation: "3.1.0",
      jupiter: "5.11.3",
      mockito: "5.14.2",
      lombok: "1.18.36",
      hibernate: "6.6.1.Final",
    };
  }
  if (javaNum >= 21) {
    return {
      boot: "3.3.0",
      fw: "6.1.14",
      data: "2023.1.5",
      logback: "1.5.6",
      log4j: "2.23.1",
      slf4j: "2.0.13",
      snakeyaml: "2.2",
      jackson: "2.17.1",
      tomcat: "10.1.24",
      mysql: "8.3.0",
      security: "6.3.0",
      annotation: "2.1.1",
      validation: "3.0.2",
      jupiter: "5.10.2",
      mockito: "5.11.0",
      lombok: "1.18.36",
      hibernate: "6.5.2.Final",
    };
  }
  if (javaNum >= 17) {
    return {
      boot: "3.2.5",
      fw: "6.1.14",
      data: "2023.1.5",
      logback: "1.4.14",
      log4j: "2.21.1",
      slf4j: "2.0.13",
      snakeyaml: "2.2",
      jackson: "2.15.4",
      tomcat: "10.1.20",
      mysql: "8.3.0",
      security: "6.2.4",
      annotation: "2.1.1",
      validation: "3.0.2",
      jupiter: "5.10.2",
      mockito: "5.8.0",
      lombok: "1.18.36",
      hibernate: "6.4.4.Final",
    };
  }
  // Java 8 / 11
  return {
    boot: "2.7.18",
    fw: "5.3.31",
    data: "2021.2.18",
    logback: "1.2.13",
    log4j: "2.17.2",
    slf4j: "1.7.36",
    snakeyaml: "1.33",
    jackson: "2.13.5",
    tomcat: "9.0.83",
    mysql: "8.0.33",
    security: "5.7.11",
    annotation: "1.3.5",
    validation: "2.0.2",
    jupiter: "5.8.2",
    mockito: "4.5.1",
    lombok: "1.18.30",
    hibernate: "5.6.15.Final",
  };
}

function resolveTargetVersionFallback(
  gid: string,
  aid: string,
  currentVer: string,
  targetJavaVersion?: string
) {
  const g = (gid || "").toLowerCase();
  const a = (aid || "").toLowerCase();
  const ver = (currentVer || "Unknown").trim();
  const javaNum = parseInt((targetJavaVersion || "17").replace(/\D/g, "") || "17", 10);
  const baseline = getMinimumBaselineForJava(javaNum);
  const bootVer = baseline.boot;
  const fwVer = baseline.fw;

  let tgtDep = `${gid}:${aid}`;
  let tgtVer = bootVer;
  let action: DependencyAction = "UPGRADE";
  let reasoning = `Managed directly by Target Spring Boot ${bootVer} BOM.`;
  let sourceChanges = "Build manifest version property update required.";
  let risk: MigrationRisk = "LOW";

  if (g === "org.springframework.boot" || a.includes("spring-boot")) {
    tgtVer = bootVer;
    reasoning = `The detected Spring Boot version belongs to an earlier generation. Target Spring Boot ${bootVer} manages all starter dependencies for Java ${javaNum}.`;
    sourceChanges = "Update Spring Boot parent/starter BOM version in build manifest.";
    risk = javaNum >= 17 ? "HIGH" : "LOW";
  } else if (g === "org.springframework" || (g.startsWith("org.springframework") && !g.includes("boot") && !g.includes("data"))) {
    tgtVer = fwVer;
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Spring Framework ${fwVer}). Crosses major Spring generation.`;
    sourceChanges = "API compatibility review required for Spring Framework breaking changes.";
    risk = javaNum >= 17 ? "HIGH" : "LOW";
  } else if (g.startsWith("org.springframework.data") || a.includes("spring-data")) {
    tgtVer = baseline.data;
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Spring Data release train).`;
    sourceChanges = "Audit custom repository interfaces for Spring Data query method changes.";
    risk = javaNum >= 17 ? "HIGH" : "LOW";
  } else if (g.startsWith("javax.") || a.startsWith("javax.") || a === "validation-api") {
    if (javaNum >= 17) {
      action = "REPLACE";
      reasoning = `The old javax.* API belongs to the pre-Jakarta namespace. Spring Boot 3.x uses Jakarta EE APIs. Requires dependency-coordinate and source-package migration.`;
      risk = "HIGH";
      if (a.includes("validation")) {
        tgtDep = "jakarta.validation:jakarta.validation-api";
        tgtVer = baseline.validation;
        sourceChanges = "javax.validation.* → jakarta.validation.*";
      } else if (a.includes("persistence")) {
        tgtDep = "jakarta.persistence:jakarta.persistence-api";
        tgtVer = "3.1.0";
        sourceChanges = "javax.persistence.* → jakarta.persistence.*";
      } else if (a.includes("servlet")) {
        tgtDep = "jakarta.servlet:jakarta.servlet-api";
        tgtVer = "6.0.0";
        sourceChanges = "javax.servlet.* → jakarta.servlet.*";
      } else if (a.includes("transaction")) {
        tgtDep = "jakarta.transaction:jakarta.transaction-api";
        tgtVer = "2.0.1";
        sourceChanges = "javax.transaction.* → jakarta.transaction.*";
      } else if (a.includes("annotation")) {
        tgtDep = "jakarta.annotation:jakarta.annotation-api";
        tgtVer = baseline.annotation;
        sourceChanges = "javax.annotation.* → jakarta.annotation.*";
      } else if (a.includes("ws.rs") || a.includes("jaxrs")) {
        tgtDep = "jakarta.ws.rs:jakarta.ws.rs-api";
        tgtVer = "3.1.0";
        sourceChanges = "javax.ws.rs.* → jakarta.ws.rs.*";
      } else {
        tgtDep = `jakarta.${a}:jakarta.${a}`;
        tgtVer = "3.0.0";
        sourceChanges = "javax.* → jakarta.*";
      }
    } else {
      tgtDep = `${gid}:${aid}`;
      tgtVer = ver;
      action = "ALREADY COMPATIBLE";
      reasoning = `Legacy javax.* artifact remains supported on Java ${javaNum} and Spring Boot ${bootVer}.`;
      sourceChanges = "None required.";
      risk = "LOW";
    }
  } else if (a.includes("lombok")) {
    tgtVer = baseline.lombok;
    action = "UPGRADE";
    reasoning = `Upgraded Lombok version required for Java ${javaNum} bytecode compiler support.`;
    sourceChanges = "Build manifest Lombok dependency version update.";
    risk = "LOW";
  } else if (a.includes("hibernate")) {
    if (a.includes("entitymanager")) {
      tgtDep = "Not Required";
      tgtVer = "N/A";
      action = "REMOVE";
      reasoning = "The old separate Hibernate EntityManager artifact is not required in Hibernate ORM 6 because functionality is integrated into hibernate-core.";
      sourceChanges = "Remove obsolete hibernate-entitymanager dependency from pom.xml";
      risk = "MEDIUM";
    } else {
      tgtVer = baseline.hibernate;
      reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Hibernate ORM ${tgtVer}).`;
      sourceChanges = "Audit JPA queries and dialect configuration for Hibernate.";
      risk = javaNum >= 17 ? "HIGH" : "LOW";
    }
  } else if (a.includes("jackson")) {
    tgtVer = baseline.jackson;
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Jackson ${tgtVer}).`;
    sourceChanges = "None - Jackson is backward compatible.";
    risk = "LOW";
  } else if (a.includes("log4j") || g.includes("log4j")) {
    tgtVer = baseline.log4j;
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Log4j 2 ${tgtVer}).`;
    sourceChanges = "None - logging configuration backward compatible.";
    risk = "LOW";
  } else if (a.includes("logback")) {
    tgtVer = baseline.logback;
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Logback ${tgtVer}).`;
    sourceChanges = "None - standard logging configuration.";
    risk = "LOW";
  } else if (a.includes("slf4j")) {
    tgtVer = baseline.slf4j;
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (SLF4J ${tgtVer}).`;
    sourceChanges = "None - logging facade backward compatible.";
    risk = "LOW";
  } else if (a.includes("tomcat")) {
    tgtVer = baseline.tomcat;
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Tomcat ${tgtVer}).`;
    sourceChanges = javaNum >= 17 ? "Refactor server web.xml or Servlet filters to modern Tomcat." : "Standard Tomcat update.";
    risk = javaNum >= 17 ? "HIGH" : "LOW";
  } else if (a.includes("mysql")) {
    tgtVer = baseline.mysql;
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (MySQL Connector/J ${tgtVer}).`;
    sourceChanges = "Update JDBC driver class name to com.mysql.cj.jdbc.Driver if legacy.";
    risk = "LOW";
  } else if (a.includes("h2") || a.includes("hsqldb")) {
    tgtVer = javaNum >= 17 ? "2.2.224" : "1.4.200";
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM.`;
    sourceChanges = "Review database connection URL compatibility.";
    risk = "LOW";
  } else if (a.includes("postgresql")) {
    tgtVer = "42.6.2";
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM.`;
    sourceChanges = "None - PostgreSQL JDBC driver backward compatible.";
    risk = "LOW";
  } else if (a === "snakeyaml" || g === "org.yaml") {
    tgtVer = baseline.snakeyaml;
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (SnakeYAML ${tgtVer}).`;
    sourceChanges = "Review YAML parsing configuration.";
    risk = "LOW";
  } else if (g.includes("spring-security") || a.includes("spring-security")) {
    tgtVer = baseline.security;
    action = "MAJOR UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Spring Security ${tgtVer}).`;
    sourceChanges = "Review security configuration adapter.";
    risk = javaNum >= 17 ? "HIGH" : "LOW";
  } else if (a === "jakarta.annotation-api" || g === "jakarta.annotation") {
    tgtVer = baseline.annotation;
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM.`;
    sourceChanges = "None required.";
    risk = "LOW";
  } else if (a === "jakarta.validation-api" || g === "jakarta.validation") {
    tgtVer = baseline.validation;
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM.`;
    sourceChanges = "None required.";
    risk = "LOW";
  } else if (a.includes("jupiter") || g === "org.junit.jupiter") {
    tgtVer = baseline.jupiter;
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (JUnit Jupiter ${tgtVer}).`;
    sourceChanges = "None - JUnit Jupiter backward compatible.";
    risk = "LOW";
  } else if (a === "junit" || g === "junit") {
    tgtVer = "4.13.2";
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (JUnit 4).`;
    sourceChanges = "None required.";
    risk = "LOW";
  } else if (a.includes("mockito")) {
    tgtVer = baseline.mockito;
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Mockito ${tgtVer}).`;
    sourceChanges = "None required.";
    risk = "LOW";
  } else if (ver && ver !== "Unknown" && ver !== "unknown" && ver !== "managed version") {
    tgtVer = ver;
    action = "ALREADY COMPATIBLE";
    reasoning = `Current version ${ver} is already compatible with target Java ${javaNum}.`;
    sourceChanges = "None required.";
    risk = "LOW";
  } else {
    tgtVer = bootVer;
    action = "MANUAL REVIEW";
    reasoning = `Third-party dependency requiring independent API compatibility verification for Java ${javaNum}.`;
    sourceChanges = "Audit library API usages against target JDK release.";
    risk = "MEDIUM";
  }

  // GOLDEN RULE (Floor & Preserve): Never downgrade a higher current version
  if (action !== "REPLACE" && action !== "REMOVE") {
    if (ver && ver !== "Unknown" && ver !== "unknown" && ver !== "managed version" && tgtVer && tgtVer !== "N/A" && tgtVer !== "Not Determined") {
      const cmp = compareSemVer(ver, tgtVer);
      const parseDigits = (s: string) => (s.match(/\d+/g) || []).map(Number);
      const curD = parseDigits(ver);
      const tgtD = parseDigits(tgtVer);
      const curMaj = curD[0] ?? 0;
      const tgtMaj = tgtD[0] ?? 0;

      if (cmp === 0) {
        action = "ALREADY COMPATIBLE";
        reasoning = `Current version ${ver} already matches target Spring Boot BOM release for Java ${javaNum}.`;
        sourceChanges = "None required.";
        risk = "LOW";
      } else if (tgtMaj > curMaj && curMaj > 0) {
        action = "MAJOR UPGRADE";
        risk = "HIGH";
      } else if (cmp < 0) {
        action = "UPGRADE";
        risk = risk === "HIGH" ? "HIGH" : "LOW";
      } else {
        // Floor & Preserve: If current version already exceeds baseline, preserve it!
        tgtVer = ver;
        action = "ALREADY COMPATIBLE";
        reasoning = `Current version ${ver} already meets or exceeds target Java ${javaNum} baseline requirements.`;
        sourceChanges = "None required.";
        risk = "LOW";
      }
    }
  }

  return {
    targetDependency: tgtDep,
    targetVersion: tgtVer,
    action,
    reasoning,
    sourceChanges,
    risk,
  };
}

export function DetectedDependenciesTable({
  repoAnalysis,
  dependencyAnalysis,
  targetJavaVersion,
  allDepsText,
  CopyAllDependenciesButton,
}: DetectedDependenciesTableProps) {
  const [activeTab, setActiveTab] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(15);

  const sourceJava = repoAnalysis?.java_version || repoAnalysis?.java_version_from_build || "1.7";
  const sourceJavaNum = parseInt(String(sourceJava).replace(/^1\./, "").replace(/\D/g, "") || "8", 10);
  const targetJavaNum = parseInt((targetJavaVersion || "21").replace(/\D/g, "") || "21", 10);
  const currentBoot = repoAnalysis?.spring_boot_version || "1.3.5.RELEASE";
  const currentFramework = repoAnalysis?.frameworks?.[0]?.name ? `${repoAnalysis.frameworks[0].name} (${currentBoot})` : `Spring Boot ${currentBoot}`;

  const { allRows, counts, javaCurrent } = useMemo(() => {
    const analyzedMap = new Map<string, any>();
    if (dependencyAnalysis?.dependencies) {
      for (const item of dependencyAnalysis.dependencies) {
        if (item.id) analyzedMap.set(item.id.toLowerCase(), item);
        if (item.group && item.artifact) {
          analyzedMap.set(`${item.group}:${item.artifact}`.toLowerCase(), item);
        }
        if (item.artifact) {
          analyzedMap.set(item.artifact.toLowerCase(), item);
        }
      }
    }

    const rows: DependencyRowItem[] = [];
    const cnts = {
      ALL: 0,
      Framework: 0,
      Library: 0,
      Dependency: 0,
    };

    const javaVer = repoAnalysis?.java_version || repoAnalysis?.java_version_from_build;

    (repoAnalysis?.dependencies || []).forEach((dependency: any) => {
      const gid = dependency.group_id || dependency.groupId || dependency.group || "";
      const aid = dependency.artifact_id || dependency.artifactId || dependency.artifact || "";
      const currentVer = dependency.current_version || dependency.resolved_version || dependency.declared_version || dependency.version || "Unknown";
      const coordinate = `${gid}:${aid}`.toLowerCase();

      let analysis = analyzedMap.get(coordinate);
      if (!analysis && aid) {
        analysis = analyzedMap.get(aid.toLowerCase());
      }
      if (!analysis && gid) {
        analysis = analyzedMap.get(gid.toLowerCase());
      }

      const fallback = resolveTargetVersionFallback(gid, aid, currentVer, targetJavaVersion);

      let targetDep = analysis?.target_dependency || fallback.targetDependency;
      let targetVer = analysis?.recommended_version || fallback.targetVersion;
      let action: DependencyAction = fallback.action;
      let reasoning = analysis?.upgrade_reason || analysis?.explanation || fallback.reasoning;
      let sourceChanges = analysis?.migration_action || analysis?.recommendation || fallback.sourceChanges;
      let risk: MigrationRisk = (analysis?.risk as MigrationRisk) || fallback.risk;

      const javaNum = targetJavaNum;
      const isJavax = gid.toLowerCase().startsWith("javax.") || aid.toLowerCase().startsWith("javax.") || aid.toLowerCase() === "validation-api";

      if (isJavax) {
        if (javaNum >= 17) {
          action = "REPLACE";
          risk = "HIGH";
          if (!sourceChanges.includes("jakarta")) {
            sourceChanges = `${gid}.* → jakarta.${aid.replace("-api", "")}.*`;
          }
        } else {
          const cmp = compareSemVer(currentVer, targetVer);
          if (cmp === 0 || currentVer.toLowerCase() === targetVer.toLowerCase()) {
            action = "ALREADY COMPATIBLE";
            risk = "LOW";
          } else if (cmp < 0) {
            action = "UPGRADE";
            risk = "LOW";
          } else {
            action = "MANUAL REVIEW";
            risk = "MEDIUM";
          }
        }
      } else if (String(analysis?.upgrade_status || "").toUpperCase().includes("REMOVE")) {
        action = "REMOVE";
        targetDep = "Not Required";
        targetVer = "N/A";
        risk = "MEDIUM";
      } else if (analysis?.upgrade_status === "REVIEW REQUIRED" || analysis?.upgrade_status === "Manual Review" || targetVer === "Not Determined") {
        action = "MANUAL REVIEW";
        risk = "MEDIUM";
      } else if (currentVer && currentVer !== "Unknown" && currentVer !== "unknown" && currentVer !== "managed version" && targetVer && targetVer !== "N/A" && targetVer !== "Not Determined") {
        const cmp = compareSemVer(currentVer, targetVer);
        const parseDigits = (s: string) => (s.match(/\d+/g) || []).map(Number);
        const curD = parseDigits(currentVer);
        const tgtD = parseDigits(targetVer);
        const curMaj = curD[0] ?? 0;
        const tgtMaj = tgtD[0] ?? 0;

        if (cmp === 0) {
          action = "ALREADY COMPATIBLE";
          risk = "LOW";
          if (!analysis?.upgrade_reason) {
            reasoning = `Current version ${currentVer} is already compatible with target Java ${javaNum}.`;
          }
        } else if (tgtMaj > curMaj && curMaj > 0) {
          action = "MAJOR UPGRADE";
          risk = "HIGH";
        } else if (cmp < 0) {
          action = "UPGRADE";
          risk = risk === "CRITICAL" ? "MEDIUM" : (risk === "HIGH" ? "MEDIUM" : "LOW");
        } else {
          // Floor & Preserve: If current version exceeds target baseline, preserve it!
          targetVer = currentVer;
          action = "ALREADY COMPATIBLE";
          risk = "LOW";
          reasoning = `Current version ${currentVer} already meets or exceeds target Java ${javaNum} baseline requirements.`;
        }
      }

      const category = (analysis?.category || "").toLowerCase();
      const group: "Framework" | "Library" | "Dependency" =
        category === "framework"
          ? "Framework"
          : ["persistence", "security", "database", "testing", "logging", "web", "utility"].includes(category)
          ? "Library"
          : "Dependency";

      const depName = gid && aid ? `${gid}:${aid}` : aid || gid || "Dependency";

      rows.push({
        dependency: depName,
        group,
        currentVersion: currentVer,
        targetDependency: targetDep,
        targetVersion: targetVer,
        action,
        reasoning,
        sourceChanges,
        risk,
        dependencyType:
          dependency.direct === false || dependency.transitive
            ? "TRANSITIVE / BOOT-MANAGED"
            : "DIRECT",
        isJavaxToJakarta: isJavax && javaNum >= 17,
      });

      cnts[group] = (cnts[group] || 0) + 1;
    });

    cnts.ALL = rows.length + (javaVer ? 1 : 0);

    return { allRows: rows, counts: cnts, javaCurrent: javaVer };
  }, [repoAnalysis, dependencyAnalysis, targetJavaVersion]);

  // Exact prompt action totals
  const actionTotals = useMemo(() => {
    const totals: Record<DependencyAction, number> = {
      UPGRADE: 0,
      "MAJOR UPGRADE": 0,
      REPLACE: 0,
      REMOVE: 0,
      "ALREADY COMPATIBLE": 0,
      "MANUAL REVIEW": 0,
    };
    allRows.forEach((row) => {
      totals[row.action] = (totals[row.action] || 0) + 1;
    });
    return totals;
  }, [allRows]);

  const selectedBootVersion = targetJavaNum >= 17 ? "3.2.5" : "2.7.18";
  const selectedFrameworkVersion = targetJavaNum >= 17 ? "6.1.14" : "5.3.31";

  const javaxList = useMemo(() => allRows.filter((r) => r.isJavaxToJakarta), [allRows]);

  useEffect(() => {
    setCurrentPage(1);
  }, [activeTab, searchQuery, pageSize]);

  const filteredRows = useMemo(() => {
    let result = allRows;

    if (activeTab !== "ALL") {
      result = result.filter((row) => row.group === activeTab);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(
        (row) =>
          row.dependency.toLowerCase().includes(q) ||
          row.currentVersion.toLowerCase().includes(q) ||
          row.targetDependency.toLowerCase().includes(q) ||
          row.targetVersion.toLowerCase().includes(q) ||
          row.action.toLowerCase().includes(q) ||
          row.reasoning.toLowerCase().includes(q) ||
          row.sourceChanges.toLowerCase().includes(q)
      );
    }

    return result;
  }, [allRows, activeTab, searchQuery]);

  const totalFilteredCount = filteredRows.length + (javaCurrent && (activeTab === "ALL" || activeTab === "Framework") && !searchQuery.trim() ? 1 : 0);
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedRows = filteredRows.slice(startIndex, startIndex + pageSize);

  const renderJavaRow = javaCurrent && (activeTab === "ALL" || activeTab === "Framework") && !searchQuery.trim() && currentPage === 1;

  // Compute Overall Assessment level dynamically based on target Java, source Java, and actions
  const overallAssessment = useMemo((): MigrationRisk => {
    const totalRows = allRows.length;
    if (totalRows === 0) return "LOW";

    // 1. If all dependencies are already compatible, risk is LOW
    if (actionTotals["ALREADY COMPATIBLE"] === totalRows) {
      return "LOW";
    }

    // 2. Target Java < 17 (e.g. Java 11 or Java 8):
    // Preserves javax.* namespace. Spring Boot 2.7 / Spring 5.3 baseline.
    if (targetJavaNum < 17) {
      if (actionTotals["MANUAL REVIEW"] >= 4 || (actionTotals["MAJOR UPGRADE"] >= 6 && sourceJavaNum < 8)) {
        return "HIGH";
      }
      if (actionTotals["MAJOR UPGRADE"] > 0 || actionTotals["MANUAL REVIEW"] > 0 || actionTotals.REMOVE > 0) {
        return "MEDIUM";
      }
      if (actionTotals.UPGRADE > 0) {
        return "LOW";
      }
      return "LOW";
    }

    // 3. Target Java >= 17 (e.g. Java 17, 21, 25):
    // Crosses Jakarta EE 9+/10 boundary (Spring Boot 3.x / Spring 6.x).
    const hasJavaxShift = javaxList.length > 0;
    const isMultiGenJump = sourceJavaNum <= 8;

    // CRITICAL:
    // Only when jumping multiple generations (Java 8 -> 17/21/25) WITH multiple javax->jakarta package replacements,
    // or heavy architectural refactoring required across many dependencies.
    if (
      (isMultiGenJump && hasJavaxShift && (javaxList.length >= 2 || actionTotals.REPLACE >= 2)) ||
      (isMultiGenJump && actionTotals["MAJOR UPGRADE"] >= 4) ||
      actionTotals["MANUAL REVIEW"] >= 5
    ) {
      return "CRITICAL";
    }

    // HIGH:
    // Required javax->jakarta shift for isolated dependencies, or multiple major version upgrades.
    if (
      hasJavaxShift ||
      actionTotals.REPLACE > 0 ||
      actionTotals["MAJOR UPGRADE"] >= 2 ||
      actionTotals["MANUAL REVIEW"] > 0 ||
      (isMultiGenJump && actionTotals["MAJOR UPGRADE"] > 0)
    ) {
      return "HIGH";
    }

    // MEDIUM:
    // Some minor upgrades or single major upgrade without namespace replacement.
    if (actionTotals.UPGRADE > 0 || actionTotals["MAJOR UPGRADE"] > 0) {
      return "MEDIUM";
    }

    return "LOW";
  }, [allRows.length, actionTotals, javaxList.length, targetJavaNum, sourceJavaNum]);

  // Dynamic explanation for Overall Assessment
  const overallAssessmentExplanation = useMemo(() => {
    const totalRows = allRows.length;
    if (totalRows === 0) {
      return "No external dependencies detected. Zero migration risk.";
    }

    if (actionTotals["ALREADY COMPATIBLE"] === totalRows) {
      return `All detected dependencies already meet or exceed Java ${targetJavaNum} baseline requirements.`;
    }

    if (targetJavaNum < 17) {
      if (overallAssessment === "HIGH") {
        return `Framework upgrade required for Java ${targetJavaNum} (Spring Boot ${selectedBootVersion}). Preserves legacy javax.* namespace while upgrading dependencies for Java ${targetJavaNum} runtime compatibility.`;
      }
      if (overallAssessment === "MEDIUM") {
        return `Moderate migration impact for Java ${targetJavaNum} (Spring Boot ${selectedBootVersion}). Dependencies require standard version alignment; legacy javax.* namespace remains supported with no package refactoring.`;
      }
      return `Low migration friction for Java ${targetJavaNum}. Dependencies are compatible with the Spring Boot ${selectedBootVersion} baseline with standard updates.`;
    }

    // targetJavaNum >= 17
    if (javaxList.length > 0) {
      if (overallAssessment === "CRITICAL") {
        return `Major multi-generational framework upgrade to Java ${targetJavaNum} (Spring Boot ${selectedBootVersion}). Involves package namespace conversions (javax.* → jakarta.* for ${javaxList.length} ${javaxList.length === 1 ? "dependency" : "dependencies"}) and source code API audits.`;
      }
      if (overallAssessment === "HIGH") {
        return `Significant migration to Java ${targetJavaNum} (Spring Boot ${selectedBootVersion}). Requires updating ${javaxList.length} ${javaxList.length === 1 ? "dependency" : "dependencies"} from javax.* to jakarta.* and aligning core framework versions.`;
      }
      return `Moderate migration to Java ${targetJavaNum}. Involves targeted namespace updates (javax.* → jakarta.*) for ${javaxList.length} ${javaxList.length === 1 ? "dependency" : "dependencies"}.`;
    }

    // targetJavaNum >= 17 without javax
    if (overallAssessment === "HIGH") {
      return `Framework upgrade to Java ${targetJavaNum} (Spring Boot ${selectedBootVersion}). No legacy javax.* conversions required, but major version updates are needed for ${actionTotals["MAJOR UPGRADE"]} dependencies.`;
    }
    if (overallAssessment === "MEDIUM") {
      return `Moderate migration impact for Java ${targetJavaNum}. Dependencies require version bumps to align with Spring Boot ${selectedBootVersion} BOM with no namespace conversions needed.`;
    }
    return `Low migration friction for Java ${targetJavaNum}. Detected dependencies are already compatible or require standard version alignment.`;
  }, [allRows.length, actionTotals, targetJavaNum, selectedBootVersion, overallAssessment, javaxList.length]);

  return (
    <section
      style={{
        margin: "22px 0",
        border: "1px solid #e2e8f0",
        borderRadius: 16,
        background: "#fff",
        boxShadow: "0 2px 5px rgba(15,23,42,.06)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "18px 20px",
          borderBottom: "1px solid #eef2f7",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "#1e40af" }}>
            Java Migration &amp; Dependency Compatibility Analysis
          </h3>
          <p style={{ margin: "5px 0 0", color: "#64748b", fontSize: 12 }}>
            Determines exact target dependencies, actions, source-code impact, and risks for target JDK {targetJavaVersion || "21"}.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {counts.ALL > 0 && <CopyAllDependenciesButton text={allDepsText} label="Copy All" />}
          <span
            style={{
              padding: "4px 10px",
              borderRadius: 7,
              background: "#eff6ff",
              color: "#2563eb",
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            {allRows.length} Total Dependencies
          </span>
        </div>
      </div>

      {/* Action Values Grid */}
      <div style={{ padding: "12px 20px", borderBottom: "1px solid #eef2f7", background: "#f8fafc", display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        {(
          [
            "MAJOR UPGRADE",
            "UPGRADE",
            "REPLACE",
            "REMOVE",
            "ALREADY COMPATIBLE",
            "MANUAL REVIEW",
          ] as DependencyAction[]
        ).map((act) => {
          const cfg = ACTION_CONFIG[act];
          return (
            <span
              key={act}
              style={{
                padding: "4px 10px",
                borderRadius: 8,
                background: cfg.background,
                color: cfg.text,
                border: `1px solid ${cfg.border}`,
                fontSize: 11,
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
              }}
            >
              <span>{act}:</span>
              <strong>{actionTotals[act] || 0}</strong>
            </span>
          );
        })}
      </div>

      {/* Categorization Tabs & Search Bar */}
      <div
        style={{
          padding: "12px 20px",
          borderBottom: "1px solid #f1f5f9",
          background: "#ffffff",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => setActiveTab("ALL")}
            style={{
              padding: "6px 12px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: activeTab === "ALL" ? 800 : 600,
              border: activeTab === "ALL" ? "1px solid #2563eb" : "1px solid #e2e8f0",
              background: activeTab === "ALL" ? "#eff6ff" : "#ffffff",
              color: activeTab === "ALL" ? "#1e40af" : "#64748b",
              cursor: "pointer",
            }}
          >
            All ({counts.ALL})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("Framework")}
            style={{
              padding: "6px 12px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: activeTab === "Framework" ? 800 : 600,
              border: activeTab === "Framework" ? "1px solid #bfdbfe" : "1px solid #e2e8f0",
              background: activeTab === "Framework" ? "#eff6ff" : "#ffffff",
              color: activeTab === "Framework" ? "#1d4ed8" : "#64748b",
              cursor: "pointer",
            }}
          >
            Framework ({counts.Framework})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("Library")}
            style={{
              padding: "6px 12px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: activeTab === "Library" ? 800 : 600,
              border: activeTab === "Library" ? "1px solid #a7f3d0" : "1px solid #e2e8f0",
              background: activeTab === "Library" ? "#ecfdf5" : "#ffffff",
              color: activeTab === "Library" ? "#047857" : "#64748b",
              cursor: "pointer",
            }}
          >
            Library ({counts.Library})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("Dependency")}
            style={{
              padding: "6px 12px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: activeTab === "Dependency" ? 800 : 600,
              border: activeTab === "Dependency" ? "1px solid #fde68a" : "1px solid #e2e8f0",
              background: activeTab === "Dependency" ? "#fffbeb" : "#ffffff",
              color: activeTab === "Dependency" ? "#b45309" : "#64748b",
              cursor: "pointer",
            }}
          >
            Dependency ({counts.Dependency})
          </button>
        </div>

        {/* Search Input */}
        <div style={{ position: "relative", width: 300 }}>
          <FaSearch
            style={{
              position: "absolute",
              left: 10,
              top: "50%",
              transform: "translateY(-50%)",
              color: "#94a3b8",
              fontSize: 12,
            }}
          />
          <input
            type="text"
            placeholder="Search dependency, action, reasoning..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              padding: "6px 12px 6px 30px",
              borderRadius: 8,
              border: "1px solid #cbd5e1",
              fontSize: 12,
              color: "#1e293b",
              background: "#ffffff",
              outline: "none",
              boxSizing: "border-box",
            }}
          />
        </div>
      </div>

      {/* Main Required Output Table */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 12 }}>
          <thead>
            <tr
              style={{
                borderBottom: "2px solid #e2e8f0",
                background: "#f8fafc",
                color: "#475569",
                fontSize: 11,
                fontWeight: 800,
                textTransform: "uppercase",
                letterSpacing: ".04em",
              }}
            >
              <th style={{ padding: "12px 16px", minWidth: 200 }}>Dependency</th>
              <th style={{ padding: "12px 12px", width: 120 }}>Current Version</th>
              <th style={{ padding: "12px 16px", minWidth: 200 }}>Target Dependency</th>
              <th style={{ padding: "12px 12px", width: 120 }}>Target Version</th>
              <th style={{ padding: "12px 12px", width: 140 }}>Action</th>
              <th style={{ padding: "12px 16px" }}>Reasoning</th>
              <th style={{ padding: "12px 16px" }}>Source Changes</th>
              <th style={{ padding: "12px 12px", width: 80 }}>Risk</th>
            </tr>
          </thead>
          <tbody>
            {/* Java Runtime special row */}
            {renderJavaRow && (
              <tr style={{ borderBottom: "1px solid #f1f5f9", background: "#faf5ff" }}>
                <td style={{ padding: "12px 16px", fontWeight: 700, color: "#1e293b" }}>
                  <div>Java Runtime</div>
                  <span
                    style={{
                      padding: "2px 6px",
                      borderRadius: 4,
                      fontSize: 10,
                      fontWeight: 700,
                      color: CATEGORY_COLORS.Runtime.text,
                      background: CATEGORY_COLORS.Runtime.background,
                      border: `1px solid ${CATEGORY_COLORS.Runtime.border}`,
                      display: "inline-block",
                      marginTop: 2,
                    }}
                  >
                    Runtime
                  </span>
                </td>
                <td style={{ padding: "12px 12px", color: "#475569" }}>{javaCurrent}</td>
                <td style={{ padding: "12px 16px", fontWeight: 700, color: "#1e293b" }}>Java Runtime</td>
                <td style={{ padding: "12px 12px", fontWeight: 700, color: "#047857" }}>
                  {targetJavaVersion || "21"}
                </td>
                <td style={{ padding: "12px 12px" }}>
                  <span
                    style={{
                      padding: "3px 8px",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 700,
                      color: ACTION_CONFIG["MAJOR UPGRADE"].text,
                      background: ACTION_CONFIG["MAJOR UPGRADE"].background,
                      border: `1px solid ${ACTION_CONFIG["MAJOR UPGRADE"].border}`,
                    }}
                  >
                    MAJOR UPGRADE
                  </span>
                </td>
                <td style={{ padding: "12px 16px", color: "#475569" }}>
                  Java platform target upgrade to JDK {targetJavaVersion || "21"} LTS release.
                </td>
                <td style={{ padding: "12px 16px", color: "#1e293b", fontWeight: 600 }}>
                  Set java.version compiler target property to {targetJavaVersion || "21"}.
                </td>
                <td style={{ padding: "12px 12px" }}>
                  <span style={{ padding: "2px 6px", borderRadius: 4, fontSize: 10, fontWeight: 800, color: "#991b1b", background: "#fef2f2" }}>
                    CRITICAL
                  </span>
                </td>
              </tr>
            )}

            {/* Dependency Rows */}
            {paginatedRows.length > 0 ? (
              paginatedRows.map((row, idx) => {
                const cColors = CATEGORY_COLORS[row.group] || CATEGORY_COLORS.Dependency;
                const aCfg = ACTION_CONFIG[row.action] || ACTION_CONFIG.UPGRADE;
                const rCfg = RISK_CONFIG[row.risk] || RISK_CONFIG.LOW;

                return (
                  <tr
                    key={`${row.dependency}-${idx}`}
                    style={{
                      borderBottom: "1px solid #f1f5f9",
                      transition: "background 0.15s ease",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "#ffffff")}
                  >
                    {/* Dependency */}
                    <td style={{ padding: "12px 16px", fontWeight: 700, color: "#1e293b", overflowWrap: "anywhere" }}>
                      <div>{row.dependency}</div>
                      <div style={{ display: "flex", gap: 4, marginTop: 3, flexWrap: "wrap" }}>
                        <span
                          style={{
                            padding: "2px 6px",
                            borderRadius: 4,
                            fontSize: 10,
                            fontWeight: 700,
                            color: cColors.text,
                            background: cColors.background,
                            border: `1px solid ${cColors.border}`,
                          }}
                        >
                          {row.group}
                        </span>
                        <span style={{ padding: "2px 6px", borderRadius: 4, fontSize: 10, fontWeight: 600, background: "#f1f5f9", color: "#475569" }}>
                          {row.dependencyType}
                        </span>
                      </div>
                    </td>

                    {/* Current Version */}
                    <td style={{ padding: "12px 12px", color: "#475569", fontWeight: 600 }}>
                      {row.currentVersion}
                    </td>

                    {/* Target Dependency */}
                    <td style={{ padding: "12px 16px", fontWeight: 700, color: row.action === "REPLACE" ? "#b45309" : "#1e293b", overflowWrap: "anywhere" }}>
                      {row.targetDependency}
                    </td>

                    {/* Target Version */}
                    <td style={{ padding: "12px 12px", fontWeight: 700, color: row.action === "REMOVE" ? "#dc2626" : "#047857" }}>
                      {row.targetVersion}
                    </td>

                    {/* Action */}
                    <td style={{ padding: "12px 12px" }}>
                      <span
                        style={{
                          padding: "4px 8px",
                          borderRadius: 6,
                          fontSize: 10,
                          fontWeight: 800,
                          color: aCfg.text,
                          background: aCfg.background,
                          border: `1px solid ${aCfg.border}`,
                          display: "inline-block",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {aCfg.label}
                      </span>
                    </td>

                    {/* Reasoning */}
                    <td style={{ padding: "12px 16px", color: "#475569" }}>
                      {row.reasoning}
                    </td>

                    {/* Source Changes */}
                    <td style={{ padding: "12px 16px", color: "#1e293b", fontWeight: 600 }}>
                      {row.sourceChanges}
                    </td>

                    {/* Risk */}
                    <td style={{ padding: "12px 12px" }}>
                      <span
                        style={{
                          padding: "2px 6px",
                          borderRadius: 4,
                          fontSize: 10,
                          fontWeight: 800,
                          color: rCfg.text,
                          background: rCfg.background,
                          border: `1px solid ${rCfg.border}`,
                        }}
                      >
                        {row.risk}
                      </span>
                    </td>
                  </tr>
                );
              })
            ) : !renderJavaRow ? (
              <tr>
                <td colSpan={8} style={{ padding: "26px 0", textAlign: "center", color: "#64748b", fontSize: 13 }}>
                  No dependencies match the selected filter.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div
        style={{
          padding: "12px 20px",
          borderTop: "1px solid #eef2f7",
          background: "#ffffff",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, color: "#64748b", fontSize: 12 }}>
          <span>
            Showing <strong>{filteredRows.length > 0 ? startIndex + 1 : 0}</strong> to{" "}
            <strong>{Math.min(startIndex + pageSize, filteredRows.length)}</strong> of{" "}
            <strong>{totalFilteredCount}</strong> items
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span>Per page:</span>
            <select
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
              style={{
                padding: "4px 8px",
                borderRadius: 6,
                border: "1px solid #cbd5e1",
                fontSize: 12,
                color: "#1e293b",
                background: "#ffffff",
                cursor: "pointer",
              }}
            >
              <option value={10}>10</option>
              <option value={15}>15</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>

        {totalPages > 1 && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button
              type="button"
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 30,
                height: 30,
                borderRadius: 6,
                border: "1px solid #cbd5e1",
                background: currentPage === 1 ? "#f1f5f9" : "#ffffff",
                color: currentPage === 1 ? "#94a3b8" : "#1e293b",
                cursor: currentPage === 1 ? "not-allowed" : "pointer",
                fontSize: 12,
              }}
              title="Previous Page"
            >
              <FaChevronLeft size={10} />
            </button>

            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter((page) => page === 1 || page === totalPages || Math.abs(page - currentPage) <= 2)
              .map((page, idx, arr) => {
                const prev = arr[idx - 1];
                const showEllipsis = prev && page - prev > 1;

                return (
                  <React.Fragment key={page}>
                    {showEllipsis && <span style={{ color: "#94a3b8", fontSize: 12 }}>...</span>}
                    <button
                      type="button"
                      onClick={() => setCurrentPage(page)}
                      style={{
                        minWidth: 30,
                        height: 30,
                        padding: "0 6px",
                        borderRadius: 6,
                        border: page === currentPage ? "1px solid #2563eb" : "1px solid #cbd5e1",
                        background: page === currentPage ? "#2563eb" : "#ffffff",
                        color: page === currentPage ? "#ffffff" : "#1e293b",
                        fontWeight: page === currentPage ? 700 : 500,
                        cursor: "pointer",
                        fontSize: 12,
                      }}
                    >
                      {page}
                    </button>
                  </React.Fragment>
                );
              })}

            <button
              type="button"
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 30,
                height: 30,
                borderRadius: 6,
                border: "1px solid #cbd5e1",
                background: currentPage === totalPages ? "#f1f5f9" : "#ffffff",
                color: currentPage === totalPages ? "#94a3b8" : "#1e293b",
                cursor: currentPage === totalPages ? "not-allowed" : "pointer",
                fontSize: 12,
              }}
              title="Next Page"
            >
              <FaChevronRight size={10} />
            </button>
          </div>
        )}
      </div>

      {/* REQUIRED FINAL SUMMARY PANEL */}
      <div style={{ padding: "20px 24px", borderTop: "2px solid #e2e8f0", background: "#f8fafc" }}>
        <h4 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 800, color: "#1e3a8a", display: "flex", alignItems: "center", gap: 8 }}>
          <FaCheckCircle color="#2563eb" /> FINAL DEPENDENCY MIGRATION SUMMARY
        </h4>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginBottom: 16 }}>
          <div style={{ background: "#ffffff", padding: "10px 14px", borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <span style={{ color: "#64748b", fontSize: 11, fontWeight: 700, display: "block" }}>TARGET JAVA</span>
            <strong style={{ fontSize: 15, color: "#1e293b" }}>{targetJavaVersion || "21"}</strong>
          </div>
          <div style={{ background: "#ffffff", padding: "10px 14px", borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <span style={{ color: "#64748b", fontSize: 11, fontWeight: 700, display: "block" }}>CURRENT JAVA</span>
            <strong style={{ fontSize: 15, color: "#1e293b" }}>{sourceJava}</strong>
          </div>
          <div style={{ background: "#ffffff", padding: "10px 14px", borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <span style={{ color: "#64748b", fontSize: 11, fontWeight: 700, display: "block" }}>CURRENT FRAMEWORK</span>
            <strong style={{ fontSize: 14, color: "#1e293b" }}>{currentFramework}</strong>
          </div>
          <div style={{ background: "#ffffff", padding: "10px 14px", borderRadius: 8, border: "1px solid #bfdbfe" }}>
            <span style={{ color: "#1d4ed8", fontSize: 11, fontWeight: 700, display: "block" }}>SELECTED TARGET FRAMEWORK</span>
            <strong style={{ fontSize: 14, color: "#1d4ed8" }}>Spring Boot {selectedBootVersion} (Spring Framework {selectedFrameworkVersion})</strong>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14, fontSize: 12 }}>
          {/* Major Migration Reasons */}
          <div style={{ background: "#ffffff", padding: "14px", borderRadius: 10, border: "1px solid #e2e8f0" }}>
            <h5 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 800, color: "#1e293b" }}>Major Migration Reasons</h5>
            <ul style={{ margin: 0, paddingLeft: 18, color: "#475569", lineHeight: 1.6 }}>
              <li>JDK {targetJavaVersion || "21"} runtime upgrade baseline alignment.</li>
              <li>Spring Boot {selectedBootVersion} dependency-management BOM integration.</li>
              {targetJavaNum >= 17 && javaxList.length > 0 ? (
                <li>Jakarta EE specification namespace shift (`javax.*` → `jakarta.*`).</li>
              ) : targetJavaNum < 17 ? (
                <li>Preserves Java EE 8 / `javax.*` namespace on Spring Boot 2.7.x LTS baseline.</li>
              ) : (
                <li>Compatible with modern runtime specifications without legacy javax namespace conversion.</li>
              )}
            </ul>
          </div>

          {/* Framework Changes */}
          <div style={{ background: "#ffffff", padding: "14px", borderRadius: 10, border: "1px solid #e2e8f0" }}>
            <h5 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 800, color: "#1e293b" }}>Framework Changes</h5>
            <p style={{ margin: 0, color: "#475569", lineHeight: 1.6 }}>
              Upgrades core Spring Boot parent from <strong>{currentBoot}</strong> to <strong>{selectedBootVersion}</strong> and Spring Framework to <strong>{selectedFrameworkVersion}</strong>.
            </p>
          </div>

          {/* Namespace Changes */}
          <div style={{ background: "#ffffff", padding: "14px", borderRadius: 10, border: "1px solid #e2e8f0" }}>
            <h5 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 800, color: "#1e293b" }}>Namespace Changes</h5>
            {javaxList.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: 18, color: "#b45309", fontWeight: 600, lineHeight: 1.6 }}>
                {javaxList.map((r, i) => (
                  <li key={i}>{r.dependency} → {r.targetDependency} ({r.sourceChanges})</li>
                ))}
              </ul>
            ) : (
              <p style={{ margin: 0, color: "#047857", fontWeight: 600 }}>
                {targetJavaNum < 17
                  ? `Java ${targetJavaNum} retains javax.* namespace support. No package replacements required.`
                  : "No legacy javax.* namespace replacements detected."}
              </p>
            )}
          </div>

          {/* Source-Code Impact */}
          <div style={{ background: "#ffffff", padding: "14px", borderRadius: 10, border: "1px solid #e2e8f0" }}>
            <h5 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 800, color: "#1e293b" }}>Source-Code Impact</h5>
            <p style={{ margin: 0, color: "#475569", lineHeight: 1.6 }}>
              {targetJavaNum >= 17
                ? `Package import updates for Jakarta EE classes (${javaxList.length > 0 ? `${javaxList.length} detected` : "none required"}), Spring Framework ${selectedFrameworkVersion} API deprecations, and custom repository query methods.`
                : `Package imports remain unchanged (javax.*). Source audits focused on Spring Framework ${selectedFrameworkVersion} compatibility and Java ${targetJavaNum} bytecode requirements.`}
            </p>
          </div>

          {/* Configuration Impact */}
          <div style={{ background: "#ffffff", padding: "14px", borderRadius: 10, border: "1px solid #e2e8f0" }}>
            <h5 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 800, color: "#1e293b" }}>Configuration Impact</h5>
            <p style={{ margin: 0, color: "#475569", lineHeight: 1.6 }}>
              {targetJavaNum >= 17 ? (
                <>
                  Update <code>application.properties</code>/<code>application.yml</code> for Boot 3 property keys, set{" "}
                  <code>&lt;java.version&gt;{targetJavaVersion || "21"}&lt;/java.version&gt;</code>, and configure Hibernate 6 dialects.
                </>
              ) : (
                <>
                  Update configuration for Spring Boot 2.7 properties, set{" "}
                  <code>&lt;java.version&gt;{targetJavaVersion || "11"}&lt;/java.version&gt;</code>, and retain Hibernate 5 dialects.
                </>
              )}
            </p>
          </div>

          {/* Overall Dependency Migration Assessment */}
          <div style={{ background: "#ffffff", padding: "14px", borderRadius: 10, border: `1px solid ${RISK_CONFIG[overallAssessment].border}` }}>
            <h5 style={{ margin: "0 0 6px", fontSize: 13, fontWeight: 800, color: "#1e293b" }}>
              Overall Dependency Migration Assessment
            </h5>
            <span
              style={{
                padding: "3px 10px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 800,
                color: RISK_CONFIG[overallAssessment].text,
                background: RISK_CONFIG[overallAssessment].background,
                display: "inline-block",
                marginBottom: 8,
              }}
            >
              {overallAssessment} RISK
            </span>
            <p style={{ margin: 0, color: "#475569", lineHeight: 1.5 }}>
              {overallAssessmentExplanation}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
