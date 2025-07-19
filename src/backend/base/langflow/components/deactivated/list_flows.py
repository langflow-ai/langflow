from lfx.custom.custom_component.custom_component import CustomComponent

from langflow.schema.data import Data


class ListFlowsComponent(CustomComponent):
    display_name = "List Flows"
    description = "A component to list all available flows."
    icon = "ListFlows"
    beta: bool = True
    name = "ListFlows"

    def build_config(self):
        return {}

    async def build(
        self,
    ) -> list[Data]:
        flows = await self.alist_flows()
        self.status = flows
        return flows
