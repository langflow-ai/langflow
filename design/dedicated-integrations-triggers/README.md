# Dedicated Integrations: Triggers (1.13): discovery gate records

Status: records written; every decision record is `Status: accepted`; exit criterion 1 (the platform owner's findings) is a stub and the sign-off tables are outstanding
Jira: LE-2398 "Dedicated Integrations" is the parent epic; LE-2477 "Integration Triggers" is the triggers epic; TRG-1 is LE-2480
Last updated: 2026-09-05

This directory is the discovery gate for the triggers initiative: persistent listeners, provider push delivery,
subscription lifecycle, durable delivery, replay, deployment binding, and conversation correlation. It is the
separate initiative that the 1.13 actions plan promised in Scope Boundary 1 and that
[`../dedicated-integrations/triggers-deferred.md`](../dedicated-integrations/triggers-deferred.md) records as
deferred. It is modeled on the INT-1 gate ([`../dedicated-integrations/README.md`](../dedicated-integrations/README.md)):
the gate freezes what the triggers release ships before any listener or subscription code is written, and every
other triggers ticket (TRG-2 onward) blocks on it.

**Release target, decided 2026-09-04 by the release owner.** The triggers epic is 1.13 scope and every TRG ticket
gets a pull request now. The scaffold created on 2026-09-02 called this directory a 1.14 candidate and
[`../dedicated-integrations/estimate.md`](../dedicated-integrations/estimate.md) excludes triggers from the 1.13
total; both are superseded by that decision and are amended rather than left to contradict this record.
[`estimate.md`](estimate.md) carries the new numbers: 39.5 engineer-weeks for TRG-1 through TRG-8, additional to the
48.75 the actions release carries. Risk 7 of the governing plan (pulling triggers into 1.13 invalidates the actions
estimate) is answered by adding capacity, not by re-scoping the actions release: no INT ticket loses scope here.

## Why a separate initiative

- Request/response actions and persistent triggers are different lifecycle and delivery products (governing plan,
  Scope Boundary 1; `../dedicated-integrations/triggers-deferred.md`). No wave-1 action opens a listener or creates a
  subscription.
- Listening cannot run inside the API process. The platform owner's position (Gabriel Almeida, 2026-09-02): a
  listener needs a separate service or a subprocess supervisor, one instance per bot, so that API replicas,
  restarts, and autoscaling neither duplicate nor drop connections. Nothing in the repo supervises a long-lived
  process today (see "Runtime seams"). [`decisions/process-model.md`](decisions/process-model.md) turns that position
  into a decision.
- Two prior attempts exist and neither merged (see "Precedents"). Both hosted the listener in the API process,
  which is the shape this initiative must not repeat.
- The deferred record's re-open triggers, as of 2026-09-05: (1) a written findings document: stubbed at
  [`findings/2026-09-listeners.md`](findings/2026-09-listeners.md) with the evidence gathered, awaiting the platform
  owner's authored sections; (2) a customer commitment naming a trigger-driven flow for a dated release: none
  recorded, and the release owner's 1.13 decision does not depend on one; (3) two of three providers' event delivery
  confirmed usable from a self-managed instance without public ingress: **three of three**, recorded in
  [`decisions/self-managed-ingress.md`](decisions/self-managed-ingress.md) and machine-checked in the matrices - Slack
  Socket Mode, Microsoft Graph delta queries, and Google sync-token/page-token polling plus Cloud Pub/Sub pull.

## Boundary with 1.13

What 1.13 owes this initiative, and nothing more:

| Obligation | Where it lives | Status |
|---|---|---|
| The INT-2 connection resolver is callable from a non-API process: a sidecar resolves connections through the registered `BaseConnectionResolverService`, not through HTTP routes | `../dedicated-integrations/connection-contract.md` section 3; question 12.a.2 | in the 1.13 contract, unsigned; required by `decisions/process-model.md` |
| INT-5 single-flight refresh coordinates across processes, not only across uvicorn workers | `../dedicated-integrations/connection-contract.md` section 6; question 12.b.4 | in the 1.13 contract, unsigned; the listener process refreshes the same connections the API does |
| INT-6 rules for non-interactive execution apply verbatim to trigger-driven runs: the `flow_owner` and `deployment_owner` families resolve a user connection only with the per-connection `allow_non_interactive` opt-in, and anonymous execution never does | `../dedicated-integrations/connection-contract.md` section 4; `scripts/ci/execution_principal_matrix.json` | in the 1.13 contract; `trigger-contract.md` section 5 adds two families and weakens no rule |
| The connection record carries no trigger-specific fields, and the INT-3 manifest `integrations` field reserves no event fields | `../dedicated-integrations/triggers-deferred.md`, "Interaction with the actions release" | held: trigger state lives on the `trigger` and `trigger_subscription` tables, and TRG-6 adds an additive bundle-owned `triggers` list rather than event fields on a capability |
| One gap found while writing this gate: the contract assigns the `connection_resolution` matrix dimension and its checker vocabulary to INT-4 and INT-5, and neither open pull request delivers it | `../dedicated-integrations/connection-contract.md` section 11 | filed against 1.13 and picked up by INT-6, which now owns the dimension; TRG-2 adds family rows only |

Exit criterion 7 asks for this table to be checked against the **merged** INT-2, INT-5 and INT-6 pull requests. Those
are open at the time of writing, so the criterion stays open with the gap above recorded; it is re-walked when the
INT stack merges and before gate close.

What this gate must not do: reopen a 1.13 decision, add to the 1.13 actions estimate, or block a 1.13 sign-off.

## Two tracks

**Track A: push ingress.** The provider posts to a Langflow URL. Needs a public HTTPS endpoint, provider signature
or handshake verification, subscription creation and renewal, and a mapping from event to flow run. It belongs on
the API process because it is request/response at the edge; today's `POST /api/v1/webhook/{flow_id_or_name}` is the
closest seam. Wave-1 mechanisms, sourced in the matrices: Microsoft Graph change notifications
(`microsoft.graph_change_notifications`), Google Calendar and Drive push channels (`google.calendar_push`,
`google.drive_push`), Gmail `users.watch` with a Cloud Pub/Sub push subscription
(`google.gmail_watch_pubsub_push`), and the Slack Events API (`slack.events_api`).

**Track B: persistent connections and polling.** Langflow reaches out: Slack Socket Mode (`slack.socket_mode`), a
Gmail Pub/Sub pull subscription (`google.gmail_watch_pubsub_pull`), Microsoft Graph delta queries
(`microsoft.graph_delta_poll`), and Google Calendar and Drive change feeds (`google.calendar_sync_poll`,
`google.drive_changes_poll`). Needs a supervised process outside the API, one instance per connection, a lease so
exactly one replica holds each connection, health, backoff, and a hand-off to the run path. No repo seam provides
this today; [`decisions/process-model.md`](decisions/process-model.md) decides the shape.

Both tracks share the trigger entity, binding, correlation, delivery semantics, the executing-identity rule, and the
frontend, all frozen in [`trigger-contract.md`](trigger-contract.md). Every provider ships at least one Track B
mechanism, which is what makes the no-relay rule liveable.

## Exit criteria and where each one lives

| # | Exit criterion | Artifact | Machine check | Status |
|---|---|---|---|---|
| 1 | Findings document covering both precedents and the sidecar position, authored by the platform owner | `findings/2026-09-listeners.md` | sign-off coverage | **open**: stub written 2026-09-05 with the evidence pack; sections 3 and 4 are the platform owner's |
| 2 | Event-transport matrix per wave-1 provider: every push and pull mechanism with its ingress requirement, inbound authentication, subscription TTL and renewal, payload shape (thin or full), delivery guarantee, replay availability, rate limits, and the deployment contexts it supports | `matrices/<provider>-events.json`, `schema/event_transport.schema.json` | `check_capability_matrices.py --design-root`: schema, sourced claims, and the no-ingress rule per context | done 2026-09-05 |
| 3 | Process-model decision: subprocess supervisor under the API lifespan, separate service, or both; lease semantics for singleton listeners; behaviour on Desktop, `lfx serve`, single-container Docker, and multi-replica Kubernetes | `decisions/process-model.md` | `Status:` line and `## Decision` heading parsed by the checker | accepted 2026-09-05 |
| 4 | Self-managed ingress decision: which Track A sources require public HTTPS, which Track B fallback exists per provider, and the explicit statement that Langflow operates no relay | `decisions/self-managed-ingress.md` | the checker's no-ingress rule enforces the fallback per context | accepted 2026-09-05 |
| 5 | Delivery-semantics decision: at-least-once with idempotency keys, replay window, dead-letter, ordering, and backpressure toward the run path | `decisions/delivery-semantics.md` | `Status:` line and `## Decision` heading parsed by the checker | accepted 2026-09-05 |
| 6 | Trigger contract: the trigger entity and its binding to a flow version or deployment; correlation of a triggered run to a conversation; executing identity per trigger kind as new `execution_principal_matrix.json` families (`trigger_push`, `trigger_listener`); signed off by the lfx, langflow-base, Enterprise, and platform owners | `trigger-contract.md` | sign-off coverage | written and accepted 2026-09-05; four sign-offs outstanding |
| 7 | 1.13 conformance: the boundary table above checked against the merged INT-2, INT-5, and INT-6 pull requests | this file, "Boundary with 1.13" | none | **open**: those pull requests are unmerged; one gap already filed (the `connection_resolution` dimension) |
| 8 | Frontend surface list: trigger node, subscription status, event log and replay, operator controls | `frontend-surfaces.md` | sign-off coverage | done 2026-09-05 |
| 9 | Estimate and ticket breakdown, TRG-2 onward | `estimate.md` | none | done 2026-09-05; TRG-2 (LE-2481) through TRG-8 (LE-2482) exist in Jira under LE-2477 |

Gate close means: every row above is done, every instantiated decision record under `decisions/` except
`TEMPLATE.md` is `Status: accepted`, and every declared owner has completed both sign-off tables. Two rows (1 and 7)
are open, so the gate is not closed; `--require-accepted` is the machine expression of gate close and does not pass
yet, by design.

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
| Background execution | `services/background_execution/service.py:95` `BackgroundExecutionService`, `:286` `submit`; `executor.py:26` `InProcessExecutor`; `runner.py:53` `JobRunner`; `services/jobs/service.py:59` `JobService` | the run path a trigger hands events to; job ownership | no supervisor for anything that is not a job; no frame source is installed until a v2 workflow route runs, so the dispatcher registers its own |
| Celery | `core/celery_app.py` | a worker-process boundary | not wired to flow execution in OSS; no long-lived task model |
| Enterprise lifespan hooks | `main.py:87` `_enterprise_lifespan_hooks`, run at `:653` (startup) and `:697` (shutdown) | a place to start and stop a supervisor | in-process only, and best-effort |
| Headless | `src/lfx/src/lfx/cli/serve_app.py`, `serve_durable.py`, `serve_workflow.py` | nothing: `lfx run` and `lfx serve` do not host listeners (governing plan) | Track B is out of scope there, and `decisions/process-model.md` answers the gate question about Track A on `lfx serve`: it is not hosted either |

## Sign-off

Acceptance rule: as in the INT-1 gate, `Status: accepted` on a record means the release owner accepted it; every
other role a record names signs off in PR review by filling in its row below and in the record's own sign-off table.
Role placeholders remain until the release owner assigns names.

| Role | Signs off on | Name | Date | PR |
|---|---|---|---|---|
| platform owner | `findings/2026-09-listeners.md`, `decisions/process-model.md`, `decisions/self-managed-ingress.md`, `decisions/delivery-semantics.md`, `trigger-contract.md` | | | |
| lfx owner | `trigger-contract.md` | | | |
| langflow-base owner | `trigger-contract.md`, `decisions/process-model.md`, `decisions/delivery-semantics.md` | | | |
| Enterprise owner | `trigger-contract.md`, `decisions/process-model.md`, `decisions/self-managed-ingress.md` | | | |
| hosted-app owner | `decisions/self-managed-ingress.md`, and the event rows of every matrix (hosted subscriptions, verification of event scopes, the Slack Events API on the hosted app) | | | |
| frontend owner | `frontend-surfaces.md` | | | |
| release owner | every record in this directory, `estimate.md`, gate close | Eric Hare | 2026-09-05 | #14911 |

## Running the checker

```bash
python scripts/ci/check_capability_matrices.py --design-root design/dedicated-integrations-triggers
```

`--design-root` points the INT-1 checker at this directory. A design root that publishes
`schema/event_transport.schema.json` is validated as a triggers gate: `matrices/<provider>-events.json` is checked
against that schema, every claim block on a wave-1 mechanism must name a source that resolves, and the no-ingress
rule is enforced per deployment context - a mechanism that needs public HTTPS may not claim a context where
`public_ingress_by_context` says ingress is unavailable, and a `conditional` context is allowed only when the
mechanism names an `outbound_only` fallback covering that same context. Every provider must ship at least one
outbound-only wave-1 mechanism. Decision-record parsing (`Status:` line, `## Decision` heading) and sign-off coverage
run exactly as they do for INT-1. Adding `--require-accepted` is gate-close mode and fails today, correctly: the
sign-off tables are empty.

The rules live in `scripts/ci/event_transport_matrix.py`; `scripts/ci/test_event_transport_matrices.py` covers them
and runs in the CI Scripts Tests workflow, which now watches this directory.

## Directory map

```text
README.md                              this file
decisions/TEMPLATE.md                  decision-record template (same parse rules as the INT-1 checker)
findings/2026-09-listeners.md          the platform owner's findings (stub; criterion 1)
schema/event_transport.schema.json     JSON Schema for one provider's event-transport matrix
matrices/google-events.json            Google Workspace event transports
matrices/microsoft-events.json         Microsoft 365 event transports
matrices/slack-events.json             Slack event transports
decisions/process-model.md             criterion 3
decisions/self-managed-ingress.md      criterion 4
decisions/delivery-semantics.md        criterion 5
trigger-contract.md                    criterion 6: the TRG-2 design, for sign-off
frontend-surfaces.md                   criterion 8
estimate.md                            criterion 9, with the TRG ticket breakdown
```

## Phases

| Phase | Deliverables | State |
|---|---|---|
| 0 | this scaffold; checker `--design-root`; triggers epic and TRG-1 in Jira | done |
| 1 | findings document (platform owner) | stub written; awaiting the author |
| 2 | event-transport matrices for Google, Microsoft, and Slack, with the schema | done |
| 3 | process-model and self-managed ingress decisions | done |
| 4 | delivery-semantics decision and the trigger contract | written; awaiting the lfx, langflow-base, Enterprise, and platform sign-offs |
| 5 | frontend surfaces | done |
| 6 | estimate and TRG ticket breakdown; gate close | estimate done; gate close waits on criteria 1 and 7 |

Re-verify by: the 1.13 release sign-off.
