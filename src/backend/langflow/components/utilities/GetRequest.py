from langflow import CustomComponent
from langchain.schema import Document
from langflow.database.models.base import orjson_dumps
import requests
from typing import Optional


class GetRequest(CustomComponent):
    display_name: str = "Get Request"
    description: str = "Make a GET request to the given URL."
    output_types: list[str] = ["Document"]
    beta = True
    field_config = {
        "url": {
            "display_name": "URL",
            "info": "The URL to make the request to",
            "is_list": True,
        },
        "headers": {
            "display_name": "Headers",
            "field_type": "code",
            "info": "The headers to send with the request.",
        },
        "code": {"show": False},
    }

    def get_document(
        self,
        url: str,
        headers: Optional[dict] = None,
    ) -> Document:
        try:
            if headers is None:
                headers = {}
            with requests.Session() as session:
                response = session.get(url, headers=headers)
                try:
                    response_json = response.json()
                    result = orjson_dumps(response_json, indent_2=False)
                except Exception:
                    result = response.text
                self.repr_value = result
                return Document(
                    page_content=result,
                    metadata={
                        "source": url,
                        "headers": headers,
                        "status_code": response.status_code,
                    },
                )
        except Exception as exc:
            return Document(
                page_content=str(exc),
                metadata={
                    "source": url,
                    "headers": headers,
                    "status_code": 500,
                },
            )

    def build(
        self,
        url: str,
        headers: Optional[dict] = None,
    ) -> Document:
        if headers is None:
            headers = {}
        if not isinstance(url, list):
            url = [url]
        return [self.get_document(u, headers) for u in url]
