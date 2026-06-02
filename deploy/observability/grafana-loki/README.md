# Langflow on Grafana + Loki

Reference stack that ingests Langflow's structured JSON logs into [Loki](https://grafana.com/oss/loki/) and visualizes them with a pre-provisioned Grafana dashboard.

Use this as a starting point. The compose file, Promtail config, and dashboard JSON are independent of the rest of `deploy/` and can be lifted into any environment.

## What you get

- **Loki 3.2** on `:3100`
- **Promtail 3.2** scraping a directory of Langflow log files
- **Grafana 11.3** on `:3000` with the Loki datasource and the `Langflow Logs` dashboard already provisioned

## Prerequisites on the Langflow side

The dashboard expects Langflow to be running in JSON mode with service metadata set. At minimum:

```bash
LANGFLOW_LOG_ENV=container
LANGFLOW_LOG_FILE=/var/log/langflow/langflow.log
LANGFLOW_SERVICE_NAME=langflow
LANGFLOW_VERSION=1.10.0
LANGFLOW_ENVIRONMENT=production
```

In JSON mode the file is a single JSON stream: application logs and third-party stdlib loggers
(`uvicorn`, `sqlalchemy`, `httpx`, `langchain`) are all rendered as JSON and run through PII
redaction, so the `json` parse stage and the **Stdlib intercept routing** panel work against it
directly. If you'd rather not write a file, drop `LANGFLOW_LOG_FILE` and scrape the container's
stdout instead (same JSON, same labels).

See [Logs and observability](../../../docs/docs/Develop/observability-grafana-loki.mdx) for the full list of environment variables (per-logger overrides, extra PII redaction keys, trace correlation, etc.).

## Run

From this directory:

```bash
# Point Promtail at the directory containing your langflow*.log file(s).
# Defaults to ./logs/ if unset (useful for a quick local smoke test).
export LANGFLOW_LOG_DIR=/path/to/langflow/logs

docker compose up -d
```

Then open [http://localhost:3000/d/langflow-prod-logs](http://localhost:3000/d/langflow-prod-logs). Default credentials are `admin` / `admin` (override with `GF_ADMIN_USER` and `GF_ADMIN_PASSWORD`).

To stop:

```bash
docker compose down -v
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
