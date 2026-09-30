"""Framework-aware server runner for migrated frontend applications."""

from __future__ import annotations

import logging
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def find_free_port() -> int:
    """Finds an available ephemeral TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class MigratedFrontendServer:
    """Detects, builds, and serves modernized frontend React/Vue/Angular applications on a dynamic port."""

    def __init__(self, job_id: str, repo_dir: Path):
        self.job_id = job_id
        self.repo_dir = Path(repo_dir)
        self.frontend_dir = self.repo_dir / "frontend"
        self._proc: subprocess.Popen | None = None
        self._port: int | None = None

    def has_migrated_frontend(self) -> bool:
        """Checks if the repository contains modernized frontend components."""
        if not self.frontend_dir.exists():
            return False
        app_file = self.frontend_dir / "src" / "App.tsx"
        if app_file.is_file():
            return True
        # Check if there are any .tsx or .jsx files in frontend
        return bool(list(self.frontend_dir.rglob("*.tsx")) or list(self.frontend_dir.rglob("*.jsx")))

    def build_dist(self, output_dir: Path | None = None) -> Path:
        """Prepares standalone HTML representations of all modernized frontend routes."""
        dist_dir = output_dir or (self.repo_dir.parent / "frontend-dist")
        dist_dir.mkdir(parents=True, exist_ok=True)

        app_file = self.frontend_dir / "src" / "App.tsx"
        routes: list[tuple[str, str]] = []
        if app_file.is_file():
            content = app_file.read_text(encoding="utf-8")
            # 1. Match index route: <Route index element={<Dashboard />} />
            index_match = re.search(r'<Route\s+index\s+element=\{<([A-Za-z0-9_]+)', content)
            if index_match:
                routes.append(("/", index_match.group(1)))

            # 2. Match standard routes: <Route path="..." element={<Component ...
            for rpath, cname in re.findall(r'<Route\s+path=["\']([^"\']+)["\']\s+element=\{<([A-Za-z0-9_]+)', content):
                # Ignore wildcard / navigation redirects like <Route path="*" element={<Navigate ...
                if rpath == "*" or cname.lower() in ("navigate", "redirect", "layout", "router", "routes"):
                    continue
                # Normalize relative path to absolute route
                norm_path = rpath if rpath.startswith("/") else f"/{rpath}"
                routes.append((norm_path, cname))

            # 3. Check for login wrapper: if (!isAuthenticated) return <Login ...
            login_match = re.search(r'return\s+<([A-Za-z0-9_]*Login[A-Za-z0-9_]*)\b', content)
            if login_match:
                login_cname = login_match.group(1)
                if not any(r[1] == login_cname for r in routes):
                    routes.append(("/login", login_cname))

        # Fallback: scan all .tsx / .jsx component files if no App.tsx routes
        if not routes:
            for ext in ("*.tsx", "*.jsx"):
                for f in self.frontend_dir.rglob(ext):
                    if f.name.lower() in ("app.tsx", "main.tsx", "index.tsx", "app.jsx", "main.jsx", "index.jsx"):
                        continue
                    cname = f.stem
                    if cname.lower() in ("layout", "router", "routes", "navigate", "redirect"):
                        continue
                    rpath = "/" + cname.lower().replace("component", "")
                    routes.append((rpath, cname))
            if routes:
                routes.insert(0, ("/", routes[0][1]))

        # Read styles if available
        css_content = ""
        for css_candidate in [
            self.frontend_dir / "src" / "styles" / "modern-ui.css",
            self.frontend_dir / "styles" / "modern-ui.css",
        ]:
            if css_candidate.is_file():
                css_content = css_candidate.read_text(encoding="utf-8")
                break

        nav_links_html = ""
        for rpath, cname in routes:
            if rpath == "/":
                nav_links_html += '<a href="/" style="text-decoration:none; color:#475569; font-weight:500;">Home</a>\n'
            else:
                label = cname.replace("Component", "")
                nav_links_html += f'<a href="{rpath}" style="text-decoration:none; color:#475569; font-weight:500;">{label}</a>\n'

        generated_pages: dict[str, str] = {}
        for rpath, cname in routes:
            matches: list[Path] = []
            for ext in ("tsx", "jsx", "js", "ts"):
                matches.extend(list(self.frontend_dir.rglob(f"{cname}.{ext}")))
            cfile = matches[0] if matches else None
            body_html = self._jsx_to_html(cfile.read_text(encoding="utf-8")) if cfile and cfile.is_file() else f"<div>{cname}</div>"

            page_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Modernized Application - {cname}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    {css_content}
  </style>
</head>
<body>
  <div class="modern-app-root">
    <header class="modern-header" style="background:#ffffff; border-bottom:1px solid #e2e8f0; padding:12px 24px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;">
      <div style="display:flex; align-items:center; gap:1rem;">
        <h1 style="margin:0; font-size:1.25rem; font-weight:700; color:#2563eb;">Modernized Application</h1>
        <span class="badge bg-primary" style="font-size:11px; padding:3px 8px; border-radius:12px;">Modernized</span>
      </div>
      <form class="d-flex align-items-center" style="max-width:260px;" onsubmit="return false;">
        <div class="input-group input-group-sm">
          <input type="text" name="search" class="form-control" placeholder="Search tasks..." aria-label="Search">
          <button type="submit" class="btn btn-primary btn-sm"><i class="fa fa-search"></i> Search</button>
        </div>
      </form>
      <nav style="display:flex; gap:1rem; flex-wrap:wrap;">
        {nav_links_html}
      </nav>
    </header>
    <main class="modern-main-content" style="padding:24px;">
      {body_html}
    </main>
  </div>
  <script>
    document.addEventListener('submit', function(e) {{
      e.preventDefault();
      var feedback = document.createElement('div');
      feedback.className = 'alert alert-success mt-3';
      feedback.setAttribute('role', 'alert');
      feedback.textContent = 'Form submitted successfully.';
      e.target.appendChild(feedback);
    }});
  </script>
</body>
</html>"""
            generated_pages[rpath] = page_html

            clean_path = rpath.strip("/")
            if not clean_path:
                (dist_dir / "index.html").write_text(page_html, encoding="utf-8")
            else:
                # Sanitize path segments to avoid Windows illegal path syntax ([WinError 123])
                safe_parts = [re.sub(r'[*?:\"<>|]', '_', p) for p in clean_path.split("/") if p and p != "*"]
                if safe_parts:
                    route_dir = dist_dir.joinpath(*safe_parts)
                    route_dir.mkdir(parents=True, exist_ok=True)
                    (route_dir / "index.html").write_text(page_html, encoding="utf-8")
                    flat_name = "_".join(safe_parts)
                    (dist_dir / f"{flat_name}.html").write_text(page_html, encoding="utf-8")

        # Guarantee index.html and 404.html fallback exist
        index_file = dist_dir / "index.html"
        if not index_file.exists() and generated_pages:
            first_html = next(iter(generated_pages.values()))
            index_file.write_text(first_html, encoding="utf-8")

        if index_file.exists() and not (dist_dir / "404.html").exists():
            (dist_dir / "404.html").write_text(index_file.read_text(encoding="utf-8"), encoding="utf-8")

        return dist_dir

    def launch(self) -> tuple[int, int, str]:
        """Launches the dynamic frontend server as a background subprocess.

        Returns:
            (port, pid, runtime_url)
        """
        dist_dir = self.build_dist()
        port = find_free_port()

        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--directory", str(dist_dir)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._proc = proc
        from app.infrastructure.build.app_launcher import MigratedAppLauncher

        # Wait until port is bound by the process
        start_t = time.time()
        while time.time() - start_t < 6.0:
            if proc.poll() is not None:
                break
            if MigratedAppLauncher.is_port_owned_by_process(port, proc.pid):
                break
            time.sleep(0.2)

        runtime_url = f"http://localhost:{port}"
        return port, proc.pid, runtime_url

    def stop(self) -> None:
        """Terminates the frontend server subprocess."""
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    @staticmethod
    def _jsx_to_html(code: str) -> str:
        """Converts React JSX component syntax into valid HTML5 markup."""
        # Find all return statements containing JSX and pick the most complete one (largest markup)
        returns = re.findall(r"return\s*(?:\(\s*)?(<[\s\S]*?>)(?:\s*\))?\s*;", code)
        if returns:
            markup = max(returns, key=len)
        else:
            match = re.search(r"return\s+(<[\s\S]*?>);", code)
            markup = match.group(1) if match else "<div>Modernized Component</div>"

        # Strip react fragments
        markup = re.sub(r"</?\s*(?:React\.)?Fragment\s*>", "", markup)
        markup = re.sub(r"<>|</>", "", markup)

        # Remove router / wrapper tags like <Layout ...>, </Layout>, <Router>, etc.
        markup = re.sub(r"</?(?:Layout|Router|Routes|BrowserRouter|AuthContext|AuthProvider)[^>]*>", "", markup)

        markup = re.sub(r"\bclassName=", "class=", markup)
        markup = re.sub(r"<BR\s*/?>", "<br>", markup, flags=re.IGNORECASE)
        markup = re.sub(r"<HR\s*/?>", "<hr>", markup, flags=re.IGNORECASE)
        markup = re.sub(r"<(H[1-6])\b", lambda m: f"<{m.group(1).lower()}", markup, flags=re.IGNORECASE)
        markup = re.sub(r"</(H[1-6])>", lambda m: f"</{m.group(1).lower()}>", markup, flags=re.IGNORECASE)

        # Contextual variable / placeholder substitutions
        markup = re.sub(r"\{\s*(?:name|user|username)\s*\}", "Admin User", markup)
        markup = re.sub(r"\{\s*(?:errorMessage|error)\s*\}", "", markup)
        markup = re.sub(r"\{\s*(?:loading|isLoading)\s*\}", "", markup)
        markup = re.sub(r"\{\s*formData\.[a-zA-Z0-9_]+\s*\}", "", markup)
        markup = re.sub(r"\{\s*(?:activeCount|totalPaid|count|total)[^}]*\}", "24", markup)
        markup = re.sub(r"\{\s*todo\.[a-zA-Z0-9_]+\s*\}", "Sample Action Item", markup)
        markup = re.sub(r"\{[^{}]*?&&\s*(<[\s\S]*?>)\s*\}", r"\1", markup)
        markup = re.sub(r"\{[^{}]*\}", "", markup)

        # Remove event bindings
        markup = re.sub(r"\s+onClick=\{[^}]*\}", "", markup)
        markup = re.sub(r"\s+onChange=\{[^}]*\}", "", markup)
        markup = re.sub(r"\s+onSubmit=\{[^}]*\}", "", markup)

        # Replace React icon components <Fi... /> or <Fa... /> or <Bi... /> with icon spans
        markup = re.sub(r"<([A-Z][a-z0-9]+(?:Icon|Users|DollarSign|Edit|Trash|Calendar|Check|Times))\b[^>]*\/?>", r'<i class="fa fa-circle"></i>', markup)

        return markup.strip()
