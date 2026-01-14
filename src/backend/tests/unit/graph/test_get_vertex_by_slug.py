# src/backend/tests/unit/graph/test_get_vertex_by_slug.py
from unittest.mock import MagicMock


def test_get_vertex_by_slug_found():
    from lfx.graph.graph.base import Graph

    # Create mock graph
    graph = MagicMock(spec=Graph)

    mock_vertex = MagicMock()
    mock_vertex.reference_slug = "HTTPRequest_1"

    graph.vertices = [mock_vertex]
    graph._slug_to_vertex = {"HTTPRequest_1": mock_vertex}

    # Call the real method
    Graph.get_vertex_by_slug(graph, "HTTPRequest_1")


def test_get_vertex_by_slug_not_found():
    from lfx.graph.graph.base import Graph

    graph = MagicMock(spec=Graph)
    graph._slug_to_vertex = {}

    result = Graph.get_vertex_by_slug(graph, "NonExistent")
    assert result is None


def test_build_slug_index_basic():
    """Test that _build_slug_index correctly builds the slug index."""
    from lfx.graph.graph.base import Graph

    graph = MagicMock(spec=Graph)

    mock_vertex1 = MagicMock()
    mock_vertex1.display_name = "HTTP Request"
    mock_vertex1.reference_slug = None

    mock_vertex2 = MagicMock()
    mock_vertex2.display_name = "Chat Input"
    mock_vertex2.reference_slug = None

    graph.vertices = [mock_vertex1, mock_vertex2]

    # Call the real method
    Graph._build_slug_index(graph)

    # Verify slugs were assigned
    assert mock_vertex1.reference_slug is not None
    assert mock_vertex2.reference_slug is not None
    # Check that the slug index was built
    assert hasattr(graph, "_slug_to_vertex")
    assert len(graph._slug_to_vertex) == 2


def test_build_slug_index_handles_duplicates():
    """Test that _build_slug_index handles duplicate display names."""
    from lfx.graph.graph.base import Graph

    graph = MagicMock(spec=Graph)

    # Two vertices with the same display name
    mock_vertex1 = MagicMock()
    mock_vertex1.display_name = "HTTP Request"
    mock_vertex1.reference_slug = None

    mock_vertex2 = MagicMock()
    mock_vertex2.display_name = "HTTP Request"
    mock_vertex2.reference_slug = None

    graph.vertices = [mock_vertex1, mock_vertex2]

    # Call the real method
    Graph._build_slug_index(graph)

    # Verify different slugs were assigned
    assert mock_vertex1.reference_slug != mock_vertex2.reference_slug
    # One should be the base slug, the other should have a suffix
    slugs = {mock_vertex1.reference_slug, mock_vertex2.reference_slug}
    assert "HttpRequest" in slugs
    assert "HttpRequest_1" in slugs


def test_get_vertex_by_slug_builds_index_if_missing():
    """Test that get_vertex_by_slug builds the index if it doesn't exist."""
    from lfx.graph.graph.base import Graph

    graph = MagicMock(spec=Graph)

    # Simulate no _slug_to_vertex attribute
    del graph._slug_to_vertex

    mock_vertex = MagicMock()
    mock_vertex.display_name = "HTTP Request"
    mock_vertex.reference_slug = None

    graph.vertices = [mock_vertex]

    # Define _build_slug_index to actually build the index
    def build_index(self):
        self._slug_to_vertex = {"HttpRequest": mock_vertex}
        mock_vertex.reference_slug = "HttpRequest"

    graph._build_slug_index = lambda: build_index(graph)

    # Call the real method
    result = Graph.get_vertex_by_slug(graph, "HttpRequest")
    assert result == mock_vertex
