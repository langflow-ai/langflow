"""Tests for the secret key migration script."""

import hashlib
import importlib.util
import json
import os
import secrets
import stat
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken
from httpx import AsyncClient
from langflow.services.auth.utils import _ensure_legacy_fernet_key, ensure_fernet_key
from langflow.services.deps import get_settings_service
from langflow.services.variable.constants import CREDENTIAL_TYPE
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.schema import CreateSchema, DropSchema


@pytest.fixture(scope="module")
def migrate_module():
    """Load the migrate_secret_key module from scripts directory."""
    # Test file is at: src/backend/tests/unit/scripts/test_migrate_secret_key.py
    # Script is at: scripts/migrate_secret_key.py
    # Need to go up 5 levels to repo root, then into scripts/
    test_file = Path(__file__).resolve()
    repo_root = test_file.parents[5]  # Goes to langflow repo root
    script_path = repo_root / "scripts" / "migrate_secret_key.py"

    if not script_path.exists():
        pytest.skip(f"migrate_secret_key.py script not found at {script_path}")

    spec = importlib.util.spec_from_file_location("migrate_secret_key", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["migrate_secret_key"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def old_key():
    """Generate a valid old secret key."""
    return secrets.token_urlsafe(32)


@pytest.fixture
def new_key():
    """Generate a valid new secret key."""
    return secrets.token_urlsafe(32)


@pytest.fixture
def short_old_key():
    """A short key that triggers the seed-based generation."""
    return "short-key"


@pytest.fixture
def short_new_key():
    """A different short key."""
    return "other-short"


@pytest.fixture
def sqlite_db():
    """Create an in-memory SQLite database with the required tables."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(
            text("""
            CREATE TABLE "user" (
                id TEXT PRIMARY KEY,
                store_api_key TEXT
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE variable (
                id TEXT PRIMARY KEY,
                name TEXT,
                value TEXT,
                type TEXT
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE folder (
                id TEXT PRIMARY KEY,
                name TEXT,
                auth_settings TEXT
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE sso_config (
                id TEXT PRIMARY KEY,
                client_secret_encrypted TEXT
            )
        """)
        )
        conn.commit()
    return engine


class TestEnsureValidKey:
    """Tests for ensure_valid_key function."""

    def test_long_key_padded(self, migrate_module, old_key):
        """Long keys should be padded to valid base64."""
        result = migrate_module.ensure_valid_key(old_key)
        assert isinstance(result, bytes)
        Fernet(result)

    def test_short_key_generates_valid_key(self, migrate_module, short_old_key):
        """Short keys should generate a valid Fernet key via seeding."""
        result = migrate_module.ensure_valid_key(short_old_key)
        assert isinstance(result, bytes)
        Fernet(result)

    def test_same_short_key_produces_same_result(self, migrate_module, short_old_key):
        """Same short key should always produce the same Fernet key."""
        result1 = migrate_module.ensure_valid_key(short_old_key)
        result2 = migrate_module.ensure_valid_key(short_old_key)
        assert result1 == result2

    def test_different_short_keys_produce_different_results(self, migrate_module, short_old_key, short_new_key):
        """Different short keys should produce different Fernet keys."""
        result1 = migrate_module.ensure_valid_key(short_old_key)
        result2 = migrate_module.ensure_valid_key(short_new_key)
        assert result1 != result2


class TestShortKeysMatchTheApp:
    """Short secrets use the app's derivation: SHA-256 for writes, the pre-1.10.1 key read-only."""

    def test_reads_values_the_app_writes_today(self, migrate_module, short_old_key, short_new_key):
        app_ciphertext = Fernet(ensure_fernet_key(short_old_key)).encrypt(b"current").decode()

        migrated = migrate_module.migrate_value(app_ciphertext, short_old_key, short_new_key)

        assert migrated is not None
        assert Fernet(ensure_fernet_key(short_new_key)).decrypt(migrated.encode()) == b"current"

    def test_still_reads_values_written_before_1_10_1(self, migrate_module, short_old_key, short_new_key):
        legacy_ciphertext = Fernet(_ensure_legacy_fernet_key(short_old_key)).encrypt(b"legacy").decode()

        migrated = migrate_module.migrate_value(legacy_ciphertext, short_old_key, short_new_key)

        assert migrated is not None
        assert Fernet(ensure_fernet_key(short_new_key)).decrypt(migrated.encode()) == b"legacy"

    def test_writes_only_with_the_current_derivation(self, migrate_module, short_new_key):
        ciphertext = migrate_module.encrypt_with_key("value", short_new_key).encode()

        assert Fernet(ensure_fernet_key(short_new_key)).decrypt(ciphertext) == b"value"
        with pytest.raises(InvalidToken):
            Fernet(_ensure_legacy_fernet_key(short_new_key)).decrypt(ciphertext)

    def test_canonical_fernet_key_matches_the_app(self, migrate_module):
        canonical_key = Fernet.generate_key().decode()

        assert migrate_module.ensure_valid_key(canonical_key) == ensure_fernet_key(canonical_key)


@pytest.mark.parametrize("value", [b"gAAAAAB", 123, None])
def test_fernet_detection_ignores_non_string_values(migrate_module, value):
    assert migrate_module.looks_like_fernet_token(value) is False


class TestEncryptDecrypt:
    """Tests for encrypt_with_key and decrypt_with_key functions."""

    def test_encrypt_decrypt_roundtrip(self, migrate_module, old_key):
        """Encrypting then decrypting should return original value."""
        plaintext = "my-secret-api-key-12345"
        encrypted = migrate_module.encrypt_with_key(plaintext, old_key)
        decrypted = migrate_module.decrypt_with_key(encrypted, old_key)
        assert decrypted == plaintext

    def test_encrypt_produces_different_output(self, migrate_module, old_key):
        """Encryption should produce ciphertext different from plaintext."""
        plaintext = "my-secret-api-key-12345"
        encrypted = migrate_module.encrypt_with_key(plaintext, old_key)
        assert encrypted != plaintext
        assert encrypted.startswith("gAAAAAB")

    def test_decrypt_with_wrong_key_fails(self, migrate_module, old_key, new_key):
        """Decrypting with wrong key should raise an error."""
        from cryptography.fernet import InvalidToken

        plaintext = "my-secret-api-key-12345"
        encrypted = migrate_module.encrypt_with_key(plaintext, old_key)
        with pytest.raises(InvalidToken):
            migrate_module.decrypt_with_key(encrypted, new_key)

    def test_sso_secret_rewrap_uses_replacement_key(self, migrate_module, old_key, new_key):
        plaintext = "oidc-client-secret"
        encrypted = migrate_module.encrypt_sso_secret_with_key(plaintext, old_key)

        migrated = migrate_module.migrate_sso_secret(encrypted, old_key, new_key)

        assert migrated is not None
        assert migrated != encrypted
        assert migrate_module.decrypt_sso_secret_with_key(migrated, new_key) == plaintext
        with pytest.raises(InvalidTag):
            migrate_module.decrypt_sso_secret_with_key(migrated, old_key)

    @pytest.mark.parametrize("payload_index", [4, 5], ids=["nonce", "ciphertext"])
    @pytest.mark.parametrize("invalid_character", ["!", "+", "/"])
    def test_sso_secret_rewrap_rejects_non_base64url_payload_characters(
        self,
        migrate_module,
        old_key,
        new_key,
        payload_index,
        invalid_character,
    ):
        encrypted = migrate_module.encrypt_sso_secret_with_key("oidc-client-secret", old_key)
        parts = encrypted.split(":")
        parts[payload_index] = f"{invalid_character}{parts[payload_index][1:]}"
        malformed_envelope = ":".join(parts)

        with pytest.raises(ValueError, match="Invalid base64url data"):
            migrate_module._decode_sso_envelope(malformed_envelope)
        assert migrate_module.migrate_sso_secret(malformed_envelope, old_key, new_key) is None

    def test_encrypt_decrypt_with_short_keys(self, migrate_module, short_old_key):
        """Short keys should work for encryption/decryption."""
        plaintext = "secret-value"
        encrypted = migrate_module.encrypt_with_key(plaintext, short_old_key)
        decrypted = migrate_module.decrypt_with_key(encrypted, short_old_key)
        assert decrypted == plaintext


class TestMigrateValue:
    """Tests for migrate_value function."""

    def test_migrate_value_success(self, migrate_module, old_key, new_key):
        """Successfully migrate a value from old key to new key."""
        plaintext = "original-secret"
        old_encrypted = migrate_module.encrypt_with_key(plaintext, old_key)

        new_encrypted = migrate_module.migrate_value(old_encrypted, old_key, new_key)

        assert new_encrypted is not None
        assert new_encrypted != old_encrypted
        decrypted = migrate_module.decrypt_with_key(new_encrypted, new_key)
        assert decrypted == plaintext

    def test_migrate_value_wrong_old_key(self, migrate_module, old_key, new_key):
        """Migration should return None if old key doesn't decrypt."""
        plaintext = "original-secret"
        encrypted = migrate_module.encrypt_with_key(plaintext, old_key)
        wrong_key = secrets.token_urlsafe(32)

        result = migrate_module.migrate_value(encrypted, wrong_key, new_key)
        assert result is None

    def test_migrate_value_invalid_ciphertext(self, migrate_module, old_key, new_key):
        """Migration should return None for invalid ciphertext."""
        result = migrate_module.migrate_value("not-valid-ciphertext", old_key, new_key)
        assert result is None


class TestMigrateAuthSettings:
    """Tests for migrate_auth_settings function."""

    def test_migrate_oauth_client_secret(self, migrate_module, old_key, new_key):
        """oauth_client_secret should be re-encrypted."""
        secret = "my-oauth-secret"  # noqa: S105  # pragma: allowlist secret
        auth_settings = {
            "auth_type": "oauth",
            "oauth_client_id": "client-123",
            "oauth_client_secret": migrate_module.encrypt_with_key(secret, old_key),
        }

        migrated, failed_fields = migrate_module.migrate_auth_settings(auth_settings, old_key, new_key)

        assert failed_fields == []
        assert migrated["auth_type"] == "oauth"
        assert migrated["oauth_client_id"] == "client-123"
        assert migrated["oauth_client_secret"] != auth_settings["oauth_client_secret"]
        decrypted = migrate_module.decrypt_with_key(migrated["oauth_client_secret"], new_key)
        assert decrypted == secret

    def test_migrate_api_key_field(self, migrate_module, old_key, new_key):
        """api_key field should be re-encrypted."""
        api_key = "sk-test-key"  # pragma: allowlist secret
        auth_settings = {
            "auth_type": "api",
            "api_key": migrate_module.encrypt_with_key(api_key, old_key),
        }

        migrated, failed_fields = migrate_module.migrate_auth_settings(auth_settings, old_key, new_key)

        assert failed_fields == []
        decrypted = migrate_module.decrypt_with_key(migrated["api_key"], new_key)
        assert decrypted == api_key

    def test_migrate_preserves_non_sensitive_fields(self, migrate_module, old_key, new_key):
        """Non-sensitive fields should be preserved unchanged."""
        auth_settings = {
            "auth_type": "oauth",
            "oauth_host": "localhost",
            "oauth_port": 3000,
            "oauth_client_id": "my-client",
            "oauth_client_secret": migrate_module.encrypt_with_key("secret", old_key),
        }

        migrated, failed_fields = migrate_module.migrate_auth_settings(auth_settings, old_key, new_key)

        assert failed_fields == []
        assert migrated["auth_type"] == auth_settings["auth_type"]
        assert migrated["oauth_host"] == auth_settings["oauth_host"]
        assert migrated["oauth_port"] == auth_settings["oauth_port"]
        assert migrated["oauth_client_id"] == auth_settings["oauth_client_id"]

    def test_migrate_empty_sensitive_fields(self, migrate_module, old_key, new_key):
        """Empty/None sensitive fields should be handled gracefully."""
        auth_settings = {
            "auth_type": "api",
            "api_key": None,
            "oauth_client_secret": "",
        }

        migrated, failed_fields = migrate_module.migrate_auth_settings(auth_settings, old_key, new_key)

        assert failed_fields == []
        assert migrated["api_key"] is None
        assert migrated["oauth_client_secret"] == ""

    def test_migrate_returns_failed_fields_for_invalid_encryption(self, migrate_module, old_key, new_key):
        """Invalid encrypted fields should be reported in failed_fields."""
        auth_settings = {
            "auth_type": "api",
            "api_key": "not-valid-encrypted-data",  # Invalid ciphertext  # pragma: allowlist secret
            "oauth_client_secret": migrate_module.encrypt_with_key("valid-secret", old_key),
        }

        migrated, failed_fields = migrate_module.migrate_auth_settings(auth_settings, old_key, new_key)

        assert "api_key" in failed_fields
        assert "oauth_client_secret" not in failed_fields
        # oauth_client_secret should still be migrated
        decrypted = migrate_module.decrypt_with_key(migrated["oauth_client_secret"], new_key)
        assert decrypted == "valid-secret"


class TestDatabaseMigrationUnit:
    """Unit tests for database migration with in-memory SQLite."""

    def test_migrate_user_store_api_key(self, migrate_module, sqlite_db, old_key, new_key):
        """Test migrating user.store_api_key column."""
        user_id = str(uuid4())
        original_value = "langflow-store-api-key"
        encrypted_value = migrate_module.encrypt_with_key(original_value, old_key)

        with sqlite_db.connect() as conn:
            conn.execute(
                text('INSERT INTO "user" (id, store_api_key) VALUES (:id, :key)'),
                {"id": user_id, "key": encrypted_value},
            )
            conn.commit()

            users = conn.execute(
                text('SELECT id, store_api_key FROM "user" WHERE store_api_key IS NOT NULL')
            ).fetchall()

            for uid, encrypted_key in users:
                new_encrypted = migrate_module.migrate_value(encrypted_key, old_key, new_key)
                assert new_encrypted is not None
                conn.execute(
                    text('UPDATE "user" SET store_api_key = :val WHERE id = :id'),
                    {"val": new_encrypted, "id": uid},
                )
            conn.commit()

            result = conn.execute(text('SELECT store_api_key FROM "user" WHERE id = :id'), {"id": user_id}).fetchone()
            decrypted = migrate_module.decrypt_with_key(result[0], new_key)
            assert decrypted == original_value

    def test_migrate_variable_values(self, migrate_module, sqlite_db, old_key, new_key):
        """Test migrating variable.value column."""
        var_id = str(uuid4())
        original_value = "my-openai-api-key"
        encrypted_value = migrate_module.encrypt_with_key(original_value, old_key)

        with sqlite_db.connect() as conn:
            conn.execute(
                text("INSERT INTO variable (id, name, value, type) VALUES (:id, :name, :value, :type)"),
                {"id": var_id, "name": "OPENAI_API_KEY", "value": encrypted_value, "type": "Credential"},
            )
            conn.commit()

            variables = conn.execute(text("SELECT id, name, value FROM variable")).fetchall()

            for vid, _, encrypted_val in variables:
                if encrypted_val:
                    new_encrypted = migrate_module.migrate_value(encrypted_val, old_key, new_key)
                    assert new_encrypted is not None
                    conn.execute(
                        text("UPDATE variable SET value = :val WHERE id = :id"),
                        {"val": new_encrypted, "id": vid},
                    )
            conn.commit()

            result = conn.execute(text("SELECT value FROM variable WHERE id = :id"), {"id": var_id}).fetchone()
            decrypted = migrate_module.decrypt_with_key(result[0], new_key)
            assert decrypted == original_value

    def test_migrate_folder_auth_settings(self, migrate_module, sqlite_db, old_key, new_key):
        """Test migrating folder.auth_settings JSON column."""
        folder_id = str(uuid4())
        oauth_secret = "my-oauth-secret"  # noqa: S105  # pragma: allowlist secret
        auth_settings = {
            "auth_type": "oauth",
            "oauth_client_id": "client-123",
            "oauth_client_secret": migrate_module.encrypt_with_key(oauth_secret, old_key),
        }

        with sqlite_db.connect() as conn:
            conn.execute(
                text("INSERT INTO folder (id, name, auth_settings) VALUES (:id, :name, :settings)"),
                {"id": folder_id, "name": "My Project", "settings": json.dumps(auth_settings)},
            )
            conn.commit()

            folders = conn.execute(
                text("SELECT id, name, auth_settings FROM folder WHERE auth_settings IS NOT NULL")
            ).fetchall()

            for fid, _, settings_json in folders:
                settings_dict = json.loads(settings_json)
                new_settings, failed_fields = migrate_module.migrate_auth_settings(settings_dict, old_key, new_key)
                assert failed_fields == []
                conn.execute(
                    text("UPDATE folder SET auth_settings = :val WHERE id = :id"),
                    {"val": json.dumps(new_settings), "id": fid},
                )
            conn.commit()

            result = conn.execute(text("SELECT auth_settings FROM folder WHERE id = :id"), {"id": folder_id}).fetchone()
            migrated_settings = json.loads(result[0])
            decrypted_secret = migrate_module.decrypt_with_key(migrated_settings["oauth_client_secret"], new_key)
            assert decrypted_secret == oauth_secret
            assert migrated_settings["oauth_client_id"] == "client-123"


class TestKeyFileManagement:
    """Tests for secret key file read/write operations."""

    def test_read_secret_key_from_file(self, migrate_module):
        """Test reading secret key from config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            secret_file = config_dir / "secret_key"
            test_key = "test-secret-key-12345"
            secret_file.write_text(test_key)

            result = migrate_module.read_secret_key_from_file(config_dir)
            assert result == test_key

    def test_read_secret_key_strips_whitespace(self, migrate_module):
        """Test that reading strips whitespace from key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            secret_file = config_dir / "secret_key"
            secret_file.write_text("  test-key-with-spaces  \n")

            result = migrate_module.read_secret_key_from_file(config_dir)
            assert result == "test-key-with-spaces"

    def test_read_secret_key_returns_none_if_missing(self, migrate_module):
        """Test that reading returns None if file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            result = migrate_module.read_secret_key_from_file(config_dir)
            assert result is None

    def test_write_secret_key_creates_file(self, migrate_module):
        """Test writing secret key creates file with correct content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            test_key = "new-secret-key-67890"

            migrate_module.write_secret_key_to_file(config_dir, test_key)

            secret_file = config_dir / "secret_key"
            assert secret_file.exists()
            assert secret_file.read_text() == test_key

    def test_write_secret_key_creates_parent_dirs(self, migrate_module):
        """Test writing creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "nested" / "config"
            test_key = "nested-key"

            migrate_module.write_secret_key_to_file(config_dir, test_key)

            secret_file = config_dir / "secret_key"
            assert secret_file.exists()

    def test_write_secret_key_custom_filename(self, migrate_module):
        """Test writing with custom filename for backups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            test_key = "backup-key"

            migrate_module.write_secret_key_to_file(config_dir, test_key, "secret_key.backup")

            backup_file = config_dir / "secret_key.backup"
            assert backup_file.exists()
            assert backup_file.read_text() == test_key

    def test_get_config_dir_default(self, migrate_module, monkeypatch):
        """Test default config directory uses platformdirs."""
        from platformdirs import user_cache_dir

        monkeypatch.delenv("LANGFLOW_CONFIG_DIR", raising=False)
        result = migrate_module.get_config_dir()
        expected = Path(user_cache_dir("langflow", "langflow"))
        assert result == expected

    def test_get_config_dir_from_env(self, migrate_module, monkeypatch):
        """Test config directory from environment variable."""
        monkeypatch.setenv("LANGFLOW_CONFIG_DIR", "/custom/config")
        result = migrate_module.get_config_dir()
        assert result == Path("/custom/config")


@pytest.mark.usefixtures("client")
class TestMigrationWithRealDatabase:
    """Integration tests using real Langflow database fixtures."""

    async def test_credential_variable_stored_encrypted(
        self,
        migrate_module,  # noqa: ARG002
        client: AsyncClient,
        active_user,  # noqa: ARG002
        logged_in_headers,
    ):
        """Test that credential variables are stored encrypted in the database.

        The API returns None for credential values (for security), so we verify
        that the value is different from the original - which means it's encrypted.

        The migration script handles these encrypted values and re-encrypts them
        with a new key - this is tested in the unit tests.
        """
        client.follow_redirects = True

        # Create a credential variable via API
        var_name = f"TEST_API_KEY_{uuid4().hex[:8]}"
        credential_variable = {
            "name": var_name,
            "value": "sk-test-secret-value-12345",
            "type": CREDENTIAL_TYPE,
            "default_fields": [],
        }
        response = await client.post("api/v1/variables/", json=credential_variable, headers=logged_in_headers)
        assert response.status_code == 201
        created_var = response.json()

        # Read the variable back
        response = await client.get("api/v1/variables/", headers=logged_in_headers)
        assert response.status_code == 200
        all_vars = response.json()

        # Find our variable
        our_var = next((v for v in all_vars if v["name"] == var_name), None)
        assert our_var is not None

        # For credentials, the API returns None for security (value is encrypted in DB)
        # This is expected behavior - the migration script works on the raw DB values
        assert our_var["value"] is None or our_var["value"] != credential_variable["value"]

        # Cleanup
        await client.delete(f"api/v1/variables/{created_var['id']}", headers=logged_in_headers)

    async def test_create_folder_via_api(
        self,
        migrate_module,  # noqa: ARG002
        client: AsyncClient,
        active_user,  # noqa: ARG002
        logged_in_headers,
    ):
        """Test that folders can be created via API."""
        client.follow_redirects = True

        project_data = {
            "name": f"Test Project {uuid4().hex[:8]}",
            "description": "Test project for migration",
        }
        response = await client.post("api/v1/folders/", json=project_data, headers=logged_in_headers)
        assert response.status_code == 201
        created_folder = response.json()

        # Cleanup
        await client.delete(f"api/v1/folders/{created_folder['id']}", headers=logged_in_headers)


@pytest.mark.usefixtures("client")
class TestMigrationCompatibility:
    """Test that migration script is compatible with Langflow's encryption."""

    def test_script_encryption_matches_langflow(self, migrate_module):
        """Verify migration script produces same results as Langflow's auth utils."""
        from langflow.services.auth import utils as auth_utils

        settings_service = get_settings_service()
        secret_key = settings_service.auth_settings.SECRET_KEY.get_secret_value()

        plaintext = "test-api-key-compatibility"

        # Encrypt with Langflow
        langflow_encrypted = auth_utils.encrypt_api_key(plaintext, settings_service)

        # Decrypt with migration script
        script_decrypted = migrate_module.decrypt_with_key(langflow_encrypted, secret_key)
        assert script_decrypted == plaintext

        # Encrypt with migration script
        script_encrypted = migrate_module.encrypt_with_key(plaintext, secret_key)

        # Decrypt with Langflow
        langflow_decrypted = auth_utils.decrypt_api_key(script_encrypted, settings_service)
        assert langflow_decrypted == plaintext


class TestTransactionAtomicity:
    """Tests for atomic transaction behavior."""

    def test_transaction_rollback_on_error(self, migrate_module, sqlite_db, old_key, new_key):
        """Test that database changes are rolled back if an error occurs mid-migration."""
        user_id = str(uuid4())
        original_value = "user-api-key"
        encrypted_value = migrate_module.encrypt_with_key(original_value, old_key)

        # Insert test data
        with sqlite_db.connect() as conn:
            conn.execute(
                text('INSERT INTO "user" (id, store_api_key) VALUES (:id, :key)'),
                {"id": user_id, "key": encrypted_value},
            )
            conn.commit()

        # Simulate a failed migration using begin() - any exception causes rollback
        try:
            with sqlite_db.begin() as conn:
                # Update the user's key
                new_encrypted = migrate_module.migrate_value(encrypted_value, old_key, new_key)
                conn.execute(
                    text('UPDATE "user" SET store_api_key = :val WHERE id = :id'),
                    {"val": new_encrypted, "id": user_id},
                )
                # Simulate an error before commit
                msg = "Simulated failure"
                raise RuntimeError(msg)
        except RuntimeError:
            pass

        # Verify the original value was preserved (transaction was rolled back)
        with sqlite_db.connect() as conn:
            result = conn.execute(text('SELECT store_api_key FROM "user" WHERE id = :id'), {"id": user_id}).fetchone()
            assert result[0] == encrypted_value  # Original value preserved

    def test_partial_migration_does_not_persist(self, migrate_module, sqlite_db, old_key, new_key):
        """Test that partial migrations don't leave database in inconsistent state."""
        user_id = str(uuid4())
        var_id = str(uuid4())
        user_value = "user-secret"
        var_value = "var-secret"

        # Insert test data
        with sqlite_db.connect() as conn:
            conn.execute(
                text('INSERT INTO "user" (id, store_api_key) VALUES (:id, :key)'),
                {"id": user_id, "key": migrate_module.encrypt_with_key(user_value, old_key)},
            )
            encrypted_var = migrate_module.encrypt_with_key(var_value, old_key)
            conn.execute(
                text("INSERT INTO variable (id, name, value, type) VALUES (:id, :name, :value, :type)"),
                {"id": var_id, "name": "TEST_VAR", "value": encrypted_var, "type": "Credential"},
            )
            conn.commit()

        original_user_key = None
        original_var_value = None
        with sqlite_db.connect() as conn:
            original_user_key = conn.execute(
                text('SELECT store_api_key FROM "user" WHERE id = :id'), {"id": user_id}
            ).fetchone()[0]
            original_var_value = conn.execute(
                text("SELECT value FROM variable WHERE id = :id"), {"id": var_id}
            ).fetchone()[0]

        # Attempt migration with failure after first table
        try:
            with sqlite_db.begin() as conn:
                # Migrate user table successfully
                new_encrypted = migrate_module.migrate_value(original_user_key, old_key, new_key)
                conn.execute(
                    text('UPDATE "user" SET store_api_key = :val WHERE id = :id'),
                    {"val": new_encrypted, "id": user_id},
                )
                # Fail before variable table
                msg = "Simulated failure after partial migration"
                raise RuntimeError(msg)
        except RuntimeError:
            pass

        # Both tables should be unchanged
        with sqlite_db.connect() as conn:
            user_result = conn.execute(
                text('SELECT store_api_key FROM "user" WHERE id = :id'), {"id": user_id}
            ).fetchone()
            var_result = conn.execute(text("SELECT value FROM variable WHERE id = :id"), {"id": var_id}).fetchone()
            assert user_result[0] == original_user_key
            assert var_result[0] == original_var_value


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_migration_handles_invalid_encrypted_data(self, migrate_module, sqlite_db, old_key, new_key):
        """Test that migration continues when encountering invalid encrypted data."""
        valid_id = str(uuid4())
        invalid_id = str(uuid4())
        valid_value = "valid-secret"

        with sqlite_db.connect() as conn:
            # Insert valid encrypted data
            conn.execute(
                text('INSERT INTO "user" (id, store_api_key) VALUES (:id, :key)'),
                {"id": valid_id, "key": migrate_module.encrypt_with_key(valid_value, old_key)},
            )
            # Insert invalid/corrupted encrypted data
            conn.execute(
                text('INSERT INTO "user" (id, store_api_key) VALUES (:id, :key)'),
                {"id": invalid_id, "key": "not-valid-encrypted-data"},
            )
            conn.commit()

        # migrate_value returns None for invalid data, allowing migration to continue
        with sqlite_db.connect() as conn:
            users = conn.execute(text('SELECT id, store_api_key FROM "user"')).fetchall()

            migrated_count = 0
            failed_count = 0
            for _uid, encrypted_key in users:
                new_encrypted = migrate_module.migrate_value(encrypted_key, old_key, new_key)
                if new_encrypted:
                    migrated_count += 1
                else:
                    failed_count += 1

            assert migrated_count == 1  # Valid entry was migrated
            assert failed_count == 1  # Invalid entry failed gracefully

    def test_migration_handles_null_values(
        self,
        migrate_module,  # noqa: ARG002
        sqlite_db,
        old_key,  # noqa: ARG002
        new_key,  # noqa: ARG002
    ):
        """Test that migration handles NULL values correctly."""
        user_id = str(uuid4())

        with sqlite_db.connect() as conn:
            conn.execute(
                text('INSERT INTO "user" (id, store_api_key) VALUES (:id, NULL)'),
                {"id": user_id},
            )
            conn.commit()

        # NULL values should not cause errors
        with sqlite_db.connect() as conn:
            result = conn.execute(
                text('SELECT id, store_api_key FROM "user" WHERE id = :id'), {"id": user_id}
            ).fetchone()
            assert result[1] is None

    def test_migration_handles_empty_auth_settings(self, migrate_module, old_key, new_key):
        """Test that migration handles empty auth_settings dict."""
        empty_settings = {}
        result, failed_fields = migrate_module.migrate_auth_settings(empty_settings, old_key, new_key)
        assert result == {}
        assert failed_fields == []

    def test_migration_handles_malformed_json_gracefully(
        self,
        migrate_module,  # noqa: ARG002
        sqlite_db,
        old_key,  # noqa: ARG002
        new_key,  # noqa: ARG002
    ):
        """Test that malformed JSON in auth_settings is handled gracefully."""
        folder_id = str(uuid4())

        with sqlite_db.connect() as conn:
            conn.execute(
                text("INSERT INTO folder (id, name, auth_settings) VALUES (:id, :name, :settings)"),
                {"id": folder_id, "name": "Bad Folder", "settings": "not-valid-json{"},
            )
            conn.commit()

        # Attempting to parse and migrate should raise JSONDecodeError
        with sqlite_db.connect() as conn:
            result = conn.execute(text("SELECT auth_settings FROM folder WHERE id = :id"), {"id": folder_id}).fetchone()

            with pytest.raises(json.JSONDecodeError):
                json.loads(result[0])

    def test_key_file_permissions_set_correctly(self, migrate_module):
        """Test that key file has restrictive permissions on Unix systems."""
        import platform
        import stat

        if platform.system() not in {"Linux", "Darwin"}:
            pytest.skip("Permission test only runs on Unix systems")

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            test_key = "secure-key-12345"

            migrate_module.write_secret_key_to_file(config_dir, test_key)

            secret_file = config_dir / "secret_key"
            file_mode = secret_file.stat().st_mode
            # Check that only owner has read/write (0o600)
            assert stat.S_IMODE(file_mode) == 0o600


class TestDryRunMode:
    """Tests for dry-run mode behavior."""

    def test_dry_run_does_not_modify_database(self, migrate_module, sqlite_db, old_key, new_key):
        """Test that dry run mode doesn't modify the database."""
        user_id = str(uuid4())
        original_value = "original-secret"
        encrypted_value = migrate_module.encrypt_with_key(original_value, old_key)

        with sqlite_db.connect() as conn:
            conn.execute(
                text('INSERT INTO "user" (id, store_api_key) VALUES (:id, :key)'),
                {"id": user_id, "key": encrypted_value},
            )
            conn.commit()

        # Simulate dry-run behavior: use begin() then rollback
        with sqlite_db.begin() as conn:
            # Migrate the value
            new_encrypted = migrate_module.migrate_value(encrypted_value, old_key, new_key)
            conn.execute(
                text('UPDATE "user" SET store_api_key = :val WHERE id = :id'),
                {"val": new_encrypted, "id": user_id},
            )
            # Explicitly rollback to simulate dry-run
            conn.rollback()

        # Verify original value is preserved
        with sqlite_db.connect() as conn:
            result = conn.execute(text('SELECT store_api_key FROM "user" WHERE id = :id'), {"id": user_id}).fetchone()
            assert result[0] == encrypted_value
            # Can still decrypt with old key
            decrypted = migrate_module.decrypt_with_key(result[0], old_key)
            assert decrypted == original_value


class TestVerifyMigration:
    """Tests for post-migration verification."""

    def test_verify_migration_success(self, migrate_module, sqlite_db, new_key):
        """Test verification passes when data is correctly migrated."""
        user_id = str(uuid4())
        var_id = str(uuid4())
        original_value = "test-secret-value"

        # Create data encrypted with new key (simulating successful migration)
        encrypted_value = migrate_module.encrypt_with_key(original_value, new_key)

        with sqlite_db.connect() as conn:
            conn.execute(
                text('INSERT INTO "user" (id, store_api_key) VALUES (:id, :key)'),
                {"id": user_id, "key": encrypted_value},
            )
            conn.execute(
                text("INSERT INTO variable (id, name, value, type) VALUES (:id, :name, :value, :type)"),
                {"id": var_id, "name": "test_var", "value": encrypted_value, "type": CREDENTIAL_TYPE},
            )
            conn.commit()

        # Verify migration
        with sqlite_db.connect() as conn:
            verified, failed = migrate_module.verify_migration(conn, new_key)
            assert verified == 2  # 1 user + 1 variable
            assert failed == 0

    def test_verify_migration_failure(self, migrate_module, sqlite_db, old_key, new_key):
        """Test verification fails when data is encrypted with wrong key."""
        user_id = str(uuid4())
        original_value = "test-secret-value"

        # Create data encrypted with old key (simulating failed migration)
        encrypted_value = migrate_module.encrypt_with_key(original_value, old_key)

        with sqlite_db.connect() as conn:
            conn.execute(
                text('INSERT INTO "user" (id, store_api_key) VALUES (:id, :key)'),
                {"id": user_id, "key": encrypted_value},
            )
            conn.commit()

        # Verify migration with new key should fail
        with sqlite_db.connect() as conn:
            verified, failed = migrate_module.verify_migration(conn, new_key)
            assert verified == 0
            assert failed == 1

    def test_verify_migration_empty_tables(self, migrate_module, sqlite_db, new_key):
        """Test verification handles empty tables gracefully."""
        with sqlite_db.connect() as conn:
            verified, failed = migrate_module.verify_migration(conn, new_key)
            assert verified == 0
            assert failed == 0

    def test_verify_migration_includes_sso_secrets(self, migrate_module, sqlite_db, new_key):
        config_id = str(uuid4())
        encrypted = migrate_module.encrypt_sso_secret_with_key("oidc-secret", new_key)
        with sqlite_db.begin() as conn:
            conn.execute(
                text("INSERT INTO sso_config (id, client_secret_encrypted) VALUES (:id, :secret)"),
                {"id": config_id, "secret": encrypted},
            )

        with sqlite_db.connect() as conn:
            verified, failed = migrate_module.verify_migration(conn, new_key)

        assert verified == 1
        assert failed == 0


class TestMigrateEndToEnd:
    """Run migrate() itself against a database holding every encrypted column."""

    @pytest.fixture
    def rotation_db(self, tmp_path, migrate_module, old_key):
        db_path = tmp_path / "langflow.db"
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE "user" (id TEXT PRIMARY KEY, store_api_key TEXT)'))
            conn.execute(text("CREATE TABLE variable (id TEXT PRIMARY KEY, name TEXT, value TEXT, type TEXT)"))
            conn.execute(text("CREATE TABLE folder (id TEXT PRIMARY KEY, name TEXT, auth_settings TEXT)"))
            conn.execute(text("CREATE TABLE sso_config (id TEXT PRIMARY KEY, client_secret_encrypted TEXT)"))
            conn.execute(text("CREATE TABLE apikey (id TEXT PRIMARY KEY, name TEXT, api_key TEXT)"))
            conn.execute(text("CREATE TABLE mcp_server (id TEXT PRIMARY KEY, name TEXT, config TEXT)"))
            conn.execute(text("CREATE TABLE deployment_provider_account (id TEXT PRIMARY KEY, api_key TEXT)"))
            conn.execute(
                text("CREATE TABLE connection_secret (connection_id TEXT PRIMARY KEY, encrypted_payload TEXT)")
            )
            conn.execute(text("CREATE TABLE job (status TEXT)"))
            conn.execute(text("CREATE TABLE connection_oauth (encrypted_verifier TEXT, expires_at TEXT)"))
            conn.execute(
                text("INSERT INTO deployment_provider_account VALUES ('d1', :k)"),
                {"k": migrate_module.encrypt_with_key("wxo-api-key", old_key)},
            )
            conn.execute(
                text("INSERT INTO connection_secret VALUES ('c1', :p)"),
                {"p": migrate_module.encrypt_with_key('{"access_token":"tok"}', old_key)},
            )
            conn.execute(
                text("INSERT INTO variable VALUES ('v1', 'OPENAI_API_KEY', :v, :t)"),
                {"v": migrate_module.encrypt_with_key("variable-secret", old_key), "t": CREDENTIAL_TYPE},
            )
            conn.execute(
                text("INSERT INTO apikey VALUES ('k1', 'ci-key', :k)"),
                {"k": migrate_module.encrypt_with_key("lf-api-key-value", old_key)},
            )
            config = {
                "command": "uvx",
                "env": {"API_TOKEN": migrate_module.encrypt_with_key("mcp-token", old_key), "PLAIN": "not-a-secret"},
                "headers": {"Authorization": migrate_module.encrypt_with_key("Bearer abc", old_key)},
            }
            conn.execute(text("INSERT INTO mcp_server VALUES ('m1', 'fixture-mcp', :c)"), {"c": json.dumps(config)})
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        return engine, config_dir, f"sqlite:///{db_path}"

    def test_rotates_every_fernet_column(self, migrate_module, rotation_db, old_key, new_key):
        engine, config_dir, url = rotation_db

        migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)

        with engine.connect() as conn:
            api_key = conn.execute(text("SELECT api_key FROM apikey")).scalar()
            config = json.loads(conn.execute(text("SELECT config FROM mcp_server")).scalar())
            provider_key = conn.execute(text("SELECT api_key FROM deployment_provider_account")).scalar()
            payload = conn.execute(text("SELECT encrypted_payload FROM connection_secret")).scalar()
        assert migrate_module.decrypt_with_key(api_key, new_key) == "lf-api-key-value"
        assert migrate_module.decrypt_with_key(provider_key, new_key) == "wxo-api-key"
        assert migrate_module.decrypt_with_key(payload, new_key) == '{"access_token":"tok"}'
        assert migrate_module.decrypt_with_key(config["env"]["API_TOKEN"], new_key) == "mcp-token"
        assert migrate_module.decrypt_with_key(config["headers"]["Authorization"], new_key) == "Bearer abc"
        # Plaintext values and structural fields are left alone.
        assert config["env"]["PLAIN"] == "not-a-secret"
        assert config["command"] == "uvx"

    def test_mcp_value_under_another_key_rolls_back(self, migrate_module, rotation_db, old_key, new_key):
        engine, config_dir, url = rotation_db
        stranger = migrate_module.encrypt_with_key("foreign", secrets.token_urlsafe(32))
        with engine.begin() as conn:
            before = conn.execute(text("SELECT config FROM mcp_server")).scalar()
            bad = json.loads(before)
            bad["env"]["OTHER"] = stranger
            conn.execute(text("UPDATE mcp_server SET config = :c"), {"c": json.dumps(bad)})
            before = json.dumps(bad)

        with pytest.raises(SystemExit):
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)

        with engine.connect() as conn:
            assert conn.execute(text("SELECT config FROM mcp_server")).scalar() == before
            variable = conn.execute(text("SELECT value FROM variable")).scalar()
            api_key = conn.execute(text("SELECT api_key FROM apikey")).scalar()
        # Stages that ran before the MCP failure are rolled back too.
        assert migrate_module.decrypt_with_key(variable, old_key) == "variable-secret"
        assert migrate_module.decrypt_with_key(api_key, old_key) == "lf-api-key-value"

    def test_verification_samples_apikey_and_mcp_server(self, migrate_module, rotation_db, old_key, new_key):
        engine, _, _ = rotation_db
        with engine.connect() as conn:
            # variable, apikey, the two encrypted MCP values, the provider account key and the
            # connection payload; the plaintext MCP value is skipped.
            assert migrate_module.verify_migration(conn, old_key) == (6, 0)
            # One failure each for the variable, the API key, the MCP server row, the provider
            # account and the connection secret.
            assert migrate_module.verify_migration(conn, new_key) == (0, 5)

    def test_dry_run_completes_without_changing_rows(self, migrate_module, rotation_db, old_key, new_key):
        engine, config_dir, url = rotation_db
        query = text("SELECT (SELECT api_key FROM apikey), (SELECT config FROM mcp_server)")
        with engine.connect() as conn:
            before = tuple(conn.execute(query).one())

        migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key, dry_run=True)

        with engine.connect() as conn:
            assert tuple(conn.execute(query).one()) == before
        assert not (config_dir / "secret_key").exists()

    @pytest.mark.parametrize("status", ["queued", "in_progress", "suspended"])
    def test_active_job_blocks_rotation(self, migrate_module, rotation_db, old_key, new_key, status):
        engine, config_dir, url = rotation_db
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO job VALUES (:status)"), {"status": status})

        with pytest.raises(SystemExit):
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)

        with engine.connect() as conn:
            api_key = conn.execute(text("SELECT api_key FROM apikey")).scalar()
        assert migrate_module.decrypt_with_key(api_key, old_key) == "lf-api-key-value"
        assert not (config_dir / "secret_key").exists()

    def test_live_oauth_verifier_blocks_rotation(self, migrate_module, rotation_db, old_key, new_key):
        engine, config_dir, url = rotation_db
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO connection_oauth VALUES (:verifier, '2999-01-01')"),
                {"verifier": migrate_module.encrypt_with_key("verifier", old_key)},
            )

        with pytest.raises(SystemExit):
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)

        with engine.connect() as conn:
            api_key = conn.execute(text("SELECT api_key FROM apikey")).scalar()
        assert migrate_module.decrypt_with_key(api_key, old_key) == "lf-api-key-value"
        assert not (config_dir / "secret_key").exists()

    def test_finished_work_does_not_block_rotation(self, migrate_module, rotation_db, old_key, new_key):
        engine, config_dir, url = rotation_db
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO job VALUES ('completed')"))
            conn.execute(
                text("INSERT INTO connection_oauth VALUES (:verifier, '2000-01-01')"),
                {"verifier": migrate_module.encrypt_with_key("expired", old_key)},
            )

        migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)

        with engine.connect() as conn:
            api_key = conn.execute(text("SELECT api_key FROM apikey")).scalar()
        assert migrate_module.decrypt_with_key(api_key, new_key) == "lf-api-key-value"

    def test_non_string_token_column_rolls_back(self, migrate_module, rotation_db, old_key, new_key):
        engine, config_dir, url = rotation_db
        with engine.begin() as conn:
            conn.execute(text("UPDATE apikey SET api_key = :value"), {"value": b"unexpected-bytes"})

        with pytest.raises(SystemExit):
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)

        with engine.connect() as conn:
            variable = conn.execute(text("SELECT value FROM variable")).scalar()
        assert migrate_module.decrypt_with_key(variable, old_key) == "variable-secret"
        assert not (config_dir / "secret_key").exists()


