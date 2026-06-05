# Langflow on Grafana + Loki

Reference stack that ingests Langflow's structured JSON logs into [Loki](https://grafana.com/oss/loki/) and its Prometheus metrics into [Prometheus](https://prometheus.io/), and visualizes both with pre-provisioned Grafana dashboards.

Use this as a starting point. The compose file, Promtail config, Prometheus config, and dashboard JSON are independent of the rest of `deploy/` and can be lifted into any environment.

## What you get

- **Loki 3.2** on `:3100`
- **Promtail 3.2** scraping a directory of Langflow log files
- **Prometheus 2.55** on `:9091`, scraping Langflow's metrics endpoint (`:9090`)
- **Grafana 11.3** on `:3000` with the Loki, Prometheus, and Postgres datasources and three dashboards already provisioned: `Langflow Logs`, `Langflow Background Execution`, and `Langflow Background Workers`

## Prerequisites on the Langflow side

The dashboard expects Langflow to be running in JSON mode with service metadata set. At minimum:

```bash
LANGFLOW_LOG_ENV=container
LANGFLOW_LOG_FILE=/absolute/path/to/langflow/logs/langflow.log
LANGFLOW_SERVICE_NAME=langflow
LANGFLOW_VERSION=1.10.0
LANGFLOW_ENVIRONMENT=production
```

