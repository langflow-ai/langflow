from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_asyntai.components.asyntai.asyntai_common import AsyntaiAPIError, asyntai_request, clean_text

DEFAULT_LIMIT = 50
MIN_LIMIT = 1
MAX_LIMIT = 100
LEAD_FIELDS = ("email", "phone", "page_url", "started_at", "session_id")


class AsyntaiLeadsComponent(Component):
    """List the leads that visitors left in the Asyntai AI chatbot."""

    display_name = "Asyntai Leads"
    description = "List the leads (email addresses and phone numbers) that visitors left in the Asyntai AI chatbot."
    documentation = "https://asyntai.com/documentation/integrations/langflow/"
    icon = "users"

    inputs = [
        SecretStrInput(
            name="asyntai_api_key",
            display_name="Asyntai API Key",
            required=True,
            info="Your Asyntai API key. Create one in the Asyntai dashboard under Settings -> API.",
            password=True,
        ),
        MessageTextInput(
            name="since",
            display_name="Since",
            required=False,
            info="Only leads from this date or later, for example '2026-01-31'. Leave empty for the newest leads.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="website",
            display_name="Website",
            required=False,
            advanced=True,
            info="Website ID or domain, for example 'example.com'. Leave empty for all websites of the account.",
        ),
        IntInput(
            name="limit",
            display_name="Max Leads",
            value=DEFAULT_LIMIT,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=MIN_LIMIT, max=MAX_LIMIT, step=1, step_type="int"),
            info="Maximum number of leads to return (1-100), newest first.",
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="asyntai_get_leads"),
    ]

    def _params(self) -> dict:
        requested = DEFAULT_LIMIT if self.limit is None else int(self.limit)
        params: dict = {"limit": max(MIN_LIMIT, min(requested, MAX_LIMIT))}
        website = clean_text(self.website)
        if website:
            params["website_id"] = website
        since = clean_text(self.since)
        if since:
            params["since"] = since
        return params

    @staticmethod
    def _lead_to_data(lead: dict) -> Data:
        row = {field: lead.get(field) or "" for field in LEAD_FIELDS}
        contact = row["email"] or row["phone"]
        text = f"{contact} on {row['page_url']}" if row["page_url"] else contact
        return Data(text=text, data=row)

    def fetch_leads(self) -> list[Data]:
        """Return the leads as Data rows, or one error row."""
        try:
            payload = asyntai_request("GET", "/leads/", self.asyntai_api_key, params=self._params())
        except AsyntaiAPIError as exc:
            error_rows = [Data(text=str(exc), data={"error": str(exc)})]
            self.status = error_rows
            return error_rows
        leads = payload.get("leads") or []
        rows = [self._lead_to_data(lead) for lead in leads if isinstance(lead, dict)]
        self.status = rows
        return rows

    def asyntai_get_leads(self) -> DataFrame:
        """Return the leads as a table."""
        return DataFrame(self.fetch_leads())
