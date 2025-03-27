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
            helper_text="Please connect before selecting tools.",
            helper_text_metadata={"icon": "OctagonAlert", "variant": "destructive"},
            options=[],
            value="",
            info="The actions to use",
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_tool"),
    ]

    def validate_tool(self, build_config: dict, field_value: Any, connected_app_names: list) -> dict:
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

        # Get the list of actions available
        all_actions = list(Action.all())
        authenticated_actions = sorted(
            [
                action
                for action in all_actions
                if action.app.lower() in list(connected_app_names) and action.app.lower() == self.tool_name.lower()
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

            return build_config

        # Handle the click of the Tool Name connect button
        if field_name == "tool_name" and field_value:
            # Get the list of apps (tools) we have connected
            toolset = ComposioToolSet(api_key=self.api_key)
            connected_apps = [app for app in toolset.get_connected_accounts() if app.status == "ACTIVE"]

            # Get the unique list of appName from the connected apps
            connected_app_names = [app.appName.lower() for app in connected_apps]

            # Clear out the list of selected actions
            build_config["actions"]["options"] = []
            build_config["actions"]["value"] = ""

            # If it's a dictionary, we need to do validation
            if isinstance(field_value, dict):
                # If the current field value is a dictionary, it means the user has selected a tool
                if "validate" not in field_value:
                    return build_config

                # Check if the selected tool is connected
                check_app = field_value["validate"].lower()

                # If the tool selected is NOT what we are validating, return the build config
                if check_app != self.tool_name.lower():
                    # Set the helper text and helper text metadata field of the actions now
                    build_config["actions"]["helper_text"] = "Please connect before selecting tools."
                    build_config["actions"]["helper_text_metadata"] = {
                        "icon": "OctagonAlert",
                        "variant": "destructive",
                    }

                    return build_config

                # Check if the tool is already validated
                if check_app not in connected_app_names:
                    return build_config

                # Validate the selected tool
                return self.validate_tool(build_config, field_value, connected_app_names)

            # Check if the tool is already validated
            if field_value.lower() in connected_app_names:
                return self.validate_tool(build_config, field_value, connected_app_names)

            # Get the entity (e.g., "default" for your user)
            entity = toolset.get_entity(id=self.entity_id)

            # Set the metadata for the actions
            build_config["actions"]["helper_text_metadata"] = {"icon": "OctagonAlert", "variant": "destructive"}

            # Get the index of the selected tool in the list of options
            selected_tool_index = next(
                (ind for ind, tool in enumerate(build_config["tool_name"]["options"]) if tool["name"] == field_value),
                None,
            )

            # Initiate a GitHub connection and get the redirect URL
            try:
                connection_request = entity.initiate_connection(app_name=getattr(App, field_value.upper()))
            except Exception as _:  # noqa: BLE001
                # Indicate that there was an error connecting to the tool
                build_config["tool_name"]["options"][selected_tool_index]["link"] = "error"
                build_config["actions"]["helper_text"] = f"Error connecting to {field_value}"

                return build_config

            # Print the direct HTTP link for authentication
            build_config["tool_name"]["options"][selected_tool_index]["link"] = connection_request.redirectUrl

            # Set the helper text and helper text metadata field of the actions now
            build_config["actions"]["helper_text"] = "Please connect before selecting tools."

        return build_config

    def build_tool(self) -> Sequence[Tool]:
        """Build Composio tools based on selected actions.

        Returns:
            Sequence[Tool]: List of configured Composio tools.
        """
        composio_toolset = self._build_wrapper()
        return composio_toolset.get_tools(actions=[action["name"] for action in self.actions])

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
