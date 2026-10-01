# SQLite Knowledge Base transition for 1.13.0

## Current implementation boundary

This change provides the SQLite storage adapter, strict migration interchange
and import verification, native-runtime qualification workflow, and ALTK
retirement. **It does not yet switch the application default or automatically
migrate an installation. Chroma remains in the application dependency graph.**

The transition targets 1.13.0 only. There is no 1.12.5 backport. Existing stores
must never be opened as empty SQLite stores merely because a legacy backend is
unavailable. Keep the default switch behind the remaining upgrade gates below.

## Storage contract

`SQLiteStorageContext` receives trusted application records: configured root,
owner UUID, KB UUID and positive storage generation. The backend derives
`sqlite/<owner>/<kb>/<generation>/vectors.sqlite3` beneath that root. Request
configuration cannot override paths or identities. Shared resources must use
the owner's context. Trusted OS ancestor aliases are canonicalized, while a
symlinked configured root or generated child is rejected.

`create_backend("sqlite", ..., storage_context=context)` opens an existing
generation. Creating a new KB or an unpublished migration destination requires
explicit `create=True`. Reads fail on missing or tombstoned storage. Deletion
tombstones the generation before removing records. Physical directory cleanup
belongs to the application's exclusive lifecycle guard.

The `lfx[sqlite]` extra pins APSW 3.53.4.0 and sqlite-vec 0.1.9. APSW supplies a
private SQLite 3.53.4 runtime without modifying the application SQL driver.
Connections load only the installed sqlite-vec extension, then disable loading.
Connections are scoped to worker operations. WAL, full synchronous durability,
foreign keys, transaction-time generation checks and a bounded busy timeout
apply. Cancellation waits for the active worker to finish before returning.
The worker pool is re-created after fork.

Canonical rows retain native IDs, text, original JSON metadata and float32
vectors. Physical IDs remain distinct from metadata `_id`. Batch validation
precedes mutation. Exact search supports squared L2, cosine and inner product,
with deterministic ID tie-breaking. Extreme finite vectors use a stable
double-precision fallback before ranking, while ordinary vectors use native
sqlite-vec distances. Source metadata filtering happens before
top-k selection and retains existing Python string-conversion behavior.
Internal job/session filters remain separate. Cosine zero vectors are rejected
explicitly because their distance is undefined. A migration encountering them
must remain unpublished and request a supported source disposition.

The normal iterator uses bounded keyset pages. It propagates failures rather
than reporting an empty store. A consistent multi-page export requires the
caller to hold an exclusive KB guard. The adapter is not itself the application's
authorization or upgrade-coordination layer.

## Migration foundation

See [the migration protocol](../../src/lfx/src/lfx/base/knowledge_bases/migration/README.md).
An entire export must match trusted snapshot inventory and its terminal
manifest before it becomes importable. Qualification uses a private disk ledger
with record, byte, depth, ID and vector limits. A failed source read cannot
produce a successful empty migration.

Import reuses the existing precomputed-vector bridge and makes no embedding
calls. It preserves IDs, vectors, metadata types and order, model identity,
metric, and known dimensions even for empty stores. Retry requires the exact
same migration identity and source fingerprint. Destination rows are compared
against the source ledger, then integrity-checked and durably finalized.

A receipt establishes a completed copy only. It does not activate routing,
release a fence, delete source snapshots or authorize a caller. Application DB
cutover and filesystem commits cannot share one transaction, so activation must
use a durable completed generation and compare-and-swap routing transaction.

## ALTK retirement

The optional ALTK integration is retired in 1.13.0 because its published SDK
unconditionally depends on langchain-chroma. Its existing component class,
module paths, fields and outputs remain loadable. Execution raises a retirement
error before model or tool calls, with guidance to replace the node with Agent.
The replacement does not reproduce ALTK's validation/reflection features.

The old `altk` extras remain empty for installation compatibility. Neither
those extras nor the dependency generator require the SDK, and the regenerated
lockfile no longer contains agent-lifecycle-toolkit. The current core component
index contains no ALTK node, so no unrelated index entries were regenerated.

## Validation and native platforms

The runtime workflow performs binary-only installation and actual extension,
WAL, second-connection, dimension-error and reopen checks across Python
3.10–3.14 on Linux x64/ARM64, macOS Intel/ARM64 and Windows x64.
Adding the workflow is not evidence that those jobs have run. Unsupported
native targets, including musl Linux and Windows ARM64, need a qualified build
or a declared support decision before the SQLite default ships.

`scripts/benchmark/sqlite_kb.py` builds a deterministic temporary corpus,
imports precomputed vectors and measures exact search with and without a 1%
filter. Example after installing the development environment and native extra:

```sh
uv run --no-sync python scripts/benchmark/sqlite_kb.py --rows 100000 --dimensions 384 1536 3072
```

The first-query measurement is not a cold OS-cache measurement. These timings
exclude model calls and do not establish an SLO or supported maximum corpus.
Cold-cache, peak-memory, concurrent read/write, crash/disk-full and large-store
upgrade rehearsals remain necessary.

## Remaining gates before default switch and full removal

1. Add authoritative app-DB migration state and storage generation, with
   migrations, durable coordinator recovery and routing compare-and-swap.
2. Integrate a whole-KB operation guard across API ingestion, direct Knowledge
   writes, Memory capture/regeneration, metadata edits, cleanup and deletion.
   The initial upgrade must stop all old workers, which cannot honor new fences.
3. Build, sign, scan and isolate the one-time helper independently of the
   application workspace. Qualify source formats and malicious input. A local
   Chroma 1.5.9 raw-Rust-reader experiment demonstrates feasibility for persisted
   index data and purged logs, not a supported upgrade tool.
4. Wire automatic preflight, pristine source and app-metadata backups, helper
   staging/offline kits, progress/recovery, readiness and post-copy verification.
   Prove crash recovery at each phase. Keep source backups by default.
5. Connect owner-aware SQLite routing to KB/Memory creation and retrieval,
   scores, UI defaults and settings. Preserve existing identities/history.
6. Retire standalone Chroma/LocalDB and Cloud implementations with saved-flow
   compatibility and validated migration bindings. Remote stores require their
   credentials and an external-writer stop, not implicit local conversion.
7. Remove both Chroma packages from manifests, extras, generators, universal
   lock/export, profiles, built wheels/images and managed installed environments.
   Run strict application startup/discovery and KB/Memory round trips with both
   packages unavailable. Keep the scanner's existing full scope.
8. Rehearse real old-install upgrades and fresh installs on supported platforms.
   Reconcile every scanner finding to its exact ID and final artifact. Track the
   helper's security disposition separately from the Chroma-free application.

Before new writes, rollback requires the preserved source, consistent app DB
backup and a compatible old application environment. After new writes, use
forward repair. Never automatically switch back to a stale source snapshot.
