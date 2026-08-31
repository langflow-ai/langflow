"""LE-2324: the step budget must be tunable per deployment, not only per session.

The ticket asks whether the step ceiling is configurable. ``/iterations N`` answers
that for one browser session, which does not help an operator who wants every user
of a Langflow instance to get a budget sized for their multi-stage flows.
``LANGFLOW_ASSISTANT_ITERATIONS`` sets the default the same way
``LANGFLOW_ASSISTANT_HISTORY_TURNS`` sets the memory window.

Precedence: per-request ``/iterations N`` > env var > the pinned default.
"""

from __future__ import annotations

import pytest
from langflow.agentic.services.flow_preparation import (
    ASSISTANT_ITERATIONS_ENV,
    DEFAULT_ASSISTANT_ITERATIONS,
    MAX_ASSISTANT_ITERATIONS,
    assistant_iterations_default,
    inject_iterations_into_flow,
)


def _flow_with_agent() -> dict:
    return {
        "data": {
            "nodes": [
                {"data": {"type": "Agent", "node": {"template": {"max_iterations": {"value": 30}}}}},
                {"data": {"type": "ChatInput", "node": {"template": {}}}},
            ]
        }
    }


def _budget(flow: dict) -> int:
    return flow["data"]["nodes"][0]["data"]["node"]["template"]["max_iterations"]["value"]


def test_should_fall_back_to_the_pinned_default_when_env_is_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ASSISTANT_ITERATIONS_ENV, raising=False)
    assert assistant_iterations_default() == DEFAULT_ASSISTANT_ITERATIONS


def test_should_use_the_env_budget_when_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(ASSISTANT_ITERATIONS_ENV, "75")
    assert assistant_iterations_default() == 75


def test_should_clamp_an_env_budget_above_the_ceiling(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(ASSISTANT_ITERATIONS_ENV, "5000")
    assert assistant_iterations_default() == MAX_ASSISTANT_ITERATIONS


def test_should_clamp_a_non_positive_env_budget(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(ASSISTANT_ITERATIONS_ENV, "0")
    assert assistant_iterations_default() == 1


@pytest.mark.parametrize("raw", ["", "   ", "abc", "12.5"])
def test_should_ignore_an_unparseable_env_budget(monkeypatch: pytest.MonkeyPatch, raw: str):
    monkeypatch.setenv(ASSISTANT_ITERATIONS_ENV, raw)
    assert assistant_iterations_default() == DEFAULT_ASSISTANT_ITERATIONS


def test_json_flow_should_receive_the_env_budget(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(ASSISTANT_ITERATIONS_ENV, "64")
    flow = inject_iterations_into_flow(_flow_with_agent(), assistant_iterations_default())
    assert _budget(flow) == 64


def test_per_request_limit_should_win_over_the_env_budget(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(ASSISTANT_ITERATIONS_ENV, "64")
    flow = inject_iterations_into_flow(_flow_with_agent(), 5)
    assert _budget(flow) == 5, "/iterations N must still override the deployment default"
