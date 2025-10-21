"""Comprehensive unit tests for ClaimsConnector component."""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from langflow.components.healthcare.claims_connector import ClaimsConnector
from langflow.schema.data import Data


class TestClaimsConnector:
    """Test suite for ClaimsConnector component."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.connector = ClaimsConnector()
        self.connector.clearinghouse = "change_healthcare"
        self.connector.payer_id = "AETNA"
        self.connector.provider_npi = "1234567890"
        self.connector.submitter_id = "SUB123"
        self.connector.authentication_type = "api_key"
        self.connector.test_mode = True
        self.connector.mock_mode = True
        self.connector.audit_logging = True

    def test_component_initialization(self):
        """Test that the component initializes correctly."""
        assert self.connector.display_name == "Claims Connector"
        assert self.connector.description == "Healthcare claims processing integration supporting EDI transactions and prior authorization"
        assert self.connector.icon == "FileInvoice"
        assert self.connector.name == "ClaimsConnector"
        assert self.connector.hipaa_compliant is True
        assert self.connector.phi_handling is True

    def test_required_fields(self):
        """Test that required fields are properly defined."""
        required_fields = self.connector.get_required_fields()
        assert "claim_data" in required_fields

    def test_general_claims_processing(self):
        """Test general claims processing with simple text input."""
        self.connector.claim_data = "general claims request"

        result = self.connector.process_claims()

        assert isinstance(result, Data)
        assert "transaction_type" in result.data
        assert result.data["transaction_type"] == "general_claims_processing"
        assert result.data["status"] == "processed"
        assert result.data["clearinghouse"] == "change_healthcare"
        assert "capabilities" in result.data
        assert "edi_transactions" in result.data["capabilities"]

    def test_837_claim_submission(self):
        """Test 837 EDI claim submission processing."""
        claim_data = {
            "request_type": "claim_submission",
            "patient_id": "PAT123456",
            "provider_npi": "1234567890",
            "procedure_code": "99213",
            "diagnosis_code": "Z00.00"
        }
        self.connector.claim_data = json.dumps(claim_data)

        result = self.connector.process_claims()

        assert isinstance(result, Data)
        assert result.data["transaction_type"] == "837_claim_submission"
        assert "submission_id" in result.data
        assert "control_number" in result.data
        assert result.data["status"] == "accepted"
        assert "edi_segments" in result.data
        assert "ISA" in result.data["edi_segments"]
        assert "compliance" in result.data
        assert result.data["compliance"]["hipaa_version"] == "5010"

    def test_837_keyword_detection(self):
        """Test that 837 keywords trigger claim submission response."""
        self.connector.claim_data = "Submit 837 professional claim"

        result = self.connector.process_claims()

        assert result.data["transaction_type"] == "837_claim_submission"
        assert "control_number" in result.data

    def test_276_claim_status_inquiry(self):
        """Test 276/277 EDI claim status inquiry processing."""
        status_data = {
            "request_type": "claim_status",
            "claim_number": "CLM123456789",
            "patient_control_number": "PAT123456"
        }
        self.connector.claim_data = json.dumps(status_data)

        result = self.connector.process_claims()

        assert result.data["transaction_type"] == "277_claim_status_response"
        assert "claim_status_inquiry" in result.data
        assert "status_code" in result.data["claim_status_inquiry"]
        assert "status_description" in result.data["claim_status_inquiry"]
        assert "provider_info" in result.data
        assert "payer_info" in result.data
        assert "claim_amounts" in result.data

    def test_276_keyword_detection(self):
        """Test that 276 keywords trigger claim status response."""
        self.connector.claim_data = "Check status with 276 inquiry"

        result = self.connector.process_claims()

        assert result.data["transaction_type"] == "277_claim_status_response"

    def test_835_remittance_advice(self):
        """Test 835 EDI Electronic Remittance Advice processing."""
        remittance_data = {
            "request_type": "remittance",
            "check_number": "CHK1234567",
            "payment_amount": "500.00"
        }
        self.connector.claim_data = json.dumps(remittance_data)

        result = self.connector.process_claims()

        assert result.data["transaction_type"] == "835_electronic_remittance_advice"
        assert "remittance_info" in result.data
        assert "check_number" in result.data["remittance_info"]
        assert "payer_info" in result.data
        assert "provider_info" in result.data
        assert "claim_payments" in result.data
        assert "summary" in result.data
        assert result.data["compliance"]["transaction_set"] == "835"

    def test_835_keyword_detection(self):
        """Test that 835 keywords trigger remittance advice response."""
        self.connector.claim_data = "Process 835 remittance advice"

        result = self.connector.process_claims()

        assert result.data["transaction_type"] == "835_electronic_remittance_advice"

    def test_prior_authorization_request(self):
        """Test prior authorization request processing."""
        pa_data = {
            "request_type": "prior_authorization",
            "member_id": "MEM123456789",
            "procedure_code": "99213",
            "diagnosis_code": "I10",
            "provider_npi": "1234567890"
        }
        self.connector.claim_data = json.dumps(pa_data)

        result = self.connector.process_claims()

        assert result.data["transaction_type"] == "prior_authorization_response"
        assert "authorization_info" in result.data
        assert "auth_number" in result.data["authorization_info"]
        assert "status_code" in result.data["authorization_info"]
        assert "patient_info" in result.data
        assert "provider_info" in result.data
        assert "service_info" in result.data
        assert "payer_info" in result.data
        assert "compliance" in result.data
        assert result.data["compliance"]["epa_compliant"] is True

    def test_prior_authorization_keyword_detection(self):
        """Test that prior authorization keywords trigger PA response."""
        self.connector.claim_data = "Submit prior authorization request"

        result = self.connector.process_claims()

        assert result.data["transaction_type"] == "prior_authorization_response"

    def test_prior_authorization_statuses(self):
        """Test that prior authorization responses include various status scenarios."""
        # Run multiple times to test different random statuses
        statuses_found = set()
        for _ in range(20):  # Run enough times to likely hit different statuses
            self.connector.claim_data = "prior authorization request"
            result = self.connector.process_claims()
            status_code = result.data["authorization_info"]["status_code"]
            statuses_found.add(status_code)

        # Should see multiple status codes over multiple runs
        assert len(statuses_found) >= 2

    def test_compliance_metadata(self):
        """Test that all responses include proper compliance metadata."""
        test_cases = [
            "837 claim submission",
            "276 status inquiry",
            "835 remittance advice",
            "prior authorization request"
        ]

        for claim_data in test_cases:
            self.connector.claim_data = claim_data
            result = self.connector.process_claims()

            # Check healthcare metadata
            assert "processing_timestamp" in result.metadata
            assert "request_id" in result.metadata
            assert "component" in result.metadata
            assert result.metadata["hipaa_compliant"] is True
            assert result.metadata["phi_protected"] is True

            # Check compliance in response data
            assert "compliance" in result.data

    def test_realistic_medical_terminology(self):
        """Test that mock responses include realistic medical terminology."""
        self.connector.claim_data = "837 professional claim"
        result = self.connector.process_claims()

        # Check for realistic medical codes and terminology
        assert "provider_npi" in result.data
        assert len(result.data["provider_npi"]) == 10  # NPI is 10 digits
        assert "estimated_processing_days" in result.data
        assert result.data["estimated_processing_days"] >= 5

        # Check EDI segments are present
        edi_segments = result.data["edi_segments"]
        expected_segments = ["ISA", "GS", "ST", "BHT", "NM1", "CLM", "SV1", "SE", "GE", "IEA"]
        for segment in expected_segments:
            assert segment in edi_segments

    def test_claims_status_realistic_codes(self):
        """Test that claim status responses use realistic status codes."""
        self.connector.claim_data = "276 claim status"
        result = self.connector.process_claims()

        status_code = result.data["claim_status_inquiry"]["status_code"]
        valid_codes = ["1", "2", "3", "19", "20", "22"]
        assert status_code in valid_codes

        # Check that amounts are realistic
        amounts = result.data["claim_amounts"]
        assert amounts["total_submitted"] > 0
        assert amounts["allowed_amount"] >= 0
        assert amounts["paid_amount"] >= 0

    def test_remittance_advice_financial_data(self):
        """Test that remittance advice includes realistic financial data."""
        self.connector.claim_data = "835 remittance"
        result = self.connector.process_claims()

        # Check payment information
        remittance_info = result.data["remittance_info"]
        assert "check_number" in remittance_info
        assert "check_amount" in remittance_info
        assert "payment_method" in remittance_info

        # Check service lines have realistic structure
        claim_payments = result.data["claim_payments"]
        assert len(claim_payments) > 0

        payment = claim_payments[0]
        assert "service_lines" in payment
        service_lines = payment["service_lines"]
        assert len(service_lines) > 0

        service_line = service_lines[0]
        assert "procedure_code" in service_line
        assert "line_charge" in service_line
        assert "line_paid" in service_line
        assert "adjustment_code" in service_line

    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        # Test with None claim data
        self.connector.claim_data = None
        result = self.connector.process_claims()

        # Should handle gracefully and return a valid response
        assert isinstance(result, Data)

    def test_json_parsing(self):
        """Test proper JSON parsing of claim data."""
        valid_json = {
            "request_type": "claim_submission",
            "patient_id": "TEST123"
        }
        self.connector.claim_data = json.dumps(valid_json)

        result = self.connector.process_claims()
        assert isinstance(result, Data)

        # Test invalid JSON handling
        self.connector.claim_data = "invalid json {{"
        result = self.connector.process_claims()
        assert isinstance(result, Data)  # Should handle gracefully

    def test_configuration_integration(self):
        """Test that component configuration is properly integrated."""
        claim_data = {"request_type": "general"}
        self.connector.claim_data = json.dumps(claim_data)

        result = self.connector.process_claims()

        # Check that configuration values are included in response
        assert result.data["clearinghouse"] == "change_healthcare"
        integration_info = result.data["integration_info"]
        assert integration_info["test_mode"] is True
        assert integration_info["mock_mode"] is True
        assert integration_info["authentication"] == "api_key"

    def test_audit_logging_integration(self):
        """Test that audit logging is properly integrated."""
        with patch.object(self.connector, '_log_phi_access') as mock_log:
            self.connector.claim_data = "test claim"
            result = self.connector.process_claims()

            # Verify audit logging was called
            assert mock_log.called

    def test_mock_vs_live_mode(self):
        """Test behavior difference between mock and live mode."""
        # Test mock mode
        self.connector.mock_mode = True
        self.connector.claim_data = "test claim"
        mock_result = self.connector.process_claims()

        # Test live mode (simulated)
        self.connector.mock_mode = False
        live_result = self.connector.process_claims()

        # Both should return Data objects but with different content
        assert isinstance(mock_result, Data)
        assert isinstance(live_result, Data)
        assert mock_result.metadata["transaction_type"] == "mock_response"
        assert live_result.metadata["transaction_type"] == "live_response"

    def test_multiple_clearinghouses(self):
        """Test support for multiple clearinghouses."""
        clearinghouses = ["change_healthcare", "availity", "relay_health", "navinet"]

        for clearinghouse in clearinghouses:
            self.connector.clearinghouse = clearinghouse
            self.connector.claim_data = "test claim"

            result = self.connector.process_claims()
            assert result.data["clearinghouse"] == clearinghouse

    def test_healthcare_workflow_execution(self):
        """Test the healthcare workflow execution with audit trail."""
        self.connector.claim_data = "test healthcare workflow"

        with patch.object(self.connector, '_generate_request_id', return_value="TEST-REQ-123"):
            result = self.connector.process_claims()

            assert result.metadata["request_id"] == "TEST-REQ-123"
            assert "processing_time_seconds" in result.metadata

    def test_phi_data_validation(self):
        """Test PHI data validation and handling."""
        phi_data = {
            "patient_id": "PAT123",
            "patient_name": "Test Patient",
            "ssn": "123-45-6789",
            "dob": "1980-01-01"
        }
        self.connector.claim_data = json.dumps(phi_data)

        result = self.connector.process_claims()

        # Should process successfully with PHI protection
        assert isinstance(result, Data)
        assert result.metadata["phi_protected"] is True

    def test_performance_metrics(self):
        """Test that performance metrics are included in responses."""
        self.connector.claim_data = "performance test"

        result = self.connector.process_claims()

        # Check for performance metadata
        assert "processing_time_seconds" in result.metadata
        assert isinstance(result.metadata["processing_time_seconds"], (int, float))
        assert result.metadata["processing_time_seconds"] >= 0

    def test_component_inputs_and_outputs(self):
        """Test that component inputs and outputs are properly defined."""
        # Check inputs
        input_names = [inp.name for inp in self.connector.inputs]
        expected_inputs = [
            "api_key", "client_id", "client_secret", "test_mode", "mock_mode",
            "audit_logging", "timeout_seconds", "clearinghouse", "payer_id",
            "provider_npi", "submitter_id", "authentication_type", "claim_data"
        ]

        for expected_input in expected_inputs:
            assert expected_input in input_names

        # Check outputs
        output_names = [out.name for out in self.connector.outputs]
        assert "claims_response" in output_names

    def test_tool_mode_compatibility(self):
        """Test that component is compatible with tool mode."""
        # Check that appropriate inputs have tool_mode=True
        tool_mode_inputs = [
            inp for inp in self.connector.inputs
            if hasattr(inp, 'tool_mode') and inp.tool_mode
        ]

        # Should have several tool-mode compatible inputs
        assert len(tool_mode_inputs) > 5

        tool_mode_names = [inp.name for inp in tool_mode_inputs]
        assert "claim_data" in tool_mode_names
        assert "clearinghouse" in tool_mode_names
        assert "test_mode" in tool_mode_names


class TestClaimsConnectorIntegration:
    """Integration tests for ClaimsConnector with other healthcare components."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.connector = ClaimsConnector()
        self.connector.mock_mode = True
        self.connector.test_mode = True

    def test_edi_transaction_workflow(self):
        """Test complete EDI transaction workflow."""
        # Simulate a complete workflow: submission -> status check -> remittance
        workflows = [
            ("Submit 837 claim", "837_claim_submission"),
            ("Check 276 status", "277_claim_status_response"),
            ("Process 835 remittance", "835_electronic_remittance_advice")
        ]

        for claim_data, expected_type in workflows:
            self.connector.claim_data = claim_data
            result = self.connector.process_claims()

            assert result.data["transaction_type"] == expected_type
            assert "compliance" in result.data
            assert result.data["compliance"]["hipaa_version"] == "5010"

    def test_prior_authorization_workflow(self):
        """Test complete prior authorization workflow."""
        pa_requests = [
            "Submit prior authorization for surgery",
            "Check prior auth status",
            "Appeal prior authorization denial"
        ]

        for request in pa_requests:
            self.connector.claim_data = request
            result = self.connector.process_claims()

            assert result.data["transaction_type"] == "prior_authorization_response"
            assert "authorization_info" in result.data
            assert result.data["compliance"]["epa_compliant"] is True


if __name__ == "__main__":
    pytest.main([__file__])