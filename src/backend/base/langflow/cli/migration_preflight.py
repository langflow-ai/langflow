"""Refuse a migration that cannot succeed, before anything moves.

The integrity check answers questions about one instance. A migration adds the
questions that need a source and a target together: will the target's migrations
run forward from the source's schema, will the target's key open the source's
credentials, will the default superuser survive the target's first boot, and will
the role grants be enforced once it has.
Several of these failed silently in a rehearsal, so each is checked here instead.

Read-only, like the integrity check it runs against the source.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlmodel import func, select

from langflow.cli.integrity import (
    CheckResult,
    IntegrityReport,
    _result,
    check_credentials,
    check_instance,
    check_schema,
    recorded_revisions,
    script_directory,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

# How to read the revision a target image runs, for --target-revision.
TARGET_REVISION_HINT = (
    'read it from the target image: python -c "import langflow, pathlib; from alembic.config import Config; '
    "from alembic.script import ScriptDirectory; c = Config(); c.set_main_option('script_location', "
    "str(pathlib.Path(langflow.__file__).parent / 'alembic')); "
    'print(ScriptDirectory.from_config(c).get_current_head())"'
)

# The migration c3e1d5a7f902_add_user_retired_at, in langflow/alembic/versions. A Langflow that has it keeps a
# never-signed-in default superuser that owns rows, where an older one deletes it.
_KEEPS_DEFAULT_SUPERUSER = "c3e1d5a7f902"  # pragma: allowlist secret

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
        checks = [await check_version_direction(session, target_revision)]
        schema = await check_schema(session)
        if schema.status != "ok":
            # The remaining checks read through this Langflow's models, which on another
            # schema would misread rows. Nothing migrates the source to make them fit.
            await session.rollback()
            return IntegrityReport([*checks, replace(schema, name="source: schema")])
        checks += [
            await check_default_superuser(session, target_revision),
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

    # get_heads() prints a list, such as ['<revision>']; pasted as is, it names that revision.
    target_revision = target_revision.strip("[]'\" ")
    script = script_directory()
    try:
        await session.connection()
    except sa.exc.SQLAlchemyError:
        await session.rollback()
        return CheckResult(name, "warn", "not checked: the database could not be reached")
    try:
        # A source with no alembic_version table records no revision, which the schema check reports.
        source_revisions = sorted(await recorded_revisions(session))
    except sa.exc.SQLAlchemyError:
        await session.rollback()
        return CheckResult(name, "warn", "not checked: the database schema could not be read")
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


async def check_default_superuser(session: AsyncSession, target_revision: str | None = None) -> CheckResult:
    """Will the default superuser survive the target's first boot?

    With AUTO_LOGIN off, Langflow deletes the default superuser when it has never
    signed in, and on Postgres the delete takes
    everything that user owns with it. The fix keeps the user: it claims the account
    for LANGFLOW_SUPERUSER or deactivates it, and setting last_login_at skips both.
    A target revision that includes the fix's migration passes. Without one, nothing
    here tells which kind of target this is, so the advice covers both.
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
    if _keeps_default_superuser(target_revision):
        return CheckResult(
            name,
            "ok",
            f"{DEFAULT_SUPERUSER!r} has never signed in and owns rows, and the target keeps the account: "
            f"LANGFLOW_SUPERUSER={DEFAULT_SUPERUSER} with a password claims it; "
            "any other name deactivates it and its API keys",
        )
    return CheckResult(
        name,
        "fail",
        f"{DEFAULT_SUPERUSER!r} has never signed in and owns rows; "
        "a target with AUTO_LOGIN off deletes it on first boot unless its Langflow keeps such an account",
        [
            ", ".join(f"{table}: {count}" for table, count in sorted(owned.items())),
            "if the target's Langflow keeps it (its migrations add user.retired_at), change nothing: "
            f"LANGFLOW_SUPERUSER={DEFAULT_SUPERUSER} claims the account with the configured password, and its API "
            "keys, including any minted while AUTO_LOGIN was on, keep working; any other name deactivates it, which "
            "stops them. Setting last_login_at on such a target skips both",
            f"otherwise, before attaching, run against the target database: {_SUPERUSER_WORKAROUND} The account "
            "stays active with its current password, so API keys minted while AUTO_LOGIN was on keep working. Set "
            f"LANGFLOW_SUPERUSER to another name and, after the first boot, deactivate {DEFAULT_SUPERUSER!r} from "
            "the Admin page",
        ],
    )


