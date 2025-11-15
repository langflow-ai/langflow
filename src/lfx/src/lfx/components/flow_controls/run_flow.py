from typing import Any

from lfx.base.tools.run_flow import RunFlowBaseComponent
from lfx.log.logger import logger
from lfx.schema.dotdict import dotdict


class RunFlowComponent(RunFlowBaseComponent):
    display_name = "Run Flow"
    description = (
        "Executes another flow from within the same project. Can also be used as a tool for agents."
        " \n **Select a Flow to use the tool mode**"
    )
    documentation: str = "https://docs.langflow.org/components-logic#run-flow"
    beta = True
    name = "RunFlow"
    icon = "Workflow"

    inputs = RunFlowBaseComponent.get_base_inputs()
    outputs = RunFlowBaseComponent.get_base_outputs()

    async def update_build_config(
        self,
        build_config: dotdict,
        field_value: Any,
        field_name: str | None = None,
    ):
        missing_keys = [key for key in self.default_keys if key not in build_config]
        for key in missing_keys:
            if key == "flow_name_selected":
                build_config[key] = {"options": [], "options_metadata": [], "value": None}
            elif key == "flow_id_selected":
                build_config[key] = {"value": None}
            elif key == "cache_flow":
                build_config[key] = {"value": False}
            else:
                build_config[key] = {}
        if field_name in {"flow_name_selected", "flow_id_selected"} and field_value is not None:
            try:
                # derive flow id in case field_name is flow_name_selected
                build_config["flow_id_selected"]["value"] = (
                    build_config["flow_name_selected"].get("selected_metadata", {}).get("id", None)
                    or build_config["flow_id_selected"]["value"]
                )

                graph = await self.get_graph(
                    flow_name_selected=field_value,
                    flow_id_selected=build_config["flow_id_selected"]["value"],
                )
                self.update_build_config_from_graph(build_config, graph)
            except Exception as e:
                msg = f"Error building graph for flow {field_value}"
                await logger.aexception(msg)
                raise RuntimeError(msg) from e
        elif field_name == "flow_name_selected" and (build_config.get("is_refresh", False) or field_value is None):
            # list flows on refresh button click or initial load
            options: list[str] = await self.alist_flows_by_flow_folder()
            build_config["flow_name_selected"]["options"] = [flow.data["name"] for flow in options]
            build_config["flow_name_selected"]["options_metadata"] = [{"id": flow.data["id"]} for flow in options]
        return build_config
