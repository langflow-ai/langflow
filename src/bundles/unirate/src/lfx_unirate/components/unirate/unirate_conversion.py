import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import FloatInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

CONVERT_ENDPOINT = "https://api.unirateapi.com/api/convert"
DEFAULT_BASE = "USD"


def _http_error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx UniRate response, keeping the API's own error message.

    UniRate error bodies vary; look for the common ``error``/``message``/``detail``
    keys before falling back to the HTTP reason phrase.
    """
    response = error.response
    detail = None
    try:
        payload = response.json()
        if isinstance(payload, dict):
            for key in ("error", "message", "detail"):
                value = payload.get(key)
                if isinstance(value, dict):
                    value = value.get("message") or value.get("code")
                if isinstance(value, str) and value.strip():
                    detail = value.strip()
                    break
    except ValueError:
        detail = None
    reason = detail or response.reason_phrase or "request failed"
    return f"UniRate API error {response.status_code}: {reason}"


class UniRateConversionComponent(Component):
    """Convert an amount between two currencies with live UniRate exchange rates."""

    display_name = "UniRate Currency Converter"
    description = "Convert an amount between two currencies using live rates from the UniRate API."
    documentation = "https://unirateapi.com"
    icon = "ArrowRightLeft"

    inputs = [
        MessageTextInput(
            name="to_currency",
            display_name="To Currency",
            required=True,
            info="ISO 4217 code of the target currency, for example 'EUR', 'GBP' or 'JPY'.",
            tool_mode=True,
        ),
        FloatInput(
            name="amount",
            display_name="Amount",
            value=1.0,
            required=False,
            info="Amount of the source currency to convert. Defaults to 1.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="from_currency",
            display_name="From Currency",
            value=DEFAULT_BASE,
            required=False,
            info="ISO 4217 code of the source currency. Defaults to 'USD'.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="unirate_api_key",
            display_name="UniRate API Key",
            required=True,
            info="Your UniRate API key. Get a free one at https://unirateapi.com.",
            password=True,
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode; keep it specific
        # so it does not collide with other currency/finance tools on an Agent.
        Output(display_name="Result", name="dataframe", method="convert_currency"),
    ]

    def _amount(self) -> float:
        return 1.0 if self.amount is None else float(self.amount)

    def _convert(self) -> dict:
        """Call the UniRate convert endpoint and return the decoded JSON payload."""
        if not self.unirate_api_key:
            msg = "UniRate API key is required. Set the UniRate API Key input."
            raise ValueError(msg)
        to_code = (self.to_currency or "").strip().upper()
        if not to_code:
            msg = "Target currency is required. Set the To Currency input."
            raise ValueError(msg)
        from_code = (self.from_currency or DEFAULT_BASE).strip().upper() or DEFAULT_BASE

        params = {
            "api_key": self.unirate_api_key,
            "from": from_code,
            "to": to_code,
            "amount": self._amount(),
        }
        # UniRate requires Accept: application/json; some endpoints 404 as HTML without it.
        headers = {"Accept": "application/json", "User-Agent": "langflow-unirate-bundle"}
        response = httpx.get(CONVERT_ENDPOINT, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def _error_result(self, message: str) -> list[Data]:
        error_data = [Data(text=message, data={"error": message})]
        self.status = error_data
        return error_data

    def fetch_content(self) -> list[Data]:
        """Execute the conversion and return a single Data row, or an error row."""
        try:
            payload = self._convert()
        except httpx.HTTPStatusError as e:
            return self._error_result(_http_error_message(e))
        except (httpx.HTTPError, ValueError) as e:
            return self._error_result(str(e))

        if not isinstance(payload, dict) or "result" not in payload:
            return self._error_result("UniRate API returned an unexpected response (no 'result' field).")

        try:
            result = float(payload["result"])
        except (TypeError, ValueError):
            return self._error_result("UniRate API returned a non-numeric conversion result.")

        amount = self._amount()
        rate = result / amount if amount else None
        from_code = (self.from_currency or DEFAULT_BASE).strip().upper() or DEFAULT_BASE
        to_code = (self.to_currency or "").strip().upper()
        row = Data(
            text=f"{amount:g} {from_code} = {result:g} {to_code}",
            data={
                "from": from_code,
                "to": to_code,
                "amount": amount,
                "rate": rate,
                "result": result,
            },
        )
        self.status = [row]
        return [row]

    def convert_currency(self) -> DataFrame:
        """Run the conversion and return the result as a DataFrame."""
        return DataFrame(self.fetch_content())
