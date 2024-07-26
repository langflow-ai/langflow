import os

from langchain_astradb import AstraDBVectorStore, CollectionVectorServiceOptions
from langflow.components.embeddings.AstraVectorize import AstraVectorizeComponent
import pytest
from integration.utils import MockEmbeddings, check_env_vars
from langchain_core.documents import Document

# from langflow.components.memories.AstraDBMessageReader import AstraDBMessageReaderComponent
# from langflow.components.memories.AstraDBMessageWriter import AstraDBMessageWriterComponent
from langflow.components.vectorstores.AstraDB import AstraVectorStoreComponent
from langflow.schema.data import Data

COLLECTION = "test_basic"
SEARCH_COLLECTION = "test_search"
# MEMORY_COLLECTION = "test_memory"
VECTORIZE_COLLECTION = "test_vectorize"
VECTORIZE_COLLECTION_OPENAI = "test_vectorize_openai"
VECTORIZE_COLLECTION_OPENAI_WITH_AUTH = "test_vectorize_openai_auth"


@pytest.fixture()
def astra_fixture(request):
    """
    Sets up the astra collection and cleans up after
    """
    try:
        from langchain_astradb import AstraDBVectorStore
    except ImportError:
        raise ImportError(
            "Could not import langchain Astra DB integration package. Please install it with `pip install langchain-astradb`."
        )

    store = AstraDBVectorStore(
        collection_name=request.param,
        embedding=MockEmbeddings(),
        api_endpoint=os.getenv("ASTRA_DB_API_ENDPOINT"),
        token=os.getenv("ASTRA_DB_APPLICATION_TOKEN"),
    )

    yield

    store.delete_collection()


@pytest.mark.skipif(
    not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT"),
    reason="missing astra env vars",
)
@pytest.mark.parametrize("astra_fixture", [COLLECTION], indirect=True)
def test_astra_setup(astra_fixture):
    application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
    embedding = MockEmbeddings()

    component = AstraVectorStoreComponent()
    component.build(
        token=application_token,
        api_endpoint=api_endpoint,
        collection_name=COLLECTION,
        embedding=embedding,
    )
    component.build_vector_store()


@pytest.mark.skipif(
    not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT"),
    reason="missing astra env vars",
)
@pytest.mark.parametrize("astra_fixture", [SEARCH_COLLECTION], indirect=True)
def test_astra_embeds_and_search(astra_fixture):
    application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
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


@pytest.mark.skipif(
    not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT"),
    reason="missing astra env vars",
)
def test_astra_vectorize():
    store = None
    try:
        options = {"provider": "nvidia", "modelName": "NV-Embed-QA", "parameters": {}, "authentication": {}}
        store = AstraDBVectorStore(
            collection_name=VECTORIZE_COLLECTION,
            api_endpoint=os.getenv("ASTRA_DB_API_ENDPOINT"),
            token=os.getenv("ASTRA_DB_APPLICATION_TOKEN"),
            collection_vector_service_options=CollectionVectorServiceOptions.from_dict(options),
        )

        application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
        api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")

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


@pytest.mark.skipif(
    not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT", "OPENAI_API_KEY"),
    reason="missing env vars",
)
def test_astra_vectorize_with_provider_api_key():
    """tests vectorize using an openai api key"""
    store = None
    try:
        application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
        api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
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
        )
        component.build_vector_store()
        records = component.search_documents()
        assert len(records) == 2
    finally:
        if store is not None:
            store.delete_collection()


@pytest.mark.skipif(
    not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT", "OPENAI_API_KEY"),
    reason="missing env vars",
)
def test_astra_vectorize_passes_authentication():
    """tests vectorize using the authentication parameter"""
    store = None
    try:
        application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
        api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
        options = {
            "provider": "openai",
            "modelName": "text-embedding-3-small",
            "parameters": {},
            "authentication": {"providerKey": "providerKey"},
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
            provider="OpenAI", model_name="text-embedding-3-small", authentication={"providerKey": "providerKey"}
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


# @pytest.mark.skipif(
#     not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT"),
#     reason="missing astra env vars",
# )
# def test_astra_memory():
#     application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
#     api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")

#     writer = AstraDBMessageWriterComponent()
#     reader = AstraDBMessageReaderComponent()

#     input_value = Data.from_document(
#         Document(
#             page_content="memory1",
#             metadata={"session_id": 1, "sender": "human", "sender_name": "Bob"},
#         )
#     )
#     writer.build(
#         input_value=input_value,
#         session_id=1,
#         token=application_token,
#         api_endpoint=api_endpoint,
#         collection_name=MEMORY_COLLECTION,
#     )

#     # verify reading w/ same session id pulls the same record
#     records = reader.build(
#         session_id=1,
#         token=application_token,
#         api_endpoint=api_endpoint,
#         collection_name=MEMORY_COLLECTION,
#     )
#     assert len(records) == 1
#     assert isinstance(records[0], Data)
#     content = records[0].get_text()
#     assert content == "memory1"

#     # verify reading w/ different session id does not pull the same record
#     records = reader.build(
#         session_id=2,
#         token=application_token,
#         api_endpoint=api_endpoint,
#         collection_name=MEMORY_COLLECTION,
#     )
#     assert len(records) == 0

#     # Cleanup store - doing here rather than fixture (see https://github.com/langchain-ai/langchain-datastax/pull/36)
#     try:
#         from langchain_astradb import AstraDBVectorStore
#     except ImportError:
#         raise ImportError(
#             "Could not import langchain Astra DB integration package. Please install it with `pip install langchain-astradb`."
#         )
#     store = AstraDBVectorStore(
#         collection_name=MEMORY_COLLECTION,
#         embedding=MockEmbeddings(),
#         api_endpoint=api_endpoint,
#         token=application_token,
#     )
#     store.delete_collection()
