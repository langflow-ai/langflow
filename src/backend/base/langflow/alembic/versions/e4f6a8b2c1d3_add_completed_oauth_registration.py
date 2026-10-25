"""Track the registration of the last completed OAuth grant.

Revision ID: e4f6a8b2c1d3
Revises: e5a7c9b1d3f2
Create Date: 2026-10-23

Phase: EXPAND
Safe to rollback: YES
Services compatible: Versions that do not read connection_oauth.completed_registration_id
"""

import json
import re
from collections.abc import Callable, Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "e4f6a8b2c1d3"  # pragma: allowlist secret -- migration revision identifier
down_revision: str | None = "e5a7c9b1d3f2"  # pragma: allowlist secret -- migration revision identifier
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MAX_REGISTRATION_ID_LENGTH = 120


def _completed_registration_id(encrypted_payload: str, decrypt_api_key: Callable[[str], str]) -> str | None:
    try:
        plaintext = decrypt_api_key(encrypted_payload)
        # Native auth deliberately accepts plaintext API keys. Connection
        # grants have always been encrypted and cannot use that fallback.
        if not plaintext or plaintext == encrypted_payload:
            return None
        payload = json.loads(plaintext)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return None
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        return None
    oauth = payload.get("oauth")
    if not isinstance(oauth, dict):
        return None
    config_digest = oauth.get("config_digest")
    generation = oauth.get("generation")
    if not isinstance(config_digest, str) or re.fullmatch(r"[0-9a-f]{64}", config_digest) is None:
        return None
    if not isinstance(generation, str):
        return None
    try:
        UUID(generation)
    except ValueError:
        return None
    registration_id = oauth.get("registration_id")
    if not isinstance(registration_id, str):
        return None
    if registration_id != registration_id.strip():
        return None
    return registration_id if 0 < len(registration_id) <= _MAX_REGISTRATION_ID_LENGTH else None


def upgrade() -> None:
    conn = op.get_bind()
    if migration.column_exists("connection_oauth", "completed_registration_id", conn):
        return
    with op.batch_alter_table("connection_oauth") as batch_op:
        batch_op.add_column(sa.Column("completed_registration_id", sa.String(length=120), nullable=True))
    op.create_index(
        "ix_connection_oauth_completed_registration_id",
        "connection_oauth",
        ["completed_registration_id"],
        unique=False,
    )
    from langflow.services.auth.utils import decrypt_api_key

    secrets = conn.exec_driver_sql(
        "SELECT s.connection_id, s.encrypted_payload FROM connection_secret AS s "
        "JOIN connection_oauth AS o ON o.connection_id = s.connection_id"
    )
    for connection_id, encrypted_payload in secrets:
        registration_id = _completed_registration_id(encrypted_payload, decrypt_api_key)
        if registration_id is not None:
            conn.execute(
                sa.text(
                    "UPDATE connection_oauth SET completed_registration_id = :registration_id "
                    "WHERE connection_id = :connection_id"
                ),
                {"registration_id": registration_id, "connection_id": connection_id},
            )


def downgrade() -> None:
    conn = op.get_bind()
    if not migration.column_exists("connection_oauth", "completed_registration_id", conn):
        return
    indexes = {index["name"] for index in sa.inspect(conn).get_indexes("connection_oauth")}
    if "ix_connection_oauth_completed_registration_id" in indexes:
        op.drop_index("ix_connection_oauth_completed_registration_id", table_name="connection_oauth")
    with op.batch_alter_table("connection_oauth") as batch_op:
        batch_op.drop_column("completed_registration_id")
