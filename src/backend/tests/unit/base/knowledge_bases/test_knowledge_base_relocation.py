"""Tests for relocating knowledge base vectors between backends.

Runs against the real test database and real local SQLite stores, created the
way the app creates them. The SQLite-to-Postgres move needs a pgvector database
and is opt-in via ``LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1`` and
``PGVECTOR_CONNECTION_STRING``.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
import typer
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langflow.__main__ import _relocate_kb
from langflow.api.utils import knowledge_base_service
from langflow.api.utils.knowledge_base_relocation import (
    KBRelocationResult,
    _metric_change,
    _repoint,
    relocate_knowledge_bases,
    validate_relocation_target_config,
)
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord, KnowledgeBaseStatus
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.knowledge_base_storage.runtime import backend_for_record, operation, unfenced_backend
from lfx.base.knowledge_bases.backends import BackendType, IngestedDocument, PostgresBackend, create_backend
from pydantic import SecretStr

if TYPE_CHECKING:
    from pathlib import Path

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
    """Run ``action`` once, right after relocation writes its first batch to Postgres.

    Leave the metric preflight scan untouched so each action still runs while
    chunks are being copied, after that read-only validation has finished.
    """
    original = PostgresBackend.add_embedded_documents

    def install(action):
        first = True

        async def add_embedded_documents(self, docs):
            nonlocal first
            result = await original(self, docs)
            if first:
                first = False
                await action()
            return result

        monkeypatch.setattr(PostgresBackend, "add_embedded_documents", add_embedded_documents)

    return install


def _vector(i: int, *, unit: bool) -> list[float]:
    raw = [1.0] + [i / 100] * (DIM - 1)
    if not unit:
        return raw
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


async def _seed_sqlite_kb(
    user_id,
    kb_name: str,
    n: int,
    *,
    chunks: int | None = None,
    model_selection: dict | None = MODEL,
    unit: bool = True,
) -> tuple[KnowledgeBaseRecord, list[IngestedDocument]]:
    """Create a SQLite knowledge base the way the app does, then write ``n`` chunks to it.

    ``chunks`` is what the row records, ``n`` unless given. Unit-length vectors by
    default, like most hosted embedding models.
    """
    docs = [
        IngestedDocument(id=f"chunk-{i}", content=f"doc {i}", metadata={"i": i}, embedding=_vector(i, unit=unit))
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


async def _set_row(record_id: uuid.UUID, **fields) -> None:
    """Change a knowledge base's row, as a storage operation elsewhere in Langflow would."""
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record_id)
        for name, value in fields.items():
            setattr(row, name, value)
        session.add(row)
        await session.commit()


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

    @pytest.mark.parametrize(
        ("backend_type", "backend_config", "storage_state", "expected"),
        [
            # Local Chroma the startup upgrade has not reached yet, or could not finish.
            ("chroma", {"mode": "local"}, "ready", "storage upgrade to SQLite has not finished"),
            ("chroma", {"mode": "local"}, "needs_attention", "storage upgrade to SQLite has not finished"),
            ("sqlite", {}, "migrating", "storage upgrade to SQLite has not finished"),
            ("chroma", {"mode": "cloud"}, "needs_attention", "Chroma Cloud"),
            ("sqlite", {}, "deleting", "storage_state deleting"),
        ],
    )
    async def test_kb_whose_storage_is_not_ready_is_refused_unread(
        self, active_user, backend_type, backend_config, storage_state, expected
    ):
        # Reading any of these would fail some other way: nothing reads Chroma, and
        # the SQLite store is empty while its row records 3 chunks.
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name=f"kb_{backend_type}_{storage_state}",
            backend_type=backend_type,
            backend_config=backend_config,
            model_selection=MODEL,
            chunks=3,
        )
        await _set_row(record.id, storage_state=storage_state)

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert expected in result.reason
        assert (result.copied, result.target_count) == (0, 0)
        row = await knowledge_base_service.get_by_id(record.id)
        assert (row.backend_type, row.storage_state) == (backend_type, storage_state)

    async def test_repoint_moves_a_row_still_routed_as_it_was_read(self, active_user):
        record, _ = await _seed_sqlite_kb(active_user.id, "kb_unchanged", 2)

        assert await _repoint(record, "postgres", {}, 2) == "repointed"

        row = await knowledge_base_service.get_by_id(record.id)
        assert (row.backend_type, row.chunks) == ("postgres", 2)
        assert row.storage_generation == record.storage_generation + 1

    @pytest.mark.parametrize(
        "change",
        [
            {"storage_generation": 2},
            {"storage_state": "deleting"},
            {"backend_type": "opensearch"},
            {"backend_config": {"url_variable": "NEW_CLUSTER"}},
        ],
    )
    async def test_repoint_leaves_a_row_that_changed_after_it_was_read(self, active_user, change):
        # ``record`` is the row as relocate-kb read it; the change is what a storage
        # operation elsewhere in Langflow, or another run, does to it before the repoint.
        record, _ = await _seed_sqlite_kb(active_user.id, "kb_moved_on", 2)
        await _set_row(record.id, **change)

        assert await _repoint(record, "postgres", {}, 2) == "changed"

        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == change.get("backend_type", "sqlite")
        assert row.backend_config == change.get("backend_config", {})

    async def test_same_backend_relocation_invalidates_the_previous_routing(self, active_user):
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="kb_remote_routing",
            backend_type="opensearch",
            backend_config={"url_variable": "OLD_CLUSTER"},
        )

        assert await _repoint(record, "opensearch", {"url_variable": "FIRST_CLUSTER"}, 0) == "repointed"
        assert await _repoint(record, "opensearch", {"url_variable": "SECOND_CLUSTER"}, 0) == "changed"

        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_config == {"url_variable": "FIRST_CLUSTER"}
        assert row.storage_generation == record.storage_generation + 1

    async def test_repoint_tells_a_deleted_row_from_a_changed_one(self, active_user):
        record, _ = await _seed_sqlite_kb(active_user.id, "kb_deleted_first", 2)
        await knowledge_base_service.delete_record(record.id)

        assert await _repoint(record, "postgres", {}, 2) == "deleted"

    @pytest.mark.parametrize(
        ("target", "config", "how"),
        [
            ("postgres", {}, "--allow-metric-change"),
            ("opensearch", {"url_variable": "OPENSEARCH_URL", "space_type": "cosinesimil"}, '{"space_type": "l2"}'),
        ],
    )
    async def test_metric_refusal_says_how_to_proceed(self, active_user, monkeypatch, request, target, config, how):
        # pgvector's metric is fixed, so the only way through is to accept the change.
        if target == "opensearch":
            # Exercise the base installation without the optional SDK even when
            # it happens to be installed in the local test environment.
            monkeypatch.setitem(sys.modules, "opensearchpy", None)
            request.getfixturevalue("fake_opensearchpy")
            import langchain_community.vectorstores
            import opensearchpy
            from opensearchpy.exceptions import NotFoundError

            client = MagicMock()
            client.indices.get_mapping.side_effect = NotFoundError(404, "index_not_found_exception", {})
            monkeypatch.setenv("OPENSEARCH_URL", "http://localhost:9200")
            monkeypatch.setattr(opensearchpy, "OpenSearch", MagicMock(return_value=client))
            monkeypatch.setattr(langchain_community.vectorstores, "OpenSearchVectorSearch", MagicMock())
        kb_name = f"kb_metric_{target}"
        record, _ = await _seed_sqlite_kb(active_user.id, kb_name, 6, unit=False)

        results = await relocate_knowledge_bases(target_backend_type=target, target_backend_config=config, dry_run=True)

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert how in result.reason


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


