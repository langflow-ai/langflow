"""Fail-closed, offline audit and atomic database rewrapping.

The completion receipt covers the database only. Operators activate the new
root in every process before restarting; no root key is written by this module.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import MetaData, Table, inspect, select, update

from langflow.services.auth.mcp_encryption import MCP_SECRET_CONFIG_MAPS, _argv_secret_positions
from langflow.services.secrets.crypto import (
    decrypt_sso_secret_with_key,
    decrypt_with_key,
    encrypt_sso_secret_with_key,
    encrypt_with_key,
    ensure_valid_key,
    looks_like_fernet_token,
    receipt_fingerprint,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.engine import Connection, Engine


MAX_INSTANCE_UID_LENGTH = 128


@dataclass(frozen=True)
class SecretLocation:
    """A trusted schema location supplied by Langflow or an installed participant."""

    table: str
    primary_key: str
    column: str
    codec: str = "fernet"
    json_path: tuple[str | int, ...] = ()
    allow_plaintext: bool = False
    selector: str = "direct"


LOCATIONS = (
    SecretLocation("user", "id", "store_api_key", allow_plaintext=True),
    SecretLocation("variable", "id", "value", selector="credential"),
    SecretLocation("folder", "id", "auth_settings", selector="folder"),
    SecretLocation("apikey", "id", "api_key", allow_plaintext=True),
    SecretLocation("deployment_provider_account", "id", "api_key", allow_plaintext=True),
    SecretLocation("connection_secret", "connection_id", "encrypted_payload"),
    SecretLocation("connection_oauth", "connection_id", "encrypted_verifier"),
    SecretLocation("trigger", "id", "signing_secret_encrypted"),
    SecretLocation("trigger_cleanup", "id", "encrypted_credential"),
    SecretLocation("job", "job_id", "job_metadata", selector="job"),
    SecretLocation("mcp_server", "id", "config", allow_plaintext=True, selector="mcp"),
    SecretLocation("sso_config", "id", "client_secret_encrypted", codec="sso"),
)


@dataclass(frozen=True)
class Finding:
    """Safe diagnostic: schema identifiers and row ID, never data or exceptions."""

    table: str
    row_id: str
    column: str
    reason: str


@dataclass
class AuditReport:
    encrypted: int = 0
    failures: list[Finding] = field(default_factory=list)
    plaintext: list[Finding] = field(default_factory=list)
    rotation_id: str | None = None


class RotationError(RuntimeError):
    def __init__(self, message: str, report: AuditReport | None = None) -> None:
        super().__init__(message)
        self.report = report


class RotationParticipant(Protocol):
    """Installed integrations extend the inventory and join its transaction.

    ``preflight`` must positively finish any external-state invalidation or
    raise. Such invalidation is intentionally not rolled back (users retry
    pending logins); a failure never commits the database or its receipt.
    ``prepare`` updates database metadata such as SSO revision counters only.
    Neither method may log secrets or call the runtime auth service.
    """

    def locations(self, conn: Connection) -> Iterable[SecretLocation]: ...

    def preflight(self) -> None: ...

    def prepare(self, conn: Connection) -> None: ...


def load_participants() -> tuple[RotationParticipant, ...]:
    """Load explicit offline hooks, without starting any runtime services."""
    try:
        return tuple(entry.load()() for entry in entry_points(group="langflow.secret_rotation"))
    except Exception:  # noqa: BLE001 - sanitize driver and plugin errors that can contain secrets
        msg = "An installed secret rotation participant could not load."
        raise RotationError(msg) from None


def _locations(conn: Connection, participants: Iterable[RotationParticipant]) -> tuple[SecretLocation, ...]:
    locations = (*LOCATIONS, *(location for participant in participants for location in participant.locations(conn)))
    supplied = {location.table for location in locations}
    enterprise_tables = {"sso_connection_revision", "variable_transfer"}
    if (set(inspect(conn).get_table_names()) & enterprise_tables) - supplied:
        msg = "Enterprise secret storage is present; install its matching rotation participant before proceeding."
        raise RotationError(msg)
    return locations


def _paths(location: SecretLocation, value: Any) -> list[tuple[str | int, ...]]:
    if location.selector == "folder":
        return [(key,) for key in ("oauth_client_secret", "api_key") if value.get(key)]
    if location.selector == "mcp":
        paths: list[tuple[str | int, ...]] = []
        for map_name in MCP_SECRET_CONFIG_MAPS:
            values = value.get(map_name)
            if isinstance(values, dict):
                paths.extend((map_name, key) for key, item in values.items() if item)
        paths.extend(("args", index) for index in _argv_secret_positions(value.get("args")))
        return paths
    if location.selector == "job":
        if not value.get("request_overrides"):
            return []
        if value.get("request_overrides_format") != "fernet-json-v1":
            msg = "Unsupported request override format"
            raise ValueError(msg)
        return [("request_overrides",)]
    if location.json_path:
        try:
            _get(value, location.json_path)
        except KeyError:
            return []
    return [location.json_path]


def _get(value: Any, path: tuple[str | int, ...]) -> Any:
    for key in path:
        value = value[key]
    return value


def _set(value: Any, path: tuple[str | int, ...], replacement: str) -> Any:
    if not path:
        return replacement
    parent = _get(value, path[:-1])
    parent[path[-1]] = replacement
    return value


def _scan(
    conn: Connection, key: str, locations: Iterable[SecretLocation], *, new_key: str | None = None
) -> AuditReport:
    report = AuditReport()
    metadata = MetaData()
    available = set(inspect(conn).get_table_names())
    for location in locations:
        if location.table not in available:
            continue
        table = Table(location.table, metadata, autoload_with=conn, extend_existing=True)
        if location.column not in table.c or location.primary_key not in table.c:
            msg = "A secret storage table is missing an expected column."
            raise RotationError(msg)
        statement = select(table.c[location.primary_key], table.c[location.column])
        if location.selector == "credential":
            statement = statement.where(table.c.type == "Credential")
        for row_id, stored in conn.execute(statement):
            if stored is None or stored == "":
                continue
            safe = {"table": location.table, "row_id": str(row_id), "column": location.column}
            structured = location.selector in {"folder", "mcp", "job"} or bool(location.json_path)
            try:
                value = json.loads(stored) if structured and isinstance(stored, str) else copy.deepcopy(stored)
                if structured and value is None:
                    continue
                paths = _paths(location, value)
                changed = False
                for path in paths:
                    encrypted = _get(value, path)
                    if encrypted is None or encrypted == "":
                        continue
                    if not isinstance(encrypted, str):
                        msg = "Invalid secret value type"
                        raise TypeError(msg)
                    if location.codec == "fernet" and not looks_like_fernet_token(encrypted):
                        if location.allow_plaintext and not encrypted.startswith("gAAAA"):
                            # Preserve supported legacy plaintext; report it separately.
                            report.plaintext.append(Finding(**safe, reason="legacy_plaintext"))
                            continue
                        msg = "Expected ciphertext"
                        raise TypeError(msg)
                    if location.codec == "sso":
                        plaintext = decrypt_sso_secret_with_key(encrypted, key)
                        encrypt = encrypt_sso_secret_with_key
                    elif location.codec == "fernet":
                        plaintext = decrypt_with_key(encrypted, key)
                        encrypt = encrypt_with_key
                    else:
                        msg = "Unsupported codec"
                        raise ValueError(msg)
                    report.encrypted += 1
                    if new_key is not None:
                        value = _set(value, path, encrypt(plaintext, new_key))
                        changed = True
                if changed:
                    # Reflection preserves real JSON/JSONB bindings. Text-backed
                    # fixtures and historic SQLite schemas require explicit JSON.
                    replacement = json.dumps(value) if structured and isinstance(stored, str) else value
                    conn.execute(
                        update(table)
                        .where(table.c[location.primary_key] == row_id)
                        .values({location.column: replacement})
                    )
            except (InvalidToken, InvalidTag, ValueError, TypeError, KeyError, IndexError, AttributeError):
                report.failures.append(Finding(**safe, reason="unreadable_secret"))
    return report


def audit(conn: Connection, key: str, *, participants: Iterable[RotationParticipant] = ()) -> AuditReport:
    """Read every stored secret directly; never print or mutate values."""
    return _scan(conn, key, _locations(conn, participants))


def rewrap(
    conn: Connection, old_key: str, new_key: str, *, participants: Iterable[RotationParticipant] = ()
) -> AuditReport:
    """Reuse the complete inventory inside a caller-owned locked transaction."""
    participants = tuple(participants)
    locations = _locations(conn, participants)
    report = _scan(conn, old_key, locations)
    if report.failures:
        msg = "Secret audit failed; no database changes were committed."
        raise RotationError(msg, report)
    migrated = _scan(conn, old_key, locations, new_key=new_key)
    if migrated.failures:
        msg = "Secret rewrapping failed; no database changes were committed."
        raise RotationError(msg, migrated)
    for participant in participants:
        participant.prepare(conn)
    verified = _scan(conn, new_key, locations)
    if verified.failures or verified.encrypted != report.encrypted:
        msg = "Complete post-rotation verification failed; no database changes were committed."
        raise RotationError(msg, verified)
    return report


def verify_backup(engine: Engine, backup_file: Path, expected_sha256: str) -> str:
    """Check the operator's backup artifact against its independently recorded digest."""
    try:
        path = backup_file.resolve(strict=True)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError
        if (
            engine.dialect.name == "sqlite"
            and engine.url.database
            and Path(engine.url.database).exists()
            and path.samefile(engine.url.database)
        ):
            raise ValueError
        digest = hashlib.sha256()
        with path.open("rb") as backup:
            for chunk in iter(lambda: backup.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = digest.hexdigest()
        if not hmac.compare_digest(actual, expected_sha256.lower()):
            raise ValueError
    except (OSError, ValueError):
        msg = "A nonempty backup file and its matching SHA-256 digest are required."
        raise RotationError(msg) from None
    else:
        return actual


def _lock(conn: Connection, locations: Iterable[SecretLocation]) -> None:
    if conn.dialect.name == "sqlite":
        conn.exec_driver_sql("BEGIN IMMEDIATE")
    elif conn.dialect.name == "postgresql":
        existing = set(inspect(conn).get_table_names())
        tables = sorted(({location.table for location in locations} | {"secret_rotation"}) & existing)
        quoted = ", ".join(conn.dialect.identifier_preparer.quote(table) for table in tables)
        conn.exec_driver_sql(f"LOCK TABLE {quoted} IN ACCESS EXCLUSIVE MODE NOWAIT")
    else:
        msg = "Offline rotation supports SQLite and PostgreSQL only."
        raise RotationError(msg)


def rotate(
    *,
    engine: Engine,
    old_key: str,
    new_key: str,
    backup_file: Path,
    backup_sha256: str,
    writers_stopped: bool,
    participants: Iterable[RotationParticipant] = (),
    instance_uid: str | None = None,
) -> AuditReport:
    """Rotate and verify all database ciphertext, committing a receipt last."""
    if instance_uid is not None and (not instance_uid.strip() or len(instance_uid) > MAX_INSTANCE_UID_LENGTH):
        msg = "Instance UID must be nonempty and at most 128 characters."
        raise RotationError(msg)
    if not writers_stopped:
        msg = "Stop all web processes, workers, and listeners and attest with --writers-stopped."
        raise RotationError(msg)
    if not old_key or not new_key or old_key == new_key:
        msg = "Distinct nonempty old and new keys are required."
        raise RotationError(msg)
    try:
        Fernet(ensure_valid_key(new_key))
    except ValueError:
        msg = "The new key is not a usable Fernet root key."
        raise RotationError(msg) from None
    backup_digest = verify_backup(engine, backup_file, backup_sha256)
    participants = tuple(participants)
    try:
        with engine.connect() as conn:
            locations = _locations(conn, participants)
            _lock(conn, locations)
            if not inspect(conn).has_table("secret_rotation"):
                msg = "Apply the secret rotation schema migration before rotating."
                raise RotationError(msg)
            # Audit before external invalidation. External transient state cannot
            # share a database transaction, so any failure leaves no receipt.
            before = _scan(conn, old_key, locations)
            if before.failures:
                msg = "Secret audit failed; no database changes were committed."
                raise RotationError(msg, before)
            for participant in participants:
                participant.preflight()
            report = rewrap(conn, old_key, new_key, participants=participants)
            receipt = Table("secret_rotation", MetaData(), autoload_with=conn)
            rotation_id = str(uuid4())
            conn.execute(
                receipt.insert().values(
                    id=rotation_id,
                    instance_uid=instance_uid,
                    old_fingerprint=receipt_fingerprint(old_key),
                    new_fingerprint=receipt_fingerprint(new_key),
                    backup_sha256=backup_digest,
                    rotated_values=report.encrypted,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            conn.commit()
            report.rotation_id = rotation_id
            return report
    except RotationError:
        raise
    except Exception:  # noqa: BLE001 - sanitize driver and plugin errors that can contain secrets
        # Driver and plugin exceptions can include bound values or credentials.
        msg = "Rotation failed; no success receipt was confirmed. Keep writers stopped and inspect safely."
        raise RotationError(msg) from None
