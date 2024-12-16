from typing import TYPE_CHECKING, Any

from typing_extensions import override

from langflow.base.flow_processing.utils import build_data_from_run_outputs
from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, NestedDictInput, Output
from langflow.schema import Data, dotdict

if TYPE_CHECKING:
    from langflow.graph.schema import RunOutputs


class RunFlowComponent(Component):
    display_name = "Run Flow"
    description = "A component to run a flow."
    name = "RunFlow"
    legacy: bool = True
    icon = "workflow"

    async def get_flow_names(self) -> list[str]:
        flow_data = await self.alist_flows()
        return [flow_data.data["name"] for flow_data in flow_data]

    @override
    async def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "flow_name":
            build_config["flow_name"]["options"] = await self.get_flow_names()

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

    async def generate_results(self) -> list[Data]:
        if "flow_name" not in self._attributes or not self._attributes["flow_name"]:
            msg = "Flow name is required"
            raise ValueError(msg)
        flow_name = self._attributes["flow_name"]

        results: list[RunOutputs | None] = await self.run_flow(
            inputs={"input_value": self.input_value}, flow_name=flow_name, tweaks=self.tweaks
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
