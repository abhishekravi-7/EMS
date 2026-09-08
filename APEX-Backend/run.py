"""Java APEX Backend Runner.

Launches Uvicorn development server with file watching configured specifically
for application source code (``app/``), explicitly excluding generated workspace
storage (``storage/``) and logs (``logs/``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    # Ensure current backend directory is in sys.path
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(BACKEND_DIR / "app")],
        reload_excludes=["storage/*", "storage/**", "logs/*", "*.json"],
        log_level="info",
    )
