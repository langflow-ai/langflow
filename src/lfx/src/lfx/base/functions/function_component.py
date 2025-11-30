"""FunctionComponent - Wrap Python functions as Langflow components."""

from __future__ import annotations

import functools
import inspect
import warnings
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    ParamSpec,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

import nanoid

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import (
    BoolInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageInput,
    MessageTextInput,
    MultilineInput,
    StrInput,
)
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.template.field.base import Output

if TYPE_CHECKING:
    from collections.abc import Callable

    from lfx.inputs.inputs import InputTypes

P = ParamSpec("P")
T = TypeVar("T")

# Mapping from Python types to Langflow Input classes
TYPE_TO_INPUT_CLASS: dict[type, type] = {
    str: MessageTextInput,
    int: IntInput,
    float: FloatInput,
    bool: BoolInput,
    Message: MessageInput,
}

# Mapping from Python types to output type strings
TYPE_TO_OUTPUT_TYPE: dict[type, str] = {
    str: "Message",
    int: "int",
    float: "float",
    bool: "bool",
    dict: "Data",
    list: "list",
    Message: "Message",
    Data: "Data",
}


@dataclass
class InputConfig:
    """Configuration for a function parameter input field.

    Use with typing.Annotated to customize input behavior.

    Example:
        def process(
            name: Annotated[str, InputConfig(placeholder="Enter name")]
        ) -> str:
            return name
    """

    display_name: str | None = None
    info: str | None = None
    placeholder: str | None = None
    advanced: bool = False
    multiline: bool = False
    password: bool = False
    show: bool = True
    required: bool | None = None  # None = infer from default
    input_types: list[str] | None = None
    options: list[str] | None = field(default=None)
    combobox: bool = False


