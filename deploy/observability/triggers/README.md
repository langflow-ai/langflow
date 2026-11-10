# Trigger delivery and renewal dashboard

Enable `LANGFLOW_PROMETHEUS_ENABLED=true` and scrape the existing application
metrics endpoint. Import `trigger-governance.json` into Grafana and choose the
Prometheus data source and a scrape job that represents **one Langflow database**.
Do not combine independent installations under that job. The queries use `max`
across replica scrapes because every collector reads the same shared database;
summing those scrapes would multiply the cohort by the replica count.

The collector uses the existing background-metrics interval and a five-minute
cohort window. These are windowed gauges, so use their values directly rather
than `rate()`. The dashboard includes source outcomes, completion fraction,
first-start latency, pending age, renewal results, and recovered coverage gaps.
Explicit replay and test rows have separate metric labels and are excluded from
the source panels. Internal provider reconciliation hints are excluded entirely.
The oldest-pending gauge includes source events older than the cohort window.

No events means no completion percentage. First-start latency excludes jobs
without a retained `run_started` observation and publishes the missing-evidence
count. A zero latency with zero samples is not a fast successful run. Subscription
observations preserve the old and new expiries in the renewal transaction;
expired subscriptions and renewals recovered after expiry remain visible.

This is an importable dashboard, not evidence that it was installed or that a
production objective was met. See the [governance guide](../../../docs/features/trigger-governance.md)
for metric scope, rollout requirements, and remaining live acceptance.
