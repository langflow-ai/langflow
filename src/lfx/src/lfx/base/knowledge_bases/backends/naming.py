"""Owner-scoped physical names for remote knowledge base storage.

Knowledge base names are unique per user, not globally. A remote backend that
names its table or index from ``kb_name`` alone makes two users' same-named
knowledge bases share storage, so each can read, count, and delete the other's
chunks. Remote backends derive their physical name from the owner id plus the
knowledge base name instead.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

# ``lf_`` + 24 lowercase hex chars. Valid as a Postgres identifier and as an
# OpenSearch index name (lowercase, no reserved characters, 27 bytes).
OWNER_SCOPED_NAME_RE = re.compile(r"^lf_[0-9a-f]{24}$")


def owner_scoped_collection_name(owner_id: UUID, kb_name: str) -> str:
    """Return a stable, non-identifying name for ``owner_id``'s ``kb_name``.

    Takes a ``UUID`` rather than a string so every caller hashes the same
    canonical form. The length prefixes keep ``(owner, name)`` pairs from
    colliding by concatenation.
    """
    owner = str(owner_id)
    payload = f"{len(owner)}:{owner}{len(kb_name)}:{kb_name}"
    return f"lf_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"
