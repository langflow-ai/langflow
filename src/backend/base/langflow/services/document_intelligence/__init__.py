"""Document Intelligence Service for Azure Document Intelligence integration."""

from .factory import DocumentIntelligenceServiceFactory
from .service import DocumentIntelligenceService

__all__ = ["DocumentIntelligenceService", "DocumentIntelligenceServiceFactory"]