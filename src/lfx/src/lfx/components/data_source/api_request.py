import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

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
from lfx.utils.component_utils import set_current_fields, set_field_advanced, set_field_display

# SSRF Protection imports - for preventing Server-Side Request Forgery attacks
from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    is_ssrf_protection_enabled,
    validate_and_resolve_url,
)
from lfx.utils.ssrf_transport import create_ssrf_protected_client

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

# HTTP redirect status codes (RFC 9110).
HTTP_MOVED_PERMANENTLY = 301
HTTP_FOUND = 302
HTTP_SEE_OTHER = 303
HTTP_TEMPORARY_REDIRECT = 307
HTTP_PERMANENT_REDIRECT = 308

# Maximum number of redirects to follow when re-validating each hop (matches httpx's default).
MAX_REDIRECTS = 20

# HTTP status codes that represent a redirect carrying a Location header.
REDIRECT_STATUS_CODES = frozenset(
    {
        HTTP_MOVED_PERMANENTLY,
        HTTP_FOUND,
        HTTP_SEE_OTHER,
        HTTP_TEMPORARY_REDIRECT,
        HTTP_PERMANENT_REDIRECT,
    }
)


class APIRequestComponent(Component):
    display_name = "API Request"
    description = "Make HTTP requests using URL or cURL commands."
    documentation: str = "https://docs.langflow.org/api-request"
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
            input_types=["Data", "JSON"],
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
            input_types=["Data", "JSON"],
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
            value=False,
            info=(
                "Whether to follow HTTP redirects. "
                "WARNING: Enabling redirects may allow SSRF bypass attacks where a public URL "
                "redirects to internal resources. Only enable if you trust the target server. "
                "See OWASP SSRF Prevention Cheat Sheet for details."
            ),
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
        follow_redirects: bool = False,
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
                "timeout": timeout,
                "follow_redirects": follow_redirects,
            }
            # Only include body for methods that support it (GET must not have a body per HTTP spec)
            if method in {"POST", "PATCH", "PUT", "DELETE"} and processed_body is not None:
                request_params["json"] = processed_body
            response = await client.request(**request_params)

            redirection_history = [
                {
                    "url": redirect.headers.get("Location", str(redirect.url)),
                    "status_code": redirect.status_code,
                }
                for redirect in response.history
            ]

            return await self._build_response_data(
                response,
                url,
                headers,
                redirection_history,
                save_to_file=save_to_file,
                include_httpx_metadata=include_httpx_metadata,
            )
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

    async def _build_response_data(
        self,
        response: httpx.Response,
        source_url: str,
        headers: dict | None,
        redirection_history: list,
        *,
        save_to_file: bool = False,
        include_httpx_metadata: bool = False,
    ) -> Data:
        """Turn an httpx response into the component's ``Data`` output.

        Shared by the standard request path (``make_request``) and the redirect
        re-validation path (``_follow_redirects_with_validation``) so both produce
        identical metadata, optional file saving, and body decoding.
        """
        is_binary, file_path = await self._response_info(response, with_file_path=save_to_file)
        response_headers = self._headers_to_dict(response.headers)

        # Base metadata
        metadata = {
            "source": source_url,
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
        """Make HTTP request with SSRF protection and DNS pinning.

        This method implements comprehensive SSRF (Server-Side Request Forgery) protection
        using DNS pinning to prevent DNS rebinding attacks. The protection works by:
        1. Validating the URL and resolving DNS during security check
        2. Pinning the validated IP address
        3. Forcing the HTTP client to use the pinned IP for the actual request
        4. Ignoring any subsequent DNS changes (prevents rebinding attacks)

        Returns:
            Data: Response data from the HTTP request

        Raises:
            ValueError: If URL is invalid or blocked by SSRF protection
        """
        # Extract request parameters
        method = self.method
        url = self.url_input.strip() if isinstance(self.url_input, str) else ""
        headers = self.headers or {}
        body = self.body or {}
        timeout = self.timeout
        follow_redirects = self.follow_redirects
        save_to_file = self.save_to_file
        include_httpx_metadata = self.include_httpx_metadata

        # Security warning: HTTP redirects can bypass SSRF protection
        # A public URL could redirect to an internal resource
        if follow_redirects:
            self.log(
                "Security Warning: HTTP redirects are enabled. This may allow SSRF bypass attacks "
                "where a public URL redirects to internal resources (e.g., cloud metadata endpoints). "
                "Only enable this if you trust the target server."
            )

        # Normalize URL (add https:// if no protocol specified)
        url = self._normalize_url(url)

        # Basic URL format validation
        if not validators.url(url):
            msg = f"Invalid URL provided: {url}"
            raise ValueError(msg)

        # ============================================================================
        # SSRF Protection with DNS Pinning
        # ============================================================================
        # This prevents DNS rebinding attacks by:
        # 1. Resolving DNS and validating IPs during security check
        # 2. Pinning the validated IP address
        # 3. Using a custom HTTP transport that forces use of the pinned IP
        # 4. Ignoring any new DNS resolutions (prevents rebinding)
        #
        # Without DNS pinning, an attacker could:
        # - First DNS lookup: returns public IP (passes validation)
        # - Second DNS lookup: returns internal IP (bypasses protection)
        # - Attack succeeds: accesses internal services
        #
        # With DNS pinning:
        # - First DNS lookup: returns public IP (passes validation)
        # - IP is pinned: "example.com = 93.184.216.34"
        # - HTTP request: uses pinned IP directly (no new DNS lookup)
        # - Attack fails: even if DNS changes, we use the validated IP
        # ============================================================================

        try:
            # Validate URL and get validated IPs for DNS pinning
            _validated_url, validated_ips = validate_and_resolve_url(url)

            # Log DNS pinning information for security auditing
            if validated_ips:
                self.log(f"SSRF Protection: Using DNS pinning with {len(validated_ips)} validated IP(s)")

        except SSRFProtectionError as e:
            # SSRF protection blocked the request (private IP, internal network, etc.)
            msg = f"SSRF Protection: {e}"
            raise ValueError(msg) from e

        # Process query parameters (from string or Data object)
        if isinstance(self.query_params, str):
            query_params = dict(parse_qsl(self.query_params))
        else:
            query_params = self.query_params.data if self.query_params else {}

        # Process headers and body into proper format
        headers = self._process_headers(headers)
        body = self._process_body(body)
        url = self.add_query_params(url, query_params)

        # ============================================================================
        # Execute the request (re-validating any redirects when SSRF protection is on)
        # ============================================================================
        # When SSRF protection is enabled we must NOT let httpx auto-follow redirects:
        # a validated public URL can redirect to an internal address (loopback, RFC1918,
        # link-local / cloud metadata) that was never checked, bypassing both the initial
        # validation and DNS pinning. Instead we follow redirects manually so every hop
        # is re-validated with the same denylist + DNS pinning. When protection is
        # disabled, we preserve the previous behavior and let httpx handle redirects.
        if is_ssrf_protection_enabled() and follow_redirects:
            result = await self._follow_redirects_with_validation(
                method,
                url,
                headers,
                body,
                timeout,
                validated_ips,
                save_to_file=save_to_file,
                include_httpx_metadata=include_httpx_metadata,
            )
        else:
            # No redirect re-validation needed:
            # - SSRF protection is disabled (user opted out), or
            # - redirects are disabled, so httpx makes a single request.
            # DNS pinning still applies to the single request when protection is enabled
            # and the host resolved to validated IPs.
            async with self._build_http_client(url, validated_ips) as client:
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

    def _build_http_client(self, url: str, validated_ips: list[str]) -> httpx.AsyncClient:
        """Create an HTTP client, pinning DNS to validated IPs when SSRF protection applies.

        Args:
            url: The request URL whose hostname will be pinned.
            validated_ips: IPs validated by ``validate_and_resolve_url`` for this hop.

        Returns:
            httpx.AsyncClient: A client that pins DNS to ``validated_ips`` (preventing
            rebinding) when SSRF protection is enabled and the hop has validated IPs;
            otherwise a standard client (protection disabled, allowlisted host, or
            hostname extraction failure).
        """
        if is_ssrf_protection_enabled() and validated_ips:
            # Extract hostname from the URL so the custom transport can pin it while
            # preserving the Host header for virtual hosting / TLS SNI.
            hostname = urlparse(url).hostname
            if hostname:
                # The custom transport tries validated IPs in order (dual-stack / LB).
                return create_ssrf_protected_client(hostname=hostname, validated_ips=validated_ips)
        return httpx.AsyncClient()

    @staticmethod
    def _method_for_redirect(method: str, status_code: int) -> str:
        """Return the HTTP method to use after a redirect, mirroring httpx semantics.

        A 303 (See Other) always becomes GET; 301/302 downgrade POST to GET for
        browser compatibility; 307/308 preserve the original method (and body).
        """
        method = method.upper()
        if status_code == HTTP_SEE_OTHER and method != "HEAD":
            return "GET"
        if status_code in (HTTP_MOVED_PERMANENTLY, HTTP_FOUND) and method == "POST":
            return "GET"
        return method

    @staticmethod
    def _headers_for_redirect(headers: dict | None, current_url: str, next_url: str) -> dict | None:
        """Drop sensitive headers when a redirect crosses to a different host.

        Mirrors httpx's auto-follow behavior so manually following redirects does not
        leak credentials (Authorization / Cookie) to a different host than the one the
        caller intended them for. Same-host redirects keep all headers.
        """
        if not headers:
            return headers
        if urlparse(current_url).hostname == urlparse(next_url).hostname:
            return headers
        sensitive = {"authorization", "proxy-authorization", "cookie"}
        return {k: v for k, v in headers.items() if k.lower() not in sensitive}

    async def _follow_redirects_with_validation(
        self,
        method: str,
        url: str,
        headers: dict | None,
        body: Any,
        timeout: int,
        validated_ips: list[str],
        *,
        save_to_file: bool = False,
        include_httpx_metadata: bool = False,
    ) -> Data:
        """Make the request and follow redirects manually, re-validating every hop.

        This closes an SSRF bypass: with ``follow_redirects`` enabled, httpx would
        otherwise auto-follow a redirect from a validated public URL to an internal
        address that was never checked. Here each redirect ``Location`` is resolved
        (relative locations included) and re-validated with ``validate_and_resolve_url``
        — the same private/loopback/link-local denylist and DNS pinning applied to the
        initial request — before any connection to it is made. A blocked hop raises
        ``ValueError``; the number of redirects is capped at ``MAX_REDIRECTS``.
        """
        method = method.upper()
        if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
            msg = f"Unsupported method: {method}"
            raise ValueError(msg)

        processed_body = self._process_body(body)
        current_url = url
        current_ips = validated_ips
        redirection_history: list[dict] = []

        for _ in range(MAX_REDIRECTS + 1):
            request_params: dict[str, Any] = {
                "method": method,
                "url": current_url,
                "headers": headers,
                "timeout": timeout,
                # Never let httpx follow redirects itself; each hop is validated below.
                "follow_redirects": False,
            }
            # Only include body for methods that support it (GET must not have a body).
            if method in {"POST", "PATCH", "PUT", "DELETE"} and processed_body is not None:
                request_params["json"] = processed_body

            try:
                async with self._build_http_client(current_url, current_ips) as client:
                    response = await client.request(**request_params)
            except (httpx.HTTPError, httpx.RequestError, httpx.TimeoutException) as exc:
                self.log(f"Error making request to {current_url}")
                return Data(
                    data={
                        "source": url,
                        "headers": headers,
                        "status_code": 500,
                        "error": str(exc),
                        **({"redirection_history": redirection_history} if redirection_history else {}),
                    },
                )

            location = response.headers.get("Location")
            if response.status_code in REDIRECT_STATUS_CODES and location:
                # Resolve relative redirects against the current URL.
                next_url = urljoin(current_url, location)
                redirection_history.append({"url": location, "status_code": response.status_code})

                # Re-validate the redirect target with the same SSRF denylist + DNS pinning.
                # Non-http(s) schemes, private/loopback/link-local hosts, and hostnames that
                # resolve to blocked IPs all raise SSRFProtectionError here.
                try:
                    _validated_url, current_ips = validate_and_resolve_url(next_url)
                except SSRFProtectionError as e:
                    msg = f"SSRF Protection: blocked redirect to {next_url}: {e}"
                    raise ValueError(msg) from e

                method = self._method_for_redirect(method, response.status_code)
                headers = self._headers_for_redirect(headers, current_url, next_url)
                current_url = next_url
                continue

            # Not a redirect (or no Location header) - this is the final response.
            return await self._build_response_data(
                response,
                url,
                headers,
                redirection_history,
                save_to_file=save_to_file,
                include_httpx_metadata=include_httpx_metadata,
            )

        msg = f"SSRF Protection: exceeded the maximum of {MAX_REDIRECTS} redirects while requesting {url}"
        raise ValueError(msg)

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the build config based on the selected mode."""
        if field_name != "mode":
            if field_name == "curl_input" and self.mode == "cURL" and self.curl_input:
                return self.parse_curl(self.curl_input, build_config)
            return build_config

        if field_value == "cURL":
            set_field_display(build_config, "curl_input", value=True)
            if build_config["curl_input"]["value"]:
                try:
                    build_config = self.parse_curl(build_config["curl_input"]["value"], build_config)
                except ValueError as e:
                    self.log(f"Failed to parse cURL input: {e}")
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
