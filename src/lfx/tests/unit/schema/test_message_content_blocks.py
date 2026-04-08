"""Tests for Message text/content_blocks behavioral contract.

These tests define how text and content_blocks interact:
- content_blocks is the source of truth when content_blocks are provided
- text is derived from top-level TextContent blocks when content_blocks exist
- Text-only messages (Message(text="hello")) keep content_blocks empty and use the data dict
- Reading msg.text concatenates all top-level TextContent blocks
- Setting msg.text replaces TextContent blocks, preserving non-text blocks
- Round-trips (model_dump -> model_validate) must not double text
"""

from langchain_core.messages import AIMessage, HumanMessage
from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import (
    ErrorContent,
    ImageContent,
    TextContent,
    ToolContent,
)
from lfx.schema.data import Data
from lfx.schema.message import ErrorMessage, Message
from lfx.schema.properties import Source
from lfx.utils.constants import (
    MESSAGE_SENDER_AI,
    MESSAGE_SENDER_NAME_AI,
    MESSAGE_SENDER_NAME_USER,
    MESSAGE_SENDER_USER,
)


class TestMessageConstruction:
    """Tests for constructing Message objects with the new content_blocks-first model."""

    def test_text_only(self):
        """Message(text="hello") keeps content_blocks empty, text from data dict."""
        msg = Message(text="hello")
        assert msg.content_blocks == []
        assert msg.text == "hello"

    def test_content_blocks_only(self):
        """Message with only content_blocks should derive text from TextContent blocks."""
        msg = Message(content_blocks=[TextContent(text="hello")])
        assert msg.text == "hello"

    def test_both_text_and_content_blocks_prefers_content_blocks(self):
        """When both text and content_blocks are provided, content_blocks wins."""
        msg = Message(
            text="ignored",
            content_blocks=[TextContent(text="from blocks")],
        )
        assert msg.text == "from blocks"
        # The content_blocks should contain only what was passed, not a duplicate from text
        text_blocks = [b for b in msg.content_blocks if isinstance(b, TextContent)]
        assert len(text_blocks) == 1
        assert text_blocks[0].text == "from blocks"

    def test_empty_message(self):
        """Message() with no arguments should have empty content_blocks and empty text."""
        msg = Message()
        assert msg.content_blocks == []
        assert msg.text == ""

    def test_empty_string_text(self):
        """Message(text='') should not create a TextContent block."""
        msg = Message(text="")
        # Empty string should not produce a TextContent block
        text_blocks = [b for b in msg.content_blocks if isinstance(b, TextContent)]
        assert len(text_blocks) == 0
        assert msg.text == ""

    def test_none_text(self):
        """Message(text=None) should result in empty text and no content blocks."""
        msg = Message(text=None)
        assert msg.text == ""
        assert msg.content_blocks == []

    def test_mixed_content_blocks(self):
        """Text should be concatenated from only top-level TextContent blocks."""
        msg = Message(
            content_blocks=[
                TextContent(text="Hello "),
                ToolContent(name="search", tool_input={"q": "test"}),
                TextContent(text="World"),
            ]
        )
        assert msg.text == "Hello World"

    def test_construction_with_grouped_content_block(self):
        """Old-style ContentBlock(title=..., contents=[...]) should still work in content_blocks."""
        grouped_block = ContentBlock(
            title="Results",
            contents=[TextContent(text="inside group")],
        )
        msg = Message(content_blocks=[grouped_block])
        # The grouped ContentBlock should be preserved
        assert len(msg.content_blocks) == 1
        assert isinstance(msg.content_blocks[0], ContentBlock)
        assert msg.content_blocks[0].title == "Results"

    def test_construction_with_all_other_fields(self):
        """Text + sender + session_id + other fields should all work together."""
        msg = Message(
            text="hello",
            sender=MESSAGE_SENDER_USER,
            sender_name=MESSAGE_SENDER_NAME_USER,
            session_id="session-123",
            flow_id="flow-456",
        )
        assert msg.text == "hello"
        assert msg.sender == MESSAGE_SENDER_USER
        assert msg.sender_name == MESSAGE_SENDER_NAME_USER
        assert msg.session_id == "session-123"
        assert msg.flow_id == "flow-456"
        # Text-only messages keep content_blocks empty
        assert msg.content_blocks == []


