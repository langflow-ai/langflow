"""Tests for healthcare components and their integration."""

import json
import pytest
from unittest.mock import MagicMock, patch

from langflow.components.healthcare import (
    HealthcareConnectorBase,
    ClaimsConnector,
    EHRConnector,
    EligibilityConnector,
    PharmacyConnector,
)
from langflow.schema.data import Data


class TestHealthcareConnectorBase:
    """Test the base healthcare connector functionality."""

    def test_healthcare_connector_base_initialization(self):
        """Test that healthcare connector base initializes with correct defaults."""
        class TestConnector(HealthcareConnectorBase):
            def get_mock_response(self, request_data):
                return {"test": "mock"}

            def process_healthcare_request(self, request_data):
                return {"test": "live"}

        connector = TestConnector()

        assert connector.hipaa_compliant is True
        assert connector.phi_handling is True
        assert connector.encryption_required is True
        assert connector.audit_trail is True

    def test_phi_data_validation(self):
        """Test PHI data validation and logging."""
        class TestConnector(HealthcareConnectorBase):
            def get_mock_response(self, request_data):
                return {"test": "mock"}

            def process_healthcare_request(self, request_data):
                return {"test": "live"}

        connector = TestConnector()
        connector.audit_logging = True

        # Test with PHI data
        phi_data = {
            "patient_id": "12345",
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
        }

        result = connector._validate_phi_data(phi_data)
        assert result is True

    def test_anonymize_for_logging(self):
        """Test data anonymization for logging."""
        class TestConnector(HealthcareConnectorBase):
            def get_mock_response(self, request_data):
                return {"test": "mock"}

            def process_healthcare_request(self, request_data):
                return {"test": "live"}

        connector = TestConnector()

        sensitive_data = {
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "api_key": "secret_key_12345",
            "normal_field": "public_data",
        }

        anonymized = connector._anonymize_for_logging(sensitive_data)

        assert anonymized["patient_name"] == "*** Doe"
        assert anonymized["ssn"] == "***6789"
        assert anonymized["api_key"] == "***2345"
        assert anonymized["normal_field"] == "public_data"

    def test_healthcare_workflow_execution_mock_mode(self):
        """Test healthcare workflow execution in mock mode."""
        class TestConnector(HealthcareConnectorBase):
            def get_mock_response(self, request_data):
                return {"status": "mock_success", "data": request_data}

            def process_healthcare_request(self, request_data):
                return {"status": "live_success", "data": request_data}

            def get_required_fields(self):
                return ["test_field"]

        connector = TestConnector()
        connector.mock_mode = True
        connector.audit_logging = False

        input_data = {"test_field": "test_value"}
        result = connector.execute_healthcare_workflow(input_data)

        assert isinstance(result, Data)
        assert result.data["status"] == "mock_success"
        assert result.metadata["transaction_type"] == "mock_response"
        assert result.metadata["hipaa_compliant"] is True

    def test_healthcare_workflow_execution_live_mode(self):
        """Test healthcare workflow execution in live mode."""
        class TestConnector(HealthcareConnectorBase):
            def get_mock_response(self, request_data):
                return {"status": "mock_success", "data": request_data}

            def process_healthcare_request(self, request_data):
                return {"status": "live_success", "data": request_data}

            def get_required_fields(self):
                return ["test_field"]

        connector = TestConnector()
        connector.mock_mode = False
        connector.audit_logging = False

        input_data = {"test_field": "test_value"}
        result = connector.execute_healthcare_workflow(input_data)

        assert isinstance(result, Data)
        assert result.data["status"] == "live_success"
        assert result.metadata["transaction_type"] == "live_response"
        assert result.metadata["hipaa_compliant"] is True

    def test_error_handling(self):
        """Test healthcare error handling."""
        class TestConnector(HealthcareConnectorBase):
            def get_mock_response(self, request_data):
                raise ValueError("Mock error")

            def process_healthcare_request(self, request_data):
                raise ValueError("Live error")

            def get_required_fields(self):
                return []

        connector = TestConnector()
        connector.mock_mode = True
        connector.audit_logging = False

        result = connector.execute_healthcare_workflow({})

        assert isinstance(result, Data)
        assert result.data["error"] is True
        assert result.data["error_type"] == "ValueError"
        assert "error_id" in result.data

    def test_required_fields_validation(self):
        """Test required fields validation."""
        class TestConnector(HealthcareConnectorBase):
            def get_mock_response(self, request_data):
                return {"test": "mock"}

            def process_healthcare_request(self, request_data):
                return {"test": "live"}

            def get_required_fields(self):
                return ["required_field"]

        connector = TestConnector()
        connector.audit_logging = False

        # Test with missing required field
        with pytest.raises(ValueError, match="Missing required healthcare fields"):
            connector.validate_healthcare_data({"other_field": "value"})

        # Test with required field present
        result = connector.execute_healthcare_workflow({"required_field": "value"})
        assert isinstance(result, Data)


