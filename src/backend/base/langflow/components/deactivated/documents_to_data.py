from langchain_core.documents import Document

from langflow.custom.custom_component.component import Component
from langflow.schema.data import Data


class DocumentsToDataComponent(Component):
    display_name = "Documents ⇢ Data"
    description = "Convert LangChain Documents into Data."
    icon = "LangChain"
    name = "DocumentsToData"

    field_config = {
        "documents": {"display_name": "Documents"},
    }

    def build(self, documents: list[Document]) -> list[Data]:
        if isinstance(documents, Document):
            documents = [documents]
        data = [Data.from_document(document) for document in documents]
        self.status = data
        return data
