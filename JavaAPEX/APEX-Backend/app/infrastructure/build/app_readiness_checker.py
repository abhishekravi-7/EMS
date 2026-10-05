"""Application readiness checker for Java applications (Source and Migrated).

Verifies that:
1. The process is still actively running (fails immediately if process died).
2. The TCP port is open (socket connect).
3. An HTTP endpoint responds (< 500 status code: 200, 302, 401, 403, 404 all indicate a running server).

Does NOT hardcode ports — port is resolved from configuration.
"""

from __future__ import annotations

import logging
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

from app.infrastructure.build.app_launcher import MigratedAppLauncher, analyze_startup_failure

logger = logging.getLogger(__name__)

# Health endpoints to probe, in priority order
_HEALTH_ENDPOINTS = ["/actuator/health", "/health", "/q/health", "/api/health", "/"]

_DEFAULT_CHECK_TIMEOUT_S = 3.0
_DEFAULT_WAIT_TIMEOUT_S = 30.0
_DEFAULT_POLL_INTERVAL_S = 2.0


@dataclass
class AppReadinessResult:
    ready: bool
    port: int
    base_url: str
    http_status: int | None = None
    health_endpoint: str | None = None
    error: str | None = None
    attempts: int = 0
    elapsed_seconds: float = 0.0
    process_exited: bool = False


