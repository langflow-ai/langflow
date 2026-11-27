"""A fake hosted decision endpoint at the HTTP boundary, for release validation without paid inference.

Only the socket is replaced: catalog, policy, credential resolution, payload translation, response parsing,
evidence validation and routing all run for real. Answers are written in each provider's documented wire
format, read from the request it was sent, so option identity is whatever the router actually sent.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx
from lfx.base.models.decisions import providers

if TYPE_CHECKING:
    import pytest

PROVIDERS = tuple(providers.ENDPOINTS)
# The alias a flow selects, and the version the provider reports serving it with.
SELECTED_MODELS = {"TypeSafe": "jev-latest", "Perplexity": "pplx-decider-latest", "OpenAI": "gpt-6-luna"}
SERVED_MODELS = {"TypeSafe": "jev-1.13.0", "Perplexity": "pplx-decider-latest", "OpenAI": "gpt-6-luna-2026-09-01"}
KEY_VARIABLES = {"TypeSafe": "TYPESAFE_API_KEY", "Perplexity": "PERPLEXITY_API_KEY", "OpenAI": "OPENAI_API_KEY"}
_OPENAI_ENDPOINT_VARIABLES = (
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
    "LANGFLOW_OPENAI_BASE_URL",
    "LANGFLOW_OPENAI_API_BASE",
)

Reply = Callable[[str, dict], httpx.Response]


def selected_model(provider: str) -> list[dict[str, str]]:
    """The model field value a flow saves for ``provider``'s decision model."""
    return [{"provider": provider, "name": SELECTED_MODELS[provider]}]


def _question(provider: str, payload: dict) -> dict:
    return payload["questions"][0] if provider == "OpenAI" else payload["questions"]["decision"]


def candidate_ids(provider: str, payload: dict) -> list[str]:
    """The option or level IDs a request asked about, in the order it sent them."""
    question = _question(provider, payload)
    if provider == "OpenAI":
        rows = question.get("choices") or question.get("levels") or []
        return [row.get("value", row.get("label")) for row in rows]
    criteria = question.get("criteria") or {}
    # Score criteria are an ordered list; its levels are answered by position.
    return [str(i) for i in range(len(criteria))] if isinstance(criteria, list) else list(criteria)


def _body(provider: str, answer: dict) -> dict:
    if provider == "OpenAI":
        return {"model": SERVED_MODELS[provider], "answers": [{"name": "decision", **answer}]}
    return {"model": SERVED_MODELS[provider], "answers": {"decision": answer}}


def _response(status: int, body: Any = None, *, headers: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", "https://decisions.invalid")
    return httpx.Response(status, json=body, headers=headers, request=request)


def distribution(*probabilities: float, score: float | None = None) -> Reply:
    """A Choice or Score answer giving each requested candidate, in order, its probability.

    A Score answer's score is the probability-weighted level unless ``score`` overrides it.
    """

    def reply(provider: str, payload: dict) -> httpx.Response:
        question = _question(provider, payload)
        kind = question["type"]
        ids = candidate_ids(provider, payload)
        if len(ids) != len(probabilities):
            msg = f"answer has {len(probabilities)} probabilities for {len(ids)} candidates"
            raise AssertionError(msg)
        answer: dict[str, Any] = {"type": kind}
        if kind == "score":
            answer["score"] = sum(i * p for i, p in enumerate(probabilities)) if score is None else score
        if provider == "OpenAI":
            if kind == "choice":
                answer["probabilities"] = [
                    {"value": i, "probability": p} for i, p in zip(ids, probabilities, strict=True)
                ]
            else:
                answer["probabilities"] = [
                    {"value": index, "label": level["label"], "probability": p}
                    for index, (level, p) in enumerate(zip(question["levels"], probabilities, strict=True))
                ]
        else:
            answer["probabilities"] = dict(zip(ids, probabilities, strict=True))
            if kind == "score":
                answer["legend"] = {str(i): text for i, text in enumerate(question["criteria"])}
        return _response(200, _body(provider, answer), headers={"x-request-id": "req_release_1"})

    return reply


def probability_true(p: float) -> Reply:
    """A Boolean answer with P(true) = ``p``."""

    def reply(provider: str, _payload: dict) -> httpx.Response:
        answer = {"type": "predicate", "probability": p} if provider == "OpenAI" else {"type": "noul", "noul": p}
        return _response(200, _body(provider, answer))

    return reply


def refusal(reason: str = "I can't help with that.") -> Reply:
    """OpenAI's documented refusal answer; the other providers document none."""

    def reply(provider: str, _payload: dict) -> httpx.Response:
        return _response(200, _body(provider, {"type": "refusal", "refusal": reason}))

    return reply


def status(code: int, error_code: str | None = None) -> Reply:
    """A failed HTTP answer, optionally with the provider's machine-readable error code."""

    def reply(_provider: str, _payload: dict) -> httpx.Response:
        body = {"error": {"code": error_code, "message": "provider text that must never be echoed"}}
        return _response(code, body if error_code else None, headers={"x-request-id": "req_release_1"})

    return reply


def raises(exc: Exception) -> Reply:
    def reply(_provider: str, _payload: dict) -> httpx.Response:
        raise exc

    return reply


@dataclass
class FakeDecisionEndpoint:
    """Answers every decision request with ``reply`` and records what reached the network."""

    reply: Reply = field(default_factory=lambda: probability_true(0.9))
    calls: list[tuple[str, str, dict]] = field(default_factory=list)

    def answer(self, reply: Reply) -> None:
        self.reply = reply

    def post(self, url: str, *, json: dict, headers: dict, **_kwargs: Any) -> httpx.Response:
        provider = next(name for name, endpoint in providers.ENDPOINTS.items() if endpoint == url)
        self.calls.append((provider, headers["Authorization"], json))
        return self.reply(provider, json)

    @property
    def payload(self) -> dict:
        assert len(self.calls) == 1, f"expected one decision request, got {len(self.calls)}"
        return self.calls[0][2]


def install(monkeypatch: pytest.MonkeyPatch) -> FakeDecisionEndpoint:
    """Give every provider its own key and replace the network with a recording fake."""
    for name in _OPENAI_ENDPOINT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    for provider, variable in KEY_VARIABLES.items():
        monkeypatch.setenv(variable, f"{provider.lower()}-release-key")
    endpoint = FakeDecisionEndpoint()
    monkeypatch.setattr(providers, "provider_safe_httpx_post", endpoint.post)
    return endpoint
