import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

from lfx.schema.data import Data


class StubCassandra:
    @staticmethod
    def from_documents(**_kwargs):
        msg = "from_documents should be monkeypatched by the test"
        raise AssertionError(msg)


def install_langchain_community_stub(monkeypatch) -> None:
    langchain_community_module = ModuleType("langchain_community")
    langchain_community_module.__path__ = []
    vectorstores_module = ModuleType("langchain_community.vectorstores")
    vectorstores_module.Cassandra = StubCassandra
    utilities_module = ModuleType("langchain_community.utilities")
    utilities_module.__path__ = []
    cassandra_utilities_module = ModuleType("langchain_community.utilities.cassandra")
    cassandra_utilities_module.SetupMode = SimpleNamespace(OFF="Off", SYNC="Sync", ASYNC="Async")
    langchain_community_module.vectorstores = vectorstores_module
    langchain_community_module.utilities = utilities_module
    utilities_module.cassandra = cassandra_utilities_module
    monkeypatch.setitem(sys.modules, "langchain_community", langchain_community_module)
    monkeypatch.setitem(sys.modules, "langchain_community.vectorstores", vectorstores_module)
    monkeypatch.setitem(sys.modules, "langchain_community.utilities", utilities_module)
    monkeypatch.setitem(sys.modules, "langchain_community.utilities.cassandra", cassandra_utilities_module)


def test_cassandra_from_documents_does_not_receive_batch_size(monkeypatch) -> None:
    module_name = "lfx.components.cassandra.cassandra"
    parent_module_name = "lfx.components.cassandra"
    parent_module = sys.modules.get(parent_module_name)
    had_parent_attr = parent_module is not None and hasattr(parent_module, "cassandra")
    previous_parent_attr = getattr(parent_module, "cassandra", None)
    previous_module = sys.modules.pop(module_name, None)
    install_langchain_community_stub(monkeypatch)
    cassandra_module = importlib.import_module(module_name)

    try:
        captured_kwargs = {}

        def fake_from_documents(**kwargs):
            captured_kwargs.update(kwargs)
            return MagicMock()

        monkeypatch.setitem(
            sys.modules,
            "cassio",
            SimpleNamespace(init=MagicMock()),
        )
        monkeypatch.setattr(cassandra_module.Cassandra, "from_documents", fake_from_documents)

        component = cassandra_module.CassandraVectorStoreComponent().set(
            database_ref="127.0.0.1",
            username="cassandra",
            token="cassandra",  # noqa: S106 - dummy value for a fully mocked unit test
            keyspace="test_keyspace",
            table_name="test_table",
            batch_size=16,
            setup_mode="Sync",
            embedding=MagicMock(),
            ingest_data=[Data(data={"text": "hello"})],
        )

        component.build_vector_store()

        assert "batch_size" not in captured_kwargs
        assert captured_kwargs["table_name"] == "test_table"
        assert captured_kwargs["keyspace"] == "test_keyspace"
    finally:
        sys.modules.pop(module_name, None)
        if previous_module is not None:
            sys.modules[module_name] = previous_module
        current_parent_module = sys.modules.get(parent_module_name)
        if current_parent_module is not None:
            if had_parent_attr:
                current_parent_module.cassandra = previous_parent_attr
            elif hasattr(current_parent_module, "cassandra"):
                delattr(current_parent_module, "cassandra")
