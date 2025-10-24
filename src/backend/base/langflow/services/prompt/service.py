"""Prompt service for Genesis Studio."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional

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
        self._ready = True
        self._prompts: Dict[str, Dict[str, Any]] = {}

    def set_ready(self) -> None:
        """Set the service as ready."""
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if the service is ready."""
        return self._ready

    async def cleanup(self) -> None:
        """Cleanup resources."""
        pass

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
        """Get prompts based on criteria."""
        criteria = criteria or {"max_results": 100}
        # Mock implementation for now
        logger.debug(f"Mock get_prompts with criteria: {criteria}")
        return {"prompts": [], "total": 0}

    async def create_prompt(self, prompt_data):
        """Create a new prompt."""
        # Mock implementation for now
        logger.debug(f"Mock create_prompt with data: {prompt_data}")
        return {"id": "mock_prompt_id", "status": "created"}

    async def create_prompt_version(self, prompt_name, prompt_data):
        """Create a new version of a prompt."""
        # Mock implementation for now
        logger.debug(f"Mock create_prompt_version for {prompt_name}")
        return {"version": "1.0", "status": "created"}

    async def delete_prompt(self, prompt_name):
        """Delete a prompt."""
        # Mock implementation for now
        logger.debug(f"Mock delete_prompt: {prompt_name}")
        return {"status": "deleted"}

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
            logger.debug(f"Formatted prompt templates: {templates}")
            return templates
        except Exception as e:
            logger.error(f"Error formatting prompt: {e!s}")
            return None

    def clean_braces(self, match):
        """Clean up brace formatting in templates."""
        return "{" + match.group(1).strip() + "}"

    def format_prompt_template(self, template: str, variables: dict) -> str:
        """Format a prompt template with variables."""
        # Convert double braces {{var}} to single-brace {var} for str.format()
        safe_template = re.sub(r"{{(.*?)}}", self.clean_braces, template)
        try:
            return safe_template.format(**variables)
        except KeyError as e:
            raise ValueError(f"Missing value for variable: {e}")