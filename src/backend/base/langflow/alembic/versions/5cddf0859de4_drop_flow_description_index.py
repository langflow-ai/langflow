"""Drop the B-tree index on the free-text flow description.

Revision ID: 5cddf0859de4
Revises: a09a699afb52
Create Date: 2026-11-25

Phase: EXPAND

No query filters, sorts, or joins on flow.description, and PostgreSQL rejects a
B-tree entry above about 2,700 bytes, so a long or multibyte description failed
the insert. Removing the index is compatible with every app version.

Downgrade recreates ix_flow_description. On PostgreSQL that fails, and the
transaction rolls back with no data change, while any description is too large
for a B-tree entry. Shorten those descriptions before rolling back: the previous
release cannot store them either.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5cddf0859de4"  # pragma: allowlist secret
down_revision: str | None = "a09a699afb52"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "ix_flow_description"


def upgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="flow", if_exists=True)


def downgrade() -> None:
    op.create_index(_INDEX_NAME, "flow", ["description"], unique=False, if_not_exists=True)
