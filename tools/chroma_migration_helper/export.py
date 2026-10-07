"""Offline inert export using the pinned native reader, in an isolated container.

No Langflow dependency and no Python Chroma SDK. The application independently
qualifies the entire protocol before using any exported record.
"""

from __future__ import annotations

import hashlib
import importlib.abc
import json
import math
import os
import pickle
import shutil
import sqlite3
import stat
import struct
import sys
from pathlib import Path

READER_VERSION = "chroma-rust-1.5.9"
MAX_LINE_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 10_000_000
MAX_DIMENSIONS = 32_768
MAX_SOURCE_BYTES = 8 * 1024**3
MAX_SOURCE_FILES = 100_000
MAX_METADATA_DEPTH = 32
MAX_ID_BYTES = 4096
MAX_REQUEST_BYTES = 16_384


class NoChromaPython(importlib.abc.MetaPathFinder):
    """Never load stored embedding-function definitions through the SDK."""

    def find_spec(self, fullname, path=None, target=None):  # noqa: ARG002 -- importlib interface
        """Reject Chroma Python SDK imports from the isolated native reader."""
        if fullname == "chromadb" or fullname.startswith("chromadb."):
            msg = "Python Chroma SDK is disabled in the migration reader"
            raise RuntimeError(msg)


def no_pickle(*_args, **_kwargs):
    """Reject Python pickle decoding during untrusted legacy export."""
    msg = "Python pickle decoding is disabled in the migration reader"
    raise RuntimeError(msg)


def encode(value, *, sort_keys=False):
    """Encode finite UTF-8 JSON with optional canonical key ordering."""
    return json.dumps(value, ensure_ascii=False, sort_keys=sort_keys, separators=(",", ":"), allow_nan=False).encode()


def emit(value, *, sort_keys=False):
    """Write one JSON protocol record while enforcing the per-record line limit."""
    payload = encode(value, sort_keys=sort_keys)
    if len(payload) + 1 > MAX_LINE_BYTES:
        msg = "Export record exceeds byte limit"
        raise ValueError(msg)
    sys.stdout.buffer.write(payload + b"\n")
    return payload


def clone_snapshot(source: Path, destination: Path):
    """Never follow a link or permit special files, even inside the sandbox."""
    if source.is_symlink() or not source.is_dir() or destination.exists():
        msg = "Invalid snapshot or nonempty working destination"
        raise ValueError(msg)
    total = 0
    count = 0
    for current, directories, files in os.walk(source, followlinks=False):
        for name in (*directories, *files):
            path = Path(current) / name
            info = path.lstat()
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                msg = "Source contains a link or special file"
                raise ValueError(msg)
            if stat.S_ISREG(info.st_mode):
                if info.st_nlink != 1:
                    msg = "Source contains hard links"
                    raise ValueError(msg)
                count += 1
                total += info.st_size
                if count > MAX_SOURCE_FILES or total > MAX_SOURCE_BYTES:
                    msg = "Snapshot exceeds helper limits"
                    raise ValueError(msg)
    if not (source / "chroma.sqlite3").is_file():
        msg = "Snapshot has no Chroma database"
        raise ValueError(msg)
    shutil.copytree(source, destination)


def metadata_depth(value, depth=0):
    """Reject unsupported metadata types, non-string keys and excessive nesting."""
    if depth > MAX_METADATA_DEPTH:
        msg = "Metadata exceeds depth limit"
        raise ValueError(msg)
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            msg = "Metadata key is not a string"
            raise ValueError(msg)
        for child in value.values():
            metadata_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            metadata_depth(child, depth + 1)
    elif value is not None and type(value) not in (str, int, float, bool):
        msg = "Unsupported metadata value"
        raise ValueError(msg)


