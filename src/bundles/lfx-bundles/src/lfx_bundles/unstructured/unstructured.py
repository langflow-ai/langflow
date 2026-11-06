import os
from contextlib import ExitStack

import httpx
from langchain_unstructured import UnstructuredLoader
from lfx.base.data.base_file import BaseFileComponent
from lfx.base.models.provider_ssrf import ensure_credential_endpoint_allowed, provider_httpx_client_kwargs
from lfx.inputs.inputs import DropdownInput, MessageTextInput, NestedDictInput, SecretStrInput
from lfx.schema.data import Data
from unstructured_client import UnstructuredClient

DEFAULT_UNSTRUCTURED_ENDPOINT = "https://api.unstructuredapp.io/general/v0/general"


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
        args = dict(self.unstructured_args or {})
        if "client" in args:
            msg = "Set the Unstructured API URL and key instead of supplying a client."
            raise ValueError(msg)

        if self.chunking_strategy:
            args["chunking_strategy"] = self.chunking_strategy

        api_key = self.api_key or os.getenv("UNSTRUCTURED_API_KEY") or ""
        endpoint = self.api_url or args.get("url") or os.getenv("UNSTRUCTURED_URL") or DEFAULT_UNSTRUCTURED_ENDPOINT
        ensure_credential_endpoint_allowed(api_key, endpoint, default_url=DEFAULT_UNSTRUCTURED_ENDPOINT)
        sync_kwargs, _ = provider_httpx_client_kwargs(endpoint, default_url=DEFAULT_UNSTRUCTURED_ENDPOINT)
        args["api_key"] = api_key
        args["partition_via_api"] = True
        args["url"] = endpoint

        with ExitStack() as stack:
            if sync_kwargs:
                client = stack.enter_context(httpx.Client(**sync_kwargs))
                args["client"] = UnstructuredClient(api_key_auth=api_key, server_url=endpoint, client=client)
                args.pop("api_key")
                args.pop("url")
            loader = UnstructuredLoader(file_paths, **args)
            documents = loader.load()

        processed_data: list[Data | None] = [Data.from_document(doc) if doc else None for doc in documents]

        # Rename the `source` field to `self.SERVER_FILE_PATH_FIELDNAME`, to avoid conflicts with the `source` field
        for data in processed_data:
            if data and "source" in data.data:
                data.data[self.SERVER_FILE_PATH_FIELDNAME] = data.data.pop("source")

        return self.rollup_data(file_list, processed_data)
