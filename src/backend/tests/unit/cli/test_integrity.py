"""Tests for the instance integrity check.

Each test seeds one real disagreement between the database and something outside
it, against the real test database, local storage and local Chroma, and checks it
is reported. A clean instance has to pass, and a run has to leave the database as
it found it.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

import anyio
import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet
from langflow.cli.integrity import check_instance
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.auth.authz import AuthzRole, AuthzRoleAssignment, CasbinRule
from langflow.services.database.models.file.model import File
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import MemoryBase, MessageIngestionRecord
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_settings_service, get_storage_service, session_scope
from langflow.services.variable.constants import CREDENTIAL_TYPE
from lfx.base.knowledge_bases.backends import create_backend
from sqlmodel import select

if TYPE_CHECKING:
    from pathlib import Path


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


def _check(report, name):
    return next(check for check in report.checks if check.name == name)


async def _add(*rows) -> None:
    async with session_scope() as session:
        for row in rows:
            session.add(row)
        await session.commit()


async def _seed_chroma(kb_root: Path, username: str, user_id, name: str, vectors: int, *, recorded: int) -> None:
    """A local Chroma knowledge base holding real vectors, and its row."""
    kb_path = kb_root / username / name
    kb_path.mkdir(parents=True)
    backend = create_backend("chroma", kb_name=name, kb_path=kb_path, user_id=user_id)
    await backend.ensure_ready()
    if vectors:
        backend.vector_store._collection.upsert(
            ids=[f"c{i}" for i in range(vectors)],
            embeddings=[[float(i), 1.0, 0.0, 0.0] for i in range(vectors)],
            documents=[f"chunk {i}" for i in range(vectors)],
        )
    await backend.teardown()
    await _add(KnowledgeBaseRecord(name=name, user_id=user_id, backend_type="chroma", chunks=recorded))


class TestCleanInstance:
    async def test_every_check_passes(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        report = await check_instance()

        assert report.ok, [(c.name, c.problems) for c in report.checks if c.status == "fail"]
        assert [c.name for c in report.checks] == [
            "credentials",
            "files",
            "knowledge bases",
            "vector counts",
            "memory bases",
            "authorization",
        ]

    async def test_a_run_leaves_the_database_as_it_found_it(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _seed_chroma(kb_root, active_user.username, active_user.id, "kb-fine", 3, recorded=3)
        await _add(File(user_id=active_user.id, name="gone", path=f"{active_user.id}/gone.txt", size=1))

        async def snapshot():
            async with session_scope() as session:
                conn = await session.connection()
                tables = await conn.run_sync(lambda c: sa.inspect(c).get_table_names())
                return {t: (await session.exec(sa.text(f'SELECT count(*) FROM "{t}"'))).one()[0] for t in tables}  # noqa: S608

        before = await snapshot()
        await check_instance()

        assert await snapshot() == before


class TestCredentials:
    async def test_a_value_encrypted_under_another_key_is_counted(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        foreign = Fernet(Fernet.generate_key()).encrypt(b"sk-from-another-instance").decode()
        await _add(
            Variable(name=f"OTHER_{uuid.uuid4().hex[:6]}", value=foreign, type=CREDENTIAL_TYPE, user_id=active_user.id)
        )

        check = _check(await check_instance(), "credentials")

        assert check.status == "fail"
        assert any(p.startswith("variable.value row ") for p in check.problems)
        assert "do not open" in check.summary

    async def test_a_generic_variable_is_not_mistaken_for_a_credential(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        # Generic variables are stored as typed. One that happens to look like a token is still plaintext.
        await _add(
            Variable(
                name=f"GEN_{uuid.uuid4().hex[:6]}", value="gAAAAA-not-a-token", type="Generic", user_id=active_user.id
            )
        )

        assert _check(await check_instance(), "credentials").status == "ok"

    async def test_an_api_key_under_another_key_is_counted(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        foreign = Fernet(Fernet.generate_key()).encrypt(b"lf-key").decode()
        await _add(ApiKey(name="other", api_key=foreign, user_id=active_user.id))

        check = _check(await check_instance(), "credentials")

        assert check.status == "fail"
        assert any(p.startswith("apikey.api_key row ") for p in check.problems)


class TestFiles:
    async def test_a_row_without_bytes_is_reported(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _add(File(user_id=active_user.id, name="report", path=f"{active_user.id}/report.pdf", size=9))

        check = _check(await check_instance(), "files")

        assert check.status == "fail"
        assert "report.pdf" in check.problems[0]

    async def test_a_row_with_bytes_passes(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        (storage_dir / str(active_user.id)).mkdir()
        (storage_dir / str(active_user.id) / "report.pdf").write_bytes(b"pdf-bytes")
        await _add(File(user_id=active_user.id, name="report", path=f"{active_user.id}/report.pdf", size=9))

        assert _check(await check_instance(), "files").status == "ok"


class TestKnowledgeBases:
    async def test_a_backend_that_cannot_be_built_is_reported(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        # Astra still parses as a backend type and fails when a backend is built for it.
        await _add(KnowledgeBaseRecord(name="kb-astra", user_id=active_user.id, backend_type="astra", chunks=0))

        check = _check(await check_instance(), "knowledge bases")

        assert check.status == "fail"
        assert "kb-astra" in check.problems[0]

    async def test_a_backend_that_builds_but_cannot_be_reached_is_reported(
        self,
        active_user,
        storage_dir,  # noqa: ARG002
        kb_root,  # noqa: ARG002
        monkeypatch,
    ):
        # The backend builds, then fails its own connection test: the pgvector driver is
        # missing, or where it is installed, nothing listens on port 1.
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", "postgresql+psycopg://nobody@127.0.0.1:1/none")
        await _add(KnowledgeBaseRecord(name="kb-pg", user_id=active_user.id, backend_type="postgres", chunks=0))

        check = _check(await check_instance(), "knowledge bases")

        assert check.status == "fail"
        assert "kb-pg" in check.problems[0]
        # The backend's own message says what to fix. A bare exception name would mean the
        # connection test was skipped and something later fell over instead.
        assert not re.search(r"\): \w+(Error|Exception): ", check.problems[0]), check.problems[0]

    async def test_a_store_holding_fewer_vectors_than_its_row_is_reported(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _seed_chroma(kb_root, active_user.username, active_user.id, "kb-short", 3, recorded=5)

        report = await check_instance()

        assert _check(report, "knowledge bases").status == "ok"
        counts = _check(report, "vector counts")
        assert counts.status == "fail"
        assert "store holds 3, row records 5" in counts.problems[0]

    async def test_a_matching_store_passes(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _seed_chroma(kb_root, active_user.username, active_user.id, "kb-fine", 3, recorded=3)

        assert _check(await check_instance(), "vector counts").status == "ok"

    async def test_a_store_never_written_to_is_not_created(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _add(KnowledgeBaseRecord(name="kb-empty", user_id=active_user.id, backend_type="chroma", chunks=0))

        report = await check_instance()

        assert _check(report, "vector counts").status == "ok"
        assert not (kb_root / active_user.username / "kb-empty").exists()


class TestMemoryBases:
    async def _memory_with_one_ingested_message(self, user, kb_name: str) -> None:
        memory = MemoryBase(name="memory", flow_id=uuid.uuid4(), user_id=user.id, kb_name=kb_name)
        message = MessageTable(sender="User", sender_name="user", session_id="s1", text="hi", flow_id=memory.flow_id)
        await _add(memory, message)
        await _add(
            MessageIngestionRecord(
                message_id=message.id, memory_base_id=memory.id, session_id="s1", ingested_at=message.timestamp
            )
        )

    async def test_ingested_messages_with_no_knowledge_base_are_reported(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await self._memory_with_one_ingested_message(active_user, "kb-that-is-gone")

        check = _check(await check_instance(), "memory bases")

        assert check.status == "fail"
        assert "kb-that-is-gone" in check.problems[0]
        assert "missing" in check.problems[0]

    async def test_ingested_messages_with_an_empty_knowledge_base_are_reported(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _seed_chroma(kb_root, active_user.username, active_user.id, "kb-memory", 0, recorded=0)
        await self._memory_with_one_ingested_message(active_user, "kb-memory")

        check = _check(await check_instance(), "memory bases")

        assert check.status == "fail"
        assert "is empty" in check.problems[0]

    async def test_ingested_messages_with_vectors_pass(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _seed_chroma(kb_root, active_user.username, active_user.id, "kb-memory", 2, recorded=2)
        await self._memory_with_one_ingested_message(active_user, "kb-memory")

        assert _check(await check_instance(), "memory bases").status == "ok"


class TestAuthorization:
    async def test_an_assignment_to_a_missing_role_is_reported(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        missing_role = uuid.uuid4()
        async with session_scope() as session:
            # SQLite does not enforce the foreign key here, which is how such a row gets in.
            await session.exec(sa.text("PRAGMA foreign_keys=OFF"))
            session.add(AuthzRoleAssignment(user_id=active_user.id, role_id=missing_role, domain_type="global"))
            await session.commit()

        check = _check(await check_instance(), "authorization")

        assert check.status == "fail"
        assert str(missing_role) in check.problems[0]

    async def test_assignments_the_policy_sync_skipped_are_reported(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        async with session_scope() as session:
            admin = (await session.exec(select(AuthzRole).where(AuthzRole.name == "admin"))).one()
            admin_id = admin.id
        await _add(AuthzRoleAssignment(user_id=active_user.id, role_id=admin_id, domain_type="global"))
        # A compiled policy that has a rule of another kind but none for this assignment.
        await _add(CasbinRule(ptype="p", v0="role:admin", v1="*", v2="flow:*", v3="read"))

        check = _check(await check_instance(), "authorization")

        assert check.status == "fail"
        assert f"user:{active_user.id} has a role assignment but no compiled role rule" in check.problems[0]

    async def test_an_assignment_compiled_into_several_rules_passes(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        async with session_scope() as session:
            admin = (await session.exec(select(AuthzRole).where(AuthzRole.name == "admin"))).one()
            admin_id = admin.id
        await _add(AuthzRoleAssignment(user_id=active_user.id, role_id=admin_id, domain_type="global"))
        # A plugin may write one rule per domain, and team memberships are g rules too.
        await _add(CasbinRule(ptype="g", v0=f"user:{active_user.id}", v1="role:admin", v2="*"))
        await _add(CasbinRule(ptype="g", v0=f"user:{active_user.id}", v1="role:admin", v2="project:1"))
        await _add(CasbinRule(ptype="g", v0=f"user:{active_user.id}", v1=f"team:{uuid.uuid4()}"))

        check = _check(await check_instance(), "authorization")

        assert check.status == "ok", check.problems

    async def test_no_compiled_policy_is_not_a_failure(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        check = _check(await check_instance(), "authorization")

        assert check.status == "ok"
        assert "no compiled policy" in check.summary


class TestLivePgvector:
    """Against a real pgvector: a reachable store passes, and a short one is caught.

    Opt-in, like the other live pgvector tests: set
    ``LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1`` and ``PGVECTOR_CONNECTION_STRING``.
    """

    @pytest.fixture
    async def pg_kb(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        import os

        if os.getenv("LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS") != "1" or not os.getenv("PGVECTOR_CONNECTION_STRING"):
            pytest.skip("Set LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1 and PGVECTOR_CONNECTION_STRING")
        from langchain_core.documents import Document
        from langchain_core.embeddings import DeterministicFakeEmbedding

        name = f"kb-pg-{uuid.uuid4().hex[:6]}"
        # Same owner and name the check will use, so both address the same table.
        backend = create_backend(
            "postgres",
            kb_name=name,
            kb_path=kb_root,
            backend_config={},
            embedding_function=DeterministicFakeEmbedding(size=8),
            user_id=active_user.id,
        )
        await backend.ensure_ready()
        connection = await backend.test_connection()
        if not connection.ok:
            pytest.skip(f"pgvector not reachable: {connection.message}")
        await backend.add_documents([Document(page_content=f"chunk {i}") for i in range(4)])
        try:
            yield active_user, name
        finally:
            await backend.delete_collection()
            await backend.teardown()

    async def test_a_reachable_store_whose_count_matches_passes(self, pg_kb):
        user, name = pg_kb
        await _add(KnowledgeBaseRecord(name=name, user_id=user.id, backend_type="postgres", chunks=4))

        report = await check_instance()

        assert _check(report, "knowledge bases").status == "ok"
        assert _check(report, "vector counts").status == "ok"

    async def test_a_store_holding_fewer_vectors_than_its_row_is_reported(self, pg_kb):
        user, name = pg_kb
        await _add(KnowledgeBaseRecord(name=name, user_id=user.id, backend_type="postgres", chunks=6))

        counts = _check(await check_instance(), "vector counts")

        assert counts.status == "fail"
        assert "store holds 4, row records 6" in counts.problems[0]
