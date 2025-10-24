from __future__ import annotations

import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from langflow.services.base import Service
from loguru import logger

from .settings import ModelHubSettings


class ModelHubService(Service):
    """Independent ModelHub service that manages its own configuration and HTTP client."""

    name = "modelhub_service"

    def __init__(self):
        super().__init__()
        # Initialize settings from environment variables
        self.settings = ModelHubSettings()
        self._http_client: aiohttp.ClientSession | None = None
        self._auth_token: str | None = None
        self._ready = False
        # Create SSL context that skips verification
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

        logger.debug(f"ModelHubService initialized with settings: {self.settings}")

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

    async def call_endpoint(
        self,
        endpoint: str,
        method: str = "POST",
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Call a ModelHub endpoint."""
        if not self.settings.is_configured():
            msg = "ModelHub settings are not properly configured"
            raise ValueError(msg)

        try:
            return await self._make_request(endpoint, method, json_data=params)
        except Exception as e:
            logger.error(f"Error calling ModelHub endpoint {endpoint}: {e!s}")
            raise

    async def text_inference(self, model_name: str, text: str, json_data: dict | None = None):
        """Call ModelHub Sdk Text Inferencing."""
        try:
            # For now, we'll return a mock response until the modelhub client is available
            logger.debug(f"Mock text_inference for model: {model_name}, text: {text[:50]}...")
            return {"result": "Mock response - ModelHub client not available"}
        except Exception as e:
            logger.error(f"Error calling Text Inferencing: {e!s}")
            raise

    async def file_inference(
        self,
        model_name: str,
        file_path: str,
        file_name: str | None = None,
        content_type: str | None = None,
    ):
        """Call ModelHub Sdk File Inferencing."""
        try:
            # For now, we'll return a mock response until the modelhub client is available
            logger.debug(f"Mock file_inference for model: {model_name}, file: {file_path}")
            return {"result": "Mock response - ModelHub client not available"}
        except Exception as e:
            logger.error(f"Error in File Inferencing : {e!s}")
            raise

    async def _make_request(
        self,
        endpoint: str,
        method: str,
        json_data: dict | None = None,
        data: bytes | None = None,
        content_type: str = "application/json",
        retry_auth: bool = True,
    ) -> Any:
        """Make a request to ModelHub with token retry logic."""
        token = await self._get_auth_token()
        headers = {
            "Content-Type": content_type,
            "Authorization": f"Bearer {token}",
        }

        async with self.get_client() as client:
            try:
                async with client.request(
                    method=method,
                    url=endpoint,
                    headers=headers,
                    json=json_data if json_data is not None else None,
                    data=data if data is not None else None,
                    ssl=self._ssl_context,
                ) as response:
                    if response.status == 401 and retry_auth:
                        # Clear cached token and retry once
                        self._auth_token = None
                        return await self._make_request(
                            endpoint,
                            method,
                            json_data,
                            data,
                            content_type,
                            retry_auth=False,
                        )
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientResponseError as e:
                if e.status == 401 and retry_auth:
                    # Clear cached token and retry once
                    self._auth_token = None
                    return await self._make_request(
                        endpoint,
                        method,
                        json_data,
                        data,
                        content_type,
                        retry_auth=False,
                    )
                raise

    def check_model_hub_configuration(self):
        if not self.settings.is_configured():
            msg = "ModelHub settings are not properly configured"
            raise ValueError(msg)

    async def call_endpoint_binary(
        self,
        endpoint: str,
        method: str = "POST",
        binary_data: bytes | None = None,
        content_type: str = "application/octet-stream",
    ) -> Any:
        """Call a ModelHub endpoint with binary data."""
        self.check_model_hub_configuration()

        try:
            return await self._make_request(
                endpoint, method, data=binary_data, content_type=content_type
            )
        except Exception as e:
            logger.error(f"Error calling ModelHub endpoint {endpoint}: {e!s}")
            raise

    async def _get_auth_token(self) -> str:
        """Get authentication token for ModelHub."""
        # Return cached token if available
        if self._auth_token:
            return self._auth_token

        if not self.settings.is_configured():
            msg = "Missing required ModelHub authentication settings"
            raise ValueError(msg)

        try:
            async with self.get_client() as client:
                async with client.post(
                    self.settings.AUTH_URL,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.settings.AUTH_CLIENT_ID,
                        "client_secret": self.settings.AUTH_CLIENT_SECRET,
                        "scope": "openid",
                    },
                    ssl=self._ssl_context,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    self._auth_token = data["access_token"]
                    return self._auth_token
        except Exception as e:
            logger.error(f"Error getting auth token: {e!s}")
            raise