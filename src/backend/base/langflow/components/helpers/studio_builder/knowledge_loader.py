"""Knowledge Loader for AI Studio Agent Builder - Loads valid components and patterns."""

import asyncio
from typing import Any
from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput, BoolInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger
from langflow.components.helpers.studio_builder.api_client import SpecAPIClient


class KnowledgeLoader(Component):
    """Loads and provides available genesis components, patterns, and specifications."""

    display_name = "Knowledge Loader"
    description = "Loads valid components, patterns, and specifications from the library via API"
    icon = "book-open"
    name = "KnowledgeLoader"
    category = "Helpers"

    inputs = [
        MessageTextInput(
            name="query_type",
            display_name="Query Type",
            info="Type of knowledge to load: components, patterns, specifications, or all",
            value="all",
            tool_mode=True,
        ),
        BoolInput(
            name="reload_cache",
            display_name="Reload Cache",
            info="Force reload from disk",
            value=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Knowledge Data", name="knowledge", method="load_knowledge"),
    ]

    def load_knowledge(self) -> Data:
        """Load requested knowledge from the library via API."""
        try:
            # Use asyncio to run the async API call
            async def _fetch_knowledge():
                async with SpecAPIClient() as client:
                    return await client.get_knowledge(
                        query_type=self.query_type,
                        reload_cache=self.reload_cache
                    )

            # Run the async function - handle existing event loop
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we're in an existing loop, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    knowledge = pool.submit(asyncio.run, _fetch_knowledge()).result()
            except RuntimeError:
                # No running loop, we can use asyncio.run directly
                knowledge = asyncio.run(_fetch_knowledge())

            return Data(data={
                "success": True,
                "knowledge": knowledge,
                "message": f"Loaded {self.query_type} knowledge successfully"
            })

        except Exception as e:
            logger.error(f"Error loading knowledge from API: {e}")
            return Data(data={
                "success": False,
                "error": str(e),
                "message": f"Failed to load knowledge: {str(e)}"
            })

