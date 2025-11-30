"""Tests for FunctionComponent - wrapping Python functions as Langflow components."""

from __future__ import annotations

import warnings
from typing import Annotated, Literal

import pytest
from lfx.base.functions import FunctionComponent, InputConfig, component, from_function
from lfx.schema.data import Data
from lfx.schema.message import Message


class TestFunctionComponentCreation:
    """Tests for FunctionComponent instantiation and signature introspection."""

    def test_simple_function_single_param(self):
        """Function with one typed parameter creates one input."""

        def greet(name: str) -> str:
            return f"Hello, {name}!"

        fc = FunctionComponent(greet)

        assert len(fc.inputs) == 1
        assert fc.inputs[0].name == "name"
        assert fc.inputs[0].display_name == "Name"
        assert fc.inputs[0].required is True
        # For required text inputs without defaults, value is empty string (not None)
        assert fc.inputs[0].value == ""

    def test_function_multiple_params(self):
        """Function with multiple parameters creates multiple inputs."""

        def calculate(a: int, b: int, c: float = 1.0) -> float:
            return (a + b) * c

        fc = FunctionComponent(calculate)

        assert len(fc.inputs) == 3
        assert fc.inputs[0].name == "a"
        assert fc.inputs[0].required is True
        assert fc.inputs[1].name == "b"
        assert fc.inputs[1].required is True
        assert fc.inputs[2].name == "c"
        assert fc.inputs[2].required is False
        assert fc.inputs[2].value == 1.0

    def test_function_with_default_values(self):
        """Default values are captured in input.value."""

        def configure(
            name: str = "default",
            count: int = 10,
            enabled: bool = True,  # noqa: FBT001, FBT002
        ) -> str:
            return f"{name}: {count}, {enabled}"

        fc = FunctionComponent(configure)

        assert fc.inputs[0].value == "default"
        assert fc.inputs[1].value == 10
        assert fc.inputs[2].value is True
        assert all(inp.required is False for inp in fc.inputs)

    def test_function_without_type_hints_warns(self):
        """Untyped parameters default to str with a warning."""

        def process(data):
            return str(data)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            fc = FunctionComponent(process)

            # Check that a warning was raised
            assert len(w) == 1
            assert "type hint" in str(w[0].message).lower()

        assert len(fc.inputs) == 1
        assert fc.inputs[0].name == "data"

    def test_function_with_list_type(self):
        """list[X] type creates is_list=True input."""

        def process_items(items: list[str]) -> str:
            return ", ".join(items)

        fc = FunctionComponent(process_items)

        assert fc.inputs[0].is_list is True

    def test_function_with_literal_type(self):
        """Literal type creates dropdown with options."""

        def set_mode(mode: Literal["fast", "slow", "balanced"]) -> str:
            return mode

        fc = FunctionComponent(set_mode)

        assert fc.inputs[0].options == ["fast", "slow", "balanced"]

    def test_function_with_optional_type(self):
        """Optional[X] is handled correctly."""

        def maybe_process(data: str | None = None) -> str:
            return data or "empty"

        fc = FunctionComponent(maybe_process)

        assert fc.inputs[0].required is False
        # For optional text inputs with None default, we use empty string
        assert fc.inputs[0].value == ""

    def test_skips_self_and_cls(self):
        """Self and cls parameters are skipped."""

        class MyClass:
            def method(self, data: str) -> str:
                return data

        fc = FunctionComponent(MyClass().method)
        # Should only have 'data', not 'self'
        assert len(fc.inputs) == 1
        assert fc.inputs[0].name == "data"

    def test_skips_args_kwargs(self):
        """*args and **kwargs are skipped."""

        def flexible(required: str, *args, **kwargs) -> str:  # noqa: ARG001
            return required

        fc = FunctionComponent(flexible)

        assert len(fc.inputs) == 1
        assert fc.inputs[0].name == "required"


