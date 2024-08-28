import os

import pytest

from tests.api_keys import get_astradb_application_token, get_astradb_api_endpoint
from tests.integration.utils import MockEmbeddings, check_env_vars, valid_nvidia_vectorize_region
from langchain_core.documents import Document

# from langflow.components.memories.AstraDBMessageReader import AstraDBMessageReaderComponent
# from langflow.components.memories.AstraDBMessageWriter import AstraDBMessageWriterComponent
from langflow.components.vectorstores.AstraDB import AstraVectorStoreComponent
from langflow.graph import Graph
from langflow.schema.data import Data
from tests.integration.utils import run_single_component

COLLECTION = "test_basic"
SEARCH_COLLECTION = "test_search"
# MEMORY_COLLECTION = "test_memory"
VECTORIZE_COLLECTION = "test_vectorize"
VECTORIZE_COLLECTION_OPENAI = "test_vectorize_openai"
VECTORIZE_COLLECTION_OPENAI_WITH_AUTH = "test_vectorize_openai_auth"



@pytest.mark.api_key_required
@pytest.mark.asyncio
async def test_astra_setup():
    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()
    embedding = MockEmbeddings()
    results = await run_single_component(AstraVectorStoreComponent, inputs={
        "token": application_token,
        "api_endpoint": api_endpoint,
        "collection_name": COLLECTION,
        "embedding": embedding,
    })
    print(results)

@pytest.mark.api_key_required
def test_astra_embeds_and_search():
    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()
    embedding = MockEmbeddings()

    documents = [Document(page_content="test1"), Document(page_content="test2")]
    records = [Data.from_document(d) for d in documents]

    component = AstraVectorStoreComponent()
    component.build(
        token=application_token,
        api_endpoint=api_endpoint,
        collection_name=SEARCH_COLLECTION,
        embedding=embedding,
        ingest_data=records,
        search_input="test1",
        number_of_results=1,
    )
    component.build_vector_store()
    records = component.search_documents()

    assert len(records) == 1



@pytest.mark.api_key_required
def test_astra_vectorize():
    from langchain_astradb import AstraDBVectorStore, CollectionVectorServiceOptions

    from langflow.components.embeddings.AstraVectorize import AstraVectorizeComponent
    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()

    store = None
    try:
        options = {"provider": "nvidia", "modelName": "NV-Embed-QA"}
        store = AstraDBVectorStore(
            collection_name=VECTORIZE_COLLECTION,
            api_endpoint=api_endpoint,
            token=application_token,
            collection_vector_service_options=CollectionVectorServiceOptions.from_dict(options),
        )


        documents = [Document(page_content="test1"), Document(page_content="test2")]
        records = [Data.from_document(d) for d in documents]

        vectorize = AstraVectorizeComponent()
        vectorize.build(provider="NVIDIA", model_name="NV-Embed-QA")
        vectorize_options = vectorize.build_options()

        component = AstraVectorStoreComponent()
        component.build(
            token=application_token,
            api_endpoint=api_endpoint,
            collection_name=VECTORIZE_COLLECTION,
            ingest_data=records,
            embedding=vectorize_options,
            search_input="test",
            number_of_results=2,
        )
        component.build_vector_store()
        records = component.search_documents()

        assert len(records) == 2
    finally:
        if store is not None:
            store.delete_collection()


@pytest.mark.api_key_required
def test_astra_vectorize_with_provider_api_key():
    """tests vectorize using an openai api key"""
    from langchain_astradb import AstraDBVectorStore, CollectionVectorServiceOptions

    from langflow.components.embeddings.AstraVectorize import AstraVectorizeComponent

    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()

    store = None
    try:
        options = {"provider": "openai", "modelName": "text-embedding-3-small", "parameters": {}, "authentication": {}}
        store = AstraDBVectorStore(
            collection_name=VECTORIZE_COLLECTION_OPENAI,
            api_endpoint=api_endpoint,
            token=application_token,
            collection_vector_service_options=CollectionVectorServiceOptions.from_dict(options),
            collection_embedding_api_key=os.getenv("OPENAI_API_KEY"),
        )
        documents = [Document(page_content="test1"), Document(page_content="test2")]
        records = [Data.from_document(d) for d in documents]

        vectorize = AstraVectorizeComponent()
        vectorize.build(
            provider="OpenAI", model_name="text-embedding-3-small", provider_api_key=os.getenv("OPENAI_API_KEY")
        )
        vectorize_options = vectorize.build_options()

        component = AstraVectorStoreComponent()
        component.build(
            token=application_token,
            api_endpoint=api_endpoint,
            collection_name=VECTORIZE_COLLECTION_OPENAI,
            ingest_data=records,
            embedding=vectorize_options,
            search_input="test",
            number_of_results=4,
        )
        component.build_vector_store()
        records = component.search_documents()
        assert len(records) == 2
    finally:
        if store is not None:
            store.delete_collection()


@pytest.mark.api_key_required
def test_astra_vectorize_passes_authentication():
    """tests vectorize using the authentication parameter"""
    from langchain_astradb import AstraDBVectorStore, CollectionVectorServiceOptions

    from langflow.components.embeddings.AstraVectorize import AstraVectorizeComponent

    store = None
    try:
        application_token = get_astradb_application_token()
        api_endpoint = get_astradb_api_endpoint()
        options = {
            "provider": "openai",
            "modelName": "text-embedding-3-small",
            "parameters": {},
            "authentication": {"providerKey": "apikey"},
        }
        store = AstraDBVectorStore(
            collection_name=VECTORIZE_COLLECTION_OPENAI_WITH_AUTH,
            api_endpoint=api_endpoint,
            token=application_token,
            collection_vector_service_options=CollectionVectorServiceOptions.from_dict(options),
        )
        documents = [Document(page_content="test1"), Document(page_content="test2")]
        records = [Data.from_document(d) for d in documents]

        vectorize = AstraVectorizeComponent()
        vectorize.build(
            provider="OpenAI", model_name="text-embedding-3-small", authentication={"providerKey": "apikey"}
        )
        vectorize_options = vectorize.build_options()

        component = AstraVectorStoreComponent()
        component.build(
            token=application_token,
            api_endpoint=api_endpoint,
            collection_name=VECTORIZE_COLLECTION_OPENAI_WITH_AUTH,
            ingest_data=records,
            embedding=vectorize_options,
            search_input="test",
        )
        component.build_vector_store()
        records = component.search_documents()
        assert len(records) == 2
    finally:
        if store is not None:
            store.delete_collection()
