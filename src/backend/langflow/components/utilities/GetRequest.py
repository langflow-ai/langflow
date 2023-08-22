from langflow import CustomComponent
from langchain.schema import Document
from langflow.database.models.base import orjson_dumps
import requests
from typing import Optional


class GetRequest(CustomComponent):
    display_name: str = "Get Request"
    description: str = "Make a GET request to the given URL"
    output_types: list[str] = ["Document"]
    beta = True
    field_config = {
        "url": {"display_name": "URL"},
        "headers": {"display_name": "Headers", "field_type": "code"},
        "code": {"show": False},
    }

    def build(
        self,
        url: str,
        headers: Optional[dict] = None,
    ) -> Document:
        if headers is None:
            headers = {}
        with requests.get(url, headers=headers) as result:
            result = result.json()
            self.repr_value = result
            return Document(page_content=orjson_dumps(result))
