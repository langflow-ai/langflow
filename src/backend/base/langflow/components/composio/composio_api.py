# Standard library imports
from collections.abc import Sequence
from typing import Any

from composio import Action, App

# Third-party imports
from composio_langchain import ComposioToolSet
from langchain_core.tools import Tool

# Local imports
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import (
    ConnectionInput,
    MessageTextInput,
    SecretStrInput,
    SortableListInput,
    StrInput,
)
from langflow.io import Output


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
            search_category=["All", "Analytics & Data", "Collaboration"],  # TODO: Add more categories
            value="",
            connection_link="",
            info="The name of the tool to use",
            real_time_refresh=True,
        ),
        StrInput(
            name="use_case",
            display_name="Use Case",
            placeholder="Create a new repository",
            info="The use case for the tool",
            real_time_refresh=True,
            advanced=True,
        ),
        SortableListInput(
            name="actions",
            display_name="Actions",
            placeholder="Select action",
            helper_text="Please connect before selecting tools",
            helper_text_metadata={"icon": "OctagonAlert", "variant": "destructive"},
            options=[],
            value="",
            info="The actions to use",
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_tool"),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        # If the list of tools is not available, always update it
        if field_name == "api_key":
            # Initialize the Composio ToolSet with your API key
            toolset = ComposioToolSet(api_key=self.api_key)

            # Get the entity (e.g., "default" for your user)
            entity = toolset.get_entity(self.entity_id)

            # Get all available apps
            all_apps = entity.client.apps.get()

            # Build an object with name, icon, link
            build_config["tool_name"]["options"] = [
                {
                    "name": app.name.title(),
                    "icon": app.name,
                    "link": "",
                }
                for app in sorted(all_apps, key=lambda x: x.name)
            ]

        # Handle the click of the Tool Name connect button
        if field_name == "tool_name" and field_value:
            # Initialize the Composio ToolSet with your API key
            toolset = ComposioToolSet(api_key=self.api_key)

            # Get the entity (e.g., "default" for your user)
            entity = toolset.get_entity(id=self.entity_id)

            # Initiate a GitHub connection and get the redirect URL
            connection_request = entity.initiate_connection(app_name=getattr(App, field_value.upper()))

            # Get the index of the selected tool in the list of options
            selected_tool_index = next(
                (ind for ind, tool in enumerate(build_config["tool_name"]["options"]) if tool["name"] == field_value),
                None,
            )

            # Print the direct HTTP link for authentication
            build_config["tool_name"]["options"][selected_tool_index]["link"] = connection_request.redirectUrl

            # Set the helper text and helper text metadata field of the actions now
            build_config["actions"]["helper_text"] = "Successfully Authenticated! Select an action."
            build_config["actions"]["helper_text_metadata"] = {"icon": "Check", "variant": "success"}

        if field_name == "use_case" or (field_name == "tool_name" and field_value):
            toolset = ComposioToolSet(api_key=self.api_key)
            connected_apps = [app for app in toolset.get_connected_accounts() if app.status == "ACTIVE"]

            # Get the list of actions available
            all_actions = list(Action.all())
            authenticated_actions = sorted(
                [
                    action
                    for action in all_actions
                    if action.app.lower() in [app.appName.lower() for app in connected_apps]
                    and action.app.lower() == self.tool_name.lower()
                ],
                key=lambda x: x.name,
            )

            # Return the list of action names
            build_config["actions"]["options"] = [
                {
                    "name": action.name,
                }
                for action in authenticated_actions
            ]

        return build_config

    def build_tool(self) -> Sequence[Tool]:
        """Build Composio tools based on selected actions.

        Returns:
            Sequence[Tool]: List of configured Composio tools.
        """
        composio_toolset = self._build_wrapper()
        return composio_toolset.get_tools(actions=self.actions)

    def _build_wrapper(self) -> ComposioToolSet:
        """Build the Composio toolset wrapper.

        Returns:
            ComposioToolSet: The initialized toolset.

        Raises:
            ValueError: If the API key is not found or invalid.
        """
        try:
            if not self.api_key:
                msg = "Composio API Key is required"
                raise ValueError(msg)
            return ComposioToolSet(api_key=self.api_key, entity_id=self.entity_id)
        except ValueError as e:
            self.log(f"Error building Composio wrapper: {e}")
            msg = "Please provide a valid Composio API Key in the component settings"
            raise ValueError(msg) from e
