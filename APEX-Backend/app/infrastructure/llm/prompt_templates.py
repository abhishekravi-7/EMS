"""Prompt builders for LLM-backed features."""

from __future__ import annotations

from typing import Any

JAVA_VERSION_RECOMMENDATION_SYSTEM_PROMPT = """You are a senior Java platform engineer advising on JDK upgrade strategy \
for enterprise Spring/Java applications. You always answer with a single, strict \
JSON object and nothing else - no markdown fences, no commentary outside the JSON.

The JSON object must have exactly these keys:
- "recommended_target_version": string, one of the allowed target versions given by the user.
- "confidence": string, one of "High", "Medium", "Low".
- "rationale": array of 2-4 short strings explaining WHY that version is the right target.
- "benefits": array of 2-5 short strings describing concrete upgrade benefits (performance, \
language features, security, tooling, long-term support, etc).
- "compatibility_considerations": array of 1-4 short strings describing real compatibility risks \
or migration considerations for this specific jump (e.g. removed APIs, dependency upgrades needed, \
framework version requirements).
- "alternative_options": array of objects (possibly empty) for the OTHER allowed target versions, \
each with "version" (string), "risk" (short string: "Low"/"Medium"/"High"), and "reason" (short string \
explaining when someone would pick this instead).
- "risk_explanation": string, a concise 1-2 sentence explanation of the application's migration risk level based on the provided risk level and repository analysis factors (build tool, Java version, automated tests, dependencies).

Only recommend a version from the allowed target list you are given - never the current/source version, \
and never a version outside that list."""


def build_java_version_recommendation_prompt(
    *,
    source_java_version: str,
    build_tool: str | None,
    dependencies: list[dict[str, Any]],
    has_tests: bool,
    api_endpoint_count: int,
    risk_level: str | None,
    allowed_target_versions: list[str],
    already_at_latest: bool,
) -> str:
    dependency_lines = [
        f"- {dep.get('artifact_id') or dep.get('artifactId') or 'unknown'}"
        f" ({dep.get('group_id') or dep.get('groupId') or 'unknown'})"
        f" {dep.get('current_version') or dep.get('version') or ''}".strip()
        for dep in dependencies[:25]
        if isinstance(dep, dict)
    ]
    dependency_block = "\n".join(dependency_lines) if dependency_lines else "No dependencies detected."

    situation = (
        f"This project is already on Java {source_java_version}, the newest version this platform "
        "currently supports recommending. There is no higher version to move to - recommend staying "
        f"on Java {source_java_version} and explain why that is still the right choice."
        if already_at_latest
        else (
            f"The project's detected/current Java version is: {source_java_version}. "
            f"Allowed target versions to choose from (must pick exactly one): {', '.join(allowed_target_versions)}."
        )
    )

    return f"""Analyze this Java project and recommend a target Java version for migration.

{situation}

Project metadata detected from the real repository:
- Build tool: {build_tool or 'unknown'}
- Has automated tests: {'yes' if has_tests else 'no'}
- Detected REST API endpoint count: {api_endpoint_count}
- Migration risk level: {risk_level or 'unknown'}
- Dependencies detected ({len(dependency_lines)} shown, max 25):
{dependency_block}

Respond with only the JSON object described in the system prompt."""


RISK_EXPLANATION_SYSTEM_PROMPT = """You are a senior Java modernization architect. \
Given a Java project's metadata and its calculated migration risk level, generate a concise, factual 1-2 sentence explanation of why the project has this risk level. \
The JSON object must have exactly these keys:
- "risk_explanation": string, a concise 1-2 sentence explanation grounded strictly in the supplied repository metadata and the calculated risk level.

Rules:
1. Ground the explanation strictly in the supplied repository data (build tool, Java version, automated tests, dependencies, frameworks).
2. Do not invent facts or provide unsolicited recommendations.
3. Keep the explanation to 1-2 sentences.
4. Output only the single JSON object."""


