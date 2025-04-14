# JSON Document Builder

# Build a Document containing a JSON object using a key and another Document page content.

# **Params**

# - **Key:** The key to use for the JSON object.
# - **Document:** The Document page to use for the JSON object.

# **Output**

# - **Document:** The Document containing the JSON object.

from langchain_core.documents import Document

from langflow.custom.custom_component.custom_component import CustomComponent
from langflow.services.database.models.base import orjson_dumps


class JSONDocumentBuilder(CustomComponent):
    display_name: str = "JSON Document Builder"
    description: str = "Build a Document containing a JSON object using a key and another Document page content."
    name = "JSONDocumentBuilder"
    legacy: bool = True

    output_types: list[str] = ["Document"]
    documentation: str = "https://docs.langflow.org/components/utilities#json-document-builder"

    field_config = {
        "key": {"display_name": "Key"},
        "document": {"display_name": "Document"},
    }

    def build(
        self,
        key: str,
        document: Document,
    ) -> Document:
        documents = None
        if isinstance(document, list):
            documents = [
                Document(page_content=orjson_dumps({key: doc.page_content}, indent_2=False)) for doc in document
            ]
        elif isinstance(document, Document):
            documents = Document(page_content=orjson_dumps({key: document.page_content}, indent_2=False))
        else:
            msg = f"Expected Document or list of Documents, got {type(document)}"
            raise TypeError(msg)
        self.repr_value = documents
        return documents
