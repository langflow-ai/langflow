from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute


class CompanyEnrichWorkforceComponent(Component):
    display_name = "Company Workforce"
    description = "Company Workforce with CompanyEnrich. One request; may consume credits. Full response preserved."
    documentation = "https://docs.companyenrich.com/reference/get_companies-workforce"
    icon = "CompanyEnrich"
    name = "CompanyEnrichWorkforce"

    inputs = [
        *connection_inputs(),
        MessageTextInput(name="company_id", display_name="Company ID", info="Company UUID", tool_mode=True),
        MessageTextInput(name="domain", display_name="Company Domain", required=False, tool_mode=True),
    ]
    outputs = [Output(display_name="Results", name="results", method="get_workforce")]

    async def get_workforce(self) -> Data:
        values = {
            "company_id": self.company_id or None,
            "domain": self.domain or None,
        }
        return await execute(self, "get_companies_workforce", values)
