"""Tests for URLComponent input type configuration."""

import sys
from unittest.mock import MagicMock

# Stub heavy third-party modules so URLComponent can be imported without them.
for mod in (
    "langchain_community",
    "langchain_community.document_loaders",
    "markitdown",
    "bs4",
    "lxml",
):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from lfx.components.data_source.url import URLComponent  # noqa: E402


class TestURLComponentInputTypes:
    """Verify the urls input accepts Message as an input type."""

    def test_urls_input_accepts_message_type(self):
        urls_input = next(inp for inp in URLComponent.inputs if inp.name == "urls")
        assert "Message" in urls_input.input_types

    def test_urls_input_is_list(self):
        urls_input = next(inp for inp in URLComponent.inputs if inp.name == "urls")
        assert urls_input.is_list is True
