"""Filesystem helpers used by the Discovery analyzers and workspace layer.

All functions are read-only with respect to the analyzed project — nothing here
modifies the cloned repository.
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path


def _long_path(path: Path) -> Path:
    """Return an extended-length form of ``path`` on Windows.

    The ``\\\\?\\`` prefix tells the Win32 API to bypass the classic 260-character
    ``MAX_PATH`` limit. Without it, copying/deleting deeply nested trees (e.g. a
    cloned repo's resources) can fail with ``WinError 3`` even though the path is
    otherwise valid. No-op on non-Windows platforms.
    """
    if sys.platform != "win32":
        return path
    resolved = str(path.resolve())
    if resolved.startswith("\\\\?\\"):
        return path
    if resolved.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + resolved.lstrip("\\"))
    return Path("\\\\?\\" + resolved)


def to_plain_path_str(path: Path | str) -> str:
    """Return a plain string representation of ``path`` without the long-path prefix.

    Used for external tools or libraries (like Java's Jackson) that might not
    support the Win32 extended-length path prefix (``\\\\?\\``).
    """
    s = str(path)
    if s.startswith("\\\\?\\"):
        if s.startswith("\\\\?\\UNC\\"):
            # \\\\?\\UNC\\server\\share -> \\\\server\\share
            return "\\\\" + s[8:]
        # \\\\?\\C:\\path -> C:\\path
        return s[4:]
    return s


def read_text(path: Path) -> str:
    """Read a text file, tolerating odd encodings. Returns "" if unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        try:
            return path.read_text(encoding="latin-1")
        except OSError:
            return ""


def exists(root: Path, *relative_parts: str) -> bool:
    """True if ``root/relative_parts...`` exists."""
    return (root.joinpath(*relative_parts)).exists()


def count_files(root: Path, suffix: str, *, limit: int | None = None) -> int:
    """Count files under ``root`` whose name ends with ``suffix`` (case-insensitive).

    Skips common noise directories (VCS, node_modules, build output). Stops early
    once ``limit`` is reached when provided.
    """
    count = 0
    for path in _iter_files(root):
        if path.name.lower().endswith(suffix.lower()):
            count += 1
            if limit is not None and count >= limit:
                break
    return count


def find_files(root: Path, suffix: str, *, limit: int = 2000) -> list[str]:
    """Return repo-relative paths of files ending with ``suffix`` (case-insensitive)."""
    matches: list[str] = []
    lowered = suffix.lower()
    # Normalize root to match the long-path format used in _iter_files
    normalized_root = _long_path(root)
    for path in _iter_files(root):
        if path.name.lower().endswith(lowered):
            matches.append(path.relative_to(normalized_root).as_posix())
            if len(matches) >= limit:
                break
    return matches


_SKIP_DIRS = {
    ".git",
    "node_modules",
    "target",
    "build",
    "dist",
    ".gradle",
    ".idea",
    ".mvn",
    "out",
    "bin",
}


def _iter_files(root: Path):
    """Yield files under ``root`` skipping noise directories."""
    # Using os.walk allows us to prune directories (like node_modules) BEFORE
    # descending into them, avoiding deep-path issues (WinError 3) and saving time.
    #
    # We use _long_path for Windows robustness, ensuring we can traverse deeply
    # nested structures without hitting the 260-character limit.
    root_str = str(_long_path(root))
    try:
        for dirpath, dirnames, filenames in os.walk(root_str):
            # Prune noise directories in-place so os.walk doesn't visit them.
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

            for name in filenames:
                yield Path(dirpath) / name
    except OSError:
        # Best-effort traversal; skip branches we can't access
        pass


def find_shallowest_dir_with(
    root: Path,
    filenames: tuple[str, ...],
    *,
    max_depth: int = 5,
) -> Path | None:
    """Return the shallowest directory (at or under ``root``) that contains any
    of ``filenames``.

    Used to locate a Java project when its build file lives in a subfolder
    (e.g. ``backend/pom.xml``) rather than the repo root. Noise directories are
    skipped and the search is depth-bounded.
    """
    targets = {name.lower() for name in filenames}
    root_str = str(_long_path(root))

    matches: list[tuple[int, Path]] = []

    for dirpath, dirnames, files in os.walk(root_str):
        # Calculate current depth relative to root
        try:
            rel_path = os.path.relpath(dirpath, root_str)
            depth = 0 if rel_path == "." else len(Path(rel_path).parts)
        except ValueError:
            # Can happen on Windows with mixed long/short path references
            depth = 100

        # Stop descending if we reached max_depth
        if depth >= max_depth:
            dirnames[:] = []

        # Prune noise directories
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

        for name in files:
            if name.lower() in targets:
                match_dir = Path(dirpath)
                matches.append((depth, match_dir))
                if depth == 0:
                    return match_dir
                # Optimization: don't look deeper in this branch if we found a build file
                dirnames[:] = []
                break

    if not matches:
        return None

    # Pick the one with minimum depth
    matches.sort(key=lambda x: (x[0], str(x[1])))
    return matches[0][1]


def remove_tree(path: Path) -> None:
    """Recursively delete ``path`` if it exists.

    Handles Windows read-only, hidden, and system files (common inside
    ``.git``) via an onerror hook that strips all special attributes before
    retrying the delete.
    """
    long_path = _long_path(path)
    if not long_path.exists():
        return

    def _on_error(func, target, _exc_info):  # pragma: no cover - platform specific
        try:
            p = Path(target)
            # Strip read-only, hidden, system attributes then retry
            current = p.stat().st_mode
            p.chmod(current | stat.S_IWRITE | stat.S_IREAD)
            func(target)
        except OSError:
            pass  # best-effort; copy_tree uses dirs_exist_ok as fallback

    shutil.rmtree(long_path, onerror=_on_error)



def _relative_files(root: Path) -> dict[str, Path]:
    """Map of repo-relative posix path -> absolute path (noise dirs skipped)."""
    normalized_root = _long_path(root)
    return {path.relative_to(normalized_root).as_posix(): path for path in _iter_files(root)}


def count_changed_files(original: Path, migrated: Path) -> int:
    """Count files that differ between two trees (added, removed, or modified).

    Both trees are compared with noise directories skipped. Used to report how
    many files a migration changed, independent of the build tool's own output.
    """
    original_files = _relative_files(original)
    migrated_files = _relative_files(migrated)

    changed = 0
    for rel in set(original_files) | set(migrated_files):
        a = original_files.get(rel)
        b = migrated_files.get(rel)
        if a is None or b is None:
            changed += 1
            continue
        try:
            if a.read_bytes() != b.read_bytes():
                changed += 1
        except OSError:
            changed += 1
    return changed


def diff_relative_files(original: Path, migrated: Path) -> tuple[list[str], list[str], list[str]]:
    """Return ``(added, removed, modified)`` repo-relative paths, each sorted.

    ``added`` exists only under ``migrated``, ``removed`` only under
    ``original``; ``modified`` exists in both but differs in content.
    """
    original_files = _relative_files(original)
    migrated_files = _relative_files(migrated)

    added: list[str] = []
    removed: list[str] = []
    modified: list[str] = []
    for rel in sorted(set(original_files) | set(migrated_files)):
        a = original_files.get(rel)
        b = migrated_files.get(rel)
        if a is None:
            added.append(rel)
        elif b is None:
            removed.append(rel)
        else:
            try:
                if a.read_bytes() != b.read_bytes():
                    modified.append(rel)
            except OSError:
                modified.append(rel)
    return added, removed, modified


def copy_tree(src: Path, dst: Path, *, exclude: set[str] | None = None) -> None:
    """Copy the ``src`` directory tree to ``dst`` (created fresh).

    ``exclude`` names directories to skip at any level (e.g. ``{".git"}``) so the
    copy is a clean working tree without VCS metadata.

    On Windows, file locks from a previous failed migration can prevent
    ``remove_tree`` from fully deleting the destination. We use
    ``dirs_exist_ok=True`` so the copy succeeds regardless, and also do a
    best-effort force-removal with a short retry loop before the copy.
    """
    import time

    exclude = exclude or set()

    # Best-effort removal: try up to 3 times with a short delay for Windows
    # file locks to release between retries.
    long_dst = _long_path(dst)
    for attempt in range(3):
        remove_tree(dst)
        if not long_dst.exists():
            break
        if attempt < 2:
            time.sleep(0.5)

    def _ignore(_dir: str, names: list[str]) -> set[str]:
        return {name for name in names if name in exclude}

    # dirs_exist_ok=True lets the copy succeed even if the destination
    # directory still exists after the removal attempts above.
    shutil.copytree(_long_path(src), long_dst, ignore=_ignore, dirs_exist_ok=True)
