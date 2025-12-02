"""Memory tracking utilities for debugging memory leaks and growth in Langflow.

This module provides comprehensive memory tracking capabilities including:
- Process memory usage tracking (RSS, VMS)
- Python object allocation tracking via tracemalloc
- Garbage collection statistics
- Memory snapshot logging
- Memory cleanup utilities
"""

import asyncio
import gc
import os
import sys
import time
import tracemalloc
from collections import defaultdict
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment, unused-ignore]

from lfx.log.logger import logger


class MemoryTracker:
    """Tracks memory usage and allocations over time."""

    def __init__(self, log_dir: Path | str | None = None, enable_tracemalloc: bool = True):
        """Initialize memory tracker.

        Args:
            log_dir: Directory to write memory logs to. If None, uses current directory.
            enable_tracemalloc: Whether to enable tracemalloc for detailed allocation tracking.
        """
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.enable_tracemalloc = enable_tracemalloc
        self.tracemalloc_started = False
        self.snapshots: list[dict[str, Any]] = []
        self.process = psutil.Process() if psutil else None
        self.start_time = time.time()

        if enable_tracemalloc and not self.tracemalloc_started:
            try:
                tracemalloc.start()
                self.tracemalloc_started = True
                logger.info("Memory tracking: tracemalloc enabled")
            except Exception as e:
                logger.warning(f"Failed to start tracemalloc: {e}")
                self.enable_tracemalloc = False

    def get_memory_stats(self) -> dict[str, Any]:
        """Get current memory statistics.

        Returns:
            Dictionary containing memory statistics.
        """
        stats: dict[str, Any] = {
            "timestamp": time.time(),
            "elapsed": time.time() - self.start_time,
        }

        # Process memory stats
        if self.process:
            try:
                mem_info = self.process.memory_info()
                stats["rss_mb"] = mem_info.rss / (1024 * 1024)  # Resident Set Size in MB
                stats["vms_mb"] = mem_info.vms / (1024 * 1024)  # Virtual Memory Size in MB
                stats["percent"] = self.process.memory_percent()
                stats["available_mb"] = psutil.virtual_memory().available / (1024 * 1024) if psutil else None
            except Exception as e:
                logger.debug(f"Error getting process memory stats: {e}")

        # Python GC stats
        gc_stats = gc.get_stats()
        stats["gc_collections"] = sum(stat["collections"] for stat in gc_stats)
        stats["gc_collected"] = sum(stat["collected"] for stat in gc_stats)
        stats["gc_uncollectable"] = sum(stat["uncollectable"] for stat in gc_stats)

        # Object counts
        stats["gc_objects"] = len(gc.get_objects())

        # tracemalloc stats
        if self.tracemalloc_started:
            try:
                current, peak = tracemalloc.get_traced_memory()
                stats["traced_current_mb"] = current / (1024 * 1024)
                stats["traced_peak_mb"] = peak / (1024 * 1024)
            except Exception as e:
                logger.debug(f"Error getting tracemalloc stats: {e}")

        return stats

    def take_snapshot(self, label: str = "", context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Take a memory snapshot with optional label and context.

        Args:
            label: Label for this snapshot (e.g., "before_flow_run", "after_component")
            context: Additional context to include in snapshot

        Returns:
            Snapshot dictionary
        """
        snapshot = self.get_memory_stats()
        snapshot["label"] = label
        if context:
            snapshot["context"] = context

        # Get top memory allocations if tracemalloc is enabled
        if self.tracemalloc_started:
            try:
                snapshot_data = tracemalloc.take_snapshot()
                top_stats = snapshot_data.statistics("lineno")
                snapshot["top_allocations"] = [
                    {
                        "filename": stat.traceback[0].filename if stat.traceback else "unknown",
                        "lineno": stat.traceback[0].lineno if stat.traceback else 0,
                        "size_mb": stat.size / (1024 * 1024),
                        "count": stat.count,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ]
            except Exception as e:
                logger.debug(f"Error getting tracemalloc snapshot: {e}")

        self.snapshots.append(snapshot)
        return snapshot

    def log_snapshot(self, label: str = "", context: dict[str, Any] | None = None, level: str = "info") -> None:
        """Take and log a memory snapshot.

        Args:
            label: Label for this snapshot
            context: Additional context
            level: Log level (info, debug, warning)
        """
        snapshot = self.take_snapshot(label, context)
        log_msg = self._format_snapshot(snapshot)
        log_func = getattr(logger, level, logger.info)
        log_func(log_msg)

    def _format_snapshot(self, snapshot: dict[str, Any]) -> str:
        """Format snapshot for logging."""
        parts = [f"[Memory Snapshot: {snapshot.get('label', 'unnamed')}]"]
        parts.append(f"RSS: {snapshot.get('rss_mb', 0):.2f} MB")
        if "traced_current_mb" in snapshot:
            parts.append(f"Traced: {snapshot['traced_current_mb']:.2f} MB")
        parts.append(f"GC Objects: {snapshot.get('gc_objects', 0):,}")
        parts.append(f"GC Collections: {snapshot.get('gc_collections', 0)}")
        if "top_allocations" in snapshot and snapshot["top_allocations"]:
            parts.append("Top allocations:")
            for alloc in snapshot["top_allocations"][:3]:
                parts.append(
                    f"  {alloc['filename']}:{alloc['lineno']} - {alloc['size_mb']:.2f} MB ({alloc['count']} objects)"
                )
        return " | ".join(parts)

    def get_top_allocations(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get top memory allocations.

        Args:
            limit: Number of top allocations to return

        Returns:
            List of allocation dictionaries
        """
        if not self.tracemalloc_started:
            return []

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics("lineno")

            allocations = []
            for stat in top_stats[:limit]:
                traceback = stat.traceback[0] if stat.traceback else None
                allocations.append(
                    {
                        "filename": traceback.filename if traceback else "unknown",
                        "lineno": traceback.lineno if traceback else 0,
                        "size_mb": stat.size / (1024 * 1024),
                        "count": stat.count,
                    }
                )
            return allocations
        except Exception as e:
            logger.debug(f"Error getting top allocations: {e}")
            return []

    def compare_snapshots(self, snapshot1: dict[str, Any], snapshot2: dict[str, Any]) -> dict[str, Any]:
        """Compare two snapshots and return differences.

        Args:
            snapshot1: First snapshot
            snapshot2: Second snapshot

        Returns:
            Dictionary with differences
        """
        diff: dict[str, Any] = {}
        for key in ["rss_mb", "vms_mb", "gc_objects", "traced_current_mb"]:
            if key in snapshot1 and key in snapshot2:
                diff[key] = snapshot2[key] - snapshot1[key]
        return diff

    def write_snapshots_to_file(self, filename: str | None = None) -> Path:
        """Write all snapshots to a JSON file.

        Args:
            filename: Optional filename. If None, generates timestamped filename.

        Returns:
            Path to written file
        """
        import json

        if not filename:
            filename = f"memory_snapshots_{int(time.time())}.json"

        filepath = self.log_dir / filename
        with open(filepath, "w") as f:
            json.dump(self.snapshots, f, indent=2)

        logger.info(f"Memory snapshots written to {filepath}")
        return filepath

    def cleanup(self) -> dict[str, Any]:
        """Force garbage collection and return cleanup stats.

        Returns:
            Dictionary with cleanup statistics
        """
        before = self.get_memory_stats()

        # Force garbage collection
        collected = gc.collect()

        after = self.get_memory_stats()

        cleanup_stats = {
            "objects_collected": collected,
            "rss_before_mb": before.get("rss_mb", 0),
            "rss_after_mb": after.get("rss_mb", 0),
            "rss_freed_mb": before.get("rss_mb", 0) - after.get("rss_mb", 0),
            "gc_objects_before": before.get("gc_objects", 0),
            "gc_objects_after": after.get("gc_objects", 0),
        }

        logger.info(
            f"Memory cleanup: Collected {collected} objects, "
            f"freed {cleanup_stats['rss_freed_mb']:.2f} MB RSS"
        )

        return cleanup_stats


# Global memory tracker instance
_global_tracker: MemoryTracker | None = None


def get_memory_tracker() -> MemoryTracker:
    """Get or create the global memory tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        log_dir = os.getenv("LANGFLOW_MEMORY_LOG_DIR")
        enable_tracemalloc = os.getenv("LANGFLOW_ENABLE_TRACEMALLOC", "true").lower() == "true"
        _global_tracker = MemoryTracker(log_dir=log_dir, enable_tracemalloc=enable_tracemalloc)
    return _global_tracker


def track_memory(label: str = "", log_before: bool = True, log_after: bool = True):
    """Decorator to track memory usage around function execution.

    Args:
        label: Label for this memory tracking (defaults to function name)
        log_before: Whether to log memory before execution
        log_after: Whether to log memory after execution
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracker = get_memory_tracker()
            func_label = label or f"{func.__module__}.{func.__name__}"

            if log_before:
                tracker.log_snapshot(f"before_{func_label}", level="debug")

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                if log_after:
                    tracker.log_snapshot(f"after_{func_label}", level="debug")

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracker = get_memory_tracker()
            func_label = label or f"{func.__module__}.{func.__name__}"

            if log_before:
                tracker.log_snapshot(f"before_{func_label}", level="debug")

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                if log_after:
                    tracker.log_snapshot(f"after_{func_label}", level="debug")

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@contextmanager
def memory_context(label: str, log_before: bool = True, log_after: bool = True):
    """Context manager for memory tracking.

    Args:
        label: Label for this memory tracking context
        log_before: Whether to log memory before context
        log_after: Whether to log memory after context
    """
    tracker = get_memory_tracker()
    if log_before:
        tracker.log_snapshot(f"before_{label}", level="debug")
    try:
        yield tracker
    finally:
        if log_after:
            tracker.log_snapshot(f"after_{label}", level="debug")


def force_gc(threshold: tuple[int, int, int] | None = None) -> dict[str, Any]:
    """Force garbage collection with optional threshold tuning.

    Args:
        threshold: GC generation thresholds (0, 1, 2). If None, uses current thresholds.

    Returns:
        Cleanup statistics
    """
    tracker = get_memory_tracker()

    if threshold:
        old_threshold = gc.get_threshold()
        gc.set_threshold(*threshold)
        logger.debug(f"GC threshold changed from {old_threshold} to {threshold}")

    return tracker.cleanup()


def get_memory_summary() -> str:
    """Get a summary of current memory usage."""
    tracker = get_memory_tracker()
    stats = tracker.get_memory_stats()
    return tracker._format_snapshot(stats)

