from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import company_domain, connection_inputs, request


class CompanyEnrichEnrichComponent(Component):
    display_name = "Enrich Company"
    description = "Retrieve a company profile by domain with CompanyEnrich. Consumes account credits."
    documentation = "https://docs.companyenrich.com/reference/get_companies-enrich"
    icon = "CompanyEnrich"
    name = "CompanyEnrichEnrich"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="domain",
            display_name="Company Domain",
            required=True,
            tool_mode=True,
            info="Bare domain, for example stripe.com.",
        ),
    ]
    outputs = [Output(display_name="Company", name="company", method="enrich_company")]

    async def enrich_company(self) -> Data:
        result = await request(
            self.api_key,
            "GET",
            "/companies/enrich",
            timeout=self.timeout,
            params={"domain": company_domain(self.domain)},
        )
        self.status = result
        return Data(data=result)
