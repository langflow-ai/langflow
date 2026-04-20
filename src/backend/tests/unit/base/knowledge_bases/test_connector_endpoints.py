"""Integration tests for the Phase 3A connector endpoints.

Covers ``GET /knowledge_bases/connectors`` (catalog) and the generic
``POST /{kb_name}/ingest/connector`` dispatcher. Ingestion is mocked
at the task-service boundary — the underlying source wiring is
exercised separately in ``test_s3_source.py``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestConnectorCatalog:
    async def test_lists_registered_connectors(self, client: AsyncClient, logged_in_headers):
        response = await client.get("api/v1/knowledge_bases/connectors", headers=logged_in_headers)
        assert response.status_code == 200
        entries = response.json()
        types = {entry["source_type"] for entry in entries}
        # s3 + folder registered; file_upload intentionally excluded
        # (has its own dedicated endpoint).
        assert "s3" in types
        assert "folder" in types
        assert "file_upload" not in types

    async def test_connector_entries_carry_metadata(self, client: AsyncClient, logged_in_headers):
        response = await client.get("api/v1/knowledge_bases/connectors", headers=logged_in_headers)
        entries = response.json()
        s3_entry = next(e for e in entries if e["source_type"] == "s3")
        assert s3_entry["display_name"] == "AWS S3"
        assert s3_entry["requires_credentials"] is True
        assert s3_entry["icon"] == "cloud"


class TestConnectorIngest:
    @patch("langflow.api.v1.knowledge_bases.get_task_service")
    @patch("langflow.api.v1.knowledge_bases.get_job_service")
    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_dispatches_s3_via_registry(
        self,
        mock_root,
        mock_meta,
        mock_job_service,
        mock_task_service,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_TEST")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret_value")

        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "connector_kb"
        kb_dir.mkdir(parents=True)
        (kb_dir / "embedding_metadata.json").write_text(
            json.dumps(
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "embedding_provider": "OpenAI",
                    "embedding_model": "text-embedding-3-small",
                }
            )
        )
        mock_meta.return_value = {
            "id": "00000000-0000-0000-0000-000000000001",
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-3-small",
        }

        js = AsyncMock()
        js.create_job = AsyncMock()
        js.execute_with_status = AsyncMock()
        mock_job_service.return_value = js
        ts = AsyncMock()
        ts.fire_and_forget_task = AsyncMock()
        mock_task_service.return_value = ts

        response = await client.post(
            "api/v1/knowledge_bases/connector_kb/ingest/connector",
            headers=logged_in_headers,
            json={
                "source_type": "s3",
                "source_config": {"bucket": "demo"},
                "chunk_size": 500,
                "chunk_overlap": 100,
                "separator": "",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert "id" in payload
        assert payload["href"].startswith("/task/")

        # Source was constructed + handed to the fire_and_forget call
        # under the same ``source=`` kwarg the folder endpoint uses.
        fire_call = ts.fire_and_forget_task.await_args
        assert fire_call is not None
        passed_source = fire_call.kwargs["source"]
        assert passed_source.source_type.value == "s3"
        assert passed_source.source_config["bucket"] == "demo"

    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_unknown_source_type_returns_400(
        self,
        mock_root,
        mock_meta,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "connector_kb_bad"
        kb_dir.mkdir(parents=True)
        mock_meta.return_value = {
            "id": "00000000-0000-0000-0000-000000000002",
            "embedding_provider": "OpenAI",
            "embedding_model": "x",
        }

        response = await client.post(
            "api/v1/knowledge_bases/connector_kb_bad/ingest/connector",
            headers=logged_in_headers,
            json={"source_type": "nonsense", "source_config": {}},
        )
        assert response.status_code == 400
        assert "nonsense" in response.json()["detail"].lower()

    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bad_source_config_returns_400(
        self,
        mock_root,
        mock_meta,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "connector_kb_bad2"
        kb_dir.mkdir(parents=True)
        mock_meta.return_value = {
            "id": "00000000-0000-0000-0000-000000000003",
            "embedding_provider": "OpenAI",
            "embedding_model": "x",
        }

        # Missing bucket → S3Source.validate_config raises ValueError →
        # endpoint maps to 400 before a job is spawned.
        response = await client.post(
            "api/v1/knowledge_bases/connector_kb_bad2/ingest/connector",
            headers=logged_in_headers,
            json={"source_type": "s3", "source_config": {}},
        )
        assert response.status_code == 400
        assert "bucket" in response.json()["detail"].lower()
