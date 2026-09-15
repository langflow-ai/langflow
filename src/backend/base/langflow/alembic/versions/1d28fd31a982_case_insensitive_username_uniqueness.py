"""Enforce case-insensitive username uniqueness.

Phase: EXPAND
Revision ID: 1d28fd31a982
Revises: b4c7d2e8f1a3
Create Date: 2026-09-15

``user.username`` was only unique byte-for-byte, so "owner1" and "Owner1"
could coexist as two entirely separate accounts — confusing at best (two
lookalike identities with no visual distinction) and a lookalike-account risk
at worst (nothing stopped registering "Admin" next to a real "admin"). A
functional unique index on ``lower(username)`` closes this at the database
level, covering every creation path (signup, admin "add user", SSO
auto-provisioning), not just one endpoint's own pre-check.

``if_not_exists``/``if_exists`` make this idempotent without a reflection
check: SQLAlchemy's ``Inspector.get_indexes()`` can't reflect expression-based
indexes on SQLite at all (see ``alembic/warning_filters.py``'s identical note
for ``ix_message_session_metadata_*``), so a manual "does this index already
exist" check would always read back False there and re-issue a doomed
``CREATE INDEX`` on every rerun.

Refuses to run if the existing data already has a case-insensitive
collision: silently merging or renaming a real account during a migration
could destroy someone's access without consent, so this is deliberately a
loud failure that names the offending usernames and asks an operator to
resolve them by hand (rename or delete one of each pair) before upgrading,
rather than guessing which account should win.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "1d28fd31a982"  # pragma: allowlist secret
down_revision: str | None = "b4c7d2e8f1a3"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_user_username_lower"


def _existing_case_insensitive_collisions(conn) -> list[str]:
    rows = conn.execute(
        sa.text(
            'SELECT lower(username) AS normalized, count(*) AS total FROM "user" '
            "GROUP BY normalized HAVING count(*) > 1"
        )
    ).fetchall()
    return [row[0] for row in rows]


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("user", conn):
        return
    collisions = _existing_case_insensitive_collisions(conn)
    if collisions:
        msg = (
            "Cannot enforce case-insensitive username uniqueness: these usernames already "
            f"collide case-insensitively and must be resolved (renamed or one deleted) before "
            f"upgrading: {sorted(collisions)}"
        )
        raise RuntimeError(msg)
    op.create_index(
        INDEX_NAME,
        "user",
        [sa.text("lower(username)")],
        unique=True,
        if_not_exists=True,
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("user", conn):
        return
    op.drop_index(INDEX_NAME, table_name="user", if_exists=True)
