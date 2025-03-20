from typing import Any

from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio_langchain import Action, ComposioToolSet
from langchain_core.tools import Tool
from loguru import logger

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import (
    BoolInput,
    DropdownInput,
    LinkInput,
    MessageTextInput,
    SecretStrInput,
    StrInput,
)
from langflow.io import Output
from langflow.schema.message import Message


class GooglesheetsAPIComponent(LCToolComponent):
    display_name: str = "Google sheets"
    description: str = "Google Sheets API"
    name = "GooglesheetsAPI"
    icon = "Googlesheets"
    documentation: str = "https://docs.composio.dev"

    _display_to_enum_map = {
        "Create Google Sheet": "GOOGLESHEETS_CREATE_GOOGLE_SHEET1",
        "Batch Get Spreadsheet": "GOOGLESHEETS_BATCH_GET",
        "Get Spreadsheet Info": "GOOGLESHEETS_GET_SPREADSHEET_INFO",
        "Lookup Spreadsheet Row": "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW",
        "Batch Update Spreadsheet": "GOOGLESHEETS_BATCH_UPDATE",
        "Sheet From Json": "GOOGLESHEETS_SHEET_FROM_JSON",
        "Clear Spreadsheet Values": "GOOGLESHEETS_CLEAR_VALUES",
    }

    _actions_data: dict = {
        "GOOGLESHEETS_CREATE_GOOGLE_SHEET1": {
            "display_name": "Create Google Sheet",
            "parameters": ["GOOGLESHEETS_CREATE_GOOGLE_SHEET1-title"],
        },
        "GOOGLESHEETS_BATCH_GET": {
            "display_name": "Batch Get Spreadsheet",
            "parameters": [
                "GOOGLESHEETS_BATCH_GET-spreadsheet_id",
                "GOOGLESHEETS_BATCH_GET-ranges",
            ],
        },
        "GOOGLESHEETS_GET_SPREADSHEET_INFO": {
            "display_name": "Get Spreadsheet Info",
            "parameters": ["GOOGLESHEETS_GET_SPREADSHEET_INFO-spreadsheet_id"],
        },
        "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW": {
            "display_name": "Lookup Spreadsheet Row",
            "parameters": [
                "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW-spreadsheet_id",
                "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW-range",
                "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW-query",
                "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW-case_sensitive",
            ],
        },
        "GOOGLESHEETS_BATCH_UPDATE": {
            "display_name": "Batch Update Spreadsheet",
            "parameters": [
                "GOOGLESHEETS_BATCH_UPDATE-spreadsheet_id",
                "GOOGLESHEETS_BATCH_UPDATE-sheet_name",
                "GOOGLESHEETS_BATCH_UPDATE-first_cell_location",
                "GOOGLESHEETS_BATCH_UPDATE-values",
                "GOOGLESHEETS_BATCH_UPDATE-includeValuesInResponse",
            ],
        },
        "GOOGLESHEETS_SHEET_FROM_JSON": {
            "display_name": "Sheet From Json",
            "parameters": [
                "GOOGLESHEETS_SHEET_FROM_JSON-title",
                "GOOGLESHEETS_SHEET_FROM_JSON-sheet_name",
                "GOOGLESHEETS_SHEET_FROM_JSON-sheet_json",
            ],
        },
        "GOOGLESHEETS_CLEAR_VALUES": {
            "display_name": "Clear Spreadsheet Values",
            "parameters": [
                "GOOGLESHEETS_CLEAR_VALUES-spreadsheet_id",
                "GOOGLESHEETS_CLEAR_VALUES-range",
            ],
        },
    }

    _bool_variables = {
        "GOOGLESHEETS_BATCH_UPDATE-includeValuesInResponse",
        "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW-case_sensitive",
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
            name="GOOGLESHEETS_BATCH_UPDATE-spreadsheet_id",
            display_name="Spreadsheet Id",
            info="The unique identifier of the Google Sheets spreadsheet to be updated",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_BATCH_UPDATE-sheet_name",
            display_name="Sheet Name",
            info="The name of the specific sheet within the spreadsheet to update",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_BATCH_UPDATE-first_cell_location",
            display_name="First Cell Location",
            info="The starting cell for the update range, specified in A1 notation (e.g., 'A1', 'B2'). The update will extend from this cell to the right and down, based on the provided values.",  # noqa: E501
            show=False,
        ),
        StrInput(
            name="GOOGLESHEETS_BATCH_UPDATE-values",
            display_name="Values",
            info="A 2D list representing the values to update. Each inner list corresponds to a row in the spreadsheet.",  # noqa: E501
            show=False,
            is_list=True,
            required=True,
        ),
        BoolInput(
            name="GOOGLESHEETS_BATCH_UPDATE-includeValuesInResponse",
            display_name="Includevaluesinresponse",
            info="If set to True, the response will include the updated values from the spreadsheet",
            show=False,
            value=False,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW-spreadsheet_id",
            display_name="Spreadsheet Id",
            info="The ID of the spreadsheet",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW-range",
            display_name="Range",
            info="The A1 notation of the range to search.If not specified, it will return the non-empty part of the first sheet in the spreadsheet.Example: Sheet1!A1:D5., Please specify the range for large spreadsheets.",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW-query",
            display_name="Query",
            info="The search query to use for matching the row. This field is required.",
            show=False,
            required=True,
        ),
        BoolInput(
            name="GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW-case_sensitive",
            display_name="Case Sensitive",
            info="Whether the search should be case-sensitive.",
            show=False,
            value=False,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_GET_SPREADSHEET_INFO-spreadsheet_id",
            display_name="Spreadsheet Id",
            info="ID of the Google Sheet to retrieve",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_CREATE_GOOGLE_SHEET1-title",
            display_name="Title",
            info="Title of the Google Sheet. Please ensure the title is mentioned.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_SHEET_FROM_JSON-title",
            display_name="Title",
            info="Title of the Google Sheet. Please ensure the title is mentioned.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_SHEET_FROM_JSON-sheet_name",
            display_name="Sheet Name",
            info="Name of the sheet to be created. Please ensure the name is mentioned.",
            show=False,
            required=True,
        ),
        StrInput(
            name="GOOGLESHEETS_SHEET_FROM_JSON-sheet_json",
            display_name="Sheet Json",
            info="A list of dictionaries where each dictionary has the same keys. Values can be strings, numbers, booleans, or null.",  # noqa: E501
            show=False,
            is_list=True,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_CLEAR_VALUES-spreadsheet_id",
            display_name="Spreadsheet Id",
            info="The ID of the spreadsheet",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_CLEAR_VALUES-range",
            display_name="Range",
            info="The A1 notation range to clear in the spreadsheet",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_BATCH_GET-spreadsheet_id",
            display_name="Spreadsheet Id",
            info="The ID of the spreadsheet",
            show=False,
            required=True,
        ),
        StrInput(
            name="GOOGLESHEETS_BATCH_GET-ranges",
            display_name="Ranges",
            info="List of ranges to retrieve in A1 notation, e.g. 'Sheet1!A1:B2'. If not specified, the filled part of the sheet will be returned if it is less than 100 rows and columns.",  # noqa: E501
            show=False,
            is_list=True,
        ),
    ]

    outputs = [
        Output(name="text", display_name="Response", method="execute_action"),
    ]

    def execute_action(self) -> Message:
        """Execute Google Sheets action and return response as Message."""
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

                    if field in self._bool_variables:
                        value = bool(value)

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

            if field in self._bool_variables:
                build_config[field]["value"] = False
            else:
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
            googlesheets_display_names = list(self._display_to_enum_map.keys())
            build_config["action"]["options"] = googlesheets_display_names

            try:
                toolset = self._build_wrapper()
                entity = toolset.client.get_entity(id=self.entity_id)

                try:
                    entity.get_connection(app="googlesheets")
                    build_config["auth_status"]["value"] = "✅"
                    build_config["auth_link"]["show"] = False

                except NoItemsFound:
                    auth_scheme = self._get_auth_scheme("googlesheets")
                    if auth_scheme.auth_mode == "OAUTH2":
                        build_config["auth_link"]["show"] = True
                        build_config["auth_link"]["advanced"] = False
                        auth_url = self._initiate_default_connection(entity, "googlesheets")
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
            "GOOGLESHEETS_CREATE_GOOGLE_SHEET1",
            "GOOGLESHEETS_BATCH_GET",
        ]
