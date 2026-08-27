"""Scoped provider-policy regressions for the legacy CUGA model selector."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.services.model_provider_policy import ModelProviderPolicyError, ModelProviderPolicyPurpose

pytest.importorskip("lfx_bundles")

try:
    from lfx_bundles.cuga import cuga_agent
except Exception as exc:
    pytest.skip(f"cuga_agent module not importable in this env: {exc}", allow_module_level=True)


async def test_legacy_agent_llm_selection_participates_in_async_provider_policy(monkeypatch) -> None:
    agent = cuga_agent.CugaComponent(
        agent_llm="OpenAI",
        _user_id="resource-owner",
        _parameters={"agent_llm": "OpenAI"},
    )
    denial = ModelProviderPolicyError("openai", ModelProviderPolicyPurpose.USE)
    snapshot = SimpleNamespace(require=Mock(side_effect=denial))
    resolve_policy = AsyncMock(return_value=snapshot)
    monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", resolve_policy)

    with pytest.raises(ModelProviderPolicyError):
        await agent.arequire_model_provider_policy(
            ModelProviderPolicyPurpose.USE,
            user_id="policy-actor",
            parameters={"agent_llm": "OpenAI"},
        )

    resolve_policy.assert_awaited_once_with(
        user_id="policy-actor",
        providers=["openai"],
        purpose=ModelProviderPolicyPurpose.USE,
    )


async def test_get_llm_denial_precedes_standalone_provider_build(monkeypatch) -> None:
    agent = cuga_agent.CugaComponent(agent_llm="OpenAI", _user_id="policy-actor")
    denial = ModelProviderPolicyError("openai", ModelProviderPolicyPurpose.USE)
    require_policy = AsyncMock(side_effect=denial)
    build_model = Mock(side_effect=AssertionError("provider model built after policy denial"))
    monkeypatch.setattr(agent, "arequire_model_provider_policy", require_policy)
    monkeypatch.setattr(agent, "_build_llm_model", build_model)

    with pytest.raises(ModelProviderPolicyError):
        await agent.get_llm()

    require_policy.assert_awaited_once_with(ModelProviderPolicyPurpose.USE)
    build_model.assert_not_called()


async def test_config_denial_precedes_provider_dynamic_update(monkeypatch) -> None:
    agent = cuga_agent.CugaComponent(agent_llm="OpenAI", _user_id="policy-actor")
    denial = ModelProviderPolicyError("openai", ModelProviderPolicyPurpose.CONFIGURE)
    require_policy = AsyncMock(side_effect=denial)
    dynamic_update = AsyncMock(side_effect=AssertionError("provider update hook reached after policy denial"))
    monkeypatch.setattr(agent, "arequire_model_provider_policy", require_policy)
    monkeypatch.setattr(cuga_agent, "update_component_build_config", dynamic_update)

    with pytest.raises(ModelProviderPolicyError):
        await agent.update_build_config({}, "OpenAI", "agent_llm")

    require_policy.assert_awaited_once_with(
        ModelProviderPolicyPurpose.CONFIGURE,
        parameters={"agent_llm": "OpenAI"},
    )
    dynamic_update.assert_not_awaited()
