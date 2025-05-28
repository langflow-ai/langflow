"""Cache monitoring utilities for tracking class constructor cache performance.

This module provides utilities to monitor cache hits, misses, memory usage,
and overall performance of the class constructor caching system.
"""

import asyncio
import gc
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass

import psutil

from langflow.utils.validate import get_cache_stats

logger = logging.getLogger(__name__)

# Constants for thresholds
EXCELLENT_HIT_RATE_THRESHOLD = 0.8
GOOD_HIT_RATE_THRESHOLD = 0.6
LOW_HIT_RATE_THRESHOLD = 0.5
VERY_LOW_HIT_RATE_THRESHOLD = 0.3
HIGH_MEMORY_THRESHOLD_MB = 1000
MEDIUM_MEMORY_THRESHOLD_MB = 500
LOW_MEMORY_THRESHOLD_MB = 200
HIGH_CREATION_TIME_THRESHOLD_MS = 100
MIN_REQUESTS_FOR_ANALYSIS = 100


@dataclass
class CacheMetrics:
    """Metrics for cache performance monitoring."""

    cache_hits: int = 0
    cache_misses: int = 0
    cache_size: int = 0
    max_cache_size: int = 0
    memory_usage_mb: float = 0.0
    creation_time_avg_ms: float = 0.0
    hit_rate: float = 0.0

    def to_dict(self) -> dict:
        """Convert metrics to dictionary for logging/serialization."""
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_size": self.cache_size,
            "max_cache_size": self.max_cache_size,
            "memory_usage_mb": round(self.memory_usage_mb, 2),
            "creation_time_avg_ms": round(self.creation_time_avg_ms, 2),
            "hit_rate": round(self.hit_rate, 4),
        }


class ClassConstructorCacheMonitor:
    """Monitor for tracking class constructor cache performance."""

    def __init__(self) -> None:
        self.metrics = CacheMetrics()
        self.creation_times: list[float] = []
        self.start_time = time.time()

    def record_cache_hit(self):
        """Record a cache hit."""
        self.metrics.cache_hits += 1
        self._update_hit_rate()

    def record_cache_miss(self, creation_time_ms: float):
        """Record a cache miss and creation time."""
        self.metrics.cache_misses += 1
        self.creation_times.append(creation_time_ms)
        self._update_hit_rate()
        self._update_avg_creation_time()

    def _update_hit_rate(self):
        """Update the cache hit rate."""
        total_requests = self.metrics.cache_hits + self.metrics.cache_misses
        if total_requests > 0:
            self.metrics.hit_rate = self.metrics.cache_hits / total_requests

    def _update_avg_creation_time(self):
        """Update the average creation time."""
        if self.creation_times:
            self.metrics.creation_time_avg_ms = sum(self.creation_times) / len(self.creation_times)

    def update_cache_stats(self):
        """Update cache size statistics."""
        stats = get_cache_stats()
        self.metrics.cache_size = stats["cache_size"]
        self.metrics.max_cache_size = stats["max_size"]

    def update_memory_usage(self):
        """Update memory usage statistics."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            self.metrics.memory_usage_mb = memory_info.rss / 1024 / 1024
        except (psutil.Error, OSError) as e:
            logger.debug("Could not get memory usage: %s", e)

    def get_metrics(self) -> CacheMetrics:
        """Get current metrics."""
        self.update_cache_stats()
        self.update_memory_usage()
        return self.metrics

    def get_summary(self) -> str:
        """Get a human-readable summary of cache performance."""
        metrics = self.get_metrics()
        uptime_hours = (time.time() - self.start_time) / 3600

        cache_efficiency = (
            "Excellent"
            if metrics.hit_rate > EXCELLENT_HIT_RATE_THRESHOLD
            else "Good"
            if metrics.hit_rate > GOOD_HIT_RATE_THRESHOLD
            else "Poor"
        )

        memory_impact = (
            "High"
            if metrics.memory_usage_mb > MEDIUM_MEMORY_THRESHOLD_MB
            else "Medium"
            if metrics.memory_usage_mb > LOW_MEMORY_THRESHOLD_MB
            else "Low"
        )

        return f"""
Class Constructor Cache Performance Summary:
============================================
Uptime: {uptime_hours:.2f} hours
Cache Hits: {metrics.cache_hits}
Cache Misses: {metrics.cache_misses}
Hit Rate: {metrics.hit_rate:.2%}
Cache Size: {metrics.cache_size}/{metrics.max_cache_size}
Memory Usage: {metrics.memory_usage_mb:.2f} MB
Avg Creation Time: {metrics.creation_time_avg_ms:.2f} ms

