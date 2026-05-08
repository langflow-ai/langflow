"""Integration tests for the KB ingestion-run visibility endpoints.

These drive ``GET /{kb}/runs`` and ``GET /{kb}/runs/{run_id}``
end-to-end against the real FastAPI app and test DB so we catch
routing, auth scoping, pagination, and SQL-level behavior in one
test pass.

Storage note: as of the unification onto the canonical ``job`` table,
ingestion-run data lives on ``Job.job_metadata``. The URL ``run_id``
path parameter is now the ``Job.job_id``; the response shape is
unchanged so the frontend is unaffected.

Asset-id semantics: ``Job.asset_id`` carries
``KnowledgeBaseRecord.id`` (the indexed DB pk) so the read path
(``list_runs_for_kb``) hits a btree-index lookup instead of a
JSON-extract on ``Job.job_metadata.kb_name``. Tests therefore seed a
matching ``KnowledgeBaseRecord`` alongside each ``Job`` so the new
indexed read path is exercised.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.deps import session_scope
from lfx.base.knowledge_bases.ingestion_sources.base import IngestionRunStatus

if TYPE_CHECKING:
    from httpx import AsyncClient


# Bump ``created_timestamp`` per insertion so the newest-first ordering
# test has a stable sort key. Without this, two rows inserted in the
# same wall-clock millisecond can flip order on fast hardware.
_INSERT_OFFSET_SECONDS = 0


def _next_created_timestamp() -> datetime:
    global _INSERT_OFFSET_SECONDS  # noqa: PLW0603
    _INSERT_OFFSET_SECONDS += 1
    return datetime.now(timezone.utc) + timedelta(seconds=_INSERT_OFFSET_SECONDS)


async def _ensure_kb_record(*, user_id: uuid.UUID, kb_name: str) -> uuid.UUID:
    """Create a minimal ``KnowledgeBaseRecord`` for ``kb_name`` if absent.

    Returns the record's ``id`` so callers can wire it into the
    ``Job.asset_id`` field — the indexed-read path filters on it.
    """
    existing = await knowledge_base_service.get_by_user_and_name(user_id, kb_name)
    if existing is not None:
        return existing.id
    record = await knowledge_base_service.create_record(
        user_id=user_id,
        name=kb_name,
        model_selection={
            "name": "sentence-transformers/all-MiniLM-L6-v2",
            "provider": "HuggingFace",
        },
    )
    return record.id


async def _insert_run(
    *,
    user_id: uuid.UUID,
    kb_name: str,
    kb_id: uuid.UUID | None = None,
    status: IngestionRunStatus = IngestionRunStatus.SUCCEEDED,
    source_type: str = "file_upload",
    items: list[dict] | None = None,
    succeeded: int = 1,
    failed: int = 0,
    source_config: dict | None = None,
) -> uuid.UUID:
    """Seed a ``Job`` row carrying KB ingestion-run data on its metadata.

    Auto-provisions a matching ``KnowledgeBaseRecord`` (when ``kb_id``
    is not supplied) so the new asset_id-indexed read path is
    exercised. Returns the ``job_id`` so callers can use it as the
    URL ``run_id`` — the two are equal post-unification.
    """
    if kb_id is None:
        kb_id = await _ensure_kb_record(user_id=user_id, kb_name=kb_name)

    run_id = uuid.uuid4()
    items_payload = items or [
        {
            "item_id": "0:a.txt",
            "display_name": "a.txt",
            "status": "succeeded",
            "chunks_created": 3,
            "error_message": None,
        }
    ]
    started_at = _next_created_timestamp()
    async with session_scope() as session:
        job = Job(
            job_id=run_id,
            flow_id=run_id,
            status=JobStatus.COMPLETED,
            type=JobType.INGESTION,
            user_id=user_id,
            asset_id=kb_id,
            asset_type="knowledge_base",
            created_timestamp=started_at,
            finished_timestamp=started_at,
            job_metadata={
                "kind": "kb_ingestion",
                "kb_name": kb_name,
                "kb_id": str(kb_id) if kb_id is not None else None,
                "source_type": source_type,
                "source_config": {"source_name": "demo"} if source_config is None else source_config,
                "status": status.value,
                "error_message": None,
                "total_items": succeeded + failed,
                "succeeded": succeeded,
                "failed": failed,
                "skipped": 0,
                "total_bytes": 1024,
                "chunks_created": succeeded * 3,
                "items": items_payload,
                "ingestion_run_id": str(run_id),
            },
        )
        session.add(job)
        await session.commit()
    return run_id


class TestListIngestionRuns:
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_returns_runs_for_kb_newest_first(
        self, mock_root, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "visibility_kb"
        kb_dir.mkdir(parents=True)

        first_id = await _insert_run(user_id=active_user.id, kb_name="visibility_kb", succeeded=2)
        second_id = await _insert_run(user_id=active_user.id, kb_name="visibility_kb", succeeded=5)

        response = await client.get(
            "api/v1/knowledge_bases/visibility_kb/runs",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] >= 2
        ids = [r["id"] for r in payload["runs"]]
        # Newer first
        assert ids.index(str(second_id)) < ids.index(str(first_id))

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_excludes_other_users_runs(
        self, mock_root, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "only_mine"
        kb_dir.mkdir(parents=True)

        mine = await _insert_run(user_id=active_user.id, kb_name="only_mine")
        other_user_id = uuid.uuid4()
        # Pass an explicit ``kb_id`` for the foreign-user run so
        # ``_insert_run`` skips the auto-create-kb-record step (the
        # foreign user has no User row, so the FK would reject it).
        # Using a fresh UUID here also models reality: even if a
        # foreign user did own a same-named KB, its record id would
        # be distinct from active_user's, so the indexed asset_id
        # lookup wouldn't match either way.
        foreign_run_id = await _insert_run(
            user_id=other_user_id,
            kb_name="only_mine",
            kb_id=uuid.uuid4(),
        )

        response = await client.get(
            "api/v1/knowledge_bases/only_mine/runs",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        ids = {r["id"] for r in payload["runs"]}
        assert str(mine) in ids
        # Must not leak the other user's run even though kb_name matches
        assert str(foreign_run_id) not in ids

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_exposes_source_name_from_source_config(
        self, mock_root, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "named_kb"
        kb_dir.mkdir(parents=True)

        await _insert_run(
            user_id=active_user.id,
            kb_name="named_kb",
            source_config={"source_name": "Test6"},
        )
        await _insert_run(
            user_id=active_user.id,
            kb_name="named_kb",
            source_config={},
        )
        await _insert_run(
            user_id=active_user.id,
            kb_name="named_kb",
            source_config={"source_name": "   "},
        )

        response = await client.get(
            "api/v1/knowledge_bases/named_kb/runs",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        names = [r["source_name"] for r in response.json()["runs"]]
        # Order is newest-first: whitespace, missing, then "Test6".
        assert "Test6" in names
        # Whitespace-only collapses to ``None``.
        assert names.count(None) == 2

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_pagination(self, mock_root, client: AsyncClient, logged_in_headers, active_user, tmp_path):
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "paginated_kb"
        kb_dir.mkdir(parents=True)

        for _ in range(3):
            await _insert_run(user_id=active_user.id, kb_name="paginated_kb")

        response = await client.get(
            "api/v1/knowledge_bases/paginated_kb/runs?page=1&limit=2",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["limit"] == 2
        assert payload["page"] == 1
        assert len(payload["runs"]) <= 2
        assert payload["total"] >= 3


class TestGetIngestionRun:
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_returns_full_detail_with_items(
        self, mock_root, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "detail_kb"
        kb_dir.mkdir(parents=True)

        items = [
            {
                "item_id": "0:ok.txt",
                "display_name": "ok.txt",
                "status": "succeeded",
                "chunks_created": 4,
                "error_message": None,
            },
            {
                "item_id": "1:bad.txt",
                "display_name": "bad.txt",
                "status": "failed",
                "chunks_created": 0,
                "error_message": "parse failure",
            },
        ]
        run_id = await _insert_run(
            user_id=active_user.id,
            kb_name="detail_kb",
            items=items,
            succeeded=1,
            failed=1,
        )

        response = await client.get(
            f"api/v1/knowledge_bases/detail_kb/runs/{run_id}",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == str(run_id)
        assert payload["succeeded"] == 1
        assert payload["failed"] == 1
        assert len(payload["items"]) == 2
        failed_item = next(i for i in payload["items"] if i["status"] == "failed")
        assert failed_item["error_message"] == "parse failure"

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_other_users_run_returns_404(
        self, mock_root, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "secret_kb"
        kb_dir.mkdir(parents=True)

        other_user_id = uuid.uuid4()
        # Foreign user has no User row, so skip kb_record auto-create
        # by passing an explicit kb_id (see notes in
        # ``test_excludes_other_users_runs``).
        foreign_run_id = await _insert_run(
            user_id=other_user_id,
            kb_name="secret_kb",
            kb_id=uuid.uuid4(),
        )

        response = await client.get(
            f"api/v1/knowledge_bases/secret_kb/runs/{foreign_run_id}",
            headers=logged_in_headers,
        )
        # Must be indistinguishable from "never existed" so the ID space
        # isn't a covert enumeration channel.
        assert response.status_code == 404

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_run_from_different_kb_returns_404(
        self, mock_root, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        mock_root.return_value = tmp_path
        (tmp_path / active_user.username / "kb_a").mkdir(parents=True)
        (tmp_path / active_user.username / "kb_b").mkdir(parents=True)

        run_id = await _insert_run(user_id=active_user.id, kb_name="kb_a")

        response = await client.get(
            f"api/v1/knowledge_bases/kb_b/runs/{run_id}",
            headers=logged_in_headers,
        )
        # Correct owner, wrong KB → still 404. Prevents a user from
        # querying their own run history under someone else's kb_name.
        assert response.status_code == 404


class TestChunksFilters:
    """Sanity-check the metadata filters on the chunks endpoint.

    The endpoint now streams chunks through the backend abstraction
    (``backend.iter_documents``) and filters in Python so the behavior
    is identical across Chroma / Mongo / Astra / Postgres. These tests
    feed synthetic batches through a mocked backend and assert the
    correct chunks surface for each filter.
    """

    @staticmethod
    def _fake_backend(entries):
        """Build a mock backend whose ``iter_documents`` yields ``entries``.

        ``entries`` is a list of ``(content, metadata)`` tuples. Each
        entry is wrapped in an ``IngestedDocument`` and yielded as one
        batch so the endpoint's in-Python filter has data to pass through.
        """
        from unittest.mock import AsyncMock, MagicMock

        from lfx.base.knowledge_bases.backends.base import IngestedDocument

        async def _iter_documents(*, batch_size: int = 1000, include_embeddings: bool = False):  # noqa: ARG001
            yield [IngestedDocument(content=c, metadata=m) for c, m in entries]

        backend = MagicMock()
        backend.iter_documents = _iter_documents
        backend.teardown = AsyncMock()
        return backend

    @pytest.mark.parametrize(
        ("query", "expected_source_types"),
        [
            ("?source_type=folder", {"folder"}),
            ("?file_name=a.pdf", {"file_upload"}),
            ("?job_id=deadbeef", {"file_upload"}),
        ],
    )
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.release_chroma_resources")
    @patch("langflow.api.v1.knowledge_bases.create_backend")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_single_metadata_filter_narrows_results(
        self,
        mock_root,
        mock_create_backend,
        mock_release,  # noqa: ARG002
        query,
        expected_source_types,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "filter_kb"
        kb_dir.mkdir(parents=True)
        # A dummy chroma.sqlite3 so the "has_data" guard passes.
        (kb_dir / "chroma.sqlite3").write_bytes(b"")

        mock_create_backend.return_value = self._fake_backend(
            [
                ("hello", {"source_type": "folder", "file_name": "b.md", "job_id": "cafe"}),
                ("world", {"source_type": "file_upload", "file_name": "a.pdf", "job_id": "deadbeef"}),
            ]
        )

        response = await client.get(
            f"api/v1/knowledge_bases/filter_kb/chunks{query}",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert {chunk["metadata"]["source_type"] for chunk in body["chunks"]} == expected_source_types

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.release_chroma_resources")
    @patch("langflow.api.v1.knowledge_bases.create_backend")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_multiple_filters_combine_with_and(
        self,
        mock_root,
        mock_create_backend,
        mock_release,  # noqa: ARG002
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "filter_multi"
        kb_dir.mkdir(parents=True)
        (kb_dir / "chroma.sqlite3").write_bytes(b"")

        mock_create_backend.return_value = self._fake_backend(
            [
                ("match", {"source_type": "folder", "file_name": "a.pdf"}),
                ("wrong-source", {"source_type": "file_upload", "file_name": "a.pdf"}),
                ("wrong-file", {"source_type": "folder", "file_name": "b.md"}),
            ]
        )

        response = await client.get(
            "api/v1/knowledge_bases/filter_multi/chunks?source_type=folder&file_name=a.pdf",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        body = response.json()
        # Only the row matching BOTH filters should survive.
        assert [chunk["content"] for chunk in body["chunks"]] == ["match"]
