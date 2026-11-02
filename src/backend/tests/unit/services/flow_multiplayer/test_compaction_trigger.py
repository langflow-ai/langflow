"""When multiplayer compaction runs (more than the window plus the step retained), and its check. No database."""

from __future__ import annotations

import hashlib
import uuid

import pytest
from langflow.services.flow_history.errors import FlowHistoryCorruptionError
from langflow.services.flow_multiplayer.compaction import Cut, _verify, due


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        (None, None, False),  # no log rows
        (1, 5000, False),  # exactly the window
        (1, 5001, False),  # past the window, within the step: the legacy trigger would compact here
        (1, 6000, False),  # the window plus the step
        (1, 6001, True),
        (901, 6900, False),  # after a compaction: the window plus less than the step
        (901, 6901, True),
    ],
)
def test_due(first, last, expected):
    assert due(first, last, window=5000, step=1000) is expected


async def test_verify_detects_a_changed_byte():
    """The cut's stored text must hash to its stored hash byte for byte, even when it is the same graph."""
    text = '{"nodes":[{"id":"a","data":{"v":"x"}}],"edges":[]}'
    cut = Cut(
        checkpoint_id=uuid.uuid4(), revision=5, graph_hash=hashlib.sha256(text.encode()).hexdigest(), first_kept=3
    )
    flow_id = uuid.uuid4()
    assert await _verify(flow_id, cut, text) >= 0
    for changed in (text.replace('"x"', '"y"'), text.replace(",", ", ", 1)):  # another graph; the same graph
        with pytest.raises(FlowHistoryCorruptionError):
            await _verify(flow_id, cut, changed)
