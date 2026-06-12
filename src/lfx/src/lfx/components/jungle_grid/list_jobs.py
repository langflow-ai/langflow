from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._client import JungleGridClient, JungleGridError, build_query_params, optional_text
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs


class JungleGridListJobsComponent(Component):
    """List Jungle Grid jobs with cursor pagination and an optional status filter."""

    display_name = "List Jobs"
    description = "List recent Jungle Grid jobs for use with status, events, logs, runtime, or artifact components."
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridListJobs"

    inputs = [
        *auth_inputs(),
        IntInput(name="limit", display_name="Limit", value=10, tool_mode=True),
        MessageTextInput(name="cursor", display_name="Cursor", advanced=True, tool_mode=True),
        MessageTextInput(
            name="status",
            display_name="Status",
            advanced=True,
            tool_mode=True,
            info="Optional API status filter. Values are not restricted because the API does not define a fixed enum.",
        ),
    ]
    outputs = [Output(display_name="JSON", name="data", method="list_jobs")]

    async def list_jobs(self) -> Data:
        """List jobs using the API's default of 10 and maximum of 100 records."""
        limit = self.limit if self.limit is not None else 10
        if limit <= 0:
            msg = "Limit must be greater than 0."
            raise JungleGridError(msg)
        params = build_query_params(
            limit=min(limit, 100),
            cursor=optional_text(self.cursor),
            status=optional_text(self._attributes.get("status")),
        )
        result = await JungleGridClient(self.api_key, self.api_base_url).request("GET", "/v1/mcp/jobs", params=params)
        data = Data(data=result)
        self.status = data
        return data
