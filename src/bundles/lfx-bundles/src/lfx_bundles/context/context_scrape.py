from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._client import context_api_key_input, request_context


class ContextScrapeMarkdownComponent(Component):
    display_name = "Context.dev Scrape Markdown"
    description = "Turn a webpage, PDF, Office document, or YouTube transcript into clean Markdown."
    documentation = "https://docs.context.dev/api-reference/web-scraping/markdown"
    icon = "Context"

    inputs = [
        context_api_key_input(),
        MessageTextInput(
            name="url",
            display_name="URL",
            info="Webpage, document, or YouTube URL to convert to Markdown.",
            required=True,
            tool_mode=True,
        ),
        BoolInput(name="use_main_content_only", display_name="Main Content Only", value=True),
        BoolInput(name="include_links", display_name="Include Links", value=True, advanced=True),
        BoolInput(name="include_images", display_name="Include Images", value=False, advanced=True),
        IntInput(
            name="max_age_ms",
            display_name="Maximum Cache Age (ms)",
            value=86_400_000,
            range_spec=RangeSpec(min=0, max=2_592_000_000, step=1, step_type="int"),
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Markdown", name="markdown", method="scrape")]

    async def scrape(self) -> Data:
        response = await request_context(
            "GET",
            "/web/scrape/markdown",
            self.api_key,
            params={
                "url": str(self.url).strip(),
                "useMainContentOnly": self.use_main_content_only,
                "includeLinks": self.include_links,
                "includeImages": self.include_images,
                "maxAgeMs": self.max_age_ms,
            },
        )
        self.status = response.get("markdown", "")
        return Data(text=response.get("markdown", ""), data=response)
