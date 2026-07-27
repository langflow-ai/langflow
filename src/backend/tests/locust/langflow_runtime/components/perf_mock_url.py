"""Stub URL fetch for Natural ``external_apis=stubbed`` (keeps ``URLComponent`` type)."""

from __future__ import annotations

from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

PERF_MOCK_URL_MARKER = "PERF_MOCK_URL"


class URLComponent(Component):
    """Deterministic URL tool — no outbound HTTP."""

    display_name = "URL"
    description = "Stub URL fetch for Natural suite stubbed runs."
    name = "URLComponent"
    icon = "layout-template"

    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            info="Ignored; stub returns a fixed page.",
            is_list=True,
            tool_mode=True,
            value=["https://example.invalid/perf-natural"],
        ),
    ]
    outputs = [
        Output(display_name="Extracted Pages", name="page_results", method="fetch_content"),
        Output(display_name="Raw Content", name="raw_results", method="fetch_content_as_message", tool_mode=False),
    ]

    async def fetch_content(self) -> DataFrame:
        return DataFrame(
            data=[
                {
                    "text": f"{PERF_MOCK_URL_MARKER}:example page body",
                    "url": "https://example.invalid/perf-natural",
                    "title": "perf-natural",
                    "description": PERF_MOCK_URL_MARKER,
                    "content_type": "text/plain",
                    "language": "en",
                }
            ]
        )

    async def fetch_content_as_message(self) -> Message:
        return Message(text=f"{PERF_MOCK_URL_MARKER}:example page body")
