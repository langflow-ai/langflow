"""Unit tests for the models.dev metadata catalog layer.

Covers:
  - fetch_models_dev_snapshot: happy path, transport error, malformed JSON,
    non-dict root.
  - load_models_dev_snapshot / save_models_dev_snapshot: round-trip,
    missing/corrupt disk states, atomic write cleanup.
  - apply_models_dev_overrides: translates fields, replaces covered providers,
    preserves uncovered providers (IBM WatsonX), passes through Langflow-only
    providers (OpenRouter) unchanged at the static-list layer.
  - provider_queries.get_models_detailed cache invalidation when a snapshot
    installs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# fetch_models_dev_snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_models_dev_snapshot_happy_path():
    from lfx.base.models import models_dev_catalog

    payload = {"anthropic": {"id": "anthropic", "name": "Anthropic", "models": {}}}

    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.get = AsyncMock(return_value=response)

    with patch.object(models_dev_catalog.httpx, "AsyncClient", return_value=mock_client) as ctor:
        result = await models_dev_catalog.fetch_models_dev_snapshot()

    ctor.assert_called_once()
    mock_client.get.assert_awaited_once_with(models_dev_catalog.MODELS_DEV_URL)
    assert result == payload


@pytest.mark.asyncio
async def test_fetch_models_dev_snapshot_transport_error_returns_none():
    from lfx.base.models import models_dev_catalog

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("network down"))

    with patch.object(models_dev_catalog.httpx, "AsyncClient", return_value=mock_client):
        assert await models_dev_catalog.fetch_models_dev_snapshot() is None


@pytest.mark.asyncio
async def test_fetch_models_dev_snapshot_http_status_error_returns_none():
    from lfx.base.models import models_dev_catalog

    bad_response = MagicMock()
    bad_response.status_code = 503
    bad_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "service unavailable", request=MagicMock(), response=bad_response
    )

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.get = AsyncMock(return_value=bad_response)

    with patch.object(models_dev_catalog.httpx, "AsyncClient", return_value=mock_client):
        assert await models_dev_catalog.fetch_models_dev_snapshot() is None


@pytest.mark.asyncio
async def test_fetch_models_dev_snapshot_non_dict_payload_returns_none():
    from lfx.base.models import models_dev_catalog

    response = MagicMock()
    response.json.return_value = ["not", "a", "dict"]
    response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.get = AsyncMock(return_value=response)

    with patch.object(models_dev_catalog.httpx, "AsyncClient", return_value=mock_client):
        assert await models_dev_catalog.fetch_models_dev_snapshot() is None


# ---------------------------------------------------------------------------
# load / save snapshot (disk)
# ---------------------------------------------------------------------------


def test_save_then_load_snapshot_roundtrips(tmp_path: Path):
    from lfx.base.models import models_dev_catalog

    snapshot = {"anthropic": {"id": "anthropic", "models": {"x": {"id": "x", "tool_call": True}}}}
    target = tmp_path / "snapshot.json"

    models_dev_catalog.save_models_dev_snapshot(snapshot, path=target)
    loaded = models_dev_catalog.load_models_dev_snapshot(path=target)
    assert loaded == snapshot


def test_load_snapshot_missing_file_returns_none(tmp_path: Path):
    from lfx.base.models import models_dev_catalog

    assert models_dev_catalog.load_models_dev_snapshot(path=tmp_path / "absent.json") is None


def test_load_snapshot_corrupt_json_returns_none(tmp_path: Path):
    from lfx.base.models import models_dev_catalog

    target = tmp_path / "corrupt.json"
    target.write_text("{ not really json ", encoding="utf-8")
    assert models_dev_catalog.load_models_dev_snapshot(path=target) is None


def test_load_snapshot_non_dict_root_returns_none(tmp_path: Path):
    from lfx.base.models import models_dev_catalog

    target = tmp_path / "list.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    assert models_dev_catalog.load_models_dev_snapshot(path=target) is None


def test_save_snapshot_cleans_up_temp_file(tmp_path: Path):
    """Atomic write must not leave behind stray .tmp files."""
    from lfx.base.models import models_dev_catalog

    target = tmp_path / "snapshot.json"
    models_dev_catalog.save_models_dev_snapshot({"openai": {}}, path=target)

    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == {"openai": {}}


# ---------------------------------------------------------------------------
# apply_models_dev_overrides
# ---------------------------------------------------------------------------


def _watsonx_group() -> list[dict]:
    return [{"provider": "IBM WatsonX", "name": "ibm/granite-13b", "tool_calling": True}]


def _anthropic_group() -> list[dict]:
    return [{"provider": "Anthropic", "name": "claude-old-1", "tool_calling": False}]


def test_apply_overrides_replaces_covered_provider():
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    snapshot = {
        "anthropic": {
            "id": "anthropic",
            "name": "Anthropic",
            "models": {
                "claude-opus-4-1-20250805": {
                    "id": "claude-opus-4-1-20250805",
                    "tool_call": True,
                    "reasoning": True,
                    "modalities": {"input": ["text", "image"], "output": ["text"]},
                    "limit": {"context": 200000, "output": 32000},
                    "cost": {"input": 15, "output": 75},
                },
                "claude-sonnet-4-5": {
                    "id": "claude-sonnet-4-5",
                    "tool_call": True,
                    "reasoning": False,
                    "limit": {"context": 200000},
                },
            },
        },
    }

    result = apply_models_dev_overrides([_anthropic_group(), _watsonx_group()], snapshot)

    # Anthropic group must be replaced with 2 new entries; WatsonX preserved.
    assert len(result) == 2
    anthropic_models = result[0]
    assert {m["name"] for m in anthropic_models} == {"claude-opus-4-1-20250805", "claude-sonnet-4-5"}

    opus = next(m for m in anthropic_models if m["name"] == "claude-opus-4-1-20250805")
    assert opus["provider"] == "Anthropic"
    assert opus["tool_calling"] is True
    assert opus["reasoning"] is True
    assert opus["vision"] is True
    assert opus["context_window"] == 200000
    assert opus["cost_per_million_in"] == 15.0
    assert opus["cost_per_million_out"] == 75.0

    sonnet = next(m for m in anthropic_models if m["name"] == "claude-sonnet-4-5")
    assert sonnet["tool_calling"] is True
    assert sonnet["reasoning"] is False
    assert "vision" not in sonnet  # no image in modalities
    assert sonnet["context_window"] == 200000
    assert "cost_per_million_in" not in sonnet  # no cost block

    # WatsonX (not in snapshot, not in MODELS_DEV_PROVIDER_KEYS) is untouched.
    assert result[1] == _watsonx_group()


def test_apply_overrides_skips_unknown_provider_keys():
    """models.dev includes routers like Helicone we shouldn't surface."""
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    snapshot = {"helicone": {"id": "helicone", "models": {"foo": {"id": "foo"}}}}
    static = [_anthropic_group(), _watsonx_group()]
    assert apply_models_dev_overrides(static, snapshot) == static


