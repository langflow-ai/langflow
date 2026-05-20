"""Tests for URLComponent input type configuration."""

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def url_component(monkeypatch):
    """Import URLComponent with heavy third-party modules stubbed for this test."""
    for mod in (
        "langchain_community",
        "langchain_community.document_loaders",
        "markitdown",
        "bs4",
        "lxml",
    ):
        monkeypatch.setitem(sys.modules, mod, MagicMock())

    from lfx.components.data_source.url import URLComponent

    return URLComponent


class TestURLComponentInputTypes:
    """Verify the urls input accepts Message as an input type."""

    def test_urls_input_accepts_message_type(self, url_component):
        urls_input = next(inp for inp in url_component.inputs if inp.name == "urls")
        assert "Message" in urls_input.input_types

    def test_urls_input_is_list(self, url_component):
        urls_input = next(inp for inp in url_component.inputs if inp.name == "urls")
        assert urls_input.is_list is True