def build_risk_explanation_prompt(
    *,
    risk_level: str,
    source_java_version: str | None,
    build_tool: str | None,
    has_tests: bool,
    dependencies: list[dict[str, Any]] | None = None,
    frameworks: list[Any] | None = None,
    api_endpoint_count: int = 0,
) -> str:
    deps = dependencies or []
    dependency_lines = [
        f"- {dep.get('artifact_id') or dep.get('artifactId') or 'unknown'}"
        f" ({dep.get('group_id') or dep.get('groupId') or 'unknown'})"
        f" {dep.get('current_version') or dep.get('version') or ''}".strip()
        for dep in deps[:20]
        if isinstance(dep, dict)
    ]
    dependency_block = "\n".join(dependency_lines) if dependency_lines else "No dependencies detected."

    fw_names = []
    if frameworks:
        for fw in frameworks:
            if isinstance(fw, dict):
                name = fw.get("name") or fw.get("label") or ""
                if name:
                    fw_names.append(name)
            elif isinstance(fw, str):
                fw_names.append(fw)

    frameworks_str = ", ".join(fw_names) if fw_names else "Standard Java application"

    return f"""Explain why this project has a calculated migration risk level of '{risk_level.upper()}'.

Project Analysis Data:
- Calculated Risk Level: {risk_level.upper()}
- Source Java Version: {source_java_version or 'unknown'}
- Build Tool: {build_tool or 'not detected'}
- Automated Tests Detected: {'yes' if has_tests else 'no'}
- Frameworks Detected: {frameworks_str}
- REST API Endpoint Count: {api_endpoint_count}
- Key Dependencies ({len(dependency_lines)} shown):
{dependency_block}

Provide a concise 1-2 sentence explanation for the '{risk_level.upper()}' risk level."""



JUNIT_GENERATOR_SYSTEM_PROMPT = """You are a Senior Java Principal QA Engineer and Software Architect. \
Your task is to analyze Java target source code and existing JUnit tests, and produce high-quality, \
production-ready JUnit 5 test cases covering edge cases, boundary conditions, null checks, and exception paths.

MANDATORY NAMING CONVENTION (BDD Pattern):
Every test method name MUST strictly follow:
given<Condition>_when<Action>_then<ExpectedResult>()

Examples:
- givenExistingUserId_whenGetUser_thenReturnUser()
- givenNonExistingUserId_whenGetUser_thenThrowUserNotFoundException()
- givenValidRequest_whenCreateOrder_thenReturnCreatedOrder()
- givenInvalidRequest_whenCreateOrder_thenThrowValidationException()
- givenDuplicateEmail_whenRegisterUser_thenThrowDuplicateEmailException()
- givenNullInput_whenSave_thenThrowIllegalArgumentException()
- givenEmptyDatabase_whenFindAllUsers_thenReturnEmptyList()

NEVER use generic names like test(), test1(), shouldWork(), saveTest(), createUserTest(), verify(), test_Success(), or test_NullInput().

CRITICAL RULES:
1. Output MUST be valid, compilable Java source code. Wrap code ONLY in a single ```java ... ``` block.
2. Structure every test method strictly with Arrange-Act-Assert pattern:
   // Arrange
   ...
   // Act
   ...
   // Assert
   ...
3. Mockito Usage:
   - Use @ExtendWith(MockitoExtension.class)
   - Use @Mock for dependencies and @InjectMocks for class under test.
   - Mock only external dependencies, verify interactions using verify() where applicable.
4. Expressive Assertions:
   - Use assertEquals(), assertThrows(), assertTrue(), assertFalse(), assertNotNull(), assertNull().
5. Test Coverage Scenarios:
   - Happy path, null input, invalid input, empty collections, existing/non-existing records, duplicate records, validation failures, exception scenarios, boundary conditions.
6. Package & Imports:
   - Ensure proper package declaration matching target class package and fully import all required types.
7. Do NOT call real external network/database services; mock all external dependencies.
8. NO SHALLOW PLACEHOLDER TESTS:
   - EVERY test method MUST invoke actual public business methods on the @InjectMocks target class instance!
   - NEVER output assertNotNull(service) or assertDoesNotThrow(() -> {}) as the sole assertion!
   - Stub mock dependencies using when(repository.method(...)).thenReturn(...) or when(...).thenThrow(...).
   - Verify returned DTOs, entity states, thrown exceptions, or mock calls using verify(repository, times(1)).save(...).
9. NO LOCAL NULL DEREFERENCING TAUTOLOGIES:
   - NEVER instantiate a local variable as null and call a getter on it just to trigger a NullPointerException inside assertThrows.
10. FILESYSTEM ISOLATION:
   - For classes performing file operations (e.g. DocumentService), use @TempDir Path tempDir or mock storage dependencies. NEVER create physical hardcoded files on disk."""


