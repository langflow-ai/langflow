from typing import Any

from langflow.schema.message import Message
from loguru import logger

from langflow.base.flow_processing.utils import build_data_from_result_data
from langflow.base.tools.run_flow import RunFlowBaseComponent
from langflow.helpers.flow import run_flow
from langflow.schema import Data, dotdict


class RunFlowComponent(RunFlowBaseComponent):
    display_name = "Run Flow"
    description = "Creates a tool component from a Flow that takes all its inputs and runs it."
    name = "RunFlow"
    beta: bool = True
    icon = "Workflow"

    inputs = RunFlowBaseComponent._base_inputs

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
        if field_name == "flow_json" and field_value:
            try:
                graph = await self.get_graph()
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
        # import pdb; pdb.set_trace()
        run_outputs = await run_flow(
            inputs=None,
            output_type="all",
            flow_id=None,
            flow_name=flow_name_selected,
            tweaks=tweaks,
            user_id=str(self.user_id),
            # run_id=self.graph.run_id,
            session_id=self.graph.session_id or self.session_id,
        )
        import pdb

        pdb.set_trace()
        return run_outputs

    # async def data_output(self) -> list[Data]:
    #     """Return the data output."""

    async def single_output(self) -> Data:
        """Return the single output."""
        run_outputs = await self.run_flow_with_tweaks()
        data: list[Data] = []
        if not run_outputs:
            return data
        run_output = run_outputs[0]

        if run_output is not None:
            for output in run_output.outputs:
                if output:
                    data.extend(build_data_from_result_data(output))
        return Data(data=data[-1].data)

    # async def dataframe_output(self) -> list[Data]:
    #     """Return the dataframe output.""

    async def data_output(self) -> list[Data]:
        """Return the data output."""
        run_outputs = await self.run_flow_with_tweaks()
        data: list[Data] = []
        if not run_outputs:
            return data
        run_output = run_outputs[0]
        return data
    

    async def message_output(self) -> Message:
        run_outputs = await self.run_flow_with_tweaks()
        message = run_outputs[0].outputs[0].results["message"]
        if isinstance(message, Message):
            return message
        return Message(content=message)