def _fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:12]


class TestKeysStayOutOfOutput:
    """The new key reaches the operator through the key file; the output only identifies it."""

    rotation_db = TestMigrateEndToEnd.rotation_db

    def test_provided_keys_are_not_printed(self, migrate_module, rotation_db, old_key, new_key, capsys):
        _, config_dir, url = rotation_db

        migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)

        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert old_key not in output
        assert new_key not in output
        assert _fingerprint(new_key) in output

    def test_generated_key_is_not_printed(self, migrate_module, rotation_db, old_key, monkeypatch, capsys):
        _, config_dir, url = rotation_db
        # With this set the script prints the banner that used to repeat the key.
        monkeypatch.setenv("LANGFLOW_SECRET_KEY", old_key)

        migrate_module.migrate(config_dir, url, old_key=old_key)

        generated = (config_dir / "secret_key").read_text()
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert generated != old_key
        assert generated not in output
        assert old_key not in output
        assert _fingerprint(generated) in output

    def test_dry_run_prints_no_key_and_writes_nothing(self, migrate_module, rotation_db, old_key, new_key, capsys):
        _, config_dir, url = rotation_db

        migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key, dry_run=True)

        output = capsys.readouterr().out
        assert new_key not in output
        assert _fingerprint(new_key) in output
        assert list(config_dir.iterdir()) == []


