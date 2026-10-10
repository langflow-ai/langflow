"""Tests for relocating knowledge base vectors between backends.

Runs against the real test database and real local SQLite stores, created the
way the app creates them. The SQLite-to-Postgres move needs a pgvector database
and is opt-in via ``LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1`` and
``PGVECTOR_CONNECTION_STRING``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
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
from langflow.__main__ import _relocate_kb, app
from langflow.api.utils import knowledge_base_service
from langflow.api.utils.knowledge_base_relocation import (
    KBRelocationResult,
    _metric_change,
    _repoint,
    _short_on_the_target,
    relocate_knowledge_bases,
    validate_relocation_target_config,
)
from langflow.api.utils.migration_copies import copy_command
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord, KnowledgeBaseStatus
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.knowledge_base_storage.runtime import backend_for_record, operation, unfenced_backend
from lfx.base.knowledge_bases.backends import BackendType, IngestedDocument, PostgresBackend, create_backend
from lfx.base.knowledge_bases.backends.base import BackendConfigurationError
from pydantic import SecretStr
from typer.testing import CliRunner

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


@pytest.fixture
def quiet_libraries(caplog: pytest.LogCaptureFixture) -> None:
    """Keep library INFO records (alembic's, here) off stdout for tests that read what the command prints.

    The test session's log handler prints them there; the command line's own prints to stderr.
    """
    caplog.set_level(logging.WARNING)


def _json_events(out: str) -> list[dict]:
    """Every line of ``out`` parsed as JSON, so a stray non-JSON line fails the test."""
    return [json.loads(line) for line in out.splitlines()]


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
        assert result.code == "kb_backend_missing"
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "astra"

    async def test_kb_already_on_the_target_is_skipped(self, active_user):
        record = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_on_pg", backend_type="postgres"
        )

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        assert next(r for r in results if r.kb_id == record.id).status == "skipped"

    @pytest.mark.parametrize("config", [{}, {"note": "kept"}])
    async def test_kb_already_on_the_target_is_counted_there_first_when_asked(self, active_user, monkeypatch, config):
        # Both skips: a config equal to the target's, and another config that resolves to the same store.
        # The count fails here, with no driver for the address or with nothing listening at it. A skip that
        # makes none does not.
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", "postgresql+psycopg://postgres@127.0.0.1:1/none")
        recorded = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_pg_recorded", backend_type="postgres", backend_config=config, chunks=3
        )
        empty = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_pg_empty", backend_type="postgres", backend_config=config
        )

        async def outcome(**asked):
            results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={}, **asked)
            by_id = {result.kb_id: (result.status, result.code) for result in results}
            return [by_id[recorded.id], by_id[empty.id]]

        # Unless asked, relocate_knowledge_bases looks at neither.
        assert await outcome() == [("skipped", None), ("skipped", None)]
        # Asked to, it counts the one that records chunks. One that records none has nothing to miss.
        assert await outcome(verify_skipped=True) == [("failed", "kb_target_unreachable"), ("skipped", None)]

    async def test_dry_run_checks_the_target_is_reachable(self, active_user, monkeypatch):
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        record, _ = await _seed_sqlite_kb(active_user.id, "kb_dry_unreachable", 2)

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={}, dry_run=True)

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert "target" in result.reason
        assert result.code == "kb_target_unreachable"

    async def test_kb_being_ingested_is_not_moved(self, active_user):
        # An ingestion still running would keep writing to the source after the copy.
        record, _ = await _seed_sqlite_kb(active_user.id, "kb_busy", 2)
        await knowledge_base_service.update_status(record.id, status=KnowledgeBaseStatus.INGESTING)

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert "ingesting" in result.reason
        assert result.code == "kb_ingesting"
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
        assert result.code == "kb_short"
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "sqlite"

    async def test_kb_already_on_the_target_is_short_when_its_store_holds_fewer_chunks(self, active_user):
        # There is no pgvector server here, so the store that is counted is a SQLite one. The rule reads no type.
        # That pgvector counts a table that is not there as 0 is checked only by the live tests.
        short, _ = await _seed_sqlite_kb(active_user.id, "kb_holds_4_of_10", 4, chunks=10)
        whole, _ = await _seed_sqlite_kb(active_user.id, "kb_holds_4_of_4", 4)

        def result(record):
            return KBRelocationResult(
                kb_id=record.id,
                kb_name=record.name,
                owner="alice",
                source_backend="sqlite",
                target_backend="sqlite",
                status="failed",
                source_count=record.chunks,
            )

        found, passed = result(short), result(whole)

        assert "4 of its 10" in await _short_on_the_target(short, found)
        assert (found.code, found.target_count) == ("kb_target_short", 4)
        assert await _short_on_the_target(whole, passed) is None
        assert (passed.code, passed.target_count) == (None, 4)

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
        assert result.code == "kb_upgrade_pending"
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
        ("target", "config", "how", "flag", "suggested"),
        [
            ("postgres", {}, "--allow-metric-change", "--allow-metric-change", None),
            # A new OpenSearch index can take the source's metric and an existing one cannot, so both are offered.
            (
                "opensearch",
                {"url_variable": "OPENSEARCH_URL", "space_type": "cosinesimil"},
                '{"space_type": "l2"}',
                "--allow-metric-change",
                {"space_type": "l2"},
            ),
        ],
    )
    async def test_metric_refusal_says_how_to_proceed(
        self, active_user, monkeypatch, request, target, config, how, flag, suggested
    ):
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
        assert flag in result.reason
        assert (result.code, result.flag, result.target_config) == ("kb_metric_change", flag, suggested)

    async def test_unknown_target_backend_is_reported_as_missing(self, active_user):
        record, _ = await _seed_sqlite_kb(active_user.id, "kb_nowhere", 2)

        results = await relocate_knowledge_bases(target_backend_type="nope", target_backend_config={})

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert result.reason.startswith("ValueError: Unknown vector-store backend 'nope'")
        assert result.code == "kb_backend_missing"

    @pytest.mark.parametrize(
        ("target", "config", "variable", "needs"),
        [
            ("postgres", {}, "PGVECTOR_CONNECTION_STRING", "PostgresBackend needs the 'PGVECTOR_CONNECTION_STRING'"),
            # An OpenSearch target resolves its settings earlier, to read the metric its index ranks by.
            (
                "opensearch",
                {"url_variable": "OPENSEARCH_URL"},
                "OPENSEARCH_URL",
                "OpenSearchBackend needs the 'OPENSEARCH_URL'",
            ),
        ],
    )
    async def test_target_without_its_connection_settings_is_told_apart_from_other_failures(
        self, active_user, monkeypatch, target, config, variable, needs
    ):
        monkeypatch.delenv(variable, raising=False)
        record, _ = await _seed_sqlite_kb(active_user.id, f"kb_no_target_{target}", 2)

        results = await relocate_knowledge_bases(target_backend_type=target, target_backend_config=config)

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert result.reason.startswith(f"ValueError: {needs}")
        assert result.code == "kb_target_unreachable"

    async def test_source_that_cannot_be_opened_is_a_plain_failure(self, active_user):
        # A row whose SQLite store was never created, or has been lost since.
        record = KnowledgeBaseRecord(user_id=active_user.id, name="kb_lost", model_selection=MODEL, chunks=2)
        async with session_scope() as session:
            session.add(record)
            await session.commit()

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert result.reason == "FileNotFoundError: SQLite knowledge base storage is missing"
        assert result.code == "kb_failed"


@pytest.mark.parametrize(
    ("target", "config", "variable", "nowhere", "driver", "error"),
    [
        (
            "postgres",
            {},
            "PGVECTOR_CONNECTION_STRING",
            "postgresql+psycopg://postgres@127.0.0.1:1/none",
            "psycopg",
            "OperationalError",
        ),
        (
            "opensearch",
            {"url_variable": "OPENSEARCH_URL"},
            "OPENSEARCH_URL",
            "http://127.0.0.1:1",
            "opensearchpy",
            "ConnectionError",
        ),
    ],
)
@pytest.mark.parametrize("chunks", [2, 0])
@pytest.mark.usefixtures("kb_root")
async def test_target_that_cannot_be_reached_is_told_apart(
    active_user, monkeypatch, target, config, variable, nowhere, driver, error, chunks
):
    # Nothing listens there. A real run first connects to Postgres when it writes, and to
    # OpenSearch before that, to read the metric its index ranks by. A knowledge base with
    # no chunks has nothing to write, so it first connects to Postgres to count what arrived.
    pytest.importorskip(driver)
    if target == "postgres":
        pytest.importorskip("pgvector")
    monkeypatch.setenv(variable, nowhere)
    kb_name = f"kb_nowhere_{target}"
    record, _ = await _seed_sqlite_kb(active_user.id, kb_name, chunks)

    results = await relocate_knowledge_bases(target_backend_type=target, target_backend_config=config)

    result = next(r for r in results if r.kb_id == record.id)
    assert result.status == "failed"
    assert result.reason.startswith(f"{error}: ")
    assert result.copied == 0
    assert result.code == "kb_target_unreachable"
    assert (await knowledge_base_service.get_by_id(record.id)).backend_type == "sqlite"


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

    @pytest.mark.usefixtures("old_audit_row", "quiet_libraries")
    async def test_json_reports_a_database_behind_this_langflow_as_an_error_event(self, capsys):
        earlier = "9d7e2a6c4b81"  # pragma: allowlist secret
        async with session_scope() as session:
            await session.exec(sa.text("UPDATE alembic_version SET version_num = :v").bindparams(v=earlier))
        capsys.readouterr()

        with pytest.raises(typer.Exit) as refused:
            await _relocate_kb(
                target_backend_type="postgres",
                target_backend_config={},
                username=None,
                dry_run=True,
                batch_size=500,
                as_json=True,
            )

        assert refused.value.exit_code == 1
        (event,) = _json_events(capsys.readouterr().out)
        assert (event["event"], event["code"]) == ("error", "schema_mismatch")
        assert earlier in event["message"]

    @pytest.mark.usefixtures("quiet_libraries")
    async def test_json_stream_of_a_dry_run(self, active_user, kb_root, capsys, monkeypatch):  # noqa: ARG002
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        refused, _ = await _seed_sqlite_kb(active_user.id, "kb_json_metric", 6, unit=False)
        busy, _ = await _seed_sqlite_kb(active_user.id, "kb_json_busy", 2)
        await knowledge_base_service.update_status(busy.id, status=KnowledgeBaseStatus.INGESTING)
        skipped = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_json_there", backend_type="postgres"
        )
        capsys.readouterr()

        failed = await _relocate_kb(
            target_backend_type="postgres",
            target_backend_config={},
            username=active_user.username,
            dry_run=True,
            batch_size=500,
            as_json=True,
        )

        # Every line of stdout is an event: one item per knowledge base, then the report.
        *items, report = _json_events(capsys.readouterr().out)
        assert failed == 2
        assert {event["event"] for event in items} == {"item"}
        by_id = {event["item"]["kb_id"]: event["item"] for event in items}
        assert len(items) == len(by_id) == 3
        assert by_id[str(skipped.id)] == {
            "kb_id": str(skipped.id),
            "kb_name": "kb_json_there",
            "owner": active_user.username,
            "source_backend": "postgres",
            "target_backend": "postgres",
            "status": "skipped",
            "source_count": 0,
            "copied": 0,
            "target_count": 0,
            "reason": "already on the target backend",
            "warnings": [],
            "code": None,
            "flag": None,
            "target_config": None,
        }
        assert by_id[str(busy.id)]["code"] == "kb_ingesting"
        metric = by_id[str(refused.id)]
        assert (metric["status"], metric["code"], metric["flag"]) == (
            "failed",
            "kb_metric_change",
            "--allow-metric-change",
        )
        assert report["event"] == "report"
        assert (report["ok"], report["dry_run"], report["counts"]) == (False, True, {"failed": 2, "skipped": 1})
        # The report repeats only what needs attention, in the shape the items came in.
        assert sorted(report["attention"], key=str) == sorted([by_id[str(busy.id)], metric], key=str)

    @pytest.mark.usefixtures("quiet_libraries")
    async def test_json_stream_reports_a_kb_whose_store_cannot_be_counted(self, active_user, capsys, monkeypatch):
        # With no PGVECTOR_CONNECTION_STRING there is no store to count, and the helper says so when it is asked
        # to count. Unless asked, it skips the knowledge base. The command asks unless it is told not to.
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        there = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_json_recorded", backend_type="postgres", chunks=3
        )
        capsys.readouterr()

        async def run(**asked):
            failed = await _relocate_kb(
                target_backend_type="postgres",
                target_backend_config={},
                username=active_user.username,
                dry_run=True,
                batch_size=500,
                as_json=True,
                **asked,
            )
            return failed, *_json_events(capsys.readouterr().out)

        failed, item, report = await run()
        assert (failed, item["item"]["status"], report["counts"]) == (0, "skipped", {"skipped": 1})

        failed, item, report = await run(verify_skipped=True)

        assert failed == 1
        assert (item["item"]["kb_id"], item["item"]["status"]) == (str(there.id), "failed")
        assert item["item"]["code"] == "kb_target_unreachable"
        assert item["item"]["reason"].startswith("could not count it on the target: ValueError: PostgresBackend needs")
        assert (report["ok"], report["counts"], report["attention"]) == (False, {"failed": 1}, [item["item"]])

    def test_the_command_takes_the_line_the_migration_page_gives_a_copy_from_sqlite(self):
        # The page starts the command as a child with this line. An option the command does not have would end
        # every such copy on a usage error, so the line is read here by the command's own parser.
        argv = copy_command("copy_knowledge_bases", {"database": {}}, dry_run=True)
        command = typer.main.get_command(app).commands["relocate-kb"]

        context = command.make_context("relocate-kb", argv[4:])

        asked = (context.params["verify_skipped"], context.params["dry_run"], context.params["as_json"])
        assert asked == (True, True, True)

    @pytest.mark.parametrize(
        ("options", "counted"), [([], True), (["--verify-skipped"], True), (["--no-verify-skipped"], False)]
    )
    def test_the_command_counts_before_it_skips_unless_it_is_told_not_to(self, options, counted):
        # Run by hand the command counts, so a knowledge base kept in another store is not passed over in
        # silence. The migration page gives the option either way.
        command = typer.main.get_command(app).commands["relocate-kb"]

        context = command.make_context("relocate-kb", ["--to", "postgres", *options])

        assert context.params["verify_skipped"] is counted

    @pytest.mark.usefixtures("quiet_libraries")
    async def test_text_output_is_the_same_without_json(self, active_user, kb_root, capsys, monkeypatch):  # noqa: ARG002
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
        await _seed_sqlite_kb(active_user.id, "kb_text", 2, model_selection=None)
        await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_text_there", backend_type="postgres"
        )
        capsys.readouterr()

        failed = await _relocate_kb(
            target_backend_type="postgres",
            target_backend_config={},
            username=active_user.username,
            dry_run=True,
            batch_size=500,
        )

        owner = active_user.username
        moving = [
            f"failed          {owner}/kb_text  sqlite -> postgres  chunks 0/2  (target is not reachable: "
            "PostgresBackend needs the 'PGVECTOR_CONNECTION_STRING' environment variable populated with a "
            "Postgres connection string, e.g. "
            "'postgresql+psycopg://user:pass@host:5432/dbname'.)",  # pragma: allowlist secret
            "                warning: model_selection is empty, "
            "so the embedding model that produced these vectors is unknown",
            "                warning: the source ranks by l2 distance and the target by cosine; "
            "these vectors are unit length, so the same neighbours come back but scores change scale",
        ]
        there = (
            f"skipped         {owner}/kb_text_there  postgres -> postgres  chunks 0  (already on the target backend)"
        )
        summary = "Knowledge base relocation dry run complete: 1 failed, 1 skipped."
        # Knowledge bases come in whatever order the database returns them.
        assert capsys.readouterr().out.splitlines() in ([*moving, there, summary], [there, *moving, summary])
        assert failed == 1


@pytest.mark.parametrize(
    "target_config",
    ["{not json", '["a list"]', '{"index_name": "shared"}'],
)
def test_json_reports_a_bad_target_config_as_an_error_event(target_config):
    result = CliRunner().invoke(app, ["relocate-kb", "--to", "opensearch", "--target-config", target_config, "--json"])

    assert result.exit_code == 2
    (event,) = _json_events(result.stdout)
    assert (event["event"], event["code"]) == ("error", "bad_target_config")
    assert "--target-config" in event["message"]


def test_progress_total_is_null_when_the_source_count_is_not_known(capsys):
    from langflow.cli.relocate_kb_events import progress

    kb_id = uuid.uuid4()
    result = KBRelocationResult(
        kb_id=kb_id,
        kb_name="kb",
        owner="alice",
        source_backend="sqlite",
        target_backend="postgres",
        status="failed",
        source_count=0,
        copied=5,
    )

    progress(result)

    assert _json_events(capsys.readouterr().out) == [
        {"event": "progress", "phase": "copying", "done": 5, "total": None, "unit": "chunks", "subject": str(kb_id)}
    ]


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


@pytest.mark.parametrize(
    ("code", "hinted"), [("kb_target_short", True), ("kb_target_unreachable", False), (None, False)]
)
def test_a_short_count_says_how_to_get_past_it_when_the_store_is_the_right_one(code, hinted):
    # The reason names one cause, chunks kept in another store. A row that records too many chunks over the
    # right store fails the same way, and the way past it is an option only the command line has.
    from langflow.__main__ import relocation_lines

    result = KBRelocationResult(
        kb_id=uuid.uuid4(),
        kb_name="kb",
        owner="alice",
        source_backend="postgres",
        target_backend="postgres",
        status="failed",
        source_count=5,
        target_count=3,
        code=code,
        reason="why",
        warnings=["a warning"],
    )

    lines = relocation_lines(result)

    assert lines[0].endswith("(why)")
    assert lines[-1].endswith("warning: a warning")
    assert [line.split()[0] for line in lines[1:-1]] == (["hint:"] if hinted else [])
    assert any("--no-verify-skipped" in line for line in lines) is hinted


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
    assert metric_result.code == "kb_metric_change"
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
    # Neither is a metric change, and accepting one does not get past them.
    code = "kb_no_vectors" if last_vector is None else "kb_read_short"
    assert (metric_result.code, metric_result.flag, metric_result.target_config) == (code, None, None)
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
        assert metric_result.code is None
        assert any("may rank unit vectors differently" in warning for warning in metric_result.warnings)
    else:
        assert "may rank unit vectors differently" in reason
        assert "--allow-metric-change" in reason
        assert metric_result.code == "kb_metric_change"
        assert metric_result.warnings == []


@pytest.mark.parametrize(("before", "after"), [("l2", "cosine"), ("cosine", "inner_product"), ("inner_product", "l2")])
async def test_unit_vectors_remain_equivalent_across_supported_metrics(metric_result, before, after):
    source = _MetricBackend(before, [[1.0, 0.0]] * metric_result.source_count)
    target = _MetricBackend(after)

    assert await _metric_change(source, target, metric_result, allow=False) is None
    assert any("scores change scale" in warning for warning in metric_result.warnings)
    assert source.closed


@pytest.mark.parametrize("store", ["source", "target"])
async def test_store_that_cannot_say_its_metric_is_told_apart(metric_result, store):
    class _NoMetric(_MetricBackend):
        async def get_distance_metric(self) -> str:
            # As OpenSearch does for an index whose mapping does not give the search field's metric.
            msg = "Cannot determine the search distance metric"
            raise BackendConfigurationError(msg)

    source = _NoMetric("l2") if store == "source" else _MetricBackend("l2")
    target = _NoMetric("cosine") if store == "target" else _MetricBackend("cosine")

    with pytest.raises(BackendConfigurationError):
        await _metric_change(source, target, metric_result, allow=True)

    assert metric_result.code == "kb_metric_unknown"


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

            # The row now names the target, so a second run leaves it alone, counted or not.
            for asked in ({}, {"verify_skipped": True}):
                rerun = await relocate_knowledge_bases(
                    target_backend_type="postgres", target_backend_config={}, **asked
                )
                assert next(r for r in rerun if r.kb_id == record.id).status == "skipped"
        finally:
            with contextlib.suppress(Exception):
                await target.delete_collection()
            await target.teardown()

    @pytest.mark.usefixtures("quiet_libraries")
    async def test_kb_recorded_on_the_target_without_its_chunks_there_is_short_when_asked(self, active_user, capsys):
        # What a knowledge base kept in another pgvector store looks like from here: its row says postgres
        # and records 36 chunks, and the store this run reads has no table for it.
        record = await knowledge_base_service.create_record(
            user_id=active_user.id, name=f"kb_elsewhere_{uuid.uuid4().hex[:6]}", backend_type="postgres", chunks=36
        )
        store = unfenced_backend(record)

        async def run(**asked):
            results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={}, **asked)
            return next(result for result in results if result.kb_id == record.id)

        try:
            assert (await run()).status == "skipped"
            for dry_run in (True, False):
                short = await run(verify_skipped=True, dry_run=dry_run)
                assert (short.status, short.code, short.copied) == ("failed", "kb_target_short", 0)
                assert "0 of its 36" in short.reason
            # Typed by hand, the command says under the knowledge base how to get past it.
            capsys.readouterr()
            failed = await _relocate_kb(
                target_backend_type="postgres",
                target_backend_config={},
                username=active_user.username,
                dry_run=True,
                batch_size=500,
                verify_skipped=True,
            )
            printed = capsys.readouterr().out.splitlines()
            at = next(index for index, line in enumerate(printed) if record.name in line)
            assert failed == 1
            assert printed[at + 1].split()[:1] == ["hint:"]
            # Once the store holds what the row records, the knowledge base is there.
            chunks = [IngestedDocument(id=f"c{i}", content="doc", embedding=[0.5] * DIM) for i in range(36)]
            await store.add_embedded_documents(chunks)
            assert (await run(verify_skipped=True)).status == "skipped"
        finally:
            with contextlib.suppress(Exception):
                await store.delete_collection()
            await store.teardown()

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
        assert result.code == "kb_changed"
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
        assert result.code == "kb_target_more"
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
        assert result.code == "kb_deleted"

    async def test_chunk_that_leaves_the_source_mid_copy_stops_the_repoint(self, active_user, tmp_path, during_copy):
        kb_name = f"kb_cut_{uuid.uuid4().hex[:6]}"

        async def delete_unread_chunk():
            record = await knowledge_base_service.get_by_user_and_name(active_user.id, kb_name)
            source = await backend_for_record(record)
            try:
                # SQLite reads in id order, and "chunk-9" sorts last, so it is still unread.
                await source.delete_by({"i": 9})
            finally:
                await source.teardown()

        during_copy(delete_unread_chunk)
        record, result = await self._move(active_user, tmp_path, kb_name)

        assert result.status == "failed"
        assert result.reason == "read 11 of 12 chunks from the source; not repointing"
        assert result.code == "kb_read_short"
        assert (await knowledge_base_service.get_by_id(record.id)).backend_type == "sqlite"

    @pytest.mark.parametrize("space_type", ["l2", "cosinesimil"])
    async def test_chunk_stored_without_a_vector_is_not_copied(self, active_user, tmp_path, space_type):
        if os.getenv("LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS") != "1" or not os.getenv("OPENSEARCH_URL"):
            pytest.skip("Set LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1 and OPENSEARCH_URL")
        pytest.importorskip("opensearchpy")
        # Postgres ranks by cosine. For a target that ranks by l2 the metric check reads the
        # source and finds the chunk, and for one that ranks by cosine too the copy does.
        kb_name = f"kb_bare_{uuid.uuid4().hex[:6]}"
        source = create_backend(
            "postgres", kb_name=kb_name, kb_path=tmp_path, backend_config={}, user_id=active_user.id
        )
        try:
            await source.add_embedded_documents(
                [IngestedDocument(id="c0", content="doc", metadata={}, embedding=_vector(0, unit=True))]
            )
            async with source._ensure_async_engine().begin() as conn:
                await conn.execute(sa.insert(source._embedding_table()).values(id="bare", document="doc"))
            record = await knowledge_base_service.create_record(
                user_id=active_user.id,
                name=kb_name,
                backend_type="postgres",
                model_selection={"name": "m", "provider": "p"},
                chunks=2,
            )

            results = await relocate_knowledge_bases(
                target_backend_type="opensearch",
                target_backend_config={"url_variable": "OPENSEARCH_URL", "space_type": space_type},
            )

            result = next(r for r in results if r.kb_id == record.id)
            assert result.status == "failed"
            assert "without vectors" in result.reason
            assert result.code == "kb_no_vectors"
            assert (await knowledge_base_service.get_by_id(record.id)).backend_type == "postgres"
        finally:
            with contextlib.suppress(Exception):
                await source.delete_collection()
            await source.teardown()

    async def test_failed_write_is_reported_without_the_chunks_it_carried(self, active_user, tmp_path):
        # SQLite stores a NUL byte and Postgres refuses one. SQLAlchemy's error quotes the
        # statement with its parameters, which are the chunks of the batch, and the
        # driver's own goes on to quote the metadata it could not take.
        kb_name = f"kb_nul_{uuid.uuid4().hex[:6]}"
        record, _ = await _seed_sqlite_kb(active_user.id, kb_name, 2, chunks=3)
        source = await backend_for_record(record)
        try:
            await source.add_embedded_documents(
                [
                    IngestedDocument(
                        id="nul",
                        content="private chunk text",
                        metadata={"note": "private\x00note"},
                        embedding=_vector(2, unit=True),
                    )
                ]
            )
        finally:
            await source.teardown()
        target = create_backend(
            "postgres", kb_name=kb_name, kb_path=tmp_path, backend_config={}, user_id=active_user.id
        )
        try:
            results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

            result = next(r for r in results if r.kb_id == record.id)
            assert (result.status, result.code) == ("failed", "kb_failed")
            assert "private" not in result.reason
            assert "doc 0" not in result.reason
            assert result.reason == "UntranslatableCharacter: database operation failed"
            assert (await knowledge_base_service.get_by_id(record.id)).backend_type == "sqlite"
        finally:
            with contextlib.suppress(Exception):
                await target.delete_collection()
            await target.teardown()

    @pytest.mark.usefixtures("quiet_libraries")
    async def test_json_stream_of_a_real_run(self, active_user, tmp_path: Path, capsys):
        suffix = uuid.uuid4().hex[:6]
        moved, _ = await _seed_sqlite_kb(active_user.id, f"kb_json_moved_{suffix}", 12)
        refused, _ = await _seed_sqlite_kb(active_user.id, f"kb_json_metric_{suffix}", 6, unit=False)
        skipped = await knowledge_base_service.create_record(
            user_id=active_user.id, name=f"kb_json_there_{suffix}", backend_type="postgres"
        )
        target = create_backend(
            "postgres", kb_name=moved.name, kb_path=tmp_path, backend_config={}, user_id=active_user.id
        )
        capsys.readouterr()
        try:
            failed = await _relocate_kb(
                target_backend_type="postgres",
                target_backend_config={},
                username=active_user.username,
                dry_run=False,
                batch_size=5,
                as_json=True,
            )

            events = _json_events(capsys.readouterr().out)
            assert failed == 1
            items = {event["item"]["kb_id"]: event["item"] for event in events if event["event"] == "item"}
            assert items.keys() == {str(moved.id), str(refused.id), str(skipped.id)}
            assert {kb_id: (item["status"], item["code"], item["flag"]) for kb_id, item in items.items()} == {
                str(moved.id): ("relocated", None, None),
                str(refused.id): ("failed", "kb_metric_change", "--allow-metric-change"),
                str(skipped.id): ("skipped", None, None),
            }

            # Progress belongs to the one knowledge base that was copied, and comes before its item.
            progress = [event for event in events if event["event"] == "progress"]
            assert [(event["done"], event["total"]) for event in progress] == [(5, 12), (10, 12), (12, 12)]
            assert {(event["phase"], event["unit"], event["subject"]) for event in progress} == {
                ("copying", "chunks", str(moved.id))
            }
            moved_item = {"event": "item", "item": items[str(moved.id)]}
            assert events.index(progress[-1]) < events.index(moved_item)

            assert events[-1] == {
                "event": "report",
                "ok": False,
                "dry_run": False,
                "counts": {"relocated": 1, "failed": 1, "skipped": 1},
                "attention": [items[str(refused.id)]],
            }
            assert [event["event"] for event in events].count("report") == 1
            assert (await knowledge_base_service.get_by_id(moved.id)).backend_type == "postgres"
        finally:
            with contextlib.suppress(Exception):
                await target.delete_collection()
            await target.teardown()

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
        assert result.code == "kb_routing_changed", result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert (row.backend_type, row.storage_generation) == ("sqlite", 2)

    async def test_storage_lock_that_stays_busy_is_a_plain_failure(
        self, active_user, tmp_path, during_copy, monkeypatch
    ):
        # The lock refuses a row it cannot get with the error it has for a rerouted one,
        # and this row is as it was read.
        monkeypatch.setattr("langflow.services.knowledge_base_storage.runtime.LOCK_TIMEOUT_SECONDS", 0.2)
        kb_name = f"kb_busy_{uuid.uuid4().hex[:6]}"
        held, release = asyncio.Event(), asyncio.Event()
        holders: list[asyncio.Task] = []

        async def hold_lock():
            record = await knowledge_base_service.get_by_user_and_name(active_user.id, kb_name)
            async with operation(record):
                held.set()
                await release.wait()

        async def start_holding():
            holders.append(asyncio.create_task(hold_lock()))
            await held.wait()

        during_copy(start_holding)
        try:
            record, result = await self._move(active_user, tmp_path, kb_name)
        finally:
            release.set()
            await holders[0]

        assert (result.status, result.code) == ("failed", "kb_failed"), result.reason
        assert result.reason == "StorageUnavailableError: Knowledge base storage is busy. Retry the operation."
        assert (await knowledge_base_service.get_by_id(record.id)).backend_type == "sqlite"

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
async def test_write_opensearch_rejects_is_reported_without_the_chunks(active_user, kb_root, tmp_path: Path):  # noqa: ARG001
    if os.getenv("LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS") != "1" or not os.getenv("OPENSEARCH_URL"):
        pytest.skip("Set LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1 and OPENSEARCH_URL")
    pytest.importorskip("opensearchpy")
    # The target index is left from another embedding model, with 4-dimensional vectors.
    # opensearch-py's error for the refused write quotes each chunk back, vector included.
    kb_name = f"kb_os_dim_{uuid.uuid4().hex[:6]}"
    config = {"url_variable": "OPENSEARCH_URL"}
    record, _ = await _seed_sqlite_kb(active_user.id, kb_name, 2)
    source = await backend_for_record(record)
    try:
        # As SQLite returns them, in float32, which is what the write would quote back.
        seeded = [doc async for batch in source.iter_documents(include_embeddings=True) for doc in batch]
    finally:
        await source.teardown()
    target = create_backend(
        "opensearch", kb_name=kb_name, kb_path=tmp_path, backend_config=config, user_id=active_user.id
    )
    try:
        await target.add_embedded_documents([IngestedDocument(id="stale", content="stale", embedding=[0.5] * 4)])

        results = await relocate_knowledge_bases(target_backend_type="opensearch", target_backend_config=config)

        result = next(r for r in results if r.kb_id == record.id)
        assert (result.status, result.code) == ("failed", "kb_failed")
        assert result.reason == "RuntimeError: 2 document(s) failed to index. Error type(s): mapper_parsing_exception."
        for doc in seeded:
            assert doc.content not in result.reason
            assert repr(doc.embedding[1]) not in result.reason
        assert (await knowledge_base_service.get_by_id(record.id)).backend_type == "sqlite"
    finally:
        await target.delete_collection()
        await target.teardown()


@pytest.mark.api_key_required
async def test_opensearch_index_that_does_not_say_its_metric_is_told_apart(active_user, kb_root, tmp_path: Path):  # noqa: ARG001
    if os.getenv("LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS") != "1" or not os.getenv("OPENSEARCH_URL"):
        pytest.skip("Set LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1 and OPENSEARCH_URL")
    pytest.importorskip("opensearchpy")
    # The target index is left from something that stored no vectors, so its mapping has no metric to read.
    kb_name = f"kb_os_plain_{uuid.uuid4().hex[:6]}"
    config = {"url_variable": "OPENSEARCH_URL"}
    record, _ = await _seed_sqlite_kb(active_user.id, kb_name, 2, unit=False)
    target = create_backend(
        "opensearch", kb_name=kb_name, kb_path=tmp_path, backend_config=config, user_id=active_user.id
    )
    try:
        await target.ensure_ready()
        _ = target.vector_store
        target._os_client.indices.create(index=target._os_index, body={"mappings": {"properties": {}}})

        # Accepting a metric change does not get past it: there is no known change to accept.
        results = await relocate_knowledge_bases(
            target_backend_type="opensearch", target_backend_config=config, allow_metric_change=True
        )

        result = next(r for r in results if r.kb_id == record.id)
        assert (result.status, result.code, result.copied) == ("failed", "kb_metric_unknown", 0)
        assert result.reason == (
            "BackendConfigurationError: Cannot determine the search distance metric "
            f"for OpenSearch index {target._os_index!r}"
        )
        assert (await knowledge_base_service.get_by_id(record.id)).backend_type == "sqlite"
    finally:
        await target.delete_collection()
        await target.teardown()


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
