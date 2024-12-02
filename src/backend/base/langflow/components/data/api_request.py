import asyncio
import json
import mimetypes
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

import httpx
import validators
from aiofile import async_open

from langflow.base.curl.parse import parse_context
from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DataInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    Output,
    TableInput,
)
from langflow.schema import Data
from langflow.schema.dotdict import dotdict


class APIRequestComponent(Component):
    display_name = "API Request"
    description = (
        "This component allows you to make HTTP requests to one or more URLs. "
        "You can provide headers and body as either dictionaries or Data objects. "
        "Additionally, you can append query parameters to the URLs.\n\n"
        "Note: Check advanced options for more settings."
    )
    icon = "Globe"
    name = "APIRequest"

    default_keys = ["urls", "method", "query_params"]

    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            list=True,
            info="Enter one or more URLs, separated by commas.",
        ),
        DropdownInput(
            name="method",
            display_name="Method",
            options=["GET", "POST", "PATCH", "PUT"],
            value="",
            info="The HTTP method to use (GET, POST, PATCH, PUT).",
            real_time_refresh=True,
        ),
        DataInput(
            name="query_params",
            display_name="Query Parameters",
            info="The query parameters to append to the URL.",
            tool_mode=True,
        ),
        TableInput(
            name="body",
            display_name="Body",
            info="The body to send with the request as a dictionary (for POST, PATCH, PUT).",
            table_schema=[
                {
                    "name": "key",
                    "display_name": "Key",
                    "type": "str",
                    "description": "Parameter name",
                },
                {
                    "name": "value",
                    "display_name": "Value",
                    "description": "Parameter value",
                },
            ],
            value=[],
            input_types=["Data"],
            tool_mode=True,
        ),
        TableInput(
            name="headers",
            display_name="Headers",
            info="The headers to send with the request as a dictionary.",
            table_schema=[
                {
                    "name": "key",
                    "display_name": "Header",
                    "type": "str",
                    "description": "Header name",
                },
                {
                    "name": "value",
                    "display_name": "Value",
                    "type": "str",
                    "description": "Header value",
                },
            ],
            value=[],
            advanced=True,
            input_types=["Data"],
            tool_mode=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            value=5,
            info="The timeout to use for the request.",
            advanced=True,
        ),
        BoolInput(
            name="follow_redirects",
            display_name="Follow Redirects",
            value=True,
            info="Whether to follow http redirects.",
            advanced=True,
        ),
        BoolInput(
            name="save_to_file",
            display_name="Save to File",
            value=False,
            info="Save the API response to a temporary file",
            advanced=True,
        ),
        BoolInput(
            name="include_httpx_metadata",
            display_name="Include HTTPx Metadata",
            value=False,
            info=(
                "Include properties such as headers, status_code, response_headers, "
                "and redirection_history in the output."
            ),
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="make_requests"),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "method":
            if field_value in ["POST", "PATCH", "PUT"]:
                build_config["body"]["advanced"] = False
            else:
                build_config["body"]["advanced"] = True
        return build_config

    async def make_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: dict | None = None,
        body: dict | None = None,
        timeout: int = 5,
        *,
        follow_redirects: bool = True,
        save_to_file: bool = False,
        include_httpx_metadata: bool = False,
    ) -> Data:
        method = method.upper()
        if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
            msg = f"Unsupported method: {method}"
            raise ValueError(msg)

        if isinstance(body, str) and body:
            try:
                body = json.loads(body)
            except Exception as e:
                msg = f"Error decoding JSON data: {e}"
                self.log.exception(msg)
                body = None
                raise ValueError(msg) from e

        data = body or None
        redirection_history = []

        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=data,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )

            redirection_history = [
                {"url": str(redirect.url), "status_code": redirect.status_code} for redirect in response.history
            ]

            if response.is_redirect:
                redirection_history.append({"url": str(response.url), "status_code": response.status_code})

            is_binary, file_path = self._response_info(response, with_file_path=save_to_file)
            response_headers = self._headers_to_dict(response.headers)

            metadata: dict[str, Any] = {
                "source": url,
            }

            if save_to_file:
                mode = "wb" if is_binary else "w"
                encoding = response.encoding if mode == "w" else None
                if file_path:
                    async with async_open(file_path, mode, encoding=encoding) as f:
                        await f.write(response.content if is_binary else response.text)

                if include_httpx_metadata:
                    metadata.update(
                        {
                            "file_path": str(file_path),
                            "headers": headers,
                            "status_code": response.status_code,
                            "response_headers": response_headers,
                            **({"redirection_history": redirection_history} if redirection_history else {}),
                        }
                    )
                return Data(data=metadata)

            if is_binary:
                result = response.content
            else:
                try:
                    result = response.json()
                except Exception:  # noqa: BLE001
                    self.log("Error decoding JSON response")
                    result = response.text.encode("utf-8")

            metadata.update({"result": result})

            if include_httpx_metadata:
                metadata.update(
                    {
                        "headers": headers,
                        "status_code": response.status_code,
                        "response_headers": response_headers,
                        **({"redirection_history": redirection_history} if redirection_history else {}),
                    }
                )
            return Data(data=metadata)
        except httpx.TimeoutException:
            return Data(
                data={
                    "source": url,
                    "headers": headers,
                    "status_code": 408,
                    "error": "Request timed out",
                },
            )
        except Exception as exc:  # noqa: BLE001
            self.log(f"Error making request to {url}")
            return Data(
                data={
                    "source": url,
                    "headers": headers,
                    "status_code": 500,
                    "error": str(exc),
                    **({"redirection_history": redirection_history} if redirection_history else {}),
                },
            )

    def add_query_params(self, url: str, params: dict) -> str:
        url_parts = list(urlparse(url))
        query = dict(parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urlencode(query)
        print(url_parts)
        return urlunparse(url_parts)

    async def make_requests(self) -> list[Data]:
        method = self.method
        urls = [url.strip() for url in self.urls if url.strip()]
        headers = self.headers or {}
        body = self.body or {}
        timeout = self.timeout
        follow_redirects = self.follow_redirects
        save_to_file = self.save_to_file
        include_httpx_metadata = self.include_httpx_metadata

        invalid_urls = [url for url in urls if not validators.url(url)]
        if invalid_urls:
            msg = f"Invalid URLs provided: {invalid_urls}"
            raise ValueError(msg)

        if isinstance(self.query_params, str):
            query_params = dict(parse_qsl(self.query_params))
        else:
            query_params = self.query_params.data if self.query_params else {}

        if isinstance(headers, Data):
            headers = headers.data

        if isinstance(body, Data):
            body = body.data

        bodies = [body] * len(urls)

        urls = [self.add_query_params(url, query_params) for url in urls]

        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                *[
                    self.make_request(
                        client,
                        method,
                        u,
                        headers,
                        rec,
                        timeout,
                        follow_redirects=follow_redirects,
                        save_to_file=save_to_file,
                        include_httpx_metadata=include_httpx_metadata,
                    )
                    for u, rec in zip(urls, bodies, strict=True)
                ]
            )
        self.status = results
        return results

    def _response_info(self, response: httpx.Response, *, with_file_path: bool = False) -> tuple[bool, Path | None]:
        """Determine the file path and whether the response content is binary.

        Args:
            response (Response): The HTTP response object.
            with_file_path (bool): Whether to save the response content to a file.

        Returns:
            Tuple[bool, Path | None]:
                A tuple containing a boolean indicating if the content is binary and the full file path (if applicable).
        """
        content_type = response.headers.get("Content-Type", "")
        is_binary = "application/octet-stream" in content_type or "application/binary" in content_type

        if not with_file_path:
            return is_binary, None

        component_temp_dir = Path(tempfile.gettempdir()) / self.__class__.__name__
        component_temp_dir.mkdir(parents=True, exist_ok=True)

        filename = None
        if "Content-Disposition" in response.headers:
            content_disposition = response.headers["Content-Disposition"]
            filename_match = re.search(r'filename="(.+?)"', content_disposition)
            if not filename_match:  # Try to match RFC 5987 style
                filename_match = re.search(r"filename\*=(?:UTF-8'')?(.+)", content_disposition)
            if filename_match:
                extracted_filename = filename_match.group(1)
                if (component_temp_dir / extracted_filename).exists():
                    timestamp = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%d%H%M%S%f")
                    filename = f"{timestamp}-{extracted_filename}"
                else:
                    filename = extracted_filename

        if not filename:
            url_path = urlparse(str(response.request.url)).path
            base_name = Path(url_path).name
            if not base_name:
                base_name = "response"

            extension = mimetypes.guess_extension(content_type.split(";")[0]) if content_type else None
            if not extension:
                extension = ".bin" if is_binary else ".txt"

            timestamp = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%d%H%M%S%f")
            filename = f"{timestamp}-{base_name}{extension}"

        file_path = component_temp_dir / filename

        return is_binary, file_path

    def _headers_to_dict(self, headers: httpx.Headers) -> dict[str, str]:
        """Convert HTTP headers to a dictionary with lowercased keys."""
        return {k.lower(): v for k, v in headers.items()}
