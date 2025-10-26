from typing import Any, Dict, List, Optional, Union
import json
import re
import logging
from datetime import datetime
from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.inputs import (
    BoolInput,
    DictInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    MultiselectInput,
    StrInput,
)
from langflow.io import Output
from langflow.schema import Data


logger = logging.getLogger(__name__)


class MedicalDataStandardizerConnector(HealthcareConnectorBase):
    display_name = "Medical Data Standardizer Connector"
    description = "HIPAA-compliant medical data standardization and validation for healthcare workflows"
    icon = "database"
    name = "MedicalDataStandardizerConnector"
    category = "connectors"

    def __init__(self, **kwargs):
        """Initialize MedicalDataStandardizerConnector with healthcare base inputs and standardizer-specific inputs."""
        super().__init__(**kwargs)

        # Add standardizer-specific inputs to the base class inputs
        standardizer_inputs = [
        DictInput(
            name="raw_data",
            display_name="Raw Medical Data",
            required=True,
            info="Raw extracted medical data to be standardized",
        ),
        MultiselectInput(
            name="standardization_rules",
            display_name="Standardization Rules",
            options=[
                "icd10_validation",
                "cpt_validation",
                "npi_validation",
                "date_normalization",
                "name_standardization",
                "address_standardization",
                "phone_normalization",
                "terminology_mapping",
                "units_conversion",
            ],
            value=["icd10_validation", "cpt_validation", "npi_validation", "date_normalization"],
            required=True,
        ),
        MultiselectInput(
            name="output_formats",
            display_name="Output Formats",
            options=[
                "fhir_r4",
                "hl7_v2",
                "x12_edi",
                "json_schema",
                "csv_export",
                "xml_export",
            ],
            value=["json_schema"],
            required=True,
        ),
        BoolInput(
            name="enable_phi_anonymization",
            display_name="Enable PHI Anonymization",
            value=False,
            info="Anonymize Protected Health Information in output",
        ),
        BoolInput(
            name="strict_validation",
            display_name="Strict Validation",
            value=True,
            info="Enforce strict validation rules for medical codes and formats",
        ),
        FloatInput(
            name="confidence_threshold",
            display_name="Confidence Threshold",
            value=0.8,
            range_spec={"min": 0.0, "max": 1.0, "step": 0.1},
            info="Minimum confidence for automated standardization",
        ),
        BoolInput(
            name="enable_terminology_lookup",
            display_name="Enable Terminology Lookup",
            value=True,
            info="Look up and validate medical terminology against standard vocabularies",
        ),
        BoolInput(
            name="hipaa_compliance_mode",
            display_name="HIPAA Compliance Mode",
            value=True,
            info="Enable HIPAA compliance features including audit logging",
        ),
        BoolInput(
            name="mock_mode",
            display_name="Mock Mode",
            value=False,
            info="Use mock standardization for testing without real validation",
        ),
        ]

        # Combine base class inputs with standardizer-specific inputs
        self.inputs = self.inputs + standardizer_inputs

    outputs = [
        Output(display_name="Standardized Data", name="standardized_data", method="standardize_data"),
        Output(display_name="Validation Report", name="validation_report", method="get_validation_report"),
        Output(display_name="Audit Log", name="audit_log", method="get_audit_log"),
    ]

    def standardize_data(self) -> Data:
        """Standardize medical data according to healthcare standards."""
        try:
            # Prepare request data
            request_data = {
                "operation": "standardize_data",
                "raw_data": getattr(self, 'raw_data', {}),
                "standardization_rules": getattr(self, 'standardization_rules', []),
                "output_formats": getattr(self, 'output_formats', []),
                "enable_phi_anonymization": getattr(self, 'enable_phi_anonymization', False),
                "strict_validation": getattr(self, 'strict_validation', True),
                "confidence_threshold": getattr(self, 'confidence_threshold', 0.8),
                "enable_terminology_lookup": getattr(self, 'enable_terminology_lookup', True),
                "hipaa_compliance_mode": getattr(self, 'hipaa_compliance_mode', True),
            }

            return self.execute_healthcare_workflow(request_data)

        except Exception as e:
            return self._handle_healthcare_error(e, "standardize_data")

    def get_validation_report(self) -> Data:
        """Generate detailed validation report."""
        try:
            request_data = {"operation": "get_validation_report"}
            return self.execute_healthcare_workflow(request_data)
        except Exception as e:
            return self._handle_healthcare_error(e, "get_validation_report")

    def get_audit_log(self) -> Data:
        """Return HIPAA compliance audit log."""
        try:
            request_data = {"operation": "get_audit_log"}
            return self.execute_healthcare_workflow(request_data)
        except Exception as e:
            return self._handle_healthcare_error(e, "get_audit_log")

    def get_required_fields(self) -> List[str]:
        """Get required fields for medical data standardization operations."""
        return ["operation"]

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Provide comprehensive mock medical data standardization for development."""
        operation = request_data.get("operation", "standardize_data")

        if operation == "get_audit_log":
            return {
                "audit_entries": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "action": "data_standardization",
                        "rules_applied": ["icd10_validation", "cpt_validation", "npi_validation"],
                        "phi_detected": ["patient_name", "dob"],
                        "user_id": "system",
                        "compliance_status": "LOGGED",
                    }
                ],
                "compliance_status": "ACTIVE",
                "last_activity": datetime.now().isoformat(),
            }

        elif operation == "get_validation_report":
            return {
                "validation_summary": {
                    "total_fields_processed": 25,
                    "successful_validations": 22,
                    "failed_validations": 3,
                    "confidence_average": 0.89,
                },
                "rule_performance": {
                    "icd10_validation": {"success_rate": 0.95, "avg_confidence": 0.92},
                    "cpt_validation": {"success_rate": 0.88, "avg_confidence": 0.85},
                    "npi_validation": {"success_rate": 1.0, "avg_confidence": 0.98},
                    "date_normalization": {"success_rate": 0.92, "avg_confidence": 0.87}
                },
                "common_errors": [
                    "Invalid ICD-10 code format",
                    "Missing procedure code",
                    "Date format inconsistency"
                ],
                "recommendations": [
                    "Improve data quality at source",
                    "Implement additional validation rules",
                    "Use terminology services for better mapping"
                ]
            }

        # Mock data standardization response
        raw_data = request_data.get("raw_data", {})
        standardization_rules = request_data.get("standardization_rules", [])

        return {
            "original_data": raw_data,
            "standardized_data": {
                "patient_info": {
                    "name": "John Doe",
                    "date_of_birth": "1960-01-15",  # Standardized format
                    "gender": "M",  # Standardized code
                    "phone": "+1-555-0123"  # Standardized format
                },
                "provider_info": {
                    "npi": "1234567890",  # Validated NPI
                    "name": "Jane Smith MD",
                    "specialty_code": "207RC0000X"  # Standardized taxonomy
                },
                "clinical_data": {
                    "diagnosis_codes": [
                        {"code": "E11.9", "system": "ICD-10-CM", "display": "Type 2 diabetes mellitus without complications"}
                    ],
                    "procedure_codes": [
                        {"code": "99213", "system": "CPT", "display": "Office visit, established patient, level 3"}
                    ]
                }
            },
            "validation_errors": [
                {
                    "field": "insurance_id",
                    "error": "Invalid format",
                    "severity": "warning"
                }
            ],
            "confidence_scores": {
                "patient_info": 0.95,
                "provider_info": 0.92,
                "clinical_data": 0.88,
                "overall": 0.92
            },
            "applied_rules": standardization_rules,
            "formatted_outputs": {
                "json_schema": {"status": "formatted"},
                "fhir_r4": {"resourceType": "Bundle", "entry": []}
            },
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "standardizer_version": "1.0.0",
                "compliance_mode": request_data.get("hipaa_compliance_mode", True),
                "phi_anonymized": request_data.get("enable_phi_anonymization", False),
                "mock_mode": True
            }
        }

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process real medical data standardization requests (production implementation).

        In production, this would:
        1. Connect to medical terminology services (UMLS, SNOMED, etc.)
        2. Perform real-time code validation
        3. Apply sophisticated NLP for data extraction
        4. Generate FHIR-compliant outputs
        5. Implement comprehensive audit logging
        """
        # For now, return mock data with production note
        mock_response = self.get_mock_response(request_data)
        mock_response["production_note"] = "Configure terminology services and validation APIs for live standardization"
        return mock_response

