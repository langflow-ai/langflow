"""MCP ``ToolAnnotations`` behavior hints surfaced to the flow author.

The hint is display-only: it tells the author which tools are worth gating for
approval. Nothing may gate, exempt, or execute a tool based on it, because the MCP
spec is explicit that annotations from an untrusted server are not trustworthy.
"""

import pytest
from lfx.base.mcp.util import (
    ACCESS_HINT_DESTRUCTIVE,
    ACCESS_HINT_READ_ONLY,
    ACCESS_HINT_WRITE,
    _tool_access_hint,
)
from mcp.types import Tool, ToolAnnotations


def _tool(annotations: ToolAnnotations | None) -> Tool:
    return Tool(name="fetch", description="", inputSchema={"type": "object"}, annotations=annotations)


@pytest.mark.parametrize(
    ("annotations", "expected"),
    [
        # A server that sent no annotations at all tells us nothing. Defaulting here
        # would mark every tool on every un-annotated server destructive.
        (None, None),
        (ToolAnnotations(), None),
        (ToolAnnotations(title="Fetch a page"), None),
        (ToolAnnotations(readOnlyHint=True), ACCESS_HINT_READ_ONLY),
        # readOnlyHint wins: destructiveHint is only meaningful for a writing tool.
        (ToolAnnotations(readOnlyHint=True, destructiveHint=True), ACCESS_HINT_READ_ONLY),
        (ToolAnnotations(readOnlyHint=False, destructiveHint=False), ACCESS_HINT_WRITE),
        (ToolAnnotations(destructiveHint=False), ACCESS_HINT_WRITE),
        (ToolAnnotations(readOnlyHint=False, destructiveHint=True), ACCESS_HINT_DESTRUCTIVE),
        (ToolAnnotations(destructiveHint=True), ACCESS_HINT_DESTRUCTIVE),
        # Either hint present means the spec's defaults apply, and destructiveHint
        # defaults to true, so a declared non-read-only tool stays destructive.
        (ToolAnnotations(readOnlyHint=False), ACCESS_HINT_DESTRUCTIVE),
    ],
)
def test_access_hint_derivation(annotations, expected):
    assert _tool_access_hint(_tool(annotations)) == expected


def test_access_hint_tolerates_a_tool_without_annotations_support():
    """Preset and in-tree tools are not MCP tools and carry no annotations attribute."""

    class PlainTool:
        name = "search"

    assert _tool_access_hint(PlainTool()) is None


def test_access_hint_reaches_the_tools_metadata_row():
    """The row the tools table renders carries the hint through unchanged."""
    from types import SimpleNamespace

    from lfx.custom.custom_component.component import Component

    tool = SimpleNamespace(
        name="delete_repo",
        description="Delete a repository",
        tags=["delete_repo"],
        args={},
        metadata={"access_hint": ACCESS_HINT_DESTRUCTIVE},
    )
    row = Component()._build_tool_data(tool)

    assert row["access_hint"] == ACCESS_HINT_DESTRUCTIVE
    # The hint must not imply a gate: that stays the author's explicit choice.
    assert row["approval_actions"] == []
