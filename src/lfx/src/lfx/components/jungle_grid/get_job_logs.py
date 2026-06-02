from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._client import JungleGridClient, build_query_params, optional_text, path_segment
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs


class JungleGridGetJobLogsComponent(Component):
    display_name = "Get Job Logs"
    description = (
        "Fetch bounded stored logs for a Jungle Grid job. This component does not open the live SSE log stream."
    )
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridGetJobLogs"

    inputs = [
        *auth_inputs(),
        MessageTextInput(name="job_id", display_name="Job ID", required=True, tool_mode=True),
        IntInput(
            name="tail",
            display_name="Tail",
            advanced=True,
            tool_mode=True,
            info="Optional documented tail size.",
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            advanced=True,
            tool_mode=True,
            info="Optional documented log limit.",
        ),
        MessageTextInput(name="cursor", display_name="Cursor", advanced=True, tool_mode=True),
        DropdownInput(
            name="stream",
            display_name="Stream",
            options=["all", "stdout", "stderr"],
            value="all",
            advanced=True,
            tool_mode=True,
            info="Stored log stream to retrieve.",
        ),
    ]
    outputs = [Output(display_name="JSON", name="data", method="get_job_logs")]

    async def get_job_logs(self) -> Data:
        job_id = path_segment(self.job_id, "Job ID")
        params = build_query_params(
            tail=self.tail,
            limit=self.limit,
            cursor=optional_text(self.cursor),
            stream=None if self.stream == "all" else self.stream,
        )
        client = JungleGridClient(self.api_key, self.api_base_url)
        result = await client.request("GET", f"/v1/jobs/{job_id}/logs", params=params)
        data = Data(data=result)
        self.status = data
        return data
