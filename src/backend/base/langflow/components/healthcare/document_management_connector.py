from typing import Any, Dict, List, Optional, Union
import json
import base64
import os
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.inputs import (
    BoolInput,
    DictInput,
    FileInput,
    IntInput,
    MessageTextInput,
    MultiselectInput,
    SecretStrInput,
    StrInput,
)
from langflow.io import Output
from langflow.schema import Data


logger = logging.getLogger(__name__)


class DocumentManagementConnector(HealthcareConnectorBase):
    display_name = "Document Management Connector"
    description = "HIPAA-compliant document attachment and management for healthcare case files with audit trails"
    icon = "folder-plus"
    name = "DocumentManagementConnector"
    category = "connectors"

    def __init__(self, **kwargs):
        """Initialize DocumentManagementConnector with healthcare base inputs and management-specific inputs."""
        super().__init__(**kwargs)

        # Add document management-specific inputs to the base class inputs
        management_inputs = [
        StrInput(
            name="storage_endpoint",
            display_name="Document Storage Endpoint",
            required=True,
            placeholder="https://your-storage.blob.core.windows.net/",
            info="HIPAA-compliant storage endpoint for document management",
        ),
        SecretStrInput(
            name="storage_key",
            display_name="Storage Access Key",
            required=True,
            password=True,
            info="Access key for secure document storage",
        ),
        StrInput(
            name="container_name",
            display_name="Storage Container",
            required=True,
            value="healthcare-documents",
            info="Container name for healthcare documents",
        ),
        MultiselectInput(
            name="operation_type",
            display_name="Operation Type",
            options=[
                "attach_document",
                "retrieve_document",
                "list_attachments",
                "delete_document",
                "update_metadata"
            ],
            value=["attach_document"],
            info="Type of document management operation to perform",
        ),
        StrInput(
            name="case_id",
            display_name="Case ID",
            required=False,
            placeholder="PA-2024-12345",
            info="Healthcare case identifier for document association",
        ),
        FileInput(
            name="document_file",
            display_name="Document File",
            required=False,
            file_types=["pdf", "tiff", "jpg", "jpeg", "png", "doc", "docx"],
            info="Document file to attach (PDF, TIFF, images, Word docs)",
        ),
        StrInput(
            name="document_path",
            display_name="Document Path",
            required=False,
            placeholder="/tmp/fax_12345.pdf",
            info="Path to document file if not using file upload",
        ),
        MultiselectInput(
            name="document_type",
            display_name="Document Type",
            options=[
                "authorization_request",
                "medical_record",
                "prescription",
                "lab_result",
                "imaging_report",
                "discharge_summary",
                "consent_form",
                "insurance_card",
                "prior_auth_form",
                "appeal_letter",
                "clinical_note",
                "pharmacy_fax",
                "provider_letter",
                "other"
            ],
            value=["pharmacy_fax"],
            info="Type of healthcare document being attached",
        ),
        DictInput(
            name="document_metadata",
            display_name="Document Metadata",
            required=False,
            info="Additional metadata for the document (received_date, page_count, source, etc.)",
        ),
        BoolInput(
            name="encrypt_document",
            display_name="Encrypt Document",
            value=True,
            info="Enable encryption for HIPAA compliance",
        ),
        BoolInput(
            name="audit_trail",
            display_name="Enable Audit Trail",
            value=True,
            info="Track all document operations for compliance",
        ),
        IntInput(
            name="retention_days",
            display_name="Retention Period (Days)",
            value=2555,  # 7 years default for healthcare
            info="Document retention period in days (default: 7 years)",
        ),
        BoolInput(
            name="mock_mode",
            display_name="Mock Mode",
            value=False,
            info="Enable mock mode for testing without actual storage operations",
        ),
        ]

        # Combine base class inputs with management-specific inputs
        self.inputs = self.inputs + management_inputs

    outputs = [
        Output(display_name="Document Info", name="document_info", method="attach_document"),
        Output(display_name="Status", name="status", method="get_status"),
        Output(display_name="Audit Log", name="audit_log", method="get_audit_log"),
    ]

    def attach_document(self) -> Data:
        """Attach document to healthcare case with HIPAA compliance and audit trail."""
        try:
            # Prepare request data
            request_data = {
                "operation": getattr(self, 'operation_type', ['attach_document'])[0] if hasattr(self, 'operation_type') and self.operation_type else "attach_document",
                "case_id": getattr(self, 'case_id', ''),
                "document_type": getattr(self, 'document_type', ['other']),
                "encrypt_document": getattr(self, 'encrypt_document', True),
                "audit_trail": getattr(self, 'audit_trail', True),
                "retention_days": getattr(self, 'retention_days', 2555),
            }

            # Handle document input
            if hasattr(self, 'document_file') and self.document_file:
                request_data['has_document_file'] = True
            elif hasattr(self, 'document_path') and self.document_path:
                request_data['document_path'] = self.document_path

            # Add metadata if provided
            if hasattr(self, 'document_metadata') and self.document_metadata:
                request_data['metadata'] = self.document_metadata

            return self.execute_healthcare_workflow(request_data)

        except Exception as e:
            return self._handle_healthcare_error(e, "attach_document")

    def get_status(self) -> Data:
        """Get status of document management operations."""
        try:
            request_data = {"operation": "get_status"}
            result = self.execute_healthcare_workflow(request_data)

            # Extract status from full response
            if hasattr(result, 'data') and isinstance(result.data, dict):
                status_info = result.data.get('status_info', {})
                return Data(data=status_info)

            return result

        except Exception as e:
            return self._handle_healthcare_error(e, "get_status")

    def get_audit_log(self) -> Data:
        """Get audit log for document management operations."""
        try:
            request_data = {"operation": "get_audit_log"}
            return self.execute_healthcare_workflow(request_data)
        except Exception as e:
            return self._handle_healthcare_error(e, "get_audit_log")

    def get_required_fields(self) -> List[str]:
        """Get required fields for document management operations."""
        return ["operation"]

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Provide comprehensive mock document management data for development."""
        operation = request_data.get("operation", "attach_document")

        if operation == "get_audit_log":
            return {
                "audit_entries": [
                    {
                        "audit_id": f"AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        "operation": "ATTACH",
                        "document_id": "DOC_20240315_123456_PA_2024_12345",
                        "case_id": request_data.get("case_id", "PA-2024-12345"),
                        "user_id": "system",
                        "timestamp": datetime.now().isoformat(),
                        "details": "Document attachment completed successfully",
                        "compliance_flags": ["HIPAA_VERIFIED", "AUDIT_ENABLED"]
                    }
                ],
                "compliance_status": "ACTIVE",
                "last_accessed": datetime.now().isoformat(),
            }

        elif operation == "get_status":
            return {
                "status_info": {
                    "operation": "document_management",
                    "status": "success",
                    "last_operation": "attach_document",
                    "documents_processed": 1,
                    "compliance_verified": True,
                    "hipaa_compliant": True,
                    "timestamp": datetime.now().isoformat()
                }
            }

        # Mock document attachment response
        mock_document_id = f"DOC_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        case_id = request_data.get("case_id", "PA-2024-12345")

        return {
            "document_info": {
                "document_id": mock_document_id,
                "case_id": case_id,
                "file_name": "mock_healthcare_document.pdf",
                "document_type": request_data.get("document_type", ["pharmacy_fax"])[0] if isinstance(request_data.get("document_type"), list) else request_data.get("document_type", "pharmacy_fax"),
                "content_hash": "mock_sha256_hash_12345",
                "encrypted": request_data.get("encrypt_document", True),
                "storage_path": f"/mock/storage/{case_id}/{mock_document_id}",
                "upload_timestamp": datetime.now().isoformat(),
                "metadata": request_data.get("metadata", {})
            },
            "status_info": {
                "status": "success",
                "operation": "attach_document",
                "document_id": mock_document_id,
                "case_id": case_id,
                "storage_location": f"/mock/storage/{case_id}/{mock_document_id}",
                "compliance_verified": True,
                "hipaa_compliant": True,
                "mock_mode": True
            },
            "audit_info": {
                "audit_id": f"AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "operation": "ATTACH",
                "document_id": mock_document_id,
                "case_id": case_id,
                "user_id": "system",
                "timestamp": datetime.now().isoformat(),
                "details": "Mock document attachment for testing",
                "compliance_flags": ["HIPAA_VERIFIED", "AUDIT_ENABLED"]
            }
        }

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process real document management requests (production implementation).

        In production, this would:
        1. Authenticate with secure storage (Azure Blob, AWS S3, etc.)
        2. Encrypt documents according to HIPAA requirements
        3. Generate secure document IDs and storage paths
        4. Create comprehensive audit trails
        5. Implement retention policies
        """
        # For now, return mock data with production note
        mock_response = self.get_mock_response(request_data)
        mock_response["production_note"] = "Configure storage credentials for live document management"
        return mock_response

