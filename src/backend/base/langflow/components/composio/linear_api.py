from typing import Any

from composio import Action

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs import (
    BoolInput,
    IntInput,
    MessageTextInput,
)
from langflow.logging import logger


class ComposioLinearAPIComponent(ComposioBaseComponent):
    display_name: str = "Linear"
    description: str = "Linear API"
    icon = "Linear"
    documentation: str = "https://docs.composio.dev"
    app_name = "linear"
    
    _actions_data: dict = {}
    
    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}
    
    _bool_variables = {}
    
    inputs = [
        *ComposioBaseComponent._base_inputs,
    ]
    
    def execute_action(self):
        """Execute action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            self._build_action_maps()
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else self.action
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

            return result.get("data", [])
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else str(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)

    def set_default_tools(self):
        self._default_tools = {
            self.sanitize_action_name("<default action 1>").replace(" ", "-"),
            self.sanitize_action_name("<default action 2>").replace(" ", "-"),
        }