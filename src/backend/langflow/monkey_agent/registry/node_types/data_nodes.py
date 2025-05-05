"""
Data node definitions for the enhanced node registry.

This module contains definitions for data nodes such as DocumentLoader, TextSplitter,
VectorStore, etc.
"""

from typing import Dict
from ..node_registry import (
    EnhancedNodeType,
    InputField,
    OutputField,
    ConnectionFormat,
)

# Registry of data nodes
DATA_NODES: Dict[str, EnhancedNodeType] = {}

# DocumentLoader node
document_loader = EnhancedNodeType(
    id="DocumentLoader",
    displayName="Document Loader",
    description="Loads documents from various sources",
    category="Data",
    inputs={
        "source": InputField(
            type=["str", "File"],
            displayName="Source",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="source",
                handleFormat="{\"fieldName\": \"source\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\", \"File\"], \"type\": \"str\"}"
            )
        )
    },
    outputs={
        "documents": OutputField(
            type=["Document", "List[Document]"],
            displayName="Documents",
            connectionFormat=ConnectionFormat(
                fieldName="documents",
                handleFormat="{\"dataType\": \"DocumentLoader\", \"id\": \"NODE_ID\", \"name\": \"documents\", \"output_types\": [\"Document\", \"List[Document]\"]}"
            )
        )
    }
)
DATA_NODES[document_loader.id] = document_loader

# TextSplitter node
text_splitter = EnhancedNodeType(
    id="TextSplitter",
    displayName="Text Splitter",
    description="Splits documents into chunks",
    category="Data",
    inputs={
        "documents": InputField(
            type=["Document", "List[Document]", "str"],
            displayName="Documents",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="documents",
                handleFormat="{\"fieldName\": \"documents\", \"id\": \"NODE_ID\", \"inputTypes\": [\"Document\", \"List[Document]\", \"str\"], \"type\": \"list\"}"
            )
        ),
        "chunk_size": InputField(
            type=["int"],
            displayName="Chunk Size",
            required=False,
            connectionFormat=ConnectionFormat(
                fieldName="chunk_size",
                handleFormat="{\"fieldName\": \"chunk_size\", \"id\": \"NODE_ID\", \"inputTypes\": [\"int\"], \"type\": \"int\"}"
            )
        ),
        "chunk_overlap": InputField(
            type=["int"],
            displayName="Chunk Overlap",
            required=False,
            connectionFormat=ConnectionFormat(
                fieldName="chunk_overlap",
                handleFormat="{\"fieldName\": \"chunk_overlap\", \"id\": \"NODE_ID\", \"inputTypes\": [\"int\"], \"type\": \"int\"}"
            )
        )
    },
    outputs={
        "chunks": OutputField(
            type=["List[Document]"],
            displayName="Chunks",
            connectionFormat=ConnectionFormat(
                fieldName="chunks",
                handleFormat="{\"dataType\": \"TextSplitter\", \"id\": \"NODE_ID\", \"name\": \"chunks\", \"output_types\": [\"List[Document]\"]}"
            )
        )
    }
)
DATA_NODES[text_splitter.id] = text_splitter

# VectorStore node
vector_store = EnhancedNodeType(
    id="VectorStore",
    displayName="Vector Store",
    description="Stores and retrieves document vectors",
    category="Data",
    inputs={
        "documents": InputField(
            type=["Document", "List[Document]"],
            displayName="Documents",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="documents",
                handleFormat="{\"fieldName\": \"documents\", \"id\": \"NODE_ID\", \"inputTypes\": [\"Document\", \"List[Document]\"], \"type\": \"list\"}"
            )
        ),
        "embedding": InputField(
            type=["Embedding"],
            displayName="Embedding",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="embedding",
                handleFormat="{\"fieldName\": \"embedding\", \"id\": \"NODE_ID\", \"inputTypes\": [\"Embedding\"], \"type\": \"object\"}"
            )
        )
    },
    outputs={
        "vectorstore": OutputField(
            type=["VectorStore"],
            displayName="Vector Store",
            connectionFormat=ConnectionFormat(
                fieldName="vectorstore",
                handleFormat="{\"dataType\": \"VectorStore\", \"id\": \"NODE_ID\", \"name\": \"vectorstore\", \"output_types\": [\"VectorStore\"]}"
            )
        )
    }
)
DATA_NODES[vector_store.id] = vector_store

# Retriever node
retriever = EnhancedNodeType(
    id="Retriever",
    displayName="Retriever",
    description="Retrieves documents from a vector store",
    category="Data",
    inputs={
        "vectorstore": InputField(
            type=["VectorStore"],
            displayName="Vector Store",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="vectorstore",
                handleFormat="{\"fieldName\": \"vectorstore\", \"id\": \"NODE_ID\", \"inputTypes\": [\"VectorStore\"], \"type\": \"object\"}"
            )
        ),
        "query": InputField(
            type=["str", "Message"],
            displayName="Query",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="query",
                handleFormat="{\"fieldName\": \"query\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\", \"Message\"], \"type\": \"str\"}"
            )
        ),
        "k": InputField(
            type=["int"],
            displayName="Number of Results",
            required=False,
            connectionFormat=ConnectionFormat(
                fieldName="k",
                handleFormat="{\"fieldName\": \"k\", \"id\": \"NODE_ID\", \"inputTypes\": [\"int\"], \"type\": \"int\"}"
            )
        )
    },
    outputs={
        "documents": OutputField(
            type=["List[Document]"],
            displayName="Documents",
            connectionFormat=ConnectionFormat(
                fieldName="documents",
                handleFormat="{\"dataType\": \"Retriever\", \"id\": \"NODE_ID\", \"name\": \"documents\", \"output_types\": [\"List[Document]\"]}"
            )
        )
    }
)
DATA_NODES[retriever.id] = retriever

# OpenAIEmbedding node - example of a specific embedding model node
openai_embedding = EnhancedNodeType(
    id="OpenAIEmbeddings",
    displayName="OpenAI Embeddings",
    description="Generates embeddings using OpenAI's embedding models",
    category="Data",
    inputs={
        "text": InputField(
            type=["str", "Message", "Document"],
            displayName="Text",
            required=True,
            connectionFormat=ConnectionFormat(
                fieldName="text",
                handleFormat="{\"fieldName\": \"text\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\", \"Message\", \"Document\"], \"type\": \"str\"}"
            )
        ),
        "model": InputField(
            type=["str"],
            displayName="Model Name",
            required=False,
            connectionFormat=ConnectionFormat(
                fieldName="model",
                handleFormat="{\"fieldName\": \"model\", \"id\": \"NODE_ID\", \"inputTypes\": [\"str\"], \"type\": \"str\"}"
            )
        )
    },
    outputs={
        "embedding": OutputField(
            type=["Embedding"],
            displayName="Embedding",
            connectionFormat=ConnectionFormat(
                fieldName="embedding",
                handleFormat="{\"dataType\": \"OpenAIEmbeddings\", \"id\": \"NODE_ID\", \"name\": \"embedding\", \"output_types\": [\"Embedding\"]}"
            )
        )
    }
)
DATA_NODES[openai_embedding.id] = openai_embedding