class AppReadinessChecker:
    """Checks whether an application is reachable and ready to serve requests."""

    def check(
        self,
        base_url: str,
        timeout_s: float = _DEFAULT_CHECK_TIMEOUT_S,
        process_pid: int | None = None,
        app_type_label: str = "Application",
    ) -> AppReadinessResult:
        """Perform a single readiness check against `base_url`."""
        parsed = urlparse(base_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8080

        start = time.time()

        # Step 1: Check process life if PID provided
        if process_pid:
            info = MigratedAppLauncher.get_process_info(process_pid)
            if info and not info["is_alive"]:
                exit_code = info["exit_code"]
                reason, _ = analyze_startup_failure(info["logs"], exit_code)
                return AppReadinessResult(
                    ready=False,
                    port=port,
                    base_url=base_url,
                    error=f"{app_type_label} process (PID={process_pid}) exited unexpectedly (exit code {exit_code}): {reason}",
                    attempts=1,
                    elapsed_seconds=round(time.time() - start, 2),
                    process_exited=True,
                )

            # Step 1b: Verify that the process PID (or its children) actually owns the listening port
            if not MigratedAppLauncher.is_port_owned_by_process(port, process_pid):
                owner_pids = MigratedAppLauncher.get_port_listening_pids(port)
                if owner_pids:
                    logger.warning(
                        "[APP] Port %d rejected: process PID %d does not own port (listening PIDs: %s)",
                        port, process_pid, owner_pids,
                    )
                    return AppReadinessResult(
                        ready=False,
                        port=port,
                        base_url=base_url,
                        error=f"Port {port} rejected: not owned by {app_type_label} process (PID={process_pid}, listening PIDs={owner_pids}).",
                        attempts=1,
                        elapsed_seconds=round(time.time() - start, 2),
                    )
                else:
                    return AppReadinessResult(
                        ready=False,
                        port=port,
                        base_url=base_url,
                        error=f"Port {port} is not listening yet ({app_type_label} PID={process_pid} is still initializing).",
                        attempts=1,
                        elapsed_seconds=round(time.time() - start, 2),
                    )

        # Step 2: TCP check
        if not self._tcp_reachable(host, port, timeout_s):
            return AppReadinessResult(
                ready=False,
                port=port,
                base_url=base_url,
                error=f"TCP port {port} is not accepting connections at {host}:{port}.",
                attempts=1,
                elapsed_seconds=round(time.time() - start, 2),
            )

        # Step 3: HTTP probe across standard endpoints
        rejection_reasons: list[str] = []
        for endpoint in _HEALTH_ENDPOINTS:
            url = base_url.rstrip("/") + endpoint
            status, err = self._http_get(url, timeout_s)
            if status is not None:
                elapsed = round(time.time() - start, 2)
                logger.info(
                    "%s at %s is READY (endpoint=%s, status=%d, elapsed=%.2fs)",
                    app_type_label, base_url, endpoint, status, elapsed,
                )
                return AppReadinessResult(
                    ready=True,
                    port=port,
                    base_url=base_url,
                    http_status=status,
                    health_endpoint=endpoint,
                    attempts=1,
                    elapsed_seconds=elapsed,
                )
            if err:
                rejection_reasons.append(f"{endpoint}: {err}")

        elapsed = round(time.time() - start, 2)
        rej_info = f" Rejections: {'; '.join(rejection_reasons)}." if rejection_reasons else ""
        return AppReadinessResult(
            ready=False,
            port=port,
            base_url=base_url,
            error=f"Port {port} is open but no valid application HTTP endpoint responded.{rej_info}",
            attempts=1,
            elapsed_seconds=elapsed,
        )

    def wait_for_ready(
        self,
        base_url: str,
        timeout_s: float = _DEFAULT_WAIT_TIMEOUT_S,
        poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S,
        process_pid: int | None = None,
        app_type_label: str = "Application",
        log_attempt_fn: Callable[[int, int], None] | None = None,
    ) -> AppReadinessResult:
        """Poll until the application is ready or `timeout_s` elapses or process exits."""
        start = time.time()
        attempts = 0
        max_attempts = max(1, int(timeout_s // poll_interval_s))

        parsed = urlparse(base_url)
        port = parsed.port or 8080

        while time.time() - start < timeout_s:
            attempts += 1
            if log_attempt_fn:
                log_attempt_fn(attempts, max_attempts)

            result = self.check(
                base_url,
                timeout_s=2.0,
                process_pid=process_pid,
                app_type_label=app_type_label,
            )
            result.attempts = attempts
            result.elapsed_seconds = round(time.time() - start, 2)

            if result.ready:
                return result

            if result.process_exited:
                # Process died — stop polling immediately without wasting remaining timeout
                logger.warning(
                    "%s (PID=%s) terminated early during readiness polling: %s",
                    app_type_label, process_pid, result.error,
                )
                return result

            time.sleep(poll_interval_s)

        elapsed = round(time.time() - start, 2)

        # Check final process logs for diagnostic
        extra_diag = ""
        if process_pid:
            info = MigratedAppLauncher.get_process_info(process_pid)
            if info:
                reason, _ = analyze_startup_failure(info["logs"], info["exit_code"])
                extra_diag = f" Last diagnostic: {reason}"

        logger.warning(
            "%s at %s NOT READY after %.1fs (%d attempts).%s",
            app_type_label, base_url, elapsed, attempts, extra_diag,
        )
        return AppReadinessResult(
            ready=False,
            port=port,
            base_url=base_url,
            error=(
                f"{app_type_label} at {base_url} did not become ready within "
                f"{timeout_s:.0f}s ({attempts} attempts).{extra_diag}"
            ),
            attempts=attempts,
            elapsed_seconds=elapsed,
        )

    @staticmethod
    def _tcp_reachable(host: str, port: int, timeout_s: float) -> bool:
        """Return True if a TCP connection to host:port succeeds within timeout."""
        try:
            with socket.create_connection((host, port), timeout=timeout_s):
                return True
        except (ConnectionRefusedError, OSError, TimeoutError):
            return False

    @staticmethod
    def _http_get(url: str, timeout_s: float) -> tuple[int | None, str | None]:
        """Perform a simple HTTP GET and return (status_code, error)."""
        try:
            req = urllib.request.Request(url, method="GET")  # noqa: S310
            req.add_header("Accept", "application/json, text/html, */*")
            req.add_header("User-Agent", "JavaAPEX-Readiness-Checker/1.0")
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
                server_hdr = resp.headers.get("Server", "")
                if "Microsoft-HTTPAPI" in server_hdr:
                    return None, f"Rejected: unrelated Windows service ({server_hdr})"
                return resp.status, None
        except urllib.error.HTTPError as e:
            server_hdr = e.headers.get("Server", "")
            if "Microsoft-HTTPAPI" in server_hdr:
                return None, f"Rejected: unrelated Windows service ({server_hdr})"
            www_auth = e.headers.get("WWW-Authenticate", "")
            if "NTLM" in www_auth:
                return None, "Rejected: NTLM authentication challenge from unrelated Windows service"
            content_len = e.headers.get("Content-Length", "")
            if content_len == "0" and e.code in (401, 403, 404, 500):
                return None, f"Rejected: HTTP {e.code} with empty body from unrelated service"
            # Valid application 4xx responses (e.g. Spring Security login redirect or custom error body)
            return e.code, None
        except urllib.error.URLError as e:
            return None, str(e.reason)
        except Exception as e:  # noqa: BLE001
            return None, str(e)
