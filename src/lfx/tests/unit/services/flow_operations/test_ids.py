"""Opaque ids: the editor's formats, never derived from content."""

from __future__ import annotations

import re

from lfx.services.flow_operations import new_edge_id, new_table_row_id


def test_edge_ids_match_the_editor_format_and_are_unique():
    ids = {new_edge_id() for _ in range(200)}

    assert len(ids) == 200
    assert all(re.fullmatch(r"e-[0-9A-Za-z]{21}", edge_id) for edge_id in ids)


def test_table_row_ids_match_the_editor_format():
    assert re.fullmatch(r"[0-9A-Za-z]{10}", new_table_row_id())
