"""Offline rotation must preserve every encrypted location or roll back everything."""

import base64
import hashlib
import json

import pytest
from cryptography.fernet import Fernet, InvalidToken
from langflow.services.secrets.crypto import (
    decrypt_with_key,
    encrypt_sso_secret_with_key,
    encrypt_with_key,
    receipt_fingerprint,
)
from langflow.services.secrets.rotation import RotationError, audit, rotate
from sqlalchemy import create_engine, text


@pytest.fixture
def keys():
    return Fernet.generate_key().decode(), Fernet.generate_key().decode()


@pytest.fixture
def database(tmp_path, keys):
    old, _ = keys
    engine = create_engine(f"sqlite:///{tmp_path / 'live.db'}")
    with engine.begin() as conn:
        for ddl in (
            "CREATE TABLE variable (id TEXT PRIMARY KEY, type TEXT, value TEXT)",
            "CREATE TABLE trigger_cleanup (id TEXT PRIMARY KEY, encrypted_credential TEXT)",
            "CREATE TABLE connection_oauth (connection_id TEXT PRIMARY KEY, encrypted_verifier TEXT)",
            "CREATE TABLE job (job_id TEXT PRIMARY KEY, job_metadata JSON)",
            "CREATE TABLE sso_config (id TEXT PRIMARY KEY, client_secret_encrypted TEXT)",
            "CREATE TABLE mcp_server (id TEXT PRIMARY KEY, config JSON)",
            "CREATE TABLE secret_rotation (id TEXT PRIMARY KEY, instance_uid TEXT, "
            "old_fingerprint TEXT, new_fingerprint TEXT, "
            "backup_sha256 TEXT, rotated_values INTEGER, completed_at DATETIME)",
        ):
            conn.execute(text(ddl))
        for index in range(8):
            conn.execute(
                text("INSERT INTO variable VALUES (:id, 'Credential', :value)"),
                {"id": str(index), "value": encrypt_with_key(f"private-{index}", old)},
            )
        conn.execute(
            text("INSERT INTO trigger_cleanup VALUES ('cleanup', :value)"),
            {"value": encrypt_with_key("private-cleanup", old)},
        )
        conn.execute(
            text("INSERT INTO connection_oauth VALUES ('oauth', :value)"),
            {"value": encrypt_with_key("private-verifier", old)},
        )
        conn.execute(
            text("INSERT INTO job VALUES ('job', :value)"),
            {
                "value": json.dumps(
                    {
                        "request_overrides_format": "fernet-json-v1",
                        "request_overrides": encrypt_with_key(
                            '{"version":1,"overrides":{"globals":{"secret":"x"}}}', old
                        ),
                        "preserve": 1,
                    }
                )
            },
        )
        conn.execute(
            text("INSERT INTO sso_config VALUES ('sso', :value)"),
            {"value": encrypt_sso_secret_with_key("private-sso", old)},
        )
        conn.execute(
            text("INSERT INTO mcp_server VALUES ('mcp', :value)"),
            {
                "value": json.dumps(
                    {
                        "env": {"TOKEN": encrypt_with_key("private-mcp", old)},
                        "headers": {"Authorization": "legacy-plaintext"},
                    }
                )
            },
        )
    backup = tmp_path / "backup.db"
    backup.write_bytes((tmp_path / "live.db").read_bytes())
    yield engine, backup
    engine.dispose()


def rotation_options(database):
    engine, backup = database
    return {
        "engine": engine,
        "backup_file": backup,
        "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
        "writers_stopped": True,
    }


def test_audit_is_complete_read_only_and_never_returns_values(database, keys):
    engine, _ = database
    with engine.connect() as conn:
        before = conn.execute(text("SELECT value FROM variable")).fetchall()
        report = audit(conn, keys[0])
        assert report.encrypted == 13
        assert report.failures == []
        assert [(item.table, item.row_id) for item in report.plaintext] == [("mcp_server", "mcp")]
        assert "legacy-plaintext" not in repr(report)
        assert "private-" not in repr(report)
        assert before == conn.execute(text("SELECT value FROM variable")).fetchall()


def test_rotation_rewraps_all_rows_and_records_only_database_completion(database, keys):
    old, new = keys
    report = rotate(old_key=old, new_key=new, **rotation_options(database))
    assert report.encrypted == 13
    with database[0].connect() as conn:
        assert audit(conn, new).failures == []
        assert len(audit(conn, old).failures) == 13
        assert conn.execute(text("SELECT count(*) FROM secret_rotation")).scalar_one() == 1
        for row in conn.execute(text("SELECT value FROM variable")):
            assert decrypt_with_key(row[0], new).startswith("private-")
            with pytest.raises(InvalidToken):
                decrypt_with_key(row[0], old)
        assert json.loads(conn.execute(text("SELECT job_metadata FROM job")).scalar_one())["preserve"] == 1


def test_receipt_fingerprint_cannot_decrypt_short_root_ciphertext(database, keys):
    new_key = "short-new-root"
    rotate(old_key=keys[0], new_key=new_key, **rotation_options(database))
    with database[0].connect() as conn:
        fingerprint = conn.execute(text("SELECT new_fingerprint FROM secret_rotation")).scalar_one()
        ciphertext = conn.execute(text("SELECT value FROM variable WHERE id='0'")).scalar_one()
    exposed_key = base64.urlsafe_b64encode(bytes.fromhex(fingerprint))
    with pytest.raises(InvalidToken):
        Fernet(exposed_key).decrypt(ciphertext.encode())


