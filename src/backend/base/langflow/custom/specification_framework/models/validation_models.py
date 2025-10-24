"""
Validation Models for the Dynamic Agent Specification Framework.

This module defines data models for validation results, errors, warnings,
and related validation metadata with comprehensive type safety.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ValidationErrorType(Enum):
    """Types of validation errors."""
    # Structure errors
    STRUCTURE = "structure"
    MISSING_FIELD = "missing_field"
    INVALID_TYPE = "invalid_type"
    INVALID_FORMAT = "invalid_format"

    # Component errors
    MISSING_COMPONENTS = "missing_components"
    INVALID_COMPONENT_FORMAT = "invalid_component_format"
    UNSUPPORTED_COMPONENT_TYPE = "unsupported_component_type"
    MISSING_COMPONENT_FIELD = "missing_component_field"
    DUPLICATE_COMPONENT_ID = "duplicate_component_id"

    # Relationship errors
    INVALID_RELATIONSHIP_TARGET = "invalid_relationship_target"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    MISSING_USE_AS = "missing_use_as"
    MISSING_TARGET = "missing_target"

    # Workflow errors
    INVALID_WORKFLOW_FORMAT = "invalid_workflow_format"
    MISSING_WORKFLOW_FIELD = "missing_workflow_field"
    INVALID_DATA_STRUCTURE = "invalid_data_structure"
    EMPTY_WORKFLOW = "empty_workflow"

    # Node errors
    INVALID_NODE_FORMAT = "invalid_node_format"
    MISSING_NODE_FIELD = "missing_node_field"
    INVALID_NODE_ID = "invalid_node_id"
    INVALID_NODE_POSITION = "invalid_node_position"
    INVALID_NODE_DATA = "invalid_node_data"
    DUPLICATE_NODE_ID = "duplicate_node_id"

    # Edge errors
    INVALID_EDGE_FORMAT = "invalid_edge_format"
    MISSING_EDGE_FIELD = "missing_edge_field"
    INVALID_EDGE_SOURCE = "invalid_edge_source"
    INVALID_EDGE_TARGET = "invalid_edge_target"
    DUPLICATE_EDGE_ID = "duplicate_edge_id"

    # Healthcare compliance errors
    MISSING_HIPAA_COMPLIANCE = "missing_hipaa_compliance"
    MISSING_PHI_HANDLING = "missing_phi_handling"

    # General errors
    VALIDATION_FAILURE = "validation_failure"
    WORKFLOW_VALIDATION_FAILURE = "workflow_validation_failure"


class ValidationWarningType(Enum):
    """Types of validation warnings."""
    # Naming and conventions
    DEPRECATED_FIELD = "deprecated_field"
    POOR_NAMING = "poor_naming"
    NAMING_CONVENTION = "naming_convention"

    # Performance
    HIGH_COMPONENT_COUNT = "high_component_count"
    HIGH_RELATIONSHIP_COUNT = "high_relationship_count"
    HIGH_NODE_COUNT = "high_node_count"
    HIGH_EDGE_COUNT = "high_edge_count"
    HIGH_MEMORY_USAGE = "high_memory_usage"
    COMPLEX_TEMPLATES = "complex_templates"

    # Component issues
    NON_STANDARD_USE_AS = "non_standard_use_as"
    INVALID_COMPONENT_KIND = "invalid_component_kind"
    UNKNOWN_COMPONENT_TYPE = "unknown_component_type"

    # Healthcare compliance
    MISSING_AUDIT_LOGGING = "missing_audit_logging"
    PHI_DATA_FLOW = "phi_data_flow"

    # Workflow issues
    ISOLATED_COMPONENTS = "isolated_components"
    INSUFFICIENT_AGENT_GOAL = "insufficient_agent_goal"
    INVALID_VIEWPORT = "invalid_viewport"

    # Frontend compatibility
    MISSING_FRONTEND_FIELDS = "missing_frontend_fields"
    MISSING_DISPLAY_NAME = "missing_display_name"
    MISSING_INPUT_TYPES = "missing_input_types"
    INVALID_TEMPLATE_FIELD = "invalid_template_field"
    MISSING_FIELD_TYPE = "missing_field_type"

    # Langflow compatibility
    MISSING_LANGFLOW_METADATA = "missing_langflow_metadata"
    UNSUPPORTED_FORMAT_VERSION = "unsupported_format_version"
    UNSUPPORTED_COMPONENT_TYPES = "unsupported_component_types"

    # Edge issues
    INVALID_HANDLE_FORMAT = "invalid_handle_format"
    INVALID_EDGE_DATA = "invalid_edge_data"
    MALFORMED_ENCODED_HANDLE = "malformed_encoded_handle"
    INVALID_ENCODED_HANDLE = "invalid_encoded_handle"

    # Template issues
    INVALID_METADATA_FORMAT = "invalid_metadata_format"


@dataclass
class ValidationError:
    """
    Represents a validation error with detailed context.

    Attributes:
        error_type: Type of validation error
        message: Human-readable error message
        field_path: JSON path to the problematic field
        severity: Severity level of the error
        suggested_fix: Optional suggestion for fixing the error
        context: Additional context information
        timestamp: When the error was detected
    """
    error_type: Union[ValidationErrorType, str]
    message: str
    field_path: str
    severity: Union[ValidationSeverity, str] = ValidationSeverity.ERROR
    suggested_fix: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Convert string values to enums if needed."""
        if isinstance(self.error_type, str):
            try:
                self.error_type = ValidationErrorType(self.error_type)
            except ValueError:
                pass  # Keep as string if not in enum

        if isinstance(self.severity, str):
            try:
                self.severity = ValidationSeverity(self.severity)
            except ValueError:
                pass  # Keep as string if not in enum

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "error_type": self.error_type.value if isinstance(self.error_type, ValidationErrorType) else self.error_type,
            "message": self.message,
            "field_path": self.field_path,
            "severity": self.severity.value if isinstance(self.severity, ValidationSeverity) else self.severity,
            "suggested_fix": self.suggested_fix,
            "context": self.context or {},
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationError':
        """Create ValidationError from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.utcnow()

        return cls(
            error_type=data["error_type"],
            message=data["message"],
            field_path=data["field_path"],
            severity=data.get("severity", ValidationSeverity.ERROR),
            suggested_fix=data.get("suggested_fix"),
            context=data.get("context"),
            timestamp=timestamp
        )


@dataclass
class ValidationWarning:
    """
    Represents a validation warning with detailed context.

    Attributes:
        warning_type: Type of validation warning
        message: Human-readable warning message
        field_path: JSON path to the problematic field
        severity: Severity level of the warning
        suggestion: Optional suggestion for improvement
        context: Additional context information
        timestamp: When the warning was detected
    """
    warning_type: Union[ValidationWarningType, str]
    message: str
    field_path: str
    severity: Union[ValidationSeverity, str] = ValidationSeverity.WARNING
    suggestion: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Convert string values to enums if needed."""
        if isinstance(self.warning_type, str):
            try:
                self.warning_type = ValidationWarningType(self.warning_type)
            except ValueError:
                pass  # Keep as string if not in enum

        if isinstance(self.severity, str):
            try:
                self.severity = ValidationSeverity(self.severity)
            except ValueError:
                pass  # Keep as string if not in enum

    def to_dict(self) -> Dict[str, Any]:
        """Convert warning to dictionary representation."""
        return {
            "warning_type": self.warning_type.value if isinstance(self.warning_type, ValidationWarningType) else self.warning_type,
            "message": self.message,
            "field_path": self.field_path,
            "severity": self.severity.value if isinstance(self.severity, ValidationSeverity) else self.severity,
            "suggestion": self.suggestion,
            "context": self.context or {},
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationWarning':
        """Create ValidationWarning from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.utcnow()

        return cls(
            warning_type=data["warning_type"],
            message=data["message"],
            field_path=data["field_path"],
            severity=data.get("severity", ValidationSeverity.WARNING),
            suggestion=data.get("suggestion"),
            context=data.get("context"),
            timestamp=timestamp
        )


@dataclass
class ValidationResult:
    """
    Comprehensive validation result with errors, warnings, and metadata.

    Attributes:
        is_valid: Whether validation passed (no critical errors)
        validation_errors: List of validation errors
        warnings: List of validation warnings
        healthcare_compliant: HIPAA compliance status (if applicable)
        validation_time_seconds: Time taken for validation
        components_validated: Number of components validated
        relationships_validated: Number of relationships validated
        validation_metadata: Additional validation metadata
        timestamp: When validation was performed
    """
    is_valid: bool
    validation_errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    healthcare_compliant: Optional[bool] = None
    validation_time_seconds: float = 0.0
    components_validated: int = 0
    relationships_validated: int = 0
    validation_metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def error_count(self) -> int:
        """Get total number of errors."""
        return len(self.validation_errors)

    @property
    def warning_count(self) -> int:
        """Get total number of warnings."""
        return len(self.warnings)

    @property
    def critical_error_count(self) -> int:
        """Get number of critical errors."""
        return len([e for e in self.validation_errors
                   if e.severity == ValidationSeverity.CRITICAL])

    @property
    def high_priority_warning_count(self) -> int:
        """Get number of high priority warnings."""
        return len([w for w in self.warnings
                   if w.severity == ValidationSeverity.HIGH])

    @property
    def error_message(self) -> Optional[str]:
        """Get first error message, or None if no errors."""
        if self.validation_errors:
            return self.validation_errors[0].message
        return None

    def get_errors_by_type(self, error_type: Union[ValidationErrorType, str]) -> List[ValidationError]:
        """Get all errors of a specific type."""
        return [e for e in self.validation_errors if e.error_type == error_type]

    def get_warnings_by_type(self, warning_type: Union[ValidationWarningType, str]) -> List[ValidationWarning]:
        """Get all warnings of a specific type."""
        return [w for w in self.warnings if w.warning_type == warning_type]

    def get_errors_by_severity(self, severity: Union[ValidationSeverity, str]) -> List[ValidationError]:
        """Get all errors of a specific severity."""
        return [e for e in self.validation_errors if e.severity == severity]

    def get_warnings_by_severity(self, severity: Union[ValidationSeverity, str]) -> List[ValidationWarning]:
        """Get all warnings of a specific severity."""
        return [w for w in self.warnings if w.severity == severity]

    def add_error(self, error: ValidationError) -> None:
        """Add a validation error."""
        self.validation_errors.append(error)
        if error.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]:
            self.is_valid = False

    def add_warning(self, warning: ValidationWarning) -> None:
        """Add a validation warning."""
        self.warnings.append(warning)

    def merge(self, other: 'ValidationResult') -> 'ValidationResult':
        """Merge another validation result into this one."""
        merged = ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            validation_errors=self.validation_errors + other.validation_errors,
            warnings=self.warnings + other.warnings,
            healthcare_compliant=self.healthcare_compliant if self.healthcare_compliant is not None else other.healthcare_compliant,
            validation_time_seconds=self.validation_time_seconds + other.validation_time_seconds,
            components_validated=self.components_validated + other.components_validated,
            relationships_validated=self.relationships_validated + other.relationships_validated,
            validation_metadata={**self.validation_metadata, **other.validation_metadata}
        )
        return merged

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary representation."""
        return {
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "critical_error_count": self.critical_error_count,
            "high_priority_warning_count": self.high_priority_warning_count,
            "validation_errors": [error.to_dict() for error in self.validation_errors],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "healthcare_compliant": self.healthcare_compliant,
            "validation_time_seconds": self.validation_time_seconds,
            "components_validated": self.components_validated,
            "relationships_validated": self.relationships_validated,
            "validation_metadata": self.validation_metadata,
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationResult':
        """Create ValidationResult from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.utcnow()

        errors = [ValidationError.from_dict(e) for e in data.get("validation_errors", [])]
        warnings = [ValidationWarning.from_dict(w) for w in data.get("warnings", [])]

        return cls(
            is_valid=data.get("is_valid", True),
            validation_errors=errors,
            warnings=warnings,
            healthcare_compliant=data.get("healthcare_compliant"),
            validation_time_seconds=data.get("validation_time_seconds", 0.0),
            components_validated=data.get("components_validated", 0),
            relationships_validated=data.get("relationships_validated", 0),
            validation_metadata=data.get("validation_metadata", {}),
            timestamp=timestamp
        )

    @classmethod
    def create_valid(cls,
                    warnings: Optional[List[ValidationWarning]] = None,
                    healthcare_compliance: Optional[bool] = None,
                    validation_time: float = 0.0,
                    components_count: int = 0,
                    relationships_count: int = 0) -> 'ValidationResult':
        """Create a valid validation result."""
        return cls(
            is_valid=True,
            validation_errors=[],
            warnings=warnings or [],
            healthcare_compliant=healthcare_compliance,
            validation_time_seconds=validation_time,
            components_validated=components_count,
            relationships_validated=relationships_count
        )

    @classmethod
    def create_invalid(cls,
                      errors: List[ValidationError],
                      warnings: Optional[List[ValidationWarning]] = None,
                      healthcare_compliance: Optional[bool] = None,
                      validation_time: float = 0.0,
                      components_count: int = 0,
                      relationships_count: int = 0) -> 'ValidationResult':
        """Create an invalid validation result."""
        return cls(
            is_valid=False,
            validation_errors=errors,
            warnings=warnings or [],
            healthcare_compliant=healthcare_compliance,
            validation_time_seconds=validation_time,
            components_validated=components_count,
            relationships_validated=relationships_count
        )


@dataclass
class ValidationSummary:
    """
    Summary of validation results for reporting.

    Attributes:
        total_validations: Total number of validations performed
        successful_validations: Number of successful validations
        failed_validations: Number of failed validations
        total_errors: Total errors across all validations
        total_warnings: Total warnings across all validations
        average_validation_time: Average validation time
        most_common_errors: Most frequently occurring errors
        most_common_warnings: Most frequently occurring warnings
        healthcare_compliance_rate: Percentage of healthcare-compliant validations
    """
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    average_validation_time: float = 0.0
    most_common_errors: Dict[str, int] = field(default_factory=dict)
    most_common_warnings: Dict[str, int] = field(default_factory=dict)
    healthcare_compliance_rate: Optional[float] = None
    generation_timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def success_rate(self) -> float:
        """Calculate validation success rate."""
        if self.total_validations == 0:
            return 0.0
        return (self.successful_validations / self.total_validations) * 100

    def add_validation_result(self, result: ValidationResult) -> None:
        """Add a validation result to the summary."""
        self.total_validations += 1

        if result.is_valid:
            self.successful_validations += 1
        else:
            self.failed_validations += 1

        self.total_errors += result.error_count
        self.total_warnings += result.warning_count

        # Update average validation time
        total_time = (self.average_validation_time * (self.total_validations - 1)) + result.validation_time_seconds
        self.average_validation_time = total_time / self.total_validations

        # Count error types
        for error in result.validation_errors:
            error_type = error.error_type.value if isinstance(error.error_type, ValidationErrorType) else str(error.error_type)
            self.most_common_errors[error_type] = self.most_common_errors.get(error_type, 0) + 1

        # Count warning types
        for warning in result.warnings:
            warning_type = warning.warning_type.value if isinstance(warning.warning_type, ValidationWarningType) else str(warning.warning_type)
            self.most_common_warnings[warning_type] = self.most_common_warnings.get(warning_type, 0) + 1

        # Update healthcare compliance rate
        if result.healthcare_compliant is not None:
            if self.healthcare_compliance_rate is None:
                self.healthcare_compliance_rate = 100.0 if result.healthcare_compliant else 0.0
            else:
                # Recalculate average
                healthcare_validations = sum(1 for _ in range(self.total_validations) if result.healthcare_compliant is not None)
                compliant_validations = healthcare_validations if result.healthcare_compliant else healthcare_validations - 1
                self.healthcare_compliance_rate = (compliant_validations / healthcare_validations) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary representation."""
        return {
            "total_validations": self.total_validations,
            "successful_validations": self.successful_validations,
            "failed_validations": self.failed_validations,
            "success_rate": round(self.success_rate, 2),
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "average_validation_time": round(self.average_validation_time, 6),
            "most_common_errors": dict(sorted(self.most_common_errors.items(), key=lambda x: x[1], reverse=True)),
            "most_common_warnings": dict(sorted(self.most_common_warnings.items(), key=lambda x: x[1], reverse=True)),
            "healthcare_compliance_rate": round(self.healthcare_compliance_rate, 2) if self.healthcare_compliance_rate is not None else None,
            "generation_timestamp": self.generation_timestamp.isoformat()
        }