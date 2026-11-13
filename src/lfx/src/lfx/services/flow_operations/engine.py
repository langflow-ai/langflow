"""The flow engine as one object, with the same interface for the Python engine and the Rust engine.

A server picks an engine by constructing a different object, or by the
``LANGFLOW_FLOW_ENGINE`` environment variable (``python``, the default, or
``rust``) through ``get_engine``. Both objects have the interface of
``lfx_native.ops``:

- ``GraphState(flow)``: a graph kept loaded between batches, with
  ``apply(operations, forward=, backward=, forward_json=)``, ``stage(...)``, ``keep()``,
  ``drop()``, ``replay(operations, backward=)``, ``staged``, ``to_dict()``
  and ``to_json(staged=)``;
- ``GraphPlain(flow)``: a graph read once, with ``validate(base,
  check_values=)``, ``repair(base)``, ``graph_hash()``, ``equals(other)``,
  ``ops_diff(target)``, ``to_dict()`` and ``to_json()``;
- the functions the backend calls: ``apply``, ``replay``, ``ops_diff``,
  ``validate``, ``repair``, ``graph_hash``, ``graphs_equal``,
  ``values_equal``, ``canonical_json``, ``apply_restore_fixes``, the table row
  functions, ``table_fields``, ``new_edge_id``, ``new_table_row_id`` and
  ``node_schema``.

Arguments and results are the same: an argument that is ``bytes`` is UTF-8
JSON text, any other argument is the JSON value itself, and results are
Python values that share nothing with the engine. ``to_json`` gives the same
text from both engines: no spaces, and ASCII only, with a JSON escape for
every other character, as ``json.dumps`` writes by default. Both engines raise
one error type, ``FlowOperationError`` (``EngineError``), as the same subclass for
the same ``kind``, with the same ``code`` and ``details``. A call that cannot
run, such as a batch while another is staged, raises ``RuntimeError``.

The Rust engine has the editor's functions too (``edge_fixes``,
``fixes_for_edges``, ``append_table_rows``, ``assign_changed_node_table_row_ids``
and ``editor=True``); the Python engine does not, as no server path calls them.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from lfx.services.flow_operations import state as _state
from lfx.services.flow_operations.canonical import (
    canonical_text,
    graph_hash_checked,
    ordered_rows,
    trusted_values,
)
from lfx.services.flow_operations.canonical import graphs_equal as _graphs_equal
from lfx.services.flow_operations.canonical import values_equal as _values_equal
from lfx.services.flow_operations.codes import GraphViolationCode
from lfx.services.flow_operations.exceptions import (
    FlowDataValidationError,
    FlowOperationError,
    FlowOperationReplayError,
    FlowOperationValidationError,
    RestoreFixNotAllowedError,
)
from lfx.services.flow_operations.ids import new_edge_id, new_table_row_id
from lfx.services.flow_operations.json_io import copy_json, dump_bytes, dumps, read_data, read_operations
from lfx.services.flow_operations.parse import parse_operations
from lfx.services.flow_operations.plain import GraphPlain as _CorePlain
from lfx.services.flow_operations.schema import NODE_SCHEMA_PATH, load_node_schema
from lfx.services.flow_operations.table_rows import (
    assign_changed_table_row_ids,
    assign_row_ids,
    assign_table_row_ids,
    strip_flow_table_row_keys,
    strip_row_keys,
)
from lfx.services.flow_operations.validation import GraphViolation, find_graph_violations, validate_flow_data

ENGINE_ENV = "LANGFLOW_FLOW_ENGINE"
EngineError = FlowOperationError


def _rows(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        msg = f"{name}: must be a list"
        raise FlowOperationValidationError(msg)
    return value


# --- The Python engine ----------------------------------------------------------------------------


def _with_forward_json(result: dict[str, Any], *, forward: bool) -> dict[str, Any]:
    """``result`` with ``forward_operations_json``, and without ``forward_operations`` unless ``forward`` asks."""
    operations = result["forward_operations"] if forward else result.pop("forward_operations")
    result["forward_operations_json"] = [dump_bytes(operation) for operation in operations]
    return result


class PythonGraphState:
    """A flow graph that the Python engine keeps loaded, to apply or replay many batches on it."""

    __slots__ = ("_state",)

    def __init__(self, flow: Any) -> None:
        self._state = _state.GraphState(read_data(flow, finite=True))

    def apply(
        self, operations: Any, *, forward: bool = False, backward: bool = False, forward_json: bool = False
    ) -> dict[str, Any]:
        """Apply a batch, with every rule; returns what it did.

        With ``forward_json``, ``forward_operations_json`` lists each forward operation as the JSON text
        ``to_json`` writes, one ``bytes`` each: the text an operation log stores.
        """
        result = self._state.apply(read_operations(operations), forward=forward or forward_json, backward=backward)
        return copy_json(_with_forward_json(result, forward=forward) if forward_json else result)

    def stage(
        self, operations: Any, *, forward: bool = False, backward: bool = False, forward_json: bool = False
    ) -> dict[str, Any]:
        """Apply a batch, as ``apply`` does, and keep it staged until ``keep`` or ``drop``."""
        result = self._state.stage(read_operations(operations), forward=forward or forward_json, backward=backward)
        return copy_json(_with_forward_json(result, forward=forward) if forward_json else result)

    def stage_json(self, operations: Any) -> list[bytes]:
        """``stage(operations, forward_json=True)["forward_operations_json"]``, without the rest of the result."""
        result = self._state.stage(read_operations(operations), forward=True, backward=False)
        return [dump_bytes(operation) for operation in result["forward_operations"]]

    def keep(self) -> None:
        self._state.keep()

    def drop(self) -> bool:
        return self._state.drop()

    @property
    def staged(self) -> bool:
        return self._state.staged

    def replay(self, operations: Any, *, backward: bool = False) -> dict[str, Any]:
        """Replay stored operations, with no rule; returns what it did."""
        return copy_json(self._state.replay(read_operations(operations), backward=backward))

    def to_json(self, *, staged: bool = False) -> str:
        """The committed graph as JSON text; with ``staged``, the graph with the staged batch."""
        return self._state.to_json(staged=staged)

    def graph_hash(self, *, staged: bool = False) -> str:
        """The committed graph's ``graph_hash``; with ``staged``, the graph with the staged batch."""
        return self._state.graph_hash(staged=staged)

    def snapshot(self) -> _state.GraphSnapshot:
        """The committed graph as it is now, to write (``to_json``) and hash (``graph_hash``) while batches go on."""
        return self._state.snapshot()

    def to_dict(self) -> dict[str, Any]:
        return self._state.to_dict()


