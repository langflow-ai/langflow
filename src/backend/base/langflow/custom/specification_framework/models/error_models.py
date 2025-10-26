"""
Standardized Error Models for the Dynamic Agent Specification Framework.

This module provides comprehensive error handling models with consistent
error response formats, error recovery strategies, and detailed error context.
"""

import logging
import traceback
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    VALIDATION = "validation"
    CONVERSION = "conversion"
    CONNECTION = "connection"
    CONFIGURATION = "configuration"
    HEALTHCARE_COMPLIANCE = "healthcare_compliance"
    PERFORMANCE = "performance"
    SYSTEM = "system"
    NETWORK = "network"
    DATA = "data"


@dataclass
class ErrorContext:
    """Context information for errors."""
    timestamp: str
    service_name: str
    operation: str
    component_id: Optional[str] = None
    field_path: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

    @classmethod
    def create(cls,
               service_name: str,
               operation: str,
               component_id: Optional[str] = None,
               field_path: Optional[str] = None,
               **kwargs) -> "ErrorContext":
        """Create error context with current timestamp."""
        return cls(
            timestamp=datetime.utcnow().isoformat(),
            service_name=service_name,
            operation=operation,
            component_id=component_id,
            field_path=field_path,
            additional_data=kwargs if kwargs else None
        )


