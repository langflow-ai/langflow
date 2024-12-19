from langflow.custom import Component
from langflow.graph.graph.base import Graph
from langflow.graph.vertex.base import Vertex
from langflow.helpers.flow import get_flow_inputs
from langflow.io import DropdownInput, Output
from langflow.schema import Data, dotdict
from langflow.template.field.base import Input


class FlowOrchestratorComponent(Component):
    display_name = "Flow Orchestrator"
    description = "A component to orchestrate flows."
    name = "FlowOrchestrator"
    legacy: bool = True
    icon = "workflow"
    inputs = [
        DropdownInput(
            name="flow_name_selected",
            display_name="Flow Name",
            info="The name of the flow to run.",
            options=[],
            refresh_button=True,
        ),
    ]
    outputs = [
        Output(display_name="Run Outputs", name="run_outputs", method="run_flow_selected"),
    ]

    async def get_list_of_flows(self) -> list[str]:
        flow_datas = await self.alist_flows()
        return [flow_data.data["name"] for flow_data in flow_datas]

    async def get_flow(self, flow_name: str):
        flow_datas = await self.alist_flows()
        for flow_data in flow_datas:
            if flow_data.data["name"] == flow_name:
                return flow_data
        return None

    async def get_graph_details(self, flow_name: str) -> tuple[Graph, list[Vertex]]:
        flow_data = await self.get_flow(flow_name)
        graph = Graph.from_payload(flow_data.data["data"])
        # Get all inputs from the graph
        inputs = get_flow_inputs(graph)
        return graph, inputs

    async def run_flow_selected(self) -> None:
        graph, inputs = await self.get_graph_details(self.flow_name_selected)
        return

    async def update_build_config(
        self, build_config: dotdict, field_value: str, field_name: str | None = None
    ) -> dotdict:
        if field_name == "flow_name_selected" and build_config["flow_name_selected"]["options"] == []:
            build_config["flow_name_selected"]["options"] = await self.get_list_of_flows()
            build_config["flow_name_selected"]["value"] = field_value
        return build_config
