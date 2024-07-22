import asyncio
import json
from typing import Any, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from loguru import logger

from langflow.base.curl.parse import parse_context
from langflow.custom import Component
from langflow.io import DataInput, DropdownInput, IntInput, MessageTextInput, NestedDictInput, Output
from langflow.schema import Data
from langflow.schema.dotdict import dotdict


class APIRequestComponent(Component):
    display_name = "API Request"
    description = (
        "This component allows you to make HTTP requests to one or more URLs. "
        "You can provide headers and body as either dictionaries or Data objects. "
        "Additionally, you can append query parameters to the URLs.\n\n"
        "**Note:** Check advanced options for more settings."
    )
    icon = "Globe"
    name = "APIRequest"

    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            is_list=True,
            info="Enter one or more URLs, separated by commas.",
        ),
        MessageTextInput(
            name="curl",
            display_name="Curl",
            info="Paste a curl command to populate the fields. This will fill in the dictionary fields for headers and body.",
            advanced=False,
            refresh_button=True,
        ),
        DropdownInput(
            name="method",
            display_name="Method",
            options=["GET", "POST", "PATCH", "PUT"],
            value="GET",
            info="The HTTP method to use (GET, POST, PATCH, PUT).",
        ),
        NestedDictInput(
            name="headers",
            display_name="Headers",
            info="The headers to send with the request as a dictionary. This is populated when using the CURL field.",
            input_types=["Data"],
        ),
        NestedDictInput(
            name="body",
            display_name="Body",
            info="The body to send with the request as a dictionary (for POST, PATCH, PUT). This is populated when using the CURL field.",
            input_types=["Data"],
        ),
        DataInput(
            name="query_params",
            display_name="Query Parameters",
            info="The query parameters to append to the URL.",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            value=5,
            info="The timeout to use for the request.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="make_requests"),
    ]

    def parse_curl(self, curl: str, build_config: dotdict) -> dotdict:
        try:
            parsed = parse_context(curl)
            build_config["urls"]["value"] = [parsed.url]
            build_config["method"]["value"] = parsed.method.upper()
            build_config["headers"]["value"] = dict(parsed.headers)

            if parsed.data:
                try:
                    json_data = json.loads(parsed.data)
                    build_config["body"]["value"] = json_data
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding JSON data: {e}")
            else:
                build_config["body"]["value"] = {}
        except Exception as exc:
            logger.error(f"Error parsing curl: {exc}")
            raise ValueError(f"Error parsing curl: {exc}")
        return build_config

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "curl" and field_value:
            build_config = self.parse_curl(field_value, build_config)
        return build_config

    async def make_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        body: Optional[dict] = None,
        timeout: int = 5,
    ) -> Data:
        method = method.upper()
        if method not in ["GET", "POST", "PATCH", "PUT", "DELETE"]:
            raise ValueError(f"Unsupported method: {method}")

        if isinstance(body, str) and body:
            try:
                body = json.loads(body)
            except Exception as e:
                logger.error(f"Error decoding JSON data: {e}")
                body = None
                raise ValueError(f"Error decoding JSON data: {e}")

        data = body if body else None

        try:
            response = await client.request(method, url, headers=headers, json=data, timeout=timeout)
            try:
                result = response.json()
            except Exception:
                result = response.text
            return Data(
                data={
                    "source": url,
                    "headers": headers,
                    "status_code": response.status_code,
                    "result": result,
                },
            )
        except httpx.TimeoutException:
            return Data(
                data={
                    "source": url,
                    "headers": headers,
                    "status_code": 408,
                    "error": "Request timed out",
                },
            )
        except Exception as exc:
            return Data(
                data={
                    "source": url,
                    "headers": headers,
                    "status_code": 500,
                    "error": str(exc),
                },
            )

    def add_query_params(self, url: str, params: dict) -> str:
        url_parts = list(urlparse(url))
        query = dict(parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urlencode(query)
        return urlunparse(url_parts)

    async def make_requests(self) -> List[Data]:
        method = self.method
        urls = [url.strip() for url in self.urls if url.strip()]
        curl = self.curl
        headers = self.headers or {}
        body = self.body or {}
        timeout = self.timeout
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
                *[self.make_request(client, method, u, headers, rec, timeout) for u, rec in zip(urls, bodies)]
            )
        self.status = results
        return results
