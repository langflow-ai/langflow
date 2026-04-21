"""Tests for ``KnowledgeBaseComponent`` after the unified-models port.

Pre-port this file was ~938 lines and tested a hand-rolled per-
provider ``_build_embeddings`` + ``_resolve_api_key`` +
``_resolve_provider_variables`` surface. All three are gone now —
retrieval delegates credential resolution to
``lfx.base.models.unified_models.get_embeddings`` (same as ingestion)
and vector access to ``ChromaBackend``.

The rewritten suite covers the actual retrieval contract:

* ``_get_kb_metadata`` reading ``embedding_metadata.json``.
* ``_resolve_model_selection`` preferring ``model_selection`` over
  the legacy string fields, with a clear error when neither is
  present and the string doesn't map to a current catalog entry.
* ``retrieve_data`` orchestrating ``get_embeddings`` +
  ``ChromaBackend.similarity_search`` against the right KB path.
* User-scoping + required-field guards that make retrieval safe
  across sessions.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
from lfx.components.files_and_knowledge.retrieval import KnowledgeBaseComponent

from tests.base import ComponentTestBaseWithClient


class TestKnowledgeBaseComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return KnowledgeBaseComponent

    @pytest.fixture(autouse=True)
    def mock_knowledge_base_path(self, tmp_path):
        """Pin the KB root at a fresh tmp dir for every test."""
        with patch(
            "langflow.components.knowledge_bases.retrieval._KNOWLEDGE_BASES_ROOT_PATH",
            tmp_path,
        ):
            yield

    @pytest.fixture
    def default_kwargs(self, tmp_path, active_user):
        kb_name = "test_kb"
        kb_path = tmp_path / active_user.username / kb_name
        kb_path.mkdir(parents=True, exist_ok=True)

        metadata = {
            "embedding_provider": "HuggingFace",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "model_selection": {
                "name": "sentence-transformers/all-MiniLM-L6-v2",
                "provider": "HuggingFace",
                "metadata": {
                    "embedding_class": "HuggingFaceEmbeddings",
                    "param_mapping": {"model_name": "model"},
                },
            },
            "chunk_size": 1000,
            "created_at": "2026-04-01T00:00:00Z",
        }
        (kb_path / "embedding_metadata.json").write_text(json.dumps(metadata))

        return {
            "knowledge_base": kb_name,
            "kb_root_path": str(tmp_path),
            "search_query": "",
            "top_k": 5,
            "include_embeddings": False,
            "_user_id": active_user.id,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """New-style component: no legacy filenames."""
        return []

    # ---- update_build_config ----------------------------------------

    async def test_get_knowledge_bases_utility(self, tmp_path, active_user):
        (tmp_path / active_user.username / "kb1").mkdir(parents=True, exist_ok=True)
        (tmp_path / active_user.username / "kb2").mkdir(parents=True, exist_ok=True)
        (tmp_path / active_user.username / ".hidden").mkdir(parents=True, exist_ok=True)

        kb_list = await get_knowledge_bases(tmp_path, user_id=active_user.id)

        assert "test_kb" in kb_list
        assert "kb1" in kb_list
        assert "kb2" in kb_list
        assert ".hidden" not in kb_list

    async def test_update_build_config_populates_options(self, component_class, default_kwargs, tmp_path, active_user):
        component = component_class(**default_kwargs)

        (tmp_path / active_user.username / "kb1").mkdir(parents=True, exist_ok=True)
        (tmp_path / active_user.username / "kb2").mkdir(parents=True, exist_ok=True)

        build_config = {"knowledge_base": {"value": "test_kb", "options": []}}
        result = await component.update_build_config(build_config, None, "knowledge_base")

        assert "test_kb" in result["knowledge_base"]["options"]
        assert "kb1" in result["knowledge_base"]["options"]
        assert "kb2" in result["knowledge_base"]["options"]

    async def test_update_build_config_resets_stale_selection(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"knowledge_base": {"value": "nonexistent_kb", "options": ["test_kb"]}}
        result = await component.update_build_config(build_config, None, "knowledge_base")
        assert result["knowledge_base"]["value"] is None

    # ---- _get_kb_metadata --------------------------------------------

    def test_get_kb_metadata_happy_path(self, component_class, default_kwargs, active_user):
        component = component_class(**default_kwargs)
        kb_path = Path(default_kwargs["kb_root_path"]) / active_user.username / default_kwargs["knowledge_base"]
        metadata = component._get_kb_metadata(kb_path)
        assert metadata["embedding_provider"] == "HuggingFace"
        assert metadata["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        # New-format KBs carry the full selection dict so retrieval can
        # pass it straight to get_embeddings.
        assert "model_selection" in metadata

    def test_get_kb_metadata_missing_file_returns_empty(self, component_class, default_kwargs, tmp_path, active_user):
        component = component_class(**default_kwargs)
        ghost = tmp_path / active_user.username / "ghost"
        ghost.mkdir(parents=True, exist_ok=True)
        assert component._get_kb_metadata(ghost) == {}

    def test_get_kb_metadata_corrupt_json_returns_empty(self, component_class, default_kwargs, tmp_path, active_user):
        component = component_class(**default_kwargs)
        kb_path = tmp_path / active_user.username / "bad_kb"
        kb_path.mkdir(parents=True, exist_ok=True)
        (kb_path / "embedding_metadata.json").write_text("{not json")
        assert component._get_kb_metadata(kb_path) == {}

    # ---- _resolve_model_selection ------------------------------------

    def test_resolve_model_selection_uses_new_format(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = {"name": "m", "provider": "p", "metadata": {}}
        assert component._resolve_model_selection({"model_selection": model}) == [model]

    def test_resolve_model_selection_accepts_list_shape(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = [{"name": "m", "provider": "p"}]
        assert component._resolve_model_selection({"model_selection": model}) == model

    def test_resolve_model_selection_falls_back_to_catalog_lookup(self, component_class, default_kwargs):
        """Fall back to catalog lookup for legacy KBs.

        No ``model_selection`` field, just ``embedding_model`` and
        ``embedding_provider`` strings — retrieval has to look the
        model up in the current unified-models catalog.
        """
        component = component_class(**default_kwargs)
        catalog_entry = {
            "name": "text-embedding-3-small",
            "provider": "OpenAI",
            "metadata": {"embedding_class": "OpenAIEmbeddings"},
        }
        with patch(
            "lfx.components.files_and_knowledge.retrieval.get_embedding_model_options",
            return_value=[catalog_entry],
        ):
            resolved = component._resolve_model_selection(
                {"embedding_model": "text-embedding-3-small", "embedding_provider": "OpenAI"}
            )
        assert resolved == [catalog_entry]

    def test_resolve_model_selection_raises_when_legacy_model_unavailable(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with (
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_embedding_model_options",
                return_value=[],
            ),
            pytest.raises(ValueError, match="no longer available"),
        ):
            component._resolve_model_selection(
                {"embedding_model": "text-embedding-ada-002", "embedding_provider": "OpenAI"}
            )

    def test_resolve_model_selection_raises_on_empty_metadata(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="no embedding model recorded"):
            component._resolve_model_selection({})

    # ---- retrieve_data orchestration ---------------------------------

    async def test_retrieve_data_missing_metadata_raises(self, component_class, default_kwargs, tmp_path, active_user):
        kb_path = tmp_path / active_user.username / default_kwargs["knowledge_base"]
        metadata_file = kb_path / "embedding_metadata.json"
        if metadata_file.exists():
            metadata_file.unlink()

        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Metadata not found"):
            await component.retrieve_data()

    async def test_retrieve_data_missing_user_id_raises(self, component_class, default_kwargs):
        default_kwargs["_user_id"] = None
        component = component_class(**default_kwargs)
        mock_vertex = MagicMock()
        mock_vertex.graph.user_id = None
        component._vertex = mock_vertex

        with patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope:
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError, match="User ID is required"):
                await component.retrieve_data()

    async def test_retrieve_data_missing_user_record_raises(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with (
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_user_by_id",
                return_value=None,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError, match=r"User with ID .* not found"):
                await component.retrieve_data()

    async def test_retrieve_data_routes_query_with_scores(
        self,
        component_class,
        default_kwargs,
        tmp_path,  # noqa: ARG002 — reserved for future side-effect assertions
        active_user,
    ):
        """Score-carrying search path.

        With a search_query set, retrieve_data asks the backend for
        scores so the UI can render a relevance column.
        """
        default_kwargs["search_query"] = "find me"
        component = component_class(**default_kwargs)

        fake_doc = MagicMock()
        fake_doc.page_content = "hit"
        fake_doc.metadata = {"source": "s1"}

        user_record = MagicMock()
        user_record.username = active_user.username

        backend_instance = MagicMock()
        backend_instance.similarity_search = AsyncMock(return_value=[(fake_doc, 0.42)])
        backend_instance.teardown = AsyncMock()

        with (
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_user_by_id",
                return_value=user_record,
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_embeddings",
                return_value=MagicMock(),
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval.ChromaBackend",
                return_value=backend_instance,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await component.retrieve_data()

        # similarity_search was called with_scores=True because
        # search_query is truthy.
        call_kwargs = backend_instance.similarity_search.await_args.kwargs
        assert call_kwargs["with_scores"] is True
        assert call_kwargs["query"] == "find me"
        assert call_kwargs["k"] == default_kwargs["top_k"]
        backend_instance.teardown.assert_awaited_once()
        assert len(result) == 1

    async def test_retrieve_data_no_query_skips_scores(self, component_class, default_kwargs, active_user):
        """No-query path skips scores.

        With search_query empty, retrieve_data asks for a
        non-scored search so the sentinel zero isn't surfaced as a
        meaningful relevance value.
        """
        default_kwargs["search_query"] = ""
        component = component_class(**default_kwargs)

        fake_doc = MagicMock()
        fake_doc.page_content = "all"
        fake_doc.metadata = {"source": "any"}

        user_record = MagicMock()
        user_record.username = active_user.username

        backend_instance = MagicMock()
        backend_instance.similarity_search = AsyncMock(return_value=[(fake_doc, 0.0)])
        backend_instance.teardown = AsyncMock()

        with (
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_user_by_id",
                return_value=user_record,
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_embeddings",
                return_value=MagicMock(),
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval.ChromaBackend",
                return_value=backend_instance,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await component.retrieve_data()

        call_kwargs = backend_instance.similarity_search.await_args.kwargs
        assert call_kwargs["with_scores"] is False
        backend_instance.teardown.assert_awaited_once()
        assert len(result) == 1

    async def test_retrieve_data_tears_down_backend_on_error(self, component_class, default_kwargs, active_user):
        """Teardown on error.

        The backend's ``teardown`` must run even when
        ``similarity_search`` blows up — otherwise Chroma's SQLite
        handle leaks between tests.
        """
        component = component_class(**default_kwargs)

        user_record = MagicMock()
        user_record.username = active_user.username

        backend_instance = MagicMock()
        backend_instance.similarity_search = AsyncMock(side_effect=RuntimeError("boom"))
        backend_instance.teardown = AsyncMock()

        with (
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_user_by_id",
                return_value=user_record,
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_embeddings",
                return_value=MagicMock(),
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval.ChromaBackend",
                return_value=backend_instance,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(RuntimeError, match="boom"):
                await component.retrieve_data()

        backend_instance.teardown.assert_awaited_once()

    async def test_retrieve_data_passes_model_selection_to_unified_models(
        self, component_class, default_kwargs, active_user
    ):
        """Full ``model_selection`` is handed off unchanged.

        The dict persisted at ingest time should land in
        ``get_embeddings`` exactly as-is — that's the whole point of
        the unified-models port.
        """
        component = component_class(**default_kwargs)

        user_record = MagicMock()
        user_record.username = active_user.username

        backend_instance = MagicMock()
        backend_instance.similarity_search = AsyncMock(return_value=[])
        backend_instance.teardown = AsyncMock()

        with (
            patch("lfx.components.files_and_knowledge.retrieval.session_scope") as mock_session_scope,
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_user_by_id",
                return_value=user_record,
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch(
                "lfx.components.files_and_knowledge.retrieval.get_embeddings",
                return_value=MagicMock(),
            ) as mock_get_embeddings,
            patch(
                "lfx.components.files_and_knowledge.retrieval.ChromaBackend",
                return_value=backend_instance,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            await component.retrieve_data()

        # get_embeddings receives the full list-wrapped selection +
        # the chunk_size persisted alongside it.
        call_kwargs = mock_get_embeddings.call_args.kwargs
        assert isinstance(call_kwargs["model"], list)
        assert call_kwargs["model"][0]["name"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert call_kwargs["chunk_size"] == 1000
        assert call_kwargs["user_id"] == default_kwargs["_user_id"]
