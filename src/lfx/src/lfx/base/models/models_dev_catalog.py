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
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from platformdirs import user_cache_dir

from lfx.base.models.model_metadata import create_model_metadata
from lfx.log.logger import logger

# models.dev exposes pinned-date snapshots (e.g. ``claude-opus-4-5-20251101``,
# ``gpt-4o-2024-05-13``, ``gemini-2.5-pro-preview-05-06``) alongside the
# moving aliases (``claude-opus-4-5``, ``gpt-4o``, ``gemini-2.5-pro``). The
# snapshots are technically callable but most users want the alias, and
# showing both clutters the picker badly. Each vendor uses a different shape:
#   * Anthropic: ``-YYYYMMDD``           (claude-opus-4-5-20251101)
#   * OpenAI:    ``-YYYY-MM-DD``         (gpt-4o-2024-05-13)
#   * Google:    ``-preview-MM-DD`` or   (gemini-2.5-pro-preview-05-06)
#                ``-preview-MM-YYYY``    (gemini-2.5-flash-preview-09-2025)
# Any id matching one of these is auto-flagged deprecated so it falls into
# the disclosure tier.
_DATED_SNAPSHOT_RE = re.compile(r"-(?:\d{4}-\d{2}-\d{2}|\d{8}|preview-\d{2}-\d{2}|preview-\d{2}-\d{4})$")

# Threshold for auto-deprecating models that haven't shipped a new version in
# a long time. models.dev has no deprecation field, and providers rarely
# formally deprecate models even after they ship a successor — but a model
# that hasn't been touched in 30 months is overwhelmingly legacy in practice
# (catches gpt-4 / gpt-4-turbo / text-embedding-ada-002 today, leaves
# gpt-4o / text-embedding-3-small/large active). Tuned conservatively so
# current embeddings (~28 months old) survive; nudge down only if successor
# adoption is verified.
_AGE_DEPRECATION_DAYS = 900

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
_SECONDS_PER_DAY = 86400


def _is_embedding_family(model_dict: dict[str, Any]) -> bool:
    """Detect embedding models in a provider's models.dev block.

    models.dev mixes embeddings into the same ``models`` dict as LLMs, so
    every entry needs a ``model_type`` decision. The most reliable signal is
    the ``family`` field (e.g. ``"text-embedding"``); the name-substring check
    is a belt-and-suspenders fallback for providers that fill ``family``
    inconsistently.
    """
    family = (model_dict.get("family") or "").lower()
    name = (model_dict.get("id") or "").lower()
    return family.startswith("text-embedding") or family == "embedding" or "embedding" in name


def _is_aged_out(model_dict: dict[str, Any], now: datetime) -> bool:
    """Return True if the model is older than ``_AGE_DEPRECATION_DAYS`` days.

    Prefers ``release_date`` (when the model functionally shipped) over
    ``last_updated`` (which tracks catalog-curator edits like typo fixes, not
    new model versions). The combination of preferring release_date and the
    900-day threshold correctly catches ``gpt-4`` / ``gpt-4-turbo`` (924d from
    their 2023-11 release) while keeping ``text-embedding-3-large`` (844d
    from its 2024-01 release) active.
    """
    raw = model_dict.get("release_date") or model_dict.get("last_updated")
    epoch = _release_date_to_epoch(raw)
    if epoch == 0:
        return False
    age_days = (now.timestamp() - epoch) / _SECONDS_PER_DAY
    return age_days > _AGE_DEPRECATION_DAYS


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


