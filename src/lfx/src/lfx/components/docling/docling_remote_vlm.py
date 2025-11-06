from typing import Any

import requests
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import (
    ApiVlmOptions,
    ResponseFormat,
    VlmPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline
from langflow.base.data import BaseFileComponent
from langflow.inputs import DropdownInput, SecretStrInput, StrInput
from langflow.schema import Data
from langflow.schema.dotdict import dotdict

from lfx.components.ibm.watsonx import WatsonxAIComponent
from lfx.log.logger import logger


class DoclingRemoteVLMComponent(BaseFileComponent):
    display_name = "Docling Remote VLM"
    description = (
        "Uses Docling to process input documents running a VLM pipeline with a remote model"
        "(OpenAI-compatible API or IBM Cloud)."
    )
    documentation = "https://docling-project.github.io/docling/examples/vlm_pipeline_api_model/"
    trace_type = "tool"
    icon = "Docling"
    name = "DoclingRemoteVLM"

    # https://docling-project.github.io/docling/usage/supported_formats/
    VALID_EXTENSIONS = [
        "adoc",
        "asciidoc",
        "asc",
        "bmp",
        "csv",
        "dotx",
        "dotm",
        "docm",
        "docx",
        "htm",
        "html",
        "jpeg",
        "json",
        "md",
        "pdf",
        "png",
        "potx",
        "ppsx",
        "pptm",
        "potm",
        "ppsm",
        "pptx",
        "tiff",
        "txt",
        "xls",
        "xlsx",
        "xhtml",
        "xml",
        "webp",
    ]

    inputs = [
        *BaseFileComponent.get_base_inputs(),
        DropdownInput(
            name="provider",
            display_name="Provider",
            info="Select which remote VLM provider to use.",
            options=["IBM Cloud", "OpenAI-Compatible"],
            value="IBM Cloud",
            real_time_refresh=True,
        ),
        # IBM Cloud inputs
        SecretStrInput(
            name="watsonx_api_key",
            display_name="Watsonx API Key",
            info="IBM Cloud API key used for authentication (leave blank to load from .env).",
            required=False,
        ),
        StrInput(
            name="watsonx_project_id",
            display_name="Watsonx Project ID",
            required=False,
            info="The Watsonx project ID or deployment space ID associated with the model.",
            value="",
        ),
        DropdownInput(
            name="url",
            display_name="Watsonx API Endpoint",
            info="The base URL of the Watsonx API.",
            options=[
                "https://us-south.ml.cloud.ibm.com",
                "https://eu-de.ml.cloud.ibm.com",
                "https://eu-gb.ml.cloud.ibm.com",
                "https://au-syd.ml.cloud.ibm.com",
                "https://jp-tok.ml.cloud.ibm.com",
                "https://ca-tor.ml.cloud.ibm.com",
            ],
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=[],
            value=None,
            dynamic=True,
            required=False,
        ),
        # OpenAI inputs
        StrInput(
            name="openai_base_url",
            display_name="OpenAI-Compatible API Base URL",
            info="Example: https://openrouter.ai/api/",
            required=False,
            show=False,
        ),
        SecretStrInput(
            name="openai_api_key",
            display_name="API Key",
            info="API key for OpenAI-compatible endpoints (leave blank if not required).",
            required=False,
            show=False,
        ),
        StrInput(
            name="openai_model",
            display_name="OpenAI Model Name",
            info="Model ID for OpenAI-compatible provider (e.g. gpt-4o-mini).",
            required=False,
            show=False,
        ),
        StrInput(name="vlm_prompt", display_name="Prompt", info="Prompt for VLM.", required=False),
    ]

    outputs = [*BaseFileComponent.get_base_outputs()]

    @staticmethod
    def fetch_models(base_url: str) -> list[str]:
        """Fetch available models from the Watsonx.ai API."""
        try:
            endpoint = f"{base_url}/ml/v1/foundation_model_specs"
            params = {"version": "2024-09-16", "filters": "function_text_chat,!lifecycle_withdrawn"}
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [model["model_id"] for model in data.get("resources", [])]
            return sorted(models)
        except (requests.RequestException, requests.HTTPError, requests.Timeout, ConnectionError, ValueError):
            logger.exception("Error fetching models. Using default models.")
            return WatsonxAIComponent._default_models  # noqa: SLF001

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        """Update shown fields based on chosen provider."""
        logger.info(f"update_build_config called: field_name={field_name}, field_value={field_value}")

        if field_name == "provider":
            provider_choice = field_value

            if provider_choice == "IBM Cloud":
                build_config.model_name.show = True
                build_config.watsonx_api_key.show = True
                build_config.watsonx_project_id.show = True
                build_config.url.show = True

                build_config.openai_base_url.show = False
                build_config.openai_api_key.show = False
                build_config.openai_model.show = False

            elif provider_choice == "OpenAI-Compatible":
                build_config.model_name.show = False
                build_config.watsonx_api_key.show = False
                build_config.watsonx_project_id.show = False
                build_config.url.show = False

                build_config.openai_base_url.show = True
                build_config.openai_api_key.show = True
                build_config.openai_model.show = True

        if field_name == "url":
            provider_value = build_config.provider.value if hasattr(build_config, "provider") else None
            if provider_value == "IBM Cloud" and field_value:
                models = self.fetch_models(base_url=field_value)
                build_config.model_name.options = models
                if models:
                    build_config.model_name.value = models[0]
                logger.info(f"Updated Watsonx model list: {len(models)} models found.")

    def watsonx_vlm_options(self, model: str, prompt: str):
        """Creates Docling ApiVlmOptions for a watsonx VLM."""
        api_key = getattr(self, "watsonx_api_key", "")
        project_id = getattr(self, "watsonx_project_id", "")
        base_url = getattr(self, "url", "https://us-south.ml.cloud.ibm.com")

        def _get_iam_access_token(api_key: str) -> str:
            res = requests.post(
                url="https://iam.cloud.ibm.com/identity/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=f"grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={api_key}",
                timeout=90,
            )
            res.raise_for_status()
            return res.json()["access_token"]

        access_token = _get_iam_access_token(api_key)
        return ApiVlmOptions(
            url=f"{base_url}/ml/v1/text/chat?version=2023-05-29",
            params={"model_id": model, "project_id": project_id, "parameters": {"max_new_tokens": 400}},
            headers={"Authorization": f"Bearer {access_token}"},
            prompt=prompt,
            timeout=60,
            response_format=ResponseFormat.MARKDOWN,
        )

    def openai_compatible_vlm_options(
        self,
        model: str,
        prompt: str,
        response_format: ResponseFormat,
        url: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        api_key: str = "",
        *,
        skip_special_tokens: bool = False,
    ):
        """Create OpenAI-compatible Docling ApiVlmOptions options (e.g., LM Studio, vLLM, Ollama)."""
        api_key = getattr(self, "openai_api_key", api_key)
        model_override = getattr(self, "openai_model", model)

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        return ApiVlmOptions(
            url=f"{url}/v1/chat/completions",
            params={"model": model_override, "max_tokens": max_tokens, "skip_special_tokens": skip_special_tokens},
            headers=headers,
            prompt=prompt,
            timeout=90,
            scale=2.0,
            temperature=temperature,
            response_format=response_format,
        )

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        file_paths = [file.path for file in file_list if file.path]
        if not file_paths:
            logger.warning("No files to process.")
            return file_list

        provider = getattr(self, "provider", "IBM Cloud")
        prompt = getattr(self, "vlm_prompt", "")

        if provider == "IBM Cloud":
            model = getattr(self, "model_name", "")
            vlm_opts = self.watsonx_vlm_options(model=model, prompt=prompt)
        else:
            model = getattr(self, "openai_model", "") or getattr(self, "model_name", "")
            base_url = getattr(self, "openai_base_url", "")
            vlm_opts = self.openai_compatible_vlm_options(
                model=model,
                prompt=prompt,
                response_format=ResponseFormat.MARKDOWN,
                url=base_url,
            )

        pipeline_options = VlmPipelineOptions(enable_remote_services=True)
        pipeline_options.vlm_options = vlm_opts

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options, pipeline_cls=VlmPipeline)
            }
        )

        results = converter.convert_all(file_paths)
        processed_data = [
            Data(data={"doc": res.document, "file_path": str(res.input.file)})
            if res.status == ConversionStatus.SUCCESS
            else None
            for res in results
        ]
        return self.rollup_data(file_list, processed_data)
