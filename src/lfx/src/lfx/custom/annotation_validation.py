"""Static validation for return annotations in executable custom-component code."""

from __future__ import annotations

import ast
import builtins
import typing
from functools import lru_cache
from types import FunctionType, MethodType, ModuleType
from typing import Any


class UnsafeReturnAnnotationError(ValueError):
    """Raised when a return annotation contains an active Python expression."""


def _annotation_root_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_safe_annotation_node(
    node: ast.AST,
    *,
    seen_strings: frozenset[str],
    inspect_strings: bool = True,
) -> bool:
    """Return whether an annotation contains only passive type-expression syntax."""
    if isinstance(node, ast.Name):
        return not node.id.startswith("__")

    if isinstance(node, ast.Attribute):
        return not node.attr.startswith("__") and _is_safe_annotation_node(
            node.value, seen_strings=seen_strings, inspect_strings=inspect_strings
        )

    if isinstance(node, ast.Subscript):
        if not _is_safe_annotation_node(node.value, seen_strings=seen_strings, inspect_strings=inspect_strings):
            return False

        root_name = _annotation_root_name(node.value)
        if root_name == "Literal":
            return _is_safe_annotation_node(node.slice, seen_strings=seen_strings, inspect_strings=False)
        if root_name == "Annotated" and isinstance(node.slice, ast.Tuple) and node.slice.elts:
            return _is_safe_annotation_node(node.slice.elts[0], seen_strings=seen_strings) and all(
                _is_safe_annotation_node(element, seen_strings=seen_strings, inspect_strings=False)
                for element in node.slice.elts[1:]
            )
        return _is_safe_annotation_node(node.slice, seen_strings=seen_strings, inspect_strings=inspect_strings)

    if isinstance(node, ast.Tuple | ast.List):
        return all(
            _is_safe_annotation_node(element, seen_strings=seen_strings, inspect_strings=inspect_strings)
            for element in node.elts
        )

    if isinstance(node, ast.Starred):
        return _is_safe_annotation_node(node.value, seen_strings=seen_strings, inspect_strings=inspect_strings)

    if isinstance(node, ast.BinOp):
        return (
            isinstance(node.op, ast.BitOr)
            and _is_safe_annotation_node(node.left, seen_strings=seen_strings, inspect_strings=inspect_strings)
            and _is_safe_annotation_node(node.right, seen_strings=seen_strings, inspect_strings=inspect_strings)
        )

    if isinstance(node, ast.UnaryOp):
        return (
            isinstance(node.op, ast.UAdd | ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int | float | complex)
        )

    if isinstance(node, ast.Constant):
        if not isinstance(node.value, str):
            return True
        if not inspect_strings:
            return True

        # Explicitly quoted annotations are evaluated later by get_type_hints.
        # Recursively inspect any string that is itself a valid expression so a
        # quoted forward reference cannot smuggle in a call.
        if node.value in seen_strings:
            return True
        try:
            expression = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            # Strings used as Literal/Annotated metadata need not be expressions.
            return True
        return _is_safe_annotation_node(expression, seen_strings=seen_strings | {node.value})

    return False


def is_safe_return_annotation(annotation: ast.AST) -> bool:
    """Return whether a return annotation is safe to resolve as a type expression."""
    return _is_safe_annotation_node(annotation, seen_strings=frozenset())


def validate_return_annotations(tree: ast.AST) -> None:
    """Reject active expressions in every executable annotation in ``tree``.

    The historical name is retained for callers, but parameters and annotated
    assignments are included because Python or ``typing`` may resolve them too.
    """
    for node in ast.walk(tree):
        annotation: ast.AST | None = None
        label = "Annotation"
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.returns is not None:
            annotation = node.returns
            label = f"Return annotation for '{node.name}'"
        elif isinstance(node, ast.arg) and node.annotation is not None:
            annotation = node.annotation
            label = f"Parameter annotation for '{node.arg}'"
        elif isinstance(node, ast.AnnAssign):
            annotation = node.annotation
            label = f"Variable annotation for '{ast.unparse(node.target)}'"

        if annotation is not None and not is_safe_return_annotation(annotation):
            msg = (
                f"{label} contains an active expression. "
                "Use names, attributes, generics, forward references, or union types only."
            )
            raise UnsafeReturnAnnotationError(msg)


@lru_cache(maxsize=1)
def _safe_type_bindings() -> dict[str, Any]:
    """Return server-owned type objects that static annotation resolution may use."""
    from lfx.field_typing.constants import CUSTOM_COMPONENT_SUPPORTED_TYPES
    from lfx.schema.message import Message

    bindings = {name: value for name, value in vars(builtins).items() if isinstance(value, type)}
    bindings.update(CUSTOM_COMPONENT_SUPPORTED_TYPES)
    bindings["Message"] = Message
    for name in (
        "Annotated",
        "Any",
        "AsyncIterator",
        "Callable",
        "ClassVar",
        "Final",
        "Iterable",
        "Iterator",
        "Literal",
        "Mapping",
        "Optional",
        "Sequence",
        "TypeAlias",
        "Union",
    ):
        bindings[name] = getattr(typing, name)
    return bindings


