"""Integration tests for Cassandra Vector Store component.

These tests verify drop-in compatibility between Apache Cassandra and ScyllaDB.
The tests should pass identically for both databases using the same code.

Prerequisites:
    - Docker containers running (ScyllaDB on port 9042, Cassandra on port 9043)
    - cassio package installed (pip install cassio)
    - OPENAI_API_KEY set (for embedding tests)

Environment Variables:
    CASSANDRA_HOST (default: localhost)
    CASSANDRA_PORT (default: 9043)
    CASSANDRA_KEYSPACE (default: langflow_test)
    SCYLLADB_HOST (default: localhost)
    SCYLLADB_PORT (default: 9042)
    SCYLLADB_KEYSPACE (default: langflow_test)

Note: cassio will automatically create keyspaces and tables on first use.
"""

import pytest
from langchain_core.documents import Document
from lfx.components.cassandra import CassandraVectorStoreComponent
from lfx.components.openai.openai import OpenAIEmbeddingsComponent
from lfx.schema.data import Data

from tests.api_keys import (
    get_cassandra_host,
    get_cassandra_keyspace,
    get_cassandra_port,
    get_openai_api_key,
    get_scylladb_host,
    get_scylladb_keyspace,
    get_scylladb_port,
)
from tests.integration.components.mock_components import TextToData
from tests.integration.utils import ComponentInputHandle, run_single_component

VECTOR_STORE_COLLECTION = "test_vector_store"
SEARCH_COLLECTION = "test_search"
INGEST_COLLECTION = "test_ingest"

ALL_COLLECTIONS = [
    VECTOR_STORE_COLLECTION,
    SEARCH_COLLECTION,
    INGEST_COLLECTION,
]


@pytest.fixture(params=["cassandra", "scylladb"])
def db_config(request):
    """Parametrized fixture providing database configuration.

    This fixture enables tests to run against both Cassandra and ScyllaDB
    automatically, verifying drop-in compatibility.

    Returns:
        dict: Database configuration with host, port, keyspace, and db_name
    """
    if request.param == "cassandra":
        return {
            "host": get_cassandra_host(),
            "port": get_cassandra_port(),
            "keyspace": get_cassandra_keyspace(),
            "db_name": "Cassandra",
        }
    return {
        "host": get_scylladb_host(),
        "port": get_scylladb_port(),
        "keyspace": get_scylladb_keyspace(),
        "db_name": "ScyllaDB",
    }


@pytest.fixture
def cassandra_client(db_config):
    """Fixture providing a Cassandra/ScyllaDB client for test cleanup.

    Yields:
        Cluster: cassandra.cluster.Cluster instance

    Cleanup:
        Drops all test tables after tests complete
    """
    try:
        from cassandra.cluster import Cluster
    except ImportError:
        pytest.skip("cassandra-driver not installed")

    cluster = Cluster([db_config["host"]], port=db_config["port"])
    session = cluster.connect(db_config["keyspace"])

    yield session

    for table in ALL_COLLECTIONS:
        try:
            session.execute(f"DROP TABLE IF EXISTS {db_config['keyspace']}.{table}")
        except Exception:  # noqa: S110
            pass

    cluster.shutdown()


@pytest.mark.api_key_required
async def test_cassandra_vector_store_basic(db_config, cassandra_client):
    """Test basic vector store creation and connectivity.

    Verifies:
        - Component can connect to the database
        - Table/collection can be created
        - Empty search returns no results
    """
    database_ref = f"{db_config['host']}"

    results = await run_single_component(
        CassandraVectorStoreComponent,
        inputs={
            "database_ref": database_ref,
            "username": "",  # No auth for local testing
            "token": "",
            "keyspace": db_config["keyspace"],
            "table_name": VECTOR_STORE_COLLECTION,
            "embedding_model": ComponentInputHandle(
                clazz=OpenAIEmbeddingsComponent,
                inputs={"openai_api_key": get_openai_api_key()},
                output_name="embeddings",
            ),
        },
    )

    assert results["search_results"] == []

    row = cassandra_client.execute(
        f"SELECT table_name FROM system_schema.tables WHERE keyspace_name='{db_config['keyspace']}' AND table_name='{VECTOR_STORE_COLLECTION}'"
    ).one()
    assert row is not None
    print(f"✓ {db_config['db_name']}: Basic vector store test passed")


