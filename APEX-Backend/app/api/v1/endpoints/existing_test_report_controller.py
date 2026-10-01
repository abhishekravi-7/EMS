import asyncio
import html as html_module
import logging
import re
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from app.api.deps import User, get_current_user, verify_job_ownership
from app.infrastructure.workspace.workspace_paths import WorkspacePaths

logger = logging.getLogger(__name__)

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
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Access denied: path traversal detected") from exc
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
            except ValueError:
                rel_subpath = ""
            return HTMLResponse(
                content=_inject_base_tag(content, job_id, subpath=rel_subpath),
                headers={"Cache-Control": "no-cache"}
            )
        except OSError:
            return FileResponse(str(candidate))

    return FileResponse(str(candidate))


def _range_stream_video(file_path: Path, request: Request, media_type: str = "video/webm") -> Response:
    """Stream video with HTTP 206 Partial Content support for browser seeking."""
    file_size = file_path.stat().st_size
    if file_size == 0:
        raise HTTPException(status_code=404, detail="Video file is empty")

    range_header = request.headers.get("range")
    if not range_header:
        with open(file_path, "rb") as f:
            content = f.read()
        return Response(
            content=content,
            status_code=200,
            media_type=media_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Type": media_type,
            }
        )

    # Parse range header: e.g. "bytes=0-" or "bytes=0-1024"
    byte_range = range_header.replace("bytes=", "").split("-")
    start = int(byte_range[0]) if byte_range[0] else 0
    end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
    end = min(end, file_size - 1)
    chunk_size = end - start + 1

    with open(file_path, "rb") as f:
        f.seek(start)
        data = f.read(chunk_size)

    return Response(
        content=data,
        status_code=206,
        media_type=media_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Type": media_type,
        }
    )


