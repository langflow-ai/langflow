"""Unified ModelHub Settings - Consolidated configuration for all providers."""

import os
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelHubSettings(BaseSettings):
    """ModelHub settings configuration"""

    # =============================================================================
    # Genesis ModelHub Core Configuration
    # =============================================================================

    API_TIMEOUT: int = 120

    URI: str = "default_base_url"
    AUTH_CLIENT_ID: str = "default_sa_client_id"
    AUTH_CLIENT_SECRET: str = "default_sa_client_secret"
    GENESIS_COPILOT_ID: str = "default_copilot_id"
    GENESIS_CLIENT_ID: str = "default_client_id"
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
    LETTER_SPLIT_MODEL: str | None = None
    EMBEDDING_MODEL: str | None = None

    def is_configured(self) -> bool:
        """Check if required settings are configured."""
        return all([self.URI, self.AUTH_CLIENT_ID, self.AUTH_CLIENT_SECRET])

    model_config = SettingsConfigDict(
        env_prefix="MODELHUB_", case_sensitive=True, validate_assignment=True
    )


# Global settings instance
modelhub_settings = ModelHubSettings()
