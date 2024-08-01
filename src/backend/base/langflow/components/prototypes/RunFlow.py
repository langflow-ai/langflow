from typing import Any, List, Optional

from langflow.base.flow_processing.utils import build_data_from_run_outputs
from langflow.custom import Component
from langflow.graph.schema import RunOutputs
from langflow.io import DropdownInput, MessageTextInput, NestedDictInput, Output
from langflow.schema import Data, dotdict


class RunFlowComponent(Component):
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

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input Value",
            info="The input value to be processed by the flow.",
        ),
        DropdownInput(
            name="flow_name",
            display_name="Flow Name",
            info="The name of the flow to run.",
            options=[],
            refresh_button=True,
        ),
        NestedDictInput(
            name="tweaks",
            display_name="Tweaks",
            info="Tweaks to apply to the flow.",
        ),
    ]

    outputs = [
        Output(display_name="Run Outputs", name="run_outputs", method="generate_results"),
    ]

    async def generate_results(self) -> List[Data]:
        results: List[Optional[RunOutputs]] = await self.run_flow(
            inputs={"input_value": self.input_value}, flow_name=self.flow_name, tweaks=self.tweaks
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
