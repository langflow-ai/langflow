from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._client import context_api_key_input, request_context


class ContextRetrieveBrandComponent(Component):
    display_name = "Context.dev Retrieve Brand"
    description = "Retrieve logos, colors, fonts, company metadata, and social links for a brand."
    documentation = "https://docs.context.dev/api-reference/brand-intelligence/brand"
    icon = "Context"

    inputs = [
        context_api_key_input(),
        DropdownInput(
            name="identifier_type",
            display_name="Brand Identifier",
            options=["domain", "name", "ticker"],
            value="domain",
        ),
        MessageTextInput(
            name="identifier",
            display_name="Identifier Value",
            info="Brand domain, company name, or stock ticker, matching the selected identifier type.",
            required=True,
            tool_mode=True,
        ),
        BoolInput(
            name="max_speed",
            display_name="Prioritize Speed",
            info="Return faster with less comprehensive enrichment.",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Brand Data", name="brand", method="retrieve_brand")]

    async def retrieve_brand(self) -> Data:
        response = await request_context(
            "GET",
            "/brand/retrieve",
            self.api_key,
            params={
                str(self.identifier_type): str(self.identifier).strip(),
                "maxSpeed": self.max_speed,
            },
        )
        self.status = response
        return Data(data=response)