class TestTextGetter:
    """Tests for reading the text property from content_blocks."""

    def test_single_text_block(self):
        """Single TextContent block should return its text."""
        msg = Message(content_blocks=[TextContent(text="hello")])
        assert msg.text == "hello"

    def test_multiple_text_blocks_concatenated(self):
        """Multiple TextContent blocks should be concatenated."""
        msg = Message(
            content_blocks=[
                TextContent(text="Hello"),
                TextContent(text=" "),
                TextContent(text="World"),
            ]
        )
        assert msg.text == "Hello World"

    def test_no_text_blocks(self):
        """When only non-text content exists, text should be empty string."""
        msg = Message(
            content_blocks=[
                ToolContent(name="search", tool_input={"q": "test"}),
                ImageContent(urls=["http://example.com/img.png"]),
            ]
        )
        assert msg.text == ""

    def test_text_interspersed_with_other_types(self):
        """TextContent blocks interspersed with other types should all be concatenated."""
        msg = Message(
            content_blocks=[
                TextContent(text="Part 1"),
                ToolContent(name="calc", tool_input={"expr": "1+1"}),
                TextContent(text=" Part 2"),
                ImageContent(urls=["http://example.com/img.png"]),
                TextContent(text=" Part 3"),
            ]
        )
        assert msg.text == "Part 1 Part 2 Part 3"

    def test_empty_content_blocks(self):
        """Empty content_blocks list should result in empty text."""
        msg = Message(content_blocks=[])
        assert msg.text == ""

    def test_text_is_a_string(self):
        """msg.text should always be a str instance."""
        msg = Message(content_blocks=[TextContent(text="hello")])
        assert isinstance(msg.text, str)

    def test_text_in_string_operations(self):
        """msg.text should work in f-strings, .upper(), etc."""
        msg = Message(content_blocks=[TextContent(text="hello")])
        assert f"Say: {msg.text}" == "Say: hello"
        assert msg.text.upper() == "HELLO"
        assert msg.text.startswith("he")
        assert len(msg.text) == 5

    def test_text_does_not_extract_from_grouped_blocks(self):
        """TextContent inside a ContentBlock group should NOT contribute to .text."""
        grouped = ContentBlock(
            title="Details",
            contents=[TextContent(text="hidden inside group")],
        )
        msg = Message(
            content_blocks=[
                TextContent(text="visible"),
                grouped,
            ]
        )
        # Only the top-level TextContent should be in .text
        assert msg.text == "visible"
        assert "hidden inside group" not in msg.text


class TestTextSetter:
    """Tests for setting the text property and its effect on content_blocks."""

    def test_set_text_on_empty_stores_in_data(self):
        """Setting text on a text-only message stores in data dict, not content_blocks."""
        msg = Message()
        msg.text = "hello"
        assert msg.text == "hello"
        # Text-only: content_blocks stays empty, text is in data dict
        assert msg.content_blocks == []

    def test_set_text_replaces_existing(self):
        """Setting text should replace text value."""
        msg = Message(text="old text")
        msg.text = "new text"
        assert msg.text == "new text"

    def test_set_text_preserves_non_text_blocks(self):
        """Setting text should preserve non-TextContent blocks."""
        tool_block = ToolContent(name="search", tool_input={"q": "test"})
        msg = Message(
            content_blocks=[
                TextContent(text="old"),
                tool_block,
            ]
        )
        msg.text = "new"
        assert msg.text == "new"
        # The tool block should still be there
        tool_blocks = [b for b in msg.content_blocks if isinstance(b, ToolContent)]
        assert len(tool_blocks) == 1
        assert tool_blocks[0].name == "search"

    def test_set_empty_string_removes_text(self):
        """Setting text to empty string should remove TextContent blocks."""
        msg = Message(text="something")
        msg.text = ""
        assert msg.text == ""
        text_blocks = [b for b in msg.content_blocks if isinstance(b, TextContent)]
        assert len(text_blocks) == 0

    def test_set_text_on_empty_message(self):
        """Setting text on a completely empty message should work."""
        msg = Message()
        assert msg.text == ""
        msg.text = "now has text"
        assert msg.text == "now has text"

    def test_multiple_set_get_cycles(self):
        """Multiple set/get cycles should not accumulate garbage."""
        msg = Message()
        for i in range(5):
            msg.text = f"iteration {i}"
            assert msg.text == f"iteration {i}"

    def test_text_block_goes_first(self):
        """After setting text, the TextContent should be first in the list."""
        tool_block = ToolContent(name="tool", tool_input={})
        msg = Message(content_blocks=[tool_block])
        msg.text = "first"
        assert isinstance(msg.content_blocks[0], TextContent)
        assert msg.content_blocks[0].text == "first"


