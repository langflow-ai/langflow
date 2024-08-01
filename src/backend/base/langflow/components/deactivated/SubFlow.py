from typing import Any, List, Optional

from langflow.base.flow_processing.utils import build_data_from_result_data
from langflow.custom import CustomComponent
from langflow.graph.graph.base import Graph
from langflow.graph.schema import RunOutputs
from langflow.graph.vertex.base import Vertex
from langflow.helpers.flow import get_flow_inputs
from langflow.schema import Data
from langflow.schema.dotdict import dotdict
from langflow.template.field.base import Input
from loguru import logger


class SubFlowComponent(CustomComponent):
    display_name = "Sub Flow"
    description = (
        "Dynamically Generates a Component from a Flow. The output is a list of data with keys 'result' and 'message'."
    )
    beta: bool = True
    field_order = ["flow_name"]
    name = "SubFlow"

    def get_flow_names(self) -> List[str]:
        flow_datas = self.list_flows()
        return [flow_data.data["name"] for flow_data in flow_datas]

    def get_flow(self, flow_name: str) -> Optional[Data]:
        flow_datas = self.list_flows()
        for flow_data in flow_datas:
            if flow_data.data["name"] == flow_name:
                return flow_data
        return None

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        logger.debug(f"Updating build config with field value {field_value} and field name {field_name}")
        if field_name == "flow_name":
            build_config["flow_name"]["options"] = self.get_flow_names()
        # Clean up the build config
        for key in list(build_config.keys()):
            if key not in self.field_order + ["code", "_type", "get_final_results_only"]:
                del build_config[key]
        if field_value is not None and field_name == "flow_name":
            try:
                flow_data = self.get_flow(field_value)
                if not flow_data:
                    raise ValueError(f"Flow {field_value} not found.")
                graph = Graph.from_payload(flow_data.data["data"])
                # Get all inputs from the graph
                inputs = get_flow_inputs(graph)
                # Add inputs to the build config
                build_config = self.add_inputs_to_build_config(inputs, build_config)
            except Exception as e:
                logger.error(f"Error getting flow {field_value}: {str(e)}")

        return build_config

    def add_inputs_to_build_config(self, inputs: List[Vertex], build_config: dotdict):
        new_fields: list[Input] = []
        for vertex in inputs:
            field = Input(
                display_name=vertex.display_name,
                name=vertex.id,
                info=vertex.description,
                field_type="str",
                value=None,
            )
            new_fields.append(field)
        logger.debug(new_fields)
        for field in new_fields:
            build_config[field.name] = field.to_dict()
        return build_config

    def build_config(self):
        return {
            "input_value": {
                "display_name": "Input Value",
                "multiline": True,
            },
            "flow_name": {
                "display_name": "Flow Name",
                "info": "The name of the flow to run.",
                "options": [],
                "real_time_refresh": True,
                "refresh_button": True,
            },
            "tweaks": {
                "display_name": "Tweaks",
                "info": "Tweaks to apply to the flow.",
            },
            "get_final_results_only": {
                "display_name": "Get Final Results Only",
                "info": "If False, the output will contain all outputs from the flow.",
                "advanced": True,
            },
        }

    async def build(self, flow_name: str, get_final_results_only: bool = True, **kwargs) -> List[Data]:
        tweaks = {key: {"input_value": value} for key, value in kwargs.items()}
        run_outputs: List[Optional[RunOutputs]] = await self.run_flow(
            tweaks=tweaks,
            flow_name=flow_name,
        )
        if not run_outputs:
            return []
        run_output = run_outputs[0]

        data = []
        if run_output is not None:
            for output in run_output.outputs:
                if output:
                    data.extend(build_data_from_result_data(output, get_final_results_only))

        self.status = data
        logger.debug(data)
        return data
