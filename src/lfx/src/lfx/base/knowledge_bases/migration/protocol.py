"""Versioned inert interchange for isolated legacy-store exporters.

An export is UTF-8 JSON Lines: one header, zero or more documents, and one
terminal manifest. No source data is executable. Qualification consumes the
entire stream before returning anything importable, and spills its ID index
and normalized documents to a private temporary SQLite database.

This is not a snapshotter or a Chroma reader. A trusted upgrade coordinator
must establish a consistent snapshot and supply its independently inventoried
header. The helper must only write a terminal manifest after a successful
total read. Checksums detect corruption, not authenticity of an untrusted
helper. Artifact verification and process isolation belong to the coordinator.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import struct
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

from lfx.base.knowledge_bases.backends.base import IngestedDocument

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from types import TracebackType
    from typing import BinaryIO

    from typing_extensions import Self

PROTOCOL_VERSION = 1
MAX_BATCH_RECORDS = 5000
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class MigrationProtocolError(ValueError):
    """An export or destination failed a mandatory migration invariant."""


class AutomaticMigrationLimitError(MigrationProtocolError):
    """The bounded native reader requires an isolated managed helper for this store."""


@dataclass(frozen=True)
class ExportLimits:
    """Resource bounds checked before allocation or writing staging records."""

    max_line_bytes: int = 8 * 1024 * 1024
    max_total_bytes: int = 64 * 1024 * 1024 * 1024
    max_records: int = 10_000_000
    max_dimensions: int = 32_768
    max_id_bytes: int = 4096
    max_metadata_depth: int = 32

    def __post_init__(self) -> None:
        """Reject invalid export bounds before processing any untrusted records."""
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            msg = "Export limits must be positive integers"
            raise ValueError(msg)


DEFAULT_LIMITS = ExportLimits()


@dataclass(frozen=True)
class ExportHeader:
    """Source identity obtained from the stopped, snapshotted legacy store."""

    source_id: str
    source_fingerprint: str
    source_version: str
    count: int
    dimensions: int | None
    metric: str
    model_fingerprint: str | None


@dataclass(frozen=True)
class ExportManifest:
    """Digest of normalized float32 records in their exported order."""

    count: int
    records_sha256: str
    header_sha256: str


def canonical_json(value: Any) -> bytes:
    """Canonical bytes used by both helper and application qualification."""
    return _json_bytes(value, sort_keys=True)


def _json_bytes(value: Any, *, sort_keys: bool = False) -> bytes:
    """Preserve metadata object order, which existing source filters observe."""
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=sort_keys, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        msg = "Invalid inert JSON value"
        raise MigrationProtocolError(msg) from exc


def _fail(message: str) -> NoReturn:
    """Raise a protocol error without adopting partially validated data."""
    raise MigrationProtocolError(message)


def _validate_header(header: ExportHeader, limits: ExportLimits) -> None:
    """Validate source identity, metric, embedding schema and protocol limits."""
    if not isinstance(header, ExportHeader):
        _fail("Expected an export header")
    if type(header.count) is not int or not 0 <= header.count <= limits.max_records:
        _fail("Source count exceeds limit or has an invalid type")
    if header.dimensions is None:
        if header.count:
            _fail("A nonempty source requires dimensions")
    elif type(header.dimensions) is not int or not 1 <= header.dimensions <= limits.max_dimensions:
        _fail("Source dimensions exceed limit or have an invalid type")
    if header.metric not in ("l2", "cosine", "ip"):
        _fail("Unsupported source distance metric")
    for value in (header.source_id, header.source_version):
        if type(value) is not str or not value or len(value.encode("utf-8")) > limits.max_id_bytes:
            _fail("Invalid source identity")
    if type(header.source_fingerprint) is not str or not _SHA256.fullmatch(header.source_fingerprint):
        _fail("Invalid source fingerprint")
    if header.model_fingerprint is not None and (
        type(header.model_fingerprint) is not str or not _SHA256.fullmatch(header.model_fingerprint)
    ):
        _fail("Invalid embedding-model fingerprint")


def _header_record(header: ExportHeader) -> dict[str, Any]:
    """Serialize the canonical header used to bind the export digest."""
    return {"type": "header", "protocol_version": PROTOCOL_VERSION, **asdict(header)}


def _validate_json(value: Any, *, depth: int, limits: ExportLimits) -> None:
    """Check metadata types, finiteness, depth and collection limits."""
    if depth > limits.max_metadata_depth:
        _fail("Metadata depth exceeds limit")
    if value is None or type(value) in (bool, str, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _validate_json(item, depth=depth + 1, limits=limits)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _validate_json(item, depth=depth + 1, limits=limits)
        return
    _fail("Metadata must contain only finite, typed JSON values with string keys")


def document_record(doc: IngestedDocument, header: ExportHeader, limits: ExportLimits) -> dict[str, Any]:
    """Validate native IDs and vectors without computing any embeddings."""
    try:
        id_size = len(doc.id.encode("utf-8")) if type(doc.id) is str else 0
    except UnicodeEncodeError:
        _fail("Document IDs must contain valid UTF-8 text")
    if type(doc.id) is not str or not doc.id or id_size > limits.max_id_bytes:
        _fail("A bounded nonempty native document ID is required")
    if type(doc.content) is not str or type(doc.metadata) is not dict:
        _fail("Document content and metadata have invalid types")
    _validate_json(doc.metadata, depth=0, limits=limits)
    if type(doc.embedding) is not list or not doc.embedding or len(doc.embedding) != header.dimensions:
        _fail("Every document needs a vector matching the source dimensions")
    vector = []
    for value in doc.embedding:
        if type(value) not in (int, float):
            _fail("Vector components must be finite numbers")
        try:
            single = struct.unpack("<f", struct.pack("<f", value))[0]
        except (OverflowError, struct.error) as exc:
            msg = "Vector component is outside float32 range"
            raise MigrationProtocolError(msg) from exc
        if not math.isfinite(single):
            _fail("Vector components must be finite numbers")
        vector.append(single)
    if header.metric == "cosine" and not any(vector):
        _fail("Cosine distance is undefined for a zero vector")
    record = {"type": "document", "id": doc.id, "content": doc.content, "metadata": doc.metadata, "embedding": vector}
    if len(_json_bytes(record)) + 1 > limits.max_line_bytes:
        _fail("Document exceeds record byte limit")
    return record


def _document(record: dict[str, Any]) -> IngestedDocument:
    """Decode a document only after checking IDs, metadata and vector dimensions."""
    return IngestedDocument(
        id=record["id"], content=record["content"], metadata=record["metadata"], embedding=record["embedding"]
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON fields in untrusted export records."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("Export contains duplicate JSON object keys")
        result[key] = value
    return result


def _parse(line: bytes) -> dict[str, Any]:
    """Decode a finite JSON object and reject malformed export records."""
    try:
        record = json.loads(line, object_pairs_hook=_unique_object, parse_constant=lambda _: _fail("Nonfinite JSON"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, MigrationProtocolError):
            raise
        msg = "Export contains invalid JSON"
        raise MigrationProtocolError(msg) from exc
    if type(record) is not dict:
        _fail("Every export record must be an object")
    return record


def _same_keys(record: dict[str, Any], keys: set[str]) -> None:
    """Reject missing or unsupported fields in a protocol record."""
    if set(record) != keys:
        _fail("Export record has missing or unsupported fields")


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    # Private qualification data, not the production vector store. No extension
    # loading or custom functions are enabled on this temporary audit ledger.
    """Own a transaction and connection to the private qualification ledger."""
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class QualifiedExport:
    """Private replayable source ledger, available only after full validation.

    Use as a context manager to remove plaintext staging data on every outcome.
    Each operation owns its connection, so callers may offload to a worker.
    """

    def __init__(
        self,
        directory: tempfile.TemporaryDirectory,
        header: ExportHeader,
        manifest: ExportManifest,
        limits: ExportLimits,
    ) -> None:
        """Bind a fully validated manifest to its private replay ledger and export limits."""
        self._directory = directory
        self.path = Path(directory.name) / "qualified.sqlite3"
        self.header = header
        self.manifest = manifest
        self.limits = limits
        self._closed = False

    def __enter__(self) -> Self:
        """Return the qualified ledger for bounded replay within a managed lifetime."""
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Remove plaintext qualification data when leaving the managed lifetime."""
        self.close()

    def close(self) -> None:
        """Idempotently remove private staging data and mark the export closed."""
        self._closed = True
        self._directory.cleanup()

    def _check_open(self) -> None:
        """Reject reads after the qualified staging ledger has been closed."""
        if self._closed:
            _fail("Qualified source is closed")

    def read_batch(
        self, offset: int, *, batch_size: int = 500, max_batch_bytes: int = 16 * 1024 * 1024
    ) -> list[IngestedDocument]:
        """Read a bounded, cursor-ordered batch from the qualified source ledger."""
        self._check_open()
        if (
            type(offset) is not int
            or offset < 0
            or type(batch_size) is not int
            or not 1 <= batch_size <= MAX_BATCH_RECORDS
        ):
            _fail("Invalid migration batch bounds")
        if type(max_batch_bytes) is not int or max_batch_bytes < self.limits.max_line_bytes:
            _fail("Batch byte limit must permit one maximum-sized record")
        batch: list[IngestedDocument] = []
        size = 0
        with _connect(self.path) as connection:
            for payload, digest in connection.execute(
                "SELECT payload, digest FROM documents WHERE sequence >= ? ORDER BY sequence LIMIT ?",
                (offset, batch_size),
            ):
                if batch and size + len(payload) > max_batch_bytes:
                    break
                if hashlib.sha256(payload).hexdigest() != digest:
                    _fail("Qualified source staging checksum mismatch")
                batch.append(_document(_parse(payload)))
                size += len(payload)
        return batch

    def verify_batch(self, documents: list[IngestedDocument], seen_path: Path) -> None:
        """Compare full destination records and reject repeated destination IDs."""
        self._check_open()
        with _connect(self.path) as source, _connect(seen_path) as seen:
            seen.execute("CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY)")
            for document in documents:
                record = document_record(document, self.header, self.limits)
                row = source.execute("SELECT digest FROM documents WHERE id = ?", (document.id,)).fetchone()
                if row is None or hashlib.sha256(_json_bytes(record)).hexdigest() != row[0]:
                    _fail("Destination document differs from qualified source")
                try:
                    seen.execute("INSERT INTO seen (id) VALUES (?)", (document.id,))
                except sqlite3.IntegrityError as exc:
                    msg = "Destination iterator returned duplicate document IDs"
                    raise MigrationProtocolError(msg) from exc


