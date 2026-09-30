"""Tests for AIMessage content-block normalization.

Gemini 3 (and other modern LangChain chat models) return ``AIMessage.content`` as a
list of content blocks instead of a plain string. ``Message.text`` only accepts
strings / iterators, so ``_normalize_message_content`` flattens the blocks before
the result hits ``Message(text=...)``.
"""

from __future__ import annotations

from lfx.base.models.model import _normalize_message_content


class TestNormalizeMessageContent:
    def test_string_input_is_returned_as_is(self):
        assert _normalize_message_content("hello") == "hello"

    def test_empty_string_is_preserved(self):
        assert _normalize_message_content("") == ""

    def test_none_is_returned_as_is(self):
        assert _normalize_message_content(None) is None

    def test_gemini_3_style_content_list_is_joined(self):
        # Shape observed from gemini-3.1-pro-preview via langchain-google-genai 4.1.3.
        content = [
            {
                "type": "text",
                "text": "Hello, world!",
                "thought_signature": "vx7EMmgbm32zqhkN+Q==",
            }
        ]
        assert _normalize_message_content(content) == "Hello, world!"

    def test_multiple_text_blocks_are_concatenated_in_order(self):
        content = [
            {"type": "text", "text": "foo"},
            {"type": "text", "text": "bar"},
        ]
        assert _normalize_message_content(content) == "foobar"

    def test_non_text_blocks_are_dropped(self):
        content = [
            {"type": "text", "text": "keep me"},
            {"type": "image_url", "image_url": {"url": "..."}},
            {"type": "thinking", "thinking": "internal monologue"},
        ]
        assert _normalize_message_content(content) == "keep me"

    def test_bare_string_blocks_are_included(self):
        content = ["foo", {"type": "text", "text": "bar"}]
        assert _normalize_message_content(content) == "foobar"

    def test_block_missing_text_field_is_skipped(self):
        content = [
            {"type": "text"},
            {"type": "text", "text": None},
            {"type": "text", "text": "kept"},
        ]
        assert _normalize_message_content(content) == "kept"

    def test_empty_list_yields_empty_string(self):
        assert _normalize_message_content([]) == ""
