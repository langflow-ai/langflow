import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioSearchVerticalsComponent(Component):
    display_name = "Pubrio Search Verticals"
    description = "Search industry verticals by keyword."
    icon = "search"
    name = "PubrioSearchVerticals"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(name="keyword", display_name="Keyword", info="Search keyword.", tool_mode=True),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="search"),
    ]

    def search(self) -> DataFrame:
        result = pubrio_post(self.api_key, "/verticals", {"keyword": self.keyword})
        records = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(records, list):
            data = [Data(text=json.dumps(r), data=r if isinstance(r, dict) else {"value": r}) for r in records]
        else:
            data = [Data(text=json.dumps(records), data=records if isinstance(records, dict) else {"result": records})]
        self.status = data
        return DataFrame(data)
