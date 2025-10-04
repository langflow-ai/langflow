"""RAG service for Genesis Studio."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from loguru import logger

from langflow.services.base import Service

from .settings import RAGSettings


class RAGService(Service):
    """Service for managing RAG QnA interactions."""

    name = "rag_service"

    def __init__(self):
        super().__init__()
        self.settings = RAGSettings()
        self._http_client: aiohttp.ClientSession | None = None

    @property
    def http_client(self) -> aiohttp.ClientSession:
        if not self._http_client or self._http_client.closed:
            self._http_client = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.settings.TIMEOUT),
                headers={"User-Agent": self.settings.USER_AGENT},
            )
        return self._http_client

    async def cleanup(self) -> None:
        if self._http_client and not self._http_client.closed:
            await self._http_client.close()
            self._http_client = None
            logger.debug("RAG QnA HTTP client closed")

    @asynccontextmanager
    async def get_client(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        try:
            yield self.http_client
        finally:
            pass

    async def get_prompt_answer(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Get answer for a prompt."""
        try:
            url = f"{self.settings.BASE_URL}/prompt-qa"

            async with self.get_client() as client:
                async with client.post(
                    url, headers={"accept": "application/json"}, json=payload
                ) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            logger.error(f"Error in get_prompt_answer: {e!s}")
            raise

    async def get_query_summarization(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Get query summarization."""
        try:
            url = f"{self.settings.BASE_URL}/query-summarization"

            async with self.get_client() as client:
                async with client.post(
                    url, headers={"accept": "application/json"}, json=payload
                ) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            logger.error(f"Error in get_query_summarization: {e!s}")
            raise

    async def generate_guideline_adjudication_summary(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate guideline adjudication summary."""
        try:
            url = f"{self.settings.V2_BASE_URL}/guidelines/adjudicate"

            async with self.get_client() as client:
                async with client.post(
                    url, headers={"accept": "application/json"}, json=payload
                ) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            logger.error(f"Error in generate_guideline_adjudication_summary: {e!s}")
            raise
