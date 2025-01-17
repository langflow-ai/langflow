from typing import Any

from loguru import logger

from langflow.base.flow_processing.utils import build_data_from_result_data
from langflow.custom import Component
from langflow.graph.graph.base import Graph
from langflow.graph.vertex.base import Vertex
from langflow.helpers.flow import get_flow_inputs
from langflow.io import DropdownInput, Output
from langflow.schema import Data, dotdict


class SubFlowComponent(Component):
    display_name = "Sub Flow"
    description = "Generates a Component from a Flow, with all of its inputs, and "
    name = "SubFlow"
    beta: bool = True
    icon = "Workflow"

    async def get_flow_names(self) -> list[str]:
        flow_data = await self.alist_flows()
        return [flow_data.data["name"] for flow_data in flow_data]

    async def get_flow(self, flow_name: str) -> Data | None:
        flow_datas = await self.alist_flows()
        for flow_data in flow_datas:
            if flow_data.data["name"] == flow_name:
                return flow_data
        return None

    async def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "flow_name":
            build_config["flow_name"]["options"] = await self.get_flow_names()

        for key in list(build_config.keys()):
            if key not in [x.name for x in self.inputs] + ["code", "_type", "get_final_results_only"]:
                del build_config[key]
        if field_value is not None and field_name == "flow_name":
            try:
                flow_data = await self.get_flow(field_value)
            except Exception:  # noqa: BLE001
                logger.exception(f"Error getting flow {field_value}")
            else:
                if not flow_data:
                    msg = f"Flow {field_value} not found."
                    logger.error(msg)
                else:
                    try:
                        graph = Graph.from_payload(flow_data.data["data"])
                        # Get all inputs from the graph
                        inputs = get_flow_inputs(graph)
                        # Add inputs to the build config
                        build_config = self.add_inputs_to_build_config(inputs, build_config)
                    except Exception:  # noqa: BLE001
                        logger.exception(f"Error building graph for flow {field_value}")

        return build_config

    def add_inputs_to_build_config(self, inputs_vertex: list[Vertex], build_config: dotdict):
        new_fields: list[dotdict] = []

        for vertex in inputs_vertex:
            new_vertex_inputs = []
            field_template = vertex.data["node"]["template"]
            for inp in field_template:
                if inp not in {"code", "_type"}:
                    field_template[inp]["display_name"] = (
                        vertex.display_name + " - " + field_template[inp]["display_name"]
                    )
                    field_template[inp]["name"] = vertex.id + "|" + inp
                    new_vertex_inputs.append(field_template[inp])
            new_fields += new_vertex_inputs
        for field in new_fields:
            build_config[field["name"]] = field
        return build_config

    inputs = [
        DropdownInput(
            name="flow_name",
            display_name="Flow Name",
            info="The name of the flow to run.",
            options=[],
            refresh_button=True,
            real_time_refresh=True,
        ),
    ]

    outputs = [Output(name="flow_outputs", display_name="Flow Outputs", method="generate_results")]

    async def generate_results(self) -> list[Data]:
        tweaks: dict = {}
        for field in self._attributes:
            if field != "flow_name" and "|" in field:
                [node, name] = field.split("|")
                if node not in tweaks:
                    tweaks[node] = {}
                tweaks[node][name] = self._attributes[field]
        flow_name = self._attributes.get("flow_name")
        run_outputs = await self.run_flow(
            tweaks=tweaks,
            flow_name=flow_name,
            output_type="all",
        )
        data: list[Data] = []
        if not run_outputs:
            return data
        run_output = run_outputs[0]

        if run_output is not None:
            for output in run_output.outputs:
                if output:
                    data.extend(build_data_from_result_data(output))
        return data
