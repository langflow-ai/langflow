
from langflow import CustomComponent
from langchain.documents import Document
from typing import Optional, Dict
from langchain.field_typing import TemplateField


class CoNLLULoaderComponent(CustomComponent):
    display_name = "CoNLLULoader"
    description = "Load `CoNLL-U` files."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/conll-u"

    def build_config(self):
        return {
            "file_path": TemplateField(
                display_name="File Path",
                required=True,
                type="file",
                file_types=["conllu"],
                suffixes=['.conllu'],
            ),
            "metadata": TemplateField(
                display_name="Metadata",
                required=False,
                type="dict",
            ),
        }

    def build(self, file_path: str, metadata: Optional[Dict[str, str]] = None) -> Document:
        # Here, you would use the actual class that loads CoNLL-U files.
        # As I don't have the specific class, I'm returning an instance of Document.
        # In a real scenario, you should replace the below Document with the actual loader class.
        return Document(file_path=file_path, metadata=metadata)
