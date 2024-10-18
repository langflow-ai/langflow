import os

import pytest
from astrapy.db import AstraDB
from langchain_core.documents import Document
from langflow.components.embeddings import OpenAIEmbeddingsComponent
from langflow.components.vectorstores import AstraVectorStoreComponent
from langflow.schema.data import Data
from tests.api_keys import get_astradb_api_endpoint, get_astradb_application_token, get_openai_api_key
from tests.integration.components.mock_components import TextToData
from tests.integration.utils import ComponentInputHandle, run_single_component

BASIC_COLLECTION = "test_basic"
SEARCH_COLLECTION = "test_search"
# MEMORY_COLLECTION = "test_memory"
VECTORIZE_COLLECTION = "test_vectorize"
VECTORIZE_COLLECTION_OPENAI = "test_vectorize_openai"
VECTORIZE_COLLECTION_OPENAI_WITH_AUTH = "test_vectorize_openai_auth"
ALL_COLLECTIONS = [
    BASIC_COLLECTION,
    SEARCH_COLLECTION,
    # MEMORY_COLLECTION,
    VECTORIZE_COLLECTION,
    VECTORIZE_COLLECTION_OPENAI,
    VECTORIZE_COLLECTION_OPENAI_WITH_AUTH,
]


@pytest.fixture
def astradb_client(request):
    client = AstraDB(api_endpoint=get_astradb_api_endpoint(), token=get_astradb_application_token())
    yield client
    for collection in ALL_COLLECTIONS:
        client.delete_collection(collection)


@pytest.mark.api_key_required
@pytest.mark.asyncio
async def test_base(astradb_client: AstraDB):
    from langflow.components.embeddings import OpenAIEmbeddingsComponent

    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()

    results = await run_single_component(
        AstraVectorStoreComponent,
        inputs={
            "token": application_token,
            "api_endpoint": api_endpoint,
            "collection_name": BASIC_COLLECTION,
            "embedding": ComponentInputHandle(
                clazz=OpenAIEmbeddingsComponent,
                inputs={"openai_api_key": get_openai_api_key()},
                output_name="embeddings",
            ),
        },
    )
    from langchain_core.vectorstores import VectorStoreRetriever

    assert isinstance(results["base_retriever"], VectorStoreRetriever)
    assert results["vector_store"] is not None
    assert results["search_results"] == []
    assert astradb_client.collection(BASIC_COLLECTION)


@pytest.mark.api_key_required
@pytest.mark.asyncio
async def test_astra_embeds_and_search():
    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()

    results = await run_single_component(
        AstraVectorStoreComponent,
        inputs={
            "token": application_token,
            "api_endpoint": api_endpoint,
            "collection_name": BASIC_COLLECTION,
            "number_of_results": 1,
            "search_input": "test1",
            "ingest_data": ComponentInputHandle(
                clazz=TextToData, inputs={"text_data": ["test1", "test2"]}, output_name="from_text"
            ),
            "embedding": ComponentInputHandle(
                clazz=OpenAIEmbeddingsComponent,
                inputs={"openai_api_key": get_openai_api_key()},
                output_name="embeddings",
            ),
        },
    )
    assert len(results["search_results"]) == 1


@pytest.mark.api_key_required
def test_astra_vectorize():
    from langchain_astradb import AstraDBVectorStore, CollectionVectorServiceOptions

    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()

    store = None
    try:
        options = {"provider": "nvidia", "modelName": "NV-Embed-QA"}
        options_comp = {"provider": "nvidia", "z_00_model_name": "NV-Embed-QA"}

        store = AstraDBVectorStore(
            collection_name=VECTORIZE_COLLECTION,
            api_endpoint=api_endpoint,
            token=application_token,
            collection_vector_service_options=CollectionVectorServiceOptions.from_dict(options),
        )

        documents = [Document(page_content="test1"), Document(page_content="test2")]
        records = [Data.from_document(d) for d in documents]

        component = AstraVectorStoreComponent()
        vectorize_options = component.build_vectorize_options(**options_comp)

        component.build(
            token=application_token,
            api_endpoint=api_endpoint,
            collection_name=VECTORIZE_COLLECTION,
            ingest_data=records,
            search_input="test",
            number_of_results=2,
            pre_delete_collection=True,
        )
        vector_store = component.build_vector_store(vectorize_options)
        records = component.search_documents(vector_store=vector_store)

        assert len(records) == 2
    finally:
        if store is not None:
            store.delete_collection()


