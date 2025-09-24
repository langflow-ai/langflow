"""Prompt service for Genesis Studio."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional

from langflow.services.base import Service
from loguru import logger
from modelhub.clients import PromptClient
from modelhub.core import ModelhubCredential

from .settings import PromptSettings

# from langflow.models.prompt import Prompt


class PromptService(Service):
    """Service for managing prompts."""

    name = "prompt_service"

    def __init__(self):
        """Initialize the prompt service."""
        super().__init__()
        self.settings = PromptSettings()
        self._ready = True
        self._prompts: Dict[str, Dict[str, Any]] = {}
        self.credential = ModelhubCredential()
        self.prompt_client = PromptClient(credential=self.credential)

    def set_ready(self) -> None:
        """Set the service as ready."""
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if the service is ready."""
        return self._ready

    async def cleanup(self) -> None:
        """Cleanup resources."""

    async def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get a prompt by ID."""
        try:
            return self._prompts.get(prompt_id)
        except Exception as e:
            logger.error(f"Error getting prompt: {e!s}")
            return None

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List all prompts."""
        try:
            return list(self._prompts.values())
        except Exception as e:
            logger.error(f"Error listing prompts: {e!s}")
            return []

    async def get_prompts(self, criteria=None):
        criteria = criteria or {"max_results": 100}
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.prompt_client.get_prompts, criteria
        )

    async def create_prompt(self, prompt_data):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.prompt_client.create_prompt, prompt_data
        )

    async def create_prompt_version(self, prompt_name, prompt_data):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.prompt_client.create_prompt_version, prompt_name, prompt_data
        )

    async def delete_prompt(self, prompt_name):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.prompt_client.delete_prompt, prompt_name
        )

    async def format_prompt(self, prompt_id: str, **kwargs) -> Optional[str]:
        """Format a prompt with the given parameters."""
        try:
            prompt = await self.get_prompt(prompt_id)
            if not prompt:
                return None
            templates = []
            for template in prompt.get("template", []):
                role = template["role"]
                content = self.format_prompt_template(
                    template["content"]["text"], kwargs
                )
                templates.append({"role": role, "content": content})
            print("gere", templates)
            return templates
        except Exception as e:
            logger.error(f"Error formatting prompt: {e!s}")
            return None

    def clean_braces(self, match):
        return "{" + match.group(1).strip() + "}"

    def format_prompt_template(self, template: str, variables: dict) -> str:
        # Convert double braces {{var}} to single-brace {var} for str.format()
        safe_template = re.sub(r"{{(.*?)}}", self.clean_braces, template)
        try:
            return safe_template.format(**variables)
        except KeyError as e:
            raise ValueError(f"Missing value for variable: {e}")
