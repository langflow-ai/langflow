from langflow.components.models.huggingface import HuggingFaceEndpointsComponent
from langflow.inputs.inputs import DictInput, DropdownInput, FloatInput, HandleInput, IntInput, SecretStrInput, StrInput


def test_huggingface_inputs():
    component = HuggingFaceEndpointsComponent()
    inputs = component.inputs

    # Define expected input types and their names
    expected_inputs = {
        "model_id": StrInput,
        "max_new_tokens": IntInput,
        "top_k": IntInput,
        "top_p": FloatInput,
        "typical_p": FloatInput,
        "temperature": FloatInput,
        "repetition_penalty": FloatInput,
        "inference_endpoint": StrInput,
        "task": DropdownInput,
        "huggingfacehub_api_token": SecretStrInput,
        "model_kwargs": DictInput,
        "retry_attempts": IntInput,
        "output_parser": HandleInput,
    }

    # Check if all expected inputs are present
    for name, input_type in expected_inputs.items():
        assert any(
            isinstance(inp, input_type) and inp.name == name for inp in inputs
        ), f"Missing or incorrect input: {name}"
