"""
Standardized Logging Configuration for the Dynamic Agent Specification Framework.

This module provides comprehensive logging configuration with structured logging,
performance monitoring, and production-ready patterns for all framework services.
"""

import logging
import logging.config
import sys
import time
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from functools import wraps
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class LogContext:
    """Context information for structured logging."""
    service_name: str
    operation: str
    component_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class StructuredFormatter(logging.Formatter):
    """Structured JSON formatter for production logging."""

    def __init__(self, include_trace: bool = False):
        """Initialize formatter."""
        super().__init__()
        self.include_trace = include_trace

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Base log structure
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Add process/thread information
        log_entry.update({
            'process_id': record.process,
            'thread_id': record.thread,
            'thread_name': record.threadName
        })

        # Add context information if available
        if hasattr(record, 'context'):
            log_entry['context'] = record.context

        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)

        # Add exception information
        if record.exc_info and self.include_trace:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info) if record.exc_info else None
            }
        elif record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None
            }

        # Add stack information for errors
        if record.levelno >= logging.ERROR and hasattr(record, 'stack_info') and record.stack_info:
            log_entry['stack_trace'] = record.stack_info

        return json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'))


class PerformanceFormatter(logging.Formatter):
    """Formatter optimized for performance monitoring."""

    def format(self, record: logging.LogRecord) -> str:
        """Format performance-related log entries."""
        if hasattr(record, 'performance_data'):
            perf_data = record.performance_data
            return (
                f"{datetime.fromtimestamp(record.created, timezone.utc).isoformat()} "
                f"[{record.levelname}] {record.name}: {record.getMessage()} "
                f"| Duration: {perf_data.get('duration', 'N/A')}s "
                f"| Memory: {perf_data.get('memory_mb', 'N/A')}MB "
                f"| Success: {perf_data.get('success', 'N/A')}"
            )
        return super().format(record)


class FrameworkLogger:
    """Centralized logger for the specification framework."""

    def __init__(self, service_name: str, context: Optional[LogContext] = None):
        """
        Initialize framework logger.

        Args:
            service_name: Name of the service
            context: Optional logging context
        """
        self.service_name = service_name
        self.context = context or LogContext(service_name=service_name, operation="")
        self.logger = logging.getLogger(f"specification_framework.{service_name}")

    def with_context(self, **kwargs) -> "FrameworkLogger":
        """Create a new logger with additional context."""
        new_context = LogContext(
            service_name=self.service_name,
            operation=kwargs.get('operation', self.context.operation),
            component_id=kwargs.get('component_id', self.context.component_id),
            user_id=kwargs.get('user_id', self.context.user_id),
            session_id=kwargs.get('session_id', self.context.session_id),
            request_id=kwargs.get('request_id', self.context.request_id),
            additional_data={**(self.context.additional_data or {}), **kwargs.get('additional_data', {})}
        )
        return FrameworkLogger(self.service_name, new_context)

    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        self._log(logging.CRITICAL, message, **kwargs)

    def performance(self, message: str, duration: float, **kwargs):
        """Log performance metrics."""
        performance_data = {
            'duration': round(duration, 6),
            'timestamp': time.time(),
            **kwargs
        }
        self._log(logging.INFO, f"PERFORMANCE: {message}",
                 performance_data=performance_data, **kwargs)

    def security(self, message: str, **kwargs):
        """Log security-related events."""
        security_data = {
            'event_type': 'security',
            'timestamp': time.time(),
            **kwargs
        }
        self._log(logging.WARNING, f"SECURITY: {message}",
                 security_data=security_data, **kwargs)

    def healthcare_compliance(self, message: str, **kwargs):
        """Log healthcare compliance events."""
        compliance_data = {
            'event_type': 'healthcare_compliance',
            'timestamp': time.time(),
            **kwargs
        }
        self._log(logging.INFO, f"COMPLIANCE: {message}",
                 compliance_data=compliance_data, **kwargs)

    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method."""
        extra = {
            'context': self.context.to_dict(),
            'extra_data': kwargs
        }
        self.logger.log(level, message, extra=extra)


def setup_framework_logging(
    log_level: str = "INFO",
    log_format: str = "structured",
    log_file: Optional[str] = None,
    enable_performance_logging: bool = True,
    enable_security_logging: bool = True,
    enable_healthcare_logging: bool = True
) -> None:
    """
    Setup standardized logging configuration for the framework.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type (structured, simple, performance)
        log_file: Optional log file path
        enable_performance_logging: Enable performance monitoring logs
        enable_security_logging: Enable security event logs
        enable_healthcare_logging: Enable healthcare compliance logs
    """
    # Convert log level string to constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    # Select formatter
    if log_format == "structured":
        formatter = StructuredFormatter(include_trace=log_level.upper() == "DEBUG")
    elif log_format == "performance":
        formatter = PerformanceFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Configure specific loggers
    framework_logger = logging.getLogger("specification_framework")
    framework_logger.setLevel(numeric_level)

    # Performance logger
    if enable_performance_logging:
        perf_logger = logging.getLogger("specification_framework.performance")
        perf_handler = logging.StreamHandler(sys.stdout)
        perf_handler.setFormatter(PerformanceFormatter())
        perf_logger.addHandler(perf_handler)
        perf_logger.setLevel(logging.INFO)

    # Security logger
    if enable_security_logging:
        security_logger = logging.getLogger("specification_framework.security")
        security_logger.setLevel(logging.WARNING)

    # Healthcare compliance logger
    if enable_healthcare_logging:
        healthcare_logger = logging.getLogger("specification_framework.healthcare")
        healthcare_logger.setLevel(logging.INFO)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.info("Framework logging configured successfully")


def log_performance(operation_name: str):
    """
    Decorator for automatic performance logging.

    Args:
        operation_name: Name of the operation being logged
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = FrameworkLogger("performance")
            start_time = time.time()
            success = True
            error = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration = time.time() - start_time
                logger.performance(
                    f"{operation_name} completed",
                    duration=duration,
                    success=success,
                    error=error,
                    function_name=func.__name__
                )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = FrameworkLogger("performance")
            start_time = time.time()
            success = True
            error = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration = time.time() - start_time
                logger.performance(
                    f"{operation_name} completed",
                    duration=duration,
                    success=success,
                    error=error,
                    function_name=func.__name__
                )

        # Return appropriate wrapper based on function type
        if hasattr(func, '__code__') and 'await' in func.__code__.co_names:
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def log_security_event(event_type: str, details: Dict[str, Any]):
    """
    Log security-related events.

    Args:
        event_type: Type of security event
        details: Event details
    """
    logger = FrameworkLogger("security")
    logger.security(
        f"Security event: {event_type}",
        event_type=event_type,
        details=details
    )


