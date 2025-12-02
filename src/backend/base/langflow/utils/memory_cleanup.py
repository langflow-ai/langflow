"""Memory cleanup utilities for Langflow.

This module provides utilities to help free memory back to the OS and improve
garbage collection effectiveness.
"""

import gc
import os
import sys
from typing import Any

from lfx.log.logger import logger

from langflow.utils.memory_tracking import get_memory_tracker


def aggressive_gc(threshold: tuple[int, int, int] | None = None) -> dict[str, Any]:
    """Perform aggressive garbage collection.

    This function:
    1. Collects all generations multiple times
    2. Optionally adjusts GC thresholds
    3. Forces collection of cyclic references

    Args:
        threshold: Optional GC generation thresholds. If None, uses (700, 10, 10) for more aggressive collection.

    Returns:
        Dictionary with cleanup statistics
    """
    tracker = get_memory_tracker()
    before_stats = tracker.get_memory_stats()

    # Set more aggressive thresholds if not provided
    if threshold is None:
        threshold = (700, 10, 10)  # More aggressive than default (700, 10, 10)

    old_threshold = gc.get_threshold()
    gc.set_threshold(*threshold)

    # Collect all generations multiple times
    collected = 0
    for generation in range(3):
        for _ in range(3):  # Multiple passes
            collected += gc.collect(generation)

    # Final full collection
    collected += gc.collect()

    after_stats = tracker.get_memory_stats()

    cleanup_stats = {
        "objects_collected": collected,
        "rss_before_mb": before_stats.get("rss_mb", 0),
        "rss_after_mb": after_stats.get("rss_mb", 0),
        "rss_freed_mb": before_stats.get("rss_mb", 0) - after_stats.get("rss_mb", 0),
        "gc_objects_before": before_stats.get("gc_objects", 0),
        "gc_objects_after": after_stats.get("gc_objects", 0),
        "old_threshold": old_threshold,
        "new_threshold": threshold,
    }

    logger.info(
        f"Aggressive GC: Collected {collected} objects, "
        f"freed {cleanup_stats['rss_freed_mb']:.2f} MB RSS "
        f"(objects: {cleanup_stats['gc_objects_before']:,} -> {cleanup_stats['gc_objects_after']:,})"
    )

    return cleanup_stats


def clear_module_cache(modules_to_clear: list[str] | None = None) -> int:
    """Clear cached modules to free memory.

    Args:
        modules_to_clear: List of module names to clear. If None, clears common caching modules.

    Returns:
        Number of modules cleared
    """
    if modules_to_clear is None:
        # Common modules that cache data
        modules_to_clear = [
            "langflow.interface.components",
            "langflow.interface.types",
            "langflow.services.cache",
        ]

    cleared = 0
    for module_name in modules_to_clear:
        if module_name in sys.modules:
            module = sys.modules[module_name]
            # Clear common cache attributes
            for attr_name in ["_cache", "_types_cache", "cache", "CACHE"]:
                if hasattr(module, attr_name):
                    cache = getattr(module, attr_name)
                    if isinstance(cache, dict):
                        cache.clear()
                        cleared += 1
                    elif hasattr(cache, "clear"):
                        cache.clear()
                        cleared += 1

    logger.info(f"Cleared cache from {cleared} module attributes")
    return cleared


def suggest_memory_cleanup() -> dict[str, Any]:
    """Suggest and optionally perform memory cleanup based on current memory usage.

    Returns:
        Dictionary with cleanup suggestions and results
    """
    tracker = get_memory_tracker()
    stats = tracker.get_memory_stats()

    suggestions: list[str] = []
    results: dict[str, Any] = {}

    # Check RSS usage
    rss_mb = stats.get("rss_mb", 0)
    if rss_mb > 1000:  # More than 1GB
        suggestions.append("High RSS usage detected, consider aggressive GC")
        gc_result = aggressive_gc()
        results["gc_cleanup"] = gc_result

    # Check object count
    gc_objects = stats.get("gc_objects", 0)
    if gc_objects > 100000:  # More than 100k objects
        suggestions.append("High object count detected, consider clearing caches")
        cache_result = clear_module_cache()
        results["cache_cleanup"] = cache_result

    # Check GC collections
    gc_collections = stats.get("gc_collections", 0)
    if gc_collections > 1000:
        suggestions.append("Many GC collections, memory pressure detected")

    results["suggestions"] = suggestions
    results["current_stats"] = stats

    if suggestions:
        logger.info(f"Memory cleanup suggestions: {', '.join(suggestions)}")

    return results


def free_memory_to_os() -> dict[str, Any]:
    """Attempt to free memory back to the OS.

    This is a best-effort approach. Python's memory allocator (pymalloc)
    may not always return memory to the OS immediately.

    Returns:
        Dictionary with cleanup results
    """
    tracker = get_memory_tracker()
    before_stats = tracker.get_memory_stats()

    # Step 1: Aggressive garbage collection
    gc_result = aggressive_gc()

    # Step 2: Clear module caches
    cache_result = clear_module_cache()

    # Step 3: Try to trigger memory return to OS (platform-specific)
    # Note: This is best-effort and may not work on all platforms
    try:
        import ctypes

        # On Linux, we can try to call malloc_trim if available
        if sys.platform == "linux":
            try:
                libc = ctypes.CDLL("libc.so.6")
                if hasattr(libc, "malloc_trim"):
                    libc.malloc_trim(0)
                    logger.debug("Called malloc_trim to free memory to OS")
            except Exception as e:
                logger.debug(f"Could not call malloc_trim: {e}")
    except ImportError:
        pass

    after_stats = tracker.get_memory_stats()

    results = {
        "gc_cleanup": gc_result,
        "cache_cleanup": cache_result,
        "rss_before_mb": before_stats.get("rss_mb", 0),
        "rss_after_mb": after_stats.get("rss_mb", 0),
        "rss_freed_mb": before_stats.get("rss_mb", 0) - after_stats.get("rss_mb", 0),
        "gc_objects_before": before_stats.get("gc_objects", 0),
        "gc_objects_after": after_stats.get("gc_objects", 0),
    }

    logger.info(
        f"Memory cleanup complete: Freed {results['rss_freed_mb']:.2f} MB RSS, "
        f"collected {gc_result['objects_collected']} objects"
    )

    return results


def configure_gc_for_memory_efficiency() -> dict[str, Any]:
    """Configure garbage collection thresholds for better memory efficiency.

    Returns:
        Dictionary with old and new thresholds
    """
    old_threshold = gc.get_threshold()

    # More aggressive thresholds for better memory management
    # Generation 0: collect after 500 allocations (default: 700)
    # Generation 1: collect after 10 collections of gen 0 (default: 10)
    # Generation 2: collect after 10 collections of gen 1 (default: 10)
    new_threshold = (500, 10, 10)

    gc.set_threshold(*new_threshold)

    result = {
        "old_threshold": old_threshold,
        "new_threshold": new_threshold,
    }

    logger.info(f"GC thresholds updated: {old_threshold} -> {new_threshold}")

    return result

