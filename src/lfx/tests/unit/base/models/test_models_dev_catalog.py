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
from datetime import datetime, timezone
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
                    "release_date": "2025-08-05",
                },
                "claude-sonnet-4-5": {
                    "id": "claude-sonnet-4-5",
                    "tool_call": True,
                    "reasoning": False,
                    "limit": {"context": 200000},
                    "release_date": "2025-09-29",
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
    assert opus["created"] == 1754352000  # 2025-08-05T00:00:00Z

    sonnet = next(m for m in anthropic_models if m["name"] == "claude-sonnet-4-5")
    assert sonnet["tool_calling"] is True
    assert sonnet["reasoning"] is False
    assert "vision" not in sonnet  # no image in modalities
    assert sonnet["context_window"] == 200000
    assert "cost_per_million_in" not in sonnet  # no cost block
    assert sonnet["created"] == 1759104000  # 2025-09-29T00:00:00Z

    # WatsonX (not in snapshot, not in MODELS_DEV_PROVIDER_KEYS) is untouched.
    assert result[1] == _watsonx_group()


def test_apply_overrides_handles_missing_or_invalid_release_date():
    """release_date is best-effort: ISO YYYY-MM-DD parses, anything else → 0.

    The downstream sort uses 0 to mean "unknown" and falls back to the
    stable original-order tier, so this needs to degrade quietly.
    """
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    snapshot = {
        "openai": {
            "id": "openai",
            "models": {
                "gpt-no-date": {"id": "gpt-no-date", "tool_call": True},
                "gpt-bad-date": {"id": "gpt-bad-date", "release_date": "not-a-date"},
                "gpt-iso": {"id": "gpt-iso", "release_date": "2024-05-13"},
            },
        }
    }
    result = apply_models_dev_overrides([], snapshot)
    by_name = {m["name"]: m for m in result[0]}
    assert by_name["gpt-no-date"]["created"] == 0
    assert by_name["gpt-bad-date"]["created"] == 0
    assert by_name["gpt-iso"]["created"] == 1715558400  # 2024-05-13T00:00:00Z


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


def test_apply_overrides_marks_dated_snapshot_ids_deprecated():
    """Dated-snapshot ids flag deprecated so they collapse into disclosure.

    Each vendor uses a different shape:
      * Anthropic ``-YYYYMMDD``         (claude-opus-4-5-20251101)
      * OpenAI    ``-YYYY-MM-DD``       (gpt-4o-2024-05-13)
      * Google    ``-preview-MM-DD``    (gemini-2.5-pro-preview-05-06)
      *           or ``-preview-MM-YYYY`` (gemini-2.5-flash-preview-09-2025)
    Moving aliases and ``-preview-tts``-style non-dated suffixes stay active.
    """
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    snapshot = {
        "anthropic": {
            "id": "anthropic",
            "models": {
                "claude-opus-4-5": {"id": "claude-opus-4-5", "tool_call": True},
                "claude-opus-4-5-20251101": {
                    "id": "claude-opus-4-5-20251101",
                    "tool_call": True,
                },
                "claude-haiku-4-5-20251001": {
                    "id": "claude-haiku-4-5-20251001",
                    "tool_call": True,
                },
            },
        },
        "openai": {
            "id": "openai",
            "models": {
                "gpt-4o": {"id": "gpt-4o", "tool_call": True},
                "gpt-4o-2024-05-13": {"id": "gpt-4o-2024-05-13", "tool_call": True},
                # 4-digit-only suffixes (e.g. -0314) are NOT a dated-snapshot
                # pattern; they should stay non-deprecated unless other signals
                # mark them.
                "gpt-4-0314": {"id": "gpt-4-0314", "tool_call": True},
            },
        },
        "google": {
            "id": "google",
            "models": {
                "gemini-2.5-pro": {"id": "gemini-2.5-pro", "tool_call": True},
                "gemini-2.5-pro-preview-05-06": {
                    "id": "gemini-2.5-pro-preview-05-06",
                    "tool_call": True,
                },
                "gemini-2.5-flash-preview-09-2025": {
                    "id": "gemini-2.5-flash-preview-09-2025",
                    "tool_call": True,
                },
                # Non-dated -preview-* suffix (TTS variant): stays active.
                "gemini-2.5-pro-preview-tts": {
                    "id": "gemini-2.5-pro-preview-tts",
                    "tool_call": True,
                },
            },
        },
    }

    fixed_now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    result = apply_models_dev_overrides([], snapshot, now=fixed_now)
    by_name: dict[str, dict] = {}
    for group in result:
        for entry in group:
            by_name[entry["name"]] = entry

    assert by_name["claude-opus-4-5"]["deprecated"] is False
    assert by_name["claude-opus-4-5-20251101"]["deprecated"] is True
    assert by_name["claude-haiku-4-5-20251001"]["deprecated"] is True
    assert by_name["gpt-4o"]["deprecated"] is False
    assert by_name["gpt-4o-2024-05-13"]["deprecated"] is True
    assert by_name["gpt-4-0314"]["deprecated"] is False
    assert by_name["gemini-2.5-pro"]["deprecated"] is False
    assert by_name["gemini-2.5-pro-preview-05-06"]["deprecated"] is True
    assert by_name["gemini-2.5-flash-preview-09-2025"]["deprecated"] is True
    assert by_name["gemini-2.5-pro-preview-tts"]["deprecated"] is False


def test_apply_overrides_preserves_gemini_1_5_static_deprecation():
    """gemini-1.5-* static deprecation flows through the override.

    The 900-day age heuristic alone wouldn't catch the more recent 1.5
    builds (gemini-1.5-flash-8b is ~592 days). The static
    google_generative_ai_constants curation explicitly flags them and the
    override preserves it.
    """
    from lfx.base.models.google_generative_ai_constants import (
        GOOGLE_GENERATIVE_AI_MODELS_DETAILED,
    )
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    # Sanity-check the static curation lists these names.
    static_names_to_deprecated = {m["name"]: m.get("deprecated") for m in GOOGLE_GENERATIVE_AI_MODELS_DETAILED}
    for name in ("gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-flash-8b"):
        assert static_names_to_deprecated.get(name) is True, (
            f"{name} must be flagged deprecated in the static Google constants"
        )

    snapshot = {
        "google": {
            "id": "google",
            "models": {
                # Recent enough not to be caught by the 900-day heuristic.
                "gemini-1.5-flash-8b": {
                    "id": "gemini-1.5-flash-8b",
                    "release_date": "2024-10-03",
                },
                "gemini-1.5-flash": {
                    "id": "gemini-1.5-flash",
                    "release_date": "2024-05-14",
                },
                "gemini-2.5-pro": {
                    "id": "gemini-2.5-pro",
                    "release_date": "2025-03-20",
                },
            },
        }
    }
    fixed_now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    result = apply_models_dev_overrides([GOOGLE_GENERATIVE_AI_MODELS_DETAILED], snapshot, now=fixed_now)
    by_name = {m["name"]: m for group in result for m in group}

    assert by_name["gemini-1.5-flash-8b"]["deprecated"] is True
    assert by_name["gemini-1.5-flash"]["deprecated"] is True
    # Sanity: the current Gemini model stays active.
    assert by_name["gemini-2.5-pro"]["deprecated"] is False


def test_apply_overrides_preserves_static_deprecated_flag():
    """Static-list curation of deprecated flag survives the override.

    models.dev has no deprecated field, so the static-list curation (e.g.
    ``gpt-3.5-turbo`` flagged deprecated in ``openai_constants.py``) must
    survive the override by name match.
    """
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    # Simulate the static OpenAI group with the curated deprecated flags.
    static_openai = [
        {"provider": "OpenAI", "name": "gpt-4o", "tool_calling": True, "deprecated": False},
        {"provider": "OpenAI", "name": "gpt-3.5-turbo", "tool_calling": True, "deprecated": True},
        {"provider": "OpenAI", "name": "gpt-4.5-preview", "tool_calling": True, "deprecated": True},
    ]
    snapshot = {
        "openai": {
            "id": "openai",
            "models": {
                "gpt-4o": {"id": "gpt-4o", "tool_call": True},
                "gpt-3.5-turbo": {"id": "gpt-3.5-turbo", "tool_call": True},
                "gpt-4.5-preview": {"id": "gpt-4.5-preview", "tool_call": True},
                # New model not in our static list — should default to
                # non-deprecated unless dated-snapshot.
                "gpt-6": {"id": "gpt-6", "tool_call": True},
            },
        }
    }

    result = apply_models_dev_overrides([static_openai], snapshot)
    by_name = {m["name"]: m for group in result for m in group}
    assert by_name["gpt-4o"]["deprecated"] is False
    assert by_name["gpt-3.5-turbo"]["deprecated"] is True
    assert by_name["gpt-4.5-preview"]["deprecated"] is True
    assert by_name["gpt-6"]["deprecated"] is False


def test_apply_overrides_marks_embedding_family_as_embeddings_model_type():
    """text-embedding-* rows must surface as embeddings, not LLMs.

    models.dev mixes embedding models into a provider's models dict with no
    explicit type flag. Detecting them by family / name keeps them out of the
    Language Models section (a real bug from screenshot review).
    """
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    snapshot = {
        "openai": {
            "id": "openai",
            "models": {
                "gpt-4o": {"id": "gpt-4o", "family": "gpt", "tool_call": True},
                "text-embedding-3-large": {
                    "id": "text-embedding-3-large",
                    "family": "text-embedding",
                },
                "text-embedding-ada-002": {
                    "id": "text-embedding-ada-002",
                    "family": "text-embedding",
                },
                # Belt-and-suspenders: a hypothetical embeddings model whose
                # family is empty still gets classified by name substring.
                "voyage-3-embedding": {"id": "voyage-3-embedding"},
            },
        }
    }
    # Use a fixed "now" so the age-based deprecation doesn't interfere with
    # this test's assertions on model_type.
    fixed_now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    result = apply_models_dev_overrides([], snapshot, now=fixed_now)
    by_name = {m["name"]: m for group in result for m in group}

    assert by_name["gpt-4o"]["model_type"] == "llm"
    assert by_name["text-embedding-3-large"]["model_type"] == "embeddings"
    assert by_name["text-embedding-ada-002"]["model_type"] == "embeddings"
    assert by_name["voyage-3-embedding"]["model_type"] == "embeddings"


def test_apply_overrides_auto_deprecates_stale_models():
    """Models with last_updated older than ~30 months are auto-deprecated.

    Catches gpt-4 / gpt-4-turbo / text-embedding-ada-002 today; leaves
    gpt-4o / text-embedding-3-* / current Claudes active.
    """
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    fixed_now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    snapshot = {
        "openai": {
            "id": "openai",
            "models": {
                # 2023-11 → 924 days as of 2026-05-18 → deprecated
                "gpt-4": {"id": "gpt-4", "release_date": "2023-11-06", "last_updated": "2024-04-09"},
                "gpt-4-turbo": {"id": "gpt-4-turbo", "release_date": "2023-11-06", "last_updated": "2024-04-09"},
                # 2022-12 → very old → deprecated
                "text-embedding-ada-002": {
                    "id": "text-embedding-ada-002",
                    "family": "text-embedding",
                    "release_date": "2022-12-15",
                    "last_updated": "2022-12-15",
                },
                # 2024-01-25 → 844 days → still active under the 900d threshold
                "text-embedding-3-large": {
                    "id": "text-embedding-3-large",
                    "family": "text-embedding",
                    "release_date": "2024-01-25",
                    "last_updated": "2024-01-25",
                },
                # 2024-08 → 650 days → active
                "gpt-4o": {"id": "gpt-4o", "release_date": "2024-05-13", "last_updated": "2024-08-06"},
                # No date at all → not auto-deprecated (insufficient signal)
                "gpt-future": {"id": "gpt-future"},
            },
        }
    }

    result = apply_models_dev_overrides([], snapshot, now=fixed_now)
    by_name = {m["name"]: m for group in result for m in group}

    assert by_name["gpt-4"]["deprecated"] is True
    assert by_name["gpt-4-turbo"]["deprecated"] is True
    assert by_name["text-embedding-ada-002"]["deprecated"] is True
    assert by_name["text-embedding-3-large"]["deprecated"] is False
    assert by_name["gpt-4o"]["deprecated"] is False
    assert by_name["gpt-future"]["deprecated"] is False


def test_apply_overrides_drops_subsequent_static_groups_for_overridden_provider():
    """Drop subsequent static groups for an already-overridden provider.

    OPENAI_MODELS_DETAILED + OPENAI_EMBEDDING_MODELS_DETAILED are two groups
    for the same provider. The override combines LLMs + embeddings from the
    single models.dev block, so the trailing static embedding group would
    duplicate every embedding row if left in place.
    """
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides

    static_openai_llms = [
        {"provider": "OpenAI", "name": "gpt-4o", "model_type": "llm"},
    ]
    static_openai_embeddings = [
        {"provider": "OpenAI", "name": "text-embedding-3-large", "model_type": "embeddings"},
        {"provider": "OpenAI", "name": "text-embedding-3-small", "model_type": "embeddings"},
    ]
    snapshot = {
        "openai": {
            "id": "openai",
            "models": {
                "gpt-4o": {"id": "gpt-4o", "family": "gpt", "tool_call": True},
                "text-embedding-3-large": {
                    "id": "text-embedding-3-large",
                    "family": "text-embedding",
                },
                "text-embedding-3-small": {
                    "id": "text-embedding-3-small",
                    "family": "text-embedding",
                },
            },
        }
    }

    fixed_now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    result = apply_models_dev_overrides([static_openai_llms, static_openai_embeddings], snapshot, now=fixed_now)

    # Flatten and collect duplicates by name.
    seen: dict[str, int] = {}
    for group in result:
        for entry in group:
            seen[entry["name"]] = seen.get(entry["name"], 0) + 1

    assert seen.get("gpt-4o") == 1
    assert seen.get("text-embedding-3-large") == 1, (
        "embedding row must not be duplicated by the trailing static embedding group"
    )
    assert seen.get("text-embedding-3-small") == 1


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


def test_get_unified_models_detailed_sorts_provider_lists():
    """Provider lists sort by (deprecated, -created) with stable ties.

    Within a provider: deprecated drops to the bottom, newest non-deprecated
    rises to the top (when ``created`` is known), and rows tied on date
    preserve their original list order via the stable sort.
    """
    from lfx.base.models import models_dev_catalog
    from lfx.base.models.unified_models.model_catalog import get_unified_models_detailed
    from lfx.base.models.unified_models.provider_queries import get_models_detailed

    # Build a synthetic snapshot whose models.dev override drives the test.
    # ``apply_models_dev_overrides`` will translate these into the catalog and
    # the assembly path will then sort them.
    snapshot = {
        "anthropic": {
            "id": "anthropic",
            "models": {
                "claude-old-deprecated": {
                    "id": "claude-old-deprecated",
                    "release_date": "2024-01-01",
                },
                "claude-newest": {"id": "claude-newest", "release_date": "2025-09-01"},
                "claude-undated-a": {"id": "claude-undated-a"},
                "claude-mid": {"id": "claude-mid", "release_date": "2025-05-01"},
                "claude-undated-b": {"id": "claude-undated-b"},
            },
        }
    }
    # apply_models_dev_overrides has no notion of "deprecated", so simulate the
    # state by flipping the flag on one row after the override step. The test
    # exercises the sort, not the deprecation derivation.
    prior = models_dev_catalog.get_active_snapshot()
    try:
        models_dev_catalog.set_active_snapshot(snapshot)
        models_dev_catalog.invalidate_catalog_cache()

        # Hand-flip deprecated on the oldest row by mutating the cached groups.
        groups = get_models_detailed()
        for group in groups:
            for m in group:
                if m.get("name") == "claude-old-deprecated":
                    m["deprecated"] = True

        unified = get_unified_models_detailed(providers=["Anthropic"], include_deprecated=True)
        anthropic = next(p for p in unified if p["provider"] == "Anthropic")
        names = [m["model_name"] for m in anthropic["models"]]

        # Non-deprecated dated rows first (newest first), then undated rows
        # in their original order, then deprecated last.
        assert names == [
            "claude-newest",
            "claude-mid",
            "claude-undated-a",
            "claude-undated-b",
            "claude-old-deprecated",
        ]
    finally:
        models_dev_catalog.set_active_snapshot(prior)
        models_dev_catalog.invalidate_catalog_cache()


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
