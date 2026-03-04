"""Base executor class with shared functionality for Langflow component execution."""

import inspect
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from stepflow_py.worker.observability import get_tracer

from ..exceptions import ExecutionError
from .handlers import (
    BaseModelInputHandler,
    BaseModelOutputHandler,
    DataFrameOutputHandler,
    InputHandler,
    LangflowTypeInputHandler,
    LangflowTypeOutputHandler,
    OutputHandler,
    ToolWrapperInputHandler,
)


class BaseExecutor(ABC):
    """Abstract base class for Langflow component executors.

    Provides shared functionality for both core and custom code executors:
    - Execution method determination
    - Component input defaults application
    - Input/output handler dispatch
    - Common component execution flow

    Subclasses must implement `_instantiate_component` to define how components
    are loaded and instantiated.
    """

    @abstractmethod
    async def _instantiate_component(
        self,
        component_info: dict[str, Any],
    ) -> tuple[Any, str]:
        """Instantiate a component from component info.

        This is the only method that differs between executors:
        - CoreExecutor: imports module and instantiates class
        - CustomCodeExecutor: compiles code from blob and instantiates class

        Args:
            component_info: Information needed to instantiate the component.
                For CoreExecutor: contains module_name, class_name
                For CustomCodeExecutor: contains component class and metadata

        Returns:
            Tuple of (component_instance, component_name) for execution
        """
        pass

    def _get_input_handlers(self) -> list[InputHandler]:
        """Return the input handlers to apply during parameter preparation.

        Base implementation returns handlers for type deserialization.
        Subclasses may override to add additional handlers (e.g.,
        StringCoercion, DataFrameConversion).
        """
        return [
            LangflowTypeInputHandler(),
            BaseModelInputHandler(),
            ToolWrapperInputHandler(),
        ]

    def _get_output_handlers(self) -> list[OutputHandler]:
        """Return the output handlers to apply during result serialization.

        Handlers are tried in order during the recursive tree walk;
        the first match wins for each value.
        """
        return [
            LangflowTypeOutputHandler(),
            DataFrameOutputHandler(),
            BaseModelOutputHandler(),
        ]

    @asynccontextmanager
    async def _handler_pipeline(
        self,
        parameters: dict[str, Any],
        template: dict[str, Any],
    ) -> AsyncIterator[tuple[dict[str, Any], list[OutputHandler]]]:
        """Enter handler contexts, apply input handlers, yield for execution.

        Uses ``AsyncExitStack`` to keep all input handler contexts alive
        across input preparation, component execution, and output processing.

        Yields:
            Tuple of (prepared_parameters, output_handlers).
        """
        input_handlers = self._get_input_handlers()
        output_handlers = self._get_output_handlers()

        async with AsyncExitStack() as stack:
            result = dict(parameters)

            for handler in input_handlers:
                matched: dict[str, tuple[Any, dict[str, Any]]] = {}
                for key, value in result.items():
                    field_def = template.get(key, {})
                    if not isinstance(field_def, dict):
                        field_def = {}
                    if handler.matches(template_field=field_def, value=value):
                        matched[key] = (value, field_def)

                if not matched:
                    continue

                ctx = await stack.enter_async_context(handler.activate())
                updates = await handler.prepare(matched, ctx)
                result.update(updates)

            yield result, output_handlers

    async def _apply_output_handlers(self, value: Any, handlers: list[OutputHandler]) -> Any:
        """Recursively walk a value tree, applying output handlers.

        For each value, tries handlers in order (first match wins).
        Dicts and lists without a handler match are recursed into.
        Primitives pass through unchanged.
        """
        for handler in handlers:
            if handler.matches(value=value):
                return await handler.process(value)

        if isinstance(value, list):
            return [await self._apply_output_handlers(item, handlers) for item in value]
        if isinstance(value, dict):
            return {k: await self._apply_output_handlers(v, handlers) for k, v in value.items()}
        if isinstance(value, str | int | float | bool | type(None)):
            return value

        raise ValueError(
            f"Cannot serialize object of type {type(value).__name__}. "
            "Only BaseModel objects and simple types are supported."
        )

    async def _execute_component_instance(
        self,
        component_instance: Any,
        component_name: str,
        execution_method: str,
        template: dict[str, Any],
        runtime_inputs: dict[str, Any],
    ) -> Any:
        """Execute a component instance with the given parameters.

        This is the shared execution flow used by both executors after
        the component has been instantiated. Returns serialized output.

        Args:
            component_instance: Instantiated component object
            component_name: Name for logging/tracing
            execution_method: Method name to call on the component
            template: Template containing field definitions
            runtime_inputs: Runtime input values

        Returns:
            Serialized component execution result
        """
        tracer = get_tracer(__name__)

        # Prepare raw parameters from template and runtime inputs
        raw_params = await self._prepare_component_parameters(template, runtime_inputs)

        # Handler pipeline: input transform → execute → output transform
        async with self._handler_pipeline(raw_params, template) as (
            component_parameters,
            output_handlers,
        ):
            # Apply component input defaults
            component_parameters = self._apply_component_input_defaults(component_instance, component_parameters)

            # Set session_id and graph context
            session_id = component_parameters.get("session_id", "default_session")
            component_instance._session_id = session_id
            self._setup_graph_context(component_instance, session_id)

            # Configure component with parameters
            if hasattr(component_instance, "set_attributes"):
                component_instance._parameters = component_parameters
                component_instance.set_attributes(component_parameters)

            # Verify execution method exists
            if not hasattr(component_instance, execution_method):
                available = [m for m in dir(component_instance) if not m.startswith("_")]
                raise ExecutionError(f"Method {execution_method} not found in {component_name}. Available: {available}")

            method = getattr(component_instance, execution_method)

            # Execute the method with tracing
            with tracer.start_as_current_span(
                f"execute_method:{execution_method}",
                attributes={
                    "component_name": component_name,
                    "execution_method": execution_method,
                },
            ):
                try:
                    if inspect.iscoroutinefunction(method):
                        result = await method()
                    else:
                        result = method()
                except Exception as e:
                    raise ExecutionError(
                        f"Error executing {execution_method} on "
                        f"{component_name} "
                        f"({type(component_instance).__name__}): {e}"
                    ) from e

            # Serialize output through handlers
            return await self._apply_output_handlers(result, output_handlers)

    async def _prepare_component_parameters(
        self, template: dict[str, Any], runtime_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Prepare component parameters from template and runtime inputs.

        Extracts defaults from template fields and merges with raw runtime
        inputs. No deserialization is performed here — input handlers
        handle all type conversion.

        Args:
            template: Template containing field definitions
            runtime_inputs: Runtime input values

        Returns:
            Merged parameters dictionary (raw values, not deserialized)
        """
        parameters: dict[str, Any] = {}

        # Extract default values from template
        for key, field in template.items():
            if isinstance(field, dict) and "value" in field:
                # Skip handle inputs with empty values (connected steps
                # provide them)
                input_types = field.get("input_types", [])
                value = field["value"]

                if input_types and (value == "" or value is None):
                    continue

                parameters[key] = value
            elif isinstance(field, dict):
                # Field without value - skip
                pass
            else:
                # Direct value
                parameters[key] = field

        # Override with raw runtime inputs (no deserialization — handlers do it)
        parameters.update(runtime_inputs)

        return parameters

    def _determine_execution_method(self, outputs: list[dict[str, Any]], selected_output: str | None) -> str | None:
        """Determine which method to call based on outputs configuration.

        Args:
            outputs: List of output definitions from the component
            selected_output: The name of the selected output (if any)

        Returns:
            The method name to call, or None if not found
        """
        if not outputs:
            return None

        # If selected_output is provided, find the matching output method
        if selected_output:
            for output in outputs:
                if output.get("name") == selected_output:
                    method = output.get("method")
                    if isinstance(method, str) and method:
                        return method

        # Default to first output's method
        method = outputs[0].get("method")
        if isinstance(method, str) and method:
            return method

        return None

    def _apply_component_input_defaults(self, component_instance: Any, parameters: dict[str, Any]) -> dict[str, Any]:
        """Apply default values from component's input definitions.

        Args:
            component_instance: Instantiated component with inputs attribute
            parameters: Current component parameters

        Returns:
            Parameters with defaults applied for missing values
        """
        if not hasattr(component_instance, "inputs"):
            return parameters

        inputs = component_instance.inputs
        if not inputs:
            return parameters

        result = dict(parameters)

        for input_def in inputs:
            field_name = getattr(input_def, "name", None)
            if not field_name:
                continue

            # Only set default if not already in parameters
            if field_name not in result:
                default_value = getattr(input_def, "value", None)
                if default_value is not None and default_value != "":
                    result[field_name] = default_value

        return result

    def _setup_graph_context(self, component_instance: Any, session_id: str) -> None:
        """Set up graph context for components that need it.

        Some components (like Agent) access self.graph.session_id and
        self.graph.vertices. This creates a minimal graph context object.

        Args:
            component_instance: Component instance to configure
            session_id: Session ID for the graph context
        """

        class GraphContext:
            def __init__(self, session_id: str):
                self.session_id = session_id
                self.vertices: list[Any] = []
                self.flow_id = None

        # Use __dict__ to set graph even if it's a read-only property
        component_instance.__dict__["graph"] = GraphContext(session_id)
