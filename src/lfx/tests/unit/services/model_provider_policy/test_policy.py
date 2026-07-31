from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, patch

import pytest
from lfx.base.models.unified_models import get_embeddings, get_llm
from lfx.services.model_provider_policy import (
    BaseModelProviderPolicyService,
    ModelProviderPolicyContext,
    ModelProviderPolicyError,
    ModelProviderPolicyPurpose,
    ModelProviderPolicyService,
    ModelProviderPolicySnapshot,
    reset_current_model_provider_policy_context,
    set_current_model_provider_policy_context,
)


def _restricted_snapshot(*allowed: str) -> ModelProviderPolicySnapshot:
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id="user-1"),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"openai", "anthropic", "ollama"}),
        allowed_provider_ids=frozenset(allowed),
    )


class _CountingPolicy(BaseModelProviderPolicyService):
    def __init__(self) -> None:
        super().__init__()
        self.evaluations = 0
        self.set_ready()

    def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
        _ = (context, purpose)
        self.evaluations += 1
        return candidate_provider_ids


def test_default_service_allows_every_candidate():
    service = ModelProviderPolicyService()

    snapshot = service.resolve(
        context=ModelProviderPolicyContext(user_id="user-1"),
        candidate_provider_ids=frozenset({"openai", "anthropic"}),
        purpose=ModelProviderPolicyPurpose.USE,
    )

    assert snapshot.allowed_provider_ids == frozenset({"openai", "anthropic"})
    assert snapshot.allows("OpenAI")
    assert snapshot.allows("Anthropic")


def test_default_service_allows_every_registered_provider():
    from lfx.base.models.provider_registry import get_registry_snapshot

    service = ModelProviderPolicyService()
    provider_ids = get_registry_snapshot().provider_ids

    snapshot = service.resolve(
        context=ModelProviderPolicyContext(user_id="user-1"),
        candidate_provider_ids=provider_ids,
        purpose=ModelProviderPolicyPurpose.USE,
    )

    assert snapshot.allowed_provider_ids == provider_ids


def test_default_service_applies_install_wide_approved_provider_ceiling():
    service = ModelProviderPolicyService()
    service.set_approved_provider_ids({"openai"}, version=7)

    snapshot = service.resolve(
        context=ModelProviderPolicyContext(user_id="user-1"),
        candidate_provider_ids=frozenset({"openai", "anthropic"}),
        purpose=ModelProviderPolicyPurpose.USE,
    )

    assert snapshot.allowed_provider_ids == frozenset({"openai"})
    assert service.approved_provider_ids == frozenset({"openai"})
    assert service.policy_version == 7


def test_empty_approved_provider_ceiling_preserves_allow_all_default():
    service = ModelProviderPolicyService()
    service.set_approved_provider_ids({"openai"})
    service.set_approved_provider_ids(set())

    snapshot = service.resolve(
        context=ModelProviderPolicyContext(user_id="user-1"),
        candidate_provider_ids=frozenset({"openai", "anthropic"}),
        purpose=ModelProviderPolicyPurpose.CONFIGURE,
    )

    assert snapshot.allowed_provider_ids == frozenset({"openai", "anthropic"})
    assert not service.approved_provider_ids


def test_default_service_rejects_a_stale_persisted_policy_version():
    service = ModelProviderPolicyService()
    service.set_approved_provider_ids({"openai"}, version=5)

    changed = service.set_approved_provider_ids({"anthropic"}, version=4)

    assert changed is False
    assert service.approved_provider_ids == frozenset({"openai"})
    assert service.policy_version == 5


def test_default_service_fails_closed_until_policy_source_recovers():
    service = ModelProviderPolicyService()
    service.set_approved_provider_ids({"openai", "anthropic"}, version=5)

    assert service.fail_closed() is True
    denied = service.resolve(
        context=ModelProviderPolicyContext(user_id="user-1"),
        candidate_provider_ids=frozenset({"openai", "anthropic"}),
        purpose=ModelProviderPolicyPurpose.USE,
    )

    assert denied.allowed_provider_ids == frozenset()
    assert service.policy_source_available is False

    # A same-version refresh is enough to recover because the persisted state
    # may not have changed while the store was temporarily unavailable.
    assert service.set_approved_provider_ids({"openai", "anthropic"}, version=5) is True
    recovered = service.resolve(
        context=ModelProviderPolicyContext(user_id="user-1"),
        candidate_provider_ids=frozenset({"openai", "anthropic"}),
        purpose=ModelProviderPolicyPurpose.USE,
    )
    assert recovered.allowed_provider_ids == frozenset({"openai", "anthropic"})
    assert service.policy_source_available is True


