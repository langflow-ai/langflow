from typing import Any, List, Optional, Text, Tuple

from loguru import logger

from langflow.custom import CustomComponent
from langflow.graph.graph.base import Graph
from langflow.graph.schema import ResultData, RunOutputs
from langflow.schema import Record
from langflow.schema.dotdict import dotdict
from langflow.template.field.base import TemplateField


class SubFlowComponent(CustomComponent):
    display_name = "SubFlow"
    description = "Dynamically Generates a Component from a Flow. The output is a list of records with keys 'result' and 'message'."
    beta: bool = True
    field_order = ["flow_name"]

    def get_flow_names(self) -> List[str]:
        flow_records = self.list_flows()
        return [flow_record.data["name"] for flow_record in flow_records]

    def get_flow(self, flow_name: str) -> Optional[Text]:
        flow_records = self.list_flows()
        for flow_record in flow_records:
            if flow_record.data["name"] == flow_name:
                return flow_record
        return None

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        logger.debug(f"Updating build config with field value {field_value} and field name {field_name}")
        if field_name == "flow_name":
            build_config["flow_name"]["options"] = self.get_flow_names()
        # Clean up the build config
        for key in list(build_config.keys()):
            if key not in self.field_order + ["code", "_type"]:
                del build_config[key]
        if field_value is not None and field_name == "flow_name":
            try:
                flow_record = self.get_flow(field_value)
                if not flow_record:
                    raise ValueError(f"Flow {field_value} not found.")
                graph = Graph.from_payload(flow_record.data["data"])
                # Get all inputs from the graph
                inputs = self.get_flow_inputs(graph)
                # Add inputs to the build config
                build_config = self.add_inputs_to_build_config(inputs, build_config)
            except Exception as e:
                logger.error(f"Error getting flow {field_value}: {str(e)}")

        return build_config

    def get_flow_inputs(self, graph: Graph) -> List[Record]:
        inputs = []
        for vertex in graph.vertices:
            if vertex.is_input:
                inputs.append((vertex.id, vertex.display_name, vertex.description))
        logger.debug(inputs)
        return inputs

    def add_inputs_to_build_config(self, inputs: List[Tuple], build_config: dotdict):
        new_fields: list[TemplateField] = []
        for input_id, input_display_name, input_description in inputs:
            field = TemplateField(
                display_name=input_display_name,
                name=input_id,
                info=input_description,
                field_type="str",
                default=None,
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
        }

    def build_records_from_result_data(self, result_data: ResultData) -> List[Record]:
        messages = result_data.messages
        if not messages:
            return []
        records = []
        for message in messages:
            message_dict = message if isinstance(message, dict) else message.model_dump()
            record = Record(data={"result": result_data.model_dump(), "message": message_dict.get("message", "")})
            records.append(record)
        return records

    async def build(self, flow_name: str, **kwargs) -> List[Record]:
        tweaks = {key: {"input_value": value} for key, value in kwargs.items()}
        run_outputs: List[Optional[RunOutputs]] = await self.run_flow(
            tweaks=tweaks,
            flow_name=flow_name,
        )
        run_output = run_outputs[0]

        records = []
        for output in run_output.outputs:
            if output:
                records.extend(self.build_records_from_result_data(output))

        self.status = records
        logger.debug(records)
        return records
