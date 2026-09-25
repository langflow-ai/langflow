"""Tests for the migration preflight.

Each test seeds one thing that would make a migration fail, against the real test
database, and checks the preflight refuses it before anything moves. A run has to
leave the database as it found it.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import anyio
import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet
from langflow.cli.migration_preflight import run_preflight
from langflow.services.auth.utils import encrypt_api_key
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

# The test database is at this Langflow's head; its parent is one revision older.
HEAD = "f2a7c9e4b681"  # pragma: allowlist secret
PARENT = "9d7e2a6c4b81"  # pragma: allowlist secret
# The alembic head of Langflow 1.12.0, which the IBM Langflow 1.12.0-dev image runs.
LANGFLOW_1_12_0 = "a3f8b1c9d7e2"  # pragma: allowlist secret


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


def _check(report, name):
    return next(check for check in report.checks if check.name == name)


async def _add(*rows) -> None:
    async with session_scope() as session:
        for row in rows:
            session.add(row)
        await session.commit()


def _current_key() -> str:
    return get_settings_service().auth_settings.SECRET_KEY.get_secret_value()


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

    async def test_a_key_file_ending_in_a_newline_is_a_warning(self, safe_superuser):
        # Fernet ignores the newline, so every credential still opens; a Secret made
        # from this file keeps it, and the SSO client secret, keyed on the raw bytes, does not.
        await _add(
            Variable(
                name=f"KEY_{uuid.uuid4().hex[:6]}",
                value=encrypt_api_key("sk-real"),
                type=CREDENTIAL_TYPE,
                user_id=safe_superuser.id,
            )
        )

        check = _check(await run_preflight(target_secret_key=_current_key() + "\n"), "target key")

        assert check.status == "warn"
        assert "--from-literal" in check.summary


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
        await _add(KnowledgeBaseRecord(name="kb-unknown", user_id=safe_superuser.id, backend_type="chroma", chunks=0))

        check = _check(await run_preflight(), "embedding models")

        assert check.status == "warn"
        assert any("kb-unknown" in p for p in check.problems)

    async def test_knowledge_bases_with_recorded_models_pass(self, safe_superuser):
        await _add(
            KnowledgeBaseRecord(
                name="kb-known",
                user_id=safe_superuser.id,
                backend_type="chroma",
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
