# SQLite Knowledge Base transition for 1.13.0

The local default is SQLite with sqlite-vec. Explicit pgVector configuration
continues to take precedence. Existing pgVector and OpenSearch stores retain
their routing. This change targets 1.13.0 only, with no 1.12.5 backport.

See the [qualification evidence](sqlite-kb-qualification.md) for measured tests,
workloads and remaining application release gates.

The application workspace, universal lock and all-packages/all-extras/all-groups
export no longer require `chromadb`, `langchain-chroma` or
`agent-lifecycle-toolkit`. `langflow-base` installs `lfx[sqlite]`, including APSW
3.53.4.0 and sqlite-vec 0.1.9. The default automatic reader is bundled, uses SQLite and bounded inert HNSW
data parsing, and imports no Chroma SDK or native HNSW library. The optional
managed controller uses this same bundled reader after stopping the old workers
and preserving a metadata backup. No separate migration helper is published.

## Runtime and storage

Each store is located at
`<knowledge_bases_root>/sqlite/<owner UUID>/<KB UUID>/<generation>/vectors.sqlite3`.
The factory obtains identities from the authoritative application record, not
request paths, display names or the accessing user's identity. Configuration
cannot override the database or extension path. Shared resources use the owner.
Normal reads open an existing generation and fail if its database is missing.
Only explicit new-store creation or unpublished migration creates files.

The backend uses a private APSW runtime, WAL, full synchronous durability,
foreign keys, bounded busy waits and short transactions. It loads only the
installed sqlite-vec extension and disables further extension loading. Connections
are scoped to bounded worker operations. Cancellation drains active workers
before releasing their lifecycle guard. Pools are recreated after fork.

Canonical tables retain native IDs, original JSON metadata, text and float32
vectors. Native IDs are distinct from user metadata `_id`. Exact filtered search
supports squared L2, cosine and inner product. Extreme finite vectors use stable
double-precision distance calculation before ranking. Equal distances use native
ID ordering. Exact search can differ from Chroma's approximate search.

The public local score remains negative distance. User source filters are applied
before top-k selection, with AND across keys, OR across values and the historical
Python string-conversion behavior. Internal job/session equality filters remain
separate. Cosine zero vectors are rejected explicitly, including during migration,
rather than silently removed or assigned a different metric.

Application factories wrap complete backend methods and iterators in a
cross-process guard. A fresh routing/state check follows lock acquisition.
Generation and identity checks also occur inside SQLite transactions. Local
stores require one host and local disk. Remote stores use application-database
coordination without requiring a local vector directory. PostgreSQL advisory
locks use a separate configurable pool, avoiding exhaustion of the application pool.
`LANGFLOW_KNOWLEDGE_BASE_STORAGE_POOL_SIZE` defaults to 20 connections per process.
Nested operations spanning several remote KBs share one coordination transaction.
Memory capture revalidates routing, message contents, session identity and cursor
under its write lease after provider calls. Embedding calls and retry back-off do
not hold that lease. Tracking commits revalidate the same snapshot. Session purges and regeneration acquire the
same guards before changing messages, cursors or history.

Deletion persists a fence, drains active operations and tombstones the generation
before removing application records. Failures retain the identity needed for a
retry. A new KB with the same display name receives a new UUID and cannot reuse
a tombstoned generation. Storage and metadata cleanup retain the original UUID,
so a delayed request cannot delete its replacement. Remote destructive requests
propagate transport and partial-completion errors. OpenSearch worker requests
drain before cancellation releases their guard.
Cleanup never manually unlinks active WAL/SHM files or
truncates live databases.

## Automatic upgrade

A plain package or image upgrade now copies supported local Chroma stores on
first startup, without a controller receipt, Docker, cosign, helper publication
or embedding calls. The built-in reader replays vector and metadata checkpoints
independently and reconciles pending log operations. Index metadata is decoded
as inert data, never through `pickle.load` or a native HNSW loader. Real fixtures
cover Python Chroma 0.5.23 and Rust Chroma 1.5.9.

The single-worker preflight checks for other Langflow entry points, orchestrator
configuration and the storage filesystem. It preserves routing metadata and a
SQLite application backup when applicable. PostgreSQL app databases need their
usual deployment backup, and the base's routing metadata is retained locally.
The coordinator checks the source fingerprint again before publishing routing.
Unsupported topologies and formats stay fenced with explicit UI guidance.
See the [published upgrade guide](../docs/Develop/knowledge-storage-upgrade.mdx).

Discovery, export and copying run in the background. Ordinary service health
stays available while the individual base remains fenced. Migration identity,
source fingerprint, phase and destination generation survive restart. The next
startup retries the same migration, preserving source files and validating the
unpublished target before it becomes ready. The UI shows progress, availability
and administrator retry controls, including Memory bases. Status revisions
refresh cached resource lists even when a migration finishes between polls.

