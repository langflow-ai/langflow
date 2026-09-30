"""Deterministic build+run canvas-application rule (the "diz que fez e não fez" bug).

Bug shape (recurring, screenshots): the user asks to build a flow AND run
it ("crie um flow ... rode ele"). The agent builds (``set_flow``) and runs
it (``run_flow`` → result reported), then says "criei e rodei NO CANVAS" —
but the flow is only a *proposal* card (Add/Replace/Dismiss); the canvas
never changed. Root cause: auto-apply was decided by a regex on the user's
wording (``_looks_like_run_request``) which misses paraphrases ("rode ele",
"run it", any language) → no auto-apply → gated → the agent's claim is a lie.

Fix shape (LLM/language-agnostic, deterministic): RunFlow emits a
``flow_ran`` signal when it ACTUALLY runs the flow. ``_reconcile_flow_updates``
turns "the agent built AND ran the flow this turn" into "apply it to the
canvas" — never inferred from the prompt text. Running a flow the user
cannot see is contradictory, so build+run MUST apply.

These tests pin the invariant for EVERY ordering permutation so it can
never silently regress: same-batch, set_flow-then-later-run, run-only,
compound, incremental-only, idempotency.
"""

from __future__ import annotations

from langflow.agentic.services.assistant_service import _reconcile_flow_updates


def _reconcile(updates, **state):
    """Call with sane defaults; return the full result tuple."""
    base = {
        "auto_apply_flow": False,
        "saw_set_flow": False,
        "saw_run": False,
        "last_set_flow": None,
        "set_flow_applied": False,
    }
    base.update(state)
    return _reconcile_flow_updates(updates, **base)


SET_FLOW = {"action": "set_flow", "flow": {"data": {"nodes": [], "edges": []}}}
FLOW_RAN = {"action": "flow_ran", "flow_id": "f-1"}
ADD = {"action": "add_component", "node": {"id": "n1"}}


class TestSameBatchBuildAndRun:
    """set_flow and flow_ran drained together → set_flow auto-applies."""

    def test_set_flow_then_flow_ran_same_batch_auto_applies(self):
        events, auto_apply, saw_set_flow, saw_run, _last, applied = _reconcile([dict(SET_FLOW), dict(FLOW_RAN)])
        set_flow_events = [e for e in events if e.get("action") == "set_flow"]
        assert len(set_flow_events) == 1
        assert set_flow_events[0]["auto_apply"] is True
        assert auto_apply is True
        assert saw_set_flow is True
        assert saw_run is True
        assert applied is True

    def test_flow_ran_before_set_flow_in_same_batch_still_auto_applies(self):
        # Two-pass: a flow_ran anywhere in the batch must apply the set_flow,
        # even if it is listed BEFORE the set_flow.
        events, *_ = _reconcile([dict(FLOW_RAN), dict(SET_FLOW)])
        set_flow_events = [e for e in events if e.get("action") == "set_flow"]
        assert len(set_flow_events) == 1
        assert set_flow_events[0]["auto_apply"] is True

    def test_flow_ran_is_internal_and_never_forwarded(self):
        events, *_ = _reconcile([dict(SET_FLOW), dict(FLOW_RAN)])
        assert not any(e.get("action") == "flow_ran" for e in events), (
            "flow_ran is an internal signal; the frontend has no reducer for it"
        )


