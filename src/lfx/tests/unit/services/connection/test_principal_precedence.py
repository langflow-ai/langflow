"""INT-6: a host-stamped execution principal outranks the headless run defaults."""

from __future__ import annotations

import dataclasses

import pytest
from lfx.run._defaults import apply_run_defaults
from lfx.services.authorization.base import ExecutionPrincipal


class _FakeGraph:
    """The subset of the Graph surface ``apply_run_defaults`` mutates."""

    def __init__(self, principal: ExecutionPrincipal) -> None:
        self.execution_principal = principal
        self.user_id: str | None = None
        self.session_id: str | None = None
        self.has_session_id_vertices: list[str] = []

    def get_vertex(self, vertex_id: str):  # pragma: no cover - no vertices in these graphs
        raise AssertionError(vertex_id)


def test_allow_explicit_shares_defaults_true_and_is_frozen() -> None:
    principal = ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True)

    assert principal.allow_explicit_shares is True
    assert ExecutionPrincipal.unknown().allow_explicit_shares is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        principal.allow_explicit_shares = False  # type: ignore[misc]


def test_apply_run_defaults_stamps_headless_only_when_principal_is_unknown() -> None:
    graph = _FakeGraph(ExecutionPrincipal.unknown())

    apply_run_defaults(graph, session_id="session-1", user_id="user-1")

    assert graph.execution_principal.kind == "headless_operator"
    assert graph.execution_principal.family == "lfx_headless"


@pytest.mark.parametrize(
    "principal",
    [
        ExecutionPrincipal(kind="actor", user_id="user-1", family="interactive_chat", interactive=True),
        ExecutionPrincipal(kind="flow_owner", user_id="user-1", family="webhook", interactive=False),
        ExecutionPrincipal(kind="anonymous_public", family="workflow_public_v2"),
    ],
)
def test_apply_run_defaults_preserves_a_host_stamped_principal(principal: ExecutionPrincipal) -> None:
    graph = _FakeGraph(principal)

    apply_run_defaults(graph, session_id="session-1", user_id="user-1")

    assert graph.execution_principal == principal
    # The identity defaults it does own are still applied.
    assert graph.user_id == "user-1"
    assert graph.session_id == "session-1"


def test_apply_run_defaults_stamps_when_the_graph_has_no_principal_attribute() -> None:
    graph = _FakeGraph(ExecutionPrincipal.unknown())
    graph.execution_principal = None  # type: ignore[assignment]

    apply_run_defaults(graph, session_id="session-1", user_id="user-1")

    assert graph.execution_principal.kind == "headless_operator"
