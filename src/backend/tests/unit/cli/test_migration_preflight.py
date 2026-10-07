"""Tests for the migration preflight.

Each test seeds one thing that would make a migration fail, against the real test
database, and checks the preflight refuses it before anything moves. A run has to
leave the database as it found it.
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

import anyio
import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet
from langflow.cli.integrity import open_instance, script_directory
from langflow.cli.migration_preflight import run_preflight
from langflow.services.auth.utils import encrypt_api_key, ensure_fernet_key
from langflow.services.database.models.auth.authz import AuthzRole, AuthzRoleAssignment
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_settings_service, get_storage_service, session_scope
from langflow.services.variable.constants import CREDENTIAL_TYPE
from lfx.services.settings.constants import DEFAULT_SUPERUSER
from sqlmodel import select

if TYPE_CHECKING:
    from pathlib import Path

# The test database is at this Langflow's head, which moves with every migration; PARENT is older than it.
HEAD = script_directory().get_current_head()
PARENT = "9d7e2a6c4b81"  # pragma: allowlist secret
# The alembic head of Langflow 1.12.0, which the IBM Langflow 1.12.0-dev image runs.
LANGFLOW_1_12_0 = "a3f8b1c9d7e2"  # pragma: allowlist secret
# The revision that c3e1d5a7f902, which adds user.retired_at, revises: the last one that deletes the default superuser.
BEFORE_RETIRED_AT = "f9d3b7a5c201"  # pragma: allowlist secret


@pytest.fixture
def storage_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "storage"
    root.mkdir()
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(root))
    get_storage_service().data_dir = anyio.Path(root)
    return root


@pytest.fixture
def kb_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "knowledge_bases"
    root.mkdir()
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(root))
    return root


@pytest.fixture
async def safe_superuser(active_user, storage_dir, kb_root):  # noqa: ARG001
    """The default superuser marked as signed in, so only the check under test can fail."""
    async with session_scope() as session:
        await session.exec(
            sa.text('UPDATE "user" SET last_login_at = CURRENT_TIMESTAMP WHERE username = :u').bindparams(
                u=DEFAULT_SUPERUSER
            )
        )
        await session.commit()
    return active_user


@pytest.fixture
async def instance_on(client, monkeypatch):  # noqa: ARG001
    """Start the services from nothing on a database the test names, as the command starts them."""
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    manager = get_service_manager()
    with monkeypatch.context() as patch:
        patch.setattr(manager, "services", {})

        def start(database_url: str) -> None:
            patch.setenv("LANGFLOW_DATABASE_URL", database_url)
            open_instance()

        yield start
        if database := manager.services.get(ServiceType.DATABASE_SERVICE):
            await database.engine.dispose()


def _check(report, name):
    return next(check for check in report.checks if check.name == name)


async def _add(*rows) -> None:
    async with session_scope() as session:
        for row in rows:
            session.add(row)
        await session.commit()


def _current_key() -> str:
    return get_settings_service().auth_settings.SECRET_KEY.get_secret_value()


def _current_key_as_fernet() -> str:
    """The configured key written as Fernet.generate_key() writes one: 44 characters, padded."""
    return ensure_fernet_key(_current_key()).decode()


def _current_key_as_token_urlsafe() -> str:
    """The configured key written as Langflow generates one, secrets.token_urlsafe(32): 43 characters."""
    return _current_key_as_fernet().rstrip("=")


class TestVersionDirection:
    async def test_a_target_on_the_same_revision_passes(self, safe_superuser):  # noqa: ARG002
        check = _check(await run_preflight(target_revision=HEAD), "version")

        assert check.status == "ok"

    async def test_a_target_older_than_the_source_is_refused(self, safe_superuser):  # noqa: ARG002
        # Attaching runs the target's migrations, which only move forward.
        check = _check(await run_preflight(target_revision=PARENT), "version")

        assert check.status == "fail"
        assert "older" in check.summary

    async def test_the_1_12_image_is_refused_for_a_newer_source(self, safe_superuser):  # noqa: ARG002
        check = _check(await run_preflight(target_revision=LANGFLOW_1_12_0), "version")

        assert check.status == "fail"

    async def test_a_revision_this_langflow_does_not_know_is_a_warning(self, safe_superuser):  # noqa: ARG002
        check = _check(await run_preflight(target_revision="0123456789ab"), "version")

        assert check.status == "warn"

    async def test_no_target_revision_is_a_warning(self, safe_superuser):  # noqa: ARG002
        assert _check(await run_preflight(), "version").status == "warn"

    def test_the_hint_prints_a_revision_that_can_be_passed_as_is(self):
        import subprocess
        import sys

        from langflow.cli.migration_preflight import TARGET_REVISION_HINT

        code = TARGET_REVISION_HINT.split('python -c "', 1)[1].removesuffix('"')
        printed = subprocess.run(  # noqa: S603 - the hint's own code, run as the operator would
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        ).stdout

        assert printed.strip() == HEAD

    async def test_a_pasted_revision_list_is_read_as_the_revision_it_names(self, safe_superuser):  # noqa: ARG002
        # get_heads() prints a list. Pasted as is, an older target must still be refused.
        check = _check(await run_preflight(target_revision=str([LANGFLOW_1_12_0])), "version")

        assert check.status == "fail"


class TestSourceThatCannotBeRead:
    """With a target revision the version check reads the source first, and leaves reporting it to the schema check."""

    async def test_a_malformed_revision_table_fails_the_schema_check(self, instance_on, tmp_path):
        database = tmp_path / "malformed.db"
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE alembic_version (unexpected_column TEXT)")
        instance_on(f"sqlite:///{database}")

        report = await run_preflight(target_revision=HEAD)

        assert [(c.name, c.status) for c in report.checks] == [("version", "warn"), ("source: schema", "fail")]
        assert "schema could not be read" in report.checks[0].summary
        assert "schema could not be read" in report.checks[1].summary

    async def test_revision_read_permissions_fail_the_schema_check(self, deny_revision_read):  # noqa: ARG002
        report = await run_preflight(target_revision=HEAD)

        assert [(c.name, c.status) for c in report.checks] == [("version", "warn"), ("source: schema", "fail")]
        assert "schema could not be read" in report.checks[0].summary
        assert "permission denied" in report.checks[1].summary

    async def test_a_source_with_no_alembic_version_table_fails_the_schema_check(self, instance_on, tmp_path):
        instance_on(f"sqlite:///{tmp_path}/empty.db")

        report = await run_preflight(target_revision=HEAD)

        assert [c.name for c in report.checks] == ["version", "source: schema"]
        assert report.checks[1].status == "fail"
        assert "no recorded revision" in report.checks[1].summary

    async def test_a_source_that_cannot_be_reached_fails_the_schema_check(self, instance_on, tmp_path):
        # A path under a regular file can be neither opened nor created, with any driver.
        (tmp_path / "not-a-directory").write_text("")
        instance_on(f"sqlite:///{tmp_path}/not-a-directory/langflow.db")

        report = await run_preflight(target_revision=HEAD)

        assert [(c.name, c.status) for c in report.checks] == [("version", "warn"), ("source: schema", "fail")]
        assert "could not be reached" in report.checks[0].summary
        assert "could not be reached" in report.checks[1].summary


class TestDefaultSuperuser:
    async def test_a_never_signed_in_default_superuser_that_owns_work_is_refused(
        self,
        active_user,  # noqa: ARG002
        storage_dir,  # noqa: ARG002
        kb_root,  # noqa: ARG002
    ):
        async with session_scope() as session:
            default = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).one()
            default.last_login_at = None
            session.add(default)
            session.add(Flow(name=f"owned-{uuid.uuid4().hex[:6]}", user_id=default.id, data={"nodes": []}))
            await session.commit()

        check = _check(await run_preflight(), "default superuser")

        assert check.status == "fail"
        # A target that keeps the account needs nothing, and setting last_login_at there would
        # stop it claiming or deactivating the account.
        kept, deleted = check.problems[-2:]
        assert "change nothing" in kept
        assert "last_login_at" in kept
        # On a target that deletes it, the workaround keeps it, and says what it leaves open.
        assert "last_login_at = now()" in deleted
        assert "API keys minted while AUTO_LOGIN was on keep working" in deleted

    @pytest.fixture
    async def owning_default_superuser(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        """The default superuser, never signed in and owning a flow."""
        async with session_scope() as session:
            default = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).one()
            default.last_login_at = None
            session.add(default)
            session.add(Flow(name=f"owned-{uuid.uuid4().hex[:6]}", user_id=default.id, data={"nodes": []}))
            await session.commit()

    async def test_a_target_that_keeps_the_account_passes_and_says_what_to_set(self, owning_default_superuser):  # noqa: ARG002
        # The head's migrations include the one that adds user.retired_at.
        check = _check(await run_preflight(target_revision=HEAD), "default superuser")

        assert check.status == "ok"
        assert "the target keeps the account" in check.summary
        assert f"LANGFLOW_SUPERUSER={DEFAULT_SUPERUSER}" in check.summary
        assert "any other name deactivates it and its API keys" in check.summary

    @pytest.mark.parametrize("target_revision", [BEFORE_RETIRED_AT, "0123456789ab"])
    async def test_a_target_not_known_to_keep_the_account_is_refused(self, owning_default_superuser, target_revision):  # noqa: ARG002
        # A schema from before user.retired_at, and a revision this Langflow does not know.
        check = _check(await run_preflight(target_revision=target_revision), "default superuser")

        assert check.status == "fail"
        assert "last_login_at = now()" in check.problems[-1]

    async def test_a_default_superuser_that_signed_in_passes(self, safe_superuser):  # noqa: ARG002
        assert _check(await run_preflight(), "default superuser").status == "ok"


class TestTargetKey:
    async def test_the_key_that_encrypted_the_data_passes(self, safe_superuser):
        await _add(
            Variable(
                name=f"KEY_{uuid.uuid4().hex[:6]}",
                value=encrypt_api_key("sk-real"),
                type=CREDENTIAL_TYPE,
                user_id=safe_superuser.id,
            )
        )

        check = _check(await run_preflight(target_secret_key=_current_key()), "target key")

        assert check.status == "ok"

    async def test_a_different_key_is_refused_with_the_operator_instruction(self, safe_superuser):
        await _add(
            Variable(
                name=f"KEY_{uuid.uuid4().hex[:6]}",
                value=encrypt_api_key("sk-real"),
                type=CREDENTIAL_TYPE,
                user_id=safe_superuser.id,
            )
        )

        check = _check(await run_preflight(target_secret_key=Fernet.generate_key().decode()), "target key")

        assert check.status == "fail"
        assert "-langflow-secret-key" in check.summary
        assert any(p.startswith("variable.value row ") for p in check.problems)

    async def test_no_target_key_is_a_warning(self, safe_superuser):  # noqa: ARG002
        assert _check(await run_preflight(), "target key").status == "warn"

    @pytest.mark.parametrize("malformed", ["x" * 40, "@" * 44])
    async def test_a_malformed_key_fails_cleanly_and_the_other_checks_still_run(
        self, safe_superuser, monkeypatch, malformed
    ):
        from pydantic import SecretStr

        await _add(
            Variable(
                name=f"KEY_{uuid.uuid4().hex[:6]}",
                value=encrypt_api_key("sk-real"),
                type=CREDENTIAL_TYPE,
                user_id=safe_superuser.id,
            )
        )
        monkeypatch.setattr(get_settings_service().auth_settings, "SECRET_KEY", SecretStr(malformed))

        report = await run_preflight(target_secret_key=malformed)

        for name in ("target key", "source: credentials"):
            check = _check(report, name)
            assert check.status == "fail"
            assert "not usable" in check.summary
        assert _check(report, "embedding models")

    async def test_a_default_key_file_ending_in_a_newline_is_refused(self, safe_superuser):
        # A Secret created from the file with --from-file carries the newline to the target. With
        # Langflow's default key shape, the key with it no longer makes a Fernet key at all.
        await _add(
            Variable(
                name=f"KEY_{uuid.uuid4().hex[:6]}",
                value=encrypt_api_key("sk-real"),
                type=CREDENTIAL_TYPE,
                user_id=safe_superuser.id,
            )
        )

        check = _check(await run_preflight(target_secret_key=_current_key_as_token_urlsafe() + "\n"), "target key")

        assert check.status == "fail"
        assert "trailing newline" in check.summary
        assert "--from-literal" in check.summary

    async def test_a_newline_that_the_key_still_opens_every_value_with_passes(self, safe_superuser):
        # A padded Fernet key decodes the same with the newline, so the target opens every value.
        await _add(
            Variable(
                name=f"KEY_{uuid.uuid4().hex[:6]}",
                value=encrypt_api_key("sk-real"),
                type=CREDENTIAL_TYPE,
                user_id=safe_superuser.id,
            )
        )

        check = _check(await run_preflight(target_secret_key=_current_key_as_fernet() + "\n"), "target key")

        assert check.status == "ok", check.summary


class TestRoleAssignments:
    async def test_role_grants_come_with_the_policy_sync_step(self, safe_superuser):
        async with session_scope() as session:
            admin_id = (await session.exec(select(AuthzRole).where(AuthzRole.name == "admin"))).one().id
        await _add(AuthzRoleAssignment(user_id=safe_superuser.id, role_id=admin_id, domain_type="global"))

        check = _check(await run_preflight(), "role assignments")

        assert check.status == "warn"
        assert "POST /api/v1/authz/policy/sync" in check.summary

    async def test_no_role_grants_pass(self, safe_superuser):  # noqa: ARG002
        assert _check(await run_preflight(), "role assignments").status == "ok"


class TestEmbeddingModels:
    async def test_a_knowledge_base_with_no_recorded_model_is_a_warning(self, safe_superuser):
        await _add(KnowledgeBaseRecord(name="kb-unknown", user_id=safe_superuser.id, chunks=0))

        check = _check(await run_preflight(), "embedding models")

        assert check.status == "warn"
        assert any("kb-unknown" in p for p in check.problems)

    @pytest.mark.parametrize("selection", [{"provider": "OpenAI"}, {"name": "", "provider": "OpenAI"}, [{}]])
    async def test_a_selection_that_names_no_model_is_a_warning(self, safe_superuser, selection):
        await _add(
            KnowledgeBaseRecord(
                name="kb-nameless",
                user_id=safe_superuser.id,
                chunks=0,
                model_selection=selection,
            )
        )

        check = _check(await run_preflight(), "embedding models")

        assert check.status == "warn"
        assert any("kb-nameless" in p for p in check.problems)

    async def test_knowledge_bases_past_the_examples_are_counted_not_listed(self, safe_superuser):
        await _add(*(KnowledgeBaseRecord(name=f"kb-{i}", user_id=safe_superuser.id, chunks=0) for i in range(7)))

        check = _check(await run_preflight(), "embedding models")

        assert check.status == "warn"
        assert "7 record none" in check.summary
        assert len(check.problems) == 6
        assert check.problems[-1] == "... and 2 more"

    async def test_knowledge_bases_with_recorded_models_pass(self, safe_superuser):
        await _add(
            KnowledgeBaseRecord(
                name="kb-known",
                user_id=safe_superuser.id,
                chunks=0,
                model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
            )
        )

        check = _check(await run_preflight(), "embedding models")

        assert check.status == "ok"
        assert "1 knowledge base" in check.summary


class TestComposition:
    async def test_the_source_integrity_checks_are_included(self, safe_superuser):
        await _add(
            Variable(
                name=f"OTHER_{uuid.uuid4().hex[:6]}",
                value=Fernet(Fernet.generate_key()).encrypt(b"x").decode(),
                type=CREDENTIAL_TYPE,
                user_id=safe_superuser.id,
            )
        )

        report = await run_preflight(target_revision=HEAD, target_secret_key=_current_key())

        assert _check(report, "source: credentials").status == "fail"
        assert not report.ok

    async def test_a_run_leaves_the_database_as_it_found_it(self, safe_superuser):  # noqa: ARG002
        async def snapshot():
            async with session_scope() as session:
                conn = await session.connection()
                tables = await conn.run_sync(lambda c: sa.inspect(c).get_table_names())
                return {t: (await session.exec(sa.text(f'SELECT count(*) FROM "{t}"'))).one()[0] for t in tables}  # noqa: S608

        before = await snapshot()
        await run_preflight(target_revision=HEAD, target_secret_key=_current_key())

        assert await snapshot() == before


class TestReadOnly:
    """The preflight reads the source. It must not migrate, repair or prune it first."""

    async def test_the_cli_entry_point_leaves_the_source_as_it_found_it(self, safe_superuser):  # noqa: ARG002
        from datetime import datetime, timezone

        from langflow.__main__ import _migration_preflight
        from langflow.services.database.models.auth.authz import AuthzAuditLog

        old = AuthzAuditLog(action="flow:read", result="allow", timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc))
        await _add(old)
        async with session_scope() as session:
            revision_before = (await session.exec(sa.text("SELECT version_num FROM alembic_version"))).all()

        await _migration_preflight(None, None)

        async with session_scope() as session:
            assert await session.get(AuthzAuditLog, old.id) is not None
            assert (await session.exec(sa.text("SELECT version_num FROM alembic_version"))).all() == revision_before

    async def test_a_source_on_an_older_schema_is_reported_without_being_migrated(self, safe_superuser):  # noqa: ARG002
        from langflow.cli.integrity import script_directory

        script = script_directory()
        head = script.get_current_head()
        parent = script.get_revision(head).down_revision
        parent = parent[0] if isinstance(parent, tuple) else parent
        async with session_scope() as session:
            await session.exec(sa.text("UPDATE alembic_version SET version_num = :r").bindparams(r=parent))
            await session.commit()
        try:
            report = await run_preflight(target_revision=head)
            async with session_scope() as session:
                after = (await session.exec(sa.text("SELECT version_num FROM alembic_version"))).one()[0]
        finally:
            async with session_scope() as session:
                await session.exec(sa.text("UPDATE alembic_version SET version_num = :r").bindparams(r=head))
                await session.commit()

        assert after == parent
        assert [(c.name, c.status) for c in report.checks] == [("version", "ok"), ("source: schema", "fail")]
        assert parent in report.checks[1].summary
