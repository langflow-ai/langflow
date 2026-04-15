import json
from typing import Any

import requests
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.inputs.inputs import SecretStrInput, StrInput
from lfx.schema.data import Data


class HomeAssistantControl(LCToolComponent):
    """This tool is used to control Home Assistant devices.

    A very simple tool to control Home Assistant devices.
    - The agent only needs to provide action (turn_on, turn_off, toggle) + entity_id (e.g., switch.xxx, light.xxx).
    - The domain (e.g., 'switch', 'light') is automatically extracted from entity_id.
    """

    display_name: str = "Home Assistant Control"
    description: str = (
        "A very simple tool to control Home Assistant devices. "
        "Only action (turn_on, turn_off, toggle) and entity_id need to be provided."
    )
    documentation: str = "https://developers.home-assistant.io/docs/api/rest/"
    icon: str = "HomeAssistant"

    # --- Input fields for LangFlow UI (token, URL) ---
    inputs = [
        SecretStrInput(
            name="ha_token",
            display_name="Home Assistant Token",
            info="Home Assistant Long-Lived Access Token",
            required=True,
        ),
        StrInput(
            name="base_url",
            display_name="Home Assistant URL",
            info="e.g., http://192.168.0.10:8123",
            required=True,
        ),
        StrInput(
            name="default_action",
            display_name="Default Action (Optional)",
            info="One of turn_on, turn_off, toggle",
            required=False,
        ),
        StrInput(
            name="default_entity_id",
            display_name="Default Entity ID (Optional)",
            info="Default entity ID to control (e.g., switch.unknown_switch_3)",
            required=False,
        ),
    ]

    # --- Parameters exposed to the agent (Pydantic schema) ---
    class ToolSchema(BaseModel):
        """Parameters to be passed by the agent: action, entity_id only."""

        action: str = Field(..., description="Home Assistant service name. (One of turn_on, turn_off, toggle)")
        entity_id: str = Field(
            ...,
            description="Entity ID to control (e.g., switch.xxx, light.xxx, cover.xxx, etc.)."
            "Do not infer; use the list_homeassistant_states tool to retrieve it.",
        )

    def run_model(self) -> Data:
        """Used when the 'Run' button is clicked in LangFlow.

        - Uses default_action and default_entity_id entered in the UI.
        """
        action = self.default_action or "turn_off"
        entity_id = self.default_entity_id or "switch.unknown_switch_3"

        result = self._control_device(
            ha_token=self.ha_token,
            base_url=self.base_url,
            action=action,
            entity_id=entity_id,
        )
        return self._make_data_response(result)

    def build_tool(self) -> Tool:
        """Returns a tool to be used by the agent (LLM).

        - The agent can only pass action and entity_id as arguments.
        """
        return StructuredTool.from_function(
            name="home_assistant_control",
            description=(
                "A tool to control Home Assistant devices easily. "
                "Parameters: action ('turn_on'/'turn_off'/'toggle'), entity_id ('switch.xxx', etc.)."
                "Entity ID must be obtained using the list_homeassistant_states tool and not guessed."
            ),
            func=self._control_device_for_tool,  # Wrapper function below
            args_schema=self.ToolSchema,
        )

    def _control_device_for_tool(self, action: str, entity_id: str) -> dict[str, Any] | str:
        """Function called by the agent.

        -> Internally calls _control_device.
        """
        return self._control_device(
            ha_token=self.ha_token,
            base_url=self.base_url,
            action=action,
            entity_id=entity_id,
        )

    def _control_device(
        self,
        ha_token: str,
        base_url: str,
        action: str,
        entity_id: str,
    ) -> dict[str, Any] | str:
        """Actual logic to call the Home Assistant service.

        The domain is extracted from the beginning of the entity_id.
        Example: entity_id="switch.unknown_switch_3" -> domain="switch".
        """
        try:
            domain = entity_id.split(".")[0]  # switch, light, cover, etc.
            url = f"{base_url}/api/services/{domain}/{action}"

            headers = {
                "Authorization": f"Bearer {ha_token}",
                "Content-Type": "application/json",
            }
            payload = {"entity_id": entity_id}

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()

            return response.json()  # HA response JSON on success
        except requests.exceptions.RequestException as e:
            return f"Error: Failed to call service. {e}"
        except Exception as e:  # noqa: BLE001
            return f"An unexpected error occurred: {e}"

    def _make_data_response(self, result: dict[str, Any] | str) -> Data:
        """Returns a response in the LangFlow Data format."""
        if isinstance(result, str):
            # Handle error messages
            return Data(text=result)

        # Convert dict to JSON string
        formatted_json = json.dumps(result, indent=2, ensure_ascii=False)
        return Data(data=result, text=formatted_json)
