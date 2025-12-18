"""Migrate encrypted data from old secret key to new secret key.

This script handles the full key rotation lifecycle:
1. Reads the current secret key from config directory
2. Generates a new secret key (or uses one provided)
3. Re-encrypts all sensitive data in the database (atomic transaction)
4. Backs up the old key
5. Saves the new key

Migrated database fields:
- user.store_api_key: Langflow Store API keys
- variable.value: All encrypted variable values
- folder.auth_settings: MCP oauth_client_secret and api_key fields

Usage:
    uv run python scripts/migrate_secret_key.py --help
    uv run python scripts/migrate_secret_key.py --dry-run
    uv run python scripts/migrate_secret_key.py --database-url postgresql://...
"""

import argparse
import base64
import json
import os
import platform
import random
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from platformdirs import user_cache_dir
from sqlalchemy import create_engine, text

MINIMUM_KEY_LENGTH = 32
SENSITIVE_AUTH_FIELDS = ["oauth_client_secret", "api_key"]


def get_default_config_dir() -> Path:
    """Get the default Langflow config directory using platformdirs."""
    return Path(user_cache_dir("langflow", "langflow"))


def get_config_dir() -> Path:
    """Get the Langflow config directory from environment or default."""
    config_dir = os.environ.get("LANGFLOW_CONFIG_DIR")
    if config_dir:
        return Path(config_dir)
    return get_default_config_dir()


def set_secure_permissions(file_path: Path) -> None:
    """Set restrictive permissions on a file (600 on Unix)."""
    if platform.system() in {"Linux", "Darwin"}:
        file_path.chmod(0o600)
    elif platform.system() == "Windows":
        try:
            import win32api
            import win32con
            import win32security

            user, _, _ = win32security.LookupAccountName("", win32api.GetUserName())
            sd = win32security.GetFileSecurity(str(file_path), win32security.DACL_SECURITY_INFORMATION)
            dacl = win32security.ACL()
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                user,
            )
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(str(file_path), win32security.DACL_SECURITY_INFORMATION, sd)
        except ImportError:
            print("Warning: Could not set secure permissions on Windows (pywin32 not installed)")


def read_secret_key_from_file(config_dir: Path) -> str | None:
    """Read the secret key from the config directory."""
    secret_file = config_dir / "secret_key"
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()
    return None


def write_secret_key_to_file(config_dir: Path, key: str, filename: str = "secret_key") -> None:
    """Write a secret key to file with secure permissions."""
    config_dir.mkdir(parents=True, exist_ok=True)
    secret_file = config_dir / filename
    secret_file.write_text(key, encoding="utf-8")
    set_secure_permissions(secret_file)


def ensure_valid_key(s: str) -> bytes:
    """Convert a secret key string to valid Fernet key bytes.

    For keys shorter than MINIMUM_KEY_LENGTH (32), generates a deterministic
    key by seeding random with the input string. For longer keys, pads with
    '=' to ensure valid base64 encoding.
    """
    if len(s) < MINIMUM_KEY_LENGTH:
        random.seed(s)
        key = bytes(random.getrandbits(8) for _ in range(32))
        return base64.urlsafe_b64encode(key)
    padding_needed = 4 - len(s) % 4
    return (s + "=" * padding_needed).encode()


def decrypt_with_key(encrypted: str, key: str) -> str:
    """Decrypt data with the given key."""
    fernet = Fernet(ensure_valid_key(key))
    return fernet.decrypt(encrypted.encode()).decode()


def encrypt_with_key(plaintext: str, key: str) -> str:
    """Encrypt data with the given key."""
    fernet = Fernet(ensure_valid_key(key))
    return fernet.encrypt(plaintext.encode()).decode()


def migrate_value(encrypted: str, old_key: str, new_key: str) -> str | None:
    """Decrypt with old key and re-encrypt with new key.

    Returns:
        The re-encrypted value, or None if decryption fails (invalid key or corrupted data).
    """
    try:
        plaintext = decrypt_with_key(encrypted, old_key)
        return encrypt_with_key(plaintext, new_key)
    except InvalidToken:
        return None


