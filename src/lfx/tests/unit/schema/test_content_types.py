import pytest
from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import (
    AudioContent,
    BaseContent,
    CitationContent,
    CodeContent,
    ErrorContent,
    FileContent,
    ImageContent,
    JSONContent,
    MediaContent,
    ReasoningContent,
    TextContent,
    ToolContent,
    UsageContent,
    VideoContent,
)
from pydantic import ValidationError


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
        duration = 1000
        content = BaseContent(type="test", duration=duration)
        assert content.duration == duration

    def test_base_content_without_duration(self):
        """Test BaseContent without duration field."""
        content = BaseContent(type="test")
        assert content.duration is None


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
        duration = 500
        text = TextContent(text="Hello", duration=duration)
        assert text.text == "Hello"
        assert text.duration == duration
        assert text.type == "text"

    def test_text_content_without_duration(self):
        """Test TextContent without duration."""
        text = TextContent(text="Hello")
        assert text.duration is None


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
        duration = 100
        tool = ToolContent(name="test_tool", tool_input={"param": "value"}, output="result", duration=duration)
        assert tool.type == "tool_use"
        assert tool.name == "test_tool"
        assert tool.tool_input == {"param": "value"}
        assert tool.output == "result"
        assert tool.duration == duration

    def test_tool_content(self):
        """Test ToolContent."""
        duration = 100
        tool = ToolContent(
            name="TestTool",
            tool_input={"param": "value"},
            output="result",
            duration=duration,
        )
        assert tool.name == "TestTool"
        assert tool.tool_input == {"param": "value"}
        assert tool.output == "result"
        assert tool.duration == duration

    def test_tool_content_with_error(self):
        """Test ToolContent with error field."""
        error_message = "Something went wrong"
        tool = ToolContent(name="test_tool", tool_input={}, error=error_message)
        assert tool.error == error_message
        assert tool.output is None

    def test_tool_content_minimal(self):
        """Test ToolContent with minimal fields."""
        tool = ToolContent()
        assert tool.type == "tool_use"
        assert tool.tool_input == {}
        assert tool.name is None
        assert tool.output is None
        assert tool.error is None

    def test_tool_content_serialization(self):
        """Test ToolContent serialization."""
        duration = 100
        tool = ToolContent(
            name="TestTool",
            tool_input={"param": "value"},
            output="result",
            duration=duration,
        )
        serialized = tool.model_dump()
        assert serialized["name"] == "TestTool"
        assert serialized["tool_input"] == {"param": "value"}
        assert serialized["output"] == "result"
        assert serialized["duration"] == duration

        deserialized = ToolContent.model_validate(serialized)
        assert deserialized == tool


# --- New content type tests ---


class TestImageContent:
    def test_construction(self):
        """Test ImageContent creation with all fields."""
        img = ImageContent(
            urls=["http://example.com/photo.png"],
            base64="iVBORw0KGgo=",
            mime_type="image/png",
            caption="A test image",
        )
        assert img.type == "image"
        assert img.urls == ["http://example.com/photo.png"]
        assert img.base64 == "iVBORw0KGgo="
        assert img.mime_type == "image/png"
        assert img.caption == "A test image"

    def test_empty_construction_raises(self):
        """ImageContent with no urls or base64 should raise."""
        with pytest.raises(ValidationError):
            ImageContent()

    def test_base64_without_mime_type_raises(self):
        """ImageContent with base64 but no mime_type should raise."""
        with pytest.raises(ValidationError):
            ImageContent(base64="abc123")

    def test_serialization_round_trip(self):
        """Test model_dump -> model_validate round trip."""
        img = ImageContent(urls=["http://example.com/a.jpg"], caption="test")
        dumped = img.model_dump()
        restored = ImageContent.model_validate(dumped)
        assert restored.type == "image"
        assert restored.urls == img.urls
        assert restored.caption == img.caption

    def test_json_round_trip(self):
        """Test model_dump_json -> model_validate_json round trip."""
        img = ImageContent(urls=["http://example.com/a.jpg"], mime_type="image/jpeg")
        json_str = img.model_dump_json()
        restored = ImageContent.model_validate_json(json_str)
        assert restored == img


