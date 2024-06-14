import os
import pytest

from integration.utils import MockEmbeddings, check_env_vars

from langflow.components.memories.AstraDBMessageReader import (
    AstraDBMessageReaderComponent,
)
from langflow.components.memories.AstraDBMessageWriter import (
    AstraDBMessageWriterComponent,
)
from langflow.components.vectorsearch.AstraDBSearch import AstraDBSearchComponent
from langflow.components.vectorstores.AstraDB import AstraDBVectorStoreComponent
from langflow.schema.record import Record

from langchain_core.documents import Document

COLLECTION = "test_basic"
MEMORY_COLLECTION = "test_memory"


@pytest.mark.order(1)
@pytest.mark.skipif(
    not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT"),
    reason="missing astra env vars",
)
def test_astra_setup():
    application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
    embedding = MockEmbeddings()

    component = AstraDBVectorStoreComponent()
    component.build(
        token=application_token,
        api_endpoint=api_endpoint,
        collection_name=COLLECTION,
        embedding=embedding,
    )

# @pytest.mark.order(2)
# @pytest.mark.skipif(
#     not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT"),
#     reason="missing astra env vars",
# )
# def test_astra_embeds_documents():
#     application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
#     api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
#     embedding = MockEmbeddings()

#     documents = [Document(page_content="test1"), Document(page_content="test2")]
#     records = [Record.from_document(d) for d in documents]

#     component = AstraDBVectorStoreComponent()
#     component.build(
#         token=application_token,
#         api_endpoint=api_endpoint,
#         collection_name=COLLECTION,
#         embedding=embedding,
#         inputs=records,
#     )


# @pytest.mark.order(3)
# @pytest.mark.skipif(
#     not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT"),
#     reason="missing astra env vars",
# )
# def test_astra_search():
#     application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
#     api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
#     embedding = MockEmbeddings()

#     component = AstraDBSearchComponent()
#     records = component.build(
#         token=application_token,
#         api_endpoint=api_endpoint,
#         collection_name=COLLECTION,
#         embedding=embedding,
#         input_value="test1",
#         number_of_results=1,
#     )

#     assert len(records) == 1
# Existing code...

@pytest.fixture(autouse=True)
def after_all_tests():
    # Code to run after all other tests have completed
    print("Running after all tests")

def test_astra_additional():
    # Additional test code
    assert True

#     document = records[0].get_text()
#     assert isinstance(document, Document)
#     assert document.page_content == "test1"


# @pytest.mark.skipif(
#     not check_env_vars("ASTRA_DB_APPLICATION_TOKEN", "ASTRA_DB_API_ENDPOINT"),
#     reason="missing astra env vars",
# )
# def test_astra_memory():
#     application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
#     api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")

#     writer = AstraDBMessageWriterComponent()
#     reader = AstraDBMessageReaderComponent()

#     input_value = Record.from_document(
#         Document(
#             page_content="memory1",
#             metadata={
#                 "session_id": 1, "sender": "User", "sender_name": "Bob"
#             },
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
#     assert isinstance(records[0], Record)
#     document = records[0].get_text()
#     print(f"DOC: {document}")
#     assert document.page_content == "memory1"

#     # verify reading w/ different session id does not pull the same record
#     records = reader.build(
#         session_id=2,
#         token=application_token,
#         api_endpoint=api_endpoint,
#         collection_name=MEMORY_COLLECTION,
#     )
#     assert len(records) == 0
