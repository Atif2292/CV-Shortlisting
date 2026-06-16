"""
utils/cleanup.py
Delete uploaded CV files from disk after processing.
This keeps the server clean and protects candidate data.
"""

import os
from pathlib import Path


def delete_uploaded_files(file_paths: list[str]) -> tuple[list[str], list[str]]:
    """
    Delete a list of files from disk.

    Args:
        file_paths: List of absolute or relative file path strings.

    Returns:
        Tuple of (deleted_paths, failed_paths) where:
          deleted_paths — files that were successfully removed.
          failed_paths  — files that could not be removed (logged with reason).
    """
    deleted = []
    failed  = []

    for path_str in file_paths:
        path = Path(path_str)

        # Only delete files; never remove directories
        if not path.is_file():
            print(f"[cleanup] Not a file (skipping): {path_str}")
            failed.append(path_str)
            continue

        # Safety check: only delete from the uploads/ directory
        # Adjust the allowed prefix if your upload dir differs.
        try:
            resolved = path.resolve()
            uploads_dir = Path("uploads").resolve()
            resolved.relative_to(uploads_dir)   # raises ValueError if not inside uploads/
        except ValueError:
            print(f"[cleanup] Refusing to delete file outside uploads/: {path_str}")
            failed.append(path_str)
            continue

        try:
            os.remove(path)
            deleted.append(path_str)
            print(f"[cleanup] 🗑️  Deleted: {path_str}")
        except PermissionError as exc:
            print(f"[cleanup] Permission denied for {path_str}: {exc}")
            failed.append(path_str)
        except FileNotFoundError:
            # Already gone — treat as success
            deleted.append(path_str)
        except Exception as exc:
            print(f"[cleanup] Unexpected error deleting {path_str}: {exc}")
            failed.append(path_str)

    return deleted, failed


def purge_uploads_dir(uploads_dir: str = "uploads") -> int:
    """
    Delete ALL files inside the uploads directory.
    Useful as a housekeeping routine on startup or as a scheduled job.

    Returns:
        Number of files deleted.
    """
    count = 0
    base = Path(uploads_dir)

    if not base.is_dir():
        return 0

    for item in base.iterdir():
        if item.is_file():
            try:
                item.unlink()
                count += 1
            except Exception as exc:
                print(f"[cleanup] Could not delete {item}: {exc}")

    print(f"[cleanup] Purged {count} file(s) from {uploads_dir}/")
    return count
