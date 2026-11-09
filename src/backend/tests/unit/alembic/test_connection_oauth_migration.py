"""Backfill and index coverage for completed OAuth registrations."""

import json
from uuid import uuid4

from alembic import command
from langflow.services.auth.utils import encrypt_api_key
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "e5a7c9b1d3f2"  # pragma: allowlist secret
_REVISION = "e4f6a8b2c1d3"  # pragma: allowlist secret
_INDEX = "ix_connection_oauth_completed_registration_id"


def _grant_payload(registration_id: object) -> dict:
    return {
        "version": 1,
        "access_token": "stored",
        "oauth": {
            "registration_id": registration_id,
            "config_digest": "0" * 64,
            "generation": str(uuid4()),
        },
    }


def test_oauth_migration_round_trip(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, "f3b6a9d2e4c1")  # pragma: allowlist secret - migration revision
    command.upgrade(config, "a7d8e9f0b1c2")  # pragma: allowlist secret - migration revision
    engine = create_engine(_engine_url(db_url))
    with engine.connect() as connection:
        columns = {col["name"] for col in inspect(connection).get_columns("connection_oauth")}
        assert {"state_digest", "encrypted_verifier", "generation"} <= columns
        assert "access_token" not in columns
    engine.dispose()
    command.downgrade(config, "f3b6a9d2e4c1")  # pragma: allowlist secret - migration revision
    engine = create_engine(_engine_url(db_url))
    with engine.connect() as connection:
        assert "connection_oauth" not in inspect(connection).get_table_names()
        assert "connection" in inspect(connection).get_table_names()
    engine.dispose()


def _seed_legacy_grant(
    connection,
    user_id,
    connection_id,
    name,
    status,
    status_reason,
    registration_id,
    secret_payload,
    encrypted_payload,
):
    connection.execute(
        text(
            "INSERT INTO connection (id, owner_id, provider_key, name, display_name, ownership_mode, status, "
            "status_reason, health, granted_scopes, executing_identity, allow_non_interactive, created_at, updated_at) "
            "VALUES (:id, :owner_id, 'slack', :name, 'Slack', 'user', :status, :status_reason, 'healthy', '[]', "
            '\'{"identity":"bot"}\', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
        ),
        {
            "id": connection_id,
            "owner_id": user_id,
            "name": name,
            "status": status,
            "status_reason": status_reason,
        },
    )
    connection.execute(
        text(
            "INSERT INTO connection_oauth (connection_id, generation, user_id, registration_id, config_digest, "
            "state_digest, scopes, expires_at) VALUES (:connection_id, :generation, :user_id, :registration_id, "
            ":config_digest, NULL, '[]', CURRENT_TIMESTAMP)"
        ),
        {
            "connection_id": connection_id,
            "generation": str(uuid4()),
            "user_id": user_id,
            "registration_id": registration_id,
            "config_digest": "0" * 64,
        },
    )
    if secret_payload is not None:
        encrypted_payload = encrypt_api_key(json.dumps(secret_payload))
    if encrypted_payload is not None:
        connection.execute(
            text("INSERT INTO connection_secret (connection_id, encrypted_payload) VALUES (:id, :payload)"),
            {"id": connection_id, "payload": encrypted_payload},
        )


def test_completed_registration_backfill_index_and_downgrade(db_url):  # noqa: F811
    config = _make_alembic_cfg(db_url)
    command.upgrade(config, _PRIOR_REVISION)
    engine = create_engine(_engine_url(db_url))
    owner_id = str(uuid4())
    grants = {
        "legacy-ready": (
            "ready",
            None,
            "legacy-app",
            _grant_payload("legacy-app"),
            None,
        ),
        "legacy-pending": (
            "pending",
            None,
            "legacy-app",
            _grant_payload("legacy-app"),
            None,
        ),
        "legacy-failed": (
            "ready",
            "oauth-failed",
            "new-attempt",
            _grant_payload("previous-app"),
            None,
        ),
        "legacy-manual": ("ready", None, "legacy-app", {"version": 1, "access_token": "stored"}, None),
        "legacy-incomplete": ("ready", None, "legacy-app", None, None),
        "legacy-pending-incomplete": ("pending", None, "legacy-app", None, None),
        "legacy-failed-incomplete": ("ready", "oauth-failed", "legacy-app", None, None),
        "legacy-undecryptable": ("ready", None, "legacy-app", None, "not-a-valid-envelope"),
        "legacy-malformed": (
            "ready",
            None,
            "legacy-app",
            _grant_payload(123),
            None,
        ),
        "legacy-blank": (
            "ready",
            None,
            "legacy-app",
            _grant_payload(" "),
            None,
        ),
        "legacy-plaintext": ("ready", None, "legacy-app", None, json.dumps(_grant_payload("untrusted-app"))),
        "legacy-no-token": ("ready", None, "legacy-app", {**_grant_payload("legacy-app"), "access_token": ""}, None),
        "legacy-bad-version": ("ready", None, "legacy-app", {**_grant_payload("legacy-app"), "version": 2}, None),
        "legacy-bad-oauth": (
            "ready",
            None,
            "legacy-app",
            {**_grant_payload("legacy-app"), "oauth": {"registration_id": "legacy-app"}},
            None,
        ),
    }
    expected = {
        "legacy-ready": "legacy-app",
        "legacy-pending": "legacy-app",
        "legacy-failed": "previous-app",
        "legacy-manual": None,
        "legacy-incomplete": None,
        "legacy-pending-incomplete": None,
        "legacy-failed-incomplete": None,
        "legacy-undecryptable": None,
        "legacy-malformed": None,
        "legacy-blank": None,
        "legacy-plaintext": None,
        "legacy-no-token": None,
        "legacy-bad-version": None,
        "legacy-bad-oauth": None,
    }
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO "user" (id, username, password, is_active, is_superuser, create_at, updated_at) '
                    "VALUES (:id, :username, 'x', true, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": owner_id, "username": f"oauth-owner-{owner_id}"},
            )
            for name, values in grants.items():
                _seed_legacy_grant(connection, owner_id, str(uuid4()), name, *values)

        command.upgrade(config, _REVISION)
        with engine.connect() as connection:
            stored = dict(
                connection.execute(
                    text(
                        "SELECT c.name, o.completed_registration_id FROM connection_oauth AS o "
                        "JOIN connection AS c ON c.id = o.connection_id"
                    )
                ).all()
            )
            assert stored == expected
            assert _INDEX in {index["name"] for index in inspect(connection).get_indexes("connection_oauth")}

        command.downgrade(config, _PRIOR_REVISION)
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert "completed_registration_id" not in {
                column["name"] for column in inspector.get_columns("connection_oauth")
            }
            assert _INDEX not in {index["name"] for index in inspector.get_indexes("connection_oauth")}
    finally:
        engine.dispose()