def test_printed_database_url_hides_the_password(migrate_module, tmp_path, old_key, capsys):
    password = "s3cr3t-db-pass"  # noqa: S105  # pragma: allowlist secret
    url = f"postgresql://langflow:{password}@127.0.0.1:1/langflow_production"  # pragma: allowlist secret

    # Nothing listens on that port. The configuration is printed before the script connects.
    with pytest.raises((OperationalError, ModuleNotFoundError)) as error:
        migrate_module.migrate(tmp_path, url, old_key=old_key, dry_run=True)

    output = capsys.readouterr().out
    assert "  Database: postgresql://langflow:***@127.0.0.1:1/langflow_production\n" in output
    assert password not in output
    assert password not in str(error.value)


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        pytest.param(
            "postgresql://langflow@127.0.0.1:1/langflow_production_with_a_long_database_name"
            "?password=qu3ry-db-pass&sslmode=require",  # pragma: allowlist secret
            "postgresql://langflow@127.0.0.1:1/langflow_production_with_a_long_database_name",
            id="password-only-in-the-query-string",
        ),
        pytest.param(
            "postgresql://langflow:s3cr3t-db-pass@127.0.0.1:1/langflow_production"  # pragma: allowlist secret
            "?password=qu3ry-db-pass&passfile=/run/secrets/pgpass",  # pragma: allowlist secret
            "postgresql://langflow:***@127.0.0.1:1/langflow_production",
            id="password-in-userinfo-and-query-string",
        ),
    ],
)
def test_printed_database_url_leaves_out_the_query_string(migrate_module, tmp_path, old_key, capsys, url, shown):
    # Drivers take credentials from the query string too, so none of it is printed.
    with pytest.raises((OperationalError, ModuleNotFoundError)) as error:
        migrate_module.migrate(tmp_path, url, old_key=old_key, dry_run=True)

    output = capsys.readouterr().out
    for hidden in ("s3cr3t-db-pass", "qu3ry-db-pass", "sslmode", "passfile"):
        assert hidden not in output
        assert hidden not in str(error.value)
    assert f"  Database: {shown} (query parameters not shown)\n" in output


