"""Pin existing OpenSearch and Chroma Cloud knowledge bases to their pre-scoping storage.

Phase: MIGRATE
Revision ID: 386662af02e9
Revises: a1b2c9d3e4f5
Create Date: 2026-09-17

OpenSearch knowledge bases without an explicit ``backend_config.index_name``
read and wrote an index named from the knowledge base name alone, and Chroma
Cloud knowledge bases used a collection named exactly after it. Names are unique
per user, not globally, so two users' knowledge bases with the same name on one
cluster, or in one Chroma Cloud tenant and database, shared storage: each could
read, count, and delete the other's chunks. Both backends now derive an
owner-scoped name instead, which would leave every existing knowledge base
pointing at new, empty storage.

This migration keeps existing data in service without keeping the leak:

* When every knowledge base that resolves to a legacy name belongs to one owner,
  each of them is pinned to it through ``index_name`` (OpenSearch) or
  ``collection_name`` (Chroma Cloud), with ``<key>_origin: legacy_kb_name``.
  Nothing moves on the cluster.
* When knowledge bases of several owners resolve to the same legacy name, their
  chunks may already be mixed and cannot be attributed to one owner. Those
  knowledge bases are not pinned: they move to their own empty owner-scoped
  storage, the shared storage is left untouched, and the row records
  ``legacy_shared_index`` / ``legacy_shared_collection`` so the backend logs a
  warning until an operator resolves it.
* A legacy name shaped like an owner-scoped name (``lf_`` + 24 hex chars) is
  handled the same way. The backend refuses such a name unless it is the
  knowledge base's own owner-scoped name, so a pin would leave the knowledge
  base unusable.

The database cannot tell which cluster, tenant, or database a row's credentials
resolve to, so same-named knowledge bases of different owners are treated as
sharing storage even when they use different accounts. That errs toward hiding
pre-upgrade data rather than continuing to expose it; the upgrade notes describe
how to pin such knowledge bases back.

Only the database is changed. OpenSearch and Chroma Cloud are never contacted.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from uuid import UUID

revision: str = "386662af02e9"  # pragma: allowlist secret
down_revision: str | None = "a1b2c9d3e4f5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger(__name__)

LEGACY_KB_NAME_ORIGIN = "legacy_kb_name"
OWNER_SCOPED_ORIGIN = "owner_scoped"

# Frozen copies of the naming rules at the time of this revision. Migrations
# must not follow later edits to application code.
_LEGACY_FORBIDDEN = re.compile(r'[\\/*?"<>|,#: \t\n\r]+')
_LEGACY_NON_ALNUM = re.compile(r"[^a-z0-9._-]+")
_OWNER_SCOPED_NAME_RE = re.compile(r"^lf_[0-9a-f]{24}$")


def legacy_index_name(kb_name: str) -> str:
    """Index name the OpenSearch backend derived from ``kb_name`` before owner scoping."""
    name = (kb_name or "").strip().lower()
    name = _LEGACY_FORBIDDEN.sub("_", name)
    name = _LEGACY_NON_ALNUM.sub("_", name)
    name = name.lstrip("-_+.")
    if not name or name in {".", ".."}:
        name = "kb"
    return name[:255]


def legacy_collection_name(kb_name: str) -> str:
    """Collection name the Chroma Cloud backend used before owner scoping."""
    return kb_name


def owner_scoped_name(owner_id: UUID, kb_name: str) -> str:
    """Name both backends derive from the owner and ``kb_name``."""
    owner = str(owner_id)
    payload = f"{len(owner)}:{owner}{len(kb_name)}:{kb_name}"
    return f"lf_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


class StorageTarget:
    """Where one backend keeps a knowledge base's storage name in ``backend_config``.

    A plain class on purpose: Alembic loads revision files without registering
    them in ``sys.modules``, and ``@dataclass`` looks the module up there.
    """

    def __init__(
        self,
        *,
        label: str,
        backend_type: str,
        name_key: str,
        origin_key: str,
        shared_key: str,
        legacy_name: Callable[[str], str],
        override_predates_scoping: bool,
    ) -> None:
        self.label = label
        self.backend_type = backend_type
        self.name_key = name_key
        self.origin_key = origin_key
        self.shared_key = shared_key
        self.legacy_name = legacy_name
        # Whether older code honors ``name_key``, so a downgrade can pin to it.
        self.override_predates_scoping = override_predates_scoping

    def applies(self, backend_type: str, config: dict[str, Any]) -> bool:
        if backend_type != self.backend_type:
            return False
        if self.backend_type == "chroma":
            return str(config.get("mode", "local")).lower() == "cloud"
        return True


OPENSEARCH = StorageTarget(
    label="OpenSearch index",
    backend_type="opensearch",
    name_key="index_name",
    origin_key="index_name_origin",
    shared_key="legacy_shared_index",
    legacy_name=legacy_index_name,
    override_predates_scoping=True,
)
CHROMA_CLOUD = StorageTarget(
    label="Chroma Cloud collection",
    backend_type="chroma",
    name_key="collection_name",
    origin_key="collection_name_origin",
    shared_key="legacy_shared_collection",
    legacy_name=legacy_collection_name,
    override_predates_scoping=False,
)
TARGETS = (OPENSEARCH, CHROMA_CLOUD)


def _remote_rows(conn: sa.Connection) -> tuple[sa.TableClause, list[sa.RowMapping]]:
    knowledge_base = sa.table(
        "knowledge_base",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("backend_type", sa.String()),
        sa.column("backend_config", sa.JSON()),
    )
    rows = (
        conn.execute(
            sa.select(
                knowledge_base.c.id,
                knowledge_base.c.user_id,
                knowledge_base.c.name,
                knowledge_base.c.backend_type,
                knowledge_base.c.backend_config,
            ).where(knowledge_base.c.backend_type.in_({target.backend_type for target in TARGETS}))
        )
        .mappings()
        .all()
    )
    return knowledge_base, rows


def _rows_for(target: StorageTarget, rows: list[sa.RowMapping]) -> list[tuple[sa.RowMapping, dict[str, Any]]]:
    return [
        (row, row["backend_config"])
        for row in rows
        if isinstance(row["backend_config"], dict) and target.applies(row["backend_type"], row["backend_config"])
    ]


def _update_config(
    conn: sa.Connection, knowledge_base: sa.TableClause, row: sa.RowMapping, config: dict[str, Any]
) -> None:
    conn.execute(knowledge_base.update().where(knowledge_base.c.id == row["id"]).values(backend_config=config))


def _pin_legacy_names(
    conn: sa.Connection, knowledge_base: sa.TableClause, target: StorageTarget, rows: list[sa.RowMapping]
) -> None:
    owners_by_name: dict[str, set[UUID]] = defaultdict(set)
    unpinned: list[tuple[sa.RowMapping, dict[str, Any], str]] = []
    for row, config in _rows_for(target, rows):
        explicit = config.get(target.name_key)
        name = str(explicit) if explicit else target.legacy_name(row["name"])
        # Explicitly configured rows count as owners too: pinning a knowledge
        # base to storage another user also targets would keep sharing it.
        owners_by_name[name].add(row["user_id"])
        if not explicit:
            unpinned.append((row, config, name))

    for row, config, name in unpinned:
        shared = len(owners_by_name[name]) > 1
        reserved = _OWNER_SCOPED_NAME_RE.fullmatch(name.lower()) is not None
        if not shared and not reserved:
            pinned = {**config, target.name_key: name, target.origin_key: LEGACY_KB_NAME_ORIGIN}
            _update_config(conn, knowledge_base, row, pinned)
            continue
        reason = (
            "shares it with other users' knowledge bases" if shared else "its name is reserved for owner-scoped storage"
        )
        logger.warning(
            "Knowledge base %s (id %s, owner %s) used %s %s, but %s. It was not pinned: it now uses its own "
            "empty storage and %s is left untouched for an operator to resolve.",
            row["name"],
            row["id"],
            row["user_id"],
            target.label,
            name,
            reason,
            name,
        )
        _update_config(conn, knowledge_base, row, {**config, target.shared_key: name})


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("knowledge_base", conn):
        return
    knowledge_base, rows = _remote_rows(conn)
    for target in TARGETS:
        _pin_legacy_names(conn, knowledge_base, target, rows)


def downgrade() -> None:
    """Keep owner-scoped knowledge bases readable by older code where it can.

    Older code names unpinned storage from the knowledge base name alone. Rows
    pinned by ``upgrade`` already carry that name. Older OpenSearch code honors
    ``index_name``, so owner-scoped OpenSearch rows are pinned to their current
    index. Older Chroma Cloud code has no collection override, so owner-scoped
    Chroma Cloud rows fall back to the ``kb_name`` collection; each is logged.
    """
    conn = op.get_bind()
    if not migration.table_exists("knowledge_base", conn):
        return
    knowledge_base, rows = _remote_rows(conn)
    for target in TARGETS:
        for row, config in _rows_for(target, rows):
            if config.get(target.name_key):
                continue
            scoped = owner_scoped_name(row["user_id"], row["name"])
            if not target.override_predates_scoping:
                logger.warning(
                    "Knowledge base %s (id %s) uses %s %s, which older code cannot read; it will use %s %s instead.",
                    row["name"],
                    row["id"],
                    target.label,
                    scoped,
                    target.label,
                    target.legacy_name(row["name"]),
                )
                continue
            pinned = {**config, target.name_key: scoped, target.origin_key: OWNER_SCOPED_ORIGIN}
            _update_config(conn, knowledge_base, row, pinned)
