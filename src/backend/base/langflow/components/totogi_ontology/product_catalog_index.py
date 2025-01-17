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

from langflow.base.langchain_utilities.model import LCToolComponent

from langflow.base.curl.parse import parse_context
from langflow.custom import Component
from langflow.io import BoolInput, DataInput, DropdownInput, IntInput, MessageTextInput, NestedDictInput, Output
from langflow.schema import Data
from langflow.schema.dotdict import dotdict

from langflow.io import Output

class TotogiOntologyProductCatalogIndex(LCToolComponent):
    display_name = "Product Catalog Index - GET"
    description = (
        "This component allows you to make HTTP requests to Totogi Ontology Product Catalog Index"
    )
    name = "TotogiOntologyProductCatalogIndex"
    documentation: str = "https://docs-totogi-ontology.redoc.ly/openapi/product/operation/retrieveProductCatalogIndex/"
    icon = "Totogi"
    method = "GET"

    inputs = [
        MessageTextInput(
            name="auth_token",
            display_name="Auth Token",
            info="Enter the Auth Token for the Totogi Ontology Adapters.",
        ),
        MessageTextInput(
            name="adapter_endpoint",
            display_name="Adapter Endpoint",
            info="Enter the Adapter Endpoint for the Totogi Ontology Product Catalog Index.",
        ),
        DataInput(
            name="query_params",
            display_name="Query Parameters",
            info="The query parameters to append to the URL.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Product Catalog Index Data", name="product_catalog_index_data", method="make_request"),
        Output(name="product_catalog_index_tool", display_name="Tool", method="build_tool"),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "curl" and field_value:
            build_config = self.parse_curl(field_value, build_config)
        return build_config

    async def make_request(
        self,
        query_params: dict={},
        timeout: int = 40,
        *,
        follow_redirects: bool = True,
        save_to_file: bool = False,
        include_httpx_metadata: bool = False,
    ) -> Data:
        self.log(f"Making request to {self.adapter_endpoint} with query params {query_params}")
        method = self.method.upper()
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }
        adapter_endpoint = self.adapter_endpoint

        data = None
        redirection_history = []

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method,
                    adapter_endpoint,
                    headers=headers,
                    json=data,
                    timeout=timeout,
                    follow_redirects=follow_redirects,
                )
                self.log(f"Response: {response}")
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
                    "source": adapter_endpoint,
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
                # Populate result when not saving to a file
                if is_binary:
                    result = response.content
                else:
                    try:
                        result = response.json()
                    except Exception:  # noqa: BLE001
                        self.log("Error decoding JSON response")
                        result = response.text.encode("utf-8")

                # Add result to metadata
                metadata.update({"result": result})

                # Add metadata to the output
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
                        "source": adapter_endpoint,
                        "headers": headers,
                        "status_code": 408,
                        "error": "Request timed out",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self.log(f"Error making request to {adapter_endpoint}")
                return Data(
                    data={
                        "source": adapter_endpoint,
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
        curl = self.curl
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

        if curl:
            self._build_config = self.parse_curl(curl, dotdict())

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
        # Determine if the content is binary
        content_type = response.headers.get("Content-Type", "")
        is_binary = "application/octet-stream" in content_type or "application/binary" in content_type

        if not with_file_path:
            return is_binary, None

        # Step 1: Set up a subdirectory for the component in the OS temp directory
        component_temp_dir = Path(tempfile.gettempdir()) / self.__class__.__name__

        # Create directory asynchronously
        await aiofiles_os.makedirs(component_temp_dir, exist_ok=True)

        # Step 2: Extract filename from Content-Disposition
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
