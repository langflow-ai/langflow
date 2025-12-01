"""Prompt service for Genesis Studio."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from loguru import logger

from langflow.services.base import Service

from .settings import PromptSettings


class PromptService(Service):
    """Service for managing prompts."""

    name = "prompt_service"

    def __init__(self):
        """Initialize the prompt service."""
        super().__init__()
        self.settings = PromptSettings()
        self._http_client: aiohttp.ClientSession | None = None
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

    def _get_auth_headers(self, token: str | None = None) -> dict[str, str]:
        """Get headers with optional authorization token."""
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def get_published_prompts(self, token: str | None = None) -> dict[str, Any]:
        """Get published prompt versions from the API."""
        if not self.ready:
            logger.error("Prompt service is not ready")
            return {
                "data": {"versions": [], "total": 0},
                "message": "Service not ready",
                "error": "Service not initialized",
            }

        try:
            url = f"{self.settings.PROMPTS_ENDPOINT_URL}/api/v1/versions"
            params = {"status": "published"}

            logger.info(f"Fetching published prompts from: {url}")

            async with (
                self.get_client() as client,
                client.get(
                    url,
                    params=params,
                    headers=self._get_auth_headers(token),
                ) as response,
            ):
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Prompt API response: {data}")
                return data

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"Prompt management service unavailable at {self.settings.PROMPTS_ENDPOINT_URL}: {e!s}")
            return {"data": {"versions": [], "total": 0}, "message": "Service unavailable", "error": str(e)}
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error fetching published prompts: {e.status}, {e.message}")
            return {"data": {"versions": [], "total": 0}, "message": f"HTTP {e.status}", "error": str(e)}
        except Exception as e:
            logger.error(f"Error fetching published prompts: {e!s}")
            logger.exception("Full error details:")
            return {"data": {"versions": [], "total": 0}, "message": "", "error": str(e)}

    async def get_draft_prompts(self, token: str | None = None) -> dict[str, Any]:
        """Get draft prompt versions for the current user from the API (requires auth).
        
        Uses /prompts/versions endpoint which filters drafts by the authenticated user.
        """
        if not self.ready:
            logger.error("Prompt service is not ready")
            return {"data": {"prompts": [], "total": 0}, "message": "Service not ready", "error": "Service not initialized"}

        if not token:
            logger.warning("No token provided for fetching draft prompts - skipping")
            return {"data": {"prompts": [], "total": 0}, "message": "Auth required", "error": None}

        try:
            # Use /prompts/versions endpoint (same as genesis-prompt-management)
            # This endpoint filters drafts by the authenticated user
            url = f"{self.settings.PROMPTS_ENDPOINT_URL}/api/v1/prompts/versions"
            params = {"status": "draft", "limit": 1000}

            logger.info(f"Fetching user's draft prompts from: {url}")

            async with (
                self.get_client() as client,
                client.get(url, params=params, headers=self._get_auth_headers(token)) as response,
            ):
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Draft prompts response: {data}")
                return data

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"Prompt management service unavailable: {e!s}")
            return {"data": {"prompts": [], "total": 0}, "message": "Service unavailable", "error": str(e)}
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error fetching draft prompts: {e.status}, {e.message}")
            return {"data": {"prompts": [], "total": 0}, "message": f"HTTP {e.status}", "error": str(e)}
        except Exception as e:
            logger.error(f"Error fetching draft prompts: {e!s}")
            return {"data": {"prompts": [], "total": 0}, "message": "", "error": str(e)}

    async def get_pending_prompts(self, token: str | None = None) -> dict[str, Any]:
        """Get pending approval prompt versions for the current user from the API (requires auth).
        
        Uses /prompts/versions endpoint which filters pending_approval by the authenticated user.
        """
        if not self.ready:
            logger.error("Prompt service is not ready")
            return {"data": {"prompts": [], "total": 0}, "message": "Service not ready", "error": "Service not initialized"}

        if not token:
            logger.warning("No token provided for fetching pending prompts - skipping")
            return {"data": {"prompts": [], "total": 0}, "message": "Auth required", "error": None}

        try:
            url = f"{self.settings.PROMPTS_ENDPOINT_URL}/api/v1/prompts/versions"
            params = {"status": "pending_approval", "limit": 1000}

            logger.info(f"Fetching user's pending approval prompts from: {url}")

            async with (
                self.get_client() as client,
                client.get(url, params=params, headers=self._get_auth_headers(token)) as response,
            ):
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Pending approval prompts response: {data}")
                return data

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"Prompt management service unavailable: {e!s}")
            return {"data": {"prompts": [], "total": 0}, "message": "Service unavailable", "error": str(e)}
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error fetching pending prompts: {e.status}, {e.message}")
            return {"data": {"prompts": [], "total": 0}, "message": f"HTTP {e.status}", "error": str(e)}
        except Exception as e:
            logger.error(f"Error fetching pending prompts: {e!s}")
            return {"data": {"prompts": [], "total": 0}, "message": "", "error": str(e)}

    async def get_prompts_with_versions(self, token: str | None = None, user_id: str | None = None) -> dict[str, Any]:
        """Get prompts with version status including drafts/pending for the current user."""
        if not self.ready:
            logger.error("Prompt service is not ready")
            return {"data": {"prompts": [], "total": 0}, "message": "Service not ready", "error": "Service not initialized"}

        try:
            url = f"{self.settings.PROMPTS_ENDPOINT_URL}/api/v1/prompts/versions"
            params = {"limit": 1000}

            logger.info(f"Fetching prompts with versions from: {url}")

            async with (
                self.get_client() as client,
                client.get(url, params=params, headers=self._get_auth_headers(token)) as response,
            ):
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Prompts with versions response: {data}")
                return data

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"Prompt management service unavailable: {e!s}")
            return {"data": {"prompts": [], "total": 0}, "message": "Service unavailable", "error": str(e)}
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error fetching prompts with versions: {e.status}, {e.message}")
            return {"data": {"prompts": [], "total": 0}, "message": f"HTTP {e.status}", "error": str(e)}
        except Exception as e:
            logger.error(f"Error fetching prompts with versions: {e!s}")
            return {"data": {"prompts": [], "total": 0}, "message": "", "error": str(e)}

    async def get_prompt_versions(self, prompt_id: str, token: str | None = None) -> dict[str, Any]:
        """Get all versions for a specific prompt."""
        if not self.ready:
            logger.error("Prompt service is not ready")
            return {"data": {"versions": [], "total": 0}, "message": "Service not ready", "error": "Service not initialized"}

        try:
            url = f"{self.settings.PROMPTS_ENDPOINT_URL}/api/v1/prompts/{prompt_id}/versions"

            logger.info(f"Fetching versions for prompt {prompt_id} from: {url}")

            async with (
                self.get_client() as client,
                client.get(url, headers=self._get_auth_headers(token)) as response,
            ):
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Prompt versions response: {data}")
                return data

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"Prompt management service unavailable: {e!s}")
            return {"data": {"versions": [], "total": 0}, "message": "Service unavailable", "error": str(e)}
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error fetching prompt versions: {e.status}, {e.message}")
            return {"data": {"versions": [], "total": 0}, "message": f"HTTP {e.status}", "error": str(e)}
        except Exception as e:
            logger.error(f"Error fetching prompt versions: {e!s}")
            return {"data": {"versions": [], "total": 0}, "message": "", "error": str(e)}

    async def create_prompt(self, prompt_data: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        """Create a new prompt in the Prompt Library."""
        if not self.ready:
            logger.error("Prompt service is not ready")
            return {"data": None, "message": "Service not ready", "error": "Service not initialized"}

        try:
            url = f"{self.settings.PROMPTS_ENDPOINT_URL}/api/v1/prompts/"

            logger.info(f"Creating prompt at: {url}")

            async with (
                self.get_client() as client,
                client.post(url, json=prompt_data, headers=self._get_auth_headers(token)) as response,
            ):
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Create prompt response: {data}")
                return data

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"Prompt management service unavailable: {e!s}")
            return {"data": None, "message": "Service unavailable", "error": str(e)}
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error creating prompt: {e.status}, {e.message}")
            return {"data": None, "message": f"HTTP {e.status}", "error": str(e)}
        except Exception as e:
            logger.error(f"Error creating prompt: {e!s}")
            return {"data": None, "message": "", "error": str(e)}

    async def create_version(self, prompt_id: str, version_data: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        """Create a new version for a prompt."""
        if not self.ready:
            logger.error("Prompt service is not ready")
            return {"data": None, "message": "Service not ready", "error": "Service not initialized"}

        try:
            url = f"{self.settings.PROMPTS_ENDPOINT_URL}/api/v1/prompts/{prompt_id}/versions"

            logger.info(f"Creating version for prompt {prompt_id} at: {url}")

            async with (
                self.get_client() as client,
                client.post(url, json=version_data, headers=self._get_auth_headers(token)) as response,
            ):
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Create version response: {data}")
                return data

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"Prompt management service unavailable: {e!s}")
            return {"data": None, "message": "Service unavailable", "error": str(e)}
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error creating version: {e.status}, {e.message}")
            return {"data": None, "message": f"HTTP {e.status}", "error": str(e)}
        except Exception as e:
            logger.error(f"Error creating version: {e!s}")
            return {"data": None, "message": "", "error": str(e)}

    async def update_version(self, prompt_id: str, version: int, version_data: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        """Update an existing version (only for DRAFT versions)."""
        if not self.ready:
            logger.error("Prompt service is not ready")
            return {"data": None, "message": "Service not ready", "error": "Service not initialized"}

        try:
            url = f"{self.settings.PROMPTS_ENDPOINT_URL}/api/v1/prompts/{prompt_id}/versions/{version}"

            logger.info(f"Updating version {version} for prompt {prompt_id} at: {url}")

            async with (
                self.get_client() as client,
                client.put(url, json=version_data, headers=self._get_auth_headers(token)) as response,
            ):
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Update version response: {data}")
                return data

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"Prompt management service unavailable: {e!s}")
            return {"data": None, "message": "Service unavailable", "error": str(e)}
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error updating version: {e.status}, {e.message}")
            return {"data": None, "message": f"HTTP {e.status}", "error": str(e)}
        except Exception as e:
            logger.error(f"Error updating version: {e!s}")
            return {"data": None, "message": "", "error": str(e)}

    async def submit_for_review(self, prompt_id: str, version: int, token: str | None = None, comment: str | None = None) -> dict[str, Any]:
        """Submit/promote a version to the next stage.
        
        Handles all forward transitions automatically:
        - DRAFT → PUBLISHED (if workflow has 0 approval stages)
        - DRAFT → PENDING_APPROVAL (STAGE_1) (if workflow has approval stages)
        - PENDING_APPROVAL (STAGE_1) → PENDING_APPROVAL (STAGE_2) (if 2-stage workflow)
        - PENDING_APPROVAL (STAGE_2) → PUBLISHED (final approval)
        - REJECTED → DRAFT (revision)
        """
        if not self.ready:
            logger.error("Prompt service is not ready")
            return {"data": None, "message": "Service not ready", "error": "Service not initialized"}

        try:
            url = f"{self.settings.PROMPTS_ENDPOINT_URL}/api/v1/prompts/{prompt_id}/versions/{version}/submit"
            payload = {"comment": comment or ""}

            logger.info(f"Submitting version {version} for prompt {prompt_id} at: {url}")

            async with (
                self.get_client() as client,
                client.post(url, json=payload, headers=self._get_auth_headers(token)) as response,
            ):
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Submit for review response: {data}")
                return data

        except aiohttp.ClientConnectorError as e:
            logger.warning(f"Prompt management service unavailable: {e!s}")
            return {"data": None, "message": "Service unavailable", "error": str(e)}
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error submitting for review: {e.status}, {e.message}")
            return {"data": None, "message": f"HTTP {e.status}", "error": str(e)}
        except Exception as e:
            logger.error(f"Error submitting for review: {e!s}")
            return {"data": None, "message": "", "error": str(e)}
