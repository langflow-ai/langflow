# SQLite upgrade qualification evidence

This ledger records the local qualification of the 1.13.0 transition on
2026-10-01. It supports review of the implementation and does not assert that a
signed production helper, application release or security closure already exists.
See the [upgrade design](sqlite-kb-upgrade.md) and
[managed controller instructions](sqlite-kb-controller.md) for supported scope.

## Completed local checks

The final combined storage, controller, cleanup, helper and application suite
passed all 320 tests. The affected bundle/component retirement suite passed 16
tests, and bundle structural discovery passed for 72 providers in the local
test environment. The universal dependency export contains none of the three
retired SDKs.

| Area | Evidence | What it establishes |
|---|---|---|
| Managed controller | 19 passing cases in `test_upgrade_controller.py` | Real disposable supervisor and worker shutdown, metadata backup, receipt, foreground launch and readiness. Covers stale identities, staging/backup failures, cancellation, resumption, duplicate-launch prevention, surviving-child rejection and exact IPv4 listener ownership. |
| Pending cleanup | Passing API and service regressions in `test_pending_cleanup.py` | Superuser enforcement, original UUID and generation checks, concurrent/idempotent retry, failure retention, Memory linkage, source-backup retention and remote cancellation draining. |
| Native failure recovery | 3 real-failure cases, included in an 87-test SQLite backend/importer run | Process kill after a committed batch and inside an open transaction, followed by reopening, integrity checks and complete replay. Native `SQLITE_FULL` preserves the previous batch and incomplete manifest, then succeeds after capacity is restored. |
| Signed-kit contracts | 18 passing cases in `test_signed_helper_kit.py` | Both-platform evidence binding, immutable archive checksums, rejection of altered signatures/archives before Docker, namespace requirement and environment restoration. These unit tests do not replace a real signed-kit run. |
| Approval protection | 20 passing cases in `test_helper_release_environment.py` | A read-only API check rejects absent, inaccessible, malformed, empty and bot-only review protection before candidate publication and signing. |
| Native helper rehearsal | 717 records, three persisted HNSW indexes, Linux ARM64 container | Exact IDs, text, metadata and vectors survived L2, cosine and inner-product export/import, updates, deletions, pending records and a known-dimension empty store. A stored hostile embedding configuration was not instantiated. Source-write, network and credential isolation passed, and malformed native input was rejected. |
| Release evidence/inventory contracts | 19 passing tests and 11 subtests | Application release evidence requires authenticated manifest and qualification bindings, both platforms, compatible source/dependencies and absence of retired SDKs in the full installed inventory. |

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

## Isolated helper security disposition

The locally inspected and scanned Linux ARM64 helper has image content ID:

```text
sha256:f7bb77c29adce1895c53542962dd96aaf4c44540f58ae0ca09cd665817708e93
```

This is a Docker image content ID, not a published multi-platform registry
digest. Trivy 0.75.0's unfiltered 2026-10-01 report for this exact image contains
7 critical, 60 high, 115 medium, 91 low and 2 unknown **package findings**. These
counts are not unique CVE counts and are not a clean-image claim. The final local
image uses pinned Python 3.13.15 slim Bookworm and removes the unused pip installer.

Eric Hare accepted a temporary security disposition for the disclosed findings
in this isolated one-time helper profile. The fixed native-reader entrypoint
does not launch the Python Chroma server or instantiate stored embedding
functions. It uses a disposable copy, no networking or secrets, non-root execution,
read-only source and root filesystem, no capabilities, and bounded resources.
Native SQLite/HNSW/pickle metadata parsing still carries residual risk. Protocol
and record verification do not prove native parsing safe or eliminate container
runtime/kernel risk. The disposition applies to this restricted helper profile,
not the application runtime or arbitrary Chroma deployments.

Fresh findings for the exact signed amd64 and arm64 candidate must still be
reviewed. New or unreviewed findings require an updated disposition. The original
Mend advisory identities remain unreconciled, so this evidence does not close
that original security finding.

## Remaining release gates

| Gate | Required evidence before release |
|---|---|
| Protected release configuration | Configure approval protection for `chroma-migration-helper-release`. A read-only API preflight requires actual human reviewers before candidate publication, with repeated checks before signing and durable publication. Missing or inaccessible protection blocks the workflow. |
| Exact candidate reports | Native amd64 and arm64 runs, full vulnerability reports and SBOMs for the immutable candidate. Security approval must cover those exact reports. |
| Signed offline qualification | Run the unmodified production signature verifier, image loader and exporter inside a network-isolated qualification process on both architectures, with networking disabled in the helper containers. Authenticate the independently provisioned Sigstore trust root and both archive checksums. |
| Durable helper publication | Publish the signed manifest, signed two-platform qualification attestation, exact archives, reports and disposition reference through the protected workflow. Do not replace an existing kit release. |
| Application release gate | Verify both signatures and compatible helper/runtime source and dependencies, then complete the application artifact inventory and release scans. Reconcile the original Mend findings before security closure. |
| Deployment acceptance | Rehearse the actual supervisor, volumes, backup capacity, downtime and forward-repair procedure for each supported deployment topology. |

The release workflow enforces artifact and signature prerequisites. A successful
local unit suite, unsigned ARM64 fixture rehearsal or temporary disposition does
not substitute for the remaining signed, two-platform release evidence.
