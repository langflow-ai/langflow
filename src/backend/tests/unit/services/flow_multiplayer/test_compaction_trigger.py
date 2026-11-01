"""When multiplayer compaction runs: once more than the window plus the step is retained. No database."""

from __future__ import annotations

import pytest
from langflow.services.flow_multiplayer.compaction import due


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
