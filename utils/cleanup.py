"""
utils/cleanup.py
Short-lived, per-run storage for uploaded CVs.

Each screening run gets its own private temporary directory. Files are saved
under random names (never the client-supplied filename), and the directory is
removed when the run ends — including on errors, reruns and disconnects,
because removal happens in a `finally` block. A startup sweep removes anything
left behind by a crashed process.
"""

import logging
import os
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

log = logging.getLogger(__name__)

_PREFIX = "rankcv-run-"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".csv"}


@contextmanager
def screening_workspace() -> Iterator[Path]:
    """Yield a private directory that is always deleted afterwards."""
    path = Path(tempfile.mkdtemp(prefix=_PREFIX))
    os.chmod(path, 0o700)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def safe_upload_path(workdir: Path, original_name: str) -> Path:
    """Random file name inside `workdir`, keeping only an allowed extension."""
    ext = Path(original_name or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext or 'none'}")
    return workdir / f"{uuid.uuid4().hex}{ext}"


def purge_stale_workspaces(max_age_seconds: int = 3600) -> int:
    """Remove run directories older than `max_age_seconds` and the legacy uploads/ folder."""
    removed = 0
    now = time.time()
    for item in Path(tempfile.gettempdir()).glob(f"{_PREFIX}*"):
        try:
            if item.is_dir() and now - item.stat().st_mtime > max_age_seconds:
                shutil.rmtree(item, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    legacy = Path("uploads")
    if legacy.is_dir():
        for f in legacy.iterdir():
            try:
                if f.is_file():
                    f.unlink()
                    removed += 1
            except OSError:
                continue
    if removed:
        log.info("Removed %d stale upload item(s)", removed)
    return removed
