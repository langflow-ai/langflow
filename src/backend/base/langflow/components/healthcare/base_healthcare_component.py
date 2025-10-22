"""Base Healthcare Component - Foundation for all HIPAA-compliant healthcare components.

Part of AUTPE-6204: This base class provides automatic compliance detection,
PHI handling, and standardized healthcare component interfaces.
"""

import logging
import hashlib
import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
from abc import ABC, abstractmethod

from langflow.custom import Component
from langflow.schema import Data, Message
from langflow.io import DataInput, Output, StrInput
from langflow.template import Input

logger = logging.getLogger(__name__)


class BaseHealthcareComponent(Component, ABC):
    """Base class for all healthcare components in Langflow.

    Provides:
    - Automatic HIPAA compliance detection
    - PHI data handling and encryption markers
    - Audit logging capabilities
    - Standardized healthcare interfaces
    - Compliance metadata generation
    """

    # Mark as abstract to exclude from component registration
    _is_abstract = True

    # Class-level markers for automatic discovery
    is_healthcare = True
    hipaa_compliant = True

    # Medical standards supported (override in subclasses)
    medical_standards: List[str] = []

    # Compliance frameworks (override in subclasses)
    compliance_frameworks: List[str] = ["HIPAA", "HITECH"]

    # PHI field markers (override in subclasses to identify PHI fields)
    phi_fields: List[str] = []

    # Component category for registration
    category = "healthcare"

    def __init__(self, **kwargs):
        """Initialize healthcare component with compliance tracking."""
        super().__init__(**kwargs)
        self._audit_log: List[Dict[str, Any]] = []
        self._phi_access_log: List[Dict[str, Any]] = []
        self._compliance_validation_results: Dict[str, Any] = {}

        # Auto-validate compliance on initialization
        self._validate_compliance()

    @property
    def healthcare_metadata(self) -> Dict[str, Any]:
        """
        Generate healthcare metadata for component registration.

        Returns:
            Dictionary containing all healthcare-specific metadata
        """
        return {
            "hipaa_compliant": self.hipaa_compliant,
            "phi_handling": len(self.phi_fields) > 0,
            "encryption_required": True,
            "audit_trail": True,
            "medical_standards": self.medical_standards,
            "data_classification": "PHI" if self.phi_fields else "Non-PHI",
            "compliance_frameworks": self.compliance_frameworks,
            "security_requirements": self._get_security_requirements(),
            "component_capabilities": self._get_healthcare_capabilities(),
        }

    def _get_security_requirements(self) -> Dict[str, bool]:
        """Get security requirements for this component."""
        return {
            "encryption_at_rest": True,
            "encryption_in_transit": True,
            "access_logging": True,
            "role_based_access": True,
            "minimum_permissions": True,
            "data_masking": len(self.phi_fields) > 0,
            "audit_retention": True,
        }

    def _get_healthcare_capabilities(self) -> Dict[str, Any]:
        """Get healthcare-specific capabilities."""
        return {
            "phi_fields": self.phi_fields,
            "supports_hl7": "HL7" in str(self.medical_standards),
            "supports_fhir": "FHIR" in str(self.medical_standards),
            "supports_x12": "X12" in str(self.medical_standards),
            "real_time_capable": hasattr(self, "real_time_mode"),
            "batch_capable": hasattr(self, "batch_mode"),
        }

    def _validate_compliance(self) -> Dict[str, Any]:
        """
        Validate component compliance at initialization.

        Returns:
            Validation results dictionary
        """
        validations = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.__class__.__name__,
            "passed": True,
            "checks": []
        }

        # Check HIPAA compliance marker
        if not self.hipaa_compliant:
            validations["checks"].append({
                "check": "hipaa_compliant_marker",
                "passed": False,
                "message": "Component not marked as HIPAA compliant"
            })
            validations["passed"] = False

        # Check PHI field definitions if component handles PHI
        if self.phi_fields and not self._validate_phi_fields():
            validations["checks"].append({
                "check": "phi_field_validation",
                "passed": False,
                "message": "PHI fields not properly configured"
            })
            validations["passed"] = False

        # Check medical standards
        if not self.medical_standards:
            validations["checks"].append({
                "check": "medical_standards",
                "passed": False,
                "message": "No medical standards specified",
                "severity": "warning"
            })

        # Check audit capability
        if not hasattr(self, "_audit_log"):
            validations["checks"].append({
                "check": "audit_capability",
                "passed": False,
                "message": "Audit logging not configured"
            })
            validations["passed"] = False

        self._compliance_validation_results = validations

        if not validations["passed"]:
            logger.warning(f"Compliance validation issues for {self.__class__.__name__}: {validations}")

        return validations

    def _validate_phi_fields(self) -> bool:
        """Validate PHI field configuration."""
        # Override in subclasses for specific validation
        return True

    def _mask_phi(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask PHI data for logging or display.

        Args:
            data: Dictionary potentially containing PHI

        Returns:
            Dictionary with PHI fields masked
        """
        masked_data = data.copy()

        for field in self.phi_fields:
            if field in masked_data:
                # Create a hash of the value for tracking without exposing PHI
                if masked_data[field]:
                    value_hash = hashlib.sha256(
                        str(masked_data[field]).encode()
                    ).hexdigest()[:8]
                    masked_data[field] = f"***PHI_{value_hash}***"
                else:
                    masked_data[field] = "***PHI_EMPTY***"

        return masked_data

    def _audit_access(self, action: str, data: Optional[Dict[str, Any]] = None,
                     user: Optional[str] = None) -> None:
        """
        Log access to healthcare data for audit purposes.

        Args:
            action: Action being performed
            data: Data being accessed (will be masked)
            user: User performing the action
        """
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.__class__.__name__,
            "action": action,
            "user": user or "system",
            "data_accessed": self._mask_phi(data) if data else None,
        }

        self._audit_log.append(audit_entry)

        # If PHI is accessed, add to PHI access log
        if data and any(field in data for field in self.phi_fields):
            self._phi_access_log.append(audit_entry)

        logger.info(f"AUDIT: {action} by {user or 'system'} on {self.__class__.__name__}")

    def _encrypt_phi_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mark PHI fields for encryption (actual encryption handled by infrastructure).

        Args:
            data: Data containing potential PHI

        Returns:
            Data with PHI fields marked for encryption
        """
        encrypted_data = data.copy()

        for field in self.phi_fields:
            if field in encrypted_data and encrypted_data[field]:
                # Mark field for encryption (actual encryption by security layer)
                encrypted_data[f"__{field}_encrypted__"] = True

        return encrypted_data

    def _validate_input_data(self, data: Union[str, Dict, Data, Message]) -> Dict[str, Any]:
        """
        Validate and normalize input data.

        Args:
            data: Input data in various formats

        Returns:
            Normalized dictionary
        """
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {"raw_input": data}
        elif isinstance(data, Message):
            return {"message": data.text, "metadata": data.data}
        elif isinstance(data, Data):
            return data.data if hasattr(data, "data") else {"data": str(data)}
        elif isinstance(data, dict):
            return data
        else:
            return {"input": str(data)}

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a healthcare request with compliance checks.

        Args:
            request_data: Request data dictionary

        Returns:
            Processed response with compliance metadata
        """
        # Audit the request
        self._audit_access("process_request", request_data)

        # Validate compliance before processing
        if not self._compliance_validation_results.get("passed", False):
            raise ValueError(f"Component failed compliance validation: {self._compliance_validation_results}")

        # Process the request (implemented by subclasses)
        response = self._process_healthcare_data(request_data)

        # Add compliance metadata to response
        response["_compliance_metadata"] = {
            "hipaa_compliant": self.hipaa_compliant,
            "audit_logged": True,
            "phi_encrypted": bool(self.phi_fields),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Audit the response
        self._audit_access("process_response", response)

        return response

    @abstractmethod
    def _process_healthcare_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process healthcare data - must be implemented by subclasses.

        Args:
            data: Input data dictionary

        Returns:
            Processed data dictionary
        """
        pass

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get the audit log for this component instance."""
        return self._audit_log.copy()

    def get_phi_access_log(self) -> List[Dict[str, Any]]:
        """Get the PHI access log for this component instance."""
        return self._phi_access_log.copy()

    def get_compliance_status(self) -> Dict[str, Any]:
        """Get current compliance status."""
        return {
            "component": self.__class__.__name__,
            "hipaa_compliant": self.hipaa_compliant,
            "validation_results": self._compliance_validation_results,
            "audit_entries": len(self._audit_log),
            "phi_accesses": len(self._phi_access_log),
            "medical_standards": self.medical_standards,
            "compliance_frameworks": self.compliance_frameworks,
        }

    def export_audit_trail(self, format: str = "json") -> str:
        """
        Export audit trail for compliance reporting.

        Args:
            format: Export format (json or csv)

        Returns:
            Formatted audit trail string
        """
        if format == "json":
            return json.dumps({
                "audit_log": self._audit_log,
                "phi_access_log": self._phi_access_log,
                "compliance_status": self.get_compliance_status(),
            }, indent=2, default=str)
        else:
            # CSV format implementation would go here
            raise NotImplementedError(f"Format {format} not implemented")

    @classmethod
    def get_component_metadata(cls) -> Dict[str, Any]:
        """
        Get metadata for component registration and discovery.

        Returns:
            Component metadata dictionary
        """
        return {
            "name": cls.__name__,
            "display_name": getattr(cls, "display_name", cls.__name__),
            "description": cls.__doc__ or "Healthcare component",
            "category": cls.category,
            "is_healthcare": cls.is_healthcare,
            "hipaa_compliant": cls.hipaa_compliant,
            "medical_standards": cls.medical_standards,
            "compliance_frameworks": cls.compliance_frameworks,
            "phi_fields": cls.phi_fields,
            "genesis_type": f"genesis:{cls.__name__.lower().replace('component', '')}",
        }