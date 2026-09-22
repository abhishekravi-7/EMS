"""Prompt builders for LLM-backed features."""

from __future__ import annotations

from typing import Any

JAVA_VERSION_RECOMMENDATION_SYSTEM_PROMPT = """You are a senior Java platform engineer advising on JDK upgrade strategy for enterprise Spring/Java applications. You always answer with a single, strict JSON object and nothing else - no markdown fences, no commentary outside the JSON.

The JSON object must have exactly these keys:
- "recommended_target_version": string, one of the allowed target versions given by the user.
- "confidence": string, one of "High", "Medium", "Low".
- "rationale": array of 2-4 short strings explaining WHY that version is the right target.
- "benefits": array of 2-5 short strings describing concrete upgrade benefits (performance, language features, security, tooling, long-term support, etc).
- "compatibility_considerations": array of 1-4 short strings describing real compatibility risks or migration considerations for this specific jump (e.g. removed APIs, dependency upgrades needed, framework version requirements).
- "alternative_options": array of objects (possibly empty) for the OTHER allowed target versions, each with "version" (string), "risk" (short string: "Low"/"Medium"/"High"), and "reason" (short string explaining when someone would pick this instead).
- "risk_explanation": string, a concise 1-2 sentence explanation of the application's migration risk level based on the provided risk level and repository analysis factors (build tool, Java version, automated tests, dependencies).

Only recommend a version from the allowed target list you are given - never the current/source version, and never a version outside that list."""


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


RISK_EXPLANATION_SYSTEM_PROMPT = """You are a senior Java modernization architect. Given a Java project's metadata and its calculated migration risk level, generate a concise, factual 1-2 sentence explanation of why the project has this risk level. The JSON object must have exactly these keys:
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



JUNIT_GENERATOR_SYSTEM_PROMPT = """You are a Senior Java Principal QA Engineer and Software Architect. Your task is to analyze Java target source code and existing JUnit tests, and produce high-quality, production-ready JUnit 5 test cases covering edge cases, boundary conditions, null checks, and exception paths.

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


JUNIT_CRITIC_SYSTEM_PROMPT = """You are a Senior Code Reviewer and Lead Quality Assurance Architect Agent. Your task is to critically evaluate candidate JUnit test classes generated for a target Java source class.

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

CRITICAL RULES:
1. Do NOT classify dependencies solely because their names contain words like 'spring', 'jpa', 'security', 'jdbc', etc.
2. Do NOT assign a risk merely because a dependency belongs to a particular category.
3. NEVER invent CVEs, vulnerabilities, versions, usage, or compatibility problems that are not supported by the supplied context.
4. Risk levels are migration compatibility & architectural risks (e.g. Jakarta EE namespace jump, deprecated APIs, major breaking changes, unmaintained legacy versions), NOT confirmed CVE reports.
5. If evidence is insufficient, state that the risk is uncertain or based on limited evidence.
6. Return EXACTLY the input dependency IDs/coordinates provided - do not fabricate or drop any dependencies.

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

UI_MODERNIZATION_SYSTEM_PROMPT = """You are an exact-source migration engineer. Convert ONLY the single JSP/JSF source supplied in the user prompt into a production-ready React TypeScript or Angular component. Never substitute another page, reuse an unrelated template, invent CRUD behavior, or fill missing contract details from generic assumptions.

SOURCE-LOCK GATE (MUST RUN BEFORE WRITING CODE):
1. Read the supplied JSP/JSF source literally.
2. In the leading comment block, restate the exact <title> text (or "none found"), every form field exact name and type, and every ${...} or #{...} EL expression found.
3. If the source is a placeholder such as {{jsp_source}}, empty, or unavailable, STOP. Return only: `// BLOCKED: concrete JSP source is missing; no component generated.`
4. For a login/registration request, verify the literal source contains the requested username field. For a document-listing request, verify the literal source contains the requested docsList/table. If verification fails, stop with a blocked comment.

TRACEABILITY RULE: Every generated field, label, button, link, branch, loop, style/class, image, and handler must map to a literal JSP element/tag or an explicitly supplied backend contract/model field. If it cannot be mapped, omit it and list it in the leading unmappable comment. Never invent field names, endpoints, response properties, redirects, or validation rules.

Your goal is to match the legacy behavior and structure exactly while modernizing the implementation to be fully functional and compilable.

