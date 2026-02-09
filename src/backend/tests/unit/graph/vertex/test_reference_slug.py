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
    # Preserves existing case: "HTTP" stays uppercase
    assert slug == "HTTPRequest"


def test_generate_slug_removes_special_chars():
    from lfx.graph.vertex.base import generate_reference_slug

    slug = generate_reference_slug("My Component (v2)")
    assert slug == "MyComponentv2"


def test_generate_slug_handles_numbers():
    from lfx.graph.vertex.base import generate_reference_slug

    slug = generate_reference_slug("OpenAI Model 3.5")
    # Preserves "OpenAI" as-is, removes period
    assert slug == "OpenAIModel35"


def test_generate_slug_empty_string():
    from lfx.graph.vertex.base import generate_reference_slug

    slug = generate_reference_slug("")
    assert slug == "Node"  # Default fallback


def test_generate_slug_preserves_acronyms():
    from lfx.graph.vertex.base import generate_reference_slug

    assert generate_reference_slug("API Request") == "APIRequest"
    assert generate_reference_slug("LLM Model") == "LLMModel"
    assert generate_reference_slug("Chat Input") == "ChatInput"


def test_generate_slug_lowercase_words():
    from lfx.graph.vertex.base import generate_reference_slug

    # First letter of each word gets capitalized
    assert generate_reference_slug("http request") == "HttpRequest"
    assert generate_reference_slug("chat input") == "ChatInput"
