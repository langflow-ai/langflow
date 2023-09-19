from langflow import CustomComponent
from langchain.schema import Document
from langflow.services.database.models.base import orjson_dumps
import requests
from typing import Optional


class PostRequest(CustomComponent):
    display_name: str = "POST Request"
    description: str = "Make a POST request to the given URL."
    output_types: list[str] = ["Document"]
    documentation: str = "https://docs.langflow.org/components/utilities#post-request"
    beta = True
    field_config = {
        "url": {"display_name": "URL", "info": "The URL to make the request to."},
        "headers": {
            "display_name": "Headers",
            "info": "The headers to send with the request.",
        },
        "code": {"show": False},
        "document": {"display_name": "Document"},
    }

    def post_document(
        self,
        session: requests.Session,
        document: Document,
        url: str,
        headers: Optional[dict] = None,
    ) -> Document:
        try:
            response = session.post(url, headers=headers, data=document.page_content)
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
                    "status_code": response,
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
        document: Document,
        url: str,
        headers: Optional[dict] = None,
    ) -> list[Document]:
        if headers is None:
            headers = {}

        if not isinstance(document, list) and isinstance(document, Document):
            documents: list[Document] = [document]
        elif isinstance(document, list) and all(
            isinstance(doc, Document) for doc in document
        ):
            documents = document
        else:
            raise ValueError("document must be a Document or a list of Documents")

        with requests.Session() as session:
            documents = [
                self.post_document(session, doc, url, headers) for doc in documents
            ]
            self.repr_value = documents
        return documents
