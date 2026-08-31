"""Small JSON read/write helpers with safe, atomic defaults."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def write_json(path: Path, data: Any) -> Path:
    """Write ``data`` as pretty-printed JSON atomically, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    tmp_path = path.with_suffix(f".tmp.{os.getpid()}")
    try:
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError:
        path.write_text(payload, encoding="utf-8")
        if tmp_path.exists():
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
    return path


def read_json(path: Path) -> Any | None:
    """Read JSON from ``path``; return ``None`` if missing or malformed."""
    if not path.is_file():
        return None
    for attempt in range(3):
        try:
            content = path.read_text(encoding="utf-8")
            if not content.strip():
                time.sleep(0.01)
                continue
            return json.loads(content)
        except (json.JSONDecodeError, OSError):
            if attempt < 2:
                time.sleep(0.01)
            else:
                return None
    return None
