from typing import List

from langchain_core.documents import Document

from langflow.custom import CustomComponent
from langflow.schema import Data


class DocumentToDataComponent(CustomComponent):
    display_name = "Documents To Data"
    description = "Convert LangChain Documents into Data."

    field_config = {
        "documents": {"display_name": "Documents"},
    }

    def build(self, documents: List[Document]) -> List[Data]:
        if isinstance(documents, Document):
            documents = [documents]
        data = [Data.from_document(document) for document in documents]
        self.status = data
        return data
