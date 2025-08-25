from . import factory, service
from .base import Settings

# Create a default settings instance for backward compatibility
settings = Settings()

__all__ = ["Settings", "factory", "service", "settings"]