async def test_async_resolver_caches_until_invalidation():
    service = ModelProviderPolicyService()
    kwargs = {
        "context": ModelProviderPolicyContext(user_id="user-1"),
        "candidate_provider_ids": frozenset({"openai", "anthropic"}),
        "purpose": ModelProviderPolicyPurpose.USE,
    }

    first = await service.aresolve(**kwargs)
    cached = await service.aresolve(**kwargs)
    service.invalidate()
    refreshed = await service.aresolve(**kwargs)

    assert cached is first
    assert refreshed == first
    assert refreshed is not first


def test_sync_resolver_caches_until_invalidation():
    service = _CountingPolicy()
    kwargs = {
        "context": ModelProviderPolicyContext(user_id="user-1"),
        "candidate_provider_ids": frozenset({"openai"}),
        "purpose": ModelProviderPolicyPurpose.USE,
    }

    first = service.resolve(**kwargs)
    cached = service.resolve(**kwargs)
    service.invalidate()
    refreshed = service.resolve(**kwargs)

    assert cached is first
    assert refreshed == first
    assert refreshed is not first
    assert service.evaluations == 2


def test_snapshot_cache_separates_users():
    service = _CountingPolicy()
    candidates = frozenset({"openai"})

    first_user = service.resolve(
        context=ModelProviderPolicyContext(user_id="user-1"),
        candidate_provider_ids=candidates,
        purpose=ModelProviderPolicyPurpose.USE,
    )
    second_user = service.resolve(
        context=ModelProviderPolicyContext(user_id="user-2"),
        candidate_provider_ids=candidates,
        purpose=ModelProviderPolicyPurpose.USE,
    )
    first_user_cached = service.resolve(
        context=ModelProviderPolicyContext(user_id="user-1"),
        candidate_provider_ids=candidates,
        purpose=ModelProviderPolicyPurpose.USE,
    )

    assert first_user_cached is first_user
    assert second_user is not first_user
    assert service.evaluations == 2


def test_snapshot_cache_expires_after_ttl(monkeypatch):
    from lfx.services.model_provider_policy import base as policy_base

    now = [100.0]
    monkeypatch.setattr(policy_base.time, "monotonic", lambda: now[0])
    service = _CountingPolicy()
    service.SNAPSHOT_CACHE_TTL_SECONDS = 5.0
    kwargs = {
        "context": ModelProviderPolicyContext(user_id="user-1"),
        "candidate_provider_ids": frozenset({"openai"}),
        "purpose": ModelProviderPolicyPurpose.USE,
    }

    first = service.resolve(**kwargs)
    now[0] += 4.0
    cached = service.resolve(**kwargs)
    now[0] += 1.0
    refreshed = service.resolve(**kwargs)

    assert cached is first
    assert refreshed == first
    assert refreshed is not first
    assert service.evaluations == 2


def test_snapshot_cache_evicts_least_recently_used_entry():
    service = _CountingPolicy()
    service.SNAPSHOT_CACHE_MAX_SIZE = 2
    candidates = frozenset({"openai"})

    def _resolve(scope: str) -> ModelProviderPolicySnapshot:
        return service.resolve(
            context=ModelProviderPolicyContext(user_id="user-1", attributes={"scope": scope}),
            candidate_provider_ids=candidates,
            purpose=ModelProviderPolicyPurpose.USE,
        )

    first = _resolve("first")
    _resolve("second")
    assert _resolve("first") is first
    _resolve("third")
    assert _resolve("first") is first
    _resolve("second")

    assert service.evaluations == 4


def test_unhashable_policy_attributes_bypass_snapshot_cache():
    class UnhashableAttribute:
        __hash__ = None

    service = _CountingPolicy()
    kwargs = {
        "context": ModelProviderPolicyContext(attributes={"request": UnhashableAttribute()}),
        "candidate_provider_ids": frozenset({"openai"}),
        "purpose": ModelProviderPolicyPurpose.USE,
    }

    first = service.resolve(**kwargs)
    second = service.resolve(**kwargs)

    assert second == first
    assert second is not first
    assert service.evaluations == 2


