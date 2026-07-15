"""Provider-agnostic, error-driven model-call remediation.

Some models reject a request that siblings accept — e.g. OpenAI ``gpt-5.6``
refuses function tools together with ``reasoning_effort`` on
``/v1/chat/completions`` and demands the Responses API. That constraint is not
exposed by any provider's model listing, so a static per-model table would
always lag new models. Instead we match the provider's ERROR TEXT to a
remediation (constructor-kwarg overrides), let the caller retry with those
overrides, and remember the winning overrides per model so later calls
pre-apply them (discover-once).

This module is the pure data layer: the registry, matching, and the per-model
cache. The retry orchestration (rebuild + re-invoke) lives at the model-call
site and consumes ``find_remediation`` / ``cached_overrides`` / ``remember``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Remediation:
    """A recognized model constraint and the kwargs that work around it.

    ``markers`` are lowercase substrings; the error matches when ANY is present
    (they are alternate phrasings of the same constraint). ``providers`` empty
    means the remediation applies to any provider.
    """

    name: str
    markers: tuple[str, ...]
    overrides: dict[str, Any]
    providers: tuple[str, ...] = field(default_factory=tuple)

    def matches(self, error_msg: str | None, provider: str | None) -> bool:
        if self.providers and (provider or "") not in self.providers:
            return False
        lowered = (error_msg or "").lower()
        return any(marker in lowered for marker in self.markers)


# The registry. Each entry keys on the provider's error text, never a model name,
# so new models that hit the same constraint are covered without a code change.
REMEDIATIONS: tuple[Remediation, ...] = (
    Remediation(
        name="openai-responses-api-for-tools",
        # gpt-5.6+ reasoning models reject tools + reasoning_effort on
        # chat/completions and point at the Responses API in the 400 body.
        markers=("/v1/responses",),
        overrides={"use_responses_api": True},
        providers=("OpenAI",),
    ),
)


def find_remediation(
    error_msg: str | None,
    provider: str | None,
    *,
    already_applied: set[str],
) -> Remediation | None:
    """Return the first matching remediation not yet applied this attempt."""
    for remediation in REMEDIATIONS:
        if remediation.name in already_applied:
            continue
        if remediation.matches(error_msg, provider):
            return remediation
    return None


# Runtime, process-scoped memory of overrides that worked, keyed per model so a
# constraint is discovered once and pre-applied thereafter.
_REMEDIATION_CACHE: dict[str, dict[str, Any]] = {}


def _model_key(provider: str | None, model_name: str | None) -> str:
    return f"{provider or ''}:{model_name or ''}"


def cached_overrides(provider: str | None, model_name: str | None) -> dict[str, Any]:
    """Return a copy of the overrides remembered for this model (empty if none)."""
    return dict(_REMEDIATION_CACHE.get(_model_key(provider, model_name), {}))


def remember(provider: str | None, model_name: str | None, overrides: dict[str, Any]) -> None:
    """Merge ``overrides`` into the remembered set for this model.

    The write is PROVISIONAL until the retry it enables actually succeeds: the cache is
    process-global, so a remembered override that did not fix anything would silently
    poison every later request for that model. Callers must snapshot with
    ``cached_overrides`` first and call ``restore_overrides`` if the retry still fails.
    """
    _REMEDIATION_CACHE.setdefault(_model_key(provider, model_name), {}).update(overrides)


def restore_overrides(provider: str | None, model_name: str | None, snapshot: dict[str, Any]) -> None:
    """Put this model's remembered set back to ``snapshot``, undoing a provisional ``remember``."""
    key = _model_key(provider, model_name)
    if snapshot:
        _REMEDIATION_CACHE[key] = dict(snapshot)
    else:
        _REMEDIATION_CACHE.pop(key, None)


def reset_remediation_cache() -> None:
    """Drop all remembered overrides (test isolation / manual reset)."""
    _REMEDIATION_CACHE.clear()
