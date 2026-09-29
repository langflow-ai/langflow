"""The per-source and per-class caches in create_class's annotation checks.

Every cached path must return what the uncached path returns, must not be
reused for a different or modified source or class, and must reject the same
unsafe input on every call.
"""

from __future__ import annotations

import ast
import sys
import traceback
import typing
from pathlib import Path

import pytest
from lfx.components.processing import output_parser
from lfx.custom import annotation_validation
from lfx.custom.annotation_validation import (
    UnsafeReturnAnnotationError,
    validate_source_return_annotations,
)
from lfx.custom.validate import _future_annotations_import, create_class
from lfx.field_typing.constants import DEFAULT_IMPORT_STRING

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


# --------------------------------------------------------------------------- inserted __future__ import location


def test_future_import_location_matches_fix_missing_locations() -> None:
    source = DEFAULT_IMPORT_STRING + "\n" + Path(output_parser.__file__).read_text(encoding="utf-8")
    fixed = ast.parse(source)
    fixed.body.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    ast.fix_missing_locations(fixed)
    located = ast.parse(source)
    located.body.insert(0, _future_annotations_import())

    assert ast.dump(located, include_attributes=True) == ast.dump(fixed, include_attributes=True)
    fixed_code = compile(fixed, "<string>", "exec")
    located_code = compile(located, "<string>", "exec")
    assert list(located_code.co_positions()) == list(fixed_code.co_positions())


def _source_line(code: str, text: str) -> int:
    """1-based line of ``text`` in the source create_class parses."""
    return (DEFAULT_IMPORT_STRING + "\n" + code).splitlines().index(text) + 1


def _string_frames(exc: BaseException) -> list[traceback.FrameSummary]:
    return [frame for frame in traceback.extract_tb(exc.__traceback__) if frame.filename == "<string>"]


def test_component_method_traceback_points_at_raising_line() -> None:
    code = """\
from lfx.custom import Component
from lfx.io import Output
from lfx.schema import Data

class LineNumberComponent(Component):
    outputs = [Output(name="result", display_name="Result", method="build")]

    def build(self) -> Data:
        value = 1
        raise RuntimeError(f"boom {value}")
"""
    component = create_class(code, "LineNumberComponent")()

    with pytest.raises(RuntimeError, match="boom") as exc_info:
        component.build()

    frame = _string_frames(exc_info.value)[-1]
    assert frame.name == "build"
    assert frame.lineno == _source_line(code, '        raise RuntimeError(f"boom {value}")')
    if sys.version_info >= (3, 11):
        assert (frame.colno, frame.end_colno) == (8, len('        raise RuntimeError(f"boom {value}")'))


def test_class_body_error_traceback_points_at_failing_line() -> None:
    code = """\
from lfx.custom import Component

class BrokenBodyComponent(Component):
    display_name = "Broken"
    ratio = 1 // 0
"""

    with pytest.raises(ValueError, match="ZeroDivisionError") as exc_info:
        create_class(code, "BrokenBodyComponent")

    frame = _string_frames(exc_info.value.__cause__)[-1]
    assert frame.lineno == _source_line(code, "    ratio = 1 // 0")


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