async def test_async_policy_hook_shares_cache_and_honors_invalidation():
    class AsyncPolicy(_CountingPolicy):
        def __init__(self) -> None:
            super().__init__()
            self.async_evaluations = 0

        async def aget_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
            _ = (context, purpose)
            self.async_evaluations += 1
            return candidate_provider_ids

    service = AsyncPolicy()
    kwargs = {
        "context": ModelProviderPolicyContext(user_id="user-1"),
        "candidate_provider_ids": frozenset({"openai"}),
        "purpose": ModelProviderPolicyPurpose.USE,
    }

    first = await service.aresolve(**kwargs)
    cached = await service.aresolve(**kwargs)
    assert service.resolve(**kwargs) is first
    service.invalidate()
    refreshed = await service.aresolve(**kwargs)

    assert cached is first
    assert refreshed == first
    assert refreshed is not first
    assert service.async_evaluations == 2
    assert service.evaluations == 0


def test_snapshot_cache_lazily_initializes_for_legacy_subclass():
    class LegacyPolicy(BaseModelProviderPolicyService):
        def __init__(self) -> None:
            self.evaluations = 0
            self.set_ready()

        def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
            _ = (context, purpose)
            self.evaluations += 1
            return candidate_provider_ids

    service = LegacyPolicy()
    kwargs = {
        "context": ModelProviderPolicyContext(user_id="user-1"),
        "candidate_provider_ids": frozenset({"openai"}),
        "purpose": ModelProviderPolicyPurpose.USE,
    }

    first = service.resolve(**kwargs)
    cached = service.resolve(**kwargs)
    service.invalidate()
    refreshed = service.resolve(**kwargs)

    assert cached is first
    assert refreshed is not first
    assert service.evaluations == 2


def test_snapshot_cache_preserves_policy_attribute_types():
    class TypedAttributePolicy(BaseModelProviderPolicyService):
        def __init__(self) -> None:
            super().__init__()
            self.evaluations = 0
            self.set_ready()

        def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
            _ = purpose
            self.evaluations += 1
            if context.attributes["flag"] is True:
                return candidate_provider_ids
            return frozenset()

    service = TypedAttributePolicy()
    candidates = frozenset({"openai"})

    allowed = service.resolve(
        context=ModelProviderPolicyContext(attributes={"flag": True}),
        candidate_provider_ids=candidates,
        purpose=ModelProviderPolicyPurpose.USE,
    )
    denied = service.resolve(
        context=ModelProviderPolicyContext(attributes={"flag": 1}),
        candidate_provider_ids=candidates,
        purpose=ModelProviderPolicyPurpose.USE,
    )

    assert allowed.allows("openai")
    assert not denied.allows("openai")
    assert service.evaluations == 2


def test_service_distinguishes_use_and_configure_purposes():
    class PurposePolicy(BaseModelProviderPolicyService):
        def __init__(self) -> None:
            super().__init__()
            self.set_ready()

        def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
            _ = context
            if purpose is ModelProviderPolicyPurpose.USE:
                return candidate_provider_ids
            return frozenset()

    service = PurposePolicy()

    assert service.is_allowed("openai", ModelProviderPolicyPurpose.USE)
    assert not service.is_allowed("openai", ModelProviderPolicyPurpose.CONFIGURE)


def test_is_allowed_canonicalizes_alias_and_uses_ambient_context():
    class CapturingPolicy(BaseModelProviderPolicyService):
        def __init__(self) -> None:
            super().__init__()
            self.calls = []

        def get_allowed_provider_ids(self, *, context, candidate_provider_ids, purpose):
            self.calls.append((context, candidate_provider_ids, purpose))
            return candidate_provider_ids

    service = CapturingPolicy()
    token = set_current_model_provider_policy_context(
        user_id="user-1",
        attributes={"workspace_id": "workspace-1"},
    )
    try:
        allowed = service.is_allowed("IBM watsonx.ai", ModelProviderPolicyPurpose.USE)
    finally:
        reset_current_model_provider_policy_context(token)

    assert allowed is True
    context, candidates, purpose = service.calls[0]
    assert context.user_id == "user-1"
    assert context.attributes["workspace_id"] == "workspace-1"
    assert candidates == frozenset({"ibm-watsonx"})
    assert purpose is ModelProviderPolicyPurpose.USE


