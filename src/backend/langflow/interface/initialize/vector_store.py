from typing import Type
from langchain.vectorstores import Pinecone, Qdrant, Chroma


def docs_in_params(params: dict) -> bool:
    """Check if params has documents OR texts and one of them is not an empty list,
    If any of them is not an empty list, return True, else return False"""
    return ("documents" in params and params["documents"]) or (
        "texts" in params and params["texts"]
    )


def initialize_pinecone(class_object: Type[Pinecone], params: dict):
    """Initialize pinecone and return the class object"""

    import pinecone

    PINECONE_API_KEY = params.get("pinecone_api_key")
    PINECONE_ENV = params.get("pinecone_env")

    if PINECONE_API_KEY is None or PINECONE_ENV is None:
        raise ValueError(
            "Pinecone API key and environment must be provided in the params"
        )

    # initialize pinecone
    pinecone.init(
        api_key=PINECONE_API_KEY,  # find at app.pinecone.io
        environment=PINECONE_ENV,  # next to api key in console
    )

    # If there are no docs in the params, return an existing index
    # but first remove any texts or docs keys from the params
    if not docs_in_params(params):
        existing_index_params = {
            "embedding": params.pop("embedding"),
        }
        if "index_name" in params:
            existing_index_params["index_name"] = params.pop("index_name")
        if "namespace" in params:
            existing_index_params["namespace"] = params.pop("namespace")

        return class_object.from_existing_index(**existing_index_params)
    # If there are docs in the params, create a new index
    if "texts" in params:
        params["documents"] = params.pop("texts")
    return class_object.from_documents(**params)


def initialize_chroma(class_object: Type[Chroma], params: dict):
    """Initialize a ChromaDB object from the params"""
    persist = params.pop("persist", False)
    if not docs_in_params(params):
        if "texts" in params:
            params["documents"] = params.pop("texts")
        for doc in params["documents"]:
            if doc.metadata is None:
                doc.metadata = {}
            for key, value in doc.metadata.items():
                if value is None:
                    doc.metadata[key] = ""
        chromadb = class_object.from_documents(**params)
    else:
        chromadb = class_object(**params)
    if persist:
        chromadb.persist()
    return chromadb


def initialize_qdrant(class_object: Type[Qdrant], params: dict):
    if not docs_in_params(params):
        if "location" not in params and "api_key" not in params:
            raise ValueError("Location and API key must be provided in the params")
        from qdrant_client import QdrantClient

        client_params = {
            "location": params.pop("location"),
            "api_key": params.pop("api_key"),
        }
        lc_params = {
            "collection_name": params.pop("collection_name"),
            "embeddings": params.pop("embedding"),
        }
        client = QdrantClient(**client_params)

        return class_object(client=client, **lc_params)

    return class_object.from_documents(**params)
