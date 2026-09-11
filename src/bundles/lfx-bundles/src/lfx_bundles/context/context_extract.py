from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, DictInput, IntInput, MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data

from ._client import context_api_key_input, defined_values, request_context


class ContextExtractStructuredDataComponent(Component):
    display_name = "Context.dev Extract Structured Data"
    description = "Extract structured data from a website using a JSON Schema."
    documentation = "https://docs.context.dev/api-reference/web-extraction/extract"
    icon = "Context"

    inputs = [
        context_api_key_input(),
        MessageTextInput(name="url", display_name="Starting URL", required=True, tool_mode=True),
        DictInput(
            name="schema",
            display_name="JSON Schema",
            info="JSON Schema describing the object to extract.",
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="instructions",
            display_name="Extraction Instructions",
            info="Optional guidance about which facts to prioritize.",
            advanced=True,
        ),
        BoolInput(name="fact_check", display_name="Fact Check", value=True, advanced=True),
        IntInput(
            name="max_pages",
            display_name="Maximum Pages",
            value=5,
            range_spec=RangeSpec(min=1, max=50, step=1, step_type="int"),
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Extracted Data", name="result", method="extract")]

    async def extract(self) -> Data:
        payload = defined_values(
            {
                "url": str(self.url).strip(),
                "schema": dict(self.schema),
                "instructions": str(self.instructions).strip() or None,
                "factCheck": self.fact_check,
                "maxPages": self.max_pages,
            }
        )
        response = await request_context("POST", "/web/extract", self.api_key, json=payload)
        self.status = response
        return Data(data=response)