def test_default_resolution_preserves_unknown_legacy_provider_names(monkeypatch):
    from lfx.services.model_provider_policy import utils

    service = ModelProviderPolicyService()
    monkeypatch.setattr("lfx.services.deps.get_model_provider_policy_service", lambda: service)

    snapshot = utils.resolve_model_provider_policy(
        user_id="user-1",
        providers=["Legacy Custom Provider"],
        purpose=ModelProviderPolicyPurpose.USE,
    )

    assert snapshot.allows("Legacy Custom Provider")


def test_default_resolution_preserves_non_sluggable_legacy_provider(monkeypatch):
    from lfx.services.model_provider_policy import utils

    service = ModelProviderPolicyService()
    monkeypatch.setattr("lfx.services.deps.get_model_provider_policy_service", lambda: service)

    snapshot = utils.resolve_model_provider_policy(
        user_id="user-1",
        providers=["🔥"],
        purpose=ModelProviderPolicyPurpose.USE,
    )

    assert len(snapshot.candidate_provider_ids) == 1
    assert next(iter(snapshot.candidate_provider_ids)).startswith("legacy-")
    assert snapshot.allows("🔥")


def test_request_principal_attributes_follow_only_the_matching_user(monkeypatch):
    from lfx.services.model_provider_policy import utils

    service = ModelProviderPolicyService()
    monkeypatch.setattr("lfx.services.deps.get_model_provider_policy_service", lambda: service)
    token = set_current_model_provider_policy_context(
        user_id="user-1",
        attributes={"is_superuser": True},
    )
    try:
        matching = utils.resolve_model_provider_policy(
            user_id="user-1",
            providers=["OpenAI"],
            purpose=ModelProviderPolicyPurpose.USE,
        )
        different = utils.resolve_model_provider_policy(
            user_id="user-2",
            providers=["OpenAI"],
            purpose=ModelProviderPolicyPurpose.USE,
        )
    finally:
        reset_current_model_provider_policy_context(token)

    assert matching.context.attributes["is_superuser"] is True
    assert dict(different.context.attributes) == {}


def test_watsonx_legacy_alias_resolves_to_stable_provider_id():
    from lfx.base.models.provider_registry import provider_id_for

    assert provider_id_for("IBM watsonx.ai") == "ibm-watsonx"
    assert _restricted_snapshot("openai").allows("IBM watsonx.ai") is False


def test_snapshot_is_immutable_and_cannot_allow_non_candidates():
    snapshot = _restricted_snapshot("openai")

    with pytest.raises(FrozenInstanceError):
        snapshot.purpose = ModelProviderPolicyPurpose.CONFIGURE  # type: ignore[misc]

    with pytest.raises(ValueError, match="subset"):
        ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(),
            purpose=ModelProviderPolicyPurpose.DISCOVER,
            candidate_provider_ids=frozenset({"openai"}),
            allowed_provider_ids=frozenset({"openai", "anthropic"}),
        )


def test_policy_error_for_non_sluggable_selector_is_generic_and_opaque():
    from lfx.base.models.provider_registry import resolve_provider_id

    selector = "🔥"
    opaque_provider_id = resolve_provider_id(selector)
    snapshot = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id="user-1"),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({opaque_provider_id}),
        allowed_provider_ids=frozenset(),
    )

    with pytest.raises(ModelProviderPolicyError) as exc_info:
        snapshot.require(selector)

    assert str(exc_info.value) == "The requested model provider is not available"
    assert exc_info.value.provider_id == opaque_provider_id
    assert exc_info.value.provider_id.startswith("legacy-")
    assert selector not in exc_info.value.provider_id


def test_context_attributes_are_deeply_immutable():
    attributes = {"roles": ["member"], "scope": {"workspace": "one"}}
    context = ModelProviderPolicyContext(attributes=attributes)
    attributes["roles"].append("admin")

    assert context.attributes["roles"] == ("member",)
    with pytest.raises(TypeError):
        context.attributes["scope"]["workspace"] = "two"


