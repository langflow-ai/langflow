from langflow.base.models.model import LCModelComponent
from langflow.components.models.amazon_bedrock import AmazonBedrockComponent
from langflow.components.models.anthropic import AnthropicModelComponent
from langflow.components.models.azure_openai import AzureChatOpenAIComponent
from langflow.components.models.groq import GroqModel
from langflow.components.models.nvidia import NVIDIAModelComponent
from langflow.components.models.ollama import ChatOllamaComponent
from langflow.components.models.openai import OpenAIModelComponent


def get_filtered_inputs(component_class):
    base_input_names = {field.name for field in LCModelComponent._base_inputs}
    return [
        set_advanced_true(input_) if input_.name == "temperature" else input_
        for input_ in component_class().inputs
        if input_.name not in base_input_names
    ]

# def get_filtered_inputs_aws(component_class):
#     base_input_names = {field.name for field in LCModelComponent._base_inputs}
#     required_input_names = {"aws_model_id", "aws_access_key_id", "aws_secret_access_key","aws_region_name"}
#     return [
#         set_advanced_true(input_) if input_.name == "temperature" else input_
#         for input_ in component_class().inputs
#         if input_.name in required_input_names and input_.name not in base_input_names
#     ]

def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


def create_input_fields_dict(inputs, prefix):
    return {f"{prefix}_{input_.name}": input_ for input_ in inputs}


OPENAI_INPUTS = get_filtered_inputs(OpenAIModelComponent)
AZURE_INPUTS = get_filtered_inputs(AzureChatOpenAIComponent)
GROQ_INPUTS = get_filtered_inputs(GroqModel)
ANTHROPIC_INPUTS = get_filtered_inputs(AnthropicModelComponent)
NVIDIA_INPUTS = get_filtered_inputs(NVIDIAModelComponent)
OLLAMA_INPUTS = get_filtered_inputs(ChatOllamaComponent)
BEDROCK_INPUTS = get_filtered_inputs(AmazonBedrockComponent)

OPENAI_FIELDS = {input_.name: input_ for input_ in OPENAI_INPUTS}


AZURE_FIELDS = create_input_fields_dict(AZURE_INPUTS, "azure")
GROQ_FIELDS = create_input_fields_dict(GROQ_INPUTS, "groq")
ANTHROPIC_FIELDS = create_input_fields_dict(ANTHROPIC_INPUTS, "anthropic")
NVIDIA_FIELDS = create_input_fields_dict(NVIDIA_INPUTS, "nvidia")
OLLAMA_FIELDS = create_input_fields_dict(OLLAMA_INPUTS, "ollama")
BEDROCK_FIELDS = create_input_fields_dict(BEDROCK_INPUTS, "aws")
MODEL_PROVIDERS = ["Azure OpenAI", "OpenAI", "Groq", "Anthropic", "NVIDIA", "OLLAMA"]

MODEL_PROVIDERS_DICT = {
    "Azure OpenAI": {
        "fields": AZURE_FIELDS,
        "inputs": AZURE_INPUTS,
        "prefix": "azure_",
        "component_class": AzureChatOpenAIComponent(),
    },
    "OpenAI": {
        "fields": OPENAI_FIELDS,
        "inputs": OPENAI_INPUTS,
        "prefix": "",
        "component_class": OpenAIModelComponent(),
    },
    "Groq": {"fields": GROQ_FIELDS, "inputs": GROQ_INPUTS, "prefix": "groq_", "component_class": GroqModel()},
    "Anthropic": {
        "fields": ANTHROPIC_FIELDS,
        "inputs": ANTHROPIC_INPUTS,
        "prefix": "anthropic_",
        "component_class": AnthropicModelComponent(),
    },
    "NVIDIA": {
        "fields": NVIDIA_FIELDS,
        "inputs": NVIDIA_INPUTS,
        "prefix": "nvidia_",
        "component_class": NVIDIAModelComponent(),
    },
    "Amazon Bedrock": {
        "fields": BEDROCK_FIELDS,
        "inputs": BEDROCK_INPUTS,
        "prefix": "aws_",
        "component_class": AmazonBedrockComponent(),
    },
    "OLLAMA": {
        "fields": OLLAMA_FIELDS,
        "inputs": OLLAMA_INPUTS,
        "prefix": "ollama_",
        "component_class": ChatOllamaComponent(),
    }
}
ALL_PROVIDER_FIELDS: list[str] = [field for provider in MODEL_PROVIDERS_DICT.values() for field in provider["fields"]]