Cache Efficiency: {cache_efficiency}
Memory Impact: {memory_impact}
"""

    def log_metrics(self, level: str = "INFO"):
        """Log current metrics."""
        metrics_dict = self.get_metrics().to_dict()
        getattr(logger, level.lower())("Cache metrics: %s", metrics_dict)

    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics = CacheMetrics()
        self.creation_times.clear()
        self.start_time = time.time()


# Global monitor instance
_cache_monitor = ClassConstructorCacheMonitor()


def get_cache_monitor() -> ClassConstructorCacheMonitor:
    """Get the global cache monitor instance."""
    return _cache_monitor


@contextmanager
def monitor_class_creation():
    """Context manager to monitor class creation time."""
    start_time = time.time()
    try:
        yield
        # If we get here, it was a cache miss (new creation)
        creation_time_ms = (time.time() - start_time) * 1000
        _cache_monitor.record_cache_miss(creation_time_ms)
    except Exception:
        # Still record the miss even if creation failed
        creation_time_ms = (time.time() - start_time) * 1000
        _cache_monitor.record_cache_miss(creation_time_ms)
        raise


def record_cache_hit():
    """Record a cache hit."""
    _cache_monitor.record_cache_hit()


def force_garbage_collection():
    """Force garbage collection and log memory stats."""
    logger.debug("Forcing garbage collection...")
    before_mb = _cache_monitor.metrics.memory_usage_mb

    # Force multiple GC cycles
    for _ in range(3):
        gc.collect()

    _cache_monitor.update_memory_usage()
    after_mb = _cache_monitor.metrics.memory_usage_mb
    freed_mb = before_mb - after_mb

    logger.info(
        "GC completed. Memory freed: %.2f MB (Before: %.2f MB, After: %.2f MB)",
        freed_mb,
        before_mb,
        after_mb,
    )


async def periodic_cache_monitoring(interval_seconds: int = 300):
    """Periodically log cache performance metrics.

    Args:
        interval_seconds: How often to log metrics (default: 5 minutes)
    """
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            _cache_monitor.log_metrics("INFO")

            # If hit rate is very low, suggest investigation
            metrics = _cache_monitor.get_metrics()
            total_requests = metrics.cache_hits + metrics.cache_misses
            if metrics.hit_rate < VERY_LOW_HIT_RATE_THRESHOLD and total_requests > MIN_REQUESTS_FOR_ANALYSIS:
                logger.warning(
                    "Low cache hit rate detected: %.2f%%. Consider investigating component code patterns.",
                    metrics.hit_rate * 100,
                )

            # If memory usage is high, suggest cleanup
            if metrics.memory_usage_mb > HIGH_MEMORY_THRESHOLD_MB:
                logger.warning(
                    "High memory usage detected: %.2f MB. Consider clearing cache or reducing cache size.",
                    metrics.memory_usage_mb,
                )

        except asyncio.CancelledError:
            logger.info("Cache monitoring stopped")
            break
        except Exception:
            logger.exception("Error in cache monitoring")


def get_cache_performance_report() -> dict:
    """Get a comprehensive cache performance report."""
    monitor = get_cache_monitor()
    metrics = monitor.get_metrics()

    return {
        "timestamp": time.time(),
        "metrics": metrics.to_dict(),
        "summary": monitor.get_summary(),
        "recommendations": _get_performance_recommendations(metrics),
    }


def _get_performance_recommendations(metrics: CacheMetrics) -> list[str]:
    """Generate performance recommendations based on metrics."""
    recommendations = []

    if metrics.hit_rate < LOW_HIT_RATE_THRESHOLD:
        recommendations.append(
            "Low hit rate suggests components are not being reused. Check if component codes are frequently changing."
        )

    if metrics.cache_size >= metrics.max_cache_size * 0.9:
        recommendations.append(
            "Cache is near capacity. Consider increasing LANGFLOW_CLASS_CACHE_SIZE environment variable."
        )

    if metrics.creation_time_avg_ms > HIGH_CREATION_TIME_THRESHOLD_MS:
        recommendations.append(
            "High average creation time suggests complex components. Caching provides significant performance benefits."
        )

    if metrics.memory_usage_mb > HIGH_MEMORY_THRESHOLD_MB:
        recommendations.append("High memory usage detected. Consider periodic cache clearing or reducing cache size.")

    if not recommendations:
        recommendations.append("Cache performance looks good!")

    return recommendations