def test_failure_after_first_three_rows_rolls_back_everything_without_marker(database, keys):
    engine, _ = database
    with engine.begin() as conn:
        conn.execute(text("UPDATE variable SET value='broken-private-ciphertext' WHERE id='7'"))
        before = conn.execute(text("SELECT value FROM variable ORDER BY id")).fetchall()
    with pytest.raises(RotationError) as exc:
        rotate(old_key=keys[0], new_key=keys[1], **rotation_options(database))
    assert "broken-private-ciphertext" not in str(exc.value)
    assert "private-" not in repr(exc.value.report)
    assert exc.value.report.failures[0].row_id == "7"
    with engine.connect() as conn:
        assert before == conn.execute(text("SELECT value FROM variable ORDER BY id")).fetchall()
        assert conn.execute(text("SELECT count(*) FROM secret_rotation")).scalar_one() == 0


@pytest.mark.parametrize(("option", "value"), [("writers_stopped", False), ("backup_sha256", "0" * 64)])
def test_rotation_requires_stopped_writers_and_verified_backup(database, keys, option, value):
    options = rotation_options(database)
    options[option] = value
    with pytest.raises(RotationError):
        rotate(old_key=keys[0], new_key=keys[1], **options)
    with database[0].connect() as conn:
        assert audit(conn, keys[0]).failures == []
        assert conn.execute(text("SELECT count(*) FROM secret_rotation")).scalar_one() == 0


def test_unknown_job_override_format_is_a_failure(database, keys):
    with database[0].begin() as conn:
        conn.execute(
            text("UPDATE job SET job_metadata=:value"),
            {"value": json.dumps({"request_overrides": "private-raw", "request_overrides_format": "unknown"})},
        )
        report = audit(conn, keys[0])
        assert [(item.table, item.row_id) for item in report.failures] == [("job", "job")]
        assert "private-raw" not in repr(report)


def test_malformed_ciphertext_cannot_silently_become_legacy_plaintext(database, keys):
    with database[0].begin() as conn:
        conn.execute(
            text("UPDATE mcp_server SET config=:value"), {"value": json.dumps({"env": {"TOKEN": "gAAAA-truncated"}})}
        )
        report = audit(conn, keys[0])
        assert [(item.table, item.row_id) for item in report.failures] == [("mcp_server", "mcp")]


def test_participant_failure_rolls_back_rewrap_and_has_no_receipt(database, keys):
    class Participant:
        def locations(self, _conn):
            return ()

        def preflight(self):
            pass

        def prepare(self, _conn):
            msg = "private-participant-error"
            raise RuntimeError(msg)

    with pytest.raises(RotationError) as exc:
        rotate(old_key=keys[0], new_key=keys[1], participants=[Participant()], **rotation_options(database))
    assert "private-participant-error" not in str(exc.value)
    with database[0].connect() as conn:
        assert audit(conn, keys[0]).failures == []
        assert conn.execute(text("SELECT count(*) FROM secret_rotation")).scalar_one() == 0


def test_cli_reads_named_env_keys_and_emits_bound_receipt(database, keys, monkeypatch, tmp_path):
    from langflow.cli.secrets import secrets_app
    from typer.testing import CliRunner

    monkeypatch.setenv("TEST_ROTATION_OLD", keys[0])
    monkeypatch.setenv("TEST_ROTATION_NEW", keys[1])
    monkeypatch.setenv("TEST_ROTATION_DATABASE", str(database[0].url))
    monkeypatch.setattr("langflow.cli.secrets.load_participants", lambda: ())
    receipt_file = tmp_path / "receipt.json"
    result = CliRunner().invoke(
        secrets_app,
        [
            "rotate",
            "--old-key-env",
            "TEST_ROTATION_OLD",
            "--new-key-env",
            "TEST_ROTATION_NEW",
            "--database-url-env",
            "TEST_ROTATION_DATABASE",
            "--writers-stopped",
            "--backup-file",
            str(database[1]),
            "--backup-sha256",
            rotation_options(database)["backup_sha256"],
            "--instance-uid",
            "instance-123",
            "--receipt-file",
            str(receipt_file),
        ],
    )
    assert result.exit_code == 0, result.output
    assert keys[0] not in result.output
    assert keys[1] not in result.output
    receipt = json.loads(receipt_file.read_text())
    assert receipt["instance_uid"] == "instance-123"
    assert receipt["previous_key_fingerprint"] == receipt_fingerprint(keys[0])
    assert receipt["key_fingerprint"] == receipt_fingerprint(keys[1])
    assert receipt["status"] == "completed"
    assert json.loads(result.output)["receipt"] == receipt
    with database[0].connect() as conn:
        assert conn.execute(text("SELECT instance_uid FROM secret_rotation")).scalar_one() == "instance-123"
        assert (
            conn.execute(text("SELECT old_fingerprint FROM secret_rotation")).scalar_one()
            == receipt["previous_key_fingerprint"]
        )
        assert (
            conn.execute(text("SELECT new_fingerprint FROM secret_rotation")).scalar_one() == receipt["key_fingerprint"]
        )


def test_enterprise_storage_cannot_be_skipped_without_participant(database, keys):
    with database[0].begin() as conn:
        conn.execute(text("CREATE TABLE sso_connection_revision (id TEXT PRIMARY KEY, revision_data JSON)"))
        with pytest.raises(RotationError, match="matching rotation participant"):
            audit(conn, keys[0])
