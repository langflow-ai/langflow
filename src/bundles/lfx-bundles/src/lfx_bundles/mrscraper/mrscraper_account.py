"""MrScraper Status, retaining the existing MrscraperAccount identifier."""

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import (
    api_token_input,
    call_sdk,
    payload,
    redact_token,
    require_updated_node,
)


def _public_fields(record: Any, fields: dict[str, type], token: str) -> dict[str, Any]:
    """Copy only the expected scalar types from explicitly supported fields."""
    if not isinstance(record, dict):
        return {}
    public_fields = {}
    for key, field_type in fields.items():
        value = record.get(key)
        if type(value) is field_type:
            public_fields[key] = redact_token(value, token) if isinstance(value, str) else value
    return public_fields


def _account_details(record: Any, token: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    details = _public_fields(
        record,
        {
            "tokenLimit": int,
            "tokenUsage": int,
            "stripeStatus": str,
            "rateLimit": int,
            "rateTtl": int,
            "isEnterprise": bool,
            "isAutoRenew": bool,
            "endsAt": str,
        },
        token,
    )
    subscription = _public_fields(record.get("subscriptionItem"), {"name": str, "tokenLimit": int}, token)
    if subscription:
        details["subscriptionItem"] = subscription
    allowance = record.get("scraperAllowance")
    if isinstance(allowance, dict):
        public_allowance = _public_fields(allowance, {"remaining": int}, token)
        if isinstance(plans := allowance.get("plans"), list):
            public_allowance["plans"] = [
                public_plan for plan in plans if (public_plan := _public_fields(plan, {"remaining": int}, token))
            ]
        details["scraperAllowance"] = public_allowance
    return details


class MrscraperAccount(Component):
    """Return account usage, rate limits, and subscription status."""

    display_name: str = "MrScraper Status"
    description: str = "Check token usage, rate limits, and subscription status."
    name = "MrscraperAccount"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [api_token_input()]

    outputs = [Output(display_name="Account Status", name="data", method="get_account")]

    async def get_account(self) -> Data:
        """Fetch the public status fields for this token's account."""
        require_updated_node(self, "timeout")
        result = await call_sdk(self.api_token, "status")
        body = payload(result)
        return Data(data={"data": _account_details(body.get("data", body), self.api_token)})
