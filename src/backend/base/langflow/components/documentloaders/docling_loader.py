from docling import Docling

from langflow.custom import Component
from langflow.io import Output
from langflow.schema import Data


class DoclingLoaderComponent(Component):
    display_name = "Docling Document Loader"
    description = "Component for loading and processing documents using Docling library."
    documentation = "https://github.com/DS4SD/docling"
    name = "DoclingLoader"
    icon = "Docling"

    inputs = [
        {
            "name": "file_path",
            "display_name": "File Path",
            "type": "str",
            "required": True,
            "info": "Path to the document file to be loaded.",
        },
        {
            "name": "config",
            "display_name": "Docling Configuration",
            "type": "dict",
            "required": False,
            "info": "Configuration for Docling library.",
        },
    ]

    outputs = [
        Output(display_name="Data", name="data", method="load_document"),
    ]

    def load_document(self) -> Data:
        file_path = self.get_input("file_path")
        config = self.get_input("config") or {}
        docling = Docling(**config)
        document = docling.parse(file_path)
        return Data.from_document(document)
