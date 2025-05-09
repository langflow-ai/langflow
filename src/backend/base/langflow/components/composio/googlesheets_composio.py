from typing import Any

from composio import Action

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs import (
    BoolInput,
    MessageTextInput,
    # NestedDictInput,
)
from langflow.logging import logger


class ComposioGooglesheetsAPIComponent(ComposioBaseComponent):
    display_name: str = "Google Sheets"
    description: str = "Google Sheets API"
    icon = "Googlesheets"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlesheets"

    # Google Sheets specific actions
    _actions_data: dict = {
        "GOOGLESHEETS_CREATE_GOOGLE_SHEET1": {
            "display_name": "Create Google Sheet",
            "action_fields": ["GOOGLESHEETS_CREATE_GOOGLE_SHEET1_title"],
        },
        "GOOGLESHEETS_BATCH_GET": {
            "display_name": "Batch Get Spreadsheet",
            "action_fields": [
                "GOOGLESHEETS_BATCH_GET_spreadsheet_id",
                "GOOGLESHEETS_BATCH_GET_ranges",
            ],
        },
        "GOOGLESHEETS_GET_SPREADSHEET_INFO": {
            "display_name": "Get Spreadsheet Info",
            "action_fields": ["GOOGLESHEETS_GET_SPREADSHEET_INFO_spreadsheet_id"],
        },
        "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW": {
            "display_name": "Lookup Spreadsheet Row",
            "action_fields": [
                "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW_spreadsheet_id",
                "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW_range",
                "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW_query",
                "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW_case_sensitive",
            ],
        },
        # "GOOGLESHEETS_BATCH_UPDATE": {
        #     "display_name": "Batch Update Spreadsheet",
        #     "action_fields": [
        #         "GOOGLESHEETS_BATCH_UPDATE_spreadsheet_id",
        #         "GOOGLESHEETS_BATCH_UPDATE_sheet_name",
        #         "GOOGLESHEETS_BATCH_UPDATE_first_cell_location",
        #         "GOOGLESHEETS_BATCH_UPDATE_values",
        #         "GOOGLESHEETS_BATCH_UPDATE_includeValuesInResponse",
        #     ],
        # },
        # "GOOGLESHEETS_SHEET_FROM_JSON": {
        #     "display_name": "Sheet From Json",
        #     "action_fields": [
        #         "GOOGLESHEETS_SHEET_FROM_JSON_title",
        #         "GOOGLESHEETS_SHEET_FROM_JSON_sheet_name",
        #         "GOOGLESHEETS_SHEET_FROM_JSON_sheet_json",
        #     ],
        # },
        "GOOGLESHEETS_CLEAR_VALUES": {
            "display_name": "Clear Spreadsheet Values",
            "action_fields": [
                "GOOGLESHEETS_CLEAR_VALUES_spreadsheet_id",
                "GOOGLESHEETS_CLEAR_VALUES_range",
            ],
        },
    }

    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}
    _bool_variables = {
        "GOOGLESHEETS_BATCH_UPDATE_includeValuesInResponse",
        "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW_case_sensitive",
    }

    inputs = [
        *ComposioBaseComponent._base_inputs,
        # MessageTextInput(
        #     name="GOOGLESHEETS_BATCH_UPDATE_spreadsheet_id",
        #     display_name="Spreadsheet Id",
        #     info="The unique identifier of the Google Sheets spreadsheet to be updated",
        #     show=False,
        #     required=True,
        # ),
        # MessageTextInput(
        #     name="GOOGLESHEETS_BATCH_UPDATE_sheet_name",
        #     display_name="Sheet Name",
        #     info="The name of the specific sheet within the spreadsheet to update",
        #     show=False,
        #     required=True,
        # ),
        # MessageTextInput(
        #     name="GOOGLESHEETS_BATCH_UPDATE_first_cell_location",
        #     display_name="First Cell Location",
        #     info="The starting cell for the update range, specified in A1 notation (e.g., 'A1', 'B2'). The update will extend from this cell to the right and down, based on the provided values.",  # noqa: E501
        #     show=False,
        # ),
        # NestedDictInput(
        #     name="GOOGLESHEETS_BATCH_UPDATE_values",
        #     display_name="Row Column Values",
        #     info="A 2D list representing the values to update. Each inner list corresponds to a row in the spreadsheet.",  # noqa: E501
        #     is_list=True,
        #     required=True,
        #     show=False,
        # ),
        # BoolInput(
        #     name="GOOGLESHEETS_BATCH_UPDATE_includeValuesInResponse",
        #     display_name="Include Values in Response",
        #     info="If set to True, the response will include the updated values from the spreadsheet",
        #     show=False,
        #     value=False,
        #     advanced=True,
        # ),
        MessageTextInput(
            name="GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW_spreadsheet_id",
            display_name="Spreadsheet Id",
            info="The ID of the spreadsheet",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW_range",
            display_name="Range",
            info="The A1 notation of the range to search. If not specified, it will return the non_empty part of the first sheet in the spreadsheet. Example: Sheet1!A1:D5.",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW_query",
            display_name="Query",
            info="The search query to use for matching the row. This field is required.",
            show=False,
            required=True,
        ),
        BoolInput(
            name="GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW_case_sensitive",
            display_name="Case Sensitive",
            info="Whether the search should be case-sensitive.",
            show=False,
            value=False,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_GET_SPREADSHEET_INFO_spreadsheet_id",
            display_name="Spreadsheet Id",
            info="ID of the Google Sheet to retrieve",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_CREATE_GOOGLE_SHEET1_title",
            display_name="Title",
            info="Title of the Google Sheet. Please ensure the title is mentioned.",
            show=False,
            required=True,
        ),
        # MessageTextInput(
        #     name="GOOGLESHEETS_SHEET_FROM_JSON_title",
        #     display_name="Title",
        #     info="Title of the Google Sheet. Please ensure the title is mentioned.",
        #     show=False,
        #     required=True,
        # ),
        # MessageTextInput(
        #     name="GOOGLESHEETS_SHEET_FROM_JSON_sheet_name",
        #     display_name="Sheet Name",
        #     info="Name of the sheet to be created. Please ensure the name is mentioned.",
        #     show=False,
        #     required=True,
        # ),
        # MessageTextInput(
        #     name="GOOGLESHEETS_SHEET_FROM_JSON_sheet_json",
        #     display_name="Sheet Json",
        #     info="A list of dictionaries where each dictionary has the same keys. Values can be strings, numbers, booleans, or null.",  # noqa: E501
        #     show=False,
        #     required=True,
        # ),
        MessageTextInput(
            name="GOOGLESHEETS_CLEAR_VALUES_spreadsheet_id",
            display_name="Spreadsheet Id",
            info="The ID of the spreadsheet",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_CLEAR_VALUES_range",
            display_name="Range",
            info="The A1 notation range to clear in the spreadsheet",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_BATCH_GET_spreadsheet_id",
            display_name="Spreadsheet Id",
            info="The ID of the spreadsheet",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLESHEETS_BATCH_GET_ranges",
            display_name="Ranges",
            info="List of ranges to retrieve in A1 notation, e.g. 'Sheet1!A1:B2'. If not specified, the filled part of the sheet will be returned if it is less than 100 rows and columns.",  # noqa: E501
            show=False,
        ),
    ]

    def execute_action(self):
        """Execute action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            self._build_action_maps()
            # Get the display name from the action list
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else self.action
            # Use the display_to_key_map to get the action key
            action_key = self._display_to_key_map.get(display_name)
            if not action_key:
                msg = f"Invalid action: {display_name}"
                raise ValueError(msg)

            enum_name = getattr(Action, action_key)
            params = {}
            if action_key in self._actions_data:
                for field in self._actions_data[action_key]["action_fields"]:
                    value = getattr(self, field)

                    if value is None or value == "":
                        continue

                    if field in ["GOOGLESHEETS_SHEET_FROM_JSON_sheet_json", "GOOGLESHEETS_BATCH_GET_ranges"] and value:
                        value = [item.strip() for item in value.split(",")]

                    if field in self._bool_variables:
                        value = bool(value)

                    param_name = field.replace(action_key + "_", "")
                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            if not result.get("successful"):
                return {"error": result.get("error", "No response")}

            result_data = result.get("data", [])
            if (
                len(result_data) != 1
                and not self._actions_data.get(action_key, {}).get("result_field")
                and self._actions_data.get(action_key, {}).get("get_result_field")
            ):
                msg = f"Expected a dict with a single key, got {len(result_data)} keys: {result_data.keys()}"
                raise ValueError(msg)
            if result_data:
                get_result_field = self._actions_data.get(action_key, {}).get("get_result_field", True)
                if get_result_field:
                    key = self._actions_data.get(action_key, {}).get("result_field", next(iter(result_data)))
                    return (
                        result_data.get(key)
                        if isinstance(result_data.get(key), dict)
                        else {"response": result_data.get(key)}
                    )
                return result_data if isinstance(result_data, dict) else {"response": result_data}
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else str(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)

    def set_default_tools(self):
        self._default_tools = {
            self.sanitize_action_name("GOOGLESHEETS_CREATE_GOOGLE_SHEET1").replace(" ", "-"),
            self.sanitize_action_name("GOOGLESHEETS_BATCH_GET").replace(" ", "-"),
        }
