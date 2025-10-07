from __future__ import annotations

from typing import Any

from langflow.custom import Component
from langflow.custom.genesis.services.deps import get_knowledge_service
from langflow.io import DropdownInput, IntInput, MultilineInput, MultiselectInput, Output
from langflow.schema import Data
from loguru import logger


class KnowledgeHubSearchComponent(Component):
    display_name = "Knowledge Hub Search"
    description = (
        "This component is used to search for information in the knowledge hub."
    )
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
                # Load the hub options when the field is refreshed
                service = get_knowledge_service()
                if not service.ready:
                    logger.error("KnowledgeHub service is not ready")
                    build_config["selected_hubs"]["options"] = ["Service not ready"]
                    return build_config

                self._hub_data = await service.get_knowledge_hubs()

                # Debug the raw response
                logger.info(f"Raw hub data: {self._hub_data}")

                options = [hub["name"] for hub in self._hub_data]
                logger.info(f"Extracted hub options: {options}")

                # Debug the build_config before update
                logger.info(
                    f"Build config before update: {build_config.get('selected_hubs', {})}"
                )

                build_config["selected_hubs"]["options"] = options

                # Store selected hub names for validation during build
                if field_value and isinstance(field_value, list):
                    self._selected_hub_names = field_value
                    logger.info(
                        f"Stored selected hub names: {self._selected_hub_names}"
                    )

                # Debug the build_config after update
                logger.info(
                    f"Build config after update: {build_config.get('selected_hubs', {})}"
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
            # Validate and refresh data sources if needed
            if self._selected_hub_names:
                is_valid, validated_hubs = (
                    await self._validate_and_refresh_data_sources()
                )

                if not is_valid and not validated_hubs:
                    error_message = f"Error: Selected data sources are no longer available. Please select different data sources."
                    logger.error(error_message)
                    return Data(
                        text=error_message,
                        data={"error": error_message, "query_results": []},
                    )

                # Use validated hubs instead of self.selected_hubs
                effective_selected_hubs = validated_hubs
            else:
                effective_selected_hubs = (
                    self.selected_hubs if hasattr(self, "selected_hubs") else []
                )

            if not effective_selected_hubs:
                logger.warning("No knowledge hubs selected or available.")
                return Data(value={"query_results": []})

            # Make sure we have hub data
            if not self._hub_data:
                service = get_knowledge_service()
                if not service.ready:
                    logger.error("KnowledgeHub service is not ready")
                    return Data(value={"query_results": []})
                self._hub_data = await service.get_knowledge_hubs()

            # Map the selected names to their IDs
            selected_hub_ids = [
                hub["id"]
                for hub in self._hub_data
                if hub["name"] in effective_selected_hubs
            ]

            logger.info(f"Using data sources: {effective_selected_hubs}")
            logger.info(f"Mapped to hub IDs: {selected_hub_ids}")

            service = get_knowledge_service()
            if not service.ready:
                logger.error("KnowledgeHub service is not ready")
                return Data(value={"query_results": []})

            query_results = await service.query_vector_store(
                knowledge_hub_ids=selected_hub_ids, query=self.search_query
            )
            logger.debug(f"query_results: {query_results}")

            # Concatenate content from query results
            contents = [
                result.get("metadata", {}).get("content", "")
                for result in query_results
            ]
            plain_text = "\n\n=== NEW CHUNK ===\n\n".join(contents)

            data = Data(
                text=plain_text,
                data={
                    "result": query_results,
                    "used_data_sources": effective_selected_hubs,  # Include which sources were actually used
                },
            )
            self.status = data
            return data

        except Exception as e:
            logger.error(f"Error in build_output: {e!s}")
            return Data(value={"query_results": []})