from langflow import CustomComponent
from langchain.schema import Document
from langflow.services.database.models.base import orjson_dumps
import requests
from typing import Optional


class GetRequest(CustomComponent):
    display_name: str = "GET Request"
    description: str = "Make a GET request to the given URL."
    output_types: list[str] = ["Document"]
    documentation: str = "https://docs.langflow.org/components/utilities#get-request"
    beta = True
    field_config = {
        "url": {
            "display_name": "URL",
            "info": "The URL to make the request to",
            "is_list": True,
        },
        "headers": {
            "display_name": "Headers",
            "info": "The headers to send with the request.",
        },
        "code": {"show": False},
        "timeout": {
            "display_name": "Timeout",
            "field_type": "int",
            "info": "The timeout to use for the request.",
            "value": 5,
        },
    }

    def get_document(
        self, session: requests.Session, url: str, headers: Optional[dict], timeout: int
    ) -> Document:
        try:
            response = session.get(url, headers=headers, timeout=int(timeout))
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
        except requests.Timeout:
            return Document(
                page_content="Request Timed Out",
                metadata={"source": url, "headers": headers, "status_code": 408},
            )
        except Exception as exc:
            return Document(
                page_content=str(exc),
                metadata={"source": url, "headers": headers, "status_code": 500},
            )

    def build(
        self,
        url: str,
        headers: Optional[dict] = None,
        timeout: int = 5,
    ) -> list[Document]:
        if headers is None:
            headers = {}
        urls = url if isinstance(url, list) else [url]
        with requests.Session() as session:
            documents = [self.get_document(session, u, headers, timeout) for u in urls]
            self.repr_value = documents
        return documents
