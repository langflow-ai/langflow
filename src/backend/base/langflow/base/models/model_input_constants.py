from typing_extensions import TypedDict

from langflow.base.models.model import LCModelComponent
from langflow.components.models.amazon_bedrock import AmazonBedrockComponent
from langflow.components.models.anthropic import AnthropicModelComponent
from langflow.components.models.azure_openai import AzureChatOpenAIComponent
from langflow.components.models.google_generative_ai import GoogleGenerativeAIComponent
from langflow.components.models.groq import GroqModel
from langflow.components.models.nvidia import NVIDIAModelComponent
from langflow.components.models.openai import OpenAIModelComponent
from langflow.inputs.inputs import InputTypes, SecretStrInput
from langflow.template.field.base import Input


class ModelProvidersDict(TypedDict):
    fields: dict
    inputs: list[InputTypes]
    prefix: str
    component_class: LCModelComponent


def get_filtered_inputs(component_class):
    base_input_names = {field.name for field in LCModelComponent._base_inputs}
    component_instance = component_class()

    return [process_inputs(input_) for input_ in component_instance.inputs if input_.name not in base_input_names]


def process_inputs(component_data: Input):
    if isinstance(component_data, SecretStrInput):
        component_data.value = ""
        component_data.load_from_db = False
    elif component_data.name in {"temperature", "tool_model_enabled", "base_url"}:
        component_data = set_advanced_true(component_data)
    elif component_data.name == "model_name":
        component_data = set_real_time_refresh_false(component_data)
        component_data = add_combobox_true(component_data)
        component_data = add_info(
            component_data,
            "To see the model names, first choose a provider. Then, enter your API key and click the refresh button "
            "next to the model name.",
        )
    return component_data


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


def set_real_time_refresh_false(component_input):
    component_input.real_time_refresh = False
    return component_input


def add_info(component_input, info_str: str):
    component_input.info = info_str
    return component_input


def add_combobox_true(component_input):
    component_input.combobox = True
    return component_input


def create_input_fields_dict(inputs: list[Input], prefix: str) -> dict[str, Input]:
    return {f"{prefix}{input_.name}": input_.to_dict() for input_ in inputs}


def _get_google_generative_ai_inputs_and_fields():
    try:
        from langflow.components.models.google_generative_ai import GoogleGenerativeAIComponent

        google_generative_ai_inputs = get_filtered_inputs(GoogleGenerativeAIComponent)
    except ImportError as e:
        msg = (
            "Google Generative AI is not installed. Please install it with "
            "`pip install langchain-google-generative-ai`."
        )
        raise ImportError(msg) from e
    return google_generative_ai_inputs, create_input_fields_dict(google_generative_ai_inputs, "")


def _get_openai_inputs_and_fields():
    try:
        from langflow.components.models.openai import OpenAIModelComponent

        openai_inputs = get_filtered_inputs(OpenAIModelComponent)
    except ImportError as e:
        msg = "OpenAI is not installed. Please install it with `pip install langchain-openai`."
        raise ImportError(msg) from e
    return openai_inputs, create_input_fields_dict(openai_inputs, "")


def _get_azure_inputs_and_fields():
    try:
        from langflow.components.models.azure_openai import AzureChatOpenAIComponent

        azure_inputs = get_filtered_inputs(AzureChatOpenAIComponent)
    except ImportError as e:
        msg = "Azure OpenAI is not installed. Please install it with `pip install langchain-azure-openai`."
        raise ImportError(msg) from e
    return azure_inputs, create_input_fields_dict(azure_inputs, "")


def _get_groq_inputs_and_fields():
    try:
        from langflow.components.models.groq import GroqModel

        groq_inputs = get_filtered_inputs(GroqModel)
    except ImportError as e:
        msg = "Groq is not installed. Please install it with `pip install langchain-groq`."
        raise ImportError(msg) from e
    return groq_inputs, create_input_fields_dict(groq_inputs, "")


