# services/ocr/settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class OCRSettings(BaseSettings):
    """Azure OCR settings configuration"""

    DEFAULT_ENDPOINT: str = ""
    DEFAULT_API_KEY: str | None = None
    DEFAULT_MODEL_TYPE: str = "prebuilt-document"
    TIMEOUT: int = 300

    def is_configured(self) -> bool:
        """Check if required settings are configured."""
        return bool(self.DEFAULT_ENDPOINT)

    model_config = SettingsConfigDict(
        env_prefix="AZURE_OCR_", case_sensitive=True, validate_assignment=True
    )