class FunctionComponent(Component):
    """A component that wraps an arbitrary Python function.

    This component dynamically generates inputs and outputs based on
    the function's signature and type annotations.

    Example:
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        fc = FunctionComponent(greet)
        fc.set(name="World")
        result = await fc.invoke_function()
        # result == "Hello, World!"
    """

    trace_type = "function"
    icon = "Code"

    def __init__(
        self,
        func: Callable,
        _id: str | None = None,
        display_name: str | None = None,
        description: str | None = None,
        _source_code: str | None = None,
        **kwargs,
    ) -> None:
        self._wrapped_function = func
        self._func_name = func.__name__

        # Extract function metadata
        self._signature = inspect.signature(func)
        try:
            # Use include_extras=True to preserve Annotated metadata
            self._type_hints = get_type_hints(func, include_extras=True) if func else {}
        except Exception:  # noqa: BLE001
            # get_type_hints can fail with NameError, AttributeError, etc.
            self._type_hints = {}
        self._docstring = inspect.getdoc(func) or ""
        self._param_docs = self._parse_docstring_params()

        # Capture source code for persistence
        if _source_code:
            self._function_source = _source_code
        else:
            try:
                self._function_source = inspect.getsource(func)
            except (OSError, TypeError):
                self._function_source = self._generate_stub_code()

        # Build inputs/outputs from signature
        inputs = self._build_inputs_from_signature()
        outputs = self._build_outputs_from_signature()

        # Set display name from function name if not provided
        if display_name is None:
            display_name = self._func_name.replace("_", " ").title()

        # Set description from docstring if not provided
        if description is None and self._docstring:
            description = self._docstring.split("\n")[0]

        # Generate ID from function name if not provided
        if _id is None:
            _id = f"{self._func_name}_{nanoid.generate(size=5)}"

        # Store for parent class
        self.inputs = inputs
        self.outputs = outputs

        super().__init__(
            _id=_id,
            _display_name=display_name,
            _description=description,
            **kwargs,
        )

    def _generate_stub_code(self) -> str:
        """Generate stub code for functions without source."""
        return f"""
# WARNING: Original function source could not be captured.
# This component cannot be reloaded from JSON.
def {self._func_name}(*args, **kwargs):
    raise RuntimeError(
        "This FunctionComponent was created from a dynamically defined "
        "function and cannot be reloaded. Define the function in a module "
        "or use the @component decorator."
    )
"""

    def _parse_docstring_params(self) -> dict[str, str]:
        """Parse parameter descriptions from docstring (Google/Numpy style)."""
        param_docs: dict[str, str] = {}
        if not self._docstring:
            return param_docs

        lines = self._docstring.split("\n")
        in_args_section = False
        current_param: str | None = None

        for line in lines:
            stripped = line.strip()

            # Detect Args/Parameters section
            if stripped.lower() in ("args:", "arguments:", "parameters:"):
                in_args_section = True
                continue

            # Detect end of Args section
            if (
                in_args_section
                and stripped
                and any(
                    stripped.lower().startswith(s)
                    for s in ("returns:", "raises:", "yields:", "examples:", "note:", "notes:")
                )
            ):
                in_args_section = False
                continue

            if in_args_section:
                # Parse "param_name: description" or "param_name (type): description"
                if ":" in stripped and not line.startswith("    " * 2):
                    parts = stripped.split(":", 1)
                    param_part = parts[0].strip()
                    # Handle "param_name (type)" format
                    if "(" in param_part:
                        param_part = param_part.split("(")[0].strip()
                    current_param = param_part
                    param_docs[current_param] = parts[1].strip() if len(parts) > 1 else ""
                elif current_param and stripped:
                    # Continuation of previous param description
                    param_docs[current_param] += " " + stripped

        return param_docs

    def _build_inputs_from_signature(self) -> list[InputTypes]:
        """Build Langflow inputs from function signature."""
        inputs: list[InputTypes] = []

        for param_name, param in self._signature.parameters.items():
            # Skip self, cls, *args, **kwargs
            if param_name in ("self", "cls"):
                continue
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            # Get type annotation
            param_type = self._type_hints.get(param_name)

            # Warn if no type hint
            if param_type is None:
                warnings.warn(
                    f"Parameter '{param_name}' in function '{self._func_name}' has no type hint. "
                    f"Defaulting to str. Add type hints for better type safety.",
                    stacklevel=3,
                )
                param_type = str

            # Get description from docstring
            info = self._param_docs.get(param_name, "")

            # Determine if required (no default value)
            required = param.default is inspect.Parameter.empty

            # Get default value
            default = None if param.default is inspect.Parameter.empty else param.default

            # Parse type for special handling
            input_field = self._create_input_for_type(
                param_name=param_name,
                param_type=param_type,
                required=required,
                default=default,
                info=info,
            )
            inputs.append(input_field)

        return inputs

    def _create_input_for_type(
        self,
        param_name: str,
        param_type: type,
        *,
        required: bool,
        default: Any,
        info: str,
    ) -> InputTypes:
        """Create appropriate input field based on type annotation."""
        display_name = param_name.replace("_", " ").title()
        is_list = False
        options: list[str] | None = None
        input_config: InputConfig | None = None

        # Check for Annotated with InputConfig
        origin = get_origin(param_type)
        if origin is Annotated:
            args = get_args(param_type)
            param_type = args[0]
            for meta in args[1:]:
                if isinstance(meta, InputConfig):
                    input_config = meta
                    break
            # Recalculate origin after extracting inner type
            origin = get_origin(param_type)

        # Check for list type
        if origin in (list, List if "List" in dir() else list):  # noqa: F821
            is_list = True
            args = get_args(param_type)
            param_type = args[0] if args else str

        # Check for Optional
        if origin is Union:
            args = get_args(param_type)
            # Filter out NoneType
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) == 1:
                param_type = non_none_args[0]

        # Check for Literal (dropdown options)
        if get_origin(param_type) is Literal:
            options = list(get_args(param_type))
            param_type = str

        # Get input class
        input_class = TYPE_TO_INPUT_CLASS.get(param_type, MessageTextInput)

        # Use MultilineInput if configured
        if input_config and input_config.multiline:
            input_class = MultilineInput

        # Use DropdownInput if we have options
        if options:
            input_class = DropdownInput

        # Build input kwargs
        input_kwargs: dict[str, Any] = {
            "name": param_name,
            "display_name": display_name,
            "required": required,
            "info": info,
        }

        # Only set value if we have a default (not None for required params)
        if default is not None:
            input_kwargs["value"] = default
        elif not required:
            # For optional params with None default, use empty string for text inputs
            if input_class in (MessageTextInput, StrInput, MultilineInput):
                input_kwargs["value"] = ""
            else:
                input_kwargs["value"] = default

        if is_list:
            input_kwargs["is_list"] = True
            # For list inputs, default to empty list if no value
            if "value" not in input_kwargs:
                input_kwargs["value"] = []

        if options:
            input_kwargs["options"] = options

        # Apply InputConfig overrides
        if input_config:
            if input_config.display_name:
                input_kwargs["display_name"] = input_config.display_name
            if input_config.info:
                input_kwargs["info"] = input_config.info
            if input_config.placeholder:
                input_kwargs["placeholder"] = input_config.placeholder
            if input_config.advanced:
                input_kwargs["advanced"] = input_config.advanced
            if input_config.required is not None:
                input_kwargs["required"] = input_config.required

        return input_class(**input_kwargs)

    def _build_outputs_from_signature(self) -> list[Output]:
        """Build Langflow outputs from function return type."""
        return_type = self._type_hints.get("return")

        output = Output(
            display_name="Result",
            name="result",
            method="invoke_function",
        )

        if return_type:
            output_types = self._get_output_types(return_type)
            output.add_types(output_types)
        else:
            output.add_types(["Any"])

        return [output]

    def _get_output_types(self, return_type: type) -> list[str]:
        """Get output type strings from return type annotation."""
        # Handle dict -> Data
        if return_type is dict:
            return ["Data"]

        # Check for basic types
        if return_type in TYPE_TO_OUTPUT_TYPE:
            return [TYPE_TO_OUTPUT_TYPE[return_type]]

        # Handle typing generics
        origin = get_origin(return_type)
        if origin is Union:
            args = get_args(return_type)
            types = []
            for arg in args:
                if arg is not type(None):
                    types.extend(self._get_output_types(arg))
            return types

        if origin in (list, List if "List" in dir() else list):  # noqa: F821
            return ["list"]

        # Default
        if hasattr(return_type, "__name__"):
            return [return_type.__name__]

        return ["Any"]

    async def invoke_function(self) -> Any:
        """Execute the wrapped function with the input values."""
        # Gather input values
        kwargs: dict[str, Any] = {}
        for param_name in self._signature.parameters:
            if param_name in ("self", "cls"):
                continue
            param = self._signature.parameters[param_name]
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            # Get value from inputs or attributes
            value = getattr(self, param_name, None)

            # If value is None or empty string, use the default from function signature
            if (value is None or value == "") and param.default is not inspect.Parameter.empty:
                value = param.default

            # Type coercion: Message -> str
            expected_type = self._type_hints.get(param_name, str)
            # Handle Annotated
            if get_origin(expected_type) is Annotated:
                expected_type = get_args(expected_type)[0]
            # Handle Optional
            if get_origin(expected_type) is Union:
                args = get_args(expected_type)
                non_none = [a for a in args if a is not type(None)]
                if non_none:
                    expected_type = non_none[0]

            if isinstance(value, Message) and expected_type is str:
                value = value.text

            kwargs[param_name] = value

        # Call the function
        result = self._wrapped_function(**kwargs)

        # Handle async functions
        if inspect.iscoroutine(result):
            result = await result

        # Type coercion: dict -> Data
        if isinstance(result, dict):
            result = Data(data=result)

        return result

    @property
    def result(self):
        """Access the result output method for chaining.

        This allows patterns like:
            fc2.set(input=fc1.result)
        """
        return self.invoke_function

    def set_class_code(self) -> None:
        """Set the code for serialization.

        For FunctionComponent, we store just the function source code
        (without the @component decorator).
        The deserialization side will wrap it in FunctionComponent.
        """
        if self._code:
            return

        # Strip decorators and dedent the function source
        self._code = self._strip_decorators_and_dedent(self._function_source)

    def _strip_decorators_and_dedent(self, source: str) -> str:
        """Strip decorator lines and dedent the function source."""
        import textwrap

        lines = source.split("\n")
        func_lines = []
        in_decorator = False

        for line in lines:
            stripped = line.strip()
            # Skip decorator lines (including multi-line decorators)
            if stripped.startswith("@"):
                in_decorator = True
                continue
            # Once we hit def/async def, we're past decorators
            if in_decorator and stripped.startswith(("def ", "async def ")):
                in_decorator = False
            # Include non-decorator lines
            if not in_decorator or stripped.startswith(("def ", "async def ")):
                func_lines.append(line)
                in_decorator = False

        return textwrap.dedent("\n".join(func_lines)).strip()


