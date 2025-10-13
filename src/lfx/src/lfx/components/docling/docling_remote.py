import base64
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
from docling_core.types.doc import DoclingDocument
from pydantic import ValidationError

from lfx.base.data import BaseFileComponent
from lfx.inputs import IntInput, NestedDictInput, StrInput
from lfx.inputs.inputs import FloatInput
from lfx.schema import Data
from lfx.utils.util import transform_localhost_url


class DoclingRemoteComponent(BaseFileComponent):
    display_name = "Docling Serve"
    description = "Uses Docling to process input documents connecting to your instance of Docling Serve."
    documentation = "https://docling-project.github.io/docling/"
    trace_type = "tool"
    icon = "Docling"
    name = "DoclingRemote"

    MAX_500_RETRIES = 5

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
        StrInput(
            name="api_url",
            display_name="Server address",
            info="URL of the Docling Serve instance.",
            required=True,
        ),
        IntInput(
            name="max_concurrency",
            display_name="Concurrency",
            info="Maximum number of concurrent requests for the server.",
            advanced=True,
            value=2,
        ),
        FloatInput(
            name="max_poll_timeout",
            display_name="Maximum poll time",
            info="Maximum waiting time for the document conversion to complete.",
            advanced=True,
            value=3600,
        ),
        NestedDictInput(
            name="api_headers",
            display_name="HTTP headers",
            advanced=True,
            required=False,
            info=("Optional dictionary of additional headers required for connecting to Docling Serve."),
        ),
        NestedDictInput(
            name="docling_serve_opts",
            display_name="Docling options",
            advanced=True,
            required=False,
            info=(
                "Optional dictionary of additional options. "
                "See https://github.com/docling-project/docling-serve/blob/main/docs/usage.md for more information."
            ),
        ),
    ]

    outputs = [
        *BaseFileComponent.get_base_outputs(),
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        # Transform localhost URLs to container-accessible hosts when running in a container
        transformed_url = transform_localhost_url(self.api_url)
        base_url = f"{transformed_url}/v1"

        def _convert_document(client: httpx.Client, file_path: Path, options: dict[str, Any]) -> Data | None:
            encoded_doc = base64.b64encode(file_path.read_bytes()).decode()
            payload = {
                "options": options,
                "sources": [{"kind": "file", "base64_string": encoded_doc, "filename": file_path.name}],
            }

            response = client.post(f"{base_url}/convert/source/async", json=payload)
            response.raise_for_status()
            task = response.json()

            http_failures = 0
            retry_status_start = 500
            retry_status_end = 600
            start_wait_time = time.monotonic()
            while task["task_status"] not in ("success", "failure"):
                # Check if processing exceeds the maximum poll timeout
                processing_time = time.monotonic() - start_wait_time
                if processing_time >= self.max_poll_timeout:
                    msg = (
                        f"Processing time {processing_time=} exceeds the maximum poll timeout {self.max_poll_timeout=}."
                        "Please increase the max_poll_timeout parameter or review why the processing "
                        "takes long on the server."
                    )
                    self.log(msg)
                    raise RuntimeError(msg)

                # Call for a new status update
                time.sleep(2)
                response = client.get(f"{base_url}/status/poll/{task['task_id']}")

                # Check if the status call gets into 5xx errors and retry
                if retry_status_start <= response.status_code < retry_status_end:
                    http_failures += 1
                    if http_failures > self.MAX_500_RETRIES:
                        self.log(f"The status requests got a http response {response.status_code} too many times.")
                        return None
                    continue

                # Update task status
                task = response.json()

            result_resp = client.get(f"{base_url}/result/{task['task_id']}")
            result_resp.raise_for_status()
            result = result_resp.json()

            if "json_content" not in result["document"] or result["document"]["json_content"] is None:
                self.log("No JSON DoclingDocument found in the result.")
                return None

            try:
                doc = DoclingDocument.model_validate(result["document"]["json_content"])
                return Data(data={"doc": doc, "file_path": str(file_path)})
            except ValidationError as e:
                self.log(f"Error validating the document. {e}")
                return None

        docling_options = {
            "to_formats": ["json"],
            "image_export_mode": "placeholder",
            **(self.docling_serve_opts or {}),
        }

        processed_data: list[Data | None] = []
        with (
            httpx.Client(headers=self.api_headers) as client,
            ThreadPoolExecutor(max_workers=self.max_concurrency) as executor,
        ):
            futures: list[tuple[int, Future]] = []
            for i, file in enumerate(file_list):
                if file.path is None:
                    processed_data.append(None)
                    continue

                futures.append((i, executor.submit(_convert_document, client, file.path, docling_options)))

            for _index, future in futures:
                try:
                    result_data = future.result()
                    processed_data.append(result_data)
                except (httpx.HTTPStatusError, httpx.RequestError, KeyError, ValueError) as exc:
                    self.log(f"Docling remote processing failed: {exc}")
                    raise

        return self.rollup_data(file_list, processed_data)
