import json
from pathlib import Path
from typing import Any

from aiofile import async_open
from loguru import logger

from langflow.base.flow_processing.utils import build_data_from_result_data
from langflow.base.tools.constants import TOOLS_METADATA_INPUT_NAME
from langflow.base.tools.flow_tool import FlowTool
from langflow.custom import Component
from langflow.custom.custom_component.component import _get_component_toolkit
from langflow.field_typing import Tool
from langflow.graph.graph.base import Graph
from langflow.graph.vertex.base import Vertex
from langflow.helpers.flow import get_flow_inputs, run_flow
from langflow.io import BoolInput, DropdownInput, FileInput, MessageInput, Output
from langflow.schema import Data, dotdict

default_keys = [
    "code",
    "_type",
    "flow_name_selected",
    "session_id",
    "flow_json",
    "return_direct",
]
FLOW_INPUTS: list[dotdict] = []


class RunFlowComponent(Component):
    display_name = "Run Flow"
    description = "Generates a Component from a Flow, with all of its inputs, and "
    name = "RunFlow"
    beta: bool = True
    icon = "Workflow"
    # async def __init__(self, *args: Any, **kwargs: Any):
    #     await super().__init__(*args, **kwargs)
    #     self.flow_data= await self.alist_flows()

    inputs = [
        DropdownInput(
            name="flow_name_selected",
            display_name="Flow Name",
            info="The name of the flow to run.",
            options=[],
            real_time_refresh=True,
            refresh_button=True,
            value=None,
        ),
        MessageInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID to run the flow in.",
            value="",
            advanced=True,
        ),
        FileInput(
            name="flow_json",
            display_name="Flow JSON",
            info="The flow JSON to run.",
            value="",
            file_types=["json"],
            advanced=True,
            refresh_button=True,
        ),
        BoolInput(
            name="return_direct",
            display_name="Return Direct",
            info="Return the result directly from the Tool.",
            advanced=True,
        ),
    ]

    outputs = [Output(name="flow_outputs", display_name="Flow Outputs", method="run_flow_with_tweaks")]

    async def get_flow_names(self) -> list[str]:
        # TODO: get flfow ID with flow name
        flow_data = await self.alist_flows()
        return [flow_data.data["name"] for flow_data in flow_data]

    async def get_flow(self, flow_name_selected: str) -> Data | None:
        # get flow from flow id
        flow_datas = await self.alist_flows()
        for flow_data in flow_datas:
            if flow_data.data["name"] == flow_name_selected:
                return flow_data
        return None

    async def get_graph(self, flow_name_selected: str | None = None) -> Graph:
        if self.flow_json and isinstance(self.flow_json, str | Path):
            try:
                if self.flow_json:
                    # resolved_path = self.resolve_path(self.flow_json)
                    file_path = Path(self.flow_json)
                    async with async_open(file_path, encoding="utf-8") as f:
                        content = await f.read()
                        flow_graph = json.loads(content)
                        return Graph.from_payload(flow_graph["data"])
            except Exception as e:
                msg = "Error loading flow from JSON"
                raise ValueError(msg) from e
        if flow_name_selected:
            flow_data = await self.get_flow(flow_name_selected)
            if flow_data:
                return Graph.from_payload(flow_data.data["data"])
            msg = "Flow not found"
            raise ValueError(msg)
        return None

    def get_new_fields_from_graph(self, graph: Graph) -> list[dotdict]:
        inputs = get_flow_inputs(graph)
        return self.get_new_fields(inputs)

    def update_build_config_from_graph(self, build_config: dotdict, graph: Graph):
        try:
            # Get all inputs from the graph
            new_fields = self.get_new_fields_from_graph(graph)
            # tool_mode_inputs = [field for field in new_fields if field.get("tool_mode") is True]
            old_fields = self.get_old_fields(build_config, new_fields)
            self.delete_fields(build_config, old_fields)
            build_config = self.add_new_fields(build_config, new_fields)

        except Exception as e:
            msg = "Error updating build config from graph"
            logger.exception(msg)
            raise RuntimeError(msg) from e

    async def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "flow_name_selected":
            build_config["flow_name_selected"]["options"] = await self.get_flow_names()
            missing_keys = [key for key in default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)
            if field_value is not None:
                try:
                    graph = await self.get_graph(field_value)
                    build_config = self.update_build_config_from_graph(build_config, graph)
                except Exception as e:
                    msg = f"Error building graph for flow {field_value}"
                    logger.exception(msg)
                    raise RuntimeError(msg) from e
        if field_name == "flow_json" and field_value:
            try:
                graph = await self.get_graph()
                build_config = self.update_build_config_from_graph(build_config, graph)
            except Exception as e:
                msg = f"Error building graph for flow {field_value}"
                logger.exception(msg)
                raise RuntimeError(msg) from e

        return build_config

    def get_new_fields(self, inputs_vertex: list[Vertex]) -> list[dotdict]:
        new_fields: list[dotdict] = []

        for vertex in inputs_vertex:
            field_template = vertex.data.get("node", {}).get("template", {})
            field_order = vertex.data.get("node", {}).get("field_order", [])
            if field_order and field_template:
                new_vertex_inputs = [
                    {
                        **field_template[input_name],
                        "display_name": vertex.display_name + " - " + field_template[input_name]["display_name"],
                        "name": vertex.id + "|" + input_name,
                        "tool_mode": not (field_template[input_name].get("advanced", False)),
                    }
                    for input_name in field_order
                ]
                new_fields += new_vertex_inputs
        return new_fields

    def add_new_fields(self, build_config: dotdict, new_fields: list[dotdict]) -> dotdict:
        """Add new fields to the build_config."""
        for field in new_fields:
            build_config[field["name"]] = field
        return build_config

    def delete_fields(self, build_config: dotdict, fields: dict | list[str]) -> None:
        """Delete specified fields from build_config."""
        if isinstance(fields, dict):
            fields = list(fields.keys())
        for field in fields:
            build_config.pop(field, None)

    def get_old_fields(self, build_config: dotdict, new_fields: list[str]) -> list[str]:
        """Get fields that are in build_config but not in new_fields."""
        return [
            field
            for field in build_config
            if field not in [new_field["name"] for new_field in new_fields] + default_keys
        ]

    async def run_flow_with_tweaks(self) -> list[Data]:
        tweaks: dict = {}

        flow_name_selected = self._attributes.get("flow_name_selected")

        for field in self._attributes:
            if field not in default_keys and "|" in field:
                [node, name] = field.split("|")
                if node not in tweaks:
                    tweaks[node] = {}
                tweaks[node][name] = self._attributes[field]
        print("IN GENERATE RESULTS")
        # tweaks= {"ChatInput-xNZ0a": {"input_value": "add 1+1"}}
        print(f"tweaks______________: {tweaks}")
        run_outputs = await run_flow(
            inputs=None,
            output_type="all",
            flow_id=None,
            flow_name=flow_name_selected,
            tweaks=tweaks,
            user_id=str(self.user_id),
            # run_id=self.graph.run_id,
            session_id=self.graph.session_id or self.session_id,
        )
        print(f"run_outputs______________: {run_outputs}")
        # import pdb; pdb.set_trace()
        data: list[Data] = []
        if not run_outputs:
            return data
        run_output = run_outputs[0]

        if run_output is not None:
            for output in run_output.outputs:
                if output:
                    data.extend(build_data_from_result_data(output))
        return Data(data={"value":"All good"})

    async def get_required_data(self, flow_name_selected):
        self.flow_data = await self.alist_flows()
        for flow_data in self.flow_data:
            if flow_data.data["name"] == flow_name_selected:
                graph = Graph.from_payload(flow_data.data["data"])
                new_fields = self.get_new_fields_from_graph(graph)
                new_fields = self.update_input_types(new_fields)
                return [field for field in new_fields if field.get("tool_mode") is True]
        return None

    def update_input_types(self, fields: list[dotdict]) -> list[dotdict]:
        for field in fields:
            if isinstance(field, dict):
                if field.get("input_types") is None:
                    field["input_types"] = []
            elif hasattr(field, "input_types") and field.input_types is None:
                field.input_types = []
        return fields


    async def to_toolkit(self) -> list[Tool]:
        component_toolkit = _get_component_toolkit()
        tool_mode_inputs = await self.get_required_data(self.flow_name_selected)
        # # convert list of dicts to list of dotdicts
        tool_mode_inputs = [dotdict(field) for field in tool_mode_inputs]
        tools = component_toolkit(component=self).get_tools(
            callbacks=self.get_langchain_callbacks(), flow_mode_inputs=tool_mode_inputs
        )
        if hasattr(self, TOOLS_METADATA_INPUT_NAME):
            tools = component_toolkit(component=self, metadata=self.tools_metadata).update_tools_metadata(tools=tools)
        return tools

    # async def to_toolkit(self) -> list[Tool]:
    #     FlowTool.model_rebuild()
    #     component_toolkit = _get_component_toolkit()
    #     if "flow_name_selected" not in self._attributes or not self._attributes["flow_name_selected"]:
    #         msg = "Flow name is required"
    #         raise ValueError(msg)
    #     flow_name = self._attributes["flow_name_selected"]
    #     flow_data = await self.get_flow(flow_name)
    #     if not flow_data:
    #         msg = "Flow not found."
    #         raise ValueError(msg)
    #     graph = Graph.from_payload(
    #         flow_data.data["data"],
    #         user_id=str(self.user_id),
    #     )
    #     # import pdb; pdb.set_trace()
    #     #TODO: Sert run id, inverstigate why self.graph has no run id
    #     #  if self.graph has an attribute run_id, set it
    #     if hasattr(self.graph, "run_id"):
    #         graph.set_run_id(self.graph.run_id)
    #     else:
    #         graph.set_run_id(None)
    #     # try:
    #     #     graph.set_run_id(self.graph.run_id)
    #     # except Exception:  # noqa: BLE001   
    #     #     logger.opt(exception=True).warning("Failed to set run_id")
    #     inputs = get_flow_inputs(graph)

    #     tool_name = f"{flow_name}_tool"
    #     tool_description = flow_data.description if flow_data.description else f"Tool for {flow_name}"
    #     tool = FlowTool(
    #         name=tool_name,
    #         description=tool_description,
    #         graph=graph,
    #         return_direct=self.return_direct,
    #         inputs=inputs,
    #         flow_id=str(flow_data.id),
    #         user_id=str(self.user_id),
    #         session_id=self.graph.session_id if hasattr(self, "graph") else None,
    #     )
    #     description_repr = repr(tool.description).strip("'")
    #     args_str = "\n".join([f"- {arg_name}: {arg_data['description']}" for arg_name, arg_data in tool.args.items()])
    #     self.status = f"{description_repr}\nArguments:\n{args_str}"
    #     if hasattr(self, TOOLS_METADATA_INPUT_NAME):
    #         return component_toolkit(component=self, metadata=self.tools_metadata).update_tools_metadata(tools=[tool])
    #     return [tool]