class TestAudioContent:
    def test_construction(self):
        """Test AudioContent creation with all fields."""
        audio = AudioContent(
            urls=["http://example.com/track.mp3"],
            base64="AAAA",
            mime_type="audio/mpeg",
            duration=180,
            transcript="Hello world",
        )
        assert audio.type == "audio"
        assert audio.urls == ["http://example.com/track.mp3"]
        assert audio.base64 == "AAAA"
        assert audio.mime_type == "audio/mpeg"
        assert audio.duration == 180
        assert audio.transcript == "Hello world"

    def test_empty_construction_raises(self):
        """AudioContent with no urls or base64 should raise."""
        with pytest.raises(ValidationError):
            AudioContent()

    def test_base64_without_mime_type_raises(self):
        """AudioContent with base64 but no mime_type should raise."""
        with pytest.raises(ValidationError):
            AudioContent(base64="AAAA")

    def test_serialization_round_trip(self):
        """Test model_dump -> model_validate round trip."""
        audio = AudioContent(urls=["http://example.com/a.wav"], duration=60, transcript="Hi")
        dumped = audio.model_dump()
        restored = AudioContent.model_validate(dumped)
        assert restored.type == "audio"
        assert restored.urls == audio.urls
        assert restored.duration == audio.duration
        assert restored.transcript == audio.transcript

    def test_json_round_trip(self):
        """Test model_dump_json -> model_validate_json round trip."""
        audio = AudioContent(urls=["http://example.com/a.mp3"], mime_type="audio/mpeg")
        json_str = audio.model_dump_json()
        restored = AudioContent.model_validate_json(json_str)
        assert restored == audio


class TestVideoContent:
    def test_construction(self):
        """Test VideoContent creation with all fields."""
        video = VideoContent(
            urls=["http://example.com/video.mp4"],
            base64="BBBB",
            mime_type="video/mp4",
            duration=300,
        )
        assert video.type == "video"
        assert video.urls == ["http://example.com/video.mp4"]
        assert video.base64 == "BBBB"
        assert video.mime_type == "video/mp4"
        assert video.duration == 300

    def test_empty_construction_raises(self):
        """VideoContent with no urls or base64 should raise."""
        with pytest.raises(ValidationError):
            VideoContent()

    def test_base64_without_mime_type_raises(self):
        """VideoContent with base64 but no mime_type should raise."""
        with pytest.raises(ValidationError):
            VideoContent(base64="BBBB")

    def test_serialization_round_trip(self):
        """Test model_dump -> model_validate round trip."""
        video = VideoContent(urls=["http://example.com/v.mp4"], duration=120)
        dumped = video.model_dump()
        restored = VideoContent.model_validate(dumped)
        assert restored.type == "video"
        assert restored.urls == video.urls
        assert restored.duration == video.duration

    def test_json_round_trip(self):
        """Test model_dump_json -> model_validate_json round trip."""
        video = VideoContent(urls=["http://example.com/v.webm"], mime_type="video/webm")
        json_str = video.model_dump_json()
        restored = VideoContent.model_validate_json(json_str)
        assert restored == video


class TestFileContent:
    def test_construction(self):
        """Test FileContent creation with all fields."""
        fc = FileContent(
            urls=["http://example.com/report.pdf"],
            mime_type="application/pdf",
            filename="report.pdf",
        )
        assert fc.type == "file"
        assert fc.urls == ["http://example.com/report.pdf"]
        assert fc.mime_type == "application/pdf"
        assert fc.filename == "report.pdf"

    def test_empty_construction_raises(self):
        """FileContent with no urls should raise."""
        with pytest.raises(ValidationError):
            FileContent()

    def test_serialization_round_trip(self):
        """Test model_dump -> model_validate round trip."""
        fc = FileContent(urls=["http://example.com/doc.txt"], filename="doc.txt")
        dumped = fc.model_dump()
        restored = FileContent.model_validate(dumped)
        assert restored.type == "file"
        assert restored.urls == fc.urls
        assert restored.filename == fc.filename

    def test_json_round_trip(self):
        """Test model_dump_json -> model_validate_json round trip."""
        fc = FileContent(urls=["http://example.com/f.csv"], mime_type="text/csv", filename="f.csv")
        json_str = fc.model_dump_json()
        restored = FileContent.model_validate_json(json_str)
        assert restored == fc


