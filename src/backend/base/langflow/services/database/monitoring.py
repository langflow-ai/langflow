"""Database connection pool monitoring utilities.

This module provides tools to monitor database connection pools and detect potential leaks.
It helps prevent the recurrence of 'não reutiliza as pools' issues.
"""

import asyncio
import time
from dataclasses import dataclass, field

from lfx.log.logger import logger
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass
class EngineMetrics:
    """Metrics for a single database engine."""

    engine_id: str
    created_at: float
    pool_size: int = 0
    max_overflow: int = 0
    checked_in: int = 0
    checked_out: int = 0
    overflow: int = 0
    invalid: int = 0
    total_connections: int = 0
    last_updated: float = field(default_factory=time.time)


@dataclass
class ConnectionPoolHealth:
    """Overall connection pool health metrics."""

    total_engines: int = 0
    total_connections: int = 0
    leaked_engines: int = 0
    leaked_connections: int = 0
    health_score: float = 100.0  # 0-100 score
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


class ConnectionPoolMonitor:
    """Monitor database connection pools for leaks and health issues."""

    def __init__(self):
        self.engines: dict[str, EngineMetrics] = {}
        self.disposed_engines: dict[str, float] = {}  # Track disposed engines
        self.monitoring_enabled = True

    def register_engine(self, engine: AsyncEngine, context: str = "unknown") -> str:
        """Register an engine for monitoring.

        Args:
            engine: The SQLAlchemy AsyncEngine to monitor
            context: Context where engine was created (e.g., 'reload', 'init')

        Returns:
            Engine ID for tracking
        """
        if not self.monitoring_enabled:
            return ""

        engine_id = f"{context}_{id(engine)}"

        try:
            # Extract pool information
            pool = engine.pool
            pool_size = getattr(pool, "_pool_size", 0) if hasattr(pool, "_pool_size") else 0
            max_overflow = getattr(pool, "_max_overflow", 0) if hasattr(pool, "_max_overflow") else 0

            metrics = EngineMetrics(
                engine_id=engine_id,
                created_at=time.time(),
                pool_size=pool_size,
                max_overflow=max_overflow
            )

            self.engines[engine_id] = metrics

            logger.debug(f"Registered engine {engine_id} with pool_size={pool_size}, max_overflow={max_overflow}")

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Failed to register engine {engine_id}: {e}")

        return engine_id

    def update_engine_metrics(self, engine_id: str, engine: AsyncEngine) -> None:
        """Update metrics for a registered engine.

        Args:
            engine_id: The engine ID from register_engine
            engine: The SQLAlchemy AsyncEngine
        """
        if not self.monitoring_enabled or engine_id not in self.engines:
            return

        try:
            pool = engine.pool
            metrics = self.engines[engine_id]

            # Update pool statistics
            metrics.checked_in = getattr(pool, "checkedin", lambda: 0)()
            metrics.checked_out = getattr(pool, "checkedout", lambda: 0)()
            metrics.overflow = getattr(pool, "overflow", lambda: 0)()
            metrics.invalid = getattr(pool, "invalid", lambda: 0)()
            metrics.total_connections = metrics.checked_in + metrics.checked_out
            metrics.last_updated = time.time()

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Failed to update metrics for engine {engine_id}: {e}")

    def mark_engine_disposed(self, engine_id: str) -> None:
        """Mark an engine as properly disposed.

        Args:
            engine_id: The engine ID from register_engine
        """
        if engine_id in self.engines:
            self.disposed_engines[engine_id] = time.time()
            del self.engines[engine_id]
            logger.debug(f"Engine {engine_id} marked as disposed")

    def detect_leaked_engines(self, max_age_seconds: float = 3600) -> list[str]:
        """Detect potentially leaked engines.

        Args:
            max_age_seconds: Maximum age for an engine before considering it leaked

        Returns:
            List of engine IDs that may be leaked
        """
        current_time = time.time()
        leaked_engines = []

        for engine_id, metrics in self.engines.items():
            age = current_time - metrics.created_at
            if age > max_age_seconds:
                leaked_engines.append(engine_id)

        return leaked_engines

    def get_health_report(self) -> ConnectionPoolHealth:
        """Generate a comprehensive health report.

        Returns:
            ConnectionPoolHealth with current status
        """
        health = ConnectionPoolHealth()

        # Basic metrics
        health.total_engines = len(self.engines)
        health.total_connections = sum(m.total_connections for m in self.engines.values())

        # Detect potential leaks
        leaked_engine_ids = self.detect_leaked_engines()
        health.leaked_engines = len(leaked_engine_ids)
        health.leaked_connections = sum(
            self.engines[eid].total_connections
            for eid in leaked_engine_ids
            if eid in self.engines
        )

        # Calculate health score
        if health.total_engines == 0:
            health.health_score = 100.0
        else:
            leak_ratio = health.leaked_engines / health.total_engines
            health.health_score = max(0.0, 100.0 - (leak_ratio * 100.0))

        # Generate warnings
        if health.leaked_engines > 0:
            health.warnings.append(f"{health.leaked_engines} potentially leaked engines detected")

        # Define thresholds as constants to avoid magic numbers
        high_connection_threshold = 100
        multiple_engines_threshold = 5

        if health.total_connections > high_connection_threshold:
            health.warnings.append(f"High connection count: {health.total_connections}")

        if health.total_engines > multiple_engines_threshold:
            health.warnings.append(f"Multiple active engines: {health.total_engines}")

        # Generate recommendations
        if health.leaked_engines > 0:
            health.recommendations.append("Review engine disposal in reload_engine() and teardown()")

        engine_consolidation_threshold = 3
        health_score_threshold = 80

        if health.total_engines > engine_consolidation_threshold:
            health.recommendations.append("Consider consolidating database connections")

        if health.health_score < health_score_threshold:
            health.recommendations.append("Investigate connection pool management")

        return health

    def log_health_report(self, level: str = "info") -> None:
        """Log a health report.

        Args:
            level: Log level (debug, info, warning, error)
        """
        health = self.get_health_report()

        log_func = getattr(logger, level, logger.info)

        log_func("Connection Pool Health Report:")
        log_func(f"  Engines: {health.total_engines}, Connections: {health.total_connections}")
        log_func(f"  Leaked: {health.leaked_engines} engines, {health.leaked_connections} connections")
        log_func(f"  Health Score: {health.health_score:.1f}/100")

        for warning in health.warnings:
            logger.warning(f"  ⚠️  {warning}")

        for recommendation in health.recommendations:
            logger.info(f"  💡 {recommendation}")

    def start_monitoring(self, interval_seconds: int = 300) -> None:
        """Start periodic monitoring.

        Args:
            interval_seconds: How often to log health reports
        """
        async def monitor_loop():
            while self.monitoring_enabled:
                try:
                    health = self.get_health_report()
                    warning_health_threshold = 90
                    if health.warnings or health.health_score < warning_health_threshold:
                        self.log_health_report("warning")
                    else:
                        self.log_health_report("debug")

                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error in connection pool monitoring: {e}")

                await asyncio.sleep(interval_seconds)

        # Start monitoring task and store reference
        monitoring_task = asyncio.create_task(monitor_loop())
        # Store reference to prevent garbage collection
        self._monitoring_task = monitoring_task
        logger.info(f"Started connection pool monitoring (interval: {interval_seconds}s)")

    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self.monitoring_enabled = False
        logger.info("Stopped connection pool monitoring")


# Global monitor instance
_connection_monitor: ConnectionPoolMonitor | None = None


def get_connection_monitor() -> ConnectionPoolMonitor:
    """Get the global connection pool monitor instance."""
    global _connection_monitor  # noqa: PLW0603
    if _connection_monitor is None:
        _connection_monitor = ConnectionPoolMonitor()
    return _connection_monitor


def monitor_engine(engine: AsyncEngine, context: str = "unknown") -> str:
    """Convenience function to monitor an engine.

    Args:
        engine: The SQLAlchemy AsyncEngine to monitor
        context: Context where engine was created

    Returns:
        Engine ID for tracking
    """
    return get_connection_monitor().register_engine(engine, context)


def engine_disposed(engine_id: str) -> None:
    """Convenience function to mark engine as disposed.

    Args:
        engine_id: The engine ID from monitor_engine
    """
    get_connection_monitor().mark_engine_disposed(engine_id)


def log_pool_health() -> None:
    """Convenience function to log current pool health."""
    get_connection_monitor().log_health_report()


def start_pool_monitoring(interval_seconds: int = 300) -> None:
    """Start automatic pool monitoring.

    Args:
        interval_seconds: How often to check pool health
    """
    get_connection_monitor().start_monitoring(interval_seconds)
