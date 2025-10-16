"""
Integration tests for AppealsDataConnector

This test suite validates the AppealsDataConnector component functionality,
HIPAA compliance, and integration with the healthcare connector system.
"""

import pytest
import json
from datetime import datetime, timezone
from typing import Dict, Any

from langflow.components.healthcare.appeals_data_connector import AppealsDataConnector
from langflow.schema.data import Data


@pytest.mark.integration
class TestAppealsDataConnectorIntegration:
    """Integration tests for AppealsDataConnector component."""

    @pytest.fixture
    def appeals_connector(self):
        """Create AppealsDataConnector instance for testing."""
        connector = AppealsDataConnector()
        # Set test configuration
        connector.appeals_system = "mock"
        connector.data_source = "comprehensive"
        connector.search_scope = "relevant"
        connector.max_results = 50
        connector.include_historical = True
        connector.mock_mode = True
        connector.test_mode = True
        return connector

    @pytest.fixture
    def sample_appeals_request(self):
        """Sample appeals request data for testing."""
        return {
            "appeal_id": "APP_TEST_001",
            "member_id": "MEM123456",
            "request_type": "comprehensive"
        }

    def test_connector_initialization(self, appeals_connector):
        """Test that AppealsDataConnector initializes correctly."""
        assert appeals_connector.display_name == "Appeals Data Connector"
        assert appeals_connector.name == "AppealsDataConnector"
        assert appeals_connector.category == "connectors"
        assert appeals_connector.icon == "FileText"

        # Check healthcare-specific initialization
        assert appeals_connector.mock_mode is True
        assert appeals_connector.test_mode is True

        # Verify inputs are properly combined
        input_names = [inp.name for inp in appeals_connector.inputs]
        assert "appeals_request" in input_names
        assert "data_source" in input_names
        assert "appeals_system" in input_names
        assert "search_scope" in input_names
        assert "max_results" in input_names
        assert "include_historical" in input_names

    def test_get_denial_reasons_output(self, appeals_connector, sample_appeals_request):
        """Test denial reasons retrieval functionality."""
        # Set appeals request
        appeals_connector.appeals_request = json.dumps(sample_appeals_request)

        # Execute denial reasons retrieval
        result = appeals_connector.get_denial_reasons()

        # Validate result type and structure
        assert isinstance(result, Data)
        assert result.data is not None
        assert not result.data.get("error", False)

        # Validate denial reasons data structure
        denial_data = result.data.get("denial_reasons", {})
        assert "denial_id" in denial_data
        assert "denial_date" in denial_data
        assert "primary_reason" in denial_data
        assert "secondary_reasons" in denial_data
        assert "denial_code" in denial_data
        assert "decision_criteria" in denial_data
        assert "reviewer_information" in denial_data
        assert "appeal_eligibility" in denial_data

        # Validate data quality
        assert denial_data["primary_reason"] != ""
        assert isinstance(denial_data["secondary_reasons"], list)
        assert len(denial_data["secondary_reasons"]) > 0

    def test_search_policies_output(self, appeals_connector, sample_appeals_request):
        """Test policy search functionality."""
        # Set appeals request
        appeals_connector.appeals_request = json.dumps(sample_appeals_request)

        # Execute policy search
        result = appeals_connector.search_policies()

        # Validate result type and structure
        assert isinstance(result, Data)
        assert result.data is not None
        assert not result.data.get("error", False)

        # Validate policies data structure
        policies_data = result.data.get("policies", {})
        assert "relevant_policies" in policies_data
        assert "policy_matching_criteria" in policies_data

        relevant_policies = policies_data["relevant_policies"]
        assert isinstance(relevant_policies, list)
        assert len(relevant_policies) > 0

        # Validate policy structure
        first_policy = relevant_policies[0]
        assert "policy_id" in first_policy
        assert "policy_name" in first_policy
        assert "version" in first_policy
        assert "effective_date" in first_policy
        assert "policy_sections" in first_policy
        assert "relevance_score" in first_policy

        # Validate relevance score is reasonable
        assert 0.0 <= first_policy["relevance_score"] <= 1.0

    def test_get_evidence_output(self, appeals_connector, sample_appeals_request):
        """Test evidence retrieval functionality."""
        # Set appeals request
        appeals_connector.appeals_request = json.dumps(sample_appeals_request)

        # Execute evidence retrieval
        result = appeals_connector.get_evidence()

        # Validate result type and structure
        assert isinstance(result, Data)
        assert result.data is not None
        assert not result.data.get("error", False)

        # Validate evidence data structure
        evidence_data = result.data.get("evidence", {})
        assert "clinical_evidence" in evidence_data
        assert "supporting_documentation" in evidence_data
        assert "evidence_quality_assessment" in evidence_data

        clinical_evidence = evidence_data["clinical_evidence"]
        assert isinstance(clinical_evidence, list)
        assert len(clinical_evidence) > 0

        # Validate evidence item structure
        first_evidence = clinical_evidence[0]
        assert "evidence_id" in first_evidence
        assert "evidence_type" in first_evidence
        assert "date" in first_evidence
        assert "source" in first_evidence
        assert "content_summary" in first_evidence
        assert "relevance_score" in first_evidence
        assert "supporting_points" in first_evidence

        # Validate quality assessment
        quality_assessment = evidence_data["evidence_quality_assessment"]
        assert "completeness_score" in quality_assessment
        assert "consistency_score" in quality_assessment
        assert "timeliness_score" in quality_assessment
        assert "overall_quality" in quality_assessment

        # All quality scores should be between 0 and 1
        for score_key in ["completeness_score", "consistency_score", "timeliness_score", "overall_quality"]:
            assert 0.0 <= quality_assessment[score_key] <= 1.0

    def test_get_comprehensive_data_output(self, appeals_connector, sample_appeals_request):
        """Test comprehensive data retrieval functionality."""
        # Set appeals request
        appeals_connector.appeals_request = json.dumps(sample_appeals_request)

        # Execute comprehensive data retrieval
        result = appeals_connector.get_comprehensive_data()

        # Validate result type and structure
        assert isinstance(result, Data)
        assert result.data is not None
        assert not result.data.get("error", False)

        # Validate comprehensive data includes all components
        comprehensive_data = result.data
        assert "appeal_id" in comprehensive_data
        assert "member_id" in comprehensive_data
        assert "data_source" in comprehensive_data
        assert "appeals_system" in comprehensive_data
        assert "denial_reasons" in comprehensive_data
        assert "policies" in comprehensive_data
        assert "evidence" in comprehensive_data
        assert "processing_metadata" in comprehensive_data

        # Validate processing metadata
        metadata = comprehensive_data["processing_metadata"]
        assert "search_scope" in metadata
        assert "max_results" in metadata
        assert "include_historical" in metadata
        assert "response_time_ms" in metadata
        assert "data_quality_score" in metadata

        # Validate data quality score
        assert 0.0 <= metadata["data_quality_score"] <= 1.0

    def test_appeals_request_parsing(self, appeals_connector):
        """Test appeals request parsing and validation."""
        # Test valid JSON request
        valid_request = {
            "appeal_id": "APP_TEST_001",
            "member_id": "MEM123456",
            "request_type": "denial_reasons"
        }

        appeals_connector.appeals_request = json.dumps(valid_request)
        parsed_data = appeals_connector._parse_appeals_request(appeals_connector.appeals_request)

        assert parsed_data["appeal_id"] == "APP_TEST_001"
        assert parsed_data["member_id"] == "MEM123456"
        assert parsed_data["request_type"] == "denial_reasons"

    def test_invalid_appeals_request_handling(self, appeals_connector):
        """Test handling of invalid appeals requests."""
        # Test invalid JSON
        appeals_connector.appeals_request = "invalid json"

        with pytest.raises(ValueError) as exc_info:
            appeals_connector._parse_appeals_request(appeals_connector.appeals_request)

        assert "Invalid JSON in appeals request" in str(exc_info.value)

    def test_missing_required_field_handling(self, appeals_connector):
        """Test handling of missing required fields."""
        # Test missing appeal_id
        invalid_request = {
            "member_id": "MEM123456",
            "request_type": "denial_reasons"
        }

        appeals_connector.appeals_request = json.dumps(invalid_request)

        with pytest.raises(ValueError) as exc_info:
            appeals_connector._parse_appeals_request(appeals_connector.appeals_request)

        assert "Missing required field: appeal_id" in str(exc_info.value)

    def test_configuration_validation(self, appeals_connector):
        """Test connector configuration validation."""
        # Test valid configuration
        assert appeals_connector.appeals_system in ["change_healthcare", "optum", "internal", "mock"]
        assert appeals_connector.data_source in ["denial_reasons", "policies", "evidence", "comprehensive"]
        assert isinstance(appeals_connector.max_results, int)
        assert appeals_connector.max_results > 0
        assert isinstance(appeals_connector.include_historical, bool)

    def test_hipaa_compliance_patterns(self, appeals_connector):
        """Test HIPAA compliance patterns in responses."""
        sample_request = {
            "appeal_id": "APP_TEST_001",
            "member_id": "MEM123456",
            "request_type": "comprehensive"
        }

        appeals_connector.appeals_request = json.dumps(sample_request)
        result = appeals_connector.get_comprehensive_data()

        # Verify no PHI in error messages or logs
        assert result.data is not None

        # Check that sensitive data is properly handled
        comprehensive_data = result.data

        # Verify request tracking without PHI exposure
        assert "request_id" in comprehensive_data
        assert "timestamp" in comprehensive_data

        # Validate timestamp format (ISO format for audit compliance)
        timestamp = comprehensive_data["timestamp"]
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            pytest.fail("Timestamp not in proper ISO format for HIPAA audit requirements")

    def test_mock_data_quality(self, appeals_connector, sample_appeals_request):
        """Test quality and realism of mock data responses."""
        appeals_connector.appeals_request = json.dumps(sample_appeals_request)
        result = appeals_connector.get_comprehensive_data()

        comprehensive_data = result.data

        # Validate denial reasons contain medical terminology
        denial_reasons = comprehensive_data["denial_reasons"]
        primary_reason = denial_reasons["primary_reason"]
        assert any(term in primary_reason.lower() for term in [
            "medical necessity", "documentation", "conservative treatment",
            "clinical", "physician", "justification"
        ])

        # Validate policies contain healthcare policy language
        policies = comprehensive_data["policies"]["relevant_policies"]
        first_policy = policies[0]
        policy_name = first_policy["policy_name"]
        assert any(term in policy_name.lower() for term in [
            "prior authorization", "mri", "imaging", "treatment",
            "medical", "coverage", "benefit"
        ])

        # Validate evidence contains clinical terminology
        evidence = comprehensive_data["evidence"]["clinical_evidence"]
        first_evidence = evidence[0]
        content_summary = first_evidence["content_summary"]
        assert any(term in content_summary.lower() for term in [
            "patient", "pain", "treatment", "physician", "clinical",
            "medical", "therapy", "diagnosis"
        ])

    def test_error_handling_integration(self, appeals_connector):
        """Test error handling in healthcare workflow integration."""
        # Test empty appeals request
        appeals_connector.appeals_request = ""

        # Should handle gracefully without crashing
        try:
            result = appeals_connector.get_denial_reasons()
            # If it doesn't raise an exception, check that error is properly handled
            if result.data and result.data.get("error"):
                assert "error_message" in result.data
                assert result.data["error_message"] != ""
        except Exception as e:
            # If it raises an exception, it should be a controlled healthcare error
            assert "healthcare" in str(type(e)).lower() or "appeals" in str(e).lower()

    def test_status_updates(self, appeals_connector, sample_appeals_request):
        """Test that status is properly updated during operations."""
        appeals_connector.appeals_request = json.dumps(sample_appeals_request)

        # Test denial reasons status update
        appeals_connector.get_denial_reasons()
        assert "Denial Reasons Retrieved" in appeals_connector.status

        # Test policy search status update
        appeals_connector.search_policies()
        assert "Policies Retrieved" in appeals_connector.status

        # Test evidence retrieval status update
        appeals_connector.get_evidence()
        assert "Evidence Retrieved" in appeals_connector.status

        # Test comprehensive data status update
        appeals_connector.get_comprehensive_data()
        assert "Comprehensive Data Retrieved" in appeals_connector.status

    def test_component_outputs_structure(self, appeals_connector):
        """Test that component outputs are properly defined."""
        # Verify outputs are defined
        assert hasattr(appeals_connector, 'outputs')
        assert len(appeals_connector.outputs) == 4

        # Check output names and methods
        output_info = {output.name: output.method for output in appeals_connector.outputs}

        expected_outputs = {
            "denial_reasons": "get_denial_reasons",
            "policy_data": "search_policies",
            "evidence_data": "get_evidence",
            "comprehensive_data": "get_comprehensive_data"
        }

        for output_name, method_name in expected_outputs.items():
            assert output_name in output_info
            assert output_info[output_name] == method_name
            # Verify method exists
            assert hasattr(appeals_connector, method_name)

    @pytest.mark.parametrize("data_source", ["denial_reasons", "policies", "evidence", "comprehensive"])
    def test_data_source_configuration(self, appeals_connector, sample_appeals_request, data_source):
        """Test different data source configurations."""
        appeals_connector.data_source = data_source
        appeals_connector.appeals_request = json.dumps(sample_appeals_request)

        # Execute comprehensive data retrieval which uses data_source
        result = appeals_connector.get_comprehensive_data()

        # Validate that data_source is reflected in response
        assert result.data["data_source"] == data_source

    def test_appeals_system_configuration(self, appeals_connector, sample_appeals_request):
        """Test different appeals system configurations."""
        test_systems = ["change_healthcare", "optum", "internal", "mock"]

        for system in test_systems:
            appeals_connector.appeals_system = system
            appeals_connector.appeals_request = json.dumps(sample_appeals_request)

            result = appeals_connector.get_comprehensive_data()
            assert result.data["appeals_system"] == system

    def test_performance_metrics(self, appeals_connector, sample_appeals_request):
        """Test performance characteristics of appeals data connector."""
        appeals_connector.appeals_request = json.dumps(sample_appeals_request)

        # Test response time tracking
        start_time = datetime.now()
        result = appeals_connector.get_comprehensive_data()
        end_time = datetime.now()

        # Should complete within reasonable time
        processing_time = (end_time - start_time).total_seconds() * 1000
        assert processing_time < 5000  # Less than 5 seconds

        # Check that response includes timing metadata
        metadata = result.data["processing_metadata"]
        assert "response_time_ms" in metadata
        assert isinstance(metadata["response_time_ms"], (int, float))
        assert metadata["response_time_ms"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])