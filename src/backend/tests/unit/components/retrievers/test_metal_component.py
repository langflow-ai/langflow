import pytest
from langflow.components.retrievers import MetalRetrieverComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMetalRetrieverComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MetalRetrieverComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "client_id": "test_client_id",
            "index_id": "test_index_id",
            "params": {"param1": "value1"},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "retrievers", "file_name": "MetalRetriever"},
        ]

    def test_build_retriever(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        retriever = component.build(
            api_key=default_kwargs["api_key"],
            client_id=default_kwargs["client_id"],
            index_id=default_kwargs["index_id"],
            params=default_kwargs["params"],
        )

        # Assert
        assert retriever is not None
        assert isinstance(retriever, MetalRetriever)

    def test_build_retriever_invalid_credentials(self, component_class):
        # Arrange
        component = component_class(api_key="invalid_key", client_id="invalid_id", index_id="test_index_id")

        # Act & Assert
        with pytest.raises(ValueError, match="Could not connect to Metal API."):
            component.build(api_key="invalid_key", client_id="invalid_id", index_id="test_index_id")
