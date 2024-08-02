from typing import TYPE_CHECKING, Optional

from loguru import logger

from langflow.services.deps import get_settings_service
from langflow.services.plugins.base import CallbackPlugin

if TYPE_CHECKING:
    from langfuse import Langfuse  # type: ignore


class LangfuseInstance:
    _instance: Optional["Langfuse"] = None

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

            if settings_manager.settings.langfuse_public_key and settings_manager.settings.langfuse_secret_key:
                logger.debug("Langfuse credentials found")
                cls._instance = Langfuse(
                    public_key=settings_manager.settings.langfuse_public_key,
                    secret_key=settings_manager.settings.langfuse_secret_key,
                    host=settings_manager.settings.langfuse_host,
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


class LangfusePlugin(CallbackPlugin):
    def initialize(self):
        LangfuseInstance.create()

    def teardown(self):
        LangfuseInstance.teardown()

    def get(self):
        return LangfuseInstance.get()

    def get_callback(self, _id: Optional[str] = None):
        if _id is None:
            _id = "default"

        logger.debug("Initializing langfuse callback")

        try:
            langfuse_instance = self.get()
            if langfuse_instance is not None and hasattr(langfuse_instance, "trace"):
                trace = langfuse_instance.trace(name="langflow-" + _id, id=_id)
                if trace:
                    return trace.getNewHandler()

        except Exception as exc:
            logger.error(f"Error initializing langfuse callback: {exc}")

        return None