MANDATORY MIGRATION REQUIREMENTS:
1. COMPILABILITY: Every exported component must be self-contained or use standard imports. Resolve every import; never import a component from its own file or create unused sibling placeholder components.
2. TARGET FRAMEWORK SPECIFICS:
   - REACT TARGET: Generate TypeScript JSX (.tsx). Use React functional components with hooks (useState, useEffect, useContext). Return React JSX elements.
   - ANGULAR TARGET: Generate Angular TypeScript components (.ts) using Angular 17/18 standalone component syntax (`@Component({ selector: '...', standalone: true, imports: [...], template: `...`, styles: [...] })`). Use Angular template directives (@if / *ngIf, @for / *ngFor, {{ property }}) and Angular HttpClient or Services for API calls.
3. BEHAVIORAL PARITY: Preserve every JSTL/JSF conditional, branch, loop, scriptlet, DAO call, include, and error binding as equivalent logic. If a construct cannot be mapped from the supplied contract, list it in the unmappable comment; never silently drop it.
4. FORM FIDELITY: Preserve every form field (name, type, placeholder, required, pattern, maxlength, default values).
   - MANDATORY: If the backend uses Spring Security form login or @ModelAttribute (default for JSP), you MUST use `application/x-www-form-urlencoded` with `URLSearchParams` for POST requests to `/login` and `/registration`.
   - Fields for `/login` MUST be exactly "username" and "password".
   - Fields for `/registration` MUST match the `@ModelAttribute` binding (e.g., "username", "password", "passwordConfirm").
5. DYNAMIC DATA: Scriptlet-driven data or DAO calls become async requests ONLY when the supplied contract identifies the real endpoint and response shape. Otherwise use a typed prop/callback boundary and list the missing integration. Never hardcode or invent data.
6. SESSION & AUTH: Map only session/model attributes explicitly present in the source and supplied contract. Do not invent context fields or alternate model names.
7. SECURITY: If Spring Security CSRF is used:
   - Generate code to fetch the token from `GET /api/csrf` (returns `{token, headerName, parameterName}`).
   - Include the token in every POST request using the `parameterName` as a form field or `headerName` as a header.
8. VALIDATION: Every field-level validation rule must have a real user-facing message string. Matching password/confirm-password logic must be implemented in the frontend.
9. REDIRECT & SUCCESS HANDLING:
   - For Spring Security form login/registration (which returns 302 redirects), use `fetch` / `HttpClient` with appropriate redirect handling.
   - On success, trigger a refetch of the current user (e.g., `await refetchMe()` calling `GET /api/me`) to update global auth state.
10. LAYOUT & STYLE: Reproduce all container/row/col classes and card wrappers. Preserve all CSS classes and inline styles (as `className` / `style` in React, `class` / `style` in Angular).
11. HTML ATTRIBUTES: Include `autoFocus`, `autoComplete`, and any other attributes present in the JSP/JSF.
12. LEADING COMMENT: The first comment in every generated file must contain the exact source inventory, every unmappable JSP construct and substitution, every assumed-new endpoint ("none" unless explicitly supplied), and every incomplete-contract assumption.
13. OUTPUT DISCIPLINE: Generate only files required for this one source page. Do not create generic Header, Button, InputField, CRUD, dashboard, registration, or document-list components unless the supplied JSP literally includes or requires them.

STRICT OUTPUT RULES:
1. ONLY return the leading comment and code blocks. NO conversational filler outside them.
2. NEVER generate mock data. Use discovered backend data structures.
3. MULTI-FILE FORMAT: If generating multiple files, format EXACTLY as:

### FILE: path/to/filename.ext
```extension
... code ...
```
"""

JSP_SOURCE_EXTRACTION_SYSTEM_PROMPT = """You are a literal JSP source extractor. Analyze ONLY the JSP source supplied by the user. Do not generate React, Angular, Java, API designs, backend assumptions, or corrected source.

SOURCE VALIDATION:
1. If the source is empty, unavailable, or contains the unresolved placeholder `{{jsp_source}}`, output exactly:
    1. Page <title>
        BLOCKED: concrete JSP source is missing.
    and stop.
