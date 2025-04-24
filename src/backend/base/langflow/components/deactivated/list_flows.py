from langflow.custom import CustomComponent
from langflow.schema import JSON


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
    ) -> list[JSON]:
        flows = await self.alist_flows()
        self.status = flows
        return flows
