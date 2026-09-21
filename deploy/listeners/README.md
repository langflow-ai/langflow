# Langflow trigger listeners

`langflow listeners` is the process that holds outbound provider connections for
Track B triggers: Slack Socket Mode, Microsoft Graph delta polling, Gmail
Pub/Sub pull. It exists so an instance behind a firewall - with no public URL a
provider could post to - can still fire flows when something happens elsewhere.

It is a separate process by decision, not by accident. The API runs several
uvicorn workers and is restarted and autoscaled on its own schedule; a
connection held inside it is either duplicated across workers or dropped on the
next rollout. The record is
[`design/dedicated-integrations-triggers/decisions/process-model.md`](../../design/dedicated-integrations-triggers/decisions/process-model.md).

## The four shapes

| Deployment | Listeners | How |
|---|---|---|
| Kubernetes, multi-replica | separate Deployment | [`kubernetes-deployment.yaml`](kubernetes-deployment.yaml) |
| Compose | separate service | [`docker-compose.listeners.yml`](docker-compose.listeners.yml) |
| Single container | child of the API | `LANGFLOW_LISTENERS_MODE=subprocess` |
| Desktop | child of the API | `LANGFLOW_LISTENERS_MODE=subprocess` |

`lfx run` and `lfx serve` host no listeners at all. Headless keeps the existing
webhook.

## What it needs

- **The same database** as the API (`LANGFLOW_DATABASE_URL`). PostgreSQL for
  anything with more than one process; SQLite is single-process, so use
  subprocess mode there.
- **The same `LANGFLOW_SECRET_KEY`.** The listener resolves and refreshes the
  same connection rows the API does, and decrypts the same token material.
- **The API started first.** The listener never runs migrations. It checks for
  the trigger tables at boot and exits with an explicit message when they are
  missing, rather than racing Alembic during a rolling upgrade.

## What it serves

`/health` (liveness) and `/healthz` (readiness) on
`LANGFLOW_LISTENERS_HEALTH_PORT`, default 7861, bound to loopback unless
`LANGFLOW_LISTENERS_HEALTH_HOST` says otherwise. Nothing else: the process
refuses to build a FastAPI application.

Readiness is false when the database is unreachable, when the reconcile loop has
gone stale, or when a connection lease failed to renew inside the last TTL -
the three ways a listener can be running and useless at the same time.

## Scaling and failover

Each connection is held by exactly one replica, elected by a
`trigger_listener_lease` row with a 30-second TTL and a 10-second heartbeat.
A replica that dies has its connections taken over within two TTLs. Scale out
when one process cannot keep up with the number of armed connections; do not
scale out for redundancy, because failover does not require a warm standby.

Lease expiry is a Langflow recovery bound, not proof that a dead process closed
its socket. Adapters are written to tolerate bounded overlap during handover.

## Operator settings

| Variable | Default | What it does |
|---|---|---|
| `LANGFLOW_LISTENERS_MODE` | `off` | `subprocess` makes the API spawn the listener as a child |
| `LANGFLOW_LISTENERS_HEALTH_HOST` | `127.0.0.1` | Health bind interface; `0.0.0.0` for probes |
| `LANGFLOW_LISTENERS_HEALTH_PORT` | `7861` | Health port |
| `LANGFLOW_LISTENER_LEASE_TTL_S` | `30` | Connection lease lifetime; failover happens within two of these |
| `LANGFLOW_LISTENER_HEARTBEAT_INTERVAL_S` | `10` | Lease renewal cadence |
| `LANGFLOW_LISTENER_RECONCILE_INTERVAL_S` | `5` | How often the table is compared with the held set |
| `LANGFLOW_LISTENER_POLL_INTERVAL_S` | `30` | Default cadence for pull adapters |
| `LANGFLOW_LISTENER_BACKOFF_BASE_S` / `_CAP_S` | `2` / `300` | Reconnect backoff, with jitter |
| `LANGFLOW_LISTENER_FAILURE_THRESHOLD` | `5` | Consecutive failures before the error is shown on the trigger |

## Verifying an install before a provider is involved

Langflow ships one built-in adapter, `listener_selftest`, that emits a ledger
event on an interval without talking to any provider. It is there so an operator
can prove the shape - process boots, lease is taken, adapter runs, event lands,
SIGTERM stops it cleanly - before a single OAuth consent exists. Arm a trigger
of kind `listener_selftest` against any connection, start the listener, and
watch events appear on the trigger's event list.
