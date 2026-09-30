"""Contract: the `human_input` content type must validate in BOTH ContentType unions.

langflow-base and lfx each define a mirrored `ContentType` union. MessageRead uses
one of them; the durable card uses the other. If a tag is added to one union but not
the other, persisting the card fails at read-back with `union_tag_invalid`. This test
guards that drift for the HITL card.
"""

from __future__ import annotations

import pytest
from langflow.schema.content_block import ContentBlock as LangflowContentBlock
from lfx.schema.content_block import ContentBlock as LfxContentBlock

_RAW = {
    "type": "human_input",
    "request_id": "HumanInput-x:job-1",
    "job_id": "job-1",
    "prompt": "Approve refund?",
    "options": [{"action_id": "approve", "label": "Approve"}],
    "allowed_decisions": ["approve"],
}


@pytest.mark.parametrize("content_block_cls", [LangflowContentBlock, LfxContentBlock])
def test_human_input_content_validates_in_both_unions(content_block_cls):
    block = content_block_cls(title="Human input required", contents=[dict(_RAW)])
    content = block.contents[0]
    assert content.type == "human_input"
    assert content.request_id == "HumanInput-x:job-1"
    assert content.options[0]["action_id"] == "approve"


@pytest.mark.parametrize("content_block_cls", [LangflowContentBlock, LfxContentBlock])
def test_human_input_content_round_trips_through_json(content_block_cls):
    block = content_block_cls(title="Human input required", contents=[dict(_RAW)])
    restored = content_block_cls.model_validate(block.model_dump())
    assert restored.contents[0].type == "human_input"
    assert restored.contents[0].submitted_action is None
