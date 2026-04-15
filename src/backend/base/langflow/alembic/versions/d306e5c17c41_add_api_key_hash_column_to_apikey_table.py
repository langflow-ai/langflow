"""add api_key_hash column to apikey table

Phase: EXPAND

Adds a SHA-256 hash column for O(1) indexed API key lookup.
Backfills hashes for all existing keys that can be decrypted.
Legacy keys that fail decryption (orphaned) get no hash and
are matched via decrypt-and-compare fallback at runtime.

Revision ID: d306e5c17c41
Revises: 8255e9fc18d9
Create Date: 2026-04-09 13:44:08.428630

"""

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "d306e5c17c41"  # pragma: allowlist secret
down_revision: str | None = "8255e9fc18d9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "apikey"
COLUMN_NAME = "api_key_hash"
INDEX_NAME = "ix_apikey_api_key_hash"


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _backfill_hashes(conn, decrypt_api_key) -> tuple[int, int, int, int]:
    """Backfill api_key_hash for rows where it is NULL.

    Decrypts each row, groups by plaintext, and only hashes unique-plaintext
    rows. Duplicate-plaintext groups are left with NULL hash so that the
    runtime fast-path lookup can never return multiple matches and fail
    closed. The runtime slow-path will match and backfill exactly one row
    per group on first use, leaving the remaining NULL rows as harmless
    orphans.

    Returns ``(backfilled, skipped, duplicate_groups, duplicate_rows)``.
    """
    rows = conn.execute(
        sa.text(f"SELECT id, api_key FROM {TABLE_NAME} WHERE api_key_hash IS NULL")  # noqa: S608
    ).fetchall()
    if not rows:
        return 0, 0, 0, 0

    # First pass: decrypt every row and group by plaintext.
    plaintext_to_ids: dict[str, list] = {}
    skipped = 0
    for row in rows:
        stored_key = row[1]
        if not stored_key:
            continue

        # Plaintext keys (1.6.x style) don't start with gAAAAA
        if not stored_key.startswith("gAAAAA"):
            plaintext = stored_key
        else:
            # decrypt_api_key returns "" on failure (never raises for decryption errors)
            try:
                plaintext = decrypt_api_key(stored_key)
            except Exception:  # noqa: BLE001
                skipped += 1
                continue
            if not plaintext:
                skipped += 1
                continue

        plaintext_to_ids.setdefault(plaintext, []).append(row[0])

    # Second pass: backfill only unique-plaintext rows.
    backfilled = 0
    duplicate_groups = 0
    duplicate_rows = 0
    for plaintext, ids in plaintext_to_ids.items():
        if len(ids) > 1:
            duplicate_groups += 1
            duplicate_rows += len(ids)
            continue
        conn.execute(
            sa.text(f"UPDATE {TABLE_NAME} SET api_key_hash = :hash WHERE id = :id"),  # noqa: S608
            {"hash": _hash_key(plaintext), "id": ids[0]},
        )
        backfilled += 1

    return backfilled, skipped, duplicate_groups, duplicate_rows


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return

    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
            batch_op.add_column(sa.Column(COLUMN_NAME, sa.String(), nullable=True))
            batch_op.create_index(INDEX_NAME, [COLUMN_NAME])

    try:
        from langflow.services.auth.utils import decrypt_api_key
    except ImportError:
        print(  # noqa: T201
            "WARNING: Could not import auth utilities. "
            "API key hash backfill skipped. Hashes will be computed at runtime on first use."
        )
        return

    backfilled, skipped, duplicate_groups, duplicate_rows = _backfill_hashes(conn, decrypt_api_key)

    if backfilled:
        print(f"Backfilled hashes for {backfilled} API key(s).")  # noqa: T201
    if skipped:
        print(  # noqa: T201
            f"WARNING: {skipped} API key(s) could not be decrypted during hash backfill. "
            "These will use the slower decrypt-and-compare fallback at runtime."
        )
    if duplicate_groups:
        print(  # noqa: T201
            f"WARNING: Skipped hashing {duplicate_groups} duplicate-plaintext key group(s) "
            f"({duplicate_rows} total rows). Auth continues to work via the slow-path fallback. "
            "Query the apikey table directly to identify affected rows if cleanup is needed."
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists(TABLE_NAME, conn):
        return
    if not migration.column_exists(TABLE_NAME, COLUMN_NAME, conn):
        return

    with op.batch_alter_table(TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME)
        batch_op.drop_column(COLUMN_NAME)
