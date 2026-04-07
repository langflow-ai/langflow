import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post, split_csv


class PubrioUpdateMonitorComponent(Component):
    display_name = "Pubrio Update Monitor"
    description = "Update an existing signal monitor configuration."
    icon = "activity"
    name = "PubrioUpdateMonitor"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(
            name="query", display_name="Query", info="JSON with monitor_id and fields to update.", tool_mode=True
        ),
        MessageTextInput(name="monitor_id", display_name="Monitor ID", info="Monitor UUID to update."),
        MessageTextInput(name="name", display_name="Name", advanced=True),
        DropdownInput(
            name="detection_mode",
            display_name="Detection Mode",
            options=["company_first", "signal_first"],
            value="company_first",
            advanced=True,
        ),
        MessageTextInput(name="signal_types", display_name="Signal Types", advanced=True),
        DropdownInput(
            name="destination_type",
            display_name="Destination Type",
            options=["webhook", "email", "sequences"],
            value="webhook",
            advanced=True,
        ),
        MessageTextInput(name="webhook_url", display_name="Webhook URL", advanced=True),
        MessageTextInput(name="companies", display_name="Companies", advanced=True),
        MessageTextInput(name="domains", display_name="Domains", advanced=True),
        MessageTextInput(name="linkedin_urls", display_name="LinkedIn URLs", advanced=True),
        BoolInput(name="is_active", display_name="Is Active", advanced=True),
        BoolInput(name="is_paused", display_name="Is Paused", advanced=True),
        IntInput(name="frequency_minute", display_name="Frequency (Minutes)", advanced=True),
        MessageTextInput(name="notification_email", display_name="Notification Email", advanced=True),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="update"),
    ]

    def update(self) -> DataFrame:
        body: dict = {}

        if self.query:
            try:
                parsed = json.loads(self.query)
                if isinstance(parsed, dict):
                    body.update(parsed)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        if self.monitor_id:
            body["monitor_id"] = self.monitor_id

        for key in ("name", "detection_mode", "destination_type", "webhook_url", "notification_email"):
            val = getattr(self, key, None)
            if val:
                body[key] = val

        if self.signal_types:
            body["signal_types"] = split_csv(self.signal_types)
        for key in ("companies", "domains", "linkedin_urls"):
            val = getattr(self, key, None)
            if val:
                body[key] = split_csv(val)
        for key in ("is_active", "is_paused"):
            val = getattr(self, key, None)
            if val is not None:
                body[key] = val
        if self.frequency_minute is not None:
            body["frequency_minute"] = self.frequency_minute

        result = pubrio_post(self.api_key, "/monitors/update", body)
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
