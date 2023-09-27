from typing import List, Optional
import requests
from langflow import CustomComponent
from langchain.schema import Document
from langflow.services.database.models.base import orjson_dumps


class UpdateRequest(CustomComponent):
    display_name: str = "Update Request"
    description: str = "Make a PATCH request to the given URL."
    output_types: list[str] = ["Document"]
    documentation: str = "https://docs.langflow.org/components/utilities#update-request"
    beta = True
    field_config = {
        "url": {"display_name": "URL", "info": "The URL to make the request to."},
        "headers": {
            "display_name": "Headers",
            "field_type": "NestedDict",
            "info": "The headers to send with the request.",
        },
        "code": {"show": False},
        "document": {"display_name": "Document"},
        "method": {
            "display_name": "Method",
            "field_type": "str",
            "info": "The HTTP method to use.",
            "options": ["PATCH", "PUT"],
            "value": "PATCH",
        },
    }

    def update_document(
        self,
        session: requests.Session,
        document: Document,
        url: str,
        headers: Optional[dict] = None,
        method: str = "PATCH",
    ) -> Document:
        try:
            if method == "PATCH":
                response = session.patch(
                    url, headers=headers, data=document.page_content
                )
            elif method == "PUT":
                response = session.put(url, headers=headers, data=document.page_content)
            else:
                raise ValueError(f"Unsupported method: {method}")
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
                metadata={"source": url, "headers": headers, "status_code": 500},
            )

    def build(
        self,
        method: str,
        document: Document,
        url: str,
        headers: Optional[dict] = None,
    ) -> List[Document]:
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
                self.update_document(session, doc, url, headers, method)
                for doc in documents
            ]
            self.repr_value = documents
        return documents
