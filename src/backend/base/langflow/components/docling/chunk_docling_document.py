import json
from typing import TYPE_CHECKING

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
        Output(display_name="Chunks", name="chunks", method="chunk_documents"),
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    def _docs_to_data(self, docs) -> list[Data]:
        return [Data(text=doc.page_content, data=doc.metadata) for doc in docs]

    def chunk_documents(self) -> list[Data]:
        from docling.chunking import BaseChunker, DocMeta, HierarchicalChunker, HybridChunker

        if TYPE_CHECKING:
            from docling_core.types.doc import DoclingDocument

        documents: list[DoclingDocument] = []
        if isinstance(self.data_inputs, DataFrame):
            if not len(self.data_inputs):
                msg = "DataFrame is empty"
                raise TypeError(msg)

            try:
                documents = self.data_inputs[self.doc_key].to_list()
            except Exception as e:
                msg = f"Error extracting DoclingDocument from DataFrame: {e}"
                raise TypeError(msg) from e
        else:
            if not self.data_inputs:
                msg = "No data inputs provided"
                raise TypeError(msg)

            if isinstance(self.data_inputs, Data):
                if self.doc_key not in self.data_inputs.data:
                    msg = f"{self.doc_key} field not available in the input Data"
                    raise TypeError(msg)
                documents = [self.data_inputs.data[self.doc_key]]
            else:
                try:
                    documents = [
                        input_.data[self.doc_key]
                        for input_ in self.data_inputs
                        if isinstance(input_, Data) and self.doc_key in input_.data
                    ]
                    if not documents:
                        msg = f"No valid Data inputs found in {type(self.data_inputs)}"
                        raise TypeError(msg)
                except AttributeError as e:
                    msg = f"Invalid input type in collection: {e}"
                    raise TypeError(msg) from e

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

        return results

    def as_dataframe(self) -> DataFrame:
        return DataFrame(self.chunk_documents())
