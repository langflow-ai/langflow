"""Unit tests for ClinicalNLPConnector."""

import pytest
from langflow.components.healthcare.clinical_nlp_connector import ClinicalNLPConnector
from langflow.schema.data import Data


class TestClinicalNLPConnector:
    """Test suite for ClinicalNLPConnector."""

    def test_connector_initialization(self):
        """Test that the connector initializes correctly."""
        connector = ClinicalNLPConnector()
        assert connector.display_name == "Clinical NLP Connector"
        assert connector.name == "ClinicalNLPConnector"
        assert connector.icon == "FileText"

    def test_required_fields(self):
        """Test that required fields are correctly defined."""
        connector = ClinicalNLPConnector()
        required_fields = connector.get_required_fields()
        assert "clinical_text" in required_fields
        assert "analysis_type" in required_fields

    def test_entity_extraction(self):
        """Test clinical entity extraction functionality."""
        connector = ClinicalNLPConnector()
        request_data = {
            "clinical_text": "Patient has type 2 diabetes and takes metformin 500mg twice daily.",
            "analysis_type": "entity_extraction",
            "medical_specialty": "endocrinology"
        }

        response = connector.get_mock_response(request_data)

        assert response["status"] == "success"
        assert "entities" in response
        assert "medications" in response["entities"]
        assert "conditions" in response["entities"]

    def test_clinical_reasoning_analysis(self):
        """Test clinical reasoning extraction."""
        connector = ClinicalNLPConnector()
        request_data = {
            "clinical_text": "Patient presents with chest pain and shortness of breath.",
            "analysis_type": "clinical_reasoning",
            "medical_specialty": "cardiology"
        }

        response = connector.get_mock_response(request_data)

        assert response["status"] == "success"
        assert "clinical_reasoning" in response
        assert "assessment" in response["clinical_reasoning"]
        assert "plan" in response["clinical_reasoning"]

    def test_medication_analysis(self):
        """Test medication-specific analysis."""
        connector = ClinicalNLPConnector()
        request_data = {
            "clinical_text": "Patient taking metformin and lisinopril.",
            "analysis_type": "medication_analysis",
            "extract_medications": True
        }

        response = connector.get_mock_response(request_data)

        assert response["status"] == "success"
        assert "medication_analysis" in response
        assert "identified_medications" in response["medication_analysis"]
        assert "drug_interactions" in response["medication_analysis"]

    def test_phi_detection(self):
        """Test PHI detection in clinical text."""
        connector = ClinicalNLPConnector()

        # Test with potentially sensitive text
        phi_text = "Patient John Doe DOB 01/01/1980"
        assert connector._contains_obvious_phi(phi_text) == True

        # Test with non-PHI text
        non_phi_text = "Patient presents with diabetes"
        assert connector._contains_obvious_phi(non_phi_text) == False

    def test_empty_text_handling(self):
        """Test handling of empty clinical text."""
        connector = ClinicalNLPConnector()
        request_data = {
            "clinical_text": "",
            "analysis_type": "entity_extraction"
        }

        with pytest.raises(ValueError, match="Clinical text is required"):
            connector.process_healthcare_request(request_data)

    def test_invalid_analysis_type(self):
        """Test handling of invalid analysis type."""
        connector = ClinicalNLPConnector()
        request_data = {
            "clinical_text": "Patient has diabetes",
            "analysis_type": "invalid_type"
        }

        with pytest.raises(ValueError, match="Invalid analysis type"):
            connector.process_healthcare_request(request_data)

    def test_run_method_execution(self):
        """Test the run method executes without errors."""
        connector = ClinicalNLPConnector()

        result = connector.run(
            clinical_text="Patient has type 2 diabetes and hypertension.",
            analysis_type="entity_extraction",
            medical_specialty="general_medicine"
        )

        assert isinstance(result, Data)
        assert result.data is not None
        assert result.data.get("status") == "success"

    def test_confidence_scoring(self):
        """Test that confidence scores are included when requested."""
        connector = ClinicalNLPConnector()
        request_data = {
            "clinical_text": "Patient has diabetes",
            "analysis_type": "entity_extraction",
            "include_confidence_scores": True
        }

        response = connector.get_mock_response(request_data)
        entities = response.get("entities", {})
        if entities.get("conditions"):
            condition = entities["conditions"][0]
            assert "confidence" in condition
            assert isinstance(condition["confidence"], float)