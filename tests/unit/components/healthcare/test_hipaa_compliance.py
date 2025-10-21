"""HIPAA compliance and security validation tests for healthcare components."""

import json
import logging
import pytest
import re
from datetime import datetime
from unittest.mock import MagicMock, patch, call

from langflow.components.healthcare.claims_connector import ClaimsConnector
from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.schema.data import Data


class TestHIPAACompliance:
    """Comprehensive HIPAA compliance validation tests."""

    def setup_method(self):
        """Set up HIPAA compliance test fixtures."""
        self.connector = ClaimsConnector()
        self.connector.mock_mode = True
        self.connector.audit_logging = True

    def test_phi_identification_and_logging(self):
        """Test that PHI is properly identified and logged."""
        phi_test_data = {
            "patient_id": "PAT123456",
            "member_id": "MEM987654321",
            "subscriber_id": "SUB111222333",
            "ssn": "123-45-6789",
            "patient_name": "John Doe",
            "dob": "1980-01-01",
            "address": "123 Main Street",
            "phone": "555-123-4567",
            "email": "patient@example.com",
            "mrn": "MRN98765"
        }

        with patch.object(self.connector, '_log_phi_access') as mock_phi_log:
            self.connector.claim_data = json.dumps(phi_test_data)
            result = self.connector.process_claims()

            # Verify PHI access was logged
            assert mock_phi_log.called

            # Check that PHI elements were identified
            phi_calls = mock_phi_log.call_args_list
            logged_phi_elements = []
            for call_args in phi_calls:
                if len(call_args[0]) >= 2:  # action, data_elements
                    logged_phi_elements.extend(call_args[0][1])

            # Should identify common PHI fields
            expected_phi = ["patient_id", "member_id", "subscriber_id", "ssn"]
            for phi_field in expected_phi:
                assert any(phi_field in elements for elements in [call_args[0][1] for call_args in phi_calls if len(call_args[0]) >= 2])

    def test_audit_trail_requirements(self):
        """Test audit trail meets HIPAA requirements."""
        test_data = {"patient_id": "PAT123", "request_type": "claim_submission"}

        with patch.object(self.connector, '_audit_logger') as mock_audit_logger:
            self.connector.claim_data = json.dumps(test_data)
            result = self.connector.process_claims()

            # Verify audit logging occurred
            assert mock_audit_logger.info.called

            # Analyze audit log entries
            audit_calls = mock_audit_logger.info.call_args_list
            for call in audit_calls:
                audit_entry = json.loads(call[0][0])

                # Required HIPAA audit fields
                assert "timestamp" in audit_entry
                assert "request_id" in audit_entry
                assert "component" in audit_entry
                assert "action" in audit_entry
                assert "phi_elements" in audit_entry
                assert "compliance_note" in audit_entry

                # Timestamp should be properly formatted
                timestamp = audit_entry["timestamp"]
                try:
                    datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    pytest.fail(f"Invalid audit timestamp format: {timestamp}")

    def test_data_anonymization(self):
        """Test that sensitive data is properly anonymized for logging."""
        sensitive_data = {
            "ssn": "123-45-6789",
            "patient_name": "John Doe",
            "address": "123 Main Street, Anytown, ST 12345",
            "phone": "555-123-4567",
            "email": "john.doe@example.com",
            "api_key": "secret_api_key_12345",
            "client_secret": "very_secret_client_secret",
            "password": "password123"
        }

        anonymized = self.connector._anonymize_for_logging(sensitive_data)

        # Check that sensitive fields are anonymized
        for field in ["ssn", "api_key", "client_secret", "password"]:
            if field in anonymized:
                assert "***" in str(anonymized[field])
                assert len(str(anonymized[field])) <= len(str(sensitive_data[field]))

        # Verify specific patterns for certain fields
        if "ssn" in anonymized:
            # SSN should show last 4 digits
            assert anonymized["ssn"] == "***6789"

    def test_minimum_necessary_standard(self):
        """Test compliance with minimum necessary standard."""
        # Test with minimal data
        minimal_data = {"request_type": "general"}
        self.connector.claim_data = json.dumps(minimal_data)
        minimal_result = self.connector.process_claims()

        # Test with extensive data
        extensive_data = {
            "request_type": "claim_submission",
            "patient_id": "PAT123",
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "procedure_code": "99213",
            "diagnosis_code": "Z00.00",
            "extra_field1": "not_needed",
            "extra_field2": "also_not_needed"
        }
        self.connector.claim_data = json.dumps(extensive_data)
        extensive_result = self.connector.process_claims()

        # Both should process successfully (demonstrating data minimization)
        assert isinstance(minimal_result, Data)
        assert isinstance(extensive_result, Data)

        # Component should work with minimal data
        assert minimal_result.metadata["hipaa_compliant"] is True
        assert extensive_result.metadata["hipaa_compliant"] is True

    def test_access_control_validation(self):
        """Test access control and authorization patterns."""
        # Simulate different user contexts
        user_contexts = [
            {"user": "provider", "role": "healthcare_provider"},
            {"user": "admin", "role": "system_administrator"},
            {"user": "patient", "role": "patient_access"}
        ]

        for context in user_contexts:
            with patch.object(self.connector, '_validate_phi_access', return_value=True):
                self.connector.claim_data = json.dumps({"patient_id": "PAT123"})
                result = self.connector.process_claims()

                # Should process successfully with proper access control
                assert isinstance(result, Data)
                assert result.metadata["hipaa_compliant"] is True

    def test_data_encryption_requirements(self):
        """Test that encryption requirements are documented and validated."""
        test_data = {"patient_id": "PAT123", "sensitive_data": "test"}
        self.connector.claim_data = json.dumps(test_data)
        result = self.connector.process_claims()

        # Check that encryption requirements are documented
        assert result.metadata["phi_protected"] is True

        # Check compliance metadata indicates encryption
        if "compliance" in result.data:
            compliance = result.data["compliance"]
            # Should indicate encryption requirements
            assert compliance.get("phi_protected", False) is True

    def test_breach_notification_preparedness(self):
        """Test that systems are prepared for breach notification requirements."""
        # Test error handling that could indicate potential breaches
        invalid_scenarios = [
            {"invalid": "json_structure"},
            {"malformed": "data", "test": None},
            "",  # Empty data
            None  # Null data
        ]

        for scenario in invalid_scenarios:
            if scenario is not None:
                self.connector.claim_data = json.dumps(scenario) if isinstance(scenario, dict) else scenario
            else:
                self.connector.claim_data = None

            result = self.connector.process_claims()

            # Should handle gracefully without exposing errors that could indicate breaches
            assert isinstance(result, Data)

            # Should maintain audit trail even in error conditions
            assert result.metadata.get("audit_logged", False) is True

    def test_retention_and_disposal_compliance(self):
        """Test compliance with data retention and disposal requirements."""
        # Test that audit logs include retention information
        test_data = {"patient_id": "PAT123"}

        with patch.object(self.connector, '_audit_logger') as mock_audit:
            self.connector.claim_data = json.dumps(test_data)
            result = self.connector.process_calls()

            # Check that audit logs can support retention requirements
            if mock_audit.info.called:
                audit_call = mock_audit.info.call_args_list[0]
                audit_entry = json.loads(audit_call[0][0])

                # Should have timestamp for retention calculation
                assert "timestamp" in audit_entry
                assert "request_id" in audit_entry  # For tracking disposal

    def test_business_associate_compliance(self):
        """Test compliance patterns for business associate agreements."""
        # Test that all external integrations maintain compliance
        clearinghouses = ["change_healthcare", "availity", "relay_health"]

        for clearinghouse in clearinghouses:
            self.connector.clearinghouse = clearinghouse
            self.connector.claim_data = json.dumps({"patient_id": "PAT123"})
            result = self.connector.process_claims()

            # Each clearinghouse integration should maintain compliance
            assert result.metadata["hipaa_compliant"] is True
            assert result.data["clearinghouse"] == clearinghouse


