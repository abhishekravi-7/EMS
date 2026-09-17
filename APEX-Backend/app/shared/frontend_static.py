"""Serve browser routes without masking missing API endpoints or assets."""

from pathlib import PurePosixPath

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class FrontendStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        normalized_path = path.replace("\\", "/").lstrip("/")
        parts = PurePosixPath(normalized_path).parts
        if parts and parts[0] in {"api", "assets", "health", "docs", "redoc"}:
            return await super().get_response(path, scope)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            accepts_html = any(
                key == b"accept" and b"text/html" in value
                for key, value in scope.get("headers", [])
            )
            if (
                exc.status_code != 404
                or scope["method"] not in {"GET", "HEAD"}
                or PurePosixPath(normalized_path).suffix
                or ".." in parts
                or not accepts_html
            ):
                raise
            return await super().get_response("index.html", scope)