class _MetricBackend:
    """A bounded document stream for exercising the backend-independent metric guard."""

    backend_type = BackendType.POSTGRES

    def __init__(self, metric: str, vectors: list[list[float] | None] | None = None):
        self.metric = metric
        self.vectors = vectors or []
        self.closed = False

    async def get_distance_metric(self) -> str:
        return self.metric

    async def iter_documents(self, *, batch_size: int, include_embeddings: bool):
        assert include_embeddings
        try:
            for start in range(0, len(self.vectors), batch_size):
                yield [
                    IngestedDocument(content="chunk", embedding=vector)
                    for vector in self.vectors[start : start + batch_size]
                ]
        finally:
            self.closed = True


@pytest.fixture
def metric_result() -> KBRelocationResult:
    return KBRelocationResult(
        kb_id=uuid.uuid4(),
        kb_name="metric_guard",
        owner="owner",
        source_backend="sqlite",
        target_backend="postgres",
        status="failed",
        source_count=101,
    )


async def test_metric_guard_checks_vectors_after_the_first_batch(metric_result):
    source = _MetricBackend("l2", [[1.0, 0.0]] * 100 + [[2.0, 0.0]])
    target = _MetricBackend("cosine")

    reason = await _metric_change(source, target, metric_result, allow=False)

    assert "not unit length" in reason
    assert "--allow-metric-change" in reason
    assert metric_result.warnings == []
    assert source.closed


