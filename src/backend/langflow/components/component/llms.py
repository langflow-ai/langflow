from typing import Optional

from langflow.components.field.base import TemplateField
from langflow.components.component.base import Component


class LLMComponent(Component):
    @staticmethod
    def format_openai_field(field: TemplateField):
        if "openai" in field.name.lower():
            field.display_name = (
                field.name.title().replace("Openai", "OpenAI").replace("_", " ")
            ).replace("Api", "API")

        if "key" not in field.name.lower() and "token" not in field.name.lower():
            field.password = False

    @staticmethod
    def format_azure_field(field: TemplateField):
        if field.name == "model_name":
            field.show = False  # Azure uses deployment_name instead of model_name.
        elif field.name == "openai_api_type":
            field.show = False
            field.password = False
            field.value = "azure"
        elif field.name == "openai_api_version":
            field.password = False

    @staticmethod
    def format_llama_field(field: TemplateField):
        field.show = True
        field.advanced = not field.required

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        display_names_dict = {
            "huggingfacehub_api_token": "HuggingFace Hub API Token",
        }
        Component.format_field(field, name)
        LLMComponent.format_openai_field(field)
        if name and "azure" in name.lower():
            LLMComponent.format_azure_field(field)
        if name and "llama" in name.lower():
            LLMComponent.format_llama_field(field)
        SHOW_FIELDS = ["repo_id"]
        if field.name in SHOW_FIELDS:
            field.show = True

        if "api" in field.name and (
            "key" in field.name
            or ("token" in field.name and "tokens" not in field.name)
        ):
            field.password = True
            field.show = True
            # Required should be False to support
            # loading the API key from environment variables
            field.required = False
            field.advanced = False

        if field.name == "task":
            field.required = True
            field.show = True
            field.is_list = True
            field.options = ["text-generation", "text2text-generation", "summarization"]
            field.value = field.options[0]
            field.advanced = True

        if display_name := display_names_dict.get(field.name):
            field.display_name = display_name
        if field.name == "model_kwargs":
            field.field_type = "code"
            field.advanced = True
            field.show = True
        elif field.name in [
            "model_name",
            "temperature",
            "model_file",
            "model_type",
            "deployment_name",
        ]:
            field.advanced = False
            field.show = True
