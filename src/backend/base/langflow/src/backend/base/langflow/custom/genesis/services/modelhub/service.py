from __future__ import annotations

import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from langflow.services.base import Service
from loguru import logger
from modelhub.clients import InferenceClient
from modelhub.core import ModelhubCredential
from loguru import logger

from .settings import ModelHubSettings


class ModelHubService(Service):
    """Independent ModelHub service that manages its own configuration and HTTP client."""

    name = "modelhub_service"

    def __init__(self):
        super().__init__()
        # Initialize settings from environment variables
        self.settings = ModelHubSettings()
        self.credential = ModelhubCredential(
            modelhub_url=self.settings.URI,
            client_id=self.settings.AUTH_CLIENT_ID,
            client_secret=self.settings.AUTH_CLIENT_SECRET,
        )
        self.client = InferenceClient(
            credential=self.credential,
            copilot_id=self.settings.GENESIS_COPILOT_ID,
            client_id=self.settings.GENESIS_CLIENT_ID,
            timeout=self.settings.TIMEOUT,
        )
        self._http_client: aiohttp.ClientSession | None = None
        self._auth_token: str | None = None
        self._ready = False
        # Create SSL context that skips verification
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

        logger.info(f"ModelHubService initialized with settings: {self.settings}")

    def set_ready(self) -> None:
        """Set the service as ready."""
        if not self.settings.is_configured():
            raise ValueError("ModelHub settings are not properly configured")
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if the service is ready."""
        return self._ready

    @property
    def http_client(self) -> aiohttp.ClientSession:
        """Get the HTTP client, initializing it if necessary."""
        if not self._http_client or self._http_client.closed:
            self._http_client = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.settings.TIMEOUT),
                headers={"User-Agent": self.settings.USER_AGENT},
            )
        return self._http_client

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._http_client and not self._http_client.closed:
            await self._http_client.close()
            self._http_client = None
            logger.debug("ModelHub HTTP client closed")

    @asynccontextmanager
    async def get_client(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """Context manager for getting an HTTP client."""
        try:
            yield self.http_client
        finally:
            pass

    async def text_inference(self, model_name: str, text: str, json_data: dict | None = None):
        """Call ModelHub Sdk Text Inferencing using async."""
        logger.info("🔍 ModelHub.text_inference called (async)")
        logger.info(f"🔍 Model name: {model_name}")
        logger.info(f"🔍 Text length: {len(text) if text else 0}")
        logger.info(f"🔍 Text preview: {text[:100] + '...' if text and len(text) > 100 else text}")
        logger.info(f"🔍 JSON data: {json_data}")

        # Log client configuration
        logger.info(f"🔍 Client type: {type(self.client).__name__}")
        logger.info(f"🔍 Service URI: {self.settings.URI}")
        logger.info(f"🔍 Service ready: {self.ready}")
        logger.info(f"🔍 Client config - Copilot ID: {self.settings.GENESIS_COPILOT_ID}")
        logger.info(f"🔍 Client config - Client ID: {self.settings.GENESIS_CLIENT_ID}")
        logger.info(f"🔍 Client config - Timeout: {self.settings.TIMEOUT}")

        try:
            logger.info("🔍 Making ModelHub SDK async text inference call...")
            result = await self.client.arun_text_inference(
                model_name, text, parameters=json_data
            )
            logger.info(f"✅ ModelHub SDK async call successful")
            logger.info(f"✅ Result type: {type(result)}")
            logger.info(f"✅ Result: {result}")

            # Check if response has the expected structure
            if isinstance(result, dict) and model_name in result:
                # Some APIs return results keyed by model name
                return result[model_name]
            else:
                return result
        except KeyError as e:
            # This might happen if the SDK expects a different response structure
            logger.error(f"❌ KeyError in ModelHub SDK response: {e}")
            logger.error(f"❌ Model name: {model_name}")
            logger.error(f"❌ Key error: {str(e)}")
            # Try to return a default structure
            if str(e).strip("'\"") == model_name:
                # The error is about the model name key itself
                logger.error(f"❌ Model '{model_name}' might not be deployed or accessible")
                # Return empty result structure
                return {"result": {"prediction": []}}
            raise
        except Exception as e:
            logger.error(f"❌ ModelHub SDK async text inference failed: {e}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            logger.error(f"❌ Error args: {e.args}")

            import traceback
            logger.error(f"❌ Full SDK traceback: {traceback.format_exc()}")
            raise

    async def file_inference(
        self,
        model_name: str,
        file_path: str,
        file_name: str | None = None,
        content_type: str | None = None,
    ):
        """Call ModelHub Sdk File Inferencing using async."""
        logger.info("🔍 ModelHub.file_inference called (async)")
        logger.info(f"🔍 Model name: {model_name}")
        logger.info(f"🔍 File path: {file_path}")
        logger.info(f"🔍 File name: {file_name}")
        logger.info(f"🔍 Content type: {content_type}")

        try:
            logger.info("🔍 Making ModelHub SDK async file inference call...")
            result = await self.client.arun_file_inference(
                model_name, file_path, file_name, content_type
            )
            logger.info(f"✅ ModelHub SDK async file inference successful")
            logger.info(f"✅ Result: {result}")
            return result
        except Exception as e:
            logger.error(f"❌ Error in async File Inferencing : {e!s}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            raise
