import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioGetMonitorLogsComponent(Component):
    display_name = "Pubrio Get Monitor Logs"
    description = "Get trigger logs for a monitor."
    icon = "activity"
    name = "PubrioGetMonitorLogs"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(name="monitor_id", display_name="Monitor ID", info="Monitor UUID.", tool_mode=True),
        IntInput(name="page", display_name="Page", value=1, advanced=True),
        IntInput(name="per_page", display_name="Per Page", value=25, advanced=True),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="get_logs"),
    ]

    def get_logs(self) -> DataFrame:
        result = pubrio_post(
            self.api_key,
            "/monitors/statistics/logs",
            {
                "monitor_id": self.monitor_id,
                "page": self.page or 1,
                "per_page": self.per_page or 25,
            },
        )
        records = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(records, list):
            data = [Data(text=json.dumps(r), data=r) for r in records]
        else:
            data = [Data(text=json.dumps(records), data=records if isinstance(records, dict) else {"result": records})]
        self.status = data
        return DataFrame(data)
