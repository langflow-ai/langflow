# src/backend/tests/unit/graph/reference/test_schema.py
from lfx.graph.reference.schema import Reference


def test_reference_creation():
    ref = Reference(node_slug="HTTPRequest_1", output_name="response")
    assert ref.node_slug == "HTTPRequest_1"
    assert ref.output_name == "response"
    assert ref.dot_path is None


def test_reference_with_dot_path():
    ref = Reference(node_slug="HTTPRequest_1", output_name="response", dot_path="body.data")
    assert ref.dot_path == "body.data"


def test_reference_full_path():
    ref = Reference(node_slug="HTTPRequest_1", output_name="response")
    assert ref.full_path == "@HTTPRequest_1.response"


def test_reference_full_path_with_dot_path():
    ref = Reference(node_slug="HTTPRequest_1", output_name="response", dot_path="body.data")
    assert ref.full_path == "@HTTPRequest_1.response.body.data"
