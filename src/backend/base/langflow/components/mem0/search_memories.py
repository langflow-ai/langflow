import re

import httpx
from loguru import logger

from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from langflow.schema import Data, DataFrame


class SearchMemoriesComponent(Component):
    """Component for searching memories in Mem0."""

    display_name = "Search Memories"
    description = "Search memories in Mem0 based on a query and filters with support for complex logical operations."
    icon: str = "Mem0"
    name = "SearchMemories"
    documentation = "https://docs.mem0.com/"

    DEFAULT_TOP_K = 5
    HTTP_STATUS_OK = 200

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The search query to use.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="mem0_user_id",
            display_name="User ID",
            info="Filter by user ID.",
            tool_mode=True,
        ),
        MultilineInput(
            name="agent_ids",
            display_name="Agent IDs",
            info="Comma-separated list of agent IDs to filter by.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="app_id",
            display_name="App ID",
            info="Filter by app ID.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="run_id",
            display_name="Run ID",
            info="Filter by run ID.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="created_at_gte",
            display_name="Created After (YYYY-MM-DD)",
            info="Filter memories created on or after this date.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="created_at_lte",
            display_name="Created Before (YYYY-MM-DD)",
            info="Filter memories created on or before this date.",
            advanced=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="logic_operator",
            display_name="Logic Operator",
            options=["AND", "OR"],
            value="AND",
            info="The logical operator to combine filters.",
            advanced=True,
            tool_mode=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K Results",
            info="The number of top results to return.",
            value=DEFAULT_TOP_K,
            advanced=True,
            tool_mode=True,
        ),
        BoolInput(
            name="rerank",
            display_name="Rerank",
            info="Whether to rerank the search results.",
            advanced=True,
            tool_mode=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Your Mem0 API Key.",
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Result",
            info="Search results as a DataFrame.",
            method="search_memories_response",
            type="DataFrame",
        ),
    ]

    def validate_inputs(self):
        logger.info("Validating inputs")
        if not self.query:
            logger.error("Search query is missing")
            error_message = "Search query is required."
            raise ValueError(error_message)
        if not self.api_key:
            logger.error("API key is missing")
            error_message = "API Key is required."
            raise ValueError(error_message)

        # Add date format validation
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        if self.created_at_gte and not date_pattern.match(self.created_at_gte):
            logger.error("Invalid date format for 'Created After' field")
            error_message = "Invalid date format for 'Created After' field. Please use YYYY-MM-DD."
            raise ValueError(error_message)
        if self.created_at_lte and not date_pattern.match(self.created_at_lte):
            logger.error("Invalid date format for 'Created Before' field")
            error_message = "Invalid date format for 'Created Before' field. Please use YYYY-MM-DD."
            raise ValueError(error_message)

        logger.success("Input validation successful")

    def build_filters(self):
        logger.info("Building filters")
        filters = {}

        # Basic filters
        if self.mem0_user_id:
            filters["user_id"] = self.mem0_user_id

        if self.app_id:
            filters["app_id"] = self.app_id

        if self.run_id:
            filters["run_id"] = self.run_id

        # Handle multiple agent IDs with IN operator
        if self.agent_ids:
            agent_list = [agent_id.strip() for agent_id in self.agent_ids.split(",") if agent_id.strip()]
            if agent_list:
                filters["agent_id"] = {"in": agent_list}

        # Date range filters
        if self.created_at_gte or self.created_at_lte:
            date_filter = {}
            if self.created_at_gte:
                date_filter["gte"] = self.created_at_gte
            if self.created_at_lte:
                date_filter["lte"] = self.created_at_lte
            filters["created_at"] = date_filter

        return filters

    def search_memories_response(self) -> DataFrame:
        """Build and execute the search operation."""
        try:
            self.validate_inputs()

            url = "https://api.mem0.ai/v2/memories/search/"
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            payload = {
                "query": self.query,
                "filters": self.build_filters(),
                "top_k": self.top_k,
                "rerank": self.rerank,
            }

            logger.info("Sending API request")
            with httpx.Client() as client:
                response = client.post(url, json=payload, headers=headers)

            logger.info(f"Received response with status code: {response.status_code}")

            if response.status_code == self.HTTP_STATUS_OK:
                result = response.json()

                memories_data = []
                for memory in result:
                    memory_data = Data(
                        text=memory.get("memory", ""),  # Use 'memory' field as the text content
                        data={
                            "memory_id": memory.get("id"),
                            "agent_id": memory.get("agent_id"),
                            "user_id": memory.get("user_id"),
                            "app_id": memory.get("app_id"),
                            "session_id": memory.get("session_id"),
                            "hash": memory.get("hash"),
                            "metadata": memory.get("metadata"),
                            "categories": memory.get("categories", []),
                            "created_at": memory.get("created_at"),
                            "updated_at": memory.get("updated_at"),
                            "score": memory.get("score"),
                        },
                    )
                    memories_data.append(memory_data)

                logger.success(f"Successfully retrieved {len(memories_data)} search results")
                self.status = memories_data
                return DataFrame(memories_data)

            error_message = f"Error: {response.text}"
            error_data = Data(
                text=error_message,
                data={"error": {"status_code": response.status_code, "message": response.text, "query": self.query}},
            )
            logger.error(f"API request failed: {error_data.data}")
            self.status = [error_data]
            return DataFrame([error_data])

        except (ValueError, KeyError, TypeError, httpx.HTTPStatusError) as e:
            error_message = f"Error: {e!s}"
            error_data = Data(
                text=error_message, data={"error": {"type": type(e).__name__, "message": str(e), "query": self.query}}
            )
            logger.exception(f"Exception occurred during API request: {e!s}")
            self.status = [error_data]
            return DataFrame([error_data])
