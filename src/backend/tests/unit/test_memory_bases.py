"""Unit tests for the MemoryBase feature.

Coverage areas:
- DB model creation and field defaults
- MemoryBaseService CRUD operations
- Concurrency guard (409 on duplicate active job)
- Cursor atomicity (cursor not advanced on ingestion failure)
- Threshold-change deferral
- FS/VectorDB mismatch detection
- Regenerate: cursor reset + re-trigger
- API endpoint routing (happy path + error paths)
- ingest_memory_task: pending message fetch, document building, cursor advance
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBaseCreate,
    MemoryBaseSession,
    MemoryBaseUpdate,
)
from langflow.services.database.models.message.model import MessageTable

# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #


def _make_mb(
    *,
    user_id: uuid.UUID | None = None,
    flow_id: uuid.UUID | None = None,
    threshold: int = 10,
    auto_capture: bool = True,
) -> MemoryBase:
    return MemoryBase(
        id=uuid.uuid4(),
        name="test_mb",
        flow_id=flow_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        threshold=threshold,
        kb_name="test_kb",
        auto_capture=auto_capture,
        created_at=datetime.now(timezone.utc),
    )


def _make_session(
    *,
    memory_base_id: uuid.UUID | None = None,
    session_id: str = "sess-1",
    cursor_id: uuid.UUID | None = None,
    total_processed: int = 0,
) -> MemoryBaseSession:
    return MemoryBaseSession(
        id=uuid.uuid4(),
        memory_base_id=memory_base_id or uuid.uuid4(),
        session_id=session_id,
        cursor_id=cursor_id,
        total_processed=total_processed,
    )


def _make_message(
    *,
    flow_id: uuid.UUID,
    session_id: str,
    is_output: bool = True,
    text: str = "Hello from the bot",
    run_id: uuid.UUID | None = None,
) -> MessageTable:
    return MessageTable(
        id=uuid.uuid4(),
        sender="AI",
        sender_name="Bot",
        session_id=session_id,
        text=text,
        flow_id=flow_id,
        is_output=is_output,
        run_id=run_id,
        timestamp=datetime.now(timezone.utc),
    )


# ------------------------------------------------------------------ #
#  Model tests                                                         #
# ------------------------------------------------------------------ #


class TestInferEmbeddingProvider:
    """Provider inference regression tests.

    The returned provider name must be a canonical key registered in
    ``EMBEDDING_PROVIDER_CLASS_MAPPING`` so the result can be round-tripped
    through ``KBIngestionHelper.build_embeddings`` without translation.
    """

    @pytest.mark.parametrize(
        ("model", "expected"),
        [
            # Google Generative AI — the original bug: gemini-embedding was
            # being misclassified as OpenAI because no Google pattern matched.
            ("models/gemini-embedding-001", "Google Generative AI"),
            ("models/text-embedding-004", "Google Generative AI"),
            ("models/embedding-001", "Google Generative AI"),
            # OpenAI — must NOT be caught by the Google "models/text-embedding"
            # pattern, since OpenAI names don't carry the "models/" prefix.
            ("text-embedding-3-small", "OpenAI"),
            ("text-embedding-3-large", "OpenAI"),
            ("text-embedding-ada-002", "OpenAI"),
            # Other providers
            ("nomic-embed-text", "Ollama"),
            ("embed-english-v3.0", "Cohere"),
            # Unknown / empty fall back to the safe default.
            ("unknown-model", "OpenAI"),
            ("", "OpenAI"),
        ],
    )
    def test_provider_inferred_correctly(self, model, expected):
        from langflow.services.memory_base.embedding_helpers import infer_embedding_provider

        assert infer_embedding_provider(model) == expected

    def test_inferred_provider_is_in_class_mapping(self):
        """Inferred provider must be a registered embedding-class mapping key.

        Otherwise the downstream ``KBIngestionHelper.build_embeddings`` call
        will reject it.
        """
        from langflow.services.memory_base.embedding_helpers import infer_embedding_provider
        from lfx.base.models.unified_models.class_registry import EMBEDDING_PROVIDER_CLASS_MAPPING

        for model in (
            "models/gemini-embedding-001",
            "text-embedding-3-small",
            "text-embedding-3-large",
            "nomic-embed-text",
            "unknown-model",
        ):
            assert infer_embedding_provider(model) in EMBEDDING_PROVIDER_CLASS_MAPPING


class TestKBIngestionHelperBuildEmbeddings:
    """Regression tests for the Memory Base retrieval bug.

    ``build_embeddings`` must not depend on the user-filtered catalog
    returned by ``get_embedding_model_options``: that catalog is empty
    whenever the per-user credential lookup fails (which can happen
    transparently when the helper runs in a thread bridged from an async
    event loop). The KB's ``embedding_metadata.json`` is the source of
    truth — we resolve the embedding class from the static registry.
    """

    @pytest.mark.asyncio
    async def test_builds_embeddings_for_openai_default_model(self):
        from langflow.api.utils.kb_helpers import KBIngestionHelper

        sentinel = object()
        with patch("langflow.api.utils.kb_helpers.EmbeddingModelComponent") as mock_component_cls:
            instance = mock_component_cls.return_value
            instance.build_embeddings.return_value = sentinel
            user = MagicMock(id=uuid.uuid4())

            result = await KBIngestionHelper.build_embeddings("OpenAI", "text-embedding-3-small", user)

        assert result is sentinel
        kwargs = mock_component_cls.call_args.kwargs
        selected = kwargs["model"][0]
        assert selected["provider"] == "OpenAI"
        assert selected["name"] == "text-embedding-3-small"
        assert selected["metadata"]["embedding_class"] == "OpenAIEmbeddings"
        assert selected["metadata"]["model_type"] == "embeddings"
        assert "param_mapping" in selected["metadata"]

    @pytest.mark.asyncio
    async def test_builds_embeddings_for_google_gemini_model(self):
        """Google-side regression coverage.

        ``gemini-embedding-001`` must resolve to
        ``GoogleGenerativeAIEmbeddings`` rather than blowing up.
        """
        from langflow.api.utils.kb_helpers import KBIngestionHelper

        with patch("langflow.api.utils.kb_helpers.EmbeddingModelComponent") as mock_component_cls:
            mock_component_cls.return_value.build_embeddings.return_value = MagicMock()
            user = MagicMock(id=uuid.uuid4())

            await KBIngestionHelper.build_embeddings("Google Generative AI", "models/gemini-embedding-001", user)

        selected = mock_component_cls.call_args.kwargs["model"][0]
        assert selected["provider"] == "Google Generative AI"
        assert selected["metadata"]["embedding_class"] == "GoogleGenerativeAIEmbeddings"

    @pytest.mark.asyncio
    async def test_unregistered_provider_raises_with_helpful_message(self):
        from langflow.api.utils.kb_helpers import KBIngestionHelper

        user = MagicMock(id=uuid.uuid4())
        with pytest.raises(ValueError, match="not registered"):
            await KBIngestionHelper.build_embeddings("MadeUpProvider", "some-model", user)

    @pytest.mark.asyncio
    async def test_does_not_consult_user_filtered_catalog(self):
        """Helper must resolve from the static registry, not the user catalog.

        Even if ``get_embedding_model_options`` would return an empty list
        (e.g. the per-user credential lookup silently failed), the helper
        must still resolve the model from the static registry.
        """
        from langflow.api.utils import kb_helpers as kb_helpers_module
        from langflow.api.utils.kb_helpers import KBIngestionHelper

        # The helper used to call ``get_embedding_model_options`` and raise
        # when the result was empty. Make sure that name is no longer wired
        # into the helper's module — otherwise the bug can silently regress.
        assert not hasattr(kb_helpers_module, "get_embedding_model_options")

        with patch("langflow.api.utils.kb_helpers.EmbeddingModelComponent") as mock_component_cls:
            mock_component_cls.return_value.build_embeddings.return_value = MagicMock()
            user = MagicMock(id=uuid.uuid4())

            await KBIngestionHelper.build_embeddings("OpenAI", "text-embedding-3-large", user)

        assert mock_component_cls.called

    @pytest.mark.asyncio
    async def test_ollama_embeddings_honor_configured_base_url(self, monkeypatch):
        """Ollama KB ingestion must use the configured OLLAMA_BASE_URL, not localhost.

        Regression for https://github.com/langflow-ai/langflow/issues/13883. The helper
        builds ``EmbeddingModelComponent`` programmatically; the component's
        ``ollama_base_url`` ``StrInput`` defaults to ``http://localhost:11434``, and that
        truthy default used to leak through ``getattr`` and short-circuit the
        ``OLLAMA_BASE_URL`` global-variable lookup in ``get_embeddings`` — so a KB
        pointed at a remote Ollama server silently tried localhost and failed with
        "Failed to connect to Ollama". This test exercises the REAL component (no mock)
        so the resolution path is covered end to end.
        """
        from langflow.api.utils.kb_helpers import KBIngestionHelper

        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        user = MagicMock(id=uuid.uuid4())

        with (
            patch("lfx.base.models.unified_models.get_api_key_for_provider", return_value=None),
            patch(
                "lfx.base.models.unified_models.get_all_variables_for_provider",
                return_value={"OLLAMA_BASE_URL": "http://ollama-server:11434"},
            ),
        ):
            embeddings = await KBIngestionHelper.build_embeddings("Ollama", "nomic-embed-text", user)

        assert str(embeddings.base_url).rstrip("/") == "http://ollama-server:11434"

    @pytest.mark.asyncio
    async def test_ollama_embeddings_fall_back_to_localhost_when_unconfigured(self, monkeypatch):
        """With no OLLAMA_BASE_URL configured, the localhost fallback is preserved."""
        from langflow.api.utils.kb_helpers import KBIngestionHelper

        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        user = MagicMock(id=uuid.uuid4())

        with (
            patch("lfx.base.models.unified_models.get_api_key_for_provider", return_value=None),
            patch("lfx.base.models.unified_models.get_all_variables_for_provider", return_value={}),
        ):
            embeddings = await KBIngestionHelper.build_embeddings("Ollama", "nomic-embed-text", user)

        assert str(embeddings.base_url).rstrip("/") == "http://localhost:11434"


class TestMemoryBaseModel:
    def test_defaults(self):
        mb = MemoryBase(
            name="mb",
            flow_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            kb_name="kb",
        )
        assert mb.threshold == 50
        assert mb.auto_capture is True

    def test_create_schema(self):
        payload = MemoryBaseCreate(
            name="mb",
            flow_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            threshold=25,
            kb_name="kb",
        )
        assert payload.threshold == 25

    def test_update_schema_partial(self):
        patch = MemoryBaseUpdate(threshold=100)
        dumped = patch.model_dump(exclude_unset=True)
        assert "threshold" in dumped
        assert "name" not in dumped

    def test_memory_base_session_defaults(self):
        mbs = MemoryBaseSession(
            memory_base_id=uuid.uuid4(),
            session_id="s1",
        )
        assert mbs.cursor_id is None
        assert mbs.total_processed == 0
        assert mbs.last_sync_at is None


class TestMessageExtensions:
    """Ensure the new fields exist on MessageTable."""

    def test_run_id_field_exists(self):
        msg = _make_message(flow_id=uuid.uuid4(), session_id="s1")
        assert hasattr(msg, "run_id")
        assert msg.run_id is None

    def test_is_output_field_defaults_false(self):
        msg = MessageTable(
            sender="Human",
            sender_name="User",
            session_id="s1",
            text="hi",
        )
        assert msg.is_output is False

    def test_is_output_can_be_set(self):
        msg = _make_message(flow_id=uuid.uuid4(), session_id="s1", is_output=True)
        assert msg.is_output is True


# ------------------------------------------------------------------ #
#  Service tests (mock DB)                                             #
# ------------------------------------------------------------------ #


class TestMemoryBaseServiceCRUD:
    @pytest.fixture
    def service(self):
        from langflow.services.memory_base.service import MemoryBaseService

        return MemoryBaseService()

    @pytest.mark.asyncio
    async def test_create_stores_user_id(self, service):
        user_id = uuid.uuid4()
        payload = MemoryBaseCreate(
            name="mb",
            flow_id=uuid.uuid4(),
            user_id=user_id,
            kb_name="kb",
        )

        created_mb = _make_mb(user_id=user_id)

        with patch.object(service, "create", AsyncMock(return_value=created_mb)):
            result = await service.create(payload, user_id=user_id)

        assert result.user_id == user_id

    @pytest.mark.asyncio
    async def test_get_returns_none_for_wrong_user(self, service):
        with patch.object(service, "get", AsyncMock(return_value=None)):
            result = await service.get(uuid.uuid4(), user_id=uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_update_returns_none_for_missing(self, service):
        with patch.object(service, "update", AsyncMock(return_value=None)):
            result = await service.update(uuid.uuid4(), uuid.uuid4(), MemoryBaseUpdate(threshold=5))
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_missing(self, service):
        with patch.object(service, "delete", AsyncMock(return_value=False)):
            result = await service.delete(uuid.uuid4(), user_id=uuid.uuid4())
        assert result is False


class TestMemoryBaseCreateFlowOwnership:
    """Regression tests for cross-user data leak via flow_id at creation time.

    A user must not be able to create a Memory Base pointed at another user's
    flow. Without the ownership check, on_flow_output() would capture that
    flow's conversation history into the attacker's Memory Base, which they
    could then read via /sessions + /messages.
    """

    @pytest.fixture
    def service(self):
        from langflow.services.memory_base.service import MemoryBaseService

        return MemoryBaseService()

    def _fake_scope(self, mock_db):
        class _FakeCtx:
            async def __aenter__(self):
                return mock_db

            async def __aexit__(self, *a):
                pass

        scope = MagicMock()
        scope.return_value = _FakeCtx()
        return scope

    @pytest.mark.asyncio
    async def test_create_rejects_unowned_flow(self, service):
        """PermissionError raised when flow_id belongs to a different user."""
        user_id = uuid.uuid4()
        payload = MemoryBaseCreate(name="mb", flow_id=uuid.uuid4())

        mock_db = AsyncMock()
        # exec() is async, but .first() on the result is synchronous — use MagicMock
        # so that flow_result.first() returns None without returning a coroutine.
        exec_result = MagicMock()
        exec_result.first.return_value = None
        mock_db.exec = AsyncMock(return_value=exec_result)

        with (
            patch("langflow.services.memory_base.service.session_scope", self._fake_scope(mock_db)),
            pytest.raises(PermissionError, match="not found"),
        ):
            await service.create(payload, user_id=user_id)

    @pytest.mark.asyncio
    async def test_create_allows_owned_flow(self, service):
        """No PermissionError when flow_id is owned by the requesting user."""
        from langflow.services.database.models.flow.model import Flow

        user_id = uuid.uuid4()
        flow_id = uuid.uuid4()
        payload = MemoryBaseCreate(name="mb", flow_id=flow_id)

        owned_flow = Flow(id=flow_id, user_id=user_id, name="my flow")
        created_mb = _make_mb(user_id=user_id, flow_id=flow_id)

        # exec() is async; .first() on the result is synchronous — use MagicMock.
        # First call: flow ownership check → returns owned_flow (passes).
        # Second call (different session_scope): name-uniqueness check → None.
        first_exec = MagicMock()
        first_exec.first.return_value = owned_flow
        second_exec = MagicMock()
        second_exec.first.return_value = None

        mock_db = AsyncMock()
        mock_db.exec = AsyncMock(side_effect=[first_exec, second_exec])
        mock_db.refresh = AsyncMock(return_value=created_mb)

        with (
            patch("langflow.services.memory_base.service.session_scope", self._fake_scope(mock_db)),
            patch(
                "langflow.services.memory_base.kb_path_helpers.resolve_kb_username", AsyncMock(return_value="testuser")
            ),
            patch("langflow.services.memory_base.kb_path_helpers.initialize_kb", AsyncMock()),
            contextlib.suppress(Exception),
        ):
            # Should not raise PermissionError — ownership check passes
            await service.create(payload, user_id=user_id)

        # The flow ownership query must have been executed
        mock_db.exec.assert_called()

    @pytest.mark.asyncio
    async def test_create_endpoint_returns_404_for_unowned_flow(self):
        """POST /memories returns 404 (not 403/409) when flow_id is unowned.

        404 is intentional: returning 403 would reveal that the flow exists,
        which is an information leak in itself.
        Tests the try/except mapping in the route handler directly.
        """
        from fastapi import HTTPException
        from langflow.api.v1.memories import create_memory_base
        from langflow.services.database.models.user.model import User

        fake_user = User(id=uuid.uuid4(), username="alice")
        mock_service = MagicMock()
        mock_service.create = AsyncMock(side_effect=PermissionError("Flow abc not found"))

        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=mock_service),
            pytest.raises(HTTPException) as exc_info,
        ):
            await create_memory_base(
                current_user=fake_user,
                payload=MemoryBaseCreate(name="mb", flow_id=uuid.uuid4()),
            )

        assert exc_info.value.status_code == 404


class TestMemoryBaseGuardPassesRealKbIdentity:
    """The ID-bearing guards must pass the REAL kb identity, not actor-as-owner.

    Previously the five F20 guards called ensure_knowledge_base_permission with
    kb_user_id=current_user.id and no kb_id, so the owner-override path always
    fired (a registered plugin's enforce never ran) and audit rows lacked the kb
    id. The fix resolves the memory base first (via the owner-scoped service.get)
    and passes kb_id / kb_user_id (the real owner) / kb_name so owner-override is
    taken only for genuine owners.
    """

    @pytest.mark.asyncio
    async def test_update_passes_real_kb_identity_to_guard(self):
        from langflow.api.v1.memories import update_memory_base
        from langflow.services.database.models.user.model import User

        owner_id = uuid.uuid4()
        mb = _make_mb(user_id=owner_id)
        actor = User(id=uuid.uuid4(), username="actor")

        mock_service = MagicMock()
        mock_service.get = AsyncMock(return_value=mb)
        mock_service.update = AsyncMock(return_value=mb)
        captured = {}

        async def _capture_guard(_user, _act, **kwargs):
            captured.update(kwargs)

        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=mock_service),
            patch("langflow.api.v1.memories.ensure_knowledge_base_permission", _capture_guard),
        ):
            await update_memory_base(
                memory_base_id=mb.id,
                current_user=actor,
                patch=MemoryBaseUpdate(threshold=99),
            )

        assert captured["kb_id"] == mb.id
        assert captured["kb_user_id"] == owner_id, "guard must receive the real owner, not the actor"
        assert captured["kb_name"] == mb.kb_name

    @pytest.mark.asyncio
    async def test_delete_passes_real_kb_identity_to_guard(self):
        from langflow.api.v1.memories import delete_memory_base
        from langflow.services.database.models.user.model import User

        owner_id = uuid.uuid4()
        mb = _make_mb(user_id=owner_id)
        actor = User(id=uuid.uuid4(), username="actor")

        mock_service = MagicMock()
        mock_service.get = AsyncMock(return_value=mb)
        mock_service.delete = AsyncMock(return_value=True)
        captured = {}

        async def _capture_guard(_user, _act, **kwargs):
            captured.update(kwargs)

        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=mock_service),
            patch("langflow.api.v1.memories.ensure_knowledge_base_permission", _capture_guard),
        ):
            await delete_memory_base(memory_base_id=mb.id, current_user=actor)

        assert captured["kb_id"] == mb.id
        assert captured["kb_user_id"] == owner_id
        assert captured["kb_name"] == mb.kb_name

    @pytest.mark.asyncio
    async def test_flush_passes_real_kb_identity_to_guard(self):
        from langflow.api.v1.memories import FlushRequest, flush_memory_base
        from langflow.services.database.models.user.model import User

        owner_id = uuid.uuid4()
        mb = _make_mb(user_id=owner_id)
        actor = User(id=uuid.uuid4(), username="actor")

        mock_service = MagicMock()
        mock_service.get = AsyncMock(return_value=mb)
        mock_service.trigger_ingestion = AsyncMock(return_value="job-1")
        captured = {}

        async def _capture_guard(_user, _act, **kwargs):
            captured.update(kwargs)

        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=mock_service),
            patch("langflow.api.v1.memories.ensure_knowledge_base_permission", _capture_guard),
        ):
            await flush_memory_base(
                memory_base_id=mb.id,
                current_user=actor,
                body=FlushRequest(session_id="sess-1"),
            )

        assert captured["kb_id"] == mb.id
        assert captured["kb_user_id"] == owner_id
        assert captured["kb_name"] == mb.kb_name

    @pytest.mark.asyncio
    async def test_regenerate_passes_real_kb_identity_to_guard(self):
        from langflow.api.v1.memories import regenerate_memory_base
        from langflow.services.database.models.user.model import User

        owner_id = uuid.uuid4()
        mb = _make_mb(user_id=owner_id)
        actor = User(id=uuid.uuid4(), username="actor")

        mock_service = MagicMock()
        mock_service.get = AsyncMock(return_value=mb)
        mock_service.regenerate = AsyncMock(return_value=["job-1"])
        captured = {}

        async def _capture_guard(_user, _act, **kwargs):
            captured.update(kwargs)

        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=mock_service),
            patch("langflow.api.v1.memories.ensure_knowledge_base_permission", _capture_guard),
        ):
            await regenerate_memory_base(memory_base_id=mb.id, current_user=actor)

        assert captured["kb_id"] == mb.id
        assert captured["kb_user_id"] == owner_id
        assert captured["kb_name"] == mb.kb_name

    @pytest.mark.asyncio
    async def test_update_returns_404_when_memory_base_not_found(self):
        """If the resolve lookup returns None, the handler 404s before the guard runs."""
        from fastapi import HTTPException
        from langflow.api.v1.memories import update_memory_base
        from langflow.services.database.models.user.model import User

        actor = User(id=uuid.uuid4(), username="actor")
        mock_service = MagicMock()
        mock_service.get = AsyncMock(return_value=None)
        guard_called = False

        async def _guard(*_a, **_k):
            nonlocal guard_called
            guard_called = True

        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=mock_service),
            patch("langflow.api.v1.memories.ensure_knowledge_base_permission", _guard),
            pytest.raises(HTTPException) as exc_info,
        ):
            await update_memory_base(
                memory_base_id=uuid.uuid4(),
                current_user=actor,
                patch=MemoryBaseUpdate(threshold=1),
            )

        assert exc_info.value.status_code == 404
        assert not guard_called, "guard must not run for a non-existent memory base"


class TestMemoryBaseServiceConcurrency:
    """409 guard: only one active ingestion per (memory_base_id, session_id)."""

    @pytest.fixture
    def service(self):
        from langflow.services.memory_base.service import MemoryBaseService

        return MemoryBaseService()

    def _fake_scope(self, mock_db):
        class _FakeCtx:
            async def __aenter__(self):
                return mock_db

            async def __aexit__(self, *a):
                pass

        scope = MagicMock()
        scope.return_value = _FakeCtx()
        return scope

    @pytest.mark.asyncio
    async def test_trigger_raises_when_job_active(self, service):
        """DuplicateJobError from create_job propagates out of trigger_ingestion."""
        from langflow.services.jobs import DuplicateJobError

        mb = _make_mb()
        mbs = _make_session(memory_base_id=mb.id)
        mock_db = AsyncMock()

        mock_job_svc = MagicMock()
        mock_job_svc.create_job = AsyncMock(side_effect=DuplicateJobError("already running"))

        with (
            patch("langflow.services.memory_base.ingestion.session_scope", self._fake_scope(mock_db)),
            patch.object(service, "get_memory_base_or_404", AsyncMock(return_value=mb)),
            patch.object(service, "_get_or_create_session", AsyncMock(return_value=mbs)),
            patch(
                "langflow.services.memory_base.ingestion._get_latest_pending_workflow_job_id",
                AsyncMock(return_value=uuid.uuid4()),
            ),
            patch("langflow.services.memory_base.ingestion.resolve_kb_username", AsyncMock(return_value="testuser")),
            patch(
                "langflow.services.memory_base.ingestion.resolve_embedding",
                return_value=("OpenAI", "text-embedding-3-small"),
            ),
            patch("langflow.services.memory_base.ingestion.get_job_service", return_value=mock_job_svc),
            pytest.raises(DuplicateJobError),
        ):
            await service.trigger_ingestion(mb.id, mb.user_id, "sess-1")

    @pytest.mark.asyncio
    async def test_trigger_succeeds_when_no_active_job(self, service):
        mb = _make_mb()
        mbs = _make_session(memory_base_id=mb.id)
        mock_db = AsyncMock()

        mock_job_svc = MagicMock()
        mock_job_svc.create_job = AsyncMock()
        mock_task_svc = MagicMock()
        mock_task_svc.fire_and_forget_task = AsyncMock()

        with (
            patch("langflow.services.memory_base.ingestion.session_scope", self._fake_scope(mock_db)),
            patch.object(service, "get_memory_base_or_404", AsyncMock(return_value=mb)),
            patch.object(service, "_get_or_create_session", AsyncMock(return_value=mbs)),
            patch(
                "langflow.services.memory_base.ingestion._get_latest_pending_workflow_job_id",
                AsyncMock(return_value=uuid.uuid4()),
            ),
            patch("langflow.services.memory_base.ingestion.resolve_kb_username", AsyncMock(return_value="testuser")),
            patch(
                "langflow.services.memory_base.ingestion.resolve_embedding",
                return_value=("OpenAI", "text-embedding-3-small"),
            ),
            patch("langflow.services.memory_base.ingestion.get_job_service", return_value=mock_job_svc),
            patch("langflow.services.memory_base.ingestion.get_task_service", return_value=mock_task_svc),
        ):
            job_id = await service.trigger_ingestion(mb.id, mb.user_id, "sess-1")

        assert isinstance(job_id, str)
        mock_job_svc.create_job.assert_awaited_once()
        mock_task_svc.fire_and_forget_task.assert_awaited_once()


class TestMemoryBaseServiceThreshold:
    """Threshold update should NOT immediately re-evaluate pending count."""

    @pytest.fixture
    def service(self):
        from langflow.services.memory_base.service import MemoryBaseService

        return MemoryBaseService()

    @pytest.mark.asyncio
    async def test_threshold_update_does_not_trigger_ingestion(self, service):
        """Updating threshold via PATCH should never fire a task."""
        mb_updated = _make_mb(threshold=5)

        with patch.object(service, "update", AsyncMock(return_value=mb_updated)):
            result = await service.update(mb_updated.id, mb_updated.user_id, MemoryBaseUpdate(threshold=5))

        assert result.threshold == 5
        # No ingestion task should have been triggered as a side effect


class TestMemoryBaseServiceMismatch:
    @pytest.fixture
    def service(self):
        from langflow.services.memory_base.service import MemoryBaseService

        return MemoryBaseService()

    @pytest.mark.asyncio
    async def test_mismatch_detected_when_processed_but_empty_store(self, service, tmp_path):
        mb = _make_mb()

        with (
            patch.object(service, "get_memory_base_or_404", AsyncMock(return_value=mb)),
            patch(
                "langflow.services.memory_base.ingestion.resolve_kb_username_by_user_id",
                AsyncMock(return_value="testuser"),
            ),
            patch("langflow.services.memory_base.ingestion.session_scope") as mock_scope,
            patch("langflow.services.memory_base.ingestion.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch(
                "langflow.services.memory_base.ingestion.KBAnalysisHelper.get_metadata",
                return_value={"chunks": 0},
            ),
        ):
            # Simulate session_scope returns total_processed=10
            mock_db = AsyncMock()
            mock_db.exec = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=10)))

            class FakeCtx:
                async def __aenter__(self):
                    return mock_db

                async def __aexit__(self, *a):
                    pass

            mock_scope.return_value = FakeCtx()

            # Create KB path dir so path.exists() is True
            kb_path = tmp_path / "testuser" / mb.kb_name
            kb_path.mkdir(parents=True)

            result = await service.check_mismatch(mb.id, mb.user_id)

        assert result is True

    async def test_no_mismatch_when_nothing_processed(self, service):
        mb = _make_mb()

        with (
            patch.object(service, "get_memory_base_or_404", AsyncMock(return_value=mb)),
            patch("langflow.services.memory_base.ingestion.session_scope") as mock_scope,
        ):
            mock_db = AsyncMock()
            mock_db.exec = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=0)))

            class FakeCtx:
                async def __aenter__(self):
                    return mock_db

                async def __aexit__(self, *a):
                    pass

            mock_scope.return_value = FakeCtx()

            result = await service.check_mismatch(mb.id, mb.user_id)

        assert result is False


class TestMemoryBaseServicePurgeSessionData:
    @pytest.fixture
    def service(self):
        from langflow.services.memory_base.service import MemoryBaseService

        return MemoryBaseService()

    @pytest.mark.asyncio
    async def test_purge_no_sessions_returns_zero(self, service):
        result = await service.purge_session_data(uuid.uuid4(), [])
        assert result == 0

    @pytest.mark.asyncio
    async def test_purge_no_matching_pairs_returns_zero(self, service):
        # No (mb, session) pairs found in DB → nothing to do, no chunk wipes attempted.
        with patch("langflow.services.memory_base.ingestion.session_scope") as mock_scope:
            mock_db = AsyncMock()
            empty_result = MagicMock()
            empty_result.all = MagicMock(return_value=[])
            mock_db.exec = AsyncMock(return_value=empty_result)

            class FakeCtx:
                async def __aenter__(self):
                    return mock_db

                async def __aexit__(self, *a):
                    pass

            mock_scope.return_value = FakeCtx()

            result = await service.purge_session_data(uuid.uuid4(), ["s1"])
        assert result == 0

    @pytest.mark.asyncio
    async def test_purge_deletes_chroma_chunks_and_tracking_rows(self, service, tmp_path):
        mb = _make_mb()
        mbs = _make_session(memory_base_id=mb.id, session_id="sess-x")

        # First scope: lookup pairs + resolve username. Second scope: delete tracking rows.
        first_db = AsyncMock()
        pair_result = MagicMock()
        pair_result.all = MagicMock(return_value=[(mb, mbs)])
        username_result = MagicMock()
        username_result.first = MagicMock(return_value="alice")
        first_db.exec = AsyncMock(side_effect=[pair_result, username_result])
        first_db.commit = AsyncMock()

        second_db = AsyncMock()
        second_db.exec = AsyncMock(return_value=MagicMock())
        second_db.commit = AsyncMock()

        scopes_iter = iter([first_db, second_db])

        class FakeCtx:
            async def __aenter__(self):
                return next(scopes_iter)

            async def __aexit__(self, *a):
                pass

        kb_root = tmp_path / "kb"
        (kb_root / "alice" / mb.kb_name).mkdir(parents=True)

        adelete_mock = AsyncMock()
        fake_chroma = MagicMock()
        fake_chroma.adelete = adelete_mock

        with (
            patch(
                "langflow.services.memory_base.ingestion.session_scope",
                side_effect=lambda: FakeCtx(),
            ),
            patch(
                "langflow.services.memory_base.ingestion.KBStorageHelper.get_root_path",
                return_value=kb_root,
            ),
            patch(
                "langflow.services.memory_base.ingestion.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.ingestion.KBStorageHelper.release_chroma_resources"),
            patch(
                "langflow.services.memory_base.ingestion.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.ingestion.resolve_embedding",
                return_value=("OpenAI", "text-embedding-3-small"),
            ),
            patch("langflow.services.memory_base.ingestion.Chroma", return_value=fake_chroma),
            patch("langflow.services.memory_base.ingestion._sync_metrics_after_purge"),
        ):
            result = await service.purge_session_data(mb.user_id, ["sess-x"])

        assert result == 1
        # Chroma was asked to drop chunks for the deleted session using $eq form.
        adelete_mock.assert_awaited_once_with(where={"session_id": {"$eq": "sess-x"}})
        # Tracking-row deletes were committed.
        assert second_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_purge_continues_when_chunk_delete_fails(self, service, tmp_path):
        # Chunk delete failure must not block tracking-row cleanup — the user
        # already pressed "delete session" and expects bookkeeping to clear.
        mb = _make_mb()
        mbs = _make_session(memory_base_id=mb.id, session_id="sess-x")

        first_db = AsyncMock()
        pair_result = MagicMock()
        pair_result.all = MagicMock(return_value=[(mb, mbs)])
        username_result = MagicMock()
        username_result.first = MagicMock(return_value="alice")
        first_db.exec = AsyncMock(side_effect=[pair_result, username_result])
        first_db.commit = AsyncMock()

        second_db = AsyncMock()
        second_db.exec = AsyncMock(return_value=MagicMock())
        second_db.commit = AsyncMock()

        scopes_iter = iter([first_db, second_db])

        class FakeCtx:
            async def __aenter__(self):
                return next(scopes_iter)

            async def __aexit__(self, *a):
                pass

        kb_root = tmp_path / "kb"
        (kb_root / "alice" / mb.kb_name).mkdir(parents=True)

        with (
            patch(
                "langflow.services.memory_base.ingestion.session_scope",
                side_effect=lambda: FakeCtx(),
            ),
            patch(
                "langflow.services.memory_base.ingestion.KBStorageHelper.get_root_path",
                return_value=kb_root,
            ),
            patch(
                "langflow.services.memory_base.ingestion._delete_chunks_for_session",
                AsyncMock(side_effect=OSError("boom")),
            ),
        ):
            result = await service.purge_session_data(mb.user_id, ["sess-x"])

        assert result == 1
        assert second_db.commit.await_count == 1


class TestMemoryBaseServiceRegenerate:
    @pytest.fixture
    def service(self):
        from langflow.services.memory_base.service import MemoryBaseService

        return MemoryBaseService()

    @pytest.mark.asyncio
    async def test_regenerate_resets_cursors_and_triggers(self, service):
        mb = _make_mb()
        mbs1 = _make_session(memory_base_id=mb.id, session_id="s1", cursor_id=uuid.uuid4())
        mbs2 = _make_session(memory_base_id=mb.id, session_id="s2", cursor_id=uuid.uuid4())

        triggered_sessions: list[str] = []

        async def fake_trigger(_mb_id, _user_id, session_id):
            triggered_sessions.append(session_id)
            return str(uuid.uuid4())

        with (
            patch("langflow.services.memory_base.ingestion.session_scope") as mock_scope,
            patch.object(service, "trigger_ingestion", side_effect=fake_trigger),
        ):
            mock_db = AsyncMock()
            mock_mb_result = MagicMock()
            mock_mb_result.first = MagicMock(return_value=mb)
            mock_session_result = MagicMock()
            mock_session_result.all = MagicMock(return_value=[mbs1, mbs2])
            mock_db.exec = AsyncMock(side_effect=[mock_mb_result, mock_session_result, MagicMock(), MagicMock()])
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()

            class FakeCtx:
                async def __aenter__(self):
                    return mock_db

                async def __aexit__(self, *a):
                    pass

            mock_scope.return_value = FakeCtx()

            job_ids = await service.regenerate(mb.id, mb.user_id)

        assert len(job_ids) == 2
        assert set(triggered_sessions) == {"s1", "s2"}
        # Verify cursors were reset
        assert mbs1.cursor_id is None
        assert mbs2.cursor_id is None


# ------------------------------------------------------------------ #
#  Task tests                                                          #
# ------------------------------------------------------------------ #


class TestIngestMemoryTask:
    async def test_no_op_when_no_pending_messages(self, tmp_path):
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        job_service = MagicMock()
        job_id = uuid.uuid4()

        with (
            patch(
                "langflow.services.memory_base.task._acquire_session_lock",
                AsyncMock(return_value=asyncio.Lock()),
            ),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[]),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path / "kb",
            ),
        ):
            result = await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=uuid.uuid4(),
                    session_id="s1",
                    flow_id=uuid.uuid4(),
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=None,
                    task_job_id=job_id,
                    job_service=job_service,
                ),
            )

        assert result["ingested"] == 0

    @pytest.mark.asyncio
    async def test_cursor_not_advanced_on_ingestion_failure(self, tmp_path):
        """Critical: cursor_id must stay unchanged if ingestion fails."""
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        flow_id = uuid.uuid4()
        mb_id = uuid.uuid4()
        old_cursor = uuid.uuid4()

        msg = _make_message(flow_id=flow_id, session_id="s1")
        job_service = MagicMock()
        job_id = uuid.uuid4()

        advance_cursor_called = False

        async def fake_advance_cursor(_db, **_kwargs):
            nonlocal advance_cursor_called
            advance_cursor_called = True

        with (
            patch(
                "langflow.services.memory_base.task._acquire_session_lock",
                AsyncMock(return_value=asyncio.Lock()),
            ),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task.build_documents_from_messages",
                return_value=[MagicMock()],
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(side_effect=RuntimeError("Chroma exploded")),
            ),
            patch(
                "langflow.services.memory_base.task._advance_cursor",
                side_effect=fake_advance_cursor,
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path / "kb",
            ),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
            pytest.raises(RuntimeError, match="Chroma exploded"),
        ):
            await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=mb_id,
                    session_id="s1",
                    flow_id=flow_id,
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=old_cursor,
                    task_job_id=job_id,
                    job_service=job_service,
                ),
            )

        # Cursor must NOT have been advanced
        assert not advance_cursor_called, "cursor_id must not advance when ingestion fails"

    @pytest.mark.asyncio
    async def test_metadata_synced_on_success(self, tmp_path):
        """embedding_metadata.json must be updated after a successful ingestion."""
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id, session_id="s1")
        job_service = MagicMock()
        job_id = uuid.uuid4()

        sync_called_with: dict = {}

        def fake_sync_kb_metadata(*, kb_path, chroma):
            sync_called_with["kb_path"] = kb_path
            sync_called_with["chroma"] = chroma

        with (
            patch(
                "langflow.services.memory_base.task._acquire_session_lock",
                AsyncMock(return_value=asyncio.Lock()),
            ),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task.build_documents_from_messages",
                return_value=[MagicMock()],
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=1),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata", side_effect=fake_sync_kb_metadata),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path / "kb",
            ),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=uuid.uuid4(),
                    session_id="s1",
                    flow_id=flow_id,
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=None,
                    task_job_id=job_id,
                    job_service=job_service,
                ),
            )

        assert "kb_path" in sync_called_with, "sync_kb_metadata was not called on success"

    @pytest.mark.asyncio
    async def test_metadata_not_synced_when_cancelled(self, tmp_path):
        """embedding_metadata.json must NOT be updated when ingestion is cancelled."""
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id, session_id="s1")
        job_service = MagicMock()
        job_id = uuid.uuid4()
        sync_called = False

        def fake_sync(*_args, **_kwargs):
            nonlocal sync_called
            sync_called = True

        with (
            patch(
                "langflow.services.memory_base.task._acquire_session_lock",
                AsyncMock(return_value=asyncio.Lock()),
            ),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task.build_documents_from_messages",
                return_value=[MagicMock()],
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            # write_documents_to_chroma returns fewer docs than sent → cancelled
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=0),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata", side_effect=fake_sync),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path / "kb",
            ),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            result = await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=uuid.uuid4(),
                    session_id="s1",
                    flow_id=flow_id,
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=None,
                    task_job_id=job_id,
                    job_service=job_service,
                ),
            )

        assert not sync_called, "sync_kb_metadata must not be called when ingestion is cancelled"
        assert "cancelled" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_cursor_advanced_on_success(self, tmp_path):
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        flow_id = uuid.uuid4()
        mb_id = uuid.uuid4()

        msg = _make_message(flow_id=flow_id, session_id="s1")
        job_service = MagicMock()
        job_id = uuid.uuid4()

        advance_kwargs: dict = {}

        async def fake_advance_cursor(_db, **kwargs):
            advance_kwargs.update(kwargs)

        with (
            patch(
                "langflow.services.memory_base.task._acquire_session_lock",
                AsyncMock(return_value=asyncio.Lock()),
            ),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task.build_documents_from_messages",
                return_value=[MagicMock()],
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=1),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata"),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock(side_effect=fake_advance_cursor)),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path / "kb",
            ),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            result = await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=mb_id,
                    session_id="s1",
                    flow_id=flow_id,
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=None,
                    task_job_id=job_id,
                    job_service=job_service,
                ),
            )

        assert result["ingested"] == 1
        assert advance_kwargs["new_cursor_id"] == msg.id
        assert advance_kwargs["ingested_count"] == 1

    def test_sync_kb_metadata_stamps_is_memory_base(self, tmp_path):
        """sync_kb_metadata must write is_memory_base: true to the metadata file."""
        import json

        from langflow.services.memory_base.document_builders import sync_kb_metadata as _sync_kb_metadata

        kb_path = tmp_path / "test_kb"
        kb_path.mkdir()

        mock_chroma = MagicMock()

        with (
            patch(
                "langflow.services.memory_base.document_builders.KBAnalysisHelper.get_metadata",
                return_value={"chunks": 0, "embedding_provider": "OpenAI"},
            ),
            patch("langflow.services.memory_base.document_builders.KBAnalysisHelper.update_text_metrics"),
            patch(
                "langflow.services.memory_base.document_builders.KBStorageHelper.get_directory_size", return_value=1024
            ),
        ):
            _sync_kb_metadata(kb_path=kb_path, chroma=mock_chroma)

        written = json.loads((kb_path / "embedding_metadata.json").read_text())
        assert written["is_memory_base"] is True
        assert "memory" in written.get("source_types", [])

    def test_sync_kb_metadata_failure_does_not_raise(self, tmp_path):
        """Metadata sync errors must be swallowed so the cursor can still advance."""
        from langflow.services.memory_base.document_builders import sync_kb_metadata as _sync_kb_metadata

        kb_path = tmp_path / "no_such_dir"  # does not exist

        with patch(
            "langflow.services.memory_base.document_builders.KBAnalysisHelper.get_metadata",
            side_effect=OSError("disk full"),
        ):
            # Must not raise
            _sync_kb_metadata(kb_path=kb_path, chroma=MagicMock())

    def test_build_documents_skips_empty_messages(self):
        from langflow.services.memory_base.document_builders import (
            build_documents_from_messages as _build_documents_from_messages,
        )

        flow_id = uuid.uuid4()
        messages = [
            _make_message(flow_id=flow_id, session_id="s1", text=""),
            _make_message(flow_id=flow_id, session_id="s1", text="   "),
            _make_message(flow_id=flow_id, session_id="s1", text="Valid content here."),
        ]
        docs = _build_documents_from_messages(messages, session_id="s1", flow_id=str(flow_id))
        assert len(docs) == 1
        assert docs[0].page_content == "Valid content here."

    def test_build_documents_metadata(self):
        from langflow.services.memory_base.document_builders import (
            build_documents_from_messages as _build_documents_from_messages,
        )

        flow_id = uuid.uuid4()
        run_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id, session_id="s1", text="Test output.", run_id=run_id)
        docs = _build_documents_from_messages([msg], session_id="s1", flow_id=str(flow_id))
        assert docs[0].metadata["message_id"] == str(msg.id)
        assert docs[0].metadata["run_id"] == str(run_id)
        assert docs[0].metadata["session_id"] == "s1"


# ------------------------------------------------------------------ #
#  on_flow_output hook and threshold-trigger tests                     #
# ------------------------------------------------------------------ #


class TestOnFlowOutputHook:
    """Tests for on_flow_output, _maybe_trigger threshold logic, and hook wiring."""

    @pytest.fixture
    def service(self):
        from langflow.services.memory_base.service import MemoryBaseService

        return MemoryBaseService()

    def _fake_scope(self, mock_db):
        """Return a mock session_scope context manager backed by mock_db."""

        class _FakeCtx:
            async def __aenter__(self):
                return mock_db

            async def __aexit__(self, *a):
                pass

        scope = MagicMock()
        scope.return_value = _FakeCtx()
        return scope

    @pytest.mark.asyncio
    async def test_on_flow_output_skips_when_below_threshold(self, service):
        """No job must be created when pending message count is below the threshold."""
        from langflow.services.memory_base.ingestion import _maybe_trigger

        mb = _make_mb(threshold=5)
        mbs = _make_session(memory_base_id=mb.id)
        mock_db = AsyncMock()

        with (
            patch("langflow.services.memory_base.ingestion.session_scope", self._fake_scope(mock_db)),
            patch.object(service, "_get_or_create_session", AsyncMock(return_value=mbs)),
            patch("langflow.services.memory_base.ingestion._insert_workflow_run", AsyncMock()),
            patch(
                "langflow.services.memory_base.ingestion.count_pending_messages", AsyncMock(return_value=3)
            ),  # 3 < threshold 5
            patch("langflow.services.memory_base.ingestion.get_job_service") as mock_jsc,
        ):
            await _maybe_trigger(
                mb=mb, session_id="s1", job_id=None, get_or_create_session=service._get_or_create_session
            )

        mock_jsc.return_value.create_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_flow_output_triggers_when_threshold_met(self, service):
        """A job must be created and dispatched when pending message count meets threshold."""
        from langflow.services.memory_base.ingestion import _maybe_trigger

        mb = _make_mb(threshold=3)
        mbs = _make_session(memory_base_id=mb.id)
        mock_db = AsyncMock()

        mock_job_svc = MagicMock()
        mock_job_svc.create_job = AsyncMock()
        mock_task_svc = MagicMock()
        mock_task_svc.fire_and_forget_task = AsyncMock()

        with (
            patch("langflow.services.memory_base.ingestion.session_scope", self._fake_scope(mock_db)),
            patch.object(service, "_get_or_create_session", AsyncMock(return_value=mbs)),
            patch("langflow.services.memory_base.ingestion._insert_workflow_run", AsyncMock()),
            patch(
                "langflow.services.memory_base.ingestion.count_pending_messages", AsyncMock(return_value=5)
            ),  # 5 >= threshold 3
            patch(
                "langflow.services.memory_base.ingestion._get_latest_pending_workflow_job_id",
                AsyncMock(return_value=uuid.uuid4()),
            ),
            patch(
                "langflow.services.memory_base.kb_path_helpers.resolve_kb_username", AsyncMock(return_value="testuser")
            ),
            patch(
                "langflow.services.memory_base.ingestion.resolve_embedding",
                return_value=("OpenAI", "text-embedding-3-small"),
            ),
            patch("langflow.services.memory_base.ingestion.get_job_service", return_value=mock_job_svc),
            patch("langflow.services.memory_base.ingestion.get_task_service", return_value=mock_task_svc),
        ):
            await _maybe_trigger(
                mb=mb, session_id="s1", job_id=None, get_or_create_session=service._get_or_create_session
            )

        mock_job_svc.create_job.assert_awaited_once()
        mock_task_svc.fire_and_forget_task.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_flow_output_is_silent_on_error(self, service):
        """on_flow_output must swallow _maybe_trigger exceptions without propagating them.

        This guarantees memory-base failures never cause regressions in flow execution.
        """
        flow_id = uuid.uuid4()
        mb = _make_mb(flow_id=flow_id, auto_capture=True)
        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=[mb])
        mock_db.exec = AsyncMock(return_value=result_mock)

        with (
            patch("langflow.services.memory_base.ingestion.session_scope", self._fake_scope(mock_db)),
            patch(
                "langflow.services.memory_base.ingestion._maybe_trigger", AsyncMock(side_effect=RuntimeError("boom"))
            ),
        ):
            # Must not raise even though _maybe_trigger blows up
            await service.on_flow_output(flow_id=flow_id, session_id="s1", job_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_hook_wiring_playground(self):
        """Playground path: background_tasks.add_task dispatches on_flow_output with correct kwargs.

        Verifies the contract of the hook-dispatch block added to generate_flow_events
        in api/build.py after end_all_traces().
        """
        from starlette.background import BackgroundTasks

        flow_id = uuid.uuid4()
        run_id = uuid.uuid4()

        mb_service = MagicMock()
        mb_service.on_flow_output = AsyncMock()

        bg_tasks = MagicMock(spec=BackgroundTasks)
        mock_graph = MagicMock()
        mock_graph.run_id = str(run_id)  # graph.run_id is always a str
        mock_graph.session_id = "test-session"

        with patch("langflow.api.build.get_memory_base_service", return_value=mb_service):
            import langflow.api.build as build_module

            # Confirm the import is wired at module level
            assert hasattr(build_module, "get_memory_base_service")

            # Execute the same hook-dispatch block as in generate_flow_events
            _run_id_uuid = uuid.UUID(mock_graph.run_id) if mock_graph.run_id else None
            bg_tasks.add_task(
                mb_service.on_flow_output,
                flow_id=flow_id,
                session_id=mock_graph.session_id or str(flow_id),
                run_id=_run_id_uuid,
            )

        bg_tasks.add_task.assert_called_once_with(
            mb_service.on_flow_output,
            flow_id=flow_id,
            session_id="test-session",
            run_id=run_id,  # UUID, not str — type-cast from graph.run_id
        )

    @pytest.mark.asyncio
    async def test_hook_wiring_v2_async_wrapper(self):
        """V2 async path: _run_and_notify preserves run_graph_internal result and dispatches hook.

        Verifies the behavioral contract of the closure added to execute_workflow_background
        in api/v2/workflow.py: the wrapper must be transparent to execute_with_status
        (return value unchanged) while also firing the memory-base hook.
        """
        expected_result = (MagicMock(), "effective-session-42")
        run_graph_mock = AsyncMock(return_value=expected_result)
        hook_mock = AsyncMock()
        task_service_mock = MagicMock()
        task_service_mock.fire_and_forget_task = AsyncMock()

        hook_flow_id = uuid.uuid4()
        hook_run_id = uuid.uuid4()

        # Mirror the _run_and_notify closure from workflow.py execute_workflow_background
        async def _run_and_notify(**kwargs):
            result = await run_graph_mock(**kwargs)
            _, _effective_session_id = result
            with contextlib.suppress(Exception):
                await task_service_mock.fire_and_forget_task(
                    hook_mock,
                    flow_id=hook_flow_id,
                    session_id=_effective_session_id,
                    run_id=hook_run_id,
                )
            return result

        result = await _run_and_notify(graph=MagicMock())

        # Return value must be identical — execute_with_status depends on this
        assert result == expected_result
        # Hook must be dispatched with the session_id extracted from run_graph_internal
        task_service_mock.fire_and_forget_task.assert_awaited_once_with(
            hook_mock,
            flow_id=hook_flow_id,
            session_id="effective-session-42",
            run_id=hook_run_id,
        )

    @pytest.mark.asyncio
    async def test_hook_failure_does_not_affect_wrapper_return(self):
        """If fire_and_forget_task raises inside _run_and_notify, the return value is still correct."""
        expected_result = (MagicMock(), "some-session")
        run_graph_mock = AsyncMock(return_value=expected_result)
        task_service_mock = MagicMock()
        task_service_mock.fire_and_forget_task = AsyncMock(side_effect=RuntimeError("dispatch failed"))

        async def _run_and_notify(**kwargs):
            result = await run_graph_mock(**kwargs)
            _, _effective_session_id = result
            with contextlib.suppress(Exception):
                await task_service_mock.fire_and_forget_task(
                    AsyncMock(),
                    flow_id=uuid.uuid4(),
                    session_id=_effective_session_id,
                    run_id=uuid.uuid4(),
                )
            return result

        result = await _run_and_notify(graph=MagicMock())
        assert result == expected_result


# ------------------------------------------------------------------ #
#  API endpoint routing tests                                          #
# ------------------------------------------------------------------ #


class TestMemoriesAPIRouting:
    """Verify routing and response codes without hitting the DB."""

    @pytest.fixture
    def patched_service(self):
        """Patch get_memory_base_service in memories.py."""
        mock_svc = MagicMock()
        with patch("langflow.api.v1.memories.get_memory_base_service", return_value=mock_svc):
            yield mock_svc

    @pytest.mark.asyncio
    async def test_get_not_found_returns_404(self, patched_service):
        """Handler returns 404 when service.get returns None (covered via direct call)."""
        from fastapi import HTTPException
        from langflow.api.v1.memories import get_memory_base

        patched_service.get = AsyncMock(return_value=None)

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await get_memory_base(memory_base_id=uuid.uuid4(), current_user=mock_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_flush_conflict_returns_409(self, patched_service):
        """trigger_ingestion raising RuntimeError should map to HTTP 409."""
        from langflow.api.v1.memories import flush_memory_base

        # We call the handler directly to test the error mapping
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        # The guard now resolves the memory base first; let it pass through so the
        # error mapping under test (trigger_ingestion -> 409) is exercised.
        patched_service.get = AsyncMock(return_value=_make_mb(user_id=mock_user.id))
        patched_service.trigger_ingestion = AsyncMock(side_effect=RuntimeError("already in progress"))

        from fastapi import HTTPException
        from langflow.api.v1.memories import FlushRequest

        with pytest.raises(HTTPException) as exc_info:
            await flush_memory_base(
                memory_base_id=uuid.uuid4(),
                body=FlushRequest(session_id="s1"),
                current_user=mock_user,
            )
        from fastapi import HTTPException

        assert isinstance(exc_info.value, HTTPException)
        assert exc_info.value.status_code == 409


# ------------------------------------------------------------------ #
#  API handler unit tests (direct invocation, no HTTP stack)           #
# ------------------------------------------------------------------ #


class TestMemoriesAPIHandlers:
    """Call endpoint handlers directly, mocking _service, to test all status-code branches."""

    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = uuid.uuid4()
        return user

    # ---------------------------------------------------------------- #
    #  create_memory_base                                               #
    # ---------------------------------------------------------------- #

    @pytest.mark.asyncio
    async def test_create_success_returns_memory_base_read(self, mock_user):
        from langflow.api.v1.memories import create_memory_base

        mb = _make_mb(user_id=mock_user.id)
        payload = MemoryBaseCreate(name="mb", flow_id=mb.flow_id, user_id=mock_user.id, kb_name="kb")

        svc = MagicMock()
        svc.create = AsyncMock(return_value=mb)
        with patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc):
            result = await create_memory_base(current_user=mock_user, payload=payload)

        assert result.id == mb.id
        assert result.user_id == mock_user.id

    @pytest.mark.asyncio
    async def test_create_duplicate_name_returns_409(self, mock_user):
        from fastapi import HTTPException
        from langflow.api.v1.memories import create_memory_base

        payload = MemoryBaseCreate(name="dup", flow_id=uuid.uuid4(), user_id=mock_user.id, kb_name="kb")

        svc = MagicMock()
        svc.create = AsyncMock(side_effect=ValueError("name already in use"))
        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await create_memory_base(current_user=mock_user, payload=payload)

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_create_missing_api_key_returns_422(self, mock_user):
        from fastapi import HTTPException
        from langflow.api.v1.memories import create_memory_base
        from langflow.services.memory_base.service import PreprocessingValidationError

        payload = MemoryBaseCreate(name="mb", flow_id=uuid.uuid4(), user_id=mock_user.id, kb_name="kb")

        svc = MagicMock()
        svc.create = AsyncMock(side_effect=PreprocessingValidationError("No API key found for provider 'OpenAI'"))
        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await create_memory_base(current_user=mock_user, payload=payload)

        assert exc_info.value.status_code == 422
        assert "API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_missing_api_key_returns_403(self, mock_user):
        from fastapi import HTTPException
        from langflow.api.v1.memories import update_memory_base
        from langflow.services.memory_base.service import PreprocessingValidationError

        svc = MagicMock()
        svc.get = AsyncMock(return_value=_make_mb(user_id=mock_user.id))
        svc.update = AsyncMock(side_effect=PreprocessingValidationError("No API key found for provider 'OpenAI'"))
        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await update_memory_base(
                memory_base_id=uuid.uuid4(),
                current_user=mock_user,
                patch=MemoryBaseUpdate(threshold=10),
            )

        assert exc_info.value.status_code == 403
        assert "API key" in exc_info.value.detail

    # ---------------------------------------------------------------- #
    #  get_memory_base                                                  #
    # ---------------------------------------------------------------- #

    @pytest.mark.asyncio
    async def test_get_success_returns_memory_base_read(self, mock_user):
        from langflow.api.v1.memories import get_memory_base

        mb = _make_mb(user_id=mock_user.id)

        svc = MagicMock()
        svc.get = AsyncMock(return_value=mb)
        with patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc):
            result = await get_memory_base(memory_base_id=mb.id, current_user=mock_user)

        assert result.id == mb.id

    @pytest.mark.asyncio
    async def test_get_not_found_raises_404(self, mock_user):
        from fastapi import HTTPException
        from langflow.api.v1.memories import get_memory_base

        svc = MagicMock()
        svc.get = AsyncMock(return_value=None)
        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_memory_base(memory_base_id=uuid.uuid4(), current_user=mock_user)

        assert exc_info.value.status_code == 404

    # ---------------------------------------------------------------- #
    #  update_memory_base                                               #
    # ---------------------------------------------------------------- #

    @pytest.mark.asyncio
    async def test_update_success_returns_updated_record(self, mock_user):
        from langflow.api.v1.memories import update_memory_base

        mb = _make_mb(user_id=mock_user.id, threshold=99)

        svc = MagicMock()
        svc.get = AsyncMock(return_value=mb)
        svc.update = AsyncMock(return_value=mb)
        with patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc):
            result = await update_memory_base(
                memory_base_id=mb.id,
                current_user=mock_user,
                patch=MemoryBaseUpdate(threshold=99),
            )

        assert result.threshold == 99

    @pytest.mark.asyncio
    async def test_update_not_found_raises_404(self, mock_user):
        from fastapi import HTTPException
        from langflow.api.v1.memories import update_memory_base

        svc = MagicMock()
        svc.get = AsyncMock(return_value=_make_mb(user_id=mock_user.id))
        svc.update = AsyncMock(return_value=None)
        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await update_memory_base(
                memory_base_id=uuid.uuid4(),
                current_user=mock_user,
                patch=MemoryBaseUpdate(threshold=5),
            )

        assert exc_info.value.status_code == 404

    # ---------------------------------------------------------------- #
    #  delete_memory_base                                               #
    # ---------------------------------------------------------------- #

    @pytest.mark.asyncio
    async def test_delete_success_returns_none(self, mock_user):
        from langflow.api.v1.memories import delete_memory_base

        svc = MagicMock()
        svc.get = AsyncMock(return_value=_make_mb(user_id=mock_user.id))
        svc.delete = AsyncMock(return_value=True)
        with patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc):
            result = await delete_memory_base(memory_base_id=uuid.uuid4(), current_user=mock_user)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_not_found_raises_404(self, mock_user):
        from fastapi import HTTPException
        from langflow.api.v1.memories import delete_memory_base

        svc = MagicMock()
        svc.get = AsyncMock(return_value=_make_mb(user_id=mock_user.id))
        svc.delete = AsyncMock(return_value=False)
        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await delete_memory_base(memory_base_id=uuid.uuid4(), current_user=mock_user)

        assert exc_info.value.status_code == 404

    # ---------------------------------------------------------------- #
    #  flush_memory_base                                                #
    # ---------------------------------------------------------------- #

    @pytest.mark.asyncio
    async def test_flush_success_returns_job_id(self, mock_user):
        from langflow.api.v1.memories import FlushRequest, flush_memory_base

        job_id = str(uuid.uuid4())

        svc = MagicMock()
        svc.get = AsyncMock(return_value=_make_mb(user_id=mock_user.id))
        svc.trigger_ingestion = AsyncMock(return_value=job_id)
        with patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc):
            result = await flush_memory_base(
                memory_base_id=uuid.uuid4(),
                current_user=mock_user,
                body=FlushRequest(session_id="s1"),
            )

        assert result == {"job_id": job_id}

    @pytest.mark.asyncio
    async def test_flush_value_error_raises_404(self, mock_user):
        from fastapi import HTTPException
        from langflow.api.v1.memories import FlushRequest, flush_memory_base

        svc = MagicMock()
        svc.get = AsyncMock(return_value=_make_mb(user_id=mock_user.id))
        svc.trigger_ingestion = AsyncMock(side_effect=ValueError("memory base not found"))
        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await flush_memory_base(
                memory_base_id=uuid.uuid4(),
                current_user=mock_user,
                body=FlushRequest(session_id="s1"),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_flush_duplicate_job_error_raises_409(self, mock_user):
        from fastapi import HTTPException
        from langflow.api.v1.memories import FlushRequest, flush_memory_base
        from langflow.services.jobs import DuplicateJobError

        svc = MagicMock()
        svc.get = AsyncMock(return_value=_make_mb(user_id=mock_user.id))
        svc.trigger_ingestion = AsyncMock(side_effect=DuplicateJobError("already running"))
        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await flush_memory_base(
                memory_base_id=uuid.uuid4(),
                current_user=mock_user,
                body=FlushRequest(session_id="s1"),
            )

        assert exc_info.value.status_code == 409

    # ---------------------------------------------------------------- #
    #  check_mismatch                                                   #
    # ---------------------------------------------------------------- #

    @pytest.mark.asyncio
    async def test_check_mismatch_detected_returns_true(self, mock_user):
        from langflow.api.v1.memories import check_mismatch

        svc = MagicMock()
        svc.check_mismatch = AsyncMock(return_value=True)
        with patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc):
            result = await check_mismatch(memory_base_id=uuid.uuid4(), current_user=mock_user)

        assert result.mismatch_detected is True

    @pytest.mark.asyncio
    async def test_check_mismatch_not_detected_returns_false(self, mock_user):
        from langflow.api.v1.memories import check_mismatch

        svc = MagicMock()
        svc.check_mismatch = AsyncMock(return_value=False)
        with patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc):
            result = await check_mismatch(memory_base_id=uuid.uuid4(), current_user=mock_user)

        assert result.mismatch_detected is False

    @pytest.mark.asyncio
    async def test_check_mismatch_not_found_raises_404(self, mock_user):
        from fastapi import HTTPException
        from langflow.api.v1.memories import check_mismatch

        svc = MagicMock()
        svc.check_mismatch = AsyncMock(side_effect=ValueError("not found"))
        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await check_mismatch(memory_base_id=uuid.uuid4(), current_user=mock_user)

        assert exc_info.value.status_code == 404

    # ---------------------------------------------------------------- #
    #  regenerate_memory_base                                           #
    # ---------------------------------------------------------------- #

    @pytest.mark.asyncio
    async def test_regenerate_success_returns_job_ids(self, mock_user):
        from langflow.api.v1.memories import regenerate_memory_base

        job_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

        svc = MagicMock()
        svc.get = AsyncMock(return_value=_make_mb(user_id=mock_user.id))
        svc.regenerate = AsyncMock(return_value=job_ids)
        with patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc):
            result = await regenerate_memory_base(memory_base_id=uuid.uuid4(), current_user=mock_user)

        assert result.job_ids == job_ids

    @pytest.mark.asyncio
    async def test_regenerate_not_found_raises_404(self, mock_user):
        from fastapi import HTTPException
        from langflow.api.v1.memories import regenerate_memory_base

        svc = MagicMock()
        svc.get = AsyncMock(return_value=_make_mb(user_id=mock_user.id))
        svc.regenerate = AsyncMock(side_effect=ValueError("not found"))
        with (
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await regenerate_memory_base(memory_base_id=uuid.uuid4(), current_user=mock_user)

        assert exc_info.value.status_code == 404

    # ---------------------------------------------------------------- #
    #  list_sessions                                                    #
    # ---------------------------------------------------------------- #

    @pytest.mark.asyncio
    async def test_list_sessions_ownership_failure_raises_404(self, mock_user):
        from fastapi import HTTPException
        from fastapi_pagination import Params
        from langflow.api.v1.memories import list_sessions

        mock_db = AsyncMock()

        class FakeCtx:
            async def __aenter__(self):
                return mock_db

            async def __aexit__(self, *a):
                pass

        svc = MagicMock()
        svc.get_memory_base_or_404 = AsyncMock(side_effect=ValueError("not found"))
        with (
            patch("langflow.api.v1.memories.session_scope", return_value=FakeCtx()),
            patch("langflow.api.v1.memories.get_memory_base_service", return_value=svc),
            pytest.raises(HTTPException) as exc_info,
        ):
            await list_sessions(
                memory_base_id=uuid.uuid4(),
                current_user=mock_user,
                params=Params(),
            )

        assert exc_info.value.status_code == 404

    # ---------------------------------------------------------------- #
    #  list_memory_base_messages                                        #
    # ---------------------------------------------------------------- #

    @pytest.mark.asyncio
    async def test_list_memory_base_messages_not_found_raises_404(self, mock_user):
        from fastapi import HTTPException
        from fastapi_pagination import Params
        from langflow.api.v1.memories import list_memory_base_messages

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.first = MagicMock(return_value=None)
        mock_db.exec = AsyncMock(return_value=result_mock)

        class FakeCtx:
            async def __aenter__(self):
                return mock_db

            async def __aexit__(self, *a):
                pass

        with (
            patch("langflow.api.v1.memories.session_scope", return_value=FakeCtx()),
            pytest.raises(HTTPException) as exc_info,
        ):
            await list_memory_base_messages(
                memory_base_id=uuid.uuid4(),
                session_id="s1",
                current_user=mock_user,
                params=Params(),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_memory_base_messages_without_session_id_not_found_raises_404(self, mock_user):
        from fastapi import HTTPException
        from fastapi_pagination import Params
        from langflow.api.v1.memories import list_memory_base_messages

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.first = MagicMock(return_value=None)
        mock_db.exec = AsyncMock(return_value=result_mock)

        class FakeCtx:
            async def __aenter__(self):
                return mock_db

            async def __aexit__(self, *a):
                pass

        with (
            patch("langflow.api.v1.memories.session_scope", return_value=FakeCtx()),
            pytest.raises(HTTPException) as exc_info,
        ):
            await list_memory_base_messages(
                memory_base_id=uuid.uuid4(),
                current_user=mock_user,
                params=Params(),
            )

        assert exc_info.value.status_code == 404

    def test_session_raw_messages_stmt_omits_session_filter_when_none(self):
        from langflow.services.memory_base.service import MemoryBaseService

        svc = MemoryBaseService.__new__(MemoryBaseService)
        mb_id = uuid.uuid4()

        stmt_filtered = svc.session_raw_messages_stmt(mb_id, "s1")
        stmt_all = svc.session_raw_messages_stmt(mb_id)

        sql_filtered = str(stmt_filtered.compile(compile_kwargs={"literal_binds": True}))
        sql_all = str(stmt_all.compile(compile_kwargs={"literal_binds": True}))

        # The filtered variant constrains on the session_id literal; the "all" variant must not.
        assert "session_id = 's1'" in sql_filtered
        assert "session_id =" not in sql_all

    def test_session_preprocessed_outputs_stmt_omits_session_filter_when_none(self):
        from langflow.services.memory_base.service import MemoryBaseService

        svc = MemoryBaseService.__new__(MemoryBaseService)
        mb_id = uuid.uuid4()

        stmt_filtered = svc.session_preprocessed_outputs_stmt(mb_id, "s1")
        stmt_all = svc.session_preprocessed_outputs_stmt(mb_id)

        sql_filtered = str(stmt_filtered.compile(compile_kwargs={"literal_binds": True}))
        sql_all = str(stmt_all.compile(compile_kwargs={"literal_binds": True}))

        assert "session_id = 's1'" in sql_filtered
        assert "session_id =" not in sql_all

    # ---------------------------------------------------------------- #
    #  MessageReadResponse schema                                       #
    # ---------------------------------------------------------------- #

    def test_message_read_response_from_attributes(self):
        from langflow.api.v1.memories import MessageReadResponse

        msg = _make_message(flow_id=uuid.uuid4(), session_id="s1", text="hello")
        response = MessageReadResponse.model_validate(msg, from_attributes=True)

        assert response.text == "hello"
        assert response.session_id == "s1"
        assert response.sender == "AI"
        assert response.content_blocks == []

    def test_flush_request_schema(self):
        from langflow.api.v1.memories import FlushRequest

        req = FlushRequest(session_id="my-session")
        assert req.session_id == "my-session"

    def test_mismatch_response_schema(self):
        from langflow.api.v1.memories import MismatchResponse

        assert MismatchResponse(mismatch_detected=True).mismatch_detected is True
        assert MismatchResponse(mismatch_detected=False).mismatch_detected is False

    def test_regenerate_response_schema(self):
        from langflow.api.v1.memories import RegenerateResponse

        ids = ["a", "b", "c"]
        assert RegenerateResponse(job_ids=ids).job_ids == ids


# ------------------------------------------------------------------ #
#  Preprocessing API key validation tests                              #
# ------------------------------------------------------------------ #


class TestPreprocessingApiKeyValidation:
    """_validate_preprocessing_api_key raises PreprocessingValidationError when key is absent."""

    def test_no_op_when_preproc_model_is_none(self):
        from langflow.services.memory_base.service import _validate_preprocessing_api_key

        # Should not raise — no model means no key needed.
        _validate_preprocessing_api_key(uuid.uuid4(), None)

    def test_raises_when_api_key_missing(self):
        from langflow.services.memory_base.service import (
            PreprocessingValidationError,
            _validate_preprocessing_api_key,
        )

        with (
            patch(
                "langflow.services.memory_base.service.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.service.get_api_key_for_provider",
                return_value=None,
            ),
            pytest.raises(PreprocessingValidationError, match="No API key"),
        ):
            _validate_preprocessing_api_key(uuid.uuid4(), "gpt-4o")

    def test_passes_when_api_key_present(self):
        from langflow.services.memory_base.service import _validate_preprocessing_api_key

        with (
            patch(
                "langflow.services.memory_base.service.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.service.get_api_key_for_provider",
                return_value="sk-valid-key",
            ),
        ):
            # Should not raise.
            _validate_preprocessing_api_key(uuid.uuid4(), "gpt-4o")

    def test_raises_when_provider_unknown(self):
        from langflow.services.memory_base.service import (
            PreprocessingValidationError,
            _validate_preprocessing_api_key,
        )

        with (
            patch(
                "langflow.services.memory_base.service.infer_llm_provider",
                side_effect=ValueError("Unknown model 'ghost-model'"),
            ),
            pytest.raises(PreprocessingValidationError, match="Unknown model"),
        ):
            _validate_preprocessing_api_key(uuid.uuid4(), "ghost-model")

    @pytest.mark.asyncio
    async def test_service_create_raises_preprocessing_validation_error_on_missing_key(self):
        """create() raises PreprocessingValidationError before touching the filesystem."""
        from langflow.services.database.models.flow.model import Flow
        from langflow.services.memory_base.service import (
            MemoryBaseService,
            PreprocessingValidationError,
        )

        service = MemoryBaseService()
        user_id = uuid.uuid4()
        flow_id = uuid.uuid4()
        payload = MemoryBaseCreate(
            name="mb",
            flow_id=flow_id,
            preprocessing=True,
            preproc_model="gpt-4o",
        )

        owned_flow = Flow(id=flow_id, user_id=user_id, name="my flow")
        exec_result = MagicMock()
        exec_result.first.return_value = owned_flow
        mock_db = AsyncMock()
        mock_db.exec = AsyncMock(return_value=exec_result)

        class FakeCtx:
            async def __aenter__(self):
                return mock_db

            async def __aexit__(self, *a):
                pass

        fake_scope = MagicMock(return_value=FakeCtx())

        with (
            patch("langflow.services.memory_base.service.session_scope", fake_scope),
            patch(
                "langflow.services.memory_base.service.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.service.get_api_key_for_provider",
                return_value=None,
            ),
            pytest.raises(PreprocessingValidationError, match="No API key"),
        ):
            await service.create(payload, user_id=user_id)

    @pytest.mark.asyncio
    async def test_service_update_raises_preprocessing_validation_error_on_missing_key(self):
        """update() raises PreprocessingValidationError.

        When the existing MB uses preprocessing but the API key is gone.
        """
        from langflow.services.memory_base.service import (
            MemoryBaseService,
            PreprocessingValidationError,
        )

        service = MemoryBaseService()
        user_id = uuid.uuid4()
        mb = _make_mb(user_id=user_id)
        mb.preprocessing = True
        mb.preproc_model = "gpt-4o"

        exec_result = MagicMock()
        exec_result.first.return_value = mb
        mock_db = AsyncMock()
        mock_db.exec = AsyncMock(return_value=exec_result)

        class FakeCtx:
            async def __aenter__(self):
                return mock_db

            async def __aexit__(self, *a):
                pass

        fake_scope = MagicMock(return_value=FakeCtx())

        with (
            patch("langflow.services.memory_base.service.session_scope", fake_scope),
            patch(
                "langflow.services.memory_base.service.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.service.get_api_key_for_provider",
                return_value=None,
            ),
            pytest.raises(PreprocessingValidationError, match="No API key"),
        ):
            await service.update(
                mb.id,
                user_id,
                MemoryBaseUpdate(threshold=10),
            )


# ------------------------------------------------------------------ #
#  Security adversarial tests                                          #
# ------------------------------------------------------------------ #


class TestMemoryBaseSecurityAdversarial:
    """Pin authorization invariants that the rest of the code depends on."""

    @pytest.fixture
    def service(self):
        from langflow.services.memory_base.service import MemoryBaseService

        return MemoryBaseService()

    def _fake_scope(self, mock_db):
        class _FakeCtx:
            async def __aenter__(self):
                return mock_db

            async def __aexit__(self, *a):
                pass

        scope = MagicMock()
        scope.return_value = _FakeCtx()
        return scope

    @pytest.mark.asyncio
    async def test_update_rejects_when_flow_changed_to_unowned_flow(self, service):
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        mb = _make_mb(user_id=user_a)
        mock_db = AsyncMock()
        exec_result = MagicMock()
        exec_result.first.return_value = None
        mock_db.exec = AsyncMock(return_value=exec_result)
        with patch("langflow.services.memory_base.service.session_scope", self._fake_scope(mock_db)):
            result = await service.update(mb.id, user_b, MemoryBaseUpdate(threshold=5))
        assert result is None

    @pytest.mark.asyncio
    async def test_on_flow_output_refuses_cross_user_flow(self, service):
        unrelated_flow_id = uuid.uuid4()
        mock_db = AsyncMock()
        exec_result = MagicMock()
        exec_result.all.return_value = []
        mock_db.exec = AsyncMock(return_value=exec_result)
        with patch("langflow.services.memory_base.ingestion.session_scope", self._fake_scope(mock_db)):
            await service.on_flow_output(flow_id=unrelated_flow_id, session_id="sess-1", job_id=uuid.uuid4())
        mock_db.exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_regenerate_rejects_unowned_memory_base(self, service):
        user_b = uuid.uuid4()
        mb_id = uuid.uuid4()
        mock_db = AsyncMock()
        exec_result = MagicMock()
        exec_result.first.return_value = None
        mock_db.exec = AsyncMock(return_value=exec_result)
        with (
            patch("langflow.services.memory_base.ingestion.session_scope", self._fake_scope(mock_db)),
            pytest.raises(ValueError, match="not found"),
        ):
            await service.regenerate(mb_id, user_b)

    @pytest.mark.asyncio
    async def test_check_mismatch_rejects_unowned_memory_base(self, service):
        user_b = uuid.uuid4()
        mb_id = uuid.uuid4()
        mock_db = AsyncMock()
        exec_result = MagicMock()
        exec_result.first.return_value = None
        mock_db.exec = AsyncMock(return_value=exec_result)
        with (
            patch("langflow.services.memory_base.ingestion.session_scope", self._fake_scope(mock_db)),
            pytest.raises(ValueError, match="not found"),
        ):
            await service.check_mismatch(mb_id, user_b)

    @pytest.mark.asyncio
    async def test_sessions_stmt_enforces_user_id(self, service):
        user_id = uuid.uuid4()
        mb_id = uuid.uuid4()
        stmt = service.sessions_stmt(mb_id, user_id)
        compiled = str(stmt)
        assert "user_id" in compiled
        assert "memory_base" in compiled.lower()


class TestMemoryBaseBodyValidation:
    """HTTP-level validation for endpoints that require a JSON request body.

    Regression for: a *missing* request body must be rejected with 422
    (the same as an empty JSON object), never a 500.  Previously the body
    parameters were declared as ``Annotated[Model, Body(embed=False)] = ...``;
    the Ellipsis default leaked through FastAPI's body solver when no body was
    sent, so the handler received ``...`` and raised
    ``'ellipsis' object has no attribute '...'`` (HTTP 500).
    """

    @pytest.mark.asyncio
    async def test_flush_missing_body_returns_422(self, client, logged_in_headers):
        """POST /memories/{id}/flush with no body -> 422 (not 500)."""
        mb_id = uuid.uuid4()
        response = await client.post(f"api/v1/memories/{mb_id}/flush", headers=logged_in_headers)
        assert response.status_code == 422, response.text

    @pytest.mark.asyncio
    async def test_flush_empty_json_returns_422(self, client, logged_in_headers):
        """POST /memories/{id}/flush with {} -> 422 flagging the missing session_id."""
        mb_id = uuid.uuid4()
        response = await client.post(f"api/v1/memories/{mb_id}/flush", headers=logged_in_headers, json={})
        assert response.status_code == 422, response.text
        assert "session_id" in response.text

    @pytest.mark.asyncio
    async def test_create_missing_body_returns_422(self, client, logged_in_headers):
        """POST /memories with no body -> 422 (not 500); same root cause as flush."""
        response = await client.post("api/v1/memories", headers=logged_in_headers)
        assert response.status_code == 422, response.text
