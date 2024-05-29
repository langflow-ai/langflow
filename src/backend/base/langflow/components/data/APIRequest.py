import asyncio
import json
from typing import Any, List, Optional

import httpx
from loguru import logger

from langflow.base.curl.parse import parse_context
from langflow.custom import CustomComponent
from langflow.schema import Record
from langflow.schema.dotdict import dotdict


class APIRequest(CustomComponent):
    display_name: str = "API Request"
    description: str = "Make HTTP requests given one or more URLs."
    output_types: list[str] = ["Record"]
    documentation: str = "https://docs.langflow.org/components/utilities#api-request"
    icon = "Globe"

    field_config = {
        "urls": {"display_name": "URLs", "info": "URLs to make requests to."},
        "curl": {
            "display_name": "Curl",
            "info": "Paste a curl command to populate the fields.",
            "refresh_button": True,
            "refresh_button_text": "",
        },
        "method": {
            "display_name": "Method",
            "info": "The HTTP method to use.",
            "options": ["GET", "POST", "PATCH", "PUT"],
            "value": "GET",
        },
        "headers": {
            "display_name": "Headers",
            "info": "The headers to send with the request.",
            "input_types": ["Record"],
        },
        "body": {
            "display_name": "Body",
            "info": "The body to send with the request (for POST, PATCH, PUT).",
            "input_types": ["Record"],
        },
        "timeout": {
            "display_name": "Timeout",
            "info": "The timeout to use for the request.",
            "value": 5,
        },
    }

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "curl" and field_value is not None:
            try:
                curl = field_value
                parsed = parse_context(curl)
                build_config["urls"]["value"] = [parsed.url]
                build_config["method"]["value"] = parsed.method
                build_config["headers"]["value"] = parsed.headers
                try:
                    json_data = json.loads(parsed.data)
                    build_config["body"]["value"] = json_data
                except json.JSONDecodeError:
                    pass
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
    ) -> Record:
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
            return Record(
                data={
                    "source": url,
                    "headers": headers,
                    "status_code": response.status_code,
                    "result": result,
                },
            )
        except httpx.TimeoutException:
            return Record(
                data={
                    "source": url,
                    "headers": headers,
                    "status_code": 408,
                    "error": "Request timed out",
                },
            )
        except Exception as exc:
            return Record(
                data={
                    "source": url,
                    "headers": headers,
                    "status_code": 500,
                    "error": str(exc),
                },
            )

    async def build(
        self,
        method: str,
        urls: List[str],
        curl: Optional[str] = None,
        headers: Optional[Record] = {},
        body: Optional[Record] = {},
        timeout: int = 5,
    ) -> List[Record]:
        if headers is None:
            headers_dict = {}
        else:
            headers_dict = headers.data

        bodies = []
        if body:
            if isinstance(body, list):
                bodies = [b.data if isinstance(b, Record) else b for b in body]
            else:
                bodies = [body.data if isinstance(body, Record) else body]

        if len(urls) != len(bodies):
            # add bodies with None
            bodies += [None] * (len(urls) - len(bodies))  # type: ignore
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                *[self.make_request(client, method, u, headers_dict, rec, timeout) for u, rec in zip(urls, bodies)]
            )
        self.status = results
        return results
