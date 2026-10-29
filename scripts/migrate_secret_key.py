"""Migrate encrypted data from old secret key to new secret key.

This script handles the full key rotation lifecycle:
1. Reads the current secret key from config directory
2. Generates a new secret key (or uses one provided)
3. Re-encrypts all sensitive data in the database (atomic transaction)
4. Writes the new key to secret_key.new before the transaction commits
5. Backs up the old key
6. Moves the new key into place as secret_key

The keys are never printed. The output identifies the new key by a fingerprint,
the first 12 hex characters of the SHA-256 of the key.

Migrated database fields:
- user.store_api_key: Langflow Store API keys
- variable.value: All encrypted variable values
- folder.auth_settings: MCP oauth_client_secret and api_key fields
- sso_config.client_secret_encrypted: SSO/OIDC client secrets
- apikey.api_key: stored API key values
- deployment_provider_account.api_key: deployment provider credentials
- connection_secret.encrypted_payload: connection credentials
- trigger.signing_secret_encrypted: webhook trigger signing secrets
- mcp_server.config: secret values in the env and headers maps, and the
  --headers values in args

Run it with Langflow stopped, no background jobs queued and no OAuth connection
flows in progress. Every persisted job request override, OAuth verifier, and trigger cleanup
credential is covered. The legacy script still refuses active jobs and live
OAuth flows. New installations should use `langflow secrets rotate`, which also
records a durable database completion receipt and loads integration hooks.

Usage:
    uv run python scripts/migrate_secret_key.py --help
    uv run python scripts/migrate_secret_key.py --dry-run
    uv run python scripts/migrate_secret_key.py --database-url postgresql://...
    uv run python scripts/migrate_secret_key.py --old-key-file old.key --new-key-file new.key

Values given on the command line show up in the process list and shell history.
Keys can come from a file (--old-key-file, --new-key-file) or the environment
(LANGFLOW_OLD_SECRET_KEY, LANGFLOW_NEW_SECRET_KEY), and the database URL from
LANGFLOW_MIGRATION_TARGET_URL. A command-line value wins over the environment,
which wins over the defaults. LANGFLOW_DATABASE_URL is not read.
"""

import argparse
import os
import platform
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from langflow.services.secrets.crypto import (
    CREDENTIAL_TYPE,
    FERNET_MIN_TOKEN_BYTES,
    FERNET_TOKEN_COLUMNS,
    FERNET_VERSION_BYTE,
    MINIMUM_KEY_LENGTH,
    PENDING_KEY_FILENAME,
    SENSITIVE_AUTH_FIELDS,
    SSO_AAD,
    SSO_BASE64URL_ALPHABET,
    SSO_ENVELOPE_HEADER,
    SSO_ENVELOPE_PARTS,
    SSO_HEADER_PARTS,
    SSO_HKDF_INFO,
    SSO_HKDF_SALT,
    SSO_NONCE_BYTES,
    SSO_TAG_BYTES,
    _decode_sso_envelope,
    _derive_sso_key,
    decrypt_sso_secret_with_key,
    decrypt_with_key,
    encrypt_sso_secret_with_key,
    encrypt_with_key,
    ensure_valid_key,
    key_fingerprint,
    legacy_short_key,
    looks_like_fernet_token,
    migrate_auth_settings,
    migrate_mcp_config,
    migrate_sso_secret,
    migrate_value,
)
from platformdirs import user_cache_dir
from sqlalchemy import create_engine, inspect, make_url, text

