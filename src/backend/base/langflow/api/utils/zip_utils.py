"""Utilities for handling ZIP file uploads containing flow JSON data."""

from __future__ import annotations

import io
import zipfile

import orjson
from lfx.log.logger import logger

# Safety limits to prevent zip bomb / DoS attacks
MAX_ZIP_ENTRIES = 500
MAX_ENTRY_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB per file


async def extract_flows_from_zip(contents: bytes) -> list[dict]:
    """Extract flow JSON data from a ZIP file.

    Reads all .json files from the ZIP archive and returns their parsed contents.
    Enforces limits on entry count and individual file size to mitigate zip bomb attacks.

    Raises:
        ValueError: If the ZIP contains more than MAX_ZIP_ENTRIES JSON files.
    """
    flows: list[dict] = []

    with zipfile.ZipFile(io.BytesIO(contents), "r") as zip_file:
        json_entries = [info for info in zip_file.infolist() if info.filename.lower().endswith(".json")]

        if len(json_entries) > MAX_ZIP_ENTRIES:
            msg = f"ZIP contains {len(json_entries)} JSON entries, exceeding the limit of {MAX_ZIP_ENTRIES}"
            raise ValueError(msg)

        for info in json_entries:
            if info.file_size > MAX_ENTRY_UNCOMPRESSED_BYTES:
                await logger.awarning(
                    f"Skipping ZIP entry '{info.filename}': uncompressed size "
                    f"{info.file_size} exceeds limit of {MAX_ENTRY_UNCOMPRESSED_BYTES} bytes"
                )
                continue
            try:
                raw = zip_file.read(info.filename)
                flows.append(orjson.loads(raw))
            except orjson.JSONDecodeError:
                await logger.awarning(f"Skipping ZIP entry '{info.filename}': invalid JSON")
                continue

    return flows