def test_printed_sqlite_url_is_whole(migrate_module, tmp_path, old_key, capsys):
    url = f"sqlite:///{tmp_path / 'langflow.db'}"

    # The new file holds no tables, so the run stops at its first query, after printing the configuration.
    with pytest.raises(OperationalError):
        migrate_module.migrate(tmp_path, url, old_key=old_key, dry_run=True)

    assert f"  Database: {url}\n" in capsys.readouterr().out


def _run_cli(migrate_module, monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["migrate_secret_key.py", *map(str, args)])
    migrate_module.main()


class TestKeySources:
    """Keys and the database URL come from files or the environment, not only from the command line."""

    rotation_db = TestMigrateEndToEnd.rotation_db

    @pytest.fixture(autouse=True)
    def _no_ambient_sources(self, monkeypatch):
        for name in ("LANGFLOW_OLD_SECRET_KEY", "LANGFLOW_NEW_SECRET_KEY", "LANGFLOW_MIGRATION_TARGET_URL"):
            monkeypatch.delenv(name, raising=False)

    @staticmethod
    def _stored_api_key(migrate_module, engine, key):
        with engine.connect() as conn:
            return migrate_module.decrypt_with_key(conn.execute(text("SELECT api_key FROM apikey")).scalar(), key)

    def test_reads_keys_from_files(self, migrate_module, rotation_db, old_key, new_key, tmp_path, monkeypatch):
        engine, config_dir, url = rotation_db
        (tmp_path / "old.key").write_text(f"{old_key}\n")
        (tmp_path / "new.key").write_text(f"{new_key}\n")

        _run_cli(
            migrate_module,
            monkeypatch,
            *("--config-dir", config_dir, "--database-url", url),
            *("--old-key-file", tmp_path / "old.key", "--new-key-file", tmp_path / "new.key"),
        )

        assert self._stored_api_key(migrate_module, engine, new_key) == "lf-api-key-value"
        # Langflow reads secret_key as it is, so the newline that ends a key file must not reach it.
        assert (config_dir / "secret_key").read_text() == new_key

    def test_reads_keys_and_database_url_from_the_environment(
        self, migrate_module, rotation_db, old_key, new_key, tmp_path, monkeypatch
    ):
        engine, config_dir, url = rotation_db
        # Lower in precedence: a key file and a default database that would both fail the run.
        (config_dir / "secret_key").write_text(secrets.token_urlsafe(32))
        (config_dir / "langflow.db").touch()
        monkeypatch.setenv("LANGFLOW_OLD_SECRET_KEY", old_key)
        monkeypatch.setenv("LANGFLOW_NEW_SECRET_KEY", new_key)
        monkeypatch.setenv("LANGFLOW_MIGRATION_TARGET_URL", url)
        # In the migration UI this is the source instance's database, which the script must not open.
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'source.db'}")

        _run_cli(migrate_module, monkeypatch, "--config-dir", config_dir)

        assert self._stored_api_key(migrate_module, engine, new_key) == "lf-api-key-value"
        assert (config_dir / "secret_key").read_text() == new_key
        assert not (tmp_path / "source.db").exists()

    @pytest.mark.parametrize("source", ["flag", "file"])
    def test_command_line_wins_over_the_environment(
        self, migrate_module, rotation_db, old_key, new_key, tmp_path, monkeypatch, source
    ):
        engine, config_dir, url = rotation_db
        monkeypatch.setenv("LANGFLOW_OLD_SECRET_KEY", secrets.token_urlsafe(32))
        monkeypatch.setenv("LANGFLOW_NEW_SECRET_KEY", secrets.token_urlsafe(32))
        monkeypatch.setenv("LANGFLOW_MIGRATION_TARGET_URL", f"sqlite:///{tmp_path / 'other.db'}")
        if source == "flag":
            key_args = (f"--old-key={old_key}", f"--new-key={new_key}")
        else:
            (tmp_path / "old.key").write_text(old_key)
            (tmp_path / "new.key").write_text(new_key)
            key_args = ("--old-key-file", tmp_path / "old.key", "--new-key-file", tmp_path / "new.key")

        _run_cli(migrate_module, monkeypatch, "--config-dir", config_dir, "--database-url", url, *key_args)

        assert self._stored_api_key(migrate_module, engine, new_key) == "lf-api-key-value"
        assert (config_dir / "secret_key").read_text() == new_key
        assert not (tmp_path / "other.db").exists()

    @pytest.mark.parametrize("which", ["old", "new"])
    def test_key_and_its_file_together_is_a_usage_error(
        self, migrate_module, rotation_db, old_key, new_key, tmp_path, monkeypatch, capsys, which
    ):
        engine, config_dir, url = rotation_db
        (tmp_path / "key").write_text(secrets.token_urlsafe(32))

        with pytest.raises(SystemExit) as exit_info:
            _run_cli(
                migrate_module,
                monkeypatch,
                *("--config-dir", config_dir, "--database-url", url, f"--old-key={old_key}", f"--new-key={new_key}"),
                *(f"--{which}-key-file", tmp_path / "key"),
            )

        error = capsys.readouterr().err
        assert exit_info.value.code == 2
        assert f"--{which}-key-file: not allowed with argument --{which}-key" in error
        assert old_key not in error
        assert new_key not in error
        assert self._stored_api_key(migrate_module, engine, old_key) == "lf-api-key-value"

    @pytest.mark.parametrize("content", [None, "\n"], ids=["missing", "empty"])
    def test_unusable_key_file_is_a_usage_error(
        self, migrate_module, rotation_db, old_key, tmp_path, monkeypatch, capsys, content
    ):
        engine, config_dir, url = rotation_db
        if content is not None:
            (tmp_path / "new.key").write_text(content)

        with pytest.raises(SystemExit) as exit_info:
            _run_cli(
                migrate_module,
                monkeypatch,
                *("--config-dir", config_dir, "--database-url", url, f"--old-key={old_key}"),
                *("--new-key-file", tmp_path / "new.key"),
            )

        assert exit_info.value.code == 2
        assert "argument --new-key-file: " in capsys.readouterr().err
        assert self._stored_api_key(migrate_module, engine, old_key) == "lf-api-key-value"
        assert list(config_dir.iterdir()) == []

    def test_help_lists_the_sources_without_the_lint_pragma(self, migrate_module, monkeypatch, capsys):
        with pytest.raises(SystemExit) as exit_info:
            _run_cli(migrate_module, monkeypatch, "--help")

        output = capsys.readouterr().out
        assert exit_info.value.code == 0
        assert "pragma" not in output
        for name in (
            "--old-key-file",
            "--new-key-file",
            "LANGFLOW_OLD_SECRET_KEY",
            "LANGFLOW_NEW_SECRET_KEY",
            "LANGFLOW_MIGRATION_TARGET_URL",
        ):
            assert name in output


