"""models.dev metadata catalog with disk-backed cache.

`models.dev <https://models.dev/api.json>`_ is a community-maintained static
JSON registry of LLM providers and per-model metadata (tool calling, reasoning,
modalities, context windows, pricing). We treat it as the source of truth for
model lists and capability tags for the providers it covers, falling back to
the bundled ``*_constants.py`` lists when the snapshot is unavailable or for
providers it doesn't cover (e.g. IBM WatsonX, Azure OpenAI, Groq).

Override scope:
    * Providers in :data:`MODELS_DEV_PROVIDER_KEYS` are replaced from the
      snapshot when one is available in memory.
    * Live-fetched providers (Ollama, IBM WatsonX, OpenRouter) are *not*
      affected at read time: ``replace_with_live_models`` in
      :mod:`lfx.base.models.model_utils` runs **after** the catalog is
      assembled and overrides whatever rows are present with a live query.

Cache layout:
    * In-memory module-level singleton (:func:`get_active_snapshot`).
    * Disk snapshot at ``<langflow-cache>/models_dev/snapshot.json`` for
      offline cold starts.
    * Bundled ``*_constants.py`` lists as the final fallback.

models.dev has no SLA: keep the static fallback bundled so an upstream outage
or schema change degrades to today's behavior rather than breaking the catalog.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from platformdirs import user_cache_dir

from lfx.base.models.model_metadata import create_model_metadata
from lfx.log.logger import logger

MODELS_DEV_URL = "https://models.dev/api.json"
MODELS_DEV_FETCH_TIMEOUT = 10.0
MODELS_DEV_SNAPSHOT_FILENAME = "snapshot.json"
MODELS_DEV_SNAPSHOT_SUBDIR = "models_dev"

# Translation: models.dev provider slug -> Langflow display name. Only
# providers Langflow already knows how to instantiate (have an entry in
# ``MODEL_PROVIDER_METADATA`` + a ``_MODEL_CLASS_IMPORTS`` row) should appear
# here; otherwise we'd surface models the runtime can't actually call.
MODELS_DEV_PROVIDER_KEYS: dict[str, str] = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google Generative AI",
    # NOTE: Groq, Azure OpenAI, IBM WatsonX deliberately omitted today: the
    # first two have half-wired class registry entries and the third isn't in
    # models.dev. OpenRouter is omitted because it's live-fetched per-user.
}


def _snapshot_dir() -> Path:
    """Return the directory where the disk snapshot lives.

    Resolved via ``platformdirs.user_cache_dir`` so deployments inherit their
    platform's conventional cache root. Creates the directory on first use.
    """
    cache_root = Path(user_cache_dir("langflow", "langflow"))
    snapshot_dir = cache_root / MODELS_DEV_SNAPSHOT_SUBDIR
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    return snapshot_dir


def snapshot_path() -> Path:
    """Return the absolute path to the on-disk snapshot file."""
    return _snapshot_dir() / MODELS_DEV_SNAPSHOT_FILENAME


# Module-level snapshot singleton. ``None`` means "no snapshot installed yet
# — callers must fall back to the bundled static lists".
_active_snapshot: dict[str, Any] | None = None


def get_active_snapshot() -> dict[str, Any] | None:
    """Return the snapshot currently installed in memory (or ``None``)."""
    return _active_snapshot


def set_active_snapshot(snapshot: dict[str, Any] | None) -> None:
    """Install (or clear) the in-memory snapshot.

    Callers responsible for invalidating any caches that consumed the previous
    snapshot — see :func:`invalidate_catalog_cache`.
    """
    global _active_snapshot  # noqa: PLW0603 — module-level singleton
    _active_snapshot = snapshot


def invalidate_catalog_cache() -> None:
    """Clear the ``@lru_cache`` on ``get_models_detailed`` after a swap.

    Imported lazily so this module stays usable when ``provider_queries`` is
    not yet imported (e.g. during early test setup).
    """
    from lfx.base.models.unified_models.provider_queries import get_models_detailed

    get_models_detailed.cache_clear()


# ---------------------------------------------------------------------------
# Fetch / load / save
# ---------------------------------------------------------------------------


async def fetch_models_dev_snapshot(timeout: float = MODELS_DEV_FETCH_TIMEOUT) -> dict[str, Any] | None:
    """Fetch the live models.dev JSON. Returns ``None`` on any failure.

    Logs a warning with the URL and HTTP status on transport/protocol errors.
    Malformed JSON or an unexpected payload shape (non-dict root) also yields
    ``None`` — callers fall back to the previous disk snapshot or to the
    bundled static lists.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(MODELS_DEV_URL)
            response.raise_for_status()
            data = response.json()
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        logger.warning("Could not fetch models.dev snapshot from %s (status=%s): %s", MODELS_DEV_URL, status_code, e)
        return None
    except (ValueError, TypeError) as e:
        logger.warning("Malformed models.dev response from %s: %s", MODELS_DEV_URL, e)
        return None

    if not isinstance(data, dict):
        logger.warning("Unexpected models.dev payload (root is %s)", type(data).__name__)
        return None

    return data


def load_models_dev_snapshot(path: Path | None = None) -> dict[str, Any] | None:
    """Load a previously persisted snapshot from disk. ``None`` on miss/corrupt."""
    path = path or snapshot_path()
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError) as e:
        logger.warning("Could not read models.dev snapshot at %s: %s", path, e)
        return None
    if not isinstance(data, dict):
        logger.warning("Disk snapshot at %s has non-dict root (got %s)", path, type(data).__name__)
        return None
    return data


