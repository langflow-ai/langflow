# Process model for triggers

Status: accepted
Decision ID: process-model
Applies to: every Track B mechanism in `matrices/*-events.json`; the TRG-2 dispatcher; TRG-3 packaging
Owners (sign-off roles): platform owner, langflow-base owner, Enterprise owner, release owner
Last verified: 2026-09-05

## Context

TRG-1 exit criterion 3. Track B mechanisms (`slack.socket_mode`, `microsoft.graph_delta_poll`,
`google.calendar_sync_poll`, `google.drive_changes_poll`, `google.gmail_watch_pubsub_pull`) hold or repeatedly open an
outbound connection. Both prior attempts hosted that loop inside the API process, and the platform owner's position
recorded in the README is that a listener needs a separate service or a supervised subprocess, one instance per
connection, so API replicas, restarts, and autoscaling neither duplicate nor drop connections. This record decides
the shape, the lease, and the behaviour in each deployment context, because TRG-2 cannot start a dispatcher and TRG-3
cannot pick a packaging without it.

Two loops are in play and they are not the same thing. The **dispatcher** drains the `trigger_event` ledger and
submits runs; it is short-lived work that fits the API process. The **listeners** hold provider connections; they do
not.

## Facts (with citations)

| # | Fact | Source URL | Verified on | Confidence |
|---|------|------------|-------------|------------|
| 1 | The API process defaults to more than one uvicorn worker: `(cpu_count() * 2) + 1` | `src/backend/base/langflow/__main__.py` worker default | 2026-09-05 | high |
| 2 | Enterprise lifespan hooks exist and are the only in-process place to start and stop background work | `src/backend/base/langflow/main.py:87` `_enterprise_lifespan_hooks`, run at `:653` and `:697` | 2026-09-05 | high |
| 3 | Nothing in the repo supervises a long-lived process; Celery exists (`core/celery_app.py`) but is not wired to flow execution in OSS | README "Runtime seams" | 2026-09-02 | high |
| 4 | A guarded-`UPDATE` lease idiom already exists and is proven on SQLite and PostgreSQL | `src/backend/base/langflow/services/jobs/service.py` claim/renew helpers | 2026-09-05 | high |
| 5 | `lfx run` and `lfx serve` do not host listeners; the headless entry points build and serve a graph only | `src/lfx/src/lfx/cli/serve_app.py`, `serve_durable.py`, `serve_workflow.py` | 2026-09-02 | high |
| 6 | Slack counts a stale Socket Mode connection against the ten-per-app cap until it times out, so two replicas holding one app's connection can lock the app out | https://docs.slack.dev/apis/socket-mode/ | 2026-09-05 | high |
| 7 | `origin/mock-orchestra` ran one Discord gateway client per bot from the API lifespan; `origin/feat-native-triggers-v2` ran one asyncio worker per uvicorn worker from the API lifespan | README "Precedents" | 2026-09-02 | high |

## Options

### Option A: subprocess supervisor under the API lifespan only

Pros: one artifact to deploy; nothing new for the operator; Desktop works with no extra shape.
Cons: fact 1 means several API processes would each try to supervise; the supervisor dies with the API; scaling the
API scales the listeners; a listener leak takes the API with it. Repeats the precedent shape (fact 7).
Cost: low now, high later.

### Option B: separate service only

Pros: the clean shape - listeners scale, restart, and fail independently of the API; matches fact 6's requirement
that exactly one process holds each provider connection.
Cons: Desktop and single-container Docker have no second process to run, so those contexts lose Track B entirely,
and every developer running `langflow run` locally loses it too.
Cost: an operator Deployment, a Compose service, and docs.

### Option C: both, with one primary (selected)

The separate service is the supported shape; the lifespan subprocess is the single-replica convenience shape.
Cost: Option B's cost plus a subprocess supervisor and its single-worker guard.

## Decision

Option C. A `langflow listeners` process is the primary shape for Track B and is what the operator Deployment and the
Compose service run; `LANGFLOW_LISTENERS_MODE=subprocess` makes the API lifespan spawn exactly that process as a
child, and that mode is the Desktop and single-container shape. The boot path asserts that no FastAPI app is created
in the listener process, so the two never converge again by accident.

The dispatcher and the schedule tick are not listeners and stay in the API lifespan, gated on
`trigger_dispatcher_enabled` and held by a `trigger_lease` heartbeat singleton so that only one of the several API
workers runs them; the listener process may host the same loop when the API is not running it.

Lease semantics, one lease per provider connection in `trigger_listener_lease`: TTL 30 s, heartbeat 10 s, reconcile
poll 5 s, failover within two TTLs of an unclean death, claim and renew through the guarded-`UPDATE` idiom of fact 4
so SQLite and PostgreSQL behave the same. A replica that loses its lease cancels its adapter tasks before another
replica's claim can succeed in the common case, and fact 6 is the reason the TTL is short rather than generous.

Per context:

| Context | Dispatcher | Listeners | Shape |
|---|---|---|---|
| hosted / multi-replica Kubernetes | API lifespan, lease-elected | separate Deployment, `replicas: 1` per listener group | operator `spec.listeners` |
| self-managed Compose or single-container Docker | API lifespan, lease-elected | `LANGFLOW_LISTENERS_MODE=subprocess`, spawned from one worker | one container or a second service |
| Desktop | API lifespan | subprocess mode | no operator action |
| headless (`lfx serve`, `lfx run`) | none | none | triggers are not hosted here at all |

Health lives on `LANGFLOW_LISTENERS_HEALTH_PORT` (default 7861) with `/health` for liveness and `/healthz` for
readiness (database probe, leases held, no renew failure within the last TTL).

## Consequences

- TRG-3 owns `langflow listeners`, the lease table, the adapter protocol, the health endpoints, and four packaging
  shapes; its estimate carries the operator Deployment and the Compose service.
- TRG-2 owns the dispatcher inside the API lifespan and the `trigger_lease` singleton; it does not start listeners.
- `headless` is `unavailable` for public ingress in all three matrices and hosts no Track B mechanism, which is this
  gate's answer to the README's open question "Track A on `lfx serve`": no. `lfx serve` neither exposes a trigger
  ingress route nor holds a listener.
- Enterprise needs no registration of its own: the listener process runs the same `lfx.toml` service discovery as
  the API, so EE service overrides apply unchanged.
- Desktop Track B is real but single-user: the subprocess dies with the app, which is acceptable because Desktop
  triggers only fire while Langflow is open. The frontend says so.

## Re-open trigger

- A customer needs Track B on `lfx serve`, or
- the subprocess mode proves unsafe under the default multi-worker API (fact 1) and has to become lease-elected too,
  or
- Celery becomes a supported OSS execution backend, which would give listeners a supervisor that already exists.

Re-verify by: the 1.14 planning gate.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| platform owner | | | |
| langflow-base owner | | | |
| Enterprise owner | | | |
| release owner | Eric Hare | 2026-09-05 | #14911 |