# Compatibility exports for integrations importing the original script helpers.
__all__ = [
    "CREDENTIAL_TYPE",
    "FERNET_MIN_TOKEN_BYTES",
    "FERNET_TOKEN_COLUMNS",
    "FERNET_VERSION_BYTE",
    "MINIMUM_KEY_LENGTH",
    "PENDING_KEY_FILENAME",
    "SENSITIVE_AUTH_FIELDS",
    "SSO_AAD",
    "SSO_BASE64URL_ALPHABET",
    "SSO_ENVELOPE_HEADER",
    "SSO_ENVELOPE_PARTS",
    "SSO_HEADER_PARTS",
    "SSO_HKDF_INFO",
    "SSO_HKDF_SALT",
    "SSO_NONCE_BYTES",
    "SSO_TAG_BYTES",
    "_decode_sso_envelope",
    "_derive_sso_key",
    "decrypt_sso_secret_with_key",
    "decrypt_with_key",
    "encrypt_sso_secret_with_key",
    "encrypt_with_key",
    "ensure_valid_key",
    "key_fingerprint",
    "legacy_short_key",
    "looks_like_fernet_token",
    "migrate_auth_settings",
    "migrate_mcp_config",
    "migrate_sso_secret",
    "migrate_value",
]


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

            # The user SID must come from the process token: resolving by name
            # (LookupAccountName + GetUserName) returns the machine-domain SID
            # when the computer name equals the username, locking the user out.
            token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
            user, _attributes = win32security.GetTokenInformation(token, win32security.TokenUser)
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


def read_key_file(path: str) -> str:
    """Read a key from a file given on the command line, stripped like the config directory's secret_key."""
    try:
        key = Path(path).read_text(encoding="utf-8").strip()
    except OSError as e:
        raise argparse.ArgumentTypeError(e) from e
    if not key:
        msg = f"{path} is empty"
        raise argparse.ArgumentTypeError(msg)
    return key


def write_secret_key_to_file(config_dir: Path, key: str, filename: str = "secret_key") -> None:
    """Write a secret key to file with secure permissions."""
    config_dir.mkdir(parents=True, exist_ok=True)
    secret_file = config_dir / filename
    secret_file.write_text(key, encoding="utf-8")
    set_secure_permissions(secret_file)


def verify_migration(conn, new_key: str) -> tuple[int, int]:
    """Verify every persisted secret using the shared offline inventory."""
    from langflow.services.secrets.rotation import audit, load_participants

    report = audit(conn, new_key, participants=load_participants())
    return report.encrypted, len(report.failures)


def get_default_database_url(config_dir: Path) -> str | None:
    """Get database URL from default SQLite location."""
    default_db = config_dir / "langflow.db"
    if default_db.exists():
        return f"sqlite:///{default_db}"
    return None


def warn_env_secret_key(new_key: str | None = None, key_file: Path | None = None) -> None:
    """Langflow uses LANGFLOW_SECRET_KEY over the key file and writes it back over the file on start."""
    print("\n" + "!" * 50)
    print("LANGFLOW_SECRET_KEY is set in this environment. Langflow uses it instead of")
    print("the secret_key file and writes it back over that file on start. Set it to the")
    print("new key before starting Langflow, or every rotated secret decrypts to empty.")
    if new_key:
        print(f"\n  Set LANGFLOW_SECRET_KEY to the contents of {key_file}")
        print(f"  (key fingerprint: {key_fingerprint(new_key)})")
    print("!" * 50)


