"""Clinical NLP Analyzer Connector for advanced clinical text analysis including negation detection and temporal extraction."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.io import (
    BoolInput,
    DropdownInput,
    MessageTextInput,
    MultilineInput,
    Output,
    StrInput,
)
from langflow.schema.data import Data


class ClinicalNLPAnalyzerConnector(HealthcareConnectorBase):
    """
    HIPAA-compliant Clinical NLP Analyzer Connector for advanced medical text analysis
    including negation detection, temporal extraction, and contextual analysis.

    Supports specialized clinical NLP tasks like negation identification,
    temporal context extraction, and clinical reasoning analysis.
    """

    display_name: str = "Clinical NLP Analyzer Connector"
    description: str = "Advanced clinical NLP analysis for negation detection, temporal extraction, and contextual analysis"
    icon: str = "Brain"
    name: str = "ClinicalNLPAnalyzerConnector"

    inputs = HealthcareConnectorBase.inputs + [
        MultilineInput(
            name="clinical_text",
            display_name="Clinical Text",
            info="Medical text for advanced NLP analysis",
            tool_mode=True,
        ),
        StrInput(
            name="clinical_entities",
            display_name="Clinical Entities",
            placeholder="JSON string of entities to analyze",
            info="Previously extracted entities for context analysis",
            tool_mode=True,
        ),
        DropdownInput(
            name="analysis_mode",
            display_name="Analysis Mode",
            options=[
                "negation_detection",
                "temporal_extraction",
                "context_analysis",
                "sentiment_analysis",
                "uncertainty_detection",
                "comprehensive_analysis"
            ],
            value="comprehensive_analysis",
            info="Type of specialized NLP analysis to perform",
            tool_mode=True,
        ),
        BoolInput(
            name="detect_negations",
            display_name="Detect Negations",
            value=True,
            info="Identify negated clinical findings (e.g., 'no fever', 'denies pain')",
            tool_mode=True,
        ),
        BoolInput(
            name="extract_temporal",
            display_name="Extract Temporal Information",
            value=True,
            info="Extract temporal context (onset, duration, frequency)",
            tool_mode=True,
        ),
        BoolInput(
            name="analyze_uncertainty",
            display_name="Analyze Uncertainty",
            value=True,
            info="Detect uncertainty markers (possible, likely, uncertain)",
            tool_mode=True,
        ),
        BoolInput(
            name="analyze_severity",
            display_name="Analyze Severity",
            value=True,
            info="Extract severity indicators (mild, moderate, severe)",
            tool_mode=True,
        ),
        DropdownInput(
            name="temporal_resolution",
            display_name="Temporal Resolution",
            options=["hours", "days", "weeks", "months", "years", "auto"],
            value="auto",
            info="Resolution for temporal analysis",
            tool_mode=True,
        ),
        BoolInput(
            name="include_confidence_scores",
            display_name="Include Confidence Scores",
            value=True,
            info="Include confidence scores for all analyses",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="NLP Analysis", name="nlp_analysis", method="analyze_clinical_text"),
        Output(display_name="Negation Results", name="negation_results", method="get_negation_results"),
        Output(display_name="Temporal Analysis", name="temporal_analysis", method="get_temporal_analysis"),
        Output(display_name="Context Analysis", name="context_analysis", method="get_context_analysis"),
    ]

    def analyze_clinical_text(self) -> Data:
        """Perform comprehensive clinical NLP analysis."""
        try:
            # Prepare request data
            request_data = {
                "operation": "analyze_clinical_text",
                "clinical_text": getattr(self, 'clinical_text', ''),
                "clinical_entities": getattr(self, 'clinical_entities', ''),
                "analysis_mode": getattr(self, 'analysis_mode', 'comprehensive_analysis'),
                "detect_negations": getattr(self, 'detect_negations', True),
                "extract_temporal": getattr(self, 'extract_temporal', True),
                "analyze_uncertainty": getattr(self, 'analyze_uncertainty', True),
                "analyze_severity": getattr(self, 'analyze_severity', True),
                "temporal_resolution": getattr(self, 'temporal_resolution', 'auto'),
                "include_confidence_scores": getattr(self, 'include_confidence_scores', True),
            }

            return self.execute_healthcare_workflow(request_data)

        except Exception as e:
            return self._handle_healthcare_error(e, "analyze_clinical_text")

    def get_negation_results(self) -> Data:
        """Get negation detection results."""
        try:
            request_data = {
                "operation": "negation_detection",
                "clinical_text": getattr(self, 'clinical_text', ''),
            }
            result = self.execute_healthcare_workflow(request_data)

            # Extract negation results from full response
            if hasattr(result, 'data') and isinstance(result.data, dict):
                negation_data = result.data.get('negation_results', {})
                return Data(data=negation_data)

            return result

        except Exception as e:
            return self._handle_healthcare_error(e, "get_negation_results")

    def get_temporal_analysis(self) -> Data:
        """Get temporal extraction results."""
        try:
            request_data = {
                "operation": "temporal_extraction",
                "clinical_text": getattr(self, 'clinical_text', ''),
                "temporal_resolution": getattr(self, 'temporal_resolution', 'auto'),
            }
            result = self.execute_healthcare_workflow(request_data)

            # Extract temporal results from full response
            if hasattr(result, 'data') and isinstance(result.data, dict):
                temporal_data = result.data.get('temporal_analysis', {})
                return Data(data=temporal_data)

            return result

        except Exception as e:
            return self._handle_healthcare_error(e, "get_temporal_analysis")

    def get_context_analysis(self) -> Data:
        """Get contextual analysis results."""
        try:
            request_data = {
                "operation": "context_analysis",
                "clinical_text": getattr(self, 'clinical_text', ''),
                "clinical_entities": getattr(self, 'clinical_entities', ''),
            }
            result = self.execute_healthcare_workflow(request_data)

            # Extract context results from full response
            if hasattr(result, 'data') and isinstance(result.data, dict):
                context_data = result.data.get('context_analysis', {})
                return Data(data=context_data)

            return result

        except Exception as e:
            return self._handle_healthcare_error(e, "get_context_analysis")

    def get_required_fields(self) -> List[str]:
        """Required fields for clinical NLP analyzer requests."""
        return ["clinical_text", "analysis_mode"]

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive mock clinical NLP analyzer data."""
        operation = request_data.get("operation", "analyze_clinical_text")
        clinical_text = request_data.get("clinical_text", "")
        analysis_mode = request_data.get("analysis_mode", "comprehensive_analysis")

        # Mock negation detection results
        negation_results = {
            "negated_entities": [
                {
                    "text": "chest pain",
                    "start_pos": 45,
                    "end_pos": 55,
                    "negation_type": "explicit_denial",
                    "negation_trigger": "denies",
                    "scope": "sentence",
                    "confidence": 0.95,
                    "context": "Patient denies chest pain at this time"
                },
                {
                    "text": "shortness of breath",
                    "start_pos": 78,
                    "end_pos": 97,
                    "negation_type": "absence",
                    "negation_trigger": "no",
                    "scope": "phrase",
                    "confidence": 0.92,
                    "context": "no shortness of breath reported"
                }
            ],
            "negation_patterns": [
                {
                    "pattern": "denies",
                    "type": "explicit_denial",
                    "frequency": 3,
                    "scope": "sentence"
                },
                {
                    "pattern": "no",
                    "type": "absence",
                    "frequency": 2,
                    "scope": "phrase"
                },
                {
                    "pattern": "without",
                    "type": "absence",
                    "frequency": 1,
                    "scope": "phrase"
                }
            ],
            "negation_statistics": {
                "total_negations": 6,
                "explicit_denials": 3,
                "absence_statements": 2,
                "implicit_negations": 1,
                "negation_density": 0.12
            }
        }

        # Mock temporal extraction results
        temporal_results = {
            "temporal_entities": [
                {
                    "text": "3 months ago",
                    "start_pos": 120,
                    "end_pos": 132,
                    "temporal_type": "relative_past",
                    "value": "3 months",
                    "reference_date": datetime.now().isoformat(),
                    "absolute_date": "2024-07-22",
                    "confidence": 0.94,
                    "associated_entity": "diagnosis of diabetes"
                },
                {
                    "text": "twice daily",
                    "start_pos": 156,
                    "end_pos": 167,
                    "temporal_type": "frequency",
                    "value": "2/day",
                    "frequency_per_day": 2,
                    "confidence": 0.98,
                    "associated_entity": "metformin administration"
                },
                {
                    "text": "ongoing",
                    "start_pos": 200,
                    "end_pos": 207,
                    "temporal_type": "duration",
                    "value": "continuous",
                    "duration_type": "ongoing",
                    "confidence": 0.89,
                    "associated_entity": "hypertension management"
                }
            ],
            "temporal_patterns": {
                "onset_indicators": [
                    {"pattern": "started", "count": 2, "type": "initiation"},
                    {"pattern": "began", "count": 1, "type": "initiation"},
                    {"pattern": "developed", "count": 1, "type": "onset"}
                ],
                "duration_indicators": [
                    {"pattern": "for", "count": 3, "type": "duration"},
                    {"pattern": "since", "count": 2, "type": "duration"},
                    {"pattern": "ongoing", "count": 1, "type": "continuous"}
                ],
                "frequency_indicators": [
                    {"pattern": "daily", "count": 4, "type": "frequency"},
                    {"pattern": "twice", "count": 2, "type": "frequency"},
                    {"pattern": "as needed", "count": 1, "type": "conditional"}
                ]
            },
            "temporal_timeline": [
                {
                    "date": "2024-07-22",
                    "event": "diabetes diagnosis",
                    "type": "diagnosis",
                    "confidence": 0.94
                },
                {
                    "date": "2024-08-01",
                    "event": "metformin initiation",
                    "type": "medication_start",
                    "confidence": 0.92
                }
            ]
        }

        # Mock uncertainty analysis results
        uncertainty_results = {
            "uncertain_entities": [
                {
                    "text": "possible pneumonia",
                    "start_pos": 89,
                    "end_pos": 107,
                    "uncertainty_type": "possibility",
                    "uncertainty_trigger": "possible",
                    "confidence_level": "low",
                    "confidence": 0.87,
                    "alternative_interpretations": ["bronchitis", "viral infection"]
                },
                {
                    "text": "likely medication side effect",
                    "start_pos": 145,
                    "end_pos": 174,
                    "uncertainty_type": "probability",
                    "uncertainty_trigger": "likely",
                    "confidence_level": "high",
                    "confidence": 0.91,
                    "probability_estimate": 0.75
                }
            ],
            "uncertainty_markers": [
                {"marker": "possible", "count": 2, "type": "possibility"},
                {"marker": "likely", "count": 1, "type": "probability"},
                {"marker": "uncertain", "count": 1, "type": "uncertainty"},
                {"marker": "may be", "count": 1, "type": "possibility"}
            ]
        }

        # Mock severity analysis results
        severity_results = {
            "severity_entities": [
                {
                    "text": "severe chest pain",
                    "start_pos": 67,
                    "end_pos": 84,
                    "severity_level": "severe",
                    "severity_score": 8.5,
                    "confidence": 0.93,
                    "severity_indicators": ["severe", "intense", "excruciating"]
                },
                {
                    "text": "mild fatigue",
                    "start_pos": 123,
                    "end_pos": 135,
                    "severity_level": "mild",
                    "severity_score": 3.2,
                    "confidence": 0.88,
                    "severity_indicators": ["mild", "slight"]
                }
            ],
            "severity_distribution": {
                "mild": 3,
                "moderate": 2,
                "severe": 1,
                "critical": 0
            },
            "severity_patterns": [
                {"pattern": "severe", "count": 1, "score_range": "8-10"},
                {"pattern": "moderate", "count": 2, "score_range": "5-7"},
                {"pattern": "mild", "count": 3, "score_range": "1-4"}
            ]
        }

        # Mock context analysis results
        context_results = {
            "clinical_context": {
                "document_type": "progress_note",
                "visit_type": "follow_up",
                "medical_specialty": "internal_medicine",
                "note_sections": [
                    {"section": "chief_complaint", "confidence": 0.95},
                    {"section": "history_present_illness", "confidence": 0.92},
                    {"section": "assessment_plan", "confidence": 0.89}
                ]
            },
            "entity_relationships": [
                {
                    "entity1": "diabetes",
                    "entity2": "metformin",
                    "relationship": "treats",
                    "confidence": 0.94,
                    "evidence": "metformin prescribed for diabetes management"
                },
                {
                    "entity1": "hypertension",
                    "entity2": "lisinopril",
                    "relationship": "treats",
                    "confidence": 0.91,
                    "evidence": "lisinopril for blood pressure control"
                }
            ],
            "clinical_reasoning": {
                "diagnostic_confidence": 0.87,
                "treatment_consistency": 0.92,
                "documentation_quality": 0.89,
                "clinical_coherence": 0.91
            }
        }

        # Build response based on analysis mode
        mock_data = {
            "status": "success",
            "analysis_mode": analysis_mode,
            "text_length": len(clinical_text),
            "processing_time_ms": 156,
            "language_detected": "en-US",
            "clinical_complexity_score": 0.73
        }

        if analysis_mode in ["negation_detection", "comprehensive_analysis"]:
            mock_data["negation_analysis"] = negation_results

        if analysis_mode in ["temporal_extraction", "comprehensive_analysis"]:
            mock_data["temporal_analysis"] = temporal_results

        if analysis_mode in ["uncertainty_detection", "comprehensive_analysis"]:
            mock_data["uncertainty_analysis"] = uncertainty_results

        if analysis_mode in ["context_analysis", "comprehensive_analysis"]:
            mock_data["context_analysis"] = context_results

        if request_data.get("analyze_severity", True):
            mock_data["severity_analysis"] = severity_results

        if analysis_mode == "sentiment_analysis":
            mock_data["sentiment_analysis"] = {
                "overall_sentiment": "neutral",
                "sentiment_score": 0.12,
                "emotional_indicators": [
                    {"emotion": "concern", "score": 0.65, "evidence": "worried about symptoms"},
                    {"emotion": "relief", "score": 0.45, "evidence": "feeling better today"}
                ],
                "patient_attitude": "cooperative",
                "communication_style": "clear_and_detailed"
            }

        # Add comprehensive summary for full analysis
        if analysis_mode == "comprehensive_analysis":
            mock_data["analysis_summary"] = {
                "total_entities_analyzed": 15,
                "negated_entities_count": len(negation_results["negated_entities"]),
                "temporal_entities_count": len(temporal_results["temporal_entities"]),
                "uncertain_entities_count": len(uncertainty_results["uncertain_entities"]),
                "severity_entities_count": len(severity_results["severity_entities"]),
                "overall_confidence": 0.91,
                "clinical_significance": "moderate",
                "documentation_completeness": 0.87
            }

        # Return operation-specific results
        if operation == "negation_detection":
            return negation_results
        elif operation == "temporal_extraction":
            return temporal_results
        elif operation == "context_analysis":
            return context_results
        else:
            # Return comprehensive analysis for analyze_clinical_text and other operations
            return mock_data

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process real clinical NLP requests (production implementation).

        In production, this would:
        1. Connect to clinical NLP services (spaCy, scispaCy, etc.)
        2. Perform real negation detection using NegEx or similar
        3. Extract temporal information using clinical temporal parsers
        4. Apply context analysis with clinical reasoning
        5. Generate confidence scores and validate results
        """
        # For now, return mock data with production note
        mock_response = self.get_mock_response(request_data)
        mock_response["production_note"] = "Configure clinical NLP services for live analysis"
        return mock_response

