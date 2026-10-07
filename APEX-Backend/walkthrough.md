# Pre-Migration Proposed Functional Test Baseline Execution & Startup Diagnostics

## Summary of Completed Changes

We have investigated, diagnosed, and resolved the source application startup and readiness failure in the Pre-Migration Proposed Functional Test baseline flow.

---

### Root Cause Analysis

1. **Port Parameter Discrepancy**:
   - `resolve_migrated_app_url(source_dir)` accurately extracted port `8081` from `application.properties`.
   - However, `MigratedAppLauncher.launch()` was called without passing the resolved `port`, which caused the launcher to fall back to default `port=8080` and command the JVM with `--server.port=8080`.
   - Meanwhile, `AppReadinessChecker.wait_for_ready()` probed `http://localhost:8081`, causing the check to timeout after 30 seconds.

2. **Unmonitored Subprocess Exit State**:
   - If the Java process exited early (due to database connection failures, port conflicts, or missing dependencies), `AppReadinessChecker` had no PID reference and continued to poll blindly for 30 seconds before reporting `NOT_READY`.

3. **Subprocess Stdout Pipe Buffering & Truncation**:
   - `proc.stdout.readline()` blocked synchronously on child process output, missing exception stack traces when the process exited or hung.

---

### Key Architectural & Implementation Enhancements

#### 1. Dynamic Port Binding & Synchronization
- Added `resolve_app_port(repo_dir, default_port=8080)` to scan `application.properties`, `application.yml`, and `application.yaml` for `server.port`.
- Both `launcher.launch(..., port=source_port)` and `AppReadinessChecker().wait_for_ready(source_app_url, ...)` now synchronize on the exact same port.
- System sets JVM flags `-Dserver.port={port}`, `--server.port={port}`, and environment variables `SERVER_PORT={port}` and `PORT={port}`.

#### 2. Continuous Background Log Capture & Deep Diagnostics (`app_launcher.py`)
- Background daemon thread drains `stdout` and `stderr` continuously to avoid pipe buffer deadlocks.
- Implemented `analyze_startup_failure(log_lines, exit_code)` to detect specific failure categories:
  - **Database Connection Failures**: `Cannot create PoolableConnection`, `Connection refused`, `Unknown database`, `Communications link failure`.
  - **Port Conflicts**: `Port ... is already in use`, `Address already in use`, `BindException`.
  - **Spring Context / Bean Errors**: `BeanCreationException`, `NoSuchBeanDefinitionException`, `APPLICATION FAILED TO START`.
  - **Runtime & Manifest Issues**: `no main manifest attribute`, `ClassNotFoundException`.

#### 3. Proactive Process Health Monitoring in Readiness Checker (`app_readiness_checker.py`)
- `wait_for_ready` accepts `process_pid`. On each 2-second iteration:
  - If the process terminates, it aborts the 30-second loop immediately, extracts the exit code and root error from stdout/stderr, and returns `ready=False, process_exited=True`.
  - Probes TCP port and HTTP endpoints (`/actuator/health`, `/health`, `/q/health`, `/api/health`, `/`). Any HTTP status `< 500` (e.g. 200, 302, 401, 403, 404) confirms the HTTP web server is alive.
  - Logs attempt progress: `[BASELINE] Readiness attempt 1/15...`.

#### 4. Clear Source vs. Migrated Terminology & Status Model (`proposed_test_service.py`)
- Separate statuses for `BUILD` (`SUCCESS` / `FAILED`), `STARTUP` (`STARTED` / `STARTUP_FAILED` / `RUNTIME_UNSUPPORTED`), and `READINESS` (`READY` / `NOT_READY` / `APPLICATION_UNAVAILABLE`).
- Strict execution rule: Baseline tests are executed against the live application **only** when `source_readiness_status == "READY"`.
- If unavailable, tests are marked `NOT_EXECUTED` with the exact diagnostic reason (never marked as a functional `FAILED`).

#### 5. Report Page Source Diagnostic Banner (`MigrationProposedTestSection.tsx`)
- Displays Source Application build status, startup status, readiness status, resolved URL, and baseline execution status.
- Renders diagnostic error banner with formatted exception details whenever startup or readiness fails.

---

### Verification Results

1. **Backend Unit Tests**:
   - `tests/unit/test_proposed_test_baseline_comparison.py`: 4/4 PASSED
   - Full test suite across `tests/unit/`: 30/30 PASSED cleanly in 26.28s
2. **Frontend Compilation**:
   - `npx tsc --noEmit`: 0 TypeScript errors.
