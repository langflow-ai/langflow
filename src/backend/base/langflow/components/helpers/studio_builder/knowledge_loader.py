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
        """Load ALL components directly from internal service - no HTTP, no auth needed!"""
        try:
            from langflow.services.spec.service import SpecService
            import concurrent.futures

            # Create service instance
            service = SpecService()

            # Use the internal service method directly - no HTTP call needed!
            async def _get_all_components():
                return await service.get_all_available_components()

            # Handle async execution properly
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we're in an existing loop, run in thread pool
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    components_data = pool.submit(asyncio.run, _get_all_components()).result()
            except RuntimeError:
                # No running loop, we can use asyncio.run directly
                components_data = asyncio.run(_get_all_components())

            # Process the knowledge based on query_type
            if self.query_type == "components" or self.query_type == "all":
                # Return comprehensive component information
                knowledge = {
                    "all_components": components_data.get("langflow_components", {}),
                    "genesis_mapped": components_data.get("genesis_mapped", {}),
                    "unmapped": components_data.get("unmapped", []),
                    "valid_genesis_types": list(components_data.get("genesis_mapped", {}).keys())
                }

                # Add a helpful summary
                if components_data.get("langflow_components"):
                    total_components = sum(
                        len(comps)
                        for category in components_data["langflow_components"].get("components", {}).values()
                        for comps in [category] if isinstance(category, dict)
                    )
                    knowledge["summary"] = {
                        "total_langflow_components": total_components,
                        "genesis_mapped_count": len(components_data.get("genesis_mapped", {})),
                        "unmapped_count": len(components_data.get("unmapped", []))
                    }
            else:
                # For backward compatibility, still support API calls for other query types
                async def _fetch_knowledge():
                    async with SpecAPIClient() as client:
                        return await client.get_knowledge(
                            query_type=self.query_type,
                            reload_cache=self.reload_cache
                        )

                try:
                    loop = asyncio.get_running_loop()
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        knowledge = pool.submit(asyncio.run, _fetch_knowledge()).result()
                except RuntimeError:
                    knowledge = asyncio.run(_fetch_knowledge())

            return Data(data={
                "success": True,
                "knowledge": knowledge,
                "message": f"Loaded {self.query_type} knowledge successfully"
            })

        except Exception as e:
            logger.error(f"Error loading knowledge: {e}")
            return Data(data={
                "success": False,
                "error": str(e),
                "message": f"Failed to load knowledge: {str(e)}"
            })

