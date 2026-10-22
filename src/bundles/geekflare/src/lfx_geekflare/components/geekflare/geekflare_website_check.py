from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output

from ._api import GeekflareAPIError, call_api, normalize_url

# check -> Geekflare endpoint path
CHECKS = {
    "site_status": "up",
    "dns_records": "dnsrecord",
    "dnssec": "dnssec",
    "tls_scan": "tlsscan",
    "redirect_check": "redirectcheck",
    "broken_links": "brokenlink",
    "load_time": "loadtime",
    "mixed_content": "mixedcontent",
    "lighthouse": "lighthouse",
}


class GeekflareWebsiteCheckComponent(Component):
    """Run a website diagnostic with Geekflare."""

    display_name = "Geekflare Website Check"
    description = (
        "Check a website with Geekflare: uptime, DNS records, DNSSEC, TLS/SSL, redirect chain, "
        "broken links, load time, mixed content, or a Lighthouse audit."
    )
    documentation = "https://docs.geekflare.com"
    icon = "shield-check"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="URL",
            required=True,
            info="Website URL or domain, for example example.com.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="geekflare_api_key",
            display_name="Geekflare API Key",
            required=True,
            info="Your Geekflare API key. Get one at https://dash.geekflare.com.",
            password=True,
        ),
        DropdownInput(
            name="check",
            display_name="Check",
            options=list(CHECKS),
            value="site_status",
            info="Which check to run. lighthouse is slow (a minute or more).",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="geekflare_website_check"),
    ]

    def geekflare_website_check(self) -> Data:
        """Run the selected check and return the API result as Data."""
        check = self.check or "site_status"
        if check not in CHECKS:
            message = f"Unknown check '{check}'. Use one of: {', '.join(CHECKS)}."
            result = Data(text=message, data={"error": message})
            self.status = result
            return result
        try:
            payload = call_api(self.geekflare_api_key, CHECKS[check], {"url": normalize_url(self.url)})
        except GeekflareAPIError as e:
            result = Data(text=str(e), data={"error": str(e)})
            self.status = result
            return result
        result = Data(data={"check": check, **payload})
        self.status = result
        return result
