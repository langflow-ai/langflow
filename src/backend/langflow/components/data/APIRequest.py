import asyncio
from typing import List, Optional

import httpx
import json

from langflow import CustomComponent
from langflow.schema import Record
from langflow.services.database.models.base import orjson_dumps


class APIRequest(CustomComponent):
    display_name: str = "API Request"
    description: str = "Make an HTTP request to the given URL."
    output_types: list[str] = ["Record"]
    documentation: str = "https://docs.langflow.org/components/utilities#api-request"
    beta: bool = True
    field_config = {
        "url": {"display_name": "URL", "info": "The URL to make the request to."},
        "method": {
            "display_name": "Method",
            "info": "The HTTP method to use.",
            "field_type": "str",
            "options": ["GET", "POST", "PATCH", "PUT"],
            "value": "GET",
        },
        "headers": {
            "display_name": "Headers",
            "info": "The headers to send with the request.",
            "input_types": ["dict"]
        },
        "body": {
            "display_name": "Body",
            "info": "The body to send with the request (for POST, PATCH, PUT).",
            "input_types": ["dict"]
        },
        "timeout": {
            "display_name": "Timeout",
            "field_type": "int",
            "info": "The timeout to use for the request.",
            "value": 5,
        },
    }

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
        if method not in ["GET", "POST", "PATCH", "PUT"]:
            raise ValueError(f"Unsupported method: {method}")

        data = body if body else None
        data = json.dumps(data)
        try:
            response = await client.request(
                method, url, headers=headers, content=data, timeout=timeout
            )
            try:
                response_json = response.json()
                result = orjson_dumps(response_json, indent_2=False)
            except Exception:
                result = response.text
            return Record(
                text=result,
                data={
                    "source": url,
                    "headers": headers,
                    "status_code": response.status_code,
                },
            )
        except httpx.TimeoutException:
            return Record(
                text="Request Timed Out",
                data={"source": url, "headers": headers, "status_code": 408},
            )
        except Exception as exc:
            return Record(
                text=str(exc),
                data={"source": url, "headers": headers, "status_code": 500},
            )

    async def build(
        self,
        method: str,
        url: List[str],
        headers: Optional[dict] = None,
        body: Optional[dict] = None,
        timeout: int = 5,
    ) -> List[Record]:
        if headers is None:
            headers = {}
        urls = url if isinstance(url, list) else [url]
        bodies = (
            body
            if isinstance(body, list)
            else [body] if body else [None] * len(urls)
        )
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                *[
                    self.make_request(client, method, u, headers, rec, timeout)
                    for u, rec in zip(urls, bodies)
                ]
            )
        return results
