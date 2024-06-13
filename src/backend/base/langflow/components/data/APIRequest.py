import asyncio
import json
from typing import List, Optional

import httpx
from loguru import logger

from langflow.base.curl.parse import parse_context
from langflow.custom import Component
from langflow.inputs import StrInput, DropdownInput, NestedDictInput, IntInput
from langflow.schema import Data
from langflow.template import Output


class APIRequestComponent(Component):
    display_name = "API Request"
    description = "Make HTTP requests given one or more URLs."
    icon = "Globe"

    inputs = [
        StrInput(
            name="urls",
            display_name="URLs",
            multiline=True,
            info="Enter one or more URLs, separated by commas.",
        ),
        StrInput(
            name="curl",
            display_name="Curl",
            info="Paste a curl command to populate the fields.",
            advanced=True,
        ),
        DropdownInput(
            name="method",
            display_name="Method",
            options=["GET", "POST", "PATCH", "PUT"],
            value="GET",
            info="The HTTP method to use.",
        ),
        NestedDictInput(
            name="headers",
            display_name="Headers",
            info="The headers to send with the request.",
        ),
        NestedDictInput(
            name="body",
            display_name="Body",
            info="The body to send with the request (for POST, PATCH, PUT).",
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

    def parse_curl(self, curl: str):
        build_config = self._build_config()
        try:
            parsed = parse_context(curl)
            build_config["urls"]["value"] = [parsed.url]
            build_config["method"]["value"] = parsed.method.upper()
            build_config["headers"]["value"] = dict(parsed.headers)

            try:
                json_data = json.loads(parsed.data)
                build_config["body"]["value"] = json_data
            except json.JSONDecodeError as e:
                logger.error(e)
        except Exception as exc:
            logger.error(f"Error parsing curl: {exc}")
            raise ValueError(f"Error parsing curl: {exc}")
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

        data = body if body else None
        payload = json.dumps(data)
        try:
            response = await client.request(method, url, headers=headers, content=payload, timeout=timeout)
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

    async def make_requests(self) -> List[Data]:
        method = self.method
        urls = [url.strip() for url in self.urls.split(",") if url.strip()]
        curl = self.curl
        headers = self.headers or {}
        body = self.body or {}
        timeout = self.timeout

        if curl:
            self._build_config = self.parse_curl(curl)

        if isinstance(headers, Data):
            headers_dict = headers.data
        else:
            headers_dict = headers

        bodies = []
        if body:
            if not isinstance(body, list):
                bodies = [body]
            else:
                bodies = body
            bodies = [b.data if isinstance(b, Data) else b for b in bodies]

        if len(urls) != len(bodies):
            bodies += [None] * (len(urls) - len(bodies))

        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                *[self.make_request(client, method, u, headers_dict, rec, timeout) for u, rec in zip(urls, bodies)]
            )
        self.status = results
        return results
