import pytest
from astrapy import DataAPIClient
from langchain_astradb import AstraDBVectorStore, VectorServiceOptions
from langchain_core.documents import Document
from lfx.components.datastax import AstraDBVectorStoreComponent
from lfx.components.openai.openai import OpenAIEmbeddingsComponent
from lfx.schema.data import Data

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
def astradb_client():
    api_client = DataAPIClient()
    client = api_client.get_database(get_astradb_api_endpoint(), token=get_astradb_application_token())

    yield client  # Provide the client to the test functions

    # Cleanup: Drop all collections after tests
    for collection in ALL_COLLECTIONS:
        try:  # noqa: SIM105
            client.drop_collection(collection)
        except Exception:  # noqa: S110
            pass


@pytest.mark.api_key_required
async def test_base(astradb_client: DataAPIClient):
    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()

    results = await run_single_component(
        AstraDBVectorStoreComponent,
        inputs={
            "token": application_token,
            "api_endpoint": api_endpoint,
            "collection_name": BASIC_COLLECTION,
            "embedding_model": ComponentInputHandle(
                clazz=OpenAIEmbeddingsComponent,
                inputs={"openai_api_key": get_openai_api_key()},
                output_name="embeddings",
            ),
        },
    )

    assert results["search_results"] == []
    assert astradb_client.get_collection(BASIC_COLLECTION)


@pytest.mark.api_key_required
async def test_astra_embeds_and_search():
    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()

    results = await run_single_component(
        AstraDBVectorStoreComponent,
        inputs={
            "token": application_token,
            "api_endpoint": api_endpoint,
            "collection_name": BASIC_COLLECTION,
            "number_of_results": 1,
            "search_query": "test1",
            "ingest_data": ComponentInputHandle(
                clazz=TextToData, inputs={"text_data": ["test1", "test2"]}, output_name="from_text"
            ),
            "embedding_model": ComponentInputHandle(
                clazz=OpenAIEmbeddingsComponent,
                inputs={"openai_api_key": get_openai_api_key()},
                output_name="embeddings",
            ),
        },
    )
    assert len(results["search_results"]) == 1


@pytest.mark.api_key_required
def test_astra_vectorize():
    application_token = get_astradb_application_token()
    api_endpoint = get_astradb_api_endpoint()

    store = None
    try:
        # Get the vectorize options
        options = {"provider": "nvidia", "modelName": "NV-Embed-QA"}

        store = AstraDBVectorStore(
            collection_name=VECTORIZE_COLLECTION,
            api_endpoint=api_endpoint,
            token=application_token,
            collection_vector_service_options=VectorServiceOptions._from_dict(options),
        )

        documents = [Document(page_content="test1"), Document(page_content="test2")]
        records = [Data.from_document(d) for d in documents]

        component = AstraDBVectorStoreComponent()

        component.build(
            token=application_token,
            api_endpoint=api_endpoint,
            collection_name=VECTORIZE_COLLECTION,
            ingest_data=records,
            search_query="test",
            number_of_results=2,
        )
        vector_store = component.build_vector_store()
        records = component.search_documents(vector_store=vector_store)

        assert len(records) == 2
    finally:
        if store is not None:
            store.delete_collection()


@pytest.mark.api_key_required
def test_astra_vectorize_with_provider_api_key():
    """Tests vectorize using an openai api key."""
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

        store = AstraDBVectorStore(
            collection_name=VECTORIZE_COLLECTION_OPENAI,
            api_endpoint=api_endpoint,
            token=application_token,
            collection_vector_service_options=VectorServiceOptions._from_dict(options),
            collection_embedding_api_key=get_openai_api_key(),
        )
        documents = [Document(page_content="test1"), Document(page_content="test2")]
        records = [Data.from_document(d) for d in documents]

        component = AstraDBVectorStoreComponent()

        component.build(
            token=application_token,
            api_endpoint=api_endpoint,
            collection_name=VECTORIZE_COLLECTION_OPENAI,
            ingest_data=records,
            search_query="test",
            number_of_results=2,
        )

        vector_store = component.build_vector_store()
        records = component.search_documents(vector_store=vector_store)

        assert len(records) == 2
    finally:
        if store is not None:
            store.delete_collection()


@pytest.mark.api_key_required
def test_astra_vectorize_passes_authentication():
    """Tests vectorize using the authentication parameter."""
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

        store = AstraDBVectorStore(
            collection_name=VECTORIZE_COLLECTION_OPENAI_WITH_AUTH,
            api_endpoint=api_endpoint,
            token=application_token,
            collection_vector_service_options=VectorServiceOptions._from_dict(options),
        )

        documents = [Document(page_content="test1"), Document(page_content="test2")]
        records = [Data.from_document(d) for d in documents]

        component = AstraDBVectorStoreComponent()

        component.build(
            token=application_token,
            api_endpoint=api_endpoint,
            collection_name=VECTORIZE_COLLECTION_OPENAI_WITH_AUTH,
            ingest_data=records,
            search_query="test",
            number_of_results=2,
        )

        vector_store = component.build_vector_store()
        records = component.search_documents(vector_store=vector_store)

        assert len(records) == 2
    finally:
        if store is not None:
            store.delete_collection()
