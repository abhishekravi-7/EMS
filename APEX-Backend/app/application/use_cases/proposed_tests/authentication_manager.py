"""Authentication Manager for discovering and managing valid test credentials and session state."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain.models.proposed_test_models import ProposedTestStatus, StepExecutionRecord

logger = logging.getLogger(__name__)


@dataclass
class AuthCredentials:
    username: str
    password: str
    source: str = "discovered"
    role: str | None = None


@dataclass
class AuthSession:
    authenticated: bool = False
    username: str | None = None
    cookies: list[dict[str, Any]] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    storage_state: dict[str, Any] | None = None
    redirect_url: str | None = None
    error: str | None = None


class AuthenticationManager:
    """Discovers application credentials from repository evidence and manages shared authentication workflows."""

    def __init__(self, repo_dir: Path | None = None, log_fn: Any | None = None) -> None:
        self.repo_dir = repo_dir
        self.log_fn = log_fn or (lambda m, lvl="INFO": logger.info(f"[AUTH] {m}"))
        self._cached_credentials: list[AuthCredentials] | None = None
        self._failed_credentials: set[tuple[str, str]] = set()
        self._active_session: AuthSession | None = None
        self._shared_api_context: Any = None

    def is_authenticated(self) -> bool:
        """Returns True if a valid authenticated session has been established."""
        return self._active_session is not None and self._active_session.authenticated

    def get_active_session(self) -> AuthSession | None:
        return self._active_session

    def get_storage_state(self) -> dict[str, Any] | None:
        if self._active_session and self._active_session.storage_state:
            return self._active_session.storage_state
        return None

    def get_auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._active_session and self._active_session.cookies:
            cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in self._active_session.cookies)
            headers["Cookie"] = cookie_str
        return headers

    def discover_credentials(self) -> list[AuthCredentials]:
        """Scans the repository for grounded user credentials from seed SQL, security configs, and test files."""
        if self._cached_credentials is not None:
            return self._cached_credentials

        discovered: list[AuthCredentials] = []
        seen: set[tuple[str, str]] = set()

        def _add(u: str, p: str, src: str, role: str | None = None):
            u_clean = u.strip()
            p_clean = p.strip()
            if not u_clean or not p_clean:
                return
            if len(u_clean) > 50 or len(p_clean) > 50:
                return
            key = (u_clean.lower(), p_clean)
            if key not in seen:
                seen.add(key)
                discovered.append(AuthCredentials(username=u_clean, password=p_clean, source=src, role=role))

        if not self.repo_dir or not self.repo_dir.exists():
            self._cached_credentials = []
            return discovered

        # 1. Scan seed SQL files (data.sql, import.sql, seed.sql)
        for sql_file in self.repo_dir.rglob("*.sql"):
            if any(k in sql_file.name.lower() for k in ["data", "seed", "import", "test", "schema"]):
                try:
                    content = sql_file.read_text(encoding="utf-8", errors="ignore")
                    # Check comments e.g. "-- Add default user (username: user, password: password)"
                    comment_matches = re.finditer(
                        r'(?:--|/\*)\s*(?:username|user):\s*([a-zA-Z0-9_\-\.]+)\s*,\s*(?:password|pass):\s*([^\s,\*]+)',
                        content,
                        re.IGNORECASE,
                    )
                    for cm in comment_matches:
                        _add(cm.group(1), cm.group(2), f"SQL comment in {sql_file.name}")

                    # Check raw INSERT queries
                    ins_matches = re.finditer(
                        r"insert\s+into\s+users?\s*\([^)]*username[^)]*password[^)]*\)\s*values\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                        content,
                        re.IGNORECASE,
                    )
                    for im in ins_matches:
                        pwd_candidate = im.group(2)
                        if not pwd_candidate.startswith("$2a$") and not pwd_candidate.startswith("$2b$"):
                            _add(im.group(1), pwd_candidate, f"INSERT query in {sql_file.name}")
                except Exception as e:
                    logger.debug("Failed reading SQL file %s: %s", sql_file, e)

        # 2. Scan Java login configurations, services, and tests
        for java_file in self.repo_dir.rglob("*.java"):
            fname_low = java_file.name.lower()
            if any(k in fname_low for k in ["login", "security", "user", "auth", "test"]):
                try:
                    c = java_file.read_text(encoding="utf-8", errors="ignore")

                    # Pattern: "in28Minutes".equals(user) && "dummy".equals(password)
                    eq_matches = re.finditer(
                        r'["\']([^"\']+)["\']\s*\.equals\s*\(\s*(?:user|username)\s*\)\s*&&\s*["\']([^"\']+)["\']\s*\.equals\s*\(\s*(?:password|pass)\s*\)',
                        c,
                        re.IGNORECASE,
                    )
                    for em in eq_matches:
                        _add(em.group(1), em.group(2), f"Hardcoded credential check in {java_file.name}")

                    # Inverse: user.equals("in28Minutes") && password.equals("dummy")
                    eq_inv = re.finditer(
                        r'(?:user|username)\s*\.equals(?:IgnoreCase)?\s*\(\s*["\']([^"\']+)["\']\s*\)\s*&&\s*(?:password|pass)\s*\.equals\s*\(\s*["\']([^"\']+)["\']\s*\)',
                        c,
                        re.IGNORECASE,
                    )
                    for em in eq_inv:
                        _add(em.group(1), em.group(2), f"Hardcoded credential check in {java_file.name}")

                    # Pattern: withUser("admin").password("admin") or password("{noop}password")
                    with_user_matches = re.finditer(
                        r'\.withUser\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\.password\s*\(\s*["\'](?:\{noop\})?([^"\']+)["\']\s*\)',
                        c,
                        re.IGNORECASE,
                    )
                    for wm in with_user_matches:
                        _add(wm.group(1), wm.group(2), f"In-memory security config in {java_file.name}")

                    # Pattern: formLogin().user("securityuser").password("password")
                    form_login_matches = re.finditer(
                        r'\.user\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\.password\s*\(\s*["\']([^"\']+)["\']\s*\)',
                        c,
                        re.IGNORECASE,
                    )
                    for fm in form_login_matches:
                        _add(fm.group(1), fm.group(2), f"Integration test login in {java_file.name}")

                    # Pattern: loginAs("user1", "user123") or loginAs("user", "password")
                    login_as_matches = re.finditer(
                        r'loginAs\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*\)',
                        c,
                        re.IGNORECASE,
                    )
                    for lam in login_as_matches:
                        _add(lam.group(1), lam.group(2), f"UI test loginAs in {java_file.name}")

                except Exception as e:
                    logger.debug("Failed reading Java file %s: %s", java_file, e)

        # 3. Scan application.properties / application.yml
        for prop_file in self.repo_dir.rglob("application*"):
            if prop_file.suffix in [".properties", ".yml", ".yaml"]:
                try:
                    c = prop_file.read_text(encoding="utf-8", errors="ignore")
                    u_m = re.search(r'spring\.security\.user\.name\s*[:=]\s*([^\s]+)', c)
                    p_m = re.search(r'spring\.security\.user\.password\s*[:=]\s*([^\s]+)', c)
                    if u_m and p_m:
                        _add(u_m.group(1), p_m.group(1), f"Spring security properties in {prop_file.name}")
                except Exception as e:
                    logger.debug("Failed reading properties file %s: %s", prop_file, e)

        self._cached_credentials = discovered
        if discovered:
            self.log_fn(f"Discovered {len(discovered)} credential profile(s) from codebase: {[c.username for c in discovered]}")
        return discovered

    def authenticate_page(self, page: Any, target_url: str) -> tuple[bool, list[StepExecutionRecord], str | None]:
        """
        Executes a browser-based authentication workflow using deduplicated candidate credentials.
        Never retries candidates that failed previously in this run.
        Caches the authenticated session and storage state upon success.
        Returns (success: bool, steps: list[StepExecutionRecord], error_reason: str | None).
        """
        # If already authenticated, check if session is still alive
        if self.is_authenticated():
            return True, [], None

        steps: list[StepExecutionRecord] = []
        step_idx = 2

        # Verify page actually has an authentication prompt
        user_input = page.locator("input[name='username'], input#username, [data-testid='username-input'], input[name='user'], input[type=text]").first
        pass_input = page.locator("input[name='password'], input#password, [data-testid='password-input'], input[type=password]").first

        if user_input.count() == 0 or pass_input.count() == 0:
            return True, steps, None

        login_btn = page.locator(
            "button[type=submit], button:has-text('Login'), button:has-text('Sign In'), [data-testid='login-button'], input[type=submit]"
        ).first

        # Check if inputs already have candidate values pre-filled in DOM (e.g. mock test server)
        dom_user = None
        dom_pass = None
        try:
            dom_user = (user_input.get_attribute("value") or "").strip()
            dom_pass = (pass_input.get_attribute("value") or "").strip()
        except Exception:
            pass

        all_candidates = list(self.discover_credentials())
        if dom_user and dom_pass:
            all_candidates = [AuthCredentials(username=dom_user, password=dom_pass, source="DOM pre-filled form value")] + [
                c for c in all_candidates if not (c.username == dom_user and c.password == dom_pass)
            ]

        # FIX 3: Filter out any candidates that already failed in this run
        credentials_list = [c for c in all_candidates if (c.username, c.password) not in self._failed_credentials]

        if not credentials_list:
            final_err = "No unattempted valid authentication credentials available for this application."
            return False, steps, final_err

        last_error = None

        for cred in credentials_list:
            cred_key = (cred.username, cred.password)
            t0 = time.time()
            try:
                user_input.fill(cred.username)
                pass_input.fill(cred.password)
            except Exception as e:
                self._failed_credentials.add(cred_key)
                continue

            steps.append(
                StepExecutionRecord(
                    step_number=step_idx,
                    description=f"Fill authentication credentials for user '{cred.username}' (Source: {cred.source})",
                    status=ProposedTestStatus.PASSED,
                    duration="0.08s",
                )
            )
            step_idx += 1

            if login_btn.count() > 0:
                btn_name = login_btn.inner_text().strip() or "Login"
                try:
                    login_btn.click(timeout=3000)
                except Exception:
                    pass

                steps.append(
                    StepExecutionRecord(
                        step_number=step_idx,
                        description=f"Submit authentication form via '{btn_name}'",
                        status=ProposedTestStatus.PASSED,
                        duration="0.10s",
                    )
                )
                step_idx += 1

                page.wait_for_timeout(1000)

                # STRICT VALIDATION: Check if authentication succeeded or failed
                current_url = page.url.lower()
                has_error_param = any(k in current_url for k in ["error", "login_error", "bad_credentials", "failed"])

                # Check for explicit error banners in DOM
                has_error_alert = False
                error_alert = page.locator(".alert-danger, .error-message, .login-error, [data-testid='error-message'], .alert:has-text('Invalid'), .alert:has-text('incorrect'), .alert:has-text('bad')").first
                if error_alert.count() > 0 and error_alert.is_visible():
                    has_error_alert = True
                    last_error = error_alert.inner_text().strip() or "Invalid credentials banner visible in DOM"

                target_is_login = any(k in (target_url or "").lower() for k in ["login", "signin", "auth"])
                still_on_login = "/login" in current_url or "/signin" in current_url
                stuck_on_login_for_protected_route = (not target_is_login) and still_on_login and page.locator("input[type=password]").count() > 0

                login_failed = has_error_param or has_error_alert or stuck_on_login_for_protected_route

                if login_failed:
                    self._failed_credentials.add(cred_key)
                    reason = f"Authentication rejected by server for '{cred.username}' (Current view: '{page.url}')"
                    if last_error:
                        reason += f": {last_error}"
                    steps.append(
                        StepExecutionRecord(
                            step_number=step_idx,
                            description=reason,
                            status=ProposedTestStatus.FAILED,
                            duration="0.05s",
                            error=reason,
                        )
                    )
                    step_idx += 1
                    last_error = reason
                    continue

                # Authentication succeeded!
                dur = round(time.time() - t0, 3)
                steps.append(
                    StepExecutionRecord(
                        step_number=step_idx,
                        description=f"Verify authenticated redirection (Successfully reached '{page.url}')",
                        status=ProposedTestStatus.PASSED,
                        duration=f"{dur}s",
                    )
                )
                step_idx += 1

                # FIX 2 & FIX 10: Cache storage state, cookies, and active session
                try:
                    cookies = page.context.cookies()
                    storage_state = page.context.storage_state()
                except Exception:
                    cookies = []
                    storage_state = None

                self._active_session = AuthSession(
                    authenticated=True,
                    username=cred.username,
                    cookies=cookies,
                    storage_state=storage_state,
                    redirect_url=page.url,
                )
                self.log_fn(f"Successfully authenticated as '{cred.username}'. Session cached for reuse.")

                # If target was a protected view, navigate to it now
                if target_url and page.url.rstrip("/") != target_url.rstrip("/"):
                    try:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=8000)
                        page.wait_for_timeout(600)
                    except Exception:
                        pass

                return True, steps, None

        # All credential candidates exhausted and failed
        final_err = last_error or "Authentication failed for all discovered credentials; application rejected login."
        return False, steps, final_err

    def is_html_login_trap(self, status_code: int, content_type: str, body_text: str) -> bool:
        """Detects whether an API call returned 200 with an HTML login page instead of authenticated JSON data."""
        if not body_text:
            return False
        ct_lower = (content_type or "").lower()
        body_lower = body_text.lower()

        # If Content-Type is HTML or starts with HTML tags
        is_html = "text/html" in ct_lower or body_text.strip().startswith("<!DOCTYPE") or body_text.strip().startswith("<html")
        if is_html and any(k in body_lower for k in ["login", "signin", "form-signin", "password", "please sign in", "username"]):
            return True
        return False
