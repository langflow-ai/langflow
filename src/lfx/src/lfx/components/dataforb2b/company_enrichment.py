"""DataForB2B — Company Enrichment component for Langflow.

Enrich a company (firmographics) from a domain, name or LinkedIn URL.
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from ._client import DataForB2BClient


class DataForB2BCompanyEnrichmentComponent(Component):
    display_name = "Enrich Company"
    description = (
        "Look up and enrich a company using DataForB2B — firmographics, "
        "headcount/size, industry, domain, social and LinkedIn URL — from a company "
        "domain, name or LinkedIn URL. Account enrichment for B2B sales and CRM."
    )
    documentation = "https://docs.dataforb2b.ai"
    icon = "DataForB2B"
    name = "DataForB2BCompanyEnrichment"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="DataForB2B API Key",
            required=True,
            info="Your DataForB2B API key (header api_key). Get one at https://app.dataforb2b.ai.",
        ),
        MessageTextInput(
            name="company_identifier",
            display_name="Company identifier",
            value="",
            tool_mode=True,
            info="Company domain, name, or LinkedIn URL to enrich.",
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="enrich"),
    ]

    def enrich(self) -> Data:
        if not self.company_identifier:
            msg = "'company_identifier' is required."
            raise ValueError(msg)
        data = DataForB2BClient(self.api_key).enrich_company(self.company_identifier)
        self.status = "Enriched"
        return Data(data=data)