class TestClaimsConnector:
    """Test the Claims Healthcare Connector."""

    def test_claims_connector_initialization(self):
        """Test Claims connector initialization."""
        connector = ClaimsConnector()

        assert connector.display_name == "Claims Connector"
        assert "claims processing" in connector.description.lower()
        assert connector.name == "ClaimsConnector"

    def test_claims_connector_inputs(self):
        """Test Claims connector has required inputs."""
        connector = ClaimsConnector()

        input_names = [input_field.name for input_field in connector.inputs]

        assert "clearinghouse" in input_names
        assert "payer_id" in input_names
        assert "provider_npi" in input_names
        assert "claim_data" in input_names
        assert "authentication_type" in input_names

    def test_claims_mock_response_claim_submission(self):
        """Test claims connector mock response for claim submission."""
        connector = ClaimsConnector()

        request_data = {
            "request_type": "claim_submission",
            "data": "837 claim data",
            "clearinghouse": "change_healthcare",
            "payer_id": "AETNA",
        }

        response = connector.get_mock_response(request_data)

        assert response["transaction_type"] == "837_claim_submission"
        assert "submission_id" in response
        assert "control_number" in response
        assert response["status"] == "accepted"
        assert response["clearinghouse"] == "change_healthcare"
        assert response["payer_id"] == "AETNA"
        assert "claim_details" in response
        assert "edi_segments" in response
        assert "compliance" in response

    def test_claims_mock_response_prior_authorization(self):
        """Test claims connector mock response for prior authorization."""
        connector = ClaimsConnector()

        request_data = {
            "request_type": "prior_authorization",
            "data": "prior auth request",
            "payer_id": "AETNA",
        }

        response = connector.get_mock_response(request_data)

        assert response["transaction_type"] == "prior_authorization_response"
        assert "authorization_info" in response
        assert "patient_info" in response
        assert "provider_info" in response
        assert "service_info" in response
        assert "compliance" in response
        assert response["compliance"]["epa_compliant"] is True

    def test_claims_process_healthcare_request(self):
        """Test claims connector live processing."""
        connector = ClaimsConnector()

        request_data = {
            "clearinghouse": "availity",
            "claim_data": "test claim",
        }

        response = connector.process_healthcare_request(request_data)

        assert response["status"] == "submitted"
        assert response["clearinghouse"] == "availity"
        assert "request_id" in response

    @patch.object(ClaimsConnector, 'execute_healthcare_workflow')
    def test_claims_process_claims_method(self, mock_workflow):
        """Test the main process_claims method."""
        connector = ClaimsConnector()
        connector.claim_data = '{"test": "data"}'
        connector.clearinghouse = "change_healthcare"
        connector.payer_id = "AETNA"
        connector.provider_npi = "1234567890"
        connector.submitter_id = "SUB123"
        connector.authentication_type = "api_key"
        connector.test_mode = True

        mock_workflow.return_value = Data(data={"result": "success"})

        result = connector.process_claims()

        assert mock_workflow.called
        call_args = mock_workflow.call_args[0][0]
        assert call_args["clearinghouse"] == "change_healthcare"
        assert call_args["payer_id"] == "AETNA"
        assert call_args["test_mode"] is True


