from typing import Any

from loguru import logger
from typing_extensions import override

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.base.tools.flow_tool import FlowTool
from langflow.field_typing import Tool
from langflow.graph.graph.base import Graph
from langflow.helpers.flow import get_flow_inputs
from langflow.io import BoolInput, DropdownInput, Output, StrInput
from langflow.schema.data import Data
from langflow.schema.dotdict import dotdict


class FlowToolComponent(LCToolComponent):
    display_name = "Flow as Tool [Deprecated]"
    description = "Construct a Tool from a function that runs the loaded Flow."
    field_order = ["flow_name", "name", "description", "return_direct"]
    trace_type = "tool"
    name = "FlowTool"
    legacy: bool = True
    icon = "hammer"

    async def get_flow_names(self) -> list[str]:
        flow_datas = await self.alist_flows()
        return [flow_data.data["name"] for flow_data in flow_datas]

    async def get_flow(self, flow_name: str) -> Data | None:
        """Retrieves a flow by its name.

        Args:
            flow_name (str): The name of the flow to retrieve.

        Returns:
            Optional[Text]: The flow record if found, None otherwise.
        """
        flow_datas = await self.alist_flows()
        for flow_data in flow_datas:
            if flow_data.data["name"] == flow_name:
                return flow_data
        return None

    @override
    async def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "flow_name":
            build_config["flow_name"]["options"] = self.get_flow_names()

        return build_config

    inputs = [
        DropdownInput(
            name="flow_name", display_name="Flow Name", info="The name of the flow to run.", refresh_button=True
        ),
        StrInput(
            name="tool_name",
            display_name="Name",
            info="The name of the tool.",
        ),
        StrInput(
            name="tool_description",
            display_name="Description",
            info="The description of the tool; defaults to the Flow's description.",
        ),
        BoolInput(
            name="return_direct",
            display_name="Return Direct",
            info="Return the result directly from the Tool.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="api_build_tool", display_name="Tool", method="build_tool"),
    ]

    async def build_tool(self) -> Tool:
        FlowTool.model_rebuild()
        if "flow_name" not in self._attributes or not self._attributes["flow_name"]:
            msg = "Flow name is required"
            raise ValueError(msg)
        flow_name = self._attributes["flow_name"]
        flow_data = await self.get_flow(flow_name)
        if not flow_data:
            msg = "Flow not found."
            raise ValueError(msg)
        graph = Graph.from_payload(
            flow_data.data["data"],
            user_id=str(self.user_id),
        )
        try:
            graph.set_run_id(self.graph.run_id)
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).warning("Failed to set run_id")
        inputs = get_flow_inputs(graph)
        tool_description = self.tool_description.strip() or flow_data.description
        tool = FlowTool(
            name=self.tool_name,
            description=tool_description,
            graph=graph,
            return_direct=self.return_direct,
            inputs=inputs,
            flow_id=str(flow_data.id),
            user_id=str(self.user_id),
            session_id=self.graph.session_id if hasattr(self, "graph") else None,
        )
        description_repr = repr(tool.description).strip("'")
        args_str = "\n".join([f"- {arg_name}: {arg_data['description']}" for arg_name, arg_data in tool.args.items()])
        self.status = f"{description_repr}\nArguments:\n{args_str}"
        return tool
