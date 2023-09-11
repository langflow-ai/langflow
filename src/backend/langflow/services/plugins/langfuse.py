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
        logger.debug("Checking Langfuse credentials")
        from langflow.settings import settings
        from langfuse import Langfuse  # type: ignore

        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            logger.debug("Langfuse credentials found")
            cls._instance = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
            )
        else:
            logger.debug("No Langfuse credentials found")
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