def migrate_auth_settings(auth_settings: dict, old_key: str, new_key: str) -> tuple[dict, list[str]]:
    """Re-encrypt sensitive fields in auth_settings dict.

    Returns:
        Tuple of (migrated_settings, failed_fields) where failed_fields contains
        names of fields that could not be decrypted with the old key.
    """
    result = auth_settings.copy()
    failed_fields = []
    for field in SENSITIVE_AUTH_FIELDS:
        if result.get(field):
            new_value = migrate_value(result[field], old_key, new_key)
            if new_value:
                result[field] = new_value
            else:
                failed_fields.append(field)
    return result, failed_fields


def get_default_database_url(config_dir: Path) -> str | None:
    """Get database URL from default SQLite location."""
    default_db = config_dir / "langflow.db"
    if default_db.exists():
        return f"sqlite:///{default_db}"
    return None


DATABASE_URL_DISPLAY_LENGTH = 50


def migrate(
    config_dir: Path,
    database_url: str,
    old_key: str | None = None,
    new_key: str | None = None,
    *,
    dry_run: bool = False,
):
    """Run the secret key migration.

    Args:
        config_dir: Path to Langflow config directory containing secret_key file.
        database_url: SQLAlchemy database connection URL.
        old_key: Current secret key. If None, reads from config_dir/secret_key.
        new_key: New secret key. If None, generates a secure random key.
        dry_run: If True, simulates migration without making changes.

    The migration runs as an atomic transaction - either all database changes
    succeed or none are applied. Key files are only modified after successful
    database migration.
    """
    # Determine old key
    if not old_key:
        old_key = read_secret_key_from_file(config_dir)
    if not old_key:
        print("Error: Could not find current secret key.")
        print(f"  Checked: {config_dir}/secret_key")
        print("  Use --old-key to provide it explicitly")
        sys.exit(1)

    # Determine new key
    if not new_key:
        new_key = secrets.token_urlsafe(32)
        print(f"Generated new secret key: {new_key}")
    else:
        print(f"Using provided new key: {new_key}")
    print("  (Save this key - you'll need it if the migration fails after database commit)")

    if old_key == new_key:
        print("Error: Old and new secret keys are the same")
        sys.exit(1)

    print("\nConfiguration:")
    print(f"  Config dir: {config_dir}")
    db_display = (
        f"{database_url[:DATABASE_URL_DISPLAY_LENGTH]}..."
        if len(database_url) > DATABASE_URL_DISPLAY_LENGTH
        else database_url
    )
    print(f"  Database: {db_display}")
    print(f"  Dry run: {dry_run}")

    if dry_run:
        print("\n[DRY RUN] No changes will be made.\n")

    engine = create_engine(database_url)
    total_migrated = 0
    total_failed = 0

    # Use begin() for atomic transaction - all changes commit together or rollback on failure
    with engine.begin() as conn:
        # Migrate user.store_api_key
        print("\n1. Migrating user.store_api_key...")
        users = conn.execute(text('SELECT id, store_api_key FROM "user" WHERE store_api_key IS NOT NULL')).fetchall()

        migrated, failed = 0, 0
        for user_id, encrypted_key in users:
            new_encrypted = migrate_value(encrypted_key, old_key, new_key)
            if new_encrypted:
                if not dry_run:
                    conn.execute(
                        text('UPDATE "user" SET store_api_key = :val WHERE id = :id'),
                        {"val": new_encrypted, "id": user_id},
                    )
                migrated += 1
            else:
                failed += 1
                print(f"   Warning: Could not decrypt for user {user_id}")

        print(f"   {'Would migrate' if dry_run else 'Migrated'}: {migrated}, Failed: {failed}")
        total_migrated += migrated
        total_failed += failed

        # Migrate variable.value
        print("\n2. Migrating variable values...")
        variables = conn.execute(text("SELECT id, name, value FROM variable")).fetchall()

        migrated, failed, skipped = 0, 0, 0
        for var_id, var_name, encrypted_value in variables:
            if not encrypted_value:
                skipped += 1
                continue
            new_encrypted = migrate_value(encrypted_value, old_key, new_key)
            if new_encrypted:
                if not dry_run:
                    conn.execute(
                        text("UPDATE variable SET value = :val WHERE id = :id"),
                        {"val": new_encrypted, "id": var_id},
                    )
                migrated += 1
            else:
                failed += 1
                print(f"   Warning: Could not decrypt variable '{var_name}' ({var_id})")

        print(f"   {'Would migrate' if dry_run else 'Migrated'}: {migrated}, Failed: {failed}, Skipped: {skipped}")
        total_migrated += migrated
        total_failed += failed

        # Migrate folder.auth_settings
        print("\n3. Migrating folder.auth_settings (MCP)...")
        folders = conn.execute(
            text("SELECT id, name, auth_settings FROM folder WHERE auth_settings IS NOT NULL")
        ).fetchall()

        migrated, failed = 0, 0
        for folder_id, folder_name, auth_settings in folders:
            if not auth_settings:
                continue
            try:
                settings_dict = auth_settings if isinstance(auth_settings, dict) else json.loads(auth_settings)
                new_settings, failed_fields = migrate_auth_settings(settings_dict, old_key, new_key)
                if failed_fields:
                    failed += 1
                    print(f"   Warning: Could not migrate folder '{folder_name}' fields: {', '.join(failed_fields)}")
                    continue
                if not dry_run:
                    conn.execute(
                        text("UPDATE folder SET auth_settings = :val WHERE id = :id"),
                        {"val": json.dumps(new_settings), "id": folder_id},
                    )
                migrated += 1
            except (json.JSONDecodeError, InvalidToken, TypeError, KeyError) as e:
                failed += 1
                print(f"   Warning: Could not migrate folder '{folder_name}': {e}")

        print(f"   {'Would migrate' if dry_run else 'Migrated'}: {migrated}, Failed: {failed}")
        total_migrated += migrated
        total_failed += failed

        # Rollback if dry run (transaction will auto-commit on exit otherwise)
        if dry_run:
            conn.rollback()

    # Save new key only after successful database migration
    if not dry_run:
        backup_file = config_dir / f"secret_key.backup.{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        write_secret_key_to_file(config_dir, old_key, backup_file.name)
        print(f"\n4. Backed up old key to: {backup_file}")
        write_secret_key_to_file(config_dir, new_key)
        print(f"5. Saved new secret key to: {config_dir / 'secret_key'}")
    else:
        print("\n4. [DRY RUN] Would backup old key")
        print(f"5. [DRY RUN] Would save new key to: {config_dir / 'secret_key'}")

    # Summary
    print("\n" + "=" * 50)
    if dry_run:
        print("DRY RUN COMPLETE")
        print(f"\nWould migrate {total_migrated} items, {total_failed} failures")
        print("\nRun without --dry-run to apply changes.")
    else:
        print("MIGRATION COMPLETE")
        print(f"\nMigrated {total_migrated} items, {total_failed} failures")
        print(f"\nBackup key location: {config_dir}/secret_key.backup.*")
        print("\nNext steps:")
        print("1. Start Langflow and verify everything works")
        print("2. Users must log in again (JWT sessions invalidated)")
        print("3. Once verified, you may delete the backup key file")

    if total_failed > 0:
        print(f"\nWarning: {total_failed} items could not be migrated.")
        print("These may have been encrypted with a different key or are corrupted.")
        sys.exit(1 if not dry_run else 0)


