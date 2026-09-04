"""Per-user scoping helpers for local (on-disk) vector stores.

Local vector stores (Chroma, FAISS, LocalDB) persist to a directory keyed only by
a collection / index name. Two different users that happen to pick the same name
and resolve to the same persist directory would otherwise read and write the same
on-disk store, leaking documents across users.

These helpers derive a stable, non-identifying per-user name so local stores are
isolated by the runtime user, while remote/server-backed stores are left
untouched. When there is genuinely no runtime user (e.g. running outside a
user-owned graph) the original name is returned unchanged, so behaviour is
preserved for non-multi-user usage.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any


def scoped_collection_name(collection_name: str, user_id: object | None) -> str:
    """Return a stable, non-identifying per-user name for a local vector store.

    The returned value is derived from a length-prefixed
    ``sha256(user_id, collection_name)`` payload and is safe to use as a Chroma
    collection name or an on-disk index/file name. Falls back to the original
    ``collection_name`` when there is no usable user id, so callers can apply this
    unconditionally on the local/on-disk path.
    """
    if not collection_name or user_id is None:
        return collection_name

    user_id_str = str(user_id).strip()
    if not user_id_str or user_id_str == "None":
        return collection_name

    # Length-prefix each field so the hash payload is unambiguous: a bare
    # "{user_id}:{collection_name}" join collides for pairs like ("a:b", "c") and
    # ("a", "b:c"), which would map distinct users/collections to the same store.
    payload = f"{len(user_id_str)}:{user_id_str}{len(collection_name)}:{collection_name}"
    digest = sha256(payload.encode()).hexdigest()[:16]
    return f"lf_{digest}"


def runtime_user_id(component: Any) -> object | None:
    """Return the runtime user id when the component executes in a user-owned graph.

    Prefers the component's ``_user_id`` and falls back to the owning graph's
    ``user_id``. Returns ``None`` when neither is available so callers fail safe to
    the unscoped name.
    """
    user_id = getattr(component, "_user_id", None)
    if user_id:
        return user_id

    vertex = getattr(component, "_vertex", None)
    graph = getattr(vertex, "graph", None) if vertex is not None else None
    return getattr(graph, "user_id", None)
