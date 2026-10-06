"""Async model choices keep the existing catalog filtering rules."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from lfx.base.models.unified_models import model_catalog
from lfx.components.models_and_agents.model_selection import aapply_model_overrides, apply_model_overrides


def policy():
    return SimpleNamespace(
        require=Mock(), allows=lambda name: name == "OpenAI", allows_model=lambda *_args, **_kwargs: True
    )


@pytest.mark.asyncio
async def test_async_catalog_parity_retains_policy_status_and_live_filters(monkeypatch):
    rows = [
        {
            "provider": "OpenAI",
            "icon": "OpenAI",
            "models": [
                {"model_name": "gpt-4o-mini", "metadata": {"default": True, "model_type": "llm", "tool_calling": True}}
            ],
        }
    ]
    p = policy()
    monkeypatch.setattr(model_catalog, "get_unified_models_detailed", lambda **_kwargs: deepcopy(rows))
    monkeypatch.setattr(model_catalog, "_get_model_status", AsyncMock(return_value=(set(), set())))
    monkeypatch.setattr(model_catalog, "_fetch_enabled_providers_for_user", AsyncMock(return_value={"OpenAI"}))
    seen = []

    def discover(models, *_args, **_kwargs):
        seen.append(models)
        models[0]["models"].append(
            {"model_name": "no-tools", "metadata": {"default": True, "model_type": "llm", "tool_calling": False}}
        )

    monkeypatch.setattr(model_catalog, "replace_with_live_models", discover)
    monkeypatch.setattr(model_catalog, "aget_live_model_variables", AsyncMock(return_value={}))
    asynchronous = await model_catalog.aget_language_model_options(
        "runtime-owner", tool_calling=True, provider_policy=p
    )
    synchronous = model_catalog.get_language_model_options("runtime-owner", tool_calling=True, provider_policy=p)
    assert asynchronous == synchronous
    assert all(x["name"] != "no-tools" for x in asynchronous)
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_unavailable_catalog_policy_precedes_status_and_credentials(monkeypatch):
    monkeypatch.setattr(
        "lfx.services.model_provider_policy.aresolve_model_provider_policy",
        AsyncMock(side_effect=RuntimeError("policy unavailable")),
    )
    status = AsyncMock()
    enabled = AsyncMock()
    monkeypatch.setattr(model_catalog, "_get_model_status", status)
    monkeypatch.setattr(model_catalog, "_fetch_enabled_providers_for_user", enabled)
    with pytest.raises(RuntimeError, match="policy unavailable"):
        await model_catalog.aget_language_model_options("runtime-owner")
    status.assert_not_awaited()
    enabled.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [None, "Anthropic"])
async def test_async_overrides_match_sync_without_mutating_saved_selection(provider):
    """Model changes must keep the stored UI default and discard old provider metadata."""
    saved = [{"name": "old-model", "provider": "OpenAI", "metadata": {"model_class": "old-client"}}]
    before = deepcopy(saved)
    sync = apply_model_overrides(saved, model_name="new-model", provider=provider)
    native = await aapply_model_overrides(saved, model_name="new-model", provider=provider)
    assert native == sync
    assert saved == before
    if provider:
        assert native[0]["metadata"] == {}
