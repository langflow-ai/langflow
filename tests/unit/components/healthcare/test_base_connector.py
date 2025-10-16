"""Unit tests for HealthcareConnectorBase class."""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.schema.data import Data


class MockHealthcareConnector(HealthcareConnectorBase):
    """Mock implementation of HealthcareConnectorBase for testing."""

    def get_mock_response(self, request_data: dict) -> dict:
        """Mock implementation of get_mock_response."""
        return {
            "mock": True,
            "patient_id": request_data.get("patient_id", "TEST123"),
            "operation": request_data.get("operation", "test"),
            "timestamp": datetime.now().isoformat(),
        }

    def process_healthcare_request(self, request_data: dict) -> dict:
        """Mock implementation of process_healthcare_request."""
        return {
            "live": True,
            "patient_id": request_data.get("patient_id", "TEST123"),
            "operation": request_data.get("operation", "test"),
            "timestamp": datetime.now().isoformat(),
        }


class TestHealthcareConnectorBase:
    """Test suite for HealthcareConnectorBase class."""

    @pytest.fixture
    def healthcare_connector(self):
        """Create a mock healthcare connector for testing."""
        connector = MockHealthcareConnector()
        connector.test_mode = True
        connector.mock_mode = True
        connector.audit_logging = True
        connector.timeout_seconds = "30"
        return connector

    def test_initialization(self):
        """Test healthcare connector initialization."""
        connector = MockHealthcareConnector()

        assert connector.hipaa_compliant is True
        assert connector.phi_handling is True
        assert connector.encryption_required is True
        assert connector.audit_trail is True
        assert hasattr(connector, '_audit_logger')
        assert connector._start_time is None
        assert connector._request_id is None

    def test_audit_logger_setup(self, healthcare_connector):
        """Test audit logger setup."""
        logger = healthcare_connector._audit_logger

        assert logger is not None
        assert logger.name.endswith('MockHealthcareConnector')
        assert logger.level <= 20  # INFO level or lower

    def test_request_id_generation(self, healthcare_connector):
        """Test request ID generation."""
        request_id = healthcare_connector._generate_request_id()

        assert request_id.startswith("HC-")
        assert len(request_id.split("-")) == 3  # HC-timestamp-hash
        assert request_id != healthcare_connector._generate_request_id()  # Should be unique

    def test_phi_access_logging(self, healthcare_connector):
        """Test PHI access logging."""
        with patch.object(healthcare_connector._audit_logger, 'info') as mock_logger:
            healthcare_connector._log_phi_access(
                "test_action",
                ["patient_id", "patient_name"],
                "TEST-REQ-001"
            )

            mock_logger.assert_called_once()
            log_call = mock_logger.call_args[0][0]
            log_data = json.loads(log_call)

            assert log_data["action"] == "test_action"
            assert log_data["phi_elements"] == ["patient_id", "patient_name"]
            assert log_data["request_id"] == "TEST-REQ-001"
            assert log_data["compliance_note"] == "PHI access logged for HIPAA compliance"

    def test_phi_access_logging_disabled(self, healthcare_connector):
        """Test PHI access logging when disabled."""
        healthcare_connector.audit_logging = False

        with patch.object(healthcare_connector._audit_logger, 'info') as mock_logger:
            healthcare_connector._log_phi_access("test_action", ["patient_id"])

            mock_logger.assert_not_called()

    def test_phi_data_validation(self, healthcare_connector):
        """Test PHI data validation."""
        phi_data = {
            "patient_id": "PAT123456",
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "dob": "1980-01-01",
            "address": "123 Main St",
            "phone": "555-1234",
            "email": "john@example.com",
            "mrn": "MRN123456",
            "normal_field": "not_phi"
        }

        with patch.object(healthcare_connector, '_log_phi_access') as mock_log:
            result = healthcare_connector._validate_phi_data(phi_data)

            assert result is True
            mock_log.assert_called_once()

            # Check that PHI fields were detected
            call_args = mock_log.call_args[0]
            assert call_args[0] == "phi_validation"
            phi_elements = call_args[1]
            assert "patient_id" in phi_elements
            assert "ssn" in phi_elements
            assert "dob" in phi_elements

    def test_phi_data_validation_no_phi(self, healthcare_connector):
        """Test PHI data validation with no PHI elements."""
        non_phi_data = {
            "operation": "test",
            "medication": "Aspirin",
            "dosage": "81mg"
        }

        with patch.object(healthcare_connector, '_log_phi_access') as mock_log:
            result = healthcare_connector._validate_phi_data(non_phi_data)

            assert result is True
            mock_log.assert_not_called()

    def test_data_anonymization(self, healthcare_connector):
        """Test data anonymization for logging."""
        sensitive_data = {
            "ssn": "123-45-6789",
            "patient_name": "John Doe",
            "address": "123 Main Street",
            "phone": "555-123-4567",
            "email": "john.doe@example.com",
            "api_key": "super_secret_key_12345",
            "client_secret": "client_secret_67890",
            "password": "password123",
            "token": "bearer_token_xyz",
            "medication": "Lisinopril 10mg",  # Not sensitive
            "short_field": "ab"  # Too short to anonymize
        }

        anonymized = healthcare_connector._anonymize_for_logging(sensitive_data)

        # Check sensitive fields are anonymized (last 4 characters shown)
        assert anonymized["ssn"] == "***6789"
        assert anonymized["patient_name"] == "***Doe"
        assert anonymized["address"] == "***reet"
        assert anonymized["phone"] == "***4567"
        assert anonymized["email"] == "***.com"
        assert anonymized["api_key"] == "***2345"
        assert anonymized["client_secret"] == "***7890"
        assert anonymized["password"] == "***123"
        assert anonymized["token"] == "***xyz"

        # Check non-sensitive fields remain unchanged
        assert anonymized["medication"] == "Lisinopril 10mg"

        # Check short fields are completely anonymized
        assert anonymized["short_field"] == "***"

    def test_healthcare_response_formatting(self, healthcare_connector):
        """Test healthcare response formatting."""
        response_data = {
            "patient_id": "PAT123456",
            "result": "success"
        }

        healthcare_connector._request_id = "TEST-REQ-001"
        healthcare_connector._start_time = 1234567890.0

        with patch('time.time', return_value=1234567892.5):  # 2.5 seconds later
            formatted_response = healthcare_connector._format_healthcare_response(
                response_data, "test_transaction"
            )

        assert isinstance(formatted_response, Data)
        assert formatted_response.data == response_data

        metadata = formatted_response.metadata
        assert metadata["transaction_type"] == "test_transaction"
        assert metadata["request_id"] == "TEST-REQ-001"
        assert metadata["component"] == "MockHealthcareConnector"
        assert metadata["hipaa_compliant"] is True
        assert metadata["phi_protected"] is True
        assert metadata["audit_logged"] is True
        assert metadata["processing_time_seconds"] == 2.5
        assert "processing_timestamp" in metadata

    def test_healthcare_error_handling(self, healthcare_connector):
        """Test healthcare error handling."""
        test_error = ValueError("Test error message")

        with patch.object(healthcare_connector._audit_logger, 'error') as mock_error_log:
            error_response = healthcare_connector._handle_healthcare_error(
                test_error, "test_context"
            )

        assert isinstance(error_response, Data)
        error_data = error_response.data

        assert error_data["error"] is True
        assert error_data["error_type"] == "ValueError"
        assert error_data["error_message"] == "Healthcare service error occurred"
        assert error_data["context"] == "test_context"
        assert "error_id" in error_data
        assert "timestamp" in error_data

        # Check metadata
        assert error_response.metadata["transaction_type"] == "error"
        assert error_response.metadata["hipaa_compliant"] is True

        # Check audit logging
        mock_error_log.assert_called_once()

    def test_validate_healthcare_data_success(self, healthcare_connector):
        """Test successful healthcare data validation."""
        valid_data = {
            "patient_id": "PAT123456",
            "medication": "Lisinopril 10mg"
        }

        # Mock required fields for testing
        healthcare_connector.get_required_fields = Mock(return_value=["patient_id", "medication"])

        result = healthcare_connector.validate_healthcare_data(valid_data)

        assert result is True

    def test_validate_healthcare_data_not_dict(self, healthcare_connector):
        """Test healthcare data validation with non-dict input."""
        with pytest.raises(ValueError, match="Healthcare data must be a dictionary"):
            healthcare_connector.validate_healthcare_data("not a dict")

    def test_validate_healthcare_data_missing_required(self, healthcare_connector):
        """Test healthcare data validation with missing required fields."""
        incomplete_data = {
            "patient_id": "PAT123456"
            # Missing "medication"
        }

        # Mock required fields for testing
        healthcare_connector.get_required_fields = Mock(return_value=["patient_id", "medication"])

        with pytest.raises(ValueError, match="Missing required healthcare fields"):
            healthcare_connector.validate_healthcare_data(incomplete_data)

    def test_execute_healthcare_workflow_mock_mode(self, healthcare_connector):
        """Test healthcare workflow execution in mock mode."""
        input_data = {
            "patient_id": "PAT123456",
            "operation": "test_operation"
        }

        healthcare_connector.mock_mode = True

        result = healthcare_connector.execute_healthcare_workflow(input_data)

        assert isinstance(result, Data)
        assert result.data["mock"] is True
        assert result.data["patient_id"] == "PAT123456"
        assert result.metadata["transaction_type"] == "mock_response"

    def test_execute_healthcare_workflow_live_mode(self, healthcare_connector):
        """Test healthcare workflow execution in live mode."""
        input_data = {
            "patient_id": "PAT123456",
            "operation": "test_operation"
        }

        healthcare_connector.mock_mode = False

        result = healthcare_connector.execute_healthcare_workflow(input_data)

        assert isinstance(result, Data)
        assert result.data["live"] is True
        assert result.data["patient_id"] == "PAT123456"
        assert result.metadata["transaction_type"] == "live_response"

    def test_execute_healthcare_workflow_audit_logging(self, healthcare_connector):
        """Test healthcare workflow execution with audit logging."""
        input_data = {
            "patient_id": "PAT123456",
            "operation": "test_operation"
        }

        with patch.object(healthcare_connector, '_log_phi_access') as mock_log:
            result = healthcare_connector.execute_healthcare_workflow(input_data)

            # Should log workflow start and completion
            assert mock_log.call_count == 2

            # Check calls
            start_call = mock_log.call_args_list[0]
            assert start_call[0][0] == "workflow_start"
            assert "patient_id" in start_call[0][1]

            complete_call = mock_log.call_args_list[1]
            assert complete_call[0][0] == "workflow_complete"

    def test_execute_healthcare_workflow_no_audit_logging(self, healthcare_connector):
        """Test healthcare workflow execution without audit logging."""
        input_data = {
            "patient_id": "PAT123456",
            "operation": "test_operation"
        }

        healthcare_connector.audit_logging = False

        with patch.object(healthcare_connector, '_log_phi_access') as mock_log:
            result = healthcare_connector.execute_healthcare_workflow(input_data)

            # Should not log anything
            mock_log.assert_not_called()

    def test_execute_healthcare_workflow_validation_error(self, healthcare_connector):
        """Test healthcare workflow execution with validation error."""
        invalid_data = "not a dict"

        result = healthcare_connector.execute_healthcare_workflow(invalid_data)

        assert isinstance(result, Data)
        assert result.data["error"] is True
        assert result.data["error_type"] == "ValueError"
        assert result.metadata["transaction_type"] == "error"

    def test_execute_healthcare_workflow_process_error(self, healthcare_connector):
        """Test healthcare workflow execution with processing error."""
        input_data = {
            "patient_id": "PAT123456",
            "operation": "test_operation"
        }

        # Mock process_healthcare_request to raise an error
        with patch.object(healthcare_connector, 'process_healthcare_request', side_effect=RuntimeError("Processing failed")):
            result = healthcare_connector.execute_healthcare_workflow(input_data)

            assert isinstance(result, Data)
            assert result.data["error"] is True
            assert result.data["error_type"] == "RuntimeError"
            assert result.metadata["transaction_type"] == "error"

    def test_request_context_tracking(self, healthcare_connector):
        """Test request context tracking throughout workflow."""
        input_data = {
            "patient_id": "PAT123456",
            "operation": "test_operation"
        }

        with patch('time.time', return_value=1234567890.0):
            result = healthcare_connector.execute_healthcare_workflow(input_data)

            # Check that request context was set
            assert healthcare_connector._request_id is not None
            assert healthcare_connector._start_time == 1234567890.0
            assert healthcare_connector._request_id.startswith("HC-")

    def test_performance_timing(self, healthcare_connector):
        """Test performance timing calculation."""
        input_data = {
            "patient_id": "PAT123456",
            "operation": "test_operation"
        }

        start_time = 1234567890.0
        end_time = 1234567893.5  # 3.5 seconds later

        with patch('time.time', side_effect=[start_time, end_time]):
            result = healthcare_connector.execute_healthcare_workflow(input_data)

            assert result.metadata["processing_time_seconds"] == 3.5

    def test_get_required_fields_default(self, healthcare_connector):
        """Test default implementation of get_required_fields."""
        required_fields = healthcare_connector.get_required_fields()

        assert isinstance(required_fields, list)
        assert len(required_fields) == 0  # Base implementation returns empty list

    def test_component_inputs_configuration(self):
        """Test that the component has proper input configuration."""
        connector = MockHealthcareConnector()

        # Check that all expected inputs are present
        input_names = [input_.name for input_ in connector.inputs]

        expected_inputs = [
            "api_key", "client_id", "client_secret", "test_mode",
            "mock_mode", "audit_logging", "timeout_seconds"
        ]

        for expected_input in expected_inputs:
            assert expected_input in input_names

    def test_hipaa_compliance_attributes(self):
        """Test HIPAA compliance attributes."""
        connector = MockHealthcareConnector()

        assert connector.hipaa_compliant is True
        assert connector.phi_handling is True
        assert connector.encryption_required is True
        assert connector.audit_trail is True

    @pytest.mark.parametrize("timeout", ["15", "30", "45", "60", "90"])
    def test_timeout_configuration(self, healthcare_connector, timeout):
        """Test different timeout configurations."""
        healthcare_connector.timeout_seconds = timeout

        # Timeout should be configurable
        assert healthcare_connector.timeout_seconds == timeout

    def test_concurrent_request_handling(self, healthcare_connector):
        """Test that each request gets a unique ID."""
        request_ids = []

        for i in range(5):
            input_data = {"patient_id": f"PAT{i:06d}", "operation": "test"}
            result = healthcare_connector.execute_healthcare_workflow(input_data)
            request_ids.append(result.metadata["request_id"])

        # All request IDs should be unique
        assert len(set(request_ids)) == 5

    def test_error_context_preservation(self, healthcare_connector):
        """Test that error context is preserved in error responses."""
        with patch.object(healthcare_connector, 'validate_healthcare_data', side_effect=ValueError("Test validation error")):
            result = healthcare_connector.execute_healthcare_workflow({"test": "data"})

            assert result.data["error"] is True
            assert result.data["context"] == "healthcare_workflow_execution"
            assert result.data["error_type"] == "ValueError"