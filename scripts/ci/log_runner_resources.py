"""Flush periodic runner and test-process measurements, including before a CI timeout."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import signal
import threading
import time
from pathlib import Path

import psutil


def read_linux_counters() -> dict[str, str]:
    """Retain pressure and cgroup counters when the runner exposes them."""
    paths = [Path("/proc/pressure") / name for name in ("cpu", "memory", "io")]
    paths += [
        Path("/sys/fs/cgroup") / name
        for name in ("cpu.max", "cpu.stat", "memory.current", "memory.max", "memory.events")
    ]
    counters = {}
    for path in paths:
        try:
            counters[str(path)] = path.read_text().strip()
        except OSError:
            # macOS development and some hosted runners do not expose these.
            continue
    return counters


def snapshot(parent: psutil.Process, directory: Path) -> dict:
    """Record counters without command lines or environment values that can contain secrets."""
    processes = []
    for process in [parent, *parent.children(recursive=True)]:
        try:
            with process.oneshot():
                processes.append(
                    {
                        "pid": process.pid,
                        "name": process.name(),
                        "cpu_seconds": process.cpu_times().user + process.cpu_times().system,
                        "rss_bytes": process.memory_info().rss,
                        "threads": process.num_threads(),
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    disk = psutil.disk_io_counters()
    return {
        "timestamp": time.time(),
        "monotonic_seconds": time.monotonic(),
        "cpu_times": psutil.cpu_times()._asdict(),
        "load_average": psutil.getloadavg(),
        "memory": psutil.virtual_memory()._asdict(),
        "swap": psutil.swap_memory()._asdict(),
        "disk_io": disk._asdict() if disk else None,
        "disk_usage": psutil.disk_usage(str(directory))._asdict(),
        "linux_counters": read_linux_counters(),
        "process_count": len(processes),
        "process_rss_bytes": sum(p["rss_bytes"] for p in processes),
        "processes": sorted(processes, key=lambda p: p["rss_bytes"], reverse=True)[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--interval", type=float, default=15)
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be a finite positive number")

    stopped = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stopped.set())
    parent = psutil.Process(args.parent_pid)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Line buffering retains complete samples even if the process is killed.
    with args.output.open("w", encoding="utf-8", buffering=1) as output:
        output.write(
            json.dumps(
                {
                    "event": "runner",
                    "platform": platform.platform(),
                    "cpu_count": psutil.cpu_count(),
                    "image_version": os.getenv("ImageVersion"),  # noqa: SIM112 - GitHub runner's variable name
                    "parent_pid": parent.pid,
                    "interval_seconds": args.interval,
                }
            )
            + "\n"
        )
        while parent.is_running():
            try:
                record = snapshot(parent, args.output.parent)
            except (OSError, psutil.Error) as exc:
                record = {"timestamp": time.time(), "event": "sampling_error", "error": type(exc).__name__}
            output.write(json.dumps(record) + "\n")
            if stopped.wait(args.interval):
                break


if __name__ == "__main__":
    main()