def _get_anthropic_inputs_and_fields():
    try:
        from langflow.components.models.anthropic import AnthropicModelComponent

        anthropic_inputs = get_filtered_inputs(AnthropicModelComponent)
    except ImportError as e:
        msg = "Anthropic is not installed. Please install it with `pip install langchain-anthropic`."
        raise ImportError(msg) from e
    return anthropic_inputs, create_input_fields_dict(anthropic_inputs, "")


def _get_nvidia_inputs_and_fields():
    try:
        from langflow.components.models.nvidia import NVIDIAModelComponent

        nvidia_inputs = get_filtered_inputs(NVIDIAModelComponent)
    except ImportError as e:
        msg = "NVIDIA is not installed. Please install it with `pip install langchain-nvidia`."
        raise ImportError(msg) from e
    return nvidia_inputs, create_input_fields_dict(nvidia_inputs, "")


def _get_amazon_bedrock_inputs_and_fields():
    try:
        from langflow.components.models.amazon_bedrock import AmazonBedrockComponent

        amazon_bedrock_inputs = get_filtered_inputs(AmazonBedrockComponent)
    except ImportError as e:
        msg = "Amazon Bedrock is not installed. Please install it with `pip install langchain-amazon-bedrock`."
        raise ImportError(msg) from e
    return amazon_bedrock_inputs, create_input_fields_dict(amazon_bedrock_inputs, "")


MODEL_PROVIDERS_DICT: dict[str, ModelProvidersDict] = {}

# Try to add each provider
try:
    openai_inputs, openai_fields = _get_openai_inputs_and_fields()
    MODEL_PROVIDERS_DICT["OpenAI"] = {
        "fields": openai_fields,
        "inputs": openai_inputs,
        "prefix": "",
        "component_class": OpenAIModelComponent(),
    }
except ImportError:
    pass

try:
    azure_inputs, azure_fields = _get_azure_inputs_and_fields()
    MODEL_PROVIDERS_DICT["Azure OpenAI"] = {
        "fields": azure_fields,
        "inputs": azure_inputs,
        "prefix": "",
        "component_class": AzureChatOpenAIComponent(),
    }
except ImportError:
    pass

try:
    groq_inputs, groq_fields = _get_groq_inputs_and_fields()
    MODEL_PROVIDERS_DICT["Groq"] = {
        "fields": groq_fields,
        "inputs": groq_inputs,
        "prefix": "",
        "component_class": GroqModel(),
    }
except ImportError:
    pass

try:
    anthropic_inputs, anthropic_fields = _get_anthropic_inputs_and_fields()
    MODEL_PROVIDERS_DICT["Anthropic"] = {
        "fields": anthropic_fields,
        "inputs": anthropic_inputs,
        "prefix": "",
        "component_class": AnthropicModelComponent(),
    }
except ImportError:
    pass

try:
    nvidia_inputs, nvidia_fields = _get_nvidia_inputs_and_fields()
    MODEL_PROVIDERS_DICT["NVIDIA"] = {
        "fields": nvidia_fields,
        "inputs": nvidia_inputs,
        "prefix": "",
        "component_class": NVIDIAModelComponent(),
    }
except ImportError:
    pass

try:
    bedrock_inputs, bedrock_fields = _get_amazon_bedrock_inputs_and_fields()
    MODEL_PROVIDERS_DICT["Amazon Bedrock"] = {
        "fields": bedrock_fields,
        "inputs": bedrock_inputs,
        "prefix": "",
        "component_class": AmazonBedrockComponent(),
    }
except ImportError:
    pass

try:
    google_generative_ai_inputs, google_generative_ai_fields = _get_google_generative_ai_inputs_and_fields()
    MODEL_PROVIDERS_DICT["Google Generative AI"] = {
        "fields": google_generative_ai_fields,
        "inputs": google_generative_ai_inputs,
        "prefix": "",
        "component_class": GoogleGenerativeAIComponent(),
    }
except ImportError:
    pass

MODEL_PROVIDERS = list(MODEL_PROVIDERS_DICT.keys())
ALL_PROVIDER_FIELDS: list[str] = [field for provider in MODEL_PROVIDERS_DICT.values() for field in provider["fields"]]

MODEL_DYNAMIC_UPDATE_FIELDS = ["api_key", "model", "tool_model_enabled", "base_url", "model_name"]