Alembic adds storage state, generation and active migration identity, plus a
durable migration ledger. It fences existing Chroma rows without reading vector
data. Ingestion status is independent and cannot clear this fence.

Startup inventories legacy sources and schedules migration automatically.

### Optional managed controller

The
managed controller accepts a **non-root POSIX single-host installation with a
SQLite application metadata database**, local disk and a dedicated foreground
supervisor session. See [the controller guide](sqlite-kb-controller.md) for its
command, prerequisites and resumable states. It records and stops the exact
API/background/Memory process family,
creates the backup and receipt, launches the new version, and verifies readiness
on a listener owned by that new process family. External automatic restarters
must be disabled before invoking it. This is a maintenance upgrade. An old worker cannot honor the new fence,
and neither a lease expiry nor an ingestion cancellation request proves it stopped.

The controller records each previous worker's PID and creation time before
shutdown. It invokes the verifier automatically. Other qualified deployment
managers can invoke the same verifier after stopping their recorded workers:

```sh
python -m langflow.services.knowledge_base_storage.maintenance \
  --root /absolute/knowledge-bases \
  --database /absolute/langflow.db \
  --receipt /private/upgrade-1.13/receipt.json \
  --previous-workers /private/upgrade-1.13/previous-workers.json
```

`previous-workers.json` is the controller's JSON array of
`{"pid": 123, "created": 1234567890.0}` identities. The verifier does not terminate
processes. It rejects still-running registered workers and other matching
Langflow workers, creates and verifies a consistent application-database backup,
and fingerprints the complete legacy source trees. The receipt is private to
the application account and bound to the host, database and storage root.
The service manager must keep the old supervisor stopped throughout upgrade.
Do not manufacture a receipt or substitute an empty process list.

The new process receives:

```text
LANGFLOW_KB_UPGRADE_RECEIPT=/private/upgrade-1.13/receipt.json
```

Migration then requires no per-KB command or confirmation. For each eligible KB,
including Memory backing stores, the coordinator:

1. Acquires the whole-KB guard and persists its migration identity.
2. Validates the stopped-worker receipt, metadata backup and source fingerprint.
3. Preserves a full pristine source snapshot, including native indexes and logs.
4. Exports from the snapshot with the bundled legacy reader.
5. Qualifies the complete inert JSONL stream and terminal count/checksums.
6. Imports existing vectors into an unpublished generation, preserving IDs,
   metadata, dimensions and model identity without embedding calls.
7. Compares every imported record and checks integrity before finalizing the
   durable destination manifest.
8. Changes routing with an application-DB compare-and-swap transaction, health
   checks the target and opens writes only after successful completion.
9. Retains source and metadata backups for recovery.

Source bindings prevent retained originals from being adopted again after a
normal restart, explicit disk reconciliation or deletion of their migrated KB.
A failed copy remains
fenced and unpublished. Retry uses the same migration identity and source
fingerprint. A crash after routing changes resumes target health checks, never
falls back to an old source. Storage files and the application database do not
share a transaction, so the completed generation and routing pointer are explicit
recovery boundaries.

Unregistered legacy directories are adopted only when ownership and stored model
metadata are unambiguous and their receipt inventory is valid. Unknown ownership,
corrupt data or a deletion marker cannot become a new empty KB.

Authenticated superuser endpoints expose status and exceptional recovery:

- `GET /api/v1/knowledge-base-storage/inventory`
- `GET /api/v1/knowledge-base-storage/migrations`
- `POST /api/v1/knowledge-base-storage/migrations/{id}/retry`
- `GET /api/v1/knowledge-base-storage/pending-cleanup`
- `POST /api/v1/knowledge-base-storage/pending-cleanup/{kb_id}/retry` with
  `{"expected_generation": <storage_generation from the inventory>}`
- `POST /api/v1/knowledge-base-storage/attention/{kb_id}/detach` with
  `{"expected_generation": <storage_generation from the inventory>}`

Cleanup retry holds the immutable KB identity and generation guard until its
storage and exact metadata row are removed. Repeated requests are idempotent.
An active Memory reference returns 409 and its UUID in the admin inventory
directs the operator to the normal Memory deletion endpoint. This prevents KB
recovery from silently removing Memory history. Source backups remain retained.

Detaching a `needs_attention` store disables its routing while preserving the
original data, migration ledger and Memory history for recovery. Its owning flow
can then be deleted without removing those retained storage artifacts. Retry
migration before detaching if the store should remain available.

Liveness and ordinary `/healthz` readiness stay available during the initial
inventory scan, background migration and administrator retries. Individual
fenced stores are reported by the status endpoints without making unrelated
flows or ready stores unavailable.
The upgrade controller uses `/healthz?require_storage_ready=true`, which remains
false until required migrations finish or an operator detaches a failed store.
Errors are safe
codes with guidance and do not expose document contents, credentials or native
parser tracebacks.

