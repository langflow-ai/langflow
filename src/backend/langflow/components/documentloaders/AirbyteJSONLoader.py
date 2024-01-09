
from langflow import CustomComponent
from langchain.field_typing import Document
from typing import Optional, Dict


class AirbyteJSONLoaderComponent(CustomComponent):
    display_name = "AirbyteJSONLoader"
    description = "Load local `Airbyte` json files."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/airbyte_json"

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "type": "file",
                "fileTypes": ["json"],
                "required": True,
            },
            "metadata": {
                "display_name": "Metadata",
                "type": "dict",
                "required": False,
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> Document:
        # Assuming there is a function or class named AirbyteJSONLoader that takes file_path and metadata as parameters
        # and returns a Document object. Replace AirbyteJSONLoader with the actual class or function name.
        # The actual implementation here is a placeholder and should be adapted to the real AirbyteJSONLoader class or function.
        return AirbyteJSONLoader(file_path=file_path, metadata=metadata)
