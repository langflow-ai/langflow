# Dedicated Integrations: Triggers (1.14 candidate): discovery gate records

Status: gate open; scaffold created 2026-09-02; no exit criterion met yet
Jira: LE-2398 "Dedicated Integrations" is the parent epic; the triggers epic and ticket TRG-1 are to be created
Last updated: 2026-09-02

This directory is the discovery gate for the triggers initiative: persistent listeners, provider push delivery,
subscription lifecycle, durable delivery, replay, deployment binding, and conversation correlation. It is the
separate initiative that the 1.13 actions plan promised in Scope Boundary 1 and that
[`../dedicated-integrations/triggers-deferred.md`](../dedicated-integrations/triggers-deferred.md) records as
deferred. It is modeled on the INT-1 gate ([`../dedicated-integrations/README.md`](../dedicated-integrations/README.md)):
the gate freezes what the triggers release ships before any listener or subscription code is written, and every
other triggers ticket (TRG-2 onward) blocks on it.

The gate runs in parallel with 1.13 execution and does not change 1.13 scope. Risk 7 of the governing plan stands:
pulling triggers into 1.13 invalidates the 48.75 engineer-week estimate.

## Why a separate initiative

- Request/response actions and persistent triggers are different lifecycle and delivery products (governing plan,
  Scope Boundary 1; `triggers-deferred.md`). No wave-1 action opens a listener or creates a subscription.
- Listening cannot run inside the API process. The platform owner's position (Gabriel Almeida, 2026-09-02): a
  listener needs a separate service or a subprocess supervisor, one instance per bot, so that API replicas,
  restarts, and autoscaling neither duplicate nor drop connections. Nothing in the repo supervises a long-lived
  process today (see "Runtime seams").
- Two prior attempts exist and neither merged (see "Precedents"). Both hosted the listener in the API process,
  which is the shape this initiative must not repeat.
- The deferred record's re-open triggers, as of 2026-09-02: (1) a written findings document: requested from the
  platform owner, pending; (2) a customer commitment naming a trigger-driven flow for a dated release: none
  recorded; (3) two of three providers' event delivery confirmed usable from a self-managed instance without public
  ingress: Slack Socket Mode is documented as such (one of two); whether a Gmail Pub/Sub pull subscription and a
  Microsoft Graph delivery alternative qualify is a Phase 2 question.

## Boundary with 1.13

What 1.13 owes this initiative, and nothing more:

| Obligation | Where it lives | Status |
|---|---|---|
| The INT-2 connection resolver is callable from a non-API process: a sidecar resolves connections through the registered `BaseConnectionResolverService`, not through HTTP routes | `../dedicated-integrations/connection-contract.md` section 3; question 12.a.2 | in the 1.13 contract, unsigned |
| INT-5 single-flight refresh coordinates across processes, not only across uvicorn workers | `connection-contract.md` section 6; question 12.b.4 | in the 1.13 contract, unsigned |
| INT-6 rules for non-interactive execution apply verbatim to trigger-driven runs: the `flow_owner` and `deployment_owner` families resolve a user connection only with the per-connection `allow_non_interactive` opt-in, and anonymous execution never does | `connection-contract.md` section 4; `scripts/ci/execution_principal_matrix.json` | in the 1.13 contract |
| The connection record carries no trigger-specific fields, and the INT-3 manifest `integrations` field reserves no event fields | `triggers-deferred.md`, "Interaction with the actions release" | recorded |

What this gate must not do: reopen a 1.13 decision, add to the 1.13 estimate, or block a 1.13 sign-off.

## Two tracks

**Track A: push ingress.** The provider posts to a Langflow URL. Needs a public HTTPS endpoint, provider signature
or handshake verification, subscription creation and renewal, and a mapping from event to flow run. It belongs on
the API process because it is request/response at the edge; today's `POST /api/v1/webhook/{flow_id_or_name}` is the
closest seam. Candidate mechanisms to source in Phase 2: Microsoft Graph change notifications (validation handshake,
`clientState`, expiring subscriptions, lifecycle notifications), Gmail `users.watch` with a Pub/Sub push
subscription, and the Slack Events API (URL verification, request signing, acknowledgement deadline).

