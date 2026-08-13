import os
import re
import html as html_module
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_job_ownership
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.models import User
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

router = APIRouter(tags=["existing-tests-report"])

def _inject_base_tag(document_html: str, job_id: str, subpath: str = "") -> str:
    """
    Injects <base href="/api/v1/existing-tests/report/{job_id}/{subpath}/"> into the <head> tag
    so relative assets (css/, images/, js/, fonts/) load seamlessly from the report's parent directory.
    """
    if not document_html:
        return document_html

    clean_subpath = subpath.replace("\\", "/").strip("/")
    prefix = f"{clean_subpath}/" if clean_subpath else ""
    base_url = f"/api/v1/existing-tests/report/{html_module.escape(job_id, quote=True)}/{prefix}"
    base_tag = f'<base href="{base_url}">'

    # Remove existing base tags
    document_html = re.sub(r"<base\b[^>]*>", "", document_html, flags=re.IGNORECASE)

    # Insert after <head>
    head_match = re.search(r"<head[^>]*>", document_html, flags=re.IGNORECASE)
    if head_match:
        insert_at = head_match.end()
        return document_html[:insert_at] + base_tag + document_html[insert_at:]

    return base_tag + document_html

def _safe_resolve(base_dir: Path, relative: str) -> Path:
    """Resolve a relative path inside base_dir. Raises 403 if outside."""
    resolved = (base_dir / relative).resolve()
    try:
        resolved.relative_to(base_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: path traversal detected")
    return resolved

def _serve_candidate(candidate: Path, evidence_base: Path, job_id: str):
    """
    Serve a resolved file candidate.  Returns an HTTPResponse or None if the
    candidate does not exist.
    """
    if candidate.is_dir():
        idx = candidate / "index.html"
        if idx.is_file():
            candidate = idx
        else:
            return None

    if not candidate.is_file():
        return None

    if candidate.suffix.lower() in [".html", ".htm"]:
        try:
            content = candidate.read_text(encoding="utf-8", errors="ignore")
            rel_subpath = ""
            try:
                rel_subpath = str(candidate.parent.relative_to(evidence_base)).replace("\\", "/")
            except Exception:
                pass
            return HTMLResponse(
                content=_inject_base_tag(content, job_id, subpath=rel_subpath),
                headers={"Cache-Control": "no-cache"}
            )
        except Exception:
            return FileResponse(str(candidate))

    return FileResponse(str(candidate))


@router.get("/existing-tests/report/{job_id}/{file_path:path}")
async def serve_existing_test_report_file(
    job_id: str,
    file_path: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Serves report files for a job from multiple possible base directories.
    Always searches all three bases in order:
      1. reports/test-evidence/         (Playwright HTML report, allure report)
      2. migrated-repo/                 (Maven surefire, gradle test results)
      3. original-repo/                 (Maven surefire on original source)
    This ensures both Playwright and JUnit/Surefire reports are accessible
    regardless of which ran first or whether test-evidence/ exists.
    """
    verify_job_ownership(db, job_id, current_user)

    paths = WorkspacePaths(job_id)

    # Ordered list of base directories to search
    candidate_bases = [
        paths.reports_dir / "test-evidence",
        paths.migrated_repo_dir,
        paths.original_repo_dir,
    ]

    last_403: HTTPException | None = None

    for base_dir in candidate_bases:
        if not base_dir.exists():
            continue
        try:
            candidate = _safe_resolve(base_dir, file_path) if file_path else base_dir
            response = _serve_candidate(candidate, base_dir, job_id)
            if response is not None:
                return response
        except HTTPException as he:
            if he.status_code == 403:
                # Path traversal attempt — propagate immediately
                raise
            # 404 or other — try next base
        except Exception:
            pass  # Try next base

    raise HTTPException(
        status_code=404,
        detail=f"File '{file_path}' not found for job '{job_id}'"
    )