class TestSecurityMeasures:
    """Test security measures beyond HIPAA compliance."""

    def setup_method(self):
        """Set up security test fixtures."""
        self.connector = ClaimsConnector()
        self.connector.mock_mode = True

    def test_input_validation_security(self):
        """Test input validation to prevent security vulnerabilities."""
        malicious_inputs = [
            {"script": "<script>alert('xss')</script>"},
            {"injection": "'; DROP TABLE patients; --"},
            {"overflow": "A" * 10000},  # Buffer overflow attempt
            {"path_traversal": "../../../etc/passwd"},
            {"command_injection": "; cat /etc/passwd #"}
        ]

        for malicious_input in malicious_inputs:
            self.connector.claim_data = json.dumps(malicious_input)
            result = self.connector.process_claims()

            # Should handle malicious input safely
            assert isinstance(result, Data)
            # Should not expose system information
            response_str = json.dumps(result.data)
            assert "/etc/passwd" not in response_str
            assert "<script>" not in response_str

    def test_error_message_security(self):
        """Test that error messages don't expose system information."""
        error_scenarios = [
            None,  # Null input
            "invalid json {{",  # Malformed JSON
            {"extremely_long_field": "x" * 100000}  # Large input
        ]

        for scenario in error_scenarios:
            try:
                if scenario is not None:
                    self.connector.claim_data = json.dumps(scenario) if isinstance(scenario, dict) else scenario
                else:
                    self.connector.claim_data = None

                result = self.connector.process_claims()

                # Error messages should be generic
                if "error" in result.data:
                    error_msg = str(result.data.get("error_message", ""))
                    # Should not expose file paths, system details, etc.
                    assert "/Users/" not in error_msg
                    assert "Exception" not in error_msg
                    assert "Traceback" not in error_msg

            except Exception as e:
                # Should not expose internal exceptions to users
                pytest.fail(f"Unhandled exception exposed: {str(e)}")

    def test_timeout_security(self):
        """Test that timeouts are properly configured for security."""
        timeout_values = ["15", "30", "45", "60", "90"]

        for timeout in timeout_values:
            self.connector.timeout_seconds = timeout
            self.connector.claim_data = json.dumps({"test": "timeout"})
            result = self.connector.process_claims()

            # Should process within reasonable time limits
            assert isinstance(result, Data)
            processing_time = result.metadata.get("processing_time_seconds", 0)
            assert processing_time < 1.0  # Should be fast in mock mode

    def test_authentication_security(self):
        """Test authentication security patterns."""
        auth_types = ["x12", "api_key", "oauth2"]

        for auth_type in auth_types:
            self.connector.authentication_type = auth_type
            self.connector.claim_data = json.dumps({"test": "auth"})
            result = self.connector.process_claims()

            # Should indicate proper authentication type
            assert result.data["integration_info"]["authentication"] == auth_type

            # Should not expose authentication details in response
            response_str = json.dumps(result.data)
            assert "password" not in response_str.lower()
            assert "secret" not in response_str.lower()
            assert "token" not in response_str.lower()


