"""Read one fax: its state and, once delivered or partial, the carrier's evidence."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.faxforagents._common import DEFAULT_BASE_URL, agent_evidence, call_api, error_data, require_id

STATE_MESSAGES = {
    "queued": "queued: accepted, waiting for the worker.",
    "active": "at the carrier. Read the status again later.",
    "delivered": "delivered: every page arrived and the carrier's evidence is attached.",
    "partial": "partial: only some pages arrived. No automatic retransmit, a human decides.",
    "failed": "failed: nothing arrived. The hold was released.",
    "unknown": "outcome unknown: the carrier gave no answer. Nothing retransmits on its own.",
}


class FaxForAgentsFaxStatusComponent(Component):
    display_name = "Get Fax Status"
    description = (
        "The state of one fax sent through Fax for Agents: queued, active, delivered, partial, failed or "
        "unknown, with the carrier's evidence once delivered or partial."
    )
    documentation: str = "https://faxforagents.com/docs/api/"
    icon = "FaxForAgents"
    name = "FaxForAgentsFaxStatusComponent"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Fax for Agents API Key",
            info="From app.faxforagents.com.",
            required=True,
        ),
        MessageTextInput(
            name="fax_id",
            display_name="Fax ID",
            info="The fax id from Send Fax, fax_ followed by 32 hex characters.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="API base URL",
            value=DEFAULT_BASE_URL,
            info="Only change it to point the component at a test double.",
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Status", name="status_data", method="read")]

    async def read(self) -> Data:
        try:
            fax_id = require_id(self.fax_id, "Fax ID")
            job = agent_evidence(
                await call_api(self.api_key, "GET", f"/v1/faxes/{fax_id}", base_url=self.base_url or DEFAULT_BASE_URL)
            )
            state = str(job.get("state"))
            summary = f"Fax {job.get('id')} to {job.get('to')} is {STATE_MESSAGES.get(state, state)}"
            if state in ("failed", "partial") and job.get("failure_code"):
                summary += f" Reason: {job['failure_code']}."
            if isinstance(job.get("evidence"), dict):
                summary += (
                    f" Evidence from {job.get('provider')}: {job.get('pages_sent')} of {job.get('billable_pages')} "
                    "page(s). It is what the carrier reported, not legal proof the recipient accepted it."
                )
            result = {
                "fax_id": job.get("id"),
                "state": state,
                "pages_sent": job.get("pages_sent"),
                "billable_pages": job.get("billable_pages"),
                "failure_code": job.get("failure_code"),
                "summary": summary,
                "fax": job,
            }
        except Exception as exc:  # noqa: BLE001
            await logger.aexception("Fax for Agents: status read failed")
            result = error_data(exc)
        self.status = result
        return Data(data=result)