_SAFE_ANNOTATION_MODULES = {
    "typing",
    "typing_extensions",
    "collections.abc",
    "lfx.schema",
    "langflow.schema",
    "lfx.schema.data",
    "langflow.schema.data",
    "lfx.schema.message",
    "langflow.schema.message",
}

_SAFE_SUBSCRIPT_BINDING_NAMES = {
    "Annotated",
    "AsyncIterator",
    "Callable",
    "ClassVar",
    "Final",
    "Iterable",
    "Iterator",
    "Literal",
    "Mapping",
    "Optional",
    "Sequence",
    "TypeAlias",
    "Union",
    "dict",
    "frozenset",
    "list",
    "set",
    "tuple",
    "type",
}

_MISSING = object()


def _dotted_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _literal_value(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def _runtime_global(globalns: dict[str, Any] | None, name: str) -> Any:
    """Read a runtime name directly from a function globals dictionary."""
    if not isinstance(globalns, dict):
        return _MISSING
    return dict.get(globalns, name, _MISSING)


def _module_namespace(module: ModuleType) -> dict[str, Any] | None:
    """Read a module namespace without dispatching to a subclass override."""
    try:
        namespace = ModuleType.__getattribute__(module, "__dict__")
    except (AttributeError, TypeError):
        return None
    return namespace if isinstance(namespace, dict) else None


@lru_cache(maxsize=1)
def _trusted_runtime_metaclasses() -> frozenset[type]:
    """Return exact metaclasses already trusted by server-owned output types."""
    metaclasses = {type(binding) for binding in _safe_type_bindings().values() if issubclass(type(binding), type)}
    metaclasses.add(type)
    return frozenset(metaclasses)


@lru_cache(maxsize=1)
def _trusted_runtime_annotation_value_types() -> frozenset[type]:
    """Return concrete runtime types for standard typing alias objects."""
    samples = (
        list[int],
        dict[str, int],
        int | str,
        typing.Annotated[int, "metadata"],
        typing.Literal["value"],
        typing.Optional[int],  # noqa: UP045 - sample the legacy typing alias runtime type
        typing.Sequence[int],
    )
    binding_types = {type(binding) for binding in _safe_type_bindings().values() if not issubclass(type(binding), type)}
    return frozenset({*binding_types, *(type(sample) for sample in samples)})


def _is_runtime_annotation_binding(value: Any) -> bool:
    """Accept only real type bindings and trusted typing constructions.

    Runtime globals may contain arbitrary instances. Returning one as an
    annotation would let downstream type formatting invoke its attribute
    hooks, so plain objects are rejected before they leave this resolver.
    """
    if any(value is binding for binding in _safe_type_bindings().values()):
        return True

    # ``type(value)`` observes the real runtime type without consulting a
    # spoofable ``__class__`` attribute. A class object's runtime type is a
    # metaclass (``type`` or a subclass of it).
    if issubclass(type(value), type):
        return type(value) in _trusted_runtime_metaclasses()

    if type(value) not in _trusted_runtime_annotation_value_types():
        return False
    origin = typing.get_origin(value)
    if origin is None:
        return False
    if not (_is_safe_subscript_base(origin) or origin is typing.Union):
        return False
    return all(
        _is_runtime_annotation_binding(argument)
        or argument is Ellipsis
        or type(argument) in {str, bytes, int, float, complex, bool}
        for argument in typing.get_args(value)
    )


def _runtime_module_attribute(node: ast.Attribute, globalns: dict[str, Any] | None) -> tuple[bool, Any]:
    """Resolve an attribute chain rooted in an already-imported module.

    Module dictionaries are read directly so module ``__getattr__`` hooks and
    descriptors stored in a module cannot run during annotation inspection.
    """
    dotted = _dotted_name(node)
    if dotted is None:
        return False, _MISSING

    root_name, *attributes = dotted.split(".")
    value = _runtime_global(globalns, root_name)
    if value is _MISSING:
        return False, _MISSING
    if not isinstance(value, ModuleType):
        return True, _MISSING

    for index, attribute in enumerate(attributes):
        namespace = _module_namespace(value)
        if namespace is None:
            return True, _MISSING
        value = dict.get(namespace, attribute, _MISSING)
        if value is _MISSING:
            return True, _MISSING
        if index < len(attributes) - 1 and not isinstance(value, ModuleType):
            return True, _MISSING
    return True, value


def _is_safe_subscript_base(value: Any) -> bool:
    """Return whether subscription is implemented by a fixed, trusted type object."""
    bindings = _safe_type_bindings()
    return any(value is bindings.get(name) for name in _SAFE_SUBSCRIPT_BINDING_NAMES)


def _is_safe_union_member(value: Any) -> bool:
    """Return whether union construction cannot dispatch to a user-defined type."""
    if value is type(None):
        return True
    if any(value is binding for binding in _safe_type_bindings().values()):
        return True
    if type(value) not in _trusted_runtime_annotation_value_types():
        return False
    args = typing.get_args(value)
    if not args:
        return False
    return all(
        _is_safe_union_member(argument)
        or argument is Ellipsis
        or type(argument) in {str, bytes, int, float, complex, bool}
        for argument in args
    )


def _resolve_annotation_node(node: ast.AST, *, globalns: dict[str, Any] | None = None) -> Any | None:
    """Resolve an annotation without imports, evaluation, or dynamic attribute access."""
    bindings = _safe_type_bindings()

    if isinstance(node, ast.Name):
        runtime_value = _runtime_global(globalns, node.id)
        if runtime_value is not _MISSING:
            return runtime_value if _is_runtime_annotation_binding(runtime_value) else None
        return bindings.get(node.id)

    if isinstance(node, ast.Attribute):
        root_found, runtime_value = _runtime_module_attribute(node, globalns)
        if root_found:
            if runtime_value is _MISSING or not _is_runtime_annotation_binding(runtime_value):
                return None
            return runtime_value
        dotted = _dotted_name(node)
        if dotted is None:
            return None
        module_name, _, member_name = dotted.rpartition(".")
        return bindings.get(member_name) if module_name in _SAFE_ANNOTATION_MODULES else None

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            try:
                return _resolve_annotation_node(ast.parse(node.value, mode="eval").body, globalns=globalns)
            except SyntaxError:
                return None
        if node.value is None:
            return type(None)
        if node.value is Ellipsis:
            return Ellipsis
        return node.value

    if isinstance(node, ast.Tuple):
        resolved = tuple(_resolve_annotation_node(element, globalns=globalns) for element in node.elts)
        return None if any(element is None for element in resolved) else resolved

    if isinstance(node, ast.List):
        resolved = [_resolve_annotation_node(element, globalns=globalns) for element in node.elts]
        return None if any(element is None for element in resolved) else resolved

    if isinstance(node, ast.Subscript):
        base = _resolve_annotation_node(node.value, globalns=globalns)
        if base is None or not _is_safe_subscript_base(base):
            return None

        if base is typing.Literal:
            elements = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            values = tuple(_literal_value(element) for element in elements)
            if any(
                value is None and not isinstance(element, ast.Constant)
                for value, element in zip(values, elements, strict=True)
            ):
                return None
            argument: Any = values[0] if len(values) == 1 else values
        elif base is typing.Annotated:
            if not isinstance(node.slice, ast.Tuple) or not node.slice.elts[1:]:
                return None
            annotation = _resolve_annotation_node(node.slice.elts[0], globalns=globalns)
            if annotation is None:
                return None
            metadata = tuple(_literal_value(element) for element in node.slice.elts[1:])
            argument = (annotation, *metadata)
        else:
            argument = _resolve_annotation_node(node.slice, globalns=globalns)
            if argument is None:
                return None

        try:
            return base[argument]
        except (AttributeError, TypeError, ValueError):
            return None

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _resolve_annotation_node(node.left, globalns=globalns)
        right = _resolve_annotation_node(node.right, globalns=globalns)
        if left is None or right is None or not all(_is_safe_union_member(value) for value in (left, right)):
            return None
        try:
            # Construct through the server-owned typing form so a user-defined
            # metaclass cannot execute an overloaded ``__or__`` hook.
            return typing.Union[left, right]  # noqa: UP007
        except TypeError:
            return None

    return None


def resolve_type_annotation(annotation: Any, *, globalns: dict[str, Any] | None = None) -> Any | None:
    """Resolve a raw annotation without imports, eval, descriptors, or user callbacks."""
    if annotation is None:
        return None
    if isinstance(annotation, ast.AST):
        return _resolve_annotation_node(annotation, globalns=globalns)
    if isinstance(annotation, str):
        try:
            return _resolve_annotation_node(ast.parse(annotation, mode="eval").body, globalns=globalns)
        except SyntaxError:
            return None
    # Already-resolved annotations from server-owned component classes do not
    # require evaluation. Custom classes are compiled with postponed annotations.
    return annotation if _is_runtime_annotation_binding(annotation) else None


def resolve_callable_return_annotation(method: Any) -> Any | None:
    """Resolve a Python function or bound method's return annotation statically."""
    function = method.__func__ if isinstance(method, MethodType) else method
    if not isinstance(function, FunctionType):
        return None
    annotations = function.__annotations__
    return resolve_type_annotation(annotations.get("return"), globalns=function.__globals__)
