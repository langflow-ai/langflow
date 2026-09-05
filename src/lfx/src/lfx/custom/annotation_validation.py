"""Static validation for return annotations in executable custom-component code."""

from __future__ import annotations

import ast
import builtins
import typing
from functools import lru_cache
from pathlib import Path
from types import FunctionType, MappingProxyType, MethodType, ModuleType, UnionType
from typing import Any
from weakref import ReferenceType, ref

_MAX_ANNOTATION_DEPTH = 32
_RUNTIME_ANNOTATED_ALIAS_TYPE = type(typing.Annotated[int, "metadata"])


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
            # Metadata does not participate in Langflow's output type. Validate
            # only the wrapped type so common metadata factories such as
            # Pydantic Field(...) remain compatible without being resolved.
            return _is_safe_annotation_node(node.slice.elts[0], seen_strings=seen_strings)
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
    from lfx.field_typing.constants import CUSTOM_COMPONENT_SUPPORTED_TYPES, OutputParser
    from lfx.schema.message import Message

    bindings = {name: value for name, value in vars(builtins).items() if isinstance(value, type)}
    bindings.update(CUSTOM_COMPONENT_SUPPORTED_TYPES)
    bindings["Message"] = Message
    bindings["OutputParser"] = OutputParser
    for name in (
        "Annotated",
        "Any",
        "AsyncIterator",
        "Callable",
        "ClassVar",
        "Final",
        "Iterable",
        "Iterator",
        "List",
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
    "List",
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


def safe_annotation_aliases(imports: list[Any]) -> dict[str, str]:
    """Map parsed safe imports to canonical names without importing them."""
    aliases: dict[str, str] = {}
    for imported in imports:
        match imported:
            case (str(module_name), str(imported_name)):
                if module_name not in _SAFE_ANNOTATION_MODULES:
                    continue
                name, separator, local_name = imported_name.partition(" as ")
                local_name = local_name if separator else name
                if name.isidentifier() and local_name.isidentifier():
                    aliases[local_name] = f"{module_name}.{name}"
            case str():
                module_name, separator, local_name = imported.partition(" as ")
                if separator and module_name in _SAFE_ANNOTATION_MODULES and local_name.isidentifier():
                    aliases[local_name] = module_name
            case _:
                continue
    return aliases


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
        typing.Callable[[str], int],
    )
    binding_types = {type(binding) for binding in _safe_type_bindings().values() if not issubclass(type(binding), type)}
    return frozenset({*binding_types, *(type(sample) for sample in samples)})


def _runtime_alias_parts(value: Any) -> tuple[Any, tuple[Any, ...]] | None:
    """Read trusted typing-alias internals without dynamic attribute dispatch."""
    if type(value) is UnionType:
        try:
            arguments = object.__getattribute__(value, "__args__")
        except (AttributeError, TypeError):
            return None
        return (typing.Union, arguments) if type(arguments) is tuple else None

    try:
        origin = object.__getattribute__(value, "__origin__")
        arguments = object.__getattribute__(value, "__args__")
    except (AttributeError, TypeError):
        return None
    if type(arguments) is not tuple:
        return None
    if type(value) is _RUNTIME_ANNOTATED_ALIAS_TYPE:
        return typing.Annotated, (origin,)
    return origin, arguments


