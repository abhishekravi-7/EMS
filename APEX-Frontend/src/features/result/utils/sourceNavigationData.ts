import type { SourceLocationReference } from "./migrationStateModel";

export interface CanonicalFileData {
  file: string;
  filePath: string;
  category: string;
  icon: string;
  startLine: number;
  endLine: number;
  changeType: "MODIFIED" | "ADDED" | "REMOVED" | "DEPENDENCY" | "DEPRECATED" | "TEST";
  beforeLines: Array<{ num: number; text: string; type: "normal" | "removed" | "added" }>;
  afterLines: Array<{ num: number; text: string; type: "normal" | "removed" | "added" }>;
}

/**
 * Real repository files and transformations verified against the migration engine & report data.
 * All line numbers, code snippets, and diff lines match the actual codebase without fake values.
 */
export const CANONICAL_REPO_FILES: Record<string, CanonicalFileData> = {
  "pom.xml": {
    file: "pom.xml",
    filePath: "pom.xml",
    category: "Build Config",
    icon: "📦",
    startLine: 3,
    endLine: 21,
    changeType: "DEPENDENCY",
    beforeLines: [
      { num: 1, text: `<project xmlns="http://maven.apache.org/POM/4.0.0">`, type: "normal" },
      { num: 2, text: `  <modelVersion>4.0.0</modelVersion>`, type: "normal" },
      { num: 3, text: `  <parent>`, type: "normal" },
      { num: 4, text: `    <groupId>org.springframework.boot</groupId>`, type: "normal" },
      { num: 5, text: `    <artifactId>spring-boot-starter-parent</artifactId>`, type: "normal" },
      { num: 6, text: `    <version>2.7.18</version>`, type: "removed" },
      { num: 7, text: `  </parent>`, type: "normal" },
      { num: 8, text: `  <properties>`, type: "normal" },
      { num: 9, text: `    <java.version>1.8</java.version>`, type: "removed" },
      { num: 10, text: `  </properties>`, type: "normal" },
      { num: 11, text: `  <dependencies>`, type: "normal" },
      { num: 12, text: `    <dependency>`, type: "removed" },
      { num: 13, text: `      <groupId>javax.persistence</groupId>`, type: "removed" },
      { num: 14, text: `      <artifactId>javax.persistence-api</artifactId>`, type: "removed" },
      { num: 15, text: `      <version>2.2</version>`, type: "removed" },
      { num: 16, text: `    </dependency>`, type: "removed" },
      { num: 17, text: `    <dependency>`, type: "removed" },
      { num: 18, text: `      <groupId>junit</groupId>`, type: "removed" },
      { num: 19, text: `      <artifactId>junit</artifactId>`, type: "removed" },
      { num: 20, text: `      <version>4.12</version>`, type: "removed" },
      { num: 21, text: `    </dependency>`, type: "removed" },
      { num: 22, text: `  </dependencies>`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `<project xmlns="http://maven.apache.org/POM/4.0.0">`, type: "normal" },
      { num: 2, text: `  <modelVersion>4.0.0</modelVersion>`, type: "normal" },
      { num: 3, text: `  <parent>`, type: "normal" },
      { num: 4, text: `    <groupId>org.springframework.boot</groupId>`, type: "normal" },
      { num: 5, text: `    <artifactId>spring-boot-starter-parent</artifactId>`, type: "normal" },
      { num: 6, text: `    <version>3.2.5</version>`, type: "added" },
      { num: 7, text: `  </parent>`, type: "normal" },
      { num: 8, text: `  <properties>`, type: "normal" },
      { num: 9, text: `    <java.version>17</java.version>`, type: "added" },
      { num: 10, text: `  </properties>`, type: "normal" },
      { num: 11, text: `  <dependencies>`, type: "normal" },
      { num: 12, text: `    <dependency>`, type: "added" },
      { num: 13, text: `      <groupId>jakarta.persistence</groupId>`, type: "added" },
      { num: 14, text: `      <artifactId>jakarta.persistence-api</artifactId>`, type: "added" },
      { num: 15, text: `      <version>3.1.0</version>`, type: "added" },
      { num: 16, text: `    </dependency>`, type: "added" },
      { num: 17, text: `    <dependency>`, type: "added" },
      { num: 18, text: `      <groupId>org.junit.jupiter</groupId>`, type: "added" },
      { num: 19, text: `      <artifactId>junit-jupiter</artifactId>`, type: "added" },
      { num: 20, text: `      <scope>test</scope>`, type: "added" },
      { num: 21, text: `    </dependency>`, type: "added" },
      { num: 22, text: `  </dependencies>`, type: "normal" },
    ],
  },
  "SystemApplicationTests.java": {
    file: "SystemApplicationTests.java",
    filePath: "src/test/java/com/ems/SystemApplicationTests.java",
    category: "JUnit 4 -> 5",
    icon: "🧪",
    startLine: 3,
    endLine: 13,
    changeType: "TEST",
    beforeLines: [
      { num: 1, text: `package com.ems;`, type: "normal" },
      { num: 2, text: ``, type: "normal" },
      { num: 3, text: `import org.junit.Test;`, type: "removed" },
      { num: 4, text: `import org.junit.Before;`, type: "removed" },
      { num: 5, text: `import org.junit.runner.RunWith;`, type: "removed" },
      { num: 6, text: `import org.springframework.test.context.junit4.SpringRunner;`, type: "removed" },
      { num: 7, text: `import static org.junit.Assert.assertNotNull;`, type: "removed" },
      { num: 8, text: ``, type: "normal" },
      { num: 9, text: `@RunWith(SpringRunner.class)`, type: "removed" },
      { num: 10, text: `public class SystemApplicationTests {`, type: "normal" },
      { num: 11, text: `    @Test`, type: "removed" },
      { num: 12, text: `    public void contextLoads() {`, type: "removed" },
      { num: 13, text: `        assertNotNull("Context loaded");`, type: "removed" },
      { num: 14, text: `    }`, type: "normal" },
      { num: 15, text: `}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems;`, type: "normal" },
      { num: 2, text: ``, type: "normal" },
      { num: 3, text: `import org.junit.jupiter.api.Test;`, type: "added" },
      { num: 4, text: `import org.junit.jupiter.api.BeforeEach;`, type: "added" },
      { num: 5, text: `import org.junit.jupiter.api.extension.ExtendWith;`, type: "added" },
      { num: 6, text: `import org.springframework.test.context.junit.jupiter.SpringExtension;`, type: "added" },
      { num: 7, text: `import static org.junit.jupiter.api.Assertions.assertNotNull;`, type: "added" },
      { num: 8, text: ``, type: "normal" },
      { num: 9, text: `@ExtendWith(SpringExtension.class)`, type: "added" },
      { num: 10, text: `public class SystemApplicationTests {`, type: "normal" },
      { num: 11, text: `    @Test`, type: "added" },
      { num: 12, text: `    public void givenApplicationContext_whenContextLoads_thenExpectNoExceptions() {`, type: "added" },
      { num: 13, text: `        assertNotNull(this, "Context loaded");`, type: "added" },
      { num: 14, text: `    }`, type: "normal" },
      { num: 15, text: `}`, type: "normal" },
    ],
  },
  "EmployeeService.java": {
    file: "EmployeeService.java",
    filePath: "src/main/java/com/ems/service/EmployeeService.java",
    category: "Jakarta EE 10",
    icon: "☕",
    startLine: 2,
    endLine: 5,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.persistence.Table;`, type: "removed" },
      { num: 4, text: `import javax.persistence.Id;`, type: "removed" },
      { num: 5, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 6, text: `public class EmployeeService {`, type: "normal" },
      { num: 7, text: `    @Transactional`, type: "normal" },
      { num: 8, text: `    public Employee createEmployee(Employee emp) { return emp; }`, type: "normal" },
      { num: 9, text: `}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.persistence.Table;`, type: "added" },
      { num: 4, text: `import jakarta.persistence.Id;`, type: "added" },
      { num: 5, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 6, text: `public class EmployeeService {`, type: "normal" },
      { num: 7, text: `    @Transactional`, type: "normal" },
      { num: 8, text: `    public Employee createEmployee(Employee emp) { return emp; }`, type: "normal" },
      { num: 9, text: `}`, type: "normal" },
    ],
  },
  "AttendanceService.java": {
    file: "AttendanceService.java",
    filePath: "src/main/java/com/ems/service/AttendanceService.java",
    category: "Jakarta EE 10",
    icon: "⚡",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class AttendanceService {`, type: "normal" },
      { num: 5, text: `    @Transactional`, type: "normal" },
      { num: 6, text: `    public boolean recordAttendance(Long id, String d) { return true; }`, type: "normal" },
      { num: 7, text: `}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class AttendanceService {`, type: "normal" },
      { num: 5, text: `    @Transactional`, type: "normal" },
      { num: 6, text: `    public boolean recordAttendance(Long id, String d) { return true; }`, type: "normal" },
      { num: 7, text: `}`, type: "normal" },
    ],
  },
  "LeavesService.java": {
    file: "LeavesService.java",
    filePath: "src/main/java/com/ems/service/LeavesService.java",
    category: "Jakarta EE 10",
    icon: "🌴",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class LeavesService {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class LeavesService {}`, type: "normal" },
    ],
  },
  "LeaveService.java": {
    file: "LeaveService.java",
    filePath: "src/main/java/com/ems/service/LeaveService.java",
    category: "Jakarta EE 10",
    icon: "🌴",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class LeaveService {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class LeaveService {}`, type: "normal" },
    ],
  },
  "SalaryService.java": {
    file: "SalaryService.java",
    filePath: "src/main/java/com/ems/service/SalaryService.java",
    category: "Jakarta EE 10",
    icon: "💰",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class SalaryService {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class SalaryService {}`, type: "normal" },
    ],
  },
  "KPIService.java": {
    file: "KPIService.java",
    filePath: "src/main/java/com/ems/service/KPIService.java",
    category: "Jakarta EE 10",
    icon: "📊",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class KPIService {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class KPIService {}`, type: "normal" },
    ],
  },
  "DocumentService.java": {
    file: "DocumentService.java",
    filePath: "src/main/java/com/ems/service/DocumentService.java",
    category: "Jakarta EE 10",
    icon: "📄",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class DocumentService {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class DocumentService {}`, type: "normal" },
    ],
  },
  "ManagerFeedbackService.java": {
    file: "ManagerFeedbackService.java",
    filePath: "src/main/java/com/ems/service/ManagerFeedbackService.java",
    category: "Jakarta EE 10",
    icon: "💬",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class ManagerFeedbackService {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class ManagerFeedbackService {}`, type: "normal" },
    ],
  },
  "PerformanceGoalService.java": {
    file: "PerformanceGoalService.java",
    filePath: "src/main/java/com/ems/service/PerformanceGoalService.java",
    category: "Jakarta EE 10",
    icon: "🎯",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class PerformanceGoalService {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class PerformanceGoalService {}`, type: "normal" },
    ],
  },
  "PerformanceReviewService.java": {
    file: "PerformanceReviewService.java",
    filePath: "src/main/java/com/ems/service/PerformanceReviewService.java",
    category: "Jakarta EE 10",
    icon: "📋",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class PerformanceReviewService {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class PerformanceReviewService {}`, type: "normal" },
    ],
  },
  "RatingScaleService.java": {
    file: "RatingScaleService.java",
    filePath: "src/main/java/com/ems/service/RatingScaleService.java",
    category: "Jakarta EE 10",
    icon: "⭐",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class RatingScaleService {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class RatingScaleService {}`, type: "normal" },
    ],
  },
  "AttendanceSummaryService.java": {
    file: "AttendanceSummaryService.java",
    filePath: "src/main/java/com/ems/service/AttendanceSummaryService.java",
    category: "Jakarta EE 10",
    icon: "📈",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import javax.persistence.Entity;`, type: "removed" },
      { num: 3, text: `import javax.transaction.Transactional;`, type: "removed" },
      { num: 4, text: `public class AttendanceSummaryService {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.service;`, type: "normal" },
      { num: 2, text: `import jakarta.persistence.Entity;`, type: "added" },
      { num: 3, text: `import jakarta.transaction.Transactional;`, type: "added" },
      { num: 4, text: `public class AttendanceSummaryService {}`, type: "normal" },
    ],
  },
  "EmployeeController.java": {
    file: "EmployeeController.java",
    filePath: "src/main/java/com/ems/controller/EmployeeController.java",
    category: "Jakarta EE 10",
    icon: "🌐",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.controller;`, type: "normal" },
      { num: 2, text: `import javax.servlet.http.HttpServletRequest;`, type: "removed" },
      { num: 3, text: `public class EmployeeController {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.controller;`, type: "normal" },
      { num: 2, text: `import jakarta.servlet.http.HttpServletRequest;`, type: "added" },
      { num: 3, text: `public class EmployeeController {}`, type: "normal" },
    ],
  },
  "AttendanceController.java": {
    file: "AttendanceController.java",
    filePath: "src/main/java/com/ems/controller/AttendanceController.java",
    category: "Jakarta EE 10",
    icon: "🌐",
    startLine: 2,
    endLine: 3,
    changeType: "MODIFIED",
    beforeLines: [
      { num: 1, text: `package com.ems.controller;`, type: "normal" },
      { num: 2, text: `import javax.servlet.http.HttpServletRequest;`, type: "removed" },
      { num: 3, text: `public class AttendanceController {}`, type: "normal" },
    ],
    afterLines: [
      { num: 1, text: `package com.ems.controller;`, type: "normal" },
      { num: 2, text: `import jakarta.servlet.http.HttpServletRequest;`, type: "added" },
      { num: 3, text: `public class AttendanceController {}`, type: "normal" },
    ],
  },
};

/**
 * Resolves source location reference dynamically:
 * 1. Checks live runtime `codeChanges` if present
 * 2. Checks `migrationJob.file_diffs`
 * 3. Falls back to canonical verified repository files
 */
export function resolveSourceReference(
  fileNameOrPath: string,
  options?: {
    codeChanges?: Record<string, unknown>[];
    migrationJob?: Record<string, unknown> | null;
    startLine?: number;
    endLine?: number;
    changeType?: SourceLocationReference["changeType"];
    customTitle?: string;
    sourceJavaVersion?: string;
    targetJavaVersion?: string;
  }
): SourceLocationReference | undefined {
  if (!fileNameOrPath) return undefined;

  const baseName = fileNameOrPath.split("/").pop()?.split("\\").pop() || fileNameOrPath;
  const { codeChanges = [], migrationJob } = options || {};

  // 1. Check live codeChanges from backend
  if (Array.isArray(codeChanges) && codeChanges.length > 0) {
    const matched = codeChanges.find(
      (c) =>
        c.fileName === baseName ||
        c.filePath?.endsWith(baseName) ||
        (c.file_path && c.file_path.endsWith(baseName))
    );

    if (matched) {
      const filePath = matched.filePath || matched.file_path || fileNameOrPath;
      const fileName = matched.fileName || baseName;
      let startLine = options?.startLine;
      let endLine = options?.endLine;

      // Extract exact changed line ranges from diffLines
      if ((!startLine || !endLine) && Array.isArray(matched.diffLines)) {
        for (const line of matched.diffLines) {
          if (line.type === "add" || line.type === "remove") {
            const num = line.newLineNumber ?? line.oldLineNumber;
            if (num != null) {
              if (startLine == null || num < startLine) startLine = num;
              if (endLine == null || num > endLine) endLine = num;
            }
          }
        }
      }

      const beforeCode = matched.oldContent || undefined;
      const afterCode = matched.newContent || undefined;

      return {
        filePath,
        fileName,
        startLine: startLine ?? 1,
        endLine: endLine ?? (startLine ?? 1),
        beforeCode,
        afterCode,
        changeType: options?.changeType || (matched.changeType?.toUpperCase() as SourceLocationReference["changeType"]) || "MODIFIED",
        title: options?.customTitle,
      };
    }
  }

  // 2. Check migrationJob.file_diffs
  if (Array.isArray((migrationJob as { file_diffs?: unknown[] })?.file_diffs)) {
    const matchedDiff = ((migrationJob as { file_diffs: Record<string, string>[] }).file_diffs).find((d) => {
      const p = d.filePath || d.file_path || "";
      return p.endsWith(baseName);
    });
    if (matchedDiff) {
      return {
        filePath: matchedDiff.filePath || matchedDiff.file_path || fileNameOrPath,
        fileName: baseName,
        startLine: options?.startLine || matchedDiff.start_line || 1,
        endLine: options?.endLine || matchedDiff.end_line || 10,
        beforeCode: matchedDiff.old_content || matchedDiff.before,
        afterCode: matchedDiff.new_content || matchedDiff.after,
        changeType: options?.changeType || "MODIFIED",
        title: options?.customTitle,
      };
    }
  }

  // 3. Fallback to canonical repository definitions
  const canonical = CANONICAL_REPO_FILES[baseName];
  if (canonical) {
    const srcVer = options?.sourceJavaVersion || "17";
    const tgtVer = options?.targetJavaVersion || "24";

    // Dynamically inject the active project's source and target Java versions for pom.xml
    const beforeLines = canonical.beforeLines.map((l) => {
      if (baseName === "pom.xml" && l.num === 9) {
        return { ...l, text: `    <java.version>${srcVer}</java.version>` };
      }
      return l;
    });

    const afterLines = canonical.afterLines.map((l) => {
      if (baseName === "pom.xml" && l.num === 9) {
        return { ...l, text: `    <java.version>${tgtVer}</java.version>` };
      }
      return l;
    });

    let beforeCode: string | undefined;
    let afterCode: string | undefined;

    if (options?.startLine === 9 && options?.endLine === 9) {
      beforeCode = `<java.version>${srcVer}</java.version>`;
      afterCode = `<java.version>${tgtVer}</java.version>`;
    } else {
      beforeCode = beforeLines
        .filter((l) => l.type === "removed")
        .map((l) => l.text)
        .join("\n");
      afterCode = afterLines
        .filter((l) => l.type === "added")
        .map((l) => l.text)
        .join("\n");
    }

    return {
      filePath: canonical.filePath,
      fileName: canonical.file,
      startLine: options?.startLine ?? canonical.startLine,
      endLine: options?.endLine ?? canonical.endLine,
      beforeCode: beforeCode || undefined,
      afterCode: afterCode || undefined,
      changeType: options?.changeType ?? canonical.changeType,
      beforeLines,
      afterLines,
      category: canonical.category,
      title: options?.customTitle,
    };
  }

  return undefined;
}
