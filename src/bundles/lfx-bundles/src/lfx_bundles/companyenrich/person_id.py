from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute


class CompanyEnrichPersonByIdComponent(Component):
    display_name = "Get Person by ID"
    description = "Get Person by ID with CompanyEnrich. One request; may consume credits. Full response preserved."
    documentation = "https://docs.companyenrich.com/reference/get_people"
    icon = "CompanyEnrich"
    name = "CompanyEnrichPersonById"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="person_id",
            display_name="Person ID",
            required=True,
            tool_mode=True,
            info="Positive int64 decimal string",
        ),
        MessageTextInput(
            name="expand",
            display_name="Expand",
            is_list=True,
            advanced=True,
            info="workforce for company routes; education for people",
        ),
    ]
    outputs = [Output(display_name="Results", name="results", method="get_person")]

    async def get_person(self) -> Data:
        values = {
            "person_id": self.person_id,
            "expand": self.expand or None,
        }
        return await execute(self, "get_people", values)
