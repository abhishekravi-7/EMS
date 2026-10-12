# JavaAPEX AI JaCoCo Coverage MCP Agent

This package is designed as the autonomous second stage after JavaAPEX
generates JUnit tests.

## What it does

1. Detects Maven/Gradle.
2. Detects Java version and JUnit generation style.
3. Runs JaCoCo.
4. Reads JaCoCo XML.
5. Finds uncovered classes, methods, lines and branches.
6. Sends targeted context to an LLM.
7. Allows the LLM to create/modify test files only.
8. Compiles tests.
9. Runs tests and JaCoCo.
10. Iterates until the configured coverage target is reached or the
   iteration budget is exhausted.
11. Never claims success without a real JaCoCo report.

## Install

```bash
pip install -r requirements.txt
```

## Java project requirements

Maven projects should have JaCoCo configured, for example through
`jacoco-maven-plugin`.

Gradle projects should apply the JaCoCo plugin and configure
`jacocoTestReport`.

## Integrating into JavaAPEX

The existing JavaAPEX `ChatLLM` should be wrapped by `JsonLLMAdapter`.

See:

`integration/javaapex_integration.py`

The desired call site is immediately after the existing JUnit generation
loop:

```python
agent_result = await run_coverage_stage(
    project_dir=project_dir,
    generator=self._generator,
    build_tool=req.build_tool,
    java_version=req.java_version,
)
```

## MCP server

Run:

```bash
python -m mcp_server.server
```

The MCP server exposes:

- `inspect_project`
- `run_jacoco`
- `get_coverage_gaps`
- `ensure_coverage`

For production JavaAPEX integration, inject the application's existing
LLM instead of using the placeholder `EnvLLM`.

## Important safety behavior

The agent refuses to modify files outside configured test roots.
Production code under `src/main` is not writable by the coverage agent.

## Recommended next hardening

For your production JavaAPEX deployment, add:

- Git checkpoint before each iteration
- automatic rollback when coverage regresses
- test failure repair sub-loop
- token-budgeted source retrieval
- Spring context failure classification
- per-module Maven/Gradle support
- JaCoCo XML/HTML artifact retention
- coverage delta reporting
- configurable branch/line thresholds
- timeout and process cancellation
- concurrent class analysis where safe
