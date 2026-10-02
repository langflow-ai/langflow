"""Tests for the instance integrity check.

Each test seeds one real disagreement between the database and something outside
it, against the real test database, local storage and local SQLite, and checks it
is reported. A clean instance has to pass, and a run has to leave the database as
it found it.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from typing import TYPE_CHECKING

import anyio
import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet
from langflow.cli.integrity import check_instance, open_instance
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
from lfx.base.knowledge_bases.backends.base import IngestedDocument
from lfx.base.knowledge_bases.backends.sqlite import SQLiteStorageContext
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


async def _seed_sqlite(kb_root: Path, user_id, name: str, vectors: int, *, recorded: int) -> KnowledgeBaseRecord:
    """A local SQLite knowledge base holding real vectors, and its row."""
    record = KnowledgeBaseRecord(name=name, user_id=user_id, backend_type="sqlite", chunks=recorded)
    context = SQLiteStorageContext(kb_root, user_id, record.id, record.storage_generation)
    backend = create_backend("sqlite", kb_name=name, storage_context=context, user_id=user_id, create=True)
    await backend.ensure_ready()
    if vectors:
        await backend.add_embedded_documents(
            [IngestedDocument(f"chunk {i}", {}, [float(i), 1.0, 0.0, 0.0], id=f"c{i}") for i in range(vectors)]
        )
    await backend.teardown()
    await _add(record)
    return record


def _contents(directory: Path) -> dict[str, str]:
    """Digest persisted data, excluding SQLite's shared-memory locks and empty WAL."""
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and not path.name.endswith("-shm") and (not path.name.endswith("-wal") or path.stat().st_size)
    }


