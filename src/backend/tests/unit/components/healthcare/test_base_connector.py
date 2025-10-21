"""Unit tests for Healthcare Connector Base Class."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.schema.data import Data


class TestHealthcareConnectorBase:
    """Test cases for Healthcare Connector Base Class."""

    class MockHealthcareConnector(HealthcareConnectorBase):
        """Mock implementation for testing base functionality."""

        def get_mock_response(self, request_data):
            return {"mock": "response", "request_id": request_data.get("request_id")}

        def process_healthcare_request(self, request_data):
            return {"real": "response", "request_id": request_data.get("request_id")}

    @pytest.fixture
    def base_connector(self):
        """Create a base healthcare connector instance for testing."""
        connector = self.MockHealthcareConnector()

        # Set test values
        connector.test_mode = True
        connector.mock_mode = True
        connector.audit_logging = True
        connector.timeout_seconds = "30"

        return connector

    @pytest.fixture
    def sample_healthcare_data(self):
        """Sample healthcare data for testing."""
        return {
            "patient_id": "PAT123456",
            "operation": "test_operation",
            "data": "test_data"
        }

    def test_base_connector_initialization(self, base_connector):
        """Test that the base connector initializes correctly."""
        assert base_connector.hipaa_compliant is True
        assert base_connector.phi_handling is True
        assert base_connector.encryption_required is True
        assert base_connector.audit_trail is True
        assert hasattr(base_connector, '_audit_logger')

    def test_base_connector_common_inputs(self, base_connector):
        """Test that base connector has common healthcare inputs."""
        input_names = [input_field.name for input_field in base_connector.inputs]

        expected_base_inputs = [
            "api_key",
            "client_id",
            "client_secret",
            "test_mode",
            "mock_mode",
            "audit_logging",
            "timeout_seconds"
        ]

        for expected_input in expected_base_inputs:
            assert expected_input in input_names

    def test_audit_logger_setup(self, base_connector):
        """Test that audit logger is properly set up."""
        logger = base_connector._audit_logger
        assert logger is not None
        assert logger.name == f"healthcare_audit.{base_connector.__class__.__name__}"

    def test_request_id_generation(self, base_connector):
        """Test request ID generation."""
        request_id_1 = base_connector._generate_request_id()
        request_id_2 = base_connector._generate_request_id()

        assert request_id_1.startswith("HC-")
        assert request_id_2.startswith("HC-")
        assert request_id_1 != request_id_2
        assert len(request_id_1.split("-")) == 3  # HC-timestamp-hash

    def test_phi_access_logging(self, base_connector):
        """Test PHI access logging functionality."""
        with patch.object(base_connector._audit_logger, 'info') as mock_info:
            base_connector._request_id = "TEST-REQ-001"

            base_connector._log_phi_access("test_action", ["patient_id", "patient_name"])

            mock_info.assert_called_once()
            log_entry = json.loads(mock_info.call_args[0][0])

            assert log_entry["request_id"] == "TEST-REQ-001"
            assert log_entry["action"] == "test_action"
            assert log_entry["phi_elements"] == ["patient_id", "patient_name"]
            assert log_entry["component"] == "MockHealthcareConnector"
            assert log_entry["compliance_note"] == "PHI access logged for HIPAA compliance"

    def test_phi_access_logging_disabled(self, base_connector):
        """Test that PHI logging is skipped when audit_logging is disabled."""
        base_connector.audit_logging = False

        with patch.object(base_connector._audit_logger, 'info') as mock_info:
            base_connector._log_phi_access("test_action", ["patient_id"])
            mock_info.assert_not_called()

    def test_phi_data_validation(self, base_connector):
        """Test PHI data validation."""
        phi_data = {
            "patient_id": "PAT123456",
            "patient_name": "John Doe",
            "dob": "1980-01-01",
            "ssn": "123-45-6789",
            "normal_field": "normal_value"
        }

        with patch.object(base_connector, '_log_phi_access') as mock_log:
            result = base_connector._validate_phi_data(phi_data)

            assert result is True
            mock_log.assert_called_once()

            # Check that PHI fields were detected
            logged_fields = mock_log.call_args[0][1]
            assert "patient_id" in logged_fields
            assert "patient_name" in logged_fields
            assert "dob" in logged_fields
            assert "ssn" in logged_fields

    def test_data_anonymization(self, base_connector):
        """Test data anonymization for logging."""
        sensitive_data = {
            "ssn": "123-45-6789",
            "patient_name": "John Doe",
            "address": "123 Main St",
            "phone": "555-1234",
            "email": "john@example.com",
            "api_key": "sk-1234567890abcdef",
            "client_secret": "secret_123456789",
            "password": "password123",
            "token": "bearer_token_123456789",
            "normal_field": "normal_value"
        }

        anonymized = base_connector._anonymize_for_logging(sensitive_data)

        # Check that sensitive fields are anonymized
        assert anonymized["ssn"] == "***6789"
        assert anonymized["patient_name"] == "***Doe"
        assert anonymized["address"] == "***St"
        assert anonymized["phone"] == "***1234"
        assert anonymized["email"] == "***com"
        assert anonymized["api_key"] == "***cdef"
        assert anonymized["client_secret"] == "***56789"
        assert anonymized["password"] == "***rd123"
        assert anonymized["token"] == "***456789"

        # Check that normal fields are preserved
        assert anonymized["normal_field"] == "normal_value"

    def test_data_anonymization_short_values(self, base_connector):
        """Test data anonymization for short values."""
        short_data = {
            "ssn": "123",  # Short value
            "pin": "1234",
            "normal_field": "test"
        }

        anonymized = base_connector._anonymize_for_logging(short_data)

        # Short sensitive fields should be completely masked
        assert anonymized["ssn"] == "***"
        assert anonymized["normal_field"] == "test"  # Not a sensitive field

    def test_format_healthcare_response(self, base_connector):
        """Test healthcare response formatting."""
        base_connector._start_time = 1000.0
        base_connector._request_id = "TEST-REQ-001"

        response_data = {"test": "data", "patient_info": "sample"}

        with patch('time.time', return_value=1002.5):  # 2.5 seconds later
            result = base_connector._format_healthcare_response(response_data, "test_transaction")

        assert isinstance(result, Data)
        assert result.data == response_data

        metadata = result.metadata
        assert metadata["transaction_type"] == "test_transaction"
        assert metadata["request_id"] == "TEST-REQ-001"
        assert metadata["component"] == "MockHealthcareConnector"
        assert metadata["hipaa_compliant"] is True
        assert metadata["phi_protected"] is True
        assert metadata["audit_logged"] is True
        assert metadata["processing_time_seconds"] == 2.5

    def test_handle_healthcare_error(self, base_connector):
        """Test healthcare error handling."""
        test_error = Exception("Database connection failed")

        with patch.object(base_connector._audit_logger, 'error') as mock_error_log:
            result = base_connector._handle_healthcare_error(test_error, "test_context")

        assert isinstance(result, Data)
        assert result.data["error"] is True
        assert result.data["error_type"] == "Exception"
        assert result.data["error_message"] == "Healthcare service error occurred"
        assert result.data["context"] == "test_context"
        assert "error_id" in result.data
        assert "timestamp" in result.data

        # Check that full error is logged but not exposed to user
        mock_error_log.assert_called_once()
        assert "Database connection failed" in str(mock_error_log.call_args)
        assert "Database connection failed" not in result.data["error_message"]

    def test_validate_healthcare_data_valid(self, base_connector, sample_healthcare_data):
        """Test healthcare data validation with valid data."""
        result = base_connector.validate_healthcare_data(sample_healthcare_data)
        assert result is True

    def test_validate_healthcare_data_invalid_type(self, base_connector):
        """Test healthcare data validation with invalid data type."""
        with pytest.raises(ValueError, match="Healthcare data must be a dictionary"):
            base_connector.validate_healthcare_data("invalid_data")

    def test_validate_healthcare_data_missing_required_fields(self, base_connector):
        """Test healthcare data validation with missing required fields."""
        # Mock required fields
        with patch.object(base_connector, 'get_required_fields', return_value=["required_field"]):
            data = {"other_field": "value"}

            with pytest.raises(ValueError, match="Missing required healthcare fields"):
                base_connector.validate_healthcare_data(data)

    def test_get_required_fields_default(self, base_connector):
        """Test that default required fields is empty."""
        required_fields = base_connector.get_required_fields()
        assert required_fields == []

    def test_execute_healthcare_workflow_mock_mode(self, base_connector, sample_healthcare_data):
        """Test healthcare workflow execution in mock mode."""
        base_connector.mock_mode = True

        with patch.object(base_connector, '_log_phi_access') as mock_log:
            result = base_connector.execute_healthcare_workflow(sample_healthcare_data)

        assert isinstance(result, Data)
        assert result.metadata["transaction_type"] == "mock_response"

        # Check audit logging calls
        assert mock_log.call_count == 2  # workflow_start and workflow_complete
        mock_log.assert_any_call("workflow_start", list(sample_healthcare_data.keys()))

    def test_execute_healthcare_workflow_live_mode(self, base_connector, sample_healthcare_data):
        """Test healthcare workflow execution in live mode."""
        base_connector.mock_mode = False

        with patch.object(base_connector, '_log_phi_access') as mock_log:
            result = base_connector.execute_healthcare_workflow(sample_healthcare_data)

        assert isinstance(result, Data)
        assert result.metadata["transaction_type"] == "live_response"

        # Check audit logging calls
        assert mock_log.call_count == 2  # workflow_start and workflow_complete

    def test_execute_healthcare_workflow_error_handling(self, base_connector, sample_healthcare_data):
        """Test healthcare workflow error handling."""
        base_connector.mock_mode = True

        # Mock get_mock_response to raise an exception
        with patch.object(base_connector, 'get_mock_response', side_effect=Exception("Mock error")):
            result = base_connector.execute_healthcare_workflow(sample_healthcare_data)

        assert isinstance(result, Data)
        assert result.data["error"] is True
        assert result.data["error_type"] == "Exception"

    def test_execute_healthcare_workflow_validation_error(self, base_connector):
        """Test healthcare workflow with validation error."""
        invalid_data = "not_a_dict"

        result = base_connector.execute_healthcare_workflow(invalid_data)

        assert isinstance(result, Data)
        assert result.data["error"] is True
        assert "Healthcare data must be a dictionary" in str(result.data)

    def test_execute_healthcare_workflow_timing(self, base_connector, sample_healthcare_data):
        """Test that workflow execution includes timing information."""
        start_time = 1000.0
        end_time = 1002.5

        with patch('time.time', side_effect=[start_time, end_time]):
            result = base_connector.execute_healthcare_workflow(sample_healthcare_data)

        assert result.metadata["processing_time_seconds"] == 2.5

    def test_execute_healthcare_workflow_request_id(self, base_connector, sample_healthcare_data):
        """Test that workflow execution generates and includes request ID."""
        result = base_connector.execute_healthcare_workflow(sample_healthcare_data)

        request_id = result.metadata["request_id"]
        assert request_id is not None
        assert request_id.startswith("HC-")

    def test_audit_logging_disabled_workflow(self, base_connector, sample_healthcare_data):
        """Test workflow execution with audit logging disabled."""
        base_connector.audit_logging = False

        with patch.object(base_connector, '_log_phi_access') as mock_log:
            result = base_connector.execute_healthcare_workflow(sample_healthcare_data)

        assert isinstance(result, Data)
        mock_log.assert_not_called()

    def test_healthcare_metadata_fields(self, base_connector, sample_healthcare_data):
        """Test that all required healthcare metadata fields are present."""
        result = base_connector.execute_healthcare_workflow(sample_healthcare_data)

        metadata = result.metadata
        required_fields = [
            "transaction_type",
            "processing_timestamp",
            "request_id",
            "component",
            "hipaa_compliant",
            "phi_protected",
            "audit_logged"
        ]

        for field in required_fields:
            assert field in metadata

    def test_inheritance_requirements(self):
        """Test that base class enforces abstract method implementation."""
        # Test that direct instantiation fails due to abstract methods
        with pytest.raises(TypeError):
            HealthcareConnectorBase()

    def test_performance_tracking(self, base_connector, sample_healthcare_data):
        """Test performance tracking functionality."""
        result = base_connector.execute_healthcare_workflow(sample_healthcare_data)

        metadata = result.metadata
        assert "processing_time_seconds" in metadata
        assert isinstance(metadata["processing_time_seconds"], float)
        assert metadata["processing_time_seconds"] >= 0

    def test_hipaa_compliance_flags(self, base_connector):
        """Test HIPAA compliance flags are properly set."""
        assert base_connector.hipaa_compliant is True
        assert base_connector.phi_handling is True
        assert base_connector.encryption_required is True
        assert base_connector.audit_trail is True

    def test_thread_safety_request_id(self, base_connector, sample_healthcare_data):
        """Test that request IDs are unique across concurrent operations."""
        request_ids = []

        # Simulate multiple concurrent requests
        for _ in range(10):
            result = base_connector.execute_healthcare_workflow(sample_healthcare_data.copy())
            request_ids.append(result.metadata["request_id"])

        # All request IDs should be unique
        assert len(set(request_ids)) == len(request_ids)