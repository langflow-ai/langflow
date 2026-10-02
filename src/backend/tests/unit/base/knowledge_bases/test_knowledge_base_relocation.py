"""Tests for relocating knowledge base vectors between backends.

Runs against the real test database and real local SQLite stores, created the
way the app creates them. The SQLite-to-Postgres move needs a pgvector database
and is opt-in via ``LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1`` and
``PGVECTOR_CONNECTION_STRING``.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
import typer
from langflow.__main__ import _relocate_kb
from langflow.api.utils import knowledge_base_service
from langflow.api.utils.knowledge_base_relocation import (
    KBRelocationResult,
    relocate_knowledge_bases,
    validate_relocation_target_config,
)
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.database.models.knowledge_base import KnowledgeBaseStatus
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.knowledge_base_storage.runtime import backend_for_record
from lfx.base.knowledge_bases.backends import IngestedDocument, SQLiteBackend, create_backend
from pydantic import SecretStr

if TYPE_CHECKING:
    from pathlib import Path

    from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord

DIM = 8
MODEL = {"name": "m", "provider": "p"}


@pytest.fixture
def kb_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "knowledge_bases"
    root.mkdir()
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(root))
    return root


@pytest.fixture
def during_copy(monkeypatch: pytest.MonkeyPatch):
    """Run ``action`` once, right after the relocation reads its first batch from SQLite.

    Wraps the real reader, so the copy itself is untouched; this only stands in
    for something else touching the knowledge base while it moves.
    """
    original = SQLiteBackend.iter_documents

    def install(action):
        async def iter_documents(self, **kwargs):
            first = True
            async for batch in original(self, **kwargs):
                yield batch
                if first:
                    first = False
                    await action()

        monkeypatch.setattr(SQLiteBackend, "iter_documents", iter_documents)

    return install


async def _seed_sqlite_kb(
    user_id, kb_name: str, n: int, *, chunks: int | None = None, model_selection: dict | None = MODEL
) -> tuple[KnowledgeBaseRecord, list[IngestedDocument]]:
    """Create a SQLite knowledge base the way the app does, then write ``n`` chunks to it.

    ``chunks`` is what the row records, ``n`` unless given.
    """
    docs = [
        IngestedDocument(id=f"chunk-{i}", content=f"doc {i}", metadata={"i": i}, embedding=[i / 100] * DIM)
        for i in range(n)
    ]
    record = await knowledge_base_service.create_record(
        user_id=user_id, name=kb_name, model_selection=model_selection, chunks=n if chunks is None else chunks
    )
    backend = await backend_for_record(record)
    try:
        await backend.add_embedded_documents(docs)
    finally:
        await backend.teardown()
    return record, docs


@pytest.mark.usefixtures("kb_root")
class TestRelocationWithoutATarget:
    async def test_stubbed_source_backend_is_reported_not_raised(self, active_user):
        record = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_on_astra", backend_type="astra", chunks=3
        )

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert "astra" in result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "astra"

    async def test_kb_already_on_the_target_is_skipped(self, active_user):
        record = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_on_pg", backend_type="postgres"
        )

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        assert next(r for r in results if r.kb_id == record.id).status == "skipped"

    async def test_dry_run_checks_the_target_is_reachable(self, active_user, monkeypatch):
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        record, _ = await _seed_sqlite_kb(active_user.id, "kb_dry_unreachable", 2)

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={}, dry_run=True)

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert "target" in result.reason

    async def test_kb_being_ingested_is_not_moved(self, active_user):
        # An ingestion still running would keep writing to the source after the copy.
        record, _ = await _seed_sqlite_kb(active_user.id, "kb_busy", 2)
        await knowledge_base_service.update_status(record.id, status=KnowledgeBaseStatus.INGESTING)

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert "ingesting" in result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "sqlite"

    async def test_empty_model_selection_is_warned_about(self, active_user):
        record, _ = await _seed_sqlite_kb(active_user.id, "kb_no_model", 2, model_selection=None)

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={}, dry_run=True)

        warnings = next(r for r in results if r.kb_id == record.id).warnings
        assert any("model_selection" in w for w in warnings)

    async def test_source_holding_fewer_chunks_than_recorded_is_not_repointed(self, active_user):
        # The row says 10, the store holds 4: that is what a truncated or
        # half-lost store looks like, so the relocation must refuse, not copy 4.
        record, _ = await _seed_sqlite_kb(active_user.id, "kb_short", 4, chunks=10)

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert "4 of 10" in result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "sqlite"


async def _database_state() -> tuple[str, list[uuid.UUID], uuid.UUID]:
    async with session_scope() as session:
        revision = (await session.exec(sa.text("SELECT version_num FROM alembic_version"))).one()[0]
        audit_rows = list((await session.exec(sa.select(AuthzAuditLog.id))).scalars())
        superuser = (await session.exec(sa.select(User.id).where(User.username == "langflow"))).one()[0]
    return revision, audit_rows, superuser


class TestRelocateKbCommand:
    """The command's own startup, the async helper ``langflow relocate-kb`` runs."""

    @pytest.fixture
    async def old_audit_row(self, client, monkeypatch):  # noqa: ARG002
        # Superuser credentials set, as an operator following the runbook has them.
        password = SecretStr("a-password")  # pragma: allowlist secret
        monkeypatch.setattr(get_settings_service().auth_settings, "SUPERUSER_PASSWORD", password)
        async with session_scope() as session:
            row = AuthzAuditLog(action="flow:read", result="allow", timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc))
            session.add(row)
        return row

    async def test_dry_run_writes_nothing_to_the_database(self, old_audit_row):
        # The server's startup migrates, sets up the superuser, reassigns orphaned
        # flows and prunes old history. None of that belongs in a dry run.
        before = await _database_state()

        await _relocate_kb(
            target_backend_type="postgres", target_backend_config={}, username=None, dry_run=True, batch_size=500
        )

        assert await _database_state() == before
        assert old_audit_row.id in before[1]

    async def test_database_behind_this_langflow_is_refused_not_migrated(self, old_audit_row, capsys):  # noqa: ARG002
        earlier = "9d7e2a6c4b81"  # an earlier revision of this Langflow's own  # pragma: allowlist secret
        async with session_scope() as session:
            await session.exec(sa.text("UPDATE alembic_version SET version_num = :v").bindparams(v=earlier))
        before = await _database_state()

        with pytest.raises(typer.Exit):
            await _relocate_kb(
                target_backend_type="postgres", target_backend_config={}, username=None, dry_run=True, batch_size=500
            )

        assert await _database_state() == before
        assert earlier in capsys.readouterr().err