def test_runtime_denies_provider_before_credential_resolution(monkeypatch):
    credential_lookup_called = False

    def _credential_lookup(*_args, **_kwargs):
        nonlocal credential_lookup_called
        credential_lookup_called = True
        return "secret"

    monkeypatch.setattr("lfx.base.models.unified_models.get_api_key_for_provider", _credential_lookup)

    with pytest.raises(ModelProviderPolicyError) as exc_info:
        get_llm(
            [{"name": "claude-test", "provider": "Anthropic", "metadata": {}}],
            user_id="user-1",
            provider_policy=_restricted_snapshot("openai"),
        )

    assert exc_info.value.code == "policy_blocked"
    assert credential_lookup_called is False


def test_embedding_runtime_denies_provider_before_credential_resolution(monkeypatch):
    credential_lookup_called = False

    def _credential_lookup(*_args, **_kwargs):
        nonlocal credential_lookup_called
        credential_lookup_called = True
        return "secret"

    monkeypatch.setattr("lfx.base.models.unified_models.get_api_key_for_provider", _credential_lookup)

    with pytest.raises(ModelProviderPolicyError):
        get_embeddings(
            [{"name": "embed-test", "provider": "Anthropic", "metadata": {}}],
            user_id="user-1",
            provider_policy=_restricted_snapshot("openai"),
        )

    assert credential_lookup_called is False


@pytest.mark.parametrize("runtime", [get_llm, get_embeddings], ids=["llm", "embeddings"])
def test_legacy_non_sluggable_runtime_denied_before_credential_resolution(monkeypatch, runtime):
    from lfx.base.models.provider_registry import resolve_provider_id

    selector = "🔥"
    credential_lookup_called = False

    def _credential_lookup(*_args, **_kwargs):
        nonlocal credential_lookup_called
        credential_lookup_called = True
        return "secret"

    monkeypatch.setattr("lfx.base.models.unified_models.get_api_key_for_provider", _credential_lookup)
    provider_id = resolve_provider_id(selector)
    policy = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id="user-1"),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({provider_id}),
        allowed_provider_ids=frozenset(),
    )

    with pytest.raises(ModelProviderPolicyError):
        runtime(
            [{"name": "legacy-test", "provider": selector, "metadata": {}}],
            user_id="user-1",
            provider_policy=policy,
        )

    assert credential_lookup_called is False


@pytest.mark.parametrize(
    ("runtime", "message"),
    [
        (get_llm, "selected model is missing a provider"),
        (get_embeddings, "selected embedding model is missing a provider"),
    ],
    ids=["llm", "embeddings"],
)
def test_whitespace_only_provider_uses_friendly_missing_provider_error(runtime, message):
    with pytest.raises(ValueError, match=message):
        runtime(
            [{"name": "legacy-test", "provider": " \t ", "metadata": {}}],
            user_id="user-1",
        )


async def test_standalone_model_component_denied_before_build_method(monkeypatch):
    """Saved legacy model nodes cannot bypass policy by skipping the unified-model helpers."""
    from lfx.base.models.model import LCModelComponent
    from lfx.io import Output

    build_called = False

    class StandaloneOpenAIComponent(LCModelComponent):
        display_name = "OpenAI"
        outputs = [Output(name="model", display_name="Model", method="build_model")]

        def build_model(self):
            nonlocal build_called
            build_called = True
            return "should-not-run"

    def _deny(*, user_id, providers, purpose, attributes=None):
        candidate_ids = frozenset(providers)
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id=user_id, attributes=attributes or {}),
            purpose=purpose,
            candidate_provider_ids=candidate_ids,
            allowed_provider_ids=frozenset(),
        )

    monkeypatch.setattr("lfx.services.model_provider_policy.utils.resolve_model_provider_policy", _deny)
    component = StandaloneOpenAIComponent(_user_id="user-1")

    with pytest.raises(ModelProviderPolicyError):
        await component.build_results()

    assert build_called is False


def test_standalone_model_component_denied_before_dynamic_configuration(monkeypatch):
    from lfx.base.models.model import LCModelComponent

    class StandaloneAnthropicComponent(LCModelComponent):
        display_name = "Anthropic"

    purposes = []

    def _deny(*, user_id, providers, purpose, attributes=None):
        purposes.append(purpose)
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id=user_id, attributes=attributes or {}),
            purpose=purpose,
            candidate_provider_ids=frozenset(providers),
            allowed_provider_ids=frozenset(),
        )

    monkeypatch.setattr("lfx.services.model_provider_policy.utils.resolve_model_provider_policy", _deny)
    component = StandaloneAnthropicComponent(_user_id="user-1")

    with pytest.raises(ModelProviderPolicyError):
        component.require_model_provider_policy(ModelProviderPolicyPurpose.CONFIGURE)

    assert purposes == [ModelProviderPolicyPurpose.CONFIGURE]