@router.get("/migration/{job_id}/tests/{test_id:path}/evidence/screenshot")
@router.get("/migration/job/{job_id}/tests/{test_id:path}/evidence/screenshot")
@router.get("/migration/{job_id}/tests/{test_id:path}/screenshot")
@router.get("/existing-tests/report/{job_id}/ui/{test_id:path}/screenshot")
@router.get("/existing-tests/report/{job_id}/ui/{test_id:path}/screenshot.png")
async def serve_ui_test_screenshot(
    job_id: str,
    test_id: str,
):
    """Serve the screenshot image for a specific UI test case."""
    paths = WorkspacePaths(job_id)
    if not paths.job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Migration job '{job_id}' not found")

    evidence_dir = paths.reports_dir / "test-evidence"
    raw_test_id = urllib.parse.unquote(test_id)
    clean_test_id = raw_test_id.replace("\\", "/").strip("/")
    clean_test_id = re.sub(r'/(?:evidence|screenshot|video)(?:\.(?:png|jpg|jpeg|webp|webm|mp4))?$', '', clean_test_id, flags=re.IGNORECASE)
    clean_test_id = clean_test_id.removesuffix(".png").removesuffix(".jpg").removesuffix(".jpeg").removesuffix(".webp")
    dot_id = clean_test_id.replace("#", ".")
    dot_sanitized = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', dot_id)
    sanitized_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', clean_test_id)

    from app.application.use_cases.existing_test_runner_service import ExistingTestRunnerService
    c_key = ExistingTestRunnerService._canonical_test_identifier(clean_test_id, None)
    canonical_cls, canonical_method = c_key[0], c_key[1]
    canonical_id = f"{canonical_cls}.{canonical_method}"
    short_test = canonical_method or clean_test_id.split("#")[-1].split(".")[-1]

    candidates = [
        evidence_dir / "ui" / dot_sanitized / "screenshot.png",
        evidence_dir / "ui" / dot_sanitized / "screenshot.jpg",
        evidence_dir / "ui" / dot_sanitized / "screenshot.webp",
        evidence_dir / "ui" / dot_id / "screenshot.png",
        evidence_dir / "ui" / dot_id / "screenshot.jpg",
        evidence_dir / "ui" / sanitized_id / "screenshot.png",
        evidence_dir / "ui" / sanitized_id / "screenshot.jpg",
        evidence_dir / "ui" / clean_test_id / "screenshot.png",
        evidence_dir / "ui" / clean_test_id / "screenshot.jpg",
        evidence_dir / "ui" / canonical_id / "screenshot.png",
        evidence_dir / f"{dot_sanitized}.png",
        evidence_dir / f"{dot_id}.png",
        evidence_dir / f"{sanitized_id}.png",
        evidence_dir / f"{clean_test_id}.png",
        evidence_dir / f"{canonical_id}.png",
    ]

    for candidate in candidates:
        if candidate.is_file():
            safe_file = _safe_resolve(paths.job_dir, str(candidate.relative_to(paths.job_dir)))
            suf = safe_file.suffix.lower()
            media_type = "image/png" if suf == ".png" else "image/webp" if suf == ".webp" else "image/jpeg"
            return FileResponse(str(safe_file), media_type=media_type)

    # Search ui/ subdirectories with matching class & method
    ui_dir = evidence_dir / "ui"
    if ui_dir.exists():
        for d in ui_dir.iterdir():
            if d.is_dir():
                d_name = d.name.lower()
                if (
                    d.name == dot_sanitized or
                    d.name == sanitized_id or
                    d_name == dot_sanitized.lower() or
                    d_name == sanitized_id.lower() or
                    (canonical_cls and canonical_method and canonical_cls in d_name and canonical_method in d_name) or
                    (canonical_method and canonical_method in d_name) or
                    (short_test and short_test.lower() in d_name)
                ):
                    for img_name in ["screenshot.png", "screenshot.jpg", "screenshot.jpeg", "screenshot.webp"]:
                        shot_file = d / img_name
                        if shot_file.is_file():
                            safe_file = _safe_resolve(paths.job_dir, str(shot_file.relative_to(paths.job_dir)))
                            suf = safe_file.suffix.lower()
                            media_type = "image/png" if suf == ".png" else "image/webp" if suf == ".webp" else "image/jpeg"
                            return FileResponse(str(safe_file), media_type=media_type)

    # Search for any matching screenshot file across test-evidence directory
    if evidence_dir.exists():
        for f in evidence_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                f_name = f.name.lower()
                f_parent = f.parent.name.lower()
                if (
                    (short_test and short_test.lower() in f_name) or
                    (short_test and short_test.lower() in f_parent) or
                    sanitized_id.lower() in f_parent or
                    dot_sanitized.lower() in f_parent or
                    dot_id.lower() in f_parent or
                    (canonical_cls and canonical_method and canonical_cls in f_parent and canonical_method in f_parent)
                ):
                    safe_file = _safe_resolve(paths.job_dir, str(f.relative_to(paths.job_dir)))
                    suf = safe_file.suffix.lower()
                    media_type = "image/png" if suf == ".png" else "image/webp" if suf == ".webp" else "image/jpeg"
                    return FileResponse(str(safe_file), media_type=media_type)

    # Check migrated repo target/screenshots
    for search_dir in [paths.migrated_repo_dir, paths.original_repo_dir]:
        if search_dir.exists():
            for f in search_dir.rglob("*.png"):
                if f.is_file() and (
                    (short_test and short_test.lower() in f.name.lower()) or
                    (canonical_method and canonical_method in f.name.lower()) or
                    "screenshot" in f.name.lower()
                ):
                    safe_file = _safe_resolve(paths.job_dir, str(f.relative_to(paths.job_dir)))
                    return FileResponse(str(safe_file), media_type="image/png")

    raise HTTPException(status_code=404, detail=f"Screenshot not found for test '{test_id}' in job '{job_id}'")


