"""Local video path validation shared by TwelveLabs file consumers."""

from collections.abc import Iterable
from pathlib import Path

from lfx.utils.file_path_security import LocalFileAccessError, enforce_local_file_access


def resolve_video_file(video_path: str, *, scope_ids: Iterable[object] | None) -> Path:
    """Return an authorized, resolved regular file before a local read or upload."""
    if not isinstance(video_path, str) or not video_path or "://" in video_path:
        msg = "Invalid video path: expected a local file"
        raise ValueError(msg)

    # Bundle installations can use an older compatible lfx release whose
    # containment helper does not yet reject UNC paths before Path.resolve().
    if video_path.replace("\\", "/").startswith("//"):
        msg = "Access to UNC and device file paths is not permitted."
        raise LocalFileAccessError(msg)

    path = enforce_local_file_access(video_path, scope_ids=scope_ids)
    try:
        path = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        msg = "Invalid video path: file not found"
        raise ValueError(msg) from exc
    if not path.is_file():
        msg = "Invalid video path: expected a regular file"
        raise ValueError(msg)
    return path
