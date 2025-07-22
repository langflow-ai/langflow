from typing import Any

from loguru import logger

from lfx.base.tools.run_flow import RunFlowBaseComponent
from lfx.helpers.flow import run_flow
from lfx.schema.dotdict import dotdict


class RunFlowComponent(RunFlowBaseComponent):
    display_name = "Run Flow"
    description = (
        "Creates a tool component from a Flow that takes all its inputs and runs it. "
        " \n **Select a Flow to use the tool mode**"
    )
    documentation: str = "https://docs.langflow.org/components-logic#run-flow"
    beta = True
    name = "RunFlow"
    icon = "Workflow"

    inputs = RunFlowBaseComponent._base_inputs
    outputs = RunFlowBaseComponent._base_outputs

    async def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "flow_name_selected":
            build_config["flow_name_selected"]["options"] = await self.get_flow_names()
            missing_keys = [key for key in self.default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)
            if field_value is not None:
                try:
                    graph = await self.get_graph(field_value)
                    build_config = self.update_build_config_from_graph(build_config, graph)
                except Exception as e:
                    msg = f"Error building graph for flow {field_value}"
                    logger.exception(msg)
                    raise RuntimeError(msg) from e
        return build_config

    async def run_flow_with_tweaks(self):
        tweaks: dict = {}

        flow_name_selected = self._attributes.get("flow_name_selected")
        parsed_flow_tweak_data = self._attributes.get("flow_tweak_data", {})
        if not isinstance(parsed_flow_tweak_data, dict):
            parsed_flow_tweak_data = parsed_flow_tweak_data.dict()

        if parsed_flow_tweak_data != {}:
            for field in parsed_flow_tweak_data:
                if "~" in field:
                    [node, name] = field.split("~")
                    if node not in tweaks:
                        tweaks[node] = {}
                    tweaks[node][name] = parsed_flow_tweak_data[field]
        else:
            for field in self._attributes:
                if field not in self.default_keys and "~" in field:
                    [node, name] = field.split("~")
                    if node not in tweaks:
                        tweaks[node] = {}
                    tweaks[node][name] = self._attributes[field]

        return await run_flow(
            inputs=None,
            output_type="all",
            flow_id=None,
            flow_name=flow_name_selected,
            tweaks=tweaks,
            user_id=str(self.user_id),
            session_id=self.graph.session_id or self.session_id,
        )