def test_delegating_model_component_skips_outer_provider_gate(monkeypatch):
    from lfx.base.models.model import LCModelComponent

    class UnifiedSelectorComponent(LCModelComponent):
        display_name = "Language Model"
        model_provider_policy_mode = "delegate"

    resolver = AsyncMock()
    monkeypatch.setattr("lfx.services.model_provider_policy.utils.resolve_model_provider_policy", resolver)

    UnifiedSelectorComponent(_user_id="user-1").require_model_provider_policy(ModelProviderPolicyPurpose.CONFIGURE)

    resolver.assert_not_called()


def test_known_llm_provider_ignores_spoofed_runtime_metadata(monkeypatch):
    requested_classes = []
    captured = {}

    class _OllamaChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    def _get_model_class(class_name):
        requested_classes.append(class_name)
        return _OllamaChatModel

    monkeypatch.setattr("lfx.base.models.unified_models.get_model_class", _get_model_class)
    monkeypatch.setattr("lfx.base.models.unified_models.get_api_key_for_provider", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("lfx.base.models.unified_models.get_all_variables_for_provider", lambda *_args: {})

    result = get_llm(
        [
            {
                "name": "llama-test",
                "provider": "Ollama",
                "metadata": {
                    "model_class": "ChatAnthropic",
                    "model_name_param": "anthropic_model",
                    "api_key_param": "anthropic_api_key",  # pragma: allowlist secret
                    "base_url_param": "anthropic_base_url",
                },
            }
        ],
        user_id="user-1",
        ollama_base_url="http://ollama.test",
        provider_policy=_restricted_snapshot("ollama"),
    )

    assert isinstance(result, _OllamaChatModel)
    assert requested_classes == ["ChatOllama"]
    assert captured == {
        "model": "llama-test",
        "streaming": False,
        "api_key": None,
        "base_url": "http://ollama.test",
    }


def test_known_embedding_provider_ignores_spoofed_runtime_metadata(monkeypatch):
    from lfx.base.models.unified_models import instantiation

    requested_classes = []
    captured = {}

    class _OllamaEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    def _get_embedding_class(class_name):
        requested_classes.append(class_name)
        return _OllamaEmbeddings

    monkeypatch.setattr("lfx.base.models.unified_models.get_embedding_class", _get_embedding_class)
    monkeypatch.setattr("lfx.base.models.unified_models.get_api_key_for_provider", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("lfx.base.models.unified_models.get_all_variables_for_provider", lambda *_args: {})
    monkeypatch.setattr(instantiation, "_get_configured_embedding_providers", lambda *_args: [])

    result = get_embeddings(
        [
            {
                "name": "nomic-embed-text",
                "provider": "Ollama",
                "metadata": {
                    "embedding_class": "OpenAIEmbeddings",
                    "param_mapping": {
                        "model": "deployment",
                        "api_key": "openai_api_key",  # pragma: allowlist secret
                        "base_url": "openai_api_base",
                    },
                },
            }
        ],
        user_id="user-1",
        ollama_base_url="http://ollama.test",
        provider_policy=_restricted_snapshot("ollama"),
    )

    assert isinstance(result.embeddings, _OllamaEmbeddings)
    assert requested_classes == ["OllamaEmbeddings"]
    assert captured == {"model": "nomic-embed-text", "base_url": "http://ollama.test"}


def test_default_runtime_policy_preserves_unknown_legacy_llm_provider(monkeypatch):
    """Unknown saved providers must reach the historical runtime validation path."""
    from lfx.services import deps

    captured = {}

    class _LegacyChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(deps, "get_model_provider_policy_service", lambda: ModelProviderPolicyService())
    monkeypatch.setattr(
        "lfx.base.models.unified_models.get_api_key_for_provider",
        lambda *_args, **_kwargs: "legacy-key",  # pragma: allowlist secret
    )
    monkeypatch.setattr(
        "lfx.base.models.unified_models.get_model_class",
        lambda _class_name: _LegacyChatModel,
    )

    result = get_llm(
        [
            {
                "name": "legacy-model",
                "provider": "Legacy Custom Provider",
                "metadata": {
                    "model_class": "LegacyChatModel",
                    "model_name_param": "model",
                    "api_key_param": "api_key",  # pragma: allowlist secret
                },
            }
        ],
        user_id="user-1",
    )

    assert isinstance(result, _LegacyChatModel)
    assert captured == {  # pragma: allowlist secret
        "model": "legacy-model",
        "streaming": False,
        "api_key": "legacy-key",  # pragma: allowlist secret
    }


def test_default_runtime_policy_preserves_unknown_legacy_embedding_provider(monkeypatch):
    """The allow-all default must not turn an old embedding selection into a policy denial."""
    from lfx.base.models.unified_models import instantiation
    from lfx.services import deps

    captured = {}

    class _LegacyEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(deps, "get_model_provider_policy_service", lambda: ModelProviderPolicyService())
    monkeypatch.setattr(
        "lfx.base.models.unified_models.get_api_key_for_provider",
        lambda *_args, **_kwargs: "legacy-key",
    )
    monkeypatch.setattr(
        "lfx.base.models.unified_models.get_embedding_class",
        lambda _class_name: _LegacyEmbeddings,
    )
    monkeypatch.setattr(instantiation, "_get_provider_embedding_model_names", lambda *_args: [])

    result = get_embeddings(
        [
            {
                "name": "legacy-embedding-model",
                "provider": "Legacy Custom Provider",
                "metadata": {
                    "embedding_class": "LegacyEmbeddings",
                    "param_mapping": {
                        "model": "model",
                        "api_key": "api_key",  # pragma: allowlist secret
                    },
                },
            }
        ],
        user_id=None,
    )

    assert isinstance(result.embeddings, _LegacyEmbeddings)
    assert captured == {
        "model": "legacy-embedding-model",
        "api_key": "legacy-key",  # pragma: allowlist secret
    }


@pytest.mark.parametrize(
    ("option_builder", "model_type", "openai_model"),
    [
        ("get_language_model_options", "llm", "gpt-test"),
        ("get_embedding_model_options", "embeddings", "text-embedding-test"),
    ],
)
def test_model_options_filter_denied_dynamic_sources(option_builder, model_type, openai_model):
    from lfx.base.models.unified_models import model_catalog

    catalog = [
        {
            "provider": "OpenAI",
            "icon": "OpenAI",
            "models": [{"model_name": openai_model, "metadata": {"default": True, "model_type": model_type}}],
        },
        {
            "provider": "Anthropic",
            "icon": "Anthropic",
            "models": [{"model_name": "blocked-static", "metadata": {"default": True, "model_type": model_type}}],
        },
    ]
    live_enabled_providers = []
    policy = _restricted_snapshot("openai")
    fetch_enabled = AsyncMock(return_value={"OpenAI", "Anthropic"})

    def _replace_with_live_models(groups, _user_id, enabled_providers, *_args, **_kwargs):
        live_enabled_providers.append(set(enabled_providers))
        groups.append(
            {
                "provider": "Anthropic",
                "models": [{"model_name": "blocked-live", "metadata": {"default": True, "model_type": model_type}}],
            }
        )

    def _inject_custom(groups, *_args, **_kwargs):
        groups.append(
            {
                "provider": "Anthropic",
                "models": [{"model_name": "blocked-custom", "metadata": {"default": True, "model_type": model_type}}],
            }
        )

    with (
        patch.object(model_catalog, "get_unified_models_detailed", return_value=catalog),
        patch.object(model_catalog, "_get_model_status", new=AsyncMock(return_value=(set(), set()))),
        patch.object(
            model_catalog,
            "_fetch_enabled_providers_for_user",
            new=fetch_enabled,
        ),
        patch.object(model_catalog, "replace_with_live_models", side_effect=_replace_with_live_models),
        patch.object(model_catalog, "inject_custom_enabled_models", side_effect=_inject_custom),
    ):
        options = getattr(model_catalog, option_builder)(
            user_id="00000000-0000-0000-0000-000000000001",
            provider_policy=policy,
        )

    fetch_enabled.assert_awaited_once_with(
        "00000000-0000-0000-0000-000000000001",
        provider_policy=policy,
    )
    assert live_enabled_providers == [{"OpenAI"}]
    assert {(option["provider"], option["name"]) for option in options} == {("OpenAI", openai_model)}