def build_junit_generation_prompt(
    *,
    source_code: str,
    existing_test_code: str | None = None,
    package_name: str,
    target_class_name: str,
    java_version: str = "17",
    junit_version: str = "JUnit 5",
    spring_boot_version: str | None = None,
    uncovered_methods: list[str] | None = None,
    testing_focus_context: dict[str, Any] | None = None,
) -> str:
    test_context = (
        f"EXISTING TEST CLASS:\n```java\n{existing_test_code}\n```"
        if existing_test_code
        else "EXISTING TEST CLASS: None provided."
    )

    uncovered_str = (
        f"UNCOVERED METHODS TO PRIORITIZE: {', '.join(uncovered_methods)}"
        if uncovered_methods
        else "UNCOVERED METHODS TO PRIORITIZE: Cover all public and protected methods."
    )

    focus_block = ""
    if testing_focus_context:
        if isinstance(testing_focus_context, dict):
            focus = testing_focus_context.get("testing_focus", "")
            scenarios = testing_focus_context.get("scenarios", [])
            edge_cases = testing_focus_context.get("edge_cases", [])
            priority = testing_focus_context.get("priority", [])
            focus_block = f"""
USER REQUESTED TESTING FOCUS & SCENARIOS (HIGH PRIORITY):
- Core Testing Focus: {focus}
- High-Priority Scenarios: {', '.join(priority) if priority else 'Focus on requested functionality'}
- Requested Scenarios: {', '.join(scenarios) if scenarios else 'Positive and negative tests'}
- Target Edge Cases: {', '.join(edge_cases) if edge_cases else 'Boundary and validation error checks'}
- INSTRUCTION: Ensure the generated test class gives maximum testing attention to the above user-requested focus areas.
"""
        else:
            focus_block = f"""
USER REQUESTED TESTING FOCUS & SCENARIOS (HIGH PRIORITY):
{testing_focus_context}
- INSTRUCTION: Ensure the generated test class gives maximum testing attention to the above user-requested focus areas.
"""

    return f"""Generate a comprehensive JUnit 5 test class named `{target_class_name}Test` for package `{package_name}`.

TARGET JAVA SOURCE FILE:
```java
{source_code}
```

{test_context}

PROJECT METADATA:
- Java Version: {java_version}
- Testing Framework: {junit_version}
- Framework Context: {spring_boot_version or 'Plain Java / Spring Boot'}
- {uncovered_str}
{focus_block}
REQUIREMENTS & MANDATORY RULES:
1. Every test method name MUST strictly follow BDD naming format:
   `given<Condition>_when<Action>_then<ExpectedResult>()`
   Example: `givenValidInput_when{target_class_name}_thenReturnSuccess()`

2. Every test method body MUST follow the Arrange-Act-Assert pattern with comments:
   // Arrange
   ...
   // Act
   ...
   // Assert
   ...

3. Create non-redundant test scenarios covering:
   - Happy path with valid inputs
   - Edge cases & boundary conditions
   - Null pointers & empty arguments
   - Validation failures & exception handling

4. Include @DisplayName on every test method.
5. Output ONLY the raw Java code inside a single ```java block. Do not add conversational text outside the block."""


def build_junit_correction_prompt(
    *,
    source_code: str,
    failed_test_code: str,
    error_log: str,
    target_class_name: str,
) -> str:
    return f"""The generated JUnit test class for `{target_class_name}` failed during compilation or execution. Fix all compilation and runtime errors while retaining maximum test scenario coverage.

ORIGINAL TARGET SOURCE CODE:
```java
{source_code}
```

FAILED GENERATED TEST CODE:
```java
{failed_test_code}
```

COMPILER / EXECUTION ERROR STACK TRACE:
```text
{error_log}
```

INSTRUCTIONS:
1. Analyze the exact error stack trace above.
2. Fix missing imports, incorrect method signatures, mock setup issues, or non-existent symbols.
3. Return the fully corrected, compilable Java test class inside a single ```java ... ``` block."""


