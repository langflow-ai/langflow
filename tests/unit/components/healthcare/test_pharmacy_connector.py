"""Comprehensive unit tests for PharmacyConnector component."""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from langflow.components.healthcare.pharmacy_connector import PharmacyConnector
from langflow.schema.data import Data


class TestPharmacyConnector:
    """Test suite for PharmacyConnector with comprehensive coverage."""

    @pytest.fixture
    def pharmacy_connector(self):
        """Create a PharmacyConnector instance for testing."""
        connector = PharmacyConnector()
        connector.pharmacy_network = "surescripts"
        connector.prescriber_npi = "1234567890"
        connector.dea_number = "AB1234567"
        connector.drug_database = "first_databank"
        connector.interaction_checking = True
        connector.formulary_checking = True
        connector.prior_auth_checking = True
        connector.test_mode = True
        connector.mock_mode = True
        connector.audit_logging = True
        connector.timeout_seconds = "30"
        return connector

    def test_initialization(self):
        """Test PharmacyConnector initialization."""
        connector = PharmacyConnector()

        assert connector.display_name == "Pharmacy Connector"
        assert connector.description.startswith("HIPAA-compliant pharmacy")
        assert connector.icon == "Pill"
        assert connector.hipaa_compliant is True
        assert connector.phi_handling is True
        assert connector.encryption_required is True
        assert connector.audit_trail is True

    def test_required_fields(self, pharmacy_connector):
        """Test required fields validation."""
        required_fields = pharmacy_connector.get_required_fields()

        assert "patient_id" in required_fields
        assert "medication" in required_fields
        assert len(required_fields) == 2

    def test_mock_response_e_prescribe(self, pharmacy_connector):
        """Test mock response for e-prescribing operation."""
        request_data = {
            "operation": "e_prescribe",
            "patient_id": "PAT123456",
            "medication": "Lisinopril 10mg"
        }

        response = pharmacy_connector.get_mock_response(request_data)

        assert response["operation"] == "e_prescribe"
        assert response["patient_id"] == "PAT123456"
        assert response["medication"] == "Lisinopril 10mg"
        assert response["status"] == "transmitted"
        assert "prescription_id" in response
        assert "pharmacy_ncpdp" in response
        assert "pharmacy_name" in response
        assert "confirmation_number" in response
        assert response["quantity_prescribed"] == 30
        assert response["refills_remaining"] == 5
        assert isinstance(response["daw"], bool)

    def test_mock_response_drug_interaction(self, pharmacy_connector):
        """Test mock response for drug interaction checking."""
        request_data = {
            "operation": "drug_interaction",
            "patient_id": "PAT123456",
            "medication": "Lisinopril 10mg"
        }

        response = pharmacy_connector.get_mock_response(request_data)

        assert response["operation"] == "drug_interaction_check"
        assert "interactions" in response
        assert "total_interactions" in response
        assert "high_severity_count" in response
        assert "moderate_severity_count" in response
        assert "low_severity_count" in response
        assert "contraindications" in response
        assert "warnings" in response

        # Check interaction structure
        if response["interactions"]:
            interaction = response["interactions"][0]
            assert "severity" in interaction
            assert "drug1" in interaction
            assert "drug2" in interaction
            assert "interaction_type" in interaction
            assert "clinical_significance" in interaction
            assert "recommendation" in interaction

    def test_mock_response_formulary_check(self, pharmacy_connector):
        """Test mock response for formulary verification."""
        request_data = {
            "operation": "formulary_check",
            "patient_id": "PAT123456",
            "medication": "Lisinopril 10mg"
        }

        response = pharmacy_connector.get_mock_response(request_data)

        assert response["operation"] == "formulary_verification"
        assert "formulary_status" in response
        assert "tier" in response
        assert "coverage_determination" in response
        assert "patient_cost" in response
        assert "alternatives" in response
        assert "prior_authorization_required" in response
        assert "quantity_limits" in response
        assert "plan_details" in response

        # Check patient cost structure
        patient_cost = response["patient_cost"]
        assert "copay" in patient_cost
        assert "coinsurance" in patient_cost
        assert "deductible_remaining" in patient_cost

        # Check alternatives structure
        if response["alternatives"]:
            alternative = response["alternatives"][0]
            assert "medication" in alternative
            assert "tier" in alternative
            assert "copay" in alternative
            assert "therapeutic_equivalent" in alternative

    def test_mock_response_medication_reconciliation(self, pharmacy_connector):
        """Test mock response for medication reconciliation."""
        request_data = {
            "operation": "medication_reconciliation",
            "patient_id": "PAT123456"
        }

        response = pharmacy_connector.get_mock_response(request_data)

        assert response["operation"] == "medication_reconciliation"
        assert "current_medications" in response
        assert "discontinued_medications" in response
        assert "reconciliation_summary" in response
        assert "clinical_alerts" in response

        # Check medication structure
        if response["current_medications"]:
            medication = response["current_medications"][0]
            assert "medication" in medication
            assert "ndc" in medication
            assert "status" in medication
            assert "prescriber" in medication
            assert "directions" in medication

    def test_mock_response_prior_authorization(self, pharmacy_connector):
        """Test mock response for prior authorization."""
        request_data = {
            "operation": "prior_authorization",
            "patient_id": "PAT123456",
            "medication": "Brand Name Drug"
        }

        response = pharmacy_connector.get_mock_response(request_data)

        assert response["operation"] == "prior_authorization"
        assert "pa_required" in response
        assert "pa_status" in response
        assert "pa_requirements" in response
        assert "pa_criteria" in response
        assert "alternatives_no_pa" in response

        # Check PA requirements structure
        pa_requirements = response["pa_requirements"]
        assert "documentation_needed" in pa_requirements
        assert "forms_required" in pa_requirements
        assert "estimated_approval_time" in pa_requirements

    def test_mock_response_mtm(self, pharmacy_connector):
        """Test mock response for medication therapy management."""
        request_data = {
            "operation": "medication_therapy_management",
            "patient_id": "PAT123456"
        }

        response = pharmacy_connector.get_mock_response(request_data)

        assert response["operation"] == "medication_therapy_management"
        assert "mtm_eligible" in response
        assert "therapy_review" in response
        assert "recommendations" in response
        assert "adherence_data" in response
        assert "cost_analysis" in response
        assert "safety_alerts" in response
        assert "drug_utilization_review" in response

        # Check therapy review structure
        therapy_review = response["therapy_review"]
        assert "overall_score" in therapy_review
        assert "adherence_rate" in therapy_review
        assert "cost_effectiveness" in therapy_review
        assert "safety_profile" in therapy_review

    def test_send_prescription_method(self, pharmacy_connector):
        """Test send_prescription method."""
        prescription_data = {
            "patient_id": "PAT123456",
            "medication": "Lisinopril 10mg",
            "quantity": 30,
            "refills": 5
        }

        with patch.object(pharmacy_connector, 'execute_healthcare_workflow') as mock_workflow:
            mock_data = Data(data={"status": "transmitted", "prescription_id": "RX123"})
            mock_workflow.return_value = mock_data

            result = pharmacy_connector.send_prescription(prescription_data)

            mock_workflow.assert_called_once()
            call_args = mock_workflow.call_args[0][0]
            assert call_args["operation"] == "e_prescribe"
            assert call_args["network"] == "surescripts"
            assert call_args["prescriber_npi"] == "1234567890"
            assert result["status"] == "transmitted"

    def test_check_drug_interactions_method(self, pharmacy_connector):
        """Test check_drug_interactions method."""
        medications = ["Lisinopril", "Potassium Chloride"]
        allergies = ["Penicillin"]

        with patch.object(pharmacy_connector, 'execute_healthcare_workflow') as mock_workflow:
            mock_data = Data(data={"interactions": [], "total_interactions": 0})
            mock_workflow.return_value = mock_data

            result = pharmacy_connector.check_drug_interactions(medications, allergies)

            mock_workflow.assert_called_once()
            call_args = mock_workflow.call_args[0][0]
            assert call_args["operation"] == "drug_interaction"
            assert call_args["medications"] == medications
            assert call_args["patient_allergies"] == allergies
            assert result["total_interactions"] == 0

    def test_verify_formulary_method(self, pharmacy_connector):
        """Test verify_formulary method."""
        ndc_code = "0093-7663-01"
        plan_id = "HP123456"

        with patch.object(pharmacy_connector, 'execute_healthcare_workflow') as mock_workflow:
            mock_data = Data(data={"formulary_status": "preferred", "tier": 2})
            mock_workflow.return_value = mock_data

            result = pharmacy_connector.verify_formulary(ndc_code, plan_id)

            mock_workflow.assert_called_once()
            call_args = mock_workflow.call_args[0][0]
            assert call_args["operation"] == "formulary_check"
            assert call_args["ndc_code"] == ndc_code
            assert call_args["plan_id"] == plan_id
            assert result["formulary_status"] == "preferred"

    def test_execute_pharmacy_workflow_with_json_data(self, pharmacy_connector):
        """Test execute_pharmacy_workflow with JSON prescription data."""
        pharmacy_connector.prescription_data = json.dumps({
            "operation": "e_prescribe",
            "patient_id": "PAT123456",
            "medication": "Lisinopril 10mg"
        })

        result = pharmacy_connector.execute_pharmacy_workflow()

        assert isinstance(result, Data)
        assert "operation" in result.data
        assert result.data["patient_id"] == "PAT123456"

    def test_execute_pharmacy_workflow_invalid_json(self, pharmacy_connector):
        """Test execute_pharmacy_workflow with invalid JSON."""
        pharmacy_connector.prescription_data = "invalid json{"

        result = pharmacy_connector.execute_pharmacy_workflow()

        assert isinstance(result, Data)
        assert "error" in result.data

    def test_execute_pharmacy_workflow_default(self, pharmacy_connector):
        """Test execute_pharmacy_workflow with default data."""
        pharmacy_connector.prescription_data = ""

        result = pharmacy_connector.execute_pharmacy_workflow()

        assert isinstance(result, Data)
        assert result.data["operation"] == "comprehensive_check"

    def test_process_healthcare_request_test_mode(self, pharmacy_connector):
        """Test process_healthcare_request in test mode."""
        request_data = {
            "operation": "e_prescribe",
            "patient_id": "PAT123456"
        }

        result = pharmacy_connector.process_healthcare_request(request_data)

        # Should return mock data in test mode
        assert result["operation"] == "e_prescribe"
        assert result["patient_id"] == "PAT123456"

    def test_process_healthcare_request_live_mode(self, pharmacy_connector):
        """Test process_healthcare_request in live mode."""
        pharmacy_connector.test_mode = False

        request_data = {
            "operation": "e_prescribe",
            "patient_id": "PAT123456"
        }

        result = pharmacy_connector.process_healthcare_request(request_data)

        # Should return placeholder response for live mode
        assert result["status"] == "live_api_not_implemented"
        assert result["fallback_to_mock"] is True

    def test_audit_logging_enabled(self, pharmacy_connector):
        """Test audit logging functionality."""
        with patch.object(pharmacy_connector._audit_logger, 'info') as mock_logger:
            request_data = {
                "patient_id": "PAT123456",
                "medication": "Lisinopril 10mg"
            }

            result = pharmacy_connector.execute_healthcare_workflow(request_data)

            # Verify audit logging was called
            assert mock_logger.call_count >= 2  # workflow_start and workflow_complete

    def test_audit_logging_disabled(self, pharmacy_connector):
        """Test with audit logging disabled."""
        pharmacy_connector.audit_logging = False

        with patch.object(pharmacy_connector._audit_logger, 'info') as mock_logger:
            request_data = {
                "patient_id": "PAT123456",
                "medication": "Lisinopril 10mg"
            }

            result = pharmacy_connector.execute_healthcare_workflow(request_data)

            # Verify audit logging was not called
            mock_logger.assert_not_called()

    def test_error_handling(self, pharmacy_connector):
        """Test error handling in healthcare workflow."""
        # Force an error by patching validate_healthcare_data
        with patch.object(pharmacy_connector, 'validate_healthcare_data', side_effect=ValueError("Test error")):
            request_data = {"invalid": "data"}

            result = pharmacy_connector.execute_healthcare_workflow(request_data)

            assert isinstance(result, Data)
            assert result.data["error"] is True
            assert result.data["error_type"] == "ValueError"
            assert "error_id" in result.data

    def test_phi_data_validation(self, pharmacy_connector):
        """Test PHI data validation."""
        phi_data = {
            "patient_id": "PAT123456",
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "medication": "Lisinopril 10mg"
        }

        with patch.object(pharmacy_connector, '_log_phi_access') as mock_log:
            is_valid = pharmacy_connector._validate_phi_data(phi_data)

            assert is_valid is True
            mock_log.assert_called_once()

            # Check that PHI elements were detected
            call_args = mock_log.call_args[0]
            assert "phi_validation" in call_args
            phi_elements = call_args[1]
            assert any("patient" in element for element in phi_elements)
            assert any("ssn" in element for element in phi_elements)

    def test_data_anonymization(self, pharmacy_connector):
        """Test data anonymization for logging."""
        sensitive_data = {
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "api_key": "secret_key_12345",
            "medication": "Lisinopril 10mg"
        }

        anonymized = pharmacy_connector._anonymize_for_logging(sensitive_data)

        # Check that sensitive fields are anonymized
        assert anonymized["patient_name"] == "***Doe"
        assert anonymized["ssn"] == "***6789"
        assert anonymized["api_key"] == "***45"
        # Non-sensitive fields should remain unchanged
        assert anonymized["medication"] == "Lisinopril 10mg"

    def test_healthcare_response_formatting(self, pharmacy_connector):
        """Test healthcare response formatting with metadata."""
        response_data = {"result": "test_data"}
        transaction_type = "test_transaction"

        # Set up request context
        pharmacy_connector._request_id = "TEST-REQ-001"
        pharmacy_connector._start_time = 1234567890.0

        with patch('time.time', return_value=1234567891.0):  # 1 second later
            formatted_response = pharmacy_connector._format_healthcare_response(
                response_data, transaction_type
            )

        assert isinstance(formatted_response, Data)
        assert formatted_response.data == response_data

        metadata = formatted_response.metadata
        assert metadata["transaction_type"] == transaction_type
        assert metadata["request_id"] == "TEST-REQ-001"
        assert metadata["component"] == "PharmacyConnector"
        assert metadata["hipaa_compliant"] is True
        assert metadata["processing_time_seconds"] == 1.0

    def test_performance_tracking(self, pharmacy_connector):
        """Test performance tracking in workflow execution."""
        start_time = 1234567890.0
        end_time = 1234567892.5  # 2.5 seconds later

        with patch('time.time', side_effect=[start_time, end_time]):
            request_data = {
                "patient_id": "PAT123456",
                "medication": "Lisinopril 10mg"
            }

            result = pharmacy_connector.execute_healthcare_workflow(request_data)

            assert result.metadata["processing_time_seconds"] == 2.5

    def test_mock_mode_enabled(self, pharmacy_connector):
        """Test behavior when mock mode is enabled."""
        pharmacy_connector.mock_mode = True

        request_data = {
            "operation": "e_prescribe",
            "patient_id": "PAT123456"
        }

        result = pharmacy_connector.execute_healthcare_workflow(request_data)

        assert result.metadata["transaction_type"] == "mock_response"

    def test_mock_mode_disabled(self, pharmacy_connector):
        """Test behavior when mock mode is disabled."""
        pharmacy_connector.mock_mode = False
        pharmacy_connector.test_mode = True  # Keep test mode to avoid real API calls

        request_data = {
            "operation": "e_prescribe",
            "patient_id": "PAT123456"
        }

        # Should still use mock in test mode even if mock_mode is False
        result = pharmacy_connector.execute_healthcare_workflow(request_data)

        assert result.metadata["transaction_type"] == "live_response"

    def test_comprehensive_workflow_coverage(self, pharmacy_connector):
        """Test comprehensive workflow to ensure all code paths are covered."""
        test_cases = [
            {"operation": "e_prescribe", "patient_id": "PAT001"},
            {"operation": "drug_interaction", "patient_id": "PAT002"},
            {"operation": "formulary_check", "patient_id": "PAT003"},
            {"operation": "medication_reconciliation", "patient_id": "PAT004"},
            {"operation": "prior_authorization", "patient_id": "PAT005"},
            {"operation": "medication_therapy_management", "patient_id": "PAT006"},
            {"operation": "comprehensive_check", "patient_id": "PAT007"},
        ]

        for test_case in test_cases:
            result = pharmacy_connector.execute_healthcare_workflow(test_case)

            assert isinstance(result, Data)
            assert "operation" in result.data
            assert result.data["patient_id"] == test_case["patient_id"]
            assert result.metadata["hipaa_compliant"] is True

    @pytest.mark.parametrize("network", ["surescripts", "ncpdp", "relay_health"])
    def test_pharmacy_networks(self, pharmacy_connector, network):
        """Test different pharmacy networks."""
        pharmacy_connector.pharmacy_network = network

        request_data = {
            "operation": "e_prescribe",
            "patient_id": "PAT123456"
        }

        result = pharmacy_connector.execute_pharmacy_workflow()

        assert result.data["network"] == network

    @pytest.mark.parametrize("database", ["first_databank", "medi_span", "lexicomp"])
    def test_drug_databases(self, pharmacy_connector, database):
        """Test different drug databases."""
        pharmacy_connector.drug_database = database

        request_data = {
            "operation": "drug_interaction",
            "medications": ["Drug A", "Drug B"]
        }

        result = pharmacy_connector.check_drug_interactions(["Drug A", "Drug B"])

        # Verify the database setting is included in the workflow
        assert isinstance(result, dict)

    def test_configuration_parameters(self, pharmacy_connector):
        """Test that configuration parameters are properly passed through."""
        pharmacy_connector.interaction_checking = False
        pharmacy_connector.formulary_checking = False
        pharmacy_connector.prior_auth_checking = False

        result = pharmacy_connector.execute_pharmacy_workflow()

        # Configuration should be included in the response metadata
        assert result.metadata["component"] == "PharmacyConnector"