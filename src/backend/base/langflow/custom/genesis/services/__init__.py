"""Genesis Studio Custom Services Registration.

This module registers all Genesis Studio custom services with Langflow.
"""

import logging

from . import deps

logger = logging.getLogger(__name__)


def register_genesis_services():
    """Register custom services with Langflow."""
    try:
        # Import the service manager
        from langflow.services.manager import ServiceManager

        service_manager = ServiceManager()
        registered_services = []
        failed_services = []

        # Try to register External Integration Service
        try:
            from .external_integration.factory import ExternalIntegrationServiceFactory

            factory = ExternalIntegrationServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"ExternalIntegrationService: {e}")

        # Try to register FlexStore Service
        try:
            from .flexstore.factory import FlexStoreServiceFactory

            factory = FlexStoreServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"FlexStoreService: {e}")

        # Try to register ModelHub Service (legacy)
        try:
            from .modelhub.factory import ModelHubServiceFactory

            factory = ModelHubServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"ModelHubService (legacy): {e}")

        # Try to register OCR Service (might fail if Azure SDK not installed)
        try:
            from .ocr.factory import OCRServiceFactory

            factory = OCRServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"OCRService: {e}")

        # Try to register Document Intelligence Service (from main services, not Genesis)
        try:
            from langflow.services.document_intelligence.factory import DocumentIntelligenceServiceFactory

            factory = DocumentIntelligenceServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"DocumentIntelligenceService: {e}")

        # Try to register Knowledge Service
        try:
            from .knowledge.factory import KnowledgeServiceFactory

            factory = KnowledgeServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"KnowledgeService: {e}")

        # Try to register RAG Service
        try:
            from .rag.factory import RAGServiceFactory

            factory = RAGServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"RAGService: {e}")

        # Try to register Tracing Service (might fail if autonomize_observer not installed)
        try:
            from .tracing.factory import TracingServiceFactory

            factory = TracingServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"TracingService: {e}")

        # Try to register AI Gateway Service
        try:
            from .ai_gateway.factory import AIGatewayServiceFactory

            factory = AIGatewayServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"AIGatewayService: {e}")

        # Try to register Prompt Service
        try:
            from .prompt.factory import PromptServiceFactory

            factory = PromptServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"PromptService: {e}")

        # Try to register Azure Search Service
        try:
            from .azure_search.factory import AzureSearchServiceFactory

            factory = AzureSearchServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"AzureSearchService: {e}")

        # Try to register Agent Builder Service
        try:
            from .agent_builder.factory import AgentBuilderServiceFactory

            factory = AgentBuilderServiceFactory()
            service_manager.register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except (ImportError, ValueError, AttributeError) as e:
            failed_services.append(f"AgentBuilderService: {e}")

        # Report results
        if registered_services:
            logger.info("✅ Custom services registered successfully:")
            for service in registered_services:
                logger.info("  - %s", service)

        if failed_services:
            logger.warning("⚠️  Some services failed to register (optional dependencies missing):")
            for service in failed_services:
                logger.warning("  - %s", service)

        # Return True if at least one service was registered
        return len(registered_services) > 0

    except ImportError:
        logger.exception("❌ Import error while registering custom services")
        return False
    except (ValueError, AttributeError, RuntimeError):
        logger.exception("❌ Failed to register custom services")
        return False


__all__ = ["deps", "register_genesis_services"]
