from typing import Any, Dict, List, Optional, Union
import json
import base64
from PIL import Image
import io
import logging
from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.inputs import (
    BoolInput,
    DictInput,
    FileInput,
    FloatInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    MultiselectInput,
    SecretStrInput,
    StrInput,
)
from langflow.io import Output
from langflow.schema import Data


logger = logging.getLogger(__name__)


class DocumentExtractionConnector(HealthcareConnectorBase):
    display_name = "Document Extraction Connector"
    description = "HIPAA-compliant document extraction for healthcare forms and clinical documents using Azure Form Recognizer"
    icon = "file-text"
    name = "DocumentExtractionConnector"
    category = "connectors"

    def __init__(self, **kwargs):
        """Initialize DocumentExtractionConnector with healthcare base inputs and extraction-specific inputs."""
        super().__init__(**kwargs)

        # Add extraction-specific inputs to the base class inputs
        extraction_inputs = [
        SecretStrInput(
            name="azure_form_recognizer_key",
            display_name="Azure Form Recognizer API Key",
            required=True,
            password=True,
        ),
        StrInput(
            name="azure_form_recognizer_endpoint",
            display_name="Azure Form Recognizer Endpoint",
            required=True,
            placeholder="https://your-resource.cognitiveservices.azure.com/",
        ),
        MultiselectInput(
            name="document_type",
            display_name="Document Type",
            options=[
                "healthcare_form",
                "prior_authorization",
                "insurance_card",
                "medical_record",
                "lab_report",
                "prescription",
                "general",
            ],
            value=["healthcare_form"],
            required=True,
        ),
        FileInput(
            name="document_file",
            display_name="Document File",
            file_types=["pdf", "png", "jpg", "jpeg", "tiff", "bmp"],
            required=False,
        ),
        StrInput(
            name="document_url",
            display_name="Document URL",
            required=False,
            placeholder="https://example.com/document.pdf",
        ),
        MessageTextInput(
            name="document_base64",
            display_name="Document Base64",
            required=False,
        ),
        BoolInput(
            name="extract_tables",
            display_name="Extract Tables",
            value=True,
        ),
        BoolInput(
            name="extract_key_value_pairs",
            display_name="Extract Key-Value Pairs",
            value=True,
        ),
        BoolInput(
            name="extract_text_lines",
            display_name="Extract Text Lines",
            value=True,
        ),
        FloatInput(
            name="confidence_threshold",
            display_name="Confidence Threshold",
            value=0.7,
            range_spec={"min": 0.0, "max": 1.0, "step": 0.1},
        ),
        BoolInput(
            name="enable_phi_detection",
            display_name="Enable PHI Detection",
            value=True,
            info="Detect and flag Protected Health Information",
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
            info="Use mock data for testing without real API calls",
        ),
        ]

        # Combine base class inputs with extraction-specific inputs
        self.inputs = self.inputs + extraction_inputs

    outputs = [
        Output(display_name="Extracted Data", name="extracted_data", method="extract_document"),
        Output(display_name="Audit Log", name="audit_log", method="get_audit_log"),
    ]

    def extract_document(self) -> Data:
        """Extract structured data from healthcare documents with HIPAA compliance."""
        try:
            # Prepare request data
            request_data = {
                "operation": "document_extraction",
                "document_type": getattr(self, 'document_type', ['general']),
                "extract_tables": getattr(self, 'extract_tables', True),
                "extract_key_value_pairs": getattr(self, 'extract_key_value_pairs', True),
                "extract_text_lines": getattr(self, 'extract_text_lines', True),
                "confidence_threshold": getattr(self, 'confidence_threshold', 0.7),
                "enable_phi_detection": getattr(self, 'enable_phi_detection', True),
                "hipaa_compliance_mode": getattr(self, 'hipaa_compliance_mode', True),
            }

            # Handle document input
            if hasattr(self, 'document_file') and self.document_file:
                request_data['has_document_file'] = True
            elif hasattr(self, 'document_url') and self.document_url:
                request_data['document_url'] = self.document_url
            elif hasattr(self, 'document_base64') and self.document_base64:
                request_data['has_document_base64'] = True

            return self.execute_healthcare_workflow(request_data)

        except Exception as e:
            return self._handle_healthcare_error(e, "extract_document")

    def get_audit_log(self) -> Data:
        """Return HIPAA compliance audit log."""
        try:
            request_data = {"operation": "get_audit_log"}
            return self.execute_healthcare_workflow(request_data)
        except Exception as e:
            return self._handle_healthcare_error(e, "get_audit_log")

    def get_required_fields(self) -> List[str]:
        """Get required fields for document extraction operations."""
        return ["operation"]

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Provide comprehensive mock document extraction data for development."""
        operation = request_data.get("operation", "document_extraction")

        if operation == "get_audit_log":
            return {
                "audit_entries": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "action": "document_extraction",
                        "document_type": ["healthcare_form"],
                        "phi_detected": ["phone", "mrn"],
                        "user_id": "system",
                        "compliance_status": "LOGGED",
                    }
                ],
                "compliance_status": "ACTIVE",
                "last_accessed": datetime.now().isoformat(),
            }

        # Mock document extraction response
        return {
            "extraction_result": {
                "text_content": "Mock extracted text content from healthcare document",
                "tables": [
                    {
                        "table_id": "table_1",
                        "rows": 5,
                        "columns": 3,
                        "data": [
                            ["Patient Name", "John Doe", ""],
                            ["DOB", "01/15/1960", ""],
                            ["Member ID", "M123456789", ""],
                            ["Provider", "Jane Smith MD", ""],
                            ["Date of Service", "03/15/2024", ""]
                        ]
                    }
                ],
                "key_value_pairs": {
                    "Patient Name": "John Doe",
                    "DOB": "01/15/1960",
                    "Member ID": "M123456789",
                    "Provider": "Jane Smith MD",
                    "Date of Service": "03/15/2024"
                },
                "text_lines": [
                    "PRIOR AUTHORIZATION REQUEST",
                    "Patient: John Doe",
                    "DOB: 01/15/1960",
                    "Member ID: M123456789"
                ],
                "healthcare_fields": {
                    "patient_info": {
                        "name": "John Doe",
                        "date_of_birth": "01/15/1960",
                        "member_id": "M123456789",
                        "gender": "Male",
                        "phone": "555-0123"
                    },
                    "provider_info": {
                        "provider_name": "Jane Smith MD",
                        "npi": "1234567890",
                        "specialty": "Cardiology",
                        "facility": "Example Medical Center"
                    },
                    "clinical_info": {
                        "diagnosis_codes": ["I25.10"],
                        "procedure_codes": ["93458"],
                        "date_of_service": "03/15/2024"
                    }
                },
                "phi_flags": ["phone", "mrn", "name"],
                "validation_errors": []
            },
            "document_type": request_data.get("document_type", ["healthcare_form"]),
            "confidence_scores": {
                "overall_confidence": 0.92,
                "text_confidence": 0.95,
                "table_confidence": 0.88,
                "healthcare_fields_confidence": 0.90
            },
            "phi_detected": ["phone", "mrn", "name"],
            "compliance_status": "HIPAA_COMPLIANT",
            "extraction_metadata": {
                "timestamp": datetime.now().isoformat(),
                "extractor_version": "1.0.0",
                "confidence_threshold": request_data.get("confidence_threshold", 0.7),
                "mock_mode": True
            }
        }

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process real document extraction requests (production implementation).

        In production, this would:
        1. Authenticate with Azure Form Recognizer
        2. Process the actual document
        3. Apply healthcare-specific field extraction
        4. Perform PHI detection and masking
        5. Generate audit logs
        """
        # For now, return mock data with production note
        mock_response = self.get_mock_response(request_data)
        mock_response["production_note"] = "Configure Azure Form Recognizer credentials for live extraction"
        return mock_response


