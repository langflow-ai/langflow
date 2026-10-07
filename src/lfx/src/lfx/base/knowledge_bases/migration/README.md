# Knowledge base migration interchange

This package qualifies inert legacy exports and imports them into an unpublished
SQLite generation. It does not launch a helper, snapshot an active source,
change application routing, or make legacy stores available in the new runtime.

The upgrade coordinator must hold exclusive access to the destination generation
throughout import and validation. It must establish that every legacy writer has
stopped before snapshotting. A lease timeout is not proof of that condition.

## Protocol version 1

The binary stream contains UTF-8 JSON Lines, with a required final newline:

1. `header`: `protocol_version`, `source_id`, SHA-256 `source_fingerprint`,
   `source_version`, `count`, `dimensions`, `metric`, and nullable SHA-256
   `model_fingerprint`.
2. Exactly `count` `document` records: nonempty native `id`, string `content`,
   JSON object `metadata`, and a list of finite float32 `embedding` values.
3. `complete`: `count`, `header_sha256`, and `records_sha256`.

All record types include `type`. Unknown/missing fields, duplicate object keys,
duplicate native IDs, nonfinite values, inconsistent dimensions, truncated lines,
missing completion, trailing output and count/digest mismatches are errors.
Empty sources require a successful count and a terminal manifest. They must not
be manufactured from a failed or interrupted source reader.

The header digest is SHA-256 of its canonical JSON bytes. The records digest is
SHA-256 of all normalized document records, in export order, including a newline
after each record. Header canonical JSON uses sorted keys. Document JSON uses
the fixed field order `type`, `id`, `content`, `metadata`, `embedding` and retains
the original metadata object key order, recursively. Both use UTF-8, no
whitespace, and no NaN/Infinity. Embeddings round-trip through little-endian
float32 before hashing. Metadata retains its JSON types and object order because
existing Python-string source filters observe that order. Verification detects
changes to it. Physical IDs are distinct from metadata `_id`.
These checksums establish consistency, not helper authenticity.

`ExportLimits` caps record size, total input bytes, count, dimensions, ID size and
metadata depth. A private temporary SQLite ledger bounds process memory, detects
duplicate IDs and stores normalized records for replay. The configured scratch
filesystem also needs a disk quota. Use `QualifiedExport` as a context manager so
staging data is deleted after success and failure. Cleanup should be included in
the upgrade controller's crash-recovery retention policy.

## Import and recovery

`qualify_export()` consumes the entire stream and compares its header with
trusted snapshot inventory before returning an importable object. Call this
synchronous operation in the coordinator's bounded worker executor.

`import_qualified_export()` reuses `add_embedded_documents()` and requires exact
native IDs. It never calls an embedding provider. The target must be empty or
carry the identical importing/completed manifest for the same migration UUID,
source fingerprint, stream digests and target identity. An interrupted copy
replays the entire source by ID. It does not trust a record-count checkpoint.

Verification compares every target ID, text, typed metadata and float32 vector
against the source ledger. It rejects duplicate target IDs, partial iterators,
extra rows, identity/model/metric changes, count disagreement and failed database
integrity checks. Only then does it finalize the durable completion manifest and
return a receipt. A completed retry is reverified rather than blindly accepted.

A receipt is evidence for a later application-database compare-and-swap of the
routing pointer. It is not activation. On any failure the coordinator keeps the
generation unpublished and the original source fenced. Source snapshots remain
untouched. Recovery must reacquire exclusive generation access before replay.

## Helper qualification boundary

The helper belongs to a separately built, scanned, signed and isolated artifact.
This package adds no Chroma requirement. Do not install Chroma in the application
environment to use these primitives.

A local experiment on generated Chroma 1.5.9 data established that raw
`chromadb_rust_bindings` can read a disposable source clone without importing the
Python Chroma SDK or invoking Python pickle deserialization. It covered a
persisted HNSW index, purged operation logs, pending operations, updates and
deletions. That is a feasible reader direction, not release qualification.
Native parsers, older Python-store formats, malicious input, supported operating
systems, enforced network/filesystem isolation, helper signing and packaging,
and end-to-end stopped-worker upgrade recovery remain separate required gates.
