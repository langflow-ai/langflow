"""Unit tests for the ArXiv extension bundle (``lfx-arxiv``).

The component used to live at ``lfx.components.arxiv.arxiv`` and was tested
under ``src/backend/tests/unit/components/search/``.  It has since been
extracted into a standalone bundle; these tests now travel with the bundle
and import the public bundle entry point.
"""

from unittest.mock import patch

import pytest
from lfx_arxiv import ArXivComponent


@pytest.fixture
def default_kwargs():
    return {
        "search_query": "quantum computing",
        "search_type": "all",
        "max_results": 10,
        "_session_id": "test-session",
    }


def test_component_initialization(default_kwargs):
    component = ArXivComponent(**default_kwargs)

    frontend_node = component.to_frontend_node()

    node_data = frontend_node["data"]["node"]
    assert node_data["template"]["search_query"]["value"] == "quantum computing"
    assert node_data["template"]["search_type"]["value"] == "all"
    assert node_data["template"]["max_results"]["value"] == 10


def test_build_query_url(default_kwargs):
    component = ArXivComponent(**default_kwargs)

    url = component.build_query_url()

    assert "http://export.arxiv.org/api/query?" in url
    assert "search_query=quantum%20computing" in url
    assert "max_results=10" in url


def test_parse_atom_response(default_kwargs):
    component = ArXivComponent(**default_kwargs)
    sample_xml = """<feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:arxiv="http://arxiv.org/schemas/atom">
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
                <arxiv:comment>Test comment</arxiv:comment>
                <arxiv:journal_ref>Test Journal</arxiv:journal_ref>
                <arxiv:primary_category term="quant-ph"/>
            </entry>
        </feed>"""

    papers = component.parse_atom_response(sample_xml)

    assert len(papers) == 1
    paper = papers[0]
    assert paper["title"] == "Test Paper"
    assert paper["summary"] == "Test summary"
    assert paper["authors"] == ["Test Author"]
    assert paper["arxiv_url"] == "http://arxiv.org/abs/quant-ph/0000001"
    assert paper["pdf_url"] == "http://arxiv.org/pdf/quant-ph/0000001"
    assert paper["comment"] == "Test comment"
    assert paper["journal_ref"] == "Test Journal"
    assert paper["primary_category"] == "quant-ph"


@patch("urllib.request.build_opener")
def test_invalid_url_handling(mock_build_opener, default_kwargs):
    component = ArXivComponent(**default_kwargs)
    mock_build_opener.return_value.open.side_effect = ValueError("Invalid URL")

    results = component.search_papers()

    assert len(results) == 1
    assert hasattr(results[0], "error")
    assert "Invalid URL" in results[0].error