def _violations(violations: list[GraphViolation]) -> list[dict[str, Any]]:
    return [violation.to_dict() for violation in violations]


class PythonGraphPlain:
    """A flow graph the Python engine read once, to validate, repair, hash, compare and diff it."""

    __slots__ = ("core",)

    def __init__(self, flow: Any, *, core: _CorePlain | None = None) -> None:
        self.core = core if core is not None else _CorePlain(read_data(flow, finite=True))

    def validate(self, base: PythonGraphPlain | None = None, *, check_values: bool = True) -> list[dict[str, Any]]:
        core_base = None if base is None else base.core
        with trusted_values():
            return _violations(self.core.violations(core_base, check_values=check_values))

    def repair(self, base: PythonGraphPlain | None = None) -> tuple[PythonGraphPlain, list[dict[str, Any]]]:
        with trusted_values():
            repaired, fixes = self.core.repair(None if base is None else base.core)
        return PythonGraphPlain(None, core=repaired), [fix.to_dict() for fix in fixes]

    def graph_hash(self) -> str:
        return self.core.graph_hash()

    def equals(self, other: PythonGraphPlain) -> bool:
        with trusted_values():
            return self.core.equals(other.core)

    def ops_diff(self, target: PythonGraphPlain) -> list[dict[str, Any]]:
        with trusted_values():
            return copy_json(self.core.ops_diff(target.core))

    def to_json(self) -> str:
        return dumps(self.core.value)

    def to_dict(self) -> Any:
        return copy_json(self.core.value)


