# Findings: listener hosting, the two precedents, and the sidecar position

Status: draft
Author: <platform owner - Gabriel Almeida> (sections 3 and 4 are the author's; sections 1 and 2 are the evidence pack this stub carries for them)
Owners (sign-off roles): platform owner, release owner
Last verified: 2026-09-05

TRG-1 exit criterion 1, and the first of the three re-open triggers recorded in
[`../dedicated-integrations/triggers-deferred.md`](../dedicated-integrations/triggers-deferred.md). The criterion asks
the platform owner for a written document on both precedents and on the sidecar position. This file is the stub the
gate PR ships: the repository evidence is gathered and dated here so the author writes judgement rather than
archaeology, and the two sections that need the author's own words are marked. It stays `Status: draft` and exit
criterion 1 stays open until they are filled and the platform owner signs below.

## 1. What the precedents actually built (verified against the branches)

Paths are under `src/backend/base/langflow/` unless stated.

### `origin/mock-orchestra` (2024-08 to 2025-03, never merged)

| Piece | Where |
|---|---|
| `task` and `subscription` tables | `alembic/versions/02e8c952e7ca_add_tasks_and_subscriptions.py` |
| Task orchestration | `services/task_orchestration/service.py:50` |
| Trigger service | `services/triggers/service.py:27` |
| Discord gateway client, one per bot, token from the environment | `services/discord/service.py:17` |
| Base trigger component | `base/triggers/model.py:15` |
| Subscriptions API | `api/v1/subscriptions.py` |
| Trigger components: Discord message, Gmail inbox, local file, schedule, task status | `components/triggers/` |

Host process: the API, started from lifespan. The Gmail inbox trigger's `check_events` returns an empty list - the
polling source was never finished.

### `origin/feat-native-triggers-v2` (2026-05-20 to 22, no PR)

| Piece | Where |
|---|---|
| `trigger` and `trigger_job` tables | `alembic/versions/tg01a2b3c4d5_add_native_triggers_schema.py` |
| Cron trigger component | lfx |
| Queue drained with `FOR UPDATE SKIP LOCKED`, optimistic update on SQLite | the trigger job service |
| One asyncio worker per uvicorn worker, started in lifespan | lifespan wiring |
| Flow-save reconciliation, triggers API, triggers UI (29 frontend files) | across the branch |

Host process: the API. The queue, the reconciliation, and the singleton-drop gating in the palette are the parts this
initiative should reuse; the worker-per-uvicorn-worker shape is the part it must not.

## 2. Why neither shape survives contact with the current runtime

| Constraint | Evidence | Consequence for a listener in the API process |
|---|---|---|
| The API runs several worker processes by default (`(cpu_count() * 2) + 1`) | `__main__.py` worker default | every worker would open its own provider connection |
| Slack counts stale Socket Mode connections against a ten-per-app cap until they time out | https://docs.slack.dev/apis/socket-mode/ | duplicated connections can lock a customer's app out, not merely waste one |
| A Slack Events API delivery must be answered in three seconds, and Graph's validation handshake in ten | https://docs.slack.dev/apis/events-api/, https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks | anything that shares the API's event loop with flow execution risks the ack deadline |
| Enterprise lifespan hooks are best-effort and in-process only | `main.py:87`, run at `:653` and `:697` | there is no supervision, restart, or health for a long-lived task today |
| `lfx run` and `lfx serve` host no background work | `src/lfx/src/lfx/cli/serve_app.py` and siblings | the headless contexts cannot host Track B at all |

## 3. The sidecar position (author's section)

> To be written by the platform owner. The position recorded from the 2026-09-02 planning conversation, for the
> author to confirm, expand, or replace: a listener needs a separate service or a subprocess supervisor, one instance
> per bot or connection, so that API replicas, restarts, and autoscaling neither duplicate nor drop connections.
>
> `decisions/process-model.md` is written against that position and is `Status: accepted` by the release owner. If
> this section lands differently, that record is amended in the same pull request rather than left to drift.

## 4. Recommendation and risks the author wants recorded (author's section)

> To be written by the platform owner. The gate needs, at minimum: whether Track A may ship before Track B; whether
> the subprocess mode is acceptable for single-container and Desktop deployments; and the operational cost the
> platform team is willing to carry for a second long-lived process per installation.

## 5. Open questions this document is expected to close

| # | Question | Where the answer lands |
|---|---|---|
| 1 | Slack on Desktop: Socket Mode with a customer-owned app, or nothing? | `matrices/slack-events.json` `slack.socket_mode` deployment contexts |
| 2 | Track A on `lfx serve`: supported or not? | `decisions/process-model.md` - currently "not" |
| 3 | Calendar and Drive without ingress | `decisions/self-managed-ingress.md` - currently "poll, no relay" |
| 4 | Teams messages as an event source | `matrices/microsoft-events.json` `microsoft.teams_message_notifications` - currently excluded |

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| platform owner | | | |
| release owner | Eric Hare | 2026-09-05 | #14911 |
