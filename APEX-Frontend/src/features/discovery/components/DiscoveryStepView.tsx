import React, { useState, useEffect, useMemo, useRef } from "react";
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
  FaRegClock,
  FaArrowLeft,
  FaTimes,
  FaDatabase,
  FaShieldAlt,
  FaWrench,
  FaVial,
  FaEye,
  FaNetworkWired,
  FaReact,
  FaAngular,
  FaVuejs,
} from "react-icons/fa";
import {
  renderForwardButtonLabel,
} from "@/shared/components/wizard";
import { wizardStyles as styles } from "@/shared/components/wizard/wizardStyles";
import type { RepoAnalysis, RepoFile, RepoInfo, DiscoveredApiEndpoint } from "@/shared/types/domain";
import { getFileContent, getDiscoveryFileContent } from "../services/discoveryService";
import { getLocalProjectFileContent } from "@/features/connect/services/connectService";
import { getUserSettings } from "@/features/admin/services/adminService";
import type {
  DocumentGenerationPromptSettings,
  DocumentPromptType,
} from "@/features/admin/services/adminService";
import { DiscoveryLoader } from "./DiscoveryLoader";
import type { useDiscoveryState } from "../hooks/useDiscoveryState";
import "./DiscoveryDashboard.css";

export interface DetectedFrameworkDetail {
  id: string;
  name: string;
  type: string;
  status: string;
  category: "spring" | "database" | "tool" | "test" | "security" | "frontend" | "generic";
  tags: { label: string; color: "purple" | "gray" | "blue" | "green" | "amber" }[];
}

