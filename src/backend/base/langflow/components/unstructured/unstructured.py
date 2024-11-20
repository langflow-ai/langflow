from pathlib import Path

from langchain_unstructured import UnstructuredLoader

from langflow.base.data import BaseFileComponent
from langflow.inputs import MessageTextInput, NestedDictInput, SecretStrInput
from langflow.schema import Data


class UnstructuredComponent(BaseFileComponent):
    display_name = "Unstructured API"
    description = (
        "Uses Unstructured.io API to extract clean text from raw source documents. "
        "Supports a wide range of file types."
    )
    documentation = (
        "https://python.langchain.com/api_reference/unstructured/document_loaders/"
        "langchain_unstructured.document_loaders.UnstructuredLoader.html"
    )
    trace_type = "tool"
    icon = "Unstructured"
    name = "Unstructured"

    # https://docs.unstructured.io/api-reference/api-services/overview#supported-file-types
    VALID_EXTENSIONS = [
        "bmp",
        "csv",
        "doc",
        "docx",
        "eml",
        "epub",
        "heic",
        "html",
        "jpeg",
        "png",
        "md",
        "msg",
        "odt",
        "org",
        "p7s",
        "pdf",
        "png",
        "ppt",
        "pptx",
        "rst",
        "rtf",
        "tiff",
        "txt",
        "tsv",
        "xls",
        "xlsx",
        "xml",
    ]

    inputs = [
        *BaseFileComponent._base_inputs,
        SecretStrInput(
            name="api_key",
            display_name="Unstructured.io Serverless API Key",
            required=True,
            info="Unstructured API Key. Create at: https://app.unstructured.io/",
        ),
        MessageTextInput(
            name="api_url",
            display_name="Unstructured.io API URL",
            required=False,
            info="Unstructured API URL.",
        ),
        NestedDictInput(
            name="unstructured_args",
            display_name="Additional Arguments",
            required=False,
            info=(
                "Optional dictionary of additional arguments to the Loader. "
                "See https://docs.unstructured.io/api-reference/api-services/api-parameters for more information."
            ),
        ),
    ]

    outputs = [
        *BaseFileComponent._base_outputs,
    ]

    def process_files(self, file_list: list[Path]) -> list[Data]:
        # https://docs.unstructured.io/api-reference/api-services/api-parameters
        args = self.unstructured_args or {}

        args["api_key"] = self.api_key
        args["partition_via_api"] = True
        if self.api_url:
            args["url"] = self.api_url

        loader = UnstructuredLoader(
            file_list,
            **args,
        )

        self.log(f"file_list: {file_list}")

        documents = loader.load()

        data = [Data.from_document(doc) for doc in documents]  # Using the from_document method of Data

        self.status = data

        return data
