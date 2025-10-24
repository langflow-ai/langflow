"""FlexStore service for managing flexible storage interactions."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Optional

import aiohttp
from langflow.services.base import Service

from .settings import FlexStoreSettings

logger = logging.getLogger(__name__)


class FlexStoreService(Service):
    """Service for managing flexible storage interactions."""

    name = "flexstore_service"

    def __init__(self):
        """Initialize the FlexStore service."""
        super().__init__()
        # Initialize settings from environment variables
        self.settings = FlexStoreSettings()
        self._http_client: Optional[aiohttp.ClientSession] = None
        self._ready = False

    def set_ready(self) -> None:
        """Set the service as ready."""
        if not self.settings.is_configured():
            logger.warning("FlexStore settings are not properly configured, service will run in limited mode")
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if the service is ready."""
        return self._ready

    @property
    def http_client(self) -> aiohttp.ClientSession:
        """Get the HTTP client, initializing it if necessary."""
        if not self._http_client or self._http_client.closed:
            # Configure connector with connection pooling
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connection pool size
                limit_per_host=20,  # Connections per host
                keepalive_timeout=30,  # Keep connections alive
                enable_cleanup_closed=True,
            )

            # Configure timeout
            timeout = aiohttp.ClientTimeout(
                total=self.settings.TIMEOUT,
                connect=self.settings.CONNECT_TIMEOUT,
                sock_read=self.settings.READ_TIMEOUT,
            )

            self._http_client = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "User-Agent": self.settings.USER_AGENT,
                    "Content-Type": "application/json",
                },
            )
            logger.debug("FlexStore HTTP client initialized with connection pooling")
        return self._http_client

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._http_client and not self._http_client.closed:
            await self._http_client.close()
            self._http_client = None
            logger.debug("FlexStore HTTP client closed")

    async def health_check(self) -> bool:
        """Check if the FlexStore service is healthy."""
        if not self.ready:
            return False

        if not self.settings.ENDPOINT_URL:
            logger.warning("FlexStore endpoint URL not configured")
            return False

        try:
            # Simple health check - try to reach the base URL
            url = f"{self.settings.ENDPOINT_URL}/health"
            async with self.get_client() as client:
                async with client.get(
                    url, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.warning(f"FlexStore health check failed: {e}")
            return False

    @asynccontextmanager
    async def get_client(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """Context manager for getting an HTTP client."""
        try:
            yield self.http_client
        finally:
            pass

    async def _make_request(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        """Make an async HTTP request using aiohttp."""
        logger.debug(f"Making {method.upper()} request to {url}")

        async with self.get_client() as client:
            try:
                async with client.request(method, url, **kwargs) as response:
                    logger.debug(f"Request completed - Status: {response.status}")
                    response.raise_for_status()
                    return await response.json()

            except aiohttp.ClientConnectionError as e:
                logger.error(f"Connection error: {e}")
                logger.error(f"URL: {url}")
                raise
            except aiohttp.ClientResponseError as e:
                logger.error(f"HTTP error: {e.status} {e.message}")
                logger.error(f"URL: {url}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                logger.error(f"URL: {url}")
                raise

    async def get_containers(self, storage_account: Optional[str] = None) -> list[str]:
        """Fetch the list of containers from the storage account."""
        if not self.settings.ENDPOINT_URL:
            logger.warning("FlexStore endpoint URL not configured")
            return []

        try:
            url = f"{self.settings.ENDPOINT_URL}/api/v1/containers"
            payload = {
                "sourceType": "azureblobstorage",
                "storageAccount": storage_account
                or self.settings.DEFAULT_STORAGE_ACCOUNT,
            }

            data = await self._make_request("POST", url, json=payload)
            return data.get("data", {}).get("containers", [])

        except Exception as e:
            logger.error(f"Error fetching containers: {e}")
            return []

    async def get_files(self, storage_account: Optional[str], container_name: str) -> list[str]:
        """Fetch the list of files from a container."""
        if not self.settings.ENDPOINT_URL:
            logger.warning("FlexStore endpoint URL not configured")
            return []

        try:
            url = f"{self.settings.ENDPOINT_URL}/api/v1/files"
            payload = {
                "sourceType": "azureblobstorage",
                "sourceDetails": {
                    "storageAccount": storage_account
                    or self.settings.DEFAULT_STORAGE_ACCOUNT,
                    "containerName": container_name,
                },
            }

            data = await self._make_request("POST", url, json=payload)
            return data.get("data", {}).get("files", [])

        except Exception as e:
            logger.error(f"Error fetching files: {e}")
            return []

    async def get_signed_url(
        self, storage_account: Optional[str], container_name: str, file_name: str
    ) -> Optional[str]:
        """Get a signed URL for a specific file."""
        if not self.settings.ENDPOINT_URL:
            logger.warning("FlexStore endpoint URL not configured")
            return None

        try:
            url = f"{self.settings.ENDPOINT_URL}/api/v1/signedUrl/read"
            payload = {
                "sourceType": "azureblobstorage",
                "fileName": file_name,
                "sourceDetails": {
                    "storageAccount": storage_account
                    or self.settings.DEFAULT_STORAGE_ACCOUNT,
                    "containerName": container_name,
                },
            }
            headers = {"accept": "application/json"}
            data = await self._make_request("POST", url, json=payload, headers=headers)
            return data.get("data", {}).get("signedUrl")

        except Exception as e:
            logger.error(f"Error getting signed URL: {e}")
            return None

    async def _retry_request(self, func, *args, max_retries: int = 3, **kwargs) -> Any:
        """Retry a request with exponential backoff."""
        import random

        last_exception = None

        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except (
                aiohttp.ClientConnectionError,
                aiohttp.ServerTimeoutError,
                aiohttp.AsyncTimeoutError,
                aiohttp.ClientResponseError,
            ) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time:.2f}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
                    raise

        # This should never be reached, but if it is, raise the last exception
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry loop completed without success or exception")

    async def get_signed_url_upload(
        self, storage_account: Optional[str], container_name: Optional[str], file_name: str
    ) -> Optional[str]:
        """Get a signed URL for uploading a file."""
        if not self.settings.ENDPOINT_URL:
            logger.warning("FlexStore endpoint URL not configured")
            return None

        try:
            url = f"{self.settings.ENDPOINT_URL}/api/v1/signedUrl/upload"
            payload = {
                "sourceType": "azureblobstorage",
                "fileName": file_name,
                "sourceDetails": {
                    "storageAccount": storage_account or self.settings.DEFAULT_TEMPORARY_STORAGE_ACCOUNT,
                    "containerName": container_name or self.settings.DEFAULT_TEMPORARY_STORAGE_CONTAINER,
                },
            }
            headers = {"accept": "application/json"}

            # Use retry logic for this critical operation
            data = await self._retry_request(
                self._make_request,
                "POST",
                url,
                json=payload,
                headers=headers,
                max_retries=3,
            )
            return data.get("data", {}).get("signedUrl")

        except Exception as e:
            logger.error(f"Error getting upload signed URL: {e}")
            return None