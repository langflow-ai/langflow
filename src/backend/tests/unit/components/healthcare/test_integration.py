"""Integration tests for Healthcare Connector components."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from langflow.components.healthcare.ehr_connector import EHRConnector
from langflow.custom.genesis.spec.mapper import ComponentMapper
from langflow.schema.data import Data
from langflow.schema.message import Message


class TestHealthcareIntegration:
    """Integration test cases for Healthcare components."""

    @pytest.fixture
    def component_mapper(self):
        """Create component mapper for testing."""
        return ComponentMapper()

    @pytest.fixture
    def ehr_connector(self):
        """Create an EHR connector for integration testing."""
        connector = EHRConnector()

        # Set up for integration testing
        connector.patient_query = '{"patient_id": "PAT123456", "operation": "get_patient_data"}'
        connector.ehr_system = "epic"
        connector.fhir_version = "R4"
        connector.authentication_type = "oauth2"
        connector.base_url = "https://test-ehr.example.com"
        connector.operation = "get_patient_data"
        connector.test_mode = True
        connector.mock_mode = True
        connector.audit_logging = True

        return connector

    def test_component_mapper_ehr_integration(self, component_mapper):
        """Test EHR connector integration with ComponentMapper."""
        # Test that EHR connector is properly mapped
        mapping = component_mapper.map_component("genesis:ehr_connector")

        assert mapping["component"] == "EHRConnector"
        assert mapping["config"]["ehr_system"] == "epic"
        assert mapping["config"]["fhir_version"] == "R4"
        assert mapping["config"]["authentication_type"] == "oauth2"
        assert mapping["config"]["hipaa_compliance"] is True

    def test_component_mapper_io_mapping(self, component_mapper):
        """Test I/O mapping for EHR connector."""
        io_mapping = component_mapper.get_component_io_mapping("EHRConnector")

        assert io_mapping["input_field"] == "patient_query"
        assert io_mapping["output_field"] == "ehr_data"
        assert "Data" in io_mapping["output_types"]
        assert any(t in io_mapping["input_types"] for t in ["str", "Message", "Data"])

    def test_tool_mode_detection(self, component_mapper):
        """Test that EHR connector is correctly detected as a tool."""
        is_tool = component_mapper.is_tool_component("genesis:ehr_connector")
        assert is_tool is True

    def test_healthcare_category_mapping(self, component_mapper):
        """Test healthcare category mapping."""
        mapping = component_mapper.map_component("genesis:ehr_connector")

        # Check healthcare-specific metadata
        healthcare_metadata = mapping.get("healthcare_metadata", {})
        assert healthcare_metadata["hipaa_compliant"] is True
        assert healthcare_metadata["phi_handling"] is True
        assert healthcare_metadata["encryption_required"] is True

    def test_end_to_end_patient_workflow(self, ehr_connector):
        """Test complete end-to-end patient data workflow."""
        # Test patient search
        search_criteria = {"name": "Johnson", "birthDate": "1985"}

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            # Mock response for patient search
            mock_search_response = Data(data={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "Patient", "id": "PAT123456"}}
                ]
            })
            mock_execute.return_value = mock_search_response

            patients = ehr_connector.search_patients(search_criteria)

            assert len(patients) == 1
            assert patients[0]["resourceType"] == "Patient"
            assert patients[0]["id"] == "PAT123456"

        # Test getting patient data
        patient_id = "PAT123456"

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            # Mock response for patient data
            mock_patient_response = Data(data={
                "resourceType": "Patient",
                "id": patient_id,
                "name": [{"family": "Johnson", "given": ["Sarah"]}]
            })
            mock_execute.return_value = mock_patient_response

            patient_data = ehr_connector.get_patient_data(patient_id)

            assert patient_data["resourceType"] == "Patient"
            assert patient_data["id"] == patient_id

    def test_multi_operation_healthcare_workflow(self, ehr_connector):
        """Test complex workflow with multiple EHR operations."""
        patient_id = "PAT123456"

        # Mock responses for different operations
        mock_responses = {
            "get_patient_data": Data(data={
                "resourceType": "Patient",
                "id": patient_id,
                "name": [{"family": "Johnson", "given": ["Sarah"]}]
            }),
            "get_observations": Data(data={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "Observation", "id": "obs-001"}}
                ]
            }),
            "get_medications": Data(data={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "MedicationRequest", "id": "med-001"}}
                ]
            }),
            "get_conditions": Data(data={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "Condition", "id": "cond-001"}}
                ]
            })
        }

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            # Configure mock to return different responses based on operation
            def mock_workflow(request_data):
                operation = request_data.get("operation")
                return mock_responses.get(operation, Data(data={}))

            mock_execute.side_effect = mock_workflow

            # Execute comprehensive patient data collection
            patient_data = ehr_connector.get_patient_data(patient_id)
            observations = ehr_connector.get_observations(patient_id)
            medications = ehr_connector.get_medications(patient_id)
            conditions = ehr_connector.get_conditions(patient_id)

            # Verify all operations completed successfully
            assert patient_data["resourceType"] == "Patient"
            assert len(observations) == 1
            assert observations[0]["resourceType"] == "Observation"
            assert len(medications) == 1
            assert medications[0]["resourceType"] == "MedicationRequest"
            assert len(conditions) == 1
            assert conditions[0]["resourceType"] == "Condition"

    def test_hipaa_compliance_integration(self, ehr_connector):
        """Test HIPAA compliance throughout the workflow."""
        patient_data = {
            "patient_id": "PAT123456",
            "operation": "get_patient_data",
            "sensitive_data": "test_phi"
        }

        # Track audit logging
        with patch.object(ehr_connector._audit_logger, 'info') as mock_audit_log:
            result = ehr_connector.execute_healthcare_workflow(patient_data)

            # Verify audit logging occurred
            assert mock_audit_log.call_count >= 2  # Start and complete

            # Check compliance metadata
            metadata = result.metadata
            assert metadata["hipaa_compliant"] is True
            assert metadata["phi_protected"] is True
            assert metadata["audit_logged"] is True

    def test_error_propagation_integration(self, ehr_connector):
        """Test error handling integration across components."""
        invalid_data = {"invalid": "data"}

        # Test validation error propagation
        with patch.object(ehr_connector, 'validate_healthcare_data', side_effect=ValueError("Invalid data")):
            result = ehr_connector.execute_healthcare_workflow(invalid_data)

            assert result.data["error"] is True
            assert result.data["error_type"] == "ValueError"

    def test_performance_monitoring_integration(self, ehr_connector):
        """Test performance monitoring integration."""
        patient_data = {
            "patient_id": "PAT123456",
            "operation": "get_patient_data"
        }

        result = ehr_connector.execute_healthcare_workflow(patient_data)

        # Check performance metrics
        metadata = result.metadata
        assert "processing_time_seconds" in metadata
        assert isinstance(metadata["processing_time_seconds"], float)
        assert metadata["processing_time_seconds"] >= 0

    def test_mock_to_live_mode_integration(self, ehr_connector):
        """Test switching between mock and live modes."""
        patient_data = {"patient_id": "PAT123456", "operation": "get_patient_data"}

        # Test mock mode
        ehr_connector.mock_mode = True
        mock_result = ehr_connector.execute_healthcare_workflow(patient_data)
        assert mock_result.metadata["transaction_type"] == "mock_response"

        # Test live mode
        ehr_connector.mock_mode = False
        live_result = ehr_connector.execute_healthcare_workflow(patient_data)
        assert live_result.metadata["transaction_type"] == "live_response"

    def test_different_ehr_systems_integration(self, ehr_connector):
        """Test integration with different EHR systems."""
        ehr_systems = ["epic", "cerner", "allscripts", "athenahealth"]

        for ehr_system in ehr_systems:
            ehr_connector.ehr_system = ehr_system

            patient_data = {
                "patient_id": "PAT123456",
                "operation": "get_patient_data",
                "ehr_system": ehr_system
            }

            result = ehr_connector.execute_healthcare_workflow(patient_data)

            # Verify successful processing for all EHR systems
            assert not result.data.get("error", False)
            assert result.metadata["component"] == "EHRConnector"

    def test_fhir_version_compatibility_integration(self, ehr_connector):
        """Test FHIR version compatibility integration."""
        fhir_versions = ["R4", "STU3", "DSTU2"]

        for fhir_version in fhir_versions:
            ehr_connector.fhir_version = fhir_version

            patient_data = {
                "patient_id": "PAT123456",
                "operation": "get_patient_data",
                "fhir_version": fhir_version
            }

            result = ehr_connector.execute_healthcare_workflow(patient_data)

            # Verify successful processing for all FHIR versions
            assert not result.data.get("error", False)

    def test_authentication_type_integration(self, ehr_connector):
        """Test different authentication types integration."""
        auth_types = ["oauth2", "basic", "api_key"]

        for auth_type in auth_types:
            ehr_connector.authentication_type = auth_type

            patient_data = {
                "patient_id": "PAT123456",
                "operation": "get_patient_data",
                "authentication_type": auth_type
            }

            result = ehr_connector.execute_healthcare_workflow(patient_data)

            # Verify successful processing for all auth types
            assert not result.data.get("error", False)

    def test_tool_integration_workflow(self, ehr_connector):
        """Test EHR connector as a tool in agent workflows."""
        # Simulate tool usage in agent context
        tool_request = {
            "patient_id": "PAT123456",
            "operation": "get_patient_data",
            "tool_mode": True
        }

        # Test that tool mode inputs are properly configured
        tool_mode_inputs = []
        for input_field in ehr_connector.inputs:
            if hasattr(input_field, 'tool_mode') and input_field.tool_mode:
                tool_mode_inputs.append(input_field.name)

        expected_tool_inputs = [
            "patient_query", "ehr_system", "fhir_version",
            "authentication_type", "base_url", "operation"
        ]

        for expected_input in expected_tool_inputs:
            assert expected_input in tool_mode_inputs

    def test_data_flow_integration(self, ehr_connector):
        """Test data flow through the entire healthcare connector."""
        # Test JSON input
        json_input = '{"patient_id": "PAT123456", "operation": "get_patient_data"}'
        ehr_connector.patient_query = json_input

        result = ehr_connector.build_ehr_response()

        assert isinstance(result, Data)
        assert result.data is not None
        assert result.metadata is not None

        # Test string input
        string_input = "PAT789012"
        ehr_connector.patient_query = string_input

        result = ehr_connector.build_ehr_response()

        assert isinstance(result, Data)
        assert result.data is not None

    def test_concurrent_request_handling(self, ehr_connector):
        """Test handling of concurrent requests (request ID uniqueness)."""
        import threading
        import time

        results = []

        def make_request():
            patient_data = {"patient_id": "PAT123456", "operation": "get_patient_data"}
            result = ehr_connector.execute_healthcare_workflow(patient_data)
            results.append(result.metadata["request_id"])

        # Simulate concurrent requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All request IDs should be unique
        assert len(set(results)) == len(results)

    def test_security_integration(self, ehr_connector):
        """Test security features integration."""
        # Test PHI data handling
        phi_data = {
            "patient_id": "PAT123456",
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "operation": "get_patient_data"
        }

        with patch.object(ehr_connector, '_log_phi_access') as mock_log:
            result = ehr_connector.execute_healthcare_workflow(phi_data)

            # Verify PHI access was logged
            mock_log.assert_called()

    def test_configuration_validation_integration(self, ehr_connector):
        """Test configuration validation integration."""
        # Test valid configuration
        valid_config = {
            "ehr_system": "epic",
            "fhir_version": "R4",
            "authentication_type": "oauth2"
        }

        for key, value in valid_config.items():
            setattr(ehr_connector, key, value)

        patient_data = {"patient_id": "PAT123456", "operation": "get_patient_data"}
        result = ehr_connector.execute_healthcare_workflow(patient_data)

        assert not result.data.get("error", False)

    def test_comprehensive_fhir_resource_integration(self, ehr_connector):
        """Test comprehensive FHIR resource handling integration."""
        fhir_operations = [
            "get_patient_data",
            "get_observations",
            "get_medications",
            "get_conditions",
            "get_providers",
            "get_care_team"
        ]

        for operation in fhir_operations:
            patient_data = {
                "patient_id": "PAT123456",
                "operation": operation
            }

            result = ehr_connector.execute_healthcare_workflow(patient_data)

            # All operations should complete successfully
            assert not result.data.get("error", False)
            assert result.metadata["component"] == "EHRConnector"

            # Check that response contains appropriate FHIR resource types
            if operation == "get_patient_data":
                assert result.data.get("resourceType") == "Patient"
            elif operation in ["get_observations", "get_medications", "get_conditions"]:
                assert result.data.get("resourceType") == "Bundle"
            elif operation == "get_care_team":
                assert result.data.get("resourceType") == "CareTeam"

    def test_healthcare_workflow_state_management(self, ehr_connector):
        """Test state management throughout healthcare workflows."""
        # Test that request ID and timing are maintained throughout workflow
        patient_data = {"patient_id": "PAT123456", "operation": "get_patient_data"}

        # Execute workflow and check state consistency
        result = ehr_connector.execute_healthcare_workflow(patient_data)

        request_id = result.metadata["request_id"]
        processing_time = result.metadata["processing_time_seconds"]

        # Verify state consistency
        assert request_id is not None
        assert request_id.startswith("HC-")
        assert processing_time >= 0
        assert isinstance(processing_time, float)