class TestRefusals:
    """Problems the script can see are reported with exit code 1 before anything is written."""

    rotation_db = TestMigrateEndToEnd.rotation_db
    # Long enough to be used as it is, but it does not decode to the 32 bytes Fernet needs.
    malformed_key = "long-enough-but-not-the-base64-of-32-bytes"

    def test_dry_run_with_an_undecryptable_value_exits_1(self, migrate_module, rotation_db, old_key, new_key, capsys):
        engine, config_dir, url = rotation_db
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE apikey SET api_key = :value"),
                {"value": migrate_module.encrypt_with_key("foreign", secrets.token_urlsafe(32))},
            )

        with pytest.raises(SystemExit) as exit_info:
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key, dry_run=True)

        output = capsys.readouterr().out
        assert exit_info.value.code == 1
        assert "DRY RUN COMPLETE" in output
        assert "Would migrate 4 items, 1 failures" in output
        assert "Warning: 1 items could not be migrated." in output
        assert list(config_dir.iterdir()) == []

    def test_malformed_new_key_is_refused_with_one_line(self, migrate_module, rotation_db, old_key, capsys):
        engine, config_dir, url = rotation_db

        with pytest.raises(SystemExit) as exit_info:
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=self.malformed_key)

        output = capsys.readouterr().out
        assert exit_info.value.code == 1
        assert "Error: The new secret key is not usable" in output.splitlines()[-1]
        assert self.malformed_key not in output
        assert list(config_dir.iterdir()) == []
        with engine.connect() as conn:
            api_key = conn.execute(text("SELECT api_key FROM apikey")).scalar()
        assert migrate_module.decrypt_with_key(api_key, old_key) == "lf-api-key-value"

    def test_malformed_new_key_is_not_saved_when_nothing_is_encrypted(self, migrate_module, rotation_db, old_key):
        engine, config_dir, url = rotation_db
        with engine.begin() as conn:
            for table in ("variable", "apikey", "mcp_server", "deployment_provider_account", "connection_secret"):
                conn.execute(text(f"DELETE FROM {table}"))  # noqa: S608

        # No value exercises the key, so only an up-front check can catch it.
        with pytest.raises(SystemExit) as exit_info:
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=self.malformed_key)

        assert exit_info.value.code == 1
        assert list(config_dir.iterdir()) == []

    def test_malformed_key_is_refused_before_the_database_is_opened(self, migrate_module, tmp_path, old_key):
        db_path = tmp_path / "langflow.db"

        with pytest.raises(SystemExit):
            migrate_module.migrate(
                tmp_path / "cfg", f"sqlite:///{db_path}", old_key=old_key, new_key=self.malformed_key
            )

        # SQLite creates the file as soon as it is opened.
        assert not db_path.exists()

    def test_rotates_away_from_an_old_key_fernet_cannot_use(self, migrate_module, rotation_db, new_key):
        engine, config_dir, url = rotation_db
        # Such an instance cannot hold Fernet values, but SSO secrets derive their key from the raw string.
        with engine.begin() as conn:
            for table in ("variable", "apikey", "mcp_server", "deployment_provider_account", "connection_secret"):
                conn.execute(text(f"DELETE FROM {table}"))  # noqa: S608
            conn.execute(
                text("INSERT INTO sso_config VALUES ('s1', :secret)"),
                {"secret": migrate_module.encrypt_sso_secret_with_key("oidc-secret", self.malformed_key)},
            )

        migrate_module.migrate(config_dir, url, old_key=self.malformed_key, new_key=new_key)

        with engine.connect() as conn:
            secret = conn.execute(text("SELECT client_secret_encrypted FROM sso_config")).scalar()
        assert migrate_module.decrypt_sso_secret_with_key(secret, new_key) == "oidc-secret"
        assert (config_dir / "secret_key").read_text() == new_key

    def test_old_key_fernet_cannot_use_fails_like_an_undecryptable_value(
        self, migrate_module, rotation_db, new_key, capsys
    ):
        engine, config_dir, url = rotation_db
        with engine.connect() as conn:
            before = conn.execute(text("SELECT value FROM variable")).scalar()

        with pytest.raises(SystemExit) as exit_info:
            migrate_module.migrate(config_dir, url, old_key=self.malformed_key, new_key=new_key)

        output = capsys.readouterr().out
        assert exit_info.value.code == 1
        assert "Warning: Could not decrypt variable 'OPENAI_API_KEY' (v1)" in output
        assert "ERROR: 5 values could not be migrated." in output
        assert self.malformed_key not in output
        assert list(config_dir.iterdir()) == []
        with engine.connect() as conn:
            assert conn.execute(text("SELECT value FROM variable")).scalar() == before