class TestReasoningContent:
    def test_construction(self):
        """Test ReasoningContent creation with text."""
        r = ReasoningContent(text="Let me think about this step by step.")
        assert r.type == "reasoning"
        assert r.text == "Let me think about this step by step."

    def test_construction_defaults(self):
        """Test ReasoningContent with default values."""
        r = ReasoningContent()
        assert r.type == "reasoning"
        assert r.text == ""

    def test_serialization_round_trip(self):
        """Test model_dump -> model_validate round trip."""
        r = ReasoningContent(text="Step 1: consider the problem.")
        dumped = r.model_dump()
        restored = ReasoningContent.model_validate(dumped)
        assert restored.type == "reasoning"
        assert restored.text == r.text

    def test_json_round_trip(self):
        """Test model_dump_json -> model_validate_json round trip."""
        r = ReasoningContent(text="Analyzing inputs...")
        json_str = r.model_dump_json()
        restored = ReasoningContent.model_validate_json(json_str)
        assert restored == r


class TestUsageContent:
    def test_construction(self):
        """Test UsageContent creation with all fields."""
        u = UsageContent(input_tokens=100, output_tokens=250, model="gpt-4")
        assert u.type == "usage"
        assert u.input_tokens == 100
        assert u.output_tokens == 250
        assert u.model == "gpt-4"

    def test_construction_defaults(self):
        """Test UsageContent with default values."""
        u = UsageContent()
        assert u.type == "usage"
        assert u.input_tokens is None
        assert u.output_tokens is None
        assert u.model is None

    def test_serialization_round_trip(self):
        """Test model_dump -> model_validate round trip."""
        u = UsageContent(input_tokens=50, output_tokens=100, model="claude-3")
        dumped = u.model_dump()
        restored = UsageContent.model_validate(dumped)
        assert restored.type == "usage"
        assert restored.input_tokens == u.input_tokens
        assert restored.output_tokens == u.output_tokens
        assert restored.model == u.model

    def test_json_round_trip(self):
        """Test model_dump_json -> model_validate_json round trip."""
        u = UsageContent(input_tokens=10, output_tokens=20)
        json_str = u.model_dump_json()
        restored = UsageContent.model_validate_json(json_str)
        assert restored == u

    def test_negative_tokens_raises(self):
        """Negative token counts should raise."""
        with pytest.raises(ValidationError):
            UsageContent(input_tokens=-5)
        with pytest.raises(ValidationError):
            UsageContent(output_tokens=-1)


class TestCitationContent:
    def test_construction(self):
        """Test CitationContent creation with all fields."""
        c = CitationContent(
            url="http://example.com/article",
            title="Test Article",
            cited_text="This is the cited passage.",
            start_index=10,
            end_index=45,
        )
        assert c.type == "citation"
        assert c.url == "http://example.com/article"
        assert c.title == "Test Article"
        assert c.cited_text == "This is the cited passage."
        assert c.start_index == 10
        assert c.end_index == 45

    def test_construction_defaults(self):
        """Test CitationContent with default values."""
        c = CitationContent()
        assert c.type == "citation"
        assert c.url is None
        assert c.title is None
        assert c.cited_text is None
        assert c.start_index is None
        assert c.end_index is None

    def test_serialization_round_trip(self):
        """Test model_dump -> model_validate round trip."""
        c = CitationContent(url="http://example.com", title="Example", start_index=0, end_index=10)
        dumped = c.model_dump()
        restored = CitationContent.model_validate(dumped)
        assert restored.type == "citation"
        assert restored.url == c.url
        assert restored.title == c.title
        assert restored.start_index == c.start_index
        assert restored.end_index == c.end_index

    def test_json_round_trip(self):
        """Test model_dump_json -> model_validate_json round trip."""
        c = CitationContent(url="http://example.com", cited_text="Some text")
        json_str = c.model_dump_json()
        restored = CitationContent.model_validate_json(json_str)
        assert restored == c

    def test_inverted_indices_raises(self):
        """start_index > end_index should raise."""
        with pytest.raises(ValidationError):
            CitationContent(start_index=50, end_index=10)

    def test_negative_index_raises(self):
        """Negative indices should raise."""
        with pytest.raises(ValidationError):
            CitationContent(start_index=-1)
        with pytest.raises(ValidationError):
            CitationContent(end_index=-5)


