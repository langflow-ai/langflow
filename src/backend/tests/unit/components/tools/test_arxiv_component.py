import pytest
from tests.base import ComponentTestBaseWithClient
from langflow.schema import Data
from unittest.mock import patch, MagicMock

class TestArXivComponent(ComponentTestBaseWithClient):
    @pytest.mark.skip(reason="New component - no previous versions exist")
    def test_all_versions_have_a_file_name_defined(self, file_names_mapping):
        """Skip version compatibility test for new component"""
        pass

    @pytest.mark.skip(reason="New component - no previous versions exist")
    def test_component_versions(self, default_kwargs, file_names_mapping):
        """Skip version compatibility test for new component"""
        pass

    @pytest.fixture
    def component_class(self):
        from src.backend.base.langflow.components.tools.arxiv import ArXivComponent
        return ArXivComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "search_query": "quantum computing",
            "search_type": "all",
            "max_results": 10,
            "_session_id": "test-session"
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_component_initialization(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)
        
        # Act
        frontend_node = component.to_frontend_node()
        
        # Assert
        node_data = frontend_node["data"]["node"]
        assert node_data["template"]["search_query"]["value"] == "quantum computing"
        assert node_data["template"]["search_type"]["value"] == "all"
        assert node_data["template"]["max_results"]["value"] == 10

    @patch("urllib.request.build_opener")
    def test_build_query_url(self, mock_opener, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)
        
        # Act
        url = component.build_query_url()
        
        # Assert
        assert "http://export.arxiv.org/api/query?" in url
        assert "search_query=all%3Aquantum%20computing" in url
        assert "max_results=10" in url

    def test_parse_atom_response(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)
        sample_xml = '''<feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <id>http://arxiv.org/abs/quant-ph/0000001</id>
                <title>Test Paper</title>
                <summary>Test summary</summary>
                <published>2023-01-01</published>
                <updated>2023-01-01</updated>
                <author><name>Test Author</name></author>
                <link rel="alternate" href="http://arxiv.org/abs/quant-ph/0000001"/>
                <link rel="related" href="http://arxiv.org/pdf/quant-ph/0000001"/>
                <category term="quant-ph" scheme="http://arxiv.org/schemas/atom"/>
            </entry>
        </feed>'''.replace('<', '<').replace('>', '>')
        
        # Act
        papers = component.parse_atom_response(sample_xml)
        
        # Assert
        assert len(papers) == 1
        paper = papers[0]
        assert paper["title"] == "Test Paper"
        assert paper["summary"] == "Test summary"
        assert paper["authors"] == ["Test Author"]
        assert paper["arxiv_url"] == "http://arxiv.org/abs/quant-ph/0000001"
        assert paper["pdf_url"] == "http://arxiv.org/pdf/quant-ph/0000001"

    @patch("urllib.request.build_opener")
    def test_invalid_url_handling(self, mock_opener, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)
        mock_response = MagicMock()
        mock_response.read.return_value = b'Error'
        mock_opener.return_value.open.side_effect = ValueError("Invalid URL")
        
        # Act
        results = component.search_papers()
        
        # Assert
        assert len(results) == 1
        assert "error" in results[0].data
        assert "Invalid URL" in results[0].data["error"]
