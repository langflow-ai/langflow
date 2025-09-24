"""Genesis Studio Custom Services Registration.

This module registers all Genesis Studio custom services with Langflow.
"""


def register_genesis_services():
    """Register custom services with Langflow."""
    try:
        # Import the service manager
        from lfx.services.manager import get_service_manager

        registered_services = []
        failed_services = []

        # Try to register External Integration Service
        try:
            from .external_integration.factory import ExternalIntegrationServiceFactory

            factory = ExternalIntegrationServiceFactory()
            get_service_manager().register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except Exception as e:
            failed_services.append(f"ExternalIntegrationService: {e}")

        # Try to register FlexStore Service
        try:
            from .flexstore.factory import FlexStoreServiceFactory

            factory = FlexStoreServiceFactory()
            get_service_manager().register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except Exception as e:
            failed_services.append(f"FlexStoreService: {e}")

        # Try to register ModelHub Service (legacy)
        try:
            from .modelhub.factory import ModelHubServiceFactory

            factory = ModelHubServiceFactory()
            get_service_manager().register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except Exception as e:
            failed_services.append(f"ModelHubService (legacy): {e}")


        # Try to register OCR Service (might fail if Azure SDK not installed)
        try:
            from .ocr.factory import OCRServiceFactory

            factory = OCRServiceFactory()
            get_service_manager().register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except Exception as e:
            failed_services.append(f"OCRService: {e}")

        # Try to register Knowledge Service
        try:
            from .knowledge.factory import KnowledgeServiceFactory

            factory = KnowledgeServiceFactory()
            get_service_manager().register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except Exception as e:
            failed_services.append(f"KnowledgeService: {e}")

        # Try to register RAG Service
        try:
            from .rag.factory import RAGServiceFactory

            factory = RAGServiceFactory()
            get_service_manager().register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except Exception as e:
            failed_services.append(f"RAGService: {e}")

        # Try to register Tracing Service (might fail if autonomize_observer not installed)
        try:
            from .tracing.factory import TracingServiceFactory

            factory = TracingServiceFactory()
            get_service_manager().register_factory(factory)
            registered_services.append(factory.service_class.__name__)
        except Exception as e:
            failed_services.append(f"TracingService: {e}")


        # Report results
        if registered_services:
            print("✅ Custom services registered successfully:")
            for service in registered_services:
                print(f"  - {service}")

        if failed_services:
            print(
                "⚠️  Some services failed to register (optional dependencies missing):"
            )
            for service in failed_services:
                print(f"  - {service}")

        # Return True if at least one service was registered
        return len(registered_services) > 0

    except ImportError as e:
        print(f"❌ Import error while registering custom services: {e}")
        return False
    except Exception as e:
        print(f"❌ Failed to register custom services: {e}")
        return False


__all__ = ["register_genesis_services", "deps"]

# Import deps module for easy access to dependency injection functions
from . import deps