class TestFunctionComponentDocstring:
    """Tests for docstring parsing."""

    def test_google_style_docstring(self):
        """Google-style docstrings are parsed for parameter info."""

        def process(data: str, count: int) -> str:
            """Process the data multiple times.

            Args:
                data: The input data to process
                count: Number of times to process

            Returns:
                Processed result
            """
            return data * count

        fc = FunctionComponent(process)

        assert fc.inputs[0].info == "The input data to process"
        assert fc.inputs[1].info == "Number of times to process"
        # Description is stored with underscore prefix by Component base class
        assert fc._description == "Process the data multiple times."

    def test_no_docstring(self):
        """Functions without docstrings have empty info."""

        def simple(x: int) -> int:
            return x * 2

        fc = FunctionComponent(simple)

        assert fc.inputs[0].info == ""
        assert fc._description in (None, "")


class TestFunctionComponentOutput:
    """Tests for output generation from return types."""

    def test_simple_return_type(self):
        """Simple return types create appropriate output."""

        def get_text() -> str:
            return "hello"

        fc = FunctionComponent(get_text)

        assert len(fc.outputs) == 1
        assert fc.outputs[0].name == "result"
        assert fc.outputs[0].method == "invoke_function"

    def test_no_return_type(self):
        """Functions without return type get Message output."""

        def mystery():
            return 42

        fc = FunctionComponent(mystery)

        # Default to Message when no return type specified
        assert "Message" in fc.outputs[0].types

    def test_dict_return_type_maps_to_data(self):
        """Functions returning dict have output type Data."""

        def get_data() -> dict:
            return {"key": "value"}

        fc = FunctionComponent(get_data)

        assert "Data" in fc.outputs[0].types


class TestFunctionComponentNaming:
    """Tests for component naming and display."""

    def test_display_name_from_function_name(self):
        """Display name is derived from function name."""

        def process_user_input(data: str) -> str:
            return data

        fc = FunctionComponent(process_user_input)

        # Display name is stored with underscore prefix by Component base class
        assert fc._display_name == "Process User Input"

    def test_custom_id(self):
        """Custom _id is respected."""

        def simple(x: str) -> str:
            return x

        fc = FunctionComponent(simple, _id="my_custom_id")

        assert fc._id == "my_custom_id"

    def test_auto_generated_id_includes_function_name(self):
        """ID is auto-generated from function name with suffix."""

        def my_func(x: str) -> str:
            return x

        fc = FunctionComponent(my_func)

        assert fc._id is not None
        assert fc._id.startswith("my_func_")


class TestFromFunctionFactory:
    """Tests for from_function factory function."""

    def test_from_function_creates_component(self):
        """from_function creates a FunctionComponent."""

        def add(a: int, b: int) -> int:
            return a + b

        fc = from_function(add)

        assert isinstance(fc, FunctionComponent)
        assert len(fc.inputs) == 2

    def test_from_function_with_id(self):
        """from_function accepts _id parameter."""

        def add(a: int, b: int) -> int:
            return a + b

        fc = from_function(add, _id="adder")

        assert fc._id == "adder"


class TestComponentDecorator:
    """Tests for @component decorator."""

    def test_decorator_creates_function_component(self):
        """@component decorator creates FunctionComponent."""

        @component
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        assert isinstance(greet, FunctionComponent)
        assert len(greet.inputs) == 1

    def test_decorator_with_parameters(self):
        """@component decorator accepts parameters."""

        @component(display_name="Custom Greeter", _id="greeter")
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        # Display name is stored with underscore prefix by Component base class
        assert greet._display_name == "Custom Greeter"
        assert greet._id == "greeter"

    def test_decorator_preserves_function_name(self):
        """Decorated function preserves __name__."""

        @component
        def my_special_function(x: str) -> str:
            return x

        assert my_special_function.__name__ == "my_special_function"


