"""Generate .pyi stub files for components to enable IDE autocomplete."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.custom.custom_component.component import Component

# Mapping from input class names to Python types
# These are the "native" types that each input stores/expects
INPUT_TYPE_MAP: dict[str, str] = {
    "StrInput": "str",
    "MessageTextInput": "str | Message",  # Accepts Message but stores str
    "MultilineInput": "str | Message",
    "MultilineSecretInput": "str",  # pragma: allowlist secret
    "SecretStrInput": "str",  # pragma: allowlist secret
    "IntInput": "int",
    "FloatInput": "float",
    "BoolInput": "bool",
    "DictInput": "dict[str, Any]",
    "NestedDictInput": "dict[str, Any]",
    "TableInput": "list[dict[str, Any]]",
    "DropdownInput": "str",
    "HandleInput": "Any",
    "DataInput": "Data",
    "DataFrameInput": "DataFrame",
    "MessageInput": "Message",
    "PromptInput": "str",
    "CodeInput": "str",
    "FileInput": "str",
    "LinkInput": "str",
    "SliderInput": "float",
    "ToolsInput": "list[dict]",
    "ConnectionInput": "Any",
}

# Input types where we should NOT use input_types for the type hint
# because input_types describes what can be connected, not what value type is stored
IGNORE_INPUT_TYPES_FOR: set[str] = {
    "MessageTextInput",
    "MultilineInput",
}


def _get_python_type_for_input(inp: Any) -> str:
    """Get the Python type annotation string for an input."""
    input_class_name = type(inp).__name__

    # For certain input types, use the explicit mapping instead of input_types
    if input_class_name in IGNORE_INPUT_TYPES_FOR:
        return INPUT_TYPE_MAP.get(input_class_name, "Any")

    # Check if it has input_types defined (like HandleInput)
    if hasattr(inp, "input_types") and inp.input_types:
        types = inp.input_types
        if len(types) == 1:
            return types[0]
        return f"{' | '.join(types)}"

    return INPUT_TYPE_MAP.get(input_class_name, "Any")


def _get_default_repr(value: Any) -> str:
    """Get a string representation of a default value for stub files."""
    if value is None:
        return "None"
    if isinstance(value, str):
        # Escape quotes in string
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        return "..."
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "..."
    return "..."


def _get_output_return_type(output: Any, component_class: type | None = None) -> str:
    """Get the return type for an output method.

    Args:
        output: The Output object.
        component_class: The component class to inspect for method return type annotations.

    Returns:
        The return type as a string.
    """
    # First, try to get the return type from output.types
    if hasattr(output, "types") and output.types:
        types = output.types
        if len(types) == 1:
            return types[0]
        return f"{' | '.join(types)}"

    # If no types defined, try to get from method's return type annotation
    if component_class and hasattr(output, "method") and output.method:
        method = getattr(component_class, output.method, None)
        if method:
            hints = getattr(method, "__annotations__", {})
            return_hint = hints.get("return")
            if return_hint is not None:
                return _type_to_str(return_hint)

    return "Any"


def _type_to_str(type_hint: Any) -> str:
    """Convert a type hint to a string representation for stubs."""
    import typing

    # Handle None type
    if type_hint is type(None):
        return "None"

    # Handle string annotations (forward references)
    if isinstance(type_hint, str):
        return type_hint

    # Handle typing module types (Union, Optional, etc.)
    origin = getattr(type_hint, "__origin__", None)

    if origin is typing.Union:
        args = getattr(type_hint, "__args__", ())
        # Check if it's Optional (Union with None)
        if len(args) == 2 and type(None) in args:  # noqa: PLR2004
            non_none = next(a for a in args if a is not type(None))
            return f"{_type_to_str(non_none)} | None"
        return " | ".join(_type_to_str(a) for a in args)

    if origin is list:
        args = getattr(type_hint, "__args__", ())
        if args:
            return f"list[{_type_to_str(args[0])}]"
        return "list"

    if origin is dict:
        args = getattr(type_hint, "__args__", ())
        if len(args) == 2:  # noqa: PLR2004
            return f"dict[{_type_to_str(args[0])}, {_type_to_str(args[1])}]"
        return "dict"

    # Handle regular types
    if hasattr(type_hint, "__name__"):
        return type_hint.__name__

    # Fallback to string representation
    return str(type_hint).replace("typing.", "").replace("lfx.schema.", "")


def generate_stubs_for_component(component_class: type[Component]) -> str:
    """Generate stub content for a single component class.

    Args:
        component_class: The component class to generate stubs for.

    Returns:
        String containing the .pyi stub content for the class.
    """
    lines = []

    # Get the class name and parent
    class_name = component_class.__name__

    # Find base class
    bases = [b.__name__ for b in component_class.__bases__ if b.__name__ != "object"]
    base_str = ", ".join(bases) if bases else "Component"

    lines.append(f"class {class_name}({base_str}):")

    # Get inputs from class attribute
    inputs = getattr(component_class, "inputs", [])
    outputs = getattr(component_class, "outputs", [])

    if not inputs and not outputs:
        lines.append("    ...")
        return "\n".join(lines)

    # Generate set() method signature
    lines.append("    def set(")
    lines.append("        self,")
    lines.append("        *,")

    seen_names: set[str] = set()
    for inp in inputs:
        if inp.name in seen_names:
            continue
        seen_names.add(inp.name)

        py_type = _get_python_type_for_input(inp)
        default = _get_default_repr(inp.value) if inp.value is not None else "..."

        lines.append(f"        {inp.name}: {py_type} = {default},")

    lines.append("    ) -> Self: ...")

    # Generate output method stubs
    for output in outputs:
        if not hasattr(output, "method") or not output.method:
            continue

        method_name = output.method
        return_type = _get_output_return_type(output, component_class)

        # Check if the method is async by inspecting the class
        method = getattr(component_class, method_name, None)
        if method and inspect.iscoroutinefunction(method):
            lines.append(f"    async def {method_name}(self) -> {return_type}: ...")
        else:
            lines.append(f"    def {method_name}(self) -> {return_type}: ...")

    return "\n".join(lines)


def _collect_imports(component_classes: list[type[Component]]) -> set[str]:
    """Collect all imports needed for the stub file."""
    imports: set[str] = set()
    imports.add("from typing import Any")
    imports.add("from typing_extensions import Self")

    for component_class in component_classes:
        inputs = getattr(component_class, "inputs", [])
        outputs = getattr(component_class, "outputs", [])

        for inp in inputs:
            py_type = _get_python_type_for_input(inp)
            if "Data" in py_type:
                imports.add("from lfx.schema.data import Data")
            if "DataFrame" in py_type:
                imports.add("from lfx.schema.dataframe import DataFrame")
            if "Message" in py_type:
                imports.add("from lfx.schema.message import Message")

        for output in outputs:
            return_type = _get_output_return_type(output, component_class)
            if "Data" in return_type:
                imports.add("from lfx.schema.data import Data")
            if "DataFrame" in return_type:
                imports.add("from lfx.schema.dataframe import DataFrame")
            if "Message" in return_type:
                imports.add("from lfx.schema.message import Message")

    return imports


def generate_stubs_for_module(module_path: str) -> dict[str, str]:
    """Generate stubs for all components in a module.

    Args:
        module_path: The import path to the module (e.g., 'lfx.components.input_output').

    Returns:
        Dict mapping relative file paths to stub content.
    """
    from lfx.custom.custom_component.component import Component

    stubs: dict[str, str] = {}

    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return stubs

    # Find all Component subclasses in the module
    component_classes: list[type[Component]] = []
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, Component) and obj is not Component:
            component_classes.append(obj)

    if not component_classes:
        return stubs

    # Generate imports
    imports = _collect_imports(component_classes)

    # Generate stub content
    lines = list(imports)
    lines.append("")
    lines.append("")

    for component_class in sorted(component_classes, key=lambda c: c.__name__):
        lines.append(generate_stubs_for_component(component_class))
        lines.append("")
        lines.append("")

    # Determine output path
    module_parts = module_path.split(".")
    stub_path = "/".join(module_parts) + ".pyi"

    stubs[stub_path] = "\n".join(lines)

    return stubs


def generate_stubs(output_dir: str | Path | None = None) -> dict[str, str]:
    """Generate stubs for all lfx components.

    Args:
        output_dir: Optional directory to write stub files to.
            If None, returns the stubs as a dict without writing.

    Returns:
        Dict mapping file paths to stub content.
    """
    from lfx.custom.custom_component.component import Component

    all_stubs: dict[str, str] = {}

    # Import the components package to discover submodules
    try:
        import lfx.components as components_pkg
    except ImportError:
        return all_stubs

    # Walk through all submodules
    package_path = Path(components_pkg.__file__).parent

    for module_info in pkgutil.walk_packages([str(package_path)], prefix="lfx.components."):
        try:
            module = importlib.import_module(module_info.name)
        except Exception:  # noqa: BLE001, S112
            # Skip modules that can't be imported (missing optional dependencies, key errors, etc.)
            continue

        # Find Component subclasses
        component_classes: list[type[Component]] = []
        for name in dir(module):
            try:
                obj = getattr(module, name)
            except Exception:  # noqa: BLE001, S112
                # Skip attributes that can't be accessed (lazy loading failures, missing deps)
                continue

            try:
                if (
                    isinstance(obj, type)
                    and issubclass(obj, Component)
                    and obj is not Component
                    and obj.__module__ == module_info.name
                ):
                    component_classes.append(obj)
            except (TypeError, Exception):  # noqa: BLE001, S112
                # issubclass can fail for some types
                continue

        if not component_classes:
            continue

        # Generate imports
        imports = _collect_imports(component_classes)

        # Generate stub content
        lines = sorted(imports)
        lines.append("")
        lines.append("")

        for component_class in sorted(component_classes, key=lambda c: c.__name__):
            lines.append(generate_stubs_for_component(component_class))
            lines.append("")
            lines.append("")

        # Determine output path
        module_parts = module_info.name.split(".")
        stub_path = "/".join(module_parts) + ".pyi"

        all_stubs[stub_path] = "\n".join(lines)

    # Write files if output_dir is specified
    if output_dir:
        output_path = Path(output_dir)

        # Track directories that need __init__.pyi
        init_dirs: set[Path] = set()

        for stub_path, content in all_stubs.items():
            full_path = output_path / stub_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

            # Track all parent directories for __init__.pyi
            parent = full_path.parent
            while parent not in (output_path, output_path.parent):
                init_dirs.add(parent)
                parent = parent.parent

        # Create __init__.pyi files for all package directories
        for init_dir in init_dirs:
            init_file = init_dir / "__init__.pyi"
            if not init_file.exists():
                # Create stub that re-exports from submodules
                init_file.write_text("# Auto-generated stub\n")

    return all_stubs
