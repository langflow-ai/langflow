import traceback

from fastapi import HTTPException

from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template, get_instance_name
from langflow.inputs.inputs import MessageTextInput
from langflow.schema import Data


class ComponentCodeValidator(Component):
    display_name = "Component Code Validator"
    description = "Validates the code of a component."
    name = "ComponentCodeValidator"

    inputs = [
        MessageTextInput(name="component_code", display_name="Component Code", required=True),
    ]

    def validate_code(self) -> Data:
        try:
            component = Component(code=self.component_code)

            built_frontend_node, component_instance = build_custom_component_template(component)
            _type = get_instance_name(component_instance)
            return Data(frontend_node=built_frontend_node, type=_type)
        except HTTPException as e:
            if "error" in e.detail and "traceback" in e.detail:
                return Data(error=e.detail["error"], traceback=e.detail["traceback"])
            else:
                return Data(error=str(e), traceback=traceback.format_exc())
        except Exception as e:
            return Data(error=str(e), traceback=traceback.format_exc())
