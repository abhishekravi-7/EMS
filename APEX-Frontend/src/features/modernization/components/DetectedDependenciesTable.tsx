import React, { useState, useMemo, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  FaChevronLeft,
  FaChevronRight,
  FaCheckCircle,
  FaExchangeAlt,
  FaShieldAlt,
  FaFilter,
  FaTimes,
  FaInfoCircle,
  FaChevronDown,
  FaChevronUp,
  FaCode,
  FaCogs,
  FaLayerGroup,
  FaDatabase,
  FaFileCode,
  FaArrowRight,
  FaExclamationTriangle,
} from "react-icons/fa";

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

export interface RiskCriterion {
  level: MigrationRisk;
  title: string;
  badgeColor: { text: string; background: string; border: string };
  summary: string;
  criteria: string[];
  examples: string;
}

export const RISK_CRITERIA_DETAILS: Record<MigrationRisk, RiskCriterion> = {
  CRITICAL: {
    level: "CRITICAL",
    title: "Critical Migration Risk",
    badgeColor: { text: "#991b1b", background: "#fef2f2", border: "#fecaca" },
    summary: "Blocks application startup or requires fundamental runtime / platform architecture overhaul.",
    criteria: [
      "Core Java Runtime major version upgrade (e.g. JDK 8 to 17/21).",
      "Bytecode incompatibility with compiler target (e.g. Java 8 bytecode on Java 17+ JVM).",
      "Usage of removed JDK internal APIs (sun.misc.*, Unsafe, removed Nashorn/Corba).",
      "End-of-Life (EOL) dependencies with unpatched critical vulnerabilities or missing JDK support.",
    ],
    examples: "Java Runtime, Log4j 1.x, legacy native/sun.* internal libraries",
  },
  HIGH: {
    level: "HIGH",
    title: "High Migration Risk",
    badgeColor: { text: "#c2410c", background: "#fff7ed", border: "#ffedd5" },
    summary: "Major framework generation leap requiring code refactoring or package namespace migration.",
    criteria: [
      "Jakarta EE namespace transition (javax.* → jakarta.* imports).",
      "Spring Framework 5.x to 6.x / Spring Boot 2.x to 3.x major upgrades.",
      "Hibernate ORM 5 to 6 upgrade with query/dialect breaking changes.",
      "Removed or fundamentally redesigned classes and configuration properties.",
    ],
    examples: "javax.validation, javax.persistence, spring-boot 2.x → 3.x, hibernate-core 5.x",
  },
  MEDIUM: {
    level: "MEDIUM",
    title: "Medium Migration Risk",
    badgeColor: { text: "#b45309", background: "#fffbeb", border: "#fde68a" },
    summary: "Requires configuration adjustments, manual review, or dependency coordination.",
    criteria: [
      "Dependencies requiring manual review or candidate validation.",
      "Obsolete transitive dependencies being removed (e.g. hibernate-entitymanager).",
      "Minor version jumps with notable behavioral shifts (e.g. SnakeYAML 2.x constructor safety).",
      "Pre-release, snapshot, or unverified version tags.",
    ],
    examples: "snakeyaml, hibernate-entitymanager (REMOVE), review-required modules",
  },
  LOW: {
    level: "LOW",
    title: "Low Migration Risk",
    badgeColor: { text: "#047857", background: "#ecfdf5", border: "#a7f3d0" },
    summary: "Directly managed by Target BOM or already backward compatible with zero code changes.",
    criteria: [
      "Directly managed by Target Spring Boot BOM with backward-compatible API.",
      "Current dependency version already matches or exceeds target requirement.",
      "Standard patch or minor upgrades with verified backward compatibility.",
      "Standard logging or serialization facades (SLF4J, Logback, Jackson, Lombok).",
    ],
    examples: "logback-classic, slf4j-api, jackson-databind, lombok, already compatible libraries",
  },
};

export function determineDependencyGroup(
  gid: string,
  aid: string,
  backendCategory?: string
): "Framework" | "Library" | "Dependency" {
  const g = (gid || "").toLowerCase().trim();
  const a = (aid || "").toLowerCase().trim();
  const cat = (backendCategory || "").toLowerCase().trim();

  // 1. FRAMEWORK:
  // All Spring Boot starters, Spring Framework modules, Spring Security, plus other application frameworks
  if (
    g.startsWith("org.springframework") ||
    a.startsWith("spring-boot") ||
    a.startsWith("spring-") ||
    g.includes("quarkus") ||
    a.includes("quarkus") ||
    g.includes("micronaut") ||
    a.includes("micronaut") ||
    g.includes("struts") ||
    a.includes("struts") ||
    g.includes("com.google.inject") ||
    a.includes("guice") ||
    cat === "framework"
  ) {
    return "Framework";
  }

  // 2. DEPENDENCY:
  // Low-level parser / formats, bytecode manipulation, reflection/compiler helpers, and auxiliary transitives
  if (
    a.includes("snakeyaml") ||
    a.includes("json-smart") ||
    a.includes("accessors-smart") ||
    a.includes("classmate") ||
    g.includes("ow2.asm") ||
    a === "asm" ||
    a.startsWith("asm-") ||
    a.includes("byte-buddy") ||
    a.includes("bytebuddy") ||
    a.includes("cglib") ||
    a.includes("javassist") ||
    a.includes("jboss-logging") ||
    a.includes("objenesis") ||
    cat === "dependency" ||
    cat === "build" ||
    cat === "other"
  ) {
    return "Dependency";
  }

  // 3. LIBRARY:
  // Reusable functional modules called by the application:
  // - Logging: Logback, Log4j, SLF4J
  // - Serialization: Jackson, Gson
  // - Embedded Servers: Tomcat Embed, Jetty, Undertow
  // - Persistence & ORM: Hibernate, JPA, MyBatis, JDBC drivers
  // - Testing: JUnit, Mockito, AssertJ, Hamcrest, JSONPath
  // - Developer utilities: Lombok, Apache Commons, Guava
  // - Standard Specifications & APIs: Jakarta EE / Java EE (annotation, validation, persistence, servlet, transaction, etc.)
  if (
    g.startsWith("jakarta.") ||
    a.startsWith("jakarta.") ||
    g.startsWith("javax.") ||
    a.startsWith("javax.") ||
    a.includes("validation-api") ||
    a.includes("annotation-api") ||
    a.includes("persistence-api") ||
    a.includes("servlet-api") ||
    g.includes("logback") ||
    a.includes("logback") ||
    g.includes("log4j") ||
    a.includes("log4j") ||
    g.includes("slf4j") ||
    a.includes("slf4j") ||
    g.includes("hibernate") ||
    a.includes("hibernate") ||
    g.includes("jackson") ||
    a.includes("jackson") ||
    g.includes("tomcat") ||
    a.includes("tomcat") ||
    a.includes("jetty") ||
    a.includes("lombok") ||
    a.includes("junit") ||
    a.includes("mockito") ||
    a.includes("assertj") ||
    a.includes("json-path") ||
    a.includes("jsonpath") ||
    a.includes("commons") ||
    a.includes("guava") ||
    a.includes("mysql") ||
    a.includes("postgresql") ||
    a.includes("h2") ||
    ["persistence", "security", "database", "testing", "logging", "web", "utility", "library"].includes(cat)
  ) {
    return "Library";
  }

  return "Dependency";
}

