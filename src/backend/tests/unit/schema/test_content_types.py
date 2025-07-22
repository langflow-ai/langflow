from lfx.schema.content_types import (
    BaseContent,
    CodeContent,
    ErrorContent,
    JSONContent,
    MediaContent,
    TextContent,
    ToolContent,
)


class TestBaseContent:
    def test_base_content_serialization(self):
        """Test BaseContent serialization methods."""
        content = BaseContent(type="test")

        # Test to_dict method
        dict_content = content.to_dict()
        assert isinstance(dict_content, dict)
        assert dict_content["type"] == "test"

        # Test from_dict method
        reconstructed = BaseContent.from_dict(dict_content)
        assert isinstance(reconstructed, BaseContent)
        assert reconstructed.type == "test"

    def test_base_content_with_header(self):
        """Test BaseContent with header information."""
        header = {"title": "Test Title", "icon": "test-icon"}
        content = BaseContent(type="test", header=header)
        assert content.header == header
        assert content.header["title"] == "Test Title"
        assert content.header["icon"] == "test-icon"

    def test_base_content_with_duration(self):
        """Test BaseContent with duration field."""
        content = BaseContent(type="test", duration=1000)
        assert content.duration == 1000


class TestErrorContent:
    def test_error_content_creation(self):
        """Test ErrorContent creation and fields."""
        error = ErrorContent(
            component="test_component",
            field="test_field",
            reason="test failed",
            solution="fix it",
            traceback="traceback info",
        )
        assert error.type == "error"
        assert error.component == "test_component"
        assert error.field == "test_field"
        assert error.reason == "test failed"
        assert error.solution == "fix it"
        assert error.traceback == "traceback info"

    def test_error_content_optional_fields(self):
        """Test ErrorContent with minimal fields."""
        error = ErrorContent()
        assert error.type == "error"
        assert error.component is None
        assert error.field is None


class TestTextContent:
    def test_text_content_creation(self):
        """Test TextContent creation and fields."""
        text = TextContent(text="Hello, world!")
        assert text.type == "text"
        assert text.text == "Hello, world!"

    def test_text_content_with_duration(self):
        """Test TextContent with duration."""
        text = TextContent(text="Hello", duration=500)
        assert text.duration == 500


class TestMediaContent:
    def test_media_content_creation(self):
        """Test MediaContent creation and fields."""
        urls = ["http://example.com/1.jpg", "http://example.com/2.jpg"]
        media = MediaContent(urls=urls, caption="Test images")
        assert media.type == "media"
        assert media.urls == urls
        assert media.caption == "Test images"

    def test_media_content_without_caption(self):
        """Test MediaContent without caption."""
        media = MediaContent(urls=["http://example.com/1.jpg"])
        assert media.caption is None


class TestJSONContent:
    def test_json_content_creation(self):
        """Test JSONContent creation and fields."""
        data = {"key": "value", "nested": {"inner": "data"}}
        json_content = JSONContent(data=data)
        assert json_content.type == "json"
        assert json_content.data == data

    def test_json_content_complex_data(self):
        """Test JSONContent with complex data structures."""
        data = {"string": "text", "number": 42, "list": [1, 2, 3], "nested": {"a": 1, "b": 2}}
        json_content = JSONContent(data=data)
        assert json_content.data == data


class TestCodeContent:
    def test_code_content_creation(self):
        """Test CodeContent creation and fields."""
        code = CodeContent(code="print('hello')", language="python", title="Test Script")
        assert code.type == "code"
        assert code.code == "print('hello')"
        assert code.language == "python"
        assert code.title == "Test Script"

    def test_code_content_without_title(self):
        """Test CodeContent without title."""
        code = CodeContent(code="console.log('hello')", language="javascript")
        assert code.title is None


class TestToolContent:
    def test_tool_content_creation(self):
        """Test ToolContent creation and fields."""
        tool = ToolContent(name="test_tool", tool_input={"param": "value"}, output="result", duration=100)
        assert tool.type == "tool_use"
        assert tool.name == "test_tool"
        assert tool.tool_input == {"param": "value"}
        assert tool.output == "result"
        assert tool.duration == 100

    def test_tool_content_with_error(self):
        """Test ToolContent with error field."""
        tool = ToolContent(name="test_tool", tool_input={}, error="Something went wrong")
        assert tool.error == "Something went wrong"
        assert tool.output is None

    def test_tool_content_minimal(self):
        """Test ToolContent with minimal fields."""
        tool = ToolContent()
        assert tool.type == "tool_use"
        assert tool.tool_input == {}
        assert tool.name is None
        assert tool.output is None
        assert tool.error is None


def test_content_type_discrimination():
    """Test that different content types are properly discriminated."""
    contents = [
        TextContent(text="Hello"),
        CodeContent(code="print('hi')", language="python"),
        ErrorContent(reason="test error"),
        JSONContent(data={"test": "data"}),
        MediaContent(urls=["http://example.com/image.jpg"]),
        ToolContent(name="test_tool"),
    ]

    assert all(
        content.type == expected
        for content, expected in zip(contents, ["text", "code", "error", "json", "media", "tool_use"], strict=False)
    )
