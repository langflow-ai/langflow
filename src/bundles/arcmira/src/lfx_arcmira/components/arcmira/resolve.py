from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from lfx_arcmira.client import read


class ArcmiraEntityResolve(Component):
    display_name = "Arcmira Resolve"
    description = "Resolve names while preserving candidates, confidence and clarification. No automatic selection."
    documentation = "https://arcmira.com/docs/search"
    icon = "Users"
    name = "ArcmiraEntityResolve"
    inputs = [
        SecretStrInput(name="api_key", display_name="Arcmira API key", required=True),
        MessageTextInput(name="query", display_name="Name or handle", required=True, tool_mode=True),
        MessageTextInput(
            name="context",
            display_name="Context",
            advanced=True,
            info="Optional disambiguating context, 2-300 characters.",
        ),
        DropdownInput(
            name="entity_type",
            display_name="Entity type",
            value="",
            options=["", "person", "organization", "product", "topic", "channel"],
        ),
        IntInput(name="limit", display_name="Maximum candidates", value=8),
    ]
    outputs = [Output(display_name="Complete resolution", name="response", method="resolve_entity")]

    async def resolve_entity(self) -> Data:
        response = await read(
            self.api_key,
            "entities/resolve",
            {
                "q": self.query,
                "context": self.context,
                "type": self.entity_type,
                "limit": self.limit,
            },
        )
        return Data(data=response)