class TestPendingKeyFile:
    """The new key is on disk before the commit, so stopping after the commit cannot lose it."""

    rotation_db = TestMigrateEndToEnd.rotation_db

    def test_new_key_stays_on_disk_when_the_commit_fails(self, migrate_module, old_key, new_key, tmp_path):
        admin_url = os.environ.get("LANGFLOW_TEST_POSTGRES_URL") or os.environ.get("LANGFLOW_TEST_DATABASE_URI")
        if not admin_url:
            pytest.skip("LANGFLOW_TEST_POSTGRES_URL or LANGFLOW_TEST_DATABASE_URI is not set")
        schema = f"keyscript_{uuid4().hex}"
        url = make_url(admin_url).update_query_dict({"options": f"-csearch_path={schema}"})
        admin = create_engine(admin_url)
        engine = create_engine(url)
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        try:
            with engine.begin() as conn:
                conn.execute(text('CREATE TABLE "user" (id TEXT PRIMARY KEY, store_api_key TEXT)'))
                conn.execute(text("CREATE TABLE variable (id TEXT PRIMARY KEY, name TEXT, value TEXT, type TEXT)"))
                conn.execute(text("CREATE TABLE folder (id TEXT PRIMARY KEY, name TEXT, auth_settings TEXT)"))
                conn.execute(
                    text("INSERT INTO variable VALUES ('v1', 'OPENAI_API_KEY', :v, :t)"),
                    {"v": migrate_module.encrypt_with_key("variable-secret", old_key), "t": CREDENTIAL_TYPE},
                )
                # A deferred constraint trigger runs at COMMIT, so the run stops at the commit itself.
                conn.execute(
                    text(
                        "CREATE FUNCTION refuse_commit() RETURNS trigger LANGUAGE plpgsql "
                        "AS $$ BEGIN RAISE EXCEPTION 'commit refused'; END $$"
                    )
                )
                conn.execute(
                    text(
                        "CREATE CONSTRAINT TRIGGER refuse_commit AFTER UPDATE ON variable "
                        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refuse_commit()"
                    )
                )

            with pytest.raises(DBAPIError, match="commit refused"):
                migrate_module.migrate(
                    tmp_path, url.render_as_string(hide_password=False), old_key=old_key, new_key=new_key
                )

            # The script cannot always know whether a failed commit was applied, so the key stays.
            pending = tmp_path / "secret_key.new"
            assert pending.read_text() == new_key
            assert stat.S_IMODE(pending.stat().st_mode) == 0o600
            assert not (tmp_path / "secret_key").exists()
            with engine.connect() as conn:
                value = conn.execute(text("SELECT value FROM variable")).scalar()
            assert migrate_module.decrypt_with_key(value, old_key) == "variable-secret"
        finally:
            engine.dispose()
            with admin.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin.dispose()

    def test_successful_run_moves_the_pending_key_into_place(self, migrate_module, rotation_db, old_key, new_key):
        _, config_dir, url = rotation_db
        (config_dir / "secret_key").write_text(old_key)

        migrate_module.migrate(config_dir, url, new_key=new_key)

        assert not (config_dir / "secret_key.new").exists()
        assert (config_dir / "secret_key").read_text() == new_key
        if os.name == "posix":
            assert stat.S_IMODE((config_dir / "secret_key").stat().st_mode) == 0o600
        [backup] = config_dir.glob("secret_key.backup.*")
        assert backup.read_text() == old_key

    def test_rolled_back_run_leaves_no_pending_file(self, migrate_module, rotation_db, old_key, new_key):
        engine, config_dir, url = rotation_db
        with engine.begin() as conn:
            conn.execute(text("UPDATE apikey SET api_key = :value"), {"value": b"unexpected-bytes"})

        with pytest.raises(SystemExit):
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)

        assert list(config_dir.iterdir()) == []

    def test_unwritable_config_dir_fails_before_the_commit(self, migrate_module, rotation_db, old_key, new_key):
        engine, config_dir, url = rotation_db
        if os.name != "posix" or os.geteuid() == 0:
            pytest.skip("Needs a directory the current user cannot write to")
        config_dir.chmod(0o500)
        try:
            with pytest.raises(PermissionError):
                migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)
        finally:
            config_dir.chmod(0o700)

        # The key could not be saved, so the database must still open with the old one.
        assert list(config_dir.iterdir()) == []
        with engine.connect() as conn:
            api_key = conn.execute(text("SELECT api_key FROM apikey")).scalar()
        assert migrate_module.decrypt_with_key(api_key, old_key) == "lf-api-key-value"

    def test_failed_save_after_commit_keeps_the_key_in_the_pending_file(
        self, migrate_module, rotation_db, old_key, new_key, capsys
    ):
        engine, config_dir, url = rotation_db
        # A directory where the key file goes makes the move into place fail, after the commit.
        (config_dir / "secret_key").mkdir()

        with pytest.raises(SystemExit) as exit_info:
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)

        pending = config_dir / "secret_key.new"
        output = capsys.readouterr().out
        assert exit_info.value.code == 1
        assert pending.read_text() == new_key
        assert str(pending) in output
        assert new_key not in output
        with engine.connect() as conn:
            api_key = conn.execute(text("SELECT api_key FROM apikey")).scalar()
        assert migrate_module.decrypt_with_key(api_key, new_key) == "lf-api-key-value"

    def test_leftover_pending_key_stops_the_next_run(self, migrate_module, rotation_db, old_key, new_key, capsys):
        engine, config_dir, url = rotation_db
        pending = config_dir / "secret_key.new"
        # Left by a run that was killed around its commit.
        pending.write_text(new_key)
        next_key = secrets.token_urlsafe(32)

        with pytest.raises(SystemExit) as exit_info:
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=next_key)

        output = capsys.readouterr().out
        assert exit_info.value.code == 1
        assert f"--dry-run --old-key-file {pending}" in output
        assert _fingerprint(new_key) in output
        assert all(key not in output for key in (old_key, new_key, next_key))
        assert pending.read_text() == new_key
        assert not (config_dir / "secret_key").exists()
        with engine.connect() as conn:
            api_key = conn.execute(text("SELECT api_key FROM apikey")).scalar()
        assert migrate_module.decrypt_with_key(api_key, old_key) == "lf-api-key-value"

    def test_dry_run_shows_which_key_opens_the_data(
        self, migrate_module, rotation_db, old_key, new_key, monkeypatch, capsys
    ):
        _, config_dir, url = rotation_db
        (config_dir / "secret_key").mkdir()
        with pytest.raises(SystemExit):
            migrate_module.migrate(config_dir, url, old_key=old_key, new_key=new_key)
        (config_dir / "secret_key").rmdir()
        pending = config_dir / "secret_key.new"
        capsys.readouterr()

        # The check the leftover-file notice asks for.
        _run_cli(
            migrate_module,
            monkeypatch,
            *("--config-dir", config_dir, "--database-url", url, "--dry-run", "--old-key-file", pending),
        )

        assert "Would migrate 5 items, 0 failures" in capsys.readouterr().out
        assert pending.read_text() == new_key


