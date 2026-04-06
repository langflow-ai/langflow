"""Tests for langflow.schema.content_types module."""

from langflow.schema.content_types import (
    BaseContent,
    CodeContent,
    ErrorContent,
    JSONContent,
    MediaContent,
    TextContent,
    ToolContent,
)


class TestErrorContent:
    def test_default_type(self):
        ec = ErrorContent()
        assert ec.type == "error"

    def test_with_all_fields(self):
        ec = ErrorContent(
            component="MyComp",
            field="my_field",
            reason="something broke",
            solution="fix it",
            traceback="Traceback...",
        )
        assert ec.component == "MyComp"
        assert ec.reason == "something broke"
        assert ec.solution == "fix it"
        assert ec.traceback == "Traceback..."

    def test_to_dict(self):
        ec = ErrorContent(reason="test")
        d = ec.to_dict()
        assert d["type"] == "error"
        assert d["reason"] == "test"


class TestTextContent:
    def test_creation(self):
        tc = TextContent(text="hello world")
        assert tc.type == "text"
        assert tc.text == "hello world"

    def test_duration(self):
        tc = TextContent(text="hi", duration=100)
        assert tc.duration == 100

    def test_to_dict(self):
        tc = TextContent(text="test")
        d = tc.to_dict()
        assert d["text"] == "test"
        assert d["type"] == "text"


class TestMediaContent:
    def test_creation(self):
        mc = MediaContent(urls=["http://example.com/img.png"])
        assert mc.type == "media"
        assert mc.urls == ["http://example.com/img.png"]

    def test_with_caption(self):
        mc = MediaContent(urls=["http://example.com/img.png"], caption="A photo")
        assert mc.caption == "A photo"

    def test_multiple_urls(self):
        mc = MediaContent(urls=["url1", "url2", "url3"])
        assert len(mc.urls) == 3


class TestJSONContent:
    def test_creation(self):
        jc = JSONContent(data={"key": "value"})
        assert jc.type == "json"
        assert jc.data == {"key": "value"}

    def test_nested_data(self):
        jc = JSONContent(data={"nested": {"deep": True}})
        assert jc.data["nested"]["deep"] is True


class TestCodeContent:
    def test_creation(self):
        cc = CodeContent(code="print('hi')", language="python")
        assert cc.type == "code"
        assert cc.code == "print('hi')"
        assert cc.language == "python"

    def test_with_title(self):
        cc = CodeContent(code="fn main() {}", language="rust", title="Main")
        assert cc.title == "Main"


class TestToolContent:
    def test_default_type(self):
        tc = ToolContent()
        assert tc.type == "tool_use"

    def test_with_input_alias(self):
        tc = ToolContent(name="my_tool", input={"arg": "value"})
        assert tc.tool_input == {"arg": "value"}

    def test_with_output_and_error(self):
        tc = ToolContent(name="t", output="result", error="err")
        assert tc.output == "result"
        assert tc.error == "err"

    def test_duration(self):
        tc = ToolContent(duration=500)
        assert tc.duration == 500


class TestBaseContent:
    def test_header_default(self):
        ec = ErrorContent()
        assert ec.header == {}

    def test_header_set(self):
        ec = ErrorContent(header={"title": "Error!", "icon": "warning"})
        assert ec.header["title"] == "Error!"
        assert ec.header["icon"] == "warning"

    def test_from_dict(self):
        ec = ErrorContent.from_dict({"type": "error", "reason": "test"})
        assert ec.reason == "test"
