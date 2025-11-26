"""Unified ModelHub Settings - Consolidated configuration for all providers."""

import os
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelHubSettings(BaseSettings):
    """ModelHub settings configuration"""



    API_TIMEOUT: int = 120
    CACHE_TTL_PROVIDERS: int = Field(
        default=300, description="Cache TTL for provider list in seconds"  # 5 minutes
    )
    CACHE_TTL_MODELS: int = Field(
        default=600, description="Cache TTL for model lists in seconds"  # 10 minutes
    )
    ENABLE_FALLBACKS: bool = True

    # =============================================================================
    # Common Provider Settings
    # =============================================================================
    API_KEY: str | None = None
    IS_VERIFY: bool = True

    # =============================================================================
    # Azure OpenAI Specific Settings (Complex Environment Handling)
    # =============================================================================
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_DEPLOYMENT: str | None = None
    AZURE_EMBEDDING_DEPLOYMENT: str | None = None
    AZURE_USE_REST_API: bool = False
    AZURE_CUSTOM_HEADERS: Dict[str, str] = {}
    AZURE_IS_CLIENT_ENVIRONMENT: bool = False
    AZURE_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_API_KEY: str | None = None


    URI: str = Field(
        default=os.getenv("MODELHUB_URI", "https://api-genesis-modelhub.sprint.autonomize.dev"),
        description="Base URI for ModelHub API"
    )
    AUTH_URL: str = Field(
        default=os.getenv("MODELHUB_AUTH_URL", "https://api-genesis-modelhub.sprint.autonomize.dev/auth/token"),
        description="Authentication URL for ModelHub"
    )
    AUTH_CLIENT_ID: str = Field(
        default=os.getenv("MODELHUB_AUTH_CLIENT_ID", ""),
        description="Service account client ID for ModelHub authentication"
    )
    AUTH_CLIENT_SECRET: str = Field(
        default=os.getenv("MODELHUB_AUTH_CLIENT_SECRET", ""),
        description="Service account client secret for ModelHub authentication"
    )
    GENESIS_COPILOT_ID: str = Field(
        default=os.getenv("MODELHUB_GENESIS_COPILOT_ID", ""),
        description="Genesis Copilot ID for ModelHub"
    )
    GENESIS_CLIENT_ID: str = Field(
        default=os.getenv("MODELHUB_GENESIS_CLIENT_ID", ""),
        description="Genesis Client ID for ModelHub"
    )
    USER_AGENT: str = "genesis_studio"
    TIMEOUT: int = 120

    # Endpoint URLs
    CLLM_MODEL: str | None = None
    CLINICAL_NOTE_CLASSIFIER_MODEL: str | None = None
    COMBINED_ENTITY_LINKING_MODEL: str | None = None
    CPT_CODE_MODEL: str | None = None
    ICD_10_MODEL: str | None = None
    RXNORM_MODEL: str | None = None
    SRF_EXTRACTION_MODEL: str | None = None
    SRF_IDENTIFICATION_MODEL: str | None = None
    EMBEDDING_MODEL: str | None = None
    # HEDIS MODELS
    HEDIS_OBJECT_DETECTION_CCS: str | None = None
    HEDIS_SLM_VALIDATION_CCS: str | None = None

    def is_configured(self) -> bool:
        """Check if required settings are configured."""
        return all([
            self.URI,
            self.AUTH_URL,
            self.AUTH_CLIENT_ID and self.AUTH_CLIENT_ID != "",
            self.AUTH_CLIENT_SECRET and self.AUTH_CLIENT_SECRET != "",
            self.GENESIS_COPILOT_ID and self.GENESIS_COPILOT_ID != "",
            self.GENESIS_CLIENT_ID and self.GENESIS_CLIENT_ID != ""
        ])

    model_config = SettingsConfigDict(
        env_prefix="MODELHUB_", case_sensitive=True, validate_assignment=True
    )


# Global settings instance
modelhub_settings = ModelHubSettings()
