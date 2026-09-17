"""Pin existing OpenSearch knowledge bases to their pre-scoping index.

Phase: MIGRATE
Revision ID: 386662af02e9
Revises: 1d28fd31a982
Create Date: 2026-09-17

OpenSearch knowledge bases without an explicit ``backend_config.index_name``
used to read and write an index named from the knowledge base name alone.
Names are unique per user, not globally, so two users' knowledge bases with the
same name shared one index: each could read, count, and delete the other's
chunks. The backend now derives an owner-scoped index instead, which would
leave every existing knowledge base pointing at a new, empty index.

This migration keeps existing data in service without keeping the leak:

* When every knowledge base that resolves to a legacy index belongs to one
  owner, each of them is pinned to that index through ``index_name``, with
  ``index_name_origin: legacy_kb_name``. Nothing moves on the cluster.
* When knowledge bases of several owners resolve to the same legacy index,
  their chunks are already mixed and cannot be attributed to one owner. Those
  knowledge bases are not pinned: they move to their own empty owner-scoped
  index, the shared index is left untouched, and the row records
  ``legacy_shared_index`` so the backend logs a warning until an operator
  resolves it.

Only the database is changed. The OpenSearch cluster is never contacted.
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
    from collections.abc import Sequence
    from uuid import UUID

revision: str = "386662af02e9"  # pragma: allowlist secret
down_revision: str | None = "1d28fd31a982"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger(__name__)

OPENSEARCH_BACKEND_TYPE = "opensearch"
INDEX_NAME_KEY = "index_name"
INDEX_NAME_ORIGIN_KEY = "index_name_origin"
LEGACY_KB_NAME_ORIGIN = "legacy_kb_name"
OWNER_SCOPED_ORIGIN = "owner_scoped"
LEGACY_SHARED_INDEX_KEY = "legacy_shared_index"

# Frozen copies of the naming rules at the time of this revision. Migrations
# must not follow later edits to application code.
_LEGACY_FORBIDDEN = re.compile(r'[\\/*?"<>|,#: \t\n\r]+')
_LEGACY_NON_ALNUM = re.compile(r"[^a-z0-9._-]+")


def legacy_index_name(kb_name: str) -> str:
    """Index name the OpenSearch backend derived from ``kb_name`` before owner scoping."""
    name = (kb_name or "").strip().lower()
    name = _LEGACY_FORBIDDEN.sub("_", name)
    name = _LEGACY_NON_ALNUM.sub("_", name)
    name = name.lstrip("-_+.")
    if not name or name in {".", ".."}:
        name = "kb"
    return name[:255]


def owner_scoped_index_name(owner_id: UUID, kb_name: str) -> str:
    """Index name the OpenSearch backend derives from the owner and ``kb_name``."""
    owner = str(owner_id)
    payload = f"{len(owner)}:{owner}{len(kb_name)}:{kb_name}"
    return f"lf_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def _opensearch_rows(conn: sa.Connection) -> tuple[sa.TableClause, list[sa.RowMapping]]:
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
                knowledge_base.c.backend_config,
            ).where(knowledge_base.c.backend_type == OPENSEARCH_BACKEND_TYPE)
        )
        .mappings()
        .all()
    )
    return knowledge_base, rows


def _update_config(
    conn: sa.Connection, knowledge_base: sa.TableClause, row: sa.RowMapping, config: dict[str, Any]
) -> None:
    conn.execute(knowledge_base.update().where(knowledge_base.c.id == row["id"]).values(backend_config=config))


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("knowledge_base", conn):
        return
    knowledge_base, rows = _opensearch_rows(conn)

    owners_by_index: dict[str, set[UUID]] = defaultdict(set)
    unpinned: list[tuple[sa.RowMapping, dict[str, Any], str]] = []
    for row in rows:
        config = row["backend_config"]
        if not isinstance(config, dict):
            continue
        explicit = config.get(INDEX_NAME_KEY)
        index_name = str(explicit) if explicit else legacy_index_name(row["name"])
        # Explicitly configured rows count as owners too: pinning a knowledge
        # base to an index another user also targets would keep sharing it.
        owners_by_index[index_name].add(row["user_id"])
        if not explicit:
            unpinned.append((row, config, index_name))

    for row, config, index_name in unpinned:
        if len(owners_by_index[index_name]) == 1:
            pinned = {**config, INDEX_NAME_KEY: index_name, INDEX_NAME_ORIGIN_KEY: LEGACY_KB_NAME_ORIGIN}
            _update_config(conn, knowledge_base, row, pinned)
            continue
        logger.warning(
            "Knowledge base %s (id %s, owner %s) shares OpenSearch index %s with other users' knowledge bases. "
            "It was not pinned: it now uses its own empty index and %s is left untouched for an operator to resolve.",
            row["name"],
            row["id"],
            row["user_id"],
            index_name,
            index_name,
        )
        _update_config(conn, knowledge_base, row, {**config, LEGACY_SHARED_INDEX_KEY: index_name})


def downgrade() -> None:
    """Pin owner-scoped knowledge bases so older code keeps reading their index.

    Older code names an unpinned index from the knowledge base name alone. Rows
    pinned by ``upgrade`` already carry that name and are left as they are.
    """
    conn = op.get_bind()
    if not migration.table_exists("knowledge_base", conn):
        return
    knowledge_base, rows = _opensearch_rows(conn)
    for row in rows:
        config = row["backend_config"]
        if not isinstance(config, dict) or config.get(INDEX_NAME_KEY):
            continue
        pinned = {
            **config,
            INDEX_NAME_KEY: owner_scoped_index_name(row["user_id"], row["name"]),
            INDEX_NAME_ORIGIN_KEY: OWNER_SCOPED_ORIGIN,
        }
        _update_config(conn, knowledge_base, row, pinned)
