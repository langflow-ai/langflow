"""Unit tests for EligibilityConnector Healthcare Component."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from langflow.components.healthcare.eligibility_connector import EligibilityConnector
from langflow.schema.data import Data


class TestEligibilityConnector:
    """Test cases for EligibilityConnector."""

    @pytest.fixture
    def eligibility_connector(self):
        """Create an eligibility connector instance for testing."""
        connector = EligibilityConnector()

        # Set test values
        connector.test_mode = True
        connector.mock_mode = True
        connector.audit_logging = True
        connector.timeout_seconds = "30"
        connector.eligibility_service = "mock"
        connector.verification_type = "comprehensive"
        connector.real_time_mode = True
        connector.cache_duration_minutes = 15
        connector.provider_npi = "1234567890"

        return connector

    @pytest.fixture
    def sample_eligibility_request(self):
        """Sample eligibility request data for testing."""
        return {
            "member_id": "INS456789",
            "provider_npi": "1234567890",
            "service_type": "office_visit",
            "service_date": "2024-01-16"
        }

    @pytest.fixture
    def sample_eligibility_request_json(self, sample_eligibility_request):
        """Sample eligibility request as JSON string."""
        return json.dumps(sample_eligibility_request)

    def test_eligibility_connector_initialization(self, eligibility_connector):
        """Test that the eligibility connector initializes correctly."""
        assert eligibility_connector.hipaa_compliant is True
        assert eligibility_connector.phi_handling is True
        assert eligibility_connector.encryption_required is True
        assert eligibility_connector.audit_trail is True
        assert eligibility_connector.display_name == "Eligibility Connector"
        assert eligibility_connector.name == "EligibilityConnector"
        assert eligibility_connector.icon == "Shield"

    def test_eligibility_connector_inheritance(self, eligibility_connector):
        """Test that EligibilityConnector properly inherits from HealthcareConnectorBase."""
        from langflow.base.healthcare_connector_base import HealthcareConnectorBase
        assert isinstance(eligibility_connector, HealthcareConnectorBase)
        assert hasattr(eligibility_connector, '_audit_logger')
        assert hasattr(eligibility_connector, 'execute_healthcare_workflow')

    def test_get_required_fields(self, eligibility_connector):
        """Test that required fields are correctly defined."""
        required_fields = eligibility_connector.get_required_fields()
        assert isinstance(required_fields, list)
        assert "member_id" in required_fields

    def test_parse_eligibility_request_valid_json(self, eligibility_connector, sample_eligibility_request_json):
        """Test parsing valid JSON eligibility request."""
        result = eligibility_connector._parse_eligibility_request(sample_eligibility_request_json)
        assert isinstance(result, dict)
        assert result["member_id"] == "INS456789"
        assert result["provider_npi"] == "1234567890"

    def test_parse_eligibility_request_dict_input(self, eligibility_connector, sample_eligibility_request):
        """Test parsing dict eligibility request."""
        result = eligibility_connector._parse_eligibility_request(sample_eligibility_request)
        assert isinstance(result, dict)
        assert result["member_id"] == "INS456789"

    def test_parse_eligibility_request_invalid_json(self, eligibility_connector):
        """Test parsing invalid JSON eligibility request."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            eligibility_connector._parse_eligibility_request('{"invalid": json}')

    def test_parse_eligibility_request_missing_member_id(self, eligibility_connector):
        """Test parsing request without required member_id."""
        request = {"provider_npi": "1234567890"}
        with pytest.raises(ValueError, match="Missing required field: member_id"):
            eligibility_connector._parse_eligibility_request(json.dumps(request))

    def test_get_mock_eligibility_response_active_member(self, eligibility_connector, sample_eligibility_request):
        """Test mock response for active member."""
        response = eligibility_connector._get_mock_eligibility_response(sample_eligibility_request)

        assert isinstance(response, dict)
        assert "verification_id" in response
        assert "timestamp" in response
        assert "member_information" in response
        assert "financial_information" in response
        assert "coverage_details" in response
        assert "network_information" in response

        # Check member information
        member_info = response["member_information"]
        assert member_info["member_id"] == "INS456789"
        assert member_info["eligibility_status"] == "active"
        assert member_info["plan_name"] == "Health Plus Premium"

    def test_get_mock_eligibility_response_inactive_member(self, eligibility_connector):
        """Test mock response for inactive member."""
        request = {"member_id": "INACTIVE123", "service_type": "office_visit"}
        response = eligibility_connector._get_mock_eligibility_response(request)

        assert response["member_information"]["eligibility_status"] == "inactive"
        assert response["coverage_details"]["benefits"]["message"] == "Coverage terminated"

    def test_get_mock_eligibility_response_pending_member(self, eligibility_connector):
        """Test mock response for pending member."""
        request = {"member_id": "PENDING456", "service_type": "office_visit"}
        response = eligibility_connector._get_mock_eligibility_response(request)

        assert response["member_information"]["eligibility_status"] == "pending"
        assert response["coverage_details"]["benefits"]["message"] == "Coverage pending verification"

    def test_get_mock_benefit_summary(self, eligibility_connector, sample_eligibility_request):
        """Test mock benefit summary generation."""
        response = eligibility_connector._get_mock_benefit_summary(sample_eligibility_request)

        assert isinstance(response, dict)
        assert "member_id" in response
        assert "plan_summary" in response
        assert "benefit_categories" in response
        assert "annual_maximums" in response

        # Check benefit categories
        benefits = response["benefit_categories"]
        assert "preventive_care" in benefits
        assert "primary_care" in benefits
        assert "specialist_care" in benefits
        assert "prescription_drugs" in benefits

    def test_get_mock_network_status(self, eligibility_connector, sample_eligibility_request):
        """Test mock network status generation."""
        response = eligibility_connector._get_mock_network_status(sample_eligibility_request)

        assert isinstance(response, dict)
        assert "provider_npi" in response
        assert "network_status" in response
        assert "provider_details" in response
        assert "network_information" in response
        assert "quality_metrics" in response

    def test_get_mock_cost_estimate(self, eligibility_connector, sample_eligibility_request):
        """Test mock cost estimate generation."""
        response = eligibility_connector._get_mock_cost_estimate(sample_eligibility_request)

        assert isinstance(response, dict)
        assert "service_type" in response
        assert "cost_breakdown" in response
        assert "benefit_details" in response
        assert "accuracy_disclaimer" in response

        # Check cost breakdown structure
        cost_breakdown = response["cost_breakdown"]
        assert "provider_charge" in cost_breakdown
        assert "patient_responsibility" in cost_breakdown
        assert "insurance_payment" in cost_breakdown

    @patch('langflow.components.healthcare.eligibility_connector.datetime')
    def test_verify_eligibility_success(self, mock_datetime, eligibility_connector, sample_eligibility_request_json):
        """Test successful eligibility verification."""
        # Mock datetime
        mock_datetime.now.return_value = datetime(2024, 1, 16, 10, 30, 0, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        # Set eligibility request
        eligibility_connector.eligibility_request = sample_eligibility_request_json

        # Call verify_eligibility
        result = eligibility_connector.verify_eligibility()

        # Assertions
        assert isinstance(result, Data)
        assert result.data is not None
        data_value = result.data.get("value", result.data)
        assert not data_value.get("error", False)
        assert "member_information" in data_value
        assert data_value["member_information"]["eligibility_status"] == "active"
        assert eligibility_connector.status.startswith("Eligibility Status:")

    def test_verify_eligibility_invalid_request(self, eligibility_connector):
        """Test eligibility verification with invalid request."""
        eligibility_connector.eligibility_request = '{"invalid": json}'

        result = eligibility_connector.verify_eligibility()

        assert isinstance(result, Data)
        data_value = result.data.get("value", result.data)
        assert data_value.get("error", False)
        assert eligibility_connector.status is None or eligibility_connector.status.startswith("Verification Failed")

    def test_get_benefit_summary_success(self, eligibility_connector, sample_eligibility_request_json):
        """Test successful benefit summary retrieval."""
        eligibility_connector.eligibility_request = sample_eligibility_request_json

        result = eligibility_connector.get_benefit_summary()

        assert isinstance(result, Data)
        assert result.data is not None
        data_value = result.data.get("value", result.data)
        assert "plan_summary" in data_value
        assert "benefit_categories" in data_value
        assert eligibility_connector.status.startswith("Benefits Retrieved")

    def test_check_network_status_success(self, eligibility_connector, sample_eligibility_request_json):
        """Test successful network status check."""
        eligibility_connector.eligibility_request = sample_eligibility_request_json

        result = eligibility_connector.check_network_status()

        assert isinstance(result, Data)
        assert result.data is not None
        data_value = result.data.get("value", result.data)
        assert "network_status" in data_value
        assert "provider_details" in data_value
        assert eligibility_connector.status.startswith("Network Status:")

    def test_calculate_cost_estimate_success(self, eligibility_connector, sample_eligibility_request_json):
        """Test successful cost estimate calculation."""
        eligibility_connector.eligibility_request = sample_eligibility_request_json

        result = eligibility_connector.calculate_cost_estimate()

        assert isinstance(result, Data)
        assert result.data is not None
        data_value = result.data.get("value", result.data)
        assert "cost_breakdown" in data_value
        assert "benefit_details" in data_value
        assert eligibility_connector.status.startswith("Estimated Patient Cost:")

    def test_different_service_types(self, eligibility_connector):
        """Test eligibility responses for different service types."""
        service_types = ["office_visit", "specialist", "diagnostic", "procedure", "emergency"]

        for service_type in service_types:
            request = {
                "member_id": "TEST123",
                "service_type": service_type,
                "provider_npi": "1234567890"
            }

            # Test eligibility response
            response = eligibility_connector._get_mock_eligibility_response(request)
            assert response["coverage_details"]["service_type"] == service_type

            # Test cost estimate
            cost_response = eligibility_connector._get_mock_cost_estimate(request)
            assert cost_response["service_type"] == service_type

    def test_eligibility_service_options(self, eligibility_connector, sample_eligibility_request):
        """Test different eligibility service options."""
        services = ["availity", "change_healthcare", "navinet", "mock"]

        for service in services:
            eligibility_connector.eligibility_service = service
            response = eligibility_connector.get_mock_response(sample_eligibility_request)
            assert response["eligibility_service"] == service

    def test_verification_type_options(self, eligibility_connector):
        """Test different verification type options."""
        verification_types = ["basic", "benefits", "network", "comprehensive"]

        for verification_type in verification_types:
            eligibility_connector.verification_type = verification_type
            # Verification type affects the thoroughness of the response
            # The mock response includes comprehensive data by default
            assert eligibility_connector.verification_type == verification_type

    def test_real_time_vs_cached_mode(self, eligibility_connector, sample_eligibility_request):
        """Test real-time vs cached mode behavior."""
        # Test real-time mode
        eligibility_connector.real_time_mode = True
        response_realtime = eligibility_connector._get_mock_eligibility_response(sample_eligibility_request)
        assert response_realtime["processing_metrics"]["cache_used"] is False

        # Test cached mode
        eligibility_connector.real_time_mode = False
        response_cached = eligibility_connector._get_mock_eligibility_response(sample_eligibility_request)
        assert response_cached["processing_metrics"]["cache_used"] is True

    def test_cache_duration_configuration(self, eligibility_connector):
        """Test cache duration configuration."""
        cache_durations = [5, 15, 30, 60]

        for duration in cache_durations:
            eligibility_connector.cache_duration_minutes = duration
            assert eligibility_connector.cache_duration_minutes == duration

    def test_provider_npi_validation(self, eligibility_connector):
        """Test provider NPI handling."""
        npi_values = ["1234567890", "9876543210", "${PROVIDER_NPI}"]

        for npi in npi_values:
            eligibility_connector.provider_npi = npi
            request = {"member_id": "TEST123", "provider_npi": npi}
            response = eligibility_connector._get_mock_network_status(request)
            assert response["provider_npi"] == npi

    def test_comprehensive_eligibility_workflow(self, eligibility_connector, sample_eligibility_request_json):
        """Test the complete eligibility workflow with all outputs."""
        eligibility_connector.eligibility_request = sample_eligibility_request_json

        # Test all output methods
        eligibility_result = eligibility_connector.verify_eligibility()
        benefit_result = eligibility_connector.get_benefit_summary()
        network_result = eligibility_connector.check_network_status()
        cost_result = eligibility_connector.calculate_cost_estimate()

        # Verify all results are Data objects with valid content
        for result in [eligibility_result, benefit_result, network_result, cost_result]:
            assert isinstance(result, Data)
            assert result.data is not None
            assert not result.data.get("error", False)

    def test_hipaa_compliance_features(self, eligibility_connector, sample_eligibility_request):
        """Test HIPAA compliance features."""
        # Test that base class methods are available
        assert hasattr(eligibility_connector, '_validate_phi_data')
        assert hasattr(eligibility_connector, '_anonymize_for_logging')
        assert hasattr(eligibility_connector, '_log_phi_access')

        # Test audit logging configuration
        eligibility_connector.audit_logging = True
        assert eligibility_connector.audit_logging is True

        # Test that PHI data is handled
        eligibility_connector.validate_healthcare_data(sample_eligibility_request)

    def test_error_handling_and_recovery(self, eligibility_connector):
        """Test error handling and recovery mechanisms."""
        # Test malformed JSON
        eligibility_connector.eligibility_request = "invalid json"
        result = eligibility_connector.verify_eligibility()
        assert isinstance(result, Data)
        # Check for error in the wrapped data structure
        data_value = result.data.get("value", result.data)
        assert data_value.get("error", False)

        # Test missing required fields
        eligibility_connector.eligibility_request = '{"provider_npi": "1234567890"}'
        result = eligibility_connector.verify_eligibility()
        assert isinstance(result, Data)
        # Check for error in the wrapped data structure
        data_value = result.data.get("value", result.data)
        assert data_value.get("error", False)

    def test_data_structure_consistency(self, eligibility_connector, sample_eligibility_request):
        """Test that all mock responses have consistent data structures."""
        # Test eligibility response structure
        eligibility_response = eligibility_connector._get_mock_eligibility_response(sample_eligibility_request)
        required_sections = [
            "verification_id", "timestamp", "member_information",
            "financial_information", "coverage_details", "network_information",
            "verification_notes", "processing_metrics"
        ]
        for section in required_sections:
            assert section in eligibility_response

        # Test benefit summary structure
        benefit_response = eligibility_connector._get_mock_benefit_summary(sample_eligibility_request)
        benefit_sections = ["member_id", "plan_summary", "benefit_categories", "annual_maximums"]
        for section in benefit_sections:
            assert section in benefit_response

        # Test network status structure
        network_response = eligibility_connector._get_mock_network_status(sample_eligibility_request)
        network_sections = ["provider_npi", "network_status", "provider_details", "network_information"]
        for section in network_sections:
            assert section in network_response

        # Test cost estimate structure
        cost_response = eligibility_connector._get_mock_cost_estimate(sample_eligibility_request)
        cost_sections = ["service_type", "cost_breakdown", "benefit_details", "accuracy_disclaimer"]
        for section in cost_sections:
            assert section in cost_response

    def test_medical_terminology_usage(self, eligibility_connector, sample_eligibility_request):
        """Test that responses include appropriate medical terminology."""
        response = eligibility_connector._get_mock_eligibility_response(sample_eligibility_request)

        # Check for medical/insurance terminology
        assert "deductible_individual" in response["financial_information"]
        assert "copay_office_visit" in response["financial_information"]
        assert "coinsurance_rate" in response["financial_information"]
        assert "out_of_pocket_max_individual" in response["financial_information"]
        assert "prior_auth_required" in response["coverage_details"]
        assert "network_tier" in response["network_information"]

    def test_performance_metrics_inclusion(self, eligibility_connector, sample_eligibility_request):
        """Test that performance metrics are included in responses."""
        response = eligibility_connector._get_mock_eligibility_response(sample_eligibility_request)

        metrics = response["processing_metrics"]
        assert "response_time_ms" in metrics
        assert "cache_used" in metrics
        assert "accuracy_score" in metrics
        assert "confidence_level" in metrics

        # Verify metric values are reasonable
        assert isinstance(metrics["response_time_ms"], int)
        assert 0 <= metrics["accuracy_score"] <= 1.0
        assert metrics["confidence_level"] in ["low", "medium", "high"]

    def test_component_outputs_configuration(self, eligibility_connector):
        """Test that component outputs are properly configured."""
        outputs = eligibility_connector.outputs

        # Check that all expected outputs exist
        output_names = [output.name for output in outputs]
        expected_outputs = [
            "eligibility_response", "benefit_summary",
            "network_status", "cost_estimate"
        ]

        for expected in expected_outputs:
            assert expected in output_names

        # Check that each output has a method
        for output in outputs:
            assert hasattr(eligibility_connector, output.method)

    def test_input_configuration(self, eligibility_connector):
        """Test that component inputs are properly configured."""
        # Check that base class inputs are inherited
        input_names = [input_field.name for input_field in eligibility_connector.inputs]

        # Base class inputs
        base_inputs = ["api_key", "client_id", "client_secret", "test_mode", "mock_mode", "audit_logging", "timeout_seconds"]
        for base_input in base_inputs:
            assert base_input in input_names

        # Eligibility-specific inputs
        eligibility_inputs = [
            "eligibility_request", "eligibility_service", "verification_type",
            "real_time_mode", "cache_duration_minutes", "provider_npi"
        ]
        for eligibility_input in eligibility_inputs:
            assert eligibility_input in input_names

    def test_search_network_providers(self, eligibility_connector):
        """Test network provider search functionality."""
        criteria = {
            "specialty": "Cardiology",
            "location": "Medical City, ST"
        }

        providers = eligibility_connector.search_network_providers(criteria)

        assert isinstance(providers, list)
        assert len(providers) >= 1

        # Check provider structure
        for provider in providers:
            assert "provider_npi" in provider
            assert "name" in provider
            assert "specialty" in provider
            assert "network_status" in provider
            assert "network_tier" in provider
            assert "accepting_new_patients" in provider

    def test_check_pre_auth_requirements(self, eligibility_connector):
        """Test pre-authorization requirements checking."""
        service_codes = ["99213", "73721", "27447"]
        requirements = eligibility_connector.check_pre_auth_requirements(service_codes)

        assert isinstance(requirements, dict)
        assert "services_checked" in requirements
        assert "requirements" in requirements
        assert requirements["services_checked"] == service_codes

        # Check requirement details
        for req in requirements["requirements"]:
            assert "service_code" in req
            assert "pre_auth_required" in req
            assert "reason" in req
            assert isinstance(req["pre_auth_required"], bool)

    def test_calculate_patient_cost(self, eligibility_connector):
        """Test patient cost calculation."""
        service_info = {
            "service_codes": ["99213", "73721"],
            "provider_npi": "1234567890",
            "service_date": "2024-01-16"
        }

        cost_estimate = eligibility_connector.calculate_patient_cost(service_info)

        assert isinstance(cost_estimate, dict)
        assert "service_details" in cost_estimate
        assert "cost_summary" in cost_estimate
        assert "benefit_status" in cost_estimate

        # Check cost summary structure
        cost_summary = cost_estimate["cost_summary"]
        assert "total_provider_charge" in cost_summary
        assert "total_patient_responsibility" in cost_summary
        assert "insurance_payment" in cost_summary
        assert "breakdown" in cost_summary

    def test_verify_provider_participation(self, eligibility_connector):
        """Test provider network participation verification."""
        # Test in-network provider
        in_network_npi = "1234567890"
        assert eligibility_connector.verify_provider_participation(in_network_npi) is True

        # Test out-of-network provider
        out_of_network_npi = "9999999999"
        assert eligibility_connector.verify_provider_participation(out_of_network_npi) is False

    def test_key_methods_api_compatibility(self, eligibility_connector):
        """Test that all key methods from JIRA story are implemented."""
        # Verify all key methods exist and are callable
        assert hasattr(eligibility_connector, 'verify_eligibility')
        assert callable(eligibility_connector.verify_eligibility)

        assert hasattr(eligibility_connector, 'get_benefit_summary')
        assert callable(eligibility_connector.get_benefit_summary)

        assert hasattr(eligibility_connector, 'search_network_providers')
        assert callable(eligibility_connector.search_network_providers)

        assert hasattr(eligibility_connector, 'check_pre_auth_requirements')
        assert callable(eligibility_connector.check_pre_auth_requirements)

        assert hasattr(eligibility_connector, 'calculate_patient_cost')
        assert callable(eligibility_connector.calculate_patient_cost)

        assert hasattr(eligibility_connector, 'verify_provider_participation')
        assert callable(eligibility_connector.verify_provider_participation)

    def test_comprehensive_workflow_with_new_methods(self, eligibility_connector):
        """Test comprehensive eligibility workflow including new methods."""
        # Test provider search
        provider_criteria = {"specialty": "Family Medicine"}
        providers = eligibility_connector.search_network_providers(provider_criteria)
        assert len(providers) > 0

        # Test pre-auth checking
        service_codes = ["99213", "73721"]
        pre_auth = eligibility_connector.check_pre_auth_requirements(service_codes)
        assert "requirements" in pre_auth

        # Test cost calculation
        service_info = {"service_codes": service_codes}
        cost_estimate = eligibility_connector.calculate_patient_cost(service_info)
        assert "cost_summary" in cost_estimate

        # Test provider verification
        provider_npi = providers[0]["provider_npi"]
        is_in_network = eligibility_connector.verify_provider_participation(provider_npi)
        assert isinstance(is_in_network, bool)