from typing import Any

from composio import Action

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs import (
    MessageTextInput,
)
from langflow.logging import logger


class ComposioGooglemeetAPIComponent(ComposioBaseComponent):
    """Google Meet API component for interacting with Google Meet services."""

    display_name: str = "Google Meet"
    description: str = "Google Meet API"
    icon = "Googlemeet"
    documentation: str = "https://docs.composio.dev"
    app_name: str = "googlemeet"

    # Google Meet specific actions
    _actions_data: dict = {
        "GOOGLEMEET_GET_TRANSCRIPTS_BY_CONFERENCE_RECORD_ID": {
            "display_name": "Get Transcripts By Conference Record ID",
            "action_fields": ["GOOGLEMEET_GET_TRANSCRIPTS_BY_CONFERENCE_RECORD_ID_conferenceRecord_id"],
        },
        "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET": {
            "display_name": "Get Conference Record By Space Name, Meeting Code, Start Time, End Time",
            "action_fields": [
                "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET_space_name",
                "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET_meeting_code",
                "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET_start_time",
                "GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET_end_time",
            ],
        },
        "GOOGLEMEET_GET_RECORDINGS_BY_CONFERENCE_RECORD_ID": {
            "display_name": "Get Recordings By Conference Record ID",
            "action_fields": ["GOOGLEMEET_GET_RECORDINGS_BY_CONFERENCE_RECORD_ID_conferenceRecord_id"],
        },
        "GOOGLEMEET_CREATE_MEET": {
            "display_name": "Create Meet",
            "action_fields": ["GOOGLEMEET_CREATE_MEET_access_type", "GOOGLEMEET_CREATE_MEET_entry_point_access"],
        },
        "GOOGLEMEET_GET_MEET": {
            "display_name": "Get Meet Details",
            "action_fields": ["GOOGLEMEET_GET_MEET_space_name"],
        },
    }

    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}

    # Combine base inputs with Google Meet specific inputs
    inputs = [
        *ComposioBaseComponent._base_inputs,
        MessageTextInput(
            name="GOOGLEMEET_GET_TRANSCRIPTS_BY_CONFERENCE_RECORD_ID_conferenceRecord_id",
            display_name="Conference Record Id",
            info="The unique identifier for the conference record.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_RECORDINGS_BY_CONFERENCE_RECORD_ID_conferenceRecord_id",
            display_name="Conference Record Id",
            info="The unique identifier for the conference record.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLEMEET_CREATE_MEET_access_type",
            display_name="Access Type",
            info="The type of access to the Google Meet space. Values include: 'OPEN','TRUSTED','RESTRICTED','ACCESS_TYPE_UNSPECIFIED'.",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLEMEET_CREATE_MEET_entry_point_access",
            display_name="Entry Point Access",
            info="The entry point for the Google Meet space. Values include: 'ENTRY_POINT_ACCESS_UNSPECIFIED', 'ALL', 'CREATOR_APP_ONLY'.",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_MEET_space_name",
            display_name="Space Name",
            info="The unique identifier for the Google Meet space.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET_space_name",
            display_name="Space Name",
            info="The name of the Google Meet space.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET_meeting_code",
            display_name="Meeting Code",
            info="The meeting code of the Google Meet space.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET_start_time",
            display_name="Start Time",
            info="The start time of the meeting.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLEMEET_GET_CONFERENCE_RECORD_FOR_MEET_end_time",
            display_name="End Time",
            info="The end time of the meeting.",
            show=False,
            advanced=True,
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
                    return result_data.get(key)
                return result_data
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else str(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)

    def set_default_tools(self):
        self._default_tools = {
            self.sanitize_action_name("GOOGLEMEET_CREATE_MEET").replace(" ", "-"),
            self.sanitize_action_name("GOOGLEMEET_GET_MEET").replace(" ", "-"),
        }
