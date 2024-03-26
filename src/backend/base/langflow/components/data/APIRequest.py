import asyncio
import json
from typing import List, Optional

import httpx

from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record


class APIRequest(CustomComponent):
    display_name: str = "API Request"
    description: str = "Make an HTTP request to the given URL."
    output_types: list[str] = ["Record"]
    documentation: str = "https://docs.langflow.org/components/utilities#api-request"
    field_config = {
        "urls": {"display_name": "URLs", "info": "The URLs to make the request to."},
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
            "input_types": ["dict"],
        },
        "body": {
            "display_name": "Body",
            "info": "The body to send with the request (for POST, PATCH, PUT).",
            "input_types": ["dict"],
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
        headers: Optional[dict] = None,
        body: Optional[List[Record]] = None,
        timeout: int = 5,
    ) -> List[Record]:
        if headers is None:
            headers = {}
        bodies = []
        if body:
            if isinstance(body, list):
                bodies = [b.data for b in body]
            else:
                bodies = [body.data]
        if len(urls) != len(bodies):
            # add bodies with None
            bodies += [None] * (len(urls) - len(bodies))  # type: ignore
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                *[self.make_request(client, method, u, headers, rec, timeout) for u, rec in zip(urls, bodies)]
            )
        self.status = results
        return results
