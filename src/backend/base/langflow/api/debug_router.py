import gc
import os
import tracemalloc
from fastapi import APIRouter, HTTPException

from lfx.log.logger import logger
from langflow.utils.memory_cleanup import (
    aggressive_gc,
    configure_gc_for_memory_efficiency,
    free_memory_to_os,
    suggest_memory_cleanup,
)
from langflow.utils.memory_tracking import get_memory_tracker, get_memory_summary

debug_router = APIRouter(tags=["Debug"])


def get_rss_memory_kb() -> int:
    """Get RSS (Resident Set Size) memory in KB for current process."""
    try:
        with open(f"/proc/{os.getpid()}/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except (FileNotFoundError, ValueError, IndexError):
        pass
    return 0


def get_large_memory_mappings() -> list[dict]:
    """Get large memory mappings (>10MB) to see what's using memory."""
    mappings = []
    try:
        pid = os.getpid()
        with open(f"/proc/{pid}/smaps", "r") as f:
            current_mapping = {}
            for line in f:
                if line[0].isdigit() or line[0] in "abcdef":
                    # New mapping - save previous if large enough
                    if current_mapping.get("size_kb", 0) > 10240:  # >10MB
                        mappings.append(current_mapping)
                    current_mapping = {"address": line.strip()}
                elif line.startswith("Size:"):
                    current_mapping["size_kb"] = int(line.split()[1])
                elif line.startswith("Rss:"):
                    current_mapping["rss_kb"] = int(line.split()[1])
                elif line.startswith("Anonymous:"):
                    current_mapping["anonymous_kb"] = int(line.split()[1])
                elif line.startswith("Path:"):
                    current_mapping["path"] = line.split(":", 1)[1].strip()
            # Don't forget the last one
            if current_mapping.get("size_kb", 0) > 10240:
                mappings.append(current_mapping)
    except (FileNotFoundError, ValueError, IndexError):
        pass
    # Sort by RSS, return top 10
    mappings.sort(key=lambda x: x.get("rss_kb", 0), reverse=True)
    return mappings[:10]


def get_python_heap_size() -> int:
    """Get approximate Python heap size from tracemalloc."""
    if not tracemalloc.is_tracing():
        return 0
    snapshot = tracemalloc.take_snapshot()
    total_size = sum(stat.size for stat in snapshot.statistics("lineno"))
    return total_size


@debug_router.get("/debug/memory-snapshot")
async def memory_snapshot(limit: int = 20):
    """Get a memory snapshot using tracemalloc.
    
    Requires LANGFLOW_TRACE_MALLOC=1 to be set.
    
    Note: With multiple Gunicorn workers, each worker has its own tracemalloc state.
    This endpoint returns the snapshot from the worker that handles this request.
    
    Args:
        limit: Number of top allocations to return (default: 20)
    
    Returns:
        JSON response with top memory allocations, process ID, and memory stats
    """
    if not tracemalloc.is_tracing():
        raise HTTPException(
            status_code=400,
            detail="tracemalloc not enabled, set LANGFLOW_TRACE_MALLOC=1"
        )
    
    process_id = os.getpid()
    snapshot = tracemalloc.take_snapshot()
    # You can also use "filename" or "traceback" — "lineno" is usually most useful first
    top_stats = snapshot.statistics("lineno")
    
    lines: list[str] = []
    for stat in top_stats[:limit]:
        # stat looks like: /path/to/file.py:123: size=..., count=...
        lines.append(str(stat))
    
    # Get memory stats
    rss_mb = get_rss_memory_kb() / 1024
    python_heap_mb = get_python_heap_size() / 1024 / 1024
    native_mb = rss_mb - python_heap_mb  # Approximate native memory
    
    # Get large memory mappings to see what's using memory
    large_mappings = get_large_memory_mappings()
    mapping_info = [
        {
            "size_mb": round(m.get("size_kb", 0) / 1024, 2),
            "rss_mb": round(m.get("rss_kb", 0) / 1024, 2),
            "path": m.get("path", "[anonymous]")
        }
        for m in large_mappings
    ]
    
    # Log for later inspection
    logger.info(
        "=== tracemalloc top %s allocations (PID %s) ===\nRSS: %.1f MB, Python heap: %.1f MB, Native: %.1f MB\n%s",
        limit, process_id, rss_mb, python_heap_mb, native_mb, "\n".join(lines)
    )
    
    # Also return in JSON so you can curl it
    return {
        "process_id": process_id,
        "memory": {
            "rss_mb": round(rss_mb, 2),
            "python_heap_mb": round(python_heap_mb, 2),
            "native_mb": round(native_mb, 2),
            "note": "Native memory is approximate (RSS - Python heap). If native_mb grows while python_heap_mb stays flat, leak is likely in C extensions."
        },
        "large_mappings": mapping_info,
        "top": lines,
        "note": "With multiple workers, each request may hit a different worker. Call multiple times to see all workers."
    }


@debug_router.get("/debug/memory-summary")
async def memory_summary_endpoint():
    """Get a summary of current memory usage.
    
    Returns:
        JSON response with current memory statistics
    """
    logger.info("Memory summary endpoint called")
    tracker = get_memory_tracker()
    stats = tracker.get_memory_stats()
    summary = get_memory_summary()
    
    logger.info(
        f"Memory summary: RSS={stats.get('rss_mb', 0):.2f} MB, "
        f"GC Objects={stats.get('gc_objects', 0):,}, "
        f"Snapshots={len(tracker.snapshots)}"
    )
    
    return {
        "summary": summary,
        "stats": stats,
        "snapshots_count": len(tracker.snapshots),
    }


@debug_router.post("/debug/memory/cleanup")
async def memory_cleanup_endpoint(aggressive: bool = False):
    """Trigger memory cleanup.
    
    Args:
        aggressive: If True, performs aggressive cleanup including cache clearing
    
    Returns:
        JSON response with cleanup results
    """
    logger.info(f"Memory cleanup endpoint called (aggressive={aggressive})")
    tracker = get_memory_tracker()
    before_stats = tracker.get_memory_stats()
    
    logger.info(
        f"Before cleanup: RSS={before_stats.get('rss_mb', 0):.2f} MB, "
        f"GC Objects={before_stats.get('gc_objects', 0):,}, "
        f"GC Collections={before_stats.get('gc_collections', 0)}"
    )
    
    if aggressive:
        logger.info("Performing aggressive memory cleanup")
        result = free_memory_to_os()
    else:
        logger.info("Performing suggested memory cleanup")
        result = suggest_memory_cleanup()
    
    after_stats = tracker.get_memory_stats()
    logger.info(
        f"After cleanup: RSS={after_stats.get('rss_mb', 0):.2f} MB, "
        f"GC Objects={after_stats.get('gc_objects', 0):,}, "
        f"RSS freed={before_stats.get('rss_mb', 0) - after_stats.get('rss_mb', 0):.2f} MB"
    )
    
    return {
        "success": True,
        "cleanup_results": result,
        "memory_summary": get_memory_summary(),
    }


@debug_router.post("/debug/memory/gc")
async def memory_gc_endpoint(threshold: str | None = None):
    """Trigger garbage collection.
    
    Args:
        threshold: Optional GC threshold as "gen0,gen1,gen2" (e.g., "500,10,10")
    
    Returns:
        JSON response with GC results
    """
    logger.info(f"Memory GC endpoint called (threshold={threshold})")
    tracker = get_memory_tracker()
    before_stats = tracker.get_memory_stats()
    
    logger.info(
        f"Before GC: RSS={before_stats.get('rss_mb', 0):.2f} MB, "
        f"GC Objects={before_stats.get('gc_objects', 0):,}, "
        f"Current GC threshold={gc.get_threshold()}"
    )
    
    gc_threshold = None
    if threshold:
        try:
            parts = threshold.split(",")
            gc_threshold = (int(parts[0]), int(parts[1]), int(parts[2]))
            logger.info(f"Using custom GC threshold: {gc_threshold}")
        except (ValueError, IndexError):
            logger.error(f"Invalid threshold format: {threshold}")
            raise HTTPException(status_code=400, detail="Invalid threshold format. Use 'gen0,gen1,gen2'")
    else:
        logger.info("Using default GC threshold")
    
    result = aggressive_gc(threshold=gc_threshold)
    
    after_stats = tracker.get_memory_stats()
    logger.info(
        f"After GC: RSS={after_stats.get('rss_mb', 0):.2f} MB, "
        f"GC Objects={after_stats.get('gc_objects', 0):,}, "
        f"Objects collected={result.get('objects_collected', 0)}, "
        f"RSS freed={result.get('rss_freed_mb', 0):.2f} MB"
    )
    
    return {
        "success": True,
        "gc_results": result,
        "memory_summary": get_memory_summary(),
    }


@debug_router.post("/debug/memory/configure-gc")
async def configure_gc_endpoint():
    """Configure GC thresholds for better memory efficiency.
    
    Returns:
        JSON response with old and new thresholds
    """
    logger.info("Configure GC endpoint called")
    old_threshold = gc.get_threshold()
    logger.info(f"Current GC threshold: {old_threshold}")
    
    result = configure_gc_for_memory_efficiency()
    
    logger.info(
        f"GC threshold configured: {result['old_threshold']} -> {result['new_threshold']}"
    )
    
    return {
        "success": True,
        "configuration": result,
    }

