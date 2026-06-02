from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data

from ._client import JungleGridClient, build_workload_payload
from ._shared import DOCUMENTATION_URL, ICON, auth_inputs, workload_inputs


class JungleGridEstimateJobComponent(Component):
    display_name = "Estimate Job"
    description = (
        "Estimate routing, availability, queue timing, and cost for a Jungle Grid workload without starting execution."
    )
    documentation = DOCUMENTATION_URL
    icon = ICON
    name = "JungleGridEstimateJob"

    inputs = [*auth_inputs(), *workload_inputs()]
    outputs = [Output(display_name="JSON", name="data", method="estimate_job")]

    async def estimate_job(self) -> Data:
        payload = build_workload_payload(
            name=self._attributes.get("name"),
            image=self.image,
            workload_type=self.workload_type,
            model_size_gb=self.model_size_gb,
            command=self.command,
            args=self.args,
            optimize_for=self.optimize_for,
        )
        client = JungleGridClient(self.api_key, self.api_base_url)
        result = await client.request("POST", "/v1/jobs/estimate", json_body=payload)
        data = Data(data=result)
        self.status = data
        return data