def main():
    default_config = get_config_dir()

    parser = argparse.ArgumentParser(
        description="Migrate Langflow encrypted data to a new secret key",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what will be migrated
  %(prog)s --dry-run

  # Run migration with defaults
  %(prog)s

  # Custom database and config
  %(prog)s --database-url postgresql://user:pass@host/db --config-dir /etc/langflow  # pragma: allowlist secret

  # Provide keys explicitly
  %(prog)s --old-key "current-key" --new-key "replacement-key"
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying anything",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=default_config,
        metavar="PATH",
        help=f"Langflow config directory (default: {default_config})",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        metavar="URL",
        help="Database connection URL (default: sqlite in config dir)",
    )
    parser.add_argument(
        "--old-key",
        type=str,
        default=None,
        metavar="KEY",
        help="Current secret key (default: read from config dir)",
    )
    parser.add_argument(
        "--new-key",
        type=str,
        default=None,
        metavar="KEY",
        help="New secret key (default: auto-generated)",
    )

    args = parser.parse_args()

    # Resolve database URL
    database_url = args.database_url or get_default_database_url(args.config_dir)
    if not database_url:
        print("Error: Could not determine database URL.")
        print(f"  No database found at {args.config_dir}/langflow.db")
        print("  Use --database-url to specify the database location")
        sys.exit(1)

    migrate(
        config_dir=args.config_dir,
        database_url=database_url,
        old_key=args.old_key,
        new_key=args.new_key,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