def test_apply_overrides_when_snapshot_empty_passes_static_through():
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    static = [_anthropic_group(), _watsonx_group()]
    assert apply_models_dev_overrides(static, {}) == static


def test_apply_overrides_appends_new_provider_when_no_static_group():
    """Append override groups for covered providers with no static group.

    Guards against accidental removal of a static group: as long as
    models.dev still knows the provider, the override path keeps it visible.
    """
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    snapshot = {
        "openai": {
            "id": "openai",
            "models": {"gpt-4o-mini": {"id": "gpt-4o-mini", "tool_call": True}},
        }
    }
    static = [_watsonx_group()]  # No OpenAI group
    result = apply_models_dev_overrides(static, snapshot)
    assert len(result) == 2
    openai_group = next(group for group in result if any(m.get("provider") == "OpenAI" for m in group))
    assert openai_group[0]["name"] == "gpt-4o-mini"
    assert openai_group[0]["tool_calling"] is True


# ---------------------------------------------------------------------------
# Catalog cache invalidation
# ---------------------------------------------------------------------------


def test_install_snapshot_invalidates_get_models_detailed_cache():
    """Snapshot install + invalidate_catalog_cache flips the next read."""
    from lfx.base.models import models_dev_catalog
    from lfx.base.models.unified_models.provider_queries import get_models_detailed

    # Snapshot any prior state so other tests aren't affected.
    prior = models_dev_catalog.get_active_snapshot()
    try:
        models_dev_catalog.set_active_snapshot(None)
        get_models_detailed.cache_clear()
        static_view = get_models_detailed()
        assert any(any(m.get("provider") == "Anthropic" for m in group) for group in static_view)

        # Install a synthetic snapshot and invalidate.
        synthetic = {
            "anthropic": {
                "id": "anthropic",
                "models": {"synthetic-claude": {"id": "synthetic-claude", "tool_call": True}},
            }
        }
        models_dev_catalog.set_active_snapshot(synthetic)
        models_dev_catalog.invalidate_catalog_cache()

        live_view = get_models_detailed()
        anthropic_groups = [g for g in live_view if any(m.get("provider") == "Anthropic" for m in g)]
        assert anthropic_groups, "Anthropic group missing after override install"
        names = {m["name"] for m in anthropic_groups[0]}
        assert names == {"synthetic-claude"}
    finally:
        # Restore prior state so subsequent tests aren't polluted.
        models_dev_catalog.set_active_snapshot(prior)
        get_models_detailed.cache_clear()
