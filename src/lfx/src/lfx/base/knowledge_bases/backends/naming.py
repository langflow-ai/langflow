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

# ``lf_`` + 24 lowercase hex chars. Valid as a Postgres identifier, an OpenSearch
# index name (lowercase, no reserved characters, 27 bytes), and a Chroma
# collection name.
OWNER_SCOPED_NAME_RE = re.compile(r"^lf_[0-9a-f]{24}$")

# ``backend_config`` keys that point a knowledge base at named storage instead of
# its owner-scoped storage, plus the markers the pin migration writes. A name
# alone proves nothing about who owns the data behind it, so only a superuser may
# persist these keys.
STORAGE_ROUTING_KEYS = (
    "index_name",
    "index_name_origin",
    "legacy_shared_index",
    "collection_name",
    "collection_name_origin",
    "legacy_shared_collection",
)


class StorageRoutingNotAllowedError(PermissionError):
    """A non-superuser tried to persist a storage routing key in ``backend_config``."""


def ensure_storage_routing_allowed(backend_config: object, *, is_superuser: bool) -> None:
    """Reject storage routing keys in a ``backend_config`` a non-superuser is persisting.

    Empty values are allowed, since clients send ``index_name: ""`` to mean
    "not set".
    """
    if is_superuser or not isinstance(backend_config, dict):
        return
    keys = [key for key in STORAGE_ROUTING_KEYS if backend_config.get(key)]
    if keys:
        msg = (
            f"Only a superuser can set {', '.join(keys)} in backend_config, because these keys "
            "point a knowledge base at storage other users' knowledge bases may use. Remove them "
            "to use this knowledge base's own storage."
        )
        raise StorageRoutingNotAllowedError(msg)


def owner_scoped_collection_name(owner_id: UUID, kb_name: str) -> str:
    """Return a stable, non-identifying name for ``owner_id``'s ``kb_name``.

    Takes a ``UUID`` rather than a string so every caller hashes the same
    canonical form. The length prefixes keep ``(owner, name)`` pairs from
    colliding by concatenation.
    """
    owner = str(owner_id)
    payload = f"{len(owner)}:{owner}{len(kb_name)}:{kb_name}"
    return f"lf_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def resolve_storage_name(
    *,
    kb_name: str,
    owner_id: UUID | None,
    override: object,
    override_key: str,
    backend: str,
    storage: str,
) -> str:
    """Resolve the physical table / index / collection name for a remote knowledge base.

    ``override`` is the explicit name from ``backend_config`` (``override_key``),
    honored for externally managed storage and for pre-scoping names a migration
    pinned. ``backend_config`` is tenant-supplied, so an override shaped like an
    owner-scoped name must be this knowledge base's own. Without an override the
    name is owner-scoped, and a missing owner fails closed rather than falling
    back to a name other users could also get.
    """
    if override:
        name = str(override)
        if OWNER_SCOPED_NAME_RE.fullmatch(name.lower()) and (
            owner_id is None or name != owner_scoped_collection_name(owner_id, kb_name)
        ):
            msg = (
                f"{backend} {override_key} {name!r} is reserved for owner-scoped knowledge base "
                f"storage. Remove {override_key} to use this knowledge base's own {storage}."
            )
            raise ValueError(msg)
        return name
    if owner_id is None:
        msg = f"{backend} requires a valid user_id to isolate its {storage}."
        raise ValueError(msg)
    return owner_scoped_collection_name(owner_id, kb_name)
