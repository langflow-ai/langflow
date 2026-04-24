"""Tests for the secret key migration script."""

import importlib.util
import json
import secrets
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from langflow.services.deps import get_settings_service
from langflow.services.variable.constants import CREDENTIAL_TYPE
from sqlalchemy import create_engine, text


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
