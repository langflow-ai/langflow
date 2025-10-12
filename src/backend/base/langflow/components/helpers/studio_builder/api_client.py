"""API Client for Studio Builder components to call backend spec endpoints."""

import os
from typing import Any, Dict, Optional

import httpx

from langflow.logging import logger


class SpecAPIClient:
    """Client for accessing Spec API endpoints from components."""

    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        """Initialize the API client.

        Args:
            base_url: Base URL for the API. Defaults to environment variable or localhost.
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url or os.getenv("LANGFLOW_API_URL", "http://localhost:7860")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_knowledge(
        self,
        query_type: str = "all",
        reload_cache: bool = False
    ) -> Dict[str, Any]:
        """Get available components, patterns, and specifications.

        Args:
            query_type: Type of knowledge to retrieve (components, patterns, specifications, or all).
            reload_cache: Whether to force reload from disk.

        Returns:
            Dictionary containing knowledge data.

        Raises:
            Exception: If the API call fails.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/spec/knowledge",
                json={
                    "query_type": query_type,
                    "reload_cache": reload_cache
                }
            )
            response.raise_for_status()
            result = response.json()

            if not result.get("success", False):
                raise Exception(f"Knowledge API failed: {result.get('message', 'Unknown error')}")

            return result.get("knowledge", {})

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting knowledge: {e}")
            raise Exception(f"Failed to get knowledge from API: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error getting knowledge: {e}")
            raise

    async def validate_spec(self, spec_yaml: str) -> Dict[str, Any]:
        """Validate a specification YAML.

        Args:
            spec_yaml: YAML specification string to validate.

        Returns:
            Dictionary with validation results (valid, errors, warnings).

        Raises:
            Exception: If the API call fails.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/spec/validate",
                json={"spec_yaml": spec_yaml}
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error validating spec: {e}")
            raise Exception(f"Failed to validate spec via API: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error validating spec: {e}")
            raise

    async def get_available_components(self) -> Dict[str, Any]:
        """Get list of available components with their configurations.

        Returns:
            Dictionary of available components.

        Raises:
            Exception: If the API call fails.
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/v1/spec/components")
            response.raise_for_status()
            result = response.json()
            return result.get("components", {})

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting components: {e}")
            raise Exception(f"Failed to get components from API: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error getting components: {e}")
            raise

    async def get_component_mapping(self, spec_type: str) -> Dict[str, Any]:
        """Get mapping information for a specification component type.

        Args:
            spec_type: The specification component type.

        Returns:
            Dictionary with mapping information.

        Raises:
            Exception: If the API call fails.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/spec/component-mapping",
                json={"spec_type": spec_type}
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting component mapping: {e}")
            raise Exception(f"Failed to get component mapping from API: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error getting component mapping: {e}")
            raise

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()