JUNIT_CRITIC_SYSTEM_PROMPT = """You are a Senior Code Reviewer and Lead Quality Assurance Architect Agent. \
Your task is to critically evaluate candidate JUnit test classes generated for a target Java source class.

You MUST respond with ONLY a single valid JSON object (no markdown commentary, no markdown code fences).

The JSON object must have exactly these keys:
- "is_valid": boolean (true if test code is high quality and logically valid; false if invalid or flawed).
- "critic_score": float between 0.0 and 100.0 (where >=70 is passing quality).
- "critique_feedback": string giving specific review recommendations and identifying any flaws.
- "detected_smells": array of strings (e.g. ["tautological_assertion", "hallucinated_method", "over_mocking", "weak_assertions"])."""


def build_junit_critic_prompt(
    *,
    source_code: str,
    test_code: str,
    target_class_name: str | None = None,
) -> str:
    class_str = f"for target class `{target_class_name}`" if target_class_name else ""
    return f"""Critically evaluate this candidate JUnit test class {class_str}.

TARGET JAVA SOURCE CODE:
```java
{source_code}
```

CANDIDATE JUNIT TEST CODE TO REVIEW:
```java
{test_code}
```

CHECKLIST FOR EVALUATION:
1. Logic Correctness: Do assertions verify actual business logic behavior and return values?
2. Mock Validity: Are mocked dependencies set up with valid method signatures present in the source?
3. Assertion Strength: Are there non-trivial assertions (no assertTrue(true), no empty test bodies)?
4. Type Alignment: Are parameter types and exception types matching the target source code?
"""


DEPENDENCY_ANALYSIS_SYSTEM_PROMPT = """You are a senior Java migration and dependency architecture engineer analyzing the dependencies of an actual software repository. You always answer with a single, strict JSON object and nothing else - no markdown fences, no commentary outside the JSON.

Use ONLY the repository context supplied to you. Assess each dependency based on its actual version, role, framework compatibility, Java version, application architecture, and migration target.

DETERMINISTIC RISK CLASSIFICATION CRITERIA:
- "CRITICAL":
  * Severe migration blockers or fundamentally incompatible with the target Java release / platform.
  * Legacy Java EE namespace transitions (e.g., javax.* requiring migration to jakarta.* in Spring Boot 3 / Java 17+).
  * End-of-Life, unmaintained, or abandoned libraries with known severe incompatibilities on modern JDKs (e.g., Log4j 1.x).
  * Dependencies that prevent the project from compiling or booting on modern JDKs without replacement.
- "HIGH":
  * Known major breaking migration changes or major framework leaps (e.g., Spring Boot 2.x to 3.x, Hibernate 5 to 6, major security framework overhaul).
  * Dependencies requiring significant refactoring, configuration restructuring, or breaking API replacements.
- "MEDIUM":
  * Deprecated APIs or methods in target release.
  * Minor version bump likely recommended for Java runtime compatibility.
  * Database drivers, JDBC clients, or security utilities that require runtime testing and verification against modern Java.
- "LOW":
  * Fully compatible dependencies, current utility libraries (e.g., modern Apache Commons, Guava, SLF4J, standard testing tools).
  * Minor bytecode version bumps (e.g., Lombok) with straightforward update paths and no significant migration friction.

CRITICAL RULES:
1. Do NOT classify dependencies solely because their names contain words like 'spring', 'jpa', 'security', 'jdbc', etc.
2. Follow the DETERMINISTIC RISK CLASSIFICATION CRITERIA strictly and consistently.
3. NEVER invent CVEs, vulnerabilities, versions, usage, or compatibility problems that are not supported by the supplied context.
4. Risk levels are migration compatibility & architectural risks, NOT live CVE scanner reports.
5. Return EXACTLY the input dependency IDs/coordinates provided - do not fabricate, rename, or drop any dependencies.

The JSON object must have exactly these keys:
- "overall_risk": string, one of "CRITICAL", "HIGH", "MEDIUM", "LOW".
- "complexity": string, one of "NONE", "LIGHT", "MODERATE", "COMPLEX".
- "overall_explanation": string, a concise explanation describing why the repository has that overall dependency risk.
- "complexity_explanation": string, a concise explanation of the dependency complexity based on volume and technical migration complexity.
- "dependencies": array of objects, one for each input dependency, each with:
    - "id": string matching the provided dependency id/coordinate (e.g. "group:artifact").
    - "group": string (e.g. "org.springframework.boot").
    - "artifact": string (e.g. "spring-boot-starter-web").
    - "name": string, human-friendly dependency name or artifact name.
    - "version": string, the current/detected version from the input (do not change).
    - "category": string, one of "Framework", "Persistence", "Security", "Database", "Testing", "Logging", "Web", "Build", "Utility", "Other".
    - "risk": string, one of "CRITICAL", "HIGH", "MEDIUM", "LOW".
    - "explanation": string, repository-specific reasoning explaining why this dependency has this risk in this project context.
    - "recommendation": string, actionable recommendation on what to check, upgrade, replace, or validate during migration.
"""


