from langchain_core.documents import Document

from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.schema.data import JSON, Data


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
        data = [Data.from_document(document) for document in documents]
        self.status = data
        return data