def qualify_export(
    stream: BinaryIO,
    *,
    expected_header: ExportHeader,
    scratch_directory: Path | None = None,
    limits: ExportLimits = DEFAULT_LIMITS,
) -> QualifiedExport:
    """Consume and verify a complete export before permitting an import.

    Disk staging is private and cleaned after any parsing failure. The caller
    supplies a trusted scratch location with an appropriate disk quota. No
    untrusted source path is accepted in the interchange format.
    """
    _validate_header(expected_header, limits)
    directory = tempfile.TemporaryDirectory(prefix="lf-kb-export-", dir=scratch_directory)
    path = Path(directory.name) / "qualified.sqlite3"
    try:
        with _connect(path) as connection:
            connection.execute(
                "CREATE TABLE documents (id TEXT PRIMARY KEY, sequence INTEGER UNIQUE NOT NULL, "
                "payload BLOB NOT NULL, digest TEXT NOT NULL)"
            )
            total_bytes = 0

            def read_record() -> dict[str, Any] | None:
                """Read one export record while enforcing line and total-byte limits."""
                nonlocal total_bytes
                line = stream.readline(limits.max_line_bytes + 1)
                if not line:
                    return None
                total_bytes += len(line)
                if len(line) > limits.max_line_bytes or total_bytes > limits.max_total_bytes:
                    _fail("Export byte limit exceeded")
                if not line.endswith(b"\n"):
                    _fail("Export record is truncated, including terminal newline")
                return _parse(line)

            first = read_record()
            expected = _header_record(expected_header)
            if first != expected or canonical_json(first) != canonical_json(expected):
                _fail("Export header does not match trusted source inventory")
            header_digest = hashlib.sha256(canonical_json(first)).hexdigest()
            records_digest = hashlib.sha256()
            count = 0
            while True:
                record = read_record()
                if record is None:
                    _fail("Export is missing its terminal manifest")
                if record.get("type") == "complete":
                    _same_keys(record, {"type", "count", "records_sha256", "header_sha256"})
                    if type(record["count"]) is not int or record["count"] != count or count != expected_header.count:
                        _fail("Terminal manifest count does not match source inventory and exported records")
                    if (
                        record["records_sha256"] != records_digest.hexdigest()
                        or record["header_sha256"] != header_digest
                    ):
                        _fail("Terminal manifest checksum mismatch")
                    if stream.read(1):
                        _fail("Export contains trailing data after terminal manifest")
                    manifest = ExportManifest(count, records_digest.hexdigest(), header_digest)
                    break
                _same_keys(record, {"type", "id", "content", "metadata", "embedding"})
                if record["type"] != "document":
                    _fail("Unsupported export record type")
                if count >= expected_header.count:
                    _fail("Export record count exceeds source inventory")
                payload = _json_bytes(document_record(_document(record), expected_header, limits))
                try:
                    connection.execute(
                        "INSERT INTO documents VALUES (?, ?, ?, ?)",
                        (record["id"], count, payload, hashlib.sha256(payload).hexdigest()),
                    )
                except sqlite3.IntegrityError as exc:
                    msg = "Export contains duplicate native document IDs"
                    raise MigrationProtocolError(msg) from exc
                records_digest.update(payload + b"\n")
                count += 1
                if count % 500 == 0:
                    connection.commit()
        return QualifiedExport(directory, expected_header, manifest, limits)
    except BaseException:
        directory.cleanup()
        raise


