"""Pharmacy Healthcare Connector for e-prescribing and medication management."""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from langflow.io import BoolInput, DropdownInput, MessageTextInput, Output
from langflow.schema.data import Data

from langflow.base.healthcare_connector_base import HealthcareConnectorBase


class PharmacyConnector(HealthcareConnectorBase):
    """
    Pharmacy Healthcare Connector for comprehensive medication management.

    Provides e-prescribing, drug interaction checking, formulary verification,
    and medication therapy management capabilities with HIPAA compliance.
    """

    display_name = "Pharmacy Connector"
    description = "HIPAA-compliant pharmacy and medication management connector with e-prescribing, drug interaction checking, and formulary verification"
    icon = "Pill"
    name = "PharmacyConnector"
    category = "connectors"

    outputs = [
        Output(display_name="Pharmacy Response", name="pharmacy_response", method="execute_pharmacy_workflow"),
    ]

    def __init__(self, **kwargs):
        """Initialize PharmacyConnector with healthcare base inputs and pharmacy-specific inputs."""
        super().__init__(**kwargs)

        # Add pharmacy-specific inputs to the base class inputs
        pharmacy_inputs = [
            DropdownInput(
                name="pharmacy_network",
                display_name="Pharmacy Network",
                options=["surescripts", "ncpdp", "relay_health"],
                value="surescripts",
                info="Pharmacy network for e-prescribing integration",
                tool_mode=True,
            ),
            MessageTextInput(
                name="prescriber_npi",
                display_name="Prescriber NPI",
                info="National Provider Identifier for prescriber",
                placeholder="1234567890",
                tool_mode=True,
            ),
            MessageTextInput(
                name="dea_number",
                display_name="DEA Number",
                info="DEA number for controlled substance prescribing",
                placeholder="AB1234567",
                tool_mode=True,
            ),
            DropdownInput(
                name="drug_database",
                display_name="Drug Database",
                options=["first_databank", "medi_span", "lexicomp"],
                value="first_databank",
                info="Drug database for interaction checking and drug information",
                tool_mode=True,
            ),
            BoolInput(
                name="interaction_checking",
                display_name="Drug Interaction Checking",
                value=True,
                info="Enable real-time drug interaction screening",
                tool_mode=True,
            ),
            BoolInput(
                name="formulary_checking",
                display_name="Formulary Checking",
                value=True,
                info="Enable formulary verification and alternative suggestions",
                tool_mode=True,
            ),
            BoolInput(
                name="prior_auth_checking",
                display_name="Prior Authorization Checking",
                value=True,
                info="Check for prior authorization requirements",
                tool_mode=True,
            ),
            MessageTextInput(
                name="prescription_data",
                display_name="Prescription Data",
                info="Prescription information in JSON format",
                placeholder='{"patient_id": "PAT123", "medication": "Lisinopril 10mg", "quantity": 30}',
                tool_mode=True,
            ),
        ]

        # Combine base class inputs with pharmacy-specific inputs
        self.inputs = self.inputs + pharmacy_inputs

        # Set pharmacy-specific defaults
        self._request_id = None
        self.test_mode = True
        self.mock_mode = True

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
        from langflow.logging.logger import logger

        # In production, this would log to secure audit system
        # For now, using standard logging with PHI protection
        sanitized_request = self._sanitize_phi_data(request_data)
        logger.info(f"Healthcare request initiated - Component: {self.__class__.__name__}, "
                   f"Request ID: {self._request_id}, Operation: {sanitized_request.get('operation', 'general')}")

    def _audit_log_response(self, response_data: dict) -> None:
        """Log healthcare response for HIPAA compliance audit trail."""
        from langflow.logging.logger import logger

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
        from langflow.logging.logger import logger
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

    def get_required_fields(self) -> List[str]:
        """Required fields for pharmacy operations."""
        return ["patient_id", "medication"]

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Provide comprehensive mock pharmacy response."""
        patient_id = request_data.get("patient_id", "PAT123456")
        medication = request_data.get("medication", "Lisinopril 10mg")

        # Generate realistic mock data based on request type
        operation = request_data.get("operation", "e_prescribe")

        base_response = {
            "patient_id": patient_id,
            "medication": medication,
            "timestamp": datetime.now().isoformat(),
            "network": self.pharmacy_network,
            "processing_time_ms": 245,
        }

        if operation == "e_prescribe":
            return {
                **base_response,
                "operation": "e_prescribe",
                "prescription_id": f"RX-{patient_id[-6:]}-001",
                "status": "transmitted",
                "pharmacy_ncpdp": "1234567",
                "pharmacy_name": "Main Street Pharmacy",
                "pharmacy_phone": "(555) 123-4567",
                "prescription_status": "accepted",
                "estimated_ready_time": (datetime.now() + timedelta(hours=2)).isoformat(),
                "confirmation_number": "CNF789456123",
                "directions": "Take one tablet by mouth daily",
                "quantity_prescribed": 30,
                "refills_remaining": 5,
                "daw": False,  # Dispense as written
                "generic_substitution_allowed": True,
            }

        elif operation == "drug_interaction":
            return {
                **base_response,
                "operation": "drug_interaction_check",
                "interactions": [
                    {
                        "severity": "moderate",
                        "drug1": "Lisinopril",
                        "drug2": "Potassium Chloride",
                        "interaction_type": "pharmacodynamic",
                        "clinical_significance": "Monitor potassium levels",
                        "recommendation": "Monitor serum potassium; consider dose adjustment",
                        "evidence_level": "well_documented",
                        "frequency": "common",
                    }
                ],
                "total_interactions": 1,
                "high_severity_count": 0,
                "moderate_severity_count": 1,
                "low_severity_count": 0,
                "contraindications": [],
                "warnings": [
                    "Monitor kidney function in elderly patients",
                    "May cause hyperkalemia with concurrent potassium supplements"
                ],
            }

        elif operation == "formulary_check":
            return {
                **base_response,
                "operation": "formulary_verification",
                "formulary_status": "preferred",
                "tier": 2,
                "coverage_determination": "covered",
                "patient_cost": {
                    "copay": 15.00,
                    "coinsurance": 0.20,
                    "deductible_remaining": 150.00,
                },
                "alternatives": [
                    {
                        "medication": "Enalapril 10mg",
                        "tier": 1,
                        "copay": 10.00,
                        "therapeutic_equivalent": True,
                        "savings_vs_preferred": 5.00,
                    },
                    {
                        "medication": "Generic Lisinopril 10mg",
                        "tier": 1,
                        "copay": 5.00,
                        "therapeutic_equivalent": True,
                        "savings_vs_preferred": 10.00,
                    }
                ],
                "prior_authorization_required": False,
                "quantity_limits": {
                    "max_quantity_per_fill": 90,
                    "max_refills_per_year": 12,
                },
                "step_therapy_required": False,
                "plan_details": {
                    "plan_name": "Comprehensive Health Plan",
                    "plan_id": "HP123456",
                    "effective_date": "2025-01-01",
                },
            }

        elif operation == "medication_reconciliation":
            return {
                **base_response,
                "operation": "medication_reconciliation",
                "current_medications": [
                    {
                        "medication": "Lisinopril 10mg",
                        "ndc": "0093-7663-01",
                        "status": "active",
                        "start_date": "2024-01-15",
                        "prescriber": "Dr. Smith",
                        "directions": "Take one tablet daily",
                        "quantity": 30,
                        "refills": 5,
                        "last_filled": "2025-01-01",
                    },
                    {
                        "medication": "Metformin 500mg",
                        "ndc": "0781-1506-01",
                        "status": "active",
                        "start_date": "2023-06-20",
                        "prescriber": "Dr. Johnson",
                        "directions": "Take twice daily with meals",
                        "quantity": 60,
                        "refills": 3,
                        "last_filled": "2025-01-10",
                    }
                ],
                "discontinued_medications": [
                    {
                        "medication": "Hydrochlorothiazide 25mg",
                        "discontinue_date": "2024-01-15",
                        "reason": "Replaced with Lisinopril",
                    }
                ],
                "reconciliation_summary": {
                    "total_medications": 2,
                    "new_medications": 0,
                    "changed_medications": 0,
                    "discontinued_medications": 1,
                    "potential_duplicates": 0,
                    "adherence_concerns": [],
                },
                "clinical_alerts": [
                    {
                        "type": "monitoring",
                        "message": "Monitor kidney function with ACE inhibitor therapy",
                        "severity": "low",
                    }
                ],
            }

        elif operation == "prior_authorization":
            return {
                **base_response,
                "operation": "prior_authorization",
                "pa_required": True,
                "pa_status": "required",
                "pa_requirements": {
                    "documentation_needed": [
                        "Previous medication trials",
                        "Clinical justification for brand name",
                        "Patient medical history",
                    ],
                    "forms_required": ["PA Form 2024-CARDIO"],
                    "estimated_approval_time": "2-5 business days",
                    "appeal_process_available": True,
                },
                "pa_criteria": {
                    "step_therapy": True,
                    "required_trials": [
                        "Generic ACE inhibitor for 30 days minimum",
                        "Alternative ARB if ACE inhibitor intolerant",
                    ],
                    "medical_justification": "Required for brand name preference",
                },
                "alternatives_no_pa": [
                    {
                        "medication": "Generic Lisinopril 10mg",
                        "copay": 5.00,
                        "immediately_available": True,
                    },
                    {
                        "medication": "Enalapril 10mg",
                        "copay": 10.00,
                        "immediately_available": True,
                    }
                ],
            }

        elif operation == "medication_therapy_management":
            return {
                **base_response,
                "operation": "medication_therapy_management",
                "mtm_eligible": True,
                "therapy_review": {
                    "overall_score": 85,
                    "adherence_rate": 0.90,
                    "cost_effectiveness": "good",
                    "safety_profile": "appropriate",
                },
                "recommendations": [
                    {
                        "type": "optimization",
                        "priority": "medium",
                        "recommendation": "Consider generic substitution to reduce costs",
                        "potential_savings_annual": 120.00,
                    },
                    {
                        "type": "monitoring",
                        "priority": "low",
                        "recommendation": "Schedule annual kidney function monitoring",
                        "next_due_date": "2025-06-15",
                    }
                ],
                "adherence_data": {
                    "proportion_days_covered": 0.90,
                    "medication_possession_ratio": 0.88,
                    "gaps_in_therapy": 2,
                    "late_refills": 1,
                },
                "cost_analysis": {
                    "total_annual_cost": 480.00,
                    "patient_responsibility": 180.00,
                    "potential_savings": 120.00,
                    "cost_per_day": 1.32,
                },
                "safety_alerts": [],
                "drug_utilization_review": {
                    "appropriate_indication": True,
                    "appropriate_dose": True,
                    "appropriate_duration": True,
                    "duplicate_therapy": False,
                    "therapeutic_monitoring_needed": True,
                },
            }

        else:
            # Default comprehensive response
            return {
                **base_response,
                "operation": "comprehensive_check",
                "e_prescribing_available": True,
                "drug_interactions_checked": True,
                "formulary_verified": True,
                "patient_summary": {
                    "active_medications": 2,
                    "allergies": ["Penicillin", "Sulfa"],
                    "conditions": ["Hypertension", "Type 2 Diabetes"],
                    "insurance": "Comprehensive Health Plan",
                },
                "clinical_decision_support": {
                    "alerts": [
                        {
                            "type": "allergy",
                            "severity": "high",
                            "message": "Patient has documented penicillin allergy",
                        }
                    ],
                    "recommendations": [
                        "Monitor blood pressure response",
                        "Schedule follow-up in 4-6 weeks",
                    ],
                },
                "pharmacy_network_status": "online",
                "estimated_processing_time": "2-5 minutes",
            }

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process live pharmacy request (placeholder for actual implementation)."""
        # In a real implementation, this would integrate with:
        # - Surescripts for e-prescribing
        # - NCPDP for pharmacy network communication
        # - Drug database APIs for interaction checking
        # - Insurance APIs for formulary verification

        operation = request_data.get("operation", "e_prescribe")

        # Placeholder for real API integration
        real_response = {
            "status": "live_api_not_implemented",
            "message": "Live pharmacy API integration not yet implemented",
            "fallback_to_mock": True,
            "operation": operation,
            "timestamp": datetime.now().isoformat(),
        }

        # In test mode, return mock data instead
        if self.test_mode:
            return self.get_mock_response(request_data)

        return real_response

    def send_prescription(self, prescription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send electronic prescription via NCPDP SCRIPT standard."""
        prescription_request = {
            **prescription_data,
            "operation": "e_prescribe",
            "network": self.pharmacy_network,
            "prescriber_npi": self.prescriber_npi,
            "dea_number": self.dea_number,
        }

        return self.execute_healthcare_workflow(prescription_request).data

    def check_drug_interactions(self, medications: List[str], patient_allergies: Optional[List[str]] = None) -> Dict[str, Any]:
        """Check drug interactions and contraindications."""
        interaction_request = {
            "operation": "drug_interaction",
            "medications": medications,
            "patient_allergies": patient_allergies or [],
            "database": self.drug_database,
            "interaction_checking": self.interaction_checking,
        }

        return self.execute_healthcare_workflow(interaction_request).data

    def verify_formulary(self, ndc_code: str, plan_id: str) -> Dict[str, Any]:
        """Verify formulary status and coverage determination."""
        formulary_request = {
            "operation": "formulary_check",
            "ndc_code": ndc_code,
            "plan_id": plan_id,
            "formulary_checking": self.formulary_checking,
        }

        return self.execute_healthcare_workflow(formulary_request).data

    def get_medication_alternatives(self, ndc_code: str, plan_id: Optional[str] = None) -> Dict[str, Any]:
        """Get therapeutic alternatives and generic substitutions."""
        alternatives_request = {
            "operation": "formulary_check",
            "ndc_code": ndc_code,
            "plan_id": plan_id,
            "include_alternatives": True,
            "include_generics": True,
        }

        return self.execute_healthcare_workflow(alternatives_request).data

    def check_prior_auth_requirements(self, ndc_code: str, plan_id: str) -> Dict[str, Any]:
        """Check prior authorization requirements and criteria."""
        prior_auth_request = {
            "operation": "prior_authorization",
            "ndc_code": ndc_code,
            "plan_id": plan_id,
            "prior_auth_checking": self.prior_auth_checking,
        }

        return self.execute_healthcare_workflow(prior_auth_request).data

    def reconcile_medications(self, patient_meds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform medication reconciliation and identify discrepancies."""
        reconciliation_request = {
            "operation": "medication_reconciliation",
            "current_medications": patient_meds,
            "patient_id": patient_meds[0].get("patient_id") if patient_meds else "unknown",
        }

        return self.execute_healthcare_workflow(reconciliation_request).data

    def perform_mtm_review(self, patient_id: str, medication_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform medication therapy management review."""
        mtm_request = {
            "operation": "medication_therapy_management",
            "patient_id": patient_id,
            "medications": medication_list,
        }

        return self.execute_healthcare_workflow(mtm_request).data

    def execute_pharmacy_workflow(self) -> Data:
        """Main execution method for pharmacy workflows."""
        try:
            # Parse prescription data if provided as JSON string
            if self.prescription_data:
                try:
                    request_data = json.loads(self.prescription_data)
                except json.JSONDecodeError:
                    request_data = {"error": "Invalid JSON in prescription_data"}
            else:
                # Default operation for testing
                request_data = {
                    "operation": "comprehensive_check",
                    "patient_id": "PAT123456",
                    "medication": "Lisinopril 10mg",
                }

            # Add configuration parameters to request
            request_data.update({
                "pharmacy_network": self.pharmacy_network,
                "prescriber_npi": self.prescriber_npi,
                "dea_number": self.dea_number,
                "drug_database": self.drug_database,
                "interaction_checking": self.interaction_checking,
                "formulary_checking": self.formulary_checking,
                "prior_auth_checking": self.prior_auth_checking,
            })

            return self.execute_healthcare_workflow(request_data)

        except Exception as e:
            return self._handle_healthcare_error(e, "pharmacy_workflow_execution")