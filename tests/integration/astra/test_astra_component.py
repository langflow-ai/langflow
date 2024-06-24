import os

import pytest
from langchain_core.documents import Document
from langflow.components.memories.AstraDBMessageReader import AstraDBMessageReaderComponent
from langflow.components.memories.AstraDBMessageWriter import AstraDBMessageWriterComponent
from langflow.components.vectorstores.AstraDB import AstraVectorStoreComponent
from langflow.schema.data import Data

from integration.utils import MockEmbeddings, check_env_vars

COLLECTION = "test_basic"
SEARCH_COLLECTION = "test_search"
MEMORY_COLLECTION = "test_memory"


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
        inputs=records,
        add_to_vector_store=True,
    )
    component.build_vector_store()

    component.build(
        token=application_token,
        api_endpoint=api_endpoint,
        collection_name=SEARCH_COLLECTION,
        embedding=embedding,
        input_value="test1",
        number_of_results=1,
    )
    records = component.search_documents()

    assert len(records) == 1


@pytest.mark.skipif(
    not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT"),
    reason="missing astra env vars",
)
def test_astra_memory():
    application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")

    writer = AstraDBMessageWriterComponent()
    reader = AstraDBMessageReaderComponent()

    input_value = Data.from_document(
        Document(
            page_content="memory1",
            metadata={"session_id": 1, "sender": "human", "sender_name": "Bob"},
        )
    )
    writer.build(
        input_value=input_value,
        session_id=1,
        token=application_token,
        api_endpoint=api_endpoint,
        collection_name=MEMORY_COLLECTION,
    )

    # verify reading w/ same session id pulls the same record
    records = reader.build(
        session_id=1,
        token=application_token,
        api_endpoint=api_endpoint,
        collection_name=MEMORY_COLLECTION,
    )
    assert len(records) == 1
    assert isinstance(records[0], Data)
    content = records[0].get_text()
    assert content == "memory1"

    # verify reading w/ different session id does not pull the same record
    records = reader.build(
        session_id=2,
        token=application_token,
        api_endpoint=api_endpoint,
        collection_name=MEMORY_COLLECTION,
    )
    assert len(records) == 0

    # Cleanup store - doing here rather than fixture (see https://github.com/langchain-ai/langchain-datastax/pull/36)
    try:
        from langchain_astradb import AstraDBVectorStore
    except ImportError:
        raise ImportError(
            "Could not import langchain Astra DB integration package. Please install it with `pip install langchain-astradb`."
        )
    store = AstraDBVectorStore(
        collection_name=MEMORY_COLLECTION,
        embedding=MockEmbeddings(),
        api_endpoint=api_endpoint,
        token=application_token,
    )
    store.delete_collection()
