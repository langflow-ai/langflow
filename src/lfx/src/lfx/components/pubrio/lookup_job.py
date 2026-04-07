import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioLookupJobComponent(Component):
    display_name = "Pubrio Lookup Job"
    description = "Look up detailed information about a specific job posting."
    icon = "briefcase"
    name = "PubrioLookupJob"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(
            name="id",
            display_name="Job Search ID",
            info="The job_search_id from a job search.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="lookup"),
    ]

    def lookup(self) -> DataFrame:
        result = pubrio_post(self.api_key, "/companies/jobs/lookup", {"job_search_id": self.id})
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
