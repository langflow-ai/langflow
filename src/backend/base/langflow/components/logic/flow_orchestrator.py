from typing import Any

from loguru import logger

from langflow.base.flow_processing.utils import build_data_from_result_data
from langflow.custom import Component
from langflow.graph.graph.base import Graph
from langflow.graph.vertex.base import Vertex
from langflow.helpers.flow import get_flow_inputs, run_flow
from langflow.io import DropdownInput, MessageInput, Output
from langflow.schema import Data, dotdict

default_keys = [
    "code",
    "_type",
    "flow_name_selected",
    "session_id",
]


class FlowOrchestrator(Component):
    display_name = "Flow Orchestrator"
    description = "Generates a Component from a Flow, with all of its inputs, and "
    name = "FlowOrchestrator"
    beta: bool = True
    icon = "Workflow"
    inputs = [
        DropdownInput(
            name="flow_name_selected",
            display_name="Flow Name",
            info="The name of the flow to run.",
            options=[],
            real_time_refresh=True,
            value=None,
        ),
        MessageInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID to run the flow in.",
            value="",
            advanced=True,
        ),
    ]

    outputs = [Output(name="flow_outputs", display_name="Flow Outputs", method="generate_results")]

    async def get_flow_names(self) -> list[str]:
        flow_data = await self.alist_flows()
        return [flow_data.data["name"] for flow_data in flow_data]

    async def get_flow(self, flow_name_selected: str) -> Data | None:
        flow_datas = await self.alist_flows()
        for flow_data in flow_datas:
            if flow_data.data["name"] == flow_name_selected:
                return flow_data
        return None

    async def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "flow_name_selected":
            build_config["flow_name_selected"]["options"] = await self.get_flow_names()

            # for key in list(build_config.keys()):
            #     if key not in [x.name for x in self.inputs] + ["code", "_type", "get_final_results_only"]:
            #         del build_config[key]
            missing_keys = [key for key in default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)
            if field_value is not None:
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
                            new_fields = self.get_new_fields(inputs)
                            print(f"New Fields {new_fields}")
                            old_fields = self.get_old_fields(build_config, new_fields)
                            self.delete_fields(build_config, old_fields)
                            build_config = self.add_new_fields(build_config, new_fields)

                        except Exception:  # noqa: BLE001
                            logger.exception(f"Error building graph for flow {field_value}")

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
                        "tool_mode": not (
                            field_template[input_name].get("advanced", False)
                        ),
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

    async def generate_results(self) -> list[Data]:
        tweaks: dict = {}
        for field in self._attributes:
            if field != "flow_name_selected" and "|" in field:
                [node, name] = field.split("|")
                if node not in tweaks:
                    tweaks[node] = {}
                tweaks[node][name] = self._attributes[field]
        flow_name_selected = self._attributes.get("flow_name_selected")

        run_outputs = await run_flow(
            inputs=None,
            output_type="all",
            flow_id=None,
            flow_name=flow_name_selected,
            tweaks=tweaks,
            user_id=str(self.user_id),
            run_id=self.graph.run_id,
            session_id=self.graph.session_id or self.session_id,
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