def from_function(func: Callable[P, T], _id: str | None = None, **kwargs) -> FunctionComponent:
    """Create a FunctionComponent from a Python function.

    Args:
        func: The Python function to wrap
        _id: Optional component ID
        **kwargs: Additional arguments passed to FunctionComponent

    Returns:
        FunctionComponent: A component wrapping the function

    Example:
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        fc = from_function(greet, _id="greeter")
        fc.set(name="World")
    """
    return FunctionComponent(func, _id=_id, **kwargs)


@overload
def component(func: Callable[P, T]) -> FunctionComponent: ...


@overload
def component(
    *,
    display_name: str | None = None,
    description: str | None = None,
    _id: str | None = None,
) -> Callable[[Callable[P, T]], FunctionComponent]: ...


def component(
    func: Callable[P, T] | None = None,
    *,
    display_name: str | None = None,
    description: str | None = None,
    _id: str | None = None,
) -> FunctionComponent | Callable[[Callable[P, T]], FunctionComponent]:
    """Decorator to transform a Python function into a FunctionComponent.

    Can be used with or without arguments:

        @component
        def my_func(x: str) -> str:
            return x.upper()

        @component(display_name="My Custom Name")
        def my_func(x: str) -> str:
            return x.upper()

    Args:
        func: The function to wrap (when used without parentheses)
        display_name: Override the auto-generated display name
        description: Override the docstring description
        _id: Explicit component ID

    Returns:
        FunctionComponent or decorator function
    """

    def decorator(fn: Callable[P, T]) -> FunctionComponent:
        # Capture source code at decoration time
        try:
            source_code = inspect.getsource(fn)
        except (OSError, TypeError):
            source_code = None

        fc = FunctionComponent(
            func=fn,
            _id=_id,
            display_name=display_name,
            description=description,
            _source_code=source_code,
        )

        # Preserve function metadata
        functools.update_wrapper(fc, fn)

        return fc

    # Handle both @component and @component(...) syntax
    if func is not None:
        return decorator(func)
    return decorator
