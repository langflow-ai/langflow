"""Component for listing all flows in the system."""

from langflow.custom import Component
from langflow.io import Output
from langflow.schema import Data


class FlowsListerComponent(Component):
    display_name = "Flows Lister"
    description = "Lists all flows in the system."
    icon = "list"
    name = "FlowsLister"

    outputs = [
        Output(name="flows", display_name="Flows", method="list_flows"),
    ]

    async def list_flows(self) -> Data:
        """Return a list of all flow names in the system."""
        try:
            # Reuse the method from RunFlowBaseComponent to get flow names
            flow_data = await self.get_flow_names()
            return Data(data=dict(flow_data))
        except Exception as e:  # noqa: BLE001
            return Data(data={"error": str(e), "flow_names": []})

    async def get_flow_names(self) -> list[tuple[str, str]]:
        """Get all flow names from the system."""
        flow_data = await self.alist_flows()
        return [(flow.name, flow.id) for flow in flow_data]