@pytest.mark.parametrize(
    ("status", "copied", "expected"),
    [("relocated", 3, "chunks 3/3"), ("failed", 0, "chunks 0/3"), ("would_relocate", 0, "chunks 3")],
)
def test_relocation_line_shows_what_was_copied(status, copied, expected):
    from langflow.__main__ import relocation_line

    result = KBRelocationResult(
        kb_id=uuid.uuid4(),
        kb_name="kb",
        owner="alice",
        source_backend="sqlite",
        target_backend="postgres",
        status=status,
        source_count=3,
        copied=copied,
    )

    assert relocation_line(result).endswith(expected)


async def test_relocation_rejects_shared_target_collection():
    with pytest.raises(ValueError, match="index_name"):
        await relocate_knowledge_bases(target_backend_type="opensearch", target_backend_config={"index_name": "shared"})


def test_relocation_allows_empty_collection_override():
    validate_relocation_target_config("opensearch", {"index_name": ""})


@pytest.mark.parametrize("backend_type", ["sqlite", "chroma"])
async def test_relocation_refuses_a_local_target(backend_type):
    # SQLite is where knowledge bases already live, and Chroma is no longer a backend.
    with pytest.raises(ValueError, match=f"--to {backend_type}"):
        await relocate_knowledge_bases(target_backend_type=backend_type, target_backend_config={})


