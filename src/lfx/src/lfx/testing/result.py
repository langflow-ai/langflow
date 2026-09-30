"""FlowResult dataclass and helpers for building results from raw dicts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_TEXT_REPR_MAX = 60


@dataclass
class FlowResult:
    """Result of a local flow execution via the ``flow_runner`` fixture.

    Attributes:
        status:   ``"success"`` or ``"error"``.
        text:     Primary text output of the flow (first non-empty text/result key).
        messages: List of message dicts produced by the flow.
        outputs:  Raw outputs dict from graph execution.
        logs:     Captured stdout/stderr from execution.
        error:    Error message when status is ``"error"``, else ``None``.
        timing:   Per-component timing dict when ``timing=True`` was passed, else ``None``.
        raw:      The unprocessed result dict returned by ``run_flow()``.
    """

    status: str
    text: str | None
    messages: list[dict[str, Any]]
    outputs: dict[str, Any]
    logs: str
    error: str | None
    timing: dict[str, Any] | None
    raw: dict[str, Any]

    @property
    def ok(self) -> bool:
        """``True`` when *status* is ``"success"``."""
        return self.status == "success"

    def first_text_output(self) -> str | None:
        """Return the primary text output, or ``None`` if there is none.

        Convenience alias for :attr:`text`, compatible with the
        ``langflow_sdk.RunResponse`` interface so test code works against
        both local and remote runners without changes.
        """
        return self.text

    def __repr__(self) -> str:
        snippet = (
            repr(self.text[:_TEXT_REPR_MAX] + "\u2026")
            if self.text and len(self.text) > _TEXT_REPR_MAX
            else repr(self.text)
        )
        return f"FlowResult(status={self.status!r}, text={snippet})"


def _build_result(raw: dict[str, Any]) -> FlowResult:
    """Construct a :class:`FlowResult` from the dict returned by ``run_flow()``."""
    # ``success`` may be absent (treat as True for forward compat)
    is_error = (raw.get("success") is False) or raw.get("type") == "error"
    status = "error" if is_error else "success"

    # Extract primary text from several candidate keys, in priority order
    text: str | None = None
    for key in ("result", "text", "output"):
        val = raw.get(key)
        if val is not None:
            text = val if isinstance(val, str) else json.dumps(val)
            break

    messages: list[dict[str, Any]] = raw.get("messages") or []
    if not isinstance(messages, list):
        messages = []

    outputs: dict[str, Any] = raw.get("outputs") or raw.get("result_dict") or {}
    if not isinstance(outputs, dict):
        outputs = {}

    error_msg: str | None = None
    if is_error:
        error_msg = raw.get("exception_message") or raw.get("error") or "Unknown error"

    return FlowResult(
        status=status,
        text=text,
        messages=messages,
        outputs=outputs,
        logs=raw.get("logs", ""),
        error=error_msg,
        timing=raw.get("timing"),
        raw=raw,
    )


def _build_result_from_sdk_response(response: Any) -> FlowResult:
    """Convert a ``langflow_sdk.RunResponse`` to a :class:`FlowResult`.

    Extracts text, messages, and raw outputs from the SDK response so that
    test assertions written against :class:`FlowResult` work identically
    whether the runner is local or remote.
    """
    text = response.first_text_output()

    messages: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {}
    for i, out in enumerate(response.outputs):
        outputs[str(i)] = out.results
        for component_out in out.outputs:
            msg = component_out.get("results", {}).get("message")
            if isinstance(msg, dict):
                messages.append(msg)

    return FlowResult(
        status="success",
        text=text,
        messages=messages,
        outputs=outputs,
        logs="",
        error=None,
        timing=None,
        raw=response.model_dump(),
    )