@dataclass
class FrameworkError:
    """Standardized error model for the framework."""
    error_id: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    context: ErrorContext
    exception_type: Optional[str] = None
    stack_trace: Optional[str] = None
    suggested_fix: Optional[str] = None
    retry_possible: bool = False
    user_friendly_message: Optional[str] = None

    @classmethod
    def create(cls,
               error_id: str,
               message: str,
               category: ErrorCategory,
               severity: ErrorSeverity,
               context: ErrorContext,
               exception: Optional[Exception] = None,
               suggested_fix: Optional[str] = None,
               retry_possible: bool = False,
               user_friendly_message: Optional[str] = None) -> "FrameworkError":
        """Create a framework error with optional exception details."""
        exception_type = None
        stack_trace = None

        if exception:
            exception_type = type(exception).__name__
            stack_trace = traceback.format_exc()

        return cls(
            error_id=error_id,
            message=message,
            category=category,
            severity=severity,
            context=context,
            exception_type=exception_type,
            stack_trace=stack_trace,
            suggested_fix=suggested_fix,
            retry_possible=retry_possible,
            user_friendly_message=user_friendly_message or message
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format."""
        return asdict(self)

    def to_log_dict(self) -> Dict[str, Any]:
        """Convert error to structured log format."""
        return {
            "error_id": self.error_id,
            "error_message": self.message,  # Changed from 'message' to avoid LogRecord conflict
            "category": self.category.value,
            "severity": self.severity.value,
            "service": self.context.service_name,
            "operation": self.context.operation,
            "component_id": self.context.component_id,
            "field_path": self.context.field_path,
            "exception_type": self.exception_type,
            "retry_possible": self.retry_possible
        }


@dataclass
class ErrorResult:
    """Result object that includes errors and warnings."""
    success: bool
    data: Optional[Any] = None
    errors: List[FrameworkError] = None
    warnings: List[FrameworkError] = None
    execution_time_seconds: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize empty lists if None."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

    @classmethod
    def success_result(cls, data: Any, execution_time: Optional[float] = None, **metadata) -> "ErrorResult":
        """Create a successful result."""
        return cls(
            success=True,
            data=data,
            execution_time_seconds=execution_time,
            metadata=metadata if metadata else None
        )

    @classmethod
    def error_result(cls,
                     errors: List[FrameworkError],
                     warnings: Optional[List[FrameworkError]] = None,
                     execution_time: Optional[float] = None) -> "ErrorResult":
        """Create an error result."""
        return cls(
            success=False,
            errors=errors,
            warnings=warnings or [],
            execution_time_seconds=execution_time
        )

    def add_error(self, error: FrameworkError) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: FrameworkError) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)

    def has_critical_errors(self) -> bool:
        """Check if result has critical errors."""
        return any(error.severity == ErrorSeverity.CRITICAL for error in self.errors)

    def has_high_severity_issues(self) -> bool:
        """Check if result has high severity errors or warnings."""
        all_issues = self.errors + self.warnings
        return any(issue.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] for issue in all_issues)

    def get_user_friendly_message(self) -> str:
        """Get a user-friendly error message."""
        if self.success:
            return "Operation completed successfully"

        if self.has_critical_errors():
            critical_errors = [e for e in self.errors if e.severity == ErrorSeverity.CRITICAL]
            return f"Critical error: {critical_errors[0].user_friendly_message}"

        if self.errors:
            return f"Operation failed: {self.errors[0].user_friendly_message}"

        return "Operation completed with warnings"

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        return {
            "success": self.success,
            "data": self.data,
            "errors": [error.to_dict() for error in self.errors],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "execution_time_seconds": self.execution_time_seconds,
            "metadata": self.metadata,
            "user_friendly_message": self.get_user_friendly_message()
        }


class ErrorHandler:
    """Centralized error handler for the framework."""

    def __init__(self, service_name: str):
        """Initialize error handler for a specific service."""
        self.service_name = service_name
        self.logger = logging.getLogger(f"{__name__}.{service_name}")

    def handle_exception(self,
                        operation: str,
                        exception: Exception,
                        error_id: str,
                        category: ErrorCategory,
                        severity: ErrorSeverity = ErrorSeverity.HIGH,
                        component_id: Optional[str] = None,
                        field_path: Optional[str] = None,
                        suggested_fix: Optional[str] = None,
                        retry_possible: bool = False,
                        **context_data) -> FrameworkError:
        """Handle an exception and convert it to a FrameworkError."""

        context = ErrorContext.create(
            service_name=self.service_name,
            operation=operation,
            component_id=component_id,
            field_path=field_path,
            **context_data
        )

        error = FrameworkError.create(
            error_id=error_id,
            message=str(exception),
            category=category,
            severity=severity,
            context=context,
            exception=exception,
            suggested_fix=suggested_fix,
            retry_possible=retry_possible
        )

        # Log the error with structured data
        self.logger.error(
            "Exception occurred in %s.%s: %s",
            self.service_name,
            operation,
            str(exception),
            extra=error.to_log_dict(),
            exc_info=True
        )

        return error

    def create_error(self,
                    operation: str,
                    error_id: str,
                    message: str,
                    category: ErrorCategory,
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    component_id: Optional[str] = None,
                    field_path: Optional[str] = None,
                    suggested_fix: Optional[str] = None,
                    retry_possible: bool = False,
                    user_friendly_message: Optional[str] = None,
                    **context_data) -> FrameworkError:
        """Create a framework error without an exception."""

        context = ErrorContext.create(
            service_name=self.service_name,
            operation=operation,
            component_id=component_id,
            field_path=field_path,
            **context_data
        )

        error = FrameworkError.create(
            error_id=error_id,
            message=message,
            category=category,
            severity=severity,
            context=context,
            suggested_fix=suggested_fix,
            retry_possible=retry_possible,
            user_friendly_message=user_friendly_message
        )

        # Log the error
        self.logger.error(
            "Error in %s.%s: %s",
            self.service_name,
            operation,
            message,
            extra=error.to_log_dict()
        )

        return error

    def create_warning(self,
                      operation: str,
                      warning_id: str,
                      message: str,
                      category: ErrorCategory,
                      severity: ErrorSeverity = ErrorSeverity.LOW,
                      component_id: Optional[str] = None,
                      field_path: Optional[str] = None,
                      suggested_fix: Optional[str] = None,
                      **context_data) -> FrameworkError:
        """Create a framework warning."""

        context = ErrorContext.create(
            service_name=self.service_name,
            operation=operation,
            component_id=component_id,
            field_path=field_path,
            **context_data
        )

        warning = FrameworkError.create(
            error_id=warning_id,
            message=message,
            category=category,
            severity=severity,
            context=context,
            suggested_fix=suggested_fix,
            retry_possible=False
        )

        # Log the warning
        self.logger.warning(
            "Warning in %s.%s: %s",
            self.service_name,
            operation,
            message,
            extra=warning.to_log_dict()
        )

        return warning


# Decorator for automatic error handling
def handle_errors(operation_name: str,
                 category: ErrorCategory,
                 severity: ErrorSeverity = ErrorSeverity.HIGH,
                 retry_possible: bool = False):
    """Decorator for automatic error handling in framework methods."""

    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # Get service name from class
            service_name = getattr(self, '_service_name', self.__class__.__name__)
            error_handler = ErrorHandler(service_name)

            try:
                result = func(self, *args, **kwargs)
                return result
            except Exception as e:
                error = error_handler.handle_exception(
                    operation=operation_name,
                    exception=e,
                    error_id=f"{service_name.lower()}_{operation_name}_error",
                    category=category,
                    severity=severity,
                    retry_possible=retry_possible
                )

                # Return ErrorResult for consistent error handling
                return ErrorResult.error_result([error])

        return wrapper
    return decorator


# Common error IDs for consistency
class CommonErrorIds:
    """Common error identifiers used across the framework."""

    # Connection Builder Errors
    CONNECTION_UUID_GENERATION_FAILED = "connection_uuid_generation_failed"
    CONNECTION_JSON_FORMATTING_FAILED = "connection_json_formatting_failed"
    CONNECTION_HANDLE_CREATION_FAILED = "connection_handle_creation_failed"
    CONNECTION_INVALID_COMPONENT_TYPE = "connection_invalid_component_type"

    # Variable Resolver Errors
    VARIABLE_TYPE_VALIDATION_FAILED = "variable_type_validation_failed"
    VARIABLE_RESOLUTION_FAILED = "variable_resolution_failed"
    VARIABLE_CIRCULAR_DEPENDENCY = "variable_circular_dependency"
    VARIABLE_TEMPLATE_PARSING_FAILED = "variable_template_parsing_failed"

    # Healthcare Compliance Errors
    HEALTHCARE_COMPLIANCE_CHECK_FAILED = "healthcare_compliance_check_failed"
    HEALTHCARE_PHI_VALIDATION_FAILED = "healthcare_phi_validation_failed"
    HEALTHCARE_AUDIT_CONFIG_MISSING = "healthcare_audit_config_missing"

    # Performance Errors
    PERFORMANCE_MEMORY_ESTIMATION_FAILED = "performance_memory_estimation_failed"
    PERFORMANCE_CACHE_OPERATION_FAILED = "performance_cache_operation_failed"
    PERFORMANCE_PARALLEL_PROCESSING_FAILED = "performance_parallel_processing_failed"

    # System Errors
    SYSTEM_DATABASE_CONNECTION_FAILED = "system_database_connection_failed"
    SYSTEM_CONFIGURATION_INVALID = "system_configuration_invalid"
    SYSTEM_RESOURCE_UNAVAILABLE = "system_resource_unavailable"