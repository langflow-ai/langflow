"""Read qualified 64-bit little-endian HNSW v1 vectors without native code."""

from __future__ import annotations

import math
import stat
import struct
from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.migration.inert_pickle import MAX_INDEX_METADATA_BYTES, read_index_metadata
from lfx.base.knowledge_bases.migration.protocol import (
    DEFAULT_LIMITS,
    AutomaticMigrationLimitError,
    MigrationProtocolError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_HEADER = struct.Struct("<i6QiI3QdQ")
_MIN_VECTOR_OFFSET = 4
_MAX_VECTOR_OFFSET = 4096
_MAX_SOURCE_BYTES = 8 * 1024**3


def regular_file(path: Path, limit: int) -> Path:
    """Reject links, special files and excessive allocation before reading."""
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        msg = "Legacy source contains an invalid or oversized file"
        raise MigrationProtocolError(msg)
    if info.st_size > limit:
        msg = "Legacy source exceeds automatic reader resource limits"
        raise AutomaticMigrationLimitError(msg)
    return path


def read_persisted_vectors(directory: Path, dimensions: int, metric: str) -> Iterator[tuple[str, bytes]]:
    """Yield original float32 vectors, restoring cosine lengths from the saved index."""
    metadata_path = directory / "index_metadata.pickle"
    metadata = (
        read_index_metadata(regular_file(metadata_path, MAX_INDEX_METADATA_BYTES).read_bytes())
        if metadata_path.exists()
        else {"id_to_label": {}, "label_to_id": {}}
    )
    ids = metadata.get("id_to_label")
    inverse = metadata.get("label_to_id")
    if (
        type(ids) is not dict
        or type(inverse) is not dict
        or len(ids) > DEFAULT_LIMITS.max_records
        or len(ids) != len(inverse)
        or any(type(key) is not str or not key or type(label) is not int or label < 0 for key, label in ids.items())
        or any(inverse.get(label) != key for key, label in ids.items())
        or metadata.get("dimensionality") not in (None, dimensions)
    ):
        msg = "Legacy index identity map is inconsistent"
        raise MigrationProtocolError(msg)
    header = regular_file(directory / "header.bin", _HEADER.size).read_bytes()
    if len(header) != _HEADER.size:
        msg = "Legacy HNSW header layout is unsupported"
        raise MigrationProtocolError(msg)
    version, level, capacity, count, stride, label_offset, vector_offset, _, _, _, _, _, _, _ = _HEADER.unpack(header)
    if (
        version != 1
        or level != 0
        or not 0 <= count <= capacity <= DEFAULT_LIMITS.max_records
        or not _MIN_VECTOR_OFFSET <= vector_offset <= _MAX_VECTOR_OFFSET
        or label_offset != vector_offset + dimensions * 4
        or stride != label_offset + 8
        or capacity * stride > _MAX_SOURCE_BYTES
    ):
        msg = "Legacy HNSW vector offsets or bounds are invalid"
        raise MigrationProtocolError(msg)
    data = regular_file(directory / "data_level0.bin", _MAX_SOURCE_BYTES)
    lengths = regular_file(directory / "length.bin", _MAX_SOURCE_BYTES)
    persisted_slots, remainder = divmod(data.stat().st_size, stride)
    if remainder or not count <= persisted_slots <= capacity or lengths.stat().st_size != persisted_slots * 4:
        msg = "Legacy HNSW vector files are truncated or inconsistent"
        raise MigrationProtocolError(msg)
    vector_format = struct.Struct(f"<{dimensions}f")
    observed = set()
    with data.open("rb") as records, lengths.open("rb") as magnitudes:
        for _ in range(count):
            record = records.read(stride)
            label = struct.unpack_from("<Q", record, label_offset)[0]
            length = struct.unpack("<f", magnitudes.read(4))[0]
            native_id = inverse.get(label)
            if native_id is None:
                continue
            if native_id in observed:
                msg = "Legacy index contains duplicate live identities"
                raise MigrationProtocolError(msg)
            if record[2] & 1:
                msg = "Legacy index maps a deleted vector to a live record"
                raise MigrationProtocolError(msg)
            vector = vector_format.unpack_from(record, vector_offset)
            if metric == "cosine":
                if not math.isfinite(length) or length < 0:
                    msg = "Legacy cosine vector has an invalid saved length"
                    raise MigrationProtocolError(msg)
                vector = tuple(value * length for value in vector)
            if not all(math.isfinite(value) for value in vector):
                msg = "Legacy vector contains a non-finite value"
                raise MigrationProtocolError(msg)
            observed.add(native_id)
            try:
                encoded = vector_format.pack(*vector)
            except (OverflowError, struct.error) as exc:
                msg = "Legacy restored vector exceeds float32 bounds"
                raise MigrationProtocolError(msg) from exc
            yield native_id, encoded
    if len(observed) != len(ids):
        msg = "Legacy index does not contain every declared vector"
        raise MigrationProtocolError(msg)