**Track B: persistent connections.** Langflow holds an outbound connection open: Slack Socket Mode, the Discord
gateway, a Gmail Pub/Sub pull subscription, and any source whose only option is polling. Needs a supervised process
outside the API, one instance per connection (bot), a lease so exactly one replica holds each connection, health,
backoff, and a hand-off to the run path. No repo seam provides this today.

Both tracks share the trigger entity, binding, correlation, delivery semantics, the executing-identity rule, and the
frontend. Track A can ship before Track B; the gate decides whether it should.

## Exit criteria and where each one lives

| # | Exit criterion | Artifact | Machine check | Status |
|---|---|---|---|---|
| 1 | Findings document covering both precedents and the sidecar position, authored by the platform owner | `findings/2026-09-listeners.md` | none | requested 2026-09-02 |
| 2 | Event-transport matrix per wave-1 provider: every push and pull mechanism with its ingress requirement, inbound authentication, subscription TTL and renewal, payload shape (thin or full), delivery guarantee, replay availability, rate limits, and the deployment contexts it supports | `matrices/<provider>-events.json`, `schema/event_transport.schema.json` | checker extension (`--design-root`): schema, sourced claims, and the no-ingress rule per context | not started |
| 3 | Process-model decision: subprocess supervisor under the API lifespan, separate service, or both; lease semantics for singleton listeners; behaviour on Desktop, `lfx serve`, single-container Docker, and multi-replica Kubernetes | `decisions/process-model.md` | `Status:` line and `## Decision` heading parsed by the checker | not started |
| 4 | Self-managed ingress decision: which Track A sources require public HTTPS, which Track B fallback exists per provider, and the explicit statement that Langflow operates no relay | `decisions/self-managed-ingress.md` | none | not started; Slack Socket Mode is one confirmed fallback |
| 5 | Delivery-semantics decision: at-least-once with idempotency keys, replay window, dead-letter, ordering, and backpressure toward the run path | `decisions/delivery-semantics.md` | none | not started |
| 6 | Trigger contract: the trigger entity and its binding to a flow version or deployment; correlation of a triggered run to a conversation; executing identity per trigger kind as new `execution_principal_matrix.json` families (`trigger_push`, `trigger_listener`); signed off by the lfx, langflow-base, Enterprise, and platform owners | `trigger-contract.md` | sign-off coverage | not started |
| 7 | 1.13 conformance: the boundary table above checked against the merged INT-2, INT-5, and INT-6 pull requests | this file, "Boundary with 1.13" | none | blocked on those PRs |
| 8 | Frontend surface list: trigger node, subscription status, event log and replay, operator controls | `frontend-surfaces.md` | none | not started |
| 9 | Estimate and ticket breakdown, TRG-2 onward | `estimate.md` | none | not started |

Gate close means: every row above is done, every record under `decisions/` is `Status: accepted`, and every
declared owner has completed both sign-off tables.

## Precedents (verified against the branches on 2026-09-02)

Paths are under `src/backend/base/langflow/` unless stated.

| Branch | What it built | Where the listener ran | Why it informs the gate |
|---|---|---|---|
| `origin/mock-orchestra` (2024-08 to 2025-03, never merged) | `task` and `subscription` tables (`alembic/versions/02e8c952e7ca_add_tasks_and_subscriptions.py`); `TaskOrchestrationService` (`services/task_orchestration/service.py:50`); `TriggerService` (`services/triggers/service.py:27`); `DiscordService` (`services/discord/service.py:17`); `BaseTriggerComponent` (`base/triggers/model.py:15`); `api/v1/subscriptions.py`; trigger components for Discord messages, Gmail inbox, local files, schedules, and task status (`components/triggers/`) | in the API process, started from lifespan; one Discord gateway client per bot from an environment token | the closest thing to Track B that exists; one instance per bot is the right shape, the host process is the wrong one |
| `origin/feat-native-triggers-v2` (2026-05-20 to 22, no PR) | `trigger` and `trigger_job` tables (`alembic/versions/tg01a2b3c4d5_add_native_triggers_schema.py`); a cron trigger component in lfx; a Postgres queue drained with `FOR UPDATE SKIP LOCKED` (optimistic update on SQLite); one asyncio worker per uvicorn worker started in lifespan; flow-save reconciliation; triggers API and UI | in the API process | adequate for cron; the queue and reconciliation pieces are candidates for Track A; not a listener host |

