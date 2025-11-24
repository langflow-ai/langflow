"""Defines ModelEndpoint Enum for Model Hub service."""

from enum import Enum

from .settings import ModelHubSettings


class ModelEndpoint(Enum):
    """Enumeration of available ModelHub endpoints and their environment variable keys."""

    CLINICAL_LLM = "CLLM_MODEL"
    CLINICAL_NOTE_CLASSIFIER = "CLINICAL_NOTE_CLASSIFIER_MODEL"
    COMBINED_ENTITY_LINKING = "COMBINED_ENTITY_LINKING_MODEL"
    CPT_CODE = "CPT_CODE_MODEL"
    ICD_10 = "ICD_10_MODEL"
    RXNORM = "RXNORM_MODEL"
    SRF_EXTRACTION = "SRF_EXTRACTION_MODEL"
    SRF_IDENTIFICATION = "SRF_IDENTIFICATION_MODEL"
    EMBEDDING = "EMBEDDING_MODEL"
    HEDIS_OBJECT_DETECTION_CCS = "HEDIS_OBJECT_DETECTION_CCS"
    HEDIS_SLM_VALIDATION_CCS = "HEDIS_SLM_VALIDATION_CCS"

    def get_model(self) -> str:
        """Retrieves the model name string from settings based on the enum value."""
        settings = ModelHubSettings()
        model = getattr(settings, self.value)
        if not model:
            raise ValueError(
                f"ModelHub {self.value} not configured in environment variables"
            )
        return model
