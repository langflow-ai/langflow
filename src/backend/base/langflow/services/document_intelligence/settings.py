"""Settings for Azure Document Intelligence Service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentIntelligenceSettings(BaseSettings):
    """Azure Document Intelligence settings configuration."""

    # Azure Document Intelligence endpoint and credentials
    ENDPOINT: str = ""
    API_KEY: str | None = None

    # Default processing options
    DEFAULT_MODEL_TYPE: str = "prebuilt-document"
    TIMEOUT: int = 300

    # Feature flags
    EXTRACT_TABLES: bool = True
    EXTRACT_KEY_VALUE_PAIRS: bool = True
    INCLUDE_CONFIDENCE: bool = False

    def is_configured(self) -> bool:
        """Check if required settings are configured."""
        return bool(self.ENDPOINT)

    model_config = SettingsConfigDict(
        env_prefix="AZURE_OCR_DEFAULT_",
        case_sensitive=True,
        validate_assignment=True
    )