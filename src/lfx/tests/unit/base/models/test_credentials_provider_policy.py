"""Provider-policy regressions for credential-backed availability checks."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

from lfx.base.models.unified_models import credentials
from lfx.services import model_provider_policy
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicyPurpose,
    ModelProviderPolicySnapshot,
)


async def test_enabled_provider_lookup_always_intersects_configure_policy(monkeypatch):
    class FakeDatabaseVariableService:
        get_all = AsyncMock(
            return_value=[
                SimpleNamespace(name="OPENAI_API_KEY"),
                SimpleNamespace(name="ANTHROPIC_API_KEY"),
            ]
        )
        get_variable_object = AsyncMock(return_value=SimpleNamespace(value="encrypted"))

    variable_module = ModuleType("langflow.services.variable.service")
    variable_module.DatabaseVariableService = FakeDatabaseVariableService
    monkeypatch.setitem(sys.modules, "langflow.services.variable.service", variable_module)

    service = FakeDatabaseVariableService()
    call_order = []

    @asynccontextmanager
    async def fake_session_scope():
        call_order.append("session")
        yield SimpleNamespace()

    monkeypatch.setattr(credentials, "session_scope", fake_session_scope)
    monkeypatch.setattr(credentials, "get_variable_service", lambda: service)
    monkeypatch.setattr(credentials, "get_model_providers", lambda: ["OpenAI", "Anthropic"])
    monkeypatch.setattr(
        credentials,
        "get_model_provider_variable_mapping",
        lambda: {"OpenAI": "OPENAI_API_KEY", "Anthropic": "ANTHROPIC_API_KEY"},
    )
    monkeypatch.setattr(
        credentials,
        "get_provider_all_variables",
        lambda provider: [
            {
                "variable_key": "OPENAI_API_KEY" if provider == "OpenAI" else "ANTHROPIC_API_KEY",
                "required": True,
            }
        ],
    )
    monkeypatch.setattr(
        credentials,
        "_validate_and_get_enabled_providers",
        lambda _variables, provider_candidates: set(provider_candidates),
    )

    resolved_purposes = []
    resolved_attributes = []

    async def resolve_configure_policy(*, user_id, providers, purpose, attributes=None):
        _ = providers
        call_order.append("policy")
        resolved_purposes.append(purpose)
        resolved_attributes.append(attributes)
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id=user_id),
            purpose=purpose,
            candidate_provider_ids=frozenset({"openai", "anthropic"}),
            allowed_provider_ids=frozenset({"openai"}),
        )

    monkeypatch.setattr(model_provider_policy, "aresolve_model_provider_policy", resolve_configure_policy)
    caller_policy = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(
            user_id="00000000-0000-0000-0000-000000000001",
            attributes={"is_superuser": True},
        ),
        purpose=ModelProviderPolicyPurpose.DISCOVER,
        candidate_provider_ids=frozenset({"openai", "anthropic"}),
        allowed_provider_ids=frozenset({"openai", "anthropic"}),
    )

    enabled = await credentials._fetch_enabled_providers_for_user(
        "00000000-0000-0000-0000-000000000001",
        provider_policy=caller_policy,
    )

    assert enabled == {"OpenAI"}
    assert resolved_purposes == [ModelProviderPolicyPurpose.CONFIGURE]
    assert resolved_attributes == [caller_policy.context.attributes]
    assert call_order == ["policy", "session"]
    service.get_variable_object.assert_awaited_once()
    assert service.get_variable_object.await_args.kwargs["name"] == "OPENAI_API_KEY"
