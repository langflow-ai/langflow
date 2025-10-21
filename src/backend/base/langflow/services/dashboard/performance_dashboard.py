"""
Performance Monitoring and Optimization Dashboard - Phase 4.

Provides comprehensive performance monitoring, real-time metrics visualization,
and optimization recommendations for Genesis specification development.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

import yaml
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.layout import Layout
from rich.align import Align
from rich.tree import Tree

from langflow.services.spec.service import SpecService
from langflow.services.runtime import RuntimeType, converter_factory
from langflow.services.runtime.performance_optimizer import PerformanceOptimizer

logger = logging.getLogger(__name__)
console = Console()


class MetricType(Enum):
    """Types of performance metrics."""
    VALIDATION_TIME = "validation_time"
    CONVERSION_TIME = "conversion_time"
    COMPONENT_COUNT = "component_count"
    ERROR_COUNT = "error_count"
    WARNING_COUNT = "warning_count"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    THROUGHPUT = "throughput"


@dataclass
class PerformanceMetric:
    """Individual performance metric."""
    metric_type: MetricType
    value: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class DashboardConfig:
    """Configuration for performance dashboard."""
    refresh_interval: float = 1.0
    max_metrics_history: int = 1000
    auto_optimize: bool = True
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "validation_time": 5.0,
        "conversion_time": 10.0,
        "error_count": 5,
        "memory_usage": 1024  # MB
    })
    enable_real_time: bool = True
    save_history: bool = True


class PerformanceDashboard:
    """
    Comprehensive performance monitoring and optimization dashboard.

    Provides real-time monitoring, metrics visualization, and optimization
    recommendations for Genesis specification development.
    """

    def __init__(self, config: Optional[DashboardConfig] = None):
        """
        Initialize performance dashboard.

        Args:
            config: Dashboard configuration
        """
        self.config = config or DashboardConfig()
        self.spec_service = SpecService()
        self.performance_optimizer = PerformanceOptimizer()

        # Metrics storage
        self.metrics_history: Dict[MetricType, List[PerformanceMetric]] = {
            metric_type: [] for metric_type in MetricType
        }
        self.current_metrics: Dict[MetricType, PerformanceMetric] = {}
        self.alerts: List[Dict[str, Any]] = []

        # Dashboard state
        self.is_running = False
        self.start_time = datetime.now(timezone.utc)
        self.session_stats = {
            "specs_processed": 0,
            "total_validation_time": 0.0,
            "total_conversion_time": 0.0,
            "total_errors": 0,
            "total_warnings": 0
        }

        # Callbacks
        self.metric_callbacks: List[Callable[[PerformanceMetric], None]] = []
        self.alert_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    async def start_monitoring(self) -> None:
        """Start real-time performance monitoring."""
        if self.is_running:
            return

        self.is_running = True
        self.start_time = datetime.now(timezone.utc)

        logger.info("Starting performance monitoring dashboard")

        if self.config.enable_real_time:
            # Start real-time monitoring task
            asyncio.create_task(self._real_time_monitoring())

    async def stop_monitoring(self) -> None:
        """Stop performance monitoring."""
        self.is_running = False

        if self.config.save_history:
            await self._save_metrics_history()

        logger.info("Stopped performance monitoring dashboard")

    async def monitor_specification_processing(
        self,
        spec_path: str,
        target_runtime: RuntimeType = RuntimeType.LANGFLOW,
        include_optimization: bool = True
    ) -> Dict[str, Any]:
        """
        Monitor specification processing with comprehensive metrics.

        Args:
            spec_path: Path to specification file
            target_runtime: Target runtime for conversion
            include_optimization: Whether to include optimization analysis

        Returns:
            Processing results with performance metrics
        """
        try:
            processing_start = time.time()

            # Load specification
            spec_content = self._load_specification(spec_path)
            if not spec_content:
                return {"success": False, "error": "Failed to load specification"}

            spec_dict = yaml.safe_load(spec_content)

            # Monitor validation
            validation_start = time.time()
            validation_result = await self.spec_service.validate_spec(spec_content, detailed=True)
            validation_time = time.time() - validation_start

            # Record validation metrics
            await self._record_metric(MetricType.VALIDATION_TIME, validation_time,
                                    {"spec_path": spec_path, "runtime": target_runtime.value})

            error_count = len(validation_result.get("errors", []))
            warning_count = len(validation_result.get("warnings", []))

            await self._record_metric(MetricType.ERROR_COUNT, error_count,
                                    {"spec_path": spec_path})
            await self._record_metric(MetricType.WARNING_COUNT, warning_count,
                                    {"spec_path": spec_path})

            # Monitor conversion if validation passes
            conversion_result = None
            conversion_time = 0.0

            if validation_result.get("valid", False):
                conversion_start = time.time()
                conversion_result = await self.spec_service.convert_spec_to_flow_enhanced(
                    spec_content, target_runtime=target_runtime
                )
                conversion_time = time.time() - conversion_start

                await self._record_metric(MetricType.CONVERSION_TIME, conversion_time,
                                        {"spec_path": spec_path, "runtime": target_runtime.value})

            # Monitor component complexity
            component_count = len(spec_dict.get("components", {}))
            await self._record_metric(MetricType.COMPONENT_COUNT, component_count,
                                    {"spec_path": spec_path})

            # Optimization analysis
            optimization_suggestions = []
            if include_optimization and conversion_result:
                optimization_suggestions = await self._analyze_optimization_opportunities(
                    spec_dict, conversion_result
                )

            # Update session statistics
            self.session_stats["specs_processed"] += 1
            self.session_stats["total_validation_time"] += validation_time
            self.session_stats["total_conversion_time"] += conversion_time
            self.session_stats["total_errors"] += error_count
            self.session_stats["total_warnings"] += warning_count

            total_time = time.time() - processing_start

            return {
                "success": True,
                "spec_path": spec_path,
                "target_runtime": target_runtime.value,
                "performance_metrics": {
                    "total_processing_time": total_time,
                    "validation_time": validation_time,
                    "conversion_time": conversion_time,
                    "component_count": component_count,
                    "error_count": error_count,
                    "warning_count": warning_count
                },
                "validation_result": validation_result,
                "conversion_result": conversion_result,
                "optimization_suggestions": optimization_suggestions,
                "alerts": self._check_performance_alerts({
                    "validation_time": validation_time,
                    "conversion_time": conversion_time,
                    "error_count": error_count
                })
            }

        except Exception as e:
            logger.error(f"Error monitoring specification processing: {e}")
            return {"success": False, "error": str(e)}

    async def get_dashboard_view(self, live_update: bool = False) -> Union[str, Layout]:
        """
        Get comprehensive dashboard view.

        Args:
            live_update: Whether to return live updating layout

        Returns:
            Dashboard content (string or Layout for live updates)
        """
        if live_update:
            return await self._create_live_dashboard()
        else:
            return await self._create_static_dashboard()

    async def get_performance_summary(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """
        Get performance summary for specified time window.

        Args:
            time_window: Time window for metrics (last hour if None)

        Returns:
            Performance summary
        """
        if time_window is None:
            time_window = timedelta(hours=1)

        cutoff_time = datetime.now(timezone.utc) - time_window

        summary = {
            "time_window": str(time_window),
            "session_stats": self.session_stats.copy(),
            "metric_summaries": {},
            "trends": {},
            "alerts": self._get_recent_alerts(time_window),
            "top_issues": await self._identify_top_issues(time_window)
        }

        # Calculate metric summaries
        for metric_type, metrics in self.metrics_history.items():
            recent_metrics = [m for m in metrics if m.timestamp >= cutoff_time]

            if recent_metrics:
                values = [m.value for m in recent_metrics]
                summary["metric_summaries"][metric_type.value] = {
                    "count": len(values),
                    "average": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "latest": values[-1]
                }

                # Calculate trend
                if len(values) >= 2:
                    first_half = values[:len(values)//2]
                    second_half = values[len(values)//2:]
                    first_avg = sum(first_half) / len(first_half)
                    second_avg = sum(second_half) / len(second_half)
                    trend = "improving" if second_avg < first_avg else "degrading"
                    summary["trends"][metric_type.value] = trend

        return summary

    async def export_metrics(self, output_path: str, format: str = "json") -> bool:
        """
        Export metrics data to file.

        Args:
            output_path: Output file path
            format: Export format ("json", "csv", "yaml")

        Returns:
            True if export successful
        """
        try:
            export_data = {
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "session_stats": self.session_stats,
                "metrics_history": {},
                "alerts": self.alerts
            }

            # Convert metrics to serializable format
            for metric_type, metrics in self.metrics_history.items():
                export_data["metrics_history"][metric_type.value] = [
                    {
                        "value": m.value,
                        "timestamp": m.timestamp.isoformat(),
                        "context": m.context,
                        "tags": m.tags
                    }
                    for m in metrics
                ]

            output_file = Path(output_path)

            if format.lower() == "json":
                with open(output_file, 'w') as f:
                    json.dump(export_data, f, indent=2)
            elif format.lower() == "yaml":
                with open(output_file, 'w') as f:
                    yaml.dump(export_data, f, default_flow_style=False)
            elif format.lower() == "csv":
                # CSV export for metrics
                import csv
                with open(output_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["metric_type", "value", "timestamp", "context"])

                    for metric_type, metrics in self.metrics_history.items():
                        for metric in metrics:
                            writer.writerow([
                                metric_type.value,
                                metric.value,
                                metric.timestamp.isoformat(),
                                json.dumps(metric.context)
                            ])

            logger.info(f"Exported metrics to {output_path} in {format} format")
            return True

        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            return False

    def add_metric_callback(self, callback: Callable[[PerformanceMetric], None]) -> None:
        """Add callback for new metrics."""
        self.metric_callbacks.append(callback)

    def add_alert_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add callback for alerts."""
        self.alert_callbacks.append(callback)

    # Private methods

    async def _record_metric(
        self,
        metric_type: MetricType,
        value: float,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record performance metric."""
        metric = PerformanceMetric(
            metric_type=metric_type,
            value=value,
            timestamp=datetime.now(timezone.utc),
            context=context or {},
            tags=tags or {}
        )

        # Store metric
        self.metrics_history[metric_type].append(metric)
        self.current_metrics[metric_type] = metric

        # Trim history if too long
        if len(self.metrics_history[metric_type]) > self.config.max_metrics_history:
            self.metrics_history[metric_type] = self.metrics_history[metric_type][-self.config.max_metrics_history:]

        # Check for alerts
        await self._check_metric_alert(metric)

        # Call callbacks
        for callback in self.metric_callbacks:
            try:
                callback(metric)
            except Exception as e:
                logger.warning(f"Error in metric callback: {e}")

    async def _check_metric_alert(self, metric: PerformanceMetric) -> None:
        """Check if metric triggers an alert."""
        threshold_key = metric.metric_type.value
        if threshold_key in self.config.alert_thresholds:
            threshold = self.config.alert_thresholds[threshold_key]

            if metric.value > threshold:
                alert = {
                    "timestamp": metric.timestamp.isoformat(),
                    "metric_type": metric.metric_type.value,
                    "value": metric.value,
                    "threshold": threshold,
                    "severity": "warning" if metric.value < threshold * 1.5 else "critical",
                    "message": f"{metric.metric_type.value} ({metric.value:.2f}) exceeded threshold ({threshold})",
                    "context": metric.context
                }

                self.alerts.append(alert)

                # Call alert callbacks
                for callback in self.alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        logger.warning(f"Error in alert callback: {e}")

    def _check_performance_alerts(self, metrics: Dict[str, float]) -> List[Dict[str, Any]]:
        """Check multiple metrics for alert conditions."""
        alerts = []

        for metric_name, value in metrics.items():
            if metric_name in self.config.alert_thresholds:
                threshold = self.config.alert_thresholds[metric_name]
                if value > threshold:
                    alerts.append({
                        "metric": metric_name,
                        "value": value,
                        "threshold": threshold,
                        "severity": "warning" if value < threshold * 1.5 else "critical"
                    })

        return alerts

    def _get_recent_alerts(self, time_window: timedelta) -> List[Dict[str, Any]]:
        """Get alerts within time window."""
        cutoff_time = datetime.now(timezone.utc) - time_window
        return [
            alert for alert in self.alerts
            if datetime.fromisoformat(alert["timestamp"].replace('Z', '+00:00')) >= cutoff_time
        ]

    async def _identify_top_issues(self, time_window: timedelta) -> List[Dict[str, Any]]:
        """Identify top performance issues in time window."""
        cutoff_time = datetime.now(timezone.utc) - time_window
        issues = []

        # Check for consistently high validation times
        validation_metrics = [
            m for m in self.metrics_history[MetricType.VALIDATION_TIME]
            if m.timestamp >= cutoff_time
        ]

        if validation_metrics:
            avg_validation_time = sum(m.value for m in validation_metrics) / len(validation_metrics)
            if avg_validation_time > 3.0:
                issues.append({
                    "type": "high_validation_time",
                    "severity": "medium",
                    "message": f"Average validation time ({avg_validation_time:.2f}s) is high",
                    "suggestion": "Consider optimizing specification structure or reducing component complexity"
                })

        # Check for high error rates
        error_metrics = [
            m for m in self.metrics_history[MetricType.ERROR_COUNT]
            if m.timestamp >= cutoff_time
        ]

        if error_metrics:
            total_errors = sum(m.value for m in error_metrics)
            if total_errors > 10:
                issues.append({
                    "type": "high_error_rate",
                    "severity": "high",
                    "message": f"High error count ({total_errors}) detected",
                    "suggestion": "Review specification syntax and component configurations"
                })

        return issues

    async def _analyze_optimization_opportunities(
        self,
        spec_dict: Dict[str, Any],
        conversion_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze optimization opportunities."""
        suggestions = []

        components = spec_dict.get("components", {})
        component_count = len(components)

        # Component complexity analysis
        if component_count > 8:
            suggestions.append({
                "type": "component_reduction",
                "priority": "medium",
                "message": f"Specification has {component_count} components",
                "suggestion": "Consider breaking into smaller, focused workflows",
                "impact": "Improved maintainability and performance"
            })

        # Connection complexity analysis
        total_connections = sum(len(comp.get("provides", [])) for comp in components.values())
        if total_connections > 15:
            suggestions.append({
                "type": "connection_optimization",
                "priority": "medium",
                "message": f"Complex connection pattern with {total_connections} connections",
                "suggestion": "Review component relationships and simplify data flow",
                "impact": "Reduced conversion time and better reliability"
            })

        # Agent optimization
        agent_count = sum(1 for comp in components.values()
                         if "agent" in comp.get("type", "").lower())
        if agent_count > 5:
            suggestions.append({
                "type": "agent_optimization",
                "priority": "high",
                "message": f"High agent count ({agent_count}) detected",
                "suggestion": "Consider using hierarchical CrewAI patterns",
                "impact": "Better coordination and reduced overhead"
            })

        return suggestions

    async def _real_time_monitoring(self) -> None:
        """Real-time monitoring task."""
        while self.is_running:
            try:
                # Update system metrics
                await self._update_system_metrics()

                # Sleep until next update
                await asyncio.sleep(self.config.refresh_interval)

            except Exception as e:
                logger.error(f"Error in real-time monitoring: {e}")
                await asyncio.sleep(1.0)

    async def _update_system_metrics(self) -> None:
        """Update system performance metrics."""
        try:
            import psutil

            # Memory usage
            memory_info = psutil.virtual_memory()
            await self._record_metric(
                MetricType.MEMORY_USAGE,
                memory_info.used / (1024 * 1024),  # MB
                {"total_mb": memory_info.total / (1024 * 1024)}
            )

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            await self._record_metric(
                MetricType.CPU_USAGE,
                cpu_percent,
                {"cpu_count": psutil.cpu_count()}
            )

        except ImportError:
            # psutil not available, skip system metrics
            pass
        except Exception as e:
            logger.debug(f"Error updating system metrics: {e}")

    async def _create_live_dashboard(self) -> Layout:
        """Create live updating dashboard layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )

        layout["main"].split_row(
            Layout(name="metrics"),
            Layout(name="alerts")
        )

        # Update header
        uptime = datetime.now(timezone.utc) - self.start_time
        header_table = Table.grid()
        header_table.add_column()
        header_table.add_row(
            Panel.fit(
                f"[bold blue]Genesis Performance Dashboard[/bold blue]\n"
                f"Uptime: {str(uptime).split('.')[0]} | "
                f"Specs Processed: {self.session_stats['specs_processed']} | "
                f"Status: {'🟢 Active' if self.is_running else '🔴 Stopped'}",
                title="System Status"
            )
        )
        layout["header"].update(header_table)

        # Update metrics
        metrics_table = self._create_metrics_table()
        layout["metrics"].update(Panel(metrics_table, title="Performance Metrics"))

        # Update alerts
        alerts_content = self._create_alerts_content()
        layout["alerts"].update(Panel(alerts_content, title="Alerts & Issues"))

        # Update footer
        footer_table = Table.grid()
        footer_table.add_column()
        footer_table.add_row(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
        layout["footer"].update(footer_table)

        return layout

    async def _create_static_dashboard(self) -> str:
        """Create static dashboard view."""
        lines = []

        # Header
        uptime = datetime.now(timezone.utc) - self.start_time
        lines.append("=" * 80)
        lines.append("GENESIS PERFORMANCE DASHBOARD")
        lines.append("=" * 80)
        lines.append(f"Uptime: {str(uptime).split('.')[0]}")
        lines.append(f"Specifications Processed: {self.session_stats['specs_processed']}")
        lines.append(f"Status: {'Active' if self.is_running else 'Stopped'}")
        lines.append("")

        # Session statistics
        lines.append("SESSION STATISTICS:")
        lines.append("-" * 40)
        lines.append(f"Total Validation Time: {self.session_stats['total_validation_time']:.2f}s")
        lines.append(f"Total Conversion Time: {self.session_stats['total_conversion_time']:.2f}s")
        lines.append(f"Total Errors: {self.session_stats['total_errors']}")
        lines.append(f"Total Warnings: {self.session_stats['total_warnings']}")
        lines.append("")

        # Current metrics
        lines.append("CURRENT METRICS:")
        lines.append("-" * 40)
        for metric_type, metric in self.current_metrics.items():
            lines.append(f"{metric_type.value}: {metric.value:.2f}")
        lines.append("")

        # Recent alerts
        recent_alerts = self._get_recent_alerts(timedelta(minutes=30))
        if recent_alerts:
            lines.append("RECENT ALERTS:")
            lines.append("-" * 40)
            for alert in recent_alerts[-5:]:  # Last 5 alerts
                lines.append(f"[{alert['severity'].upper()}] {alert['message']}")
        lines.append("")

        return "\n".join(lines)

    def _create_metrics_table(self) -> Table:
        """Create metrics table for display."""
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Metric", style="cyan")
        table.add_column("Current", style="green")
        table.add_column("Average", style="yellow")
        table.add_column("Trend", style="magenta")

        for metric_type in MetricType:
            metrics = self.metrics_history[metric_type]
            if metrics:
                current = metrics[-1].value
                average = sum(m.value for m in metrics[-10:]) / min(len(metrics), 10)

                # Simple trend calculation
                if len(metrics) >= 2:
                    recent_avg = sum(m.value for m in metrics[-5:]) / min(len(metrics), 5)
                    older_avg = sum(m.value for m in metrics[-10:-5]) / max(min(len(metrics) - 5, 5), 1)
                    trend = "↗️" if recent_avg > older_avg else "↘️"
                else:
                    trend = "→"

                table.add_row(
                    metric_type.value.replace("_", " ").title(),
                    f"{current:.2f}",
                    f"{average:.2f}",
                    trend
                )

        return table

    def _create_alerts_content(self) -> str:
        """Create alerts content for display."""
        recent_alerts = self._get_recent_alerts(timedelta(hours=1))

        if not recent_alerts:
            return "No recent alerts 🟢"

        lines = []
        for alert in recent_alerts[-5:]:  # Last 5 alerts
            severity_icon = "🔴" if alert["severity"] == "critical" else "🟡"
            lines.append(f"{severity_icon} {alert['message']}")

        return "\n".join(lines)

    def _load_specification(self, spec_path: str) -> Optional[str]:
        """Load specification content from file."""
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading specification: {e}")
            return None

    async def _save_metrics_history(self) -> None:
        """Save metrics history to file."""
        try:
            history_file = Path("metrics_history.json")
            await self.export_metrics(str(history_file), "json")
            logger.info(f"Saved metrics history to {history_file}")
        except Exception as e:
            logger.error(f"Error saving metrics history: {e}")


def create_dashboard(config: Optional[DashboardConfig] = None) -> PerformanceDashboard:
    """
    Create performance dashboard instance.

    Args:
        config: Dashboard configuration

    Returns:
        Performance dashboard instance
    """
    return PerformanceDashboard(config)


if __name__ == "__main__":
    async def main():
        """Example usage of performance dashboard."""
        # Create dashboard
        dashboard = create_dashboard(DashboardConfig(
            refresh_interval=2.0,
            enable_real_time=True
        ))

        # Start monitoring
        await dashboard.start_monitoring()

        # Monitor a specification
        result = await dashboard.monitor_specification_processing(
            "example.genesis.yaml",
            RuntimeType.LANGFLOW,
            include_optimization=True
        )

        console.print("Processing Results:")
        console.print(json.dumps(result, indent=2, default=str))

        # Get performance summary
        summary = await dashboard.get_performance_summary()
        console.print("\nPerformance Summary:")
        console.print(json.dumps(summary, indent=2, default=str))

        # Stop monitoring
        await dashboard.stop_monitoring()

    # Run example
    asyncio.run(main())