"""The caches in create_class's annotation checks.

Every cached path must return what the uncached path returns, must not be
reused for a different or modified source, and must reject the same unsafe
input on every call.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import traceback
import typing
from pathlib import Path

import pytest
from cachetools import LRUCache
from lfx.components.processing import output_parser
from lfx.components.processing.output_parser import OutputParserComponent
from lfx.custom import annotation_validation
from lfx.custom.annotation_validation import (
    UnsafeReturnAnnotationError,
    snapshot_trusted_class_method_returns,
    validate_source_return_annotations,
)
from lfx.custom.eval import eval_custom_component_code
from lfx.custom.validate import _future_annotations_import, create_class
from lfx.field_typing.constants import DEFAULT_IMPORT_STRING
from lfx.schema import Data
from lfx.schema.message import Message

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
    monkeypatch.setattr(annotation_validation, "_VALIDATED_SOURCE_DIGESTS", LRUCache(maxsize=2))
    sources = [f"def build_{index}() -> str:\n    pass\n" for index in range(3)]
    _validate(sources[0])
    _validate(sources[1])
    _validate(sources[0])  # cache hit, now the most recently used
    _validate(sources[2])  # evicts sources[1]

    assert len(annotation_validation._VALIDATED_SOURCE_DIGESTS) == 2
    _validate(sources[0])  # still cached
    _validate(sources[1])  # evicted, validated again

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
    # co_positions (line and column spans) exists from Python 3.11; 3.10 has line tables only.
    if sys.version_info >= (3, 11):
        assert list(located_code.co_positions()) == list(fixed_code.co_positions())
    else:
        assert list(located_code.co_lines()) == list(fixed_code.co_lines())


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


# --------------------------------------------------------------------------- trusted class snapshots


def _uncached_snapshot(classes: list[type]) -> dict:
    annotation_validation._parse_return_source.cache_clear()
    return snapshot_trusted_class_method_returns(classes)


def _comparable(snapshots: dict) -> dict:
    return {
        key: (class_ref(), function_ref(), code, guard, resolved)
        for key, (class_ref, function_ref, code, guard, resolved) in snapshots.items()
    }


@pytest.fixture
def parse_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    original = ast.parse

    def counted(source, *args, **kwargs):
        calls.append(source)
        return original(source, *args, **kwargs)

    monkeypatch.setattr(annotation_validation.ast, "parse", counted)
    return calls


def test_trusted_snapshot_with_cached_parses_matches_uncached(parse_calls: list[str]) -> None:
    uncached = _uncached_snapshot([OutputParserComponent])
    parses_uncached = len(parse_calls)
    cached = snapshot_trusted_class_method_returns([OutputParserComponent])

    assert parses_uncached > 0
    assert len(parse_calls) == parses_uncached
    assert _comparable(cached) == _comparable(uncached)
    assert cached[(id(OutputParserComponent), "build_parser")][4] is not None


def test_return_source_parse_is_shared_and_rejects_invalid_syntax() -> None:
    first = annotation_validation._parse_return_source("list[Data]")

    assert first is annotation_validation._parse_return_source("list[Data]")
    assert ast.dump(first) == ast.dump(ast.parse("list[Data]", mode="eval").body)
    assert annotation_validation._parse_return_source("list[") is None


@pytest.fixture
def server_module(tmp_path):
    module_path = tmp_path / "snapshot_cache_server.py"
    module_path.write_text(
        """\
from lfx.schema import Data

Payload = Data

class ServerBase:
    def build(self) -> Payload:
        return Payload()

    def text(self) -> str:
        return ""
""",
        encoding="utf-8",
    )
    module_name = "_lfx_snapshot_cache_server"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)


def _resolved(snapshots: dict, component_class: type, method_name: str) -> typing.Any:
    entry = snapshots.get((id(component_class), method_name))
    return None if entry is None else entry[4]


def test_trusted_snapshot_follows_replaced_method(server_module) -> None:
    base = server_module.ServerBase
    assert _resolved(snapshot_trusted_class_method_returns([base]), base, "text") is str

    base.text = base.build
    after = snapshot_trusted_class_method_returns([base])

    assert _comparable(after) == _comparable(_uncached_snapshot([base]))
    assert _resolved(after, base, "text") is None


def test_trusted_snapshot_follows_replaced_annotations(server_module) -> None:
    base = server_module.ServerBase
    before = snapshot_trusted_class_method_returns([base])
    assert _resolved(before, base, "build") is Data

    base.build.__annotations__ = {"return": "Payload"}
    after = snapshot_trusted_class_method_returns([base])

    assert _comparable(after) == _comparable(_uncached_snapshot([base]))
    assert after[(id(base), "build")][3] != before[(id(base), "build")][3]


def test_trusted_snapshot_follows_rebound_annotation_global(server_module) -> None:
    base = server_module.ServerBase
    assert _resolved(snapshot_trusted_class_method_returns([base]), base, "build") is Data

    server_module.Payload = Message
    after = snapshot_trusted_class_method_returns([base])
    assert _resolved(after, base, "build") is Message
    assert _comparable(after) == _comparable(_uncached_snapshot([base]))

    del server_module.Payload
    assert _resolved(snapshot_trusted_class_method_returns([base]), base, "build") is None


def test_replaced_server_annotation_fails_closed_after_cached_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    clean_code = """\
from lfx.components.processing.output_parser import OutputParserComponent

class CleanOutputParserComponent(OutputParserComponent):
    pass
"""
    poisoned_code = """\
from lfx.components.processing.output_parser import OutputParserComponent

annotation_calls = []

class PoisonAnnotations(dict):
    def get(self, key, default=None):
        annotation_calls.append(key)
        return str

OutputParserComponent.build_parser.__annotations__ = PoisonAnnotations()

class PoisonedOutputParserComponent(OutputParserComponent):
    pass
"""
    original_annotations = OutputParserComponent.build_parser.__annotations__
    monkeypatch.setattr(OutputParserComponent.build_parser, "__annotations__", original_annotations)

    clean_class = eval_custom_component_code(clean_code)
    assert clean_class()._get_method_return_type("build_parser") == ["OutputParser"]
    assert (id(OutputParserComponent), "build_parser") in snapshot_trusted_class_method_returns([OutputParserComponent])

    for _ in range(2):
        poisoned_class = eval_custom_component_code(poisoned_code)
        assert poisoned_class()._get_method_return_type("build_parser") == []
        poison = OutputParserComponent.build_parser.__annotations__
        assert type(poison).get.__globals__["annotation_calls"] == []

    OutputParserComponent.build_parser.__annotations__ = original_annotations
    assert eval_custom_component_code(clean_code)()._get_method_return_type("build_parser") == ["OutputParser"]


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


def test_identity_sets_are_rebuilt_with_bindings() -> None:
    before = annotation_validation._safe_types()
    annotation_validation._safe_types.cache_clear()
    after = annotation_validation._safe_types()

    assert after is not before
    assert after.binding_ids == frozenset(id(value) for value in after.bindings.values())
    assert annotation_validation._safe_type_bindings() is after.bindings
