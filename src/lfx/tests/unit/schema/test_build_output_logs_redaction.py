"""Regression tests for global-variable redaction in ``build_output_logs``.

Components that echo their ``load_from_db`` input values back in their output
(Text Input, Split Text's separator, Write File's filename, etc.) used to leak
the resolved value of a global variable into the Component Output panel. The
fix tracks the resolved value on the vertex and masks it inside
``build_output_logs`` before returning. These tests pin that behaviour.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from lfx.schema.schema import build_output_logs


class _FakeComponent:
    def __init__(self, results: dict[str, Any]) -> None:
        self.status = None
        self._results = results

    def get_results(self) -> dict[str, Any]:
        return self._results

    def get_artifacts(self) -> dict[str, Any]:  # pragma: no cover - unused branch
        return {}


def _make_vertex(outputs: list[dict[str, Any]], resolved: dict[str, str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(outputs=outputs, _resolved_global_values=resolved or {})


def test_outputs_are_redacted_when_vertex_has_resolved_global_values():
    resolved_value = "sk-leaked-value-42"
    vertex = _make_vertex(
        outputs=[{"name": "text"}],
        resolved={resolved_value: "OPENAI_API_KEY"},
    )
    component = _FakeComponent(results={"text": f"echoing {resolved_value} back"})

    outputs = build_output_logs(vertex, (component,))

    assert resolved_value not in outputs["text"]["message"]
    assert "[REDACTED: OPENAI_API_KEY]" in outputs["text"]["message"]


def test_outputs_unchanged_when_no_resolved_globals():
    vertex = _make_vertex(outputs=[{"name": "text"}])
    payload = "just a normal output with no secrets"
    component = _FakeComponent(results={"text": payload})

    outputs = build_output_logs(vertex, (component,))

    assert outputs["text"]["message"] == payload


def test_non_matching_values_are_untouched():
    vertex = _make_vertex(
        outputs=[{"name": "text"}],
        resolved={"some-other-secret": "OTHER_VAR"},  # pragma: allowlist secret
    )
    payload = "output that does not contain the secret"
    component = _FakeComponent(results={"text": payload})

    outputs = build_output_logs(vertex, (component,))

    assert outputs["text"]["message"] == payload


def test_redaction_handles_dict_outputs():
    resolved_value = "my-private-token"
    vertex = _make_vertex(
        outputs=[{"name": "structured"}],
        resolved={resolved_value: "PRIVATE_TOKEN"},
    )
    component = _FakeComponent(
        results={
            "structured": {
                "summary": f"result: {resolved_value}",
                "nested": [{"field": resolved_value}],
            }
        }
    )

    outputs = build_output_logs(vertex, (component,))

    payload = outputs["structured"]["message"]
    assert resolved_value not in str(payload)
    assert "[REDACTED: PRIVATE_TOKEN]" in str(payload)
