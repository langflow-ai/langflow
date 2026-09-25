"""Report where an instance disagrees with itself.

Langflow keeps state in the database and in places that are not the database:
encrypted columns that only the configured secret key opens, file bytes in the
storage backend, vectors in each knowledge base's store, and a compiled Casbin
policy. Nothing checks that those agree, and when they don't, nothing raises until
someone opens the flow, file or memory that depends on it.

Each check reads and reports. None of them writes, repairs or deletes, so this is
safe to run against production: after a restore, an upgrade, a migration, or when a
customer reports flows failing for no visible reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, Literal

from cryptography.fernet import InvalidToken
from sqlmodel import func, select

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.settings.service import SettingsService

Status = Literal["ok", "warn", "fail"]

# A failing check names this many examples, enough to find the pattern.
_EXAMPLES = 5
# Every Fernet token starts with its version byte, 0x80, which is "gAAAAA" in base64.
_FERNET_PREFIX = "gAAAAA"


@dataclass
class CheckResult:
    name: str
    status: Status
    summary: str
    problems: list[str] = field(default_factory=list)


@dataclass
class IntegrityReport:
    checks: list[CheckResult]

    @property
    def ok(self) -> bool:
        return all(check.status != "fail" for check in self.checks)


async def check_instance() -> IntegrityReport:
    """Run every check against the running instance's configuration."""
    from langflow.services.deps import session_scope

    # One session, and it never commits: everything here is a read.
    async with session_scope() as session:
        checks = [
            await check_credentials(session),
            await check_files(session),
        ]
        kb_checks, vector_counts = await _check_knowledge_bases(session)
        checks += kb_checks
        checks.append(await check_memory_bases(session, vector_counts))
        checks.append(await check_authorization(session))
        await session.rollback()
    return IntegrityReport(checks)


def _result(name: str, problems: list[str], ok_summary: str, fail_summary: str) -> CheckResult:
    if not problems:
        return CheckResult(name, "ok", ok_summary)
    return CheckResult(name, "fail", fail_summary, problems[:_EXAMPLES])


# ---- credentials ---------------------------------------------------------------


async def check_credentials(session: AsyncSession, settings_service: SettingsService | None = None) -> CheckResult:
    """Can the configured secret key open every encrypted value?

    The app's own decryption returns an empty string on failure and logs below the
    default level, so a wrong key looks like a blank credential. This decrypts each
    value itself and counts the ones that do not open. Pass ``settings_service`` to
    ask the same question of another key, such as the one a migration target holds.
    """
    from langflow.services.auth.utils import get_fernet_for_decryption
    from langflow.services.deps import get_settings_service

    settings_service = settings_service or get_settings_service()
    fernet = get_fernet_for_decryption(settings_service)
    counted = 0
    problems = []
    for column, row_id, value in await _encrypted_values(session):
        counted += 1
        try:
            if column == "sso_config.client_secret_encrypted":
                from langflow.services.database.models.auth.sso_secret import decrypt_sso_client_secret

                decrypt_sso_client_secret(value, settings_service)
            else:
                fernet.decrypt(value.encode())
        except (InvalidToken, ValueError, TypeError):
            problems.append(f"{column} row {row_id}")
    return _result(
        "credentials",
        problems,
        f"{counted} encrypted values, all open with the configured secret key",
        f"{len(problems)} of {counted} encrypted values do not open with the configured secret key",
    )