export function resolveSourceChangesDescription(
  gid: string,
  aid: string,
  currentVer: string,
  targetVer: string,
  action: DependencyAction,
  isJavaxToJakarta: boolean,
  rawSourceChanges?: string,
  targetJavaNum: number = 21,
  selectedBootVersion: string = "3.2.5",
  buildTool: string = "Maven"
): string {
  const g = (gid || "").toLowerCase();
  const a = (aid || "").toLowerCase();
  const cur = (currentVer || "").trim();
  const tgt = (targetVer || "").trim();
  const buildFile = buildTool === "Gradle" ? "build.gradle" : "pom.xml";
  const depLabel = aid || gid || "dependency";
  const verInfo = cur && tgt && cur !== "Unknown" && cur !== tgt ? ` (${cur} → ${tgt})` : cur && cur !== "Unknown" ? ` (${cur})` : "";

  // If a non-generic, high-quality custom description is provided, preserve it
  const rawLower = (rawSourceChanges || "").toLowerCase();
  const isStaleJakarta = targetJavaNum < 17 && (rawLower.includes("jakarta") || rawLower.includes("spring boot 3"));
  const isGeneric =
    rawLower.includes("verify compatibility") ||
    rawLower.includes("build manifest version property update") ||
    rawLower.includes("none") ||
    rawLower.includes("upgrade dependency version") ||
    rawLower.includes("update to latest") ||
    rawLower.includes("managed directly by") ||
    rawLower === "n/a" ||
    rawLower === "";

  if (rawSourceChanges && !isGeneric && !isStaleJakarta && rawSourceChanges.trim().length > 25 && !rawLower.startsWith("refactor package imports")) {
    return rawSourceChanges;
  }

  // 1. Jakarta / javax package namespace shift (ONLY when target Java >= 17 and migrating to Jakarta)
  if (isJavaxToJakarta) {
    if (a.includes("validation")) {
      return `Refactor package imports in source code: javax.validation.* → jakarta.validation.* (e.g., @NotNull, @Size, @Valid) for ${depLabel}${verInfo} under Spring Boot ${selectedBootVersion}.`;
    }
    if (a.includes("persistence")) {
      return `Refactor package imports in entity classes: javax.persistence.* → jakarta.persistence.* (e.g., @Entity, @Id, @Table) for ${depLabel}${verInfo} under Spring Boot ${selectedBootVersion}.`;
    }
    if (a.includes("servlet")) {
      return `Refactor package imports: javax.servlet.* → jakarta.servlet.* (e.g., HttpServletRequest, Filter, ServletContext) for ${depLabel}${verInfo}.`;
    }
    if (a.includes("transaction")) {
      return `Refactor package imports: javax.transaction.* → jakarta.transaction.* (e.g., @Transactional) for ${depLabel}${verInfo}.`;
    }
    if (a.includes("annotation")) {
      return `Refactor package imports: javax.annotation.* → jakarta.annotation.* (e.g., @PostConstruct, @PreDestroy, @Resource) for ${depLabel}${verInfo}.`;
    }
    if (a.includes("ws.rs") || a.includes("jaxrs")) {
      return `Refactor package imports: javax.ws.rs.* → jakarta.ws.rs.* (e.g., @Path, @GET, @POST) for ${depLabel}${verInfo}.`;
    }
    if (a.includes("mail")) {
      return `Refactor package imports: javax.mail.* → jakarta.mail.* for JavaMail APIs in ${depLabel}${verInfo}.`;
    }
    if (a.includes("xml.bind") || a.includes("jaxb")) {
      return `Refactor package imports: javax.xml.bind.* → jakarta.xml.bind.* across XML serialization code for ${depLabel}${verInfo}.`;
    }
    const cleanAid = a.replace("-api", "").replace("javax.", "");
    return `Refactor package imports: ${gid || "javax"}.* → jakarta.${cleanAid || aid}.* across source code for ${depLabel}${verInfo}.`;
  }

  // For Java < 17 targeting javax.* dependencies, retain standard Java EE 8 namespace
  if (targetJavaNum < 17 && (g.startsWith("javax.") || a.startsWith("javax.") || a === "validation-api")) {
    return `No source-code modifications required. Standard javax.* package namespace is retained for ${depLabel}${verInfo} under Spring Boot ${selectedBootVersion} on Java ${targetJavaNum}.`;
  }

  // 2. Already Compatible state
  if (action === "ALREADY COMPATIBLE" || (cur && tgt && cur.toLowerCase() === tgt.toLowerCase() && cur !== "Unknown")) {
    if (g.startsWith("jakarta.") || a.startsWith("jakarta.")) {
      return `No source-code modifications required. Standard Jakarta annotations in ${depLabel}${verInfo} are fully compatible with target Java ${targetJavaNum} and Spring Boot ${selectedBootVersion}.`;
    }
    if (a.includes("snakeyaml")) {
      return `No source-code modifications required. Existing YAML parsing configuration in ${depLabel}${verInfo} is compatible with target Java ${targetJavaNum} runtime.`;
    }
    if (a.includes("jackson")) {
      return `No source-code modifications required. Existing Jackson serialization configuration in ${depLabel}${verInfo} is compatible with target Java ${targetJavaNum} runtime.`;
    }
    if (a.includes("slf4j") || a.includes("logback") || a.includes("log4j")) {
      return `No source-code modifications required. Logging configuration in ${depLabel}${verInfo} matches target Java ${targetJavaNum} runtime baseline.`;
    }
    if (a.includes("spring")) {
      return `No source-code modifications required. Framework configuration for ${depLabel}${verInfo} already matches target Spring Boot ${selectedBootVersion} BOM.`;
    }
    return `No source-code modifications required. Current version of ${depLabel}${verInfo} is already compatible with target Java ${targetJavaNum} and Spring Boot ${selectedBootVersion}.`;
  }

  // 3. Jackson family
  if (a.includes("jackson") || g.includes("jackson")) {
    if (a.includes("databind")) {
      return `No source-code modifications required. Jackson databind and ObjectMapper APIs in ${depLabel}${verInfo} remain backward compatible with Java ${targetJavaNum}.`;
    }
    if (a.includes("annotations")) {
      return `No source-code modifications required. Standard JSON annotations (@JsonProperty, @JsonIgnore, @JsonInclude) in ${depLabel}${verInfo} remain backward compatible.`;
    }
    if (a.includes("core")) {
      return `No source-code modifications required. Low-level JsonParser and JsonGenerator streaming APIs in ${depLabel}${verInfo} remain backward compatible.`;
    }
    if (a.includes("jdk8") || a.includes("jsr310")) {
      return `No source-code modifications required. ${depLabel}${verInfo} is managed transparently by target Spring Boot ${selectedBootVersion} BOM.`;
    }
    return `No source-code modifications required. ${depLabel}${verInfo} APIs remain fully backward compatible with target Java ${targetJavaNum}.`;
  }

  // 4. SLF4J / Logging Bridges
  if (a.includes("slf4j") || g.includes("slf4j")) {
    if (a.includes("jul-to-slf4j") || a.includes("jcl-over-slf4j") || a.includes("log4j-over-slf4j")) {
      return `No source-code modifications required. ${depLabel}${verInfo} preserves backward-compatible Logger APIs with ServiceLoader provider model in Java ${targetJavaNum}.`;
    }
    if (a.includes("slf4j-api")) {
      return `No source-code modifications required. SLF4J Logger API in ${depLabel}${verInfo} retains backward compatibility; provider binding is handled via ServiceLoader.`;
    }
    return `No source-code modifications required. SLF4J logging facade in ${depLabel}${verInfo} preserves backward compatibility with Java ${targetJavaNum}.`;
  }

  // 5. Logback
  if (a.includes("logback")) {
    return `No source-code modifications required. Standard logback.xml appenders and SLF4J logger calls in ${depLabel}${verInfo} remain compatible with Java ${targetJavaNum}.`;
  }

  // 6. SnakeYAML
  if (a.includes("snakeyaml")) {
    return targetJavaNum >= 17
      ? `Audit custom Yaml() constructor usage in ${depLabel}${verInfo}; SnakeYAML 2.x requires LoaderOptions(SafeConstructor) when parsing untrusted YAML.`
      : `No source-code modifications required. Standard YAML parsing contracts in ${depLabel}${verInfo} remain supported under Spring Boot ${selectedBootVersion}.`;
  }

  // 7. Spring Boot starters
  if (g === "org.springframework.boot" || a.includes("spring-boot")) {
    if (a.includes("starter-web")) {
      return targetJavaNum >= 17
        ? `Refactor package imports in controllers and filters: javax.servlet.* → jakarta.servlet.*. Replace deprecated WebMvcConfigurerAdapter with WebMvcConfigurer interface for ${depLabel}${verInfo}.`
        : `No namespace migration required. Retains javax.servlet.* namespace under Spring Boot ${selectedBootVersion}. Replace deprecated WebMvcConfigurerAdapter with WebMvcConfigurer interface if present for ${depLabel}${verInfo}.`;
    }
    if (a.includes("starter-data-jpa")) {
      return targetJavaNum >= 17
        ? `Refactor package imports in entity classes: javax.persistence.* → jakarta.persistence.*. Audit custom repository queries for Hibernate 6 dialect and Spring Data 3.x compatibility in ${depLabel}${verInfo}.`
        : `No namespace migration required. Retains javax.persistence.* namespace and Hibernate 5.6.x under Spring Boot ${selectedBootVersion} for ${depLabel}${verInfo}.`;
    }
    if (a.includes("starter-security")) {
      return targetJavaNum >= 17
        ? `Migrate deprecated WebSecurityConfigurerAdapter to SecurityFilterChain @Bean in security configuration. Replace antMatchers() with requestMatchers() for ${depLabel}${verInfo}.`
        : `Spring Security 5.7 in Spring Boot ${selectedBootVersion} retains WebSecurityConfigurerAdapter compatibility. Migrating to SecurityFilterChain @Bean is recommended for ${depLabel}${verInfo}.`;
    }
    if (a.includes("starter-json")) {
      return `Update BOM version in ${buildFile}. Jackson ObjectMapper configuration in ${depLabel}${verInfo} is handled transparently by Spring Boot ${selectedBootVersion} BOM.`;
    }
    if (a.includes("starter-validation")) {
      return targetJavaNum >= 17
        ? `Refactor package imports in model beans: javax.validation.* → jakarta.validation.* (e.g., @NotNull, @Size, @Valid) for ${depLabel}${verInfo}.`
        : `No namespace migration required. Retains javax.validation.* annotations under Spring Boot ${selectedBootVersion} for ${depLabel}${verInfo}.`;
    }
    if (a.includes("starter-actuator")) {
      return targetJavaNum >= 17
        ? `Audit management endpoint path mappings and security configurations in application.properties/yml for ${depLabel}${verInfo} under Spring Boot ${selectedBootVersion}.`
        : `No source-code modifications required. Retains Spring Boot ${selectedBootVersion} actuator management endpoint configurations for ${depLabel}${verInfo}.`;
    }
    if (a.includes("starter-test")) {
      return targetJavaNum >= 17
        ? `Update test annotations for ${depLabel}${verInfo}: Replace legacy JUnit 4 imports with JUnit 5 (@Test org.junit.jupiter.api.Test) and @ExtendWith(SpringExtension.class).`
        : `No source-code modifications required. Standard test annotations and Spring Runner execute under Spring Boot ${selectedBootVersion} on Java ${targetJavaNum} for ${depLabel}${verInfo}.`;
    }
    if (a.includes("starter-batch")) {
      return targetJavaNum >= 17
        ? `Migrate StepBuilderFactory and JobBuilderFactory to JobRepository-based JobBuilder and StepBuilder for Spring Batch 5 in ${depLabel}${verInfo}.`
        : `No source-code modifications required. StepBuilderFactory and JobBuilderFactory remain supported in Spring Batch 4.x for ${depLabel}${verInfo}.`;
    }
    if (a.includes("starter-mail")) {
      return targetJavaNum >= 17
        ? `Refactor package imports: javax.mail.* → jakarta.mail.* for MIME message and JavaMailSender implementations in ${depLabel}${verInfo}.`
        : `No source-code modifications required. Retains javax.mail.* under Spring Boot ${selectedBootVersion} for ${depLabel}${verInfo}.`;
    }
    if (a.includes("starter-thymeleaf")) {
      return targetJavaNum >= 17
        ? `Update Thymeleaf template dialect syntax and layout integrations for Spring 6 / Jakarta EE 10 in ${depLabel}${verInfo}.`
        : `No source-code modifications required. Standard Thymeleaf template syntax is compatible with Spring Boot ${selectedBootVersion} for ${depLabel}${verInfo}.`;
    }
    if (a.includes("starter-aop")) {
      return `No source-code modifications required. AspectJ and Spring AOP annotations (@Aspect, @Around) in ${depLabel}${verInfo} remain backward compatible.`;
    }
    return targetJavaNum >= 17
      ? `Update starter BOM version in ${buildFile}. Audit application properties for Spring Boot ${selectedBootVersion} property changes in ${depLabel}${verInfo}.`
      : `Update starter BOM version in ${buildFile}. Retains Spring Boot ${selectedBootVersion} configuration properties for ${depLabel}${verInfo}.`;
  }

  // 8. Spring Data
  if (g.startsWith("org.springframework.data") || a.includes("spring-data")) {
    return targetJavaNum >= 17
      ? `Audit custom repository interfaces; Spring Data 3.x in Spring Boot ${selectedBootVersion} deprecates legacy query execution and changes null-safety contracts for ${depLabel}${verInfo}.`
      : `No source-code modifications required. Spring Data repository contracts in ${depLabel}${verInfo} remain backward compatible under Spring Boot ${selectedBootVersion}.`;
  }

  // 9. Spring Framework core
  if (g.startsWith("org.springframework")) {
    if (a.includes("web")) {
      return targetJavaNum >= 17
        ? `Refactor package imports: javax.servlet.* → jakarta.servlet.* in controllers. Audit Controller advice and HTTP message converters for Spring 6 in ${depLabel}${verInfo}.`
        : `No source-code modifications required. Retains javax.servlet.* namespace and Spring MVC 5.3 contracts in ${depLabel}${verInfo}.`;
    }
    if (a.includes("tx") || a.includes("jdbc")) {
      return targetJavaNum >= 17
        ? `Refactor package imports: javax.transaction.* → jakarta.transaction.*. Audit custom JdbcTemplate RowMappers for ${depLabel}${verInfo}.`
        : `No source-code modifications required. Retains javax.transaction.* namespace and Spring 5.3 contracts in ${depLabel}${verInfo}.`;
    }
    if (a.includes("core") || a.includes("beans") || a.includes("context")) {
      return `No source-code modifications required. Standard IoC/DI annotations (@Component, @Autowired, @Service) in ${depLabel}${verInfo} remain backward compatible.`;
    }
    return targetJavaNum >= 17
      ? `API compatibility review for Spring Framework 6.x. Audit reflective calls and deprecated method invocations for ${depLabel}${verInfo}.`
      : `No source-code modifications required. Spring Framework 5.3 baseline preserves backward compatibility for ${depLabel}${verInfo}.`;
  }

  // 10. Jakarta namespace
  if (g.startsWith("jakarta.") || a.startsWith("jakarta.")) {
    return `No source-code modifications required. Jakarta EE namespace and annotations in ${depLabel}${verInfo} are already in place for Java ${targetJavaNum}.`;
  }

  // 11. Hibernate
  if (a.includes("hibernate")) {
    if (a.includes("entitymanager")) {
      return targetJavaNum >= 17
        ? `Remove obsolete dependency ${depLabel} from ${buildFile}; EntityManager is bundled directly in hibernate-core 6.x.`
        : `Entity manager module ${depLabel}${verInfo} is managed by Spring Boot ${selectedBootVersion} BOM in ${buildFile}.`;
    }
    if (a.includes("validator")) {
      return targetJavaNum >= 17
        ? `Refactor package imports: javax.validation.* → jakarta.validation.* in ${depLabel}${verInfo}. Standard constraint validators remain compatible.`
        : `No namespace migration required. Retains javax.validation.* constraint validators under Spring Boot ${selectedBootVersion} for ${depLabel}${verInfo}.`;
    }
    return targetJavaNum >= 17
      ? `Refactor annotations: javax.persistence.* → jakarta.persistence.*. Audit custom UserType implementations and query syntax for Hibernate 6.x in ${depLabel}${verInfo}.`
      : `No source-code modifications required. Retains javax.persistence.* annotations and Hibernate 5.6.x dialect configurations for ${depLabel}${verInfo}.`;
  }

  // 12. Lombok
  if (a.includes("lombok")) {
    return `No Java source changes. Ensure Lombok version in ${buildFile}${verInfo} supports Java ${targetJavaNum} bytecode compiler support.`;
  }

  // 13. Tomcat
  if (a.includes("tomcat")) {
    return targetJavaNum >= 17
      ? `Refactor custom Servlet filters or web.xml to Jakarta Servlet 6.0 specifications for embedded Tomcat in ${depLabel}${verInfo}.`
      : `No source-code modifications required. Embedded Tomcat 9.0 in ${depLabel}${verInfo} operates under Java EE 8 / Servlet 4.0 specification on Java ${targetJavaNum}.`;
  }

  // 14. Database drivers
  if (a.includes("mysql")) {
    return `Update datasource configuration: Set driver-class-name to com.mysql.cj.jdbc.Driver for ${depLabel}${verInfo} if legacy com.mysql.jdbc.Driver is configured.`;
  }
  if (a.includes("postgresql")) {
    return `No source-code modifications required. PostgreSQL JDBC driver in ${depLabel}${verInfo} is backward compatible with Java ${targetJavaNum}.`;
  }
  if (a.includes("h2") || a.includes("hsqldb")) {
    return `Audit SQL queries and test schema DDL for H2 2.x reserved keywords (e.g. USER, VALUE, KEY) in ${depLabel}${verInfo}. Update JDBC URL syntax if required.`;
  }

  // 15. Testing
  if (a === "junit" || (g === "junit" && a.includes("junit"))) {
    return targetJavaNum >= 17
      ? `Refactor unit tests in ${depLabel}${verInfo}: Replace legacy org.junit.Test with org.junit.jupiter.api.Test and assert/assume methods.`
      : `No source-code modifications required. JUnit test classes execute under Java ${targetJavaNum} and Spring Boot ${selectedBootVersion} test runner for ${depLabel}${verInfo}.`;
  }
  if (a.includes("junit-jupiter")) {
    return `No source-code modifications required. JUnit Jupiter 5 test annotations and assertions in ${depLabel}${verInfo} remain backward compatible.`;
  }
  if (a.includes("mockito")) {
    return `No source-code modifications required. Standard @Mock, @InjectMocks, and Mockito.when() APIs in ${depLabel}${verInfo} remain compatible.`;
  }
  if (a.includes("assertj")) {
    return `No source-code modifications required. AssertJ fluent assertion APIs (assertThat) in ${depLabel}${verInfo} remain backward compatible.`;
  }

  // 16. Common utilities
  if (a.includes("commons-lang") || a.includes("commons-collections") || a.includes("commons-io") || a.includes("guava")) {
    return `No source-code modifications required. Standard utility APIs in ${depLabel}${verInfo} remain backward compatible with Java ${targetJavaNum}.`;
  }

  // Action-based defaults
  if (action === "REMOVE") {
    return `Remove dependency declaration ${depLabel} from ${buildFile}. Clean up any unused imports from project source files.`;
  }
  if (action === "REPLACE") {
    return targetJavaNum >= 17
      ? `Replace ${depLabel} coordinate in ${buildFile} with ${tgt} and refactor package import statements across the codebase.`
      : `Align dependency ${depLabel} coordinate in ${buildFile} with Spring Boot ${selectedBootVersion} BOM.`;
  }
  if (action === "UPGRADE") {
    return `No source-code modifications required. Minor/patch version update for ${depLabel}${verInfo} in ${buildFile} maintains binary and source API compatibility.`;
  }
  if (action === "MAJOR UPGRADE") {
    return targetJavaNum >= 17
      ? `Update dependency ${depLabel}${verInfo} in ${buildFile}. Audit public API invocations against the library's major version migration guide.`
      : `Update dependency ${depLabel}${verInfo} in ${buildFile}. Aligns with Spring Boot ${selectedBootVersion} BOM baseline on Java ${targetJavaNum}.`;
  }

  return `Review ${depLabel}${verInfo} API calls against Java ${targetJavaNum} release notes for deprecated method removals.`;
}

