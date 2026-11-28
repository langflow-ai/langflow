"""Utilities for handling ZIP file uploads containing flow JSON data."""

from __future__ import annotations

import asyncio
import io
import zipfile
import zlib
from copy import copy
from dataclasses import dataclass, field

import orjson
from lfx.log.logger import logger

# Safety limits to prevent zip bomb / DoS attacks
MAX_ZIP_ENTRIES = 500
MAX_ENTRY_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB per file
# Archive-wide limit on expanded JSON bytes. The per-entry caps above alone
# allow up to ~25 GB of aggregate expansion (500 x 50 MB), which is enough to
# exhaust the worker's memory from a small compressed upload.
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100 MB across all entries
_ZIP_READ_CHUNK_BYTES = 64 * 1024


@dataclass
class _ZipExtractionResult:
    """Result of synchronous ZIP extraction, including warnings to log after."""

    flows: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _read_zip_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytearray:
    # These methods bound decompression on every supported Python version.
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        msg = f"Unsupported compression method for ZIP entry '{info.filename}'"
        raise ValueError(msg)

    # ZipExtFile stops at ZipInfo.file_size. Give it room to detect an extra
    # byte while keeping the original size and CRC for validation.
    read_info = copy(info)
    read_info.file_size += 1
    raw = bytearray()
    try:
        with archive.open(read_info) as entry:
            while len(raw) < read_info.file_size:
                chunk = entry.read(min(_ZIP_READ_CHUNK_BYTES, read_info.file_size - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
    except (zipfile.BadZipFile, EOFError, RuntimeError, zlib.error) as exc:
        msg = f"Invalid ZIP entry '{info.filename}'"
        raise ValueError(msg) from exc

    if len(raw) != info.file_size:
        msg = f"Uncompressed size does not match the declared size for ZIP entry '{info.filename}'"
        raise ValueError(msg)
    return raw


def _extract_flows_sync(contents: bytes) -> _ZipExtractionResult:
    """Synchronous helper that performs all blocking ZIP I/O.

    Raises:
        ValueError: If the ZIP is corrupt, contains more than MAX_ZIP_ENTRIES JSON files,
            or exceeds the aggregate uncompressed-size limit.
    """
    result = _ZipExtractionResult()

    try:
        zf = zipfile.ZipFile(io.BytesIO(contents), "r")
    except zipfile.BadZipFile as exc:
        msg = f"Uploaded file is not a valid ZIP archive: {exc}"
        raise ValueError(msg) from exc

    with zf:
        json_entries = [info for info in zf.infolist() if info.filename.lower().endswith(".json")]

        if len(json_entries) > MAX_ZIP_ENTRIES:
            msg = f"ZIP contains {len(json_entries)} JSON entries, exceeding the limit of {MAX_ZIP_ENTRIES}"
            raise ValueError(msg)

        # Entries over the per-entry limit are skipped below without being read,
        # so they cannot contribute to memory use and are excluded here.
        declared_total = sum(info.file_size for info in json_entries if info.file_size <= MAX_ENTRY_UNCOMPRESSED_BYTES)
        if declared_total > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
            msg = (
                f"ZIP entries declare {declared_total} uncompressed bytes in total, "
                f"exceeding the aggregate limit of {MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES} bytes"
            )
            raise ValueError(msg)

        for info in json_entries:
            if info.file_size > MAX_ENTRY_UNCOMPRESSED_BYTES:
                result.warnings.append(
                    f"Skipping ZIP entry '{info.filename}': uncompressed size "
                    f"{info.file_size} exceeds limit of {MAX_ENTRY_UNCOMPRESSED_BYTES} bytes"
                )
                continue
            # Each read verifies the entry's budget, including for invalid JSON.
            raw = _read_zip_entry(zf, info)
            try:
                result.flows.append(orjson.loads(raw))
            except orjson.JSONDecodeError:
                result.warnings.append(f"Skipping ZIP entry '{info.filename}': invalid JSON")

    return result


async def extract_flows_from_zip(contents: bytes) -> list[dict]:
    """Extract flow JSON data from a ZIP file.

    Reads all .json files from the ZIP archive and returns their parsed contents.
    Enforces limits on entry count, individual file size, and aggregate expanded
    size to mitigate zip bomb attacks.
    Blocking I/O is offloaded to a thread to avoid blocking the event loop.

    Raises:
        ValueError: If the ZIP is corrupt, contains more than MAX_ZIP_ENTRIES JSON files,
            or exceeds the aggregate uncompressed-size limit.
    """
    result = await asyncio.to_thread(_extract_flows_sync, contents)

    for warning in result.warnings:
        await logger.awarning(warning)

    return result.flows
