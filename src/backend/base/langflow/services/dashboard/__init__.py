"""
Performance Monitoring and Optimization Dashboard - Phase 4.

This package provides comprehensive performance monitoring, metrics collection,
and optimization dashboard capabilities for Genesis specification development.
"""

from .performance_dashboard import PerformanceDashboard, create_dashboard
from .metrics_collector import MetricsCollector, MetricType
from .optimization_advisor import OptimizationAdvisor, OptimizationSuggestion

__all__ = [
    "PerformanceDashboard",
    "create_dashboard",
    "MetricsCollector",
    "MetricType",
    "OptimizationAdvisor",
    "OptimizationSuggestion"
]

__version__ = "1.0.0"