## Bundled reader and release prerequisites

Both automatic and managed upgrades use the bundled SQLite and inert HNSW reader.
Index metadata is decoded as bounded data without Python pickle execution or a
native Chroma library. Stored embedding-function configuration is never
instantiated. Migration reads a preserved source snapshot and independently
validates the complete interchange stream before activating the SQLite generation.
See [the interchange protocol](../../src/lfx/src/lfx/base/knowledge_bases/migration/README.md).

The reader is qualified against local persistent HNSW stores produced by Chroma
0.5.23 and 1.5.9, including pending operations, purged logs, updated/deleted IDs
and empty stores with known dimensions. Unknown historical formats, SPANN and
stores exceeding the reader's resource limits remain fenced for administrator
recovery. Export those sources from an isolated compatible old-release
environment to a supported destination. The managed controller does not bypass
the bundled reader's format or resource limits.

Migration needs no model calls or network access. Air-gapped deployments need
only the normal Langflow packages or image and their application dependencies.
There is no Docker/cosign helper, offline helper kit or helper release tag gate.
Application release inventories, cross-platform native-runtime checks and final
artifact security scans remain required. The original scanner findings must
still be reconciled against those final artifacts before security closure.

## Compatibility and retired providers

Chroma and Chroma Cloud are removed from new provider choices. Their backend
identity remains recognizable for inventory and migration errors. Local KB and
Memory routing changes automatically only after validation. Remote Chroma stores
require an operator-coordinated export and a configured target such as pgVector
or OpenSearch. They are never silently converted to machine-local data.

Saved standalone Chroma/LocalDB nodes retain their class identities, fields,
outputs and legacy imports. They raise a migration-required error before any
provider call. Arbitrary paths, external endpoints, MMR/image configurations and
unregistered standalone stores are not silently reinterpreted as SQLite. Replace
those nodes with a validated Knowledge binding after migrating their data.
Core Knowledge starter flows use the updated component. An optional starter
that required standalone Chroma was retired.

Saved flows also retain component Python source. Before evaluating it, Langflow
recognizes an inventory of shipped Knowledge, Memory, Chroma, LocalDB and ALTK
sources by their complete semantic AST fingerprint and resolves those to the
current component classes. Matching preserves literal values and extra
statements, so a class name alone cannot authorize replacement. Custom edits
remain on the normal evaluation path. The persisted source stays unchanged for
recovery. Dependency extraction uses the same recognized replacement, preventing
old shipped imports from reinstalling retired SDKs in deployment exports.

ALTK is retired because its SDK requires langchain-chroma. Existing ALTK nodes
remain loadable and fail before model/tool execution with guidance to replace
them with Agent. The replacement does not reproduce ALTK validation/reflection.
Compatibility classes live in LFX and do not require optional provider bundles.
The legacy `chroma` and `altk` extras remain empty for installation compatibility.

## Verification and rollback

`scripts/ci/check_chroma_removal.py` checks the complete universal application
export without reducing the security scanner's scope. Clean-environment tests
exercise application construction and actual SQLite KB/Memory operations with
both Chroma packages absent. Bundled-reader tests use real source fixtures and
compare records after import, including negative tests for malformed index data
and stored executable metadata.
The existing release-tier inventory gate also checks every installed distribution
for the retired SDKs, including transitive packages outside Langflow's own tiers.

The native runtime workflow covers Python 3.10–3.14 on Linux x64/ARM64, macOS
Intel/ARM64 and Windows x64. This wheel matrix does not qualify the separate
POSIX upgrade controller on every platform. musl Linux and Windows ARM64 require a
qualified native runtime build before support can be claimed.

`scripts/benchmark/sqlite_kb.py` measures deterministic exact search at declared
corpus sizes. Its first-query timing is not a cold OS-cache result or an SLO.
Large-store, disk-full/crash and deployment-specific upgrade rehearsals remain
release qualifications, separate from unit-test success.

Before new writes, rollback requires the pristine source, consistent pre-upgrade
application DB backup and a compatible old application environment. After new
writes, use forward repair. Never automatically switch to a stale Chroma backup.
Managed upgrades should recreate their private application environment. For
user-managed shared Python environments, install 1.13 into a clean environment
and point it at the existing data paths. Removing a requirement does not uninstall
unrelated orphan packages from a shared environment.

The published [upgrade page](../docs/Develop/knowledge-storage-upgrade.mdx) explains ordinary package and image upgrades, retirement, and pending chat-history purges.

Nested PostgreSQL storage operations share their coordination transaction.
Their advisory locks remain held until the outermost operation finishes, so a
multi-store operation keeps its complete fence through rollback and cleanup.
