"""Bounded mixed local disk I/O isolator for the performance suite.

Embedded into ``perf_disk_io`` (and ensemble fixtures) by ``flows/build_fixtures.py``.
Writes deterministic blocks with normal buffered I/O, ``fsync``s, optionally advises
the kernel to drop clean cached pages (``POSIX_FADV_DONTNEED``), then reads back and
verifies a checksum. Distinct from ``perf_payload_echo``, which validates the
SaveToFile/storage abstraction rather than sustained filesystem I/O.

File size is clamped using free disk space plus portable ``os.sysconf``
available-memory hints (``SC_AVPHYS_PAGES`` * ``SC_PAGE_SIZE``) and suite hard
caps. Logical vs backing-storage I/O counters are reported on Linux
(``/proc/thread-self/io``). Cached reads are reported, not failed — tmpfs /
device caches prevent a portable physical-media guarantee.

Covered by unit checks and live Workflows tests under ``tests/locust/tests/``.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from lfx.custom import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema.message import Message

_MIN_SIZE_BYTES = 64 * 1024  # 64 KiB
_DEFAULT_SIZE_BYTES = 4 * 1024 * 1024  # 4 MiB
_MAX_SIZE_BYTES = 64 * 1024 * 1024  # 64 MiB
_BLOCK_SIZE = 64 * 1024

_RESULT_RE = re.compile(
    r"^diskio:size=(?P<size>\d+):written=(?P<written>\d+):read=(?P<read>\d+):"
    r"cksum_ok=(?P<cksum_ok>[01]):write_ms=(?P<write_ms>\d+):fsync_ms=(?P<fsync_ms>\d+):"
    r"read_ms=(?P<read_ms>\d+):advise=(?P<advise>[01]):rchar=(?P<rchar>\d+):wchar=(?P<wchar>\d+):"
    r"read_bytes=(?P<read_bytes>\d+):write_bytes=(?P<write_bytes>\d+):"
    r"cached_read=(?P<cached_read>[01]):seed=(?P<seed>.*)$"
)


def available_memory_bytes(*, fallback: int = _MAX_SIZE_BYTES) -> int:
    """Estimate available physical RAM via portable ``os.sysconf`` names.

    Uses POSIX system-configuration queries when present:

    * ``SC_AVPHYS_PAGES`` — available physical memory pages
    * ``SC_PAGE_SIZE`` — bytes per memory page

    Product ≈ currently available physical RAM. This is an OS estimate, not a
    container/cgroup limit. On platforms without these names (e.g. Windows),
    return ``fallback`` so suite hard caps still bound the workload.

    Note: duplicated in ``perf_subprocess_churn`` on purpose — each isolator's
    source is embedded into fixture JSON and must stay import-free of sibling
    modules.
    """
    try:
        pages = int(os.sysconf("SC_AVPHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, TypeError, ValueError):
        return fallback
    if pages <= 0 or page_size <= 0:
        return fallback
    return pages * page_size


def resolve_size_bytes(*, requested: int, root: Path) -> int:
    """Clamp file size against free disk, memory budget, and suite hard caps."""
    if requested <= 0:
        requested = _DEFAULT_SIZE_BYTES
    try:
        free_disk = shutil.disk_usage(root).free
    except OSError:
        free_disk = _MAX_SIZE_BYTES
    mem_budget = available_memory_bytes() // 8
    return max(
        _MIN_SIZE_BYTES,
        min(requested, free_disk // 4, mem_budget, _MAX_SIZE_BYTES),
    )


def _work_root() -> Path:
    """Prefer Langflow ``config_dir`` when settings are available; else system temp."""
    with contextlib.suppress(Exception):
        from lfx.services.deps import get_settings_service

        config_dir = get_settings_service().settings.config_dir
        if config_dir:
            root = Path(config_dir) / "perf_disk_io"
            root.mkdir(parents=True, exist_ok=True)
            return root
    root = Path(tempfile.gettempdir()) / "langflow_perf_disk_io"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _read_thread_io() -> dict[str, int]:
    for path in (Path("/proc/thread-self/io"), Path("/proc/self/io")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        values: dict[str, int] = {}
        for line in text.splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            try:
                values[key.strip()] = int(raw.strip())
            except ValueError:
                continue
        if values:
            return values
    return {}


def _io_delta(before: dict[str, int], after: dict[str, int], key: str) -> int:
    return max(0, after.get(key, 0) - before.get(key, 0))


def _render_block(seed: str, index: int, size: int) -> bytes:
    material = f"{seed}:{index}:".encode()
    repeats = (size // len(material)) + 1
    return (material * repeats)[:size]


def parse_diskio_result(text: str) -> dict[str, object]:
    match = _RESULT_RE.match(text.strip())
    if match is None:
        msg = f"malformed diskio result: {text!r}"
        raise ValueError(msg)
    data = match.groupdict()
    return {
        "size": int(data["size"]),
        "written": int(data["written"]),
        "read": int(data["read"]),
        "cksum_ok": data["cksum_ok"] == "1",
        "write_ms": int(data["write_ms"]),
        "fsync_ms": int(data["fsync_ms"]),
        "read_ms": int(data["read_ms"]),
        "advise": data["advise"] == "1",
        "rchar": int(data["rchar"]),
        "wchar": int(data["wchar"]),
        "read_bytes": int(data["read_bytes"]),
        "write_bytes": int(data["write_bytes"]),
        "cached_read": data["cached_read"] == "1",
        "seed": data["seed"],
    }


class PerfDiskIo(Component):
    """Write/fsync/read/verify a bounded temporary file and report I/O metrics."""

    display_name = "Perf Disk IO"
    description = "Bounded mixed local disk I/O (write, fsync, advisory cold-read, verify)."
    name = "PerfDiskIo"
    icon = "hard-drive"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="Opaque payload mixed into deterministic file contents and echoed in the result.",
            value="perf-disk",
        ),
        IntInput(
            name="size_bytes",
            display_name="Size bytes",
            info=(
                "Target file size. Zero selects the suite default; values are clamped to free "
                f"disk / memory budget and {_MAX_SIZE_BYTES} bytes."
            ),
            value=_DEFAULT_SIZE_BYTES,
            range_spec=RangeSpec(min=0, max=_MAX_SIZE_BYTES, step=4096, step_type="int"),
        ),
    ]
    outputs = [
        Output(display_name="Output", name="output", method="run"),
    ]

    def run(self) -> Message:
        seed = getattr(self.input_value, "text", None) or str(self.input_value)
        root = _work_root()
        root.mkdir(parents=True, exist_ok=True)
        size = resolve_size_bytes(requested=int(self.size_bytes or 0), root=root)
        path = root / f"perf-disk-{uuid4().hex}.bin"
        digest = hashlib.sha256()
        written = 0
        read_total = 0
        advise_ok = 0
        cksum_ok = 0
        io_before = _read_thread_io()
        write_ms = 0
        fsync_ms = 0
        read_ms = 0
        try:
            write_start = time.perf_counter()
            with path.open("wb") as handle:
                remaining = size
                index = 0
                while remaining > 0:
                    chunk = _render_block(seed, index, min(_BLOCK_SIZE, remaining))
                    handle.write(chunk)
                    digest.update(chunk)
                    written += len(chunk)
                    remaining -= len(chunk)
                    index += 1
                handle.flush()
                write_ms = max(1, int((time.perf_counter() - write_start) * 1000))
                fsync_start = time.perf_counter()
                os.fsync(handle.fileno())
                fsync_ms = max(1, int((time.perf_counter() - fsync_start) * 1000))
                if hasattr(os, "posix_fadvise") and hasattr(os, "POSIX_FADV_DONTNEED"):
                    try:
                        os.posix_fadvise(handle.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
                        advise_ok = 1
                    except OSError:
                        advise_ok = 0

            expected = digest.hexdigest()
            verify = hashlib.sha256()
            read_start = time.perf_counter()
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(_BLOCK_SIZE)
                    if not chunk:
                        break
                    verify.update(chunk)
                    read_total += len(chunk)
            read_ms = max(1, int((time.perf_counter() - read_start) * 1000))
            cksum_ok = 1 if verify.hexdigest() == expected else 0
        finally:
            path.unlink(missing_ok=True)
            with contextlib.suppress(OSError):
                root.rmdir()

        io_after = _read_thread_io()
        rchar = _io_delta(io_before, io_after, "rchar")
        wchar = _io_delta(io_before, io_after, "wchar")
        read_bytes = _io_delta(io_before, io_after, "read_bytes")
        write_bytes = _io_delta(io_before, io_after, "write_bytes")
        # Report whether the kernel appears to have served the read from page cache.
        cached_read = 1 if (advise_ok and read_total > 0 and read_bytes < (read_total // 2)) else 0
        text = (
            f"diskio:size={size}:written={written}:read={read_total}:cksum_ok={cksum_ok}:"
            f"write_ms={write_ms}:fsync_ms={fsync_ms}:read_ms={read_ms}:advise={advise_ok}:"
            f"rchar={rchar}:wchar={wchar}:read_bytes={read_bytes}:write_bytes={write_bytes}:"
            f"cached_read={cached_read}:seed={seed}"
        )
        return Message(text=text)
