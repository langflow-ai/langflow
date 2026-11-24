from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from filelock import FileLock
from platformdirs import user_cache_dir

_TELEMETRY_ID_FILE = "telemetry_id"
_USER_ID_PREFIX = "lf"
_INSTALLATION_USER_ID_PREFIX = "lf-user-"
_SHA256_HEX_LENGTH = 64


def get_hashed_user_id(identifier: str) -> str:
    """Return an opaque IBM custom-realm ID for a random installation identifier."""
    digest = hashlib.sha256(identifier.encode()).hexdigest()
    return f"{_USER_ID_PREFIX}-{digest}"


def get_installation_user_id(user_id: uuid.UUID, installation_id: str) -> str:
    """Pseudonymize a random database user UUID within one installation.

    Usernames and SSO emails never enter this hash. The distinct prefix lets
    resumed jobs and the transport reject IDs made by the old username scheme.
    """
    digest = hashlib.sha256(installation_id.encode() + b"\0" + user_id.bytes).hexdigest()
    return f"{_INSTALLATION_USER_ID_PREFIX}{digest}"


def is_installation_user_id(user_id: str | None) -> bool:
    """Recognize the current identity scheme, excluding legacy username hashes."""
    if not isinstance(user_id, str) or not user_id.startswith(_INSTALLATION_USER_ID_PREFIX):
        return False
    digest = user_id[len(_INSTALLATION_USER_ID_PREFIX) :]
    return len(digest) == _SHA256_HEX_LENGTH and all(character in "0123456789abcdef" for character in digest)


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
