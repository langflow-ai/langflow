import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioGetMonitorChartComponent(Component):
    display_name = "Pubrio Get Monitor Chart"
    description = "Get daily trigger chart data for a monitor."
    icon = "activity"
    name = "PubrioGetMonitorChart"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(
            name="monitor_id", required=True, display_name="Monitor ID", info="Monitor UUID.", tool_mode=True
        ),
        MessageTextInput(name="start_date", display_name="Start Date", info="YYYY-MM-DD", advanced=True),
        MessageTextInput(name="end_date", display_name="End Date", info="YYYY-MM-DD", advanced=True),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="get_chart"),
    ]

    def get_chart(self) -> DataFrame:
        body: dict = {"monitor_id": self.monitor_id}
        if self.start_date:
            body["start_date"] = self.start_date
        if self.end_date:
            body["end_date"] = self.end_date
        result = pubrio_post(self.api_key, "/monitors/statistics/chart", body)
        records = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(records, list):
            data = [Data(text=json.dumps(r), data=r) for r in records]
        else:
            data = [Data(text=json.dumps(records), data=records if isinstance(records, dict) else {"result": records})]
        self.status = data
        return DataFrame(data)