class TestInputConfig:
    """Tests for InputConfig with Annotated types."""

    def test_input_config_placeholder(self):
        """InputConfig placeholder is used."""

        @component
        def process(name: Annotated[str, InputConfig(placeholder="Enter name")]) -> str:
            return name

        # Access via _inputs dict (Component maps inputs there)
        assert process._inputs["name"].placeholder == "Enter name"

    def test_input_config_advanced(self):
        """InputConfig advanced flag is used."""

        @component
        def process(
            debug: Annotated[bool, InputConfig(advanced=True)] = False,  # noqa: FBT002
        ) -> str:
            return str(debug)

        assert process._inputs["debug"].advanced is True

    def test_input_config_multiline(self):
        """InputConfig multiline flag is used."""
        from lfx.inputs.inputs import MultilineInput

        @component
        def process(text: Annotated[str, InputConfig(multiline=True)]) -> str:
            return text

        # When multiline=True, the input class becomes MultilineInput
        assert isinstance(process._inputs["text"], MultilineInput)
        assert process._inputs["text"].multiline is True


class TestTypeCoercion:
    """Tests for type coercion (Message->str, dict->Data)."""

    @pytest.mark.asyncio
    async def test_message_to_str_coercion(self):
        """Message is coerced to str when function expects str."""

        def process(text: str) -> str:
            return text.upper()

        fc = FunctionComponent(process)
        fc.set(text=Message(text="hello"))

        result = await fc.invoke_function()
        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_dict_to_data_coercion_on_output(self):
        """Dict return value is wrapped in Data."""

        def get_info() -> dict:
            return {"key": "value"}

        fc = FunctionComponent(get_info)

        result = await fc.invoke_function()
        assert isinstance(result, Data)
        assert result.data["key"] == "value"

    @pytest.mark.asyncio
    async def test_str_passthrough(self):
        """Str values pass through unchanged."""

        def echo(text: str) -> str:
            return text

        fc = FunctionComponent(echo)
        fc.set(text="hello")

        result = await fc.invoke_function()
        assert result == "hello"


class TestFunctionComponentExecution:
    """Tests for executing FunctionComponents."""

    @pytest.mark.asyncio
    async def test_simple_execution(self):
        """FunctionComponent executes and produces output."""

        def double(x: int) -> int:
            return x * 2

        fc = FunctionComponent(double)
        fc.set(x=5)

        result = await fc.invoke_function()
        assert result == 10

    @pytest.mark.asyncio
    async def test_async_function_execution(self):
        """Async functions are awaited properly."""

        async def async_process(data: str) -> str:
            return data.upper()

        fc = FunctionComponent(async_process)
        fc.set(data="hello")

        result = await fc.invoke_function()
        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_function_with_exception(self):
        """Exceptions in functions bubble up."""

        def risky(x: int) -> int:
            if x < 0:
                msg = "x must be non-negative"
                raise ValueError(msg)
            return x

        fc = FunctionComponent(risky)
        fc.set(x=-1)

        with pytest.raises(ValueError, match="x must be non-negative"):
            await fc.invoke_function()


class TestFunctionComponentResultProperty:
    """Tests for the result property for chaining."""

    def test_result_property_returns_method(self):
        """fc.result returns the invoke_function method."""

        def add(a: int, b: int) -> int:
            return a + b

        fc = FunctionComponent(add)

        # result should be callable
        assert callable(fc.result)
        # result should be the bound invoke_function method
        assert fc.result == fc.invoke_function


class TestSourceCodeCapture:
    """Tests for source code capture for persistence."""

    def test_source_code_captured(self):
        """Function source code is captured."""

        def my_function(x: str) -> str:
            return x.upper()

        fc = FunctionComponent(my_function)

        assert hasattr(fc, "_function_source")
        assert "def my_function" in fc._function_source
        assert "return x.upper()" in fc._function_source

    def test_decorated_function_source_captured(self):
        """Decorated function source is captured."""

        @component
        def my_decorated_func(x: str) -> str:
            return x.lower()

        assert hasattr(my_decorated_func, "_function_source")
        assert "def my_decorated_func" in my_decorated_func._function_source


