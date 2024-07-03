from typing import Any, List, Optional

from langflow.base.flow_processing.utils import build_data_from_run_outputs
from langflow.custom import CustomComponent
from langflow.field_typing import NestedDict, Text
from langflow.graph.schema import RunOutputs
from langflow.schema import Data, dotdict


class RunFlowComponent(CustomComponent):
    display_name = "Run Flow"
    description = "A component to run a flow."
    name = "RunFlow"
    beta: bool = True

    def get_flow_names(self) -> List[str]:
        flow_data = self.list_flows()
        return [flow_data.data["name"] for flow_data in flow_data]

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

    async def build(self, input_value: Text, flow_name: str, tweaks: NestedDict) -> List[Data]:
        results: List[Optional[RunOutputs]] = await self.run_flow(
            inputs={"input_value": input_value}, flow_name=flow_name, tweaks=tweaks
        )
        if isinstance(results, list):
            data = []
            for result in results:
                if result:
                    data.extend(build_data_from_run_outputs(result))
        else:
            data = build_data_from_run_outputs()(results)

        self.status = data
        return data
