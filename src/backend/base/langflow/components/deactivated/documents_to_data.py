from langchain_core.documents import Document

from langflow.custom import CustomComponent
from langflow.schema import JSON


class DocumentsToDataComponent(CustomComponent):
    display_name = "Documents ⇢ Data"
    description = "Convert LangChain Documents into Data."
    icon = "LangChain"
    name = "DocumentsToData"

    field_config = {
        "documents": {"display_name": "Documents"},
    }

    def build(self, documents: list[Document]) -> list[JSON]:
        if isinstance(documents, Document):
            documents = [documents]
        data = [JSON.from_document(document) for document in documents]
        self.status = data
        return data
