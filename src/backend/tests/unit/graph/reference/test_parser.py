# src/backend/tests/unit/graph/reference/test_parser.py
from lfx.graph.reference.parser import parse_references


def test_parse_single_reference():
    text = "Hello @HTTPRequest_1.response world"
    refs = parse_references(text)
    assert len(refs) == 1
    assert refs[0].node_slug == "HTTPRequest_1"
    assert refs[0].output_name == "response"
    assert refs[0].dot_path is None


def test_parse_reference_with_dot_path():
    text = "Data: @HTTPRequest_1.response.body.data"
    refs = parse_references(text)
    assert len(refs) == 1
    assert refs[0].node_slug == "HTTPRequest_1"
    assert refs[0].output_name == "response"
    assert refs[0].dot_path == "body.data"


def test_parse_multiple_references():
    text = "First: @Node1.output1 Second: @Node2.output2"
    refs = parse_references(text)
    assert len(refs) == 2
    assert refs[0].node_slug == "Node1"
    assert refs[1].node_slug == "Node2"


def test_parse_no_references():
    text = "Hello world, no references here"
    refs = parse_references(text)
    assert len(refs) == 0


def test_parse_reference_with_array_index():
    text = "Item: @HTTPRequest_1.response.items[0].name"
    refs = parse_references(text)
    assert len(refs) == 1
    assert refs[0].dot_path == "items[0].name"


def test_parse_reference_at_start():
    text = "@Node.output is the value"
    refs = parse_references(text)
    assert len(refs) == 1


def test_parse_reference_at_end():
    text = "The value is @Node.output"
    refs = parse_references(text)
    assert len(refs) == 1


def test_parse_adjacent_references():
    text = "@Node1.out1@Node2.out2"
    refs = parse_references(text)
    assert len(refs) == 2
