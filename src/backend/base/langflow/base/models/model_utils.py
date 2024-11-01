import importlib

from langflow.base.models.model import LCModelComponent
from langflow.inputs.inputs import InputTypes


def get_model_info() -> dict[str, dict[str, str | list[InputTypes]]]:
    """Get inputs for all model components."""
    model_inputs = {}
    models_module = importlib.import_module("langflow.components.models")
    model_component_names = getattr(models_module, "__all__", [])

    for name in model_component_names:
        if name in ("base", "DynamicLLMComponent"):  # Skip the base module
            continue

        component_class = getattr(models_module, name)
        if issubclass(component_class, LCModelComponent):
            component = component_class()
            base_input_names = {input_field.name for input_field in LCModelComponent._base_inputs}
            input_fields_list = [
                input_field for input_field in component.inputs if input_field.name not in base_input_names
            ]
            component_display_name = component.display_name
            model_inputs[name] = {
                "display_name": component_display_name,
                "inputs": input_fields_list,
                "icon": component.icon,
            }

    return model_inputs
