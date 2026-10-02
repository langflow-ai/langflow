"""Export local Chroma SQLite/HNSW data without importing a retired SDK.

Only a private, consistent snapshot may be passed here. Native index files
are treated as bounded data. The persisted write-ahead log is replayed for
vectors and metadata independently, since their checkpoints can differ.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import struct
import tempfile
from contextlib import closing
from pathlib import Path
from uuid import UUID

from lfx.base.knowledge_bases.backends.base import IngestedDocument
from lfx.base.knowledge_bases.migration.inert_pickle import read_index_metadata
from lfx.base.knowledge_bases.migration.legacy_index import read_persisted_vectors, regular_file
from lfx.base.knowledge_bases.migration.protocol import (
    DEFAULT_LIMITS,
    ExportHeader,
    MigrationProtocolError,
    write_export,
)

_DELETE = 3
_CHECKPOINT_BYTES = 8


def _sequence(value) -> int:
    """Decode a supported nonnegative legacy write-ahead-log sequence number."""
    if isinstance(value, bytes):
        if len(value) != _CHECKPOINT_BYTES:
            msg = "Unsupported legacy checkpoint"
            raise MigrationProtocolError(msg)
        value = int.from_bytes(value, "big")
    if type(value) is not int or value < 0:
        msg = "Invalid legacy checkpoint"
        raise MigrationProtocolError(msg)
    return value


def _metric(connection, collection: dict, segment_id: str) -> str:
    """Resolve a consistent distance metric from the legacy collection configuration."""
    metrics = set()
    legacy_defaults = set()
    for column in ("config_json_str", "schema_str"):
        value = collection.get(column)
        if not value:
            continue
        if len(value) > DEFAULT_LIMITS.max_line_bytes:
            msg = "Oversized legacy collection configuration"
            raise MigrationProtocolError(msg)
        config = json.loads(value)
        if not isinstance(config, dict):
            msg = "Invalid legacy collection configuration"
            raise MigrationProtocolError(msg)
        for key in ("hnsw", "hnsw_configuration"):
            if isinstance(config.get(key), dict) and "space" in config[key]:
                # Python Chroma records default internal configuration even
                # when the actual index uses hnsw:space from segment metadata.
                target = legacy_defaults if config[key].get("_type") == "HNSWConfigurationInternal" else metrics
                target.add(config[key]["space"])
        vector_index = config.get("vector_index", {})
        if isinstance(vector_index, dict) and isinstance(vector_index.get("hnsw"), dict):
            space = vector_index["hnsw"].get("space")
            if space is not None:
                metrics.add(space)
        # Rust stores the actual index metric in the collection schema.
        vector = config.get("keys", {}).get("#embedding", {}).get("float_list", {}).get("vector_index", {})
        if vector.get("config", {}).get("space") is not None:
            metrics.add(vector["config"]["space"])
    for table, identity, identifier in (
        ("collection_metadata", "collection_id", collection["id"]),
        ("segment_metadata", "segment_id", segment_id),
    ):
        # These identifiers are constants, never taken from the database.
        for row in connection.execute(
            f"SELECT str_value FROM {table} WHERE {identity}=? AND key='hnsw:space'",  # noqa: S608 -- identifiers are constants
            (identifier,),
        ):
            metrics.add(row[0])
    if not metrics:
        metrics = legacy_defaults
    if len(metrics) > 1 or (metrics and next(iter(metrics)) not in ("l2", "ip", "cosine")):
        msg = "Unsupported or inconsistent legacy distance metric"
        raise MigrationProtocolError(msg)
    return next(iter(metrics), "l2")


def _replay(connection, staging, topic: str, vector_checkpoint: int, metadata_checkpoint: int, dimensions: int | None):
    """Replay vector and metadata updates independently after their saved checkpoints."""
    rows = connection.execute(
        "SELECT seq_id, operation, id, vector, encoding, metadata FROM embeddings_queue "
        "WHERE topic=? AND seq_id>? ORDER BY seq_id",
        (topic, min(vector_checkpoint, metadata_checkpoint)),
    )
    for number, (sequence, operation, native_id, vector, encoding, metadata) in enumerate(rows):
        if number >= DEFAULT_LIMITS.max_records or operation not in (0, 1, 2, 3):
            msg = "Unsupported or excessive legacy log operations"
            raise MigrationProtocolError(msg)
        if type(native_id) is not str or not native_id or len(native_id.encode()) > DEFAULT_LIMITS.max_id_bytes:
            msg = "Invalid legacy document identity"
            raise MigrationProtocolError(msg)
        if sequence > vector_checkpoint:
            found = staging.execute("SELECT 1 FROM vectors WHERE id=?", (native_id,)).fetchone()
            if operation == _DELETE:
                staging.execute("DELETE FROM vectors WHERE id=?", (native_id,))
            elif (operation != 0 or not found) and (operation != 1 or found):
                if vector is not None:
                    if encoding != "FLOAT32" or dimensions is None or len(vector) != dimensions * 4:
                        msg = "Invalid legacy log vector"
                        raise MigrationProtocolError(msg)
                    staging.execute("INSERT OR REPLACE INTO vectors VALUES (?,?)", (native_id, vector))
                elif not found:
                    msg = "Legacy add operation has no vector"
                    raise MigrationProtocolError(msg)
        if sequence > metadata_checkpoint:
            found = staging.execute("SELECT metadata FROM documents WHERE id=?", (native_id,)).fetchone()
            if operation == _DELETE:
                staging.execute("DELETE FROM documents WHERE id=?", (native_id,))
            elif (operation != 0 or not found) and (operation != 1 or found):
                current = json.loads(found[0]) if found else {}
                if metadata is not None:
                    if len(metadata) > DEFAULT_LIMITS.max_line_bytes:
                        msg = "Oversized legacy log metadata"
                        raise MigrationProtocolError(msg)
                    patch = json.loads(metadata)
                    if type(patch) is not dict:
                        msg = "Invalid legacy log metadata"
                        raise MigrationProtocolError(msg)
                    for key, value in patch.items():
                        if value is None:
                            current.pop(key, None)
                        else:
                            current[key] = value
                staging.execute("INSERT OR REPLACE INTO documents VALUES (?,?)", (native_id, json.dumps(current)))


def export_local_snapshot(
    source: Path,
    output: Path,
    *,
    collection_name: str,
    source_id: str,
    source_fingerprint: str,
    model_fingerprint: str | None,
) -> ExportHeader:
    """Preserve native IDs, text, metadata, float32 vectors and distance metric."""
    database = regular_file(source / "chroma.sqlite3", 8 * 1024**3)
    with tempfile.TemporaryDirectory(prefix="legacy-reader-", dir=output.parent) as temporary:
        working = Path(temporary) / "source.sqlite3"
        shutil.copyfile(database, working)
        for suffix in ("-wal", "-journal"):
            companion = source / f"chroma.sqlite3{suffix}"
            if companion.exists():
                shutil.copyfile(regular_file(companion, 8 * 1024**3), working.with_name(f"source.sqlite3{suffix}"))
        # A killed DELETE-journal writer can leave uncommitted pages. Recover
        # only this private copy before opening it read-only for export.
        with closing(sqlite3.connect(working)) as recovery:
            recovery.execute("PRAGMA trusted_schema=OFF")
            if recovery.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                msg = "Legacy SQLite snapshot failed integrity verification"
                raise MigrationProtocolError(msg)
        with (
            closing(sqlite3.connect(f"{working.as_uri()}?mode=ro", uri=True)) as connection,
            closing(sqlite3.connect(Path(temporary) / "staging.sqlite3")) as staging,
        ):
            return _export(
                connection,
                staging,
                source,
                output,
                collection_name=collection_name,
                source_id=source_id,
                source_fingerprint=source_fingerprint,
                model_fingerprint=model_fingerprint,
            )


def _export(connection, staging, source, output, *, collection_name, source_id, source_fingerprint, model_fingerprint):
    """Read the disposable database copy, leaving the pristine snapshot unchanged."""
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA cache_size=-8192")
    connection.row_factory = sqlite3.Row
    expected_tables = {
        "collections",
        "segments",
        "embeddings",
        "embedding_metadata",
        "embeddings_queue",
        "max_seq_id",
        "collection_metadata",
        "segment_metadata",
    }
    placeholders = ",".join("?" for _ in expected_tables)
    tables = {
        row[0]: row[1]
        for row in connection.execute(
            f"SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN ({placeholders})",  # noqa: S608 -- generated placeholders
            tuple(expected_tables),
        )
    }
    if any(not (tables.get(name) or "").lstrip().upper().startswith("CREATE TABLE") for name in expected_tables):
        msg = "Legacy SQLite schema contains missing or unsupported tables"
        raise MigrationProtocolError(msg)
    for table, columns in (
        ("collections", ("id", "name", "dimension", "topic", "config_json_str", "schema_str")),
        ("segments", ("id", "type", "scope")),
        ("embeddings", ("embedding_id",)),
        ("embedding_metadata", ("key", "string_value", "int_value", "float_value", "bool_value")),
        ("embeddings_queue", ("seq_id", "operation", "id", "metadata", "vector", "encoding")),
        ("max_seq_id", ("seq_id",)),
        ("collection_metadata", ("str_value",)),
        ("segment_metadata", ("str_value",)),
    ):
        present = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for column in columns:
            if (
                column in present
                and connection.execute(
                    f"SELECT 1 FROM {table} WHERE length({column}) > ? LIMIT 1",  # noqa: S608 -- constant identifiers
                    (DEFAULT_LIMITS.max_line_bytes,),
                ).fetchone()
            ):
                msg = "Legacy SQLite value exceeds migration bounds"
                raise MigrationProtocolError(msg)
    present = {row[1] for row in connection.execute("PRAGMA table_info(collections)")}
    columns = ",".join(
        name for name in ("id", "name", "dimension", "topic", "config_json_str", "schema_str") if name in present
    )
    collections = connection.execute(
        f"SELECT {columns} FROM collections WHERE name=? LIMIT 2",  # noqa: S608 -- constant column names
        (collection_name,),
    ).fetchall()
    if len(collections) != 1:
        msg = "Legacy collection identity is ambiguous or missing"
        raise MigrationProtocolError(msg)
    collection = dict(collections[0])
    UUID(collection["id"])
    dimensions = collection["dimension"]
    if dimensions is not None and (type(dimensions) is not int or not 1 <= dimensions <= DEFAULT_LIMITS.max_dimensions):
        msg = "Invalid legacy vector dimensions"
        raise MigrationProtocolError(msg)
    segments = connection.execute(
        "SELECT id, type, scope FROM segments WHERE collection=? LIMIT 3", (collection["id"],)
    ).fetchall()
    vector = [row for row in segments if row["scope"] == "VECTOR"]
    metadata = [row for row in segments if row["scope"] == "METADATA"]
    if (
        len(vector) != 1
        or len(metadata) != 1
        or vector[0]["type"] != "urn:chroma:segment/vector/hnsw-local-persisted"
        or metadata[0]["type"] != "urn:chroma:segment/metadata/sqlite"
    ):
        msg = "Unsupported legacy segment format"
        raise MigrationProtocolError(msg)
    segment_id = vector[0]["id"]
    if str(UUID(segment_id)) != segment_id:
        msg = "Invalid legacy segment identity"
        raise MigrationProtocolError(msg)
    metric = _metric(connection, collection, segment_id)
    staging.executescript(
        "CREATE TABLE vectors(id TEXT PRIMARY KEY, embedding BLOB NOT NULL); "
        "CREATE TABLE documents(id TEXT PRIMARY KEY, metadata TEXT NOT NULL);"
    )
    checkpoints = {
        row[0]: _sequence(row[1])
        for row in connection.execute(
            "SELECT segment_id, seq_id FROM max_seq_id WHERE segment_id IN (?,?)", (segment_id, metadata[0]["id"])
        )
    }
    index = source / segment_id
    vector_checkpoint = 0
    empty_index = index.is_dir() and not index.is_symlink() and not any(index.iterdir())
    if index.exists() and not (empty_index and not checkpoints.get(segment_id, 0)):
        if index.is_symlink() or not index.is_dir() or dimensions is None:
            msg = "Invalid legacy index directory"
            raise MigrationProtocolError(msg)
        metadata_path = index / "index_metadata.pickle"
        state = (
            read_index_metadata(regular_file(metadata_path, 32 * 1024**2).read_bytes())
            if metadata_path.exists()
            else {}
        )
        vector_checkpoint = checkpoints.get(
            segment_id, _sequence(state["max_seq_id"]) if state.get("max_seq_id") is not None else 0
        )
        staging.executemany("INSERT INTO vectors VALUES (?,?)", read_persisted_vectors(index, dimensions, metric))
    elif checkpoints.get(segment_id, 0):
        msg = "Checkpointed legacy index is missing"
        raise MigrationProtocolError(msg)
    current_id = None
    values = {}
    metadata_bytes = 0
    rows = connection.execute(
        "SELECT e.embedding_id, m.key, m.string_value, m.int_value, m.float_value, m.bool_value "
        "FROM embeddings e LEFT JOIN embedding_metadata m ON e.id=m.id WHERE e.segment_id=? ORDER BY e.id, m.key",
        (metadata[0]["id"],),
    )
    for number, row in enumerate(rows):
        if number > DEFAULT_LIMITS.max_records * 100:
            msg = "Legacy metadata exceeds migration bounds"
            raise MigrationProtocolError(msg)
        if row[0] != current_id:
            if current_id is not None:
                staging.execute("INSERT INTO documents VALUES (?,?)", (current_id, json.dumps(values)))
            current_id, values, metadata_bytes = row[0], {}, 0
        if row[1] is not None:
            populated = [value for value in row[2:] if value is not None]
            if len(populated) != 1:
                msg = "Unsupported legacy metadata value"
                raise MigrationProtocolError(msg)
            value = bool(row[5]) if row[5] is not None else populated[0]
            metadata_bytes += len(json.dumps({row[1]: value}, ensure_ascii=False).encode("utf-8"))
            if metadata_bytes > DEFAULT_LIMITS.max_line_bytes:
                msg = "Legacy document metadata exceeds migration bounds"
                raise MigrationProtocolError(msg)
            values[row[1]] = value
    if current_id is not None:
        staging.execute("INSERT INTO documents VALUES (?,?)", (current_id, json.dumps(values)))
    _array_metadata(connection, staging, metadata[0]["id"])
    topic = collection.get("topic") or f"persistent://default/default/{collection['id']}"
    _replay(connection, staging, topic, vector_checkpoint, checkpoints.get(metadata[0]["id"], 0), dimensions)
    missing = staging.execute(
        "SELECT id FROM vectors WHERE id NOT IN (SELECT id FROM documents) UNION ALL "
        "SELECT id FROM documents WHERE id NOT IN (SELECT id FROM vectors) LIMIT 1"
    ).fetchone()
    if missing:
        msg = "Legacy vector and document identities do not match"
        raise MigrationProtocolError(msg)
    count = staging.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
    header = ExportHeader(source_id, source_fingerprint, "chroma-hnsw-v1", count, dimensions, metric, model_fingerprint)

    def documents():
        """Yield staged documents and embeddings after removing Chroma document metadata."""
        for native_id, vector, metadata in staging.execute(
            "SELECT v.id, v.embedding, d.metadata FROM vectors v JOIN documents d ON v.id=d.id ORDER BY v.id"
        ):
            values = json.loads(metadata)
            content = values.pop("chroma:document", None)
            if type(content) is not str:
                msg = "Legacy document text is missing"
                raise MigrationProtocolError(msg)
            yield IngestedDocument(
                id=native_id,
                content=content,
                metadata={key: value for key, value in values.items() if not key.startswith("chroma:")},
                embedding=list(struct.unpack(f"<{dimensions}f", vector)),
            )

    with output.open("wb") as stream:
        write_export(stream, header, documents())
    return header


def _array_metadata(connection, staging, segment_id: str) -> None:
    """Retain typed Chroma 1.5 lists in insertion order, under per-document bounds."""
    table = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='embedding_metadata_array'"
    ).fetchone()
    if table is None:
        return
    if not (table[0] or "").lstrip().upper().startswith("CREATE TABLE"):
        msg = "Unsupported legacy array metadata schema"
        raise MigrationProtocolError(msg)
    if connection.execute(
        "SELECT 1 FROM embedding_metadata_array WHERE length(key)>? OR length(string_value)>? LIMIT 1",
        (DEFAULT_LIMITS.max_line_bytes, DEFAULT_LIMITS.max_line_bytes),
    ).fetchone():
        msg = "Legacy array metadata value exceeds migration bounds"
        raise MigrationProtocolError(msg)
    rows = connection.execute(
        "SELECT e.embedding_id,m.key,m.string_value,m.int_value,m.float_value,m.bool_value "
        "FROM embeddings e JOIN embedding_metadata_array m ON e.id=m.id "
        "WHERE e.segment_id=? ORDER BY e.id,m.key,m.rowid",
        (segment_id,),
    )
    current_id, current_key, values, size = None, None, {}, 0
    for number, row in enumerate(rows):
        if number >= DEFAULT_LIMITS.max_records * 100:
            msg = "Legacy array metadata exceeds migration bounds"
            raise MigrationProtocolError(msg)
        if row[0] != current_id:
            if current_id is not None:
                staging.execute("UPDATE documents SET metadata=? WHERE id=?", (json.dumps(values), current_id))
            saved = staging.execute("SELECT metadata FROM documents WHERE id=?", (row[0],)).fetchone()
            if saved is None:
                msg = "Legacy array metadata document is missing"
                raise MigrationProtocolError(msg)
            current_id, current_key, values, size = row[0], None, json.loads(saved[0]), len(saved[0].encode())
        populated = [value for value in row[2:] if value is not None]
        if type(row[1]) is not str or len(populated) != 1:
            msg = "Unsupported legacy array metadata value"
            raise MigrationProtocolError(msg)
        value = bool(row[5]) if row[5] is not None else populated[0]
        size += len(json.dumps(value, ensure_ascii=False).encode()) + len(row[1].encode()) + 4
        if size > DEFAULT_LIMITS.max_line_bytes:
            msg = "Legacy document array metadata exceeds migration bounds"
            raise MigrationProtocolError(msg)
        if row[1] != current_key:
            if row[1] in values:
                msg = "Legacy scalar and array metadata overlap"
                raise MigrationProtocolError(msg)
            current_key = row[1]
            values[current_key] = []
        values[current_key].append(value)
    if current_id is not None:
        staging.execute("UPDATE documents SET metadata=? WHERE id=?", (json.dumps(values), current_id))
