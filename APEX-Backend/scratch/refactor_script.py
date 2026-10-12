import re

with open('app/api/v1/endpoints/migration_execution_controller.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add BackgroundTasks to import
if 'BackgroundTasks' not in content:
    content = content.replace('from fastapi.responses import JSONResponse', 'from fastapi.responses import JSONResponse\nfrom fastapi import BackgroundTasks')

original_func = '''@router.post("/migration/{job_id}/rerun-tests", summary="Re-run and regenerate unit tests for migration job.")
async def rerun_migration_tests(
    job_id: str,
    llm_provider: str = "groq",
    use_llm_tests: str = "true",
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:'''

new_bg_func = '''async def _run_migration_tests_background(
    job_id: str,
    llm_provider: str,
    use_llm_tests: str,
    current_user: User
):'''

if original_func in content:
    content = content.replace(original_func, new_bg_func)

    new_router = '''@router.post("/migration/{job_id}/rerun-tests", summary="Re-run and regenerate unit tests for migration job.")
async def rerun_migration_tests(
    job_id: str,
    background_tasks: BackgroundTasks,
    llm_provider: str = "groq",
    use_llm_tests: str = "true",
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    from app.infrastructure.workspace.workspace_paths import WorkspacePaths
    import json
    paths = WorkspacePaths(job_id)
    if paths.migration_report_path.exists():
        try:
            rep = json.loads(paths.migration_report_path.read_text(encoding="utf-8"))
            rep["test_pipeline"] = {"status": "IN_PROGRESS", "execution_status": "IN_PROGRESS"}
            paths.migration_report_path.write_text(json.dumps(rep, indent=2), encoding="utf-8")
        except Exception:
            pass

    background_tasks.add_task(
        _run_migration_tests_background,
        job_id,
        llm_provider,
        use_llm_tests,
        current_user
    )
    return JSONResponse(status_code=200, content={"status": "IN_PROGRESS", "message": "Unit tests generation started in the background."})

'''

    content = content.replace(new_bg_func, new_router + new_bg_func)

    with open('app/api/v1/endpoints/migration_execution_controller.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done")
else:
    print("Not found")
