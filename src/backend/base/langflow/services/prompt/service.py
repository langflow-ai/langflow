"""Prompt service for Genesis Studio."""

from __future__ import annotations

import aiohttp
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from langflow.services.base import Service
from loguru import logger

from .settings import PromptSettings


class PromptService(Service):
    """Service for managing prompts."""

    name = "prompt_service"

    def __init__(self):
        """Initialize the prompt service."""
        super().__init__()
        self.settings = PromptSettings()
        self._http_client: Optional[aiohttp.ClientSession] = None
        self._ready = False

    def set_ready(self) -> None:
        """Set the service as ready."""
        if not self.settings.is_configured():
            logger.warning("Prompt settings are not properly configured, service will run in limited mode")
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
            logger.debug("Prompt HTTP client closed")

    @asynccontextmanager
    async def get_client(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """Context manager for getting an HTTP client."""
        try:
            yield self.http_client
        finally:
            pass

    async def get_published_prompts(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Get published prompt versions from the API."""
        if not self.ready:
            logger.error("Prompt service is not ready")
            return {"data": {"versions": [], "total": 0}, "message": "Service not ready", "error": "Service not initialized"}

        try:
            url = f"{self.settings.ENDPOINT_URL}/api/v1/versions"
            params = {"status": "published"}

            logger.info(f"Fetching published prompts from: {url}")

            async with self.get_client() as client:
                async with client.get(
                    url,
                    params=params,
                    headers={"accept": "application/json"},
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    logger.info(f"Prompt API response: {data}")
                    return data

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"Prompt management service unavailable at {self.settings.ENDPOINT_URL}: {e!s}")
            return {"data": {"versions": [], "total": 0}, "message": "Service unavailable", "error": str(e)}
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error fetching published prompts: {e.status}, {e.message}")
            return {"data": {"versions": [], "total": 0}, "message": f"HTTP {e.status}", "error": str(e)}
        except Exception as e:
            logger.error(f"Error fetching published prompts: {e!s}")
            logger.exception("Full error details:")
            return {"data": {"versions": [], "total": 0}, "message": "", "error": str(e)}