class PythonEngine:
    """The Python engine (``lfx.services.flow_operations``), with the interface of ``lfx_native.ops``."""

    name = "python"
    GraphState = PythonGraphState
    GraphPlain = PythonGraphPlain
    EngineError = FlowOperationError

    @staticmethod
    def apply(flow: Any, operations: Any, *, forward: bool = True, backward: bool = False) -> dict[str, Any]:
        """Apply operations to a graph, with every rule; returns ``{"flow_data", ...}``."""
        from lfx.services.flow_operations.apply import apply_batch

        flow = read_data(flow, finite=True)
        parsed = parse_operations(read_operations(operations))
        state = _state.GraphState.checked(flow)
        result = apply_batch(state, parsed, forward=forward, backward=backward)
        state.commit()
        result["flow_data"] = state.to_value()
        return result

    @staticmethod
    def replay(flow: Any, operations: Any, *, backward: bool = False) -> dict[str, Any]:
        """Replay stored operations on a graph, with no rule; returns ``{"flow_data", ...}``."""
        from lfx.services.flow_operations.replay import replay_batch

        flow = read_data(flow, finite=True)
        parsed = parse_operations(read_operations(operations))
        state = _state.GraphState(flow)
        result = replay_batch(state, parsed, backward=backward)
        state.commit()
        result["flow_data"] = state.to_value()
        return result

    @staticmethod
    def ops_diff(base: Any, target: Any) -> list[dict[str, Any]]:
        """The operations that turn ``base`` into ``target``, checked by replay."""
        from lfx.services.flow_operations.diff import derive_checked

        base, target = read_data(base), read_data(target)
        with trusted_values():
            validate_flow_data(base, check_values=False)
            validate_flow_data(target, context="target flow.data")
            operations, _flow_data = derive_checked(base, target)
        return operations

    @staticmethod
    def validate(flow: Any, base: Any = None, *, check_values: bool = True) -> list[dict[str, Any]]:
        flow = read_data(flow)
        base = None if base is None else read_data(base)
        with trusted_values():
            return _violations(find_graph_violations(flow, check_values=check_values, base=base))

    @staticmethod
    def repair(flow: Any, base: Any = None) -> dict[str, Any]:
        from lfx.services.flow_operations.repair import repair_checked

        flow = read_data(flow)
        base = None if base is None else read_data(base)
        with trusted_values():
            repaired = repair_checked(flow, base=base)
        return {"flow_data": repaired.flow_data, "fixes": [fix.to_dict() for fix in repaired.fixes]}

    @staticmethod
    def graph_hash(flow: Any) -> str:
        return graph_hash_checked(read_data(flow))

    @staticmethod
    def text_sha256(text: str | bytes) -> str:
        """The SHA-256 hex digest of ``text`` (a ``str`` as UTF-8): a checkpoint's stored-text hash."""
        return hashlib.sha256(text.encode() if isinstance(text, str) else text).hexdigest()

    @staticmethod
    def graphs_equal(left: Any, right: Any) -> bool:
        left, right = read_data(left), read_data(right)
        with trusted_values():
            return _graphs_equal(left, right)

    @staticmethod
    def values_equal(left: Any, right: Any) -> bool:
        return _values_equal(read_data(left), read_data(right))

    @staticmethod
    def canonical_json(value: Any) -> str:
        return canonical_text(read_data(value))

    @staticmethod
    def apply_restore_fixes(revision: Any, stored: Any, fixes: Any) -> dict[str, Any]:
        """A revision with a restore's fixes applied, after checking each one."""
        from langflow.services.flow_history import errors as history_errors
        from langflow.services.flow_history.restore_fixes import apply_restore_fixes

        from lfx.services.flow_operations.ops import parse_flow_operations

        revision, stored = read_data(revision), read_data(stored)
        parsed = parse_flow_operations(read_operations(fixes))
        try:
            return apply_restore_fixes(revision, stored, parsed)
        except history_errors.RestoreFixNotAllowedError as error:
            raised = RestoreFixNotAllowedError(str(error))
            raised.code = error.code
            raise raised from None

    @staticmethod
    def ordered_rows(rows: Any) -> list[Any]:
        return ordered_rows(_rows(read_data(rows), "rows"))

    @staticmethod
    def strip_row_keys(rows: Any) -> Any:
        return strip_row_keys(read_data(rows))

    @staticmethod
    def strip_flow_table_row_keys(flow: Any) -> Any:
        return strip_flow_table_row_keys(read_data(flow))

    @staticmethod
    def assign_row_ids(rows: Any, previous: Any = None) -> list[Any]:
        rows = _rows(read_data(rows), "rows")
        return assign_row_ids(rows, None if previous is None else read_data(previous))

    @staticmethod
    def assign_table_row_ids(node: Any) -> Any:
        return assign_table_row_ids(read_data(node))

    @staticmethod
    def assign_changed_table_row_ids(base: Any, target: Any) -> Any:
        return assign_changed_table_row_ids(read_data(base), read_data(target))

    @staticmethod
    def table_fields(node: Any) -> list[str]:
        node = read_data(node)
        template = node.get("data", {}).get("node", {}).get("template") if isinstance(node, dict) else None
        if not isinstance(template, dict):
            return []
        schema = load_node_schema()
        return [
            name
            for name, field in template.items()
            if isinstance(field, dict)
            and isinstance(field.get("value"), list)
            and schema.is_table_at(node, ("data", "node", "template", name, "value"))
        ]

    new_edge_id = staticmethod(new_edge_id)
    new_table_row_id = staticmethod(new_table_row_id)

    @staticmethod
    def node_schema() -> str:
        return NODE_SCHEMA_PATH.read_text(encoding="utf-8")


