from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from lfx_arcmira.client import read


class ArcmiraTranscriptSearch(Component):
    display_name = "Arcmira Search"
    description = (
        "Find the moment something was said on YouTube, including podcasts on YouTube: the exact "
        "quote, often who said it, the channel, the date and a watch link cued to the second. "
        "Filter by who is speaking, by the person or company discussed, and by sponsored or organic"
        " passages. Use one topic per call, and resolve names to ids before filtering. An empty "
        "result does not prove something was never said."
    )
    documentation = "https://arcmira.com/docs/search"
    icon = "Search"
    name = "ArcmiraTranscriptSearch"
    inputs = [
        SecretStrInput(name="api_key", display_name="Arcmira API key", required=True),
        MessageTextInput(
            name="query",
            display_name="Query",
            required=True,
            tool_mode=True,
            info="One topic or phrase, at least 2 characters.",
        ),
        IntInput(
            name="limit",
            display_name="Maximum passages",
            value=5,
            info="1 to 20 passages. The first 5 use no credits; each one past 5 uses 4.",
        ),
        DropdownInput(
            name="source",
            display_name="Transcript source",
            value="",
            options=["", "arcmira_premium", "creator_captions", "third_party_quick"],
            info=(
                "Leave blank to omit the source filter. Premium restricts results to Premium; access "
                "refusals are preserved."
            ),
        ),
        MessageTextInput(name="channel_ids", display_name="Channel IDs", advanced=True),
        MessageTextInput(name="entity_ids", display_name="Entity IDs", advanced=True),
        MessageTextInput(name="about", display_name="Mentioned entity IDs", advanced=True),
        MessageTextInput(
            name="by",
            display_name="Speaker person IDs",
            advanced=True,
            info="Resolve names first. Speaker labels have limited coverage.",
        ),
        MessageTextInput(
            name="kind",
            display_name="Passage kinds",
            advanced=True,
            info="Comma-separated sponsored, organic, mention.",
        ),
        MessageTextInput(
            name="after",
            display_name="Published at or after",
            advanced=True,
            info="ISO8601 date or offset datetime. Account access applies.",
        ),
        MessageTextInput(
            name="before",
            display_name="Published before",
            advanced=True,
            info="Exclusive ISO8601 date or offset datetime. Account access applies.",
        ),
    ]
    outputs = [Output(display_name="Complete response", name="response", method="search_transcripts")]

    async def search_transcripts(self) -> Data:
        params = {
            name: getattr(self, name, None)
            for name in ("limit", "source", "channel_ids", "entity_ids", "about", "by", "kind", "after", "before")
        }
        params["q"] = self.query
        response = await read(self.api_key, "search", params)
        return Data(data=response)
