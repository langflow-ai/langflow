"""Bounded recovery details for administrators inspecting orphaned legacy stores."""

import json
from pathlib import PurePosixPath

from langflow.services.knowledge_base_storage.maintenance import MaintenanceRequiredError
from langflow.services.knowledge_base_storage.migration_io import read_regular_file, run_worker
from langflow.services.knowledge_base_storage.runtime import StorageUnavailableError, storage_root

_SOURCE_PATH_PARTS = 2


async def inventory_recovery_details(*, scan_failed: bool = False) -> dict:
    """Expose relative source names, safe error codes and whether the latest scan finished, without sidecar contents."""
    try:
        root = storage_root()
    except StorageUnavailableError:
        return {"details": [], "scan_failed": scan_failed}
    if scan_failed:
        return {"storage_directory": str(root), "details": [], "scan_failed": True}
    details = []
    try:
        value = json.loads(
            await run_worker(read_regular_file, root / ".migration" / "inventory.json", limit=4 * 1024 * 1024)
        )
        scan_failed = isinstance(value, dict) and value.get("scan_failed") is True
        issues = value.get("issues", []) if isinstance(value, dict) else []
        if not isinstance(issues, list):
            issues = []
        for issue in issues[:500]:
            if not isinstance(issue, dict):
                continue
            source, code = issue.get("source"), issue.get("code")
            if not isinstance(source, str) or not isinstance(code, str):
                continue
            parts = PurePosixPath(source).parts
            if (
                PurePosixPath(source).is_absolute()
                or len(parts) != _SOURCE_PATH_PARTS
                or any(part in (".", "..") or "\\" in part for part in parts)
            ):
                continue
            details.append({"source": source, "code": code})
    except (ValueError, MaintenanceRequiredError):
        # Old scans and interrupted scans still offer a fresh inventory retry.
        pass
    return {"storage_directory": str(root), "details": details, "scan_failed": scan_failed}