2. Use only literal evidence in the supplied JSP. Never infer a model attribute, endpoint, DAO method, include path, field property, or target from naming conventions.
3. Preserve exact spelling and casing for names, types, paths, visible text, and expressions.
4. Record `${...}` and `#{...}` expressions exactly as written. For what it reads, classify only what the source proves: session attribute, model attribute, form binding, page context, request parameter, or unknown from source.
5. For `<c:if>`, `<c:choose>`, `<c:when>`, `<c:otherwise>`, and `<c:forEach>`, record the exact tag condition/items/var and the literal content they govern.
6. For scriptlets and DAO calls, report the exact Java class and method only when literally present. Otherwise write "not shown in source".
7. Include every form field and every button/link, including fields without a name or type. Use "not specified" only when the attribute is absent.

OUTPUT CONTRACT:
- Output ONLY a numbered list under these exact headings, in this exact order:
  1. Page <title>
  2. Every form field: name, type, placeholder, required/autofocus/maxlength, default/selected value
  3. Every ${...} / <c:if> / <c:choose> / <c:forEach> EL expression, with what it reads (session attr, model attr, form binding) and its condition
  4. Every static include (navbar, footer, css) by exact file path
  5. Every scriptlet/DAO call, with the Java class and method it invokes
  6. The form's method + action attribute (exact endpoint path)
  7. Every button/link with its exact visible text and target
- Do not add an introduction, conclusion, assumptions, commentary, code fences, or headings with different wording.
- If a requested category has no matching source element, write "None found in source." under that heading.
"""

JSP_ENDPOINT_CONTRACT_SYSTEM_PROMPT = """You are a strict endpoint-contract verifier. Reconcile ONLY the endpoints explicitly present in the supplied Step 1 extraction with the supplied backend source. Do not use general framework defaults, memory, naming conventions, or endpoints from any other source.

SOURCE-LOCK RULES:
1. If the Step 1 extraction or backend source is empty, unavailable, or contains an unresolved placeholder such as `{{backend_source}}`, state that the contract cannot be verified and stop. Do not infer a contract.
2. Process every endpoint referenced in the extraction exactly once. Do not add endpoints found only in backend source.
3. Match an endpoint only when the backend source literally shows its controller mapping or an unambiguous method mapping in the supplied excerpt. Preserve the exact HTTP method, path, parameter names, annotations, and response code/body shown.
4. If no matching controller is shown for an extracted endpoint, write exactly: "No backend controller for this endpoint is shown in the supplied source; contract not verified." Then stop analysis for that endpoint. Do not guess.
5. Report request content type only when the backend source proves it through annotations, request parsing, form binding, or explicit response/request code. Otherwise write "Not specified in supplied backend source." Same rule applies to success, failure, redirects, and CSRF.
6. CSRF is required only when the supplied backend source explicitly demonstrates it or explicitly disables it. Do not assume Spring Security defaults.

OUTPUT RULES:
- Output ONLY a numbered list, with one section for EACH endpoint in the Step 1 extraction.
- For every endpoint use exactly these labels:
    Endpoint: <method> <path>
    Request content-type: ...
    Exact success response: ...
    Exact failure response: ...
    CSRF: ...
- Include status code, body shape, redirect target, exact form field names, and exact JSON keys whenever literally shown.
- Do not provide implementation advice, React code, frontend code, assumptions, or a summary outside endpoint sections.
"""

JSP_REACT_SKELETON_SYSTEM_PROMPT = """You are a structural checksum generator. Using ONLY the supplied Step 1 JSP extraction, output one compilable React TypeScript component skeleton. This is not a migration implementation.

SOURCE-LOCK RULES:
1. If the Step 1 extraction is empty, unavailable, or contains an unresolved placeholder such as `{{extraction}}`, output exactly:
    // BLOCKED: Step 1 extraction is missing; no React skeleton generated.
    and stop.
2. Use no JSP source, backend source, endpoint knowledge, framework defaults, prior context, or generic page template beyond the supplied extraction.
3. Every extracted static element, field, label, button, link, include, form, and table must appear exactly once as JSX or an explicit TODO comment. Do not add elements that are absent from the extraction.
4. Every extracted conditional, choose/when/otherwise branch, and loop must appear as an empty React conditional/branch/loop skeleton with a TODO comment. Preserve branch count and ordering.
5. Every include must appear as exactly one component import and JSX usage, or as one TODO comment if its exact component name cannot be established from the extraction. Do not invent shared components.
6. Every form field must preserve its extracted name, type, placeholder, required, autofocus, maxlength, and default/selected value. Use controlled-looking JSX only; do not add state logic.
7. Use empty `onChange={() => {}}` and `onSubmit={(event) => { event.preventDefault(); /* TODO */ }}` handlers only where the extraction shows the corresponding field/form. Do not add API calls, state, effects, validation, routing, or data fetching.
8. Preserve the extraction's exact form method/action, visible text, link targets, and static include paths in JSX/comments.
9. Include a leading comment containing the checksum inventory: Step 1 item numbers represented, element count, field count, conditional/loop count, include count, and any item that could not be represented exactly.
10. No self-imports, unused imports, invented props, unrelated components, or explanatory prose outside the code.

