from langflow import CustomComponent
from langchain.document_loaders import Document
from typing import Optional, Dict


class UnstructuredPowerPointLoaderComponent(CustomComponent):
    display_name = "UnstructuredPowerPointLoader"
    description = "Load `Microsoft PowerPoint` files using `Unstructured`."

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "type": "file",
                "fileTypes": ["pptx", "ppt"],
            },
            "metadata": {
                "display_name": "Metadata",
                "type": "dict",
            },
        }

    def build(
        self,
        file_path: str,
        metadata: Optional[Dict] = None,
    ) -> Document:
        # Assuming there is a loader class `UnstructuredPowerPointLoader` that takes these parameters
        # Since the actual loader class is not provided, this is a placeholder for the actual implementation
        loader_class = self.get_loader_class()  # Placeholder method to obtain the correct loader class
        return loader_class(file_path=file_path, metadata=metadata)