@pytest.mark.api_key_required
def test_astra_vectorize_with_provider_api_key():
    """Tests vectorize using an openai api key."""
    from langchain_astradb import AstraDBVectorStore, CollectionVectorServiceOptions

    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()

    store = None
    try:
        options = {
            "provider": "openai",
            "modelName": "text-embedding-3-small",
            "parameters": {},
            "authentication": {"providerKey": "openai"},
        }

        options_comp = {
            "provider": "openai",
            "z_00_model_name": "text-embedding-3-small",
            "z_01_model_parameters": {},
            "z_03_provider_api_key": "openai",
            "z_04_authentication": {},
        }

        store = AstraDBVectorStore(
            collection_name=VECTORIZE_COLLECTION_OPENAI,
            api_endpoint=api_endpoint,
            token=application_token,
            collection_vector_service_options=CollectionVectorServiceOptions.from_dict(options),
            collection_embedding_api_key=os.getenv("OPENAI_API_KEY"),
        )
        documents = [Document(page_content="test1"), Document(page_content="test2")]
        records = [Data.from_document(d) for d in documents]

        component = AstraVectorStoreComponent()
        vectorize_options = component.build_vectorize_options(**options_comp)

        component.build(
            token=application_token,
            api_endpoint=api_endpoint,
            collection_name=VECTORIZE_COLLECTION_OPENAI,
            ingest_data=records,
            search_input="test",
            number_of_results=2,
            pre_delete_collection=True,
        )

        vector_store = component.build_vector_store(vectorize_options)
        records = component.search_documents(vector_store=vector_store)

        assert len(records) == 2
    finally:
        if store is not None:
            store.delete_collection()


@pytest.mark.api_key_required
def test_astra_vectorize_passes_authentication():
    """Tests vectorize using the authentication parameter."""
    from langchain_astradb import AstraDBVectorStore, CollectionVectorServiceOptions

    store = None
    try:
        application_token = get_astradb_application_token()
        api_endpoint = get_astradb_api_endpoint()

        options = {
            "provider": "openai",
            "modelName": "text-embedding-3-small",
            "parameters": {},
            "authentication": {"providerKey": "openai"},
        }
        options_comp = {
            "provider": "openai",
            "z_00_model_name": "text-embedding-3-small",
            "z_01_model_parameters": {},
            "z_04_authentication": {"providerKey": "openai"},
        }

        store = AstraDBVectorStore(
            collection_name=VECTORIZE_COLLECTION_OPENAI_WITH_AUTH,
            api_endpoint=api_endpoint,
            token=application_token,
            collection_vector_service_options=CollectionVectorServiceOptions.from_dict(options),
        )

        documents = [Document(page_content="test1"), Document(page_content="test2")]
        records = [Data.from_document(d) for d in documents]

        component = AstraVectorStoreComponent()
        vectorize_options = component.build_vectorize_options(**options_comp)

        component.build(
            token=application_token,
            api_endpoint=api_endpoint,
            collection_name=VECTORIZE_COLLECTION_OPENAI_WITH_AUTH,
            ingest_data=records,
            search_input="test",
            number_of_results=2,
            pre_delete_collection=True,
        )

        vector_store = component.build_vector_store(vectorize_options)
        records = component.search_documents(vector_store=vector_store)

        assert len(records) == 2
    finally:
        if store is not None:
            store.delete_collection()