# --- Existing type regression tests ---


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


def test_existing_types_serialization_round_trip():
    """Verify serialization round-trip for all existing content types (regression test)."""
    existing = [
        TextContent(text="Hello"),
        CodeContent(code="x = 1", language="python", title="snippet"),
        ErrorContent(component="comp", reason="fail"),
        JSONContent(data={"a": 1}),
        MediaContent(urls=["http://example.com/img.png"], caption="cap"),
        ToolContent(name="tool", tool_input={"k": "v"}, output="out"),
    ]
    for content in existing:
        dumped = content.model_dump()
        restored = type(content).model_validate(dumped)
        assert restored == content


def test_existing_types_json_round_trip():
    """Verify JSON round-trip for all existing content types (regression test)."""
    existing = [
        TextContent(text="Hello"),
        CodeContent(code="x = 1", language="python"),
        ErrorContent(reason="fail"),
        JSONContent(data={"a": [1, 2]}),
        MediaContent(urls=["http://example.com/img.png"]),
        ToolContent(name="tool", tool_input={"k": "v"}),
    ]
    for content in existing:
        json_str = content.model_dump_json()
        restored = type(content).model_validate_json(json_str)
        assert restored == content


# --- Discriminator dispatch tests via ContentBlock ---


def test_discriminator_dispatch_existing_types():
    """Test ContentBlock correctly dispatches existing content types from dicts."""
    block = ContentBlock(
        title="test",
        contents=[
            {"type": "text", "text": "hello"},
            {"type": "code", "code": "x=1", "language": "python"},
            {"type": "error", "reason": "oops"},
            {"type": "json", "data": {"k": "v"}},
            {"type": "media", "urls": ["http://example.com/a.jpg"]},
            {"type": "tool_use", "name": "my_tool", "input": {}},
        ],
    )
    assert isinstance(block.contents[0], TextContent)
    assert isinstance(block.contents[1], CodeContent)
    assert isinstance(block.contents[2], ErrorContent)
    assert isinstance(block.contents[3], JSONContent)
    assert isinstance(block.contents[4], MediaContent)
    assert isinstance(block.contents[5], ToolContent)


def test_discriminator_dispatch_image():
    """Test ContentBlock dispatches ImageContent from dict."""
    block = ContentBlock(
        title="test",
        contents=[{"type": "image", "urls": ["http://example.com/pic.png"], "caption": "a pic"}],
    )
    assert isinstance(block.contents[0], ImageContent)
    assert block.contents[0].urls == ["http://example.com/pic.png"]
    assert block.contents[0].caption == "a pic"


def test_discriminator_dispatch_audio():
    """Test ContentBlock dispatches AudioContent from dict."""
    block = ContentBlock(
        title="test",
        contents=[{"type": "audio", "urls": ["http://example.com/a.mp3"], "duration": 60, "transcript": "Hi"}],
    )
    assert isinstance(block.contents[0], AudioContent)
    assert block.contents[0].duration == 60
    assert block.contents[0].transcript == "Hi"


def test_discriminator_dispatch_video():
    """Test ContentBlock dispatches VideoContent from dict."""
    block = ContentBlock(
        title="test",
        contents=[{"type": "video", "urls": ["http://example.com/v.mp4"], "duration": 120}],
    )
    assert isinstance(block.contents[0], VideoContent)
    assert block.contents[0].duration == 120


