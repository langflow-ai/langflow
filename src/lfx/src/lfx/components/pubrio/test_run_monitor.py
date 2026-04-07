import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioTestRunMonitorComponent(Component):
    display_name = "Pubrio Test Run Monitor"
    description = "Execute a test run of a monitor."
    icon = "activity"
    name = "PubrioTestRunMonitor"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(name="monitor_id", display_name="Monitor ID", info="Monitor UUID to test.", tool_mode=True),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run"),
    ]

    def run(self) -> DataFrame:
        result = pubrio_post(self.api_key, "/monitors/process/try", {"monitor_id": self.monitor_id})
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
