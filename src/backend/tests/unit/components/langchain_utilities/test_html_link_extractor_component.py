import pytest

from langflow.components.langchain_utilities import HtmlLinkExtractorComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestHtmlLinkExtractorComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return HtmlLinkExtractorComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "kind": "hyperlink",
            "drop_fragments": True,
            "data_input": "Here is a link: <a href='http://example.com'>Example</a>",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "html_link_extractor", "file_name": "HtmlLinkExtractor"},
        ]

    async def test_build_document_transformer(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        transformer = component.build_document_transformer()

        # Assert
        assert transformer is not None
        assert isinstance(transformer, LinkExtractorTransformer)

    def test_get_data_input(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        data_input = component.get_data_input()

        # Assert
        assert data_input == default_kwargs["data_input"]
