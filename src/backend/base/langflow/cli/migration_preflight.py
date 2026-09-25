"""Refuse a migration that cannot succeed, before anything moves.

The integrity check answers questions about one instance. A migration adds the
questions that need a source and a target together: will the target's migrations
run forward from the source's schema, will the target's key open the source's
credentials, will the default superuser survive the target's first boot, and will
the role grants be enforced once it has.
Several of these failed silently in a rehearsal against the IBM Langflow operator,
so each is checked here instead.

Read-only, like the integrity check it runs against the source.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlmodel import func, select

from langflow.cli.integrity import CheckResult, IntegrityReport, check_credentials, check_instance

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

# How to read the revision a target image runs, for --target-revision.
TARGET_REVISION_HINT = (
    'read it from the target image: python -c "import langflow, pathlib; from alembic.config import Config; '
    "from alembic.script import ScriptDirectory; c = Config(); c.set_main_option('script_location', "
    "str(pathlib.Path(langflow.__file__).parent / 'alembic')); print(ScriptDirectory.from_config(c).get_heads())\""
)

_SUPERUSER_WORKAROUND = (
    "UPDATE \"user\" SET last_login_at = now() WHERE username = 'langflow' AND last_login_at IS NULL;"
)


async def run_preflight(
    *,
    target_revision: str | None = None,
    target_secret_key: str | None = None,
) -> IntegrityReport:
    """Run the migration checks, then the source's own integrity checks."""
    from langflow.services.deps import session_scope

    async with session_scope() as session:
        checks = [
            await check_version_direction(session, target_revision),
            await check_default_superuser(session),
            await check_target_key(session, target_secret_key),
            await check_embedding_models(session),
            await check_role_assignments(session),
        ]
        await session.rollback()
    source = await check_instance()
    checks += [replace(check, name=f"source: {check.name}") for check in source.checks]
    return IntegrityReport(checks)


async def check_version_direction(session: AsyncSession, target_revision: str | None) -> CheckResult:
    """Attaching runs the target's migrations, which only move forward.

    So the source's revision has to be one the target's image already contains.
    A source ahead of the target would need migrations run backwards, which no
    Langflow supports.
    """
    name = "version"
    if not target_revision:
        return CheckResult(name, "warn", f"not checked: pass --target-revision ({TARGET_REVISION_HINT})")

    script = _script_directory()
    source_revisions = [row[0] for row in await session.exec(sa.text("SELECT version_num FROM alembic_version"))]
    try:
        target_ancestry = {revision.revision for revision in script.iterate_revisions(target_revision, "base")}
    except Exception:  # noqa: BLE001 - an unknown revision raises one of several alembic errors
        return CheckResult(
            name,
            "warn",
            f"target revision {target_revision} is not one this Langflow knows, so it may be newer; "
            "run the preflight with the target's Langflow version to be sure",
        )

    behind = [revision for revision in source_revisions if revision not in target_ancestry]
    if behind:
        return CheckResult(
            name,
            "fail",
            f"the target runs an older schema ({target_revision}) than the source ({', '.join(behind)}); "
            "attaching would need its migrations run backwards",
        )
    if set(source_revisions) == {target_revision}:
        return CheckResult(name, "ok", f"source and target are both at {target_revision}; attaching runs no migration")
    return CheckResult(
        name, "ok", f"the target ({target_revision}) is ahead of the source; attaching migrates the schema forward"
    )


async def check_default_superuser(session: AsyncSession) -> CheckResult:
    """Will the default superuser survive the target's first boot?

    With AUTO_LOGIN off, which IBM Langflow requires, Langflow deletes the default
    superuser when it has never signed in, and on Postgres the delete takes
    everything that user owns with it. The fix keeps the user; images that shipped
    before it do not, so this is checked against the source.
    """
    from lfx.services.settings.constants import DEFAULT_SUPERUSER

    from langflow.services.database.models.user.model import User

    name = "default superuser"
    user = (
        await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER, User.is_superuser == True))  # noqa: E712
    ).first()
    if user is None or user.last_login_at is not None:
        return CheckResult(name, "ok", f"no never-signed-in superuser named {DEFAULT_SUPERUSER!r}")

    owned = await _rows_owned_by(session, user.id)
    if not owned:
        return CheckResult(name, "ok", f"{DEFAULT_SUPERUSER!r} has never signed in but owns nothing")
    return CheckResult(
        name,
        "fail",
        f"{DEFAULT_SUPERUSER!r} has never signed in and owns rows; "
        "a target with AUTO_LOGIN off deletes it on first boot",
        [
            ", ".join(f"{table}: {count}" for table, count in sorted(owned.items())),
            f"before attaching, run against the target database: {_SUPERUSER_WORKAROUND}",
        ],
    )