async def check_target_key(session: AsyncSession, target_secret_key: str | None) -> CheckResult:
    """Will the key the target runs with open the source's credentials?

    A wrong key decrypts every credential to nothing and raises nothing, so the
    target boots cleanly and every flow fails at run time.
    """
    name = "target key"
    key_note = (
        "Give the new instance this instance's secret key before its first start; an instance that starts "
        "without one makes its own, which cannot open these values"
    )
    if not target_secret_key:
        return CheckResult(name, "warn", f"not checked: pass --target-secret-key-file. {key_note}")

    # Tested as the file holds it, trailing newline and all: a Secret created from the
    # file with --from-file carries it to the target, which reads the key as it is.
    result = await check_credentials(session, _settings_with_key(target_secret_key))
    summary = result.summary.replace("the configured", "the target's")
    if result.status == "ok":
        return CheckResult(name, "ok", summary, result.problems)
    key = target_secret_key.strip()
    if key != target_secret_key and (await check_credentials(session, _settings_with_key(key))).status == "ok":
        return CheckResult(
            name,
            "fail",
            "the key file has whitespace around the key, such as a trailing newline, and a Secret created from it "
            f"with --from-file carries that to the target. With it, {summary}; without it, every value opens. "
            "Remove it from the file, or create the Secret with --from-literal",
            result.problems,
        )
    return CheckResult(name, "fail", f"{summary}. {key_note}", result.problems)


async def check_embedding_models(session: AsyncSession) -> CheckResult:
    """Which knowledge bases can have their vectors copied?

    Vectors are only usable with the model that produced them, so a knowledge base
    that records its model can be copied. One that records none is not safe to
    assume anything about: embedding resolution silently falls back to a default
    model, which may never have produced these vectors.
    """
    from langflow.api.utils.knowledge_base_service import get_embedding_model
    from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
    from langflow.services.database.models.user.model import User

    rows = (
        await session.exec(
            select(KnowledgeBaseRecord.name, KnowledgeBaseRecord.model_selection, User.username).join(
                User, User.id == KnowledgeBaseRecord.user_id
            )
        )
    ).all()
    # A selection can name a provider and no model, which resolves to the same default.
    unknown = [
        f"{owner}/{kb}: no embedding model recorded"
        for kb, selection, owner in rows
        if not get_embedding_model(selection)
    ]
    copyable = len(rows) - len(unknown)
    plural = "" if copyable == 1 else "s"
    recorded = f"{copyable} knowledge base{plural} record their model"
    # Listed as the integrity checks list theirs, the first few and a count of the rest.
    result = _result(
        "embedding models", unknown, recorded, f"{recorded}; {len(unknown)} record none and may need re-ingesting"
    )
    # A knowledge base that may need re-ingesting does not stop the migration.
    return replace(result, status="warn") if unknown else result


async def check_role_assignments(session: AsyncSession) -> CheckResult:
    """Will the role grants that move with the database be enforced on the target?

    Grants live in authz_role_assignment and move with the database, but they are
    enforced from casbin_rule, which an authorization plugin compiles from them. Some
    plugins compile only when a role changes, so adopted grants do nothing until a
    superuser asks for a sync.
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


def _keeps_default_superuser(target_revision: str | None) -> bool:
    """Do the target's migrations include the one that keeps the default superuser?"""
    if not target_revision:
        return False
    try:
        ancestry = script_directory().iterate_revisions(target_revision.strip("[]'\" "), "base")
        return any(revision.revision == _KEEPS_DEFAULT_SUPERUSER for revision in ancestry)
    except Exception:  # noqa: BLE001 - an unknown revision raises one of several alembic errors
        return False


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