def write_export(
    stream: BinaryIO,
    header: ExportHeader,
    documents: Iterable[IngestedDocument],
    *,
    limits: ExportLimits = DEFAULT_LIMITS,
) -> ExportManifest:
    """Emit the strict protocol, omitting completion on any source-read failure.

    Native readers supply their independently obtained successful source count.
    This utility never converts an exception into an empty or partial success.
    IDs are indexed on disk so duplicate detection does not grow process memory
    with collection size. The output stream must not be exposed before close.
    """
    _validate_header(header, limits)
    total_bytes = 0

    def emit(record: dict[str, Any], *, preserve_order: bool = False) -> bytes:
        """Write a complete export record while enforcing stream byte limits."""
        nonlocal total_bytes
        payload = _json_bytes(record) if preserve_order else canonical_json(record)
        total_bytes += len(payload) + 1
        if len(payload) + 1 > limits.max_line_bytes or total_bytes > limits.max_total_bytes:
            _fail("Export byte limit exceeded")
        if stream.write(payload + b"\n") != len(payload) + 1:
            _fail("Export output stream performed a partial write")
        return payload

    header_digest = hashlib.sha256(emit(_header_record(header))).hexdigest()
    digest = hashlib.sha256()
    count = 0
    with (
        tempfile.TemporaryDirectory(prefix="lf-kb-export-ids-") as directory,
        _connect(Path(directory) / "ids.sqlite3") as connection,
    ):
        connection.execute("CREATE TABLE ids (id TEXT PRIMARY KEY)")
        for doc in documents:
            record = document_record(doc, header, limits)
            if count >= header.count:
                _fail("Export count exceeds source count")
            try:
                connection.execute("INSERT INTO ids VALUES (?)", (doc.id,))
            except sqlite3.IntegrityError as exc:
                msg = "Export contains duplicate native document IDs"
                raise MigrationProtocolError(msg) from exc
            digest.update(emit(record, preserve_order=True) + b"\n")
            count += 1
            if count % 500 == 0:
                connection.commit()
        if count != header.count:
            _fail("Export count does not match successful source count")
    manifest = ExportManifest(count, digest.hexdigest(), header_digest)
    emit({"type": "complete", **asdict(manifest)})
    return manifest
