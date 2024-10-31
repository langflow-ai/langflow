from langflow.base.models.model import LCModelComponent
from langflow.base.models.model_constants import ModelConstants
from langflow.field_typing import LanguageModel
from langflow.inputs.inputs import InputTypes
from langflow.io import DropdownInput
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message


class DynamicLLMComponent(LCModelComponent):

    display_name: str = "LLM"
    description: str = "Load any LLM based on the selected provider."
    icon = "llm"
    name = "DynamicLLM"
    model_constants = ModelConstants()
    model_constants.initialize()

    inputs = [
        DropdownInput(
            name="provider",
            display_name="Provider",
            options=model_constants.PROVIDER_NAMES,
            value=model_constants.PROVIDER_NAMES[0],
            real_time_refresh=True,
            refresh_button=True,
        ),
        *LCModelComponent._base_inputs,
    ]

    def build_model(self) -> LanguageModel:
        """Build the model using the selected provider."""
        return self.get_llm(self.provider, self.model_constants.MODEL_INFO)

    def update_build_config(self, build_config: dotdict, field_value: str, field_name: str | None = None):
        if field_name == "provider":
            # Clear model-specific inputs
            base_input_names = {input_field.name for input_field in LCModelComponent._base_inputs}
            default_keys = ["code", "_type", *base_input_names]
            model_keys = {key for key in build_config if key not in ["provider", *default_keys]}
            for key in model_keys:
                del build_config[key]

            # Find the component class name from MODEL_INFO
            component_info = next(
                (info for info in self.model_constants.MODEL_INFO.values() if info["display_name"] == field_value), None
            )

            if component_info:
                # Update inputs based on the selected provider
                for input_field in component_info["inputs"]:
                    if isinstance(input_field, InputTypes):
                        build_config[input_field.name] = input_field.to_dict()

        return build_config

    async def get_response(self) -> Message:
        llm_model = self.build_model()
        if llm_model is None:
            msg = "No language model selected"
            raise ValueError(msg)

        # Implement the logic to get a response from the LLM
        # This is a placeholder for the actual implementation
        return Message(text="Response from the LLM")
