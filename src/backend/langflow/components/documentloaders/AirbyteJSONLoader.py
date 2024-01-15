from langflow import CustomComponent
from langflow.field_typing import Document
from typing import Optional, Dict
from langchain_community.document_loaders.airbyte_json import AirbyteJSONLoader


class AirbyteJSONLoaderComponent(CustomComponent):
    display_name = "AirbyteJSONLoader"
    description = "Load local `Airbyte` json files."
    documentation = (
        "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/airbyte_json"
    )

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "file_types": [".json"],
                "required": True,
                "field_type": "file",
            },
            "metadata": {
                "display_name": "Metadata",
                "field_type": "dict",
                "required": False,
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> Document:
        documents = AirbyteJSONLoader(file_path=file_path).load()
        if(metadata):
            for document in documents:
                if not document.metadata:
                    document.metadata = metadata
                else:
                    document.metadata.update(metadata)
        return documents
