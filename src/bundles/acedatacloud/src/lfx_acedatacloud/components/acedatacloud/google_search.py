"""Google Search components."""

from lfx_acedatacloud.components.base import (
    AceGenerationComponent,
    generation_inputs,
)


class GoogleSearchComponent(AceGenerationComponent):
    display_name = "Google Search"
    description = "Run the Ace Data Cloud Google Search first-run API action."
    icon = "Bot"
    service_name = "google_search"
    inputs = generation_inputs("google_search")
