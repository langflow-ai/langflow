from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute


class CompanyEnrichCompanyByIdComponent(Component):
    display_name = "Get Company by ID"
    description = "Get Company by ID with CompanyEnrich. One request; may consume credits. Full response preserved."
    documentation = "https://docs.companyenrich.com/reference/get_companies"
    icon = "CompanyEnrich"
    name = "CompanyEnrichCompanyById"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="company_id", display_name="Company ID", info="Company UUID", tool_mode=True, required=True
        ),
        MessageTextInput(
            name="expand",
            display_name="Expand",
            is_list=True,
            advanced=True,
            info="workforce for company routes; education for people",
        ),
    ]
    outputs = [Output(display_name="Results", name="results", method="get_company")]

    async def get_company(self) -> Data:
        values = {
            "company_id": self.company_id or None,
            "expand": self.expand or None,
        }
        return await execute(self, "get_companies", values)
