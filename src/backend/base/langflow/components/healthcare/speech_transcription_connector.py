"""Speech Transcription Connector for clinical speech-to-text services."""

import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.io import (
    BoolInput,
    DropdownInput,
    FileInput,
    MessageTextInput,
    StrInput,
)
from langflow.schema.data import Data


class SpeechTranscriptionConnector(HealthcareConnectorBase):
    """
    HIPAA-compliant Speech Transcription Connector for clinical speech-to-text
    services optimized for medical terminology and healthcare environments.

    Supports real-time transcription, batch processing, speaker identification,
    and medical vocabulary enhancement for clinical documentation.
    """

    display_name: str = "Speech Transcription Connector"
    description: str = "Convert clinical speech to text with medical terminology optimization and HIPAA compliance"
    icon: str = "Mic"
    name: str = "SpeechTranscriptionConnector"

    inputs = HealthcareConnectorBase.inputs + [
        FileInput(
            name="audio_file",
            display_name="Audio File",
            file_types=["wav", "mp3", "m4a", "flac", "ogg"],
            info="Audio file for transcription (WAV, MP3, M4A, FLAC, OGG)",
        ),
        StrInput(
            name="audio_url",
            display_name="Audio URL",
            placeholder="https://example.com/audio.wav",
            info="URL to audio file for transcription",
            tool_mode=True,
        ),
        DropdownInput(
            name="transcription_mode",
            display_name="Transcription Mode",
            options=[
                "real_time",
                "batch_processing",
                "conversation",
                "dictation",
                "phone_call"
            ],
            value="batch_processing",
            info="Mode of speech transcription processing",
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
                "emergency_medicine",
                "surgery",
                "radiology"
            ],
            value="general_medicine",
            info="Medical specialty for enhanced vocabulary recognition",
            tool_mode=True,
        ),
        DropdownInput(
            name="language_model",
            display_name="Language Model",
            options=[
                "medical_enhanced",
                "clinical_notes",
                "provider_dictation",
                "patient_interview",
                "general_healthcare"
            ],
            value="medical_enhanced",
            info="Language model optimized for healthcare terminology",
            tool_mode=True,
        ),
        BoolInput(
            name="enable_speaker_identification",
            display_name="Enable Speaker ID",
            value=True,
            info="Identify and label different speakers in audio",
            tool_mode=True,
        ),
        BoolInput(
            name="enable_punctuation",
            display_name="Enable Punctuation",
            value=True,
            info="Automatically add punctuation and formatting",
            tool_mode=True,
        ),
        BoolInput(
            name="filter_profanity",
            display_name="Filter Profanity",
            value=False,
            info="Filter inappropriate language in transcription",
            tool_mode=True,
        ),
        DropdownInput(
            name="confidence_threshold",
            display_name="Confidence Threshold",
            options=["0.7", "0.8", "0.85", "0.9", "0.95"],
            value="0.85",
            info="Minimum confidence score for transcription acceptance",
            tool_mode=True,
        ),
        BoolInput(
            name="include_timestamps",
            display_name="Include Timestamps",
            value=True,
            info="Include word-level timestamps in transcription",
            tool_mode=True,
        ),
        BoolInput(
            name="medical_entity_recognition",
            display_name="Medical Entity Recognition",
            value=True,
            info="Identify and highlight medical entities in transcription",
            tool_mode=True,
        ),
    ]

    def get_required_fields(self) -> List[str]:
        """Required fields for speech transcription requests."""
        return ["transcription_mode"]

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive mock speech transcription data."""
        transcription_mode = request_data.get("transcription_mode", "batch_processing")
        medical_specialty = request_data.get("medical_specialty", "general_medicine")
        language_model = request_data.get("language_model", "medical_enhanced")

        # Mock transcription based on medical specialty
        if medical_specialty == "cardiology":
            mock_transcript = "The patient presents with chest pain that began approximately two hours ago. The pain is described as substernal, crushing in nature, radiating to the left arm. Vital signs show blood pressure 160 over 95, heart rate 98 beats per minute. EKG demonstrates ST elevation in leads V2 through V4 consistent with anterior STEMI. Troponin levels are elevated at 2.5. I recommend immediate cardiac catheterization and PCI."
            medical_entities = [
                {"text": "chest pain", "entity_type": "symptom", "confidence": 0.95},
                {"text": "substernal", "entity_type": "anatomical_location", "confidence": 0.92},
                {"text": "ST elevation", "entity_type": "diagnostic_finding", "confidence": 0.98},
                {"text": "anterior STEMI", "entity_type": "diagnosis", "confidence": 0.97},
                {"text": "cardiac catheterization", "entity_type": "procedure", "confidence": 0.94},
                {"text": "PCI", "entity_type": "procedure", "confidence": 0.96}
            ]
        elif medical_specialty == "endocrinology":
            mock_transcript = "The patient is a 45-year-old female with type 2 diabetes mellitus presenting for routine follow-up. Her hemoglobin A1C is 7.2 percent, which shows improvement from the previous value of 8.1 percent. She reports good adherence to metformin 500 milligrams twice daily. Blood glucose logs show fasting values ranging from 120 to 140 milligrams per deciliter. I will continue current therapy and recheck A1C in three months."
            medical_entities = [
                {"text": "type 2 diabetes mellitus", "entity_type": "diagnosis", "confidence": 0.98},
                {"text": "hemoglobin A1C", "entity_type": "lab_test", "confidence": 0.96},
                {"text": "metformin", "entity_type": "medication", "confidence": 0.97},
                {"text": "500 milligrams", "entity_type": "dosage", "confidence": 0.94},
                {"text": "blood glucose", "entity_type": "lab_test", "confidence": 0.95}
            ]
        else:
            mock_transcript = "Patient presents with a three-day history of fever, cough, and shortness of breath. Temperature is 101.5 degrees Fahrenheit, oxygen saturation 94 percent on room air. Chest X-ray reveals bilateral infiltrates. Given the clinical presentation, I suspect community-acquired pneumonia. I will start empiric antibiotic therapy with azithromycin and monitor closely."
            medical_entities = [
                {"text": "fever", "entity_type": "symptom", "confidence": 0.96},
                {"text": "cough", "entity_type": "symptom", "confidence": 0.95},
                {"text": "shortness of breath", "entity_type": "symptom", "confidence": 0.94},
                {"text": "bilateral infiltrates", "entity_type": "diagnostic_finding", "confidence": 0.93},
                {"text": "community-acquired pneumonia", "entity_type": "diagnosis", "confidence": 0.97},
                {"text": "azithromycin", "entity_type": "medication", "confidence": 0.98}
            ]

        # Mock speaker identification data
        speakers = [
            {
                "speaker_id": "Speaker_1",
                "speaker_role": "provider",
                "confidence": 0.89,
                "segments": [
                    {"start_time": 0.0, "end_time": 45.2, "text": mock_transcript}
                ]
            }
        ]

        if transcription_mode == "conversation":
            speakers.append({
                "speaker_id": "Speaker_2",
                "speaker_role": "patient",
                "confidence": 0.85,
                "segments": [
                    {"start_time": 45.3, "end_time": 52.1, "text": "Yes, the pain started suddenly while I was at work."}
                ]
            })

        # Mock word-level timestamps
        words_with_timestamps = [
            {"word": "The", "start_time": 0.1, "end_time": 0.3, "confidence": 0.98},
            {"word": "patient", "start_time": 0.4, "end_time": 0.8, "confidence": 0.97},
            {"word": "presents", "start_time": 0.9, "end_time": 1.3, "confidence": 0.96},
            {"word": "with", "start_time": 1.4, "end_time": 1.6, "confidence": 0.98}
            # ... more words would be included in real implementation
        ]

        mock_data = {
            "status": "success",
            "transcription_mode": transcription_mode,
            "medical_specialty": medical_specialty,
            "language_model": language_model,
            "processing_time_seconds": 12.5,
            "audio_duration_seconds": 45.2,
            "transcription": {
                "full_text": mock_transcript,
                "confidence_score": 0.91,
                "language_detected": "en-US",
                "medical_terminology_count": len(medical_entities)
            },
            "quality_metrics": {
                "overall_confidence": 0.91,
                "word_accuracy_estimate": 0.94,
                "medical_term_accuracy": 0.96,
                "audio_quality_score": 0.88,
                "background_noise_level": "low"
            }
        }

        # Add speaker identification if enabled
        if request_data.get("enable_speaker_identification", True):
            mock_data["speaker_identification"] = {
                "speakers_detected": len(speakers),
                "speakers": speakers,
                "speaker_change_detection": True
            }

        # Add timestamps if enabled
        if request_data.get("include_timestamps", True):
            mock_data["word_timestamps"] = words_with_timestamps[:10]  # Sample subset
            mock_data["segment_timestamps"] = [
                {"start_time": 0.0, "end_time": 45.2, "text": mock_transcript}
            ]

        # Add medical entity recognition if enabled
        if request_data.get("medical_entity_recognition", True):
            mock_data["medical_entities"] = {
                "entities": medical_entities,
                "entity_categories": {
                    "symptoms": len([e for e in medical_entities if e["entity_type"] == "symptom"]),
                    "diagnoses": len([e for e in medical_entities if e["entity_type"] == "diagnosis"]),
                    "medications": len([e for e in medical_entities if e["entity_type"] == "medication"]),
                    "procedures": len([e for e in medical_entities if e["entity_type"] == "procedure"])
                }
            }

        # Add real-time specific data
        if transcription_mode == "real_time":
            mock_data["real_time_metrics"] = {
                "latency_ms": 150,
                "streaming_confidence": 0.89,
                "interim_results": True,
                "final_result": True
            }

        # Add batch processing specific data
        elif transcription_mode == "batch_processing":
            mock_data["batch_processing"] = {
                "queue_position": 1,
                "estimated_completion": "2 minutes",
                "processing_status": "completed",
                "file_format": "wav",
                "file_size_mb": 2.5
            }

        return mock_data

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process speech transcription request with healthcare-specific logic."""
        # Log PHI access for audit trail
        self._log_phi_access("speech_transcription", ["audio_content", "clinical_conversation"])

        # Validate transcription mode
        valid_modes = ["real_time", "batch_processing", "conversation", "dictation", "phone_call"]
        transcription_mode = request_data.get("transcription_mode")
        if transcription_mode not in valid_modes:
            raise ValueError(f"Invalid transcription mode. Must be one of: {valid_modes}")

        # Validate audio input
        audio_file = request_data.get("audio_file")
        audio_url = request_data.get("audio_url")

        if not audio_file and not audio_url:
            # For demo purposes, allow mock transcription without actual audio
            pass

        # Validate confidence threshold
        try:
            confidence_threshold = float(request_data.get("confidence_threshold", "0.85"))
            if not 0.0 <= confidence_threshold <= 1.0:
                raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        except ValueError:
            raise ValueError("Invalid confidence threshold format")

        # In production, this would connect to actual speech transcription services
        # For now, return comprehensive mock data
        return self.get_mock_response(request_data)

    def run(
        self,
        audio_file: Optional[str] = None,
        audio_url: str = "",
        transcription_mode: str = "batch_processing",
        medical_specialty: str = "general_medicine",
        language_model: str = "medical_enhanced",
        enable_speaker_identification: bool = True,
        enable_punctuation: bool = True,
        filter_profanity: bool = False,
        confidence_threshold: str = "0.85",
        include_timestamps: bool = True,
        medical_entity_recognition: bool = True,
        **kwargs
    ) -> Data:
        """
        Execute clinical speech transcription workflow.

        Args:
            audio_file: Audio file for transcription
            audio_url: URL to audio file
            transcription_mode: Mode of transcription processing
            medical_specialty: Medical specialty for vocabulary enhancement
            language_model: Language model for healthcare terminology
            enable_speaker_identification: Enable speaker identification
            enable_punctuation: Enable automatic punctuation
            filter_profanity: Filter inappropriate language
            confidence_threshold: Minimum confidence score
            include_timestamps: Include word-level timestamps
            medical_entity_recognition: Enable medical entity recognition

        Returns:
            Data: Speech transcription response with healthcare metadata
        """
        request_data = {
            "audio_file": audio_file,
            "audio_url": audio_url,
            "transcription_mode": transcription_mode,
            "medical_specialty": medical_specialty,
            "language_model": language_model,
            "enable_speaker_identification": enable_speaker_identification,
            "enable_punctuation": enable_punctuation,
            "filter_profanity": filter_profanity,
            "confidence_threshold": confidence_threshold,
            "include_timestamps": include_timestamps,
            "medical_entity_recognition": medical_entity_recognition,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self.execute_healthcare_workflow(request_data)