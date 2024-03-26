from typing import Any, List, Optional

from langflow.custom import CustomComponent
from langflow.field_typing import NestedDict, Text
from langflow.graph.schema import ResultData
from langflow.schema import Record, dotdict


class RunFlowComponent(CustomComponent):
    display_name = "Run Flow"
    description = "A component to run a flow."
    beta: bool = True

    def get_flow_names(self) -> List[str]:
        flow_records = self.list_flows()
        return [flow_record.data["name"] for flow_record in flow_records]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "flow_name":
            build_config["flow_name"]["options"] = self.get_flow_names()

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
            record = Record(text=message_dict.get("text", ""), data={"result": result_data})
            records.append(record)
        return records

    async def build(self, input_value: Text, flow_name: str, tweaks: NestedDict) -> List[Record]:
        results: List[Optional[ResultData]] = await self.run_flow(
            inputs={"input_value": input_value}, flow_name=flow_name, tweaks=tweaks
        )
        if isinstance(results, list):
            records = []
            for result in results:
                if result:
                    records.extend(self.build_records_from_result_data(result))
        else:
            records = self.build_records_from_result_data(results)

        self.status = records
        return records
