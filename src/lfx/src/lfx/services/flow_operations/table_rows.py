"""Row identity in table values.

Every row of a table value stored in a flow carries a stable ``_id`` and a
fractional position ``_pos`` so that concurrent edits address rows instead of
indexes. They are bookkeeping for the flow's history, not data: components
never see them, so every place that hands a stored table to component code
strips them first.
"""

from __future__ import annotations

from typing import Any

ROW_ID_KEY = "_id"
ROW_POSITION_KEY = "_pos"
ROW_KEYS = frozenset({ROW_ID_KEY, ROW_POSITION_KEY})


def strip_row_keys(rows: Any) -> Any:
    """Return table rows without ``_id`` and ``_pos``; anything that is not a list of rows is returned as is."""
    if not isinstance(rows, list):
        return rows
    return [
        {key: value for key, value in row.items() if key not in ROW_KEYS} if isinstance(row, dict) else row
        for row in rows
    ]
