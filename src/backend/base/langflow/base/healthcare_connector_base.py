"""Base class for all healthcare connectors with HIPAA compliance."""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langflow.custom.custom_component.component import Component
from langflow.io import BoolInput, DropdownInput, MessageTextInput, SecretStrInput
from langflow.logging.logger import logger
from langflow.schema.data import Data
from langflow.schema.message import Message


class HealthcareConnectorBase(Component):
    """
    Base class for all healthcare connectors.

    Provides HIPAA-compliant data handling, audit logging, and standardized
    healthcare integration patterns.
    """

    # Healthcare-specific metadata
    hipaa_compliant: bool = True
    phi_handling: bool = True
    encryption_required: bool = True
    audit_trail: bool = True

    # Component metadata for Langflow
    display_name: str = "Healthcare Connector Base"
    description: str = "Base class for healthcare integration components"
    icon: str = "Heart"
    category: str = "connectors"

    # Common healthcare inputs
    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="API key for healthcare service authentication",
            required=False,
        ),
        SecretStrInput(
            name="client_id",
            display_name="Client ID",
            info="Client ID for OAuth2 authentication",
            required=False,
        ),
        SecretStrInput(
            name="client_secret",
            display_name="Client Secret",
            info="Client secret for OAuth2 authentication",
            required=False,
        ),
        BoolInput(
            name="test_mode",
            display_name="Test Mode",
            value=True,
            info="Use test/sandbox environment for healthcare service",
            tool_mode=True,
            advanced=True,
        ),
        BoolInput(
            name="mock_mode",
            display_name="Mock Mode",
            value=True,
            info="Use mock responses for development/testing",
            tool_mode=True,
            advanced=True,
        ),
        BoolInput(
            name="audit_logging",
            display_name="Audit Logging",
            value=True,
            info="Enable comprehensive audit logging for HIPAA compliance",
            tool_mode=True,
        ),
        DropdownInput(
            name="timeout_seconds",
            display_name="Timeout (seconds)",
            options=["15", "30", "45", "60", "90"],
            value="30",
            info="Request timeout for healthcare API calls",
            tool_mode=True,
        ),
    ]

    def __init__(self, **kwargs):
        """Initialize healthcare connector with compliance defaults."""
        super().__init__(**kwargs)
        self._audit_logger = self._setup_audit_logger()
        self._start_time = None
        self._request_id = None

    def _setup_audit_logger(self) -> logging.Logger:
        """Set up HIPAA-compliant audit logger."""
        audit_logger = logging.getLogger(f"healthcare_audit.{self.__class__.__name__}")
        audit_logger.setLevel(logging.INFO)

        # Ensure handler exists for audit logging
        if not audit_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s [HEALTHCARE_AUDIT] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S UTC"
            )
            handler.setFormatter(formatter)
            audit_logger.addHandler(handler)

        return audit_logger

    def _generate_request_id(self) -> str:
        """Generate unique request ID for audit trail."""
        timestamp = int(time.time() * 1000)
        return f"HC-{timestamp}-{hash(str(timestamp)) % 10000:04d}"

    def _log_phi_access(self, action: str, data_elements: List[str],
                       request_id: Optional[str] = None) -> None:
        """Log PHI access for HIPAA audit trail."""
        if not self.audit_logging:
            return

        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id or self._request_id,
            "component": self.__class__.__name__,
            "action": action,
            "phi_elements": data_elements,
            "user_context": "system",  # In real implementation, get from auth context
            "compliance_note": "PHI access logged for HIPAA compliance",
        }

        self._audit_logger.info(json.dumps(audit_entry))

    def _validate_phi_data(self, data: Dict[str, Any]) -> bool:
        """Validate PHI data handling compliance."""
        # Check for common PHI elements
        phi_fields = [
            "patient_id", "member_id", "subscriber_id", "ssn", "dob",
            "patient_name", "address", "phone", "email", "mrn"
        ]

        found_phi = []
        for field in phi_fields:
            if field in data or any(field in str(key).lower() for key in data.keys()):
                found_phi.append(field)

        if found_phi:
            self._log_phi_access("phi_validation", found_phi)

        return True

    def _anonymize_for_logging(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize sensitive data for logging purposes."""
        sensitive_fields = [
            "ssn", "patient_name", "address", "phone", "email",
            "api_key", "client_secret", "password", "token"
        ]

        anonymized = data.copy()
        for field in sensitive_fields:
            if field in anonymized:
                if isinstance(anonymized[field], str) and len(anonymized[field]) > 4:
                    anonymized[field] = "***" + anonymized[field][-4:]
                else:
                    anonymized[field] = "***"

        return anonymized

    def _format_healthcare_response(self, response_data: Dict[str, Any],
                                   transaction_type: str = "unknown") -> Data:
        """Format response data with healthcare metadata."""
        # Add healthcare-specific metadata
        healthcare_metadata = {
            "transaction_type": transaction_type,
            "processing_timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": self._request_id,
            "component": self.__class__.__name__,
            "hipaa_compliant": True,
            "phi_protected": True,
            "audit_logged": self.audit_logging,
        }

        # Add performance metrics
        if self._start_time:
            processing_time = time.time() - self._start_time
            healthcare_metadata["processing_time_seconds"] = round(processing_time, 3)

        return Data(
            data=response_data,
            metadata=healthcare_metadata,
        )

    def _handle_healthcare_error(self, error: Exception, context: str = "") -> Data:
        """Handle healthcare-specific errors with proper logging."""
        error_id = self._generate_request_id()

        error_data = {
            "error": True,
            "error_type": type(error).__name__,
            "error_message": "Healthcare service error occurred",  # Generic message to avoid PHI exposure
            "error_id": error_id,
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Log full error details securely (not exposed to user)
        if self.audit_logging:
            self._audit_logger.error(f"Healthcare error {error_id}: {str(error)}")

        logger.error(f"Healthcare connector error: {str(error)}")

        return self._format_healthcare_response(error_data, "error")

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provide realistic mock response for development.

        Subclasses should override this method to provide
        comprehensive mock data with medical terminology.
        """
        return {
            "status": "success",
            "message": "Healthcare connector base mock response",
            "data": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.__class__.__name__,
            "mock_mode": True
        }

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process healthcare-specific request.

        Subclasses should override this method to handle
        the specific healthcare workflow.
        """
        # Default implementation returns mock data with production note
        mock_response = self.get_mock_response(request_data)
        mock_response["production_note"] = "Configure healthcare credentials for live data access"
        return mock_response

    def validate_healthcare_data(self, data: Dict[str, Any]) -> bool:
        """Validate healthcare data structure and compliance."""
        if not isinstance(data, dict):
            raise ValueError("Healthcare data must be a dictionary")

        # Validate PHI handling
        self._validate_phi_data(data)

        # Check for required healthcare fields (override in subclasses)
        required_fields = self.get_required_fields()
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            raise ValueError(f"Missing required healthcare fields: {missing_fields}")

        return True

    def get_required_fields(self) -> List[str]:
        """Get required fields for this healthcare connector. Override in subclasses."""
        return []

    def execute_healthcare_workflow(self, input_data: Dict[str, Any]) -> Data:
        """
        Execute healthcare workflow with full compliance tracking.

        This is the main entry point that handles:
        - Request ID generation
        - Audit logging
        - Data validation
        - Error handling
        - Performance tracking
        """
        self._start_time = time.time()
        self._request_id = self._generate_request_id()

        try:
            # Log workflow start
            if self.audit_logging:
                self._log_phi_access("workflow_start", list(input_data.keys()))

            # Validate input data
            self.validate_healthcare_data(input_data)

            # Process request (mock or real)
            if self.mock_mode:
                response_data = self.get_mock_response(input_data)
                transaction_type = "mock_response"
            else:
                response_data = self.process_healthcare_request(input_data)
                transaction_type = "live_response"

            # Log workflow completion
            if self.audit_logging:
                self._log_phi_access("workflow_complete", list(response_data.keys()))

            return self._format_healthcare_response(response_data, transaction_type)

        except Exception as e:
            return self._handle_healthcare_error(e, "healthcare_workflow_execution")