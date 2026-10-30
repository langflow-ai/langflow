from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output

from lfx_famulor.components.famulor._client import (
    MAX_PAGE_SIZE,
    api_key_input,
    clamp_page,
    error_message,
    guard,
    page_total,
    request_json,
    unwrap_data,
)

_CAMPAIGN_FIELDS = ("id", "name", "status", "channel", "assistant_id", "timezone", "updated_at")
_ALL_STATUSES = "all"
_STATUS_OPTIONS = [_ALL_STATUSES, "draft", "running", "paused", "completed", "archived"]


class FamulorListCampaignsComponent(Component):
    """List Famulor campaigns in the workspace."""

    display_name = "Famulor List Campaigns"
    description = "List Famulor campaigns, optionally filtered by status."
    documentation = "https://docs.famulor.io/api-reference/campaigns/list-campaigns"
    icon = "Famulor"

    inputs = [
        api_key_input(),
        DropdownInput(
            name="campaign_status",
            display_name="Status",
            options=_STATUS_OPTIONS,
            value=_ALL_STATUSES,
            required=False,
            info="Campaign status filter. All leaves the filter off.",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            value=50,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=1, max=MAX_PAGE_SIZE, step=1, step_type="int"),
            info="Page size, from 1 to 200. Default: 50.",
            tool_mode=True,
        ),
        IntInput(
            name="offset",
            display_name="Offset",
            value=0,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=0, max=100000, step=1, step_type="int"),
            info="Number of campaigns to skip. Default: 0.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Campaigns", name="campaigns", method="famulor_list_campaigns"),
        Output(display_name="Table", name="dataframe", method="famulor_list_campaigns_table", tool_mode=False),
        Output(display_name="Message", name="message", method="famulor_list_campaigns_message", tool_mode=False),
    ]

    def _load_page(self) -> Data:
        limit, offset = clamp_page(self.limit, self.offset)
        params: dict = {"limit": limit, "offset": offset}
        status = (self.campaign_status or "").strip()
        if status and status != _ALL_STATUSES:
            if status not in _STATUS_OPTIONS:
                msg = f"Status must be one of: {', '.join(_STATUS_OPTIONS)}."
                raise ValueError(msg)
            params["status"] = status
        payload = request_json("GET", "/campaigns", self.famulor_api_key, params=params)
        rows, meta = unwrap_data(payload)
        if not isinstance(rows, list):
            msg = "Famulor API returned an unexpected response (expected a list of campaigns)."
            raise TypeError(msg)
        items = [_campaign_row(row) for row in rows if isinstance(row, dict)]
        total = page_total(meta, len(items))
        text = f"Showing {len(items)} campaigns (total {total})."
        return Data(
            text=text,
            data={"items": items, "limit": limit, "offset": offset, "total": total, "status": status or _ALL_STATUSES},
        )

    def famulor_list_campaigns(self) -> Data:
        """List campaigns and return the page, including the total count."""
        result = guard(self._load_page)
        self.status = result
        return result

    def famulor_list_campaigns_table(self) -> DataFrame:
        """List campaigns and return one table row per campaign."""
        result = self.famulor_list_campaigns()
        if isinstance(result.data, dict) and "error" in result.data:
            return DataFrame([result])
        items = result.data.get("items", []) if isinstance(result.data, dict) else []
        return DataFrame(items)

    def famulor_list_campaigns_message(self) -> Message:
        """List campaigns and return a one-line count."""
        return error_message(self.famulor_list_campaigns())


def _campaign_row(row: dict) -> dict:
    return {field: row.get(field) for field in _CAMPAIGN_FIELDS}