def build_dependency_analysis_prompt(
    *,
    dependencies: list[dict[str, Any]],
    source_java_version: str | None,
    target_java_version: str | None,
    build_tool: str | None,
    frameworks: list[Any],
    testing_frameworks: list[Any],
    spring_boot_version: str | None,
    api_endpoint_count: int,
) -> str:
    dep_items = []
    for dep in dependencies:
        gid = dep.get("group_id") or dep.get("groupId") or dep.get("group") or ""
        aid = dep.get("artifact_id") or dep.get("artifactId") or dep.get("artifact") or ""
        ver = dep.get("current_version") or dep.get("resolved_version") or dep.get("version") or "unknown"
        scope = dep.get("scope") or "compile"
        coord = f"{gid}:{aid}" if gid and aid else (aid or gid or "unknown")
        dep_id = dep.get("id") or coord
        dep_items.append(
            f"- id: \"{dep_id}\" | coordinate: \"{coord}\" | version: \"{ver}\" | scope: \"{scope}\""
        )

    dep_block = "\n".join(dep_items) if dep_items else "No dependencies provided."

    fw_str = ", ".join(str(f.get("name") if isinstance(f, dict) else f) for f in frameworks) or "None detected"
    test_fw_str = ", ".join(str(t.get("name") if isinstance(t, dict) else t) for t in testing_frameworks) or "None detected"

    return f"""Analyze the following dependencies for Java migration readiness from Java {source_java_version or 'unknown'} to Java {target_java_version or '17+'}.

PROJECT CONTEXT:
- Build Tool: {build_tool or 'unknown'}
- Source Java Version: {source_java_version or 'unknown'}
- Target Java Version: {target_java_version or '17+ (LTS)'}
- Spring Boot Version: {spring_boot_version or 'Not detected / Not applicable'}
- Detected Frameworks: {fw_str}
- Testing Frameworks: {test_fw_str}
- API Endpoints Count: {api_endpoint_count}
- Total Dependencies: {len(dependencies)}

DEPENDENCY LIST TO EVALUATE:
{dep_block}

Evaluate each dependency above. Return ONLY the strict JSON object with 'overall_risk', 'complexity', 'overall_explanation', 'complexity_explanation', and 'dependencies' matching the system prompt schema."""


TESTING_PROMPT_ANALYSIS_SYSTEM_PROMPT = """You are an expert Lead QA Automation Architect. \
Given an arbitrary natural language user testing prompt and a list of available Java classes/components in the software repository, analyze the prompt and dynamically extract the testing focus. \
You MUST return ONLY a single, strict JSON object and no commentary outside the JSON.

The JSON object must have exactly these keys:
- "testing_focus": string, a concise 1-2 sentence summary of what the user wants to test.
- "target_areas": array of short strings representing the functional areas identified (e.g. ["Authentication", "Password Validation", "Error Handling"]).
- "target_classes": array of class names or simple patterns from the repository matching the requested focus (e.g. ["LoginController", "UserService"]).
- "target_methods": array of method names or method patterns relevant to the user request.
- "priority": array of 2-5 high-priority scenario descriptions requested by the user.
- "scenarios": array of 2-6 specific positive and negative test scenarios to verify.
- "edge_cases": array of 1-4 boundary conditions, invalid inputs, or error handling scenarios.

Rules:
1. Dynamically understand whatever testing requirement the user provides.
2. Do not rely on hardcoded keywords; interpret the natural language intent.
3. Return only valid JSON."""