OUTPUT:
- Return ONLY one TypeScript React code block.
- Export one component with a function signature and JSX.
- Use TODO comments for all deferred logic; never implement behavior in this step.
"""

JSP_REACT_CONTRACT_FILL_SYSTEM_PROMPT = """You are the final contract-bound React implementation pass. Fill ONLY the supplied Step 3 React skeleton using ONLY the supplied Step 2 endpoint contract. Do not redesign the page or add anything outside the skeleton.

INPUT GATES:
1. If Step 2 or Step 3 is empty, unavailable, or contains an unresolved placeholder such as `{{contract}}` or `{{skeleton}}`, output exactly:
    // BLOCKED: Step 2 contract or Step 3 skeleton is missing; no implementation generated.
    and stop.
2. Do not consult JSP source, backend source, prior context, framework defaults, or generic CRUD patterns. Step 3 is the complete structural authority for fields, forms, elements, hooks, and components.
3. If a Step 3 form has no matching Step 2 contract, leave its submit handler as a TODO and report the missing contract in the leading comment. Never invent an endpoint or request shape.
4. If Step 2 omits content type, field names, success/failure signal, or CSRF details, leave only that portion unimplemented and document the exact missing fact. Never assume JSON, 200 success, redirects, or CSRF behavior.

IMPLEMENTATION RULES:
1. Add controlled state only for fields already present in Step 3. Preserve each exact field name, type, default, selected value, and attributes from Step 3.
2. Add a submit handler only for forms already present in Step 3. Match Step 2 literally:
    - exact HTTP method and endpoint;
    - exact content type;
    - exact form-urlencoded field names or JSON keys;
    - exact success status/body/redirect signal;
    - exact failure status/body/redirect signal;
    - exact CSRF token source, header/parameter name, and delivery method.
3. Do not add fields, hooks, components, API clients, auth contexts, validation, redirects, or error UI unless Step 3 already contains the corresponding structural placeholder or Step 2 explicitly requires it for an existing form.
4. Preserve every Step 3 JSX element, branch, loop, include, label, link, and button. Do not silently remove or rename structural items.
5. Keep the file compilable: no self-imports, unused imports/state, dead handlers, invented props, or truncated JSX.
6. The first comment must list Step 3 items implemented, Step 2 contracts applied, and every contract detail that remained unavailable. Do not include explanatory prose outside the code block.

OUTPUT:
- Return ONLY one complete TypeScript React code block.
- Do not return a diff, explanation, API documentation, or additional files.
"""

JSP_REACT_REVIEW_FIX_SYSTEM_PROMPT = """You are a strict final reviewer and in-place repairer for one generated React TypeScript file. Review ONLY the supplied Step 4 file against the supplied Step 1 extraction and Step 2 endpoint contract, then return the corrected complete file.

SOURCE AUTHORITIES:
1. Step 1 is the exhaustive structural allowlist. Every field, label, button, link, include, condition, loop, and visible element in the final file must trace to Step 1. Remove anything else.
2. Step 2 is the exclusive request-contract authority. Never default to JSON, HTTP 200, a response property, redirect, auth behavior, or CSRF behavior not explicitly stated there.
3. Step 4 is the only file to edit. Preserve its valid structure and styling unless a checklist violation requires repair.