function renderFrameworkIcon(category: string, id?: string) {
  if (id === "angular" || id === "angular-router") {
    return <FaAngular size={15} />;
  }
  if (id === "react" || id === "react-router") {
    return <FaReact size={15} />;
  }
  if (id === "vue") {
    return <FaVuejs size={15} />;
  }
  switch (category) {
    case "spring":
      return <FaLeaf size={15} />;
    case "frontend":
      return <FaCode size={15} />;
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

// Canonical technology mapping table for robust deduplication across different sources and namings
const CANONICAL_TECH_MAP: Record<string, string> = {
  // Spring Ecosystem
  "spring-boot": "spring-boot",
  "springboot": "spring-boot",
  "spring-framework": "spring-framework",
  "springframework": "spring-framework",
  "spring-core": "spring-framework",
  "springcore": "spring-framework",
  "spring-security": "spring-security",
  "springsecurity": "spring-security",
  "security": "spring-security",
  "spring-cloud": "spring-cloud",
  "springcloud": "spring-cloud",
  "spring-data": "spring-data",
  "springdata": "spring-data",
  "spring-data-jpa": "spring-data-jpa",
  "springdatajpa": "spring-data-jpa",
  "jpa-hibernate": "jpa-hibernate",
  "jpahibernate": "jpa-hibernate",
  "hibernate": "hibernate",
  "hibernate-orm": "hibernate",
  "hibernateorm": "hibernate",

  // Frontend Frameworks & Libraries
  "angular": "angular",
  "@angular/core": "angular",
  "angular-core": "angular",
  "angularcore": "angular",
  "angular-router": "angular-router",
  "@angular/router": "angular-router",
  "angularrouter": "angular-router",
  "react": "react",
  "react-dom": "react",
  "reactjs": "react",
  "react-router": "react-router",
  "react-router-dom": "react-router",
  "reactrouter": "react-router",
  "reactrouterdom": "react-router",
  "vue": "vue",
  "vuejs": "vue",
  "vue-router": "vue-router",
  "vuerouter": "vue-router",
  "svelte": "svelte",
  "sveltejs": "svelte",
  "next": "nextjs",
  "nextjs": "nextjs",
  "next.js": "nextjs",
  "redux": "redux",
  "@reduxjs/toolkit": "redux",
  "reduxtoolkit": "redux",

  // Build / Tooling / Styling
  "typescript": "typescript",
  "vite": "vite",
  "webpack": "webpack",
  "tailwindcss": "tailwindcss",
  "tailwind": "tailwindcss",
  "tailwind-css": "tailwindcss",
  "tailwind-styling": "tailwindcss",
  "axios": "axios",
  "lombok": "lombok",
  "project-lombok": "lombok",
  "projectlombok": "lombok",

  // Database / Drivers / Migrations / Caches
  "postgresql": "postgresql",
  "postgres": "postgresql",
  "mysql": "mysql",
  "mysql-connector": "mysql",
  "mysql-connector-j": "mysql",
  "liquibase": "liquibase",
  "flyway": "flyway",
  "redis": "redis",

  // API Documentation
  "openapi": "springdoc-openapi",
  "springdoc": "springdoc-openapi",
  "springdoc-openapi": "springdoc-openapi",
  "swagger": "springdoc-openapi",

  // Testing Frameworks
  "junit": "junit",
  "junit5": "junit",
  "junit4": "junit",
  "jupiter": "junit",
  "mockito": "mockito",
  "testng": "testng",
  "jest": "jest",
  "vitest": "vitest",
  "cypress": "cypress",
  "playwright": "playwright",
  "@playwright/test": "playwright",
};

function normalizeTechKey(val: string): string {
  return (val || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function getCanonicalTechId(idOrName: string): string {
  const norm = normalizeTechKey(idOrName);
  return CANONICAL_TECH_MAP[norm] || CANONICAL_TECH_MAP[idOrName.toLowerCase().trim()] || norm;
}

function formatTechDisplayName(raw: string): string {
  if (!raw) return "Framework";
  const friendly: Record<string, string> = {
    "spring-boot": "Spring Boot",
    "spring-framework": "Spring Framework",
    "spring-security": "Spring Security",
    "spring-cloud": "Spring Cloud",
    "spring-data": "Spring Data",
    "spring-data-jpa": "Spring Data JPA",
    "hibernate": "Hibernate ORM",
    "jpa-hibernate": "Spring Data JPA / Hibernate",
    "angular": "Angular",
    "angular-router": "Angular Router",
    "react": "React",
    "react-router": "React Router",
    "vue": "Vue.js",
    "svelte": "Svelte",
    "typescript": "TypeScript",
    "vite": "Vite",
    "webpack": "Webpack",
    "tailwindcss": "Tailwind CSS",
    "axios": "Axios",
    "next": "Next.js",
    "nextjs": "Next.js",
    "redux": "Redux",
    "junit": "JUnit Testing",
    "mockito": "Mockito",
    "testng": "TestNG",
    "jest": "Jest Testing",
    "vitest": "Vitest",
    "cypress": "Cypress",
    "playwright": "Playwright",
    "springdoc-openapi": "Springdoc OpenAPI",
    "liquibase": "Liquibase",
    "flyway": "Flyway",
    "postgresql": "PostgreSQL JDBC",
    "mysql": "MySQL Connector",
    "lombok": "Project Lombok",
    "redis": "Redis Cache",
  };
  const key = raw.toLowerCase().trim();
  if (friendly[key]) return friendly[key];
  return raw
    .split(/[-_\s]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function extractDetectedFrameworks(repoAnalysis: RepoAnalysis | null): DetectedFrameworkDetail[] {
  if (!repoAnalysis) {
    return [];
  }
  const items: DetectedFrameworkDetail[] = [];
  const seenCanonicalKeys = new Set<string>();
  const seenAliases = new Set<string>();

  function registerItem(item: DetectedFrameworkDetail, aliases: string[] = []) {
    const canonKey = getCanonicalTechId(item.id) || normalizeTechKey(item.id);
    seenCanonicalKeys.add(canonKey);
    seenAliases.add(normalizeTechKey(item.id));
    seenAliases.add(normalizeTechKey(item.name));
    aliases.forEach((a) => {
      seenAliases.add(normalizeTechKey(a));
      const aCanon = getCanonicalTechId(a);
      if (aCanon) seenCanonicalKeys.add(aCanon);
    });
    items.push(item);
  }

  function isAlreadyRepresented(candidate: string): boolean {
    if (!candidate) return false;
    const norm = normalizeTechKey(candidate);
    if (seenAliases.has(norm)) return true;
    const canon = getCanonicalTechId(candidate);
    if (canon && seenCanonicalKeys.has(canon)) return true;
    return false;
  }

  const deps = repoAnalysis?.dependencies || [];
  const feDeps = repoAnalysis?.frontend_dependencies || (repoAnalysis as any)?.frontendDependencies || [];
  const allDeps = [...deps, ...feDeps];

  const depCoords = allDeps.map((d) => `${d.group_id || ""}:${d.artifact_id || ""}`.toLowerCase());
  const depGroups = allDeps.map((d) => (d.group_id || "").toLowerCase());
  const depArtifacts = allDeps.map((d) => (d.artifact_id || "").toLowerCase());
  const depNames = allDeps.map((d) => (d.name || d.artifact_id || "").toLowerCase());
  const rawFrameworks = (repoAnalysis?.frameworks || []).map((f) => f.toLowerCase());
  const detectedFrameworksRaw = (repoAnalysis?.detected_frameworks || []).map((df) =>
    (typeof df === "string" ? df : df.name || "").toLowerCase()
  );

  // 1. Spring Boot (Backend Framework)
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
    deps.some((d) => (d.group_id || "").toLowerCase() === "org.springframework.boot") ||
    deps.some((d) => `${d.group_id || ""}:${d.artifact_id || ""}`.toLowerCase().startsWith("org.springframework.boot:"));

  if (isSpringBoot && !isAlreadyRepresented("spring-boot")) {
    registerItem(
      {
        id: "spring-boot",
        name: springBootVersion ? `Spring Boot ${springBootVersion}` : "Spring Boot",
        type: "Backend Framework",
        status: springBootVersion ? `v${springBootVersion}` : "Detected",
        category: "spring",
        tags: [
          { label: "FRAMEWORK", color: "purple" },
          { label: "SPRING BOOT", color: "green" },
          { label: "JAVA", color: "gray" },
        ],
      },
      ["spring-boot", "springboot", "spring-framework", "springframework"]
    );
  } else if (!isSpringBoot) {
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
      deps.some((d) => (d.group_id || "").toLowerCase().includes("org.springframework"));

    if (isSpring && !isAlreadyRepresented("spring-framework")) {
      registerItem(
        {
          id: "spring-framework",
          name: springVersion ? `Spring Framework ${springVersion}` : "Spring Framework",
          type: "Backend Framework",
          status: springVersion ? `v${springVersion}` : "Detected",
          category: "spring",
          tags: [
            { label: "FRAMEWORK", color: "purple" },
            { label: "SPRING", color: "green" },
            { label: "JAVA", color: "gray" },
          ],
        },
        ["spring-framework", "springframework", "spring-core"]
      );
    }
  }

  // 3. Angular (Frontend Framework) - Primary evidence: @angular/core
  const angularDep = allDeps.find(
    (d) =>
      d.name?.toLowerCase() === "@angular/core" ||
      (d.group_id?.toLowerCase() === "@angular" && d.artifact_id?.toLowerCase() === "core")
  );
  const isAngular =
    Boolean(angularDep) ||
    rawFrameworks.includes("angular") ||
    detectedFrameworksRaw.some((f) => f === "angular");

  if (isAngular && !isAlreadyRepresented("angular")) {
    const angularVersion =
      angularDep?.resolvedVersion ||
      angularDep?.current_version ||
      (angularDep?.declaredVersion ? angularDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "angular",
        name: angularVersion && !angularVersion.toLowerCase().includes("unknown") ? `Angular ${angularVersion}` : "Angular",
        type: "Frontend Framework",
        status: angularVersion && !angularVersion.toLowerCase().includes("unknown") ? `v${angularVersion}` : "Detected",
        category: "frontend",
        tags: [
          { label: "FRAMEWORK", color: "purple" },
          { label: "ANGULAR", color: "amber" },
          { label: "SPA", color: "blue" },
        ],
      },
      ["angular", "@angular/core", "angular-core"]
    );
  }

  // Angular Router (kept strictly distinct from Angular)
  const angularRouterDep = allDeps.find(
    (d) =>
      d.name?.toLowerCase() === "@angular/router" ||
      (d.group_id?.toLowerCase() === "@angular" && d.artifact_id?.toLowerCase() === "router")
  );
  if ((angularRouterDep || rawFrameworks.includes("angular-router")) && !isAlreadyRepresented("angular-router")) {
    const routerVer =
      angularRouterDep?.resolvedVersion ||
      angularRouterDep?.current_version ||
      (angularRouterDep?.declaredVersion ? angularRouterDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "angular-router",
        name: routerVer && !routerVer.toLowerCase().includes("unknown") ? `Angular Router ${routerVer}` : "Angular Router",
        type: "Routing Library",
        status: routerVer && !routerVer.toLowerCase().includes("unknown") ? `v${routerVer}` : "Detected",
        category: "frontend",
        tags: [
          { label: "ROUTING", color: "blue" },
          { label: "LIBRARY", color: "gray" },
        ],
      },
      ["angular-router", "@angular/router"]
    );
  }

  // React (Frontend Framework) - Primary evidence: react / react-dom
  const reactDep = allDeps.find(
    (d) => d.name?.toLowerCase() === "react" || d.artifact_id?.toLowerCase() === "react"
  );
  const reactDomDep = allDeps.find(
    (d) => d.name?.toLowerCase() === "react-dom" || d.artifact_id?.toLowerCase() === "react-dom"
  );
  const isReact =
    Boolean(reactDep) ||
    Boolean(reactDomDep) ||
    rawFrameworks.includes("react") ||
    detectedFrameworksRaw.some((f) => f === "react");

  if (isReact && !isAlreadyRepresented("react")) {
    const rDep = reactDep || reactDomDep;
    const reactVer =
      rDep?.resolvedVersion ||
      rDep?.current_version ||
      (rDep?.declaredVersion ? rDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "react",
        name: reactVer && !reactVer.toLowerCase().includes("unknown") ? `React ${reactVer}` : "React",
        type: "Frontend Framework",
        status: reactVer && !reactVer.toLowerCase().includes("unknown") ? `v${reactVer}` : "Detected",
        category: "frontend",
        tags: [
          { label: "FRAMEWORK", color: "purple" },
          { label: "REACT", color: "blue" },
          { label: "UI", color: "green" },
        ],
      },
      ["react", "react-dom", "reactjs"]
    );
  }

  // React Router (kept strictly distinct from React)
  const reactRouterDep = allDeps.find(
    (d) =>
      d.name?.toLowerCase() === "react-router" ||
      d.name?.toLowerCase() === "react-router-dom" ||
      d.artifact_id?.toLowerCase() === "react-router" ||
      d.artifact_id?.toLowerCase() === "react-router-dom"
  );
  if ((reactRouterDep || rawFrameworks.includes("react-router")) && !isAlreadyRepresented("react-router")) {
    const rrVer =
      reactRouterDep?.resolvedVersion ||
      reactRouterDep?.current_version ||
      (reactRouterDep?.declaredVersion ? reactRouterDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "react-router",
        name: rrVer && !rrVer.toLowerCase().includes("unknown") ? `React Router ${rrVer}` : "React Router",
        type: "Routing Library",
        status: rrVer && !rrVer.toLowerCase().includes("unknown") ? `v${rrVer}` : "Detected",
        category: "frontend",
        tags: [
          { label: "ROUTING", color: "blue" },
          { label: "LIBRARY", color: "gray" },
        ],
      },
      ["react-router", "react-router-dom"]
    );
  }

  // Vue.js
  const vueDep = allDeps.find(
    (d) => d.name?.toLowerCase() === "vue" || d.artifact_id?.toLowerCase() === "vue"
  );
  if ((vueDep || rawFrameworks.includes("vue")) && !isAlreadyRepresented("vue")) {
    const vueVer =
      vueDep?.resolvedVersion ||
      vueDep?.current_version ||
      (vueDep?.declaredVersion ? vueDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "vue",
        name: vueVer && !vueVer.toLowerCase().includes("unknown") ? `Vue.js ${vueVer}` : "Vue.js",
        type: "Frontend Framework",
        status: vueVer && !vueVer.toLowerCase().includes("unknown") ? `v${vueVer}` : "Detected",
        category: "frontend",
        tags: [
          { label: "FRAMEWORK", color: "purple" },
          { label: "VUE", color: "green" },
        ],
      },
      ["vue", "vuejs"]
    );
  }

  // Svelte
  const svelteDep = allDeps.find(
    (d) => d.name?.toLowerCase() === "svelte" || d.artifact_id?.toLowerCase() === "svelte"
  );
  if ((svelteDep || rawFrameworks.includes("svelte")) && !isAlreadyRepresented("svelte")) {
    const svelteVer =
      svelteDep?.resolvedVersion ||
      svelteDep?.current_version ||
      (svelteDep?.declaredVersion ? svelteDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "svelte",
        name: svelteVer && !svelteVer.toLowerCase().includes("unknown") ? `Svelte ${svelteVer}` : "Svelte",
        type: "Frontend Framework",
        status: svelteVer && !svelteVer.toLowerCase().includes("unknown") ? `v${svelteVer}` : "Detected",
        category: "frontend",
        tags: [
          { label: "FRAMEWORK", color: "purple" },
          { label: "SVELTE", color: "amber" },
        ],
      },
      ["svelte", "sveltejs"]
    );
  }

  // 4. Spring Data JPA / Hibernate (Carefully merged when representing the same stack)
  const hasSpringDataJpa = deps.some((a) => {
    const aid = (a.artifact_id || "").toLowerCase();
    const gid = (a.group_id || "").toLowerCase();
    return aid.includes("spring-boot-starter-data-jpa") || aid.includes("spring-data-jpa") || `${gid}:${aid}`.includes("data-jpa");
  });

  const hasHibernate =
    rawFrameworks.includes("hibernate") ||
    deps.some((g) => (g.group_id || "").toLowerCase().includes("hibernate")) ||
    deps.some((c) => `${c.group_id || ""}:${c.artifact_id || ""}`.toLowerCase().includes("hibernate"));

  const hasSpringDataOther =
    (rawFrameworks.includes("spring-data") || deps.some((d) => (d.artifact_id || "").toLowerCase().includes("spring-data"))) &&
    !hasSpringDataJpa;

  if (hasSpringDataJpa) {
    // Both Spring Data JPA and Hibernate represent the shared persistence layer
    registerItem(
      {
        id: "jpa-hibernate",
        name: "Spring Data JPA / Hibernate",
        type: "Persistence Framework",
        status: "Detected",
        category: "database",
        tags: [
          { label: "ORM", color: "blue" },
          { label: "JPA", color: "purple" },
          { label: "DATABASE", color: "gray" },
        ],
      },
      ["spring-data", "spring-data-jpa", "springdata", "springdatajpa", "hibernate", "jpa", "jpa-hibernate"]
    );
  } else {
    // Distinguishable separate representations when not combined as Spring Data JPA
    if (hasHibernate && !isAlreadyRepresented("hibernate")) {
      registerItem(
        {
          id: "hibernate",
          name: "Hibernate ORM",
          type: "Persistence Framework",
          status: "Detected",
          category: "database",
          tags: [
            { label: "ORM", color: "blue" },
            { label: "HIBERNATE", color: "purple" },
            { label: "DATABASE", color: "gray" },
          ],
        },
        ["hibernate", "jpa", "hibernate-orm"]
      );
    }
    if (hasSpringDataOther && !isAlreadyRepresented("spring-data")) {
      registerItem(
        {
          id: "spring-data",
          name: "Spring Data",
          type: "Data Access Framework",
          status: "Detected",
          category: "database",
          tags: [
            { label: "SPRING DATA", color: "blue" },
            { label: "DATABASE", color: "gray" },
          ],
        },
        ["spring-data", "springdata"]
      );
    }
  }

  // 5. Spring Security (Guaranteed single canonical card)
  const hasSecurity =
    rawFrameworks.includes("spring-security") ||
    deps.some((c) => {
      const coord = `${c.group_id || ""}:${c.artifact_id || ""}`.toLowerCase();
      return coord.includes("spring-security") || coord.includes("spring-boot-starter-security");
    });

  if (hasSecurity && !isAlreadyRepresented("spring-security")) {
    registerItem(
      {
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
      },
      ["spring-security", "springsecurity", "security"]
    );
  }

  // 6. Spring Cloud
  const hasSpringCloud =
    rawFrameworks.includes("spring-cloud") ||
    depCoords.some((c) => c.startsWith("org.springframework.cloud:"));

  if (hasSpringCloud && !isAlreadyRepresented("spring-cloud")) {
    registerItem(
      {
        id: "spring-cloud",
        name: "Spring Cloud",
        type: "Cloud Framework",
        status: "Detected",
        category: "spring",
        tags: [
          { label: "FRAMEWORK", color: "purple" },
          { label: "CLOUD", color: "blue" },
          { label: "JAVA", color: "gray" },
        ],
      },
      ["spring-cloud", "springcloud"]
    );
  }

  // 7. Database Drivers & Migrations
  const postgresDep = deps.find((d) => d.group_id?.includes("postgresql") || d.artifact_id?.includes("postgresql"));
  if (postgresDep && !isAlreadyRepresented("postgresql")) {
    registerItem(
      {
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
      },
      ["postgresql", "postgres"]
    );
  }

  const mysqlDep = deps.find((d) => d.group_id?.includes("mysql") || d.artifact_id?.includes("mysql"));
  if (mysqlDep && !isAlreadyRepresented("mysql")) {
    registerItem(
      {
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
      },
      ["mysql", "mysql-connector", "mysql-connector-j"]
    );
  }

  const liquibaseDep = deps.find((d) => d.artifact_id?.toLowerCase().includes("liquibase"));
  if ((liquibaseDep || rawFrameworks.includes("liquibase")) && !isAlreadyRepresented("liquibase")) {
    registerItem(
      {
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
      },
      ["liquibase"]
    );
  }

  const flywayDep = deps.find((d) => d.artifact_id?.toLowerCase().includes("flyway"));
  if ((flywayDep || rawFrameworks.includes("flyway")) && !isAlreadyRepresented("flyway")) {
    registerItem(
      {
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
      },
      ["flyway"]
    );
  }

  // Redis Cache
  const redisDep = deps.find(
    (d) => d.artifact_id?.toLowerCase().includes("redis") || d.group_id?.toLowerCase().includes("redis")
  );
  if (redisDep && !isAlreadyRepresented("redis")) {
    registerItem(
      {
        id: "redis",
        name: "Redis Cache",
        type: "In-Memory Store",
        status: "Detected",
        category: "database",
        tags: [
          { label: "CACHE", color: "amber" },
          { label: "NOSQL", color: "gray" },
        ],
      },
      ["redis"]
    );
  }

  // 8. OpenAPI / Swagger (Springdoc)
  const springdocDep = deps.find(
    (d) =>
      d.artifact_id?.toLowerCase().includes("springdoc") ||
      d.group_id?.toLowerCase().includes("springdoc") ||
      d.group_id?.toLowerCase().includes("swagger") ||
      d.artifact_id?.toLowerCase().includes("swagger")
  );
  if (
    (springdocDep || rawFrameworks.includes("springdoc-openapi") || rawFrameworks.includes("swagger")) &&
    !isAlreadyRepresented("springdoc-openapi")
  ) {
    registerItem(
      {
        id: "springdoc-openapi",
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
      },
      ["springdoc-openapi", "springdoc", "swagger", "openapi"]
    );
  }

  // 9. Project Lombok
  const lombokDep = deps.find(
    (d) => d.artifact_id?.toLowerCase().includes("lombok") || d.group_id?.toLowerCase().includes("lombok")
  );
  if ((lombokDep || rawFrameworks.includes("lombok")) && !isAlreadyRepresented("lombok")) {
    registerItem(
      {
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
      },
      ["lombok", "project-lombok", "projectlombok"]
    );
  }

  // 10. Frontend Build Tools & Styling
  // TypeScript
  const tsDep = allDeps.find(
    (d) => d.name?.toLowerCase() === "typescript" || d.artifact_id?.toLowerCase() === "typescript"
  );
  if ((tsDep || rawFrameworks.includes("typescript")) && !isAlreadyRepresented("typescript")) {
    const tsVer =
      tsDep?.resolvedVersion ||
      tsDep?.current_version ||
      (tsDep?.declaredVersion ? tsDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "typescript",
        name: tsVer && !tsVer.toLowerCase().includes("unknown") ? `TypeScript ${tsVer}` : "TypeScript",
        type: "Language / Tooling",
        status: tsVer && !tsVer.toLowerCase().includes("unknown") ? `v${tsVer}` : "Detected",
        category: "tool",
        tags: [
          { label: "TOOL", color: "purple" },
          { label: "TYPESCRIPT", color: "blue" },
        ],
      },
      ["typescript"]
    );
  }

  // Vite
  const viteDep = allDeps.find(
    (d) => d.name?.toLowerCase() === "vite" || d.artifact_id?.toLowerCase() === "vite"
  );
  if ((viteDep || rawFrameworks.includes("vite")) && !isAlreadyRepresented("vite")) {
    const viteVer =
      viteDep?.resolvedVersion ||
      viteDep?.current_version ||
      (viteDep?.declaredVersion ? viteDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "vite",
        name: viteVer && !viteVer.toLowerCase().includes("unknown") ? `Vite ${viteVer}` : "Vite",
        type: "Build Tool",
        status: viteVer && !viteVer.toLowerCase().includes("unknown") ? `v${viteVer}` : "Detected",
        category: "tool",
        tags: [
          { label: "BUILD TOOL", color: "purple" },
          { label: "BUNDLER", color: "amber" },
        ],
      },
      ["vite"]
    );
  }

  // Webpack
  const webpackDep = allDeps.find(
    (d) => d.name?.toLowerCase() === "webpack" || d.artifact_id?.toLowerCase() === "webpack"
  );
  if ((webpackDep || rawFrameworks.includes("webpack")) && !isAlreadyRepresented("webpack")) {
    const wpVer =
      webpackDep?.resolvedVersion ||
      webpackDep?.current_version ||
      (webpackDep?.declaredVersion ? webpackDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "webpack",
        name: wpVer && !wpVer.toLowerCase().includes("unknown") ? `Webpack ${wpVer}` : "Webpack",
        type: "Build Tool",
        status: wpVer && !wpVer.toLowerCase().includes("unknown") ? `v${wpVer}` : "Detected",
        category: "tool",
        tags: [
          { label: "BUILD TOOL", color: "purple" },
          { label: "BUNDLER", color: "gray" },
        ],
      },
      ["webpack"]
    );
  }

  // Tailwind CSS
  const tailwindDep = allDeps.find(
    (d) => d.name?.toLowerCase() === "tailwindcss" || d.artifact_id?.toLowerCase() === "tailwindcss"
  );
  if ((tailwindDep || rawFrameworks.includes("tailwindcss")) && !isAlreadyRepresented("tailwindcss")) {
    const twVer =
      tailwindDep?.resolvedVersion ||
      tailwindDep?.current_version ||
      (tailwindDep?.declaredVersion ? tailwindDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "tailwindcss",
        name: twVer && !twVer.toLowerCase().includes("unknown") ? `Tailwind CSS ${twVer}` : "Tailwind CSS",
        type: "Styling Tool",
        status: twVer && !twVer.toLowerCase().includes("unknown") ? `v${twVer}` : "Detected",
        category: "tool",
        tags: [
          { label: "STYLING", color: "blue" },
          { label: "CSS", color: "green" },
        ],
      },
      ["tailwindcss", "tailwind"]
    );
  }

  // Axios
  const axiosDep = allDeps.find(
    (d) => d.name?.toLowerCase() === "axios" || d.artifact_id?.toLowerCase() === "axios"
  );
  if ((axiosDep || rawFrameworks.includes("axios")) && !isAlreadyRepresented("axios")) {
    const axVer =
      axiosDep?.resolvedVersion ||
      axiosDep?.current_version ||
      (axiosDep?.declaredVersion ? axiosDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "axios",
        name: axVer && !axVer.toLowerCase().includes("unknown") ? `Axios ${axVer}` : "Axios",
        type: "HTTP Client Library",
        status: axVer && !axVer.toLowerCase().includes("unknown") ? `v${axVer}` : "Detected",
        category: "tool",
        tags: [
          { label: "HTTP CLIENT", color: "blue" },
          { label: "LIBRARY", color: "gray" },
        ],
      },
      ["axios"]
    );
  }

  // Next.js
  const nextDep = allDeps.find(
    (d) => d.name?.toLowerCase() === "next" || d.artifact_id?.toLowerCase() === "next"
  );
  if ((nextDep || rawFrameworks.includes("next")) && !isAlreadyRepresented("next")) {
    const nextVer =
      nextDep?.resolvedVersion ||
      nextDep?.current_version ||
      (nextDep?.declaredVersion ? nextDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "nextjs",
        name: nextVer && !nextVer.toLowerCase().includes("unknown") ? `Next.js ${nextVer}` : "Next.js",
        type: "Full-Stack Framework",
        status: nextVer && !nextVer.toLowerCase().includes("unknown") ? `v${nextVer}` : "Detected",
        category: "frontend",
        tags: [
          { label: "FRAMEWORK", color: "purple" },
          { label: "SSR", color: "blue" },
        ],
      },
      ["next", "nextjs"]
    );
  }

  // Redux
  const reduxDep = allDeps.find(
    (d) =>
      d.name?.toLowerCase() === "redux" ||
      d.name?.toLowerCase() === "@reduxjs/toolkit" ||
      d.artifact_id?.toLowerCase() === "redux"
  );
  if ((reduxDep || rawFrameworks.includes("redux")) && !isAlreadyRepresented("redux")) {
    const redVer =
      reduxDep?.resolvedVersion ||
      reduxDep?.current_version ||
      (reduxDep?.declaredVersion ? reduxDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "redux",
        name: redVer && !redVer.toLowerCase().includes("unknown") ? `Redux ${redVer}` : "Redux",
        type: "State Management",
        status: redVer && !redVer.toLowerCase().includes("unknown") ? `v${redVer}` : "Detected",
        category: "frontend",
        tags: [
          { label: "STATE", color: "purple" },
          { label: "LIBRARY", color: "gray" },
        ],
      },
      ["redux", "@reduxjs/toolkit"]
    );
  }

  // 11. Testing Frameworks & Tools (strictly validated against actual dependency metadata)
  // JUnit: MUST have actual test dependency evidence (never inferred merely from generic test dirs)
  const junitDep = deps.find(
    (d) =>
      d.artifact_id?.toLowerCase().includes("junit") ||
      d.group_id?.toLowerCase().includes("junit") ||
      d.artifact_id?.toLowerCase().includes("jupiter")
  );
  const hasJunit =
    Boolean(junitDep) ||
    rawFrameworks.includes("junit") ||
    depCoords.some((c) => c.includes("junit") || c.includes("jupiter"));

  if (hasJunit && !isAlreadyRepresented("junit")) {
    const isJunit5 = depCoords.some((c) => c.includes("jupiter")) || junitDep?.artifact_id?.includes("jupiter");
    registerItem(
      {
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
      },
      ["junit", "jupiter", "junit5", "junit4"]
    );
  }

  // Mockito
  const mockitoDep = deps.find(
    (d) => d.artifact_id?.toLowerCase().includes("mockito") || d.group_id?.toLowerCase().includes("mockito")
  );
  if ((mockitoDep || rawFrameworks.includes("mockito")) && !isAlreadyRepresented("mockito")) {
    registerItem(
      {
        id: "mockito",
        name: "Mockito",
        type: "Mocking Framework",
        status:
          mockitoDep?.current_version && !mockitoDep.current_version.toLowerCase().includes("unknown")
            ? `v${mockitoDep.current_version}`
            : "Detected",
        category: "test",
        tags: [
          { label: "TESTING", color: "purple" },
          { label: "MOCK", color: "gray" },
        ],
      },
      ["mockito"]
    );
  }

  // TestNG
  const testngDep = deps.find(
    (d) => d.artifact_id?.toLowerCase().includes("testng") || d.group_id?.toLowerCase().includes("testng")
  );
  if (testngDep && !isAlreadyRepresented("testng")) {
    registerItem(
      {
        id: "testng",
        name: "TestNG",
        type: "Testing Framework",
        status:
          testngDep.current_version && !testngDep.current_version.toLowerCase().includes("unknown")
            ? `v${testngDep.current_version}`
            : "Detected",
        category: "test",
        tags: [
          { label: "TESTING", color: "purple" },
          { label: "UNIT TEST", color: "gray" },
        ],
      },
      ["testng"]
    );
  }

  // Frontend Testing
  const jestDep = allDeps.find((d) => d.name?.toLowerCase() === "jest" || d.artifact_id?.toLowerCase() === "jest");
  if ((jestDep || rawFrameworks.includes("jest")) && !isAlreadyRepresented("jest")) {
    const jVer =
      jestDep?.resolvedVersion ||
      jestDep?.current_version ||
      (jestDep?.declaredVersion ? jestDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "jest",
        name: jVer && !jVer.toLowerCase().includes("unknown") ? `Jest ${jVer}` : "Jest Testing",
        type: "Testing Tool",
        status: jVer && !jVer.toLowerCase().includes("unknown") ? `v${jVer}` : "Detected",
        category: "test",
        tags: [
          { label: "TESTING", color: "purple" },
          { label: "UNIT TEST", color: "gray" },
        ],
      },
      ["jest"]
    );
  }

  const vitestDep = allDeps.find((d) => d.name?.toLowerCase() === "vitest" || d.artifact_id?.toLowerCase() === "vitest");
  if ((vitestDep || rawFrameworks.includes("vitest")) && !isAlreadyRepresented("vitest")) {
    const vVer =
      vitestDep?.resolvedVersion ||
      vitestDep?.current_version ||
      (vitestDep?.declaredVersion ? vitestDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "vitest",
        name: vVer && !vVer.toLowerCase().includes("unknown") ? `Vitest ${vVer}` : "Vitest",
        type: "Testing Tool",
        status: vVer && !vVer.toLowerCase().includes("unknown") ? `v${vVer}` : "Detected",
        category: "test",
        tags: [
          { label: "TESTING", color: "purple" },
          { label: "UNIT TEST", color: "gray" },
        ],
      },
      ["vitest"]
    );
  }

  const cypressDep = allDeps.find((d) => d.name?.toLowerCase() === "cypress" || d.artifact_id?.toLowerCase() === "cypress");
  if ((cypressDep || rawFrameworks.includes("cypress")) && !isAlreadyRepresented("cypress")) {
    const cVer =
      cypressDep?.resolvedVersion ||
      cypressDep?.current_version ||
      (cypressDep?.declaredVersion ? cypressDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "cypress",
        name: cVer && !cVer.toLowerCase().includes("unknown") ? `Cypress ${cVer}` : "Cypress",
        type: "E2E Testing Tool",
        status: cVer && !cVer.toLowerCase().includes("unknown") ? `v${cVer}` : "Detected",
        category: "test",
        tags: [
          { label: "TESTING", color: "purple" },
          { label: "E2E", color: "gray" },
        ],
      },
      ["cypress"]
    );
  }

  const playwrightDep = allDeps.find(
    (d) =>
      d.name?.toLowerCase() === "@playwright/test" ||
      d.name?.toLowerCase() === "playwright" ||
      d.artifact_id?.toLowerCase() === "playwright"
  );
  if ((playwrightDep || rawFrameworks.includes("playwright")) && !isAlreadyRepresented("playwright")) {
    const pVer =
      playwrightDep?.resolvedVersion ||
      playwrightDep?.current_version ||
      (playwrightDep?.declaredVersion ? playwrightDep.declaredVersion.replace(/^[~^>=<v\s]*/, "") : null);
    registerItem(
      {
        id: "playwright",
        name: pVer && !pVer.toLowerCase().includes("unknown") ? `Playwright ${pVer}` : "Playwright",
        type: "E2E Testing Tool",
        status: pVer && !pVer.toLowerCase().includes("unknown") ? `v${pVer}` : "Detected",
        category: "test",
        tags: [
          { label: "TESTING", color: "purple" },
          { label: "E2E", color: "gray" },
        ],
      },
      ["playwright", "@playwright/test"]
    );
  }

  // 12. Fallback / Raw detected frameworks from repository intelligence
  // Deduplicates against all previously registered technologies and formats friendly labels
  if (repoAnalysis?.detected_frameworks) {
    repoAnalysis.detected_frameworks.forEach((df, idx) => {
      const name = typeof df === "string" ? df : df.name;
      if (!name) return;
      if (!isAlreadyRepresented(name)) {
        const canonicalKey = getCanonicalTechId(name) || normalizeTechKey(name);
        const isFe = typeof df === "object" && df.type === "FRONTEND";
        registerItem(
          {
            id: canonicalKey || `custom-fw-${idx}`,
            name: formatTechDisplayName(name),
            type: typeof df === "object" && df.type ? df.type : "Library / Framework",
            status: "Detected",
            category: isFe ? "frontend" : "generic",
            tags: [
              { label: "FRAMEWORK", color: "purple" },
              { label: isFe ? "FRONTEND" : "JAVA", color: "gray" },
            ],
          },
          [name, canonicalKey]
        );
      }
    });
  }

  // Final deduplication pass: groups strictly by canonical technology identifier
  const deduplicatedItems: DetectedFrameworkDetail[] = [];
  const finalSeenKeys = new Set<string>();

  for (const it of items) {
    const canon = getCanonicalTechId(it.id) || normalizeTechKey(it.id) || normalizeTechKey(it.name);
    if (!finalSeenKeys.has(canon)) {
      finalSeenKeys.add(canon);
      deduplicatedItems.push(it);
    } else {
      // If a record with version/status is available, enrich the existing record
      const existingIdx = deduplicatedItems.findIndex(
        (existing) => (getCanonicalTechId(existing.id) || normalizeTechKey(existing.id)) === canon
      );
      if (existingIdx !== -1) {
        const existing = deduplicatedItems[existingIdx];
        if (
          (!existing.status || existing.status === "Detected") &&
          it.status &&
          it.status !== "Detected"
        ) {
          deduplicatedItems[existingIdx] = {
            ...existing,
            status: it.status,
            name: it.name,
          };
        }
      }
    }
  }

  // Fallback if no framework was detected at all
  if (deduplicatedItems.length === 0) {
    const buildTool = repoAnalysis?.build_tool ? repoAnalysis.build_tool.toUpperCase() : "Standard";
    deduplicatedItems.push({
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

  return deduplicatedItems;
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
  brdMetadata: { filename: string; size?: number; uploadedAt?: string } | null;
  brdUploadError: string | null;
  handleBrdFileSelect: (file: File | null) => void;
  handleBrdUpload: () => Promise<void>;
  conversionDecision: "yes" | "no" | null;
  setConversionDecision: (value: "yes" | "no" | null) => void;
  showFolderStructure: boolean;
  setShowFolderStructure: (value: boolean) => void;
  handleCheckMicroserviceEligibility: () => Promise<void>;
  handleGenerateBrdDocument: () => Promise<void>;
  documentPromptSettings: DocumentGenerationPromptSettings;
  documentPromptLoading: boolean;
  documentPromptLoadError: string;
  documentPromptSavingType: DocumentPromptType | null;
  handleSaveDocumentPrompt: (promptType: DocumentPromptType, prompt: string) => Promise<string>;
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
  onHandleJobError?: (err: unknown) => boolean;
}

export interface FileTreeItem {
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
  documentPromptSettings,
  documentPromptLoading,
  documentPromptLoadError,
  documentPromptSavingType,
  handleSaveDocumentPrompt,
  handleOpenFrameworkFile: _handleOpenFrameworkFile,
  handleRerunAnalysis: _handleRerunAnalysis,
  isDiscoveryPending,
  formattedAnalysisElapsed,
  formattedAnalysisCompleted: _formattedAnalysisCompleted,
  detectedJavaStructureLabel: _detectedJavaStructureLabel,
  technicalSpecificationButtonLabel,
  technicalSpecificationHelperText: _technicalSpecificationHelperText,
  onBack,
  onChooseDifferentRepository,
  onContinueToStrategy,
  onError: _onError,
  onHandleJobError: _onHandleJobError,
}: DiscoveryStepViewProps) {
  const {
    repoAnalysis,
    repoFiles,
    selectedFile,
    setSelectedFile,
    fileContent,
    setFileContent,
    editedContent: _editedContent,
    setEditedContent,
    isEditing: _isEditing,
    setIsEditing,
    fileLoading,
    setFileLoading,
    analysisElapsedSeconds,
  } = discovery;

  const { isLocalRepoRef, extractLocalRepoPath } = repoUtils;

  // Search & folder collapse state for the Repository Files tree
  const [searchQuery, setSearchQuery] = useState("");
  const query = searchQuery.trim().toLowerCase();
  const [fileCategoryFilter, setFileCategoryFilter] = useState<string>("ALL");
  const [collapsedFolders, setCollapsedFolders] = useState<Record<string, boolean>>({});

  const [isBrdAllowed, setIsBrdAllowed] = useState<boolean>(true);
  const [documentPromptType, setDocumentPromptType] = useState<DocumentPromptType>("TECHNICAL_SPECIFICATION");
  const [documentPromptDrafts, setDocumentPromptDrafts] = useState<Record<DocumentPromptType, string>>({
    BRD: "",
    TECHNICAL_SPECIFICATION: "",
  });
  const [documentPromptSaveError, setDocumentPromptSaveError] = useState("");
  const documentPromptDraftsInitialized = useRef(false);

  useEffect(() => {
    if (!documentPromptLoading && !documentPromptDraftsInitialized.current) {
      setDocumentPromptDrafts(documentPromptSettings.prompts);
      documentPromptDraftsInitialized.current = true;
    }
  }, [documentPromptLoading, documentPromptSettings.prompts]);

  const activeDocumentPrompt = documentPromptDrafts[documentPromptType];
  const activeSavedPrompt = documentPromptSettings.prompts[documentPromptType];
  const isDocumentPromptDirty = activeDocumentPrompt !== activeSavedPrompt;
  const isDocumentPromptSaved =
    !documentPromptLoading &&
    !isDocumentPromptDirty &&
    documentPromptSettings.savedTypes[documentPromptType] &&
    !documentPromptSaveError;
  const documentPromptStatusMessage = documentPromptLoadError
    ? "Saved prompts could not be loaded."
    : documentPromptSaveError
      ? "Prompt save failed."
      : isDocumentPromptSaved
        ? "Saved"
        : isDocumentPromptDirty || documentPromptSettings.savedTypes[documentPromptType]
          ? "Unsaved changes"
          : "Not saved yet";

  const saveActiveDocumentPrompt = async () => {
    setDocumentPromptSaveError("");
    try {
      const confirmedPrompt = await handleSaveDocumentPrompt(documentPromptType, activeDocumentPrompt);
      setDocumentPromptDrafts((current) => ({ ...current, [documentPromptType]: confirmedPrompt }));
    } catch (err: unknown) {
      setDocumentPromptSaveError(
        err instanceof Error ? err.message : "The document prompt could not be saved."
      );
    }
  };

  useEffect(() => {
    getUserSettings()
      .then((s) => {
        if (s?.settings_permissions?.brd_testing === false) {
          setIsBrdAllowed(false);
        }
      })
      .catch(() => {});
  }, []);

  // Hover & pinned state for KPI metric cards
  const [hoveredKpi, setHoveredKpi] = useState<string | null>(null);
  const [pinnedKpi, setPinnedKpi] = useState<string | null>(null);
  const activeKpi = pinnedKpi || hoveredKpi;

  // API Endpoints modal and filter state
  const [showEndpointsModal, setShowEndpointsModal] = useState<boolean>(false);
  const [endpointFilterMethod, setEndpointFilterMethod] = useState<string>("ALL");
  const [endpointSearchQuery, setEndpointSearchQuery] = useState<string>("");

  // Global click to unpin KPI popover when clicking elsewhere
  useEffect(() => {
    const handleGlobalClick = () => setPinnedKpi(null);
    window.addEventListener("click", handleGlobalClick);
    return () => window.removeEventListener("click", handleGlobalClick);
  }, []);

  const fileMetrics = repoAnalysis?.file_metrics;
  const categories = fileMetrics?.categories;
  const categoryFiles = fileMetrics?.category_files;

  const rawJavaFileList = useMemo(
    () => categoryFiles?.java ?? repoAnalysis?.java_files ?? [],
    [categoryFiles?.java, repoAnalysis?.java_files]
  );
  const javaTestFileList = useMemo(
    () => categoryFiles?.java_test ?? [],
    [categoryFiles?.java_test]
  );
  const javaFileList = useMemo(
    () => Array.from(new Set([...rawJavaFileList, ...javaTestFileList])),
    [rawJavaFileList, javaTestFileList]
  );
  const reactFileList = useMemo(
    () => categoryFiles?.react ?? [],
    [categoryFiles?.react]
  );
  const angularFileList = useMemo(
    () => categoryFiles?.angular ?? [],
    [categoryFiles?.angular]
  );
  const jspFileList = useMemo(
    () => categoryFiles?.jsp ?? repoAnalysis?.jsp_files ?? [],
    [categoryFiles?.jsp, repoAnalysis?.jsp_files]
  );
  const jsfFileList = useMemo(
    () => categoryFiles?.jsf ?? repoAnalysis?.jsf_files ?? [],
    [categoryFiles?.jsf, repoAnalysis?.jsf_files]
  );
  const xmlFileList = useMemo(
    () => categoryFiles?.xml ?? [],
    [categoryFiles?.xml]
  );
  const configFileList = useMemo(
    () => categoryFiles?.configuration ?? repoAnalysis?.config_files ?? [],
    [categoryFiles?.configuration, repoAnalysis?.config_files]
  );
  const jsFileList = useMemo(
    () => categoryFiles?.javascript ?? [],
    [categoryFiles?.javascript]
  );
  const tsFileList = useMemo(
    () => categoryFiles?.typescript ?? [],
    [categoryFiles?.typescript]
  );
  const cssFileList = useMemo(
    () => categoryFiles?.css ?? [],
    [categoryFiles?.css]
  );
  const htmlFileList = useMemo(
    () => categoryFiles?.html ?? [],
    [categoryFiles?.html]
  );
  const resourceFileList = useMemo(
    () => categoryFiles?.resources ?? [],
    [categoryFiles?.resources]
  );
  const docFileList = useMemo(
    () => categoryFiles?.documentation ?? [],
    [categoryFiles?.documentation]
  );
  const scriptFileList = useMemo(
    () => categoryFiles?.scripts ?? [],
    [categoryFiles?.scripts]
  );
  const sqlFileList = useMemo(
    () => categoryFiles?.sql ?? [],
    [categoryFiles?.sql]
  );
  const otherFileList = useMemo(
    () => categoryFiles?.other ?? repoAnalysis?.other_files ?? [],
    [categoryFiles?.other, repoAnalysis?.other_files]
  );

  // Exact 17 Primary Category Counts
  const javaFiles = categories?.java ?? javaFileList.length;
  const javaTestFiles = categories?.java_test ?? javaTestFileList.length;
  const reactFiles = categories?.react ?? reactFileList.length;
  const angularFiles = categories?.angular ?? angularFileList.length;
  const jspFiles = categories?.jsp ?? jspFileList.length;
  const jsfFiles = categories?.jsf ?? jsfFileList.length;
  const jsFiles = categories?.javascript ?? jsFileList.length;
  const tsFiles = categories?.typescript ?? tsFileList.length;
  const cssFiles = categories?.css ?? cssFileList.length;
  const htmlFiles = categories?.html ?? htmlFileList.length;
  const xmlFiles = categories?.xml ?? xmlFileList.length;
  const configFiles = categories?.configuration ?? configFileList.length;
  const resourceFiles = categories?.resources ?? resourceFileList.length;
  const docFiles = categories?.documentation ?? docFileList.length;
  const scriptFiles = categories?.scripts ?? scriptFileList.length;
  const sqlFiles = categories?.sql ?? sqlFileList.length;
  const otherFiles = categories?.other ?? otherFileList.length;

  const xmlConfigTotal = xmlFiles + configFiles;
  const combinedXmlConfigFileList = useMemo(
    () => Array.from(new Set([...xmlFileList, ...configFileList])),
    [xmlFileList, configFileList]
  );

  const topLevelOthersFiles =
    jsFiles +
    tsFiles +
    cssFiles +
    htmlFiles +
    resourceFiles +
    docFiles +
    scriptFiles +
    sqlFiles +
    otherFiles;

  const topLevelOthersFileList = useMemo(
    () =>
      Array.from(
        new Set([
          ...jsFileList,
          ...tsFileList,
          ...cssFileList,
          ...htmlFileList,
          ...resourceFileList,
          ...docFileList,
          ...scriptFileList,
          ...sqlFileList,
          ...otherFileList,
        ])
      ),
    [
      jsFileList,
      tsFileList,
      cssFileList,
      htmlFileList,
      resourceFileList,
      docFileList,
      scriptFileList,
      sqlFileList,
      otherFileList,
    ]
  );

  const totalFiles =
    fileMetrics?.total ??
    repoAnalysis?.total_file_count ??
    javaFiles +
      javaTestFiles +
      reactFiles +
      angularFiles +
      jspFiles +
      jsfFiles +
      jsFiles +
      tsFiles +
      cssFiles +
      htmlFiles +
      xmlFiles +
      configFiles +
      resourceFiles +
      docFiles +
      scriptFiles +
      sqlFiles +
      otherFiles;

  const apiEndpoints = useMemo<DiscoveredApiEndpoint[]>(() => {
    const raw = repoAnalysis?.api_endpoints;
    if (Array.isArray(raw)) return raw;
    if (raw && typeof raw === "object" && Array.isArray((raw as any).endpoints)) {
      return (raw as any).endpoints;
    }
    return [];
  }, [repoAnalysis?.api_endpoints]);

  const apiEndpointCount =
    typeof repoAnalysis?.api_endpoint_count === "number"
      ? repoAnalysis.api_endpoint_count
      : (typeof (repoAnalysis?.api_endpoints as any)?.count === "number"
          ? (repoAnalysis?.api_endpoints as any).count
          : apiEndpoints.length);

  const getHttpMethodBadge = (method: string): { color: string; bg: string } => {
    switch ((method || "").toUpperCase()) {
      case "GET":
        return { color: "#0284c7", bg: "#e0f2fe" };
      case "POST":
        return { color: "#16a34a", bg: "#dcfce7" };
      case "PUT":
        return { color: "#d97706", bg: "#fef3c7" };
      case "DELETE":
        return { color: "#dc2626", bg: "#fee2e2" };
      case "PATCH":
        return { color: "#7c3aed", bg: "#f5f3ff" };
      case "OPTIONS":
      case "HEAD":
        return { color: "#475569", bg: "#f1f5f9" };
      default:
        return { color: "#2563eb", bg: "#eff6ff" };
    }
  };

  const filteredEndpoints = useMemo(() => {
    const q = endpointSearchQuery.trim().toLowerCase();
    return apiEndpoints.filter((ep) => {
      const method = (ep.httpMethod || ep.method || "GET").toUpperCase();
      if (endpointFilterMethod !== "ALL" && method !== endpointFilterMethod) {
        return false;
      }
      if (!q) return true;
      const path = (ep.path || ep.urlPath || ep.endpoint || "").toLowerCase();
      const ctrl = (ep.controller || ep.className || "").toLowerCase();
      const handler = (ep.handlerMethod || ep.methodName || "").toLowerCase();
      const file = (ep.sourceFile || ep.file || "").toLowerCase();
      return (
        path.includes(q) ||
        ctrl.includes(q) ||
        handler.includes(q) ||
        file.includes(q) ||
        method.toLowerCase().includes(q)
      );
    });
  }, [apiEndpoints, endpointFilterMethod, endpointSearchQuery]);

  const extractFileName = (filepath: string) => {
    const parts = filepath.replace(/\\/g, "/").split("/");
    return parts[parts.length - 1] || filepath;
  };

  const pathCategoryMap = useMemo(() => {
    const map = new Map<string, string>();
    if (categoryFiles) {
      Object.entries(categoryFiles).forEach(([cat, files]) => {
        files.forEach((f) => map.set(f.replace(/\\/g, "/").replace(/^\/+/, ""), cat));
      });
    }
    return map;
  }, [categoryFiles]);

  const getFileBadge = (filepath: string) => {
    const norm = filepath.replace(/\\/g, "/").replace(/^\/+/, "");
    const cat = pathCategoryMap.get(norm);

    if (cat === "react") return { label: "REACT", color: "#06b6d4", bg: "#e0f2fe" };
    if (cat === "angular") return { label: "ANGULAR", color: "#dc2626", bg: "#fef2f2" };
    if (cat === "java_test") return { label: "JAVA TEST", color: "#6366f1", bg: "#e0e7ff" };
    if (cat === "java") return { label: "JAVA", color: "#9333ea", bg: "#f3e8ff" };
    if (cat === "jsp") return { label: "JSP", color: "#db2777", bg: "#fce7f3" };
    if (cat === "jsf") return { label: "JSF", color: "#7c3aed", bg: "#f5f3ff" };
    if (cat === "xml") return { label: "XML", color: "#ea580c", bg: "#fff7ed" };
    if (cat === "configuration") return { label: "CFG", color: "#d97706", bg: "#fef3c7" };
    if (cat === "javascript") return { label: "JS", color: "#ca8a04", bg: "#fef9c3" };
    if (cat === "typescript") return { label: "TS", color: "#2563eb", bg: "#dbeafe" };
    if (cat === "css") return { label: "CSS", color: "#0d9488", bg: "#ccfbf1" };
    if (cat === "html") return { label: "HTML", color: "#ea580c", bg: "#ffedd5" };
    if (cat === "resources") return { label: "ASSET", color: "#059669", bg: "#d1fae5" };
    if (cat === "documentation") return { label: "DOC", color: "#475569", bg: "#f1f5f9" };
    if (cat === "scripts") return { label: "SCRIPT", color: "#16a34a", bg: "#dcfce7" };
    if (cat === "sql") return { label: "SQL", color: "#0284c7", bg: "#e0f2fe" };

    const lower = filepath.toLowerCase();
    if (lower.endsWith(".jsx") || lower.endsWith(".tsx")) return { label: "REACT", color: "#06b6d4", bg: "#e0f2fe" };
    if (lower.endsWith(".java")) return { label: "JAVA", color: "#9333ea", bg: "#f3e8ff" };
    if (lower.endsWith(".jsp") || lower.endsWith(".jspf") || lower.endsWith(".jspx")) return { label: "JSP", color: "#db2777", bg: "#fce7f3" };
    if (lower.endsWith(".xhtml") || lower.endsWith(".jsf")) return { label: "JSF", color: "#7c3aed", bg: "#f5f3ff" };
    if (lower.endsWith(".xml")) return { label: "XML", color: "#ea580c", bg: "#fff7ed" };
    if (lower.endsWith(".yml") || lower.endsWith(".yaml")) return { label: "YML", color: "#d97706", bg: "#fef3c7" };
    if (lower.endsWith(".properties")) return { label: "CFG", color: "#0284c7", bg: "#e0f2fe" };
    if (lower.endsWith(".gradle")) return { label: "GRADLE", color: "#0284c7", bg: "#e0f2fe" };
    if (lower.endsWith(".md") || lower.endsWith(".txt")) return { label: "DOC", color: "#475569", bg: "#f1f5f9" };
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
    repoAnalysis?.java_version || repoAnalysis?.java_version_from_build || "";

  const buildFileName =
    configFileList.find((f) => f === "pom.xml" || f.endsWith("/pom.xml") || f === "build.gradle" || f.endsWith("/build.gradle"))
      ? extractFileName(
          configFileList.find((f) => f === "pom.xml" || f.endsWith("/pom.xml") || f === "build.gradle" || f.endsWith("/build.gradle"))!
        )
      : repoAnalysis?.structure?.has_build_gradle || repoAnalysis?.build_tool?.toLowerCase().includes("gradle")
      ? "build.gradle"
      : repoAnalysis?.structure?.has_pom_xml || repoAnalysis?.build_tool?.toLowerCase().includes("maven")
      ? "pom.xml"
      : "";

  const detectedFrameworks = extractDetectedFrameworks(repoAnalysis);
  const [showFrameworksModal, setShowFrameworksModal] = useState(false);

  // File tree construction matching repository structure
  const rootRepoName = selectedRepo?.name || "Repository";

  // Aggregate all discovered repository file paths (deduplicated by normalized relative path from authoritative fileMetrics)
  const allDiscoveredPaths: string[] = useMemo(() => {
    const normalizePath = (p: string) => p.replace(/\\/g, "/").replace(/^\/+/, "").trim();
    const pathSet = new Set<string>();
    if (categoryFiles) {
      Object.values(categoryFiles).forEach((list) => {
        (list || []).forEach((f) => {
          const norm = normalizePath(f);
          if (norm) pathSet.add(norm);
        });
      });
    } else {
      [
        javaFileList,
        javaTestFileList,
        reactFileList,
        angularFileList,
        jspFileList,
        jsfFileList,
        configFileList,
        xmlFileList,
        otherFileList,
      ].forEach((list) => {
        (list || []).forEach((f) => {
          const norm = normalizePath(f);
          if (norm) pathSet.add(norm);
        });
      });
      (repoFiles || []).forEach((f) => {
        if (f?.path) {
          const norm = normalizePath(f.path);
          if (norm) pathSet.add(norm);
        }
      });
    }

    return Array.from(pathSet);
  }, [
    categoryFiles,
    javaFileList,
    javaTestFileList,
    reactFileList,
    angularFileList,
    jspFileList,
    jsfFileList,
    configFileList,
    xmlFileList,
    otherFileList,
    repoFiles,
  ]);

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
      let dir = list.find((item) => item.name === name);
      if (dir) {
        if (!dir.isDir) {
          dir.isDir = true;
          dir.children = [];
          dir.itemCount = 0;
        }
        return dir;
      }

      dir = {
        id: currentPath,
        name,
        path: currentPath,
        isDir: true,
        children: [],
        itemCount: 0,
      };
      list.push(dir);
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
          if (!currentList.some((item) => item.name === part)) {
            currentList.push({
              id: accumulatedPath,
              name: part,
              path: accumulatedPath,
              isDir: false,
              children: [],
              itemCount: 1,
            });
          }
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

  const { visibleTree, filteredFileCount } = useMemo(() => {
    const isCategoryMatch = (filepath: string) => {
      if (fileCategoryFilter === "ALL") return true;
      const norm = filepath.replace(/\\/g, "/").replace(/^\/+/, "");
      const cat = pathCategoryMap.get(norm);
      const lower = filepath.toLowerCase();

      if (fileCategoryFilter === "JAVA") return cat === "java" || cat === "java_test" || (not(cat) && lower.endsWith(".java"));
      if (fileCategoryFilter === "REACT") return cat === "react" || (not(cat) && (lower.endsWith(".jsx") || lower.endsWith(".tsx")));
      if (fileCategoryFilter === "ANGULAR") return cat === "angular" || (not(cat) && lower.includes("component"));
      if (fileCategoryFilter === "JSP") return cat === "jsp" || (not(cat) && (lower.endsWith(".jsp") || lower.endsWith(".jspf") || lower.endsWith(".jspx")));
      if (fileCategoryFilter === "JSF") return cat === "jsf" || (not(cat) && (lower.endsWith(".xhtml") || lower.endsWith(".jsf")));
      if (fileCategoryFilter === "CONFIG") return cat === "xml" || cat === "configuration" || (not(cat) && (lower.endsWith(".xml") || lower.endsWith(".properties") || lower.endsWith(".yml") || lower.endsWith(".json")));
      if (fileCategoryFilter === "OTHERS") return cat === "other" || cat === "javascript" || cat === "typescript" || cat === "css" || cat === "html" || cat === "resources" || cat === "documentation" || cat === "scripts" || cat === "sql" || (!cat && !lower.endsWith(".java") && !lower.endsWith(".jsp") && !lower.endsWith(".xhtml") && !lower.endsWith(".jsf") && !lower.endsWith(".xml") && !lower.endsWith(".jsx") && !lower.endsWith(".tsx"));
      return true;
    };

    function not(val: string | undefined): boolean {
      return !val;
    }

    let count = 0;

    function filterList(list: DynamicTreeNode[]): DynamicTreeNode[] {
      const result: DynamicTreeNode[] = [];
      for (const node of list) {
        if (node.isDir) {
          const matchingChildren = filterList(node.children);
          if (matchingChildren.length > 0) {
            result.push({
              ...node,
              children: matchingChildren,
            });
          }
        } else {
          const catOk = isCategoryMatch(node.path);
          const nameMatches = !query || node.name.toLowerCase().includes(query) || node.path.toLowerCase().includes(query);
          if (catOk && nameMatches) {
            count++;
            result.push(node);
          }
        }
      }
      return result;
    }

    if (!query && fileCategoryFilter === "ALL") {
      return { visibleTree: fileTree || [], filteredFileCount: allDiscoveredPaths.length };
    }

    return { visibleTree: filterList(fileTree || []), filteredFileCount: count };
  }, [fileTree, query, fileCategoryFilter, allDiscoveredPaths.length, pathCategoryMap]);

  const isFolderOpen = (folderId: string): boolean => {
    if (searchQuery || fileCategoryFilter !== "ALL") return true;
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
      (nodes || []).forEach((n) => {
        if (n.isDir) {
          allFolderIds.push(n.id);
          collect(n.children);
        }
      });
    };
    collect(fileTree || []);
    return allFolderIds.length > 0 && allFolderIds.every((id) => collapsedFolders[id] === true);
  }, [fileTree, collapsedFolders]);

  const handleToggleAll = () => {
    const allFolderIds: string[] = ["root"];
    const collect = (nodes: DynamicTreeNode[]) => {
      (nodes || []).forEach((n) => {
        if (n.isDir) {
          allFolderIds.push(n.id);
          collect(n.children);
        }
      });
    };
    collect(fileTree || []);

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
    const nodeKey = `${node.isDir ? "dir" : "file"}-${node.id || node.name}-${depth}`;

    if (node.isDir) {
      return (
        <React.Fragment key={nodeKey}>
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
        key={nodeKey}
        className={`discovery-tree-row ${isSelected ? "is-active" : ""}`}
        style={{ paddingLeft }}
        onClick={() => void handleSelectFile({ name: node.name, path: node.path })}
      >
        <div className="discovery-tree-left">
          <span className="discovery-tree-toggle" />
          {node.name.toLowerCase().endsWith(".jsp") || node.name.toLowerCase().endsWith(".jspf") || node.name.toLowerCase().endsWith(".jspx") ? (
            <FaCode color="#db2777" size={14} />
          ) : node.name.toLowerCase().endsWith(".xhtml") || node.name.toLowerCase().endsWith(".jsf") ? (
            <FaCode color="#7c3aed" size={14} />
          ) : node.name.endsWith(".java") ? (
            <FaFileCode color="#9333ea" size={14} />
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

  const kpiCategoryBreakdown = useMemo(() => {
    const list = [
      {
        label: "Java",
        count: javaFiles,
        color: "#9333ea",
        subText: javaTestFiles > 0 ? `includes ${javaTestFiles} test files` : undefined,
      },
      { label: "React", count: reactFiles, color: "#06b6d4" },
      { label: "Angular", count: angularFiles, color: "#dc2626" },
      { label: "JSP", count: jspFiles, color: "#db2777" },
      { label: "JSF", count: jsfFiles, color: "#7c3aed" },
      { label: "JavaScript", count: jsFiles, color: "#ca8a04" },
      { label: "TypeScript", count: tsFiles, color: "#2563eb" },
      { label: "CSS / Styles", count: cssFiles, color: "#0d9488" },
      { label: "HTML", count: htmlFiles, color: "#ea580c" },
      { label: "XML", count: xmlFiles, color: "#d97706" },
      { label: "Configuration", count: configFiles, color: "#b45309" },
      { label: "Resources", count: resourceFiles, color: "#059669" },
      { label: "Documentation", count: docFiles, color: "#475569" },
      { label: "Scripts", count: scriptFiles, color: "#16a34a" },
      { label: "SQL", count: sqlFiles, color: "#0284c7" },
      { label: "Other", count: otherFiles, color: "#94a3b8" },
    ];
    return list.filter((item) => item.count > 0);
  }, [
    javaFiles,
    javaTestFiles,
    reactFiles,
    angularFiles,
    jspFiles,
    jsfFiles,
    jsFiles,
    tsFiles,
    cssFiles,
    htmlFiles,
    xmlFiles,
    configFiles,
    resourceFiles,
    docFiles,
    scriptFiles,
    sqlFiles,
    otherFiles,
  ]);

  if (!selectedRepo || !selectedRepo.url) {
    return (
      <div className="discovery-dashboard-wrapper">
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
        </div>

        <div
          className="discovery-empty-state-card"
          style={{
            background: "#ffffff",
            borderRadius: "16px",
            border: "1px dashed #cbd5e1",
            padding: "56px 24px",
            textAlign: "center",
            margin: "32px auto",
            maxWidth: "600px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "16px",
          }}
        >
          <div
            style={{
              width: "60px",
              height: "60px",
              borderRadius: "50%",
              background: "#eff6ff",
              color: "#2563eb",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "24px",
            }}
          >
            <FaFolderOpen />
          </div>
          <h3 style={{ margin: 0, fontSize: "18px", fontWeight: 700, color: "#0f172a" }}>
            No Repository Connected
          </h3>
          <p style={{ margin: 0, fontSize: "13px", color: "#64748b", maxWidth: "420px", lineHeight: 1.5 }}>
            No repository has been provided. Please connect and validate a repository on the Connect page to run discovery analysis.
          </p>
          <button
            onClick={onChooseDifferentRepository || onBack}
            className="discovery-btn-continue"
            style={{ marginTop: "8px", display: "inline-flex", alignItems: "center", gap: "8px" }}
          >
            <FaArrowLeft size={11} /> Go to Connect Page
          </button>
        </div>
      </div>
    );
  }

  const hasViewTechnology = jspFiles > 0 || jsfFiles > 0;

  return (
    <div className="discovery-dashboard-wrapper">

      {/* Main Header */}
      <div className="discovery-header-box">
        <div className="discovery-header-left" style={{ alignItems: "center" }}>
          <div className="discovery-header-icon-badge">
            <span className="discovery-search-icon-animated"><FaSearch /></span>
          </div>
          <div className="discovery-header-titles">
             <h2 style={{ margin: 0, fontSize: 22 }}>Repository Discovery &amp; Dependencies</h2>
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
                    {kpiCategoryBreakdown.map((item) => (
                      <div
                        key={item.label}
                        className="discovery-kpi-dist-seg"
                        style={{
                          width: `${Math.max(1, Math.round((item.count / totalFiles) * 100))}%`,
                          background: item.color,
                        }}
                        title={`${item.label}: ${item.count} files`}
                      />
                    ))}
                  </div>

                  <div className="discovery-kpi-dist-legend" style={{ maxHeight: 140, overflowY: "auto" }}>
                    {kpiCategoryBreakdown.map((item) => (
                      <div key={item.label} className="discovery-kpi-dist-row">
                        <span>
                          <span className="discovery-kpi-dist-dot" style={{ background: item.color }} />
                          {item.label}
                          {item.subText && (
                            <span style={{ fontSize: "10px", color: "#64748b", marginLeft: "6px" }}>
                              ({item.subText})
                            </span>
                          )}
                        </span>
                        <strong style={{ color: "#0f172a" }}>{item.count}</strong>
                      </div>
                    ))}
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
                            key={`${file}-${idx}`}
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
                          key={`${file}-${idx}`}
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
                  <span className="discovery-kpi-number">{xmlConfigTotal}</span>
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
                        {xmlConfigTotal} files
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
                    {combinedXmlConfigFileList.map((file, idx) => {
                      const name = extractFileName(file);
                      const badge = getFileBadge(name);
                      return (
                        <div
                          key={`${file}-${idx}`}
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
                    <span>{combinedXmlConfigFileList.length} build &amp; config files</span>
                    <span style={{ color: "#94a3b8" }}>{pinnedKpi === "config" ? "Pinned" : "Click to pin"}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Card 4: JSP Files (if detected) */}
            {jspFiles > 0 && (
              <div
                className={`discovery-kpi-card ${activeKpi === "jsp" ? "has-popover-open" : ""}`}
                onMouseEnter={() => setHoveredKpi("jsp")}
                onMouseLeave={() => setHoveredKpi(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  setPinnedKpi((prev) => (prev === "jsp" ? null : "jsp"));
                  setSearchQuery(".jsp");
                }}
                style={{ cursor: "pointer" }}
              >
                <div className="discovery-kpi-top">
                  <div className="discovery-kpi-icon" style={{ background: "#fce7f3", color: "#db2777" }}>
                    <FaCode />
                  </div>
                  <div className="discovery-kpi-number-wrap">
                    <span className="discovery-kpi-number">{jspFiles}</span>
                  </div>
                </div>
                <div className="discovery-kpi-bottom">
                  <span className="discovery-kpi-label">JSP Files</span>
                  <span className="discovery-kpi-sub">.jsp/.jspf files (Detected)</span>
                </div>

                {/* Popover */}
                {activeKpi === "jsp" && (
                  <div
                    className="discovery-kpi-popover align-left"
                    onClick={(e) => e.stopPropagation()}
                    onMouseEnter={() => setHoveredKpi("jsp")}
                    onMouseLeave={() => setHoveredKpi(null)}
                  >
                    <div className="discovery-kpi-popover-header">
                      <div className="discovery-kpi-popover-title-wrap">
                        <FaCode color="#db2777" size={14} />
                        <span className="discovery-kpi-popover-title">JSP Files</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span className="discovery-kpi-popover-badge" style={{ background: "#fce7f3", color: "#db2777" }}>
                          {jspFiles} files
                        </span>
                        {pinnedKpi === "jsp" && (
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
                      {jspFileList.map((file) => {
                        const name = extractFileName(file);
                        return (
                          <div
                            key={file}
                            className="discovery-kpi-file-item"
                            onClick={(e) => handleSelectPopoverFile(file, e)}
                            title={`Click to preview ${name}`}
                          >
                            <div className="discovery-kpi-file-left">
                              <span className="discovery-kpi-file-icon">
                                <FaCode color="#db2777" />
                              </span>
                              <div className="discovery-kpi-file-info">
                                <span className="discovery-kpi-file-name">{name}</span>
                                <span className="discovery-kpi-file-path">{file}</span>
                              </div>
                            </div>
                            <span className="discovery-kpi-file-tag" style={{ color: "#db2777", background: "#fce7f3" }}>
                              JSP
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    <div className="discovery-kpi-popover-footer">
                      <span>Showing {jspFileList.length} JSP files</span>
                      <span style={{ color: "#94a3b8" }}>{pinnedKpi === "jsp" ? "Pinned" : "Click to pin"}</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Card 5: JSF Files (if detected) */}
            {jsfFiles > 0 && (
              <div
                className={`discovery-kpi-card ${activeKpi === "jsf" ? "has-popover-open" : ""}`}
                onMouseEnter={() => setHoveredKpi("jsf")}
                onMouseLeave={() => setHoveredKpi(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  setPinnedKpi((prev) => (prev === "jsf" ? null : "jsf"));
                  const hasXhtml = allDiscoveredPaths.some(p => p.toLowerCase().endsWith('.xhtml'));
                  setSearchQuery(hasXhtml ? ".xhtml" : ".jsf");
                }}
                style={{ cursor: "pointer" }}
              >
                <div className="discovery-kpi-top">
                  <div className="discovery-kpi-icon" style={{ background: "#f5f3ff", color: "#7c3aed" }}>
                    <FaCode />
                  </div>
                  <div className="discovery-kpi-number-wrap">
                    <span className="discovery-kpi-number">{jsfFiles}</span>
                  </div>
                </div>
                <div className="discovery-kpi-bottom">
                  <span className="discovery-kpi-label">JSF Files</span>
                  <span className="discovery-kpi-sub">.xhtml/.jsf files (Detected)</span>
                </div>

                {/* Popover */}
                {activeKpi === "jsf" && (
                  <div
                    className="discovery-kpi-popover align-right"
                    onClick={(e) => e.stopPropagation()}
                    onMouseEnter={() => setHoveredKpi("jsf")}
                    onMouseLeave={() => setHoveredKpi(null)}
                  >
                    <div className="discovery-kpi-popover-header">
                      <div className="discovery-kpi-popover-title-wrap">
                        <FaCode color="#7c3aed" size={14} />
                        <span className="discovery-kpi-popover-title">JSF Files</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span className="discovery-kpi-popover-badge" style={{ background: "#f5f3ff", color: "#7c3aed" }}>
                          {jsfFiles} files
                        </span>
                        {pinnedKpi === "jsf" && (
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
                      {jsfFileList.map((file) => {
                        const name = extractFileName(file);
                        return (
                          <div
                            key={file}
                            className="discovery-kpi-file-item"
                            onClick={(e) => handleSelectPopoverFile(file, e)}
                            title={`Click to preview ${name}`}
                          >
                            <div className="discovery-kpi-file-left">
                              <span className="discovery-kpi-file-icon">
                                <FaCode color="#7c3aed" />
                              </span>
                              <div className="discovery-kpi-file-info">
                                <span className="discovery-kpi-file-name">{name}</span>
                                <span className="discovery-kpi-file-path">{file}</span>
                              </div>
                            </div>
                            <span className="discovery-kpi-file-tag" style={{ color: "#7c3aed", background: "#f5f3ff" }}>
                              JSF
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    <div className="discovery-kpi-popover-footer">
                      <span>Showing {jsfFileList.length} JSF files</span>
                      <span style={{ color: "#94a3b8" }}>{pinnedKpi === "jsf" ? "Pinned" : "Click to pin"}</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Card: React Files (if detected) */}
            {reactFiles > 0 && (
              <div
                className={`discovery-kpi-card ${activeKpi === "react" ? "has-popover-open" : ""}`}
                onMouseEnter={() => setHoveredKpi("react")}
                onMouseLeave={() => setHoveredKpi(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  setPinnedKpi((prev) => (prev === "react" ? null : "react"));
                  setFileCategoryFilter("REACT");
                }}
                style={{ cursor: "pointer" }}
              >
                <div className="discovery-kpi-top">
                  <div className="discovery-kpi-icon" style={{ background: "#e0f2fe", color: "#06b6d4" }}>
                    <FaCode />
                  </div>
                  <div className="discovery-kpi-number-wrap">
                    <span className="discovery-kpi-number">{reactFiles}</span>
                  </div>
                </div>
                <div className="discovery-kpi-bottom">
                  <span className="discovery-kpi-label">React</span>
                  <span className="discovery-kpi-sub">React JSX/TSX source</span>
                </div>

                {/* Popover */}
                {activeKpi === "react" && (
                  <div
                    className="discovery-kpi-popover align-right"
                    onClick={(e) => e.stopPropagation()}
                    onMouseEnter={() => setHoveredKpi("react")}
                    onMouseLeave={() => setHoveredKpi(null)}
                  >
                    <div className="discovery-kpi-popover-header">
                      <div className="discovery-kpi-popover-title-wrap">
                        <FaCode color="#06b6d4" size={14} />
                        <span className="discovery-kpi-popover-title">React Files</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span className="discovery-kpi-popover-badge" style={{ background: "#e0f2fe", color: "#06b6d4" }}>
                          {reactFiles} files
                        </span>
                        {pinnedKpi === "react" && (
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
                      {reactFileList.map((file) => {
                        const name = extractFileName(file);
                        return (
                          <div
                            key={file}
                            className="discovery-kpi-file-item"
                            onClick={(e) => handleSelectPopoverFile(file, e)}
                            title={`Click to preview ${name}`}
                          >
                            <div className="discovery-kpi-file-left">
                              <span className="discovery-kpi-file-icon">
                                <FaCode color="#06b6d4" />
                              </span>
                              <div className="discovery-kpi-file-info">
                                <span className="discovery-kpi-file-name">{name}</span>
                                <span className="discovery-kpi-file-path">{file}</span>
                              </div>
                            </div>
                            <span className="discovery-kpi-file-tag" style={{ color: "#06b6d4", background: "#e0f2fe" }}>
                              REACT
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    <div className="discovery-kpi-popover-footer">
                      <span>Showing {reactFileList.length} React files</span>
                      <span style={{ color: "#94a3b8" }}>{pinnedKpi === "react" ? "Pinned" : "Click to pin"}</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Card: Angular Files (if detected) */}
            {angularFiles > 0 && (
              <div
                className={`discovery-kpi-card ${activeKpi === "angular" ? "has-popover-open" : ""}`}
                onMouseEnter={() => setHoveredKpi("angular")}
                onMouseLeave={() => setHoveredKpi(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  setPinnedKpi((prev) => (prev === "angular" ? null : "angular"));
                  setFileCategoryFilter("ANGULAR");
                }}
                style={{ cursor: "pointer" }}
              >
                <div className="discovery-kpi-top">
                  <div className="discovery-kpi-icon" style={{ background: "#fef2f2", color: "#dc2626" }}>
                    <FaCode />
                  </div>
                  <div className="discovery-kpi-number-wrap">
                    <span className="discovery-kpi-number">{angularFiles}</span>
                  </div>
                </div>
                <div className="discovery-kpi-bottom">
                  <span className="discovery-kpi-label">Angular</span>
                  <span className="discovery-kpi-sub">Angular TypeScript/HTML</span>
                </div>

                {/* Popover */}
                {activeKpi === "angular" && (
                  <div
                    className="discovery-kpi-popover align-right"
                    onClick={(e) => e.stopPropagation()}
                    onMouseEnter={() => setHoveredKpi("angular")}
                    onMouseLeave={() => setHoveredKpi(null)}
                  >
                    <div className="discovery-kpi-popover-header">
                      <div className="discovery-kpi-popover-title-wrap">
                        <FaCode color="#dc2626" size={14} />
                        <span className="discovery-kpi-popover-title">Angular Files</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span className="discovery-kpi-popover-badge" style={{ background: "#fef2f2", color: "#dc2626" }}>
                          {angularFiles} files
                        </span>
                        {pinnedKpi === "angular" && (
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
                      {angularFileList.map((file) => {
                        const name = extractFileName(file);
                        return (
                          <div
                            key={file}
                            className="discovery-kpi-file-item"
                            onClick={(e) => handleSelectPopoverFile(file, e)}
                            title={`Click to preview ${name}`}
                          >
                            <div className="discovery-kpi-file-left">
                              <span className="discovery-kpi-file-icon">
                                <FaCode color="#dc2626" />
                              </span>
                              <div className="discovery-kpi-file-info">
                                <span className="discovery-kpi-file-name">{name}</span>
                                <span className="discovery-kpi-file-path">{file}</span>
                              </div>
                            </div>
                            <span className="discovery-kpi-file-tag" style={{ color: "#dc2626", background: "#fef2f2" }}>
                              ANGULAR
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    <div className="discovery-kpi-popover-footer">
                      <span>Showing {angularFileList.length} Angular files</span>
                      <span style={{ color: "#94a3b8" }}>{pinnedKpi === "angular" ? "Pinned" : "Click to pin"}</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Card 6: Others */}
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
                  <span className="discovery-kpi-number">{topLevelOthersFiles}</span>
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
                        {topLevelOthersFiles} files
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
                    {topLevelOthersFileList.map((file, idx) => {
                      const name = extractFileName(file);
                      const badge = getFileBadge(name);
                      return (
                        <div
                          key={`${file}-${idx}`}
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
                    <span>Showing {topLevelOthersFileList.length} remaining files</span>
                    <span style={{ color: "#94a3b8" }}>{pinnedKpi === "others" ? "Pinned" : "Click to pin"}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Card: API Endpoints */}
            <div
              className={`discovery-kpi-card ${activeKpi === "endpoints" ? "has-popover-open" : ""}`}
              onMouseEnter={() => setHoveredKpi("endpoints")}
              onMouseLeave={() => setHoveredKpi(null)}
              onClick={(e) => {
                e.stopPropagation();
                setShowEndpointsModal(true);
                setPinnedKpi(null);
              }}
              style={{ cursor: "pointer" }}
            >
              <div className="discovery-kpi-top">
                <div className="discovery-kpi-icon" style={{ background: "#ecfdf5", color: "#059669" }}>
                  <FaNetworkWired />
                </div>
                <div className="discovery-kpi-number-wrap">
                  <span className="discovery-kpi-number">{apiEndpointCount}</span>
                </div>
              </div>
              <div className="discovery-kpi-bottom">
                <span className="discovery-kpi-label">API Endpoints</span>
                <span className="discovery-kpi-sub">Detected API endpoints</span>
              </div>

              {/* Popover */}
              {activeKpi === "endpoints" && (
                <div
                  className="discovery-kpi-popover align-right"
                  onClick={(e) => e.stopPropagation()}
                  onMouseEnter={() => setHoveredKpi("endpoints")}
                  onMouseLeave={() => setHoveredKpi(null)}
                  style={{ width: 440, maxWidth: "90vw" }}
                >
                  <div className="discovery-kpi-popover-header">
                    <div className="discovery-kpi-popover-title-wrap">
                      <FaNetworkWired color="#059669" size={14} />
                      <span className="discovery-kpi-popover-title">Detected API Endpoints</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className="discovery-kpi-popover-badge" style={{ background: "#ecfdf5", color: "#059669" }}>
                        {apiEndpointCount} endpoints
                      </span>
                      {pinnedKpi === "endpoints" && (
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

                  {apiEndpoints.length === 0 ? (
                    <div style={{ padding: "16px 12px", color: "#64748b", fontSize: 13, textAlign: "center" }}>
                      No REST endpoints detected in this repository.
                    </div>
                  ) : (
                    <div className="discovery-kpi-file-list" style={{ maxHeight: 240, overflowY: "auto" }}>
                      {apiEndpoints.map((ep, idx) => {
                        const method = (ep.httpMethod || ep.method || "GET").toUpperCase();
                        const methodBadge = getHttpMethodBadge(method);
                        const path = ep.path || ep.urlPath || ep.endpoint || "/";
                        const controllerName = ep.controller || ep.className || "Controller";
                        const methodName = ep.handlerMethod || ep.methodName || "";
                        const sourceFile = ep.sourceFile || ep.file || "";

                        return (
                          <div
                            key={ep.id || `${method}-${path}-${idx}`}
                            className="discovery-kpi-file-item discovery-endpoint-row"
                            onClick={(e) => {
                              if (sourceFile) {
                                handleSelectPopoverFile(sourceFile, e);
                              }
                            }}
                            title={sourceFile ? `Click to view ${sourceFile}` : `${controllerName}.${methodName}`}
                            style={{ cursor: sourceFile ? "pointer" : "default" }}
                          >
                            <div className="discovery-kpi-file-left" style={{ gap: 8 }}>
                              <span
                                style={{
                                  fontSize: 10,
                                  fontWeight: 800,
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                  background: methodBadge.bg,
                                  color: methodBadge.color,
                                  minWidth: 42,
                                  textAlign: "center",
                                  letterSpacing: "0.03em",
                                  flexShrink: 0,
                                }}
                              >
                                {method}
                              </span>
                              <div className="discovery-kpi-file-info" style={{ minWidth: 0 }}>
                                <span className="discovery-kpi-file-name" style={{ fontFamily: "monospace", fontSize: 12 }}>
                                  {path}
                                </span>
                                <span className="discovery-kpi-file-path">
                                  {controllerName}{methodName ? ` · ${methodName}` : ""}
                                </span>
                              </div>
                            </div>
                            {sourceFile && (
                              <span className="discovery-kpi-file-tag" style={{ color: "#059669", background: "#ecfdf5", fontSize: 10 }}>
                                {extractFileName(sourceFile)}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  <div className="discovery-kpi-popover-footer">
                    <span>Showing {apiEndpoints.length} detected endpoints</span>
                    <span style={{ color: "#94a3b8" }}>{pinnedKpi === "endpoints" ? "Pinned" : "Click to pin"}</span>
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

                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div className="discovery-filter-tabs">
                    <button
                      type="button"
                      className={`discovery-filter-tab ${fileCategoryFilter === "ALL" ? "is-active" : ""}`}
                      onClick={() => setFileCategoryFilter("ALL")}
                    >
                      All Files
                    </button>
                    {javaFiles > 0 && (
                      <button
                        type="button"
                        className={`discovery-filter-tab ${fileCategoryFilter === "JAVA" ? "is-active" : ""}`}
                        onClick={() => setFileCategoryFilter("JAVA")}
                      >
                        Java ({javaFiles})
                      </button>
                    )}

                    {reactFiles > 0 && (
                      <button
                        type="button"
                        className={`discovery-filter-tab ${fileCategoryFilter === "REACT" ? "is-active" : ""}`}
                        onClick={() => setFileCategoryFilter("REACT")}
                      >
                        React ({reactFiles})
                      </button>
                    )}
                    {angularFiles > 0 && (
                      <button
                        type="button"
                        className={`discovery-filter-tab ${fileCategoryFilter === "ANGULAR" ? "is-active" : ""}`}
                        onClick={() => setFileCategoryFilter("ANGULAR")}
                      >
                        Angular ({angularFiles})
                      </button>
                    )}
                    {jspFiles > 0 && (
                      <button
                        type="button"
                        className={`discovery-filter-tab ${fileCategoryFilter === "JSP" ? "is-active" : ""}`}
                        onClick={() => setFileCategoryFilter("JSP")}
                      >
                        JSP ({jspFiles})
                      </button>
                    )}
                    {jsfFiles > 0 && (
                      <button
                        type="button"
                        className={`discovery-filter-tab ${fileCategoryFilter === "JSF" ? "is-active" : ""}`}
                        onClick={() => setFileCategoryFilter("JSF")}
                      >
                        JSF ({jsfFiles})
                      </button>
                    )}
                    <button
                      type="button"
                      className={`discovery-filter-tab ${fileCategoryFilter === "CONFIG" ? "is-active" : ""}`}
                      onClick={() => setFileCategoryFilter("CONFIG")}
                    >
                      Config ({xmlFiles + configFiles})
                    </button>
                    <button
                      type="button"
                      className={`discovery-filter-tab ${fileCategoryFilter === "OTHERS" ? "is-active" : ""}`}
                      onClick={() => setFileCategoryFilter("OTHERS")}
                    >
                      Others
                    </button>
                  </div>

                  <span className="discovery-tree-badge-items">
                    {filteredFileCount} {filteredFileCount === 1 ? "file" : "files"}
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
          <div className={`discovery-bottom-grid ${hasViewTechnology ? "has-4-cols" : "has-3-cols"}`}>
            {/* Card 1: Detected Frameworks & Libraries */}
            <div className="discovery-panel-card">
              <div className="discovery-panel-header">
                <div className="discovery-panel-title-wrap">
                  <div className="discovery-panel-icon" style={{ background: "#faf5ff", color: "#9333ea" }}>
                    <FaPuzzlePiece />
                  </div>
                  <div className="discovery-panel-titles">
                    <h3>Detected Frameworks &amp; Libraries</h3>
                    <p>Major frameworks and build tools</p>
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
                          {renderFrameworkIcon(fw.category, fw.id)}
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

            {/* Card 2: Detected View Technology (if JSP or JSF detected) */}
            {hasViewTechnology && (
              <div className="discovery-panel-card">
                <div className="discovery-panel-header">
                  <div className="discovery-panel-title-wrap">
                    <div className="discovery-panel-icon" style={{ background: "#e0f2fe", color: "#0284c7" }}>
                      <FaEye size={14} />
                    </div>
                    <div className="discovery-panel-titles">
                      <h3>Detected View Technology</h3>
                      <p>Analysis of JSP/JSF view layer technologies</p>
                    </div>
                  </div>
                </div>

                <div className="discovery-viewtech-cards-row">
                  {/* Subcard 1: JSP */}
                  {jspFiles > 0 && (
                    <div className="discovery-viewtech-card">
                      <div className="discovery-viewtech-card-header">
                        <div className="discovery-viewtech-card-title-group">
                          <div className="discovery-viewtech-icon" style={{ background: "#fce7f3", color: "#db2777" }}>
                            <FaCode size={12} />
                          </div>
                          <span className="discovery-viewtech-name">JSP</span>
                        </div>
                        <span className="discovery-viewtech-badge is-detected">
                          Detected
                        </span>
                      </div>
                      <div className="discovery-viewtech-files-count">
                        {jspFiles} {jspFiles === 1 ? "file" : "files"} found
                      </div>
                      <div className="discovery-viewtech-desc">
                        JSP view technology is present in this repository.
                      </div>
                    </div>
                  )}

                  {/* Subcard 2: JSF */}
                  {jsfFiles > 0 && (
                    <div className="discovery-viewtech-card">
                      <div className="discovery-viewtech-card-header">
                        <div className="discovery-viewtech-card-title-group">
                          <div className="discovery-viewtech-icon" style={{ background: "#f5f3ff", color: "#7c3aed" }}>
                            <FaCode size={12} />
                          </div>
                          <span className="discovery-viewtech-name">JSF</span>
                        </div>
                        <span className="discovery-viewtech-badge is-detected">
                          Detected
                        </span>
                      </div>
                      <div className="discovery-viewtech-files-count">
                        {jsfFiles} {jsfFiles === 1 ? "file" : "files"} found
                      </div>
                      <div className="discovery-viewtech-desc">
                        JSF (XHTML) view technology is present in this repository.
                      </div>
                    </div>
                  )}
                </div>

                <div className="discovery-callout-blue discovery-viewtech-callout">
                  <FaInfoCircle color="#2563eb" size={16} style={{ flexShrink: 0 }} />
                  <div className="discovery-viewtech-callout-text">
                    {repoAnalysis?.view_technologies?.summaryMessage || (
                      jspFiles > 0 && jsfFiles === 0
                        ? "JSP files detected. The application uses JSP for its view layer."
                        : jsfFiles > 0 && jspFiles === 0
                        ? "JSF files detected. The application uses JSF for its view layer."
                        : `JSP (${jspFiles} files) and JSF (${jsfFiles} files) detected. Both view technologies are present in this repository.`
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Card 3: Project Structure Summary */}
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
            <div className="discovery-spec-card" style={!isBrdAllowed ? { opacity: 0.65, filter: "grayscale(0.8)" } : undefined}>
              <div className="discovery-panel-header">
                <div className="discovery-panel-title-wrap">
                  <div className="discovery-panel-icon" style={{ background: "#faf5ff", color: "#9333ea" }}>
                    <FaFileAlt />
                  </div>
                  <div className="discovery-panel-titles">
                    <h3>Technical Specification Document</h3>
                    <p>{!isBrdAllowed ? "BRD Document generation is disabled by Super Admin for your user account." : "Generate a repository-grounded technical specification document."}</p>
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

                <h4 className="discovery-spec-h4">{!isBrdAllowed ? "BRD Generation Disabled by Admin" : "Generate Technical Specification Document"}</h4>
                <p className="discovery-spec-desc">
                  {!isBrdAllowed && "Contact your system super admin to request BRD generation feature access."}
                </p>

                <button
                  className="discovery-spec-generate-btn"
                  disabled={
                    !isBrdAllowed ||
                    documentGenerationLoading !== null ||
                    documentPromptLoading ||
                    documentPromptSavingType !== null
                  }
                  style={!isBrdAllowed ? { opacity: 0.5, cursor: "not-allowed", backgroundColor: "#94a3b8" } : undefined}
                  onClick={() => {
                    if (!isBrdAllowed) return;
                    void handleGenerateBrdDocument();
                  }}
                  title={!isBrdAllowed ? "BRD Generation is disabled by Super Admin for your user account" : undefined}
                >
                  <FaFileAlt size={13} />
                  {!isBrdAllowed ? "Disabled by Super Admin" : (documentGenerationLoading ? "Generating Document..." : (technicalSpecificationButtonLabel || "Generate Document"))}
                </button>

                <div className="discovery-document-prompt">
                  <div className="discovery-document-prompt-tabs" role="tablist" aria-label="Document prompt type">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={documentPromptType === "TECHNICAL_SPECIFICATION"}
                      className={documentPromptType === "TECHNICAL_SPECIFICATION" ? "is-active" : ""}
                      disabled={documentPromptSavingType !== null}
                      onClick={() => setDocumentPromptType("TECHNICAL_SPECIFICATION")}
                    >
                      Technical Specification
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={documentPromptType === "BRD"}
                      className={documentPromptType === "BRD" ? "is-active" : ""}
                      disabled={documentPromptSavingType !== null}
                      onClick={() => setDocumentPromptType("BRD")}
                    >
                      BRD
                    </button>
                  </div>
                  <div className="discovery-document-prompt-input-row">
                    <textarea
                      aria-label={`${documentPromptType === "BRD" ? "BRD" : "Technical Specification"} custom document instructions`}
                      className={`discovery-document-prompt-input ${
                        isDocumentPromptSaved ? "is-saved" : "is-pending"
                      }`}
                      value={activeDocumentPrompt}
                      onChange={(event) => {
                        setDocumentPromptDrafts((current) => ({
                          ...current,
                          [documentPromptType]: event.target.value,
                        }));
                        setDocumentPromptSaveError("");
                      }}
                      placeholder="Enter custom document instructions..."
                      rows={3}
                      disabled={documentPromptLoading}
                    />
                    <button
                      type="button"
                      className={`discovery-document-prompt-save ${
                        isDocumentPromptSaved ? "is-saved" : "is-pending"
                      }`}
                      onClick={() => void saveActiveDocumentPrompt()}
                      disabled={documentPromptLoading || documentPromptSavingType !== null}
                      title={isDocumentPromptSaved ? "Prompt saved" : "Save custom document instructions"}
                      aria-label={`Save ${documentPromptType === "BRD" ? "BRD" : "Technical Specification"} prompt`}
                    >
                      {documentPromptSavingType === documentPromptType ? "…" : <FaCheckCircle size={15} />}
                    </button>
                  </div>
                  <div
                    className={`discovery-document-prompt-status ${
                      isDocumentPromptSaved ? "is-saved" : "is-pending"
                    }`}
                    role="status"
                  >
                    {documentPromptLoadError || documentPromptSaveError || documentPromptStatusMessage}
                  </div>
                </div>

                <div className="discovery-spec-footnote">
                  {/* {technicalSpecificationHelperText || "The Technical Specification Document is ready to download."} */}
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Bottom Bar: Navigation Buttons (hidden while analysis is in progress) */}
      {!isDiscoveryPending && (
        <div style={{ ...styles.btnRow, justifyContent: "flex-end" }} className="discovery-nav-btn-row">
          <button
            style={styles.primaryBtn}
            onClick={onContinueToStrategy}
            disabled={isDiscoveryPending}
          >
            {renderForwardButtonLabel("Continue to Strategy")}
          </button>
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
                          {renderFrameworkIcon(fw.category, fw.id)}
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

      {/* All Detected API Endpoints Explorer Modal */}
      {showEndpointsModal && (
        <div className="discovery-modal-overlay" onClick={() => setShowEndpointsModal(false)}>
          <div
            className="discovery-modal-content is-endpoints"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 960, width: "95vw", maxHeight: "88vh", display: "flex", flexDirection: "column" }}
          >
            <div className="discovery-modal-header" style={{ padding: "16px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div className="discovery-panel-icon" style={{ background: "#ecfdf5", color: "#059669" }}>
                  <FaNetworkWired />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#0f172a" }}>
                    Detected API Endpoints
                  </h3>
                  <p style={{ margin: "2px 0 0", fontSize: 12, color: "#64748b" }}>
                    {apiEndpoints.length} total endpoints detected in Spring Boot controllers
                  </p>
                </div>
              </div>
              <button
                className="discovery-preview-close-btn"
                onClick={() => setShowEndpointsModal(false)}
                title="Close"
              >
                <FaTimes size={14} />
              </button>
            </div>

            {/* Filter and Search Bar */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                padding: "12px 20px",
                borderBottom: "1px solid #e2e8f0",
                background: "#f8fafc",
                flexWrap: "wrap",
              }}
            >
              {/* Method filter pills */}
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {["ALL", "GET", "POST", "PUT", "DELETE", "PATCH"].map((m) => {
                  const isActive = endpointFilterMethod === m;
                  const badge = m === "ALL" ? null : getHttpMethodBadge(m);
                  return (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setEndpointFilterMethod(m)}
                      style={{
                        padding: "4px 10px",
                        fontSize: 12,
                        fontWeight: 700,
                        borderRadius: 6,
                        border: isActive ? "1px solid transparent" : "1px solid #cbd5e1",
                        background: isActive ? (badge ? badge.bg : "#0f172a") : "#ffffff",
                        color: isActive ? (badge ? badge.color : "#ffffff") : "#475569",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      {m}
                    </button>
                  );
                })}
              </div>

              {/* Search input */}
              <div style={{ position: "relative", minWidth: 240, flex: "1 1 200px", maxWidth: 360 }}>
                <input
                  type="text"
                  placeholder="Filter by path, controller, method..."
                  value={endpointSearchQuery}
                  onChange={(e) => setEndpointSearchQuery(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "6px 28px 6px 10px",
                    fontSize: 12,
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    outline: "none",
                    background: "#ffffff",
                    boxSizing: "border-box",
                  }}
                />
                {endpointSearchQuery && (
                  <button
                    type="button"
                    onClick={() => setEndpointSearchQuery("")}
                    style={{
                      position: "absolute",
                      right: 8,
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      color: "#94a3b8",
                      padding: 0,
                    }}
                  >
                    <FaTimes size={10} />
                  </button>
                )}
              </div>
            </div>

            {/* Modal Body: Table of endpoints */}
            <div className="discovery-modal-body" style={{ padding: 0, overflowY: "auto", flex: 1 }}>
              {filteredEndpoints.length === 0 ? (
                <div style={{ padding: 40, textAlign: "center", color: "#64748b", fontSize: 13 }}>
                  {apiEndpoints.length === 0
                    ? "No REST API endpoints detected in this repository."
                    : "No endpoints match the selected filter."}
                </div>
              ) : (
                <table className="discovery-endpoints-table">
                  <thead>
                    <tr>
                      <th style={{ width: 90 }}>HTTP Method</th>
                      <th>Path</th>
                      <th>Controller</th>
                      <th>Method</th>
                      <th>Source File</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEndpoints.map((ep, idx) => {
                      const method = (ep.httpMethod || ep.method || "GET").toUpperCase();
                      const methodBadge = getHttpMethodBadge(method);
                      const path = ep.path || ep.urlPath || ep.endpoint || "/";
                      const controllerName = ep.controller || ep.className || "Controller";
                      const methodName = ep.handlerMethod || ep.methodName || "—";
                      const sourceFile = ep.sourceFile || ep.file || "";

                      return (
                        <tr key={ep.id || `${method}-${path}-${idx}`} className="discovery-endpoint-row">
                          <td>
                            <span
                              style={{
                                display: "inline-block",
                                fontSize: 11,
                                fontWeight: 800,
                                padding: "2px 8px",
                                borderRadius: 4,
                                background: methodBadge.bg,
                                color: methodBadge.color,
                                letterSpacing: "0.03em",
                              }}
                            >
                              {method}
                            </span>
                          </td>
                          <td style={{ fontFamily: "monospace", fontSize: 12, fontWeight: 600, color: "#0f172a" }}>
                            {path}
                          </td>
                          <td style={{ color: "#334155", fontWeight: 500 }}>
                            {controllerName}
                          </td>
                          <td style={{ color: "#64748b", fontFamily: "monospace", fontSize: 11 }}>
                            {methodName}
                          </td>
                          <td>
                            {sourceFile ? (
                              <button
                                type="button"
                                onClick={() => {
                                  setShowEndpointsModal(false);
                                  handleSelectPopoverFile(sourceFile);
                                }}
                                title={`Open file preview: ${sourceFile}`}
                                style={{
                                  background: "none",
                                  border: "none",
                                  padding: 0,
                                  color: "#2563eb",
                                  cursor: "pointer",
                                  fontSize: 12,
                                  textDecoration: "underline",
                                  textAlign: "left",
                                }}
                              >
                                {extractFileName(sourceFile)}
                              </button>
                            ) : (
                              <span style={{ color: "#94a3b8" }}>—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
