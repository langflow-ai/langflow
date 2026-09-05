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

#: Job request key carrying the execution family to the worker. INT-6 owns the
#: helper that reads it back; the key name is agreed with that ticket so the two
#: stamping paths never diverge.
EXECUTION_FAMILY_REQUEST_KEY = "execution_family"

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
