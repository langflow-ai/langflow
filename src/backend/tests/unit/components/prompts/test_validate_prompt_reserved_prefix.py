"""Tests for the reserved `_*` namespace in prompt variable names.

Keys prefixed with an underscore are node-template metadata (`_type`,
`_frontend_node_flow_id`, ...), not component fields. The frontend filters that namespace
out of every render path, so a variable such as `{_x}` used to be accepted by
`validate_prompt` and written into the template while never producing an input field or a
handle -- it could not be given a value and resolved to an empty string at run time.

Regression test for LE-2144. The case list is mirrored by the frontend unit test for
`isReservedVariableName`; keep the two in sync.
"""

import pytest
from lfx.base.prompts.api_utils import validate_prompt

REJECTED = ["_x", "_", "__y", "_type", "_frontend_node_flow_id"]
ACCEPTED = ["var", "a_b", "var_1", "private_", "x"]


class TestValidatePromptReservedPrefix:
    """Variable names starting with an underscore are rejected in both syntaxes."""

    @pytest.mark.parametrize("name", REJECTED)
    def test_leading_underscore_rejected_fstring(self, name):
        with pytest.raises(ValueError, match="cannot start with `_`"):
            validate_prompt(f"Hello {{{name}}}, how are you?")

    @pytest.mark.parametrize("name", REJECTED)
    def test_leading_underscore_rejected_mustache(self, name):
        with pytest.raises(ValueError, match="cannot start with `_`"):
            validate_prompt(f"Hello {{{{{name}}}}}, how are you?", is_mustache=True)

    @pytest.mark.parametrize("name", ACCEPTED)
    def test_regular_names_still_accepted_fstring(self, name):
        assert validate_prompt(f"Hello {{{name}}}, how are you?") == [name]

    @pytest.mark.parametrize("name", ACCEPTED)
    def test_regular_names_still_accepted_mustache(self, name):
        assert validate_prompt(f"Hello {{{{{name}}}}}, how are you?", is_mustache=True) == [name]

    def test_error_names_only_the_offending_variables(self):
        """A mixed template reports the rejected names, not every variable in it."""
        with pytest.raises(ValueError, match=r"Invalid input variables: `_a`, `_b`\.") as exc_info:
            validate_prompt("{name} {_a} {city} {_b}")
        assert "name" not in str(exc_info.value).split(".")[0]

    def test_names_are_backticked_so_markdown_keeps_the_underscores(self):
        """The frontend renders this message with react-markdown.

        Bare underscores pair up into emphasis markers there, so `_x` would reach the
        user as `x` and the rule itself would read "cannot start with ''".
        """
        with pytest.raises(ValueError, match="Invalid input variables") as exc_info:
            validate_prompt("{_a} {_b}")
        message = str(exc_info.value)
        assert "`_a`" in message
        assert "`_b`" in message
        assert "start with `_`" in message

    def test_metadata_key_no_longer_reaches_the_template_writer(self):
        """`{_type}` used to pass validation and then fail with an opaque HTTP 500.

        `add_new_variables_to_template` read `template["_type"]["value"]` on the plain
        string that holds the node type, raising `string indices must be integers`.
        It is now rejected up front with an actionable message.
        """
        with pytest.raises(ValueError, match="cannot start with `_`"):
            validate_prompt("Hello {_type}")
