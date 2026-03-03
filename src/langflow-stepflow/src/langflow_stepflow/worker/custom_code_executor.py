"""Custom code executor for Langflow components.

Executes Langflow components by compiling their code from blob storage.
Uses a pre-compilation approach to eliminate context calls during execution.
"""

import inspect
from typing import Any

from stepflow_py.worker import StepflowContext
from stepflow_py.worker.observability import get_tracer

from ..exceptions import ExecutionError
from .base_executor import BaseExecutor
from .handlers import (
    BaseModelInputHandler,
    DataFrameConversionInputHandler,
    InputHandler,
    LangflowTypeInputHandler,
    StringCoercionInputHandler,
    ToolWrapperInputHandler,
)


class CustomCodeExecutor(BaseExecutor):
    """Executes Langflow custom code components by compiling code from blobs.

    This executor compiles component code from blob storage and instantiates
    the resulting classes. It uses a pre-compilation approach to eliminate
    context calls during execution.
    """

    def __init__(self):
        """Initialize custom code executor."""
        super().__init__()
        self.compiled_components: dict[str, Any] = {}

    def _get_input_handlers(self) -> list[InputHandler]:
        """Return input handlers for custom code execution.

        Includes all base handlers plus StringCoercion and DataFrame
        conversion needed for Langflow type transformations.
        """
        return [
            LangflowTypeInputHandler(),
            BaseModelInputHandler(),
            ToolWrapperInputHandler(),
            DataFrameConversionInputHandler(),
            StringCoercionInputHandler(),
        ]

    async def _instantiate_component(
        self,
        component_info: dict[str, Any],
    ) -> tuple[Any, str]:
        """Instantiate a component from pre-compiled component info.

        Args:
            component_info: Contains 'class' (the component class) and
                'component_type' (name for logging)

        Returns:
            Tuple of (component_instance, component_type)
        """
        component_class = component_info["class"]
        component_type = component_info.get("component_type", "Unknown")
        tracer = get_tracer(__name__)

        with tracer.start_as_current_span(
            f"instantiate_component:{component_type}",
            attributes={"component_type": component_type},
        ):
            try:
                component_instance = component_class()
            except Exception as e:
                raise ExecutionError(
                    f"Failed to instantiate {component_type}: {e}"
                ) from e

            return component_instance, component_type

    async def execute(
        self, input_data: dict[str, Any], context: StepflowContext
    ) -> dict[str, Any]:
        """Execute using the new pre-compilation approach.

        This method first pre-compiles all components, then executes without context.

        Args:
            input_data: Component input containing blob_id and runtime inputs
            context: Stepflow context for pre-compilation only

        Returns:
            Component execution result
        """

        # Step 1: Pre-compile all components from blobs
        await self._prepare_components(input_data, context)

        # Step 2: Execute using pre-compiled components (no context needed)
        return await self._execute_with_precompiled_components(input_data)

    async def _prepare_components(
        self, input_data: dict[str, Any], context: StepflowContext
    ) -> None:
        """Pre-compile all components from blob data to eliminate runtime context calls.

        This method fetches all blob data containing component source code and
        compiles them into executable component instances.

        Args:
            input_data: Component input containing blob IDs
            context: Stepflow context for blob operations
                (used only for pre-compilation)
        """
        blob_ids_to_compile = self._extract_blob_ids(input_data)
        tracer = get_tracer(__name__)

        for blob_id in blob_ids_to_compile:
            if blob_id not in self.compiled_components:
                try:
                    # Trace blob retrieval
                    with tracer.start_as_current_span(
                        "blob_get", attributes={"blob_id": blob_id}
                    ):
                        blob_data = await context.get_blob(blob_id)
                except Exception as e:
                    raise ExecutionError(
                        f"No component code found for blob {blob_id}. "
                        f"All components must have real Langflow code."
                    ) from e

                # Pass blob_id to compilation for better tracing
                compiled_component = await self._compile_component(blob_data, blob_id)
                self.compiled_components[blob_id] = compiled_component

    def _extract_blob_ids(self, input_data: dict[str, Any]) -> set[str]:
        """Extract all blob IDs that need to be compiled from input data."""
        blob_ids = set()

        # Main blob_id
        if "blob_id" in input_data:
            blob_ids.add(input_data["blob_id"])

        return blob_ids

    async def _compile_component(
        self, blob_data: dict[str, Any], blob_id: str | None = None
    ) -> dict[str, Any]:
        """Compile a component from enhanced blob data into an executable definition."""
        component_type = blob_data.get("component_type", "Unknown")
        code = blob_data.get("code", "")
        template = blob_data.get("template", {})
        outputs = blob_data.get("outputs", [])
        selected_output = blob_data.get("selected_output")

        # Extract enhanced metadata from Phase 1 improvements
        base_classes = blob_data.get("base_classes", [])
        display_name = blob_data.get("display_name", component_type)
        description = blob_data.get("description", "")
        documentation = blob_data.get("documentation", "")
        metadata = blob_data.get("metadata", {})
        field_order = blob_data.get("field_order", [])
        icon = blob_data.get("icon", "")

        # Trace the compilation process
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span(
            f"compile_component:{component_type}",
            attributes={
                "component_type": component_type,
                "display_name": display_name,
                **({"blob_id": blob_id} if blob_id else {}),
            },
        ):
            # Patch PlaceholderGraph for lfx compatibility
            self._patch_placeholder_graph()

            if not code or not code.strip():
                raise ExecutionError(
                    f"No code found for component {component_type}. "
                    f"All executable components should have custom code."
                )

            try:
                from lfx.custom.eval import eval_custom_component_code

                # Trace the actual code evaluation
                with tracer.start_as_current_span(
                    "eval_custom_component_code",
                    attributes={
                        "component_type": component_type,
                        "code_length": len(code),
                    },
                ):
                    component_class = eval_custom_component_code(code)
            except Exception as e:
                raise ExecutionError(
                    f"Failed to evaluate component code for {component_type}: {e}"
                ) from e

            if not component_class:
                raise ExecutionError(
                    f"eval_custom_component_code returned None for {component_type}"
                )

            # Determine execution method with enhanced logic
            execution_method = self._determine_execution_method(
                outputs, selected_output
            )
            if not execution_method:
                raise ExecutionError(f"No execution method found for {component_type}")

            return {
                "class": component_class,
                "template": template,
                "execution_method": execution_method,
                "component_type": component_type,
                # Enhanced metadata for better component execution
                "base_classes": base_classes,
                "display_name": display_name,
                "description": description,
                "documentation": documentation,
                "metadata": metadata,
                "field_order": field_order,
                "icon": icon,
            }

    async def _execute_with_precompiled_components(
        self, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute using pre-compiled components - no context needed."""
        return await self._execute_single_component_precompiled(input_data)

    async def _execute_single_component_precompiled(
        self, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a single component using pre-compiled data."""
        blob_id = input_data.get("blob_id")
        if not blob_id:
            raise ExecutionError("No blob_id provided")

        if blob_id not in self.compiled_components:
            raise ExecutionError(f"Component {blob_id} not pre-compiled")

        compiled_component = self.compiled_components[blob_id]
        runtime_inputs = input_data.get("input", {})

        # Execute the component (returns serialized output)
        result = await self._execute_compiled_component(
            compiled_component, runtime_inputs
        )

        return {"result": result}

    async def _execute_compiled_component(
        self, compiled_component: dict[str, Any], runtime_inputs: dict[str, Any]
    ) -> Any:
        """Execute a pre-compiled component instance.

        Returns serialized output (output handlers handle serialization).
        """
        component_class = compiled_component["class"]
        template = compiled_component["template"]
        execution_method = compiled_component["execution_method"]
        component_type = compiled_component["component_type"]
        display_name = compiled_component.get("display_name", component_type)

        tracer = get_tracer(__name__)

        # Create component instance with tracing
        with tracer.start_as_current_span(
            f"instantiate_component:{component_type}",
            attributes={
                "component_type": component_type,
                "display_name": display_name,
            },
        ):
            try:
                component_instance = component_class()
            except Exception as e:
                raise ExecutionError(
                    f"Failed to instantiate {component_type}: {e}"
                ) from e

        # Prepare raw parameters
        raw_params = await self._prepare_component_parameters(template, runtime_inputs)

        # Handler pipeline: input transform → execute → output transform
        async with self._handler_pipeline(raw_params, template) as (
            component_parameters,
            output_handlers,
        ):
            # Apply component input defaults before configuring
            component_parameters = self._apply_component_input_defaults(
                component_instance, component_parameters
            )
            session_id = component_parameters.get("session_id", "default_session")
            component_instance._session_id = session_id
            self._setup_graph_context(component_instance, session_id)

            resolved_parameters = component_parameters

            # Configure component
            if hasattr(component_instance, "set_attributes"):
                component_instance._parameters = resolved_parameters
                component_instance.set_attributes(resolved_parameters)

            # Execute component method with tracing
            if not hasattr(component_instance, execution_method):
                available = [
                    m for m in dir(component_instance) if not m.startswith("_")
                ]
                raise ExecutionError(
                    f"Method {execution_method} not found in "
                    f"{component_type}. Available: {available}"
                )

            method = getattr(component_instance, execution_method)

            with tracer.start_as_current_span(
                f"execute_method:{execution_method}",
                attributes={
                    "component_type": component_type,
                    "display_name": display_name,
                    "execution_method": execution_method,
                },
            ):
                try:
                    if inspect.iscoroutinefunction(method):
                        result = await method()
                    else:
                        result = await self._execute_sync_method_safely(
                            method, component_type
                        )

                    # Handle OpenSearch client objects
                    try:
                        from opensearchpy import OpenSearch

                        if isinstance(result, OpenSearch):
                            return {
                                "status": "success",
                                "type": "OpenSearchVectorStore",
                            }
                    except ImportError:
                        pass

                    # Serialize output through handlers
                    return await self._apply_output_handlers(result, output_handlers)
                except Exception as e:
                    raise ExecutionError(
                        f"Failed to execute {execution_method}: {e}"
                    ) from e

    def _patch_placeholder_graph(self) -> None:
        """Patch PlaceholderGraph to add vertices attribute for lfx compatibility.

        lfx 0.1.12+ Agent components access graph.vertices, but PlaceholderGraph
        doesn't have this attribute by default. This patch adds it.
        """
        from typing import NamedTuple

        class EnhancedPlaceholderGraph(NamedTuple):
            """Enhanced PlaceholderGraph with vertices for lfx compatibility."""

            flow_id: str | None = None
            flow_name: str | None = None
            user_id: str | None = None
            session_id: str | None = None
            context: dict | None = None
            vertices: list = []

        try:
            from lfx.custom.custom_component import (
                component as lfx_component_module,
            )

            lfx_component_module.PlaceholderGraph = EnhancedPlaceholderGraph  # type: ignore[assignment,misc]
        except ImportError:
            pass

    def _apply_component_input_defaults(
        self, component_instance: Any, component_parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply component input defaults for missing parameters.

        Args:
            component_instance: Instantiated component
            component_parameters: Current parameters

        Returns:
            Parameters with defaults applied from component inputs definition
        """
        if hasattr(component_instance, "inputs"):
            for input_field in component_instance.inputs:
                if hasattr(input_field, "name") and hasattr(input_field, "value"):
                    param_name = input_field.name
                    default_value = input_field.value

                    if (
                        param_name not in component_parameters
                        and default_value is not None
                        and default_value != ""
                    ):
                        component_parameters[param_name] = default_value

        return component_parameters

    def _determine_execution_method(
        self, outputs: list, selected_output: str | None
    ) -> str | None:
        """Determine execution method from outputs metadata."""
        if selected_output:
            for output in outputs:
                if output.get("name") == selected_output:
                    method = output.get("method")
                    if isinstance(method, str) and method:
                        return method

        # Fallback to first output's method
        if outputs:
            method = outputs[0].get("method")
            if isinstance(method, str) and method:
                return method

        return None

    async def _execute_sync_method_safely(self, method, component_type: str):
        """Execute sync method safely in async context."""
        return method()
