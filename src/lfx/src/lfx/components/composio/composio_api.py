# Standard library imports
from collections.abc import Sequence
from typing import Any

from composio import Composio
from composio_langchain import LangchainProvider

# Third-party imports
from langchain_core.tools import Tool

# Local imports
from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.inputs.inputs import (
    ConnectionInput,
    MessageTextInput,
    SecretStrInput,
    SortableListInput,
)
from lfx.io import Output

# TODO: We get the list from the API but we need to filter it
enabled_tools = ["confluence", "discord", "dropbox", "github", "gmail", "linkedin", "notion", "slack", "youtube"]


class ComposioAPIComponent(LCToolComponent):
    display_name: str = "Composio Tools"
    description: str = "Use Composio toolset to run actions with your agent"
    name = "ComposioAPI"
    icon = "Composio"
    documentation: str = "https://docs.composio.dev"

    inputs = [
        # Basic configuration inputs
        MessageTextInput(name="entity_id", display_name="Entity ID", value="default", advanced=True),
        SecretStrInput(
            name="api_key",
            display_name="Composio API Key",
            required=True,
            info="Refer to https://docs.composio.dev/faq/api_key/api_key",
            real_time_refresh=True,
        ),
        ConnectionInput(
            name="tool_name",
            display_name="Tool Name",
            placeholder="Select a tool...",
            button_metadata={"icon": "unplug", "variant": "destructive"},
            options=[],
            search_category=[],
            value="",
            connection_link="",
            info="The name of the tool to use",
            real_time_refresh=True,
        ),
        SortableListInput(
            name="actions",
            display_name="Actions",
            placeholder="Select action",
            helper_text="Please connect before selecting actions.",
            helper_text_metadata={"icon": "OctagonAlert", "variant": "destructive"},
            options=[],
            value="",
            info="The actions to use",
            limit=1,
            show=False,
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_tool"),
    ]

    def validate_tool(self, build_config: dict, field_value: Any, tool_name: str | None = None) -> dict:
        # Get the index of the selected tool in the list of options
        selected_tool_index = next(
            (
                ind
                for ind, tool in enumerate(build_config["tool_name"]["options"])
                if tool["name"] == field_value
                or ("validate" in field_value and tool["name"] == field_value["validate"])
            ),
            None,
        )

        # Set the link to be the text 'validated'
        build_config["tool_name"]["options"][selected_tool_index]["link"] = "validated"

        # Set the helper text and helper text metadata field of the actions now
        build_config["actions"]["helper_text"] = ""
        build_config["actions"]["helper_text_metadata"] = {"icon": "Check", "variant": "success"}

        try:
            composio = self._build_wrapper()
            current_tool = tool_name or getattr(self, "tool_name", None)
            if not current_tool:
                self.log("No tool name available for validate_tool")
                return build_config

            toolkit_slug = current_tool.lower()

            tools = composio.tools.get(user_id=self.entity_id, toolkits=[toolkit_slug])

            authenticated_actions = []
            for tool in tools:
                if hasattr(tool, "name"):
                    action_name = tool.name
                    display_name = action_name.replace("_", " ").title()
                    authenticated_actions.append({"name": action_name, "display_name": display_name})
        except (ValueError, ConnectionError, AttributeError) as e:
            self.log(f"Error getting actions for {current_tool or 'unknown tool'}: {e}")
            authenticated_actions = []

        build_config["actions"]["options"] = [
            {
                "name": action["name"],
            }
            for action in authenticated_actions
        ]

        build_config["actions"]["show"] = True
        return build_config

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name == "api_key" or (self.api_key and not build_config["tool_name"]["options"]):
            if field_name == "api_key" and not field_value:
                build_config["tool_name"]["options"] = []
                build_config["tool_name"]["value"] = ""

                # Reset the list of actions
                build_config["actions"]["show"] = False
                build_config["actions"]["options"] = []
                build_config["actions"]["value"] = ""

                return build_config

            # Build the list of available tools
            build_config["tool_name"]["options"] = [
                {
                    "name": app.title(),
                    "icon": app,
                    "link": (
                        build_config["tool_name"]["options"][ind]["link"]
                        if build_config["tool_name"]["options"]
                        else ""
                    ),
                }
                for ind, app in enumerate(enabled_tools)
            ]

            return build_config

        if field_name == "tool_name" and field_value:
            composio = self._build_wrapper()

            current_tool_name = (
                field_value
                if isinstance(field_value, str)
                else field_value.get("validate")
                if isinstance(field_value, dict) and "validate" in field_value
                else getattr(self, "tool_name", None)
            )

            if not current_tool_name:
                self.log("No tool name available for connection check")
                return build_config

            try:
                toolkit_slug = current_tool_name.lower()

                connection_list = composio.connected_accounts.list(
                    user_ids=[self.entity_id], toolkit_slugs=[toolkit_slug]
                )

                # Check for active connections
                has_active_connections = False
                if (
                    connection_list
                    and hasattr(connection_list, "items")
                    and connection_list.items
                    and isinstance(connection_list.items, list)
                    and len(connection_list.items) > 0
                ):
                    for connection in connection_list.items:
                        if getattr(connection, "status", None) == "ACTIVE":
                            has_active_connections = True
                            break

                # Get the index of the selected tool in the list of options
                selected_tool_index = next(
                    (
                        ind
                        for ind, tool in enumerate(build_config["tool_name"]["options"])
                        if tool["name"] == current_tool_name.title()
                    ),
                    None,
                )

                if has_active_connections:
                    # User has active connection
                    if selected_tool_index is not None:
                        build_config["tool_name"]["options"][selected_tool_index]["link"] = "validated"

                    # If it's a validation request, validate the tool
                    if (isinstance(field_value, dict) and "validate" in field_value) or isinstance(field_value, str):
                        return self.validate_tool(build_config, field_value, current_tool_name)
                else:
                    # No active connection - create OAuth connection
                    try:
                        connection = composio.toolkits.authorize(user_id=self.entity_id, toolkit=toolkit_slug)
                        redirect_url = getattr(connection, "redirect_url", None)

                        if redirect_url and redirect_url.startswith(("http://", "https://")):
                            if selected_tool_index is not None:
                                build_config["tool_name"]["options"][selected_tool_index]["link"] = redirect_url
                        elif selected_tool_index is not None:
                            build_config["tool_name"]["options"][selected_tool_index]["link"] = "error"
                    except (ValueError, ConnectionError, AttributeError) as e:
                        self.log(f"Error creating OAuth connection: {e}")
                        if selected_tool_index is not None:
                            build_config["tool_name"]["options"][selected_tool_index]["link"] = "error"

            except (ValueError, ConnectionError, AttributeError) as e:
                self.log(f"Error checking connection status: {e}")

        return build_config

    def build_tool(self) -> Sequence[Tool]:
        """Build Composio tools based on selected actions.

        Returns:
            Sequence[Tool]: List of configured Composio tools.
        """
        composio = self._build_wrapper()
        action_names = [action["name"] for action in self.actions]

        # Get toolkits from action names
        toolkits = set()
        for action_name in action_names:
            if "_" in action_name:
                toolkit = action_name.split("_")[0].lower()
                toolkits.add(toolkit)

        if not toolkits:
            return []

        # Get all tools for the relevant toolkits
        all_tools = composio.tools.get(user_id=self.entity_id, toolkits=list(toolkits))

        # Filter to only the specific actions we want using list comprehension
        return [tool for tool in all_tools if hasattr(tool, "name") and tool.name in action_names]

    def _build_wrapper(self) -> Composio:
        """Build the Composio wrapper using new SDK.

        Returns:
            Composio: The initialized Composio client.

        Raises:
            ValueError: If the API key is not found or invalid.
        """
        try:
            if not self.api_key:
                msg = "Composio API Key is required"
                raise ValueError(msg)
            return Composio(api_key=self.api_key, provider=LangchainProvider())
        except ValueError as e:
            self.log(f"Error building Composio wrapper: {e}")
            msg = "Please provide a valid Composio API Key in the component settings"
            raise ValueError(msg) from e
