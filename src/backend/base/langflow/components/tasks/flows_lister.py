"""Component for listing all flows in the system."""

from uuid import UUID

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
            # Get flow information as a list of dictionaries
            flows_list = await self.get_flows_info()
            # Structure the response
            flows_dict = {"flows": flows_list}
            return Data(data=flows_dict)
        except Exception as e:  # noqa: BLE001
            return Data(data={"error": str(e), "flow_names": []})

    async def get_folder_id(self, flow_data: list[Data], flow_id: str) -> UUID | None:
        """Get the folder_id of the flow that flow_id == self.flow_id."""
        folder_id = next((flow.folder_id for flow in flow_data if flow.id == flow_id), None)
        if folder_id is None:
            msg = "Folder ID not found"
            raise ValueError(msg)
        if isinstance(folder_id, str):
            folder_id = UUID(folder_id)
        return folder_id

    async def get_flows_info(self) -> list[dict]:
        """Get all flow information from the system as a list of dictionaries."""
        flow_data = await self.alist_flows()
        # Get the folder_id of the flow that flow_id == self.flow_id
        folder_id = await self.get_folder_id(flow_data, self.flow_id)
        return [
            {"name": flow.name, "id": flow.id, "description": flow.description}
            for flow in flow_data
            if flow.folder_id == folder_id
        ]