class TestRotationOnAppWrittenDatabase:
    """Rows written through the app's models and encryption, in a schema built from its models."""

    @pytest.fixture
    def app_db(self, tmp_path):
        from langflow.services.auth.mcp_encryption import encrypt_mcp_config
        from langflow.services.auth.utils import encrypt_api_key
        from langflow.services.database.models import Flow, MCPServer, User
        from langflow.services.database.models.trigger.model import Trigger
        from sqlmodel import Session, SQLModel

        url = f"sqlite:///{tmp_path / 'langflow.db'}"
        engine = create_engine(url)
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            user = User(username="owner", password="hashed")  # noqa: S106
            flow = Flow(name="webhook flow", user_id=user.id)
            # The shape projects_mcp_helpers registers for an apikey project.
            project_server = {
                "command": "uvx",
                "args": [
                    "mcp-proxy",
                    "--transport",
                    "streamablehttp",
                    "--headers",
                    "x-api-key",
                    "sk-project-key",
                    "http://localhost:7860/api/v1/mcp/project/p/streamable",
                ],
            }
            session.add_all(
                [
                    user,
                    flow,
                    MCPServer(user_id=user.id, name="lf-project", config=encrypt_mcp_config(project_server)),
                    Trigger(
                        flow_id=flow.id,
                        user_id=user.id,
                        name="hook",
                        kind="webhook",
                        concurrency_limit=1,
                        max_attempts=5,
                        signing_secret_encrypted=encrypt_api_key("whsec-signing"),
                    ),
                ]
            )
            session.commit()
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        app_key = get_settings_service().auth_settings.SECRET_KEY.get_secret_value()
        return engine, config_dir, url, app_key

    def test_rotates_the_header_value_mcp_proxy_takes_in_args(self, migrate_module, app_db, new_key):
        engine, config_dir, url, app_key = app_db

        migrate_module.migrate(config_dir, url, old_key=app_key, new_key=new_key)

        with engine.connect() as conn:
            args = json.loads(conn.execute(text("SELECT config FROM mcp_server")).scalar())["args"]
        assert migrate_module.decrypt_with_key(args[args.index("x-api-key") + 1], new_key) == "sk-project-key"

    def test_verification_samples_the_header_value_in_args(self, migrate_module, app_db, new_key):
        engine, _, _, app_key = app_db
        with engine.connect() as conn:
            # The trigger secret and the args header value.
            assert migrate_module.verify_migration(conn, app_key) == (2, 0)
            assert migrate_module.verify_migration(conn, new_key) == (0, 2)

    def test_rotates_trigger_signing_secrets(self, migrate_module, app_db, new_key):
        engine, config_dir, url, app_key = app_db

        migrate_module.migrate(config_dir, url, old_key=app_key, new_key=new_key)

        with engine.connect() as conn:
            secret = conn.execute(text('SELECT signing_secret_encrypted FROM "trigger"')).scalar()
        assert migrate_module.decrypt_with_key(secret, new_key) == "whsec-signing"

    def test_header_value_under_another_key_rolls_back(self, migrate_module, app_db, new_key):
        engine, config_dir, url, app_key = app_db
        with engine.begin() as conn:
            config = json.loads(conn.execute(text("SELECT config FROM mcp_server")).scalar())
            args = config["args"]
            args[args.index("x-api-key") + 1] = migrate_module.encrypt_with_key("foreign", secrets.token_urlsafe(32))
            conn.execute(text("UPDATE mcp_server SET config = :c"), {"c": json.dumps(config)})

        with pytest.raises(SystemExit):
            migrate_module.migrate(config_dir, url, old_key=app_key, new_key=new_key)

        assert not (config_dir / "secret_key").exists()

    def test_skips_projects_without_auth_settings(self, migrate_module, app_db, new_key):
        from langflow.services.database.models import User
        from langflow.services.database.models.folder.model import Folder
        from sqlmodel import Session, select

        engine, config_dir, url, app_key = app_db
        # The default folder Langflow creates for every user leaves auth_settings unset.
        with Session(engine) as session:
            session.add(Folder(name="Starter Project", user_id=session.exec(select(User)).one().id))
            session.commit()
        with engine.connect() as conn:
            assert conn.execute(text("SELECT auth_settings FROM folder")).scalar() == "null"

        migrate_module.migrate(config_dir, url, old_key=app_key, new_key=new_key)

        with engine.connect() as conn:
            assert conn.execute(text("SELECT auth_settings FROM folder")).scalar() == "null"
        assert migrate_module.read_secret_key_from_file(config_dir) == new_key

    def test_env_secret_key_must_be_updated_before_restart(self, migrate_module, app_db, new_key, monkeypatch, capsys):
        _, config_dir, url, app_key = app_db
        # Langflow uses this over the key file and writes it back over the file on start.
        monkeypatch.setenv("LANGFLOW_SECRET_KEY", app_key)

        migrate_module.migrate(config_dir, url, old_key=app_key, new_key=new_key)

        output = capsys.readouterr().out
        start, _, _ = output.partition("1. Migrating")
        _, _, completion = output.partition("MIGRATION COMPLETE")
        assert "LANGFLOW_SECRET_KEY is set" in start
        assert f"Set LANGFLOW_SECRET_KEY to the contents of {config_dir / 'secret_key'}" in completion
        assert _fingerprint(new_key) in completion
        assert new_key not in output
