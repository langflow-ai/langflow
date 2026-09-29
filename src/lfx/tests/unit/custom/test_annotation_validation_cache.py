"""The per-source and per-class caches in create_class's annotation checks.

Every cached path must return what the uncached path returns, must not be
reused for a different or modified source or class, and must reject the same
unsafe input on every call.
"""

from __future__ import annotations

import typing

from lfx.custom import annotation_validation

# --------------------------------------------------------------------------- identity sets


def _candidate_values() -> list[typing.Any]:
    bindings = annotation_validation._safe_type_bindings()
    candidates: list[typing.Any] = [None, Ellipsis, object(), type("Data", (), {}), "Data", 1, list[int], int | str]
    for binding in bindings.values():
        candidates.extend((binding, typing.get_origin(binding)))
    return candidates


def test_safe_type_binding_identity_set_matches_linear_scan() -> None:
    bindings = annotation_validation._safe_type_bindings()
    for value in _candidate_values():
        expected = any(value is binding for binding in bindings.values())
        assert annotation_validation._is_safe_type_binding(value) is expected


def test_safe_subscript_base_identity_set_matches_linear_scan() -> None:
    bindings = annotation_validation._safe_type_bindings()
    for value in _candidate_values():
        expected = any(
            value is binding or value is typing.get_origin(binding)
            for name in annotation_validation._SAFE_SUBSCRIPT_BINDING_NAMES
            if (binding := bindings.get(name)) is not None
        )
        assert annotation_validation._is_safe_subscript_base(value) is expected


def test_identity_sets_follow_rebuilt_bindings() -> None:
    annotation_validation._safe_type_binding_ids()
    annotation_validation._safe_subscript_base_ids()
    annotation_validation._safe_type_bindings.cache_clear()
    try:
        bindings = annotation_validation._safe_type_bindings()
        assert annotation_validation._safe_type_binding_ids() == frozenset(id(value) for value in bindings.values())
        assert annotation_validation._SAFE_TYPE_BINDING_IDS[0] is bindings
        annotation_validation._safe_subscript_base_ids()
        assert annotation_validation._SAFE_SUBSCRIPT_BASE_IDS[0] is bindings
    finally:
        annotation_validation._safe_type_bindings.cache_clear()