def test_discriminator_dispatch_file():
    """Test ContentBlock dispatches FileContent from dict."""
    block = ContentBlock(
        title="test",
        contents=[{"type": "file", "urls": ["http://example.com/f.pdf"], "filename": "f.pdf"}],
    )
    assert isinstance(block.contents[0], FileContent)
    assert block.contents[0].filename == "f.pdf"


def test_discriminator_dispatch_reasoning():
    """Test ContentBlock dispatches ReasoningContent from dict."""
    block = ContentBlock(
        title="test",
        contents=[{"type": "reasoning", "text": "thinking..."}],
    )
    assert isinstance(block.contents[0], ReasoningContent)
    assert block.contents[0].text == "thinking..."


def test_discriminator_dispatch_usage():
    """Test ContentBlock dispatches UsageContent from dict."""
    block = ContentBlock(
        title="test",
        contents=[{"type": "usage", "input_tokens": 100, "output_tokens": 200, "model": "gpt-4"}],
    )
    assert isinstance(block.contents[0], UsageContent)
    assert block.contents[0].input_tokens == 100
    assert block.contents[0].output_tokens == 200
    assert block.contents[0].model == "gpt-4"


def test_discriminator_dispatch_citation():
    """Test ContentBlock dispatches CitationContent from dict."""
    block = ContentBlock(
        title="test",
        contents=[
            {
                "type": "citation",
                "url": "http://example.com",
                "title": "Example",
                "cited_text": "some text",
                "start_index": 0,
                "end_index": 9,
            }
        ],
    )
    assert isinstance(block.contents[0], CitationContent)
    assert block.contents[0].url == "http://example.com"
    assert block.contents[0].cited_text == "some text"
    assert block.contents[0].start_index == 0
    assert block.contents[0].end_index == 9


def test_discriminator_dispatch_all_new_types_together():
    """Test ContentBlock with all new types in a single block."""
    block = ContentBlock(
        title="all new types",
        contents=[
            {"type": "image", "urls": ["http://example.com/img.png"]},
            {"type": "audio", "urls": ["http://example.com/a.mp3"]},
            {"type": "video", "urls": ["http://example.com/v.mp4"]},
            {"type": "file", "urls": ["http://example.com/f.txt"]},
            {"type": "reasoning", "text": "step 1"},
            {"type": "usage", "input_tokens": 10},
            {"type": "citation", "url": "http://example.com"},
        ],
    )
    expected_types = [
        ImageContent,
        AudioContent,
        VideoContent,
        FileContent,
        ReasoningContent,
        UsageContent,
        CitationContent,
    ]
    for i, expected_cls in enumerate(expected_types):
        assert isinstance(block.contents[i], expected_cls), f"contents[{i}] should be {expected_cls.__name__}"


def test_content_block_serialization_round_trip_with_new_types():
    """Test ContentBlock model_dump -> model_validate with new content types."""
    block = ContentBlock(
        title="round trip",
        contents=[
            ImageContent(urls=["http://example.com/img.png"], caption="pic"),
            AudioContent(urls=["http://example.com/a.mp3"], duration=30),
            VideoContent(urls=["http://example.com/v.mp4"]),
            FileContent(urls=["http://example.com/f.pdf"], filename="f.pdf"),
            ReasoningContent(text="thinking"),
            UsageContent(input_tokens=5, output_tokens=10),
            CitationContent(url="http://example.com", title="Ref"),
        ],
    )
    dumped = block.model_dump()
    restored = ContentBlock.model_validate(dumped)
    assert len(restored.contents) == 7
    assert isinstance(restored.contents[0], ImageContent)
    assert restored.contents[0].caption == "pic"
    assert isinstance(restored.contents[4], ReasoningContent)
    assert restored.contents[4].text == "thinking"
    assert isinstance(restored.contents[6], CitationContent)
    assert restored.contents[6].title == "Ref"
