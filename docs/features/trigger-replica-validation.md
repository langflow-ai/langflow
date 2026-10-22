# Trigger replica validation

This record covers the replica investigation for LE-3191 and the resulting listener delivery fix on release-1.14.0. It provides repeatable checks, not a supported trigger count or event rate.

## Ownership map

| Work | Database ownership | Scaling and takeover |
|---|---|---|
| Schedule production | Named scheduler lease in `trigger_lease` | One producer normally runs. A successor waits for expiry. The ledger deduplicates the scheduled instant. |
| Ordinary dispatch | Named dispatcher lease, event claims, and trigger row locks | One dispatcher normally runs. API replicas provide takeover. A trigger's concurrency cap is shared across claimers. |
| Source maintenance | Separate named maintenance lease and per-source lease | Dispatch can continue during slow source I/O. Source scans remain serial within the maintenance task. |
| Subscription renewal | Named renewal lease and individual subscription claims | One renewal pass normally runs. A returned provider response cannot commit after losing its live claim. |
| Listener connections | Per-connection lease and replica presence rows | New replicas cause excess connections to be released. One connection and all its triggers stay on one replica. |
| Listener child hosting | Named host lease | Subprocess mode elects one child for the shared database. Separate listener processes provide independent scaling. |

The named leases can have different owners. Adding an API replica does not create another normal dispatch lane. Adding a listener distributes connections without splitting a busy connection or providing event-volume balancing.

Dispatch and source maintenance renew their leases during long work. Subscription renewal also extends its individual claims. Scheduler passes take their lease once and rely on the scheduled identity for duplicate suppression. A clean dispatcher stop does not release scheduler ownership.

## Reproduce the PostgreSQL checks

Use an administrative PostgreSQL test database. The suite creates a uniquely named database for each case and removes that database afterward. The outage case rejects connections only to its own temporary database. Never point the suite at a database account that lacks permission to create test databases.

```bash
uv sync --group dev --package langflow-base --package lfx
uv run --with 'psycopg[binary]' pytest src/backend/tests/integration/triggers/test_replica_coordination.py -q --tb=short
```

Set `LANGFLOW_TEST_DATABASE_URI` before running the command. No configured database means these tests skip. The service-level suites remain separate from these process tests.

The local validation uses PostgreSQL 18.6, Python 3.14.3, and two independent spawned processes per case on macOS. Listener and trigger worker TTLs are 1.5 seconds. The listener heartbeat interval is 0.1 seconds and reconciliation interval is 0.05 seconds. These shortened intervals exercise transitions without suggesting production timing guarantees.

On October 22, 2026, the strengthened process tests reproduced a stale listener appending a unique event after takeover. The listener now locks its captured connection lease generation through event persistence and verifies current trigger ownership, consent, state, kind, and optional captured configuration. Stale emission raises a typed rejection; an ordinary duplicate still returns false. Stale cursor writes remain ignored. The seven process tests passed in 172.85 seconds with this fix. The focused dispatcher, listener, scheduler, subscription, source runtime, and source delivery suites passed all 205 tests in 170.74 seconds, including the PostgreSQL capacity case and 1,000-event two-dispatcher soak. Both runs reported the existing Starlette test-client deprecation warning. The starting release commit was `5af9a26d1d3a742bc36731f9239e9fff688f7a06`.

The dispatcher processes call the production dispatcher directly. They do not boot HTTP servers. Listener processes use the production supervisor with an idle adapter. The background sink persists real Job rows with the submitted identity without executing a flow. Lease election, row locking, event claims, ledger uniqueness, cursor fencing, process kills, process stalls, and database connection failures use the real database.

The final listener follow-up also reproduced a PostgreSQL deadlock between delivery and connection deletion. Delivery now locks connection parents in deterministic order before its lease and trigger, then rechecks the target binding. The seven process checks plus three concurrent deletion cases passed all 10 tests in 137.02 seconds. The deletion cases exercise event emission, cursor writes, and cross-connection Slack fanout through actual listener contexts.

## What the checks establish

| Case | Assertions |
|---|---|
| Competing dispatcher processes | Two processes claim one shared concurrency slot across twelve waiting events. A job committed before event accounting is recovered with its original stable identity. After the elected dispatcher dies, its successor drains fifty additional events in two batches of twenty-five. |
| Listener scale-up and scale-down | One listener owns four connections. A second listener receives two. Killing the first permits the survivor to own all four after expiry. Starting a replacement restores disjoint ownership. Cleanly stopping a peer releases its share. |
| Late listener writes | The old listener's captured context cannot append a unique event or replace its successor's cursor. The current owner can append once and suppress a duplicate. A released and reclaimed lease also rejects the old generation when both processes use the same holder identity. |
| Concurrent connection deletion | Event and cursor writes finish or reject a removed target while connection deletion completes without a deadlock. Slack fanout also locks both connection parents in the same order. |
| Subscription ownership | Concurrent processes claim one due subscription only once. The surviving process can claim it after the winner is killed and its claim expires. |
| Slow work and database outage | Heartbeats prevent a second process taking ownership after the original TTL. Rejecting database connections cancels guarded work. Ownership can be acquired after connectivity returns and the lease expires. |
| Stalled process | SIGSTOP suspends an owner beyond its TTL. Its peer takes ownership. After SIGCONT, the old process cancels its guarded work rather than renewing the replacement owner's lease. |

The sleeps advance expiry and are not measured recovery latency. The assertions check eventual ownership after that wait. The suite does not measure a maximum failover time, throughput, delivery lag, or a latency percentile.

## Remaining deployment validation

Full API startup and HTTP ingress during rolling upgrades still need deployment-level validation. These tests do not validate actual provider sockets, OAuth refresh, subscription creation or renewal calls, provider throttling, real flow execution, or background worker recovery. The subscription process test covers database claims rather than remote renewal effects.

An external listener retries failed reconciliation while adapters can stay alive. A database outage can therefore outlast its lease while the old provider connection remains open. Provider reconnection and overlap need validation with the actual adapter. Ledger persistence must succeed before acknowledgment. The generation fence rejects stale event and cursor writes after takeover but does not close the old remote connection.

Scheduler work exceeding its TTL, network partitions, clock skew, production database contention, source pagination, and retained-ledger growth remain separate checks. A long soak must include renewal and cleanup before describing a deployment's supported workload.
