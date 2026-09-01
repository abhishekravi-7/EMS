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

Respond with ONLY the strict JSON object matching the system prompt schema."""


