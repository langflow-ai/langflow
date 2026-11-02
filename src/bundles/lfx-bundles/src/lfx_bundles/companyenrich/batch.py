from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute


class CompanyEnrichBatchComponent(Component):
    display_name = "Enrich Company Batch"
    description = "Enrich Company Batch with CompanyEnrich. One request; may consume credits. Full response preserved."
    documentation = "https://docs.companyenrich.com/reference/post_companies-enrich-batch"
    icon = "CompanyEnrich"
    name = "CompanyEnrichBatch"

    inputs = [
        *connection_inputs(),
        MessageTextInput(name="domains", display_name="Company Domains", is_list=True, required=True, tool_mode=True),
        MessageTextInput(
            name="expand",
            display_name="Expand",
            is_list=True,
            advanced=True,
            info="workforce for company routes; education for people",
        ),
    ]
    outputs = [Output(display_name="Results", name="results", method="enrich_batch")]

    async def enrich_batch(self) -> Data:
        values = {
            "domains": self.domains,
            "expand": self.expand or None,
        }
        return await execute(self, "post_companies_enrich_batch", values)
