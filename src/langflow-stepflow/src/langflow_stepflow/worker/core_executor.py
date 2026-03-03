"""Core component executor for known Langflow components.

Executes known Langflow components by importing them directly by module path,
without needing to compile code from blob storage. This is more efficient for
components whose code hash matches a known version.
"""

import importlib
from typing import Any

from stepflow_py.worker import StepflowContext
from stepflow_py.worker.observability import get_tracer

from ..exceptions import ExecutionError
from .base_executor import BaseExecutor


class CoreExecutor(BaseExecutor):
    """Executes known Langflow components by importing them directly.

    This executor imports components by their module path and instantiates them
    directly, without needing to compile code from blob storage.
    """

    async def _instantiate_component(
        self,
        component_info: dict[str, Any],
    ) -> tuple[Any, str]:
        """Instantiate a component by importing its module.

        Args:
            component_info: Contains 'module_name' and 'class_name'

        Returns:
            Tuple of (component_instance, class_name)
        """
        module_name = component_info["module_name"]
        class_name = component_info["class_name"]
        tracer = get_tracer(__name__)

        with tracer.start_as_current_span(
            f"instantiate_component:{class_name}",
            attributes={"class_name": class_name, "module_name": module_name},
        ):
            # Import the module and get the class
            try:
                module = importlib.import_module(module_name)
                component_class = getattr(module, class_name)
            except ImportError as e:
                raise ExecutionError(
                    f"Failed to import module {module_name}: {e}"
                ) from e
            except AttributeError as e:
                raise ExecutionError(
                    f"Class {class_name} not found in module {module_name}: {e}"
                ) from e

            # Instantiate the component
            try:
                component_instance = component_class()
            except Exception as e:
                raise ExecutionError(f"Failed to instantiate {class_name}: {e}") from e

            return component_instance, class_name

    async def execute(
        self,
        component_path: str,
        input_data: dict[str, Any],
        context: StepflowContext,
    ) -> dict[str, Any]:
        """Execute a core Langflow component.

        Args:
            component_path: The component path suffix after /langflow/core/
                           (e.g., "lfx/components/docling/DoclingInlineComponent")
            input_data: Component input containing template, outputs, runtime inputs
            context: Stepflow context (may be needed for some operations)

        Returns:
            Component execution result
        """
        tracer = get_tracer(__name__)

        # Convert path to module path (slashes to dots)
        module_path = component_path.replace("/", ".")

        # Split into module and class name
        parts = module_path.rsplit(".", 1)
        if len(parts) != 2:
            raise ExecutionError(f"Invalid component path: {component_path}")

        module_name, class_name = parts

        with tracer.start_as_current_span(
            f"core_execute:{class_name}",
            attributes={
                "component_path": component_path,
                "module_name": module_name,
                "class_name": class_name,
            },
        ):
            # Extract execution parameters from input
            template = input_data.get("template", {})
            outputs = input_data.get("outputs", [])
            selected_output = input_data.get("selected_output")
            runtime_inputs = input_data.get("input", {})

            # Determine execution method
            execution_method = self._determine_execution_method(
                outputs, selected_output
            )
            if not execution_method:
                raise ExecutionError(f"No execution method found for {class_name}")

            # Instantiate the component
            component_instance, component_name = await self._instantiate_component(
                {"module_name": module_name, "class_name": class_name}
            )

            # Execute using shared base class method (returns serialized)
            result = await self._execute_component_instance(
                component_instance=component_instance,
                component_name=component_name,
                execution_method=execution_method,
                template=template,
                runtime_inputs=runtime_inputs,
            )

            return {"result": result}
