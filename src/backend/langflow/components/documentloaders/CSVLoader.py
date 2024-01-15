
from langflow import CustomComponent
from typing import List
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain.docstore.document import Document

class CSVLoaderComponent(CustomComponent):
    display_name = "CSVLoader"
    description = "Load a `CSV` file into a list of Documents."

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "suffixes": [".csv"],
                "file_types": ["csv"],
                "field_type": "file",
            },
            "metadata": {
                "display_name": "Metadata",
                "required": False,
            },
        }

    def build(
        self,
        file_path: str,
        metadata: dict
    ) -> List[Document]:
        documents = CSVLoader(file_path=file_path).load()
        if(metadata):
            for document in documents:
                if not document.metadata:
                    document.metadata = metadata
                else:
                    document.metadata.update(metadata)
        return documents