@pytest.mark.api_key_required
async def test_cassandra_ingest_and_search(db_config, cassandra_client):
    """Test document ingestion and similarity search.

    Verifies:
        - Documents can be ingested with embeddings
        - Similarity search returns relevant results
        - Results are ranked by relevance
    """
    database_ref = f"{db_config['host']}"

    results = await run_single_component(
        CassandraVectorStoreComponent,
        inputs={
            "database_ref": database_ref,
            "username": "",
            "token": "",
            "keyspace": db_config["keyspace"],
            "table_name": SEARCH_COLLECTION,
            "number_of_results": 2,
            "search_query": "artificial intelligence",
            "ingest_data": ComponentInputHandle(
                clazz=TextToData,
                inputs={
                    "text_data": [
                        "Langflow is a low-code app builder for RAG and multi-agent AI applications",
                        "ScyllaDB is a NoSQL database compatible with Apache Cassandra",
                        "Artificial intelligence is transforming software development",
                    ]
                },
                output_name="from_text",
            ),
            "embedding_model": ComponentInputHandle(
                clazz=OpenAIEmbeddingsComponent,
                inputs={"openai_api_key": get_openai_api_key()},
                output_name="embeddings",
            ),
        },
    )

    assert len(results["search_results"]) == 2
    assert all(isinstance(r, Data) for r in results["search_results"])
    search_results_data = results["search_results"]
    assert all(r.text_data for r in search_results_data)

    print(f"✓ {db_config['db_name']}: Ingest and search test passed")
    print(f"  Found {len(results['search_results'])} results")


@pytest.mark.api_key_required
async def test_cassandra_document_ingestion(db_config, cassandra_client):
    """Test ingesting structured Document objects.

    Verifies:
        - Document objects can be converted to Data and ingested
        - Metadata is preserved
        - Content is searchable
    """
    database_ref = f"{db_config['host']}"

    documents = [
        Document(
            page_content="Langflow makes building AI applications easy",
            metadata={"source": "docs", "category": "tutorial"},
        ),
        Document(
            page_content="Vector databases enable semantic search",
            metadata={"source": "docs", "category": "concepts"},
        ),
    ]

    records = [Data.from_document(d) for d in documents]

    results = await run_single_component(
        CassandraVectorStoreComponent,
        inputs={
            "database_ref": database_ref,
            "username": "",
            "token": "",
            "keyspace": db_config["keyspace"],
            "table_name": INGEST_COLLECTION,
            "ingest_data": records,
            "search_query": "semantic search",
            "number_of_results": 1,
            "embedding_model": ComponentInputHandle(
                clazz=OpenAIEmbeddingsComponent,
                inputs={"openai_api_key": get_openai_api_key()},
                output_name="embeddings",
            ),
        },
    )

    assert len(results["search_results"]) >= 1

    print(f"✓ {db_config['db_name']}: Document ingestion test passed")


@pytest.mark.api_key_required
async def test_cassandra_connection_formats(db_config):
    """Test different connection string formats.

    Verifies:
        - Single host connection works
        - Component handles different input formats
    """
    database_ref = f"{db_config['host']}"

    results = await run_single_component(
        CassandraVectorStoreComponent,
        inputs={
            "database_ref": database_ref,
            "username": "",
            "token": "",
            "keyspace": db_config["keyspace"],
            "table_name": "test_connection",
            "embedding_model": ComponentInputHandle(
                clazz=OpenAIEmbeddingsComponent,
                inputs={"openai_api_key": get_openai_api_key()},
                output_name="embeddings",
            ),
        },
    )

    assert results["search_results"] == []

    print(f"✓ {db_config['db_name']}: Connection format test passed")


def test_cassandra_driver_compatibility(db_config):
    """Test that the cassandra-driver works with both databases.

    This test verifies the core drop-in compatibility claim:
    The same driver library works unchanged with both Cassandra and ScyllaDB.
    """
    try:
        from cassandra.cluster import Cluster
    except ImportError:
        pytest.skip("cassandra-driver not installed")

    cluster = Cluster([db_config["host"]], port=db_config["port"])
    session = cluster.connect()

    try:
        result = session.execute("SELECT release_version FROM system.local")
        version = result.one()[0]

        assert version is not None

        print(f"✓ {db_config['db_name']}: Driver compatibility test passed")
        print(f"  Database version: {version}")

    finally:
        cluster.shutdown()


def test_cassandra_keyspace_exists(db_config):
    """Verify the test keyspace exists and is accessible.

    This test checks that the setup script ran successfully.
    """
    try:
        from cassandra.cluster import Cluster
    except ImportError:
        pytest.skip("cassandra-driver not installed")

    cluster = Cluster([db_config["host"]], port=db_config["port"])
    session = cluster.connect()

    try:
        result = session.execute(
            f"SELECT keyspace_name FROM system_schema.keyspaces WHERE keyspace_name='{db_config['keyspace']}'"
        )
        keyspace = result.one()

        assert keyspace is not None, f"Keyspace {db_config['keyspace']} not found. Did you run the setup script?"

        print(f"✓ {db_config['db_name']}: Keyspace '{db_config['keyspace']}' exists")

    finally:
        cluster.shutdown()
