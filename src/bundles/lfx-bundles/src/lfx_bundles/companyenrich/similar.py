from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DictInput, MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import (
    company_domain,
    connection_inputs,
    pagination_inputs,
    request,
    search_payload,
)

MAX_SEED_DOMAINS = 10


class CompanyEnrichSimilarComponent(Component):
    display_name = "Find Similar Companies"
    description = "Find companies similar to up to ten seed domains. Results consume CompanyEnrich credits."
    documentation = "https://docs.companyenrich.com/reference/post_companies-similar"
    icon = "CompanyEnrich"
    name = "CompanyEnrichSimilar"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="domains",
            display_name="Company Domains",
            is_list=True,
            required=True,
            tool_mode=True,
            info="One to ten bare company domains, for example stripe.com.",
        ),
        DictInput(
            name="search_filters",
            display_name="Filters",
            advanced=True,
            info="Similar Companies API fields, such as countries and technologies. See the API reference.",
        ),
        *pagination_inputs(),
    ]
    outputs = [Output(display_name="Results", name="results", method="find_similar_companies")]

    async def find_similar_companies(self) -> Data:
        if not isinstance(self.domains, list) or not 1 <= len(self.domains) <= MAX_SEED_DOMAINS:
            msg = "Provide between one and ten company domains."
            raise ValueError(msg)
        payload = search_payload(self.search_filters, self.page, self.page_size)
        payload["domains"] = [company_domain(domain) for domain in self.domains]
        result = await request(self.api_key, "POST", "/companies/similar", timeout=self.timeout, payload=payload)
        self.status = result
        return Data(data=result)