class TestCleanInstance:
    async def test_every_check_passes(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        report = await check_instance()

        assert report.ok, [(c.name, c.problems) for c in report.checks if c.status == "fail"]
        assert [c.name for c in report.checks] == [
            "schema",
            "credentials",
            "files",
            "knowledge bases",
            "vector counts",
            "memory bases",
            "authorization",
        ]

    async def test_a_run_leaves_the_database_as_it_found_it(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _seed_sqlite(kb_root, active_user.id, "kb-fine", 3, recorded=3)
        await _add(File(user_id=active_user.id, name="gone", path=f"{active_user.id}/gone.txt", size=1))

        async def snapshot():
            async with session_scope() as session:
                conn = await session.connection()
                tables = await conn.run_sync(lambda c: sa.inspect(c).get_table_names())
                return {t: (await session.exec(sa.text(f'SELECT count(*) FROM "{t}"'))).one()[0] for t in tables}  # noqa: S608

        before = await snapshot()
        await check_instance()

        assert await snapshot() == before


class TestSchema:
    """A database that cannot be reached is not one on another schema."""

    async def test_a_database_that_cannot_be_reached_is_reported_as_unreachable(self, instance_on):
        # Nothing listens on port 1, so the connection is refused.
        instance_on("postgresql://user:not-to-be-shown@127.0.0.1:1/x")  # pragma: allowlist secret

        report = await check_instance()

        assert [(c.name, c.status) for c in report.checks] == [("schema", "fail")]
        summary = report.checks[0].summary
        assert "could not be reached" in summary
        assert "127.0.0.1" in summary
        assert "no recorded revision" not in summary
        assert "not-to-be-shown" not in summary
        assert "postgresql" not in summary

    async def test_a_database_with_no_alembic_version_table_has_no_recorded_revision(self, instance_on, tmp_path):
        instance_on(f"sqlite:///{tmp_path}/empty.db")

        report = await check_instance()

        assert [(c.name, c.status) for c in report.checks] == [("schema", "fail")]
        assert "no recorded revision" in report.checks[0].summary


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

    @pytest.mark.parametrize("empty_payload", [False, True], ids=["damaged-prefix", "empty"])
    async def test_a_malformed_connection_payload_is_counted(self, active_user, storage_dir, kb_root, empty_payload):  # noqa: ARG002
        # A connection's payload is always written encrypted, and its reader raises on one it cannot decode.
        from langflow.services.connection.service import (
            ConnectionSecretError,
            _decrypt_credential_payload,
            _encrypt_credential_payload,
        )
        from langflow.services.database.models.connection.model import Connection, ConnectionSecret

        connection = Connection(
            owner_id=active_user.id, provider_key="github", name="gh", display_name="GitHub", status="ready"
        )
        await _add(connection)
        payload = _encrypt_credential_payload(json.dumps({"version": 1, "access_token": "gho-token"}))
        await _add(ConnectionSecret(connection_id=connection.id, encrypted_payload=payload))
        assert _check(await check_instance(), "credentials").status == "ok"

        damaged = "" if empty_payload else "damaged" + payload.removeprefix("gAAAAA")
        async with session_scope() as session:
            (await session.get(ConnectionSecret, connection.id)).encrypted_payload = damaged
            await session.commit()

        check = _check(await check_instance(), "credentials")

        with pytest.raises(ConnectionSecretError):
            _decrypt_credential_payload(damaged)
        assert check.status == "fail"
        assert f"connection_secret.encrypted_payload row {connection.id}" in check.problems

    async def test_a_legacy_plaintext_api_key_is_not_counted(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        # Keys from 1.6.x are stored as issued, and the app still matches them as they are.
        before = _check(await check_instance(), "credentials")
        issued = "sk-issued-before-encryption"
        await _add(ApiKey(name="legacy", api_key=issued, user_id=active_user.id))

        check = _check(await check_instance(), "credentials")

        assert check.status == "ok"
        assert check.summary == before.summary

    async def test_a_trigger_signing_secret_under_another_key_is_counted(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        # Webhook ingress decrypts this with the instance key and rejects every delivery when it does not open.
        from langflow.services.database.models.flow.model import Flow
        from langflow.services.database.models.trigger.model import Trigger

        flow = Flow(name=f"webhook-{uuid.uuid4().hex[:6]}", user_id=active_user.id)
        await _add(flow)
        foreign = Fernet(Fernet.generate_key()).encrypt(b"whsec").decode()
        await _add(
            Trigger(
                flow_id=flow.id, user_id=active_user.id, name="hook", kind="webhook", signing_secret_encrypted=foreign
            )
        )

        check = _check(await check_instance(), "credentials")

        assert check.status == "fail"
        assert any(p.startswith("trigger.signing_secret_encrypted row ") for p in check.problems)

    async def test_rows_past_the_examples_are_counted_not_dropped(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        other = Fernet(Fernet.generate_key())
        await _add(
            *(
                Variable(
                    name=f"OTHER_{uuid.uuid4().hex[:6]}",
                    value=other.encrypt(b"sk").decode(),
                    type=CREDENTIAL_TYPE,
                    user_id=active_user.id,
                )
                for _ in range(6)
            )
        )

        check = _check(await check_instance(), "credentials")

        assert check.summary.startswith("6 of "), check.summary
        assert len(check.problems) == 6
        assert check.problems[-1] == "... and 1 more"


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
        await _seed_sqlite(kb_root, active_user.id, "kb-short", 3, recorded=5)

        report = await check_instance()

        assert _check(report, "knowledge bases").status == "ok"
        counts = _check(report, "vector counts")
        assert counts.status == "fail"
        assert "store holds 3, row records 5" in counts.problems[0]

    async def test_a_matching_store_passes(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _seed_sqlite(kb_root, active_user.id, "kb-fine", 3, recorded=3)

        assert _check(await check_instance(), "vector counts").status == "ok"

    async def test_a_store_never_written_to_is_not_created(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        record = KnowledgeBaseRecord(name="kb-empty", user_id=active_user.id, backend_type="sqlite", chunks=0)
        await _add(record)

        report = await check_instance()

        assert _check(report, "knowledge bases").status == "ok"
        assert _check(report, "vector counts").status == "ok"
        assert not SQLiteStorageContext(kb_root, active_user.id, record.id).database_path.parent.exists()


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
        await _seed_sqlite(kb_root, active_user.id, "kb-memory", 0, recorded=0)
        await self._memory_with_one_ingested_message(active_user, "kb-memory")

        check = _check(await check_instance(), "memory bases")

        assert check.status == "fail"
        assert "is empty" in check.problems[0]

    async def test_ingested_messages_with_vectors_pass(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _seed_sqlite(kb_root, active_user.id, "kb-memory", 2, recorded=2)
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


class TestReadOnly:
    """The check reads. Running it must not create storage or change the database."""

    async def test_an_existing_empty_store_directory_is_not_initialized(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        record = KnowledgeBaseRecord(name="kb-empty-dir", user_id=active_user.id, backend_type="sqlite", chunks=0)
        kb_path = SQLiteStorageContext(kb_root, active_user.id, record.id).database_path.parent
        kb_path.mkdir(parents=True)
        await _add(record)

        report = await check_instance()

        assert _check(report, "knowledge bases").status == "ok"
        assert list(kb_path.iterdir()) == []

    async def test_a_store_for_another_knowledge_base_is_not_used_or_created(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        await _seed_sqlite(kb_root, active_user.id, "something-else", 3, recorded=3)
        record = KnowledgeBaseRecord(name="kb-no-store", user_id=active_user.id, backend_type="sqlite", chunks=3)
        await _add(record)
        before = _contents(kb_root)

        report = await check_instance()

        assert not SQLiteStorageContext(kb_root, active_user.id, record.id).database_path.exists()
        assert _contents(kb_root) == before
        assert "store holds 0, row records 3" in " ".join(_check(report, "vector counts").problems)

    @pytest.mark.parametrize("older_schema", [True, False], ids=["older-schema", "current-schema"])
    async def test_an_existing_store_is_left_byte_for_byte_as_it_was(
        self,
        active_user,
        storage_dir,  # noqa: ARG002
        kb_root,
        older_schema,
    ):
        record = await _seed_sqlite(kb_root, active_user.id, "kb-kept", 3, recorded=3)
        context = SQLiteStorageContext(kb_root, active_user.id, record.id)
        kb_path = context.database_path.parent
        if older_schema:
            store = sqlite3.connect(context.database_path)
            store.execute("UPDATE store_header SET schema_version = schema_version - 1")
            store.commit()
            store.close()
        before = _contents(kb_path)

        report = await check_instance()

        assert _check(report, "knowledge bases").status == ("fail" if older_schema else "ok")
        if older_schema:
            assert "schema_version" in " ".join(_check(report, "knowledge bases").problems)
        else:
            assert _check(report, "vector counts").status == "ok"
        assert _contents(kb_path) == before

    async def test_retired_chroma_is_reported_without_opening_its_store(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        kb_path = kb_root / active_user.username / "kb-retired"
        kb_path.mkdir(parents=True)
        (kb_path / "chroma.sqlite3").write_bytes(b"original retired store")
        await _add(KnowledgeBaseRecord(name="kb-retired", user_id=active_user.id, backend_type="chroma", chunks=3))
        before = _contents(kb_path)

        report = await check_instance()

        assert _check(report, "knowledge bases").status == "fail"
        assert "requires migration" in " ".join(_check(report, "knowledge bases").problems)
        assert _contents(kb_path) == before

    async def test_a_store_that_cannot_be_read_is_reported_and_not_counted_as_empty(
        self,
        active_user,
        storage_dir,  # noqa: ARG002
        kb_root,
    ):
        record = await _seed_sqlite(kb_root, active_user.id, "kb-unreadable", 3, recorded=3)
        store = sqlite3.connect(SQLiteStorageContext(kb_root, active_user.id, record.id).database_path)
        store.executescript("DROP TABLE chunks")
        store.close()

        report = await check_instance()

        problems = " ".join(_check(report, "knowledge bases").problems)
        assert "kb-unreadable" in problems
        assert "no such table: chunks" in problems
        assert _check(report, "vector counts").status == "ok"

    async def test_a_database_on_another_schema_is_reported_and_not_read(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        async with session_scope() as session:
            revision = (await session.exec(sa.text("SELECT version_num FROM alembic_version"))).one()[0]
            await session.exec(sa.text("UPDATE alembic_version SET version_num = 'aaaaaaaaaaaa'"))
            await session.commit()
        try:
            report = await check_instance()
        finally:
            async with session_scope() as session:
                await session.exec(sa.text("UPDATE alembic_version SET version_num = :r").bindparams(r=revision))
                await session.commit()

        assert [(c.name, c.status) for c in report.checks] == [("schema", "fail")]
        assert "aaaaaaaaaaaa" in report.checks[0].summary

    async def test_the_cli_entry_point_leaves_the_database_as_it_found_it(self, active_user, storage_dir, kb_root):  # noqa: ARG002
        from datetime import datetime, timezone

        from langflow.__main__ import _check_integrity
        from langflow.services.database.models.auth.authz import AuthzAuditLog

        # Startup maintenance prunes audit rows older than the retention window.
        old = AuthzAuditLog(action="flow:read", result="allow", timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc))
        await _add(old)
        async with session_scope() as session:
            revision_before = (await session.exec(sa.text("SELECT version_num FROM alembic_version"))).all()

        await _check_integrity()

        async with session_scope() as session:
            assert await session.get(AuthzAuditLog, old.id) is not None
            assert (await session.exec(sa.text("SELECT version_num FROM alembic_version"))).all() == revision_before


class TestSecretKeyFile:
    """The check reads the instance's key file and never writes it: it may be the only copy of the key."""

    @pytest.fixture
    async def config_dir(self, active_user, tmp_path, monkeypatch):  # noqa: ARG002
        """Services built from nothing, as the command starts them, on a config dir of its own."""
        from lfx.services.manager import get_service_manager
        from lfx.services.schema import ServiceType

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(config_dir))
        manager = get_service_manager()
        monkeypatch.setattr(manager, "services", {})
        yield config_dir
        # Not a service teardown: the database's would tear down the superuser.
        if database := manager.services.get(ServiceType.DATABASE_SERVICE):
            await database.engine.dispose()

    async def test_a_different_key_in_the_environment_leaves_the_key_file_as_it_was(self, config_dir, monkeypatch):
        from langflow.__main__ import _check_integrity

        key_file = config_dir / "secret_key"
        key_file.write_bytes(b"the-only-copy-of-this-instance-key")
        monkeypatch.setenv("LANGFLOW_SECRET_KEY", Fernet.generate_key().decode())

        await _check_integrity()

        assert key_file.read_bytes() == b"the-only-copy-of-this-instance-key"

    async def test_no_key_anywhere_does_not_create_a_key_file(self, config_dir, monkeypatch):
        from langflow.__main__ import _check_integrity

        monkeypatch.delenv("LANGFLOW_SECRET_KEY", raising=False)

        await _check_integrity()

        assert not (config_dir / "secret_key").exists()