class TestAutoWrappingWithComponentSet:
    """Tests for auto-wrapping plain functions when using Component.set()."""

    @pytest.mark.asyncio
    async def test_plain_function_auto_wrapped_on_set(self):
        """Plain function passed to Component.set() is auto-wrapped in FunctionComponent."""
        from lfx.custom.custom_component.component import Component
        from lfx.inputs.inputs import MessageTextInput
        from lfx.template.field.base import Output

        # Create a target component that accepts input
        class TargetComponent(Component):
            inputs = [MessageTextInput(name="text", display_name="Text")]
            outputs = [Output(display_name="Result", name="result", method="process")]

            def process(self) -> str:
                return self.text

        def source_function() -> str:
            return "hello from function"

        target = TargetComponent()
        target.set(text=source_function)

        # The function should be wrapped and connected
        assert len(target._components) == 1
        assert isinstance(target._components[0], FunctionComponent)

    @pytest.mark.asyncio
    async def test_plain_function_with_args_auto_wrapped(self):
        """Plain function with parameters is auto-wrapped and its result used."""
        from lfx.custom.custom_component.component import Component
        from lfx.inputs.inputs import MessageTextInput
        from lfx.template.field.base import Output

        class TargetComponent(Component):
            inputs = [MessageTextInput(name="text", display_name="Text")]
            outputs = [Output(display_name="Result", name="result", method="process")]

            def process(self) -> str:
                return self.text

        def uppercase(text: str) -> str:
            return text.upper()

        source = FunctionComponent(uppercase)
        source.set(text="hello")

        target = TargetComponent()
        target.set(text=source.result)

        # Manual FunctionComponent connection should work
        assert len(target._components) == 1
        assert target._components[0] is source


class TestFunctionComponentConnection:
    """Tests for connecting FunctionComponents to other components."""

    def test_connect_to_chat_input(self):
        """FunctionComponent can receive from ChatInput."""
        from lfx.components.input_output import ChatInput

        def process(text: str) -> str:
            return text.upper()

        chat_input = ChatInput(_id="chat_input_1")
        fc = FunctionComponent(process, _id="processor")
        fc.set(text=chat_input.message_response)

        assert len(fc._components) == 1
        assert fc._components[0] is chat_input
        assert len(fc._edges) == 1

        # Verify edge data structure
        edge = fc._edges[0]
        assert edge["source"] == "chat_input_1"
        assert edge["target"] == "processor"
        assert "sourceHandle" in edge["data"]
        assert "targetHandle" in edge["data"]

    def test_connect_to_another_function_component(self):
        """FunctionComponents can chain together."""

        @component
        def step1(text: str) -> str:
            return f"[{text}]"

        @component
        def step2(text: str) -> str:
            return f"<{text}>"

        step1.set(text="hello")
        step2.set(text=step1.result)

        assert len(step2._components) == 1
        assert step2._components[0] is step1
        assert len(step2._edges) == 1

    def test_connect_to_chat_output(self):
        """FunctionComponent output can connect to ChatOutput."""
        from lfx.components.input_output import ChatOutput

        @component
        def transform(text: str) -> str:
            return text.lower()

        chat_output = ChatOutput(_id="chat_output_1")
        transform.set(text="HELLO")
        chat_output.set(input_value=transform.result)

        assert len(chat_output._components) == 1
        assert chat_output._components[0] is transform
        assert len(chat_output._edges) == 1

    def test_edge_has_correct_output_types(self):
        """Edge data includes correct output types for FunctionComponent."""

        @component
        def process(text: str) -> str:
            return text

        @component
        def consumer(text: str) -> str:
            return text

        consumer.set(text=process.result)

        edge = consumer._edges[0]
        source_handle = edge["data"]["sourceHandle"]

        # FunctionComponent with str return should have Message output type
        assert "Message" in source_handle["output_types"]

    def test_edge_has_correct_input_types(self):
        """Edge data includes correct input types for target."""

        @component
        def producer() -> str:
            return "hello"

        @component
        def consumer(text: str) -> str:
            return text

        consumer.set(text=producer.result)

        edge = consumer._edges[0]
        target_handle = edge["data"]["targetHandle"]

        # str input should accept Message type
        assert "Message" in target_handle["inputTypes"]
        assert target_handle["fieldName"] == "text"


