"""Per-user namespace derivation for the FileSystem tool sandbox.

This module owns one responsibility: turning an authenticated `user_id` into a
stable, opaque, collision-free directory name AND ensuring the HMAC pepper that
makes the mapping unguessable exists on disk before it is consumed.

The namespace path is intentionally relative (`Path("users/<hash>")`). Callers
join it under their own absolute base directory.

Why HMAC-SHA256 truncated to 32 hex chars (128 bits):
    - 128 bits is far past any practical collision risk for the realistic ceiling
      on Langflow tenants per instance.
    - Hashing with a server-side pepper prevents directory listings of
      ``<base>/users/`` from leaking the set of user IDs that have ever used the
      tool.
    - Truncation keeps directory names short enough for path-length-limited
      filesystems (Windows MAX_PATH 260) while remaining opaque.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sys
from pathlib import Path

PEPPER_SIZE_BYTES = 32
NAMESPACE_HEX_LEN = 32


def compute_user_namespace(user_id: str, *, pepper: bytes) -> Path:
    """Return the relative namespace path for ``user_id`` under ``users/<hash>``.

    An empty ``user_id`` yields ``Path("")`` so callers can treat legacy /
    anonymous mode by joining the result transparently. The pepper MUST be
    non-empty — an empty pepper would let an attacker who controls only the
    user_id replicate the hash and infer the directory name.
    """
    if not pepper:
        msg = "pepper must not be empty"
        raise ValueError(msg)
    if not user_id:
        return Path()
    digest = hmac.new(pepper, user_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return Path("users") / digest[:NAMESPACE_HEX_LEN]


def load_or_create_pepper(pepper_path: Path) -> bytes:
    """Return the pepper at ``pepper_path``, creating it on first call.

    On POSIX the new file is created with mode 0o600 — pepper compromise lets an
    attacker enumerate the on-disk namespace, so it has to live behind the same
    fence as a private key. On Windows we rely on the standard NTFS DACL
    inherited from the parent directory; tightening that requires the ``ntsecurity``
    APIs which are out of scope for this helper.
    """
    if pepper_path.exists():
        existing = pepper_path.read_bytes()
        if len(existing) < PEPPER_SIZE_BYTES:
            msg = f"pepper at {pepper_path} is too short ({len(existing)} bytes); expected at least {PEPPER_SIZE_BYTES}"
            raise ValueError(msg)
        return existing

    pepper_path.parent.mkdir(parents=True, exist_ok=True)
    new_pepper = secrets.token_bytes(PEPPER_SIZE_BYTES)
    if sys.platform == "win32":
        pepper_path.write_bytes(new_pepper)
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(pepper_path, flags, 0o600)
        try:
            os.write(fd, new_pepper)
        finally:
            os.close(fd)
    return new_pepper
