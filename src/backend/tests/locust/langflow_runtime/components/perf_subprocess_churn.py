"""Bounded concurrent multiprocess context-switch isolator for the performance suite.

Embedded into ``perf_multiproc_churn`` (and ensemble fixtures) by
``flows/build_fixtures.py``. Children run concurrently with independent
memory-resident working sets on one CPU (when affinity is available) so the
OS must schedule among them. This stresses spawn, context switching, and
cache/TLB disruption — not disk paging.

Working-set size is clamped using portable ``os.sysconf`` available-memory
hints (``SC_AVPHYS_PAGES`` * ``SC_PAGE_SIZE``) plus suite hard caps — not
Linux-only ``/proc`` or cgroup paths.

Covered by unit bounds checks and live Workflows assertions under
``tests/locust/tests/``. Child scheduler counters prefer Unix ``resource``;
when unavailable they report zeros (affinity metrics remain best-effort).
"""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
import sys
import time

from lfx.custom import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema.message import Message

# Hard ceilings so a misconfigured profile cannot fork-bomb or OOM the host.
_MAX_COUNT = 8
_MAX_TIMEOUT_S = 30
_MAX_DURATION_MS = 5_000
_MIN_WORKING_SET_BYTES = 256 * 1024  # 256 KiB
_DEFAULT_WORKING_SET_BYTES = 4 * 1024 * 1024  # 4 MiB
_MAX_WORKING_SET_BYTES = 64 * 1024 * 1024  # 64 MiB per child
_MAX_TOTAL_WORKING_SET_BYTES = 128 * 1024 * 1024  # 128 MiB across children
# Deterministic sentinel when a child exceeds timeout_s (not a real OS status).
_TIMEOUT_SENTINEL = -9
_PAGE_SIZE = 4096

# Compact child: wait for synchronized start, pin CPU, touch working set, report metrics.
# ``resource`` is Unix-only; on other platforms vcs/ivcs are reported as 0.
_CHILD_SCRIPT = r"""
import hashlib
import os
import sys
import time

try:
    import resource
except ImportError:
    resource = None

index = int(sys.argv[1])
ws_bytes = int(sys.argv[2])
duration_ms = int(sys.argv[3])
cpu_token = sys.argv[4]
page = int(sys.argv[5])
sys.stdin.readline()
aff = "none"
if cpu_token != "":
    try:
        cpu = int(cpu_token)
        os.sched_setaffinity(0, {cpu})
        aff = str(sorted(os.sched_getaffinity(0))[0])
    except (AttributeError, OSError, ValueError):
        aff = "unsupported"
pages = max(1, ws_bytes // page)
buf = bytearray(pages * page)
for i in range(pages):
    buf[i * page] = (index + i) & 0xFF
start = time.perf_counter()
deadline = start + (duration_ms / 1000.0)
touched = 0
round_i = 0
while time.perf_counter() < deadline:
    for i in range(pages):
        off = ((i + round_i) % pages) * page
        buf[off] = (buf[off] + 1) & 0xFF
        touched += 1
    round_i += 1
end = time.perf_counter()
digest = hashlib.sha256(bytes(buf[::page][:64])).hexdigest()[:16]
if resource is not None:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    vcs = int(usage.ru_nvcsw)
    ivcs = int(usage.ru_nivcsw)
else:
    vcs = 0
    ivcs = 0
print(
    f"child:pid={os.getpid()}:start={start:.6f}:end={end:.6f}:"
    f"pages={pages}:touched={touched}:cksum={digest}:aff={aff}:"
    f"vcs={vcs}:ivcs={ivcs}"
)
"""

_CHILD_RE = re.compile(
    r"^child:pid=(?P<pid>\d+):start=(?P<start>[0-9.]+):end=(?P<end>[0-9.]+):"
    r"pages=(?P<pages>\d+):touched=(?P<touched>\d+):cksum=(?P<cksum>[0-9a-f]+):"
    r"aff=(?P<aff>[^:]+):vcs=(?P<vcs>\d+):ivcs=(?P<ivcs>\d+)$"
)


def _sanitize_seed(raw: object) -> str:
    """Return a delimiter-safe seed for the multiproc metrics framing.

    Child records are joined with ``|`` after the header, so ``|`` and newlines
    are replaced. Colons inside the seed are left as-is (``split(":", 8)`` keeps
    the remainder intact).
    """
    text = getattr(raw, "text", None)
    seed = text if text is not None else str(raw)
    for ch in ("|", "\n", "\r"):
        seed = seed.replace(ch, "_")
    return seed


