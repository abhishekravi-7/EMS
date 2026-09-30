# Cycode quality checks

Cycode appears beside SonarQube and FOSSA in Migration > Quality Gates.
The integration runs secrets and SAST scans on `migrated-repo` before its
initial publication. It is advisory, matching the existing migration checks:
findings and scanner failures are reported without blocking publication.

## Enable

1. Deploy the updated frontend and rebuild the backend Docker image. The image
   installs Cycode CLI **3.24.1** in its own Python environment.
2. In Super Admin > Quality Checks, enable **Cycode** and save the configuration.
   Existing configurations remain unchanged until Cycode is explicitly enabled.
3. In User Settings > Quality Checks, save the Cycode **API / tenant URL**,
   **account/tenant identifier**, **API Token**, and scopes containing
   `secrets,sast`. The settings API masks the token on retrieval.
4. Select **Cycode** in the migration's Quality Gates area and start migration.
5. Open Results > Cycode Security to review each scan and its finding metadata.

For a backend running outside Docker, install `cycode==3.24.1` in an isolated
environment and set `CYCODE_CLI_COMMAND` to its executable path. The worker
requires network access to the configured Cycode API URL. The runner rejects
invalid URLs, missing tenants, and scopes that do not include both `secrets` and
`sast`. OIDC authentication is not configured by this UI.
`CYCODE_TIMEOUT_SECONDS` defaults to 600 per scan.

## Behavior

- The migration option is saved as `runCycode` and sent as `run_cycode`.
- Admin authorization is checked again on the backend. Disabled or missing
  authorization never launches the CLI, even if the request selects Cycode.
- Each invocation receives the owning user's credentials in its own environment.
  CLI home directories are temporary; credentials are not command arguments.
- Reports are included in existing authenticated migration summary/detail
  responses as `cycode_report`; no new public endpoint is introduced.
- Raw CLI output, source snippets and secret values are not stored in reports.
  The UI displays counts and at most 200 findings per scan, with severity,
  file and rule identifier. Review remediation in the Cycode platform.
- Missing credentials/CLI, timeouts, malformed output and partial scans produce
  **Unavailable**, never a passing result. Other selected scans still run.
- Dependency/license scanning remains with FOSSA in this implementation.

## Verification

Run `python -m pytest tests/unit/test_cycode_runner.py` from `APEX-Backend`.
The tests mock CLI execution and do not send source code to Cycode.
Run frontend `npm run typecheck` and `npm run build` separately.

A live tenant smoke test is still required after credentials are configured.
Test both a clean sample and an approved synthetic finding; confirm that
results appear on the migration report and no secret values appear in logs.
