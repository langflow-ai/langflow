import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

import aiofiles
import aiofiles.os as aiofiles_os
import httpx
import validators

from lfx.base.curl.parse import parse_context
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import TabInput
from lfx.io import (
    BoolInput,
    DataInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    TableInput,
)
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.utils.component_utils import (
    set_current_fields,
    set_field_advanced,
    set_field_display,
)
from lfx.utils.ssrf_protection import SSRFProtectionError, validate_url_for_ssrf

# -----------------------------------------------------------------------------
# UI behavior: fields shown/hidden based on "mode"
# -----------------------------------------------------------------------------
MODE_FIELDS = {
    "URL": [
        "url_input",
        "path_input",
        "path_params",
        "method",
    ],
    "cURL": ["curl_input"],
}

DEFAULT_FIELDS = ["mode"]

# Placeholder pattern: matches {case_id}, {userId}, etc.
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class APIRequestComponent(Component):
    display_name = "API Request"
    description = "Make HTTP requests using URL or cURL commands."
    documentation: str = "https://docs.langflow.org/api-request"
    icon = "Globe"
    name = "APIRequest"

    inputs = [
        # Base URL (selected via globe icon in UI)
        MessageTextInput(
            name="url_input",
            display_name="URL",
            info="Enter the base URL for the request (scheme://host[:port]).",
            advanced=False,
            tool_mode=True,
        ),
        # Relative path (optionally with querystring), supports placeholders
        MessageTextInput(
            name="path_input",
            display_name="Path",
            info="Path to append to the base URL (e.g. /api/cases/{case_id} or /v1/run?stream=false).",
            value="",
            advanced=False,
            tool_mode=True,
        ),
        # cURL mode input (hidden by default)
        MultilineInput(
            name="curl_input",
            display_name="cURL",
            info=(
                "Paste a curl command to populate the fields. "
                "This will fill in the dictionary fields for headers and body."
            ),
            real_time_refresh=True,
            tool_mode=True,
            advanced=True,
            show=False,
        ),
        DropdownInput(
            name="method",
            display_name="Method",
            options=["GET", "POST", "PATCH", "PUT", "DELETE"],
            value="GET",
            info="The HTTP method to use.",
            real_time_refresh=True,
        ),
        TabInput(
            name="mode",
            display_name="Mode",
            options=["URL", "cURL"],
            value="URL",
            info="Enable cURL mode to populate fields from a cURL command.",
            real_time_refresh=True,
        ),
        # Query parameters appended to the final URL
        DataInput(
            name="query_params",
            display_name="Query Parameters",
            info="Query parameters to append to the URL.",
            advanced=True,
        ),
        # Parameters used to replace placeholders in path_input: /x/{id} -> /x/123
        DataInput(
            name="path_params",
            display_name="Path Parameters",
            info='Path parameters as Data (e.g. {"command_id": "..."}).',
            advanced=True,
        ),
        # Body as a key/value table (POST/PATCH/PUT)
        TableInput(
            name="body",
            display_name="Body",
            info="Body to send with the request as a dictionary (POST, PATCH, PUT).",
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
        # Headers as a key/value table
        TableInput(
            name="headers",
            display_name="Headers",
            info="Headers to send with the request.",
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
            value=[{"key": "User-Agent", "value": "Langflow/1.0"}],
            advanced=True,
            input_types=["Data"],
            real_time_refresh=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            value=30,
            info="Timeout in seconds.",
            advanced=True,
        ),
        BoolInput(
            name="follow_redirects",
            display_name="Follow Redirects",
            value=False,
            info=(
                "Whether to follow HTTP redirects. "
                "WARNING: Enabling redirects may allow SSRF bypass attacks where a public URL "
                "redirects to internal resources. Only enable if you trust the target server."
            ),
            advanced=True,
        ),
        BoolInput(
            name="save_to_file",
            display_name="Save to File",
            value=False,
            info="Save the API response to a temporary file.",
            advanced=True,
        ),
        BoolInput(
            name="include_httpx_metadata",
            display_name="Include HTTPx Metadata",
            value=False,
            info="Include HTTP metadata (request headers, status code, redirection history, etc).",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="API Response", name="data", method="make_api_request"),
    ]

    # -------------------------------------------------------------------------
    # Helpers: body parsing
    # -------------------------------------------------------------------------
    def _parse_json_value(self, value: Any) -> Any:
        """Parse a value that might be a JSON string."""
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def _is_valid_key_value_item(self, item: Any) -> bool:
        """Check if an item is a valid key-value dict."""
        return isinstance(item, dict) and "key" in item and "value" in item

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
        """Process list body by converting key-value list into a dict."""
        processed_dict: dict[str, Any] = {}
        try:
            for item in body:
                current_item = item
                # Unwrap Data objects
                if hasattr(item, "data"):
                    unwrapped = item.data
                    # If it's a dict but not key-value format, use it directly
                    if isinstance(unwrapped, dict) and not self._is_valid_key_value_item(unwrapped):
                        return unwrapped
                    current_item = unwrapped

                if not self._is_valid_key_value_item(current_item):
                    continue

                key = current_item["key"]
                value = self._parse_json_value(current_item["value"])
                processed_dict[key] = value
        except (KeyError, TypeError, ValueError) as e:
            self.log(f"Failed to process body list: {e}")
            return {}
        return processed_dict

    def _process_body(self, body: Any) -> dict:
        """Process the body input into a valid dictionary."""
        if body is None:
            return {}
        if hasattr(body, "data"):
            body = body.data
        if isinstance(body, dict):
            return self._process_dict_body(body)
        if isinstance(body, str):
            return self._process_string_body(body)
        if isinstance(body, list):
            return self._process_list_body(body)
        return {}

    # -------------------------------------------------------------------------
    # Helpers: header parsing
    # -------------------------------------------------------------------------
    def _process_headers(self, headers: Any) -> dict:
        """Process headers input into a dict."""
        if headers is None:
            return {}
        if isinstance(headers, dict):
            return headers
        if isinstance(headers, list):
            return {item["key"]: item["value"] for item in headers if self._is_valid_key_value_item(item)}
        return {}

    def _headers_to_dict(self, headers: httpx.Headers) -> dict[str, str]:
        """Convert HTTP headers to a plain dict with lowercased keys."""
        return {k.lower(): v for k, v in headers.items()}

    # -------------------------------------------------------------------------
    # URL normalization + composition
    # -------------------------------------------------------------------------
    def _normalize_url(self, url: str) -> str:
        """Normalize URL by adding https:// if protocol is missing."""
        if not url or not isinstance(url, str):
            empty_url_msg = "URL cannot be empty"
            raise ValueError(empty_url_msg)
        url = url.strip()
        if url.startswith(("http://", "https://")):
            return url
        return f"https://{url}"

    def add_query_params(self, url: str, params: dict) -> str:
        """Append/merge query params to an URL."""
        if not params:
            return url
        url_parts = list(urlparse(url))
        query = dict(parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urlencode(query)
        return urlunparse(url_parts)

    def _join_base_and_path(self, base_url: str, path_input: str) -> str:
        """Join base URL and a (possibly relative) path_input.

        - Keeps base scheme/netloc
        - Preserves/merges query if path_input contains "?"
        """
        base_url = self._normalize_url(base_url)
        if not path_input:
            return base_url

        base = urlparse(base_url)
        rel = urlparse(path_input.strip())

        base_path = base.path or ""
        rel_path = rel.path or ""

        # Join paths safely (avoid // and missing /)
        joined_path = "/".join([base_path.rstrip("/"), rel_path.lstrip("/")]).strip()
        if not joined_path.startswith("/"):
            joined_path = "/" + joined_path

        # Merge query strings: base.query + rel.query
        query = dict(parse_qsl(base.query))
        query.update(dict(parse_qsl(rel.query)))

        final = base._replace(path=joined_path, query=urlencode(query))
        return urlunparse(final)

    def _apply_path_template(self, api_path: str, params: dict[str, Any], *, strict: bool = True) -> str:
        """Replace placeholders like {case_id} in api_path using params.

        - strict=True: raises if any placeholder is missing/empty in params.
        Values are URL-encoded using quote(..., safe="") to avoid path injection.
        """
        if not api_path:
            return api_path

        placeholders = _PLACEHOLDER_RE.findall(api_path)
        if not placeholders:
            return api_path

        missing = [p for p in placeholders if p not in params or params[p] in (None, "")]
        if missing and strict:
            error_msg = f"Missing path params for placeholders: {missing}"
            raise ValueError(error_msg)

        def repl(match: re.Match) -> str:
            key = match.group(1)
            val = params.get(key)
            if val is None:
                return match.group(0)
            return quote(str(val), safe="")  # encode everything (including '/')

        return _PLACEHOLDER_RE.sub(repl, api_path)

    # -------------------------------------------------------------------------
    # cURL parsing (optional convenience)
    # -------------------------------------------------------------------------
    def parse_curl(self, curl: str, build_config: dotdict) -> dotdict:
        """Parse a cURL command and update the component configuration.

        Additionally, split the parsed URL into:
        - url_input: scheme://netloc
        - path_input: path + ?query
        """
        try:
            parsed = parse_context(curl)

            raw_url = self._normalize_url(parsed.url)
            u = urlparse(raw_url)

            # Base = scheme://netloc
            base_only = urlunparse(u._replace(path="", params="", query="", fragment=""))

            # Path = /path + ?query
            path_only = u.path or ""
            if u.query:
                path_only = f"{path_only}?{u.query}"

            build_config["url_input"]["value"] = base_only
            build_config["path_input"]["value"] = path_only
            build_config["method"]["value"] = parsed.method.upper()

            # Headers
            headers_list = [{"key": k, "value": v} for k, v in parsed.headers.items()]
            build_config["headers"]["value"] = headers_list

            # Body
            if not parsed.data:
                build_config["body"]["value"] = []
            else:
                try:
                    json_data = json.loads(parsed.data)
                    if isinstance(json_data, dict):
                        body_list = [
                            {
                                "key": k,
                                "value": (json.dumps(v) if isinstance(v, (dict, list)) else str(v)),
                            }
                            for k, v in json_data.items()
                        ]
                        build_config["body"]["value"] = body_list
                    else:
                        build_config["body"]["value"] = [{"key": "data", "value": json.dumps(json_data)}]
                except json.JSONDecodeError:
                    build_config["body"]["value"] = [{"key": "data", "value": parsed.data}]

        except Exception as exc:
            error_msg = f"Error parsing curl: {exc}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        return build_config

    # -------------------------------------------------------------------------
    # HTTP execution
    # -------------------------------------------------------------------------
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
            unsupported_method_msg = f"Unsupported method: {method}"
            raise ValueError(unsupported_method_msg)

        processed_body = self._process_body(body)
        redirection_history: list[dict[str, Any]] = []

        try:
            request_params = {
                "method": method,
                "url": url,
                "headers": headers,
                "json": processed_body,
                "timeout": timeout,
                "follow_redirects": follow_redirects,
            }
            response = await client.request(**request_params)

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
                "status_code": response.status_code,
                "response_headers": response_headers,
            }
            if redirection_history:
                metadata["redirection_history"] = redirection_history

            # Save response to temp file if requested
            if save_to_file:
                mode = "wb" if is_binary else "w"
                encoding = response.encoding if mode == "w" else None

                if file_path:
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
                    metadata.update({"request_headers": headers})
                return Data(data=metadata)

            # Read response content
            if is_binary:
                result: Any = response.content
            else:
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    self.log("Failed to decode JSON response; returning raw bytes")
                    result = response.text.encode("utf-8")

            metadata["result"] = result
            if include_httpx_metadata:
                metadata.update({"request_headers": headers})

            return Data(data=metadata)

        except (httpx.HTTPError, httpx.RequestError, httpx.TimeoutException) as exc:
            self.log(f"Error making request to {url}")
            return Data(
                data={
                    "source": url,
                    "request_headers": headers,
                    "status_code": 500,
                    "error": str(exc),
                    **({"redirection_history": redirection_history} if redirection_history else {}),
                }
            )

    # -------------------------------------------------------------------------
    # Main entrypoint
    # -------------------------------------------------------------------------
    async def make_api_request(self) -> Data:
        """Build final URL (base + templated path + query params).

        Validate, apply SSRF protection, then execute the request.
        """
        method = self.method

        # Base URL + relative path
        base_url = self.url_input.strip() if isinstance(self.url_input, str) else ""
        path_input = self.path_input.strip() if isinstance(self.path_input, str) else ""

        # Replace placeholders in path using path_params, if present
        path_params_dict = self.path_params.data if self.path_params else {}
        path_input = self._apply_path_template(path_input, path_params_dict, strict=True)

        # Join base + path (and merge query in path_input, if present)
        url = self._join_base_and_path(base_url, path_input)

        # Validate URL syntax
        if not validators.url(url):
            invalid_url_msg = f"Invalid URL provided: {url}"
            raise ValueError(invalid_url_msg)

        # SSRF protection (warn_only=True: logs warnings but doesn't block by default)
        try:
            validate_url_for_ssrf(url, warn_only=True)
        except SSRFProtectionError as e:
            ssrf_error_msg = f"SSRF Protection: {e}"
            raise ValueError(ssrf_error_msg) from e

        # Query params appended afterwards (in addition to any query already in path_input)
        if isinstance(self.query_params, str):
            query_params = dict(parse_qsl(self.query_params))
        else:
            query_params = self.query_params.data if self.query_params else {}

        headers = self._process_headers(self.headers or {})
        body = self._process_body(self.body or {})

        timeout = self.timeout
        follow_redirects = self.follow_redirects
        save_to_file = self.save_to_file
        include_httpx_metadata = self.include_httpx_metadata

        # Optional warning
        if follow_redirects:
            self.log(
                "Security Warning: redirects are enabled and may allow SSRF bypass via open redirects. "
                "Only enable if you trust the target."
            )

        # Merge query params into final URL
        url = self.add_query_params(url, query_params)

        async with httpx.AsyncClient() as client:
            result = await self.make_request(
                client=client,
                method=method,
                url=url,
                headers=headers,
                body=body,
                timeout=timeout,
                follow_redirects=follow_redirects,
                save_to_file=save_to_file,
                include_httpx_metadata=include_httpx_metadata,
            )

        self.status = result
        return result

    # -------------------------------------------------------------------------
    # Dynamic UI updates (show/hide fields based on Mode)
    # -------------------------------------------------------------------------
    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the build config based on the selected mode.

        - When switching to cURL, show curl_input and optionally parse it.
        - When switching to URL, hide curl_input.
        - set_current_fields controls which fields are shown/advanced.
        """
        if field_name != "mode":
            # In cURL mode, parse live when curl_input changes
            if field_name == "curl_input" and self.mode == "cURL" and self.curl_input:
                return self.parse_curl(self.curl_input, build_config)
            return build_config

        if field_value == "cURL":
            set_field_display(build_config, "curl_input", value=True)
            if build_config["curl_input"]["value"]:
                build_config = self.parse_curl(build_config["curl_input"]["value"], build_config)
        else:
            set_field_display(build_config, "curl_input", value=False)

        return set_current_fields(
            build_config=build_config,
            action_fields=MODE_FIELDS,
            selected_action=field_value,
            default_fields=DEFAULT_FIELDS,
            func=set_field_advanced,
            default_value=True,
        )

    # -------------------------------------------------------------------------
    # Response helper: decide binary/text and optionally file name/path
    # -------------------------------------------------------------------------
    async def _response_info(
        self, response: httpx.Response, *, with_file_path: bool = False
    ) -> tuple[bool, Path | None]:
        """Determine whether response is binary and compute a temp file path if requested."""
        content_type = response.headers.get("Content-Type", "")
        is_binary = "application/octet-stream" in content_type or "application/binary" in content_type

        if not with_file_path:
            return is_binary, None

        component_temp_dir = Path(tempfile.gettempdir()) / self.__class__.__name__
        await aiofiles_os.makedirs(component_temp_dir, exist_ok=True)

        filename = None
        if "Content-Disposition" in response.headers:
            content_disposition = response.headers["Content-Disposition"]
            filename_match = re.search(r'filename="(.+?)"', content_disposition)
            if filename_match:
                filename = filename_match.group(1)

        # Infer file name if missing
        if not filename:
            url_path = urlparse(str(response.request.url) if response.request else "").path
            base_name = Path(url_path).name or "response"

            content_type_to_extension = {
                "text/plain": ".txt",
                "application/json": ".json",
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "application/octet-stream": ".bin",
            }
            extension = content_type_to_extension.get(content_type, ".bin" if is_binary else ".txt")
            filename = f"{base_name}{extension}"

        file_path = component_temp_dir / filename

        # Avoid overwriting existing file: if exists, prefix with timestamp
        try:
            async with aiofiles.open(file_path, "x") as _:
                pass
        except FileExistsError:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
            file_path = component_temp_dir / f"{timestamp}-{filename}"

        return is_binary, file_path
