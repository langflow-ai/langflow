"""Tests for the v1 (release-1.11.0) content_blocks projection.

Covers the flat-agent-log reconstruction: the agent renderer emits a flat,
chronological content_blocks list (interleaved text + tool_use, no wrapping
group), and ``legacy_content_blocks`` reconstructs an "Agent Steps" group so the
v1 wire keeps tool-call visibility. The reconstruction must gate on ``tool_use``
(the agent-step signal), NOT on "any non-text leaf", or plain replies that carry
top-level ``usage`` / ``media`` leaves (from ``from_lc_message``) would get a
phantom "Agent Steps" group on the v1 wire.
"""

from langchain_core.messages import AIMessage
from lfx.schema.legacy_render import legacy_content_blocks, render_v1_content_blocks
from lfx.schema.message import Message


def _leaf(**kwargs):
    return {"id": "x", "duration": None, "header": {}, "contents": [], **kwargs}


def test_flat_agent_log_with_tool_use_wraps_into_agent_steps():
    """A flat log with a tool_use leaf is wrapped so v1 shows the tool call."""
    flat = [
        _leaf(type="text", text="let me search"),
        _leaf(type="tool_use", name="search", tool_input={"q": "x"}, output="r", error=None),
        _leaf(type="text", text="final answer"),
    ]
    result = legacy_content_blocks(flat)
    assert len(result) == 1
    group = result[0]
    assert group["title"] == "Agent Steps"
    assert group["allow_markdown"] is True
    assert group["media_url"] is None
    # all three leaves are kept, in order, stripped of id/contents
    assert [c["type"] for c in group["contents"]] == ["text", "tool_use", "text"]
    assert all("id" not in c and "contents" not in c for c in group["contents"])
    assert any(c["type"] == "tool_use" for c in group["contents"])


def test_plain_reply_with_usage_leaf_is_not_wrapped():
    """A plain reply (text + top-level usage) must stay text-only on the v1 wire."""
    blocks = [_leaf(type="text", text="Hello!"), _leaf(type="usage", input_tokens=10, output_tokens=5)]
    assert legacy_content_blocks(blocks) == []


def test_multimodal_message_with_media_leaf_is_not_wrapped():
    """Text + top-level media (a vision message) is not an agent step log."""
    blocks = [_leaf(type="text", text="look"), _leaf(type="media", urls=["http://example.com/i.png"])]
    assert legacy_content_blocks(blocks) == []


def test_tool_less_agent_answer_projects_empty():
    """A flat log with no tool call has no steps to show, so it projects to []."""
    assert legacy_content_blocks([_leaf(type="text", text="just an answer")]) == []


def test_grouped_agent_message_still_folds_output_leaf():
    """The existing grouped-agent path is unchanged: the answer folds as Output."""
    grouped = [
        {
            "type": "group",
            "title": "Agent Steps",
            "allow_markdown": True,
            "media_url": None,
            "contents": [_leaf(type="tool_use", name="s", tool_input={}, output="o", error=None)],
        },
        _leaf(type="text", text="the answer"),
    ]
    result = legacy_content_blocks(grouped)
    assert len(result) == 1
    output_leaf = result[0]["contents"][-1]
    assert output_leaf["header"] == {"title": "Output", "icon": "MessageSquare"}
    assert output_leaf["text"] == "the answer"


def test_lc_message_with_usage_does_not_get_phantom_group():
    """End-to-end: a real from_lc_message reply does not gain an Agent Steps group."""
    lc = AIMessage(
        content="Hello there",
        usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
    )
    message = Message.from_lc_message(lc)
    rendered = render_v1_content_blocks(message.content_blocks)
    assert all(block.get("title") != "Agent Steps" for block in rendered or [])