Promtail scrapes a directory of `*.log` files, so `LANGFLOW_LOG_FILE` must point at a file inside
the directory you expose to Promtail as `LANGFLOW_LOG_DIR` (see [Run](#run)). Set both to the same
directory, otherwise Promtail watches an empty folder and the dashboard stays blank. Use an
absolute path: `LANGFLOW_LOG_FILE` is resolved against Langflow's working directory, not this one.

In JSON mode the file is a single JSON stream: application logs and third-party stdlib loggers
(`uvicorn`, `sqlalchemy`, `httpx`, `langchain`) are all rendered as JSON and run through PII
redaction, so the `json` parse stage and the **Stdlib intercept routing** panel work against it
directly. This stack scrapes a file, so `LANGFLOW_LOG_FILE` is required. If you instead run
Langflow as a container, you can drop the file and scrape its stdout by swapping Promtail's
`static_configs` file target for `docker_sd_configs` (same JSON, same labels).

See [Logs and observability](../../../docs/docs/Develop/observability-grafana-loki.mdx) for the full list of environment variables (per-logger overrides, extra PII redaction keys, trace correlation, etc.).

## Background execution metrics (Prometheus)

The `Langflow Background Execution` dashboard visualizes the durable background execution service: queue depth, job states, run durations, worker liveness, and failure rates. It reads from Prometheus, so Langflow must expose its metrics endpoint:

```bash
LANGFLOW_PROMETHEUS_ENABLED=true
# Optional, defaults shown:
LANGFLOW_PROMETHEUS_PORT=9090
```

Langflow then serves metrics on `:9090`. Prometheus in this stack scrapes `host.docker.internal:9090`, which reaches a Langflow running on the host from inside the container. If you run Langflow itself as a container on the same compose network, change the target in `prometheus/config.yml` to that service name instead.

Ports: Grafana `:3000`, Prometheus `:9091` (its UI/targets at `http://localhost:9091/targets`), Langflow metrics `:9090`.

Open [http://localhost:3000/d/langflow-bg-execution](http://localhost:3000/d/langflow-bg-execution) once jobs start flowing.

### Metric catalog

All of these are derived from the durable job tables by a single collector in the Langflow process that owns the metrics port, so they work identically on the in-process default backend and a distributed `langflow worker` fleet (the workers never need their own scrape target). All metrics carry a `backend` label (`default` or `scaled`).

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `langflow_bg_jobs` | gauge | `status`, `backend` | Current count of non-terminal jobs (`queued`, `in_progress`) |
| `langflow_bg_oldest_queued_seconds` | gauge | `backend` | Age of the oldest queued job (queue-backlog signal) |
| `langflow_bg_workers_online` | gauge | `backend` | Workers heartbeating within the online window (= `busy` + `idle`) |
| `langflow_bg_workers_busy` | gauge | `backend` | Online workers currently running a job |
| `langflow_bg_workers_idle` | gauge | `backend` | Online workers currently idle |
| `langflow_bg_jobs_started_total` | counter | `backend` | Jobs started |
| `langflow_bg_jobs_completed_total` | counter | `backend` | Jobs completed |
| `langflow_bg_jobs_failed_total` | counter | `reason`, `backend` | Jobs failed (`reason` in `error`/`timeout`/`worker_lost`/`cancelled`) |
| `langflow_bg_orphans_reconciled_total` | counter | `backend` | Orphaned jobs reconciled by the watchdog |
| `langflow_bg_job_duration_p50_seconds` | gauge | `backend` | Median run duration over a recent window |
| `langflow_bg_job_duration_p95_seconds` | gauge | `backend` | p95 run duration over a recent window |

The three worker gauges come from the `worker_registry` table (see [Worker fleet](#worker-fleet-langflow-background-workers)). A worker is `online` while its `last_heartbeat` is within the online window (3x the heartbeat interval, 30s at the default 10s cadence); `online` always equals `busy` + `idle`. The counts are aggregate only: per-worker detail (owner, pid, host, uptime) stays in the roster table and the logs, never in a Prometheus label.

Metrics stay aggregate: labels are small enums only. Per-job detail (`job_id`, `flow_id`, `user_id`) lives in the logs, not the metrics. The bg-execution dashboard's logs panel filters those with `{job="langflow"} | json | event_type="bg_job"`, so you can pivot from an aggregate spike to the individual jobs behind it.

## Worker fleet (`Langflow Background Workers`)

The `Langflow Background Workers` dashboard (uid `langflow-bg-workers`) is the per-worker view of a scaled `langflow worker` fleet. Open [http://localhost:3000/d/langflow-bg-workers](http://localhost:3000/d/langflow-bg-workers).

Each `langflow worker` registers a row in the durable `worker_registry` table on startup, heartbeats every `background_worker_registry_interval_s` (idle or busy), records its current job, and deregisters on graceful stop. A crashed worker stops beating, so its row goes stale and the API-side collector prunes it after `background_worker_registry_retention_s`.

The dashboard reads `worker_registry` directly from Postgres (joined with per-owner aggregates from the `job` table). Per-worker detail stays out of Prometheus, so this needs a Postgres datasource rather than a scrape target. It has:

- **Header stats**: online / busy / idle / total registered.
- **Worker roster table**: every registered worker, online vs offline, uptime, current job, and per-worker processed / succeeded / failed counts. The roster's online/offline flag uses a fixed 30s window (the default 3x `background_worker_registry_interval_s`); the Prometheus gauges adapt automatically, so if you raise the interval, edit the `30 seconds` literal in the roster SQL to match.
- **`$worker` drill-down**: a dashboard variable that filters a per-worker table plus the Loki `bg_job` logs for the selected worker (`{job="langflow"} | json | event_type="bg_job" | worker=~"$worker"`). The `bg_job` logs carry a `worker` field on the scaled backend.

Two settings control the registry, both in lfx settings:

| Setting | Default | What it controls |
|---|---|---|
| `background_worker_registry_interval_s` | `10.0` | Heartbeat cadence. A worker refreshes its `worker_registry` row this often, idle or busy. The online window is 3x this (30s at the default), so a worker counts as online while it has beaten within three of its own intervals. |
| `background_worker_registry_retention_s` | `3600.0` | Stale-row prune retention. A crashed worker's row shows offline for this window, then the collector removes it so the roster does not accumulate dead owners across restarts. |

The stack provisions a `Postgres` datasource (uid `langflow-postgres`) pointed at your Langflow database. Set these to point it at your DB. The defaults match the reference dev DB published on `host.docker.internal:5432`:

```bash
LANGFLOW_DB_HOST=host.docker.internal   # reaches a Postgres published on the host
LANGFLOW_DB_PORT=5432
LANGFLOW_DB_NAME=langflow
LANGFLOW_DB_USER=langflow
LANGFLOW_DB_PASSWORD=langflow
LANGFLOW_DB_SSLMODE=disable
```

In PRODUCTION this must be a READ-ONLY database role, never the app's read-write credentials. Grafana only runs SELECTs against `worker_registry` and `job`, so a role with read access to those tables is enough. Pointing it at a privileged role gives every dashboard viewer a SQL surface into your write path.

## Run

From this directory:

```bash
# Point Promtail at the directory that holds the file you set in
# LANGFLOW_LOG_FILE above. Must be the same directory. Defaults to the
# bundled ./logs (used by the quick smoke test below).
export LANGFLOW_LOG_DIR=/absolute/path/to/langflow/logs

docker compose up -d
```

Then open [http://localhost:3000/d/langflow-prod-logs](http://localhost:3000/d/langflow-prod-logs). Default credentials are `admin` / `admin` (override with `GF_ADMIN_USER` and `GF_ADMIN_PASSWORD`).

To stop:

```bash
docker compose down -v
```

### Quick smoke test (no Langflow required)

To verify the stack end to end without running Langflow, write a sample record into the bundled
`./logs` directory and query Loki directly:

```bash
mkdir -p logs
echo '{"event":"smoke test","level":"info","logger":"langflow.api.run","timestamp":"2026-06-01T00:00:00Z","service":"langflow","environment":"production","version":"1.10.0"}' >> logs/langflow.log

docker compose up -d

# Give Promtail a few seconds to tail the file, then confirm the line reached Loki:
sleep 5
curl -sG 'http://localhost:3100/loki/api/v1/query_range' --data-urlencode 'query={job="langflow"}' | grep -q "smoke test" && echo "OK: log reached Loki"
```

## What each dashboard panel proves

| Panel | LogQL it runs |
|---|---|
| **PII leak count (must be 0)** | `sum(count_over_time({job="langflow"} \|~ "sk-do-not-leak\|hunter2\|Bearer xyz" [$__range]))` |
| **Errors with structured tracebacks** | `{job="langflow", level=~"error\|critical"} \|= "exception" \| json` |
| **Redaction proof** | `{job="langflow"} \|~ "\\*\\*\\*"` |
| **Stdlib intercept routing** | `{job="langflow", logger=~"uvicorn.*\|sqlalchemy.*\|httpx.*\|langchain.*"}` |
| **Service / environment / version coverage** | `sum by (service, environment, version) (count_over_time({job="langflow"}[$__range]))` |
| **Log rate by level** | `sum by (level) (rate({job="langflow"}[1m]))` |
| **Log rate by logger** | `topk(10, sum by (logger) (rate({job="langflow"}[1m])))` |

## Notes

- Promtail only promotes `level`, `service`, `environment`, `version`, `logger` to labels. High-cardinality fields (`user_id`, `flow_id`, `trace_id`) stay in the log body — query them with `| json` in LogQL.
- Replace Promtail with [Grafana Alloy](https://grafana.com/oss/alloy/) if you already standardize on it; the JSON parse stage maps 1:1.
- If your runtime ships logs through a different transport (Fluent Bit, Vector, OTLP), only the scrape side changes — the dashboard and label schema stay the same.