@pytest.mark.parametrize("allow", [False, True])
@pytest.mark.parametrize("last_vector", [None, "truncated"])
async def test_metric_guard_refuses_incomplete_vectors_even_when_change_is_allowed(metric_result, allow, last_vector):
    vectors = [[1.0, 0.0]] * 100 + ([None] if last_vector is None else [])
    source = _MetricBackend("l2", vectors)
    target = _MetricBackend("cosine")

    reason = await _metric_change(source, target, metric_result, allow=allow)

    expected = "without vectors" if last_vector is None else "read 100 of 101 chunks"
    assert expected in reason
    assert metric_result.warnings == []
    assert source.closed


@pytest.mark.parametrize(("before", "after"), [("l2", "l1"), ("linf", "cosine"), ("l1", "linf")])
@pytest.mark.parametrize("allow", [False, True])
async def test_unit_vectors_do_not_make_other_metrics_equivalent(metric_result, before, after, allow):
    source = _MetricBackend(before, [[1.0, 0.0]] * metric_result.source_count)
    target = _MetricBackend(after)

    reason = await _metric_change(source, target, metric_result, allow=allow)

    if allow:
        assert reason is None
        assert any("may rank unit vectors differently" in warning for warning in metric_result.warnings)
    else:
        assert "may rank unit vectors differently" in reason
        assert "--allow-metric-change" in reason
        assert metric_result.warnings == []


@pytest.mark.parametrize(("before", "after"), [("l2", "cosine"), ("cosine", "inner_product"), ("inner_product", "l2")])
async def test_unit_vectors_remain_equivalent_across_supported_metrics(metric_result, before, after):
    source = _MetricBackend(before, [[1.0, 0.0]] * metric_result.source_count)
    target = _MetricBackend(after)

    assert await _metric_change(source, target, metric_result, allow=False) is None
    assert any("scores change scale" in warning for warning in metric_result.warnings)
    assert source.closed


@pytest.mark.parametrize(
    ("backend_type", "config", "metric"),
    [
        ("postgres", {}, "cosine"),
        ("opensearch", {"url_variable": "OPENSEARCH_URL"}, "l2"),
        ("opensearch", {"url_variable": "OPENSEARCH_URL", "space_type": "cosinesimil"}, "cosine"),
        ("opensearch", {"url_variable": "OPENSEARCH_URL", "space_type": "innerproduct"}, "inner_product"),
    ],
)
def test_backends_report_the_metric_they_rank_by(tmp_path: Path, backend_type, config, metric):
    backend = create_backend(backend_type, kb_name="kb", kb_path=tmp_path, backend_config=config, user_id=uuid.uuid4())
    assert backend.distance_metric == metric


