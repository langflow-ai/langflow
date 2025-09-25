from lfx.components.huggingface.huggingface import DEFAULT_MODEL, HuggingFaceEndpointsComponent
from lfx.inputs.inputs import DictInput, DropdownInput, FloatInput, IntInput, SecretStrInput, SliderInput, StrInput


def test_huggingface_inputs():
    component = HuggingFaceEndpointsComponent()
    inputs = component.inputs

    # Define expected input types and their names
    expected_inputs = {
        "model_id": DropdownInput,
        "custom_model": StrInput,
        "max_new_tokens": IntInput,
        "top_k": IntInput,
        "top_p": FloatInput,
        "typical_p": FloatInput,
        "temperature": SliderInput,
        "repetition_penalty": FloatInput,
        "inference_endpoint": StrInput,
        "task": DropdownInput,
        "huggingfacehub_api_token": SecretStrInput,
        "model_kwargs": DictInput,
        "retry_attempts": IntInput,
    }

    # Check if all expected inputs are present and have correct type
    for name, input_type in expected_inputs.items():
        matching_inputs = [inp for inp in inputs if isinstance(inp, input_type) and inp.name == name]
        assert matching_inputs, f"Missing or incorrect input: {name} {input_type}"

        if name == "model_id":
            input_field = matching_inputs[0]
            assert input_field.value == DEFAULT_MODEL
            assert "custom" in input_field.options
            assert input_field.required is True
            assert input_field.real_time_refresh is True
        elif name == "custom_model":
            input_field = matching_inputs[0]
            assert input_field.show is False
            assert input_field.required is True
        elif name == "temperature":
            input_field = matching_inputs[0]
            assert input_field.value == 0.8
            assert input_field.range_spec.min == 0
            assert input_field.range_spec.max == 2
            assert input_field.range_spec.step == 0.01
