"""Characterization tests for the extracted progress-step decision.

Pins the EXACT label produced for every branch (precedence + the
flow-request sub-cases) so the extraction from assistant_service is
behavior-preserving and the recurring orchestrating/plan/continuation
label bugs stay caught.
"""

from __future__ import annotations

import pytest
from langflow.agentic.services.flow_types import EDIT_CONTINUATION_INPUT, PLAN_APPROVAL_INPUT
from langflow.agentic.services.request_framing import decide_progress_step


def _step(**kw):
    base = {
        "is_component_request": False,
        "is_document_request": False,
        "is_run_request": False,
        "is_flow_request": False,
        "is_compound": False,
        "original_user_input": "x",
    }
    base.update(kw)
    return decide_progress_step(**base)


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({"is_component_request": True}, ("generating_component", "Generating component...")),
        ({"is_document_request": True}, ("generating_document", "Generating document...")),
        ({"is_run_request": True}, ("generating", "Running the flow...")),
        # precedence: component wins over everything
        (
            {"is_component_request": True, "is_flow_request": True, "is_compound": True},
            ("generating_component", "Generating component..."),
        ),
        # plain flow request (no run/approval/continuation) → the RICH
        # `generating_flow` step (so the frontend shows the Langflow flow
        # icon/card immediately, same as `generating_component`), but with
        # a NEUTRAL message — at this point we still can't promise
        # "Generating plan..." (the agent may direct-edit). Requirement
        # change: a fresh build_flow must NOT fall back to the generic
        # random "Processing..." thinking indicator.
        ({"is_flow_request": True}, ("generating_flow", "Working on the flow...")),
        # compound → orchestrating
        ({"is_flow_request": True, "is_compound": True}, ("orchestrating", "Orchestrating...")),
        # build_flow that ALSO asks to run → orchestrating
        (
            {"is_flow_request": True, "original_user_input": "crie um flow com um agent e rode esse flow"},
            ("orchestrating", "Orchestrating..."),
        ),
        # nothing classified → generic
        ({}, ("generating", "Generating response...")),
    ],
)
def test_step_matrix(flags, expected):
    assert _step(**flags) == expected


def test_plan_approval_signal_labels_generating_flow():
    assert _step(is_flow_request=True, original_user_input=PLAN_APPROVAL_INPUT) == (
        "generating_flow",
        "Generating flow...",
    )


def test_edit_continuation_signal_labels_continuing():
    assert _step(is_flow_request=True, original_user_input=EDIT_CONTINUATION_INPUT) == (
        "generating",
        "Continuing...",
    )


def test_protocol_signals_are_not_treated_as_build_and_run():
    # The continuation signal contains "running the flow" prose; it must
    # NOT be mistaken for a build+run orchestration.
    name, _ = _step(is_flow_request=True, original_user_input=EDIT_CONTINUATION_INPUT)
    assert name != "orchestrating"
