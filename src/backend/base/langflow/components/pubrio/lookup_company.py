import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioLookupCompanyComponent(Component):
    display_name = "Pubrio Lookup Company"
    description = "Look up detailed company information by domain, LinkedIn URL, or ID."
    icon = "building"
    name = "PubrioLookupCompany"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="JSON with lookup_type and value, or a domain name.",
            tool_mode=True,
        ),
        DropdownInput(
            name="lookup_type",
            display_name="Lookup Type",
            options=["domain", "linkedin_url", "domain_search_id", "domain_id"],
            value="domain",
        ),
        MessageTextInput(name="value", display_name="Value", info="The domain, LinkedIn URL, or ID to look up."),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run_lookup"),
    ]

    def run_lookup(self) -> DataFrame:
        lookup_type = self.lookup_type
        value = self.value

        if self.query and not value:
            try:
                params = json.loads(self.query)
                if not isinstance(params, dict):
                    raise TypeError
                lookup_type = params.get("lookup_type", lookup_type)
                value = params.get("value", "")
            except (json.JSONDecodeError, TypeError, ValueError):
                value = self.query

        result = pubrio_post(self.api_key, "/companies/lookup", {lookup_type: value})
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
