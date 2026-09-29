"""The per-source and per-class caches in create_class's annotation checks.

Every cached path must return what the uncached path returns, must not be
reused for a different or modified source or class, and must reject the same
unsafe input on every call.
"""

from __future__ import annotations

import ast
import typing

import pytest
from lfx.custom import annotation_validation
from lfx.custom.annotation_validation import (
    UnsafeReturnAnnotationError,
    validate_source_return_annotations,
)
from lfx.custom.validate import create_class

SAFE_SOURCE = "def build() -> list[str]:\n    pass\n"
UNSAFE_SOURCE = 'def build() -> list[open("marker", "w")]:\n    pass\n'


@pytest.fixture(autouse=True)
def _empty_caches():
    annotation_validation._VALIDATED_SOURCE_DIGESTS.clear()
    yield
    annotation_validation._VALIDATED_SOURCE_DIGESTS.clear()


@pytest.fixture
def validation_calls(monkeypatch: pytest.MonkeyPatch) -> list[ast.AST]:
    calls: list[ast.AST] = []
    original = annotation_validation.validate_return_annotations

    def counted(tree: ast.AST) -> None:
        calls.append(tree)
        original(tree)

    monkeypatch.setattr(annotation_validation, "validate_return_annotations", counted)
    return calls


def _validate(source: str) -> None:
    validate_source_return_annotations(source, ast.parse(source))


# --------------------------------------------------------------------------- per-source validation


def test_source_validation_runs_once_per_exact_source(validation_calls: list[ast.AST]) -> None:
    _validate(SAFE_SOURCE)
    _validate(SAFE_SOURCE)

    assert len(validation_calls) == 1


def test_modified_source_is_validated_again(validation_calls: list[ast.AST]) -> None:
    _validate(SAFE_SOURCE)
    _validate(SAFE_SOURCE + "\n")
    _validate(SAFE_SOURCE.replace("list[str]", "list[int]"))

    assert len(validation_calls) == 3


def test_unsafe_source_is_rejected_on_every_call(validation_calls: list[ast.AST]) -> None:
    for _ in range(3):
        with pytest.raises(UnsafeReturnAnnotationError, match="active expression"):
            _validate(UNSAFE_SOURCE)

    assert len(validation_calls) == 3
    assert not annotation_validation._VALIDATED_SOURCE_DIGESTS


def test_unsafe_edit_of_validated_source_is_rejected() -> None:
    _validate(SAFE_SOURCE)

    with pytest.raises(UnsafeReturnAnnotationError, match="active expression"):
        _validate(SAFE_SOURCE.replace("list[str]", 'list[open("marker", "w")]'))


def test_validated_source_cache_is_bounded(monkeypatch: pytest.MonkeyPatch, validation_calls: list[ast.AST]) -> None:
    monkeypatch.setattr(annotation_validation, "_VALIDATED_SOURCES_MAX_ENTRIES", 2)
    sources = [f"def build_{index}() -> str:\n    pass\n" for index in range(3)]
    for source in sources:
        _validate(source)

    assert len(annotation_validation._VALIDATED_SOURCE_DIGESTS) == 2
    _validate(sources[0])  # evicted, validated again
    _validate(sources[2])  # still cached

    assert len(validation_calls) == 4


def _component_source(annotation: str) -> str:
    return f"""\
from lfx.custom import Component
from lfx.io import Output
from lfx.schema import Data

class CachedAnnotationComponent(Component):
    outputs = [Output(name="result", display_name="Result", method="build")]

    def build(self) -> {annotation}:
        return Data(data={{"ok": True}})
"""


def test_create_class_rejects_unsafe_variant_of_cached_source(tmp_path) -> None:
    marker = tmp_path / "annotation-evaluated"
    safe_code = _component_source("Data")
    unsafe_code = _component_source(f"(open({str(marker)!r}, 'w'), Data)[1]")

    first = create_class(safe_code, "CachedAnnotationComponent")()._get_method_return_type("build")
    second = create_class(safe_code, "CachedAnnotationComponent")()._get_method_return_type("build")
    assert first == second != []
    for _ in range(2):
        with pytest.raises(ValueError, match="active expression"):
            create_class(unsafe_code, "CachedAnnotationComponent")

    assert not marker.exists()


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
