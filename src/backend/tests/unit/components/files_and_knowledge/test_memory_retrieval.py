"""Unit tests for MemoryBaseComponent.

Covers:
- Validation: missing session_id, missing flow_id, MB not attached to flow,
  unselected MB, missing owner, missing/invalid metadata, KB path traversal.
- Where-clause composition (session filter on / off / multi-predicate).
- update_build_config dropdown population.
- _coerce_uuid input coercion.
- retrieve_data behavior: similarity search w/ filter, empty query short-circuit,
  filter_by_session=False end-to-end, include_metadata=False output shape.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import numpy as np
import pytest
from langflow.services.memory_base.kb_path_helpers import hash_session_id
from lfx.components.files_and_knowledge import _kb_paths
from lfx.components.files_and_knowledge.memory_retrieval import (
    MemoryBaseComponent,
    _coerce_uuid,
    _to_python_scalar,
)


def _make_component(
    *,
    flow_id: uuid.UUID | None,
    session_id: str | None,
    invoker_user_id: uuid.UUID | None = None,
    selected: str | None = "mb-one",
    filter_by_session: bool | str = True,
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


def _exec_owner_scoped(mb_row):
    """Model the DB result for an exact ``name + flow + execution user`` lookup.

    The legacy vulnerable query omitted ``user_id`` and therefore resolved the
    owner's row for every execution principal.  Keeping that behavior when the
    predicate is absent makes the non-owner tests below fail for the actual
    security reason instead of depending on SQL string assertions alone.
    """
    db = MagicMock()

    async def _exec(stmt):
        params = stmt.compile().params
        requested_user_id = params.get("user_id_1")
        matched = requested_user_id is None or requested_user_id == mb_row.user_id
        result = MagicMock()
        result.first.return_value = mb_row if matched else None
        return result

    db.exec = AsyncMock(side_effect=_exec)
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


# Score normalization is the backend's contract, covered per backend in
# tests/unit/base/knowledge_bases; this module only asserts the component
# delegates to it.


def test_result_formatting_uses_backend_score_contract():
    component = _make_component(flow_id=uuid.uuid4(), session_id="s1")
    backend = MagicMock()
    backend.normalize_score.return_value = 0.91
    doc = SimpleNamespace(page_content="match", metadata={})

    result = component._format_results([(doc, 7.0)], backend)

    assert result.to_dict(orient="records")[0]["_score"] == 0.91
    backend.normalize_score.assert_called_once_with(7.0)


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
        assert component._build_where_clause(session_id="s1") == {"session_id": "s1"}

    def test_session_filter_off_returns_none(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1", filter_by_session=False)
        assert component._build_where_clause(session_id="s1") is None

    def test_no_session_id_returns_none(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id=None, filter_by_session=True)
        assert component._build_where_clause(session_id=None) is None

    @pytest.mark.parametrize("serialized_false", ["false", "False", " 0 ", "no", "off", ""])
    def test_serialized_false_values_disable_session_filter(self, serialized_false):
        component = _make_component(
            flow_id=uuid.uuid4(),
            session_id="s1",
            filter_by_session=serialized_false,
        )
        assert component._build_where_clause(session_id="s1") is None

    def test_unknown_string_keeps_session_filter_enabled(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1", filter_by_session="unexpected")
        assert component._build_where_clause(session_id="s1") == {"session_id": "s1"}

    def test_session_filter_falsy_value_disables_toggle(self):
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1", filter_by_session=False)
        component.filter_by_session = ""  # falsy non-bool
        assert component._build_where_clause(session_id="s1") is None

    def test_session_filter_off_with_end_user_scopes_to_end_user(self):
        # Serving-plane cross-session recall stays within one end user instead of spanning
        # every end user's chunks in the shared service-account store.
        component = _make_component(flow_id=uuid.uuid4(), session_id="alice::s1", filter_by_session=False)
        assert component._build_where_clause(session_id="alice::s1", end_user_id="alice") == {"end_user_id": "alice"}

    def test_session_filter_on_ignores_end_user(self):
        # The session-id prefix already scopes to the end user, so the session predicate wins.
        component = _make_component(flow_id=uuid.uuid4(), session_id="alice::s1", filter_by_session=True)
        assert component._build_where_clause(session_id="alice::s1", end_user_id="alice") == {"session_id": "alice::s1"}

    def test_session_filter_off_without_end_user_returns_none(self):
        # Editor / feature off: no end user, so cross-session recall spans all sessions (unchanged).
        component = _make_component(flow_id=uuid.uuid4(), session_id="s1", filter_by_session=False)
        assert component._build_where_clause(session_id="s1", end_user_id=None) is None


# ---------------------------------------------------------------------------
# Serving-plane fail-closed: anonymous caller cannot do cross-session recall
# ---------------------------------------------------------------------------

MR_MODULE = "lfx.components.files_and_knowledge.memory_retrieval"


class TestMemoryBaseProviderPolicyPreflight:
    async def test_db_provider_denial_precedes_owner_credentials_and_uses_actor_scope(self, monkeypatch):
        """Raw MB selection resolves owner metadata but authorizes the current runtime actor."""
        from lfx.services.model_provider_policy import (
            ModelProviderPolicyContext,
            ModelProviderPolicyError,
            ModelProviderPolicyPurpose,
            current_model_provider_policy_context,
            reset_current_model_provider_policy_context,
            set_current_model_provider_policy_context,
        )

        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        component = _make_component(
            flow_id=flow_id,
            session_id="s1",
            invoker_user_id=owner_id,
        )
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        db = _exec_owner_scoped(mb_row)
        selection_lookup = AsyncMock(return_value=("OpenAI", "text-embedding-3-small"))
        owner_embedding_build = AsyncMock(side_effect=AssertionError("owner credential read before actor denial"))
        denial = ModelProviderPolicyError("openai", ModelProviderPolicyPurpose.USE)
        snapshot = SimpleNamespace(require=MagicMock(side_effect=denial))
        observed_contexts = []

        async def resolve_policy(**_kwargs):
            observed_contexts.append(current_model_provider_policy_context())
            return snapshot

        monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve_policy)
        token = set_current_model_provider_policy_context(
            user_id=actor_id,
            attributes={"project_id": "project-current", "workspace_id": "workspace-current"},
        )
        try:
            with (
                _patched_session_scope(db),
                patch(f"{MR_MODULE}.resolve_embedding_selection", selection_lookup),
                patch("langflow.api.utils.kb_helpers.KBIngestionHelper.build_embeddings", owner_embedding_build),
                pytest.raises(ModelProviderPolicyError),
            ):
                await component.arequire_model_provider_policy(
                    ModelProviderPolicyPurpose.USE,
                    user_id=actor_id,
                    parameters={"memory_base": "mb-one"},
                )
        finally:
            reset_current_model_provider_policy_context(token)

        selection_lookup.assert_awaited_once_with(user_id=owner_id, kb_name=mb_row.kb_name)
        assert observed_contexts == [
            ModelProviderPolicyContext(
                user_id=actor_id,
                attributes={"project_id": "project-current", "workspace_id": "workspace-current"},
            )
        ]
        owner_embedding_build.assert_not_awaited()
        stmt_params = db.exec.await_args.args[0].compile().params
        assert owner_id in stmt_params.values()
        assert actor_id not in stmt_params.values()

    async def test_backend_recheck_uses_actor_policy_snapshot_with_owner_credentials(self, monkeypatch):
        """A fresh actor decision is passed through while model credentials remain owner-scoped."""
        from lfx.services.model_provider_policy import (
            ModelProviderPolicyPurpose,
            reset_current_model_provider_policy_context,
            set_current_model_provider_policy_context,
        )

        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        owner = SimpleNamespace(id=owner_id, username="owner")
        component = _make_component(
            flow_id=flow_id,
            session_id="s1",
            invoker_user_id=owner_id,
        )
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        snapshot = SimpleNamespace(require=MagicMock())
        resolve_policy = AsyncMock(return_value=snapshot)
        selection_lookup = AsyncMock(return_value=("OpenAI", "text-embedding-3-small"))
        owner_embedding_build = AsyncMock(side_effect=AssertionError("owner policy was re-evaluated"))
        embedding = MagicMock()
        get_embeddings = MagicMock(return_value=embedding)
        backend = AsyncMock()

        monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve_policy)
        token = set_current_model_provider_policy_context(
            user_id=actor_id,
            attributes={"project_id": "project-current", "workspace_id": "workspace-current"},
        )
        try:
            with (
                _patched_session_scope(_exec_owner_scoped(mb_row)),
                patch(f"{MR_MODULE}.resolve_embedding_selection", selection_lookup),
                patch(f"{MR_MODULE}.resolve_backend_selection", new=AsyncMock(return_value=("chroma", {}))),
                patch(f"{MR_MODULE}.resolve_local_store_path", return_value=None),
                patch("langflow.api.utils.kb_helpers.KBIngestionHelper.build_embeddings", owner_embedding_build),
                patch("lfx.base.models.unified_models.get_embeddings", get_embeddings),
                patch(f"{MR_MODULE}.create_backend", return_value=backend),
            ):
                await component.arequire_model_provider_policy(
                    ModelProviderPolicyPurpose.USE,
                    user_id=actor_id,
                    parameters={"memory_base": "mb-one"},
                )
                built_backend = await component._build_backend(owner, owner.username, mb_row.kb_name)
        finally:
            reset_current_model_provider_policy_context(token)

        assert built_backend is backend
        assert resolve_policy.await_count == 2
        assert all(call.kwargs["user_id"] == actor_id for call in resolve_policy.await_args_list)
        selection_lookup.assert_has_awaits(
            [
                call(user_id=owner_id, kb_name=mb_row.kb_name),
                call(user_id=owner_id, kb_name=mb_row.kb_name),
            ]
        )
        owner_embedding_build.assert_not_awaited()
        assert get_embeddings.call_args.kwargs["user_id"] == owner_id
        assert get_embeddings.call_args.kwargs["provider_policy"] is snapshot
        backend.ensure_ready.assert_awaited_once()


class TestServingFailClosed:
    async def test_anonymous_cross_session_recall_returns_empty(self):
        # Serving on + filter_by_session off + no derivable end user (anonymous) must NOT
        # run an unfiltered search over the shared store — it would return every end user's
        # memory. It short-circuits to empty before any owner lookup / backend construction.
        component = _make_component(flow_id=uuid.uuid4(), session_id="anon::deadbeef", filter_by_session=False)
        with (
            patch(f"{MR_MODULE}.serving_end_user_enabled", return_value=True),
            patch(f"{MR_MODULE}.end_user_id_from_scoped_session", return_value=None),
        ):
            result = await component.retrieve_memory()
        assert len(result) == 0

    async def test_feature_off_cross_session_recall_not_blocked(self):
        # Feature off: the fail-closed guard must not fire — cross-session recall stays
        # available exactly as before (proven by reaching the flow_id validation, not the
        # early empty return). end_user_id_from_scoped_session returns None when off.
        component = _make_component(flow_id=None, session_id="s1", filter_by_session=False)
        with (
            patch(f"{MR_MODULE}.serving_end_user_enabled", return_value=False),
            patch(f"{MR_MODULE}.end_user_id_from_scoped_session", return_value=None),
            pytest.raises(ValueError, match="flow_id is not available"),
        ):
            await component.retrieve_memory()


# ---------------------------------------------------------------------------


class TestRootPathCache:
    def test_reset_cache_picks_up_new_setting(self, tmp_path):
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

    @pytest.mark.parametrize("serialized_false", ["false", "0"])
    async def test_serialized_false_does_not_require_session_id(self, serialized_false):
        component = _make_component(
            flow_id=uuid.uuid4(),
            session_id=None,
            selected=None,
            filter_by_session=serialized_false,
        )
        with pytest.raises(ValueError, match="No Memory Base"):
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

        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = []

        with contextlib.ExitStack() as stack:
            TestMemoryBaseRetrievalBehavior._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_backend=fake_backend,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            result = await component.retrieve_memory()

        assert len(result) == 0
        kwargs = fake_backend.similarity_search.call_args.kwargs
        assert kwargs["filter"] is None

    async def test_missing_flow_id_raises(self):
        component = _make_component(flow_id=None, session_id="s1")
        with pytest.raises(ValueError, match="flow_id"):
            await component.retrieve_memory()

    @pytest.mark.parametrize("runtime_user_id", [None, "not-a-uuid"])
    async def test_missing_or_invalid_runtime_user_fails_before_owner_resolution(self, runtime_user_id):
        """A malformed graph principal must never fall back to the Memory Base owner."""
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(
            flow_id=flow_id,
            session_id=None,
            filter_by_session=False,
            invoker_user_id=owner_id,
        )
        component.graph.user_id = runtime_user_id
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = []

        with contextlib.ExitStack() as stack:
            TestMemoryBaseRetrievalBehavior._enter_full_chain(
                stack,
                db=_exec_owner_scoped(mb_row),
                fake_backend=fake_backend,
                owner=SimpleNamespace(id=owner_id, username="owner"),
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            with pytest.raises(ValueError, match="user_id"):
                await component.retrieve_memory()

        fake_backend.ensure_ready.assert_not_awaited()
        fake_backend.similarity_search.assert_not_awaited()

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

    async def test_retrieval_works_without_on_disk_sidecar(self):
        """A missing on-disk sidecar must NOT block retrieval.

        Embedding + backend resolve from the knowledge_base row, so a remote-backed
        Memory Base is queryable on a replica whose local disk never held the KB
        directory. This is the regression guard for the old hard-fail
        ("has no embedding metadata on disk").
        """
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1")
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")

        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = []

        with contextlib.ExitStack() as stack:
            TestMemoryBaseRetrievalBehavior._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_backend=fake_backend,
                owner=owner,
                # No sidecar on disk — resolver falls back to the default model.
                metadata={},
            )
            result = await component.retrieve_memory()

        assert len(result) == 0
        fake_backend.similarity_search.assert_awaited_once()

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
                "lfx.components.files_and_knowledge.memory_retrieval.resolve_backend_selection",
                new=AsyncMock(return_value=("chroma", {})),
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.resolve_local_store_path",
                side_effect=ValueError("KB path escapes root directory"),
            ),
            pytest.raises(ValueError, match="not accessible"),
        ):
            await component.retrieve_memory()


class TestMemoryBaseRetrievalBehavior:
    @staticmethod
    def _enter_full_chain(stack: contextlib.ExitStack, *, db, fake_backend, owner, metadata):
        # Embedding provider/model now come from the DB row via
        # resolve_embedding_selection (no on-disk sidecar), so patch that instead
        # of the removed sidecar read. The ``metadata`` dict is reused as
        # the source of the provider/model the resolver returns.
        provider = metadata.get("embedding_provider", "OpenAI")
        model = metadata.get("embedding_model", "x")
        # Stand in for the distance-based backend contract (higher == more similar).
        fake_backend.normalize_score = MagicMock(side_effect=lambda score: -float(score))
        for cm in (
            _patched_session_scope(db),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.get_user_by_id",
                new=AsyncMock(return_value=owner),
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.resolve_local_store_path",
                return_value=None,
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.resolve_embedding_selection",
                new=AsyncMock(return_value=(provider, model)),
            ),
            patch("lfx.base.models.unified_models.get_embeddings", return_value=MagicMock()),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.resolve_backend_selection",
                new=AsyncMock(return_value=("chroma", {})),
            ),
            patch(
                "lfx.components.files_and_knowledge.memory_retrieval.create_backend",
                return_value=fake_backend,
            ),
        ):
            stack.enter_context(cm)

    async def test_similarity_search_uses_session_filter_when_enabled(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1", filter_by_session=True)
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")

        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = []

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_backend=fake_backend,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x", "api_key": "k"},
            )
            await component.retrieve_memory()

        kwargs = fake_backend.similarity_search.call_args.kwargs
        assert kwargs["k"] == 5
        assert kwargs["filter"] == {"session_id": "s1"}

    async def test_debug_log_redacts_raw_session_id(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        session_id = "private-session-id"
        component = _make_component(flow_id=flow_id, session_id=session_id, filter_by_session=True)
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")
        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = []

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_backend=fake_backend,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            debug_mock = stack.enter_context(patch("lfx.components.files_and_knowledge.memory_retrieval.logger.debug"))
            await component.retrieve_memory()

        logged = repr(debug_mock.call_args_list)
        assert session_id not in logged
        assert hash_session_id(session_id) in logged

    async def test_similarity_search_no_filter_when_disabled(self):
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(flow_id=flow_id, session_id="s1", filter_by_session=False)
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="alice")

        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = []

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_backend=fake_backend,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            await component.retrieve_memory()

        kwargs = fake_backend.similarity_search.call_args.kwargs
        assert kwargs["filter"] is None

    async def test_owner_can_retrieve_across_sessions_under_owner_principal(self):
        """The owner-equivalent execution principal keeps the cross-session feature working."""
        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        component = _make_component(
            flow_id=flow_id,
            session_id=None,
            filter_by_session=False,
            invoker_user_id=owner_id,
        )
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="owner")
        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = []

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_owner_scoped(mb_row),
                fake_backend=fake_backend,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            result = await component.retrieve_memory()

        assert len(result) == 0
        fake_backend.ensure_ready.assert_awaited_once()
        fake_backend.similarity_search.assert_awaited_once()

    @pytest.mark.parametrize(
        "caller_kind",
        ["delegate", "public_v1", "public_v2", "public_a2a_initial", "public_a2a_hitl_resume"],
    )
    async def test_non_owner_principal_cannot_open_owner_backend_when_session_filter_is_off(self, caller_kind):
        """Every non-owner route principal fails before owner lookup/backend construction."""
        from langflow.services.authorization.public_access import PUBLIC_ANONYMOUS_ACTOR_ID

        flow_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        caller_id = uuid.uuid4() if caller_kind == "delegate" else PUBLIC_ANONYMOUS_ACTOR_ID
        component = _make_component(
            flow_id=flow_id,
            session_id=None,
            filter_by_session=False,
            invoker_user_id=caller_id,
        )
        mb_row = _make_mb_row(flow_id=flow_id, owner_id=owner_id)
        owner = SimpleNamespace(id=owner_id, username="owner")
        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = []

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_owner_scoped(mb_row),
                fake_backend=fake_backend,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            with pytest.raises(ValueError, match="not attached to this flow"):
                await component.retrieve_memory()

        fake_backend.ensure_ready.assert_not_awaited()
        fake_backend.similarity_search.assert_not_awaited()

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

        fake_backend = AsyncMock()

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_backend=fake_backend,
                owner=owner,
                metadata={"embedding_provider": "OpenAI", "embedding_model": "x"},
            )
            result = await component.retrieve_memory()

        assert len(result) == 0
        fake_backend.similarity_search.assert_not_called()
        fake_backend.similarity_search.assert_not_called()

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
        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = [(doc, 0.25)]

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_backend=fake_backend,
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
        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = [(doc, 0.1)]

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_backend=fake_backend,
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
        fake_backend = AsyncMock()
        fake_backend.similarity_search.return_value = [(doc, np.float64(0.25))]

        with contextlib.ExitStack() as stack:
            self._enter_full_chain(
                stack,
                db=_exec_returning(mb_row),
                fake_backend=fake_backend,
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