@router.get("/migration/{job_id}/tests/{test_id:path}/evidence/video")
@router.get("/migration/job/{job_id}/tests/{test_id:path}/evidence/video")
@router.get("/migration/{job_id}/tests/{test_id:path}/video")
@router.get("/existing-tests/report/{job_id}/ui/{test_id:path}/video")
@router.get("/existing-tests/report/{job_id}/ui/{test_id:path}/video.webm")
@router.get("/existing-tests/report/{job_id}/ui/{test_id:path}/video.mp4")
async def serve_ui_test_video(
    job_id: str,
    test_id: str,
    request: Request,
):
    """Stream the video recording for a specific UI test case with range request support."""
    paths = WorkspacePaths(job_id)
    if not paths.job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Migration job '{job_id}' not found")

    evidence_dir = paths.reports_dir / "test-evidence"
    raw_test_id = urllib.parse.unquote(test_id)
    clean_test_id = raw_test_id.replace("\\", "/").strip("/")
    clean_test_id = re.sub(r'/(?:evidence|screenshot|video)(?:\.(?:png|jpg|jpeg|webp|webm|mp4))?$', '', clean_test_id, flags=re.IGNORECASE)
    clean_test_id = clean_test_id.removesuffix(".webm").removesuffix(".mp4")
    dot_id = clean_test_id.replace("#", ".")
    dot_sanitized = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', dot_id)
    sanitized_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', clean_test_id)

    from app.application.use_cases.existing_test_runner_service import ExistingTestRunnerService
    c_key = ExistingTestRunnerService._canonical_test_identifier(clean_test_id, None)
    canonical_cls, canonical_method = c_key[0], c_key[1]
    canonical_id = f"{canonical_cls}.{canonical_method}"
    short_test = canonical_method or clean_test_id.split("#")[-1].split(".")[-1]

    candidates = [
        evidence_dir / "ui" / dot_sanitized / "video.webm",
        evidence_dir / "ui" / dot_sanitized / "video.mp4",
        evidence_dir / "ui" / dot_id / "video.webm",
        evidence_dir / "ui" / dot_id / "video.mp4",
        evidence_dir / "ui" / sanitized_id / "video.webm",
        evidence_dir / "ui" / sanitized_id / "video.mp4",
        evidence_dir / "ui" / clean_test_id / "video.webm",
        evidence_dir / "ui" / clean_test_id / "video.mp4",
        evidence_dir / "ui" / canonical_id / "video.webm",
        evidence_dir / "ui" / canonical_id / "video.mp4",
        evidence_dir / f"{dot_sanitized}.webm",
        evidence_dir / f"{dot_id}.webm",
        evidence_dir / f"{sanitized_id}.webm",
        evidence_dir / f"{clean_test_id}.webm",
    ]

    for candidate in candidates:
        if candidate.is_file():
            safe_file = _safe_resolve(paths.job_dir, str(candidate.relative_to(paths.job_dir)))
            media_type = "video/webm" if safe_file.suffix == ".webm" else "video/mp4"
            return _range_stream_video(safe_file, request, media_type=media_type)

    # Search ui/ subdirectories with matching class & method
    ui_dir = evidence_dir / "ui"
    if ui_dir.exists():
        for d in ui_dir.iterdir():
            if d.is_dir():
                d_name = d.name.lower()
                if (
                    d.name == dot_sanitized or
                    d.name == sanitized_id or
                    d_name == dot_sanitized.lower() or
                    d_name == sanitized_id.lower() or
                    (canonical_cls and canonical_method and canonical_cls in d_name and canonical_method in d_name) or
                    (canonical_method and canonical_method in d_name) or
                    (short_test and short_test.lower() in d_name)
                ):
                    for vid_name in ["video.webm", "video.mp4"]:
                        vid_file = d / vid_name
                        if vid_file.is_file():
                            safe_file = _safe_resolve(paths.job_dir, str(vid_file.relative_to(paths.job_dir)))
                            media_type = "video/webm" if safe_file.suffix == ".webm" else "video/mp4"
                            return _range_stream_video(safe_file, request, media_type=media_type)

    if evidence_dir.exists():
        for f in evidence_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".webm", ".mp4"):
                f_name = f.name.lower()
                f_parent = f.parent.name.lower()
                if (
                    (short_test and short_test.lower() in f_name) or
                    (short_test and short_test.lower() in f_parent) or
                    sanitized_id.lower() in f_parent or
                    dot_sanitized.lower() in f_parent or
                    dot_id.lower() in f_parent or
                    (canonical_cls and canonical_method and canonical_cls in f_parent and canonical_method in f_parent)
                ):
                    safe_file = _safe_resolve(paths.job_dir, str(f.relative_to(paths.job_dir)))
                    media_type = "video/webm" if safe_file.suffix == ".webm" else "video/mp4"
                    return _range_stream_video(safe_file, request, media_type=media_type)

    raise HTTPException(status_code=404, detail=f"Video recording not found for test '{test_id}' in job '{job_id}'")