async def _encrypted_values(session: AsyncSession) -> list[tuple[str, Any, str]]:
    """Every encrypted value as (column, row id, ciphertext). Plaintext values are not counted."""
    from langflow.services.auth.mcp_encryption import (
        MCP_SECRET_CONFIG_MAPS,
        SENSITIVE_FIELDS,
        _argv_secret_positions,
    )
    from langflow.services.database.models.api_key.model import ApiKey
    from langflow.services.database.models.auth.sso import SSOConfig
    from langflow.services.database.models.connection.model import ConnectionSecret
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.mcp_server.model import MCPServer
    from langflow.services.database.models.user.model import User
    from langflow.services.database.models.variable.model import Variable
    from langflow.services.variable.constants import CREDENTIAL_TYPE

    values: list[tuple[str, Any, str]] = []

    def add(column: str, rows: Iterable[tuple[Any, Any]]) -> None:
        values.extend(
            (column, row_id, value)
            for row_id, value in rows
            if isinstance(value, str) and value.startswith(_FERNET_PREFIX)
        )

    # Generic variables are stored as typed, so only credentials are encrypted.
    add(
        "variable.value",
        await session.exec(select(Variable.id, Variable.value).where(Variable.type == CREDENTIAL_TYPE)),
    )
    add("apikey.api_key", await session.exec(select(ApiKey.id, ApiKey.api_key)))
    add("user.store_api_key", await session.exec(select(User.id, User.store_api_key)))
    add(
        "deployment_provider_account.api_key",
        await session.exec(select(DeploymentProviderAccount.id, DeploymentProviderAccount.api_key)),
    )
    add(
        "connection_secret.encrypted_payload",
        await session.exec(select(ConnectionSecret.connection_id, ConnectionSecret.encrypted_payload)),
    )

    for folder_id, settings in await session.exec(select(Folder.id, Folder.auth_settings)):
        if isinstance(settings, dict):
            add("folder.auth_settings", ((folder_id, settings.get(key)) for key in SENSITIVE_FIELDS))

    for server_id, config in await session.exec(select(MCPServer.id, MCPServer.config)):
        if not isinstance(config, dict):
            continue
        for map_name in MCP_SECRET_CONFIG_MAPS:
            secrets = config.get(map_name)
            if isinstance(secrets, dict):
                add(f"mcp_server.config.{map_name}", ((server_id, value) for value in secrets.values()))
        args = config.get("args")
        add("mcp_server.config.args", ((server_id, args[i]) for i in _argv_secret_positions(args)))

    # SSO secrets are an AES-GCM envelope, not a Fernet token, so they are taken as stored.
    values.extend(
        ("sso_config.client_secret_encrypted", row_id, value)
        for row_id, value in await session.exec(select(SSOConfig.id, SSOConfig.client_secret_encrypted))
        if value
    )
    return values


# ---- files ---------------------------------------------------------------------


async def check_files(session: AsyncSession) -> CheckResult:
    """Does every file row resolve to bytes in the configured storage?

    Readers resolve a file from its owner and the basename of ``path``, so this
    asks the storage backend the same question they do.
    """
    from langflow.services.database.models.file.model import File
    from langflow.services.deps import get_storage_service

    storage = get_storage_service()
    rows = (await session.exec(select(File.id, File.user_id, File.path))).all()
    problems = []
    # ponytail: one storage call per row, sequentially; batch per owner if a large instance makes this slow.
    for file_id, user_id, path in rows:
        name = PurePosixPath(path).name
        try:
            await storage.get_file_size(flow_id=str(user_id), file_name=name)
        except FileNotFoundError:
            problems.append(f"file {file_id} ({name}): no bytes in storage")
        except Exception as exc:  # noqa: BLE001 - reported per file
            problems.append(f"file {file_id} ({name}): {type(exc).__name__}")
    return _result(
        "files",
        problems,
        f"{len(rows)} file rows, all resolve in storage",
        f"{len(problems)} of {len(rows)} file rows point at bytes storage does not hold",
    )


# ---- knowledge bases and vector counts -----------------------------------------


async def _check_knowledge_bases(
    session: AsyncSession,
) -> tuple[list[CheckResult], dict[tuple[UUID, str], int | None]]:
    """Two checks from one pass: can each backend be reached, and does its count match the row.

    Returns the vector count per (owner, knowledge base) for the memory base check,
    with None where the store could not be read.
    """
    from lfx.base.knowledge_bases.backends import create_backend

    from langflow.api.utils.kb_helpers import resolve_local_store_path
    from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
    from langflow.services.database.models.user.model import User

    rows = (
        await session.exec(
            select(KnowledgeBaseRecord, User.username).join(User, User.id == KnowledgeBaseRecord.user_id)
        )
    ).all()
    unreachable: list[str] = []
    mismatched: list[str] = []
    counts: dict[tuple[UUID, str], int | None] = {}

    for record, owner in rows:
        label = f"{owner}/{record.name} ({record.backend_type})"
        counts[(record.user_id, record.name)] = None
        try:
            kb_path = resolve_local_store_path(
                record.name,
                owner,
                backend_type=record.backend_type,
                backend_config=record.backend_config,
                create=False,
            )
            if kb_path is not None and not kb_path.exists():
                # A local store that was never written to has no directory yet. Opening
                # one would create it, and this check does not write.
                count = 0
            else:
                backend = create_backend(
                    record.backend_type,
                    kb_name=record.name,
                    kb_path=kb_path,
                    backend_config=record.backend_config,
                    user_id=record.user_id,
                )
                try:
                    connection = await backend.test_connection()
                    if not connection.ok:
                        unreachable.append(f"{label}: {connection.message}")
                        continue
                    count = await backend.count()
                finally:
                    await backend.teardown()
        except Exception as exc:  # noqa: BLE001 - reported per knowledge base
            unreachable.append(f"{label}: {type(exc).__name__}: {exc}")
            continue

        counts[(record.user_id, record.name)] = count
        if count != record.chunks:
            mismatched.append(f"{label}: store holds {count}, row records {record.chunks}")

    reachable = len(rows) - len(unreachable)
    return [
        _result(
            "knowledge bases",
            unreachable,
            f"{len(rows)} knowledge bases, every backend reachable",
            f"{len(unreachable)} of {len(rows)} knowledge bases have a backend that cannot be built or reached",
        ),
        _result(
            "vector counts",
            mismatched,
            f"{reachable} reachable knowledge bases, each store count matches its row",
            f"{len(mismatched)} of {reachable} reachable knowledge bases hold a different count than their row",
        ),
    ], counts


