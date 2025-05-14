import asyncio
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import aiofiles
import aiofiles.os as aiofiles_os
import httpx
import validators

from langflow.base.curl.parse import parse_context
from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DataInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    StrInput,
    TableInput,
)
from langflow.schema import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.dotdict import dotdict
from langflow.services.deps import get_settings_service

# Get settings using the service


class APIRequestComponent(Component):
    display_name = "API Request"
    description = "Make HTTP requests using URLs or cURL commands."
    icon = "Globe"
    name = "APIRequest"

    default_keys = ["urls", "method", "query_params"]

    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            list=True,
            info="Enter one or more URLs, separated by commas.",
            advanced=False,
            tool_mode=True,
        ),
        MultilineInput(
            name="curl",
            display_name="cURL",
            info=(
                "Paste a curl command to populate the fields. "
                "This will fill in the dictionary fields for headers and body."
            ),
            advanced=True,
            real_time_refresh=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="method",
            display_name="Method",
            options=["GET", "POST", "PATCH", "PUT", "DELETE"],
            info="The HTTP method to use.",
            real_time_refresh=True,
        ),
        BoolInput(
            name="use_curl",
            display_name="Use cURL",
            value=False,
            info="Enable cURL mode to populate fields from a cURL command.",
            real_time_refresh=True,
        ),
        DataInput(
            name="query_params",
            display_name="Query Parameters",
            info="The query parameters to append to the URL.",
            advanced=True,
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
            advanced=True,
            real_time_refresh=True,
        ),
        TableInput(
            name="headers",
            display_name="Headers",
            info="The headers to send with the request",
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
            value=[{"key": "User-Agent", "value": get_settings_service().settings.user_agent}],
            advanced=True,
            input_types=["Data"],
            real_time_refresh=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            value=30,
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
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    def _parse_json_value(self, value: Any) -> Any:
        """Parse a value that might be a JSON string."""
        if not isinstance(value, str):
            return value

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        else:
            return parsed

    def _process_body(self, body: Any) -> dict:
        """Process the body input into a valid dictionary.

        Args:
            body: The body to process, can be dict, str, or list
        Returns:
            Processed dictionary
        """
        if body is None:
            return {}
        if isinstance(body, dict):
            return self._process_dict_body(body)
        if isinstance(body, str):
            return self._process_string_body(body)
        if isinstance(body, list):
            return self._process_list_body(body)

        return {}

    def _process_dict_body(self, body: dict) -> dict:
        """Process dictionary body by parsing JSON values."""
        return {k: self._parse_json_value(v) for k, v in body.items()}

    def _process_string_body(self, body: str) -> dict:
        """Process string body by attempting JSON parse."""
        try:
            return self._process_body(json.loads(body))
        except json.JSONDecodeError:
            return {"data": body}

    def _process_list_body(self, body: list) -> dict:
        """Process list body by converting to key-value dictionary."""
        processed_dict = {}

        try:
            for item in body:
                if not self._is_valid_key_value_item(item):
                    continue

                key = item["key"]
                value = self._parse_json_value(item["value"])
                processed_dict[key] = value

        except (KeyError, TypeError, ValueError) as e:
            self.log(f"Failed to process body list: {e}")
            return {}  # Return empty dictionary instead of None

        return processed_dict

    def _is_valid_key_value_item(self, item: Any) -> bool:
        """Check if an item is a valid key-value dictionary."""
        return isinstance(item, dict) and "key" in item and "value" in item

    def parse_curl(self, curl: str, build_config: dotdict) -> dotdict:
        """Parse a cURL command and update build configuration.

        Args:
            curl: The cURL command to parse
            build_config: The build configuration to update
        Returns:
            Updated build configuration
        """
        try:
            parsed = parse_context(curl)

            # Update basic configuration
            build_config["urls"]["value"] = [parsed.url]
            build_config["method"]["value"] = parsed.method.upper()
            build_config["headers"]["advanced"] = True
            build_config["body"]["advanced"] = True

            # Process headers
            headers_list = [{"key": k, "value": v} for k, v in parsed.headers.items()]
            build_config["headers"]["value"] = headers_list

            if headers_list:
                build_config["headers"]["advanced"] = False

            # Process body data
            if not parsed.data:
                build_config["body"]["value"] = []
            elif parsed.data:
                try:
                    json_data = json.loads(parsed.data)
                    if isinstance(json_data, dict):
                        body_list = [
                            {"key": k, "value": json.dumps(v) if isinstance(v, dict | list) else str(v)}
                            for k, v in json_data.items()
                        ]
                        build_config["body"]["value"] = body_list
                        build_config["body"]["advanced"] = False
                    else:
                        build_config["body"]["value"] = [{"key": "data", "value": json.dumps(json_data)}]
                        build_config["body"]["advanced"] = False
                except json.JSONDecodeError:
                    build_config["body"]["value"] = [{"key": "data", "value": parsed.data}]
                    build_config["body"]["advanced"] = False

        except Exception as exc:
            msg = f"Error parsing curl: {exc}"
            self.log(msg)
            raise ValueError(msg) from exc

        return build_config

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "use_curl" and field_value:
            # if we remove field value from validation, this gets validated every time
            build_config = self._update_curl_mode(build_config, use_curl=field_value)

            # If curl is not used, we don't need to reset the fields
            if not self.use_curl:
                return build_config

            # Fields that should not be reset
            preserve_fields = {"timeout", "follow_redirects", "save_to_file", "include_httpx_metadata", "use_curl"}

            # Mapping between input types and their reset values
            type_reset_mapping = {
                TableInput: [],
                BoolInput: False,
                IntInput: 0,
                FloatInput: 0.0,
                MessageTextInput: "",
                StrInput: "",
                MultilineInput: "",
                DropdownInput: "GET",
                DataInput: {},
            }

            for input_field in self.inputs:
                # Only reset if field is not in preserve list
                if input_field.name not in preserve_fields:
                    reset_value = type_reset_mapping.get(type(input_field), None)
                    build_config[input_field.name]["value"] = reset_value
                    self.log(f"Reset field {input_field.name} to {reset_value}")
            # Don't try to parse the boolean value as a curl command
            return build_config
        if field_name == "method" and not self.use_curl:
            build_config = self._update_method_fields(build_config, field_value)
        elif field_name == "curl" and self.use_curl and field_value:
            # Not reachable, because we don't have a way to update
            # the curl field, self.use_curl is set after the build_config is created
            build_config = self.parse_curl(field_value, build_config)
        return build_config

    def _update_curl_mode(self, build_config: dotdict, *, use_curl: bool) -> dotdict:
        always_visible = ["method", "use_curl"]

        for field in self.inputs:
            field_name = field.name
            field_config = build_config.get(field_name)
            if isinstance(field_config, dict):
                if field_name in always_visible:
                    field_config["advanced"] = False
                elif field_name == "urls":
                    field_config["advanced"] = use_curl
                elif field_name == "curl":
                    field_config["advanced"] = not use_curl
                    field_config["real_time_refresh"] = use_curl
                elif field_name in {"body", "headers"}:
                    field_config["advanced"] = True  # Always keep body and headers in advanced when use_curl is False
                else:
                    field_config["advanced"] = use_curl or field_config.get("advanced")
            else:
                self.log(f"Expected dict for build_config[{field_name}], got {type(field_config).__name__}")

        if not use_curl:
            current_method = build_config.get("method", {}).get("value", "GET")
            build_config = self._update_method_fields(build_config, current_method)

        return build_config

    def _update_method_fields(self, build_config: dotdict, method: str) -> dotdict:
        common_fields = [
            "urls",
            "method",
            "use_curl",
        ]

        always_advanced_fields = [
            "body",
            "headers",
            "timeout",
            "follow_redirects",
            "save_to_file",
            "include_httpx_metadata",
        ]

        body_fields = ["body"]

        for field in self.inputs:
            field_name = field.name
            field_config = build_config.get(field_name)
            if isinstance(field_config, dict):
                if field_name in common_fields:
                    field_config["advanced"] = False
                elif field_name in body_fields:
                    field_config["advanced"] = method not in {"POST", "PUT", "PATCH"}
                elif field_name in always_advanced_fields:
                    field_config["advanced"] = True
            else:
                self.log(f"Expected dict for build_config[{field_name}], got {type(field_config).__name__}")

        return build_config

    async def make_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: dict | None = None,
        body: Any = None,
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

        # Process body using the new helper method
        processed_body = self._process_body(body)
        redirection_history = []

        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=processed_body,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )

            redirection_history = [
                {
                    "url": redirect.headers.get("Location", str(redirect.url)),
                    "status_code": redirect.status_code,
                }
                for redirect in response.history
            ]

            is_binary, file_path = await self._response_info(response, with_file_path=save_to_file)
            response_headers = self._headers_to_dict(response.headers)

            metadata: dict[str, Any] = {
                "source": url,
            }

            if save_to_file:
                mode = "wb" if is_binary else "w"
                encoding = response.encoding if mode == "w" else None
                if file_path:
                    # Ensure parent directory exists
                    await aiofiles_os.makedirs(file_path.parent, exist_ok=True)
                    if is_binary:
                        async with aiofiles.open(file_path, "wb") as f:
                            await f.write(response.content)
                            await f.flush()
                    else:
                        async with aiofiles.open(file_path, "w", encoding=encoding) as f:
                            await f.write(response.text)
                            await f.flush()
                    metadata["file_path"] = str(file_path)

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

            if is_binary:
                result = response.content
            else:
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    self.log("Failed to decode JSON response")
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

        if self.use_curl and self.curl:
            self._build_config = self.parse_curl(self.curl, dotdict())

        invalid_urls = [url for url in urls if not validators.url(url)]
        if invalid_urls:
            msg = f"Invalid URLs provided: {invalid_urls}"
            raise ValueError(msg)

        if isinstance(self.query_params, str):
            query_params = dict(parse_qsl(self.query_params))
        else:
            query_params = self.query_params.data if self.query_params else {}

        # Process headers here
        headers = self._process_headers(headers)

        # Process body
        body = self._process_body(body)

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
                    for u, rec in zip(urls, bodies, strict=False)
                ]
            )
        self.status = results
        return results

    async def _response_info(
        self, response: httpx.Response, *, with_file_path: bool = False
    ) -> tuple[bool, Path | None]:
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

        # Create directory asynchronously
        await aiofiles_os.makedirs(component_temp_dir, exist_ok=True)

        filename = None
        if "Content-Disposition" in response.headers:
            content_disposition = response.headers["Content-Disposition"]
            filename_match = re.search(r'filename="(.+?)"', content_disposition)
            if filename_match:
                extracted_filename = filename_match.group(1)
                filename = extracted_filename

        # Step 3: Infer file extension or use part of the request URL if no filename
        if not filename:
            # Extract the last segment of the URL path
            url_path = urlparse(str(response.request.url) if response.request else "").path
            base_name = Path(url_path).name  # Get the last segment of the path
            if not base_name:  # If the path ends with a slash or is empty
                base_name = "response"

            # Infer file extension
            content_type_to_extension = {
                "text/plain": ".txt",
                "application/json": ".json",
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "application/octet-stream": ".bin",
            }
            extension = content_type_to_extension.get(content_type, ".bin" if is_binary else ".txt")
            filename = f"{base_name}{extension}"

        # Step 4: Define the full file path
        file_path = component_temp_dir / filename

        # Step 5: Check if file exists asynchronously and handle accordingly
        try:
            # Try to create the file exclusively (x mode) to check existence
            async with aiofiles.open(file_path, "x") as _:
                pass  # File created successfully, we can use this path
        except FileExistsError:
            # If file exists, append a timestamp to the filename
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
            file_path = component_temp_dir / f"{timestamp}-{filename}"

        return is_binary, file_path

    def _headers_to_dict(self, headers: httpx.Headers) -> dict[str, str]:
        """Convert HTTP headers to a dictionary with lowercased keys."""
        return {k.lower(): v for k, v in headers.items()}

    def _process_headers(self, headers: Any) -> dict:
        """Process the headers input into a valid dictionary.

        Args:
            headers: The headers to process, can be dict, str, or list
        Returns:
            Processed dictionary
        """
        if headers is None:
            return {}
        if isinstance(headers, dict):
            return headers
        if isinstance(headers, list):
            processed_headers = {}
            try:
                for item in headers:
                    if not self._is_valid_key_value_item(item):
                        continue
                    key = item["key"]
                    value = item["value"]
                    processed_headers[key] = value
            except (KeyError, TypeError, ValueError) as e:
                self.log(f"Failed to process headers list: {e}")
                return {}  # Return empty dictionary instead of None
            return processed_headers
        return {}

    async def as_dataframe(self) -> DataFrame:
        """Convert the API response data into a DataFrame.

        Returns:
            DataFrame: A DataFrame containing the API response data.
        """
        data = await self.make_requests()
        return DataFrame(data)
