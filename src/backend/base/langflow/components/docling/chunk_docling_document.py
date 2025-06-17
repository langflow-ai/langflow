import json

from langflow.custom import Component
from langflow.io import DropdownInput, HandleInput, MessageTextInput, Output
from langflow.schema import Data, DataFrame


class ChunkDoclingDocumentComponent(Component):
    display_name: str = "Chunk DoclingDocument"
    description: str = "Use the DocumentDocument chunkers to split the document into chunks."
    documentation = "https://docling-project.github.io/docling/concepts/chunking/"
    icon = "Docling"
    name = "ChunkDoclingDocument"

    inputs = [
        HandleInput(
            name="data_inputs",
            display_name="Data or DataFrame",
            info="The data with documents to split in chunks.",
            input_types=["Data", "DataFrame"],
            required=True,
        ),
        DropdownInput(
            name="chunker",
            display_name="Chunker",
            options=["HybridChunker", "HierarchicalChunker"],
            info=("Which chunker to use."),
            value="HybridChunker",
        ),
        MessageTextInput(
            name="doc_key",
            display_name="Doc Key",
            info="The key to use for the DoclingDocument column.",
            value="doc",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="DataFrame", name="dataframe", method="chunk_documents"),
    ]

    def _docs_to_data(self, docs) -> list[Data]:
        return [Data(text=doc.page_content, data=doc.metadata) for doc in docs]

    def chunk_documents(self) -> DataFrame:
        from docling.chunking import BaseChunker, DocMeta, HierarchicalChunker, HybridChunker

        from langflow.components.docling._utils import extract_docling_documents

        documents = extract_docling_documents(self.data_inputs, self.doc_key)

        chunker: BaseChunker
        if self.chunker == "HybridChunker":
            chunker = HybridChunker()
        elif self.chunker == "HierarchicalChunker":
            chunker = HierarchicalChunker()

        results: list[Data] = []
        try:
            for doc in documents:
                for chunk in chunker.chunk(dl_doc=doc):
                    enriched_text = chunker.contextualize(chunk=chunk)
                    meta = DocMeta.model_validate(chunk.meta)

                    results.append(
                        Data(
                            data={
                                "text": enriched_text,
                                "document_id": f"{doc.origin.binary_hash}",
                                "doc_items": json.dumps([item.self_ref for item in meta.doc_items]),
                            }
                        )
                    )

        except Exception as e:
            msg = f"Error splitting text: {e}"
            raise TypeError(msg) from e

        return DataFrame(results)
