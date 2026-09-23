import re
from typing import Any

from mem0 import MemoryClient

from langflow.custom import Component
from langflow.io import (
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from langflow.schema import DataFrame


class GetMemoriesComponent(Component):
    """Component for retrieving memories in Mem0."""

    display_name = "Get Memories"
    description = "Retrieve memories from Mem0 using advanced filtering capabilities."
    icon: str = "Mem0"
    name = "GetMemories"
    documentation = "https://docs.mem0.com/"

    inputs = [
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
            name="limit",
            display_name="Limit",
            info="Maximum number of memories to retrieve.",
            value=100,
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
            info="Retrieved memories as a DataFrame.",
            method="get_memories_response",
            type="DataFrame",
        ),
    ]

    def validate_inputs(self):
        if not self.api_key:
            error_message = "API Key is required."
            raise ValueError(error_message)

        # Validate date formats
        date_format = r"^\d{4}-\d{2}-\d{2}$"  # YYYY-MM-DD format

        if self.created_at_gte and not re.match(date_format, self.created_at_gte):
            error_message = f"Created After date must be in YYYY-MM-DD format. Got: {self.created_at_gte}"
            raise ValueError(error_message)

        if self.created_at_lte and not re.match(date_format, self.created_at_lte):
            error_message = f"Created Before date must be in YYYY-MM-DD format. Got: {self.created_at_lte}"
            raise ValueError(error_message)

    def build_filters(self) -> dict[str, Any]:
        filters = {}

        if self.mem0_user_id:
            filters["user_id"] = self.mem0_user_id

        if self.app_id:
            filters["app_id"] = self.app_id

        if self.run_id:
            filters["run_id"] = self.run_id

        if self.agent_ids:
            agent_list = [agent_id.strip() for agent_id in self.agent_ids.split(",") if agent_id.strip()]
            if agent_list:
                filters["agent_id"] = {"in": agent_list}

        if self.created_at_gte or self.created_at_lte:
            date_filter = {}
            if self.created_at_gte:
                date_filter["gte"] = self.created_at_gte
            if self.created_at_lte:
                date_filter["lte"] = self.created_at_lte
            filters["created_at"] = date_filter

        return filters

    def get_memories_response(self) -> DataFrame:
        """Retrieve memories based on the provided filters."""
        try:
            self.validate_inputs()
            client = MemoryClient(api_key=self.api_key)

            filters = self.build_filters()
            self.log(f"Retrieving memories with filters: {filters}")

            memories = client.get_all(filters=filters, version="v2")
            self.log(f"Memories retrieved: {memories}")

            if memories:
                memories_df = DataFrame(data=memories)
                self.status = memories_df
                return memories_df
            error_message = "No memories found."
            error_data = {"error": error_message}
            error_df = DataFrame(data=[error_data])
            self.status = error_df
        except (ValueError, RuntimeError) as e:
            error_message = f"Error: {e!s}"
            error_data = {"error": error_message}
            error_df = DataFrame(data=[error_data])
            self.status = error_df
        return self.status
