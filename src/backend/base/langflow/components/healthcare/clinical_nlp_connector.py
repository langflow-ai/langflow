"""Clinical NLP Connector for medical text analysis and entity extraction."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.io import (
    BoolInput,
    DropdownInput,
    MessageTextInput,
    MultilineInput,
    StrInput,
)
from langflow.schema.data import Data


class ClinicalNLPConnector(HealthcareConnectorBase):
    """
    HIPAA-compliant Clinical NLP Connector for medical text analysis,
    entity extraction, and clinical language processing.

    Supports medical entity recognition, clinical reasoning extraction,
    and healthcare-specific natural language understanding.
    """

    display_name: str = "Clinical NLP Connector"
    description: str = "Process medical text with clinical NLP for entity extraction and medical language understanding"
    icon: str = "FileText"
    name: str = "ClinicalNLPConnector"

    inputs = HealthcareConnectorBase.inputs + [
        MultilineInput(
            name="clinical_text",
            display_name="Clinical Text",
            info="Medical text for NLP processing (clinical notes, reports, etc.)",
            tool_mode=True,
        ),
        DropdownInput(
            name="analysis_type",
            display_name="Analysis Type",
            options=[
                "entity_extraction",
                "clinical_reasoning",
                "diagnosis_extraction",
                "medication_analysis",
                "symptom_identification",
                "full_analysis"
            ],
            value="entity_extraction",
            info="Type of clinical NLP analysis to perform",
            tool_mode=True,
        ),
        DropdownInput(
            name="medical_specialty",
            display_name="Medical Specialty",
            options=[
                "general_medicine",
                "cardiology",
                "pulmonology",
                "endocrinology",
                "neurology",
                "oncology",
                "psychiatry",
                "emergency_medicine"
            ],
            value="general_medicine",
            info="Medical specialty context for enhanced NLP accuracy",
            tool_mode=True,
        ),
        BoolInput(
            name="extract_medications",
            display_name="Extract Medications",
            value=True,
            info="Extract medication names, dosages, and administration details",
            tool_mode=True,
        ),
        BoolInput(
            name="extract_conditions",
            display_name="Extract Conditions",
            value=True,
            info="Extract medical conditions, diagnoses, and symptoms",
            tool_mode=True,
        ),
        BoolInput(
            name="extract_procedures",
            display_name="Extract Procedures",
            value=True,
            info="Extract medical procedures and interventions",
            tool_mode=True,
        ),
        BoolInput(
            name="include_confidence_scores",
            display_name="Include Confidence Scores",
            value=True,
            info="Include confidence scores for extracted entities",
            tool_mode=True,
        ),
        DropdownInput(
            name="output_format",
            display_name="Output Format",
            options=["structured", "annotated_text", "both"],
            value="structured",
            info="Format for NLP analysis output",
            tool_mode=True,
        ),
    ]

    def get_required_fields(self) -> List[str]:
        """Required fields for clinical NLP requests."""
        return ["clinical_text", "analysis_type"]

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive mock clinical NLP analysis data."""
        clinical_text = request_data.get("clinical_text", "")
        analysis_type = request_data.get("analysis_type", "entity_extraction")
        medical_specialty = request_data.get("medical_specialty", "general_medicine")

        # Mock medical entities for demonstration
        mock_entities = {
            "medications": [
                {
                    "text": "metformin",
                    "start_pos": 45,
                    "end_pos": 53,
                    "entity_type": "medication",
                    "confidence": 0.98,
                    "attributes": {
                        "dosage": "500mg",
                        "frequency": "twice daily",
                        "route": "oral",
                        "generic_name": "metformin",
                        "drug_class": "biguanide"
                    }
                },
                {
                    "text": "lisinopril",
                    "start_pos": 78,
                    "end_pos": 88,
                    "entity_type": "medication",
                    "confidence": 0.95,
                    "attributes": {
                        "dosage": "10mg",
                        "frequency": "daily",
                        "route": "oral",
                        "generic_name": "lisinopril",
                        "drug_class": "ACE inhibitor"
                    }
                }
            ],
            "conditions": [
                {
                    "text": "type 2 diabetes mellitus",
                    "start_pos": 120,
                    "end_pos": 144,
                    "entity_type": "condition",
                    "confidence": 0.97,
                    "attributes": {
                        "icd10_code": "E11",
                        "category": "endocrine_disorder",
                        "severity": "moderate",
                        "status": "active"
                    }
                },
                {
                    "text": "hypertension",
                    "start_pos": 156,
                    "end_pos": 168,
                    "entity_type": "condition",
                    "confidence": 0.94,
                    "attributes": {
                        "icd10_code": "I10",
                        "category": "cardiovascular_disorder",
                        "severity": "mild",
                        "status": "controlled"
                    }
                }
            ],
            "procedures": [
                {
                    "text": "HbA1c test",
                    "start_pos": 200,
                    "end_pos": 210,
                    "entity_type": "procedure",
                    "confidence": 0.92,
                    "attributes": {
                        "cpt_code": "83036",
                        "category": "laboratory",
                        "frequency": "quarterly"
                    }
                }
            ],
            "vitals": [
                {
                    "text": "blood pressure 130/80",
                    "start_pos": 85,
                    "end_pos": 107,
                    "entity_type": "vital_sign",
                    "confidence": 0.96,
                    "attributes": {
                        "measurement_type": "blood_pressure",
                        "systolic": "130",
                        "diastolic": "80",
                        "unit": "mmHg"
                    }
                }
            ]
        }

        # Mock clinical reasoning extraction
        clinical_reasoning = {
            "chief_complaint": "Follow-up for diabetes and hypertension management",
            "assessment": "Type 2 diabetes mellitus well-controlled on metformin, hypertension stable on lisinopril",
            "plan": "Continue current medications, monitor HbA1c quarterly, lifestyle counseling",
            "differential_diagnosis": [
                "Type 2 diabetes mellitus - confirmed",
                "Essential hypertension - confirmed"
            ],
            "clinical_decision_points": [
                "HbA1c target <7% appropriate for this patient",
                "Blood pressure goal <130/80 achieved",
                "Consider adding lifestyle modifications"
            ]
        }

        # Mock symptom identification
        symptoms = [
            {
                "text": "increased thirst",
                "confidence": 0.89,
                "severity": "mild",
                "duration": "2 weeks",
                "associated_condition": "diabetes mellitus"
            },
            {
                "text": "fatigue",
                "confidence": 0.85,
                "severity": "moderate",
                "duration": "1 month",
                "associated_condition": "diabetes mellitus"
            }
        ]

        # Build response based on analysis type
        mock_data = {
            "status": "success",
            "analysis_type": analysis_type,
            "medical_specialty": medical_specialty,
            "text_length": len(clinical_text),
            "processing_time_ms": 245,
            "language_detected": "en-US",
            "medical_terminology_density": 0.23
        }

        if analysis_type in ["entity_extraction", "full_analysis"]:
            mock_data["entities"] = mock_entities
            mock_data["entity_summary"] = {
                "total_entities": sum(len(entities) for entities in mock_entities.values()),
                "medications_count": len(mock_entities["medications"]),
                "conditions_count": len(mock_entities["conditions"]),
                "procedures_count": len(mock_entities["procedures"]),
                "avg_confidence": 0.94
            }

        if analysis_type in ["clinical_reasoning", "full_analysis"]:
            mock_data["clinical_reasoning"] = clinical_reasoning

        if analysis_type in ["symptom_identification", "full_analysis"]:
            mock_data["symptoms"] = symptoms

        if analysis_type == "medication_analysis":
            mock_data["medication_analysis"] = {
                "identified_medications": mock_entities["medications"],
                "drug_interactions": [
                    {
                        "drug1": "metformin",
                        "drug2": "lisinopril",
                        "interaction_level": "none",
                        "clinical_significance": "No significant interaction"
                    }
                ],
                "adherence_indicators": ["appropriate_dosing", "standard_frequency"],
                "therapeutic_duplications": []
            }

        if analysis_type == "diagnosis_extraction":
            mock_data["diagnoses"] = {
                "primary_diagnoses": mock_entities["conditions"],
                "secondary_diagnoses": [],
                "diagnostic_confidence": 0.95,
                "coding_suggestions": [
                    {
                        "condition": "type 2 diabetes mellitus",
                        "suggested_codes": ["E11.9", "E11.65"],
                        "documentation_gaps": []
                    }
                ]
            }

        # Add annotated text if requested
        if request_data.get("output_format") in ["annotated_text", "both"]:
            annotated_text = clinical_text
            # Simulate entity annotation (in real implementation, would mark entities)
            mock_data["annotated_text"] = {
                "original_text": clinical_text,
                "html_annotated": f"<span class='medication'>metformin</span> and <span class='medication'>lisinopril</span> for <span class='condition'>diabetes</span>",
                "annotations": [
                    {"start": 0, "end": 9, "label": "medication", "confidence": 0.98},
                    {"start": 14, "end": 24, "label": "medication", "confidence": 0.95}
                ]
            }

        return mock_data

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process clinical NLP request with healthcare-specific logic."""
        # Log PHI access for audit trail
        self._log_phi_access("clinical_nlp_processing", ["clinical_text", "medical_entities"])

        clinical_text = request_data.get("clinical_text", "")
        if not clinical_text.strip():
            raise ValueError("Clinical text is required for NLP analysis")

        # Validate analysis type
        valid_types = [
            "entity_extraction", "clinical_reasoning", "diagnosis_extraction",
            "medication_analysis", "symptom_identification", "full_analysis"
        ]

        analysis_type = request_data.get("analysis_type")
        if analysis_type not in valid_types:
            raise ValueError(f"Invalid analysis type. Must be one of: {valid_types}")

        # Check for PHI in text (basic validation)
        if self._contains_obvious_phi(clinical_text):
            self._log_phi_access("phi_detected_in_text", ["patient_identifiers"])

        # In production, this would connect to actual clinical NLP services
        # For now, return comprehensive mock data
        return self.get_mock_response(request_data)

    def _contains_obvious_phi(self, text: str) -> bool:
        """Basic check for obvious PHI patterns in clinical text."""
        # Check for common PHI patterns (this is a simplified example)
        phi_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN pattern
            r'\b\d{10,}\b',  # Long number sequences
            r'[A-Za-z]+\s+[A-Za-z]+\s+DOB',  # Name + DOB pattern
            r'Patient\s+[A-Z][a-z]+\s+[A-Z][a-z]+',  # Patient Name pattern
        ]

        for pattern in phi_patterns:
            if re.search(pattern, text):
                return True
        return False

    def run(
        self,
        clinical_text: str = "",
        analysis_type: str = "entity_extraction",
        medical_specialty: str = "general_medicine",
        extract_medications: bool = True,
        extract_conditions: bool = True,
        extract_procedures: bool = True,
        include_confidence_scores: bool = True,
        output_format: str = "structured",
        **kwargs
    ) -> Data:
        """
        Execute clinical NLP analysis workflow.

        Args:
            clinical_text: Medical text for NLP processing
            analysis_type: Type of clinical NLP analysis to perform
            medical_specialty: Medical specialty context for enhanced accuracy
            extract_medications: Extract medication entities
            extract_conditions: Extract condition entities
            extract_procedures: Extract procedure entities
            include_confidence_scores: Include confidence scores
            output_format: Format for analysis output

        Returns:
            Data: Clinical NLP analysis response with healthcare metadata
        """
        request_data = {
            "clinical_text": clinical_text,
            "analysis_type": analysis_type,
            "medical_specialty": medical_specialty,
            "extract_medications": extract_medications,
            "extract_conditions": extract_conditions,
            "extract_procedures": extract_procedures,
            "include_confidence_scores": include_confidence_scores,
            "output_format": output_format,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self.execute_healthcare_workflow(request_data)