def export(request, source: Path, work: Path):
    """Read the isolated snapshot through the pinned native binding and emit bounded records."""
    sys.meta_path.insert(0, NoChromaPython())
    pickle.load = no_pickle
    pickle.loads = no_pickle
    import chromadb_rust_bindings as bindings

    clone_snapshot(source, work)
    reader = bindings.Bindings(
        allow_reset=False,
        sqlite_db_config=bindings.SqliteDBConfig(
            hash_type=bindings.MigrationHash.MD5,
            migration_mode=bindings.MigrationMode.Validate,
            url=str(work / "chroma.sqlite3"),
        ),
        hnsw_cache_size=2,
        persist_path=str(work),
    )
    collection = reader.get_collection(request["collection_name"], "default_tenant", "default_database")
    count = reader.count(str(collection.id))
    dimensions = collection.dimension
    configuration = collection.configuration
    if configuration.get("spann") is not None:
        msg = "SPANN source format has not been qualified"
        raise ValueError(msg)
    metric = (configuration.get("hnsw") or {}).get("space")
    if metric not in ("l2", "cosine", "ip"):
        msg = "Source has an unsupported or missing distance metric"
        raise ValueError(msg)
    if type(count) is not int or not 0 <= count <= MAX_RECORDS:
        msg = "Invalid source count"
        raise ValueError(msg)
    if dimensions is None:
        if count:
            msg = "Nonempty source lacks dimensions"
            raise ValueError(msg)
    elif type(dimensions) is not int or not 1 <= dimensions <= MAX_DIMENSIONS:
        msg = "Invalid source dimensions"
        raise ValueError(msg)
    header = {
        "type": "header",
        "protocol_version": 1,
        "source_id": request["source_id"],
        "source_fingerprint": request["source_fingerprint"],
        "source_version": READER_VERSION,
        "count": count,
        "dimensions": dimensions,
        "metric": metric,
        "model_fingerprint": request["model_fingerprint"],
    }
    header_hash = hashlib.sha256(emit(header, sort_keys=True)).hexdigest()
    digest = hashlib.sha256()
    observed = 0
    with sqlite3.connect(work.parent / "seen.sqlite3") as seen:
        seen.execute("CREATE TABLE ids (id TEXT PRIMARY KEY)")
        while observed < count:
            batch = reader.get(
                str(collection.id),
                limit=min(250, count - observed),
                offset=observed,
                include=["documents", "metadatas", "embeddings"],
            )
            if any(value is None for value in (batch.documents, batch.metadatas, batch.embeddings)):
                msg = "Native reader omitted requested fields"
                raise ValueError(msg)
            if len({len(batch.ids), len(batch.documents), len(batch.metadatas), len(batch.embeddings)}) != 1:
                msg = "Native reader returned inconsistent field lengths"
                raise ValueError(msg)
            if not batch.ids or len(batch.ids) > count - observed:
                msg = "Native reader returned a partial or oversized batch"
                raise ValueError(msg)
            for index, native_id in enumerate(batch.ids):
                if type(native_id) is not str or not native_id or len(native_id.encode()) > MAX_ID_BYTES:
                    msg = "Invalid native document ID"
                    raise ValueError(msg)
                text = batch.documents[index]
                metadata = batch.metadatas[index]
                if metadata is None:
                    metadata = {}
                if type(text) is not str or type(metadata) is not dict:
                    msg = "Source document content or metadata is invalid"
                    raise ValueError(msg)
                metadata_depth(metadata)
                vector = [struct.unpack("<f", struct.pack("<f", item))[0] for item in batch.embeddings[index]]
                if len(vector) != dimensions or not all(math.isfinite(item) for item in vector):
                    msg = "Source vector has invalid values or dimensions"
                    raise ValueError(msg)
                if metric == "cosine" and not any(vector):
                    msg = "Source cosine zero vector requires operator disposition"
                    raise ValueError(msg)
                seen.execute("INSERT INTO ids VALUES (?)", (native_id,))
                record = {
                    "type": "document",
                    "id": native_id,
                    "content": text,
                    "metadata": metadata,
                    "embedding": vector,
                }
                digest.update(emit(record) + b"\n")
                observed += 1
            seen.commit()
    if reader.count(str(collection.id)) != observed:
        msg = "Source count changed during export"
        raise ValueError(msg)
    if reader.get(str(collection.id), limit=1, offset=observed, include=[]).ids:
        msg = "Source contains records beyond its declared count"
        raise ValueError(msg)
    emit(
        {"type": "complete", "count": observed, "records_sha256": digest.hexdigest(), "header_sha256": header_hash},
        sort_keys=True,
    )
    sys.stdout.buffer.flush()


def main():
    """Read the helper request and export the mounted snapshot under fixed limits."""
    payload = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(payload) > MAX_REQUEST_BYTES:
        msg = "Request exceeds byte limit"
        raise ValueError(msg)
    request = json.loads(payload)
    required = {"collection_name", "source_id", "source_fingerprint", "model_fingerprint"}
    if type(request) is not dict or set(request) != required:
        msg = "Invalid export request"
        raise ValueError(msg)
    for key in ("collection_name", "source_id", "source_fingerprint"):
        if type(request[key]) is not str or not request[key] or len(request[key].encode()) > MAX_ID_BYTES:
            msg = "Invalid request identity"
            raise ValueError(msg)
    export(request, Path("/source"), Path("/work/source"))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- sanitize all native parser errors at the process boundary
        # Source data and stored configuration must not escape in error text.
        sys.exit(1)
