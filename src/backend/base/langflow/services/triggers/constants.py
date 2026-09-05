"""Names the trigger subsystem shares with the CI matrices and later tickets.

These strings are a contract, not an implementation detail: the execution
principal matrix (``scripts/ci/execution_principal_matrix.json``), the
authorization endpoint matrix, TRG-3's listener process and TRG-4's ingress
routes all key off the same values.
"""

from __future__ import annotations

#: Execution-principal families. Equal, character for character, to the
#: ``family`` values in scripts/ci/execution_principal_matrix.json.
FAMILY_TRIGGER_PUSH = "trigger_push"
FAMILY_TRIGGER_LISTENER = "trigger_listener"
TRIGGER_FAMILIES = frozenset({FAMILY_TRIGGER_PUSH, FAMILY_TRIGGER_LISTENER})

#: The matrix ``actor`` word for a run nobody is waiting on.
ACTOR_TRIGGER_DISPATCHER = "trigger_dispatcher"

#: The keyword argument name INT-6's stamping helper takes the family under.
#: Deliberately NOT a run-request field: ``WorkflowRunRequest`` forbids extras,
#: so anything the dispatcher invented on the request body would be rejected by
#: the worker's re-parse and every trigger run would fail. The family therefore
#: travels as an argument (``trigger_execution_principal(..., family=...)``
#: today, INT-6's ``stamp_execution_principal(..., execution_family=...)`` once
#: that lands), and the single call site is
#: ``langflow.services.triggers.principal``.
EXECUTION_FAMILY_KWARG = "execution_family"

#: Template field the dispatcher writes the firing event into, as a JSON string,
#: through the run request's ``tweaks`` keyed by the trigger's canvas node id.
#: This is the seam that carries a provider payload into the flow; it is the
#: same mechanism the Webhook component's payload rides. Equal, character for
#: character, to ``lfx.base.triggers.base.TRIGGER_EVENT_FIELD`` (lfx must not
#: import langflow, so the string is declared on both sides and pinned by
#: ``test_trigger_event_field_matches_the_lfx_component_contract``).
TRIGGER_EVENT_FIELD = "event_payload"

#: Named singleton leases held in ``trigger_lease``.
DISPATCHER_LEASE_NAME = "trigger_dispatcher"
SCHEDULER_LEASE_NAME = "trigger_scheduler"

#: Session-id prefixes. ``per_event`` gives each run its own session;
#: ``shared`` keeps one session per trigger so an agent has memory across ticks.
SESSION_PREFIX = "trigger"

#: Ledger dedupe-key prefixes, one per producer.
TICK_DEDUPE_PREFIX = "tick"
REPLAY_DEDUPE_PREFIX = "replay"
TEST_DEDUPE_PREFIX = "test"
