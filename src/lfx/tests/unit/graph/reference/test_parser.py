# src/lfx/tests/unit/graph/reference/test_parser.py

from lfx.graph.reference.parser import parse_references
from lfx.graph.reference.schema import Reference


class TestParseReferences:
    def test_parse_simple_reference(self):
        text = "@NodeSlug.output"
        refs = parse_references(text)
        assert len(refs) == 1
        assert refs[0].node_slug == "NodeSlug"
        assert refs[0].output_name == "output"
        assert refs[0].dot_path is None

    def test_parse_reference_with_dot_path(self):
        text = "@Node.output.nested.path"
        refs = parse_references(text)
        assert len(refs) == 1
        assert refs[0].node_slug == "Node"
        assert refs[0].output_name == "output"
        assert refs[0].dot_path == "nested.path"

    def test_parse_reference_with_array_index(self):
        text = "@Node.output[0]"
        refs = parse_references(text)
        assert len(refs) == 1
        assert refs[0].node_slug == "Node"
        assert refs[0].output_name == "output"
        assert refs[0].dot_path == "[0]"

    def test_parse_reference_with_mixed_path(self):
        text = "@Node.output.items[0].name"
        refs = parse_references(text)
        assert len(refs) == 1
        assert refs[0].node_slug == "Node"
        assert refs[0].output_name == "output"
        assert refs[0].dot_path == "items[0].name"

    def test_parse_multiple_references(self):
        text = "Hello @User.name, your balance is @Account.balance"
        refs = parse_references(text)
        assert len(refs) == 2
        assert refs[0].node_slug == "User"
        assert refs[0].output_name == "name"
        assert refs[1].node_slug == "Account"
        assert refs[1].output_name == "balance"

    def test_parse_no_references(self):
        text = "Hello world, no references here"
        refs = parse_references(text)
        assert len(refs) == 0

    def test_parse_empty_string(self):
        refs = parse_references("")
        assert len(refs) == 0

    def test_parse_incomplete_reference_no_output(self):
        text = "@Node"
        refs = parse_references(text)
        assert len(refs) == 0

    def test_parse_email_not_matched(self):
        """Email addresses should not be parsed as references."""
        text = "Email: user@domain.com"
        refs = parse_references(text)
        # The negative lookbehind prevents matching @ preceded by word chars
        assert len(refs) == 0

    def test_parse_reference_with_underscores(self):
        text = "@My_Node.output_name"
        refs = parse_references(text)
        assert len(refs) == 1
        assert refs[0].node_slug == "My_Node"
        assert refs[0].output_name == "output_name"

    def test_parse_reference_with_numbers(self):
        text = "@Node1.output2"
        refs = parse_references(text)
        assert len(refs) == 1
        assert refs[0].node_slug == "Node1"
        assert refs[0].output_name == "output2"

    def test_parse_reference_in_sentence(self):
        text = "The value of @ChatInput.message is important"
        refs = parse_references(text)
        assert len(refs) == 1
        assert refs[0].node_slug == "ChatInput"
        assert refs[0].output_name == "message"

    def test_parse_consecutive_references_no_space(self):
        """Consecutive references without space only match the first one."""
        text = "@A.x@B.y"
        refs = parse_references(text)
        # Second @ is preceded by 'x' (word char), so not matched
        assert len(refs) == 1
        assert refs[0].node_slug == "A"

    def test_parse_consecutive_references_with_space(self):
        """Consecutive references with space match both."""
        text = "@A.x @B.y"
        refs = parse_references(text)
        assert len(refs) == 2
        assert refs[0].node_slug == "A"
        assert refs[1].node_slug == "B"


class TestReferenceFullPath:
    def test_full_path_simple(self):
        ref = Reference(node_slug="Node", output_name="output")
        assert ref.full_path == "@Node.output"

    def test_full_path_with_dot_path(self):
        ref = Reference(node_slug="Node", output_name="output", dot_path="nested.path")
        assert ref.full_path == "@Node.output.nested.path"

    def test_full_path_with_array_index(self):
        ref = Reference(node_slug="Node", output_name="output", dot_path="items[0]")
        assert ref.full_path == "@Node.output.items[0]"
