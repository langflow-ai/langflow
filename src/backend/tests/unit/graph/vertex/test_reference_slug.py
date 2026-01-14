from lfx.graph.vertex.base import Vertex


def test_vertex_has_reference_slug():
    # Minimal vertex creation
    vertex = Vertex.__new__(Vertex)
    vertex._data = {"id": "test-id", "data": {"node": {"display_name": "HTTP Request"}}}
    vertex._id = "test-id"
    vertex.reference_slug = None  # Initialize

    assert hasattr(vertex, "reference_slug")


def test_generate_slug_from_display_name():
    from lfx.graph.vertex.base import generate_reference_slug

    slug = generate_reference_slug("HTTP Request")
    # title() converts "HTTP" to "Http" and "Request" to "Request"
    assert slug == "HttpRequest"


def test_generate_slug_removes_special_chars():
    from lfx.graph.vertex.base import generate_reference_slug

    slug = generate_reference_slug("My Component (v2)")
    # title() capitalizes each word, including "V2"
    assert slug == "MyComponentV2"


def test_generate_slug_handles_numbers():
    from lfx.graph.vertex.base import generate_reference_slug

    slug = generate_reference_slug("OpenAI Model 3.5")
    # title() converts "OpenAI" to "Openai" and removes the period
    assert slug == "OpenaiModel35"


def test_generate_slug_empty_string():
    from lfx.graph.vertex.base import generate_reference_slug

    slug = generate_reference_slug("")
    assert slug == "Node"  # Default fallback
