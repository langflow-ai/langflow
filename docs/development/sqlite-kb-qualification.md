# SQLite upgrade qualification evidence

This ledger records the local qualification of the 1.13.0 transition on
2026-10-01. It supports review of the implementation and does not assert that a
application release or security closure already exists. The separate container
helper described in the original qualification has since been retired. Both
automatic and managed upgrades now use the bundled reader.
See the [upgrade design](sqlite-kb-upgrade.md) and
[managed controller instructions](sqlite-kb-controller.md) for supported scope.

## Completed local checks

The original combined storage, controller, cleanup, helper and application suite
passed all 320 tests before helper retirement. Those counts are historical.
The affected bundle/component retirement suite passed 16 tests, and bundle structural discovery passed for 72 providers in the local
test environment. The universal dependency export contains none of the three
retired SDKs.

| Area | Evidence | What it establishes |
|---|---|---|
| Managed controller | 19 passing cases in `test_upgrade_controller.py` | Real disposable supervisor and worker shutdown, metadata backup, receipt, foreground launch and readiness. Covers stale identities, backup failures, cancellation, resumption, duplicate-launch prevention, surviving-child rejection and exact IPv4 listener ownership. |
| Pending cleanup | Passing API and service regressions in `test_pending_cleanup.py` | Superuser enforcement, original UUID and generation checks, concurrent/idempotent retry, failure retention, Memory linkage, source-backup retention and remote cancellation draining. |
| Native failure recovery | 3 real-failure cases, included in an 87-test SQLite backend/importer run | Process kill after a committed batch and inside an open transaction, followed by reopening, integrity checks and complete replay. Native `SQLITE_FULL` preserves the previous batch and incomplete manifest, then succeeds after capacity is restored. |

The process-death and capacity tests use disposable databases and exact child
processes. `SQLITE_FULL` is induced with SQLite's `max_page_count`, not by filling
the host disk. It exposed and verified a fix for an error-handling bug: an
implicit SQLite rollback must not be followed by a second rollback that masks
the original error. These checks establish transaction/replay behavior, not
power-loss durability of every supported filesystem or storage device.

Controller and native failure checks ran on macOS ARM64, Python 3.14.3. The
controller requires a non-root POSIX application account, a dedicated foreground
supervisor session, disabled external restarters, local storage and SQLite
application metadata. A native wheel matrix does not extend controller support
to Windows services, distributed deployments or PostgreSQL metadata.

## Measured local search workloads

Measurements use `scripts/benchmark/sqlite_kb.py`, deterministic precomputed
float32 vectors and five searches per filter. The exact self-match was checked
on every query. Document embedding and network time are excluded.

Host: macOS 27.0.1 ARM64, Python 3.14.3. Other qualification work ran concurrently
on this host. These are observed measurements, not an SLO, capacity limit or
isolated performance comparison. The first query is not a cold OS-cache probe.
Storage sizes below use decimal MB.

| Rows | Dimensions | Ingest (s) | All records, median / max (ms) | 1% filter, median / max (ms) | Storage (MB) |
|---|---:|---:|---:|---:|---:|
| 100,000 | 384 | 30.89 | 125.46 / 197.83 | 76.70 / 142.43 | 219.37 |
| 10,000 | 1,536 | 8.02 | 66.71 / 146.62 | 13.46 / 23.76 | 83.39 |
| 10,000 | 3,072 | 14.22 | 105.77 / 146.98 | 14.84 / 20.38 | 129.39 |

Reproduce in the Chroma-free application environment:

```sh
uv run --no-sync python scripts/benchmark/sqlite_kb.py --rows 100000 --dimensions 384 --runs 5
uv run --no-sync python scripts/benchmark/sqlite_kb.py --rows 10000 --dimensions 1536 3072 --runs 5
```

These workloads do not qualify near-limit 8 GiB source migrations, sustained
multi-user load, every metadata-filter distribution or network filesystems.

## Remaining release gates

| Gate | Required evidence before release |
|---|---|
| Application artifacts | Complete the installed application dependency inventory, cross-platform native-runtime checks and final artifact security scans. Reconcile the original scanner findings before security closure. |
| Deployment acceptance | Rehearse the actual supervisor, volumes, backup capacity, downtime and forward-repair procedure for each supported deployment topology. |

The release workflow enforces application artifact and inventory prerequisites.
A separate helper build, signing approval and publication are no longer required.
Local unit-test success does not substitute for final artifact scans or
deployment-specific acceptance.
