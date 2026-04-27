"""Integration tests for the connector endpoints in their current,
trimmed-down state.

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
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


_STUBBED_SOURCE_TYPES = ("s3", "google_drive", "onedrive", "sharepoint")


class TestConnectorCatalog:
    async def test_returns_only_registered_connectors(
        self, client: AsyncClient, logged_in_headers
    ):
        response = await client.get(
            "api/v1/knowledge_bases/connectors", headers=logged_in_headers
        )
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
                f"{stubbed!r} is stubbed in this phase and must be hidden from "
                "the connector catalog"
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
        """Stubbed cloud connectors are unregistered, so the dispatcher
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

    async def test_rejects_unbounded_chunk_parameters(
        self, client: AsyncClient, logged_in_headers
    ):
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

    async def test_folder_ingest_rejects_unbounded_chunk_parameters(
        self, client: AsyncClient, logged_in_headers
    ):
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
