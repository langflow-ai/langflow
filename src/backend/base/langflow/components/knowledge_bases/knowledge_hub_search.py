from __future__ import annotations

from typing import Any

from langflow.custom import Component
from langflow.inputs.inputs import DictInput
from langflow.services.deps import get_knowledge_service
from langflow.io import DropdownInput, IntInput, MultilineInput, MultiselectInput, Output
from langflow.schema import Data
from loguru import logger

# Import the service and factory directly
from langflow.services.knowledge.factory import KnowledgeServiceFactory
from langflow.services.knowledge.service import KnowledgeService


class KnowledgeHubSearchComponent(Component):
    display_name = "Knowledge Hub"
    description = (
        "This component is used to search for information in the knowledge hub."
    )
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "Autonomize"
    name = "KnowledgeHubSearch"

    inputs = [
        MultilineInput(
            name="search_query",
            display_name="Search Query",
            tool_mode=True,
        ),
        DropdownInput(
            name="selected_hubs",
            display_name="Data Sources",
            value=[],
            refresh_button=True,
        ),
        DictInput(
            name="filters",
            display_name="Filter on metadata",
            info="filter on metadata",
            show=True,
            value={},
            is_list=True,
            tool_mode=True
        )
    ]

    outputs = [
        Output(
            display_name="Query Results",
            name="query_results",
            method="build_output",
        ),
    ]

    def __init__(self, **kwargs):
        self._hub_data: list[dict[str, str]] = []
        self._selected_hub_names: list[str] = []  # Track selected hub names
        self._knowledge_service: KnowledgeService | None = None  # Cache the service instance
        super().__init__(**kwargs)

    def _get_knowledge_service(self) -> KnowledgeService:
        """Get or create the knowledge service instance."""
        if self._knowledge_service is None:
            factory = KnowledgeServiceFactory()
            self._knowledge_service = factory.create()
        return self._knowledge_service

    async def update_build_config(
        self, build_config: dict, field_value: Any, field_name: str | None = None
    ):
        """Update the build configuration based on field changes."""
        logger.info(f"update_build_config called with field_name: {field_name}")

        if field_name == "selected_hubs":
            try:
                # Get the knowledge service directly
                service = self._get_knowledge_service()
                if not service.ready:
                    logger.error("KnowledgeHub service is not ready")
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
                    logger.info(f"Stored selected hub names: {self._selected_hub_names}")

                # Debug the build_config after update
                logger.info(
                    f"Build config after update: {build_config.get('selected_hubs', {})}"
                )

                return build_config
            except Exception as e:
                logger.exception(f"Error in update_build_config: {e!s}")
                raise
        return build_config


    async def _validate_and_refresh_data_sources(self) -> tuple[bool, list[str]]:
        """Validate that the selected data sources are still available, if not fetch and update them"""
        if not self._selected_hub_names:
            logger.info("No data sources selected, validation skipped")
            return True, []
            
        try:
            # Get the knowledge service directly
            service = self._get_knowledge_service()
            if not service.ready:
                logger.error("KnowledgeHub service is not ready for validation")
                return True, self._selected_hub_names  # Return original selection if service not ready
                
            fresh_hub_data = await service.get_knowledge_hubs()
            available_names = [hub["name"] for hub in fresh_hub_data]
            
            logger.info(f"Available data sources: {available_names}")
            logger.info(f"Selected data sources: {self._selected_hub_names}")
            
            # Check which selected hubs are still available
            still_available = []
            missing_hubs = []
            refreshed_hubs = []
            
            for selected_name in self._selected_hub_names:
                if selected_name in available_names:
                    still_available.append(selected_name)
                    logger.info(f"Data source '{selected_name}' is still available")
                else:
                    missing_hubs.append(selected_name)
                    logger.warning(f"Data source '{selected_name}' is no longer available")
            
            # Try to find missing hubs in fresh data (in case of name changes or refresh issues)
            for missing_name in missing_hubs:
                # Look for exact match first
                found_hub = next(
                    (hub for hub in fresh_hub_data if hub["name"] == missing_name), None
                )
                
                if found_hub:
                    still_available.append(found_hub["name"])
                    refreshed_hubs.append(found_hub["name"])
                    logger.info(f"Refreshed data source '{missing_name}' found and re-added")
                else:
                    # Try partial match (in case of minor name changes)
                    partial_matches = [
                        hub["name"] for hub in fresh_hub_data 
                        if missing_name.lower() in hub["name"].lower() or hub["name"].lower() in missing_name.lower()
                    ]
                    
                    if partial_matches:
                        logger.info(f"Possible matches for missing '{missing_name}': {partial_matches}")
                        # For now, don't auto-select partial matches, just log them
                    else:
                        logger.error(f"Data source '{missing_name}' not found even after refresh")
            
            # Update the hub data cache
            self._hub_data = fresh_hub_data
            
            # Update selected hub names to only include available ones
            self._selected_hub_names = still_available
            
            if refreshed_hubs:
                logger.info(f"Successfully refreshed data sources: {refreshed_hubs}")
            
            if missing_hubs and not refreshed_hubs:
                logger.warning(f"Some data sources are no longer available: {[h for h in missing_hubs if h not in refreshed_hubs]}")
                return False, still_available
            
            return True, still_available
                
        except Exception as e:
            logger.error(f"Error validating/refreshing data sources: {e}")
            logger.exception("Full error details:")
            # If we can't validate, return original selection to avoid breaking the flow
            return True, self._selected_hub_names

    async def build_output(self) -> Data:
        """Generate the output based on selected knowledge hubs."""
        try:
            # Validate and refresh data sources if needed
            if self._selected_hub_names:
                is_valid, validated_hubs = await self._validate_and_refresh_data_sources()
                
                if not is_valid and not validated_hubs:
                    error_message = f"Error: Selected data sources are no longer available. Please select different data sources."
                    logger.error(error_message)
                    return Data(
                        text=error_message,
                        data={"error": error_message, "query_results": []}
                    )
                
                # Use validated hubs instead of self.selected_hubs
                effective_selected_hubs = validated_hubs
            else:
                effective_selected_hubs = self.selected_hubs if hasattr(self, 'selected_hubs') else []

            if not effective_selected_hubs:
                logger.warning("No knowledge hubs selected or available.")
                return Data(value={"query_results": []})

            # Make sure we have hub data
            if not self._hub_data:
                service = self._get_knowledge_service()
                if not service.ready:
                    logger.error("KnowledgeHub service is not ready")
                    return Data(value={"query_results": []})
                self._hub_data = await service.get_knowledge_hubs()

            # Map the selected names to their IDs
            selected_hub_ids = [
                hub["id"] for hub in self._hub_data if hub["name"] in effective_selected_hubs
            ]

            logger.info(f"Using data sources: {effective_selected_hubs}")
            logger.info(f"Mapped to hub IDs: {selected_hub_ids}")

            service = self._get_knowledge_service()
            if not service.ready:
                logger.error("KnowledgeHub service is not ready")
                return Data(value={"query_results": []})
            
            query_results = await service.query_vector_store(
                knowledge_hub_ids=selected_hub_ids, query=self.search_query, filters=self.filters
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

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        if self._knowledge_service:
            await self._knowledge_service.cleanup()
            self._knowledge_service = None