def save_models_dev_snapshot(snapshot: dict[str, Any], path: Path | None = None) -> None:
    """Persist *snapshot* to disk atomically.

    Writes to a sibling ``.tmp`` file then ``os.replace``s into the target so
    a crash mid-write leaves the previous snapshot intact rather than half a
    payload that ``load_models_dev_snapshot`` would reject as corrupt.
    """
    path = path or snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".snapshot-", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(snapshot, f)
        tmp_path.replace(path)
    except OSError as e:
        logger.warning("Could not write models.dev snapshot to %s: %s", path, e)
        # Best-effort cleanup of the temp file if replace didn't consume it.
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()


# ---------------------------------------------------------------------------
# Override / translation
# ---------------------------------------------------------------------------


_RELEASE_DATE_MIN_LEN = len("YYYY-MM-DD")


def _release_date_to_epoch(value: Any) -> int:
    """Convert a models.dev ``release_date`` (YYYY-MM-DD) to a Unix epoch.

    Returns 0 for missing or unparseable values so downstream sort code can
    treat "unknown" as a stable tier without special-casing.
    """
    if not isinstance(value, str) or len(value) < _RELEASE_DATE_MIN_LEN:
        return 0
    try:
        # Date-only ISO 8601; interpret as UTC midnight.
        dt = datetime.strptime(value[:_RELEASE_DATE_MIN_LEN], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    return int(dt.timestamp())


def _translate_model_entry(provider_name: str, model_dict: dict[str, Any]) -> dict[str, Any]:
    """Convert one models.dev model entry to Langflow's ``ModelMetadata`` shape.

    models.dev field -> ours:
        ``tool_call``           -> ``tool_calling``
        ``reasoning``           -> ``reasoning``
        ``modalities.input``    -> ``vision`` (when ``"image"`` is present)
        ``limit.context``       -> ``context_window``
        ``cost.input``          -> ``cost_per_million_in``
        ``cost.output``         -> ``cost_per_million_out``
        ``release_date``        -> ``created`` (Unix epoch)
    """
    model_id = model_dict.get("id") or ""
    modalities = model_dict.get("modalities") or {}
    inputs = modalities.get("input") if isinstance(modalities, dict) else None
    limit = model_dict.get("limit") or {}
    cost = model_dict.get("cost") or {}

    metadata = create_model_metadata(
        provider=provider_name,
        name=model_id,
        icon=provider_name,  # falls back to provider icon registry
        tool_calling=bool(model_dict.get("tool_call")),
        reasoning=bool(model_dict.get("reasoning")),
        created=_release_date_to_epoch(model_dict.get("release_date")),
    )
    # Additive fields — kept as plain dict keys so existing consumers that read
    # the strict TypedDict shape stay happy while new consumers can pick them up.
    if isinstance(inputs, list) and "image" in inputs:
        metadata["vision"] = True
    if isinstance(limit, dict) and isinstance(limit.get("context"), int):
        metadata["context_window"] = limit["context"]
    if isinstance(cost, dict):
        if isinstance(cost.get("input"), (int, float)):
            metadata["cost_per_million_in"] = float(cost["input"])
        if isinstance(cost.get("output"), (int, float)):
            metadata["cost_per_million_out"] = float(cost["output"])
    return metadata


def _provider_model_dicts(provider_block: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the per-model dicts from a provider block (defensive)."""
    models = provider_block.get("models")
    if isinstance(models, dict):
        return [m for m in models.values() if isinstance(m, dict)]
    if isinstance(models, list):
        return [m for m in models if isinstance(m, dict)]
    return []


def apply_models_dev_overrides(
    static_lists: list[list[dict[str, Any]]],
    snapshot: dict[str, Any],
) -> list[list[dict[str, Any]]]:
    """Replace per-provider static rows with models.dev rows where available.

    Static lists for providers models.dev doesn't cover (or that aren't in
    :data:`MODELS_DEV_PROVIDER_KEYS`) pass through unchanged. Override groups
    for covered providers that had no static group at all are appended.
    """
    # Build provider_name -> translated list once.
    overrides: dict[str, list[dict[str, Any]]] = {}
    for snapshot_key, provider_name in MODELS_DEV_PROVIDER_KEYS.items():
        provider_block = snapshot.get(snapshot_key)
        if not isinstance(provider_block, dict):
            continue
        translated = [_translate_model_entry(provider_name, m) for m in _provider_model_dicts(provider_block)]
        if translated:
            overrides[provider_name] = translated

    if not overrides:
        return static_lists

    replaced: list[list[dict[str, Any]]] = []
    consumed_providers: set[str] = set()
    for group in static_lists:
        # A group is a list of model metadata dicts that all share a provider.
        # If the group's provider has an override, swap the whole group.
        provider_names = {m.get("provider") for m in group if isinstance(m, dict) and m.get("provider")}
        if len(provider_names) == 1:
            (provider,) = provider_names
            if provider in overrides and provider not in consumed_providers:
                replaced.append(overrides[provider])
                consumed_providers.add(provider)
                continue
        replaced.append(group)

    # Append override groups for providers that had no static list at all.
    for provider, models in overrides.items():
        if provider not in consumed_providers:
            replaced.append(models)

    return replaced


__all__ = [
    "MODELS_DEV_FETCH_TIMEOUT",
    "MODELS_DEV_PROVIDER_KEYS",
    "MODELS_DEV_SNAPSHOT_FILENAME",
    "MODELS_DEV_SNAPSHOT_SUBDIR",
    "MODELS_DEV_URL",
    "apply_models_dev_overrides",
    "fetch_models_dev_snapshot",
    "get_active_snapshot",
    "invalidate_catalog_cache",
    "load_models_dev_snapshot",
    "save_models_dev_snapshot",
    "set_active_snapshot",
    "snapshot_path",
]
