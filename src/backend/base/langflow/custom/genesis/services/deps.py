"""Dependency injection utilities for Genesis Studio Backend services.

This module provides clean access to custom services through getter functions,
following the same pattern as langflow's deps.py for consistency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.backend.base.langflow.custom.genesis.services.ai_gateway.service import AIGatewayService
    from src.backend.base.langflow.custom.genesis.services.claim_auth_history.service import ClaimAuthHistoryService
    from src.backend.base.langflow.custom.genesis.services.encoder_pro.service import EncoderProService
    from src.backend.base.langflow.custom.genesis.services.external_integration.service import (
        ExternalIntegrationService,
    )
    from src.backend.base.langflow.custom.genesis.services.flexstore.service import FlexStoreService
    from src.backend.base.langflow.custom.genesis.services.knowledge.service import KnowledgeService
    from src.backend.base.langflow.custom.genesis.services.modelhub.service import ModelHubService
    from src.backend.base.langflow.custom.genesis.services.ocr.service import OCRService
    from src.backend.base.langflow.custom.genesis.services.pa_lookup.service import PALookupService
    from src.backend.base.langflow.custom.genesis.services.prompt.service import PromptService
    from src.backend.base.langflow.custom.genesis.services.rag.service import RAGService
    from src.backend.base.langflow.custom.genesis.services.tracing.service import TracingService


def get_service(service_name: str, default=None):
    """Retrieves the service instance for the given service name.

    Args:
        service_name (str): The name of the service to retrieve.
        default (ServiceFactory, optional): The default ServiceFactory to use if the service is not found.
            Defaults to None.

    Returns:
        Any: The service instance.
    """
    from lfx.services.manager import get_service_manager

    service_manager = get_service_manager()

    if not service_manager.factories:
        # Ensure that the service manager is initialized
        try:
            from loguru import logger

            logger.debug("Initializing service manager and registering LFX factories...")
            service_manager.register_factories()

            # Register our custom services
            logger.debug("Registering Genesis custom services...")
            from src.backend.base.langflow.custom.genesis.services import register_genesis_services

            success = register_genesis_services()
            if success:
                logger.debug("✅ Genesis services registration completed successfully")
            else:
                logger.warning("⚠️ Genesis services registration completed with some failures")
        except (ImportError, ValueError, RuntimeError, AttributeError) as e:
            from loguru import logger

            logger.error("❌ Failed to register Genesis services: %s", e)
            import traceback

            logger.debug("Error details: %s", traceback.format_exc())

    try:
        return service_manager.get(service_name, default)
    except (KeyError, AttributeError, RuntimeError) as e:
        from loguru import logger

        logger.error("❌ Failed to get service '%s': %s", service_name, e)
        raise


def get_external_integration_service() -> ExternalIntegrationService:
    """Retrieves the ExternalIntegrationService instance from the service manager.

    Returns:
        ExternalIntegrationService: The ExternalIntegrationService instance.
    """
    from src.backend.base.langflow.custom.genesis.services.external_integration.factory import (
        ExternalIntegrationServiceFactory,
    )

    return get_service("external_integration_service", ExternalIntegrationServiceFactory())


def get_flexstore_service() -> FlexStoreService:
    """Retrieves the FlexStoreService instance from the service manager.

    Returns:
        FlexStoreService: The FlexStoreService instance.
    """
    from src.backend.base.langflow.custom.genesis.services.flexstore.factory import FlexStoreServiceFactory

    return get_service("flexstore_service", FlexStoreServiceFactory())


def get_knowledge_service() -> KnowledgeService:
    """Retrieves the KnowledgeService instance from the service manager.

    Returns:
        KnowledgeService: The KnowledgeService instance.
    """
    from src.backend.base.langflow.custom.genesis.services.knowledge.factory import KnowledgeServiceFactory

    return get_service("knowledge_service", KnowledgeServiceFactory())


def get_modelhub_service() -> ModelHubService:
    """Retrieves the ModelHubService instance from the service manager.

    Returns:
        ModelHubService: The ModelHubService instance.
    """
    from src.backend.base.langflow.custom.genesis.services.modelhub.factory import ModelHubServiceFactory

    return get_service("modelhub_service", ModelHubServiceFactory())


def get_ocr_service() -> OCRService:
    """Retrieves the OCRService instance from the service manager.

    Returns:
        OCRService: The OCRService instance.
    """
    from src.backend.base.langflow.custom.genesis.services.ocr.factory import OCRServiceFactory

    return get_service("ocr_service", OCRServiceFactory())


def get_prompt_service() -> PromptService:
    """Retrieves the PromptService instance from the service manager.

    Returns:
        PromptService: The PromptService instance.
    """
    from src.backend.base.langflow.custom.genesis.services.prompt.factory import PromptServiceFactory

    return get_service("prompt_service", PromptServiceFactory())


def get_rag_service() -> RAGService:
    """Retrieves the RAGService instance from the service manager.

    Returns:
        RAGService: The RAGService instance.
    """
    from src.backend.base.langflow.custom.genesis.services.rag.factory import RAGServiceFactory

    return get_service("rag_service", RAGServiceFactory())


def get_genesis_tracing_service() -> TracingService:
    """Retrieves the Genesis TracingService instance from the service manager.

    Note: This is different from langflow's built-in tracing service.

    Returns:
        TracingService: The Genesis TracingService instance.
    """
    from src.backend.base.langflow.custom.genesis.services.tracing.factory import TracingServiceFactory

    return get_service("genesis_tracing_service", TracingServiceFactory())


def get_pa_lookup_service() -> PALookupService:
    """Retrieves the PALookupService instance from the service manager."""
    from src.backend.base.langflow.custom.genesis.services.pa_lookup.factory import PALookupServiceFactory

    return get_service("pa_lookup_service", PALookupServiceFactory())


def get_encoder_pro_service() -> EncoderProService:
    """Retrieves the EncoderProService instance from the service manager."""
    from src.backend.base.langflow.custom.genesis.services.encoder_pro.factory import EncoderProServiceFactory

    return get_service("encoder_pro_service", EncoderProServiceFactory())


def get_claim_auth_history_service() -> ClaimAuthHistoryService:
    """Retrieves the ClaimAuthHistoryService instance from the service manager."""
    from src.backend.base.langflow.custom.genesis.services.claim_auth_history.factory import (
        ClaimAuthHistoryServiceFactory,
    )

    return get_service("claim_auth_history_service", ClaimAuthHistoryServiceFactory())


def get_ai_gateway_service() -> AIGatewayService:
    """Retrieves the AIGatewayService instance from the service manager."""
    from .ai_gateway.factory import AIGatewayServiceFactory

    return get_service("ai_gateway_service", AIGatewayServiceFactory())


# Convenience function for common service combinations
def get_ai_services() -> tuple[ModelHubService, PromptService, RAGService]:
    """Get commonly used AI-related services together.

    Returns:
        tuple: (ModelHubService, PromptService, RAGService)
    """
    return (
        get_modelhub_service(),
        get_prompt_service(),
        get_rag_service(),
    )


def get_data_services() -> tuple[FlexStoreService, KnowledgeService, ExternalIntegrationService]:
    """Get commonly used data-related services together.

    Returns:
        tuple: (FlexStoreService, KnowledgeService, ExternalIntegrationService)
    """
    return (
        get_flexstore_service(),
        get_knowledge_service(),
        get_external_integration_service(),
    )