@router.get("/migration/{job_id}/tests/{test_id:path}/report")
@router.get("/existing-tests/report/{job_id}/test/{test_id:path}/report")
async def serve_individual_test_report(
    job_id: str,
    test_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Download individual test report JSON / metadata."""
    await verify_job_ownership(job_id, current_user)
    paths = WorkspacePaths(job_id)
    evidence_dir = paths.reports_dir / "test-evidence"

    clean_test_id = test_id.replace("\\", "/").strip("/")
    json_path = evidence_dir / "ui" / clean_test_id / "result.json"
    if json_path.is_file():
        safe_file = _safe_resolve(evidence_dir, str(json_path.relative_to(evidence_dir)))
        return FileResponse(str(safe_file), media_type="application/json", filename=f"{clean_test_id}_report.json")

    # Generate on-the-fly report data
    report_data = {
        "jobId": job_id,
        "testId": test_id,
        "exportedAt": "2026-08-14T17:00:00Z"
    }
    return JSONResponse(report_data)


@router.get("/migration/{job_id}/tests/{test_id:path}/logs")
@router.get("/existing-tests/report/{job_id}/test/{test_id:path}/logs")
async def serve_individual_test_logs(
    job_id: str,
    test_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Download test execution logs."""
    await verify_job_ownership(job_id, current_user)
    from app.application.use_cases.existing_test_runner_service import existing_test_runner_service

    clean_test_id = urllib.parse.unquote(test_id).replace("\\", "/")
    logger.info("[LOG DOWNLOAD] execution_id=%s test_id=%s", job_id, clean_test_id)
    status_data = await asyncio.to_thread(existing_test_runner_service.get_status, job_id)
    logs = await asyncio.to_thread(existing_test_runner_service.get_logs, job_id)

    # Match test from results if available
    test_results = status_data.get("result", {}).get("test_results", [])
    matched_test = None
    for t in test_results:
        t_id = (t.get("test_id") or f"{t.get('suite')}#{t.get('test_name')}").replace("\\", "/")
        if t_id == clean_test_id or t.get("test_name") == clean_test_id or t.get("name") == clean_test_id:
            matched_test = t
            break

    header_lines = [
        f"Execution ID: {job_id}",
        "",
        f"Test Name: {matched_test.get('test_name', clean_test_id) if matched_test else clean_test_id}",
        f"Class: {matched_test.get('suite', 'Unknown') if matched_test else 'Unknown'}",
        f"Framework: {matched_test.get('framework', 'JUnit') if matched_test else 'JUnit'}",
        f"Status: {matched_test.get('status', 'PASSED') if matched_test else 'PASSED'}",
    ]
    if matched_test and matched_test.get("duration"):
        header_lines.append(f"Duration: {matched_test.get('duration')}")
    if matched_test and matched_test.get("file"):
        header_lines.append(f"Source File: {matched_test.get('file')}")

    header_lines.extend([
        "",
        "=" * 80,
        "EXECUTION LOGS",
        "=" * 80,
        "",
    ])

    log_source = "existing_test_runner_service"
    log_exists = bool(logs) or bool(matched_test and (matched_test.get("stdout") or matched_test.get("stderr")))
    log_size = len(logs) if logs else (1 if (matched_test and (matched_test.get("stdout") or matched_test.get("stderr"))) else 0)
    logger.info(
        "[LOG DOWNLOAD] log source=%s log exists=%s log size=%d",
        log_source,
        log_exists,
        log_size
    )

    body_content = ""
    if matched_test:
        if matched_test.get("error"):
            body_content += f"[ERROR] {matched_test.get('error')}\n\n"
        if matched_test.get("stack_trace") or matched_test.get("stackTrace"):
            body_content += f"--- Stack Trace ---\n{matched_test.get('stack_trace') or matched_test.get('stackTrace')}\n\n"
        if matched_test.get("stdout"):
            body_content += f"--- Standard Output (stdout) ---\n{matched_test.get('stdout')}\n\n"
        if matched_test.get("stderr"):
            body_content += f"--- Standard Error (stderr) ---\n{matched_test.get('stderr')}\n\n"

    if logs:
        body_content += "--- Execution Output Logs ---\n" + "\n".join(logs) + "\n"

    if body_content.strip():
        content = "\n".join(header_lines) + body_content.strip() + "\n"
    else:
        content = "\n".join(header_lines) + "No execution logs recorded.\n"

    logger.info("[LOG DOWNLOAD] download successful execution_id=%s test_id=%s size=%d bytes", job_id, test_id, len(content))
    safe_filename = test_id.replace("/", "_").replace("\\", "_").replace("#", "_")
    return PlainTextResponse(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}_logs.txt"'}
    )