def _is_runtime_annotation_binding(
    value: Any,
    *,
    seen: frozenset[int] = frozenset(),
    depth: int = 0,
) -> bool:
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
    if depth >= _MAX_ANNOTATION_DEPTH or id(value) in seen:
        return False
    alias_parts = _runtime_alias_parts(value)
    if alias_parts is None:
        return False
    origin, arguments = alias_parts
    if not (_is_safe_subscript_base(origin) or origin is typing.Union):
        return False
    nested_seen = seen | {id(value)}
    return all(
        _is_runtime_annotation_binding(argument, seen=nested_seen, depth=depth + 1)
        or argument is Ellipsis
        or type(argument) in {str, bytes, int, float, complex, bool}
        for argument in arguments
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
    return any(
        value is binding or value is typing.get_origin(binding)
        for name in _SAFE_SUBSCRIPT_BINDING_NAMES
        if (binding := bindings.get(name)) is not None
    )


def _is_safe_union_member(value: Any) -> bool:
    """Return whether union construction cannot dispatch to a user-defined type."""
    if value is type(None):
        return True
    return _is_runtime_annotation_binding(value)


def _resolve_static_alias(alias: str) -> Any | None:
    module_name, separator, member_name = alias.rpartition(".")
    if not separator or module_name not in _SAFE_ANNOTATION_MODULES:
        return None
    return _safe_type_bindings().get(member_name)


def _resolve_annotation_node(
    node: ast.AST,
    *,
    globalns: dict[str, Any] | None = None,
    aliases: dict[str, str] | None = None,
) -> Any | None:
    """Resolve an annotation without imports, evaluation, or dynamic attribute access."""
    bindings = _safe_type_bindings()

    if isinstance(node, ast.Name):
        runtime_value = _runtime_global(globalns, node.id)
        if runtime_value is not _MISSING:
            return runtime_value if _is_runtime_annotation_binding(runtime_value) else None
        if aliases and (alias := aliases.get(node.id)) is not None:
            return _resolve_static_alias(alias)
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
        if aliases:
            root_name, separator, remainder = dotted.partition(".")
            if separator and (alias := aliases.get(root_name)) is not None:
                dotted = f"{alias}.{remainder}"
        module_name, _, member_name = dotted.rpartition(".")
        return bindings.get(member_name) if module_name in _SAFE_ANNOTATION_MODULES else None

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            try:
                return _resolve_annotation_node(
                    ast.parse(node.value, mode="eval").body,
                    globalns=globalns,
                    aliases=aliases,
                )
            except SyntaxError:
                return None
        if node.value is None:
            return type(None)
        if node.value is Ellipsis:
            return Ellipsis
        return node.value

    if isinstance(node, ast.Tuple):
        resolved = tuple(_resolve_annotation_node(element, globalns=globalns, aliases=aliases) for element in node.elts)
        return None if any(element is None for element in resolved) else resolved

    if isinstance(node, ast.List):
        resolved = [_resolve_annotation_node(element, globalns=globalns, aliases=aliases) for element in node.elts]
        return None if any(element is None for element in resolved) else resolved

    if isinstance(node, ast.Subscript):
        base = _resolve_annotation_node(node.value, globalns=globalns, aliases=aliases)
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
            # Langflow's output type contract consumes only the wrapped type;
            # metadata is deliberately never evaluated by this resolver.
            return _resolve_annotation_node(node.slice.elts[0], globalns=globalns, aliases=aliases)
        else:
            argument = _resolve_annotation_node(node.slice, globalns=globalns, aliases=aliases)
            if argument is None:
                return None

        try:
            return base[argument]
        except (AttributeError, TypeError, ValueError):
            return None

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _resolve_annotation_node(node.left, globalns=globalns, aliases=aliases)
        right = _resolve_annotation_node(node.right, globalns=globalns, aliases=aliases)
        if left is None or right is None or not all(_is_safe_union_member(value) for value in (left, right)):
            return None
        try:
            # Construct through the server-owned typing form so a user-defined
            # metaclass cannot execute an overloaded ``__or__`` hook.
            return typing.Union[left, right]  # noqa: UP007
        except TypeError:
            return None

    return None


def resolve_type_annotation(
    annotation: Any,
    *,
    globalns: dict[str, Any] | None = None,
    aliases: dict[str, str] | None = None,
) -> Any | None:
    """Resolve a raw annotation without imports, eval, descriptors, or user callbacks."""
    if annotation is None:
        return None
    if isinstance(annotation, ast.AST):
        return _resolve_annotation_node(annotation, globalns=globalns, aliases=aliases)
    if isinstance(annotation, str):
        try:
            return _resolve_annotation_node(ast.parse(annotation, mode="eval").body, globalns=globalns, aliases=aliases)
        except SyntaxError:
            return None
    # Already-resolved annotations from server-owned component classes do not
    # require evaluation. Custom classes are compiled with postponed annotations.
    if not _is_runtime_annotation_binding(annotation):
        return None
    if type(annotation) is _RUNTIME_ANNOTATED_ALIAS_TYPE:
        alias_parts = _runtime_alias_parts(annotation)
        return alias_parts[1][0] if alias_parts is not None else None
    return annotation


_TrustedMethodKey = tuple[int, str]
_TrustedMethodSnapshot = tuple[ReferenceType, ReferenceType, Any, tuple[Any, ...], Any]
_COMPILED_CLASS_METHOD_RETURNS: dict[
    int,
    tuple[ReferenceType, MappingProxyType, MappingProxyType],
] = {}


def _remove_compiled_class_sidecar(class_id: int, dead_reference: ReferenceType) -> None:
    entry = dict.get(_COMPILED_CLASS_METHOD_RETURNS, class_id)
    if entry is not None and entry[0] is dead_reference:
        dict.pop(_COMPILED_CLASS_METHOD_RETURNS, class_id, None)


def _compiled_class_metadata(component_class: type) -> tuple[MappingProxyType, MappingProxyType] | None:
    entry = dict.get(_COMPILED_CLASS_METHOD_RETURNS, id(component_class))
    if entry is None or entry[0]() is not component_class:
        return None
    return entry[1], entry[2]


@lru_cache(maxsize=128)
def _source_function_returns(filename: str) -> MappingProxyType | None:
    try:
        tree = ast.parse(Path(filename).read_text(encoding="utf-8"), filename=filename)
    except (OSError, SyntaxError, UnicodeError):
        return None

    method_returns: dict[tuple[str, int], str | None] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        try:
            return_source = ast.unparse(node.returns) if node.returns is not None else None
        except (RecursionError, ValueError):
            return_source = None
        start_line = min((decorator.lineno for decorator in node.decorator_list), default=node.lineno)
        for key in {(node.name, start_line), (node.name, node.lineno)}:
            if key in method_returns:
                method_returns[key] = None
            else:
                method_returns[key] = return_source
    return MappingProxyType(method_returns)


def _static_function_return(function: FunctionType, method_name: str) -> ast.AST | None:
    code = FunctionType.__getattribute__(function, "__code__")
    filename = code.co_filename
    first_line = code.co_firstlineno
    method_returns = _source_function_returns(filename) if isinstance(filename, str) else None
    if method_returns is None:
        return None
    return_source = MappingProxyType.get(method_returns, (method_name, first_line))
    if return_source is None:
        return None
    try:
        return ast.parse(return_source, mode="eval").body
    except SyntaxError:
        return None


def _runtime_annotation_guard(function: FunctionType) -> tuple[Any, ...] | None:
    """Capture annotation storage identity without invoking deferred evaluation."""
    try:
        annotator = FunctionType.__getattribute__(function, "__annotate__")
    except AttributeError:
        annotator = None
    if annotator is not None:
        annotator_code = (
            FunctionType.__getattribute__(annotator, "__code__") if type(annotator) is FunctionType else None
        )
        return ("deferred", annotator, annotator_code)

    annotations = FunctionType.__getattribute__(function, "__annotations__")
    if type(annotations) is not dict or not dict.__contains__(annotations, "return"):
        return None
    return ("eager", id(annotations), dict.__getitem__(annotations, "return"))


def snapshot_trusted_class_method_returns(
    classes: list[type],
) -> dict[_TrustedMethodKey, _TrustedMethodSnapshot]:
    """Snapshot inherited method returns from server source without evaluating annotations."""
    trusted_classes: dict[int, type] = {}
    for value in classes:
        try:
            mro = type.__getattribute__(value, "__mro__")
        except (AttributeError, TypeError):
            continue
        if type(mro) is tuple:
            for base in mro:
                trusted_classes[id(base)] = base

    method_returns: dict[_TrustedMethodKey, _TrustedMethodSnapshot] = {}
    for class_id, component_class in trusted_classes.items():
        try:
            namespace = type.__getattribute__(component_class, "__dict__")
        except (AttributeError, TypeError):
            continue
        if type(namespace) is not MappingProxyType:
            continue
        for method_name, descriptor in MappingProxyType.items(namespace):
            if type(method_name) is not str:
                continue
            function = (
                object.__getattribute__(descriptor, "__func__")
                if type(descriptor) in {classmethod, staticmethod}
                else descriptor
            )
            if type(function) is not FunctionType:
                continue
            function_code = FunctionType.__getattribute__(function, "__code__")
            return_node = _static_function_return(function, method_name)
            annotation_guard = _runtime_annotation_guard(function)
            if return_node is None or annotation_guard is None:
                continue
            resolved_return = resolve_type_annotation(
                return_node,
                globalns=FunctionType.__getattribute__(function, "__globals__"),
            )
            if resolved_return is None:
                continue
            method_returns[(class_id, method_name)] = (
                ref(component_class),
                ref(function),
                function_code,
                annotation_guard,
                resolved_return,
            )
    return method_returns


def _annotation_contains_untracked_class(
    annotation: Any,
    preexisting_class_ids: frozenset[int],
    *,
    seen: frozenset[int] = frozenset(),
    depth: int = 0,
) -> bool:
    if issubclass(type(annotation), type):
        is_server_binding = any(annotation is binding for binding in _safe_type_bindings().values())
        return not is_server_binding and id(annotation) not in preexisting_class_ids
    if depth >= _MAX_ANNOTATION_DEPTH or id(annotation) in seen:
        return True
    if type(annotation) is not UnionType and type(annotation) not in _trusted_runtime_annotation_value_types():
        return False
    alias_parts = _runtime_alias_parts(annotation)
    if alias_parts is None:
        return False
    nested_seen = seen | {id(annotation)}
    return any(
        _annotation_contains_untracked_class(
            argument,
            preexisting_class_ids,
            seen=nested_seen,
            depth=depth + 1,
        )
        for argument in alias_parts[1]
    )


def _class_control_flow_method_names(class_node: ast.ClassDef) -> tuple[str, ...]:
    """Collect method names under class control flow without inferring a branch."""
    method_names: list[str] = []

    class ClassScopeVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            method_names.append(node.name)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            method_names.append(node.name)

        def visit_ClassDef(self, _node: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, _node: ast.Lambda) -> None:
            return

    visitor = ClassScopeVisitor()
    for statement in class_node.body:
        if not isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            visitor.visit(statement)
    return tuple(method_names)


def _validate_compiled_class_identity(
    component_class: type,
    class_node: ast.ClassDef,
    globalns: dict[str, Any],
    preexisting_class_ids: frozenset[int],
    *,
    allow_preexisting_class: bool,
) -> None:
    """Reject a class decorator that substitutes a foreign runtime class."""
    from lfx.custom.custom_component.component import Component
    from lfx.custom.custom_component.custom_component import CustomComponent

    expected_module = dict.get(globalns, "__name__")
    try:
        runtime_module = type.__getattribute__(component_class, "__module__")
        runtime_name = type.__getattribute__(component_class, "__name__")
        runtime_qualname = type.__getattribute__(component_class, "__qualname__")
    except (AttributeError, TypeError) as exc:
        msg = "Compiled component class provenance could not be verified."
        raise UnsafeReturnAnnotationError(msg) from exc

    if (
        component_class is Component
        or component_class is CustomComponent
        or (id(component_class) in preexisting_class_ids and not allow_preexisting_class)
        or runtime_module != expected_module
        or runtime_name != class_node.name
        or runtime_qualname != class_node.name
    ):
        msg = f"Class decorator for '{class_node.name}' returned a foreign class."
        raise UnsafeReturnAnnotationError(msg)


def register_compiled_class_method_returns(
    component_class: type,
    class_node: ast.ClassDef,
    *,
    globalns: dict[str, Any],
    preexisting_class_ids: frozenset[int],
    trusted_method_returns: dict[_TrustedMethodKey, _TrustedMethodSnapshot] | None = None,
    allow_preexisting_class: bool = False,
    infer_decorated_methods: bool = True,
    trusted_vector_store_applied: bool = False,
    trusted_vector_store_output: type | None = None,
) -> None:
    """Store immutable direct-method return types derived from validated AST."""
    if allow_preexisting_class and (class_node.decorator_list or type(component_class) is not type):
        msg = f"Preexisting class '{class_node.name}' cannot be registered safely."
        raise UnsafeReturnAnnotationError(msg)
    _validate_compiled_class_identity(
        component_class,
        class_node,
        globalns,
        preexisting_class_ids,
        allow_preexisting_class=allow_preexisting_class,
    )
    method_returns: dict[str, Any | None] = {}
    infer_direct_returns = not class_node.decorator_list or trusted_vector_store_applied
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            resolved_return = (
                resolve_type_annotation(node.returns, globalns=globalns)
                if (
                    infer_direct_returns
                    and (infer_decorated_methods or not node.decorator_list)
                    and node.returns is not None
                )
                else None
            )
            method_returns[node.name] = (
                None
                if _annotation_contains_untracked_class(resolved_return, preexisting_class_ids)
                else resolved_return
            )
    for method_name in _class_control_flow_method_names(class_node):
        method_returns[method_name] = None
    if trusted_vector_store_applied:
        method_returns["as_vector_store"] = (
            trusted_vector_store_output
            if trusted_vector_store_output is not None and _is_runtime_annotation_binding(trusted_vector_store_output)
            else None
        )
    class_id = id(component_class)
    class_reference = ref(
        component_class,
        lambda dead_reference, class_id=class_id: _remove_compiled_class_sidecar(class_id, dead_reference),
    )
    dict.__setitem__(
        _COMPILED_CLASS_METHOD_RETURNS,
        class_id,
        (
            class_reference,
            MappingProxyType(method_returns),
            MappingProxyType(dict(trusted_method_returns or {})),
        ),
    )


def _resolve_trusted_method_snapshot(
    defining_class: type,
    method_name: str,
    namespace: MappingProxyType,
    trusted_snapshots: list[MappingProxyType],
) -> tuple[bool, Any | None]:
    key = (id(defining_class), method_name)
    for snapshots in trusted_snapshots:
        if key not in snapshots:
            continue
        (
            class_reference,
            function_reference,
            function_code,
            annotation_guard,
            resolved_return,
        ) = MappingProxyType.__getitem__(snapshots, key)
        if class_reference() is not defining_class:
            return True, None
        descriptor = MappingProxyType.__getitem__(namespace, method_name)
        function = (
            object.__getattribute__(descriptor, "__func__")
            if type(descriptor) in {classmethod, staticmethod}
            else descriptor
        )
        if (
            type(function) is not FunctionType
            or function_reference() is not function
            or FunctionType.__getattribute__(function, "__code__") is not function_code
        ):
            return True, None
        if annotation_guard[0] == "deferred":
            try:
                current_annotator = FunctionType.__getattribute__(function, "__annotate__")
            except AttributeError:
                return True, None
            annotator, annotator_code = annotation_guard[1:]
            if current_annotator is not annotator or (
                type(annotator) is FunctionType
                and FunctionType.__getattribute__(annotator, "__code__") is not annotator_code
            ):
                return True, None
        else:
            annotations = FunctionType.__getattribute__(function, "__annotations__")
            annotations_id, raw_return = annotation_guard[1:]
            if (
                type(annotations) is not dict
                or id(annotations) != annotations_id
                or not dict.__contains__(annotations, "return")
                or dict.__getitem__(annotations, "return") is not raw_return
            ):
                return True, None
        if not _is_runtime_annotation_binding(resolved_return):
            return True, None
        return True, resolved_return
    return False, None


def resolve_compiled_method_return_annotation(component_class: type, method_name: str) -> tuple[bool, Any | None]:
    """Read a compiled method return from its static MRO owner."""
    try:
        mro = type.__getattribute__(component_class, "__mro__")
    except (AttributeError, TypeError):
        return False, None
    if type(mro) is not tuple:
        return False, None

    crossed_sidecar = False
    trusted_snapshots: list[MappingProxyType] = []
    for defining_class in mro:
        metadata = _compiled_class_metadata(defining_class)
        method_returns = metadata[0] if metadata is not None else None
        if metadata is not None:
            trusted_snapshots.append(metadata[1])
        try:
            namespace = type.__getattribute__(defining_class, "__dict__")
        except (AttributeError, TypeError):
            return False, None
        if type(namespace) is not MappingProxyType:
            return False, None
        if method_name not in namespace:
            crossed_sidecar = crossed_sidecar or method_returns is not None
            continue

        if method_returns is None:
            if not crossed_sidecar:
                return False, None
            found, return_annotation = _resolve_trusted_method_snapshot(
                defining_class,
                method_name,
                namespace,
                trusted_snapshots,
            )
            return (found, return_annotation) if found else (True, None)
        if method_name not in method_returns:
            return True, None
        break
    else:
        return (True, None) if crossed_sidecar else (False, None)

    return_annotation = method_returns[method_name]
    if return_annotation is not None and not _is_runtime_annotation_binding(return_annotation):
        return True, None
    return True, return_annotation


def resolve_callable_return_annotation(method: Any) -> Any | None:
    """Resolve a Python function or bound method's return annotation statically."""
    function = method.__func__ if isinstance(method, MethodType) else method
    if not isinstance(function, FunctionType):
        return None
    annotations = function.__annotations__
    return resolve_type_annotation(annotations.get("return"), globalns=function.__globals__)


def _static_bound_method_name(component_class: type, function: Any) -> tuple[bool, str | None]:
    """Find the unique class-dictionary key bound to a method function."""
    try:
        mro = type.__getattribute__(component_class, "__mro__")
    except (AttributeError, TypeError):
        return False, None
    if type(mro) is not tuple:
        return False, None

    method_name = None
    for defining_class in mro:
        try:
            namespace = type.__getattribute__(defining_class, "__dict__")
        except (AttributeError, TypeError):
            return False, None
        if type(namespace) is not MappingProxyType:
            return False, None
        for name, descriptor in MappingProxyType.items(namespace):
            if type(name) is not str:
                continue
            candidate = (
                object.__getattribute__(descriptor, "__func__") if type(descriptor) is classmethod else descriptor
            )
            if candidate is not function:
                continue
            if method_name is not None and method_name != name:
                return False, None
            method_name = name
    return True, method_name


def resolve_method_return_annotation(
    method: Any | None = None,
    *,
    component_class: type | None = None,
    method_name: str | None = None,
    method_getter: typing.Callable[[], Any] | None = None,
) -> Any | None:
    """Resolve a method return through the compiled sidecar before runtime annotations."""
    if type(method) is MethodType:
        try:
            bound_self = MethodType.__getattribute__(method, "__self__")
            function = MethodType.__getattribute__(method, "__func__")
        except (AttributeError, TypeError):
            pass
        else:
            if component_class is None:
                component_class = bound_self if issubclass(type(bound_self), type) else type(bound_self)
            if method_name is None:
                unambiguous, method_name = _static_bound_method_name(component_class, function)
                if not unambiguous:
                    return None
                if method_name is None and type(function) is FunctionType:
                    method_name = FunctionType.__getattribute__(function, "__name__")

    if component_class is not None and method_name is not None:
        found, return_annotation = resolve_compiled_method_return_annotation(component_class, method_name)
        if found:
            return return_annotation

    if method is None and method_getter is not None:
        method = method_getter()
    return resolve_callable_return_annotation(method) if method is not None else None
