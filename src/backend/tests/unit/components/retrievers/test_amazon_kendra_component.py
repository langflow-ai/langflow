import pytest
from langflow.components.retrievers import AmazonKendraRetrieverComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAmazonKendraRetrieverComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AmazonKendraRetrieverComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "index_id": "test-index",
            "top_k": 5,
            "region_name": "us-west-2",
            "credentials_profile_name": "default",
            "attribute_filter": None,
            "user_context": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "retrievers", "file_name": "AmazonKendraRetriever"},
        ]

    async def test_build_retriever(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        retriever = component.build(**default_kwargs)

        # Assert
        assert retriever is not None
        assert isinstance(retriever, AmazonKendraRetriever)

    async def test_build_retriever_with_invalid_index(self, component_class):
        # Arrange
        component = component_class(index_id="invalid-index")

        # Act & Assert
        with pytest.raises(ValueError, match="Could not connect to AmazonKendra API."):
            component.build(index_id="invalid-index")
