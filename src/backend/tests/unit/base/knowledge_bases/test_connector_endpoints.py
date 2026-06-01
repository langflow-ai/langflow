"""Integration tests for the connector endpoints in their trimmed-down state.

The catalog (``GET /knowledge_bases/connectors``) and dispatcher
(``POST /{kb_name}/ingest/connector``) endpoints are kept as
framework infrastructure even though only ``file_upload`` and
``folder`` are registered in this phase. The cloud-connector
sources (S3 / Google Drive / OneDrive / SharePoint) are stubbed
out at the registry layer; the catalog must hide them and the
dispatcher must reject them as 400 typos rather than 500s.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


_STUBBED_SOURCE_TYPES = ("s3", "google_drive", "onedrive", "sharepoint")


class TestConnectorCatalog:
    async def test_returns_only_registered_connectors(self, client: AsyncClient, logged_in_headers):
        response = await client.get("api/v1/knowledge_bases/connectors", headers=logged_in_headers)
        assert response.status_code == 200
        entries = response.json()
        types = {entry["source_type"] for entry in entries}

        # ``folder`` is registered and surfaces in the catalog.
        # ``file_upload`` is registered but intentionally hidden — it
        # has its own dedicated endpoint.
        assert "folder" in types
        assert "file_upload" not in types

        # Stubbed cloud connectors must NOT appear in the catalog so
        # the UI picker doesn't surface a non-functional choice.
        for stubbed in _STUBBED_SOURCE_TYPES:
            assert stubbed not in types, (
                f"{stubbed!r} is stubbed in this phase and must be hidden from the connector catalog"
            )


class TestConnectorIngest:
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
        (kb_dir / "embedding_metadata.json").write_text(
            json.dumps(
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "embedding_provider": "OpenAI",
                    "embedding_model": "x",
                }
            )
        )
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

    @pytest.mark.parametrize("source_type", _STUBBED_SOURCE_TYPES)
    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_stubbed_source_type_returns_400(
        self,
        mock_root,
        mock_meta,
        source_type,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        """Stubbed cloud connectors are unregistered.

        treats them as user-typo 400s — not 500s. Keeps the contract
        identical to a typo'd source type from the user's perspective.
        """
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / f"connector_kb_{source_type}"
        kb_dir.mkdir(parents=True)
        (kb_dir / "embedding_metadata.json").write_text(
            json.dumps(
                {
                    "id": "00000000-0000-0000-0000-000000000003",
                    "embedding_provider": "OpenAI",
                    "embedding_model": "x",
                }
            )
        )
        mock_meta.return_value = {
            "id": "00000000-0000-0000-0000-000000000003",
            "embedding_provider": "OpenAI",
            "embedding_model": "x",
        }

        response = await client.post(
            f"api/v1/knowledge_bases/connector_kb_{source_type}/ingest/connector",
            headers=logged_in_headers,
            json={"source_type": source_type, "source_config": {}},
        )
        assert response.status_code == 400

    async def test_rejects_unbounded_chunk_parameters(self, client: AsyncClient, logged_in_headers):
        response = await client.post(
            "api/v1/knowledge_bases/connector_kb/ingest/connector",
            headers=logged_in_headers,
            json={
                "source_type": "folder",
                "source_config": {"path": "/example"},
                "chunk_size": 100_000_000,
                "chunk_overlap": 0,
            },
        )

        assert response.status_code == 422
        assert "chunk_size" in response.text


class TestFolderIngest:
    @patch("langflow.api.v1.knowledge_bases.get_task_service")
    @patch("langflow.api.v1.knowledge_bases.get_job_service")
    @patch("langflow.api.v1.knowledge_bases.get_settings_service")
    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_dispatches_folder_source_with_settings_allow_list(
        self,
        mock_root,
        mock_meta,
        mock_settings_service,
        mock_job_service,
        mock_task_service,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        allowed_root = tmp_path / "allowed"
        folder = allowed_root / "docs"
        folder.mkdir(parents=True)
        (folder / "readme.md").write_text("hello")

        mock_settings_service.return_value = SimpleNamespace(
            settings=SimpleNamespace(kb_allowed_folder_roots=[str(allowed_root)])
        )
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "folder_kb"
        kb_dir.mkdir(parents=True)
        mock_meta.return_value = {
            "id": "00000000-0000-0000-0000-000000000004",
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
            "api/v1/knowledge_bases/folder_kb/ingest/folder",
            headers=logged_in_headers,
            json={"path": str(folder), "chunk_size": 500, "chunk_overlap": 100},
        )

        assert response.status_code == 200
        fire_call = ts.fire_and_forget_task.await_args
        assert fire_call is not None
        passed_source = fire_call.kwargs["source"]
        assert passed_source.source_type.value == "folder"
        assert passed_source.source_config["path"] == str(folder)
        assert passed_source.source_config["allowed_roots"] == [str(allowed_root)]

    @patch("langflow.api.v1.knowledge_bases.get_job_service")
    @patch("langflow.api.v1.knowledge_bases.get_settings_service")
    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_rejects_folder_outside_settings_allow_list_before_job(
        self,
        mock_root,
        mock_meta,
        mock_settings_service,
        mock_job_service,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        allowed_root = tmp_path / "allowed"
        allowed_root.mkdir()
        outside_folder = tmp_path / "outside"
        outside_folder.mkdir()

        mock_settings_service.return_value = SimpleNamespace(
            settings=SimpleNamespace(kb_allowed_folder_roots=[str(allowed_root)])
        )
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "folder_kb"
        kb_dir.mkdir(parents=True)
        mock_meta.return_value = {
            "id": "00000000-0000-0000-0000-000000000005",
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-3-small",
        }

        response = await client.post(
            "api/v1/knowledge_bases/folder_kb/ingest/folder",
            headers=logged_in_headers,
            json={"path": str(outside_folder)},
        )

        assert response.status_code == 400
        assert "outside the configured allow-list" in response.json()["detail"]
        mock_job_service.assert_not_called()

    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_folder_ingest_with_real_settings_returns_400_not_500(
        self,
        mock_root,
        mock_meta,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
        monkeypatch,
    ):
        """Regression: the route must read a *declared* Settings field.

        The other folder-ingest tests inject ``SimpleNamespace(kb_allowed_folder_roots=...)``
        so they never touch the real ``Settings`` model. In 1.10.0 the field was not
        declared, so the route raised ``AttributeError`` → HTTP 500 on every call. This
        test deliberately does NOT mock ``get_settings_service``: with the field present
        and defaulting to an empty allow-list, the route reaches
        ``FolderSource.validate_config()`` and returns an actionable 400 — exactly like
        the sibling ``/ingest/connector`` route — instead of a 500.
        """
        # The regression depends on an *empty* allow-list (the default). Clear any
        # ``LANGFLOW_KB_ALLOWED_FOLDER_ROOTS`` a developer may have exported so the
        # test deterministically hits the empty-allow-list gate rather than the
        # "outside the configured allow-list" branch.
        monkeypatch.delenv("LANGFLOW_KB_ALLOWED_FOLDER_ROOTS", raising=False)

        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "folder_kb_real_settings"
        kb_dir.mkdir(parents=True)
        mock_meta.return_value = {
            "id": "00000000-0000-0000-0000-000000000006",
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-3-small",
        }

        # ``tmp_path`` exists and is a directory, so validation advances past the
        # path checks to the allow-list gate (empty by default → actionable 400).
        response = await client.post(
            "api/v1/knowledge_bases/folder_kb_real_settings/ingest/folder",
            headers=logged_in_headers,
            json={"path": str(tmp_path)},
        )

        assert response.status_code == 400, response.text
        # Assert the *specific* empty-allow-list message so the test pins the
        # regression path (real Settings → empty default → actionable 400) rather
        # than the generic substring shared with the "outside the allow-list" branch.
        assert "Configure LANGFLOW_KB_ALLOWED_FOLDER_ROOTS" in response.json()["detail"]

    async def test_folder_ingest_rejects_unbounded_chunk_parameters(self, client: AsyncClient, logged_in_headers):
        response = await client.post(
            "api/v1/knowledge_bases/folder_kb/ingest/folder",
            headers=logged_in_headers,
            json={
                "path": "/example-folder",
                "chunk_size": 100_000_000,
                "chunk_overlap": 0,
            },
        )

        assert response.status_code == 422
        assert "chunk_size" in response.text

    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_folder_ingest_blocked_for_memory_base_kb(
        self,
        mock_root,
        mock_meta,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        # Memory-Base-managed KBs must not be mutable through the
        # generic folder-ingest endpoint — they are owned by the
        # Memory Base APIs.
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "mb_kb"
        kb_dir.mkdir(parents=True)
        mock_meta.return_value = {
            "id": "00000000-0000-0000-0000-0000000000aa",
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-3-small",
            "source_types": ["memory"],
        }

        response = await client.post(
            "api/v1/knowledge_bases/mb_kb/ingest/folder",
            headers=logged_in_headers,
            json={"path": str(tmp_path), "chunk_size": 500, "chunk_overlap": 100},
        )

        assert response.status_code == 403
        assert "managed by a Memory Base" in response.json()["detail"]

    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_connector_ingest_blocked_for_memory_base_kb(
        self,
        mock_root,
        mock_meta,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        # Same guard for the generic connector dispatcher.
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / active_user.username / "mb_connector_kb"
        kb_dir.mkdir(parents=True)
        mock_meta.return_value = {
            "id": "00000000-0000-0000-0000-0000000000bb",
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-3-small",
            "source_types": ["memory"],
        }

        response = await client.post(
            "api/v1/knowledge_bases/mb_connector_kb/ingest/connector",
            headers=logged_in_headers,
            json={"source_type": "folder", "source_config": {"path": str(tmp_path)}},
        )

        assert response.status_code == 403
        assert "managed by a Memory Base" in response.json()["detail"]
