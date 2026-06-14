"""Unit tests for MemoryBaseComponent.

Covers:
- Validation: missing session_id, missing flow_id, MB not attached to flow,
  unselected MB, missing owner, missing/invalid metadata, KB path traversal.
- Where-clause composition (session filter on / off / multi-predicate).
- update_build_config dropdown population.
- _coerce_uuid input coercion.
- _load_kb_metadata branches (missing file, invalid JSON, decrypt failure).
- retrieve_data behavior: similarity search w/ filter, empty query short-circuit,
  filter_by_session=False end-to-end, include_metadata=False output shape.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from lfx.components.files_and_knowledge import _kb_paths
from lfx.components.files_and_knowledge.memory_retrieval import (
    MemoryBaseComponent,
    _coerce_uuid,
    _distance_to_similarity,
    _to_python_scalar,
)


def _make_component(
    *,
    flow_id: uuid.UUID | None,
    session_id: str | None,
    invoker_user_id: uuid.UUID | None = None,
    selected: str | None = "mb-one",
    filter_by_session: bool = True,
    search_query: str = "hello",
    include_metadata: bool = True,
) -> MemoryBaseComponent:
    invoker_user_id = invoker_user_id or uuid.uuid4()
    component = MemoryBaseComponent()
    component._vertex = MagicMock()
    component._vertex.graph = SimpleNamespace(
        flow_id=str(flow_id) if flow_id else None,
        session_id=session_id,
        user_id=str(invoker_user_id),
        flow_name="test-flow",
        context={},
    )
    component._user_id = str(invoker_user_id)
    component.memory_base = selected
    component.search_query = search_query
    component.top_k = 5
    component.include_metadata = include_metadata
    component.filter_by_session = filter_by_session
    return component


class _Scope:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *_):
        return False


def _patched_session_scope(db) -> object:
    return patch(
        "lfx.components.files_and_knowledge.memory_retrieval.session_scope",
        return_value=_Scope(db),
    )


def _make_mb_row(*, name: str = "mb-one", flow_id: uuid.UUID, owner_id: uuid.UUID, kb_name: str = "mb_one_kb"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        flow_id=flow_id,
        user_id=owner_id,
        kb_name=kb_name,
    )


def _exec_returning(value):
    """Build a mock matching ``(await db.exec(...)).first()`` / ``.all()`` usage."""
    db = MagicMock()
    exec_result = MagicMock()
    exec_result.first.return_value = value
    exec_result.all.return_value = value if isinstance(value, list) else [value] if value else []
    db.exec = AsyncMock(return_value=exec_result)
    return db


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestCoerceUuid:
    def test_uuid_passthrough(self):
        u = uuid.uuid4()
        assert _coerce_uuid(u) is u

    def test_string_coerced(self):
        u = uuid.uuid4()
        assert _coerce_uuid(str(u)) == u

    def test_none_returns_none(self):
        assert _coerce_uuid(None) is None

    def test_invalid_returns_none(self):
        assert _coerce_uuid("not-a-uuid") is None

    def test_unhashable_returns_none(self):
        # Falls through TypeError branch.
        assert _coerce_uuid(object()) is None


class TestDistanceToSimilarity:
    def test_flips_sign(self):
        assert _distance_to_similarity(0.42) == -0.42
        assert _distance_to_similarity(-0.1) == 0.1


class TestToPythonScalar:
    """Numpy scalars must be coerced or the Agent tool path fails serialization."""

    def test_numpy_int64_becomes_python_int(self):
        result = _to_python_scalar(np.int64(42))
        assert result == 42
        assert type(result) is int

    def test_numpy_float64_becomes_python_float(self):
        result = _to_python_scalar(np.float64(1.5))
        assert result == 1.5
        assert type(result) is float

    def test_numpy_bool_becomes_python_bool(self):
        result = _to_python_scalar(np.bool_(True))  # noqa: FBT003
        assert result is True
        assert type(result) is bool

    def test_python_scalar_passes_through(self):
        assert _to_python_scalar("hello") == "hello"
        assert _to_python_scalar(7) == 7
        assert _to_python_scalar(None) is None

    def test_arbitrary_object_passes_through(self):
        sentinel = object()
        assert _to_python_scalar(sentinel) is sentinel


class TestToolSurface:
    """Pin the tool-description surface seen by LLM agents.

    The component description and output info are surfaced to LLM agents as the
    tool description; they must mention the cross-session capability so the agent
    knows to call the tool from a fresh session when 'Filter by Session' is off.

    Regression guard for: agents ignoring this tool because the description said
    'session-scoped' only, defeating ``filter_by_session=False``.
    """

    def test_description_mentions_cross_session(self):
        assert "session" in MemoryBaseComponent.description.lower()
        assert "across" in MemoryBaseComponent.description.lower()

    def test_filter_by_session_input_info_documents_off_state(self):
        bool_input = next(i for i in MemoryBaseComponent.inputs if i.name == "filter_by_session")
        assert "disable" in bool_input.info.lower()

    def test_output_info_advertises_cross_session(self):
        output = next(o for o in MemoryBaseComponent.outputs if o.name == "retrieve_data")
        assert "across" in (output.info or "").lower()


class TestBuildWhereClause:
    def test_session_filter_on_returns_session_predicate(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1", filter_by_session=True)
        assert component._build_where_clause(session_id="s1") == {"session_id": {"$eq": "s1"}}

    def test_session_filter_off_returns_none(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1", filter_by_session=False)
        assert component._build_where_clause(session_id="s1") is None

    def test_no_session_id_returns_none(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id=None, filter_by_session=True)
        assert component._build_where_clause(session_id=None) is None

    def test_session_filter_truthy_string_does_not_disable_toggle(self):
        # Regression: a previous version used the raw attribute as a bool, so
        # an externally-set "false" string would be truthy and silently allow
        # cross-session retrieval. Confirm bool() coerces properly.
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1", filter_by_session=True)
        component.filter_by_session = "false"  # non-bool value
        assert component._build_where_clause(session_id="s1") == {"session_id": {"$eq": "s1"}}

    def test_session_filter_falsy_value_disables_toggle(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1", filter_by_session=False)
        component.filter_by_session = ""  # falsy non-bool
        assert component._build_where_clause(session_id="s1") is None


# ---------------------------------------------------------------------------
# load_kb_metadata branches (shared helper)
# ---------------------------------------------------------------------------


class TestLoadKbMetadata:
    def test_missing_file_returns_empty(self, tmp_path: Path):
        assert _kb_paths.load_kb_metadata(tmp_path, log_label="x") == {}

    def test_invalid_json_returns_empty(self, tmp_path: Path):
        (tmp_path / "embedding_metadata.json").write_text("{not-json")
        assert _kb_paths.load_kb_metadata(tmp_path, log_label="x") == {}

    def test_no_api_key_skips_decrypt(self, tmp_path: Path):
        payload = {"embedding_provider": "OpenAI", "embedding_model": "x"}
        (tmp_path / "embedding_metadata.json").write_text(json.dumps(payload))
        with patch("lfx.components.files_and_knowledge._kb_paths.decrypt_api_key") as decrypt:
            result = _kb_paths.load_kb_metadata(tmp_path, log_label="x")
            decrypt.assert_not_called()
        assert result == payload

    def test_decrypt_success(self, tmp_path: Path):
        payload = {"embedding_provider": "OpenAI", "api_key": "ENCRYPTED"}  # pragma: allowlist secret
        (tmp_path / "embedding_metadata.json").write_text(json.dumps(payload))
        with patch(
            "lfx.components.files_and_knowledge._kb_paths.decrypt_api_key",
            return_value="plain",
        ):
            result = _kb_paths.load_kb_metadata(tmp_path, log_label="x")
        assert result["api_key"] == "plain"  # pragma: allowlist secret

    def test_decrypt_failure_sets_none(self, tmp_path: Path):
        payload = {"embedding_provider": "OpenAI", "api_key": "ENCRYPTED"}  # pragma: allowlist secret
        (tmp_path / "embedding_metadata.json").write_text(json.dumps(payload))
        with patch(
            "lfx.components.files_and_knowledge._kb_paths.decrypt_api_key",
            side_effect=ValueError("bad token"),
        ):
            result = _kb_paths.load_kb_metadata(tmp_path, log_label="x")
        assert result["api_key"] is None


class TestRootPathCache:
    def test_reset_cache_picks_up_new_setting(self, tmp_path: Path):
        _kb_paths.reset_knowledge_bases_root_path_cache()
        first = tmp_path / "first"
        second = tmp_path / "second"
        with patch("lfx.components.files_and_knowledge._kb_paths.get_settings_service") as gs:
            gs.return_value.settings.knowledge_bases_dir = str(first)
            assert _kb_paths.get_knowledge_bases_root_path() == first
            # Cached value is returned even if settings change.
            gs.return_value.settings.knowledge_bases_dir = str(second)
            assert _kb_paths.get_knowledge_bases_root_path() == first
            _kb_paths.reset_knowledge_bases_root_path_cache()
            assert _kb_paths.get_knowledge_bases_root_path() == second
        _kb_paths.reset_knowledge_bases_root_path_cache()

    def test_unset_directory_raises(self):
        _kb_paths.reset_knowledge_bases_root_path_cache()
        with patch("lfx.components.files_and_knowledge._kb_paths.get_settings_service") as gs:
            gs.return_value.settings.knowledge_bases_dir = ""
            with pytest.raises(ValueError, match="Knowledge bases directory"):
                _kb_paths.get_knowledge_bases_root_path()
        _kb_paths.reset_knowledge_bases_root_path_cache()


# ---------------------------------------------------------------------------
# update_build_config
# ---------------------------------------------------------------------------


class TestUpdateBuildConfig:
    async def test_other_field_returns_unchanged(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1")
        cfg = {"memory_base": {"options": ["existing"], "value": "existing"}}
        result = await component.update_build_config(cfg, None, field_name="other")
        assert result is cfg
        assert cfg["memory_base"]["options"] == ["existing"]

    async def test_missing_flow_id_clears_options(self):
        component = _make_component(flow_id=None, session_id="s1")
        component._get_runtime_or_frontend_node_attr = MagicMock(return_value=None)
        cfg = {"memory_base": {"options": ["mb-stale"], "value": "mb-stale"}}
        result = await component.update_build_config(cfg, None, field_name="memory_base")
        assert result["memory_base"]["options"] == []
        assert result["memory_base"]["value"] is None

    async def test_options_populated_and_stale_value_cleared(self):
        flow_id = uuid.uuid4()
        invoker = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1", invoker_user_id=invoker)
        component._get_runtime_or_frontend_node_attr = MagicMock(return_value=str(flow_id))

        rows = [
            SimpleNamespace(name="mb-b"),
            SimpleNamespace(name="mb-a"),
        ]
        db = _exec_returning(rows)

        cfg = {"memory_base": {"options": [], "value": "mb-not-here"}}
        with _patched_session_scope(db):
            result = await component.update_build_config(cfg, None, field_name="memory_base")
        assert result["memory_base"]["options"] == ["mb-a", "mb-b"]
        assert result["memory_base"]["value"] is None


# ---------------------------------------------------------------------------
# retrieve_data — invariants and full path
# ---------------------------------------------------------------------------


class TestMemoryBaseRetrievalInvariants:
    async def test_missing_session_id_raises_when_filter_enabled(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id=None, filter_by_session=True)
        with pytest.raises(ValueError, match="session_id is required"):
            await component.retrieve_memory()

    async def test_missing_session_id_allowed_when_filter_disabled(self):
        """Cross-session retrieval should not require a session_id on the graph."""
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(
            flow_id=flow_id,
            session_id=None,
            filter_by_session=False,
        )
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")

        fake_chroma = MagicMock()
        fake_chroma.similarity_search_with_score.return_value = []

        with contextlib.ExitStack() as stack:
            TestMemoryBaseRetrievalBehavior._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_chroma=fake_chroma,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            result = await component.retrieve_memory()

        assert len(result) == 0
        kwargs = fake_chroma.similarity_search_with_score.call_args.kwargs
        assert kwargs["filter"] is None

    async def test_missing_flow_id_raises(self):
        component = _make_component(flow_id=None, session_id="s1")
        with pytest.raises(ValueError, match="flow_id"):
            await component.retrieve_memory()

    async def test_no_memory_base_selected_raises(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1", selected=None)
        with pytest.raises(ValueError, match="No Memory Base"):
            await component.retrieve_memory()

    async def test_mb_not_attached_to_flow_raises(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1")
        db = _exec_returning(None)
        with _patched_session_scope(db), pytest.raises(ValueError, match="not attached to this flow"):
            await component.retrieve_memory()

    async def test_owner_not_found_raises(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1")
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        db = _exec_returning(mb_row)
        with (
            _patched_session_scope(db),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.get_user_by_id",
                new=AsyncMock(return_value=None),
            ),
            pytest.raises(ValueError, match="owner account"),
        ):
            await component.retrieve_memory()

    async def test_missing_metadata_raises(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1")
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")
        db = _exec_returning(mb_row)
        with (
            _patched_session_scope(db),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.get_user_by_id",
                new=AsyncMock(return_value=owner),
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.get_knowledge_bases_root_path",
                return_value=Path(),
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.validate_kb_path",
                return_value=None,
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.load_kb_metadata",
                return_value={},
            ),
            pytest.raises(ValueError, match="no embedding metadata"),
        ):
            await component.retrieve_memory()

    async def test_kb_path_traversal_raises(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1")
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="../escape")
        db = _exec_returning(mb_row)
        with (
            _patched_session_scope(db),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.get_user_by_id",
                new=AsyncMock(return_value=owner),
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.get_knowledge_bases_root_path",
                return_value=Path(),
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.validate_kb_path",
                side_effect=ValueError("escapes root"),
            ),
            pytest.raises(ValueError, match="not accessible"),
        ):
            await component.retrieve_memory()


class TestMemoryBaseRetrievalBehavior:
    @staticmethod
    def _enter_full_chain(stack: contextlib.ExitStack, *, db, fake_chroma, owner, metadata):
        for cm in (
            _patched_session_scope(db),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.get_user_by_id",
                new=AsyncMock(return_value=owner),
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.get_knowledge_bases_root_path",
                return_value=Path(),
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.validate_kb_path",
                return_value=None,
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.load_kb_metadata",
                return_value=metadata,
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.KBIngestionHelper.build_embeddings",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.Chroma",
                return_value=fake_chroma,
            ),
        ):
            stack.enter_context(cm)

    async def test_similarity_search_uses_session_filter_when_enabled(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1", filter_by_session=True)
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")

        fake_chroma = MagicMock()
        fake_chroma.similarity_search_with_score.return_value = []

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_chroma=fake_chroma,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x", "api_key": "k"},
            )
            await component.retrieve_memory()

        kwargs = fake_chroma.similarity_search_with_score.call_args.kwargs
        assert kwargs["k"] == 5
        assert kwargs["filter"] == {"session_id": {"$eq": "s1"}}

    async def test_similarity_search_no_filter_when_disabled(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1", filter_by_session=False)
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")

        fake_chroma = MagicMock()
        fake_chroma.similarity_search_with_score.return_value = []

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_chroma=fake_chroma,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            await component.retrieve_memory()

        kwargs = fake_chroma.similarity_search_with_score.call_args.kwargs
        assert kwargs["filter"] is None

    async def test_empty_search_query_returns_empty_dataframe_without_embedding(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(
            flow_id=flow_id,
            session_id="s1",
            search_query="",
        )
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")

        fake_chroma = MagicMock()

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_chroma=fake_chroma,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            result = await component.retrieve_memory()

        assert len(result) == 0
        fake_chroma.similarity_search_with_score.assert_not_called()
        fake_chroma.similarity_search.assert_not_called()

    async def test_include_metadata_false_drops_metadata_keys(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(
            flow_id=flow_id,
            session_id="s1",
            include_metadata=False,
        )
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")

        doc = SimpleNamespace(page_content="hello world", metadata={"session_id": "s1", "sender": "user"})
        fake_chroma = MagicMock()
        fake_chroma.similarity_search_with_score.return_value = [(doc, 0.25)]

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_chroma=fake_chroma,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            df = await component.retrieve_memory()

        assert len(df) == 1
        row = df.to_dict(orient="records")[0]
        assert row["content"] == "hello world"
        assert row["_score"] == -0.25
        assert "session_id" not in row
        assert "sender" not in row

    async def test_include_metadata_true_merges_metadata(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1", include_metadata=True)
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")

        doc = SimpleNamespace(page_content="hi", metadata={"session_id": "s1", "sender": "ai"})
        fake_chroma = MagicMock()
        fake_chroma.similarity_search_with_score.return_value = [(doc, 0.1)]

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_chroma=fake_chroma,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            df = await component.retrieve_memory()

        row = df.to_dict(orient="records")[0]
        assert row["sender"] == "ai"
        assert row["session_id"] == "s1"

    async def test_numpy_metadata_values_are_normalized(self):
        """Regression: numpy.int64 in Chroma metadata broke Agent tool serialization.

        Chroma stores integer metadata (timestamps, ingestion IDs, …) as
        numpy.int64 scalars. The Agent's tool-output path then calls
        ``vars()`` on / iterates those values, raising TypeError. Confirm
        the component coerces to Python primitives before emitting Data rows.
        """
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1", include_metadata=True)
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")

        doc = SimpleNamespace(
            page_content="hello",
            metadata={
                "session_id": "s1",
                "ingest_seq": np.int64(7),
                "timestamp": np.int64(1_700_000_000),
                "score_raw": np.float64(0.42),
                "is_summary": np.bool_(True),  # noqa: FBT003
            },
        )
        fake_chroma = MagicMock()
        fake_chroma.similarity_search_with_score.return_value = [(doc, np.float64(0.25))]

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_chroma=fake_chroma,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            df = await component.retrieve_memory()

        row = df.to_dict(orient="records")[0]
        assert row["ingest_seq"] == 7
        assert type(row["ingest_seq"]) is int
        assert row["timestamp"] == 1_700_000_000
        assert type(row["timestamp"]) is int
        assert row["score_raw"] == 0.42
        assert type(row["score_raw"]) is float
        assert row["is_summary"] is True
        assert type(row["is_summary"]) is bool
        # _score derives from the numpy distance; confirm it is also normalized.
        assert type(row["_score"]) is float

        # The whole row must JSON-serialize without falling back to a custom encoder.
        json.dumps(row)
