from typing import Optional

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


class LLMFrontendNode(FrontendNode):
    @staticmethod
    def format_openai_field(field: TemplateField):
        if "openai" in field.name.lower():
            field.display_name = (
                field.name.title().replace("Openai", "OpenAI").replace("_", " ")
            ).replace("Api", "API")

    @staticmethod
    def format_azure_field(field: TemplateField):
        if field.name == "model_name":
            field.show = False  # Azure uses deployment_name instead of model_name.
        if field.name == "openai_api_type":
            field.show = False
            field.password = False
            field.value = "azure"
        if field.name == "openai_api_version":
            field.password = False
            field.value = "2023-03-15-preview"

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        display_names_dict = {
            "huggingfacehub_api_token": "HuggingFace Hub API Token",
        }
        FrontendNode.format_field(field, name)
        SHOW_FIELDS = ["repo_id"]
        if field.name in SHOW_FIELDS:
            field.show = True

        if "api" in field.name and ("key" in field.name or "token" in field.name):
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
            field.options = ["text-generation", "text2text-generation"]
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

        LLMFrontendNode.format_openai_field(field)
        if "azure" in name.lower():
            LLMFrontendNode.format_azure_field(field)
