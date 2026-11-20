from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute


class CompanyEnrichPersonLookupComponent(Component):
    display_name = "Look Up Person"
    description = "Look Up Person with CompanyEnrich. One request; may consume credits. Full response preserved."
    documentation = "https://docs.companyenrich.com/reference/post_people-lookup"
    icon = "CompanyEnrich"
    name = "CompanyEnrichPersonLookup"

    inputs = [
        *connection_inputs(),
        MessageTextInput(name="email", display_name="Email", required=True, tool_mode=True),
        MessageTextInput(
            name="expand",
            display_name="Expand",
            is_list=True,
            advanced=True,
            info="workforce for company routes; education for people",
        ),
    ]
    outputs = [Output(display_name="Results", name="results", method="lookup_person")]

    async def lookup_person(self) -> Data:
        values = {
            "email": self.email,
            "expand": self.expand or None,
        }
        return await execute(self, "post_people_lookup", values)
