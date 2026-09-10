# Delivery semantics for triggered runs

Status: accepted
Decision ID: delivery-semantics
Applies to: the `trigger_event` ledger and the dispatcher (TRG-2); every `delivery`, `replay` and `dedupe_key` block in `matrices/*-events.json`
Owners (sign-off roles): platform owner, langflow-base owner, release owner
Last verified: 2026-09-05

## Context

TRG-1 exit criterion 5. Every wave-1 mechanism is at-least-once at the provider (Slack retries three times, Graph
retries for about four hours and may duplicate and reorder, Pub/Sub is at-least-once and unordered, and every Track B
recovery path replays a window). A flow run is not idempotent: it posts messages, writes files, and bills tokens. The
gate therefore has to decide once, for every provider, where duplicates are collapsed, how long an event stays
replayable, what happens to an event that never succeeds, whether ordering is promised, and what backpressure the run
path applies - before TRG-2 writes the ledger and before TRG-4 and TRG-5 write their ack paths.

## Facts (with citations)

| # | Fact | Source URL | Verified on | Confidence |
|---|------|------------|-------------|------------|
| 1 | Slack retries a failed or slow event delivery three times (immediately, 1 min, 5 min) and disables delivery after sustained failure; the deadline is three seconds | https://docs.slack.dev/apis/events-api/ | 2026-09-05 | high |
| 2 | Slack `event_id` is stable across retries and across a Socket Mode redelivery; `envelope_id` is per delivery | https://docs.slack.dev/apis/socket-mode/ | 2026-09-05 | high |
| 3 | Microsoft Graph notifications may arrive out of order and may be duplicated, and carry no provider event id | https://learn.microsoft.com/en-us/graph/change-notifications-overview | 2026-09-05 | high |
| 4 | Cloud Pub/Sub delivery is at-least-once and unordered unless ordering is enabled; an unacknowledged message is redelivered after the ack deadline | https://cloud.google.com/pubsub/docs/pull | 2026-09-05 | high |
| 5 | Google push channels send an initial `X-Goog-Resource-State: sync` message that carries no change | https://developers.google.com/workspace/calendar/api/guides/push | 2026-09-05 | high |
| 6 | `Job.dedupe_key` has no database unique index: `create_job` counts and then inserts, so background-execution idempotency is racy across replicas | `src/backend/base/langflow/services/jobs/service.py` create_job | 2026-09-05 | high |
| 7 | A guarded-`UPDATE` claim (`FOR UPDATE SKIP LOCKED` on PostgreSQL, `UPDATE ... WHERE state = 'pending'` on SQLite) is already used for job claiming in this repo | `src/backend/base/langflow/services/jobs/service.py` | 2026-09-05 | high |
| 8 | The default API worker count is greater than one, so even SQLite deployments run several processes against one file | `src/backend/base/langflow/__main__.py` | 2026-09-05 | high |

## Options

### Option A: exactly-once end to end

Pros: the semantics a user assumes.
Cons: undeliverable. Fact 3 alone (duplicated, unordered, id-less notifications) means the provider cannot supply the
identity an exactly-once contract needs, and fact 6 means the run layer cannot supply it either.
Cost: unbounded.

### Option B: at-least-once with per-provider dedupe inside each source adapter

Pros: each adapter can use the sharpest key it knows.
Cons: five adapters each own a correctness-critical invariant, with no single place to test it; a resync path and a
push path in the same provider can disagree and re-run flows.
Cost: repeated per provider, and repeated again for every future provider.

### Option C: at-least-once at the edge, collapsed once in the ledger by a database unique index (selected)

Pros: one invariant, one index, one test; adapters only have to *derive* a key, and the recorded-payload contract
tests can pin that push and poll derive the same one. Replay, dead-letter, and backpressure all become properties of
one table.
Cons: the key derivation is still per provider, and a bad derivation degrades to duplicate runs rather than to an
error, so it has to be tested rather than reviewed.
Cost: one migration and one dispatcher, both already in TRG-2.

## Decision

Option C.

