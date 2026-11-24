# Delivery semantics for triggered runs

Status: proposed
Decision ID: delivery-semantics
Applies to: the `trigger_event` ledger and the dispatcher (TRG-2); every `delivery`, `replay` and `dedupe_key` block in `matrices/*-events.json`
Owners (sign-off roles): platform owner, langflow-base owner, release owner
Last verified: 2026-09-15 (criterion 5 reopened after delivery review)

## Context

TRG-1 exit criterion 5. Provider delivery can duplicate or lose notifications: retries are bounded, and Calendar
explicitly documents dropped notifications even during normal operation. Pub/Sub's at-least-once transport does
not make every upstream Gmail change recoverable. A flow run is not idempotent: it posts messages, writes files,
and bills tokens. The gate therefore has to decide once, for every provider, where duplicates are collapsed, how long an event stays
replayable, what happens to an event that never succeeds, whether ordering is promised, and what backpressure the run
path applies - before TRG-2 writes the ledger and before TRG-4 and TRG-5 write their ack paths.

**Reopened 2026-09-15.** The ledger index alone cannot provide the previously claimed one-run guarantee. The
platform and langflow-base owners must resolve the following before criterion 5 closes; the lfx owner must review
the resulting dispatch contract under criterion 6. The 2026-09-05 signature records the earlier baseline only.

- **Durable intake before normalization.** Calendar notifications contain no changed-event identity, and a Gmail
  history watermark can expand into several changes. The current matrices defer the provider read until a job,
  but require a normalized change key before inserting the row that starts that job. Specify durable storage for
  the notification before acknowledgement, the worker that expands it into canonical events, and atomic cursor
  advancement after every page's events are persisted. Decide the storage shape and include it in the migration
  and estimate. A notification key and a canonical change key serve different purposes.
- **A recoverable dispatch handoff.** A worker can submit a job and die before saving `trigger_event.job_id`.
  Lease expiry then permits another submission of the same ledger row. Specify a durable event-to-job identity
  and recovery protocol, including a job that finishes or is purged before recovery. Exercise crash points around
  submission and recording the result. The event index and a singleton lease do not make those writes atomic.
- **Bounded recovery and retention.** Select periodic reconciliation for lossy push sources, including hosted
  deployments. A full list after cursor expiry is a current snapshot, not an archive of every past change.
  Purging dedupe rows at 30 days also permits old unchanged items to run again during a full resync. Define
  re-baselining or longer-lived dedupe state, deletion handling, and the recovery limits the UI reports.

Provider evidence: [Calendar notification payloads and reliability](https://developers.google.com/workspace/calendar/api/guides/push),
[Gmail history recovery](https://developers.google.com/workspace/gmail/api/guides/sync), and
[Graph webhook delivery limits](https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks).
Repository evidence: `BackgroundExecutionService.submit` creates a job independently of any trigger ledger update;
`JobService.create_job` checks then inserts a dedupe key without a unique constraint.

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

Option C remains the proposed direction, subject to the reopened requirements above.

**Canonical-event dedupe.** Ingress and listeners never execute a flow. After normalization, each canonical change
gets a `trigger_event` row. `trigger_event` carries a `UNIQUE (trigger_id, dedupe_key)` index, and an insert that violates it is an
idempotent success, not an error - Slack's three retries (fact 1), Graph's duplicates (fact 3), and Pub/Sub's
redeliveries (fact 4) collapse to one canonical event row while its dedupe entry is retained. This does not by itself
guarantee one job or one external side effect. The ledger's index is the *only* database-level
dedupe guarantee in the system; the dispatcher does not rely on `Job.dedupe_key` (fact 6).

**Dedupe keys are per mechanism and recorded in the matrices.** Where the provider supplies a stable identity it is
used verbatim (Slack `event_id`, fact 2). Where it does not, the key is derived from the changed item's identity and
version - Graph from canonical resource identity, item id and provider version (never `subscriptionId`), Calendar
from calendar id, event id and `updated`, Drive from `fileId` and `modifiedTime`, and Gmail from mailbox, history
record id and individual change identity (one history record can contain several message changes) - and
the derivation must agree after push and poll normalization. A thin notification may not contain that identity;
its durable intake and expansion are open requirements above. A `sync` message (fact 5) does not represent a change.

**Ack ordering.** A listener acknowledges only after durable intake commits. Full events may be normalized directly
into the ledger; the storage boundary for thin notifications remains open above. An ingress route answers within
the provider's deadline and, if the write cannot
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
- TRG-8 must distinguish provider-side loss, accepted notifications, canonical events, submitted jobs, and run
  attempts. Add the crash and resync cases above before claiming zero lost accepted events or duplicate submissions;
  run retries cannot promise exactly-once external side effects.
- Fact 8 means even a single-container SQLite deployment needs the lease rows; "single process" is never assumed.

## Re-open trigger

- A provider ships an ordered, exactly-once delivery Langflow can honour end to end, or
- the 7-day replay window proves wrong in the soak (either too short for a real recovery or too expensive to retain),
  or
- `Job.dedupe_key` gains a database unique index, which would let the dispatcher lean on it for the submit step.

Re-verify by: the 1.13 release sign-off, after the reopened delivery requirements are resolved.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| platform owner | | | |
| langflow-base owner | | | |
| release owner | Eric Hare | 2026-09-05 | #14911 |
