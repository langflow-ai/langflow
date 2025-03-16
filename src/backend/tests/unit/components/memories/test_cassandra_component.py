import pytest
from langflow.components.memories import CassandraChatMemory
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCassandraChatMemory(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CassandraChatMemory

    @pytest.fixture
    def default_kwargs(self):
        return {
            "database_ref": "test_database_id",
            "username": "test_user",
            "token": "test_token",
            "keyspace": "test_keyspace",
            "table_name": "test_table",
            "session_id": "test_session_id",
            "cluster_kwargs": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "memory", "file_name": "CassandraChatMemory"},
        ]

    def test_build_message_history_astra(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        message_history = component.build_message_history()
        assert message_history is not None
        assert message_history.session_id == default_kwargs["session_id"]
        assert message_history.table_name == default_kwargs["table_name"]
        assert message_history.keyspace == default_kwargs["keyspace"]

    def test_build_message_history_contact_points(self, component_class, default_kwargs):
        default_kwargs["database_ref"] = "127.0.0.1"
        component = component_class(**default_kwargs)
        message_history = component.build_message_history()
        assert message_history is not None
        assert message_history.session_id == default_kwargs["session_id"]
        assert message_history.table_name == default_kwargs["table_name"]
        assert message_history.keyspace == default_kwargs["keyspace"]

    def test_import_error_handling(self, component_class, default_kwargs):
        with pytest.raises(ImportError, match="Could not import cassio integration package"):
            component = component_class(**default_kwargs)
            component.build_message_history()
