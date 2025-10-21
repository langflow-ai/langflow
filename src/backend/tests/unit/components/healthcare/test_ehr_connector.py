"""Unit tests for EHR Healthcare Connector."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from langflow.components.healthcare.ehr_connector import EHRConnector
from langflow.schema.data import Data
from langflow.schema.message import Message


class TestEHRConnector:
    """Test cases for EHR Healthcare Connector."""

    @pytest.fixture
    def ehr_connector(self):
        """Create an EHR connector instance for testing."""
        connector = EHRConnector()

        # Set test values for inputs
        connector.patient_query = '{"patient_id": "PAT123456", "operation": "get_patient_data"}'
        connector.ehr_system = "epic"
        connector.fhir_version = "R4"
        connector.authentication_type = "oauth2"
        connector.base_url = "${EHR_BASE_URL}"
        connector.operation = "get_patient_data"
        connector.test_mode = True
        connector.mock_mode = True
        connector.audit_logging = True
        connector.timeout_seconds = "30"

        return connector

    @pytest.fixture
    def sample_patient_data(self):
        """Sample patient data for testing."""
        return {
            "patient_id": "PAT123456",
            "operation": "get_patient_data",
            "ehr_system": "epic",
            "fhir_version": "R4"
        }

    def test_component_initialization(self, ehr_connector):
        """Test that the EHR connector initializes correctly."""
        assert ehr_connector.display_name == "EHR Connector"
        assert ehr_connector.description == "Electronic Health Record integration with FHIR R4 and HL7 support"
        assert ehr_connector.icon == "FileText"
        assert ehr_connector.name == "EHRConnector"
        assert ehr_connector.hipaa_compliant is True
        assert ehr_connector.phi_handling is True
        assert ehr_connector.encryption_required is True
        assert ehr_connector.audit_trail is True

    def test_component_inputs(self, ehr_connector):
        """Test that the component has the required inputs."""
        input_names = [input_field.name for input_field in ehr_connector.inputs]

        expected_inputs = [
            "patient_query",
            "ehr_system",
            "fhir_version",
            "authentication_type",
            "base_url",
            "operation",
            # Base healthcare inputs
            "api_key",
            "client_id",
            "client_secret",
            "test_mode",
            "mock_mode",
            "audit_logging",
            "timeout_seconds"
        ]

        for expected_input in expected_inputs:
            assert expected_input in input_names

    def test_component_outputs(self, ehr_connector):
        """Test that the component has the required output."""
        assert len(ehr_connector.outputs) == 1
        assert ehr_connector.outputs[0].name == "ehr_data"
        assert ehr_connector.outputs[0].display_name == "EHR Data"

    def test_get_required_fields(self, ehr_connector):
        """Test that required fields are correctly identified."""
        required_fields = ehr_connector.get_required_fields()
        assert "operation" in required_fields

    def test_build_ehr_response_with_json_query(self, ehr_connector):
        """Test building EHR response with JSON patient query."""
        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_response = Data(data={"test": "response"})
            mock_execute.return_value = mock_response

            result = ehr_connector.build_ehr_response()

            assert isinstance(result, Data)
            mock_execute.assert_called_once()

            # Check the call arguments
            call_args = mock_execute.call_args[0][0]
            assert call_args["patient_id"] == "PAT123456"
            assert call_args["operation"] == "get_patient_data"
            assert call_args["ehr_system"] == "epic"
            assert call_args["fhir_version"] == "R4"

    def test_build_ehr_response_with_string_query(self, ehr_connector):
        """Test building EHR response with simple string patient query."""
        ehr_connector.patient_query = "PAT789012"

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_response = Data(data={"test": "response"})
            mock_execute.return_value = mock_response

            result = ehr_connector.build_ehr_response()

            assert isinstance(result, Data)
            mock_execute.assert_called_once()

            # Check the call arguments
            call_args = mock_execute.call_args[0][0]
            assert call_args["patient_id"] == "PAT789012"
            assert call_args["operation"] == "get_patient_data"

    def test_build_ehr_response_error_handling(self, ehr_connector):
        """Test error handling in build_ehr_response."""
        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_execute.side_effect = Exception("Test error")

            with patch.object(ehr_connector, '_handle_healthcare_error') as mock_error_handler:
                mock_error_handler.return_value = Data(data={"error": True})

                result = ehr_connector.build_ehr_response()

                assert isinstance(result, Data)
                mock_error_handler.assert_called_once()

    def test_get_mock_response_patient_search(self, ehr_connector, sample_patient_data):
        """Test mock response for patient search operation."""
        sample_patient_data["operation"] = "search_patients"

        response = ehr_connector.get_mock_response(sample_patient_data)

        assert response["resourceType"] == "Bundle"
        assert response["type"] == "searchset"
        assert response["total"] == 1
        assert len(response["entry"]) == 1
        assert response["entry"][0]["resource"]["resourceType"] == "Patient"
        assert "processing_time_ms" in response

    def test_get_mock_response_get_patient_data(self, ehr_connector, sample_patient_data):
        """Test mock response for get patient data operation."""
        response = ehr_connector.get_mock_response(sample_patient_data)

        assert response["resourceType"] == "Patient"
        assert response["id"] == "PAT123456"
        assert response["name"][0]["family"] == "Johnson"
        assert response["name"][0]["given"] == ["Sarah", "Elizabeth"]
        assert response["gender"] == "female"
        assert response["birthDate"] == "1985-03-15"
        assert "processing_time_ms" in response

    def test_get_mock_response_get_observations(self, ehr_connector, sample_patient_data):
        """Test mock response for get observations operation."""
        sample_patient_data["operation"] = "get_observations"

        response = ehr_connector.get_mock_response(sample_patient_data)

        assert response["resourceType"] == "Bundle"
        assert response["type"] == "searchset"
        assert response["total"] == 3
        assert len(response["entry"]) >= 2

        # Check first observation (blood pressure)
        bp_obs = response["entry"][0]["resource"]
        assert bp_obs["resourceType"] == "Observation"
        assert bp_obs["status"] == "final"
        assert bp_obs["code"]["coding"][0]["code"] == "85354-9"
        assert len(bp_obs["component"]) == 2  # Systolic and Diastolic

    def test_get_mock_response_get_medications(self, ehr_connector, sample_patient_data):
        """Test mock response for get medications operation."""
        sample_patient_data["operation"] = "get_medications"

        response = ehr_connector.get_mock_response(sample_patient_data)

        assert response["resourceType"] == "Bundle"
        assert response["type"] == "searchset"
        assert response["total"] == 2
        assert len(response["entry"]) == 2

        # Check first medication (Metformin)
        med1 = response["entry"][0]["resource"]
        assert med1["resourceType"] == "MedicationRequest"
        assert med1["status"] == "active"
        assert "860975" in str(med1["medicationCodeableConcept"]["coding"][0]["code"])  # RxNorm code for Metformin

    def test_get_mock_response_get_conditions(self, ehr_connector, sample_patient_data):
        """Test mock response for get conditions operation."""
        sample_patient_data["operation"] = "get_conditions"

        response = ehr_connector.get_mock_response(sample_patient_data)

        assert response["resourceType"] == "Bundle"
        assert response["type"] == "searchset"
        assert response["total"] == 3
        assert len(response["entry"]) >= 2

        # Check first condition (Diabetes)
        diabetes = response["entry"][0]["resource"]
        assert diabetes["resourceType"] == "Condition"
        assert diabetes["clinicalStatus"]["coding"][0]["code"] == "active"
        assert "44054006" in str(diabetes["code"]["coding"][0]["code"])  # SNOMED code for Type 2 DM

    def test_get_mock_response_get_providers(self, ehr_connector, sample_patient_data):
        """Test mock response for get providers operation."""
        sample_patient_data["operation"] = "get_providers"

        response = ehr_connector.get_mock_response(sample_patient_data)

        assert response["resourceType"] == "Bundle"
        assert response["type"] == "searchset"
        assert response["total"] == 2
        assert len(response["entry"]) >= 1

        # Check provider data
        provider = response["entry"][0]["resource"]
        assert provider["resourceType"] == "Practitioner"
        assert provider["active"] is True
        assert provider["name"][0]["family"] == "Smith"
        assert "1234567890" in str(provider["identifier"][0]["value"])  # NPI

    def test_get_mock_response_get_care_team(self, ehr_connector, sample_patient_data):
        """Test mock response for get care team operation."""
        sample_patient_data["operation"] = "get_care_team"

        response = ehr_connector.get_mock_response(sample_patient_data)

        assert response["resourceType"] == "CareTeam"
        assert response["status"] == "active"
        assert response["subject"]["reference"] == f"Patient/{sample_patient_data['patient_id']}"
        assert len(response["participant"]) == 2

        # Check participants
        cardiologist = response["participant"][0]
        assert "17561000" in str(cardiologist["role"][0]["coding"][0]["code"])  # SNOMED Cardiologist

        pharmacist = response["participant"][1]
        assert "46255001" in str(pharmacist["role"][0]["coding"][0]["code"])  # SNOMED Pharmacist

    def test_get_mock_response_unknown_operation(self, ehr_connector, sample_patient_data):
        """Test mock response for unknown operation."""
        sample_patient_data["operation"] = "unknown_operation"

        response = ehr_connector.get_mock_response(sample_patient_data)

        assert response["resourceType"] == "OperationOutcome"
        assert response["issue"][0]["severity"] == "error"
        assert response["issue"][0]["code"] == "not-supported"
        assert "unknown_operation" in response["issue"][0]["diagnostics"]

    def test_process_healthcare_request(self, ehr_connector, sample_patient_data):
        """Test processing healthcare request (production mode)."""
        with patch.object(ehr_connector, 'get_mock_response') as mock_get_mock:
            mock_response = {"test": "data"}
            mock_get_mock.return_value = mock_response

            result = ehr_connector.process_healthcare_request(sample_patient_data)

            assert "production_note" in result
            assert "ehr_system_configured" in result
            assert "authentication_type" in result
            assert result["ehr_system_configured"] == "epic"
            assert result["authentication_type"] == "oauth2"

    def test_search_patients_method(self, ehr_connector):
        """Test the search_patients convenience method."""
        criteria = {"name": "Johnson", "birthDate": "1985-03-15"}

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_response = Data(data={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "Patient", "id": "PAT123456"}}
                ]
            })
            mock_execute.return_value = mock_response

            result = ehr_connector.search_patients(criteria)

            assert len(result) == 1
            assert result[0]["resourceType"] == "Patient"
            assert result[0]["id"] == "PAT123456"

            # Check call arguments
            call_args = mock_execute.call_args[0][0]
            assert call_args["operation"] == "search_patients"
            assert call_args["name"] == "Johnson"

    def test_get_patient_data_method(self, ehr_connector):
        """Test the get_patient_data convenience method."""
        patient_id = "PAT123456"

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_response = Data(data={"resourceType": "Patient", "id": patient_id})
            mock_execute.return_value = mock_response

            result = ehr_connector.get_patient_data(patient_id)

            assert result["resourceType"] == "Patient"
            assert result["id"] == patient_id

            # Check call arguments
            call_args = mock_execute.call_args[0][0]
            assert call_args["operation"] == "get_patient_data"
            assert call_args["patient_id"] == patient_id

    def test_get_observations_method(self, ehr_connector):
        """Test the get_observations convenience method."""
        patient_id = "PAT123456"
        category = "vital-signs"

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_response = Data(data={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "Observation", "id": "obs-001"}}
                ]
            })
            mock_execute.return_value = mock_response

            result = ehr_connector.get_observations(patient_id, category)

            assert len(result) == 1
            assert result[0]["resourceType"] == "Observation"

            # Check call arguments
            call_args = mock_execute.call_args[0][0]
            assert call_args["operation"] == "get_observations"
            assert call_args["patient_id"] == patient_id
            assert call_args["category"] == category

    def test_get_medications_method(self, ehr_connector):
        """Test the get_medications convenience method."""
        patient_id = "PAT123456"

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_response = Data(data={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "MedicationRequest", "id": "med-001"}}
                ]
            })
            mock_execute.return_value = mock_response

            result = ehr_connector.get_medications(patient_id)

            assert len(result) == 1
            assert result[0]["resourceType"] == "MedicationRequest"

    def test_get_conditions_method(self, ehr_connector):
        """Test the get_conditions convenience method."""
        patient_id = "PAT123456"

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_response = Data(data={
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "Condition", "id": "cond-001"}}
                ]
            })
            mock_execute.return_value = mock_response

            result = ehr_connector.get_conditions(patient_id)

            assert len(result) == 1
            assert result[0]["resourceType"] == "Condition"

    def test_update_patient_data_success(self, ehr_connector):
        """Test successful patient data update."""
        patient_id = "PAT123456"
        update_data = {"address": "new address"}

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_response = Data(data={"success": True})
            mock_execute.return_value = mock_response

            result = ehr_connector.update_patient_data(patient_id, update_data)

            assert result is True

            # Check call arguments
            call_args = mock_execute.call_args[0][0]
            assert call_args["operation"] == "update_patient_data"
            assert call_args["patient_id"] == patient_id
            assert call_args["update_data"] == update_data

    def test_update_patient_data_failure(self, ehr_connector):
        """Test failed patient data update."""
        patient_id = "PAT123456"
        update_data = {"address": "new address"}

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_response = Data(data={"error": True, "message": "Update failed"})
            mock_execute.return_value = mock_response

            result = ehr_connector.update_patient_data(patient_id, update_data)

            assert result is False

    def test_update_patient_data_exception(self, ehr_connector):
        """Test patient data update with exception."""
        patient_id = "PAT123456"
        update_data = {"address": "new address"}

        with patch.object(ehr_connector, 'execute_healthcare_workflow') as mock_execute:
            mock_execute.side_effect = Exception("Connection error")

            result = ehr_connector.update_patient_data(patient_id, update_data)

            assert result is False

    def test_fhir_compliance_in_mock_data(self, ehr_connector, sample_patient_data):
        """Test that mock data follows FHIR R4 standards."""
        # Test patient data compliance
        patient_response = ehr_connector.get_mock_response(sample_patient_data)

        # Check FHIR Patient resource structure
        assert patient_response["resourceType"] == "Patient"
        assert "identifier" in patient_response
        assert "name" in patient_response
        assert "gender" in patient_response
        assert "birthDate" in patient_response

        # Check identifier structure (MRN)
        identifier = patient_response["identifier"][0]
        assert "system" in identifier
        assert "value" in identifier
        assert "type" in identifier

        # Test observations data compliance
        sample_patient_data["operation"] = "get_observations"
        obs_response = ehr_connector.get_mock_response(sample_patient_data)

        # Check FHIR Bundle structure
        assert obs_response["resourceType"] == "Bundle"
        assert obs_response["type"] == "searchset"
        assert "entry" in obs_response

        # Check FHIR Observation resource structure
        observation = obs_response["entry"][0]["resource"]
        assert observation["resourceType"] == "Observation"
        assert "status" in observation
        assert "code" in observation
        assert "subject" in observation
        assert "effectiveDateTime" in observation

    def test_medical_coding_standards(self, ehr_connector, sample_patient_data):
        """Test that mock data includes proper medical coding standards."""
        # Test conditions with ICD-10 and SNOMED codes
        sample_patient_data["operation"] = "get_conditions"
        conditions_response = ehr_connector.get_mock_response(sample_patient_data)

        condition = conditions_response["entry"][0]["resource"]
        codings = condition["code"]["coding"]

        # Should have both SNOMED CT and ICD-10 codes
        snomed_code = next((c for c in codings if "snomed.info/sct" in c["system"]), None)
        icd10_code = next((c for c in codings if "icd-10-cm" in c["system"]), None)

        assert snomed_code is not None
        assert icd10_code is not None
        assert snomed_code["code"] == "44054006"  # SNOMED for Type 2 DM
        assert icd10_code["code"] == "E11.9"     # ICD-10 for Type 2 DM

        # Test medications with RxNorm codes
        sample_patient_data["operation"] = "get_medications"
        meds_response = ehr_connector.get_mock_response(sample_patient_data)

        medication = meds_response["entry"][0]["resource"]
        med_coding = medication["medicationCodeableConcept"]["coding"][0]

        assert "rxnorm" in med_coding["system"]
        assert med_coding["code"] == "860975"  # RxNorm code for Metformin 500mg

    def test_ehr_system_specific_responses(self, ehr_connector, sample_patient_data):
        """Test that responses adapt to different EHR systems."""
        # Test Epic system
        sample_patient_data["ehr_system"] = "epic"
        epic_response = ehr_connector.get_mock_response(sample_patient_data)
        assert "epic" in str(epic_response.get("meta", {}).get("source", ""))

        # Test Cerner system
        sample_patient_data["ehr_system"] = "cerner"
        cerner_response = ehr_connector.get_mock_response(sample_patient_data)
        assert "cerner" in str(cerner_response.get("meta", {}).get("source", ""))

    def test_performance_metrics_inclusion(self, ehr_connector, sample_patient_data):
        """Test that all responses include performance metrics."""
        operations = [
            "search_patients", "get_patient_data", "get_observations",
            "get_medications", "get_conditions", "get_providers", "get_care_team"
        ]

        for operation in operations:
            sample_patient_data["operation"] = operation
            response = ehr_connector.get_mock_response(sample_patient_data)

            assert "processing_time_ms" in response
            assert isinstance(response["processing_time_ms"], int)
            assert response["processing_time_ms"] > 0

    @pytest.mark.parametrize("ehr_system", ["epic", "cerner", "allscripts", "athenahealth"])
    def test_multiple_ehr_systems(self, ehr_connector, sample_patient_data, ehr_system):
        """Test compatibility with multiple EHR systems."""
        sample_patient_data["ehr_system"] = ehr_system
        ehr_connector.ehr_system = ehr_system

        response = ehr_connector.get_mock_response(sample_patient_data)

        # All EHR systems should return valid FHIR data
        assert response["resourceType"] == "Patient"
        assert response["id"] == sample_patient_data["patient_id"]

    @pytest.mark.parametrize("fhir_version", ["R4", "STU3", "DSTU2"])
    def test_fhir_version_compatibility(self, ehr_connector, sample_patient_data, fhir_version):
        """Test compatibility with different FHIR versions."""
        sample_patient_data["fhir_version"] = fhir_version
        ehr_connector.fhir_version = fhir_version

        response = ehr_connector.get_mock_response(sample_patient_data)

        # All FHIR versions should return valid patient data
        assert response["resourceType"] == "Patient"
        assert response["id"] == sample_patient_data["patient_id"]

    def test_hipaa_audit_logging(self, ehr_connector):
        """Test that HIPAA audit logging is properly implemented."""
        # This test verifies the audit logging functionality from the base class
        assert hasattr(ehr_connector, '_audit_logger')
        assert hasattr(ehr_connector, '_log_phi_access')
        assert ehr_connector.audit_logging is True

        # Test PHI validation
        test_data = {
            "patient_id": "PAT123456",
            "patient_name": "John Doe",
            "dob": "1980-01-01"
        }

        # This should not raise an exception
        is_valid = ehr_connector._validate_phi_data(test_data)
        assert is_valid is True

    def test_error_handling_without_phi_exposure(self, ehr_connector):
        """Test that error handling doesn't expose PHI data."""
        test_error = Exception("Patient PAT123456 not found in database")

        with patch.object(ehr_connector, '_audit_logger') as mock_logger:
            error_response = ehr_connector._handle_healthcare_error(test_error, "test_context")

            # Check that the returned error doesn't contain PHI
            assert "PAT123456" not in str(error_response.data)
            assert error_response.data["error"] is True
            assert error_response.data["error_message"] == "Healthcare service error occurred"

            # But audit logger should have the full error for internal use
            mock_logger.error.assert_called_once()
            assert "PAT123456" in str(mock_logger.error.call_args)

    def test_data_anonymization(self, ehr_connector):
        """Test data anonymization for logging."""
        sensitive_data = {
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "api_key": "sk-1234567890abcdef",
            "normal_field": "normal_value"
        }

        anonymized = ehr_connector._anonymize_for_logging(sensitive_data)

        assert anonymized["patient_name"] == "***Doe"
        assert anonymized["ssn"] == "***6789"
        assert anonymized["api_key"] == "***cdef"
        assert anonymized["normal_field"] == "normal_value"

    def test_compliance_metadata_in_responses(self, ehr_connector):
        """Test that responses include compliance metadata."""
        test_data = {"patient_id": "PAT123456", "operation": "get_patient_data"}

        with patch.object(ehr_connector, 'get_mock_response') as mock_get_mock:
            mock_get_mock.return_value = {"test": "data"}

            response = ehr_connector.execute_healthcare_workflow(test_data)

            # Check that compliance metadata is included
            metadata = response.metadata
            assert metadata["hipaa_compliant"] is True
            assert metadata["phi_protected"] is True
            assert metadata["audit_logged"] is True
            assert metadata["component"] == "EHRConnector"
            assert "processing_timestamp" in metadata
            assert "request_id" in metadata

    def test_tool_mode_compatibility(self, ehr_connector):
        """Test that the component works correctly in tool mode."""
        # Check that key inputs have tool_mode=True
        tool_mode_inputs = []
        for input_field in ehr_connector.inputs:
            if hasattr(input_field, 'tool_mode') and input_field.tool_mode:
                tool_mode_inputs.append(input_field.name)

        expected_tool_inputs = [
            "patient_query", "ehr_system", "fhir_version", "authentication_type",
            "base_url", "operation", "test_mode", "mock_mode", "audit_logging", "timeout_seconds"
        ]

        for expected_input in expected_tool_inputs:
            assert expected_input in tool_mode_inputs