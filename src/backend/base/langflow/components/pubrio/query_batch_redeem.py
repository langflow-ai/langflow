import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioQueryBatchRedeemComponent(Component):
    display_name = "Pubrio Query Batch Redeem"
    description = "Check the status and results of a batch contact reveal."
    icon = "search"
    name = "PubrioQueryBatchRedeem"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(name="redeem_query_id", display_name="Redeem Query ID", info="The redeem_query_id from a batch redeem operation.", required=True, tool_mode=True),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="query"),
    ]

    def query(self) -> DataFrame:
        result = pubrio_post(self.api_key, "/redeem/people/batch/query", {"redeem_query_id": self.redeem_query_id})
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