function resolveTargetVersionFallback(
  gid: string,
  aid: string,
  currentVer: string,
  targetJavaVersion?: string,
  targetBootVersion?: string,
  buildTool: string = "Maven"
) {
  const g = (gid || "").toLowerCase();
  const a = (aid || "").toLowerCase();
  const ver = (currentVer || "Unknown").trim();
  const javaNum = parseInt((targetJavaVersion || "21").replace(/\D/g, "") || "21", 10);
  const bootVer = targetBootVersion || (javaNum >= 17 ? "3.2.5" : "2.7.18");
  const fwVer = bootVer.startsWith("3.") ? "6.1.14" : "5.3.31";

  let tgtDep = `${gid}:${aid}`;
  let tgtVer = bootVer;
  let action: DependencyAction = "UPGRADE";
  let reasoning = `Managed directly by Target Spring Boot ${bootVer} BOM.`;
  let risk: MigrationRisk = "LOW";

  if (g === "org.springframework.boot" || a.includes("spring-boot")) {
    tgtVer = bootVer;
    if (javaNum < 17) {
      action = "UPGRADE";
      reasoning = `Target Spring Boot ${bootVer} manages starter dependencies for Java ${javaNum} while preserving Java EE 8 compatibility.`;
      risk = "LOW";
    } else {
      action = "MAJOR UPGRADE";
      reasoning = `The detected Spring Boot version belongs to an earlier generation. Target Spring Boot ${bootVer} manages all starter dependencies for Java ${javaNum}.`;
      risk = "HIGH";
    }
  } else if (g === "org.springframework" || (g.startsWith("org.springframework") && !g.includes("boot") && !g.includes("data"))) {
    tgtVer = fwVer;
    if (javaNum < 17) {
      action = "UPGRADE";
      reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Spring Framework ${fwVer}). Preserves Spring 5.3 API baseline.`;
      risk = "LOW";
    } else {
      action = "MAJOR UPGRADE";
      reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Spring Framework ${fwVer}). Crosses major Spring generation.`;
      risk = "HIGH";
    }
  } else if (g.startsWith("org.springframework.data") || a.includes("spring-data")) {
    tgtVer = javaNum >= 17 ? "3.2.5" : "2.7.18";
    if (javaNum < 17) {
      action = "UPGRADE";
      reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Spring Data 2021.2 release train).`;
      risk = "LOW";
    } else {
      action = "MAJOR UPGRADE";
      reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Spring Data 2023.1.5 release train).`;
      risk = "HIGH";
    }
  } else if (g.startsWith("javax.") || a.startsWith("javax.") || a === "validation-api") {
    if (javaNum >= 17) {
      action = "REPLACE";
      reasoning = `The old javax.* API belongs to the pre-Jakarta namespace. Spring Boot 3.x uses Jakarta EE APIs. Requires dependency-coordinate and source-package migration.`;
      risk = "HIGH";
      if (a.includes("validation")) {
        tgtDep = "jakarta.validation:jakarta.validation-api";
        tgtVer = "3.0.2";
      } else if (a.includes("persistence")) {
        tgtDep = "jakarta.persistence:jakarta.persistence-api";
        tgtVer = "3.1.0";
      } else if (a.includes("servlet")) {
        tgtDep = "jakarta.servlet:jakarta.servlet-api";
        tgtVer = "6.0.0";
      } else if (a.includes("transaction")) {
        tgtDep = "jakarta.transaction:jakarta.transaction-api";
        tgtVer = "2.0.1";
      } else if (a.includes("annotation")) {
        tgtDep = "jakarta.annotation:jakarta.annotation-api";
        tgtVer = "2.1.1";
      } else if (a.includes("ws.rs") || a.includes("jaxrs")) {
        tgtDep = "jakarta.ws.rs:jakarta.ws.rs-api";
        tgtVer = "3.1.0";
      } else {
        tgtDep = `jakarta.${a}:jakarta.${a}`;
        tgtVer = "3.0.0";
      }
    } else {
      tgtDep = `${gid}:${aid}`;
      tgtVer = ver && ver !== "Unknown" ? ver : (a.includes("validation") ? "2.0.1.Final" : "1.2");
      action = (ver && ver.toLowerCase() === tgtVer.toLowerCase()) ? "ALREADY COMPATIBLE" : "UPGRADE";
      reasoning = `Managed by Spring Boot ${bootVer} BOM retaining standard javax.* package namespace under Java EE 8 specification.`;
      risk = "LOW";
    }
  } else if (a.includes("lombok")) {
    tgtVer = javaNum >= 17 ? "1.18.36" : "1.18.30";
    action = "UPGRADE";
    reasoning = `Upgraded Lombok version required for Java ${javaNum} bytecode compiler support.`;
    risk = "LOW";
  } else if (a.includes("hibernate")) {
    if (a.includes("entitymanager")) {
      if (javaNum >= 17) {
        tgtDep = "Not Required";
        tgtVer = "N/A";
        action = "REMOVE";
        reasoning = "The old separate Hibernate EntityManager artifact is not required in Hibernate ORM 6 because functionality is integrated into hibernate-core.";
        risk = "MEDIUM";
      } else {
        tgtVer = "5.6.15.Final";
        action = "UPGRADE";
        reasoning = `Managed by Spring Boot ${bootVer} BOM (Hibernate 5.6.15.Final).`;
        risk = "LOW";
      }
    } else {
      tgtVer = javaNum >= 17 ? "6.4.4.Final" : "5.6.15.Final";
      action = javaNum >= 17 ? "MAJOR UPGRADE" : "UPGRADE";
      reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Hibernate ORM ${tgtVer}).`;
      risk = javaNum >= 17 ? "HIGH" : "LOW";
    }
  } else if (a.includes("jackson")) {
    tgtVer = javaNum >= 17 ? "2.15.4" : "2.13.5";
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Jackson ${tgtVer}).`;
    risk = "LOW";
  } else if (a.includes("logback")) {
    tgtVer = javaNum >= 11 ? "1.4.14" : "1.2.13";
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Logback ${tgtVer}).`;
    risk = "LOW";
  } else if (a.includes("slf4j")) {
    tgtVer = javaNum >= 11 ? "2.0.13" : "1.7.36";
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (SLF4J ${tgtVer}).`;
    risk = "LOW";
  } else if (a.includes("snakeyaml")) {
    tgtVer = javaNum >= 17 ? "2.2" : "1.33";
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (SnakeYAML ${tgtVer}).`;
    risk = "LOW";
  } else if (a.includes("tomcat")) {
    tgtVer = javaNum >= 17 ? "10.1.20" : "9.0.83";
    action = javaNum >= 17 ? "MAJOR UPGRADE" : "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (Tomcat ${tgtVer}${javaNum >= 17 ? ", Jakarta Servlet 6.0 compatible" : ", Servlet 4.0 compatible"}).`;
    risk = javaNum >= 17 ? "HIGH" : "LOW";
  } else if (a.includes("mysql")) {
    tgtVer = javaNum >= 17 ? "8.3.0" : "8.0.33";
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM (MySQL Connector/J ${tgtVer}).`;
    risk = "LOW";
  } else if (a.includes("h2") || a.includes("hsqldb")) {
    tgtVer = javaNum >= 17 ? "2.2.224" : "1.4.200";
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM.`;
    risk = "LOW";
  } else if (a.includes("postgresql")) {
    tgtVer = "42.6.2";
    action = "UPGRADE";
    reasoning = `Managed by Target Spring Boot ${bootVer} BOM.`;
    risk = "LOW";
  } else if (ver && ver !== "Unknown" && ver !== "unknown" && ver !== "managed version") {
    tgtVer = ver;
    action = "ALREADY COMPATIBLE";
    reasoning = `Current version ${ver} is already compatible with target Java ${javaNum}.`;
    risk = "LOW";
  } else {
    tgtVer = bootVer;
    action = "MANUAL REVIEW";
    reasoning = `Third-party dependency requiring independent API compatibility verification for Java ${javaNum}.`;
    risk = "MEDIUM";
  }

  if (action !== "REPLACE" && action !== "REMOVE") {
    if (ver && ver !== "Unknown" && ver !== "unknown" && ver !== "managed version") {
      if (ver.toLowerCase() === tgtVer.toLowerCase()) {
        action = "ALREADY COMPATIBLE";
        reasoning = `Current version ${ver} already matches target Spring Boot BOM release.`;
        risk = "LOW";
      } else {
        const parseDigits = (s: string) => (s.match(/\d+/g) || []).map(Number);
        const curD = parseDigits(ver);
        const tgtD = parseDigits(tgtVer);
        const curMaj = curD[0] ?? 0;
        const tgtMaj = tgtD[0] ?? 0;

        if (tgtMaj > curMaj && curMaj > 0 && javaNum >= 17) {
          action = "MAJOR UPGRADE";
          risk = "HIGH";
        } else if (tgtD > curD) {
          action = "UPGRADE";
          risk = "LOW";
        } else {
          action = "ALREADY COMPATIBLE";
          risk = "LOW";
        }
      }
    }
  }

  const isJavax = g.startsWith("javax.") || a.startsWith("javax.") || a === "validation-api";
  const isTargetJava17Plus = javaNum >= 17;
  const isJavaxToJakarta = isJavax && isTargetJava17Plus;
  const sourceChanges = resolveSourceChangesDescription(
    gid,
    aid,
    ver,
    tgtVer,
    action,
    isJavaxToJakarta,
    undefined,
    javaNum,
    bootVer,
    buildTool
  );

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
  const [actionFilter, setActionFilter] = useState<DependencyAction | "ALL">("ALL");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(15);
  const [activeRiskTooltip, setActiveRiskTooltip] = useState<{
    rect: DOMRect;
  } | null>(null);

  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({
    reasons: false,
    framework: false,
    namespace: false,
    sourceCode: false,
    configuration: false,
  });

  const toggleCard = (key: string) => {
    setExpandedCards((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const allExpanded = useMemo(
    () => Object.values(expandedCards).every(Boolean),
    [expandedCards]
  );

  const toggleAllCards = () => {
    const nextState = !allExpanded;
    setExpandedCards({
      reasons: nextState,
      framework: nextState,
      namespace: nextState,
      sourceCode: nextState,
      configuration: nextState,
    });
  };

  const sourceJava = repoAnalysis?.java_version || repoAnalysis?.java_version_from_build || "1.7";
  const currentBoot = useMemo(() => {
    if (repoAnalysis?.spring_boot_version) return repoAnalysis.spring_boot_version;
    const bootDep = (repoAnalysis?.dependencies || []).find((d: any) => {
      const g = (d.group_id || d.groupId || d.group || "").toLowerCase();
      const a = (d.artifact_id || d.artifactId || d.artifact || "").toLowerCase();
      return (g === "org.springframework.boot" || a.startsWith("spring-boot")) && d.version && d.version !== "Unknown" && d.version !== "managed version";
    });
    if (bootDep) return bootDep.version;
    if (repoAnalysis?.frameworks?.[0]?.version) return repoAnalysis.frameworks[0].version;
    return "2.7.12";
  }, [repoAnalysis]);

  const currentFramework = repoAnalysis?.frameworks?.[0]?.name ? `${repoAnalysis.frameworks[0].name} (${currentBoot})` : `Spring Boot ${currentBoot}`;

  const targetJavaNum = parseInt((targetJavaVersion || "21").replace(/\D/g, "") || "21", 10);
  const selectedBootVersion = targetJavaNum >= 17 ? "3.2.5" : "2.7.18";
  const selectedFrameworkVersion = targetJavaNum >= 17 ? "6.1.14" : "5.3.31";
  const repoBuildTool = repoAnalysis?.build_tool || (repoAnalysis?.structure?.has_build_gradle ? "Gradle" : "Maven");

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

      const fallback = resolveTargetVersionFallback(gid, aid, currentVer, targetJavaVersion, selectedBootVersion, repoBuildTool);

      let targetDep = analysis?.target_dependency || fallback.targetDependency;
      let targetVer = analysis?.recommended_version || fallback.targetVersion;
      let action: DependencyAction = fallback.action;
      let reasoning = analysis?.upgrade_reason || analysis?.explanation || fallback.reasoning;
      let risk: MigrationRisk = (analysis?.risk as MigrationRisk) || fallback.risk;

      const isJavax = gid.toLowerCase().startsWith("javax.") || aid.toLowerCase().startsWith("javax.") || aid.toLowerCase() === "validation-api";
      const isTargetJava17Plus = targetJavaNum >= 17;
      const isJavaxToJakarta = isJavax && isTargetJava17Plus;

      if (isJavaxToJakarta) {
        action = "REPLACE";
        risk = "HIGH";
      } else if (isJavax && !isTargetJava17Plus) {
        if (action === "REPLACE") {
          action = currentVer && currentVer.toLowerCase() === targetVer.toLowerCase() ? "ALREADY COMPATIBLE" : "UPGRADE";
          risk = "LOW";
        }
      } else if (String(analysis?.upgrade_status || "").toUpperCase().includes("REMOVE")) {
        action = "REMOVE";
        targetDep = "Not Required";
        targetVer = "N/A";
        risk = "MEDIUM";
      } else if (analysis?.upgrade_status === "REVIEW REQUIRED" || analysis?.upgrade_status === "Manual Review" || targetVer === "Not Determined") {
        action = "MANUAL REVIEW";
        risk = "MEDIUM";
      } else if (currentVer.toLowerCase() === targetVer.toLowerCase() && currentVer !== "Unknown") {
        action = "ALREADY COMPATIBLE";
        risk = "LOW";
      }

      const rawSourceChanges = analysis?.migration_action || analysis?.recommendation || fallback.sourceChanges;
      const sourceChanges = resolveSourceChangesDescription(
        gid,
        aid,
        currentVer,
        targetVer,
        action,
        isJavaxToJakarta,
        rawSourceChanges,
        targetJavaNum,
        selectedBootVersion,
        repoBuildTool
      );

      const group: "Framework" | "Library" | "Dependency" = determineDependencyGroup(
        gid,
        aid,
        analysis?.category
      );

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
        isJavaxToJakarta,
      });

      cnts[group] = (cnts[group] || 0) + 1;
    });

    cnts.Framework = (cnts.Framework || 0) + (javaVer ? 1 : 0);
    cnts.ALL = rows.length + (javaVer ? 1 : 0);

    return { allRows: rows, counts: cnts, javaCurrent: javaVer };
  }, [repoAnalysis, dependencyAnalysis, targetJavaVersion, targetJavaNum, selectedBootVersion, repoBuildTool]);

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

  const javaxList = useMemo(() => allRows.filter((r) => r.isJavaxToJakarta), [allRows]);

  // Repository-specific findings extracted from detected dependencies and repository analysis
  const repoFindings = useMemo(() => {
    const deps = allRows.map((r) => r.dependency.toLowerCase());

    const hasSecurity = deps.some((d) => d.includes("security"));
    const hasDataJpa = deps.some((d) => d.includes("data-jpa") || d.includes("spring-data"));
    const hasHibernate = deps.some((d) => d.includes("hibernate"));
    const hasWeb = deps.some((d) => d.includes("web") || d.includes("tomcat"));
    const hasValidation = deps.some((d) => d.includes("validation"));
    const hasLombok = deps.some((d) => d.includes("lombok"));
    const hasJunit4 = deps.some((d) => d === "junit:junit" || (d.includes("junit") && !d.includes("jupiter")));
    const hasJunit5 = deps.some((d) => d.includes("jupiter"));
    const hasActuator = deps.some((d) => d.includes("actuator"));
    const hasBatch = deps.some((d) => d.includes("batch"));

    let dbDriver: string | null = null;
    if (deps.some((d) => d.includes("mysql"))) dbDriver = "MySQL";
    else if (deps.some((d) => d.includes("postgresql") || d.includes("postgres"))) dbDriver = "PostgreSQL";
    else if (deps.some((d) => d.includes("h2"))) dbDriver = "H2";
    else if (deps.some((d) => d.includes("oracle") || d.includes("ojdbc"))) dbDriver = "Oracle";
    else if (deps.some((d) => d.includes("sqlserver") || d.includes("mssql"))) dbDriver = "SQL Server";

    const webDep = allRows.find((r) => {
      const d = r.dependency.toLowerCase();
      return d.includes("starter-web") || d.includes("spring-web");
    });
    const dataJpaDep = allRows.find((r) => {
      const d = r.dependency.toLowerCase();
      return d.includes("starter-data-jpa") || d.includes("spring-data");
    });
    const securityDep = allRows.find((r) => {
      const d = r.dependency.toLowerCase();
      return d.includes("starter-security") || d.includes("spring-security");
    });
    const testDep = allRows.find((r) => {
      const d = r.dependency.toLowerCase();
      return d.includes("starter-test") || d.includes("junit");
    });
    const validationDep = allRows.find((r) => {
      const d = r.dependency.toLowerCase();
      return d.includes("validation");
    });
    const lombokDep = allRows.find((r) => {
      const d = r.dependency.toLowerCase();
      return d.includes("lombok");
    });
    const hibernateDep = allRows.find((r) => {
      const d = r.dependency.toLowerCase();
      return d.includes("hibernate");
    });
    const dbDriverDep = allRows.find((r) => {
      const d = r.dependency.toLowerCase();
      return d.includes("mysql") || d.includes("postgresql") || d.includes("postgres") || d.includes("h2") || d.includes("oracle") || d.includes("sqlserver");
    });

    const buildTool = repoBuildTool;
    const buildFile = buildTool === "Gradle" ? "build.gradle" : "pom.xml";
    const repoName = repoAnalysis?.name || "this repository";
    const javaFileCount = repoAnalysis?.java_file_count || repoAnalysis?.java_files?.length || 0;
    const testFileCount = repoAnalysis?.test_file_count ?? (repoAnalysis?.has_tests ? 1 : 0);
    const configFileCount = repoAnalysis?.config_file_count || repoAnalysis?.config_files?.length || 1;

    const isSameBootGen = currentBoot.startsWith("2.") && selectedBootVersion.startsWith("2.");
    const isCrossBootGen = !isSameBootGen && (currentBoot.startsWith("1.") || currentBoot.startsWith("2.")) && selectedBootVersion.startsWith("3.");

    return {
      hasSecurity,
      hasDataJpa,
      hasHibernate,
      hasWeb,
      hasValidation,
      hasLombok,
      hasJunit4,
      hasJunit5,
      hasActuator,
      hasBatch,
      dbDriver,
      webDep,
      dataJpaDep,
      securityDep,
      testDep,
      validationDep,
      lombokDep,
      hibernateDep,
      dbDriverDep,
      buildTool,
      buildFile,
      repoName,
      javaFileCount,
      testFileCount,
      configFileCount,
      isSameBootGen,
      isCrossBootGen,
    };
  }, [allRows, repoAnalysis, currentBoot, selectedBootVersion, repoBuildTool]);

  useEffect(() => {
    setCurrentPage(1);
  }, [activeTab, actionFilter, pageSize]);

  const filteredRows = useMemo(() => {
    let result = allRows;

    if (activeTab !== "ALL") {
      result = result.filter((row) => row.group === activeTab);
    }

    if (actionFilter !== "ALL") {
      result = result.filter((row) => row.action === actionFilter);
    }

    return result;
  }, [allRows, activeTab, actionFilter]);

  const includesJavaRow = Boolean(
    javaCurrent &&
    (activeTab === "ALL" || activeTab === "Framework") &&
    (actionFilter === "ALL" || actionFilter === "MAJOR UPGRADE")
  );
  const totalFilteredCount = filteredRows.length + (includesJavaRow ? 1 : 0);
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedRows = filteredRows.slice(startIndex, startIndex + pageSize);

  const renderJavaRow = includesJavaRow && currentPage === 1;

  const currentFrameworkVersion = useMemo(() => {
    const boot = String(currentBoot || "").trim();
    if (boot.startsWith("3.")) return "6.x";
    if (boot.startsWith("2.7") || boot.startsWith("2.6") || boot.startsWith("2.5") || boot.startsWith("2.4")) return "5.3.x";
    if (boot.startsWith("2.3") || boot.startsWith("2.2")) return "5.2.x";
    if (boot.startsWith("2.1")) return "5.1.x";
    if (boot.startsWith("2.0")) return "5.0.x";
    if (boot.startsWith("1.5")) return "4.3.x";
    if (boot.startsWith("1.4") || boot.startsWith("1.3")) return "4.2.x";
    if (boot.startsWith("1.")) return "4.x";
    return "5.3.x";
  }, [currentBoot]);

  // Compute Overall Assessment level based on actual repository findings
  const overallAssessment: MigrationRisk = useMemo(() => {
    if (targetJavaNum >= 17) {
      if (currentBoot.startsWith("1.") || actionTotals.REMOVE > 0) return "CRITICAL";
      if (javaxList.length > 0 || actionTotals.REPLACE > 0 || actionTotals["MAJOR UPGRADE"] > 0) return "HIGH";
      if (actionTotals["MANUAL REVIEW"] > 0) return "MEDIUM";
      return "LOW";
    }

    // Target is Java < 17 (e.g. Java 11 / Spring Boot 2.7.x)
    if (repoFindings.isSameBootGen) {
      if (actionTotals["MANUAL REVIEW"] > 0) return "MEDIUM";
      return "LOW";
    }

    if (currentBoot.startsWith("1.")) return "HIGH";
    if (actionTotals["MANUAL REVIEW"] > 0) return "MEDIUM";
    return "LOW";
  }, [actionTotals, targetJavaNum, javaxList.length, currentBoot, repoFindings.isSameBootGen]);

  const overallAssessmentExplanation = useMemo(() => {
    const totalDeps = allRows.length;
    const compatibleCount = actionTotals["ALREADY COMPATIBLE"] || 0;
    const upgradeCount = (actionTotals.UPGRADE || 0) + (actionTotals["MAJOR UPGRADE"] || 0);
    const repoLabel = repoFindings.repoName;

    if (targetJavaNum < 17) {
      if (repoFindings.isSameBootGen) {
        return `Low-risk maintenance upgrade within the Spring Boot 2.7.x generation for ${totalDeps} total dependencies in ${repoLabel} (${compatibleCount} already compatible, ${upgradeCount} minor BOM alignments). All javax.* package imports, Spring Framework 5.3 APIs, and Hibernate 5 dialects remain fully supported on Java ${targetJavaNum} with zero breaking namespace migrations.`;
      }
      if (currentBoot.startsWith("1.")) {
        return `High-risk framework upgrade from Spring Boot ${currentBoot} to ${selectedBootVersion} on Java ${targetJavaNum} across ${totalDeps} dependencies in ${repoLabel}. Retains javax.* namespace, but requires migrating configuration properties, security adapters, and updating third-party libraries.`;
      }
      return `Moderate migration effort to Spring Boot ${selectedBootVersion} on Java ${targetJavaNum} across ${totalDeps} dependencies in ${repoLabel} (${compatibleCount} already compatible, ${upgradeCount} BOM alignments). Retains the standard javax.* namespace, with updates concentrated in Spring Framework 5.3 baseline alignment.`;
    }

    // Java 17+ / Spring Boot 3+
    if (currentBoot.startsWith("1.")) {
      return `Critical multi-generational framework upgrade from Spring Boot ${currentBoot} directly to Spring Boot ${selectedBootVersion} and Java ${targetJavaNum} for ${repoLabel}. Involves full Jakarta EE 10 namespace migration (javax.* → jakarta.*), Spring Framework 6 architectural changes, and comprehensive property overhauls across ${totalDeps} dependencies (${upgradeCount} upgrades required).`;
    }

    if (overallAssessment === "CRITICAL" || overallAssessment === "HIGH") {
      return `Major multi-generational framework upgrade to Spring Boot ${selectedBootVersion} and Java ${targetJavaNum} across ${totalDeps} dependencies in ${repoLabel} (${upgradeCount} upgrades required). Requires Jakarta EE 10 specification transition (javax.* → jakarta.*)${javaxList.length > 0 ? ` for ${javaxList.length} detected specification libraries` : " across managed starter dependencies"}, Spring Framework 6 API deprecation updates, and Hibernate 6 ORM query syntax validation.`;
    }

    return `Standard framework modernization to Spring Boot ${selectedBootVersion} and Java ${targetJavaNum} across ${totalDeps} dependencies in ${repoLabel} (${compatibleCount} already compatible, ${upgradeCount} upgrades) with manageable migration impact.`;
  }, [targetJavaNum, selectedBootVersion, overallAssessment, allRows.length, actionTotals, repoFindings.isSameBootGen, repoFindings.repoName, currentBoot, javaxList.length]);

  // Formatted copy text including both source and target versions
  const targetDepsCopyText = useMemo(() => {
    const lines: string[] = [];
    const javaVer = repoAnalysis?.java_version || repoAnalysis?.java_version_from_build;
    if (javaVer) {
      lines.push(`Java: ${javaVer} -> ${targetJavaVersion || "21"}`);
    }
    allRows.forEach((row) => {
      const tgtDep = row.targetDependency && row.targetDependency !== "Not Required" ? row.targetDependency : row.dependency;
      if (row.action === "REMOVE" || row.targetDependency === "Not Required") {
        lines.push(`source version - ${row.dependency} (${row.currentVersion}) target version-Not Required`);
      } else if (!row.targetVersion || row.targetVersion === "N/A") {
        lines.push(`source version - ${row.dependency} (${row.currentVersion}) target version-${tgtDep}`);
      } else {
        lines.push(`source version - ${row.dependency} (${row.currentVersion}) target version-${tgtDep} (${row.targetVersion})`);
      }
    });
    return lines.join("\n");
  }, [allRows, repoAnalysis, targetJavaVersion]);

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
            Determines exact target dependencies, actions, source-code impact, and risks for {repoFindings.repoName} migrating from Java {sourceJava} to JDK {targetJavaVersion || "21"} with Spring Boot {selectedBootVersion} ({allRows.length} total dependencies analyzed).
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {counts.ALL > 0 && <CopyAllDependenciesButton text={targetDepsCopyText || allDepsText} label="Copy All" />}
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

      {/* Action Values Grid & Filter Pills */}
      <div
        style={{
          padding: "10px 20px",
          borderBottom: "1px solid #eef2f7",
          background: "#f8fafc",
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {/* All Pill */}
        <button
          type="button"
          onClick={() => setActionFilter("ALL")}
          title="Show all dependency actions"
          style={{
            padding: "4px 10px",
            borderRadius: 8,
            background: actionFilter === "ALL" ? "#1e293b" : "#ffffff",
            color: actionFilter === "ALL" ? "#ffffff" : "#475569",
            border: actionFilter === "ALL" ? "1px solid #0f172a" : "1px solid #cbd5e1",
            boxShadow: actionFilter === "ALL" ? "0 1px 3px rgba(15,23,42,0.18)" : "none",
            fontSize: 11,
            fontWeight: 700,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            transition: "all 0.15s ease",
          }}
        >
          {actionFilter === "ALL" && <FaCheckCircle style={{ fontSize: 10 }} />}
          <span>ALL:</span>
          <strong>{allRows.length}</strong>
        </button>

        {(
          [
            "MAJOR UPGRADE",
            "UPGRADE",
            "ALREADY COMPATIBLE",
          ] as DependencyAction[]
        ).map((act) => {
          const cfg = ACTION_CONFIG[act];
          const isSelected = actionFilter === act;
          return (
            <button
              key={act}
              type="button"
              onClick={() => setActionFilter(isSelected ? "ALL" : act)}
              title={isSelected ? `Clear filter (currently showing only ${act})` : `Click to filter by ${act}`}
              style={{
                padding: "4px 10px",
                borderRadius: 8,
                background: isSelected ? cfg.text : cfg.background,
                color: isSelected ? "#ffffff" : cfg.text,
                border: isSelected ? `1px solid ${cfg.text}` : `1px solid ${cfg.border}`,
                boxShadow: isSelected ? `0 0 0 2px ${cfg.border}, 0 2px 4px rgba(0,0,0,0.1)` : "none",
                fontSize: 11,
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {isSelected && <FaCheckCircle style={{ fontSize: 10 }} />}
              <span>{act}:</span>
              <strong>{actionTotals[act] || 0}</strong>
            </button>
          );
        })}

        {actionFilter !== "ALL" && (
          <button
            type="button"
            onClick={() => setActionFilter("ALL")}
            style={{
              marginLeft: "auto",
              padding: "4px 10px",
              borderRadius: 6,
              background: "#ffffff",
              color: "#64748b",
              border: "1px solid #cbd5e1",
              fontSize: 11,
              fontWeight: 600,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              transition: "all 0.15s ease",
            }}
          >
            <FaTimes style={{ fontSize: 10 }} />
            <span>Reset Filter</span>
          </button>
        )}
      </div>

      {/* Categorization Tabs */}
      <div
        style={{
          padding: "12px 20px",
          borderBottom: "1px solid #f1f5f9",
          background: "#ffffff",
          display: "flex",
          alignItems: "center",
          gap: 6,
          flexWrap: "wrap",
        }}
      >
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
            transition: "all 0.15s ease",
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
            transition: "all 0.15s ease",
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
            transition: "all 0.15s ease",
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
            transition: "all 0.15s ease",
          }}
        >
          Dependency ({counts.Dependency})
        </button>
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
              <th
                style={{
                  padding: "12px 12px",
                  width: 90,
                  cursor: "help",
                  userSelect: "none",
                }}
                onMouseEnter={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  setActiveRiskTooltip({ rect });
                }}
                onMouseLeave={() => setActiveRiskTooltip(null)}
                title="Risk Assessment: Hover to view classification criteria"
              >
                <div style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                  <span>Risk</span>
                  <FaInfoCircle size={11} style={{ color: "#94a3b8" }} />
                </div>
              </th>
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
                  Java platform target upgrade from Java {sourceJava} to JDK {targetJavaVersion || "21"} LTS release.
                </td>
                <td style={{ padding: "12px 16px", color: "#1e293b", fontWeight: 600 }}>
                  Set &lt;java.version&gt;{targetJavaVersion || "21"}&lt;/java.version&gt; compiler release target property in {repoFindings.buildFile}.
                </td>
                <td style={{ padding: "12px 12px" }}>
                  <span
                    style={{
                      padding: "2px 6px",
                      borderRadius: 4,
                      fontSize: 10,
                      fontWeight: 800,
                      color: "#991b1b",
                      background: "#fef2f2",
                      border: "1px solid #fecaca",
                      display: "inline-block",
                      boxShadow: "0 1px 2px rgba(153, 27, 27, 0.08)",
                    }}
                  >
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
                          display: "inline-block",
                          boxShadow: "0 1px 2px rgba(0, 0, 0, 0.04)",
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
                <td colSpan={8} style={{ padding: "32px 0", textAlign: "center", color: "#64748b", fontSize: 13 }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
                    <div>
                      No dependencies match the current filter criteria{" "}
                      {actionFilter !== "ALL" && (
                        <strong style={{ color: ACTION_CONFIG[actionFilter]?.text }}>
                          [Action: {actionFilter}]
                        </strong>
                      )}
                      {activeTab !== "ALL" && <span> [Category: {activeTab}]</span>}.
                    </div>
                    {(actionFilter !== "ALL" || activeTab !== "ALL") && (
                      <button
                        type="button"
                        onClick={() => {
                          setActionFilter("ALL");
                          setActiveTab("ALL");
                        }}
                        style={{
                          padding: "6px 14px",
                          borderRadius: 8,
                          background: "#eff6ff",
                          border: "1px solid #bfdbfe",
                          color: "#1d4ed8",
                          fontSize: 12,
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        Reset All Filters
                      </button>
                    )}
                  </div>
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
            {actionFilter !== "ALL" && (
              <span style={{ marginLeft: 6, color: ACTION_CONFIG[actionFilter]?.text, fontWeight: 700 }}>
                (filtered by {actionFilter})
              </span>
            )}
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
      <div
        style={{
          padding: "24px 28px",
          borderTop: "2px solid #e2e8f0",
          background: "#f8fafc",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        {/* Header & Global Expand/Collapse Action */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                background: "#eff6ff",
                border: "1px solid #bfdbfe",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#2563eb",
              }}
            >
              <FaCheckCircle size={17} />
            </div>
            <div>
              <h4
                style={{
                  margin: 0,
                  fontSize: 15,
                  fontWeight: 800,
                  color: "#0f172a",
                  letterSpacing: "-0.01em",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                FINAL DEPENDENCY MIGRATION SUMMARY
              </h4>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                <span
                  style={{
                    background: "#e2e8f0",
                    color: "#334155",
                    fontSize: 11,
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: 4,
                  }}
                >
                  {repoFindings.repoName}
                </span>
                <span
                  style={{
                    background: "#dbeafe",
                    color: "#1e40af",
                    fontSize: 11,
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: 4,
                  }}
                >
                  JDK {targetJavaVersion || "21"} • Spring Boot {selectedBootVersion}
                </span>
                <span
                  style={{
                    background: "#f1f5f9",
                    color: "#64748b",
                    fontSize: 11,
                    fontWeight: 600,
                    padding: "2px 8px",
                    borderRadius: 4,
                  }}
                >
                  {allRows.length} total dependencies
                </span>
              </div>
            </div>
          </div>

          {/* Global Toggle Button */}
          <button
            type="button"
            onClick={toggleAllCards}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              padding: "7px 14px",
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              color: "#1d4ed8",
              background: "#eff6ff",
              border: "1px solid #bfdbfe",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
            title={allExpanded ? "Collapse all details" : "Expand all details"}
          >
            {allExpanded ? <FaChevronUp size={11} /> : <FaChevronDown size={11} />}
            {allExpanded ? "Collapse All Details" : "Expand All Details"}
          </button>
        </div>

        {/* Executive Migration Pathway & Dependency Metrics Strip */}
        <div
          style={{
            background: "#ffffff",
            borderRadius: 10,
            border: "1px solid #e2e8f0",
            boxShadow: "0 1px 3px rgba(0, 0, 0, 0.03)",
            padding: "16px 20px",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 16,
            alignItems: "center",
          }}
        >
          {/* Pathway Column */}
          <div>
            <div
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: 8,
              }}
            >
              Modernization Pathway
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ color: "#64748b", fontSize: 11, minWidth: 70, fontWeight: 600 }}>Java:</span>
                <span style={{ fontWeight: 700, color: "#334155" }}>Java {sourceJava}</span>
                <FaArrowRight size={10} color="#94a3b8" />
                <span style={{ fontWeight: 800, color: "#1d4ed8", background: "#eff6ff", padding: "1px 6px", borderRadius: 4 }}>
                  Java {targetJavaVersion || "21"}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ color: "#64748b", fontSize: 11, minWidth: 70, fontWeight: 600 }}>Framework:</span>
                <span style={{ fontWeight: 700, color: "#334155" }}>Spring Boot {currentBoot}</span>
                <FaArrowRight size={10} color="#94a3b8" />
                <span style={{ fontWeight: 800, color: "#1d4ed8", background: "#eff6ff", padding: "1px 6px", borderRadius: 4 }}>
                  Spring Boot {selectedBootVersion}
                </span>
                <span style={{ fontSize: 11, color: "#64748b" }}>(Spring {selectedFrameworkVersion})</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ color: "#64748b", fontSize: 11, minWidth: 70, fontWeight: 600 }}>Build Tool:</span>
                <span style={{ fontWeight: 700, color: "#1e293b" }}>{repoFindings.buildTool}</span>
                <span style={{ color: "#64748b", fontSize: 11 }}>({repoFindings.buildFile})</span>
              </div>
            </div>
          </div>

          {/* Action Totals Breakdown */}
          <div>
            <div
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: 8,
              }}
            >
              Action Breakdown
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {actionTotals["MAJOR UPGRADE"] > 0 && (
                <div
                  style={{
                    background: "#fef3c7",
                    border: "1px solid #fde68a",
                    color: "#92400e",
                    padding: "4px 10px",
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  {actionTotals["MAJOR UPGRADE"]} Major Upgrade{actionTotals["MAJOR UPGRADE"] > 1 ? "s" : ""}
                </div>
              )}
              {actionTotals.UPGRADE > 0 && (
                <div
                  style={{
                    background: "#eff6ff",
                    border: "1px solid #bfdbfe",
                    color: "#1e40af",
                    padding: "4px 10px",
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  {actionTotals.UPGRADE} Upgrade{actionTotals.UPGRADE > 1 ? "s" : ""}
                </div>
              )}
              {actionTotals["ALREADY COMPATIBLE"] > 0 && (
                <div
                  style={{
                    background: "#ecfdf5",
                    border: "1px solid #a7f3d0",
                    color: "#065f46",
                    padding: "4px 10px",
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  {actionTotals["ALREADY COMPATIBLE"]} Already Compatible
                </div>
              )}
              {actionTotals.REPLACE > 0 && (
                <div
                  style={{
                    background: "#faf5ff",
                    border: "1px solid #e9d5ff",
                    color: "#6b21a8",
                    padding: "4px 10px",
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  {actionTotals.REPLACE} Replace
                </div>
              )}
              {actionTotals.REMOVE > 0 && (
                <div
                  style={{
                    background: "#fef2f2",
                    border: "1px solid #fecaca",
                    color: "#991b1b",
                    padding: "4px 10px",
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  {actionTotals.REMOVE} Remove
                </div>
              )}
              {actionTotals["MANUAL REVIEW"] > 0 && (
                <div
                  style={{
                    background: "#fffbeb",
                    border: "1px solid #fef3c7",
                    color: "#b45309",
                    padding: "4px 10px",
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  {actionTotals["MANUAL REVIEW"]} Manual Review
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Executive Overall Dependency Migration Assessment Banner */}
        <div
          style={{
            background: RISK_CONFIG[overallAssessment].background,
            border: `1px solid ${RISK_CONFIG[overallAssessment].border}`,
            borderRadius: 10,
            padding: "14px 18px",
            display: "flex",
            alignItems: "flex-start",
            gap: 14,
          }}
        >
          <div style={{ flexShrink: 0 }}>
            <span
              style={{
                display: "inline-block",
                padding: "4px 10px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 800,
                color: RISK_CONFIG[overallAssessment].text,
                background: "#ffffff",
                border: `1px solid ${RISK_CONFIG[overallAssessment].border}`,
                boxShadow: "0 1px 2px rgba(0, 0, 0, 0.05)",
                letterSpacing: "0.03em",
              }}
            >
              {overallAssessment} RISK
            </span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 12.5,
                lineHeight: 1.55,
                color: "#1e293b",
                fontWeight: 500,
              }}
            >
              {overallAssessmentExplanation}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "#475569",
                  background: "rgba(255, 255, 255, 0.7)",
                  padding: "2px 8px",
                  borderRadius: 4,
                  border: "1px solid rgba(0, 0, 0, 0.05)",
                }}
              >
                {targetJavaNum < 17
                  ? "Java EE 8 Baseline (No Namespace Changes)"
                  : javaxList.length > 0
                  ? `${javaxList.length} Jakarta EE Package Migrations`
                  : "Transitive Jakarta EE 10 Alignment"}
              </span>
              {repoFindings.javaFileCount > 0 && (
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "#475569",
                    background: "rgba(255, 255, 255, 0.7)",
                    padding: "2px 8px",
                    borderRadius: 4,
                    border: "1px solid rgba(0, 0, 0, 0.05)",
                  }}
                >
                  {repoFindings.javaFileCount} Source Files
                </span>
              )}
              {repoFindings.configFileCount > 0 && (
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "#475569",
                    background: "rgba(255, 255, 255, 0.7)",
                    padding: "2px 8px",
                    borderRadius: 4,
                    border: "1px solid rgba(0, 0, 0, 0.05)",
                  }}
                >
                  {repoFindings.configFileCount} Configuration File{repoFindings.configFileCount > 1 ? "s" : ""}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 5 Structured Categorized Cards with Expandable Details */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
            gap: 14,
          }}
        >
          {/* Card 1: Major Migration Reasons */}
          <div
            style={{
              background: "#ffffff",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              overflow: "hidden",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.03)",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              onClick={() => toggleCard("reasons")}
              style={{
                cursor: "pointer",
                padding: "12px 16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                userSelect: "none",
                background: expandedCards.reasons ? "#f8fafc" : "#ffffff",
                borderBottom: expandedCards.reasons ? "1px solid #e2e8f0" : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 6,
                    background: "#eff6ff",
                    color: "#2563eb",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <FaLayerGroup size={13} />
                </div>
                <div>
                  <h5 style={{ margin: 0, fontSize: 13, fontWeight: 800, color: "#1e293b" }}>
                    Major Migration Reasons
                  </h5>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    JDK {targetJavaVersion || "21"} Runtime • BOM Alignment
                  </span>
                </div>
              </div>
              <span style={{ fontSize: 11, color: "#64748b", fontWeight: 600, display: "flex", alignItems: "center", gap: 5 }}>
                {expandedCards.reasons ? "Hide" : "Details"}
                {expandedCards.reasons ? <FaChevronUp size={10} /> : <FaChevronDown size={10} />}
              </span>
            </div>

            {/* Always visible concise preview */}
            <div style={{ padding: "10px 16px", fontSize: 12, color: "#475569", lineHeight: 1.5 }}>
              Modernizing <strong>{repoFindings.repoName}</strong> from Java {sourceJava} to JDK {targetJavaVersion || "21"} LTS runtime with Spring Boot {selectedBootVersion} BOM dependency coordination for {allRows.length} detected dependencies.
            </div>

            {/* Expandable detailed tray */}
            {expandedCards.reasons && (
              <div style={{ padding: "12px 16px", background: "#f8fafc", borderTop: "1px solid #e2e8f0", fontSize: 12 }}>
                <ul style={{ margin: 0, paddingLeft: 18, color: "#475569", lineHeight: 1.6, display: "flex", flexDirection: "column", gap: 6 }}>
                  <li>
                    <strong>JDK Runtime:</strong> Modernize {repoFindings.repoName} from Java {sourceJava} to JDK {targetJavaVersion || "21"} LTS runtime for improved JVM performance, compiler optimizations, and extended security support.
                  </li>
                  <li>
                    <strong>BOM Integration:</strong> Align {repoFindings.buildFile} ({repoFindings.buildTool}) with Spring Boot {selectedBootVersion} (Spring Framework {selectedFrameworkVersion}) dependency-management BOM for {allRows.length} detected dependencies.
                  </li>
                  {targetJavaNum >= 17 ? (
                    <li>
                      <strong>Specification Baseline:</strong> Shift from Java EE 8 to Jakarta EE 10 baseline{javaxList.length > 0 ? ` with package namespace refactoring for ${javaxList.length} specification libraries (${javaxList.slice(0, 3).map(j => j.dependency.split(':')[1] || j.dependency).join(", ")}${javaxList.length > 3 ? `, +${javaxList.length - 3} more` : ""})` : " with transitive Jakarta EE coordination"}.
                    </li>
                  ) : (
                    <li>
                      <strong>Specification Baseline:</strong> Retain Java EE 8 specification compatibility under Spring Boot {selectedBootVersion} on Java {targetJavaNum}, preserving <code>javax.*</code> package stability without breaking namespace migration across all {allRows.length} dependencies.
                    </li>
                  )}
                  {repoFindings.hasDataJpa || repoFindings.hasHibernate ? (
                    <li>
                      <strong>Persistence Modernization:</strong> {targetJavaNum >= 17 ? (
                        <>Upgrade persistence layer{repoFindings.dataJpaDep ? <> (<code>{repoFindings.dataJpaDep.dependency.split(':')[1] || repoFindings.dataJpaDep.dependency}</code>: {repoFindings.dataJpaDep.currentVersion} → {repoFindings.dataJpaDep.targetVersion})</> : ""} to Hibernate ORM 6.4.x with modern SQM query translation and Jakarta persistence.</>
                      ) : (
                        <>Synchronize persistence dependencies{repoFindings.dataJpaDep ? <> (<code>{repoFindings.dataJpaDep.dependency.split(':')[1] || repoFindings.dataJpaDep.dependency}</code>: {repoFindings.dataJpaDep.currentVersion} → {repoFindings.dataJpaDep.targetVersion})</> : ""} under Spring Boot {selectedBootVersion} BOM while retaining existing SQL dialects and entity mappings.</>
                      )}
                    </li>
                  ) : null}
                  {repoFindings.hasLombok ? (
                    <li>
                      <strong>Compiler Tooling:</strong> Synchronize Project Lombok{repoFindings.lombokDep ? <> (<code>{repoFindings.lombokDep.currentVersion}</code> → <code>{repoFindings.lombokDep.targetVersion}</code>)</> : ""} annotation processor in {repoFindings.buildFile} for Java {targetJavaNum} bytecode compiler support.
                    </li>
                  ) : null}
                </ul>
              </div>
            )}
          </div>

          {/* Card 2: Framework Changes */}
          <div
            style={{
              background: "#ffffff",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              overflow: "hidden",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.03)",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              onClick={() => toggleCard("framework")}
              style={{
                cursor: "pointer",
                padding: "12px 16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                userSelect: "none",
                background: expandedCards.framework ? "#f8fafc" : "#ffffff",
                borderBottom: expandedCards.framework ? "1px solid #e2e8f0" : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 6,
                    background: "#e0f2fe",
                    color: "#0284c7",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <FaCogs size={13} />
                </div>
                <div>
                  <h5 style={{ margin: 0, fontSize: 13, fontWeight: 800, color: "#1e293b" }}>
                    Framework Changes
                  </h5>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    Spring Boot {currentBoot} → {selectedBootVersion}
                  </span>
                </div>
              </div>
              <span style={{ fontSize: 11, color: "#64748b", fontWeight: 600, display: "flex", alignItems: "center", gap: 5 }}>
                {expandedCards.framework ? "Hide" : "Details"}
                {expandedCards.framework ? <FaChevronUp size={10} /> : <FaChevronDown size={10} />}
              </span>
            </div>

            {/* Always visible concise preview */}
            <div style={{ padding: "10px 16px", fontSize: 12, color: "#475569", lineHeight: 1.5 }}>
              Updating Spring Boot parent from <strong>{currentBoot}</strong> to <strong>{selectedBootVersion}</strong> (Spring Framework <strong>{selectedFrameworkVersion}</strong>) with BOM coordination for {counts.Framework} component{counts.Framework === 1 ? "" : "s"}.
            </div>

            {/* Expandable detailed tray */}
            {expandedCards.framework && (
              <div style={{ padding: "12px 16px", background: "#f8fafc", borderTop: "1px solid #e2e8f0", fontSize: 12 }}>
                <div style={{ color: "#475569", lineHeight: 1.6 }}>
                  <p style={{ margin: "0 0 6px" }}>
                    {repoFindings.isSameBootGen ? (
                      <>
                        In-place maintenance update in <strong>{repoFindings.repoName}</strong> for Spring Boot parent from <strong>{currentBoot}</strong> to <strong>{selectedBootVersion}</strong> (aligning Spring Framework to <strong>{selectedFrameworkVersion}</strong> within the 5.3 baseline).
                      </>
                    ) : (
                      <>
                        Generation upgrade in <strong>{repoFindings.repoName}</strong> for Spring Boot parent from <strong>{currentBoot}</strong> to <strong>{selectedBootVersion}</strong> and Spring Framework from <strong>{currentFrameworkVersion}</strong> to <strong>{selectedFrameworkVersion}</strong>.
                      </>
                    )}
                  </p>
                  <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
                    {repoFindings.hasWeb ? (
                      <li>
                        <strong>Spring Web{repoFindings.webDep ? <> (<code>{repoFindings.webDep.dependency.split(':')[1] || repoFindings.webDep.dependency}</code>: {repoFindings.webDep.currentVersion} → {repoFindings.webDep.targetVersion})</> : ""}:</strong> {targetJavaNum >= 17 ? "Upgraded to Spring MVC 6.1 with embedded Tomcat 10.1 (Jakarta Servlet 6.0)." : "Retains Spring MVC 5.3 with embedded Tomcat 9.0 (Servlet 4.0 / javax.servlet API)."}
                      </li>
                    ) : null}
                    {repoFindings.hasDataJpa ? (
                      <li>
                        <strong>Spring Data JPA{repoFindings.dataJpaDep ? <> (<code>{repoFindings.dataJpaDep.dependency.split(':')[1] || repoFindings.dataJpaDep.dependency}</code>: {repoFindings.dataJpaDep.currentVersion} → {repoFindings.dataJpaDep.targetVersion})</> : ""}:</strong> {targetJavaNum >= 17 ? "Upgraded to Spring Data 2023.1.x with Hibernate 6.4.x runtime." : "Synchronized to Spring Data 2021.2.x with Hibernate 5.6.x (dialect compatibility preserved)."}
                      </li>
                    ) : null}
                    {repoFindings.hasSecurity ? (
                      <li>
                        <strong>Spring Security{repoFindings.securityDep ? <> (<code>{repoFindings.securityDep.dependency.split(':')[1] || repoFindings.securityDep.dependency}</code>: {repoFindings.securityDep.currentVersion} → {repoFindings.securityDep.targetVersion})</> : ""}:</strong> {targetJavaNum >= 17 ? "Migrated to Spring Security 6.2.x; deprecated adapters replaced by SecurityFilterChain." : "Synchronized to Spring Security 5.7.x with legacy adapter backward compatibility."}
                      </li>
                    ) : null}
                    {repoFindings.hasValidation ? (
                      <li>
                        <strong>Validation{repoFindings.validationDep ? <> (<code>{repoFindings.validationDep.dependency.split(':')[1] || repoFindings.validationDep.dependency}</code>: {repoFindings.validationDep.currentVersion} → {repoFindings.validationDep.targetVersion})</> : ""}:</strong> {targetJavaNum >= 17 ? "Aligned with Jakarta Validation 3.0 specification." : "Retains Java EE 8 Bean Validation 2.0 specification."}
                      </li>
                    ) : null}
                    <li>
                      <strong>BOM Alignment:</strong> {counts.Framework} framework component{counts.Framework === 1 ? "" : "s"} and {counts.Library} librar{counts.Library === 1 ? "y" : "ies"} coordinated under Spring Boot {selectedBootVersion} BOM.
                    </li>
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* Card 3: Namespace Changes */}
          <div
            style={{
              background: "#ffffff",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              overflow: "hidden",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.03)",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              onClick={() => toggleCard("namespace")}
              style={{
                cursor: "pointer",
                padding: "12px 16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                userSelect: "none",
                background: expandedCards.namespace ? "#f8fafc" : "#ffffff",
                borderBottom: expandedCards.namespace ? "1px solid #e2e8f0" : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 6,
                    background: targetJavaNum < 17 || javaxList.length === 0 ? "#ecfdf5" : "#fef3c7",
                    color: targetJavaNum < 17 || javaxList.length === 0 ? "#059669" : "#d97706",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <FaExchangeAlt size={13} />
                </div>
                <div>
                  <h5 style={{ margin: 0, fontSize: 13, fontWeight: 800, color: "#1e293b" }}>
                    Namespace Changes
                  </h5>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    {targetJavaNum < 17
                      ? "Java EE 8 Baseline (No Namespace Changes)"
                      : javaxList.length > 0
                      ? `${javaxList.length} Package Migrations Required`
                      : "Transitive Jakarta EE 10 Alignment"}
                  </span>
                </div>
              </div>
              <span style={{ fontSize: 11, color: "#64748b", fontWeight: 600, display: "flex", alignItems: "center", gap: 5 }}>
                {expandedCards.namespace ? "Hide" : "Details"}
                {expandedCards.namespace ? <FaChevronUp size={10} /> : <FaChevronDown size={10} />}
              </span>
            </div>

            {/* Always visible concise preview */}
            <div style={{ padding: "10px 16px", fontSize: 12, color: "#475569", lineHeight: 1.5 }}>
              {targetJavaNum < 17 ? (
                <>All existing <code>javax.*</code> package imports remain 100% valid and supported in <strong>{repoFindings.repoName}</strong> on Java {targetJavaNum}. Zero namespace migration required.</>
              ) : javaxList.length > 0 ? (
                <>{javaxList.length} legacy specification librar{javaxList.length > 1 ? "ies" : "y"} detected in <strong>{repoFindings.repoName}</strong> requiring package refactoring from <code>javax.*</code> to <code>jakarta.*</code>.</>
              ) : (
                <>No direct legacy <code>javax.*</code> dependencies declared in {repoFindings.buildFile}; transitive Jakarta EE 10 alignment managed by Spring Boot BOM.</>
              )}
            </div>

            {/* Expandable detailed tray */}
            {expandedCards.namespace && (
              <div style={{ padding: "12px 16px", background: "#f8fafc", borderTop: "1px solid #e2e8f0", fontSize: 12 }}>
                {targetJavaNum < 17 ? (
                  <div style={{ background: "#ecfdf5", border: "1px solid #a7f3d0", padding: "10px 12px", borderRadius: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#047857", fontWeight: 700, fontSize: 12, marginBottom: 4 }}>
                      <FaCheckCircle /> NO NAMESPACE MIGRATION REQUIRED
                    </div>
                    <p style={{ margin: 0, color: "#065f46", lineHeight: 1.5 }}>
                      Target Java {targetJavaNum} and Spring Boot {selectedBootVersion} operate on the Java EE 8 specification baseline. All <code>javax.*</code> package imports (including <code>javax.persistence.*</code>, <code>javax.validation.*</code>, and <code>javax.servlet.*</code>) remain 100% valid and supported in {repoFindings.repoName}. Zero package namespace refactoring is required for the {allRows.length} detected dependencies in this repository.
                    </p>
                  </div>
                ) : javaxList.length > 0 ? (
                  <div>
                    <div style={{ display: "inline-block", background: "#fef3c7", border: "1px solid #fde68a", padding: "3px 8px", borderRadius: 6, color: "#92400e", fontWeight: 700, fontSize: 11, marginBottom: 8 }}>
                      {javaxList.length} Specification Package Migration{javaxList.length > 1 ? "s" : ""} Required in {repoFindings.repoName}
                    </div>
                    <ul style={{ margin: 0, paddingLeft: 18, color: "#b45309", fontWeight: 600, lineHeight: 1.6, display: "flex", flexDirection: "column", gap: 6 }}>
                      {javaxList.map((r, i) => (
                        <li key={i}>
                          <code>{r.dependency} ({r.currentVersion})</code> → <code>{r.targetDependency} ({r.targetVersion})</code>
                          <div style={{ fontSize: 11, fontWeight: 400, color: "#475569" }}>{r.sourceChanges}</div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div style={{ background: "#ecfdf5", border: "1px solid #a7f3d0", padding: "10px 12px", borderRadius: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#047857", fontWeight: 700, fontSize: 12, marginBottom: 4 }}>
                      <FaCheckCircle /> TRANSITIVE JAKARTA EE 10 ALIGNMENT
                    </div>
                    <p style={{ margin: 0, color: "#065f46", lineHeight: 1.5 }}>
                      No direct legacy <code>javax.*</code> dependencies are declared in {repoFindings.buildFile}. Transitive Jakarta EE 10 specifications (e.g., <code>jakarta.servlet</code>, <code>jakarta.annotation</code>, <code>jakarta.persistence</code>) are provided and managed automatically by the Spring Boot {selectedBootVersion} BOM for {repoFindings.repoName}.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Card 4: Source-Code Impact */}
          <div
            style={{
              background: "#ffffff",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              overflow: "hidden",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.03)",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              onClick={() => toggleCard("sourceCode")}
              style={{
                cursor: "pointer",
                padding: "12px 16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                userSelect: "none",
                background: expandedCards.sourceCode ? "#f8fafc" : "#ffffff",
                borderBottom: expandedCards.sourceCode ? "1px solid #e2e8f0" : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 6,
                    background: "#f3e8ff",
                    color: "#7c3aed",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <FaFileCode size={13} />
                </div>
                <div>
                  <h5 style={{ margin: 0, fontSize: 13, fontWeight: 800, color: "#1e293b" }}>
                    Source-Code Impact
                  </h5>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    {repoFindings.javaFileCount > 0 ? `${repoFindings.javaFileCount} Source Files` : "Source Files Scope"}
                  </span>
                </div>
              </div>
              <span style={{ fontSize: 11, color: "#64748b", fontWeight: 600, display: "flex", alignItems: "center", gap: 5 }}>
                {expandedCards.sourceCode ? "Hide" : "Details"}
                {expandedCards.sourceCode ? <FaChevronUp size={10} /> : <FaChevronDown size={10} />}
              </span>
            </div>

            {/* Always visible concise preview */}
            <div style={{ padding: "10px 16px", fontSize: 12, color: "#475569", lineHeight: 1.5 }}>
              {targetJavaNum < 17 ? (
                <>Zero breaking namespace changes across {repoFindings.javaFileCount > 0 ? `${repoFindings.javaFileCount} source files` : "the codebase"}. Existing entity mappings, controllers, and tests remain intact.</>
              ) : (
                <>Package refactoring from <code>javax.*</code> to <code>jakarta.*</code> and framework deprecation updates across {repoFindings.javaFileCount > 0 ? `${repoFindings.javaFileCount} source files` : "the codebase"}.</>
              )}
            </div>

            {/* Expandable detailed tray */}
            {expandedCards.sourceCode && (
              <div style={{ padding: "12px 16px", background: "#f8fafc", borderTop: "1px solid #e2e8f0", fontSize: 12 }}>
                <div style={{ color: "#475569", lineHeight: 1.6 }}>
                  <p style={{ margin: "0 0 6px" }}>
                    {targetJavaNum < 17 ? (
                      <>
                        Zero breaking namespace changes across {repoFindings.javaFileCount > 0 ? <strong>{repoFindings.javaFileCount} discovered Java source files</strong> : "application source files"} in <strong>{repoFindings.repoName}</strong>. Source-code modifications are minimal and focused on compiler target alignment.
                      </>
                    ) : (
                      <>
                        Source-code refactoring concentrated in package imports and framework deprecations across {repoFindings.javaFileCount > 0 ? <strong>{repoFindings.javaFileCount} discovered Java source files</strong> : "application source files"} in <strong>{repoFindings.repoName}</strong>.
                      </>
                    )}
                  </p>
                  <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
                    {targetJavaNum < 17 ? (
                      <>
                        <li>
                          <strong>Package Imports:</strong> All existing <code>javax.*</code> imports (<code>javax.persistence.*</code>, <code>javax.validation.*</code>, <code>javax.servlet.*</code>) remain unchanged across {repoFindings.javaFileCount > 0 ? `${repoFindings.javaFileCount} Java source files` : "the codebase"}.
                        </li>
                        {repoFindings.hasDataJpa || repoFindings.hasHibernate ? (
                          <li>
                            <strong>Persistence Layer{repoFindings.dataJpaDep ? <> (<code>{repoFindings.dataJpaDep.dependency.split(':')[1] || repoFindings.dataJpaDep.dependency}</code>)</> : ""}:</strong> Entity mappings (<code>@Entity</code>, <code>@Table</code>) and Spring Data repository query methods remain fully compatible without code adjustments.
                          </li>
                        ) : null}
                        {repoFindings.hasWeb ? (
                          <li>
                            <strong>Web Controllers{repoFindings.webDep ? <> (<code>{repoFindings.webDep.dependency.split(':')[1] || repoFindings.webDep.dependency}</code>)</> : ""}:</strong> Spring MVC controllers, request handlers, and servlet filter contracts execute without modifications.
                          </li>
                        ) : null}
                        {repoFindings.hasLombok ? (
                          <li>
                            <strong>Lombok Annotations:</strong> Verify build compiler plugin version in {repoFindings.buildFile} for Java {targetJavaNum} bytecode support; Java POJO annotations require no modifications.
                          </li>
                        ) : null}
                        {repoFindings.testFileCount > 0 || repoFindings.hasJunit4 || repoFindings.hasJunit5 ? (
                          <li>
                            <strong>Test Suites:</strong> {repoFindings.testFileCount > 0 ? `${repoFindings.testFileCount} test file${repoFindings.testFileCount > 1 ? "s" : ""}` : "Test suites"} execute against existing test runners without annotation rewrites.
                          </li>
                        ) : null}
                      </>
                    ) : (
                      <>
                        <li>
                          <strong>Package Imports:</strong> Refactor all <code>javax.*</code> imports to <code>jakarta.*</code> (e.g., <code>jakarta.persistence.*</code>, <code>jakarta.validation.*</code>, <code>jakarta.servlet.*</code>) across {repoFindings.javaFileCount > 0 ? `${repoFindings.javaFileCount} Java source files` : "the codebase"}.
                        </li>
                        {repoFindings.hasSecurity ? (
                          <li>
                            <strong>Security Configuration{repoFindings.securityDep ? <> (<code>{repoFindings.securityDep.dependency.split(':')[1] || repoFindings.securityDep.dependency}</code>)</> : ""}:</strong> Migrate <code>WebSecurityConfigurerAdapter</code> to <code>SecurityFilterChain</code> @Bean and replace <code>antMatchers()</code> with <code>requestMatchers()</code>.
                          </li>
                        ) : null}
                        {repoFindings.hasDataJpa || repoFindings.hasHibernate ? (
                          <li>
                            <strong>Persistence Layer{repoFindings.dataJpaDep ? <> (<code>{repoFindings.dataJpaDep.dependency.split(':')[1] || repoFindings.dataJpaDep.dependency}</code>)</> : ""}:</strong> Audit custom JPQL/HQL queries in repository interfaces for Hibernate 6 SQM syntax compliance and type-safe query execution.
                          </li>
                        ) : null}
                        {repoFindings.hasLombok ? (
                          <li>
                            <strong>Lombok Tooling:</strong> Upgrade Lombok to <code>{repoFindings.lombokDep?.targetVersion || "1.18.36"}</code> in {repoFindings.buildFile} to support Java {targetJavaNum} bytecode generation.
                          </li>
                        ) : null}
                        {repoFindings.hasJunit4 || repoFindings.testFileCount > 0 ? (
                          <li>
                            <strong>Testing Framework:</strong> Migrate unit test annotations from JUnit 4 (<code>@Test org.junit.Test</code>) to JUnit Jupiter 5 (<code>@Test org.junit.jupiter.api.Test</code>) across {repoFindings.testFileCount > 0 ? `${repoFindings.testFileCount} test files` : "test classes"}.
                          </li>
                        ) : null}
                      </>
                    )}
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* Card 5: Configuration Impact */}
          <div
            style={{
              background: "#ffffff",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              overflow: "hidden",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.03)",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              onClick={() => toggleCard("configuration")}
              style={{
                cursor: "pointer",
                padding: "12px 16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                userSelect: "none",
                background: expandedCards.configuration ? "#f8fafc" : "#ffffff",
                borderBottom: expandedCards.configuration ? "1px solid #e2e8f0" : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 6,
                    background: "#cffafe",
                    color: "#0891b2",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <FaDatabase size={13} />
                </div>
                <div>
                  <h5 style={{ margin: 0, fontSize: 13, fontWeight: 800, color: "#1e293b" }}>
                    Configuration Impact
                  </h5>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    {repoFindings.buildFile} &amp; Properties
                  </span>
                </div>
              </div>
              <span style={{ fontSize: 11, color: "#64748b", fontWeight: 600, display: "flex", alignItems: "center", gap: 5 }}>
                {expandedCards.configuration ? "Hide" : "Details"}
                {expandedCards.configuration ? <FaChevronUp size={10} /> : <FaChevronDown size={10} />}
              </span>
            </div>

            {/* Always visible concise preview */}
            <div style={{ padding: "10px 16px", fontSize: 12, color: "#475569", lineHeight: 1.5 }}>
              Set compiler target Java {targetJavaVersion || "21"} in <strong>{repoFindings.buildFile}</strong> and maintain {repoFindings.configFileCount} configuration file{repoFindings.configFileCount > 1 ? "s" : ""}{repoFindings.dbDriver ? ` (${repoFindings.dbDriver} datasource)` : ""}.
            </div>

            {/* Expandable detailed tray */}
            {expandedCards.configuration && (
              <div style={{ padding: "12px 16px", background: "#f8fafc", borderTop: "1px solid #e2e8f0", fontSize: 12 }}>
                <div style={{ color: "#475569", lineHeight: 1.6 }}>
                  <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
                    {targetJavaNum < 17 ? (
                      <>
                        <li>
                          <strong>Build Manifest ({repoFindings.buildTool} / {repoFindings.buildFile}):</strong> Set <code>&lt;java.version&gt;{targetJavaVersion || "11"}&lt;/java.version&gt;</code> (or compiler release {targetJavaNum}) and update Spring Boot parent version to <code>{selectedBootVersion}</code>.
                        </li>
                        <li>
                          <strong>Application Properties ({repoFindings.configFileCount > 0 ? `${repoFindings.configFileCount} configuration file${repoFindings.configFileCount > 1 ? "s" : ""}` : "application.properties/yml"}):</strong> Retain existing Spring Boot 2.7 property keys (e.g., <code>spring.datasource.*</code>, <code>spring.jpa.hibernate.ddl-auto</code>). No property relocation needed.
                        </li>
                        <li>
                          <strong>Database &amp; Dialects:</strong> Retain Hibernate 5 dialect configuration{repoFindings.dbDriver ? ` and ${repoFindings.dbDriver} datasource properties` : ""}.
                        </li>
                      </>
                    ) : (
                      <>
                        <li>
                          <strong>Build Manifest ({repoFindings.buildTool} / {repoFindings.buildFile}):</strong> Set <code>&lt;java.version&gt;{targetJavaVersion || "21"}&lt;/java.version&gt;</code>, update parent to Spring Boot <code>{selectedBootVersion}</code>, and configure compiler release {targetJavaNum}.
                        </li>
                        <li>
                          <strong>Application Properties ({repoFindings.configFileCount > 0 ? `${repoFindings.configFileCount} configuration file${repoFindings.configFileCount > 1 ? "s" : ""}` : "application.properties/yml"}):</strong> Audit properties for Spring Boot 3 renames (e.g., <code>spring.data.*</code> prefix updates, management endpoint key relocations).
                        </li>
                        <li>
                          <strong>Database &amp; Dialects:</strong> Hibernate 6 automatically resolves database dialects{repoFindings.dbDriver ? ` for ${repoFindings.dbDriver}` : ""}; remove obsolete explicit dialect classes (e.g. <code>org.hibernate.dialect.*</code>) from properties.
                        </li>
                      </>
                    )}
                  </ul>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Portal-based Risk Tooltip for Column Header */}
      {typeof document !== "undefined" &&
        activeRiskTooltip &&
        createPortal(
          (() => {
            const tooltipWidth = 370;
            const rect = activeRiskTooltip.rect;
            const isNearBottom = rect.bottom + 270 > window.innerHeight;
            const top = isNearBottom ? Math.max(12, rect.top - 8) : rect.bottom + 8;
            const transform = isNearBottom ? "translateY(-100%)" : "none";
            const left = Math.max(
              16,
              Math.min(window.innerWidth - tooltipWidth - 16, rect.right - tooltipWidth + 10)
            );

            return (
              <div
                style={{
                  position: "fixed",
                  top,
                  left,
                  transform,
                  width: tooltipWidth,
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                  borderRadius: 10,
                  boxShadow: "0 14px 34px -4px rgba(15, 23, 42, 0.22), 0 6px 14px -4px rgba(15, 23, 42, 0.08)",
                  padding: "14px 16px",
                  zIndex: 999999,
                  pointerEvents: "none",
                  fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 5 }}>
                  <FaShieldAlt size={14} style={{ color: "#2563eb" }} />
                  <span style={{ fontSize: 13, fontWeight: 800, color: "#0f172a" }}>
                    Risk Assessment Classification Criteria
                  </span>
                </div>
                <p style={{ margin: "0 0 10px 0", fontSize: 11, color: "#64748b", lineHeight: 1.4 }}>
                  Criteria used to classify migration risk based on bytecode, framework generation, and source-code impact:
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as MigrationRisk[]).map((lvl) => {
                    const detail = RISK_CRITERIA_DETAILS[lvl];
                    return (
                      <div
                        key={lvl}
                        style={{
                          background: detail.badgeColor.background,
                          border: `1px solid ${detail.badgeColor.border}`,
                          borderRadius: 6,
                          padding: "6px 9px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                          <span
                            style={{
                              fontSize: 9.5,
                              fontWeight: 800,
                              color: detail.badgeColor.text,
                              background: "#ffffff",
                              border: `1px solid ${detail.badgeColor.border}`,
                              padding: "1px 5px",
                              borderRadius: 3,
                            }}
                          >
                            {lvl}
                          </span>
                          <span style={{ fontSize: 11, fontWeight: 700, color: detail.badgeColor.text }}>
                            {detail.title}
                          </span>
                        </div>
                        <div style={{ fontSize: 10.5, color: "#334155", lineHeight: 1.35 }}>
                          {detail.summary}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })(),
          document.body
        )}
    </section>
  );
}
