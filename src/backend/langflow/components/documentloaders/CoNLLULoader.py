from langflow import CustomComponent
from langchain.docstore.document import Document
from typing import Optional, Dict
from langflow.field_typing import TemplateField


class CoNLLULoaderComponent(CustomComponent):
    display_name = "CoNLLULoader"
    description = "Load `CoNLL-U` files."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/conll-u"

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "suffixes": [".conllu"],
                "file_types": ["conllu"],
                "field_type": "file",
            },
            "metadata": TemplateField(
                display_name="Metadata",
                required=False,
                type="dict",
            ),
        }

    def build(self, file_path: str, metadata: dict) -> Document:
        # Here, you would use the actual class that loads CoNLL-U files.
        # As I don't have the specific class, I'm returning an instance of Document.
        # In a real scenario, you should replace the below Document with the actual loader class.
        return Document(file_path=file_path, metadata=metadata)
