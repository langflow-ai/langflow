from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute


class CompanyEnrichEnrichComponent(Component):
    display_name = "Enrich Company"
    description = "Enrich Company with CompanyEnrich. One request; may consume credits. Full response preserved."
    documentation = "https://docs.companyenrich.com/reference/get_companies-enrich"
    icon = "CompanyEnrich"
    name = "CompanyEnrichEnrich"

    inputs = [
        *connection_inputs(),
        MessageTextInput(name="domain", display_name="Company Domain", required=True, tool_mode=True),
        MessageTextInput(
            name="expand",
            display_name="Expand",
            is_list=True,
            advanced=True,
            info="workforce for company routes; education for people",
        ),
        DropdownInput(
            name="wait_for_enrichment",
            display_name="Wait for Enrichment",
            options=["API default", "Wait", "Return immediately"],
            value="API default",
            advanced=True,
        ),
    ]
    outputs = [Output(display_name="Results", name="company", method="enrich_company")]

    async def enrich_company(self) -> Data:
        values = {
            "domain": self.domain or None,
            "expand": self.expand or None,
            "wait_for_enrichment": {"API default": None, "Wait": True, "Return immediately": False}[
                self.wait_for_enrichment
            ],
        }
        return await execute(self, "get_companies_enrich", values)
