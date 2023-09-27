from typing import Any, Callable, Dict, Type
from langchain.vectorstores import (
    Pinecone,
    Qdrant,
    Chroma,
    FAISS,
    Weaviate,
    SupabaseVectorStore,
    MongoDBAtlasVectorSearch,
)
from langchain.schema import Document
import os

import orjson


def docs_in_params(params: dict) -> bool:
    """Check if params has documents OR texts and one of them is not an empty list,
    If any of them is not an empty list, return True, else return False"""
    return ("documents" in params and params["documents"]) or (
        "texts" in params and params["texts"]
    )


def initialize_mongodb(class_object: Type[MongoDBAtlasVectorSearch], params: dict):
    """Initialize mongodb and return the class object"""

    MONGODB_ATLAS_CLUSTER_URI = params.pop("mongodb_atlas_cluster_uri")
    if not MONGODB_ATLAS_CLUSTER_URI:
        raise ValueError("Mongodb atlas cluster uri must be provided in the params")
    from pymongo import MongoClient
    import certifi

    client: MongoClient = MongoClient(
        MONGODB_ATLAS_CLUSTER_URI, tlsCAFile=certifi.where()
    )
    db_name = params.pop("db_name", None)
    collection_name = params.pop("collection_name", None)
    if not db_name or not collection_name:
        raise ValueError("db_name and collection_name must be provided in the params")

    index_name = params.pop("index_name", None)
    if not index_name:
        raise ValueError("index_name must be provided in the params")

    collection = client[db_name][collection_name]
    if not docs_in_params(params):
        # __init__ requires collection, embedding and index_name
        init_args = {
            "collection": collection,
            "index_name": index_name,
            "embedding": params.get("embedding"),
        }

        return class_object(**init_args)

    if "texts" in params:
        params["documents"] = params.pop("texts")

    params["collection"] = collection
    params["index_name"] = index_name

    return class_object.from_documents(**params)


def initialize_supabase(class_object: Type[SupabaseVectorStore], params: dict):
    """Initialize supabase and return the class object"""
    from supabase.client import Client, create_client

    if "supabase_url" not in params or "supabase_service_key" not in params:
        raise ValueError("Supabase url and service key must be provided in the params")
    if "texts" in params:
        params["documents"] = params.pop("texts")

    client_kwargs = {
        "supabase_url": params.pop("supabase_url"),
        "supabase_key": params.pop("supabase_service_key"),
    }

    supabase: Client = create_client(**client_kwargs)
    if not docs_in_params(params):
        params.pop("documents", None)
        params.pop("texts", None)
        return class_object(client=supabase, **params)
    # If there are docs in the params, create a new index

    return class_object.from_documents(client=supabase, **params)


def initialize_weaviate(class_object: Type[Weaviate], params: dict):
    """Initialize weaviate and return the class object"""
    if not docs_in_params(params):
        import weaviate  # type: ignore

        client_kwargs_json = params.get("client_kwargs", "{}")
        client_kwargs = orjson.loads(client_kwargs_json)
        client_params = {
            "url": params.get("weaviate_url"),
        }
        client_params.update(client_kwargs)
        weaviate_client = weaviate.Client(**client_params)

        new_params = {
            "client": weaviate_client,
            "index_name": params.get("index_name"),
            "text_key": params.get("text_key"),
        }
        return class_object(**new_params)
    # If there are docs in the params, create a new index
    if "texts" in params:
        params["documents"] = params.pop("texts")

    return class_object.from_documents(**params)


def initialize_faiss(class_object: Type[FAISS], params: dict):
    """Initialize faiss and return the class object"""

    if not docs_in_params(params):
        return class_object.load_local

    save_local = params.get("save_local")
    faiss_index = class_object(**params)
    if save_local:
        faiss_index.save_local(folder_path=save_local)
    return faiss_index


def initialize_pinecone(class_object: Type[Pinecone], params: dict):
    """Initialize pinecone and return the class object"""

    import pinecone  # type: ignore

    pinecone_api_key = params.pop("pinecone_api_key")
    pinecone_env = params.pop("pinecone_env")

    if pinecone_api_key is None or pinecone_env is None:
        if os.getenv("PINECONE_API_KEY") is not None:
            pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if os.getenv("PINECONE_ENV") is not None:
            pinecone_env = os.getenv("PINECONE_ENV")

    if pinecone_api_key is None or pinecone_env is None:
        raise ValueError(
            "Pinecone API key and environment must be provided in the params"
        )

    # initialize pinecone
    pinecone.init(
        api_key=pinecone_api_key,  # find at app.pinecone.io
        environment=pinecone_env,  # next to api key in console
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
    if (  # type: ignore
        "chroma_server_host" in params or "chroma_server_http_port" in params
    ):
        import chromadb  # type: ignore

        settings_params = {
            key: params[key]
            for key, value_ in params.items()
            if key.startswith("chroma_server_") and value_
        }
        chroma_settings = chromadb.config.Settings(**settings_params)
        params["client_settings"] = chroma_settings
    else:
        # remove all chroma_server_ keys from params
        params = {
            key: value
            for key, value in params.items()
            if not key.startswith("chroma_server_")
        }

    persist = params.pop("persist", False)
    if not docs_in_params(params):
        params.pop("documents", None)
        params.pop("texts", None)
        params["embedding_function"] = params.pop("embedding")
        chromadb = class_object(**params)
    else:
        if "texts" in params:
            params["documents"] = params.pop("texts")
        for doc in params["documents"]:
            if not isinstance(doc, Document):
                # remove any non-Document objects from the list
                params["documents"].remove(doc)
                continue
            if doc.metadata is None:
                doc.metadata = {}
            for key, value in doc.metadata.items():
                if value is None:
                    doc.metadata[key] = ""

        chromadb = class_object.from_documents(**params)
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


vecstore_initializer: Dict[str, Callable[[Type[Any], dict], Any]] = {
    "Pinecone": initialize_pinecone,
    "Chroma": initialize_chroma,
    "Qdrant": initialize_qdrant,
    "Weaviate": initialize_weaviate,
    "FAISS": initialize_faiss,
    "SupabaseVectorStore": initialize_supabase,
    "MongoDBAtlasVectorSearch": initialize_mongodb,
}
