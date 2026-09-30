import pytest
from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import CodeContent, ErrorContent, JSONContent, MediaContent, TextContent, ToolContent


class TestContentBlock:
    def test_initialize_with_valid_title_and_contents(self):
        """Test initializing ContentBlock with valid title and contents."""
        valid_title = "Sample Title"
        valid_contents = [TextContent(type="text", text="Sample text")]
        content_block = ContentBlock(title=valid_title, contents=valid_contents)

        assert content_block.title == valid_title
        assert len(content_block.contents) == 1
        assert isinstance(content_block.contents[0], TextContent)
        assert content_block.contents[0].text == "Sample text"
        assert content_block.allow_markdown is True
        assert content_block.media_url is None

    def test_initialize_with_empty_contents(self):
        """Test initializing ContentBlock with empty contents list."""
        valid_title = "Sample Title"
        empty_contents = []
        content_block = ContentBlock(title=valid_title, contents=empty_contents)

        assert content_block.title == valid_title
        assert content_block.contents == empty_contents
        assert content_block.allow_markdown is True
        assert content_block.media_url is None

    def test_validate_different_content_types(self):
        """Test ContentBlock with different content types."""
        contents = [
            TextContent(type="text", text="Sample text"),
            CodeContent(type="code", code="print('hello')", language="python"),
            ErrorContent(type="error", error="Sample error"),
            JSONContent(type="json", data={"key": "value"}),
            MediaContent(type="media", urls=["http://example.com/image.jpg"]),
            ToolContent(type="tool_use", output="Sample thought", name="test_tool", tool_input={"input": "test"}),
        ]

        content_block = ContentBlock(title="Test", contents=contents)
        expected_len = 6
        assert len(content_block.contents) == expected_len
        assert isinstance(content_block.contents[0], TextContent)
        assert isinstance(content_block.contents[1], CodeContent)
        assert isinstance(content_block.contents[2], ErrorContent)
        assert isinstance(content_block.contents[3], JSONContent)
        assert isinstance(content_block.contents[4], MediaContent)
        assert isinstance(content_block.contents[5], ToolContent)

    def test_invalid_contents_type(self):
        """Test that providing contents as dict raises TypeError."""
        with pytest.raises(TypeError, match="Contents must be a list of ContentTypes"):
            ContentBlock(title="Test", contents={"invalid": "content"})

    def test_single_content_conversion(self):
        """Test that single content item is converted to list."""
        single_content = TextContent(type="text", text="Single item")
        content_block = ContentBlock(title="Test", contents=single_content)
        assert isinstance(content_block.contents, list)
        assert len(content_block.contents) == 1

    def test_serialize_contents(self):
        """Test serialization of contents to dict format."""
        contents = [
            TextContent(type="text", text="Sample text"),
            CodeContent(type="code", code="print('hello')", language="python"),
        ]
        block = ContentBlock(title="Test Block", contents=contents)
        serialized = block.serialize_contents(block.contents)

        assert isinstance(serialized, list)
        expected_len = 2
        assert len(serialized) == expected_len
        assert serialized[0]["type"] == "text"
        assert serialized[1]["type"] == "code"
        assert serialized[1]["language"] == "python"

    def test_media_url_handling(self):
        """Test handling of media_url field."""
        media_urls = ["http://example.com/1.jpg", "http://example.com/2.jpg"]
        block = ContentBlock(title="Test", contents=[TextContent(type="text", text="Sample")], media_url=media_urls)
        assert block.media_url == media_urls

    def test_allow_markdown_override(self):
        """Test overriding allow_markdown default value."""
        block = ContentBlock(title="Test", contents=[], allow_markdown=False)
        assert block.allow_markdown is False
