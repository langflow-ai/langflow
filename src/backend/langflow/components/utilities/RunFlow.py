from typing import List, Optional

from langflow import CustomComponent
from langflow.field_typing import NestedDict, Text
from langflow.graph.schema import ResultData
from langflow.schema import Record


class RunFlowComponent(CustomComponent):
    display_name = "Run Flow"
    description = "A component to run a flow."

    def get_flow_names(self) -> List[str]:
        flow_records = self.list_flows()
        self.flow_records = flow_records
        return [flow_record.data["name"] for flow_record in flow_records]

    def build_config(self):
        return {
            "input_value": {
                "display_name": "Input Value",
                "multiline": True,
            },
            "flow": {
                "display_name": "Flow ID",
                "info": "The ID of the flow to run.",
                "options": self.get_flow_names,
            },
            "tweaks": {
                "display_name": "Tweaks",
                "info": "Tweaks to apply to the flow.",
            },
        }

    async def build(self, input_value: Text, flow: str, tweaks: NestedDict) -> Record:
        input_dict = {"input_value": input_value}
        flow_ids = [
            flow_record.data["id"]
            for flow_record in self.flow_records
            if flow_record.data["name"] == flow
        ]
        if not flow_ids:
            raise ValueError(f"Flow {flow} not found.")
        flow_id = flow_ids[0]

        result: List[Optional[ResultData]] = await self.run_flow(
            input_value=input_dict, flow_id=flow_id, tweaks=tweaks
        )
        record = Record(data=result)
        self.status = record
        return record
