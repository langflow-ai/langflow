from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_publora.components.publora._publora_api import PubloraAPIError, publora_request

CONNECTION_FIELDS = ("platformId", "username", "displayName", "connectionStatus", "tokenStatus", "tokenExpiresIn")


class PubloraListConnectionsComponent(Component):
    """List the social accounts connected to a Publora account."""

    display_name = "Publora List Connections"
    description = "List the social accounts connected to Publora, with the platformId to post to."
    documentation = "https://docs.publora.com/endpoints/platform-connections"
    icon = "send"

    inputs = [
        SecretStrInput(
            name="publora_api_key",
            display_name="Publora API Key",
            required=True,
            info="Your Publora API key, from the API page of your Publora dashboard (app.publora.com/dashboard/api).",
            password=True,
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode; keep it product-specific.
        Output(display_name="Connections", name="connections", method="publora_list_connections"),
    ]

    def _error_result(self, message: str) -> list[Data]:
        error_data = [Data(text=message, data={"error": message})]
        self.status = error_data
        return error_data

    @staticmethod
    def _connection_to_data(connection: dict) -> Data:
        fields = {field: connection.get(field) for field in CONNECTION_FIELDS}
        label = fields["displayName"] or fields["username"] or ""
        return Data(text=f"{fields['platformId']} ({label})".strip(), data=fields)

    def fetch_connections(self) -> list[Data]:
        """Return one Data row per connected social account."""
        try:
            payload = publora_request("GET", "/platform-connections", self.publora_api_key)
        except PubloraAPIError as e:
            return self._error_result(str(e))

        connections = payload.get("connections") or []
        rows = [self._connection_to_data(c) for c in connections if isinstance(c, dict)]
        self.status = rows
        return rows

    def publora_list_connections(self) -> DataFrame:
        """List the connected social accounts as a table."""
        return DataFrame(self.fetch_connections())
