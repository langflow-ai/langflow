"""Backfill existing effective role assignments with manual grant sources.

Phase: MIGRATE
Revision ID: cp02a2b3c4d5
Revises: cp01a2b3c4d5
Create Date: 2026-07-30

The data migration is idempotent and leaves effective assignments untouched.
Its downgrade is intentionally a no-op: removing provenance before the schema
downgrade would make a partially downgraded application misclassify grants.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "cp02a2b3c4d5"  # pragma: allowlist secret
down_revision: str | None = "cp01a2b3c4d5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BATCH_SIZE = 1000


def upgrade() -> None:
    conn = op.get_bind()
    metadata = sa.MetaData()
    assignment = sa.Table("authz_role_assignment", metadata, autoload_with=conn)
    grant = sa.Table("authz_role_assignment_grant", metadata, autoload_with=conn)

    existing_source = sa.exists(sa.select(grant.c.id).where(grant.c.assignment_id == assignment.c.id))
    last_assignment_id = None

    def new_grant_id():
        value = uuid4()
        return value.hex if conn.dialect.name == "sqlite" else value

    while True:
        query = sa.select(
            assignment.c.id,
            assignment.c.assigned_by,
            assignment.c.assigned_at,
        ).where(~existing_source)
        if last_assignment_id is not None:
            query = query.where(assignment.c.id > last_assignment_id)

        rows = conn.execute(query.order_by(assignment.c.id).limit(_BATCH_SIZE)).all()
        if not rows:
            return

        conn.execute(
            grant.insert(),
            [
                {
                    "id": new_grant_id(),
                    "assignment_id": row.id,
                    "source_kind": "manual",
                    "provider_id": None,
                    "external_group": None,
                    "administrative_actor": row.assigned_by,
                    "created_at": row.assigned_at,
                    "updated_at": row.assigned_at,
                }
                for row in rows
            ],
        )
        last_assignment_id = rows[-1].id


def downgrade() -> None:
    pass
