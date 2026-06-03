from __future__ import annotations

import base64
import json
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path  # noqa: TC003
from typing import Any

import httpx
from lfx.base.data import BaseFileComponent
from lfx.base.data.docling_utils import coerce_docling_document
from lfx.inputs import IntInput, NestedDictInput, StrInput, TableInput
from lfx.inputs.inputs import FloatInput
from lfx.schema import Data, DataFrame, dotdict
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
        "jpg",
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
        StrInput(
            name="task_id",
            display_name="Task ID",
            info=(
                "Optional task ID from a previous Docling Serve upload. "
                "If provided, file input is ignored and the component polls for this task's results."
            ),
            required=False,
        ),
        IntInput(
            name="max_concurrency",
            display_name="Concurrency",
            info="Maximum number of concurrent requests for the server.",
            advanced=True,
            value=2,
            input_types=["Message"],
        ),
        FloatInput(
            name="max_poll_timeout",
            display_name="Maximum poll time",
            info="Maximum waiting time for the document conversion to complete.",
            advanced=True,
            value=3600,
            input_types=["Message"],
        ),
        TableInput(
            name="api_headers",
            display_name="HTTP headers",
            advanced=True,
            required=False,
            info=("Optional headers required for connecting to Docling Serve."),
            table_schema=[
                {
                    "name": "key",
                    "display_name": "Key",
                    "type": "string",
                    "description": "Key name",
                },
                {
                    "name": "value",
                    "display_name": "Value",
                    "load_from_db": True,
                    "type": "string",
                    "description": "Value of the header",
                },
            ],
            value=[],
            real_time_refresh=True,
            input_types=["Data", "JSON"],
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
            input_types=["Message"],
        ),
    ]

    outputs = [
        *BaseFileComponent.get_base_outputs(),
    ]

    def build(self) -> DataFrame:
        # Static bundle validation cannot see BaseFileComponent's inherited output method.
        return self.load_files()

    @staticmethod
    def _add_header(headers: dict[str, str], key: Any, value: Any) -> None:
        key_str = str(key).strip()
        if not key_str or key_str == "None":
            return
        headers[key_str] = str(value)

    def _process_headers_input(self, headers_input: Any, component_headers_dict: dict[str, str]) -> None:
        if not headers_input:
            return

        items = headers_input if isinstance(headers_input, list) else [headers_input]

        for item in items:
            if not item:
                continue

            # Case 1: Data object
            if hasattr(item, "data") and isinstance(item.data, dict):
                data = item.data
                if "key" in data and "value" in data:
                    self._add_header(component_headers_dict, data["key"], data["value"])
                else:
                    # Fallback: merge all keys from Data object
                    for k, v in data.items():
                        if k not in ("text_key", "default_value"):
                            self._add_header(component_headers_dict, k, v)

            # Case 2: Dictionary (Table row)
            elif isinstance(item, dict):
                if "key" in item and "value" in item:
                    self._add_header(component_headers_dict, item["key"], item["value"])
                else:
                    # Fallback: merge all keys
                    for k, v in item.items():
                        self._add_header(component_headers_dict, k, v)

            # Case 3: Message object
            elif hasattr(item, "text") and isinstance(item.text, str):
                try:
                    parsed = json.loads(item.text)
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            self._add_header(component_headers_dict, k, v)
                except json.JSONDecodeError:
                    pass

    def _process_headers(self) -> dict[str, str]:
        """Process the headers input into a valid dictionary."""
        component_headers_dict: dict[str, str] = {}
        self._process_headers_input(self.api_headers, component_headers_dict)
        return component_headers_dict

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "api_headers":
            if isinstance(field_value, dict):
                build_config["api_headers"]["value"] = [{"key": k, "value": v} for k, v in field_value.items()]
                return build_config
            if field_value is None:
                build_config["api_headers"]["value"] = []
                return build_config

        # Default behavior
        return super().update_build_config(build_config, field_value, field_name)

    def _poll_and_fetch_result(
        self, client: httpx.Client, base_url: str, task_id: str, file_path: str | None = None
    ) -> Data | None:
        """Poll for task completion and fetch the result.

        Args:
            client: The HTTP client to use for requests.
            base_url: The base URL of the Docling Serve API.
            task_id: The task ID to poll for.
            file_path: Optional file path to include in the result data.

        Returns:
            Data object with the DoclingDocument, or None if processing failed.
        """
        http_failures = 0
        retry_status_start = 500
        retry_status_end = 600
        start_wait_time = time.monotonic()

        task_status = None
        while task_status not in ("success", "failure"):
            processing_time = time.monotonic() - start_wait_time
            if processing_time >= self.max_poll_timeout:
                msg = (
                    f"Processing time {processing_time=} exceeds the maximum poll timeout {self.max_poll_timeout=}."
                    "Please increase the max_poll_timeout parameter or review why the processing "
                    "takes long on the server."
                )
                self.log(msg)
                raise RuntimeError(msg)

            response = client.get(f"{base_url}/status/poll/{task_id}")

            if retry_status_start <= response.status_code < retry_status_end:
                http_failures += 1
                if http_failures > self.MAX_500_RETRIES:
                    self.log(f"The status requests got a http response {response.status_code} too many times.")
                    return None
                time.sleep(2)
                continue

            response.raise_for_status()
            task = response.json()
            task_status = task["task_status"]
            if task_status not in ("success", "failure"):
                time.sleep(2)

        result_resp = client.get(f"{base_url}/result/{task_id}")
        result_resp.raise_for_status()
        result = result_resp.json()

        if result.get("status") == "failure" or result.get("errors"):
            errors = result.get("errors", [])
            err_msg_list = []
            for err in errors:
                if isinstance(err, dict) and "error_message" in err:
                    err_msg_list.append(err["error_message"])
                elif isinstance(err, str):
                    err_msg_list.append(err)

            err_details = "; ".join(err_msg_list) if err_msg_list else "Unknown Docling processing error"

            msg = f"Docling processing failed: {err_details}"
            raise ValueError(msg)

        if "json_content" not in result["document"] or result["document"]["json_content"] is None:
            self.log("No JSON DoclingDocument found in the result.")
            return None

        try:
            doc = coerce_docling_document(result["document"]["json_content"])
            data_dict: dict[str, Any] = {"doc": doc}
            if file_path:
                data_dict["file_path"] = file_path
            return Data(data=data_dict)
        except Exception as e:  # noqa: BLE001
            self.log(f"Error validating the document. {e}")
            return None

    def _process_task_id(self) -> list[Data]:
        """Process an existing task by polling for status and retrieving results.

        Returns:
            List containing the result Data object, or empty list if processing failed.
        """
        transformed_url = transform_localhost_url(self.api_url)
        base_url = f"{transformed_url}/v1"

        with httpx.Client(headers=self._process_headers()) as client:
            result = self._poll_and_fetch_result(client, base_url, self.task_id)
            return [result] if result else []

    def load_files_base(self) -> list[Data]:
        """Load and process files, or poll an existing task if task_id is provided.

        Returns:
            list[Data]: Parsed data from the processed files or task.
        """
        if self.task_id:
            return self._process_task_id()
        return super().load_files_base()

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
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

            return self._poll_and_fetch_result(client, base_url, task["task_id"], str(file_path))

        docling_options = {
            "to_formats": ["json"],
            "image_export_mode": "placeholder",
            **(self.docling_serve_opts or {}),
        }

        processed_data: list[Data | None] = []
        with (
            httpx.Client(headers=self._process_headers()) as client,
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