## Runtime seams on `release-1.13.0` (verified 2026-09-02)

| Seam | Location | What it gives triggers | What it lacks |
|---|---|---|---|
| Webhook entry | `api/v1/endpoints.py:1314` `webhook_run_flow`; `:1236` `webhook_events_stream`; `scripts/ci/execution_principal_matrix.json` family `webhook` executes as `flow_owner` | Track A's HTTP edge and its identity rule | provider signature verification, subscription state, replay |
| Background execution | `services/background_execution/service.py:95` `BackgroundExecutionService`, `:286` `submit`; `executor.py:26` `InProcessExecutor`; `runner.py:53` `JobRunner`; `services/jobs/service.py:59` `JobService` | the run path a trigger hands events to; job ownership | no supervisor for anything that is not a job |
| Celery | `core/celery_app.py` | a worker-process boundary | not wired to flow execution in OSS; no long-lived task model |
| Enterprise lifespan hooks | `main.py:87` `_enterprise_lifespan_hooks`, run at `:653` (startup) and `:697` (shutdown) | a place to start and stop a supervisor | in-process only |
| Headless | `src/lfx/src/lfx/cli/serve_app.py`, `serve_durable.py`, `serve_workflow.py` | nothing: `lfx run` and `lfx serve` do not host listeners (governing plan) | Track B is out of scope there; Track A on `lfx serve` is a gate question |

## Sign-off

Acceptance rule: as in the INT-1 gate, `Status: accepted` on a record means the release owner accepted it; every
other role a record names signs off in PR review by filling in its row below and in the record's own sign-off table.
Role placeholders remain until the release owner assigns names.

| Role | Signs off on | Name | Date | PR |
|---|---|---|---|---|
| platform owner | `findings/`, `decisions/process-model.md`, `decisions/self-managed-ingress.md`, `decisions/delivery-semantics.md`, `trigger-contract.md` | | | |
| lfx owner | `trigger-contract.md` | | | |
| langflow-base owner | `trigger-contract.md`, `decisions/process-model.md` | | | |
| Enterprise owner | `trigger-contract.md`, `decisions/self-managed-ingress.md` | | | |
| hosted-app owner | event rows of every matrix (hosted subscriptions, verification of event scopes, the Slack Events API on the hosted app) | | | |
| frontend owner | `frontend-surfaces.md` | | | |
| release owner | every record in this directory, `estimate.md`, gate close | Eric Hare | 2026-09-02 | #14911 |

## Running the checker

Not yet. `scripts/ci/check_capability_matrices.py` is rooted at `design/dedicated-integrations`. The first Phase 0
change is a `--design-root` argument so the same decision-record and sign-off validation runs here, followed by a
schema for event transports in Phase 2. Until then the records in this directory are reviewed by hand.

## Directory map

```text
README.md                          this file
decisions/TEMPLATE.md              decision-record template (same parse rules as the INT-1 checker)
findings/                          (Phase 1) the platform owner's findings document
schema/event_transport.schema.json (Phase 2) JSON Schema for one provider's event-transport matrix
matrices/<provider>-events.json    (Phase 2) one event-transport matrix per wave-1 provider
decisions/process-model.md         (Phase 3)
decisions/self-managed-ingress.md  (Phase 3)
decisions/delivery-semantics.md    (Phase 4)
trigger-contract.md                (Phase 4) TRG-2 design for sign-off
frontend-surfaces.md               (Phase 5)
estimate.md                        (Phase 6) with the TRG ticket breakdown
```

## Phases

| Phase | Deliverables | Needs a decision from the release owner |
|---|---|---|
| 0 | this scaffold; checker `--design-root`; triggers epic and TRG-1 in Jira | no |
| 1 | findings document (platform owner) | no |
| 2 | event-transport matrices for Google, Microsoft, and Slack, with the schema | yes: which sources are candidates for the first wave |
| 3 | process-model and self-managed ingress decisions | yes |
| 4 | delivery-semantics decision and the trigger contract | review by the lfx, langflow-base, Enterprise, and platform owners |
| 5 | frontend surfaces | no |
| 6 | estimate and TRG ticket breakdown; gate close | yes |

Re-verify by: the 1.14 planning gate.