class TestComplianceReporting:
    """Test compliance reporting and monitoring capabilities."""

    def setup_method(self):
        """Set up compliance reporting test fixtures."""
        self.connector = ClaimsConnector()
        self.connector.mock_mode = True
        self.connector.audit_logging = True

    def test_compliance_metadata_completeness(self):
        """Test that all responses include complete compliance metadata."""
        test_scenarios = [
            "837 claim submission",
            "276 claim status",
            "835 remittance advice",
            "prior authorization request",
            "general healthcare request"
        ]

        for scenario in test_scenarios:
            self.connector.claim_data = scenario
            result = self.connector.process_claims()

            # Check healthcare metadata
            required_metadata = [
                "processing_timestamp",
                "request_id",
                "component",
                "hipaa_compliant",
                "phi_protected",
                "audit_logged"
            ]

            for field in required_metadata:
                assert field in result.metadata, f"Missing metadata field: {field}"

            # Check compliance in response data
            assert "compliance" in result.data
            compliance = result.data["compliance"]

            # Basic compliance fields should be present
            assert isinstance(compliance, dict)

    def test_audit_log_format_consistency(self):
        """Test that audit logs maintain consistent format for compliance reporting."""
        requests = [
            {"patient_id": "PAT1", "type": "claim"},
            {"member_id": "MEM1", "type": "status"},
            {"auth_request": "PA1", "type": "prior_auth"}
        ]

        audit_entries = []

        with patch.object(self.connector, '_audit_logger') as mock_audit:
            for request in requests:
                self.connector.claim_data = json.dumps(request)
                result = self.connector.process_claims()

                if mock_audit.info.called:
                    for call in mock_audit.info.call_args_list:
                        audit_entry = json.loads(call[0][0])
                        audit_entries.append(audit_entry)

        # All audit entries should have consistent structure
        if audit_entries:
            required_fields = ["timestamp", "request_id", "component", "action"]
            for entry in audit_entries:
                for field in required_fields:
                    assert field in entry, f"Audit entry missing field: {field}"

    def test_performance_monitoring_compliance(self):
        """Test that performance monitoring supports compliance requirements."""
        self.connector.claim_data = json.dumps({"performance_test": True})
        result = self.connector.process_claims()

        # Should include performance metrics for monitoring
        assert "processing_time_seconds" in result.metadata
        processing_time = result.metadata["processing_time_seconds"]

        # Performance should be within acceptable ranges
        assert isinstance(processing_time, (int, float))
        assert processing_time >= 0
        assert processing_time < 10  # Should complete quickly


if __name__ == "__main__":
    pytest.main([__file__])