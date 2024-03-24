from typing import Any, Callable, List, Optional, Text, Tuple

from langchain_core.tools import StructuredTool
from loguru import logger
from pydantic.v1 import BaseModel, Field, create_model

from langflow import CustomComponent
from langflow.field_typing import Tool
from langflow.graph.graph.base import Graph
from langflow.schema import Record
from langflow.schema.dotdict import dotdict


class FlowToolComponent(CustomComponent):
    display_name = "Flow as Tool"
    description = "Construct a Tool from a function that runs the loaded Flow."
    field_order = ["flow_name", "name", "description", "return_direct"]

    def generate_function_for_flow(self, inputs: List[tuple[str, str, str]], flow_id: str) -> Callable:
        # Prepare function arguments with type hints and default values
        args = [f'{input_[1].lower().replace(" ", "_")}: str = ""' for input_ in inputs]
        # Maintain original argument names for constructing the tweaks dictionary
        original_arg_names = [input_[1] for input_ in inputs]
        # Prepare a Pythonic, valid function argument string
        func_args = ", ".join(args)
        # Map original argument names to their corresponding Pythonic variable names in the function
        arg_mappings = ", ".join(
            [
                f'"{original_name}": {name}'
                for original_name, name in zip(original_arg_names, [arg.split(":")[0] for arg in args])
            ]
        )

        func_body = f"""
async def dynamic_flow_function({func_args}):
    tweaks = {{ {arg_mappings} }}
    from langflow.helpers.flow import run_flow  # Ensure this import exists or adjust accordingly
    return await run_flow(
        tweaks={{key: {{'input_value': value}} for key, value in tweaks.items()}},
        flow_id="{flow_id}",
    )
"""
        local_scope = {}
        exec(func_body, globals(), local_scope)
        return local_scope["dynamic_flow_function"]

    async def build_function_and_schema(self, flow_name: str) -> Tuple[Callable, BaseModel]:
        flow_record = self.get_flow(flow_name)
        if not flow_record:
            raise ValueError(f"Flow {flow_name} not found.")
        flow_id = flow_record.id  # Assuming the flow record has an 'id' attribute
        graph = Graph.from_payload(flow_record.data["data"])
        inputs = self.get_flow_inputs(graph)
        dynamic_flow_function = self.generate_function_for_flow(inputs, flow_id)
        schema = self.build_schema_from_inputs(flow_name, inputs)
        return dynamic_flow_function, schema

    def get_flow_names(self) -> List[str]:
        flow_records = self.list_flows()
        return [flow_record.data["name"] for flow_record in flow_records]

    def get_flow(self, flow_name: str) -> Optional[Text]:
        """
        Retrieves a flow by its name.

        Args:
            flow_name (str): The name of the flow to retrieve.

        Returns:
            Optional[Text]: The flow record if found, None otherwise.
        """
        flow_records = self.list_flows()
        for flow_record in flow_records:
            if flow_record.data["name"] == flow_name:
                return flow_record
        return None

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        logger.debug(f"Updating build config with field value {field_value} and field name {field_name}")
        if field_name == "flow_name":
            build_config["flow_name"]["options"] = self.get_flow_names()

        return build_config

    def get_flow_inputs(self, graph: Graph) -> List[Record]:
        """
        Retrieves the flow inputs from the given graph.

        Args:
            graph (Graph): The graph object representing the flow.

        Returns:
            List[Record]: A list of input records, where each record contains the ID, name, and description of the input vertex.
        """
        inputs = []
        for vertex in graph.vertices:
            if vertex.is_input:
                inputs.append((vertex.id, vertex.display_name, vertex.description))
        logger.debug(inputs)
        return inputs

    def build_schema_from_inputs(self, name: str, inputs: List[tuple[str, str, str]]) -> BaseModel:
        """
        Builds a schema from the given inputs.

        Args:
            name (str): The name of the schema.
            inputs (List[tuple[str, str, str]]): A list of tuples representing the inputs.
                Each tuple contains three elements: the input name, the input type, and the input description.

        Returns:
            BaseModel: The schema model.

        """
        fields = {}
        for input_ in inputs:
            fields[input_[1]] = (str, Field(default="", description=input_[2]))
        return create_model(name, **fields)

    def build_config(self):
        return {
            "flow_name": {
                "display_name": "Flow Name",
                "info": "The name of the flow to run.",
                "options": [],
                "real_time_refresh": True,
                "refresh_button": True,
            },
            "name": {
                "display_name": "Name",
                "description": "The name of the tool.",
            },
            "description": {
                "display_name": "Description",
                "description": "The description of the tool.",
            },
            "return_direct": {
                "display_name": "Return Direct",
                "description": "Return the result directly from the Tool.",
                "advanced": True,
            },
        }

    async def build(self, flow_name: str, name: str, description: str, return_direct: bool = False) -> Tool:
        dynamic_flow_function, schema = await self.build_function_and_schema(flow_name)
        tool = StructuredTool.from_function(
            coroutine=dynamic_flow_function,
            name=name,
            description=description,
            return_direct=return_direct,
            args_schema=schema,
        )
        description_repr = repr(tool.description).strip("'")
        args_str = "\n".join([f"- {arg_name}: {arg_data['description']}" for arg_name, arg_data in tool.args.items()])
        self.status = f"{description_repr}\nArguments:\n{args_str}"
        return tool