@router.get("/migration/{job_id}/tests/report/download")
@router.get("/existing-tests/report/{job_id}/download")
async def download_full_test_report(
    job_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Download full test report HTML or JSON summary."""
    await verify_job_ownership(job_id, current_user)
    from app.application.use_cases.existing_test_runner_service import existing_test_runner_service
    status_data = existing_test_runner_service.get_status(job_id)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Java APEX - Existing Tests Validation Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 32px; }}
    h1 {{ color: #38bdf8; margin-bottom: 8px; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: 700; font-size: 11px; }}
    .badge-pass {{ background: #065f46; color: #34d399; }}
    .badge-fail {{ background: #991b1b; color: #f87171; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background: #1e293b; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; }}
    th {{ background: #0f172a; color: #94a3b8; font-size: 11px; text-transform: uppercase; }}
  </style>
</head>
<body>
  <h1>Existing Tests Validation Report</h1>
  <p>Job ID: {job_id}</p>
  <table>
    <thead>
      <tr>
        <th>Status</th><th>Test Name</th><th>Suite</th><th>Type</th><th>Duration</th>
      </tr>
    </thead>
    <tbody>
"""
    results = status_data.get("result", {}).get("test_results", [])
    for t in results:
        status_cls = "badge-pass" if t.get("status") == "PASSED" else "badge-fail"
        html_content += f"""      <tr>
        <td><span class="badge {status_cls}">{t.get('status')}</span></td>
        <td>{t.get('test_name')}</td>
        <td>{t.get('suite')}</td>
        <td>{t.get('test_type') or t.get('type') or 'UNIT'}</td>
        <td>{t.get('duration') or 'N/A'}</td>
      </tr>\n"""

    html_content += """    </tbody>
  </table>
</body>
</html>"""
    return HTMLResponse(content=html_content, headers={"Content-Disposition": f'attachment; filename="test_validation_report_{job_id}.html"'})


@router.get("/existing-tests/report/{job_id}/{file_path:path}")
async def serve_existing_test_report_file(
    job_id: str,
    file_path: str = "",
    current_user: User = Depends(get_current_user),  # noqa: B008
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
    await verify_job_ownership(job_id, current_user)

    paths = WorkspacePaths(job_id)

    # Ordered list of base directories to search
    candidate_bases = [
        paths.reports_dir / "test-evidence",
        paths.migrated_repo_dir,
        paths.original_repo_dir,
    ]

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
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to resolve or serve candidate path under %s: %s", base_dir, exc)

    raise HTTPException(
        status_code=404,
        detail=f"File '{file_path}' not found for job '{job_id}'"
    )