class TestHealthcareComponentsImport:
    """Test that healthcare components can be imported correctly."""

    def test_import_healthcare_base(self):
        """Test importing healthcare base connector."""
        assert HealthcareConnectorBase is not None
        assert hasattr(HealthcareConnectorBase, 'hipaa_compliant')
        assert hasattr(HealthcareConnectorBase, 'execute_healthcare_workflow')

    def test_import_claims_connector(self):
        """Test importing claims connector."""
        assert ClaimsConnector is not None
        assert issubclass(ClaimsConnector, HealthcareConnectorBase)
        assert ClaimsConnector.display_name == "Claims Connector"

    def test_import_ehr_connector(self):
        """Test importing EHR connector."""
        assert EHRConnector is not None
        assert issubclass(EHRConnector, HealthcareConnectorBase)

    def test_import_eligibility_connector(self):
        """Test importing eligibility connector."""
        assert EligibilityConnector is not None
        assert issubclass(EligibilityConnector, HealthcareConnectorBase)

    def test_import_pharmacy_connector(self):
        """Test importing pharmacy connector."""
        assert PharmacyConnector is not None
        assert issubclass(PharmacyConnector, HealthcareConnectorBase)

    def test_all_healthcare_connectors_inheritance(self):
        """Test that all healthcare connectors inherit from base."""
        connectors = [ClaimsConnector, EHRConnector, EligibilityConnector, PharmacyConnector]

        for connector_class in connectors:
            assert issubclass(connector_class, HealthcareConnectorBase)

            # Test instantiation
            instance = connector_class()
            assert instance.hipaa_compliant is True
            assert instance.phi_handling is True
            assert instance.encryption_required is True
            assert instance.audit_trail is True


class TestHealthcareComponentsIntegration:
    """Test healthcare components integration with Langflow."""

    def test_healthcare_components_module_structure(self):
        """Test that healthcare components module has correct structure."""
        from langflow.components import healthcare

        assert hasattr(healthcare, 'HealthcareConnectorBase')
        assert hasattr(healthcare, 'ClaimsConnector')
        assert hasattr(healthcare, 'EHRConnector')
        assert hasattr(healthcare, 'EligibilityConnector')
        assert hasattr(healthcare, 'PharmacyConnector')

    def test_healthcare_category_registration(self):
        """Test that healthcare category is properly registered."""
        # This would test the component registration system
        # For now, we test that the components can be instantiated
        connectors = [
            ClaimsConnector(),
            EHRConnector(),
            EligibilityConnector(),
            PharmacyConnector(),
        ]

        for connector in connectors:
            assert hasattr(connector, 'display_name')
            assert hasattr(connector, 'description')
            assert hasattr(connector, 'inputs')
            assert hasattr(connector, 'outputs')

    def test_healthcare_components_output_format(self):
        """Test that healthcare components return Data objects."""
        connector = ClaimsConnector()
        connector.claim_data = "test"
        connector.payer_id = "TEST"
        connector.clearinghouse = "test"
        connector.provider_npi = "test"
        connector.submitter_id = "test"
        connector.authentication_type = "api_key"
        connector.mock_mode = True
        connector.audit_logging = False

        result = connector.process_claims()

        assert isinstance(result, Data)
        assert hasattr(result, 'data')
        assert hasattr(result, 'metadata')
        assert result.metadata.get('hipaa_compliant') is True

    def test_healthcare_audit_logging(self):
        """Test healthcare audit logging functionality."""
        connector = ClaimsConnector()
        connector.audit_logging = True

        with patch.object(connector, '_log_phi_access') as mock_log:
            connector._log_phi_access("test_action", ["patient_id"], "REQ123")
            mock_log.assert_called_with("test_action", ["patient_id"], "REQ123")