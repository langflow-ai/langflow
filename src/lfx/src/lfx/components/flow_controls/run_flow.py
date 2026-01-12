from datetime import datetime
from typing import Any

from lfx.base.tools.run_flow import RunFlowBaseComponent
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict


class RunFlowComponent(RunFlowBaseComponent):
    display_name = "Run Flow"
    description = (
        "Executes another flow from within the same project. Can also be used as a tool for agents."
        " \n **Select a Flow to use the tool mode**"
    )
    documentation: str = "https://docs.langflow.org/run-flow"
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
        if field_name == "flow_name_selected" and (build_config.get("is_refresh", False) or field_value is None):
            # refresh button was clicked or componented was initialized, so list the flows
            options: list[str] = await self.alist_flows_by_flow_folder()
            build_config["flow_name_selected"]["options"] = [flow.data["name"] for flow in options]
            build_config["flow_name_selected"]["options_metadata"] = []
            for flow in options:
                # populate options_metadata
                build_config["flow_name_selected"]["options_metadata"].append(
                    {"id": flow.data["id"], "updated_at": flow.data["updated_at"]}
                )
                # update selected flow if it is stale
                if str(flow.data["id"]) == self.flow_id_selected:
                    await self.check_and_update_stale_flow(flow, build_config)
        elif field_name in {"flow_name_selected", "flow_id_selected"} and field_value is not None:
            # flow was selected by name or id, so get the flow and update the bcfg
            try:
                # derive flow id if the field_name is flow_name_selected
                build_config["flow_id_selected"]["value"] = (
                    self.get_selected_flow_meta(build_config, "id") or build_config["flow_id_selected"]["value"]
                )
                updated_at = self.get_selected_flow_meta(build_config, "updated_at")
                await self.load_graph_and_update_cfg(
                    build_config, build_config["flow_id_selected"]["value"], updated_at
                )
            except Exception as e:
                msg = f"Error building graph for flow {field_value}"
                await logger.aexception(msg)
                raise RuntimeError(msg) from e

        return build_config

    def get_selected_flow_meta(self, build_config: dotdict, field: str) -> dict:
        """Get the selected flow's metadata from the build config."""
        return build_config.get("flow_name_selected", {}).get("selected_metadata", {}).get(field)

    async def load_graph_and_update_cfg(
        self,
        build_config: dotdict,
        flow_id: str,
        updated_at: str | datetime,
    ) -> None:
        """Load a flow's graph and update the build config."""
        graph = await self.get_graph(
            flow_id_selected=flow_id,
            updated_at=self.get_str_isots(updated_at),
        )
        self.update_build_config_from_graph(build_config, graph)

    def should_update_stale_flow(self, flow: Data, build_config: dotdict) -> bool:
        """Check if the flow should be updated."""
        return (
            (updated_at := self.get_str_isots(flow.data["updated_at"]))  # true updated_at date just fetched from db
            and (stale_at := self.get_selected_flow_meta(build_config, "updated_at"))  # outdated date in bcfg
            and self._parse_timestamp(updated_at) > self._parse_timestamp(stale_at)  # stale flow condition
        )

    async def check_and_update_stale_flow(self, flow: Data, build_config: dotdict) -> None:
        """Check if the flow should be updated and update it if necessary."""
        # TODO: improve contract/return value
        if self.should_update_stale_flow(flow, build_config):
            await self.load_graph_and_update_cfg(
                build_config,
                flow.data["id"],
                flow.data["updated_at"],
            )

    def get_str_isots(self, date: datetime | str) -> str:
        """Get a string timestamp from a datetime or string."""
        return date.isoformat() if hasattr(date, "isoformat") else date
