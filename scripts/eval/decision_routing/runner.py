"""Route each case through the real Smart Router, the same code a flow runs, and record what happened.

Nothing about routing is reimplemented here: thresholds, ties, per-route minimums, Score rounding and
error handling are the component's own. Replays feed a recorded answer back through the same component,
so a threshold sweep costs no requests.
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from lfx.base.models.decisions.schema import DecisionResult
from lfx.components.llm_operations import llm_conditional_router
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent

from .dataset import ELSE, Case, Suite

if TYPE_CHECKING:
    from collections.abc import Iterator

DECISION, LANGUAGE = "decision", "language"
ERROR_REASONS = {"evaluation_error", "refusal"}


@dataclass(frozen=True)
class Target:
    """A model to evaluate: a decision model, or a language model as the existing-flow baseline."""

    mode: str
    provider: str
    model: str

    @property
    def label(self) -> str:
        prefix = "baseline " if self.mode == LANGUAGE else ""
        return f"{prefix}{self.provider}:{self.model}"

    @classmethod
    def parse(cls, value: str, mode: str = DECISION) -> Target:
        provider, _, model = value.partition(":")
        if not (provider.strip() and model.strip()):
            msg = f"Name a model as provider:model, such as TypeSafe:jev-latest; got {value!r}."
            raise ValueError(msg)
        return cls(mode=mode, provider=provider.strip(), model=model.strip())


class FatalTargetError(RuntimeError):
    """The target can't run any case, such as a rejected key; the run stops instead of billing on."""


def _language_model_value(target: Target) -> list[dict[str, Any]]:
    from lfx.base.models.unified_models import get_language_model_options

    rows = get_language_model_options()
    row = next((r for r in rows if r.get("provider") == target.provider and r.get("name") == target.model), None)
    if row is None:
        msg = f"{target.label} isn't an available language model here. Check its provider is installed and enabled."
        raise FatalTargetError(msg)
    return [row]


def _router(suite: Suite, target: Target, minimum_probability: float | None) -> SmartRouterComponent:
    router = SmartRouterComponent()
    rows = [
        {
            "route_category": route.name,
            "route_description": route.description,
            "output_value": "",
            "minimum_probability": route.minimum_probability,
        }
        for route in suite.routes
    ]
    settings: dict[str, Any] = {"enable_else_output": True}
    if target.mode == LANGUAGE:
        settings |= {"routing_mode": "Language Model", "model": _language_model_value(target), "routes": rows}
    else:
        settings |= {
            "routing_mode": "Decision Model",
            "decision_model": [{"provider": target.provider, "name": target.model}],
            "decision_kind": suite.kind.title(),
            "decision_question": suite.question,
            # Errors are measured, not fatal: Route to Else records them and carries on.
            "evaluation_error_action": "Route to Else",
        }
        if suite.kind != "score":
            settings["minimum_probability"] = (
                suite.minimum_probability if minimum_probability is None else minimum_probability
            )
        if suite.kind != "boolean":
            settings["score_levels" if suite.kind == "score" else "routes"] = rows
    router.set(**settings)
    # Decision mode checks that Else is connected; a single Else edge stands in for the graph.
    router._vertex = SimpleNamespace(  # noqa: SLF001
        outgoing_edges=[SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))]
    )
    router.log = lambda *_args, **_kwargs: None
    return router


@contextlib.contextmanager
def replaying(result: DecisionResult) -> Iterator[None]:
    """Answer the router's decision with ``result`` instead of calling the provider."""
    original = llm_conditional_router.evaluate_decision
    llm_conditional_router.evaluate_decision = lambda *_args, **_kwargs: result
    try:
        yield
    finally:
        llm_conditional_router.evaluate_decision = original


def _routed(suite: Suite, label: str) -> str:
    """The suite outcome a router label names; anything that isn't a route, such as NONE, is Else."""
    by_name = {name.casefold(): name for name in suite.outcomes if name != ELSE}
    return by_name.get(str(label or "").strip().strip('"').casefold(), ELSE)


def route_case(
    suite: Suite,
    target: Target,
    case: Case,
    *,
    minimum_probability: float | None = None,
    recorded: dict | None = None,
) -> dict[str, Any]:
    """Route one case and return its record. ``recorded`` replays a stored decision instead of a request."""
    router = _router(suite, target, minimum_probability)
    router.input_text = case.text
    record: dict[str, Any] = {
        "suite": suite.name,
        "target": target.label,
        "mode": target.mode,
        "case_id": case.id,
        "expected": case.expected,
        "tags": list(case.tags),
    }
    replay = replaying(DecisionResult(**recorded)) if recorded else contextlib.nullcontext()
    started = time.perf_counter()
    try:
        with replay:
            label = router._get_categorization()  # noqa: SLF001 - drive the component as the graph does
    except Exception as exc:  # noqa: BLE001 - any raise with Route to Else means no case can run
        # With Route to Else, only the key, the account, policy or the settings raise: every case would.
        msg = f"{target.label}: {exc}"
        raise FatalTargetError(msg) from None
    elapsed_ms = (time.perf_counter() - started) * 1000
    evidence = router._decision_evidence or {}  # noqa: SLF001 - drive the component as the graph does
    reason = evidence.get("reason") or ("accepted" if _routed(suite, label) != ELSE else "no_match")
    result = evidence.get("result") or {}
    usage = router._token_usage  # noqa: SLF001 - drive the component as the graph does
    routed = _routed(suite, label)
    if reason in ERROR_REASONS:
        outcome = "error"
    elif routed == ELSE:
        outcome = "else"
    else:
        outcome = "correct" if routed == case.expected else "wrong"
    record |= {
        "routed": routed,
        "outcome": outcome,
        "reason": reason,
        "error_category": (evidence.get("error") or {}).get("category") or (reason if reason == "refusal" else None),
        "top_outcome": evidence.get("top_outcome"),
        "latency_ms": None if recorded else round(elapsed_ms, 1),
        "model": result.get("model", target.model),
        "model_source": result.get("model_source", "request" if target.mode == LANGUAGE else None),
        "request_id": result.get("request_id"),
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "result": result or None,
    }
    return record