class TestFunctionComponentInvalidConnections:
    """Tests for invalid type connections - types that don't match."""

    def test_dict_output_to_str_input_type_mismatch(self):
        """Graph creation with dict->str type mismatch raises ValueError."""
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.graph import Graph

        @component
        def dict_producer(text: str) -> dict:
            return {"key": text}

        @component
        def str_consumer(text: str) -> str:
            return text

        chat_input = ChatInput()
        chat_output = ChatOutput()

        dict_producer.set(text=chat_input.message_response)
        str_consumer.set(text=dict_producer.result)
        chat_output.set(input_value=str_consumer.result)

        # Check edge data shows type mismatch
        edge = str_consumer._edges[0]
        source_handle = edge["data"]["sourceHandle"]
        target_handle = edge["data"]["targetHandle"]

        # dict output maps to Data type
        assert "Data" in source_handle["output_types"]
        # str input accepts Message type
        assert "Message" in target_handle["inputTypes"]

        # Types should not overlap - this is an invalid connection
        output_types = set(source_handle["output_types"])
        input_types = set(target_handle["inputTypes"])
        assert not output_types.intersection(input_types), "Output and input types should not overlap"

        # Graph creation should raise ValueError due to type mismatch
        with pytest.raises(ValueError, match="invalid handles"):
            Graph(start=chat_input, end=chat_output)

    def test_int_output_to_str_input_type_mismatch(self):
        """Graph creation with int->str type mismatch raises ValueError."""
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.graph import Graph

        @component
        def int_producer(text: str) -> int:
            return len(text)

        @component
        def str_consumer(text: str) -> str:
            return text

        chat_input = ChatInput()
        chat_output = ChatOutput()

        int_producer.set(text=chat_input.message_response)
        str_consumer.set(text=int_producer.result)
        chat_output.set(input_value=str_consumer.result)

        edge = str_consumer._edges[0]
        source_handle = edge["data"]["sourceHandle"]
        target_handle = edge["data"]["targetHandle"]

        # int output type shows as "int"
        assert "int" in source_handle["output_types"]
        # str input accepts Message type
        assert "Message" in target_handle["inputTypes"]

        # Types should NOT overlap - int and Message are different types
        output_types = set(source_handle["output_types"]) - {"Any"}
        input_types = set(target_handle["inputTypes"]) - {"Any"}
        assert not output_types.intersection(input_types), "int and Message should not overlap"

        # Graph creation should raise ValueError due to type mismatch
        with pytest.raises(ValueError, match="invalid handles"):
            Graph(start=chat_input, end=chat_output)

    def test_list_output_to_single_input_type_mismatch(self):
        """Graph creation with list->single type raises ValueError."""
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.graph import Graph

        @component
        def list_producer(text: str) -> list[str]:
            return text.split()

        @component
        def single_consumer(text: str) -> str:
            return text

        chat_input = ChatInput()
        chat_output = ChatOutput()

        list_producer.set(text=chat_input.message_response)
        single_consumer.set(text=list_producer.result)
        chat_output.set(input_value=single_consumer.result)

        edge = single_consumer._edges[0]
        source_handle = edge["data"]["sourceHandle"]
        target_handle = edge["data"]["targetHandle"]

        # Verify edge data is captured
        assert "output_types" in source_handle
        assert "inputTypes" in target_handle

        # Graph creation should raise ValueError due to type mismatch
        with pytest.raises(ValueError, match="invalid handles"):
            Graph(start=chat_input, end=chat_output)

    def test_data_output_to_message_input_type_mismatch(self):
        """Graph creation with Data->Message type mismatch raises ValueError."""
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.graph import Graph
        from lfx.schema.data import Data

        @component
        def data_producer(text: str) -> Data:
            return Data(data={"text": text})

        @component
        def message_consumer(text: str) -> str:
            return text

        chat_input = ChatInput()
        chat_output = ChatOutput()

        data_producer.set(text=chat_input.message_response)
        message_consumer.set(text=data_producer.result)
        chat_output.set(input_value=message_consumer.result)

        edge = message_consumer._edges[0]
        source_handle = edge["data"]["sourceHandle"]
        target_handle = edge["data"]["targetHandle"]

        # Data output type
        assert "Data" in source_handle["output_types"]
        # str input expects Message
        assert "Message" in target_handle["inputTypes"]

        # Types don't overlap
        output_types = set(source_handle["output_types"])
        input_types = set(target_handle["inputTypes"])
        assert not output_types.intersection(input_types), "Data and Message should not overlap"

        # Graph creation should raise ValueError due to type mismatch
        with pytest.raises(ValueError, match="invalid handles"):
            Graph(start=chat_input, end=chat_output)

    def test_multiple_invalid_connections_in_graph(self):
        """Graph with multiple type mismatches raises ValueError."""
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.graph import Graph

        @component
        def dict_output(text: str) -> dict:
            return {"a": text}

        @component
        def consumer(text: str, value: str) -> str:
            return f"{text}:{value}"

        @component
        def another_dict(text: str) -> dict:
            return {"b": text}

        chat_input = ChatInput()
        chat_output = ChatOutput()

        dict_output.set(text=chat_input.message_response)
        another_dict.set(text=chat_input.message_response)
        consumer.set(text=dict_output.result, value=another_dict.result)
        chat_output.set(input_value=consumer.result)

        # Should have 2 edges on consumer
        assert len(consumer._edges) == 2

        # Both edges should show type mismatch (Data -> Message)
        for edge in consumer._edges:
            source_handle = edge["data"]["sourceHandle"]
            target_handle = edge["data"]["targetHandle"]

            output_types = set(source_handle["output_types"])
            input_types = set(target_handle["inputTypes"])

            # Verify type mismatch
            assert "Data" in output_types
            assert "Message" in input_types
            assert not output_types.intersection(input_types)

        # Graph creation should raise ValueError due to type mismatch
        with pytest.raises(ValueError, match="invalid handles"):
            Graph(start=chat_input, end=chat_output)

    def test_valid_connection_in_graph(self):
        """Graph with valid str->str connection has overlapping types."""
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.graph import Graph

        @component
        def str_producer(text: str) -> str:
            return text.upper()

        @component
        def str_consumer(text: str) -> str:
            return text.lower()

        chat_input = ChatInput()
        chat_output = ChatOutput()

        str_producer.set(text=chat_input.message_response)
        str_consumer.set(text=str_producer.result)
        chat_output.set(input_value=str_consumer.result)

        edge = str_consumer._edges[0]
        source_handle = edge["data"]["sourceHandle"]
        target_handle = edge["data"]["targetHandle"]

        # Both should have Message
        output_types = set(source_handle["output_types"])
        input_types = set(target_handle["inputTypes"])

        # Types should overlap - this is a valid connection
        assert output_types.intersection(input_types), "Valid connection should have overlapping types"
        assert "Message" in output_types.intersection(input_types)

        # Graph creation should work for valid connections
        graph = Graph(start=chat_input, end=chat_output)
        assert len(graph.vertices) == 4
