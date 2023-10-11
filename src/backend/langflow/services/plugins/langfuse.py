from langflow.services.getters import get_settings_service
from langflow.utils.logger import logger

### Temporary implementation
# This will be replaced by a plugin system once merged into 0.5.0


class LangfuseInstance:
    _instance = None

    @classmethod
    def get(cls):
        logger.debug("Getting Langfuse instance")
        if cls._instance is None:
            cls.create()
        return cls._instance

    @classmethod
    def create(cls):
        try:
            logger.debug("Creating Langfuse instance")
            from langfuse import Langfuse  # type: ignore

            settings_manager = get_settings_service()

            if (
                settings_manager.settings.LANGFUSE_PUBLIC_KEY
                and settings_manager.settings.LANGFUSE_SECRET_KEY
            ):
                logger.debug("Langfuse credentials found")
                cls._instance = Langfuse(
                    public_key=settings_manager.settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings_manager.settings.LANGFUSE_SECRET_KEY,
                    host=settings_manager.settings.LANGFUSE_HOST,
                )
            else:
                logger.debug("No Langfuse credentials found")
                cls._instance = None
        except ImportError:
            logger.debug("Langfuse not installed")
            cls._instance = None

    @classmethod
    def update(cls):
        logger.debug("Updating Langfuse instance")
        cls._instance = None
        cls.create()

    @classmethod
    def teardown(cls):
        logger.debug("Tearing down Langfuse instance")
        if cls._instance is not None:
            cls._instance.flush()
        cls._instance = None
