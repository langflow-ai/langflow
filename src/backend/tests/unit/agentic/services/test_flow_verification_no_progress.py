"""LE-1776 item 1(b) — verification must not repair away a deliberate incompleteness.

The repair loop used to command the agent to fix the wiring unconditionally, so a
user who explicitly asked for an unconnected component got it silently connected.
The agent holds the user's request in context, so the decision belongs to it — the
retry prompt now lets it decline. Declining means returning the flow unchanged, and
the loop detects that structurally (no keyword matching, works in any language) and
stops instead of burning the remaining attempts re-asking.

Same guard covers the cost case the ticket raised: an agent that cannot fix a flow
used to be asked ``MAX_FLOW_VERIFICATION_ATTEMPTS`` times for the same no-op.
"""

from __future__ import annotations

import copy

import pytest
from langflow.agentic.services.flow_structural_validation import FLOW_STRUCTURE_RETRY_TEMPLATE
from langflow.agentic.services.flow_verification import (
    FlowVerificationStatus,
    verify_built_flow,
    verify_loop_structure,
)


def _flow(n_nodes: int = 1, n_edges: int = 0) -> dict:
    return {
        "data": {
            "nodes": [{"id": f"N{i}", "data": {"id": f"N{i}", "type": "LoopComponent"}} for i in range(n_nodes)],
            "edges": [
                {"source": f"N{i}", "target": f"N{i + 1}", "data": {"sourceHandle": {}, "targetHandle": {}}}
                for i in range(n_edges)
            ],
        }
    }


class TestLoopStructureStopsWhenTheAgentDeclines:
    @pytest.mark.asyncio
    async def test_should_stop_after_one_no_op_fix_turn(self):
        """An unchanged flow means "I am not fixing this" — stop asking."""
        calls = []

        async def fix_fn(error: str):
            calls.append(error)
            return copy.deepcopy(_flow())  # same structure back

        result = await verify_loop_structure(
            flow=_flow(),
            validate_fn=lambda _f: ["loop has no data source"],
            fix_fn=fix_fn,
            max_attempts=3,
        )

        assert len(calls) == 1, f"kept re-asking after a no-op fix: {len(calls)} turns"
        assert result.status is FlowVerificationStatus.NEEDS_CAVEAT

    @pytest.mark.asyncio
    async def test_should_deliver_the_flow_the_user_asked_for_unmodified(self):
        original = _flow()

        async def fix_fn(_error: str):
            return copy.deepcopy(original)

        result = await verify_loop_structure(
            flow=original,
            validate_fn=lambda _f: ["orphan node"],
            fix_fn=fix_fn,
            max_attempts=3,
        )

        assert len(result.flow["data"]["nodes"]) == 1
        assert result.flow["data"]["edges"] == []
        assert result.caveat is not None, "an unrepaired flow must still be flagged honestly"

    @pytest.mark.asyncio
    async def test_should_keep_iterating_while_the_agent_makes_progress(self):
        """Non-regression: a genuine repair sequence must still run to completion."""
        flows = [_flow(3, 1), _flow(5, 4)]
        calls = []

        async def fix_fn(_error: str):
            calls.append(1)
            return flows.pop(0)

        result = await verify_loop_structure(
            flow=_flow(1),
            validate_fn=lambda f: [] if len(f["data"]["nodes"]) == 5 else ["still incomplete"],
            fix_fn=fix_fn,
            max_attempts=3,
        )

        assert len(calls) == 2
        assert result.status is FlowVerificationStatus.PASSED
        assert len(result.flow["data"]["nodes"]) == 5


class TestBuiltFlowStopsWhenTheFixIsANoOp:
    @pytest.mark.asyncio
    async def test_should_not_rerun_an_unchanged_flow(self):
        runs, fixes = [], []

        async def run_fn(_flow):
            runs.append(1)
            return {"error": "component X failed"}

        async def fix_fn(_error):
            fixes.append(1)
            return copy.deepcopy(_flow(2, 1))

        result = await verify_built_flow(
            flow=_flow(2, 1),
            run_fn=run_fn,
            fix_fn=fix_fn,
            max_attempts=3,
        )

        assert len(fixes) == 1, "re-ran the same flow after a no-op fix"
        assert len(runs) == 1, "burned a real run on an unchanged flow"
        assert result.status is FlowVerificationStatus.FAILED

    @pytest.mark.asyncio
    async def test_should_keep_retrying_when_the_fix_changes_the_flow(self):
        """Non-regression: real repairs still get their full attempt budget."""
        runs = []

        async def run_fn(flow):
            runs.append(len(flow["data"]["nodes"]))
            return {} if len(flow["data"]["nodes"]) == 4 else {"error": "boom"}

        async def fix_fn(_error):
            return _flow(4, 3)

        result = await verify_built_flow(flow=_flow(2, 1), run_fn=run_fn, fix_fn=fix_fn, max_attempts=3)

        assert runs == [2, 4]
        assert result.status is FlowVerificationStatus.PASSED


class TestRetryPromptOffersAnOptOut:
    def test_template_lets_the_agent_honour_a_deliberate_incompleteness(self):
        """Language-agnostic by construction: the model decides, no keyword match."""
        lowered = FLOW_STRUCTURE_RETRY_TEMPLATE.lower()

        assert "{error}" in FLOW_STRUCTURE_RETRY_TEMPLATE
        assert "leave it" in lowered or "leave the flow" in lowered, "no opt-out offered to the agent"
        assert "asked" in lowered, "the opt-out must be conditioned on what the user asked for"