# --- The Rust engine --------------------------------------------------------------------------------


def _error_from_native(error: Exception) -> FlowOperationError:
    """The Python engine's error for an error of the Rust engine: the same kind, code and details."""
    details = getattr(error, "details", None) or {}
    kind = getattr(error, "kind", "")
    code = getattr(error, "code", FlowOperationError.code)
    message = details.get("message", str(error))
    if kind == "FlowOperationValidationError":
        return FlowOperationValidationError(message, code=code, edge_id=details.get("edge_id"))
    if kind == "FlowDataValidationError":
        violations = [
            GraphViolation(
                GraphViolationCode(violation["code"]),
                tuple(violation["path"]),
                violation["message"],
                violation.get("edge_id"),
            )
            for violation in details.get("violations", [])
        ]
        raised: FlowOperationError = FlowDataValidationError(message, violations=violations)
    elif kind == "FlowOperationReplayError":
        raised = FlowOperationReplayError(message)
    elif kind == "RestoreFixNotAllowedError":
        raised = RestoreFixNotAllowedError(message)
    else:
        raised = FlowOperationError(message)
    raised.code = code
    return raised


def _native() -> Any:
    from lfx_native import ops

    return ops


def _call(function: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return function(*args, **kwargs)
    except _native().EngineError as error:
        raise _error_from_native(error) from None


class RustGraphState:
    """A flow graph that the Rust engine keeps loaded (``lfx_native.ops.GraphState``)."""

    __slots__ = ("_state",)

    def __init__(self, flow: Any) -> None:
        self._state = _call(_native().GraphState, flow)

    def apply(
        self, operations: Any, *, forward: bool = False, backward: bool = False, forward_json: bool = False
    ) -> dict[str, Any]:
        return _call(self._state.apply, operations, forward=forward, backward=backward, forward_json=forward_json)

    def stage(
        self, operations: Any, *, forward: bool = False, backward: bool = False, forward_json: bool = False
    ) -> dict[str, Any]:
        # The write path calls this once per batch: the native call is inlined, without ``_call``.
        try:
            return self._state.stage(operations, forward=forward, backward=backward, forward_json=forward_json)
        except _native().EngineError as error:
            raise _error_from_native(error) from None

    def stage_json(self, operations: Any) -> list[bytes]:
        """``stage(operations, forward_json=True)["forward_operations_json"]``, without the rest of the result.

        The native ``stage`` with only ``forward_json`` returns just that list, so no other part is built.
        """
        try:
            result = self._state.stage(operations, forward_json=True)
        except _native().EngineError as error:
            raise _error_from_native(error) from None
        return result.get("forward_operations_json") or []

    def keep(self) -> None:
        self._state.keep()

    def drop(self) -> bool:
        return self._state.drop()

    @property
    def staged(self) -> bool:
        return self._state.staged

    def replay(self, operations: Any, *, backward: bool = False) -> dict[str, Any]:
        return _call(self._state.replay, operations, backward=backward)

    def to_json(self, *, staged: bool = False) -> str:
        return self._state.to_json(staged=staged)

    def graph_hash(self, *, staged: bool = False) -> str:
        return _call(self._state.graph_hash, staged=staged)

    def snapshot(self) -> RustGraphSnapshot:
        return RustGraphSnapshot(self._state.snapshot())

    def to_dict(self) -> dict[str, Any]:
        return self._state.to_dict()


class RustGraphSnapshot:
    """A graph as a ``RustGraphState`` held it when ``snapshot`` took it (``lfx_native.ops.GraphSnapshot``)."""

    __slots__ = ("_snapshot",)

    def __init__(self, snapshot: Any) -> None:
        self._snapshot = snapshot

    def to_json(self) -> str:
        return self._snapshot.to_json()

    def graph_hash(self) -> str:
        return _call(self._snapshot.graph_hash)


class RustGraphPlain:
    """A flow graph the Rust engine read once (``lfx_native.ops.GraphPlain``)."""

    __slots__ = ("core",)

    def __init__(self, flow: Any, *, core: Any = None) -> None:
        self.core = core if core is not None else _call(_native().GraphPlain, flow)

    def validate(self, base: RustGraphPlain | None = None, *, check_values: bool = True) -> list[dict[str, Any]]:
        return _call(self.core.validate, None if base is None else base.core, check_values=check_values)

    def repair(self, base: RustGraphPlain | None = None) -> tuple[RustGraphPlain, list[dict[str, Any]]]:
        repaired, fixes = _call(self.core.repair, None if base is None else base.core)
        return RustGraphPlain(None, core=repaired), fixes

    def graph_hash(self) -> str:
        return _call(self.core.graph_hash)

    def equals(self, other: RustGraphPlain) -> bool:
        return _call(self.core.equals, other.core)

    def ops_diff(self, target: RustGraphPlain) -> list[dict[str, Any]]:
        return _call(self.core.ops_diff, target.core)

    def to_json(self) -> str:
        return self.core.to_json()

    def to_dict(self) -> Any:
        return self.core.to_dict()


def _rust_function(name: str) -> Any:
    def call(*args: Any, **kwargs: Any) -> Any:
        return _call(getattr(_native(), name), *args, **kwargs)

    call.__name__ = name
    call.__doc__ = f"``lfx_native.ops.{name}``, with the Python engine's errors."
    return staticmethod(call)


class RustEngine:
    """The Rust engine (``lfx_native.ops``), with its errors raised as the Python engine's error types."""

    name = "rust"
    GraphState = RustGraphState
    GraphPlain = RustGraphPlain
    EngineError = FlowOperationError

    apply = _rust_function("apply")
    replay = _rust_function("replay")
    ops_diff = _rust_function("ops_diff")
    validate = _rust_function("validate")
    repair = _rust_function("repair")
    graph_hash = _rust_function("graph_hash")
    text_sha256 = _rust_function("text_sha256")
    graphs_equal = _rust_function("graphs_equal")
    values_equal = _rust_function("values_equal")
    canonical_json = _rust_function("canonical_json")
    apply_restore_fixes = _rust_function("apply_restore_fixes")
    ordered_rows = _rust_function("ordered_rows")
    strip_row_keys = _rust_function("strip_row_keys")
    strip_flow_table_row_keys = _rust_function("strip_flow_table_row_keys")
    assign_row_ids = _rust_function("assign_row_ids")
    assign_table_row_ids = _rust_function("assign_table_row_ids")
    assign_changed_table_row_ids = _rust_function("assign_changed_table_row_ids")
    assign_changed_node_table_row_ids = _rust_function("assign_changed_node_table_row_ids")
    append_table_rows = _rust_function("append_table_rows")
    edge_fixes = _rust_function("edge_fixes")
    fixes_for_edges = _rust_function("fixes_for_edges")
    table_fields = _rust_function("table_fields")
    new_edge_id = _rust_function("new_edge_id")
    new_table_row_id = _rust_function("new_table_row_id")
    node_schema = _rust_function("node_schema")


ENGINES = {"python": PythonEngine, "rust": RustEngine}


def get_engine(name: str | None = None) -> type[PythonEngine | RustEngine]:
    """The engine ``name`` names, or the one ``LANGFLOW_FLOW_ENGINE`` names (``python`` by default)."""
    chosen = (name or os.environ.get(ENGINE_ENV) or "python").strip().lower()
    engine = ENGINES.get(chosen)
    if engine is None:
        msg = f"{ENGINE_ENV} must be one of {', '.join(ENGINES)}, not {chosen!r}"
        raise ValueError(msg)
    if engine is RustEngine:
        _native()
    return engine


__all__ = [
    "ENGINE_ENV",
    "EngineError",
    "PythonEngine",
    "PythonGraphPlain",
    "PythonGraphState",
    "RustEngine",
    "RustGraphPlain",
    "RustGraphState",
    "get_engine",
]
