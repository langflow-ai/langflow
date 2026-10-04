"""Opaque ids for things code adds to a flow, in the editor's formats.

An id names an entry and nothing else: it is never derived from what the entry
connects or contains, so changing an edge's handles or a row's cells never
changes its id, and no code may parse one. Existing ids are kept as they are.
"""

from __future__ import annotations

import secrets

# The editor's ids come from short-unique-id's default alphanumeric dictionary.
ALPHANUMERIC = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
EDGE_ID_PREFIX = "e-"
EDGE_ID_LENGTH = 21
TABLE_ROW_ID_LENGTH = 10


def random_alphanumeric(length: int) -> str:
    """Return ``length`` random alphanumeric characters."""
    return "".join(secrets.choice(ALPHANUMERIC) for _ in range(length))


def new_edge_id() -> str:
    """Return a new edge id, ``e-`` and 21 random alphanumerics, like the editor's ``newEdgeId()``."""
    return f"{EDGE_ID_PREFIX}{random_alphanumeric(EDGE_ID_LENGTH)}"


def new_table_row_id() -> str:
    """Return a new table row ``_id``, 10 random alphanumerics, like the editor's ``newTableRowId()``."""
    return random_alphanumeric(TABLE_ROW_ID_LENGTH)