class TestLateRunReconciliation:
    """set_flow proposed in an earlier batch, run happens later → re-apply."""

    def test_set_flow_proposed_then_run_in_later_batch_reemits_with_auto_apply(self):
        # Batch 1: build only (no run known yet) → proposal, NOT applied.
        ev1, auto1, saw_sf1, saw_run1, last1, applied1 = _reconcile([dict(SET_FLOW)])
        assert ev1[0].get("auto_apply") is not True, "no run yet → must be a proposal"
        assert applied1 is False
        assert saw_sf1 is True

        # Batch 2: the agent ran it. Must re-emit the remembered set_flow
        # with auto_apply so the canvas ends in the reported state.
        ev2, _auto2, _saw_sf2, saw_run2, _last2, applied2 = _reconcile(
            [dict(FLOW_RAN)],
            auto_apply_flow=auto1,
            saw_set_flow=saw_sf1,
            saw_run=saw_run1,
            last_set_flow=last1,
            set_flow_applied=applied1,
        )
        reapplied = [e for e in ev2 if e.get("action") == "set_flow"]
        assert len(reapplied) == 1, "must re-emit the set_flow to apply it"
        assert reapplied[0]["auto_apply"] is True
        assert saw_run2 is True
        assert applied2 is True

    def test_late_reconciliation_is_idempotent_across_batches(self):
        _ev1, a1, s1, r1, l1, ap1 = _reconcile([dict(SET_FLOW)])
        _ev2, a2, s2, r2, l2, ap2 = _reconcile(
            [dict(FLOW_RAN)],
            auto_apply_flow=a1,
            saw_set_flow=s1,
            saw_run=r1,
            last_set_flow=l1,
            set_flow_applied=ap1,
        )
        # A THIRD drain (empty / trailing) must NOT re-emit set_flow again.
        ev3, *_ = _reconcile(
            [],
            auto_apply_flow=a2,
            saw_set_flow=s2,
            saw_run=r2,
            last_set_flow=l2,
            set_flow_applied=ap2,
        )
        assert not [e for e in ev3 if e.get("action") == "set_flow"], (
            "set_flow must be applied exactly once, never duplicated"
        )


class TestNoRegression:
    """The fix is strictly additive — existing behaviour is untouched."""

    def test_build_only_no_run_stays_a_proposal(self):
        events, auto_apply, _saw_set_flow, saw_run, _l, applied = _reconcile([dict(SET_FLOW)])
        assert events[0].get("auto_apply") is not True
        assert auto_apply is False
        assert saw_run is False
        assert applied is False

    def test_compound_auto_apply_unchanged(self):
        # Compound already sets auto_apply_flow=True up front; behaviour
        # must be identical (set_flow applied, single emit).
        events, *_, applied = _reconcile([dict(SET_FLOW)], auto_apply_flow=True)
        set_flow_events = [e for e in events if e.get("action") == "set_flow"]
        assert len(set_flow_events) == 1
        assert set_flow_events[0]["auto_apply"] is True
        assert applied is True

    def test_compound_with_run_does_not_double_emit_set_flow(self):
        events, *_ = _reconcile([dict(SET_FLOW), dict(FLOW_RAN)], auto_apply_flow=True)
        assert len([e for e in events if e.get("action") == "set_flow"]) == 1

    def test_incremental_edits_pass_through_untouched(self):
        events, _a, saw_set_flow, _r, _l, _ap = _reconcile([dict(ADD)])
        assert events == [ADD]
        assert saw_set_flow is False

    def test_incremental_edits_plus_run_no_spurious_set_flow(self):
        # Run after incremental edits (no set_flow) must NOT synthesize a
        # set_flow re-emit (nothing remembered to apply).
        events, _a, saw_set_flow, saw_run, _l, _ap = _reconcile([dict(ADD), dict(FLOW_RAN)])
        assert events == [ADD]
        assert saw_set_flow is False
        assert saw_run is True

    def test_run_only_batch_emits_no_events(self):
        # Pure "run the existing flow" — no canvas mutation at all. The
        # caller relies on an empty event list to keep has_flow_updates
        # unchanged so the run-only path is not rerouted (regression).
        events, _a, saw_set_flow, saw_run, _l, _ap = _reconcile([dict(FLOW_RAN)])
        assert events == []
        assert saw_set_flow is False
        assert saw_run is True


class TestLanguageAndWordingAgnostic:
    """The decision must NOT depend on the prompt text in any way."""

    def test_function_signature_takes_no_prompt(self):
        import inspect

        params = set(inspect.signature(_reconcile_flow_updates).parameters)
        forbidden = {"prompt", "user_input", "original_user_input", "text", "message"}
        assert not (params & forbidden), (
            "reconciliation must be driven by the real run action, never by "
            f"parsing the user's wording. Params: {params}"
        )
