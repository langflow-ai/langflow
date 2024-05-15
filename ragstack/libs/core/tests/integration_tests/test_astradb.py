import orjson
import pytest
from typing import Callable

from langchain_core.documents import Document
from langflow.load import run_flow_from_json
from langflow.schema import Record

from astrapy.core.db import AstraDB, AstraDBCollection

from tests.integration_tests.conftest import get_env_var

BASIC_COLLECTION = "test"
EMBEDDING_FLOW_COLLECTION = "test_embedding_flow"


def test_build_no_inputs(astradb_component: Callable):
    astradb_component(collection=BASIC_COLLECTION)


def test_build_with_inputs(astradb_component: Callable):
    record = Record.from_document(Document(page_content="test"))
    record2 = Record.from_document(Document(page_content="test2"))
    inputs = [record, record2]
    astradb_component(collection=BASIC_COLLECTION, inputs=inputs)


@pytest.mark.order(1)
def test_astra_embedding_flow(embedding_flow: str):
    """
    Embeds the contents of a URL into AstraDB.
    """
    flow = orjson.loads(embedding_flow)
    TWEAKS = {
        "AstraDB-s9tdG": {
            "token": get_env_var("ASTRA_DB_APPLICATION_TOKEN"),
            "api_endpoint": get_env_var("ASTRA_DB_API_ENDPOINT"),
            "collection_name": EMBEDDING_FLOW_COLLECTION,
        },
        "SplitText-v9ZHX": {},
        "URL-vWSxt": {},
        "OpenAIEmbeddings-YQwtD": {"openai_api_key": get_env_var("OPENAI_API_KEY")},
    }

    result = run_flow_from_json(flow=flow, input_value="", tweaks=TWEAKS)
    # embedding flow, so no particular output
    assert result is not None

    # however, we can check astradb to see if data was inserted
    astra = AstraDB(
        token=get_env_var("ASTRA_DB_APPLICATION_TOKEN"),
        api_endpoint=get_env_var("ASTRA_DB_API_ENDPOINT"),
    )
    collection: AstraDBCollection = astra.collection(EMBEDDING_FLOW_COLLECTION)
    docs = collection.count_documents()
    assert docs["status"]["count"] > 0


@pytest.mark.order(2)
def test_astra_search(vector_store_search_flow: str):
    """
    Searches AstraDB for the most similar document to a given query.
    """
    flow = orjson.loads(vector_store_search_flow)

    TWEAKS = {
        "OpenAIEmbeddings-sSuTz": {
            "openai_api_key": get_env_var("OPENAI_API_KEY"),
        },
        "AstraDBSearch-avH6c": {
            "token": get_env_var("ASTRA_DB_APPLICATION_TOKEN"),
            "api_endpoint": get_env_var("ASTRA_DB_API_ENDPOINT"),
            "collection_name": EMBEDDING_FLOW_COLLECTION,
            "input_value": "Find 3 steps to upload examples",
        },
    }

    result = run_flow_from_json(
        flow=flow,
        input_value="",  # Would like to pass the search input value here, but
        output_component="AstraDBSearch-avH6c",
        tweaks=TWEAKS,
    )
    assert result is not None
    data = result[0].outputs[0]
    assert data is not None
    assert data.component_display_name == "Astra DB Search"