def ensure_no_pending_encrypted_work(conn) -> None:
    """Refuse rotation while jobs or OAuth callbacks may still need the old key."""
    if inspect(conn).has_table("job"):
        active_job = conn.execute(
            text("SELECT 1 FROM job WHERE status IN ('queued', 'in_progress', 'suspended') LIMIT 1")
        ).first()
        if active_job:
            print("Error: Queued, running, or suspended jobs must finish before rotating the secret key.")
            sys.exit(1)

    if inspect(conn).has_table("connection_oauth"):
        pending_oauth = conn.execute(
            text("SELECT 1 FROM connection_oauth WHERE encrypted_verifier IS NOT NULL AND expires_at > :now LIMIT 1"),
            {"now": datetime.now(timezone.utc)},
        ).first()
        if pending_oauth:
            print("Error: Pending OAuth connection flows must finish before rotating the secret key.")
            sys.exit(1)


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
    succeed or none are applied. The new key is written to secret_key.new just
    before the commit and replaces secret_key after it, so a run that stops in
    between leaves the key on disk.
    """
    # Determine old key
    if not old_key:
        old_key = read_secret_key_from_file(config_dir)
    if not old_key:
        print("Error: Could not find current secret key.")
        print(f"  Checked: {config_dir}/secret_key")
        print("  Use --old-key-file or LANGFLOW_OLD_SECRET_KEY to provide it explicitly")
        sys.exit(1)

    # Determine new key
    if not new_key:
        new_key = secrets.token_urlsafe(32)
        print(f"Generated new secret key, fingerprint: {key_fingerprint(new_key)}")
    else:
        print(f"Using provided new key, fingerprint: {key_fingerprint(new_key)}")
    print("  (The key is only written to the key file, never printed)")

    try:
        Fernet(ensure_valid_key(new_key))
    except ValueError:
        print("Error: The new secret key is not usable: 32+ characters must be url-safe base64 of 32 bytes")
        sys.exit(1)

    if old_key == new_key:
        print("Error: Old and new secret keys are the same")
        sys.exit(1)

    print("\nConfiguration:")
    print(f"  Config dir: {config_dir}")
    # Drivers take credentials from query parameters too (password, passfile, options), so none are shown.
    url = make_url(database_url)
    query_note = " (query parameters not shown)" if url.query else ""
    redacted_database_url = url.set(query={}).render_as_string(hide_password=True)
    print(f"  Database: {redacted_database_url}{query_note}")
    print(f"  Dry run: {dry_run}")
    if os.environ.get("LANGFLOW_SECRET_KEY"):
        warn_env_secret_key()

    secret_file = config_dir / "secret_key"
    pending_file = config_dir / PENDING_KEY_FILENAME
    if pending_file.exists():
        pending_fingerprint = key_fingerprint(pending_file.read_text(encoding="utf-8"))
        print(f"\nA previous run stopped before saving its new key: {pending_file} exists.")
        print(f"The database may already be encrypted with the key in that file (fingerprint: {pending_fingerprint}).")
        print(f"To find out, run with --dry-run --old-key-file {pending_file}:")
        print(f"  0 failures: the database is on that key. Move {pending_file} to {secret_file}.")
        print(f"  Failures: the database is not on that key. Delete {pending_file}.")
        if not dry_run:
            print("Nothing was changed.")
            sys.exit(1)

    if dry_run:
        print("\n[DRY RUN] No changes will be made.\n")

    from langflow.services.secrets.rotation import RotationError, _locations, _lock, audit, load_participants, rewrap

    engine = create_engine(database_url, hide_parameters=True)
    participants = load_participants()
    total_migrated = 0
    total_failed = 0
    step = 1
    with engine.connect() as conn:
        if not dry_run:
            _lock(conn, _locations(conn, participants))
        conn.execute(text('SELECT id FROM "user" LIMIT 0'))
        ensure_no_pending_encrypted_work(conn)
        report = audit(conn, old_key, participants=participants)
        total_failed = len(report.failures)
        total_migrated = report.encrypted
        for finding in report.failures:
            print(f"   Could not decrypt {finding.table}.{finding.column} for row {finding.row_id}")
        if total_failed and not dry_run:
            print(f"ERROR: {total_failed} values could not be migrated.")
            print("Rolling back all database changes; the secret key was not changed.")
            sys.exit(1)
        if not dry_run:
            try:
                for participant in participants:
                    participant.preflight()
                rewrap(conn, old_key, new_key, participants=participants)
            except RotationError:
                print("Complete verification failed; rolling back all database changes.")
                sys.exit(1)
            try:
                write_secret_key_to_file(config_dir, new_key, PENDING_KEY_FILENAME)
            except BaseException:
                pending_file.unlink(missing_ok=True)
                raise
            conn.commit()
            print(f"Verified all {total_migrated} encrypted values with the new key")
        else:
            conn.rollback()

    # Move the new key into place only after the database commit
    if not dry_run:
        backup_file = config_dir / f"secret_key.backup.{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        try:
            write_secret_key_to_file(config_dir, old_key, backup_file.name)
            print(f"\n{step + 1}. Backed up old key to: {backup_file}")
            pending_file.replace(secret_file)
        except OSError as e:
            print(f"\nERROR: The database is now encrypted with the new key, but saving the key failed: {e}")
            print(f"The new key is in {pending_file}. Move it to {secret_file} before starting Langflow.")
            sys.exit(1)
        print(f"{step + 2}. Saved new secret key to: {secret_file}")
    else:
        print(f"\n{step + 1}. [DRY RUN] Would backup old key")
        print(f"{step + 2}. [DRY RUN] Would save new key to: {secret_file}")

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
        print("1. If Langflow gets LANGFLOW_SECRET_KEY (environment, .env file, secret store), set it to the new key:")
        print(f"   the contents of {secret_file}")
        print("2. Start Langflow and verify everything works")
        print("3. Users must log in again (JWT sessions invalidated)")
        print("4. Once verified, you may delete the backup key file")
        if os.environ.get("LANGFLOW_SECRET_KEY"):
            warn_env_secret_key(new_key, secret_file)

    if total_failed > 0:
        print(f"\nWarning: {total_failed} items could not be migrated.")
        print("These may have been encrypted with a different key or are corrupted.")
        sys.exit(1)


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
  %(prog)s --database-url postgresql://user@host/db --config-dir /etc/langflow

  # Keys from files, which keeps them out of the process list and shell history
  %(prog)s --old-key-file old.key --new-key-file new.key

Environment variables, used when the matching option is not given:
  LANGFLOW_MIGRATION_TARGET_URL  Database URL. Use it for a URL that holds a password.
  LANGFLOW_OLD_SECRET_KEY        Current secret key
  LANGFLOW_NEW_SECRET_KEY        New secret key
  LANGFLOW_CONFIG_DIR            Langflow config directory
LANGFLOW_DATABASE_URL is not read.
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
        help="Database connection URL (default: LANGFLOW_MIGRATION_TARGET_URL, then sqlite in config dir)",
    )
    old_key_group = parser.add_mutually_exclusive_group()
    old_key_group.add_argument(
        "--old-key",
        type=str,
        default=None,
        metavar="KEY",
        help="Current secret key. Shows in the process list: prefer --old-key-file",
    )
    old_key_group.add_argument(
        "--old-key-file",
        dest="old_key",
        type=read_key_file,
        metavar="PATH",
        help="File holding the current secret key (default: LANGFLOW_OLD_SECRET_KEY, then secret_key in config dir)",
    )
    new_key_group = parser.add_mutually_exclusive_group()
    new_key_group.add_argument(
        "--new-key",
        type=str,
        default=None,
        metavar="KEY",
        help="New secret key. Shows in the process list: prefer --new-key-file",
    )
    new_key_group.add_argument(
        "--new-key-file",
        dest="new_key",
        type=read_key_file,
        metavar="PATH",
        help="File holding the new secret key (default: LANGFLOW_NEW_SECRET_KEY, then auto-generated)",
    )

    parser.add_argument(
        "--writers-stopped", action="store_true", help="Attest all web processes, workers, and listeners are stopped"
    )
    parser.add_argument("--backup-file", type=Path, help="Verified database backup artifact")
    parser.add_argument("--backup-sha256", help="Independently recorded SHA-256 of the backup")

    args = parser.parse_args()

    # Resolve database URL
    database_url = (
        args.database_url
        or os.environ.get("LANGFLOW_MIGRATION_TARGET_URL")
        or get_default_database_url(args.config_dir)
    )
    if not database_url:
        print("Error: Could not determine database URL.")
        print(f"  No database found at {args.config_dir}/langflow.db")
        print("  Use --database-url or LANGFLOW_MIGRATION_TARGET_URL to specify the database location")
        sys.exit(1)

    if not args.dry_run:
        from langflow.services.secrets.rotation import RotationError, verify_backup

        if not args.writers_stopped or args.backup_file is None or not args.backup_sha256:
            parser.error("Non-dry runs require --writers-stopped, --backup-file, and --backup-sha256")
        backup_engine = create_engine(database_url, hide_parameters=True)
        try:
            verify_backup(backup_engine, args.backup_file, args.backup_sha256)
        except RotationError as exc:
            parser.error(str(exc))
        finally:
            backup_engine.dispose()

    migrate(
        config_dir=args.config_dir,
        database_url=database_url,
        old_key=args.old_key or os.environ.get("LANGFLOW_OLD_SECRET_KEY"),
        new_key=args.new_key or os.environ.get("LANGFLOW_NEW_SECRET_KEY"),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