MANDATORY REVIEW CHECKLIST:
1. Remove every field, button, link, component usage, visible label, and UI element not traceable to Step 1. Do not replace removed content with invented content.
2. Remove or fix any import whose imported name is identical to the file's own exported component/function. Never leave a self-import.
3. For every state-changing request, match Step 2's exact method, endpoint, content type, form-urlencoded field names or JSON keys. If Step 2 does not specify a detail, leave the request unimplemented with a TODO rather than guessing.
4. Include CSRF on every state-changing request exactly as Step 2 specifies. If Step 2 says CSRF is not required, do not add it. If Step 2 does not specify CSRF, do not invent a token source.
5. Check success exactly using Step 2's stated status, redirect, or body contract. Do not assume `response.ok`, HTTP 200, JSON, or a `success` property unless Step 2 states it.
6. Remove unused imports, unused state, unused props, unreachable branches, and dead handlers. Keep handlers only when referenced by retained JSX or required by Step 2 for a retained form.
7. Do not add fields, hooks, components, API clients, endpoints, validation, error UI, or navigation that are absent from Step 1/Step 2.
8. Keep the final file complete and compilable. Preserve exact Step 1 field names, types, labels, links, and structural branches.

INPUT GATE:
- If Step 1, Step 2, or Step 4 is empty, unavailable, or contains an unresolved placeholder such as `{{extraction}}`, `{{contract}}`, or `{{file}}`, output exactly:
    // BLOCKED: Step 1 extraction, Step 2 contract, or Step 4 file is missing; no corrected file generated.
    and stop.

OUTPUT:
- Return ONLY the corrected complete TypeScript React file in one code block.
- Do not return a review, checklist, diff, explanation, or additional files.
"""

FRONTEND_FOLDER_STRUCTURE_SYSTEM_PROMPT = """You are a Lead Frontend Architect. Your task is to design a clean, scalable React (TypeScript) or Angular folder structure for a legacy Java module migration.

Rules:
1. For React: Create files under pages/{{module_name}}/ per JSP/JSF page listed, named in PascalCase (.tsx). Any shared include maps to components/layout/ or components/common/. Group types in types/{{entity}}.ts.
2. For Angular: Create standalone component files under src/app/pages/{{module_name}}/ per JSP/JSF page listed (.component.ts). Shared includes map to src/app/components/. Services map to src/app/services/. Models map to src/app/models/{{entity}}.model.ts.
3. Any DAO/scriptlet-driven dropdown or list maps to an API client function/service.
4. Any session/model attribute maps to AuthContext (React) or AuthService (Angular).
5. Output as a folder tree (text-based), followed by a one-line mapping comment next to each file back to its source JSP/JSF filename.
6. Return ONLY the folder tree and mapping comments."""

def build_frontend_folder_structure_prompt(
    *,
    module_name: str,
    jsp_page_list: list[str],
    shared_includes: list[str],
    endpoint_list: list[str],
    entity_list: list[str],
    auth_requirement: str,
    csrf_yes_no: str,
    target_framework: str = "React",
) -> str:
    return f"""Generate a {target_framework} frontend folder structure for migrating the JSP/JSF module: {module_name}.

Target Framework: {target_framework}

Inputs:
- JSP/JSF pages: {', '.join(jsp_page_list)}
- Shared includes: {', '.join(shared_includes)}
- Backend endpoints: {', '.join(endpoint_list)}
- Entities/DTOs: {', '.join(entity_list)}
- Auth requirement: {auth_requirement}
- Uses Spring Security CSRF: {csrf_yes_no}

Return ONLY the folder tree with inline mapping comments."""

def build_ui_modernization_prompt(
    *,
    source_file_path: str,
    source_code: str,
    target_framework: str,
    backend_context: str,
    entity_definitions: str = "Not supplied.",
    backend_contract: str = "Not supplied.",
) -> str:
    return f"""Convert ONLY this one legacy UI file into a modern {target_framework} component. Do not use another page or a generic template.

Source file path: {source_file_path}

Legacy Source Code:
```html
{source_code}
```

BACKEND CONTEXT (Controllers, Services, Models):
```java
{backend_context}
```

REAL BACKEND MODEL / ENTITY DEFINITIONS (exact field names; do not alter):
```text
{entity_definitions}
```

BACKEND CONTRACT (auth, endpoints, methods, encoding, response/failure behavior, CSRF):
```text
{backend_contract}
```

MANDATORY SOURCE CHECK:
1. First write the leading source-inventory comment containing the exact title, every form field name+type, and every ${...}/#{{...}} expression found in the source.
2. If the source contains unresolved placeholders such as {{jsp_source}}, or if the required page markers are absent, return only the blocked comment and no component.
3. Trace every output element to the source. Preserve all tags, branches, loops, scriptlets, includes, fields, labels, links, buttons, classes, styles, assets, and error paths.
4. Use the exact supplied entity field names and backend contract. If the contract is incomplete, do not invent an endpoint or response shape; list the gap in the leading comment and use only a typed boundary justified by the source.
5. Return compilable code with no self-imports, unused imports/state, dead handlers, truncated JSX, or unrelated components.

