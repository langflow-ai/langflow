from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from filelock import FileLock
from platformdirs import user_cache_dir

_TELEMETRY_ID_FILE = "telemetry_id"
_USER_ID_PREFIX = "lf"


def get_hashed_user_id(identifier: str) -> str:
    """Return an opaque IBM custom-realm user ID for a username or installation ID."""
    digest = hashlib.sha256(identifier.encode()).hexdigest()
    return f"{_USER_ID_PREFIX}-{digest}"


def get_or_create_anonymous_id(config_dir: str | Path | None = None) -> str:
    """Return a stable, opaque installation identifier for product telemetry."""
    root = Path(config_dir or os.environ.get("LANGFLOW_CONFIG_DIR") or user_cache_dir("langflow", "langflow"))
    identity_path = root / _TELEMETRY_ID_FILE

    existing = _read_id(identity_path)
    if existing is not None:
        return existing

    generated = str(uuid.uuid4())
    try:
        root.mkdir(parents=True, exist_ok=True)
        # The lock covers both the second read and write, including concurrent
        # workers that see the file before its first write has completed.
        with FileLock(f"{identity_path}.lock"):
            existing = _read_id(identity_path)
            if existing is not None:
                return existing
            identity_path.write_text(generated, encoding="utf-8")
    except OSError:
        return generated
    return generated


def _read_id(identity_path: Path) -> str | None:
    try:
        return str(uuid.UUID(identity_path.read_text(encoding="utf-8").strip()))
    except (OSError, ValueError):
        return None
