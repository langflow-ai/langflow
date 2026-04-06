"""Tests for langflow.schema.content_block module."""

import pytest
from pydantic import BaseModel

from langflow.schema.content_block import ContentBlock, _get_type
from langflow.schema.content_types import (
    CodeContent,
    ErrorContent,
    TextContent,
    ToolContent,
)


class TestGetType:
    def test_dict_with_type(self):
        assert _get_type({"type": "error"}) == "error"

    def test_dict_without_type(self):
        assert _get_type({}) is None

    def test_model_with_type(self):
        ec = ErrorContent()
        assert _get_type(ec) == "error"

    def test_model_without_type(self):

        class NoType(BaseModel):
            name: str = "test"

        obj = NoType()
        assert _get_type(obj) is None


class TestContentBlock:
    def test_basic_creation(self):
        cb = ContentBlock(title="Test", contents=[ErrorContent(reason="err")])
        assert cb.title == "Test"
        assert len(cb.contents) == 1
        assert cb.allow_markdown is True

    def test_multiple_content_types(self):
        cb = ContentBlock(
            title="Mixed",
            contents=[
                TextContent(text="hello"),
                CodeContent(code="x=1", language="python"),
            ],
        )
        assert len(cb.contents) == 2

    def test_contents_must_be_list(self):
        with pytest.raises(TypeError):
            ContentBlock(title="T", contents={"type": "error"})

    def test_single_content_wrapped_in_list(self):
        ec = ErrorContent(reason="test")
        cb = ContentBlock(title="T", contents=ec)
        assert len(cb.contents) == 1
        assert cb.contents[0].reason == "test"

    def test_serialize_contents(self):
        cb = ContentBlock(
            title="T",
            contents=[TextContent(text="hi")],
        )
        d = cb.model_dump()
        assert isinstance(d["contents"], list)
        assert d["contents"][0]["type"] == "text"
        assert d["contents"][0]["text"] == "hi"

    def test_media_url(self):
        cb = ContentBlock(
            title="T",
            contents=[TextContent(text="x")],
            media_url=["http://example.com/img.png"],
        )
        assert cb.media_url == ["http://example.com/img.png"]

    def test_allow_markdown_false(self):
        cb = ContentBlock(
            title="T",
            contents=[TextContent(text="x")],
            allow_markdown=False,
        )
        assert cb.allow_markdown is False
