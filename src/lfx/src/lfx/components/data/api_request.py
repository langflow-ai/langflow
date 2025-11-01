import json
import os
import re
import ssl
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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
    FileInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
    StrInput,
    TableInput,
)
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.utils.component_utils import set_current_fields, set_field_advanced, set_field_display

# Define fields for each mode
MODE_FIELDS = {
    "URL": [
        "url_input",
        "method",
    ],
    "cURL": ["curl_input"],
}

# Fields that should always be visible
DEFAULT_FIELDS = ["mode"]


class APIRequestComponent(Component):
    display_name = "API Request"
    description = "Make HTTP requests using URL or cURL commands."
    documentation: str = "https://docs.langflow.org/components-data#api-request"
    icon = "Globe"
    name = "APIRequest"

    inputs = [
        MessageTextInput(
            name="url_input",
            display_name="URL",
            info="Enter the URL for the request.",
            advanced=False,
            tool_mode=True,
        ),
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
            value=[{"key": "User-Agent", "value": "Langflow/1.0"}],
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
        BoolInput(
            name="use_mtls",
            display_name="Enable mTLS",
            value=False,
            info="Enable mutual TLS authentication for this request.",
            advanced=True,
        ),
        DropdownInput(
            name="cert_source",
            display_name="Certificate Source",
            options=["File Path", "Environment Variable", "Secrets Manager"],
            value="File Path",
            info="Select where to load client certificates from.",
            advanced=True,
        ),
        FileInput(
            name="client_cert_file",
            display_name="Client Certificate File",
            info="Path to client certificate file (.pem, .crt). Can contain both cert and key.",
            advanced=True,
            file_types=["pem", "crt", "cert"],
        ),
        FileInput(
            name="client_key_file",
            display_name="Client Key File (Optional)",
            info="Path to private key file if separate from certificate (.key, .pem).",
            advanced=True,
            file_types=["key", "pem"],
        ),
        SecretStrInput(
            name="key_password",
            display_name="Key Password (Optional)",
            info="Password for encrypted private key.",
            advanced=True,
        ),
        StrInput(
            name="cert_env_var",
            display_name="Certificate Env Var",
            info="Environment variable name containing path to certificate (e.g., CLIENT_CERT_PATH).",
            advanced=True,
        ),
        StrInput(
            name="key_env_var",
            display_name="Key Env Var",
            info="Environment variable name containing path to private key (e.g., CLIENT_KEY_PATH).",
            advanced=True,
        ),
        BoolInput(
            name="verify_server_cert",
            display_name="Verify Server Certificate",
            value=True,
            info="Verify the server's SSL certificate.",
            advanced=True,
        ),
        FileInput(
            name="ca_bundle_file",
            display_name="CA Bundle File (Optional)",
            info="Path to custom CA bundle for server certificate verification.",
            advanced=True,
            file_types=["pem", "crt", "cert"],
        ),
    ]

    outputs = [
        Output(display_name="API Response", name="data", method="make_api_request"),
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
                # Unwrap Data objects
                current_item = item
                if hasattr(item, "data"):
                    unwrapped_data = item.data
                    # If the unwrapped data is a dict but not key-value format, use it directly
                    if isinstance(unwrapped_data, dict) and not self._is_valid_key_value_item(unwrapped_data):
                        return unwrapped_data
                    current_item = unwrapped_data
                if not self._is_valid_key_value_item(current_item):
                    continue
                key = current_item["key"]
                value = self._parse_json_value(current_item["value"])
                processed_dict[key] = value
        except (KeyError, TypeError, ValueError) as e:
            self.log(f"Failed to process body list: {e}")
            return {}
        return processed_dict

    def _is_valid_key_value_item(self, item: Any) -> bool:
        """Check if an item is a valid key-value dictionary."""
        return isinstance(item, dict) and "key" in item and "value" in item

    def validate_mtls_config(self) -> None:
        """Validate mTLS configuration before building SSL context.

        Ensures that all required mTLS parameters are properly configured based on the
        selected certificate source (file path, environment variable, or secrets manager).

        Raises:
            ValueError: If mTLS is enabled but required configuration is missing:
                - When cert_source is "File Path" but no client_cert_file is provided
                - When cert_source is "Environment Variable" but no cert_env_var is provided

        Warnings:
            Logs a warning when verify_server_cert is disabled, as this creates an insecure connection.

        Example:
            >>> component.use_mtls = True
            >>> component.cert_source = "File Path"
            >>> component.client_cert_file = "/path/to/cert.pem"
            >>> component.validate_mtls_config()  # Passes validation
        """
        if not self.use_mtls:
            return

        cert_source = getattr(self, "cert_source", "File Path")

        if cert_source == "File Path" and not self.client_cert_file:
            msg = "mTLS enabled but no client certificate file provided"
            raise ValueError(msg)
        if cert_source == "Environment Variable" and not self.cert_env_var:
            msg = "mTLS enabled with env vars but no certificate environment variable name provided"
            raise ValueError(msg)

        if not self.verify_server_cert:
            self.log("WARNING: Server certificate verification is disabled. This is insecure!")

    def build_ssl_context(self) -> ssl.SSLContext | None:
        """Build SSL context for mTLS authentication.

        Constructs an SSL context configured with client certificates for mutual TLS authentication.
        Supports multiple certificate sources (local files, environment variables) and custom CA bundles.

        Certificate Loading:
            - File Path: Loads certificates from local filesystem paths
            - Environment Variable: Reads paths from environment variables
            - Secrets Manager: Reserved for future implementation

        Returns:
            ssl.SSLContext: Configured SSL context with client certificates loaded, or
            None: If mTLS is disabled (use_mtls=False)

        Raises:
            ValueError: If mTLS configuration is invalid:
                - Certificate environment variable not found or empty
                - SSL error while loading certificates (wrapped SSLError)
                - General configuration errors
            FileNotFoundError: If certificate or key files don't exist at specified paths

        Example:
            >>> # Using local certificate files
            >>> component.use_mtls = True
            >>> component.cert_source = "File Path"
            >>> component.client_cert_file = "/path/to/client.pem"
            >>> component.client_key_file = "/path/to/client.key"  # Optional if combined
            >>> ssl_ctx = component.build_ssl_context()

            >>> # Using environment variables (e.g., in Docker/K8s)
            >>> import os
            >>> os.environ['CLIENT_CERT_PATH'] = '/path/to/cert.pem'
            >>> component.use_mtls = True
            >>> component.cert_source = "Environment Variable"
            >>> component.cert_env_var = "CLIENT_CERT_PATH"
            >>> ssl_ctx = component.build_ssl_context()

        Note:
            - Passwords for encrypted keys should be provided via key_password attribute
            - Custom CA bundles can be specified via ca_bundle_file for internal CAs
            - Server certificate verification can be disabled via verify_server_cert (not recommended)
        """
        if not self.use_mtls:
            return None

        try:
            cert_source = getattr(self, "cert_source", "File Path")
            cert_path = None
            key_path = None

            if cert_source == "File Path":
                cert_path = self.client_cert_file
                key_path = self.client_key_file if self.client_key_file else None
            elif cert_source == "Environment Variable":
                cert_env = self.cert_env_var
                key_env = self.key_env_var

                if not cert_env:
                    msg = "Certificate environment variable name not provided"
                    raise ValueError(msg)

                cert_path = os.environ.get(cert_env)
                if not cert_path:
                    msg = f"Environment variable '{cert_env}' not found or empty"
                    raise ValueError(msg)

                if key_env:
                    key_path = os.environ.get(key_env)
                    if not key_path:
                        msg = f"Environment variable '{key_env}' not found or empty"
                        raise ValueError(msg)

            if not cert_path or not Path(cert_path).exists():
                msg = f"Certificate file not found: {cert_path}"
                raise FileNotFoundError(msg)

            if key_path and not Path(key_path).exists():
                msg = f"Private key file not found: {key_path}"
                raise FileNotFoundError(msg)

            ssl_context = ssl.create_default_context()

            if not self.verify_server_cert:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            else:
                ca_bundle = self.ca_bundle_file
                if ca_bundle:
                    if Path(ca_bundle).exists():
                        ssl_context.load_verify_locations(cafile=ca_bundle)
                    else:
                        self.log(f"WARNING: CA bundle file not found: {ca_bundle}")

            password = self.key_password if hasattr(self, "key_password") and self.key_password else None
            if password:
                password = password.encode("utf-8")

            ssl_context.load_cert_chain(
                certfile=cert_path,
                keyfile=key_path,
                password=password,
            )

        except ssl.SSLError as e:
            msg = f"SSL error while configuring mTLS: {e}"
            self.log(msg)
            raise ValueError(msg) from e
        except FileNotFoundError as e:
            msg = f"Certificate file not found: {e}"
            self.log(msg)
            raise
        except Exception as e:
            msg = f"Failed to configure mTLS: {e}"
            self.log(msg)
            raise ValueError(msg) from e
        else:
            self.log(f"mTLS enabled: Loaded certificate from {cert_path}")
            return ssl_context

    def parse_curl(self, curl: str, build_config: dotdict) -> dotdict:
        """Parse a cURL command and update build configuration."""
        try:
            parsed = parse_context(curl)

            # Update basic configuration
            url = parsed.url
            # Normalize URL before setting it
            url = self._normalize_url(url)

            build_config["url_input"]["value"] = url
            build_config["method"]["value"] = parsed.method.upper()

            # Process headers
            headers_list = [{"key": k, "value": v} for k, v in parsed.headers.items()]
            build_config["headers"]["value"] = headers_list

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
                    else:
                        build_config["body"]["value"] = [{"key": "data", "value": json.dumps(json_data)}]
                except json.JSONDecodeError:
                    build_config["body"]["value"] = [{"key": "data", "value": parsed.data}]

        except Exception as exc:
            msg = f"Error parsing curl: {exc}"
            self.log(msg)
            raise ValueError(msg) from exc

        return build_config

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by adding https:// if no protocol is specified."""
        if not url or not isinstance(url, str):
            msg = "URL cannot be empty"
            raise ValueError(msg)

        url = url.strip()
        if url.startswith(("http://", "https://")):
            return url
        return f"https://{url}"

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

        processed_body = self._process_body(body)
        redirection_history = []

        try:
            # Prepare request parameters
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

            # Base metadata
            metadata = {
                "source": url,
                "status_code": response.status_code,
                "response_headers": response_headers,
            }

            if redirection_history:
                metadata["redirection_history"] = redirection_history

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
                    metadata.update({"headers": headers})
                return Data(data=metadata)

            # Handle response content
            if is_binary:
                result = response.content
            else:
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    self.log("Failed to decode JSON response")
                    result = response.text.encode("utf-8")

            metadata["result"] = result

            if include_httpx_metadata:
                metadata.update({"headers": headers})

            return Data(data=metadata)
        except (httpx.HTTPError, httpx.RequestError, httpx.TimeoutException) as exc:
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
        """Add query parameters to URL efficiently."""
        if not params:
            return url
        url_parts = list(urlparse(url))
        query = dict(parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urlencode(query)
        return urlunparse(url_parts)

    def _headers_to_dict(self, headers: httpx.Headers) -> dict[str, str]:
        """Convert HTTP headers to a dictionary with lowercased keys."""
        return {k.lower(): v for k, v in headers.items()}

    def _process_headers(self, headers: Any) -> dict:
        """Process the headers input into a valid dictionary."""
        if headers is None:
            return {}
        if isinstance(headers, dict):
            return headers
        if isinstance(headers, list):
            return {item["key"]: item["value"] for item in headers if self._is_valid_key_value_item(item)}
        return {}

    async def make_api_request(self) -> Data:
        """Make HTTP request with optimized parameter handling."""
        method = self.method
        url = self.url_input.strip() if isinstance(self.url_input, str) else ""
        headers = self.headers or {}
        body = self.body or {}
        timeout = self.timeout
        follow_redirects = self.follow_redirects
        save_to_file = self.save_to_file
        include_httpx_metadata = self.include_httpx_metadata

        # if self.mode == "cURL" and self.curl_input:
        #     self._build_config = self.parse_curl(self.curl_input, dotdict())
        #     # After parsing curl, get the normalized URL
        #     url = self._build_config["url_input"]["value"]

        # Normalize URL before validation
        url = self._normalize_url(url)

        # Validate URL
        if not validators.url(url):
            msg = f"Invalid URL provided: {url}"
            raise ValueError(msg)

        self.validate_mtls_config()
        ssl_context = self.build_ssl_context()

        if isinstance(self.query_params, str):
            query_params = dict(parse_qsl(self.query_params))
        else:
            query_params = self.query_params.data if self.query_params else {}

        headers = self._process_headers(headers)
        body = self._process_body(body)
        url = self.add_query_params(url, query_params)

        verify_param = ssl_context if ssl_context else self.verify_server_cert

        async with httpx.AsyncClient(
            verify=verify_param,
            timeout=timeout or 30.0,
            follow_redirects=follow_redirects,
        ) as client:
            result = await self.make_request(
                client,
                method,
                url,
                headers,
                body,
                timeout,
                follow_redirects=follow_redirects,
                save_to_file=save_to_file,
                include_httpx_metadata=include_httpx_metadata,
            )
        self.status = result
        return result

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the build config based on the selected mode."""
        if field_name != "mode":
            if field_name == "curl_input" and self.mode == "cURL" and self.curl_input:
                return self.parse_curl(self.curl_input, build_config)
            return build_config

        # print(f"Current mode: {field_value}")
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