def log_healthcare_event(event_type: str, compliance_data: Dict[str, Any]):
    """
    Log healthcare compliance events.

    Args:
        event_type: Type of compliance event
        compliance_data: Compliance-related data
    """
    logger = FrameworkLogger("healthcare")
    logger.healthcare_compliance(
        f"Healthcare compliance event: {event_type}",
        event_type=event_type,
        compliance_data=compliance_data
    )


class LoggingMiddleware:
    """Middleware for automatic request/response logging."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = FrameworkLogger(service_name)

    async def log_request(self, operation: str, params: Dict[str, Any]):
        """Log incoming request."""
        self.logger.info(
            f"Request started: {operation}",
            operation=operation,
            params=self._sanitize_params(params)
        )

    async def log_response(self, operation: str, duration: float,
                          success: bool, result_summary: Dict[str, Any]):
        """Log operation response."""
        if success:
            self.logger.info(
                f"Request completed: {operation}",
                operation=operation,
                duration=duration,
                result_summary=result_summary
            )
        else:
            self.logger.error(
                f"Request failed: {operation}",
                operation=operation,
                duration=duration,
                result_summary=result_summary
            )

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize parameters for logging (remove sensitive data)."""
        sensitive_keys = {
            'password', 'api_key', 'secret', 'token', 'auth', 'credentials',
            'ssn', 'patient_id', 'medical_record', 'phi_data'
        }

        sanitized = {}
        for key, value in params.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = f"***LARGE_DATA:{len(value)}chars***"
            elif isinstance(value, (dict, list)) and len(str(value)) > 1000:
                sanitized[key] = f"***LARGE_OBJECT:{type(value).__name__}***"
            else:
                sanitized[key] = value

        return sanitized


# Convenience function to get a framework logger
def get_framework_logger(service_name: str, context: Optional[Dict[str, Any]] = None) -> FrameworkLogger:
    """
    Get a framework logger instance.

    Args:
        service_name: Name of the service
        context: Optional context data

    Returns:
        FrameworkLogger instance
    """
    log_context = None
    if context:
        log_context = LogContext(
            service_name=service_name,
            operation=context.get('operation', ''),
            component_id=context.get('component_id'),
            user_id=context.get('user_id'),
            session_id=context.get('session_id'),
            request_id=context.get('request_id'),
            additional_data=context.get('additional_data')
        )

    return FrameworkLogger(service_name, log_context)


# Default logging configuration
DEFAULT_LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'structured': {
            '()': StructuredFormatter,
            'include_trace': False
        },
        'performance': {
            '()': PerformanceFormatter
        },
        'simple': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'structured',
            'stream': 'ext://sys.stdout'
        }
    },
    'loggers': {
        'specification_framework': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False
        }
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['console']
    }
}