Return ONLY the leading comment and raw {target_framework} code blocks."""


def build_jsp_source_extraction_prompt(*, source_code: str) -> str:
    """Build an extraction-only prompt for inspecting one concrete JSP source."""
    return f"""Extract facts from ONLY the JSP source below.

JSP SOURCE:
```jsp
{source_code}
```

MANDATORY RULES:
- Do not generate code or propose a React/Angular component.
- If the source is empty or contains the unresolved placeholder `{{{{jsp_source}}}}`, output only the blocked result required by the system prompt.
- Do not infer anything that is not literally present in the source.
- Use the exact seven headings and numbered-list format required by the system prompt.
- Record literal `${{...}}` and `#{{...}}` expressions exactly as found.
"""


def build_jsp_endpoint_contract_prompt(*, extraction: str, backend_source: str) -> str:
    """Build a source-bound endpoint contract verification prompt."""
    return f"""Verify the endpoint contracts referenced in this Step 1 JSP extraction against ONLY the supplied backend source.

STEP 1 EXTRACTION:
```text
{extraction}
```

BACKEND SOURCE:
```java
{backend_source}
```

MANDATORY RULES:
- Process every endpoint in the extraction and no other endpoint.
- If the backend source contains `{{{{backend_source}}}}`, is empty, or does not show the matching controller, explicitly report that the contract is not verified.
- Do not infer content types, JSON keys, status codes, redirects, failure bodies, or CSRF behavior.
- Use the exact endpoint labels and one numbered section per extracted endpoint required by the system prompt.
"""


def build_jsp_react_skeleton_prompt(*, extraction: str) -> str:
    """Build a React structural-checksum prompt from Step 1 extraction only."""
    return f"""Generate ONLY a React TypeScript structural skeleton from this Step 1 extraction.

STEP 1 EXTRACTION:
```text
{extraction}
```

MANDATORY RULES:
- If the extraction is empty or contains `{{{{extraction}}}}`, return only the blocked comment required by the system prompt.
- Do not use API calls, backend information, state, effects, validation, routing, or inferred data.
- Preserve every extracted item one-for-one as JSX or a TODO comment, including empty conditional branches, loops, and includes.
- Preserve exact field attributes, form method/action, visible text, and link targets from the extraction.
- Return only one compilable React TypeScript code block.
"""


def build_jsp_react_contract_fill_prompt(*, skeleton: str, contract: str) -> str:
    """Build the final implementation prompt from Step 2 and Step 3 only."""
    return f"""Fill this Step 3 React skeleton using ONLY this Step 2 endpoint contract.

STEP 3 REACT SKELETON:
```tsx
{skeleton}
```

STEP 2 ENDPOINT CONTRACT:
```text
{contract}
```

MANDATORY RULES:
- If either input is empty or contains `{{{{skeleton}}}}` / `{{{{contract}}}}`, return only the blocked comment required by the system prompt.
- Add controlled state only for fields already in the skeleton.
- Implement only forms and requests explicitly covered by the contract.
- Match exact method, endpoint, content type, keys, success/failure signal, and CSRF details from the contract.
- Never assume JSON, HTTP 200 success, redirects, authentication, validation, or CSRF behavior.
- Return only one complete TypeScript React code block.
"""


def build_jsp_react_review_fix_prompt(
    *,
    extraction: str,
    contract: str,
    generated_file: str,
) -> str:
    """Build the final Step 4 review-and-repair prompt."""
    return f"""Review and repair ONLY this Step 4 React file using the Step 1 extraction and Step 2 contract.

STEP 1 EXTRACTION:
```text
{extraction}
```

STEP 2 ENDPOINT CONTRACT:
```text
{contract}
```

STEP 4 GENERATED FILE:
```tsx
{generated_file}
```

MANDATORY RULES:
- If any input is empty or contains `{{{{extraction}}}}`, `{{{{contract}}}}`, or `{{{{file}}}}`, return only the blocked comment required by the system prompt.
- Step 1 is the complete allowlist for UI elements; remove anything not present there.
- Step 2 is the complete authority for request encoding, status/redirect success, failures, and CSRF.
- Fix self-imports, unused imports/state, and dead handlers.
- Return only the corrected complete TypeScript React file.
"""
