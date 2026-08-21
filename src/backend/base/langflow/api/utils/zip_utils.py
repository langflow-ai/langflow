"""Utilities for handling ZIP file uploads containing flow JSON data."""

from __future__ import annotations

import asyncio
import io
import zipfile
from dataclasses import dataclass, field

import orjson
from lfx.log.logger import logger

# Safety limits to prevent zip bomb / DoS attacks
MAX_ZIP_ENTRIES = 500
MAX_ENTRY_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB per file

# Reserved zip member carrying project-level metadata (project_type, project_config).
# Every other ``.json`` entry is a flow, so this name must be skipped when collecting
# flows or it is imported as a junk flow. Matched on the basename, case-insensitively,
# so a zip written with a directory prefix still resolves.
PROJECT_METADATA_FILENAME = "project.json"


def _is_project_metadata(filename: str) -> bool:
    return filename.rsplit("/", 1)[-1].lower() == PROJECT_METADATA_FILENAME


@dataclass
class _ZipExtractionResult:
    """Result of synchronous ZIP extraction, including warnings to log after."""

    flows: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    project_metadata: dict | None = None


def _extract_flows_sync(contents: bytes) -> _ZipExtractionResult:
    """Synchronous helper that performs all blocking ZIP I/O.

    Raises:
        ValueError: If the ZIP is corrupt or contains more than MAX_ZIP_ENTRIES JSON files.
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

        for info in json_entries:
            if info.file_size > MAX_ENTRY_UNCOMPRESSED_BYTES:
                result.warnings.append(
                    f"Skipping ZIP entry '{info.filename}': uncompressed size "
                    f"{info.file_size} exceeds limit of {MAX_ENTRY_UNCOMPRESSED_BYTES} bytes"
                )
                continue
            try:
                raw = zf.read(info.filename)
                if len(raw) > MAX_ENTRY_UNCOMPRESSED_BYTES:
                    result.warnings.append(
                        f"Skipping ZIP entry '{info.filename}': actual size "
                        f"{len(raw)} exceeds limit of {MAX_ENTRY_UNCOMPRESSED_BYTES} bytes"
                    )
                    continue
                parsed = orjson.loads(raw)
                if _is_project_metadata(info.filename):
                    # Project metadata, not a flow. Ignore a non-object payload rather than
                    # failing the whole import over it.
                    if isinstance(parsed, dict):
                        result.project_metadata = parsed
                    else:
                        result.warnings.append(f"Ignoring ZIP entry '{info.filename}': expected a JSON object")
                    continue
                result.flows.append(parsed)
            except orjson.JSONDecodeError:
                result.warnings.append(f"Skipping ZIP entry '{info.filename}': invalid JSON")
                continue

    return result


async def extract_flows_from_zip(contents: bytes) -> list[dict]:
    """Extract flow JSON data from a ZIP file.

    Reads all .json files from the ZIP archive and returns their parsed contents.
    Enforces limits on entry count and individual file size to mitigate zip bomb attacks.
    Blocking I/O is offloaded to a thread to avoid blocking the event loop.

    Raises:
        ValueError: If the ZIP is corrupt or contains more than MAX_ZIP_ENTRIES JSON files.
    """
    flows, _ = await extract_project_from_zip(contents)
    return flows


async def extract_project_from_zip(contents: bytes) -> tuple[list[dict], dict | None]:
    """Extract flows and the optional project metadata member from a ZIP file.

    Returns the flows and the parsed ``project.json`` payload, or ``None`` when the archive
    does not carry one. Archives exported before project metadata existed simply have no such
    member, so they return ``None`` and import exactly as before.
    """
    result = await asyncio.to_thread(_extract_flows_sync, contents)

    for warning in result.warnings:
        await logger.awarning(warning)

    return result.flows, result.project_metadata
