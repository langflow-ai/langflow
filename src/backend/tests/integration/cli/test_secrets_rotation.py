"""Exercise offline secrets commands through the installed CLI and real migrations."""

import hashlib
import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import InvalidToken
from langflow.__main__ import app
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.secrets.crypto import decrypt_with_key, encrypt_with_key, receipt_fingerprint
from sqlalchemy import create_engine, text
from sqlmodel import Session
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def _start_app():
    """Offline commands operate while the application is stopped."""


def test_top_level_cli_audits_and_rotates_a_migrated_database(tmp_path, monkeypatch):
    """Apply the real schema and verify audit, rotation, and receipt agreement."""
    database_file = tmp_path / "langflow.db"
    database_url = f"sqlite:///{database_file}"
    config = Config()
    workspace = Path(__file__).resolve().parents[5]
    config.set_main_option("script_location", str(workspace / "src/backend/base/langflow/alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_file}")
    command.upgrade(config, "head")
    old_key, new_key = "integration-old-root", "integration-new-root"
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            user = User(username="rotation-user", password="")
            session.add(user)
            session.flush()
            session.add(
                Variable(
                    name="credential",
                    type="Credential",
                    value=encrypt_with_key("private-value", old_key),
                    user_id=user.id,
                )
            )
            session.commit()
        backup = tmp_path / "backup.db"
        backup.write_bytes(database_file.read_bytes())
        monkeypatch.setenv("TEST_ROTATION_DATABASE", database_url)
        monkeypatch.setenv("TEST_ROTATION_OLD", old_key)
        monkeypatch.setenv("TEST_ROTATION_NEW", new_key)
        runner = CliRunner()
        audit_args = [
            "secrets",
            "audit",
            "--key-env",
            "TEST_ROTATION_OLD",
            "--database-url-env",
            "TEST_ROTATION_DATABASE",
        ]
        result = runner.invoke(app, audit_args)
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["encrypted"] == 1
        receipt_file = tmp_path / "receipt.json"
        result = runner.invoke(
            app,
            [
                "secrets",
                "rotate",
                "--old-key-env",
                "TEST_ROTATION_OLD",
                "--new-key-env",
                "TEST_ROTATION_NEW",
                "--database-url-env",
                "TEST_ROTATION_DATABASE",
                "--writers-stopped",
                "--backup-file",
                str(backup),
                "--backup-sha256",
                hashlib.sha256(backup.read_bytes()).hexdigest(),
                "--instance-uid",
                "test-instance",
                "--receipt-file",
                str(receipt_file),
            ],
        )
        assert result.exit_code == 0, result.output
        receipt = json.loads(receipt_file.read_text())
        assert json.loads(result.output)["receipt"] == receipt
        assert receipt["key_fingerprint"] == receipt_fingerprint(new_key)
        with engine.connect() as connection:
            ciphertext = connection.execute(text("SELECT value FROM variable")).scalar_one()
            assert decrypt_with_key(ciphertext, new_key) == "private-value"
            with pytest.raises(InvalidToken):
                decrypt_with_key(ciphertext, old_key)
            row = connection.execute(text("SELECT * FROM secret_rotation")).mappings().one()
            assert row["id"] == receipt["rotation_id"]
            assert row["old_fingerprint"] == receipt["previous_key_fingerprint"]
            assert row["new_fingerprint"] == receipt["key_fingerprint"]
        old_audit = runner.invoke(app, audit_args)
        assert old_audit.exit_code == 1
        new_audit = runner.invoke(app, [arg.replace("TEST_ROTATION_OLD", "TEST_ROTATION_NEW") for arg in audit_args])
        assert new_audit.exit_code == 0, new_audit.output
        for output in (result.output, old_audit.output, new_audit.output):
            assert old_key not in output
            assert new_key not in output
            assert "private-value" not in output
    finally:
        engine.dispose()
