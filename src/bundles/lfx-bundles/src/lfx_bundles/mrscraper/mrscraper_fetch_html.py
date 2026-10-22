"""MrScraper Scraper API, retaining the existing component identifier."""

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import call_sdk, optional_integer, payload


class MrscraperFetchHtml(Component):
    """Fetch HTML, Markdown, and screenshots through the current SDK."""

    display_name: str = "MrScraper Scraper API"
    description: str = "Fetch a public web page as rendered HTML, Markdown, screenshot, or a combination"
    name = "MrscraperFetchHtml"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [
        SecretStrInput(
            name="api_token",
            display_name="MrScraper API Token",
            required=True,
            password=True,
            info="Your MrScraper API token. Get yours at https://app.mrscraper.com.",
        ),
        MultilineInput(
            name="url",
            display_name="URL",
            required=True,
            info="Target page URL to retrieve.",
            tool_mode=True,
        ),
        BoolInput(name="html", display_name="HTML", value=True),
        BoolInput(name="markdown", display_name="Markdown", value=False),
        BoolInput(
            name="screenshot",
            display_name="Screenshot",
            value=False,
            info="Capture a screenshot. This also enables browser rendering.",
        ),
        DropdownInput(
            name="browser_rendering",
            display_name="Browser Rendering",
            value="Auto",
            options=["Auto", "Enabled", "Disabled"],
            advanced=True,
            info="Auto tries without a browser first, then falls back to browser rendering.",
        ),
        BoolInput(
            name="super",
            display_name="Super",
            value=False,
            advanced=True,
            info="Enable real device routing independently of browser rendering.",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=120,
            info="Page timeout from 1 to 300 seconds. The HTTP deadline adds 30 seconds.",
            advanced=True,
        ),
        StrInput(
            name="geo_code",
            display_name="Geo Code",
            value="US",
            info='ISO country code for proxy geolocation (e.g. "US", "GB", "ID", "SG").',
            advanced=True,
        ),
        BoolInput(
            name="block_resources",
            display_name="Block Resources",
            value=False,
            info="Block images, CSS, and fonts to speed up the request.",
            advanced=True,
        ),
        StrInput(name="proxy_country", display_name="Proxy Country", advanced=True),
        BoolInput(name="use_proxy", display_name="Use Proxy", value=True, advanced=True),
        SecretStrInput(
            name="proxy",
            display_name="Custom Proxy",
            advanced=True,
            password=True,
            info="Optional proxy in username:password@host:port form.",
        ),
        BoolInput(name="bypass_proxy", display_name="Bypass Proxy", value=False, advanced=True),
        StrInput(name="wait_for_selector", display_name="Wait for Selector", advanced=True),
        BoolInput(
            name="home_page",
            display_name="Visit Home Page First",
            value=False,
            advanced=True,
            info="Visit the site's root first; sent as warmStart=true.",
        ),
        StrInput(
            name="cookie_jar",
            display_name="Cookie Jar",
            advanced=True,
            info="Cookie configuration, for example domain=example.com&country=us&max_used=100&max_age=50m.",
        ),
        MultilineInput(
            name="headers",
            display_name="Target Headers",
            advanced=True,
            info='Optional target request headers as a JSON object, for example {"accept-language": "en-US"}.',
        ),
        IntInput(name="max_retries", display_name="Max Retries", value=3, advanced=True),
        StrInput(
            name="token_cap",
            display_name="Token Cap",
            value="",
            advanced=True,
            info="Optional nonnegative retry token budget. Leave empty for no cap.",
        ),
        DropdownInput(
            name="stream",
            display_name="Stream",
            options=["Auto", "Enabled", "Disabled"],
            value="Auto",
            advanced=True,
            info="Request streaming; the SDK buffers the complete response.",
        ),
        SecretStrInput(
            name="discard_token_secret",
            display_name="Discard Token Secret",
            password=True,
            advanced=True,
            info="Optional x-discard-token-secret request header.",
        ),
    ]

    outputs = [
        Output(display_name="Page Content", name="data", method="fetch"),
    ]

    async def fetch(self) -> Data:
        """Call Scraper API and return its payload, preserving the legacy HTML key."""
        optional_boolean = {"Auto": None, "Enabled": True, "Disabled": False}
        result = await call_sdk(
            self.api_token,
            "scraper_api",
            url=self.url,
            html=self.html,
            markdown=self.markdown,
            screenshot=self.screenshot,
            browser_rendering=optional_boolean[self.browser_rendering],
            super=self.super,
            timeout=self.timeout,
            geo_code=self.geo_code or "US",
            block_resources=self.block_resources,
            proxy_country=self.proxy_country or None,
            use_proxy=self.use_proxy,
            proxy=self.proxy or None,
            bypass_proxy=self.bypass_proxy,
            wait_for_selector=self.wait_for_selector or None,
            home_page=self.home_page,
            cookie_jar=self.cookie_jar or None,
            headers=self.headers or None,
            max_retries=self.max_retries,
            token_cap=optional_integer(self.token_cap, name="token_cap"),
            stream=optional_boolean[self.stream],
            discard_token_secret=self.discard_token_secret or "",
        )
        return Data(data=payload(result, scalar_key="html"))
