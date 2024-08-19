from typing import Any

from langchain_core.tools import BaseTool, ToolException

from langflow.custom.custom_component.component import Component


class ComponentTool(BaseTool):
    name: str
    description: str
    component: "Component"

    def __init__(self, component: "Component") -> None:
        """Initialize the tool."""
        from langflow.io.schema import create_input_schema

        name = component.name or component.__class__.__name__
        description = component.description or ""
        args_schema = create_input_schema(component.inputs)
        super().__init__(name=name, description=description, args_schema=args_schema, component=component)
        # self.component = component

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
            results, _ = self.component(**kwargs)
            return results
        except Exception as e:
            raise ToolException(f"Error running {self.name}: {e}")


ComponentTool.update_forward_refs()
