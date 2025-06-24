import json

import tiktoken
from docling_core.transforms.chunker import BaseChunker, DocMeta
from docling_core.transforms.chunker.hierarchical_chunker import HierarchicalChunker
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

from langflow.base.data.docling_utils import extract_docling_documents
from langflow.custom import Component
from langflow.io import DropdownInput, HandleInput, IntInput, MessageTextInput, Output, StrInput
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
            real_time_refresh=True,
        ),
        DropdownInput(
            name="provider",
            display_name="Provider",
            options=["Hugging Face", "OpenAI"],
            info=("Which tokenizer provider."),
            value="Hugging Face",
            show=True,
            real_time_refresh=True,
            advanced=True,
            dynamic=True,
        ),
        StrInput(
            name="hf_model_name",
            display_name="HF model name",
            info=(
                "Model name of the tokenizer to use with the HybridChunker when Hugging Face is chosen as a tokenizer."
            ),
            value="sentence-transformers/all-MiniLM-L6-v2",
            show=True,
            advanced=True,
            dynamic=True,
        ),
        StrInput(
            name="openai_model_name",
            display_name="OpenAI model name",
            info=("Model name of the tokenizer to use with the HybridChunker when OpenAI is chosen as a tokenizer."),
            value="gpt-4o",
            show=False,
            advanced=True,
            dynamic=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Maximum tokens",
            info=("Maximum number of tokens for the HybridChunker."),
            show=True,
            required=False,
            advanced=True,
            dynamic=True,
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

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        if field_name == "chunker":
            provider_type = build_config["provider"]["value"]
            is_hf = provider_type == "Hugging Face"
            is_openai = provider_type == "OpenAI"
            if field_value == "HybridChunker":
                build_config["provider"]["show"] = True
                build_config["hf_model_name"]["show"] = is_hf
                build_config["openai_model_name"]["show"] = is_openai
                build_config["max_tokens"]["show"] = True
            else:
                build_config["provider"]["show"] = False
                build_config["hf_model_name"]["show"] = False
                build_config["openai_model_name"]["show"] = False
                build_config["max_tokens"]["show"] = False
        elif field_name == "provider" and build_config["chunker"]["value"] == "HybridChunker":
            if field_value == "Hugging Face":
                build_config["hf_model_name"]["show"] = True
                build_config["openai_model_name"]["show"] = False
            elif field_value == "OpenAI":
                build_config["hf_model_name"]["show"] = False
                build_config["openai_model_name"]["show"] = True

        return build_config

    def _docs_to_data(self, docs) -> list[Data]:
        return [Data(text=doc.page_content, data=doc.metadata) for doc in docs]

    def chunk_documents(self) -> DataFrame:
        documents = extract_docling_documents(self.data_inputs, self.doc_key)

        chunker: BaseChunker
        if self.chunker == "HybridChunker":
            max_tokens: int | None = self.max_tokens if self.max_tokens else None
            if self.provider == "Hugging Face":
                tokenizer = HuggingFaceTokenizer.from_pretrained(
                    model_name=self.hf_model_name,
                    max_tokens=max_tokens,
                )
            elif self.provider == "OpenAI":
                if max_tokens is None:
                    max_tokens = 128 * 1024  # context window length required for OpenAI tokenizers
                tokenizer = OpenAITokenizer(
                    tokenizer=tiktoken.encoding_for_model(self.openai_model_name), max_tokens=max_tokens
                )
            chunker = HybridChunker(
                tokenizer=tokenizer,
            )
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