@pytest.mark.api_key_required
@pytest.mark.parametrize("space_type", ["cosinesimil", "innerproduct"])
@pytest.mark.parametrize("write", ["ingest", "copy"])
async def test_opensearch_creates_its_index_with_the_configured_space_type(tmp_path: Path, space_type, write):
    # distance_metric reports the configured space_type, so the index has to rank by it.
    if os.getenv("LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS") != "1" or not os.getenv("OPENSEARCH_URL"):
        pytest.skip("Set LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1 and OPENSEARCH_URL")
    pytest.importorskip("opensearchpy")
    backend = create_backend(
        "opensearch",
        kb_name=f"kb_space_{uuid.uuid4().hex[:6]}",
        kb_path=tmp_path,
        backend_config={"url_variable": "OPENSEARCH_URL", "space_type": space_type},
        embedding_function=DeterministicFakeEmbedding(size=DIM),
        user_id=uuid.uuid4(),
    )
    try:
        if write == "ingest":
            await backend.add_documents([Document(page_content="doc")])
        else:
            await backend.add_embedded_documents([IngestedDocument(id="c0", content="doc", embedding=[0.5] * DIM)])

        mapping = backend._os_client.indices.get_mapping(index=backend._os_index)
        method = mapping[backend._os_index]["mappings"]["properties"]["vector_field"]["method"]
        assert method["space_type"] == space_type
    finally:
        await backend.delete_collection()
        await backend.teardown()


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
                assert moved[doc.id].metadata == doc.metadata
                assert moved[doc.id].embedding == pytest.approx(doc.embedding)

            # The row now names the target, so a second run leaves it alone.
            rerun = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})
            assert next(r for r in rerun if r.kb_id == record.id).status == "skipped"
        finally:
            with contextlib.suppress(Exception):
                await target.delete_collection()
            await target.teardown()

    async def test_vectors_that_are_not_unit_length_are_not_moved_to_another_metric(self, active_user):
        # SQLite ranks by l2 unless configured otherwise, and pgvector by cosine. For
        # vectors that are not unit length the two disagree on neighbours, and every
        # count would still match.
        kb_name = f"kb_metric_{uuid.uuid4().hex[:6]}"
        record, _ = await _seed_sqlite_kb(active_user.id, kb_name, 6, unit=False)

        for dry_run in (True, False):
            results = await relocate_knowledge_bases(
                target_backend_type="postgres", target_backend_config={}, dry_run=dry_run
            )
            result = next(r for r in results if r.kb_id == record.id)
            assert result.status == "failed"
            assert "ranks by l2 distance and the target by cosine" in result.reason
            assert "not unit length" in result.reason
            assert result.copied == 0

        assert (await knowledge_base_service.get_by_id(record.id)).backend_type == "sqlite"

    async def test_allow_metric_change_moves_them_anyway_with_a_warning(self, active_user, tmp_path: Path):
        kb_name = f"kb_allow_{uuid.uuid4().hex[:6]}"
        record, _ = await _seed_sqlite_kb(active_user.id, kb_name, 6, unit=False)
        target = create_backend(
            "postgres", kb_name=kb_name, kb_path=tmp_path, backend_config={}, user_id=active_user.id
        )
        try:
            results = await relocate_knowledge_bases(
                target_backend_type="postgres", target_backend_config={}, allow_metric_change=True
            )
            result = next(r for r in results if r.kb_id == record.id)
            assert result.status == "relocated", result.reason
            assert any(
                "ranks by l2 distance and the target by cosine" in w and "may change" in w for w in result.warnings
            ), result.warnings
        finally:
            with contextlib.suppress(Exception):
                await target.delete_collection()
            await target.teardown()

    async def test_nonunit_vector_beyond_first_batch_prevents_copy(self, active_user, tmp_path: Path):
        kb_name = f"kb_late_metric_{uuid.uuid4().hex[:6]}"
        record, _ = await _seed_sqlite_kb(active_user.id, kb_name, 100)
        source = await backend_for_record(record)
        target = create_backend(
            "postgres", kb_name=kb_name, kb_path=tmp_path, backend_config={}, user_id=active_user.id
        )
        try:
            await source.add_embedded_documents(
                [IngestedDocument(id="z-nonunit", content="last", embedding=[2.0] * DIM)]
            )
            await _set_row(record.id, chunks=101)
            for dry_run in (True, False):
                results = await relocate_knowledge_bases(
                    target_backend_type="postgres", target_backend_config={}, dry_run=dry_run
                )
                result = next(r for r in results if r.kb_id == record.id)
                assert result.status == "failed", result.reason
                assert "not unit length" in result.reason
                assert result.copied == 0
                assert (await knowledge_base_service.get_by_id(record.id)).backend_type == "sqlite"
            assert await target.count() == 0
        finally:
            await source.teardown()
            with contextlib.suppress(Exception):
                await target.delete_collection()
            await target.teardown()

    async def test_unit_length_vectors_move_with_a_warning_about_scores(self, active_user, tmp_path: Path):
        kb_name = f"kb_unit_{uuid.uuid4().hex[:6]}"
        record, _ = await _seed_sqlite_kb(active_user.id, kb_name, 6)
        target = create_backend(
            "postgres", kb_name=kb_name, kb_path=tmp_path, backend_config={}, user_id=active_user.id
        )
        try:
            results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})
            result = next(r for r in results if r.kb_id == record.id)
            assert result.status == "relocated", result.reason
            assert any("scores change scale" in warning for warning in result.warnings), result.warnings
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

    async def test_row_moved_to_another_generation_mid_copy_is_not_repointed(self, active_user, tmp_path, during_copy):
        # The copy goes on reading the generation it opened, so its counts agree;
        # only the row shows that what it routes to is no longer what was copied.
        kb_name = f"kb_regen_{uuid.uuid4().hex[:6]}"
        records = []

        async def new_generation():
            await _set_row(records[0].id, storage_generation=2)

        during_copy(new_generation)
        record, result = await self._move(active_user, tmp_path, kb_name, on_record=records.append)

        assert result.status == "failed", (result.source_count, result.copied, result.target_count)
        assert "storage changed" in result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert (row.backend_type, row.storage_generation) == ("sqlite", 2)

    async def test_write_under_way_when_the_copy_ends_is_counted_before_the_repoint(
        self, active_user, tmp_path, during_copy
    ):
        kb_name = f"kb_inflight_{uuid.uuid4().hex[:6]}"
        locked = asyncio.Event()
        moves: list[asyncio.Task] = []
        writes: list[asyncio.Task] = []

        async def write_under_way():
            # What a guarded write does: take the storage lock, check the routing, then
            # write to the store it resolved. This one passes the check before the copy
            # ends and writes after the move would have repointed without the lock.
            record = await knowledge_base_service.get_by_user_and_name(active_user.id, kb_name)
            async with operation(record):
                locked.set()
                await asyncio.wait(moves, timeout=2)
                source = unfenced_backend(record)
                try:
                    await source.add_embedded_documents(
                        [IngestedDocument(id="a-late", content="late", metadata={}, embedding=[0.5] * DIM)]
                    )
                finally:
                    await source.teardown()

        async def start_write():
            writes.append(asyncio.create_task(write_under_way()))
            await locked.wait()

        during_copy(start_write)
        moves.append(asyncio.create_task(self._move(active_user, tmp_path, kb_name)))
        record, result = await moves[0]
        await writes[0]

        assert result.status == "failed", (result.source_count, result.copied, result.target_count)
        assert "source changed during the copy (12 -> 13 chunks)" in result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "sqlite"


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
