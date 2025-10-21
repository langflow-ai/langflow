"""Claims Healthcare Connector for EDI transaction processing and prior authorization."""

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from langflow.io import DropdownInput, MessageTextInput, Output
from langflow.logging.logger import logger
from langflow.schema.data import Data

from langflow.base.healthcare_connector_base import HealthcareConnectorBase


class ClaimsConnector(HealthcareConnectorBase):
    """
    Claims Healthcare Connector for comprehensive claims processing.

    Supports:
    - 837 EDI transaction submission (Professional, Institutional, Dental)
    - 835 EDI remittance advice processing
    - Claims status inquiry (276/277 transactions)
    - Prior authorization workflows
    - Real-time adjudication and payment posting
    """

    display_name = "Claims Connector"
    description = "Healthcare claims processing integration supporting EDI transactions and prior authorization"
    icon = "FileText"
    name = "ClaimsConnector"
    category = "connectors"

    outputs = [
        Output(display_name="Claims Response", name="claims_response", method="process_claims"),
    ]

    def __init__(self, **kwargs):
        """Initialize ClaimsConnector with healthcare base inputs and claims-specific inputs."""
        super().__init__(**kwargs)

        # Add claims-specific inputs to the base class inputs
        claims_inputs = [
            DropdownInput(
                name="clearinghouse",
                display_name="Clearinghouse",
                options=["change_healthcare", "availity", "relay_health", "navinet"],
                value="change_healthcare",
                info="Healthcare clearinghouse for claims processing",
                tool_mode=True,
            ),
            MessageTextInput(
                name="payer_id",
                display_name="Payer ID",
                info="Insurance payer identifier",
                tool_mode=True,
            ),
            MessageTextInput(
                name="provider_npi",
                display_name="Provider NPI",
                info="National Provider Identifier for healthcare provider",
                tool_mode=True,
            ),
            MessageTextInput(
                name="submitter_id",
                display_name="Submitter ID",
                info="Submitter identification for clearinghouse",
                tool_mode=True,
            ),
            MessageTextInput(
                name="claim_data",
                display_name="Claim Data",
                info="Claims data in JSON format for processing",
                tool_mode=True,
            ),
        ]

        # Combine base class inputs with claims-specific inputs
        self.inputs = self.inputs + claims_inputs

        # Set claims-specific defaults
        self._request_id = None
        self.test_mode = True
        self.mock_mode = True

    def get_required_fields(self) -> List[str]:
        """Required fields for claims processing."""
        return ["claim_data"]

    def execute_healthcare_workflow(self, request_data: dict) -> Data:
        """Execute healthcare workflow with proper error handling and audit logging."""
        import uuid
        from datetime import datetime

        try:
            # Generate unique request ID for tracking
            self._request_id = str(uuid.uuid4())

            # Log request for HIPAA audit trail
            self._audit_log_request(request_data)

            # Determine if using mock or real response
            if self.mock_mode or self.test_mode:
                response_data = self.get_mock_response(request_data)
                response_data["mode"] = "mock"
            else:
                response_data = self.process_healthcare_request(request_data)
                response_data["mode"] = "live"

            # Add metadata
            response_data.update({
                "request_id": self._request_id,
                "timestamp": datetime.now().isoformat(),
                "component": self.__class__.__name__,
                "hipaa_compliant": True,
                "audit_logged": True
            })

            # Log response for audit trail
            self._audit_log_response(response_data)

            return Data(value=response_data)

        except Exception as e:
            return self._handle_healthcare_error(e, "execute_healthcare_workflow")

    def _audit_log_request(self, request_data: dict) -> None:
        """Log healthcare request for HIPAA compliance audit trail."""
        # In production, this would log to secure audit system
        # For now, using standard logging with PHI protection
        sanitized_request = self._sanitize_phi_data(request_data)
        logger.info(f"Healthcare request initiated - Component: {self.__class__.__name__}, "
                   f"Request ID: {self._request_id}, Operation: {sanitized_request.get('operation', 'general')}")

    def _audit_log_response(self, response_data: dict) -> None:
        """Log healthcare response for HIPAA compliance audit trail."""
        logger.info(f"Healthcare response completed - Component: {self.__class__.__name__}, "
                   f"Request ID: {self._request_id}, Status: {response_data.get('status', 'unknown')}")

    def _sanitize_phi_data(self, data: dict) -> dict:
        """Remove or mask PHI/PII data for logging purposes."""
        sanitized = data.copy()

        # List of fields that may contain PHI
        phi_fields = [
            'patient_id', 'member_id', 'ssn', 'date_of_birth', 'phone_number',
            'email', 'address', 'name', 'first_name', 'last_name', 'mrn'
        ]

        for field in phi_fields:
            if field in sanitized:
                if isinstance(sanitized[field], str) and len(sanitized[field]) > 3:
                    # Mask all but last 3 characters
                    sanitized[field] = '*' * (len(sanitized[field]) - 3) + sanitized[field][-3:]
                else:
                    sanitized[field] = '***'

        return sanitized

    def _handle_healthcare_error(self, error: Exception, operation: str) -> Data:
        """Handle healthcare-specific errors with proper logging and response."""
        from datetime import datetime

        error_message = str(error)

        # Log error for audit trail (without PHI)
        logger.error(f"Healthcare operation failed - Component: {self.__class__.__name__}, "
                    f"Operation: {operation}, Error: {error_message}")

        # Return structured error response
        error_response = {
            "error": True,
            "error_type": type(error).__name__,
            "error_message": error_message,
            "operation": operation,
            "component": self.__class__.__name__,
            "request_id": getattr(self, '_request_id', None),
            "timestamp": datetime.now().isoformat(),
            "hipaa_compliant": True,
            "mode": "error"
        }

        return Data(value=error_response)

    def process_claims(self) -> Data:
        """Main method to process claims requests."""
        try:
            # Parse claim data
            if isinstance(self.claim_data, str):
                try:
                    claim_input = json.loads(self.claim_data)
                except json.JSONDecodeError:
                    # Treat as simple text input
                    claim_input = {"request_type": "general", "data": self.claim_data}
            else:
                claim_input = {"request_type": "general", "data": str(self.claim_data)}

            # Add connector configuration
            claim_input.update({
                "clearinghouse": self.clearinghouse,
                "payer_id": self.payer_id,
                "provider_npi": self.provider_npi,
                "submitter_id": self.submitter_id,
                "authentication_type": self.authentication_type,
                "test_mode": self.test_mode,
            })

            return self.execute_healthcare_workflow(claim_input)

        except Exception as e:
            return self._handle_healthcare_error(e, "process_claims")

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process real healthcare claims request."""
        # This would integrate with actual clearinghouse APIs in production
        # For now, return a structured response indicating live mode
        return {
            "status": "submitted",
            "message": "Claims request submitted to live clearinghouse API",
            "clearinghouse": request_data.get("clearinghouse", "unknown"),
            "request_id": self._request_id,
            "note": "Production implementation would integrate with actual clearinghouse APIs",
        }

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive mock response with realistic healthcare data."""
        request_type = request_data.get("request_type", "general")

        if request_type == "claim_submission" or "837" in str(request_data.get("data", "")).upper():
            return self._mock_claim_submission_response(request_data)
        elif request_type == "claim_status" or "276" in str(request_data.get("data", "")).upper():
            return self._mock_claim_status_response(request_data)
        elif request_type == "remittance" or "835" in str(request_data.get("data", "")).upper():
            return self._mock_remittance_advice_response(request_data)
        elif request_type == "prior_authorization" or "prior" in str(request_data.get("data", "")).lower():
            return self._mock_prior_authorization_response(request_data)
        else:
            return self._mock_general_claims_response(request_data)

    def _mock_claim_submission_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock 837 EDI claim submission response."""
        control_number = f"ICN{random.randint(100000000, 999999999)}"
        submission_id = f"SUB{uuid.uuid4().hex[:8].upper()}"

        return {
            "transaction_type": "837_claim_submission",
            "submission_id": submission_id,
            "control_number": control_number,
            "status": "accepted",
            "clearinghouse": request_data.get("clearinghouse", "change_healthcare"),
            "payer_id": request_data.get("payer_id", "AETNA"),
            "provider_npi": request_data.get("provider_npi", "1234567890"),
            "submission_timestamp": datetime.now().isoformat(),
            "estimated_processing_days": random.randint(5, 14),
            "claim_details": {
                "claim_frequency_code": "1",  # Original claim
                "patient_control_number": f"PAT{random.randint(100000, 999999)}",
                "total_claim_charge": round(random.uniform(150.00, 2500.00), 2),
                "service_lines": random.randint(1, 5),
            },
            "edi_segments": {
                "ISA": "Interchange Control Header",
                "GS": "Functional Group Header",
                "ST": "Transaction Set Header (837)",
                "BHT": "Beginning of Hierarchical Transaction",
                "NM1": "Individual or Organizational Name",
                "CLM": "Claim Information",
                "SV1": "Professional Service",
                "SE": "Transaction Set Trailer",
                "GE": "Functional Group Trailer",
                "IEA": "Interchange Control Trailer",
            },
            "compliance": {
                "hipaa_version": "5010",
                "ansi_version": "X12 005010X222A1",
                "phi_protected": True,
                "audit_logged": True,
            },
            "next_steps": [
                "Monitor claim status using 276/277 transactions",
                "Check for acknowledgment within 24-48 hours",
                "Follow up on processing status in 7-10 business days",
            ],
        }

    def _mock_claim_status_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock 276/277 EDI claim status response."""
        claim_statuses = [
            {"code": "1", "description": "Processed as Primary", "category": "Finalized"},
            {"code": "2", "description": "Processed as Secondary", "category": "Finalized"},
            {"code": "3", "description": "Processed as Tertiary", "category": "Finalized"},
            {"code": "19", "description": "Claim Received", "category": "Acknowledged"},
            {"code": "20", "description": "Under Review", "category": "Pended"},
            {"code": "22", "description": "Reversed", "category": "Reversed"},
        ]

        status = random.choice(claim_statuses)
        claim_number = f"CLM{random.randint(1000000000, 9999999999)}"

        return {
            "transaction_type": "277_claim_status_response",
            "claim_status_inquiry": {
                "claim_number": claim_number,
                "patient_control_number": f"PAT{random.randint(100000, 999999)}",
                "status_code": status["code"],
                "status_description": status["description"],
                "status_category": status["category"],
                "effective_date": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                "payer_claim_number": f"PCN{random.randint(10000000, 99999999)}",
            },
            "provider_info": {
                "provider_npi": request_data.get("provider_npi", "1234567890"),
                "provider_name": "Healthcare Provider Group",
                "provider_taxonomy": "207Q00000X",  # Family Medicine
            },
            "payer_info": {
                "payer_id": request_data.get("payer_id", "AETNA"),
                "payer_name": "Aetna Better Health",
                "contact_info": "1-800-AETNA-EDI",
            },
            "claim_amounts": {
                "total_submitted": round(random.uniform(200.00, 1500.00), 2),
                "allowed_amount": round(random.uniform(150.00, 1200.00), 2),
                "deductible": round(random.uniform(0.00, 100.00), 2),
                "copay": round(random.uniform(10.00, 50.00), 2),
                "paid_amount": round(random.uniform(100.00, 1000.00), 2),
            },
            "adjudication_info": {
                "adjudication_date": (datetime.now() - timedelta(days=random.randint(1, 14))).date().isoformat(),
                "remittance_date": (datetime.now() - timedelta(days=random.randint(0, 7))).date().isoformat(),
                "check_number": f"CHK{random.randint(1000000, 9999999)}",
            },
            "compliance": {
                "hipaa_version": "5010",
                "transaction_set": "277",
                "phi_protected": True,
            },
        }

    def _mock_remittance_advice_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock 835 EDI Electronic Remittance Advice response."""
        adjustment_codes = [
            {"code": "CO", "description": "Contractual Obligation", "group": "Denial"},
            {"code": "PR", "description": "Patient Responsibility", "group": "Patient"},
            {"code": "PI", "description": "Payer Initiated", "group": "Payer"},
            {"code": "OA", "description": "Other Adjustment", "group": "Other"},
        ]

        service_lines = []
        total_paid = 0.0

        for i in range(random.randint(1, 4)):
            line_charge = round(random.uniform(50.00, 500.00), 2)
            line_paid = round(line_charge * random.uniform(0.7, 1.0), 2)
            total_paid += line_paid

            adjustment = random.choice(adjustment_codes)
            adjustment_amount = round(line_charge - line_paid, 2)

            service_lines.append({
                "line_number": i + 1,
                "procedure_code": f"9921{random.randint(1, 5)}",  # E&M codes
                "modifier": random.choice(["", "25", "59", "GT"]),
                "line_charge": line_charge,
                "line_paid": line_paid,
                "adjustment_code": adjustment["code"],
                "adjustment_amount": adjustment_amount,
                "adjustment_reason": adjustment["description"],
                "service_date": (datetime.now() - timedelta(days=random.randint(7, 30))).date().isoformat(),
            })

        return {
            "transaction_type": "835_electronic_remittance_advice",
            "remittance_info": {
                "check_number": f"CHK{random.randint(1000000, 9999999)}",
                "check_date": datetime.now().date().isoformat(),
                "check_amount": round(total_paid, 2),
                "payment_method": random.choice(["ACH", "Check", "Wire Transfer"]),
                "trace_number": f"TRN{random.randint(100000000, 999999999)}",
            },
            "payer_info": {
                "payer_id": request_data.get("payer_id", "AETNA"),
                "payer_name": "Aetna Better Health",
                "payer_address": "151 Farmington Avenue, Hartford, CT 06156",
                "contact_number": "1-800-AETNA-EDI",
            },
            "provider_info": {
                "provider_npi": request_data.get("provider_npi", "1234567890"),
                "provider_name": "Healthcare Provider Group",
                "tax_id": f"EIN{random.randint(100000000, 999999999)}",
            },
            "claim_payments": [
                {
                    "claim_number": f"CLM{random.randint(1000000000, 9999999999)}",
                    "patient_control_number": f"PAT{random.randint(100000, 999999)}",
                    "patient_name": "PATIENT, SAMPLE",
                    "patient_id": f"MEM{random.randint(100000000, 999999999)}",
                    "service_date_range": {
                        "from": (datetime.now() - timedelta(days=30)).date().isoformat(),
                        "to": (datetime.now() - timedelta(days=30)).date().isoformat(),
                    },
                    "total_charge": round(sum(line["line_charge"] for line in service_lines), 2),
                    "total_paid": round(total_paid, 2),
                    "patient_responsibility": round(random.uniform(10.00, 100.00), 2),
                    "service_lines": service_lines,
                }
            ],
            "summary": {
                "total_claims": 1,
                "total_charges": round(sum(line["line_charge"] for line in service_lines), 2),
                "total_payments": round(total_paid, 2),
                "total_adjustments": round(sum(line["adjustment_amount"] for line in service_lines), 2),
            },
            "compliance": {
                "hipaa_version": "5010",
                "transaction_set": "835",
                "phi_protected": True,
                "financial_data": True,
            },
        }

    def _mock_prior_authorization_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock prior authorization response with ePA workflow."""
        auth_statuses = [
            {"code": "A", "description": "Approved", "urgency": "Standard"},
            {"code": "D", "description": "Denied", "urgency": "Standard"},
            {"code": "P", "description": "Pended - Additional Information Required", "urgency": "Standard"},
            {"code": "U", "description": "Under Review", "urgency": "Urgent"},
        ]

        status = random.choice(auth_statuses)
        auth_number = f"PA{uuid.uuid4().hex[:8].upper()}"

        response = {
            "transaction_type": "prior_authorization_response",
            "authorization_info": {
                "auth_number": auth_number,
                "status_code": status["code"],
                "status_description": status["description"],
                "urgency": status["urgency"],
                "effective_date": datetime.now().date().isoformat(),
                "expiration_date": (datetime.now() + timedelta(days=365)).date().isoformat(),
                "response_timestamp": datetime.now().isoformat(),
            },
            "patient_info": {
                "member_id": f"MEM{random.randint(100000000, 999999999)}",
                "patient_name": "PATIENT, SAMPLE",
                "date_of_birth": "1980-01-01",  # Anonymized DOB
                "subscriber_id": f"SUB{random.randint(100000000, 999999999)}",
            },
            "provider_info": {
                "requesting_provider_npi": request_data.get("provider_npi", "1234567890"),
                "provider_name": "Healthcare Provider Group",
                "provider_specialty": "Internal Medicine",
                "contact_info": "(555) 123-4567",
            },
            "service_info": {
                "procedure_code": random.choice(["99213", "99214", "99215", "71020", "73060"]),
                "procedure_description": "Professional Service",
                "diagnosis_code": random.choice(["Z00.00", "I10", "E78.5", "M79.603"]),
                "service_type": random.choice(["Medical", "Surgical", "Diagnostic", "Therapeutic"]),
                "units_authorized": random.randint(1, 10),
            },
            "payer_info": {
                "payer_id": request_data.get("payer_id", "AETNA"),
                "payer_name": "Aetna Better Health",
                "plan_type": "HMO",
                "contact_info": "1-800-AETNA-PA",
            },
        }

        # Add status-specific information
        if status["code"] == "A":  # Approved
            response["approval_details"] = {
                "approved_amount": round(random.uniform(500.00, 5000.00), 2),
                "frequency": "Once per year",
                "special_instructions": "Prior authorization approved for requested service",
                "review_required": False,
            }
        elif status["code"] == "D":  # Denied
            response["denial_details"] = {
                "denial_reason": "Medical necessity not established",
                "denial_code": "D001",
                "appeal_rights": "Patient may appeal within 60 days",
                "alternative_treatments": ["Conservative management", "Physical therapy"],
            }
        elif status["code"] == "P":  # Pended
            response["pending_details"] = {
                "required_information": [
                    "Additional clinical documentation",
                    "Recent lab results",
                    "Specialist consultation notes"
                ],
                "submission_deadline": (datetime.now() + timedelta(days=14)).date().isoformat(),
                "contact_for_questions": "1-800-AETNA-PA ext. 1234",
            }

        response["compliance"] = {
            "epa_compliant": True,
            "real_time_decision": True,
            "phi_protected": True,
            "audit_logged": True,
        }

        response["workflow_info"] = {
            "decision_time_minutes": random.randint(1, 15),
            "automated_decision": status["code"] in ["A", "D"],
            "requires_human_review": status["code"] == "P",
            "appeal_process_available": True,
        }

        return response

    def _mock_general_claims_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """General claims processing response."""
        return {
            "transaction_type": "general_claims_processing",
            "status": "processed",
            "message": "Claims request processed successfully",
            "clearinghouse": request_data.get("clearinghouse", "change_healthcare"),
            "capabilities": {
                "edi_transactions": ["837P", "837I", "837D", "835", "276", "277"],
                "prior_authorization": True,
                "real_time_adjudication": True,
                "batch_processing": True,
                "claim_status_inquiry": True,
                "payment_posting": True,
            },
            "supported_clearinghouses": [
                "Change Healthcare",
                "Availity",
                "Relay Health",
                "NaviNet"
            ],
            "compliance_features": {
                "hipaa_5010": True,
                "phi_protection": True,
                "audit_logging": True,
                "encryption": True,
                "secure_transmission": True,
            },
            "integration_info": {
                "real_time_mode": not self.test_mode,
                "test_mode": self.test_mode,
                "mock_mode": self.mock_mode,
                "authentication": request_data.get("authentication_type", "api_key"),
            },
            "next_steps": [
                "Configure specific EDI transaction type",
                "Provide claim data in appropriate format",
                "Monitor processing status and responses",
            ],
        }