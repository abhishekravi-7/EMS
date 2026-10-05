"""Shared subprocess runner.

A thin, safe wrapper around :mod:`subprocess` used by the git layer (and any
future external-tool integration). It avoids ``shell=True``, captures
stdout/stderr/exit-code, and supports a timeout — returning a structured result
rather than raising on non-zero exit.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


def resolve_executable(name: str) -> str | None:
    """Return the full path to an executable on PATH, or ``None`` if missing.

    Needed on Windows where tools like ``mvn``/``gradle`` are ``.cmd`` scripts
    that ``subprocess`` (via CreateProcess) will not resolve from a bare name.
    """
    found = shutil.which(name)
    if found:
        return found

    # Fallback search for Maven if not directly on PATH
    if name.lower() in ("mvn", "mvn.cmd", "maven"):
        target_name = "mvn.cmd" if os.name == "nt" else "mvn"
        m2_dists = Path.home() / ".m2" / "wrapper" / "dists"
        if m2_dists.is_dir():
            try:
                candidates = sorted(m2_dists.rglob(target_name), key=lambda p: p.stat().st_mtime, reverse=True)
                if candidates:
                    return str(candidates[0])
            except Exception:
                pass

        search_roots = [
            Path("C:/Program Files"),
            Path("C:/ProgramData"),
            Path("C:/apache-maven"),
            Path("C:/maven"),
            Path("C:/tools"),
        ]
        for root in search_roots:
            if root.is_dir():
                try:
                    candidates = sorted(root.rglob(target_name), key=lambda p: p.stat().st_mtime, reverse=True)
                    if candidates:
                        return str(candidates[0])
                except Exception:
                    pass

    return None


@dataclass(frozen=True)
class CommandResult:
    """Structured outcome of a command invocation."""

    command: Sequence[str]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def run_command(
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run ``command`` (a list of args — never a shell string).

    Never raises on a non-zero exit or timeout; inspect
    :attr:`CommandResult.succeeded`. Only genuinely exceptional conditions
    (e.g. the executable not being found) propagate.
    """
    try:
        completed = subprocess.run(  # nosec B603 # noqa: S603
            list(command),
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(env) if env is not None else None,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=list(command),
            exit_code=-1,
            stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr or "" if isinstance(exc.stderr, str) else "",
            timed_out=True,
        )

    return CommandResult(
        command=list(command),
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
