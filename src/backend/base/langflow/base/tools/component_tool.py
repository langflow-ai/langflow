from typing import Any, Callable

from langchain_core.tools import BaseTool, ToolException


class ComponentTool(BaseTool):
    name: str
    description: str
    component_call_method: Callable | None = None

    def __init__(self, component) -> None:
        """Initialize the tool."""
        from langflow.io.schema import create_input_schema

        name = component.name or component.__class__.__name__
        description = component.description or ""
        args_schema = create_input_schema(component.inputs)
        super().__init__(name=name, description=description, args_schema=args_schema)
        self.component_call_method = component.__call__
        # self.component = component

    def __copy__(self):
        self.component_call_method = None
        return super().__copy__()

    @property
    def args(self) -> dict:
        schema = self.get_input_schema()
        return schema.schema()["properties"]

    def _run(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> dict:
        """Use the tool."""
        try:
            results, _ = self.component_call_method(**kwargs)
            return results
        except Exception as e:
            raise ToolException(f"Error running {self.name}: {e}")
