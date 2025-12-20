from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.inputs import HandleInput
from lfx.io import MessageTextInput, Output
from lfx.schema import Data, Message


class SwitchComponent(Component):
    display_name = "Switch"
    description = "Routes an input message to a corresponding output based on text comparison."
    icon = "FlowConditionIcon"
    name = "SwitchComponent"

    inputs = [
        HandleInput(
            name="switch",
            display_name="Input",
            info="Input is Data or Message",
            input_types=["Data", "Message"],
            required=True,
        ),
        MessageTextInput(
            name="switch_key",
            display_name="Switch Key",
            advanced=True,
        ),
        MessageTextInput(
            name="cases",
            display_name="Case List",
            is_list=True,
            real_time_refresh=True,
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Output 1",
            name="output_1",
            method="build_output",
            group_outputs=True,
        )
    ]

    async def _build_results(self) -> tuple[dict, dict]:
        results, artifacts = {}, {}

        self._pre_run_setup_if_needed()
        self._handle_tool_mode()

        value = None
        if isinstance(self.switch, Message):
            value = self.switch.text
        elif isinstance(self.switch, Data):
            if self.switch_key is None or self.switch_key == "":
                raise ValueError("Data must specify a ‘case’ key.")
            value = self.switch.data.get(self.switch_key)

        output_name = None
        for index, case in enumerate(self.cases):
            if value == case:
                output_name = f"output_{index + 1}"
                break

        for output in self._get_outputs_to_process():
            if output.name == output_name:
                self._current_output = output.name
                result = await self._get_output_result(output)
                results[output.name] = result
                artifacts[output.name] = self._build_artifact(result)
                self._log_output(output)
                break

        self._finalize_results(results, artifacts)
        return results, artifacts

    def build_output(self):
        return self.switch.data

    def update_outputs(self, frontend_node: dict, field_name: str, _field_value: Any) -> dict:
        target_count = len(self.cases)
        if field_name == "cases" and target_count != len(frontend_node):
            frontend_node["outputs"] = []
            for i in range(target_count):
                new_output = Output(
                    display_name=f"Output {i + 1}",
                    name=f"output_{i + 1}",
                    method="build_output",
                    group_outputs=True,
                )
                frontend_node["outputs"].append(new_output.to_dict())
        return frontend_node
