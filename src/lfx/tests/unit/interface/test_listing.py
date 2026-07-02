"""Tests for lfx.interface.listing — the synchronous all-types lookup."""

from __future__ import annotations


def test_all_types_dict_is_a_mapping_not_a_coroutine():
    """`all_types_dict` must return a real mapping synchronously.

    Regression: `get_type_dict` called the async `get_all_types_dict` without awaiting it,
    so the sync `_build_dict` did `{**coroutine}` and raised
    "'coroutine' object is not a mapping". This path is reached during graph build (a vertex
    falling back to look up its base_type), so every flow that hit it failed to load.
    """
    from lfx.interface.listing import AllTypesDict

    result = AllTypesDict().all_types_dict

    assert isinstance(result, dict)
    # The sync builder discovers the bundled component categories plus the "Custom" entry.
    assert "Custom" in result