**At-least-once, collapsed once.** Ingress and listeners never execute a flow; they write one `trigger_event` row and
return. `trigger_event` carries a `UNIQUE (trigger_id, dedupe_key)` index, and an insert that violates it is an
idempotent success, not an error - Slack's three retries (fact 1), Graph's duplicates (fact 3), and Pub/Sub's
redeliveries (fact 4) all collapse to one row and therefore one run. The ledger's index is the *only* database-level
dedupe guarantee in the system; the dispatcher does not rely on `Job.dedupe_key` (fact 6).

**Dedupe keys are per mechanism and recorded in the matrices.** Where the provider supplies a stable identity it is
used verbatim (Slack `event_id`, fact 2). Where it does not, the key is derived from the changed item's identity and
version - Graph from `subscriptionId`/`resource`/`resourceData.id`/`changeType`/etag, Google Calendar from calendar
id, event id and `updated`, Drive from `fileId` and `modifiedTime`, Gmail from mailbox and history record id - and
the derivation must be reachable from both the push payload and the poll item, because every Track A recovery path is
a Track B read. A `sync` message (fact 5) is dropped before the ledger write and never becomes a row.

**Ack ordering.** A listener acknowledges the provider only after the ledger write has committed (fact 4's
redelivery is the safety net). An ingress route answers within the provider's deadline and, if the write cannot
complete in time, answers non-2xx so the provider retries rather than answering 2xx and losing the event.

**Replay window: 7 days, purge at 30 days.** Ledger rows stay replayable for 7 days from receipt; rows older than 30
days are purged by a leased job. Replay writes a *new* row linked by `replay_of_event_id` rather than mutating the
original, so lineage survives and the unique index is not fought. Catch-up for a missed schedule tick coalesces
within the replay window: many missed ticks produce one run, not a storm.

**Retries and dead-letter.** A claimed event is leased; an expired lease returns it to `pending` with `attempt + 1`.
Attempts are capped per trigger (`max_attempts`, default 5) with exponential backoff and jitter, and an event that
exhausts them moves to `dead` with the last error retained. Dead rows never dispatch again on their own; an operator
replays them explicitly. A trigger whose events die repeatedly moves to `error` so the failure is visible on the
trigger rather than only in the ledger.

**Ordering is not promised.** No mechanism guarantees it (facts 3, 4) and the ledger does not add one. Per-trigger
run concurrency is capped (`concurrency_limit`, default 1) so events for one trigger execute one at a time in claim
order, which is the closest useful approximation and is what a conversation-correlated flow actually needs.
Cross-trigger ordering is undefined and documented as such.

**Backpressure.** The dispatcher claims a bounded batch and never claims more than the per-trigger concurrency cap
allows, so a burst grows the ledger rather than the run queue. When the run path rejects a submission the event is
rescheduled with backoff, not dropped. The ledger is the buffer; that is why the purge job, not the ingress, bounds
its size.

## Consequences

- TRG-2 owns the `UNIQUE (trigger_id, dedupe_key)` index, the claim/lease/retry/dead-letter state machine, the replay
  and purge jobs, and the `replay_of_event_id` self-reference; all of it is in one migration.
- TRG-4's ingress and TRG-5's Socket Mode adapter both write-then-ack; TRG-4's ingress performs no outbound HTTP and
  no execution inside the request, which is what makes the three-second Slack deadline and the ten-second Graph
  handshake reachable.
- TRG-6's recorded-payload contract tests must assert that push and poll produce byte-identical dedupe keys for the
  same change; without that assertion a Graph resync or a Google full list re-runs flows.
- TRG-7 shows attempts, dedupe key, state, and replay lineage per event, and the operator replay action is explicit
  rather than automatic.
- TRG-8's soak measures exactly these numbers: zero lost events, zero duplicate runs, dead-letter only after
  `max_attempts`.
- Fact 8 means even a single-container SQLite deployment needs the lease rows; "single process" is never assumed.

## Re-open trigger

- A provider ships an ordered, exactly-once delivery Langflow can honour end to end, or
- the 7-day replay window proves wrong in the soak (either too short for a real recovery or too expensive to retain),
  or
- `Job.dedupe_key` gains a database unique index, which would let the dispatcher lean on it for the submit step.

Re-verify by: the 1.14 planning gate.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| platform owner | | | |
| langflow-base owner | | | |
| release owner | Eric Hare | 2026-09-05 | #14911 |
