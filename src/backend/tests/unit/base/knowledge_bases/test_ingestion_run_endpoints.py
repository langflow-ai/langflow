"""Integration tests for the Phase 2 ingestion-run visibility endpoints.

These drive ``GET /{kb}/runs`` and ``GET /{kb}/runs/{run_id}``
end-to-end against the real FastAPI app and test DB so we catch
routing, auth scoping, pagination, and SQL-level behavior in one
test pass.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from langflow.services.database.models.ingestion_run import IngestionRun, IngestionRunStatus
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from httpx import AsyncClient


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
) -> uuid.UUID:
    run_id = uuid.uuid4()
    async with session_scope() as session:
        row = IngestionRun(
            id=run_id,
            job_id=uuid.uuid4(),
            kb_name=kb_name,
            kb_id=kb_id,
            user_id=user_id,
            source_type=source_type,
            source_config={"source_name": "demo"},
            status=status.value,
            total_items=succeeded + failed,
            succeeded=succeeded,
            failed=failed,
            skipped=0,
            total_bytes=1024,
            chunks_created=succeeded * 3,
            items=items
            or [
                {
                    "item_id": "0:a.txt",
                    "display_name": "a.txt",
                    "status": "succeeded",
                    "chunks_created": 3,
                    "error_message": None,
                }
            ],
        )
        session.add(row)
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
        await _insert_run(user_id=other_user_id, kb_name="only_mine")

        response = await client.get(
            "api/v1/knowledge_bases/only_mine/runs",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        ids = {r["id"] for r in payload["runs"]}
        assert str(mine) in ids
        # Must not leak the other user's run even though kb_name matches
        assert all(r["id"] != str(other_user_id) for r in payload["runs"])

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
        foreign_run_id = await _insert_run(user_id=other_user_id, kb_name="secret_kb")

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
    """Sanity-check the new metadata filters on the chunks endpoint.

    The happy paths are covered by the existing chunks tests; these
    only guard the query-parameter-to-Chroma-filter translation.
    """

    @pytest.mark.parametrize(
        ("query", "expected_filter"),
        [
            ("?source_type=folder", {"source_type": "folder"}),
            ("?file_name=a.pdf", {"file_name": "a.pdf"}),
            ("?job_id=deadbeef", {"job_id": "deadbeef"}),
        ],
    )
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.release_chroma_resources")
    @patch("langflow.api.v1.knowledge_bases.Chroma")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_single_metadata_filter_becomes_where_clause(
        self,
        mock_root,
        mock_fresh_client,
        mock_chroma,
        mock_release,  # noqa: ARG002
        query,
        expected_filter,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        from unittest.mock import MagicMock

        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "filter_kb"
        kb_dir.mkdir(parents=True)
        # A dummy chroma.sqlite3 so the "has_data" guard passes.
        (kb_dir / "chroma.sqlite3").write_bytes(b"")

        mock_fresh_client.return_value = MagicMock()
        collection = MagicMock()
        collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
        collection.count.return_value = 0
        chroma_inst = MagicMock()
        chroma_inst._collection = collection
        mock_chroma.return_value = chroma_inst

        response = await client.get(
            f"api/v1/knowledge_bases/filter_kb/chunks{query}",
            headers=logged_in_headers,
        )
        assert response.status_code == 200
        # Metadata-filtered path calls get() once with where=<filter>.
        get_calls = collection.get.call_args_list
        assert get_calls, "expected chroma.get to be called"
        assert get_calls[-1].kwargs.get("where") == expected_filter

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.release_chroma_resources")
    @patch("langflow.api.v1.knowledge_bases.Chroma")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_multiple_filters_combine_with_and(
        self,
        mock_root,
        mock_fresh_client,
        mock_chroma,
        mock_release,  # noqa: ARG002
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        from unittest.mock import MagicMock

        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "filter_multi"
        kb_dir.mkdir(parents=True)
        (kb_dir / "chroma.sqlite3").write_bytes(b"")

        mock_fresh_client.return_value = MagicMock()
        collection = MagicMock()
        collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
        collection.count.return_value = 0
        chroma_inst = MagicMock()
        chroma_inst._collection = collection
        mock_chroma.return_value = chroma_inst

        response = await client.get(
            "api/v1/knowledge_bases/filter_multi/chunks?source_type=folder&file_name=a.pdf",
            headers=logged_in_headers,
        )
        assert response.status_code == 200

        where = collection.get.call_args_list[-1].kwargs.get("where")
        assert where == {
            "$and": [
                {"source_type": "folder"},
                {"file_name": "a.pdf"},
            ]
        }
