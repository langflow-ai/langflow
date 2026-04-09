import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_get


class PubrioGetManagementLevelsComponent(Component):
    display_name = "Pubrio Get Management Levels"
    description = "Get all management/seniority level codes."
    icon = "list"
    name = "PubrioGetManagementLevels"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="fetch"),
    ]

    def fetch(self) -> DataFrame:
        result = pubrio_get(self.api_key, "/management_levels")
        records = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(records, list):
            data = [Data(text=json.dumps(r), data=r if isinstance(r, dict) else {"value": r}) for r in records]
        else:
            data = [Data(text=json.dumps(records), data=records if isinstance(records, dict) else {"result": records})]
        self.status = data
        return DataFrame(data)
