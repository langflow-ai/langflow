from langflow.schema.dotdict import dotdict
from loguru import logger

from langflow.components.inputs.chat import ChatInput
from langflow.components.outputs.chat import ChatOutput
from langflow.custom import Component
from langflow.graph.graph.base import Graph
from langflow.graph.state.model import create_state_model
from langflow.graph.vertex.base import Vertex
from langflow.helpers.flow import get_flow_inputs
from langflow.inputs.inputs import MessageInput
from langflow.io import (
    BoolInput,
    CodeInput,
    DataFrameInput,
    DataInput,
    DefaultPromptField,
    DictInput,
    DropdownInput,
    FileInput,
    FloatInput,
    HandleInput,
    IntInput,
    LinkInput,
    MessageInput,
    MessageTextInput,
    MultilineInput,
    MultilineSecretInput,
    MultiselectInput,
    NestedDictInput,
    PromptInput,
    SecretStrInput,
    SliderInput,
    StrInput,
    TableInput,
    Output,
)
from langflow.schema.message import Message
from langflow.template.field.base import Input


class FlowOrchestratorComponent(Component):
    display_name = "Flow Orchestrator"
    description = "A component to orchestrate flows."
    name = "FlowOrchestrator"
    icon = "workflow"
    verbose = True
    inputs = [
        DropdownInput(
            name="flow_name_selected",
            display_name="Flow Name",
            info="The name of the flow to run.",
            options=[],
            value=None,
            refresh_button=True,
        ),
    ]
    outputs = [
        Output(display_name="Run Outputs", name="run_outputs", method="run_flow_selected"),
    ]

    async def get_list_of_flows(self) -> list[str]:
        flow_datas = await self.alist_flows()
        return [flow_data.data["name"] for flow_data in flow_datas]

    async def get_flow(self, flow_name: str):
        flow_datas = await self.alist_flows()
        for flow_data in flow_datas:
            if flow_data.data["name"] == flow_name:
                return flow_data
        return None

    async def get_graph_details(self, flow_name: str) -> tuple[Graph, list[Vertex]]:
        try:
            flow_data = await self.get_flow(flow_name)
            graph = Graph.from_payload(flow_data.data["data"])
            # Get all inputs from the graph
            inputs = get_flow_inputs(graph)
        except Exception as e:
            logger.exception(f"Error retrieving graph details for flow '{flow_name}': {e}")
            msg = f"Could not retrieve graph details for flow '{flow_name}'."
            raise ValueError(msg) from e
        return graph, inputs

    async def run_flow_selected(self) -> Message:
        graph, inputs = await self.get_graph_details(self.flow_name_selected)

        chat_input = ChatInput().set(input_value="hello")

        chat_output = ChatOutput().set(input_value=chat_input.message_response)
        output_model = create_state_model("ChatOutput", output=chat_output.message_response)()

        # Build the graph
        graph = Graph(chat_input, chat_output)
        async for result in graph.async_start(max_iterations=10):
            if self.verbose:
                logger.info(result)
        # logger.debug(new_fields)
        data = output_model.output
        print(data)
        self.status = data
        return data

    async def add_inputs_to_build_config(self, inputs: list[Vertex], build_config: dotdict):
        new_fields: list[Input] = []
        for vertex in inputs:
            field_order = vertex.data.get("node", {}).get("field_order", [])
            print(f"field_order: {field_order}")
            template = vertex.data.get("node", {}).get("template", {})
            print(f"template: {template}")
            for field_name in field_order:
                print(f"field_name: {field_name}")
                fields_dict = template.get(field_name, {})
                print(f"fields_dict: {fields_dict}")
                fields_dict["tool_mode"] = bool(
                    fields_dict.get("advanced", False)
                    or fields_dict.get("tool_mode", True)
                    or fields_dict.get("required", False)
                )
                field_input_type = fields_dict.get("_input_type", "str")
                print(f"field_input_type: {field_input_type}")
                field_class = globals().get(field_input_type)
                print(f"field_class: {field_class}")
                if field_class is not None:
                    field = field_class(**{k: v for k, v in fields_dict.items() if k in field_class.__fields__})  # Filter to prevent extra inputs
                else:
                    msg = f"Unsupported field input type: {field_input_type}"
                    raise ValueError(msg)
                new_fields.append(field)
        print(f"new_fields: {new_fields}")
        logger.debug(new_fields)
        for field in new_fields:
            build_config[field.name] = field.to_dict()
        return build_config

    async def update_build_config(
        self, build_config: dotdict, field_value: str, field_name: str | None = None
    ) -> dotdict:
        flow_list = await self.get_list_of_flows()
        if field_name == "flow_name_selected" and len(flow_list) > len(build_config["flow_name_selected"]["options"]):
            build_config["flow_name_selected"]["options"] = await self.get_list_of_flows()
        if field_value is not None and field_value != "" and field_name == "flow_name_selected":
            try:
                graph, inputs = await self.get_graph_details(field_value)
            except Exception as e:
                logger.exception(f"Error retrieving graph details for flow '{field_value}': {e}")
                msg = f"Could not retrieve graph details for flow '{field_value}'."
                raise ValueError(msg) from e

            try:
                build_config = await self.add_inputs_to_build_config(inputs, build_config)
            except Exception as e:
                logger.exception(f"Error adding inputs to build config for flow '{field_value}': {e}")
                msg = f"Could not add inputs to build config for flow '{field_value}'."
                raise ValueError(msg) from e