def available_memory_bytes(*, fallback: int = _MAX_TOTAL_WORKING_SET_BYTES) -> int:
    """Estimate available physical RAM via portable ``os.sysconf`` names.

    Uses POSIX system-configuration queries when present:

    * ``SC_AVPHYS_PAGES`` — available physical memory pages
    * ``SC_PAGE_SIZE`` — bytes per memory page

    Product ≈ currently available physical RAM. This is an OS estimate, not a
    container/cgroup limit. On platforms without these names (e.g. Windows),
    return ``fallback`` so suite hard caps still bound the workload.

    Note: duplicated in ``perf_disk_io`` on purpose — each isolator's source is
    embedded into fixture JSON and must stay import-free of sibling modules.
    """
    try:
        pages = int(os.sysconf("SC_AVPHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, TypeError, ValueError):
        return fallback
    if pages <= 0 or page_size <= 0:
        return fallback
    return pages * page_size


def resolve_working_set_bytes(*, requested: int, count: int) -> int:
    """Clamp per-child working set against host memory and suite hard caps."""
    if requested <= 0:
        requested = _DEFAULT_WORKING_SET_BYTES
    budget = available_memory_bytes() // 8  # leave headroom for the parent + Locust workers
    per_child_budget = max(_MIN_WORKING_SET_BYTES, min(_MAX_WORKING_SET_BYTES, budget // max(count, 1)))
    total_cap = _MAX_TOTAL_WORKING_SET_BYTES // max(count, 1)
    return max(_MIN_WORKING_SET_BYTES, min(requested, per_child_budget, total_cap, _MAX_WORKING_SET_BYTES))


def pick_affinity_cpu() -> str:
    """Return one allowed CPU id as a string, or empty when affinity is unavailable."""
    try:
        allowed = sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return ""
    if not allowed:
        return ""
    return str(allowed[0])


def parse_child_line(line: str) -> dict[str, object] | None:
    match = _CHILD_RE.match(line.strip())
    if match is None:
        return None
    data = match.groupdict()
    return {
        "pid": int(data["pid"]),
        "start": float(data["start"]),
        "end": float(data["end"]),
        "pages": int(data["pages"]),
        "touched": int(data["touched"]),
        "cksum": data["cksum"],
        "aff": data["aff"],
        "vcs": int(data["vcs"]),
        "ivcs": int(data["ivcs"]),
    }


def parse_multiproc_result(text: str) -> dict[str, object]:
    """Parse the component Message text into aggregate + child metrics."""
    header, *child_parts = text.split("|")
    # multiproc:count:codes:ws:elapsed_ms:overlap_ms:vcs:ivcs:seed
    parts = header.split(":", 8)
    if len(parts) != 9 or parts[0] != "multiproc":
        msg = f"malformed multiproc header: {header!r}"
        raise ValueError(msg)
    children = []
    for part in child_parts:
        parsed = parse_child_line(part)
        if parsed is None:
            msg = f"malformed child metrics: {part!r}"
            raise ValueError(msg)
        children.append(parsed)
    return {
        "count": int(parts[1]),
        "codes": [int(code) for code in parts[2].split(",") if code != ""],
        "ws_bytes": int(parts[3]),
        "elapsed_ms": int(parts[4]),
        "overlap_ms": int(parts[5]),
        "vcs": int(parts[6]),
        "ivcs": int(parts[7]),
        "seed": parts[8],
        "children": children,
    }


class PerfSubprocessChurn(Component):
    """Spawn concurrent short-lived processes that thrash independent working sets.

    Blocking multiprocess work is intentional for the multiproc isolator. Langflow
    runs sync ``run()`` via a thread pool; under high concurrency that pool can
    saturate — size generator threads accordingly when profiling this axis.
    """

    display_name = "Perf Subprocess Churn"
    description = "Bounded concurrent multiprocess context-switch pressure with memory-resident working sets."
    name = "PerfSubprocessChurn"
    icon = "terminal"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="Opaque payload echoed into the deterministic result.",
            value="perf-multiproc",
        ),
        IntInput(
            name="count",
            display_name="Subprocess count",
            info=f"Number of concurrent subprocesses to spawn (capped at {_MAX_COUNT}).",
            value=2,
            range_spec=RangeSpec(min=1, max=_MAX_COUNT, step=1, step_type="int"),
        ),
        IntInput(
            name="duration_ms",
            display_name="Duration ms",
            info=f"How long each child stays runnable while touching memory (capped at {_MAX_DURATION_MS}).",
            value=100,
            range_spec=RangeSpec(min=1, max=_MAX_DURATION_MS, step=1, step_type="int"),
        ),
        IntInput(
            name="working_set_bytes",
            display_name="Working set bytes",
            info=(
                "Per-child memory-resident working set. Zero selects the suite default; "
                f"values are clamped to host budget and {_MAX_WORKING_SET_BYTES} bytes."
            ),
            value=_DEFAULT_WORKING_SET_BYTES,
            advanced=True,
            range_spec=RangeSpec(min=0, max=_MAX_WORKING_SET_BYTES, step=4096, step_type="int"),
        ),
        IntInput(
            name="timeout_s",
            display_name="Timeout seconds",
            info=f"Wall-clock timeout for the whole concurrent batch (capped at {_MAX_TIMEOUT_S}).",
            value=5,
            advanced=True,
            range_spec=RangeSpec(min=1, max=_MAX_TIMEOUT_S, step=1, step_type="int"),
        ),
    ]
    outputs = [
        Output(display_name="Output", name="output", method="run"),
    ]

    def run(self) -> Message:
        count = max(1, min(int(self.count or 1), _MAX_COUNT))
        duration_ms = max(1, min(int(self.duration_ms or 1), _MAX_DURATION_MS))
        timeout_s = max(1, min(int(self.timeout_s or 1), _MAX_TIMEOUT_S))
        requested_ws = int(self.working_set_bytes or 0)
        ws_bytes = resolve_working_set_bytes(requested=requested_ws, count=count)
        seed = _sanitize_seed(self.input_value)
        cpu = pick_affinity_cpu()
        page = _PAGE_SIZE
        try:
            page = int(os.sysconf("SC_PAGE_SIZE"))
        except (AttributeError, OSError, ValueError):
            page = _PAGE_SIZE

        procs: list[subprocess.Popen[str]] = []
        codes: list[int] = []
        children: list[dict[str, object]] = []
        wall_start = time.perf_counter()
        try:
            for index in range(count):
                proc = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        _CHILD_SCRIPT,
                        str(index),
                        str(ws_bytes),
                        str(duration_ms),
                        cpu,
                        str(page),
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                procs.append(proc)
            for proc in procs:
                if proc.stdin is None:
                    msg = "subprocess stdin pipe was not created"
                    raise RuntimeError(msg)
                proc.stdin.write("go\n")
                proc.stdin.flush()
                proc.stdin.close()

            deadline = wall_start + timeout_s
            for proc in procs:
                remaining = max(0.01, deadline - time.perf_counter())
                try:
                    stdout, stderr = proc.communicate(timeout=remaining)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                    codes.append(_TIMEOUT_SENTINEL)
                    continue
                code = int(proc.returncode if proc.returncode is not None else _TIMEOUT_SENTINEL)
                codes.append(code)
                line = (stdout or "").strip().splitlines()[-1] if (stdout or "").strip() else ""
                parsed = parse_child_line(line) if line else None
                if parsed is None:
                    detail = (stderr or "").strip() or line or f"exit={code}"
                    msg = f"child produced malformed metrics: {detail}"
                    raise RuntimeError(msg)
                children.append(parsed)
        finally:
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                    with contextlib.suppress(Exception):
                        proc.wait(timeout=1)

        elapsed_ms = max(1, int((time.perf_counter() - wall_start) * 1000))
        if children:
            latest_start = max(float(child["start"]) for child in children)
            earliest_end = min(float(child["end"]) for child in children)
            overlap_ms = max(0, int((earliest_end - latest_start) * 1000))
        else:
            overlap_ms = 0
        total_vcs = sum(int(child["vcs"]) for child in children)
        total_ivcs = sum(int(child["ivcs"]) for child in children)
        code_csv = ",".join(str(code) for code in codes)
        child_csv = "|".join(
            (
                f"child:pid={child['pid']}:start={float(child['start']):.6f}:end={float(child['end']):.6f}:"
                f"pages={child['pages']}:touched={child['touched']}:cksum={child['cksum']}:"
                f"aff={child['aff']}:vcs={child['vcs']}:ivcs={child['ivcs']}"
            )
            for child in children
        )
        header = f"multiproc:{count}:{code_csv}:{ws_bytes}:{elapsed_ms}:{overlap_ms}:{total_vcs}:{total_ivcs}:{seed}"
        text = header if not child_csv else f"{header}|{child_csv}"
        return Message(text=text)
