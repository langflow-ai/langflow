from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._client import JungleGridClient, JungleGridError, build_query_params, optional_text, path_segment
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs


class JungleGridGetJobLogsComponent(Component):
    """Retrieve persisted paginated workload and runtime logs."""

    display_name = "Get Job Logs"
    description = (
        "Retrieve paginated persisted logs. Logs may be empty before workload execution; use Get Job Events for "
        "platform scheduling and startup progress. Polling this endpoint is not true streaming."
    )
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridGetJobLogs"

    inputs = [
        *auth_inputs(),
        MessageTextInput(name="job_id", display_name="Job ID", required=True, tool_mode=True),
        IntInput(
            name="limit",
            display_name="Limit",
            value=100,
            advanced=True,
            tool_mode=True,
            info="Page size. The API caps this value at 1000.",
        ),
        MessageTextInput(name="cursor", display_name="Cursor", advanced=True, tool_mode=True),
    ]
    outputs = [Output(display_name="JSON", name="data", method="get_job_logs")]

    async def get_job_logs(self) -> Data:
        """Return one current log page without obsolete tail or stream parameters."""
        job_id = path_segment(self.job_id, "Job ID")
        limit = self.limit if self.limit is not None else 100
        if limit <= 0:
            msg = "Limit must be greater than 0."
            raise JungleGridError(msg)
        params = build_query_params(
            limit=min(limit, 1000),
            cursor=optional_text(self.cursor),
        )
        client = JungleGridClient(self.api_key, self.api_base_url)
        result = await client.request("GET", f"/v1/mcp/jobs/{job_id}/logs", params=params)
        data = Data(data=result)
        self.status = data
        return data