def _translate_model_entry(
    provider_name: str,
    model_dict: dict[str, Any],
    *,
    deprecated: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Convert one models.dev model entry to Langflow's ``ModelMetadata`` shape.

    models.dev field -> ours:
        ``tool_call``           -> ``tool_calling``
        ``reasoning``           -> ``reasoning``
        ``modalities.input``    -> ``vision`` (when ``"image"`` is present)
        ``limit.context``       -> ``context_window``
        ``cost.input``          -> ``cost_per_million_in``
        ``cost.output``         -> ``cost_per_million_out``
        ``release_date``        -> ``created`` (Unix epoch)
        ``family == "text-embedding"`` -> ``model_type="embeddings"``

    Three derived deprecation signals layer on top of the explicit
    ``deprecated`` kwarg (which lets callers forward the static-list
    curation that models.dev itself doesn't surface):
      * dated-snapshot id (:data:`_DATED_SNAPSHOT_RE`);
      * stale ``last_updated`` / ``release_date`` per :data:`_AGE_DEPRECATION_DAYS`.
    ``now`` is injected for testability — defaults to the current UTC time.
    """
    now = now or datetime.now(tz=timezone.utc)
    model_id = model_dict.get("id") or ""
    modalities = model_dict.get("modalities") or {}
    inputs = modalities.get("input") if isinstance(modalities, dict) else None
    limit = model_dict.get("limit") or {}
    cost = model_dict.get("cost") or {}

    is_dated_snapshot = bool(_DATED_SNAPSHOT_RE.search(model_id))
    is_aged_out = _is_aged_out(model_dict, now)
    model_type = "embeddings" if _is_embedding_family(model_dict) else "llm"

    metadata = create_model_metadata(
        provider=provider_name,
        name=model_id,
        icon=provider_name,  # falls back to provider icon registry
        tool_calling=bool(model_dict.get("tool_call")),
        reasoning=bool(model_dict.get("reasoning")),
        created=_release_date_to_epoch(model_dict.get("release_date")),
        deprecated=bool(deprecated) or is_dated_snapshot or is_aged_out,
        model_type=model_type,
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
    *,
    now: datetime | None = None,
) -> list[list[dict[str, Any]]]:
    """Replace per-provider static rows with models.dev rows where available.

    Static lists for providers models.dev doesn't cover (or that aren't in
    :data:`MODELS_DEV_PROVIDER_KEYS`) pass through unchanged. Override groups
    for covered providers that had no static group at all are appended.

    models.dev exposes no ``deprecated`` field of its own, so this function
    preserves the static-list curation by name: any model that was already
    flagged deprecated in the bundled ``*_constants.py`` lists keeps that flag
    after the override. Dated-snapshot ids
    (e.g. ``claude-opus-4-5-20251101``, ``gpt-4o-2024-05-13``) and rows whose
    most recent date is older than :data:`_AGE_DEPRECATION_DAYS` are also
    auto-flagged in :func:`_translate_model_entry`. ``now`` is forwarded for
    testability.
    """
    now = now or datetime.now(tz=timezone.utc)
    # Build provider_name -> {model_name: deprecated} from the static lists so
    # we can preserve the static curation through the override.
    static_deprecated_by_provider: dict[str, set[str]] = {}
    for group in static_lists:
        for entry in group:
            if not isinstance(entry, dict):
                continue
            provider = entry.get("provider")
            name = entry.get("name")
            if not provider or not name:
                continue
            if entry.get("deprecated"):
                static_deprecated_by_provider.setdefault(provider, set()).add(name)

    # Build provider_name -> translated list once.
    overrides: dict[str, list[dict[str, Any]]] = {}
    for snapshot_key, provider_name in MODELS_DEV_PROVIDER_KEYS.items():
        provider_block = snapshot.get(snapshot_key)
        if not isinstance(provider_block, dict):
            continue
        static_deprecated = static_deprecated_by_provider.get(provider_name, set())
        translated = [
            _translate_model_entry(
                provider_name,
                m,
                deprecated=(m.get("id") in static_deprecated),
                now=now,
            )
            for m in _provider_model_dicts(provider_block)
        ]
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
            if provider in overrides:
                if provider in consumed_providers:
                    # A second (or later) static group for the same provider
                    # — e.g. OPENAI_EMBEDDING_MODELS_DETAILED appears after
                    # OPENAI_MODELS_DETAILED. The override already contains
                    # both LLMs and embeddings from that provider, so
                    # appending this static group would duplicate the rows.
                    continue
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
