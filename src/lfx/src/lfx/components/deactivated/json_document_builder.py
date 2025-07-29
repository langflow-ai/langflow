# JSON Document Builder

# Build a Document containing a JSON object using a key and another Document page content.

# **Params**

# - **Key:** The key to use for the JSON object.
# - **Document:** The Document page to use for the JSON object.

# **Output**

# - **Document:** The Document containing the JSON object.


import orjson
from langchain_core.documents import Document

from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.io import HandleInput, StrInput


class JSONDocumentBuilder(CustomComponent):
    display_name: str = "JSON Document Builder"
    description: str = "Build a Document containing a JSON object using a key and another Document page content."
    name = "JSONDocumentBuilder"
    documentation: str = "https://docs.langflow.org/components/utilities#json-document-builder"
    legacy = True

    inputs = [
        StrInput(
            name="key",
            display_name="Key",
            required=True,
        ),
        HandleInput(
            name="document",
            display_name="Document",
            required=True,
        ),
    ]

    def build(
        self,
        key: str,
        document: Document,
    ) -> Document:
        documents = None
        if isinstance(document, list):
            documents = [Document(page_content=orjson.dumps({key: doc.page_content}).decode()) for doc in document]
        elif isinstance(document, Document):
            documents = Document(page_content=orjson.dumps({key: document.page_content}).decode())
        else:
            msg = f"Expected Document or list of Documents, got {type(document)}"
            raise TypeError(msg)

        self.repr_value = documents
        return documents