def build_testing_prompt_analysis_prompt(
    user_prompt: str | None = None,
    available_classes: list[dict[str, Any]] | None = None,
    project_context: str | None = None,
    prompt: str | None = None,
) -> str:
    actual_prompt = (user_prompt or prompt or "").strip()
    class_lines = []
    if available_classes:
        for c in available_classes[:30]:
            name = c.get("name") or c.get("class_name") or str(c)
            pkg = c.get("package_name") or ""
            methods = c.get("methods") or []
            method_str = f" (methods: {', '.join(methods[:5])})" if methods else ""
            class_lines.append(f"- {pkg}.{name}{method_str}".strip("."))
    class_block = "\n".join(class_lines) if class_lines else (project_context or "Repository classes available across project.")

    return f"""Analyze this user testing prompt and determine the dynamic testing focus for the Java project.

USER TESTING PROMPT:
"{actual_prompt}"

PROJECT REPOSITORY CONTEXT:
{class_block}

Respond with only the JSON object described in the system prompt."""


PROMPT_COVERAGE_EVALUATION_SYSTEM_PROMPT = """You are a Lead Quality Assurance Architect. \
Given the user's original testing prompt, the dynamic testing focus analysis, and the executed JUnit test suite results and coverage, evaluate whether the user's requested testing focus received sufficient coverage. \
You MUST return ONLY a single, strict JSON object and no commentary outside the JSON.

The JSON object must have exactly these keys:
- "user_prompt": string matching the original user testing prompt.
- "focus_matched": boolean (true if the requested testing focus received adequate attention and tests; false if key scenarios were missed).
- "coverage_assessment": string giving a clear 1-3 sentence evaluation of how well the executed unit tests met the user's request.
- "covered_scenarios": array of strings listing specific requested scenarios that were verified by the executed tests.
- "uncovered_scenarios": array of strings listing requested scenarios or edge cases that still lack test coverage.
- "recommendations": array of 1-3 actionable recommendations for improving test coverage in alignment with the user prompt."""


def build_prompt_coverage_evaluation_prompt(
    user_prompt: str | None = None,
    testing_focus_data: dict[str, Any] | None = None,
    executed_test_details: list[dict[str, Any]] | None = None,
    line_coverage_pct: float = 0.0,
    prompt: str | None = None,
    prompt_analysis: Any | None = None,
    executed_tests: list[dict[str, Any]] | None = None,
    analysis_summary: str | None = None,
    executed_tests_summary: str | None = None,
    coverage_pct: float = 0.0,
) -> str:
    actual_prompt = (user_prompt or prompt or "").strip()
    actual_coverage = line_coverage_pct or coverage_pct or 0.0
    details = executed_test_details or executed_tests or []

    test_lines = []
    for t in details[:30]:
        c_name = t.get("test_class") or "TestClass"
        m_name = t.get("test_method") or "testMethod"
        status = t.get("status") or "PASSED"
        test_lines.append(f"- [{status}] {c_name} :: {m_name}")
    test_block = "\n".join(test_lines) if test_lines else (executed_tests_summary or "No test execution details recorded.")

    focus_dict = testing_focus_data if isinstance(testing_focus_data, dict) else {}
    if not focus_dict and hasattr(prompt_analysis, "dict"):
        focus_dict = prompt_analysis.dict()
    elif not focus_dict and isinstance(prompt_analysis, dict):
        focus_dict = prompt_analysis

    focus_desc = focus_dict.get("testing_focus") or analysis_summary or "General Testing"
    scenarios = focus_dict.get("scenarios", [])

    return f"""Evaluate whether the executed JUnit test suite satisfied the user's testing prompt requirements.

USER ORIGINAL TESTING PROMPT:
"{actual_prompt}"

DYNAMIC TESTING FOCUS:
- Focus Summary: {focus_desc}
- Target Scenarios: {', '.join(scenarios) if scenarios else 'General scenarios'}

EXECUTED JUNIT TESTS & COVERAGE:
- Overall Line Coverage: {actual_coverage}%
- Executed Test Details:
{test_block}

Respond with only the JSON object described in the system prompt."""




