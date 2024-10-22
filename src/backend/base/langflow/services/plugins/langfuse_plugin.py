from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from langflow.services.deps import get_settings_service
from langflow.services.plugins.base import CallbackPlugin

if TYPE_CHECKING:
    from langfuse import Langfuse


class LangfuseInstance:
    _instance: Langfuse | None = None

    @classmethod
    def get(cls):
        logger.debug("Getting Langfuse instance")
        if cls._instance is None:
            cls.create()
        return cls._instance

    @classmethod
    def create(cls) -> None:
        try:
            logger.debug("Creating Langfuse instance")
            from langfuse import Langfuse

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
    def update(cls) -> None:
        logger.debug("Updating Langfuse instance")
        cls._instance = None
        cls.create()

    @classmethod
    def teardown(cls) -> None:
        logger.debug("Tearing down Langfuse instance")
        if cls._instance is not None:
            cls._instance.flush()
        cls._instance = None


class LangfusePlugin(CallbackPlugin):
    def initialize(self) -> None:
        LangfuseInstance.create()

    def teardown(self) -> None:
        LangfuseInstance.teardown()

    def get(self):
        return LangfuseInstance.get()

    def get_callback(self, _id: str | None = None):
        if _id is None:
            _id = "default"

        logger.debug("Initializing langfuse callback")

        try:
            langfuse_instance = self.get()
            if langfuse_instance is not None and hasattr(langfuse_instance, "trace"):
                trace = langfuse_instance.trace(name="langflow-" + _id, id=_id)
                if trace:
                    return trace.getNewHandler()

        except Exception:  # noqa: BLE001
            logger.exception("Error initializing langfuse callback")

        return None
