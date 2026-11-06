"""List Sequenzy email campaigns."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.sequenzy.sequenzy_common import (
    DOCUMENTATION_URL,
    SequenzyAPIError,
    api_key_input,
    call_sequenzy,
    error_data,
    timeout_input,
)

ANY_STATUS = "any"
CAMPAIGN_STATUSES = [
    ANY_STATUS,
    "draft",
    "scheduled",
    "sending",
    "sent",
    "paused",
    "cancelled",
    "waiting_approval",
    "rejected",
]
MAX_LIMIT = 100


class SequenzyListCampaignsComponent(Component):
    """List campaigns with their status, subject and send dates, one row per campaign."""

    display_name = "Sequenzy List Campaigns"
    description = "List Sequenzy email campaigns with their status, subject and send dates."
    documentation = f"{DOCUMENTATION_URL}/api-reference/campaigns/list"
    icon = "Sequenzy"
    name = "SequenzyListCampaigns"

    inputs = [
        api_key_input(),
        DropdownInput(
            name="campaign_status",
            display_name="Status",
            info="Only list campaigns with this status.",
            options=CAMPAIGN_STATUSES,
            value=ANY_STATUS,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info=f"The number of campaigns to return, from 1 to {MAX_LIMIT}.",
            value=20,
            advanced=True,
        ),
        timeout_input(),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="list_campaigns_dataframe"),
    ]

    def list_campaigns(self) -> list[Data]:
        params: dict[str, object] = {"limit": min(max(int(self.limit or 1), 1), MAX_LIMIT)}
        if self.campaign_status and self.campaign_status != ANY_STATUS:
            params["status"] = self.campaign_status
        try:
            body = call_sequenzy(self, "GET", "/campaigns", params=params)
            campaigns = body.get("campaigns")
            if not isinstance(campaigns, list):
                msg = "Sequenzy API returned a campaigns response without a campaigns list."
                raise SequenzyAPIError(msg)
        except SequenzyAPIError as exc:
            return [error_data(self, str(exc))]
        data = [
            Data(text=str(item.get("name") or item.get("subject") or ""), data=item)
            for item in campaigns
            if isinstance(item, dict)
        ]
        self.status = data
        return data

    def list_campaigns_dataframe(self) -> DataFrame:
        return DataFrame(self.list_campaigns())
