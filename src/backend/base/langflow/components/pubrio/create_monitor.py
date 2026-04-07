import contextlib
import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post, split_csv


class PubrioCreateMonitorComponent(Component):
    display_name = "Pubrio Create Monitor"
    description = "Create a new signal monitor for jobs, news, or advertisements."
    icon = "activity"
    name = "PubrioCreateMonitor"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(
            name="query", display_name="Query", info="JSON with full monitor configuration.", tool_mode=True
        ),
        MessageTextInput(name="name", display_name="Monitor Name"),
        DropdownInput(
            name="detection_mode",
            display_name="Detection Mode",
            options=["company_first", "signal_first"],
            value="company_first",
        ),
        MessageTextInput(
            name="signal_types", display_name="Signal Types", info="Comma-separated: jobs, news, advertisements"
        ),
        DropdownInput(
            name="destination_type",
            display_name="Destination Type",
            options=["webhook", "email", "sequences"],
            value="webhook",
        ),
        MessageTextInput(name="webhook_url", display_name="Webhook URL", advanced=True),
        MessageTextInput(name="destination_email", display_name="Destination Email", advanced=True),
        MessageTextInput(name="description", display_name="Description", advanced=True),
        MessageTextInput(
            name="companies", display_name="Companies", info="Comma-separated domain_search_id UUIDs.", advanced=True
        ),
        MessageTextInput(name="domains", display_name="Domains", advanced=True),
        MessageTextInput(name="linkedin_urls", display_name="LinkedIn URLs", advanced=True),
        MessageTextInput(name="company_filters", display_name="Company Filters (JSON)", advanced=True),
        MessageTextInput(name="signal_filters", display_name="Signal Filters (JSON)", advanced=True),
        BoolInput(name="is_company_enrichment", display_name="Company Enrichment", value=False, advanced=True),
        BoolInput(name="is_people_enrichment", display_name="People Enrichment", value=False, advanced=True),
        IntInput(name="frequency_minute", display_name="Frequency (Minutes)", advanced=True),
        IntInput(name="max_daily_trigger", display_name="Max Daily Triggers", advanced=True),
        IntInput(name="max_records_per_trigger", display_name="Max Records Per Trigger", advanced=True),
        MessageTextInput(name="notification_email", display_name="Notification Email", advanced=True),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="create"),
    ]

    def create(self) -> DataFrame:
        body: dict = {}

        if self.query:
            try:
                parsed = json.loads(self.query)
                if isinstance(parsed, dict):
                    body.update(parsed)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        if self.name:
            body["name"] = self.name
        if self.detection_mode:
            body["detection_mode"] = self.detection_mode
        if self.signal_types:
            body["signal_types"] = split_csv(self.signal_types)
        if self.destination_type:
            body["destination_type"] = self.destination_type

        for key in ("webhook_url", "destination_email", "description", "notification_email"):
            val = getattr(self, key, None)
            if val:
                body[key] = val

        for key in ("companies", "domains", "linkedin_urls"):
            val = getattr(self, key, None)
            if val:
                body[key] = split_csv(val)

        for key in ("company_filters", "signal_filters"):
            val = getattr(self, key, None)
            if val:
                with contextlib.suppress(json.JSONDecodeError, TypeError, ValueError):
                    body[key] = json.loads(val)

        for key in ("is_company_enrichment", "is_people_enrichment"):
            val = getattr(self, key, None)
            if val is not None:
                body[key] = val

        for key in ("frequency_minute", "max_daily_trigger", "max_records_per_trigger"):
            val = getattr(self, key, None)
            if val is not None:
                body[key] = val

        result = pubrio_post(self.api_key, "/monitors/create", body)
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
