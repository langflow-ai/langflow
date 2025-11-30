"""FunctionComponent - Transform Python functions into Langflow components.

This module provides a way to create Langflow components from plain Python functions
without the boilerplate of class-based components. Type annotations are automatically
converted to inputs and outputs.

Quick Start
-----------

The simplest way to create a component is with the ``@component`` decorator::

    from lfx.base.functions import component

    @component
    def greet(name: str) -> str:
        '''Say hello to someone.'''
        return f"Hello, {name}!"

    # Use it
    greet.set(name="World")
    result = await greet.invoke_function()  # "Hello, World!"

Customizing Components
----------------------

Use decorator arguments to customize the component appearance::

    @component(display_name="Text Greeter", description="A friendly greeter")
    def greet(name: str) -> str:
        return f"Hello, {name}!"

Use ``InputConfig`` to customize individual inputs. It can be used as a default value::

    from lfx.base.functions import component, InputConfig

    @component
    def format_text(
        text: str,
        uppercase: bool = InputConfig(
            default=False,
            display_name="Convert to Uppercase",
            info="When enabled, converts all text to uppercase"
        )
    ) -> str:
        '''Format text with optional transformations.'''
        return text.upper() if uppercase else text

Or with ``Annotated`` for type-safe configuration::

    from typing import Annotated

    @component
    def process(
        text: Annotated[str, InputConfig(multiline=True, placeholder="Enter text...")]
    ) -> str:
        return text.strip()

Supported Types
---------------

The following Python types are automatically mapped to Langflow inputs:

- ``str`` -> MessageTextInput
- ``int`` -> IntInput
- ``float`` -> FloatInput
- ``bool`` -> BoolInput
- ``Message`` -> MessageInput
- ``Literal["a", "b"]`` -> DropdownInput with options
- ``list[T]`` -> List input of type T
- ``Optional[T]`` -> Optional input of type T

Async Functions
---------------

Async functions are fully supported::

    @component
    async def fetch_data(url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.text()

Chaining Components
-------------------

Use ``.result`` to connect component outputs to inputs::

    @component
    def step1(text: str) -> str:
        return text.upper()

    @component
    def step2(text: str) -> str:
        return f"[{text}]"

    # Connect step1's output to step2's input
    step1.set(text="hello")
    step2.set(text=step1.result)

    # Build and run the graph
    graph = Graph(step1, step2)
    await graph.arun(inputs=[])

Alternative: from_function
--------------------------

For programmatic creation without decorators::

    def my_func(x: int) -> int:
        return x * 2

    fc = from_function(my_func, _id="doubler")
    fc.set(x=21)
"""

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
    SecretStrInput,
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
    """Configuration for customizing a function parameter's input field.

    Can be used in two ways:

    1. As a default value (includes the actual default)::

        @component
        def greet(
            name: str = InputConfig(default="World", display_name="Name")
        ) -> str:
            return f"Hello, {name}!"

    2. With ``typing.Annotated`` (type-safe, default specified separately)::

        from typing import Annotated

        @component
        def greet(
            name: Annotated[str, InputConfig(display_name="Name")] = "World"
        ) -> str:
            return f"Hello, {name}!"

    Attributes:
        default: Default value for the input (only when used as default value syntax).
        display_name: Human-readable label shown in the UI.
        info: Help text/tooltip displayed next to the input.
        placeholder: Placeholder text shown when input is empty.
        advanced: If True, input is hidden under "Advanced" section.
        multiline: If True, uses a multiline text input (for str type).
        password: If True, masks the input (for sensitive data).
        show: If False, hides the input from the UI.
        required: Override whether the input is required (default: inferred from presence of default).
        input_types: List of accepted input types (e.g., ["str", "Message"]).
        options: List of dropdown options (alternative to using Literal type).
        combobox: If True with options, allows typing custom values.

    Examples:
        Advanced input with tooltip::

            @component
            def process(
                debug: bool = InputConfig(
                    default=False,
                    advanced=True,
                    info="Enable debug logging"
                )
            ) -> str:
                ...

        Password input::

            @component
            def authenticate(
                api_key: str = InputConfig(password=True, display_name="API Key")
            ) -> str:
                ...

        Dropdown with options::

            @component
            def select_model(
                model: str = InputConfig(
                    default="gpt-4",
                    options=["gpt-4", "gpt-3.5-turbo", "claude-3"]
                )
            ) -> str:
                ...
    """

    default: Any = field(default=None)
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

        # Set the name attribute for frontend styling/identification
        # This is separate from display_name and is used as the component type
        self.name = display_name
        # Set display_name for get_template_config (ATTR_FUNC_MAPPING lookup)
        self.display_name = display_name

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
        """Parse parameter descriptions from docstring.

        Supports multiple formats:
        1. Google/Numpy style with Args: section
        2. Simple format: "param_name: description" anywhere in docstring
        """
        param_docs: dict[str, str] = {}
        if not self._docstring:
            return param_docs

        lines = self._docstring.split("\n")
        in_args_section = False
        current_param: str | None = None

        # Get parameter names from signature to validate simple format
        param_names = set(self._signature.parameters.keys()) - {"self", "cls"}

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
            elif not in_args_section and ":" in stripped:
                # Simple format: "param_name: description" without Args: section
                # Only match if the word before : is a known parameter name
                parts = stripped.split(":", 1)
                potential_param = parts[0].strip()
                if potential_param in param_names and len(parts) > 1:
                    param_docs[potential_param] = parts[1].strip()

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

            # Get default value - check if it's an InputConfig used as default
            raw_default = param.default
            input_config_from_default: InputConfig | None = None

            if isinstance(raw_default, InputConfig):
                # InputConfig used as default value: `param: str = InputConfig(default="value")`
                input_config_from_default = raw_default
                default = raw_default.default
                required = default is None and raw_default.required is not False
            elif raw_default is inspect.Parameter.empty:
                default = None
                required = True
            else:
                default = raw_default
                required = False

            # Parse type for special handling
            input_field = self._create_input_for_type(
                param_name=param_name,
                param_type=param_type,
                required=required,
                default=default,
                info=info,
                input_config_from_default=input_config_from_default,
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
        input_config_from_default: InputConfig | None = None,
    ) -> InputTypes:
        """Create appropriate input field based on type annotation."""
        display_name = param_name.replace("_", " ").title()
        is_list = False
        options: list[str] | None = None
        input_config: InputConfig | None = input_config_from_default

        # Check for Annotated with InputConfig (takes precedence over default-based config)
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

        # Use SecretStrInput if password is configured
        if input_config and input_config.password:
            input_class = SecretStrInput

        # Use MultilineInput if configured
        if input_config and input_config.multiline:
            input_class = MultilineInput

        # Use DropdownInput if we have options (from Literal or InputConfig)
        if input_config and input_config.options:
            options = input_config.options
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
            if not input_config.show:
                input_kwargs["show"] = False

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
            # Default to Message when no return type specified
            output.add_types(["Message"])

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

        # For custom types, use their class name
        if hasattr(return_type, "__name__"):
            return [return_type.__name__]

        # Fallback to Message for unknown types
        return ["Message"]

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

            # Get value from inputs first, fall back to attributes
            # Note: We must use _inputs directly because getattr may return
            # component attributes (like 'name' for display_name) instead of input values
            value = self._inputs[param_name].value if param_name in self._inputs else getattr(self, param_name, None)

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