class TestSerialization:
    """Tests for model_dump / model_validate round-trip behavior."""

    def test_model_dump_includes_text(self):
        """model_dump() should include a 'text' key (computed_field appears in serialization)."""
        msg = Message(text="hello")
        dumped = msg.model_dump()
        assert "text" in dumped
        assert dumped["text"] == "hello"

    def test_model_dump_includes_content_blocks(self):
        """model_dump() should include content_blocks."""
        msg = Message(content_blocks=[TextContent(text="hello")])
        dumped = msg.model_dump()
        assert "content_blocks" in dumped
        assert len(dumped["content_blocks"]) >= 1

    def test_roundtrip_text_only(self):
        """model_dump -> model_validate should preserve text correctly."""
        msg = Message(text="hello")
        dumped = msg.model_dump()
        restored = Message.model_validate(dumped)
        assert restored.text == "hello"
        # Text-only messages keep content_blocks empty
        assert restored.content_blocks == []

    def test_roundtrip_mixed_content(self):
        """Round-trip with mixed content types should preserve everything."""
        msg = Message(
            content_blocks=[
                TextContent(text="hello"),
                ToolContent(name="search", tool_input={"q": "test"}),
            ]
        )
        dumped = msg.model_dump()
        restored = Message.model_validate(dumped)
        assert restored.text == "hello"
        assert len(restored.content_blocks) == 2
        assert isinstance(restored.content_blocks[0], TextContent)
        assert isinstance(restored.content_blocks[1], ToolContent)

    def test_roundtrip_json(self):
        """model_dump_json -> model_validate_json round-trip should work."""
        msg = Message(
            text="hello",
            sender=MESSAGE_SENDER_USER,
            sender_name=MESSAGE_SENDER_NAME_USER,
        )
        json_str = msg.model_dump_json()
        restored = Message.model_validate_json(json_str)
        assert restored.text == "hello"

    def test_deserialize_old_format_text_only(self):
        """Deserializing old format with text and empty content_blocks should work."""
        old_data = {
            "text": "hello",
            "content_blocks": [],
        }
        msg = Message(**old_data)
        assert msg.text == "hello"
        # Text stays in data dict, content_blocks stays empty
        assert msg.content_blocks == []

    def test_deserialize_new_format(self):
        """Deserializing new format with content_blocks containing TextContent should work."""
        new_data = {
            "content_blocks": [{"type": "text", "text": "hello"}],
        }
        msg = Message(**new_data)
        assert msg.text == "hello"

    def test_deserialize_both_present_content_blocks_wins(self):
        """When both text and content_blocks are present in data, content_blocks wins."""
        data = {
            "text": "from text field",
            "content_blocks": [{"type": "text", "text": "from blocks"}],
        }
        msg = Message(**data)
        assert msg.text == "from blocks"


class TestBackwardsCompatibility:
    """Tests for backwards compatibility with existing Message usage patterns."""

    def test_from_lc_message_human(self):
        """Message.from_lc_message with HumanMessage should work."""
        lc_msg = HumanMessage(content="hello from user")
        msg = Message.from_lc_message(lc_msg)
        assert msg.text == "hello from user"
        assert msg.sender == MESSAGE_SENDER_USER
        assert msg.sender_name == MESSAGE_SENDER_NAME_USER

    def test_from_lc_message_ai(self):
        """Message.from_lc_message with AIMessage should work."""
        lc_msg = AIMessage(content="hello from ai")
        msg = Message.from_lc_message(lc_msg)
        assert msg.text == "hello from ai"
        assert msg.sender == MESSAGE_SENDER_AI
        assert msg.sender_name == MESSAGE_SENDER_NAME_AI

    def test_to_lc_message_user(self):
        """Converting a user Message to lc_message should produce HumanMessage."""
        msg = Message(text="hello", sender=MESSAGE_SENDER_USER)
        lc_msg = msg.to_lc_message()
        assert isinstance(lc_msg, HumanMessage)
        assert lc_msg.content == "hello"

    def test_to_lc_message_ai(self):
        """Converting an AI Message to lc_message should produce AIMessage."""
        msg = Message(text="hello", sender=MESSAGE_SENDER_AI)
        lc_msg = msg.to_lc_message()
        assert isinstance(lc_msg, AIMessage)
        assert lc_msg.content == "hello"

    def test_error_message_still_works(self):
        """ErrorMessage should still create content_blocks with ErrorContent."""
        source = Source(
            id="test-id",
            display_name="TestComponent",
            source="TestComponent",
        )
        exc = ValueError("something went wrong")
        err_msg = ErrorMessage(
            exception=exc,
            session_id="session-1",
            source=source,
            flow_id="flow-1",
        )
        assert err_msg.error is True
        assert err_msg.category == "error"
        # .text should contain the plain error reason
        assert "something went wrong" in err_msg.text
        # Should have a TextContent (plain reason) and a ContentBlock (error details)
        assert len(err_msg.content_blocks) >= 2
        assert isinstance(err_msg.content_blocks[0], TextContent)
        # Find the grouped error block
        error_blocks = [b for b in err_msg.content_blocks if isinstance(b, ContentBlock)]
        assert len(error_blocks) == 1
        assert error_blocks[0].title == "Error"
        error_contents = [c for c in error_blocks[0].contents if isinstance(c, ErrorContent)]
        assert len(error_contents) == 1

    def test_message_from_data(self):
        """Message.from_data should preserve text through content_blocks."""
        data = Data(text="data text")
        msg = Message.from_data(data)
        assert msg.text == "data text"
