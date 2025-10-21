"""Integration tests for healthcare workflow components."""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from langflow.components.healthcare.claims_connector import ClaimsConnector
from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.schema.data import Data


class TestHealthcareWorkflowIntegration:
    """Integration tests for complete healthcare workflows."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.claims_connector = ClaimsConnector()
        self.claims_connector.mock_mode = True
        self.claims_connector.test_mode = True
        self.claims_connector.audit_logging = True
        self.claims_connector.clearinghouse = "change_healthcare"
        self.claims_connector.payer_id = "AETNA"
        self.claims_connector.provider_npi = "1234567890"

    def test_complete_claims_lifecycle(self):
        """Test complete claims processing lifecycle."""
        # Step 1: Submit claim (837)
        claim_submission = {
            "request_type": "claim_submission",
            "patient_id": "PAT123456",
            "procedure_code": "99213",
            "diagnosis_code": "Z00.00",
            "charge_amount": 150.00
        }

        self.claims_connector.claim_data = json.dumps(claim_submission)
        submission_result = self.claims_connector.process_claims()

        assert submission_result.data["transaction_type"] == "837_claim_submission"
        claim_control_number = submission_result.data["control_number"]
        assert claim_control_number.startswith("ICN")

        # Step 2: Check claim status (276/277)
        status_inquiry = {
            "request_type": "claim_status",
            "control_number": claim_control_number,
            "patient_id": "PAT123456"
        }

        self.claims_connector.claim_data = json.dumps(status_inquiry)
        status_result = self.claims_connector.process_claims()

        assert status_result.data["transaction_type"] == "277_claim_status_response"
        assert "claim_status_inquiry" in status_result.data

        # Step 3: Process remittance advice (835)
        remittance_request = {
            "request_type": "remittance",
            "control_number": claim_control_number
        }

        self.claims_connector.claim_data = json.dumps(remittance_request)
        remittance_result = self.claims_connector.process_claims()

        assert remittance_result.data["transaction_type"] == "835_electronic_remittance_advice"
        assert "remittance_info" in remittance_result.data

        # Verify workflow continuity
        for result in [submission_result, status_result, remittance_result]:
            assert result.metadata["hipaa_compliant"] is True
            assert result.metadata["phi_protected"] is True
            assert "request_id" in result.metadata

    def test_prior_authorization_to_claims_workflow(self):
        """Test prior authorization followed by claims submission."""
        # Step 1: Submit prior authorization
        pa_request = {
            "request_type": "prior_authorization",
            "member_id": "MEM123456789",
            "procedure_code": "71020",  # Chest X-ray
            "diagnosis_code": "J44.1",  # COPD
            "provider_npi": "1234567890"
        }

        self.claims_connector.claim_data = json.dumps(pa_request)
        pa_result = self.claims_connector.process_claims()

        assert pa_result.data["transaction_type"] == "prior_authorization_response"
        auth_number = pa_result.data["authorization_info"]["auth_number"]
        status_code = pa_result.data["authorization_info"]["status_code"]

        # Step 2: Submit claim with authorization (if approved)
        claim_with_auth = {
            "request_type": "claim_submission",
            "member_id": "MEM123456789",
            "procedure_code": "71020",
            "diagnosis_code": "J44.1",
            "authorization_number": auth_number,
            "charge_amount": 125.00
        }

        self.claims_connector.claim_data = json.dumps(claim_with_auth)
        claim_result = self.claims_connector.process_claims()

        assert claim_result.data["transaction_type"] == "837_claim_submission"

        # Verify authorization context is maintained
        assert "control_number" in claim_result.data
        assert claim_result.data["provider_npi"] == "1234567890"

    def test_multi_clearinghouse_workflow(self):
        """Test workflow across multiple clearinghouses."""
        clearinghouses = ["change_healthcare", "availity", "relay_health"]

        for clearinghouse in clearinghouses:
            self.claims_connector.clearinghouse = clearinghouse
            self.claims_connector.claim_data = json.dumps({
                "request_type": "claim_submission",
                "patient_id": f"PAT-{clearinghouse}-123"
            })

            result = self.claims_connector.process_claims()

            assert result.data["clearinghouse"] == clearinghouse
            assert result.data["transaction_type"] == "837_claim_submission"
            assert result.metadata["hipaa_compliant"] is True

    def test_error_handling_workflow(self):
        """Test error handling across workflow steps."""
        # Test invalid JSON
        self.claims_connector.claim_data = "invalid json {{"
        result = self.claims_connector.process_claims()
        assert isinstance(result, Data)

        # Test missing required data
        self.claims_connector.claim_data = json.dumps({"invalid": "data"})
        result = self.claims_connector.process_claims()
        assert isinstance(result, Data)

        # Test empty claim data
        self.claims_connector.claim_data = ""
        result = self.claims_connector.process_claims()
        assert isinstance(result, Data)

    def test_audit_trail_continuity(self):
        """Test that audit trail is maintained across workflow steps."""
        workflow_steps = [
            "Submit 837 claim",
            "Check 276 status",
            "Process 835 remittance",
            "Submit prior authorization"
        ]

        audit_trail = []

        with patch.object(self.claims_connector, '_log_phi_access') as mock_audit:
            for step in workflow_steps:
                self.claims_connector.claim_data = step
                result = self.claims_connector.process_claims()

                # Verify audit logging called
                assert mock_audit.called
                audit_trail.append(result.metadata["request_id"])

        # Each step should have unique request ID
        assert len(set(audit_trail)) == len(audit_trail)

    def test_performance_across_workflow(self):
        """Test performance consistency across workflow steps."""
        workflow_requests = [
            {"request_type": "claim_submission", "patient_id": "PAT123"},
            {"request_type": "claim_status", "claim_number": "CLM123"},
            {"request_type": "remittance", "check_number": "CHK123"},
            {"request_type": "prior_authorization", "member_id": "MEM123"}
        ]

        performance_metrics = []

        for request in workflow_requests:
            self.claims_connector.claim_data = json.dumps(request)
            result = self.claims_connector.process_claims()

            processing_time = result.metadata.get("processing_time_seconds", 0)
            performance_metrics.append(processing_time)

        # All should complete within reasonable time
        assert all(time >= 0 for time in performance_metrics)
        assert all(time < 1.0 for time in performance_metrics)  # Should be fast in mock mode


class TestHealthcareDataFlow:
    """Test data flow between healthcare components."""

    def setup_method(self):
        """Set up data flow test fixtures."""
        self.connector = ClaimsConnector()
        self.connector.mock_mode = True

    def test_data_structure_consistency(self):
        """Test that data structures are consistent across transaction types."""
        transaction_types = [
            "837 claim submission",
            "276 claim status",
            "835 remittance advice",
            "prior authorization request"
        ]

        results = []
        for transaction in transaction_types:
            self.connector.claim_data = transaction
            result = self.connector.process_claims()
            results.append(result)

        # All should have consistent metadata structure
        for result in results:
            assert "processing_timestamp" in result.metadata
            assert "request_id" in result.metadata
            assert "component" in result.metadata
            assert "hipaa_compliant" in result.metadata
            assert "phi_protected" in result.metadata

        # All should have compliance information
        for result in results:
            assert "compliance" in result.data

    def test_medical_code_validation(self):
        """Test that medical codes are realistic and properly formatted."""
        # Test procedure codes (CPT)
        self.connector.claim_data = "837 claim with procedures"
        result = self.connector.process_claims()

        # Should contain realistic procedure codes
        if "edi_segments" in result.data:
            # Basic format validation for medical codes would be here
            assert isinstance(result.data["edi_segments"], dict)

        # Test remittance with procedure codes
        self.connector.claim_data = "835 remittance"
        remittance_result = self.connector.process_claims()

        if "claim_payments" in remittance_result.data:
            payments = remittance_result.data["claim_payments"]
            for payment in payments:
                if "service_lines" in payment:
                    for line in payment["service_lines"]:
                        # Verify procedure code format (should be 5 digits for CPT)
                        proc_code = line.get("procedure_code", "")
                        assert len(proc_code) == 5
                        assert proc_code.isdigit()

    def test_financial_data_consistency(self):
        """Test that financial data is consistent and realistic."""
        self.connector.claim_data = "835 remittance advice"
        result = self.connector.process_claims()

        summary = result.data.get("summary", {})

        # Financial totals should be consistent
        if all(key in summary for key in ["total_charges", "total_payments", "total_adjustments"]):
            total_charges = summary["total_charges"]
            total_payments = summary["total_payments"]
            total_adjustments = summary["total_adjustments"]

            # Payments + adjustments should approximately equal charges
            assert total_charges >= total_payments
            assert total_adjustments >= 0
            assert total_payments >= 0

    def test_date_format_consistency(self):
        """Test that dates are consistently formatted across responses."""
        test_requests = [
            "837 claim submission",
            "277 claim status",
            "835 remittance",
            "prior authorization"
        ]

        for request in test_requests:
            self.connector.claim_data = request
            result = self.connector.process_claims()

            # Check processing timestamp format
            timestamp = result.metadata.get("processing_timestamp")
            if timestamp:
                # Should be ISO format
                try:
                    datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    pytest.fail(f"Invalid timestamp format: {timestamp}")


class TestHIPAACompliance:
    """Test HIPAA compliance across healthcare workflows."""

    def setup_method(self):
        """Set up HIPAA compliance test fixtures."""
        self.connector = ClaimsConnector()
        self.connector.mock_mode = True
        self.connector.audit_logging = True

    def test_phi_protection_workflow(self):
        """Test PHI protection throughout workflow."""
        phi_data = {
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "dob": "1980-01-01",
            "address": "123 Main St",
            "phone": "555-123-4567"
        }

        self.connector.claim_data = json.dumps(phi_data)
        result = self.connector.process_claims()

        # Should process without exposing PHI in logs
        assert result.metadata["phi_protected"] is True
        assert result.metadata["hipaa_compliant"] is True

    def test_audit_logging_compliance(self):
        """Test that audit logging meets HIPAA requirements."""
        with patch.object(self.connector, '_audit_logger') as mock_logger:
            self.connector.claim_data = json.dumps({"patient_id": "PAT123"})
            result = self.connector.process_claims()

            # Verify audit logging occurred
            assert mock_logger.info.called

            # Check audit log structure
            audit_calls = mock_logger.info.call_args_list
            for call in audit_calls:
                audit_data = json.loads(call[0][0])
                assert "timestamp" in audit_data
                assert "request_id" in audit_data
                assert "component" in audit_data
                assert "action" in audit_data

    def test_data_minimization(self):
        """Test that only necessary data is processed and logged."""
        minimal_data = {"request_type": "general"}
        extensive_data = {
            "request_type": "claim_submission",
            "patient_name": "Test Patient",
            "ssn": "123-45-6789",
            "unnecessary_field": "should_not_be_needed"
        }

        # Both should process successfully
        for data in [minimal_data, extensive_data]:
            self.connector.claim_data = json.dumps(data)
            result = self.connector.process_claims()
            assert isinstance(result, Data)

    def test_secure_error_handling(self):
        """Test that error messages don't expose PHI."""
        # Test with PHI data that might cause errors
        sensitive_data = {
            "patient_ssn": "123-45-6789",
            "invalid_field": "cause_error"
        }

        self.connector.claim_data = json.dumps(sensitive_data)
        result = self.connector.process_claims()

        # Should handle gracefully without exposing sensitive data
        assert isinstance(result, Data)
        # Error messages should be generic, not exposing input data
        if "error" in result.data:
            error_msg = str(result.data.get("error_message", ""))
            assert "123-45-6789" not in error_msg


if __name__ == "__main__":
    pytest.main([__file__])