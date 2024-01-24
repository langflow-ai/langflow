from langflow import CustomComponent
from langchain.docstore.document import Document
from langchain_community.document_loaders.conllu import CoNLLULoader


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
            "metadata": {
                "display_name": "Metadata",
                "field_type": "dict",
                "required": False,
            },
        }

    def build(self, file_path: str, metadata: dict) -> Document:
        documents = CoNLLULoader(file_path=file_path).load()
        if metadata:
            for document in documents:
                if not document.metadata:
                    document.metadata = metadata
                else:
                    document.metadata.update(metadata)
        return documents