@pytest.mark.api_key_required
@pytest.mark.usefixtures("kb_root")
class TestRelocationToPostgresLive:
    @pytest.fixture(autouse=True)
    def _require_pgvector(self):
        if os.getenv("LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS") != "1" or not os.getenv("PGVECTOR_CONNECTION_STRING"):
            pytest.skip("Set LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1 and PGVECTOR_CONNECTION_STRING")
        pytest.importorskip("pgvector")

    async def test_moves_vectors_and_repoints_the_row(self, active_user, tmp_path: Path):
        kb_name = f"kb_move_{uuid.uuid4().hex[:6]}"
        record, seeded = await _seed_sqlite_kb(active_user.id, kb_name, 12)
        target = create_backend(
            "postgres", kb_name=kb_name, kb_path=tmp_path, backend_config={}, user_id=active_user.id
        )
        try:
            results = await relocate_knowledge_bases(
                target_backend_type="postgres", target_backend_config={}, batch_size=5
            )
            result = next(r for r in results if r.kb_id == record.id)
            assert result.status == "relocated", result.reason
            assert (result.source_count, result.copied, result.target_count) == (12, 12, 12)

            row = await knowledge_base_service.get_by_id(record.id)
            assert row.backend_type == "postgres"

            moved = {}
            async for batch in target.iter_documents(include_embeddings=True):
                moved.update({d.id: d for d in batch})
            for doc in seeded:
                assert moved[doc.id].content == doc.content
                assert moved[doc.id].embedding == pytest.approx(doc.embedding)

            # The row now names the target, so a second run leaves it alone.
            rerun = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})
            assert next(r for r in rerun if r.kb_id == record.id).status == "skipped"
        finally:
            with contextlib.suppress(Exception):
                await target.delete_collection()
            await target.teardown()

    async def test_dry_run_counts_without_writing(self, active_user):
        kb_name = f"kb_dry_{uuid.uuid4().hex[:6]}"
        record, _ = await _seed_sqlite_kb(active_user.id, kb_name, 7)

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={}, dry_run=True)

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "would_relocate", result.reason
        assert result.source_count == 7
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "sqlite"

    async def _move(self, active_user, tmp_path, kb_name, *, target_setup=None, on_record=None, batch_size=4):
        record, _ = await _seed_sqlite_kb(active_user.id, kb_name, 12)
        if on_record:
            on_record(record)
        target = create_backend(
            "postgres", kb_name=kb_name, kb_path=tmp_path, backend_config={}, user_id=active_user.id
        )
        try:
            if target_setup:
                await target_setup(target)
            results = await relocate_knowledge_bases(
                target_backend_type="postgres", target_backend_config={}, batch_size=batch_size
            )
            return record, next(r for r in results if r.kb_id == record.id)
        finally:
            with contextlib.suppress(Exception):
                await target.delete_collection()
            await target.teardown()

    async def test_chunk_written_to_the_source_mid_copy_stops_the_repoint(self, active_user, tmp_path, during_copy):
        kb_name = f"kb_late_{uuid.uuid4().hex[:6]}"

        async def write_late_chunk():
            record = await knowledge_base_service.get_by_user_and_name(active_user.id, kb_name)
            source = await backend_for_record(record)
            try:
                # SQLite reads in id order, so an id before "chunk-" is one the read has
                # already paged past, and only the source's own count shows it.
                await source.add_embedded_documents(
                    [IngestedDocument(id="a-late", content="late", metadata={}, embedding=[0.5] * DIM)]
                )
            finally:
                await source.teardown()

        during_copy(write_late_chunk)
        record, result = await self._move(active_user, tmp_path, kb_name)

        assert result.status == "failed", (result.source_count, result.copied, result.target_count)
        assert "changed" in result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "sqlite"

    async def test_target_that_already_holds_other_chunks_is_not_repointed(self, active_user, tmp_path):
        async def add_stale_rows(target):
            await target.ensure_ready()
            await target.add_embedded_documents(
                [
                    IngestedDocument(id=f"stale-{i}", content="stale", metadata={}, embedding=[0.9] * DIM)
                    for i in range(3)
                ]
            )

        kb_name = f"kb_stale_{uuid.uuid4().hex[:6]}"
        record, result = await self._move(active_user, tmp_path, kb_name, target_setup=add_stale_rows)

        assert result.status == "failed", (result.source_count, result.copied, result.target_count)
        assert "15" in result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "sqlite"

    async def test_kb_deleted_mid_copy_is_not_reported_as_relocated(self, active_user, tmp_path, during_copy):
        kb_name = f"kb_gone_{uuid.uuid4().hex[:6]}"
        records = []

        async def delete_row():
            await knowledge_base_service.delete_record(records[0].id)

        during_copy(delete_row)
        _, result = await self._move(active_user, tmp_path, kb_name, on_record=records.append)

        assert result.status == "failed"
        assert "deleted" in result.reason


@pytest.mark.api_key_required
async def test_opensearch_kb_is_not_relocated_onto_its_own_index(active_user, kb_root, tmp_path: Path):  # noqa: ARG001
    if os.getenv("LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS") != "1" or not os.getenv("OPENSEARCH_URL"):
        pytest.skip("Set LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1 and OPENSEARCH_URL")
    pytest.importorskip("opensearchpy")
    kb_name = f"kb_os_{uuid.uuid4().hex[:6]}"
    # What the DB Providers UI stores, against a target config that names only the URL.
    source_config = {"url_variable": "OPENSEARCH_URL", "vector_field": "chunk_embedding", "use_ssl": False}
    source = create_backend(
        "opensearch", kb_name=kb_name, kb_path=tmp_path, backend_config=source_config, user_id=active_user.id
    )
    try:
        await source.ensure_ready()
        await source.add_embedded_documents([IngestedDocument(id="c0", content="doc", embedding=[0.5] * DIM)])
        source._os_client.indices.refresh(index=source._os_index)
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name=kb_name,
            backend_type="opensearch",
            backend_config=source_config,
            model_selection={"name": "m", "provider": "p"},
            chunks=1,
        )

        results = await relocate_knowledge_bases(
            target_backend_type="opensearch", target_backend_config={"url_variable": "OPENSEARCH_URL"}
        )

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "skipped", result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_config == source_config
    finally:
        await source.delete_collection()
        await source.teardown()
