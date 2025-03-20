from typing import Any

from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio_langchain import Action, ComposioToolSet
from langchain_core.tools import Tool
from loguru import logger

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import (
    DropdownInput,
    LinkInput,
    MessageTextInput,
    SecretStrInput,
    StrInput,
)
from langflow.io import Output
from langflow.schema.message import Message


class GooglemeetAPIComponent(LCToolComponent):
    display_name: str = "Google Meet"
    description: str = "Google Meet API"
    name = "GooglemeetAPI"
    icon = "Googlemeet"
    documentation: str = "https://docs.composio.dev"

    _display_to_enum_map = {
        "Get Transcripts By Conference Record ID": "GOOGLEMEET_GET_TRANSCRIPTS_BY_CONFERENCE_RECORD_ID",
        "Get Conference Record By Space Name, Meeting Code, Start Time, End Time": "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET",  # noqa: E501
        "Get Recordings By Conference Record ID": "GOOGLEMEET_GET_RECORDINGS_BY_CONFERENCE_RECORD_ID",
        "Create Meet": "GOOGLEMEET_CREATE_MEET",
        "Get Meet Details": "GOOGLEMEET_GET_MEET",
    }

    _actions_data: dict = {
        "GOOGLEMEET_GET_TRANSCRIPTS_BY_CONFERENCE_RECORD_ID": {
            "display_name": "Get Transcripts By Conference Record ID",
            "parameters": ["GOOGLEMEET_GET_TRANSCRIPTS_BY_CONFERENCE_RECORD_ID-conferenceRecord_id"],
        },
        "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET": {
            "display_name": "Get Conference Record By Space Name, Meeting Code, Start Time, End Time",
            "parameters": [
                "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET-space_name",
                "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET-meeting_code",
                "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET-start_time",
                "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET-end_time",
            ],
        },
        "GOOGLEMEET_GET_RECORDINGS_BY_CONFERENCE_RECORD_ID": {
            "display_name": "Get Recordings By Conference Record ID",
            "parameters": ["GOOGLEMEET_GET_RECORDINGS_BY_CONFERENCE_RECORD_ID-conferenceRecord_id"],
        },
        "GOOGLEMEET_CREATE_MEET": {
            "display_name": "Create Meet",
            "parameters": ["GOOGLEMEET_CREATE_MEET-access_type", "GOOGLEMEET_CREATE_MEET-entry_point_access"],
        },
        "GOOGLEMEET_GET_MEET": {"display_name": "Get Meet Details", "parameters": ["GOOGLEMEET_GET_MEET-space_name"]},
    }

    inputs = [
        MessageTextInput(
            name="entity_id",
            display_name="Entity ID",
            value="default",
            advanced=True,
            tool_mode=True,  # Intentionally setting tool_mode=True to make this Component support both tool and non-tool functionality  # noqa: E501
        ),
        SecretStrInput(
            name="api_key",
            display_name="Composio API Key",
            required=True,
            info="Refer to https://docs.composio.dev/faq/api_key/api_key",
            real_time_refresh=True,
        ),
        LinkInput(
            name="auth_link",
            display_name="Authentication Link",
            value="",
            info="Click to authenticate with OAuth2",
            dynamic=True,
            show=False,
            placeholder="Click to authenticate",
        ),
        StrInput(
            name="auth_status",
            display_name="Auth Status",
            value="Not Connected",
            info="Current authentication status",
            dynamic=True,
            show=False,
            refresh_button=True,
        ),
        # Non tool-mode input fields
        DropdownInput(
            name="action",
            display_name="Action",
            options=[],
            value="",
            info="Select Gmail action to pass to the agent",
            show=True,
            real_time_refresh=True,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_TRANSCRIPTS_BY_CONFERENCE_RECORD_ID-conferenceRecord_id",
            display_name="Conferencerecord Id",
            info="The unique identifier for the conference record.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_RECORDINGS_BY_CONFERENCE_RECORD_ID-conferenceRecord_id",
            display_name="Conferencerecord Id",
            info="The unique identifier for the conference record.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLEMEET_CREATE_MEET-access_type",
            display_name="AccessType",
            info="The type of access to the Google Meet space.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLEMEET_CREATE_MEET-entry_point_access",
            display_name="EntryPointAccess",
            info="The entry point for the Google Meet space.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_MEET-space_name",
            display_name="Space Name",
            info="The unique identifier for the Google Meet space.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET-space_name",
            display_name="Space Name",
            info="The name of the Google Meet space.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET-meeting_code",
            display_name="Meeting Code",
            info="The meeting code of the Google Meet space.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET-start_time",
            display_name="Start Time",
            info="The start time of the meeting.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET-end_time",
            display_name="End Time",
            info="The end time of the meeting.",
            show=False,
        ),
    ]

    outputs = [
        Output(name="text", display_name="Response", method="execute_action"),
    ]

    def execute_action(self) -> Message:
        """Execute Google Meet action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            action_key = self._display_to_enum_map.get(self.action)

            enum_name = getattr(Action, action_key)  # type: ignore[arg-type]
            params = {}
            if action_key in self._actions_data:
                for field in self._actions_data[action_key]["parameters"]:
                    param_name = field.split("-", 1)[1] if "-" in field else field
                    value = getattr(self, field)

                    if value is None or value == "":
                        continue

                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            self.status = result
            return Message(text=str(result))
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action
            if self.action in self._actions_data:
                display_name = self._actions_data[self.action]["display_name"]
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def show_hide_fields(self, build_config: dict, field_value: Any):
        all_fields = set()
        for action_data in self._actions_data.values():
            all_fields.update(action_data["parameters"])

        for field in all_fields:
            build_config[field]["show"] = False
            build_config[field]["value"] = ""

        action_key = self._display_to_enum_map.get(field_value)

        if action_key in self._actions_data:
            for field in self._actions_data[action_key]["parameters"]:
                build_config[field]["show"] = True

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        build_config["auth_status"]["show"] = True
        build_config["auth_status"]["advanced"] = False

        if field_name == "tool_mode":
            if field_value:
                build_config["action"]["show"] = False

                all_fields = set()
                for action_data in self._actions_data.values():
                    all_fields.update(action_data["parameters"])
                for field in all_fields:
                    build_config[field]["show"] = False

            else:
                build_config["action"]["show"] = True

        if field_name == "action":
            self.show_hide_fields(build_config, field_value)

        if hasattr(self, "api_key") and self.api_key != "":
            googlemeet_display_names = list(self._display_to_enum_map.keys())
            build_config["action"]["options"] = googlemeet_display_names

            try:
                toolset = self._build_wrapper()
                entity = toolset.client.get_entity(id=self.entity_id)

                try:
                    entity.get_connection(app="googlemeet")
                    build_config["auth_status"]["value"] = "✅"
                    build_config["auth_link"]["show"] = False

                except NoItemsFound:
                    auth_scheme = self._get_auth_scheme("googlemeet")
                    if auth_scheme.auth_mode == "OAUTH2":
                        build_config["auth_link"]["show"] = True
                        build_config["auth_link"]["advanced"] = False
                        auth_url = self._initiate_default_connection(entity, "googlemeet")
                        build_config["auth_link"]["value"] = auth_url
                        build_config["auth_status"]["value"] = "Click link to authenticate"

            except (ValueError, ConnectionError) as e:
                logger.error(f"Error checking auth status: {e}")
                build_config["auth_status"]["value"] = f"Error: {e!s}"

        return build_config

    def _get_auth_scheme(self, app_name: str) -> AppAuthScheme:
        """Get the primary auth scheme for an app.

        Args:
        app_name (str): The name of the app to get auth scheme for.

        Returns:
        AppAuthScheme: The auth scheme details.
        """
        toolset = self._build_wrapper()
        try:
            return toolset.get_auth_scheme_for_app(app=app_name.lower())
        except Exception:  # noqa: BLE001
            logger.exception(f"Error getting auth scheme for {app_name}")
            return None

    def _initiate_default_connection(self, entity: Any, app: str) -> str:
        connection = entity.initiate_connection(app_name=app, use_composio_auth=True, force_new_integration=True)
        return connection.redirectUrl

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
            return ComposioToolSet(api_key=self.api_key)
        except ValueError as e:
            logger.error(f"Error building Composio wrapper: {e}")
            msg = "Please provide a valid Composio API Key in the component settings"
            raise ValueError(msg) from e

    async def _get_tools(self) -> list[Tool]:
        toolset = self._build_wrapper()
        tools = toolset.get_tools(actions=self._actions_data.keys())
        for tool in tools:
            tool.tags = [tool.name]  # Assigning tags directly
        return tools

    @property
    def enabled_tools(self):
        return [
            "GOOGLEMEET_CREATE_MEET",
            "GOOGLEMEET_GET_MEET",
        ]