# ---- memory bases --------------------------------------------------------------


async def check_memory_bases(session: AsyncSession, vector_counts: dict[tuple[UUID, str], int | None]) -> CheckResult:
    """Do memory bases that record ingested messages have vectors to show for them?

    A cursor advances only after a confirmed write, so a message marked ingested is
    never processed again. If the knowledge base behind it is gone or empty, the
    agent believes it has memories it cannot retrieve. This checks that much; it
    does not match individual messages to individual vectors.
    """
    from langflow.services.database.models.memory_base.model import MemoryBase, MessageIngestionRecord

    rows = (
        await session.exec(
            select(MemoryBase.id, MemoryBase.user_id, MemoryBase.name, MemoryBase.kb_name, func.count())
            .join(MessageIngestionRecord, MessageIngestionRecord.memory_base_id == MemoryBase.id)
            .group_by(MemoryBase.id, MemoryBase.user_id, MemoryBase.name, MemoryBase.kb_name)
        )
    ).all()
    problems = []
    for _memory_id, user_id, name, kb_name, ingested in rows:
        key = (user_id, kb_name)
        if key not in vector_counts:
            problems.append(f"memory base '{name}': {ingested} messages recorded, knowledge base '{kb_name}' missing")
        elif vector_counts[key] == 0:
            problems.append(f"memory base '{name}': {ingested} messages recorded, knowledge base '{kb_name}' is empty")
        # None means the store could not be read, which the knowledge base check already reports.
    return _result(
        "memory bases",
        problems,
        f"{len(rows)} memory bases with ingested messages, each backed by a non-empty knowledge base",
        f"{len(problems)} of {len(rows)} memory bases record ingested messages their knowledge base does not hold",
    )


# ---- authorization -------------------------------------------------------------


async def check_authorization(session: AsyncSession) -> CheckResult:
    """Does every role assignment resolve, and did each one compile into a policy rule?

    An authorization plugin compiles assignments into Casbin ``g`` rules and skips
    any whose role it cannot find, with only a log warning. The user keeps an
    assignment that looks right and grants nothing.
    """
    from langflow.services.database.models.auth.authz import AuthzRole, AuthzRoleAssignment, CasbinRule

    role_ids = set((await session.exec(select(AuthzRole.id))).all())
    assignments = (
        await session.exec(select(AuthzRoleAssignment.id, AuthzRoleAssignment.role_id, AuthzRoleAssignment.user_id))
    ).all()
    problems = [
        f"assignment {assignment_id}: role {role_id} does not exist"
        for assignment_id, role_id, _ in assignments
        if role_id not in role_ids
    ]

    compiled = (await session.exec(select(func.count()).select_from(CasbinRule))).one()
    if compiled == 0:
        # OSS ships no plugin, so nothing compiles a policy and there is nothing to compare.
        note = "no compiled policy in casbin_rule, so assignments were not compared with it"
    else:
        # A plugin may compile one assignment into several rules (one per domain, say),
        # so compare who holds a role, not how many rules there are.
        with_role = set(
            (
                await session.exec(
                    select(CasbinRule.v0).where(CasbinRule.ptype == "g", CasbinRule.v1.like("role:%")).distinct()
                )
            ).all()
        )
        assigned = {f"user:{user_id}" for _, _, user_id in assignments}
        missing = sorted(assigned - with_role)
        note = f"{len(assigned) - len(missing)} of {len(assigned)} assigned users have a compiled role rule"
        problems.extend(
            f"{subject} has a role assignment but no compiled role rule: the policy sync skipped it or is stale"
            for subject in missing
        )
    return _result(
        "authorization",
        problems,
        f"{len(assignments)} role assignments, all resolve; {note}",
        f"{len(problems)} authorization problems",
    )
