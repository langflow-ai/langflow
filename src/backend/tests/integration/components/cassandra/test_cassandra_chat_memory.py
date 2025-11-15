"""Integration tests for Cassandra Chat Memory component.

These tests verify drop-in compatibility between Apache Cassandra and ScyllaDB
for the chat memory functionality.

Prerequisites:
    - Docker containers running (ScyllaDB on port 9042, Cassandra on port 9043)
    - cassio package installed (pip install cassio)

Note: cassio will automatically create keyspaces and tables on first use.
"""

import pytest

from tests.api_keys import (
    get_cassandra_host,
    get_cassandra_keyspace,
    get_cassandra_port,
    get_scylladb_host,
    get_scylladb_keyspace,
    get_scylladb_port,
)


@pytest.fixture(params=["cassandra", "scylladb"])
def db_config(request):
    """Parametrized fixture providing database configuration.

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
def cassandra_session(db_config):
    """Fixture providing a Cassandra/ScyllaDB session for direct database access."""
    try:
        from cassandra.cluster import Cluster
    except ImportError:
        pytest.skip("cassandra-driver not installed")

    cluster = Cluster([db_config["host"]], port=db_config["port"])
    session = cluster.connect(db_config["keyspace"])

    yield session

    try:
        session.execute(f"TRUNCATE {db_config['keyspace']}.chat_memory_test")
    except Exception:  # noqa: S110
        pass

    cluster.shutdown()


def test_cassandra_chat_memory_connection(db_config):
    """Test that CassandraChatMessageHistory can connect to the database.

    Verifies:
        - Component can import successfully
        - Connection can be established
        - Session can be created
    """
    try:
        import cassio
        from langchain_community.chat_message_histories import CassandraChatMessageHistory
    except ImportError:
        pytest.skip("cassio or langchain-community not installed")

    cassio.init(
        contact_points=[db_config["host"]],
        keyspace=db_config["keyspace"],
    )

    chat_memory = CassandraChatMessageHistory(
        session_id="test_session_1",
        table_name="chat_memory_test",
    )

    messages = chat_memory.messages
    assert isinstance(messages, list)

    chat_memory.clear()
    cassio.config.resolve_session().shutdown()
    cassio.config.resolve_cluster().shutdown()

    print(f"✓ {db_config['db_name']}: Chat memory connection test passed")


def test_cassandra_chat_memory_add_messages(db_config):
    """Test adding and retrieving messages from chat memory.

    Verifies:
        - Messages can be added
        - Messages can be retrieved
        - Message order is preserved
    """
    try:
        import cassio
        from langchain_community.chat_message_histories import CassandraChatMessageHistory
        from langchain_core.messages import AIMessage, HumanMessage
    except ImportError:
        pytest.skip("cassio or langchain-community not installed")

    cassio.init(
        contact_points=[db_config["host"]],
        keyspace=db_config["keyspace"],
    )

    chat_memory = CassandraChatMessageHistory(
        session_id="test_session_2",
        table_name="chat_memory_test",
    )

    try:
        chat_memory.clear()

        chat_memory.add_user_message("Hello, how are you?")
        chat_memory.add_ai_message("I'm doing well, thank you!")
        chat_memory.add_user_message("What can you help me with?")

        messages = chat_memory.messages

        assert len(messages) == 3
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "Hello, how are you?"
        assert isinstance(messages[1], AIMessage)
        assert messages[1].content == "I'm doing well, thank you!"

        print(f"✓ {db_config['db_name']}: Chat memory add messages test passed")
        print(f"  Stored {len(messages)} messages successfully")

    finally:
        chat_memory.clear()
        cassio.config.resolve_session().shutdown()
        cassio.config.resolve_cluster().shutdown()


def test_cassandra_chat_memory_persistence(db_config):
    """Test that messages persist across chat memory instances.

    Verifies:
        - Messages are stored in the database
        - New instances can retrieve existing messages
        - Data persists beyond Python object lifecycle
    """
    try:
        import cassio
        from langchain_community.chat_message_histories import CassandraChatMessageHistory
    except ImportError:
        pytest.skip("cassio or langchain-community not installed")

    session_id = "test_session_persistence"

    cassio.init(
        contact_points=[db_config["host"]],
        keyspace=db_config["keyspace"],
    )

    try:
        chat_memory_1 = CassandraChatMessageHistory(
            session_id=session_id,
            table_name="chat_memory_test",
        )
        chat_memory_1.clear()
        chat_memory_1.add_user_message("Test persistence message")

        cassio.config.resolve_session().shutdown()
        cassio.config.resolve_cluster().shutdown()

        cassio.init(
            contact_points=[db_config["host"]],
            keyspace=db_config["keyspace"],
        )

        chat_memory_2 = CassandraChatMessageHistory(
            session_id=session_id,
            table_name="chat_memory_test",
        )

        messages = chat_memory_2.messages

        assert len(messages) == 1
        assert messages[0].content == "Test persistence message"

        print(f"✓ {db_config['db_name']}: Chat memory persistence test passed")

        chat_memory_2.clear()

    finally:
        cassio.config.resolve_session().shutdown()
        cassio.config.resolve_cluster().shutdown()


def test_cassandra_chat_memory_clear(db_config):
    """Test clearing chat memory.

    Verifies:
        - Messages can be cleared
        - Only session-specific messages are cleared
    """
    try:
        import cassio
        from langchain_community.chat_message_histories import CassandraChatMessageHistory
    except ImportError:
        pytest.skip("cassio or langchain-community not installed")

    cassio.init(
        contact_points=[db_config["host"]],
        keyspace=db_config["keyspace"],
    )

    try:
        session_1 = CassandraChatMessageHistory(
            session_id="clear_test_session_1",
            table_name="chat_memory_test",
        )
        session_2 = CassandraChatMessageHistory(
            session_id="clear_test_session_2",
            table_name="chat_memory_test",
        )

        session_1.clear()
        session_2.clear()

        session_1.add_user_message("Message in session 1")
        session_2.add_user_message("Message in session 2")

        session_1.clear()

        assert len(session_1.messages) == 0
        assert len(session_2.messages) == 1

        print(f"✓ {db_config['db_name']}: Chat memory clear test passed")

        session_2.clear()

    finally:
        cassio.config.resolve_session().shutdown()
        cassio.config.resolve_cluster().shutdown()


def test_cassandra_chat_memory_multiple_sessions(db_config):
    """Test that multiple sessions can coexist independently.

    Verifies:
        - Sessions are isolated
        - Different sessions can have different messages
        - No cross-contamination between sessions
    """
    try:
        import cassio
        from langchain_community.chat_message_histories import CassandraChatMessageHistory
    except ImportError:
        pytest.skip("cassio or langchain-community not installed")

    cassio.init(
        contact_points=[db_config["host"]],
        keyspace=db_config["keyspace"],
    )

    try:
        sessions = []
        for i in range(3):
            session = CassandraChatMessageHistory(
                session_id=f"multi_test_session_{i}",
                table_name="chat_memory_test",
            )
            session.clear()
            session.add_user_message(f"Message from session {i}")
            sessions.append(session)

        for i, session in enumerate(sessions):
            messages = session.messages
            assert len(messages) == 1
            assert messages[0].content == f"Message from session {i}"

        print(f"✓ {db_config['db_name']}: Multiple sessions test passed")
        print(f"  Successfully isolated {len(sessions)} sessions")

        for session in sessions:
            session.clear()

    finally:
        cassio.config.resolve_session().shutdown()
        cassio.config.resolve_cluster().shutdown()
