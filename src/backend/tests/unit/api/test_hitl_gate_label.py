"""Regression tests for the resumed HITL gate span label (LE-1851).

The gate span name must reflect the *actual* action the human chose, not a hardcoded
"Approved". Actions are user-defined (Approve, Reject, Remove, Escalate, ...), so the
label comes from the pending request's option label, falling back to a humanized
action_id.
"""

from langflow.api.build import _hitl_gate_label

_OPTIONS = [
    {"action_id": "approve", "label": "Approve"},
    {"action_id": "remove", "label": "Remove"},
]


def test_gate_label_uses_option_label_for_reject_like_action():
    # The reported bug: a "remove" decision was mislabeled "Approved".
    assert _hitl_gate_label("remove", _OPTIONS) == "Remove"


def test_gate_label_uses_option_label_for_approve():
    assert _hitl_gate_label("approve", _OPTIONS) == "Approve"


def test_gate_label_humanizes_action_id_when_no_matching_option():
    assert _hitl_gate_label("request_changes", _OPTIONS) == "Request Changes"


def test_gate_label_humanizes_action_id_when_options_missing():
    assert _hitl_gate_label("escalate", None) == "Escalate"


def test_gate_label_prefers_option_label_over_humanized_id():
    options = [{"action_id": "reject", "label": "Reject Request"}]
    assert _hitl_gate_label("reject", options) == "Reject Request"


def test_gate_label_falls_back_when_action_id_empty():
    assert _hitl_gate_label("", _OPTIONS) == "Resolved"


def test_gate_label_ignores_option_with_blank_label():
    options = [{"action_id": "remove", "label": "  "}]
    assert _hitl_gate_label("remove", options) == "Remove"
