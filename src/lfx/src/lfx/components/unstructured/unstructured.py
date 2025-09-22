from langchain_unstructured import UnstructuredLoader

from lfx.base.data.base_file import BaseFileComponent
from lfx.inputs.inputs import DropdownInput, MessageTextInput, NestedDictInput, SecretStrInput
from lfx.schema.data import Data


class UnstructuredComponent(BaseFileComponent):
    display_name = "Unstructured API"
    description = (
        "Uses Unstructured.io API to extract clean text from raw source documents. Supports a wide range of file types."
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
        *BaseFileComponent.get_base_inputs(),
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
        DropdownInput(
            name="chunking_strategy",
            display_name="Chunking Strategy",
            info="Chunking strategy to use, see https://docs.unstructured.io/api-reference/api-services/chunking",
            options=["", "basic", "by_title", "by_page", "by_similarity"],
            real_time_refresh=False,
            value="",
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
        *BaseFileComponent.get_base_outputs(),
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        file_paths = [str(file.path) for file in file_list if file.path]

        if not file_paths:
            self.log("No files to process.")
            return file_list

        # https://docs.unstructured.io/api-reference/api-services/api-parameters
        args = self.unstructured_args or {}

        if self.chunking_strategy:
            args["chunking_strategy"] = self.chunking_strategy

        args["api_key"] = self.api_key
        args["partition_via_api"] = True
        if self.api_url:
            args["url"] = self.api_url

        loader = UnstructuredLoader(
            file_paths,
            **args,
        )

        documents = loader.load()

        processed_data: list[Data | None] = [Data.from_document(doc) if doc else None for doc in documents]

        # Rename the `source` field to `self.SERVER_FILE_PATH_FIELDNAME`, to avoid conflicts with the `source` field
        for data in processed_data:
            if data and "source" in data.data:
                data.data[self.SERVER_FILE_PATH_FIELDNAME] = data.data.pop("source")

        return self.rollup_data(file_list, processed_data)
