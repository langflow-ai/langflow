from __future__ import annotations

from typing import Any

from langflow.custom import Component
from langflow.io import DropdownInput, IntInput, MultilineInput, MultiselectInput, Output
from langflow.schema import Data
from loguru import logger


class KnowledgeHubSearchComponent(Component):
    display_name = "Knowledge Hub Search"
    description = (
        "This component is used to search for information in the knowledge hub."
    )
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "Autonomize"
    name = "KnowledgeHubSearch"

    def __init__(self, **kwargs):
        self._hub_data: list[dict[str, str]] = []
        self._selected_hub_names: list[str] = []
        super().__init__(**kwargs)

    async def update_build_config(
        self, build_config: dict, field_value: Any, field_name: str | None = None
    ):
        """Update the build configuration based on field changes."""
        logger.info(f"update_build_config called with field_name: {field_name}")

        if field_name == "selected_hubs":
            try:
                # For now, return some mock options until the service is properly configured
                options = ["Mock Hub 1", "Mock Hub 2", "Mock Hub 3"]
                logger.info(f"Mock hub options: {options}")

                build_config["selected_hubs"]["options"] = options

                if field_value and isinstance(field_value, list):
                    self._selected_hub_names = field_value
                    logger.info(
                        f"Stored selected hub names: {self._selected_hub_names}"
                    )

                return build_config
            except Exception as e:
                logger.exception(f"Error in update_build_config: {e!s}")
                raise
        return build_config

    inputs = [
        MultilineInput(
            name="search_query",
            display_name="Search Query",
            tool_mode=True,
        ),
        MultiselectInput(
            name="selected_hubs",
            display_name="Data Sources",
            value=[],
            refresh_button=True,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["similarity", "semantic", "keyword", "hybrid"],
            value="similarity",
            info="Type of search to perform",
        ),
        IntInput(
            name="top_k",
            display_name="Top K Results",
            value=10,
            info="Number of top results to retrieve",
        ),
    ]

    outputs = [
        Output(
            display_name="Query Results",
            name="query_results",
            method="build_output",
        ),
    ]

    async def build_output(self) -> Data:
        """Generate the output based on selected knowledge hubs."""
        try:
            # Get configuration values
            search_type = getattr(self, 'search_type', 'similarity')
            top_k = getattr(self, 'top_k', 10)

            # For now, return mock results until the service is properly configured
            query_results = [
                {
                    "metadata": {
                        "content": f"Mock search result for query: {self.search_query} (type: {search_type}, top_k: {top_k})"
                    }
                }
            ]

            logger.info(f"Mock query results with search_type={search_type}, top_k={top_k}: {query_results}")

            plain_text = f"Mock search result content (search_type: {search_type}, top_k: {top_k})"

            data = Data(
                text=plain_text,
                data={
                    "result": query_results,
                    "used_data_sources": self._selected_hub_names,
                    "search_type": search_type,
                    "top_k": top_k,
                },
            )
            self.status = data
            return data

        except Exception as e:
            logger.error(f"Error in build_output: {e!s}")
            return Data(value={"query_results": []})