async def check_target_key(session: AsyncSession, target_secret_key: str | None) -> CheckResult:
    """Will the key the target runs with open the source's credentials?

    A wrong key decrypts every credential to nothing and raises nothing, so the
    target boots cleanly and every flow fails at run time.
    """
    name = "target key"
    operator_note = (
        "On the IBM Langflow operator, create <instance>-langflow-secret-key holding the source key before applying "
        "the LangflowInstance; a key passed through envFrom is overridden by the one the operator generates"
    )
    if not target_secret_key:
        return CheckResult(name, "warn", f"not checked: pass --target-secret-key-file. {operator_note}")

    # A key file usually ends in a newline. Fernet ignores it, so every credential
    # opens, but a Secret made from the file with --from-file keeps it, and the SSO
    # client secret is keyed on the raw bytes. That breaks SSO sign-in and nothing else.
    key = target_secret_key.strip()
    padded = ""
    if key != target_secret_key:
        padded = (
            ". The key file has whitespace around the key, such as a trailing newline. A Secret created from it "
            "with --from-file keeps that whitespace: credentials still decrypt, but the SSO client secret does not. "
            "Create the Secret with --from-literal"
        )

    result = await check_credentials(session, _settings_with_key(key))
    if result.status == "ok":
        summary = result.summary.replace("the configured", "the target's") + padded
        return CheckResult(name, "warn" if padded else "ok", summary, result.problems)
    return CheckResult(
        name,
        "fail",
        f"{result.summary.replace('the configured', 'the target')}. {operator_note}{padded}",
        result.problems,
    )


async def check_embedding_models(session: AsyncSession) -> CheckResult:
    """Which knowledge bases can have their vectors copied?

    Vectors are only usable with the model that produced them, so a knowledge base
    that records its model can be copied. One that records none is not safe to
    assume anything about: embedding resolution silently falls back to a default
    model, which may never have produced these vectors.
    """
    from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
    from langflow.services.database.models.user.model import User

    rows = (
        await session.exec(
            select(KnowledgeBaseRecord.name, KnowledgeBaseRecord.model_selection, User.username).join(
                User, User.id == KnowledgeBaseRecord.user_id
            )
        )
    ).all()
    unknown = [f"{owner}/{kb}: no embedding model recorded" for kb, selection, owner in rows if not selection]
    copyable = len(rows) - len(unknown)
    plural = "" if copyable == 1 else "s"
    if not unknown:
        return CheckResult("embedding models", "ok", f"{copyable} knowledge base{plural} record their model")
    return CheckResult(
        "embedding models",
        "warn",
        f"{copyable} knowledge base{plural} record their model; {len(unknown)} record none and may need re-ingesting",
        unknown,
    )


async def check_role_assignments(session: AsyncSession) -> CheckResult:
    """Will the role grants that move with the database be enforced on the target?

    Grants live in authz_role_assignment and move with the database, but they are
    enforced from casbin_rule, which an authorization plugin compiles from them. Some
    IBM Langflow builds compile only when a role changes, so adopted grants do nothing
    until a superuser asks for a sync.
    """
    from langflow.services.database.models.auth.authz import AuthzRoleAssignment

    name = "role assignments"
    count = (await session.exec(select(func.count()).select_from(AuthzRoleAssignment))).one()
    if not count:
        return CheckResult(name, "ok", "no role assignments to carry over")
    plural = "" if count == 1 else "s"
    return CheckResult(
        name,
        "warn",
        f"{count} role assignment{plural} move with the database, but the target may not enforce them until its "
        "policy is compiled. After the first boot, sign in as a superuser, send POST /api/v1/authz/policy/sync, "
        "and check that casbin_rule has rows",
    )


async def _rows_owned_by(session: AsyncSession, user_id) -> dict[str, int]:
    """Rows in every table with a foreign key to user.id that point at this user."""
    from sqlmodel import SQLModel

    import langflow.services.database.models  # noqa: F401 - importing registers every table

    owned = {}
    for table in SQLModel.metadata.sorted_tables:
        for column in table.columns:
            if any(fk.column.table.name == "user" and fk.column.name == "id" for fk in column.foreign_keys):
                count = (await session.exec(select(func.count()).select_from(table).where(column == user_id))).one()
                if count:
                    owned[table.name] = owned.get(table.name, 0) + count
    return owned


def _settings_with_key(secret_key: str):
    from pydantic import SecretStr

    from langflow.services.deps import get_settings_service
    from langflow.services.settings.service import SettingsService

    current = get_settings_service()
    auth = current.auth_settings.model_copy(update={"SECRET_KEY": SecretStr(secret_key)})
    return SettingsService(current.settings, auth)


def _script_directory():
    import pathlib

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    import langflow

    config = Config()
    config.set_main_option("script_location", str(pathlib.Path(langflow.__file__).parent / "alembic"))
    return ScriptDirectory.from_config(config)
