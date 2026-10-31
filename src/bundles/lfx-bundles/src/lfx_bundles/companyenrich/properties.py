from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DictInput, MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute


class CompanyEnrichPropertiesComponent(Component):
    display_name = "Match Company Properties"
    description = (
        "Match Company Properties with CompanyEnrich. One request; may consume credits. Full response preserved."
    )
    documentation = "https://docs.companyenrich.com/reference/post_companies-enrich"
    icon = "CompanyEnrich"
    name = "CompanyEnrichProperties"

    inputs = [
        *connection_inputs(),
        DictInput(
            name="properties",
            display_name="Company Matching Properties",
            required=True,
            info="At least one name/social profile field from the API schema",
        ),
        MessageTextInput(
            name="expand",
            display_name="Expand",
            is_list=True,
            advanced=True,
            info="workforce for company routes; education for people",
        ),
    ]
    outputs = [Output(display_name="Results", name="results", method="match_company")]

    async def match_company(self) -> Data:
        values = {
            "properties": self.properties,
            "expand": self.expand or None,
        }
        return await execute(self, "post_companies_enrich", values)
