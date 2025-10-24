"""Processing context and result models."""

import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProcessingContext:
    """Context for tracking specification processing state."""

    specification: Dict[str, Any]
    variables: Dict[str, Any] = field(default_factory=dict)
    healthcare_compliance: bool = False
    performance_benchmarking: bool = False
    processing_start_time: float = field(default_factory=time.time)

    # Processing results
    spec_validation_result: Optional[Any] = None
    component_mappings: Optional[Dict[str, Any]] = None
    langflow_workflow: Optional[Dict[str, Any]] = None
    workflow_validation_result: Optional[Any] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    generator: str = "SpecificationProcessor"
    framework_version: str = "2.0.0"


@dataclass
class ProcessingResult:
    """Result of specification processing."""

    success: bool
    workflow: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    context: Optional[ProcessingContext] = None

    # Timing
    processing_time_seconds: float = 0.0

    # Validation results
    spec_validation: Optional[Any] = None
    workflow_validation: Optional[Any] = None

    # Metrics
    component_count: int = 0
    edge_count: int = 0
    automation_metrics: Optional[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    compliance_metrics: Optional[Dict[str, Any]] = None

    @classmethod
    def create_error(cls, error_message: str, context: Optional[ProcessingContext] = None) -> 'ProcessingResult':
        """Create an error result."""
        processing_time = time.time() - context.processing_start_time if context else 0.0

        return cls(
            success=False,
            error_message=error_message,
            context=context,
            processing_time_seconds=processing_time
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        result = {
            "success": self.success,
            "processing_time_seconds": self.processing_time_seconds,
            "component_count": self.component_count,
            "edge_count": self.edge_count
        }

        if self.workflow:
            result["workflow"] = self.workflow

        if self.error_message:
            result["error_message"] = self.error_message

        if self.automation_metrics:
            result["automation_metrics"] = self.automation_metrics

        if self.performance_metrics:
            result["performance_metrics"] = self.performance_metrics

        if self.compliance_metrics:
            result["compliance_metrics"] = self.compliance_metrics

        return result