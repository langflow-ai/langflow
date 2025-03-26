import pytest
from langflow.components.tools import ArXivComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestArXivComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ArXivComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"search_query": "quantum computing", "search_type": "all", "max_results": 5, "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "arxiv", "file_name": "ArXiv"},
            {"version": "1.1.0", "module": "arxiv", "file_name": "arxiv"},
        ]

    def test_build_query_url(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        expected_url = "http://export.arxiv.org/api/query?search_query=all:quantum+computing&max_results=5"
        assert component.build_query_url() == expected_url

    def test_parse_atom_response(self, component_class):
        component = component_class()
        sample_response = """<feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <id>http://arxiv.org/abs/1234.5678</id>
                <title>Sample Paper Title</title>
                <summary>This is a summary of the paper.</summary>
                <published>2023-01-01T00:00:00Z</published>
                <updated>2023-01-01T00:00:00Z</updated>
                <author><name>John Doe</name></author>
                <link rel="alternate" href="http://arxiv.org/abs/1234.5678"/>
                <link rel="related" href="http://arxiv.org/pdf/1234.5678.pdf"/>
                <arxiv:comment>Sample comment</arxiv:comment>
                <arxiv:journal_ref>Sample Journal Reference</arxiv:journal_ref>
                <arxiv:primary_category term="cs.LG"/>
                <category term="cs.LG"/>
            </entry>
        </feed>"""
        papers = component.parse_atom_response(sample_response)
        assert len(papers) == 1
        assert papers[0]["title"] == "Sample Paper Title"
        assert papers[0]["id"] == "http://arxiv.org/abs/1234.5678"

    async def test_search_papers(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.search_papers()
        assert result is not None
        assert isinstance(result, list)

    def test_invalid_url_scheme(self, component_class):
        component = component_class(search_query="quantum computing", search_type="all", max_results=5)
        component.search_query = "invalid_scheme"
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            component.search_papers()

    def test_invalid_host(self, component_class):
        component = component_class(search_query="quantum computing", search_type="all", max_results=5)
        component.search_query = "invalid_host"
        with pytest.raises(ValueError, match="Invalid host"):
            component.search_papers()
