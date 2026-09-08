from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._client import context_api_key_input, request_context


class ContextCrawlWebsiteComponent(Component):
    display_name = "Context.dev Crawl Website"
    description = "Crawl a website and return clean Markdown for each discovered page."
    documentation = "https://docs.context.dev/api-reference/web-scraping/crawl"
    icon = "Context"

    inputs = [
        context_api_key_input(),
        MessageTextInput(
            name="url",
            display_name="Starting URL",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_pages",
            display_name="Maximum Pages",
            value=10,
            range_spec=RangeSpec(min=1, max=500, step=1, step_type="int"),
        ),
        IntInput(
            name="max_depth",
            display_name="Maximum Depth",
            value=2,
            range_spec=RangeSpec(min=0, max=20, step=1, step_type="int"),
        ),
        BoolInput(name="use_main_content_only", display_name="Main Content Only", value=True, advanced=True),
        BoolInput(name="follow_subdomains", display_name="Follow Subdomains", value=False, advanced=True),
    ]

    outputs = [Output(display_name="Crawl Results", name="results", method="crawl")]

    async def crawl(self) -> Data:
        payload = {
            "url": str(self.url).strip(),
            "maxPages": self.max_pages,
            "maxDepth": self.max_depth,
            "useMainContentOnly": self.use_main_content_only,
            "followSubdomains": self.follow_subdomains,
        }
        response = await request_context("POST", "/web/crawl", self.api_key, json=payload)
        self.status = response
        return Data(data=response)
